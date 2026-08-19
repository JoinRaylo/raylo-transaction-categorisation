{{
  config(
    materialized='incremental',
    unique_key=['transaction_id'],
    partition_by = {
        "field": "search_date",
        "data_type": "timestamp",
        "granularity": "day"
    },
    incremental_strategy = 'insert_overwrite',
    tags=['daily']
  )
}}

WITH raw_data AS (
    SELECT
        ID AS account_score_result_id,
        ClientApplicationID AS client_application_id,
        ClientApplicationReference AS client_application_reference,
        ClientCustomerReference AS client_customer_reference,
        SearchDate AS search_date,
        ResponseXML AS response_xml
    FROM {{ source('landing_sentinel_proposal_v2', 'AccountScoreResults') }}
    WHERE
        ResultStatus = 1
        AND ResponseXML IS NOT NULL
        AND SearchDate >= '2024-01-01'

        {% if is_incremental() %}
        AND date(SearchDate) >= date_sub(date(_dbt_max_partition), interval 7 day)
        {% endif %}
),

-- Split each ResponseXML blob into one row per <transactions>...</transactions> block.
-- (s) makes `.` match newlines, in case the source has any embedded line breaks.
transaction_blocks AS (
    SELECT
        r.* EXCEPT(response_xml),
        block
    FROM raw_data r,
    UNNEST(REGEXP_EXTRACT_ALL(response_xml, r'(?s)<transactions>(.*?)</transactions>')) AS block
),

tx AS (
    SELECT
        search_date,
        account_score_result_id,
        client_application_id,
        client_application_reference,
        client_customer_reference,

        REGEXP_EXTRACT(block, r'(?s)<accountId>(.*?)</accountId>') AS account_id,
        REGEXP_EXTRACT(block, r'(?s)<bankName>(.*?)</bankName>') AS bank_name,
        REGEXP_EXTRACT(block, r'(?s)<primaryCategoryDescription>(.*?)</primaryCategoryDescription>') AS primary_category_description,
        REGEXP_EXTRACT(block, r'(?s)<subCategoryDescription>(.*?)</subCategoryDescription>') AS sub_category_description,
        REGEXP_EXTRACT(block, r'(?s)<vendorDescription>(.*?)</vendorDescription>') AS vendor_description,
        REGEXP_EXTRACT(block, r'(?s)<description>(.*?)</description>') AS description,
        REGEXP_EXTRACT(block, r'(?s)<postDate>(.*?)</postDate>') AS post_date_raw,
        REGEXP_EXTRACT(block, r'(?s)<direction>(.*?)</direction>') AS direction,
        SAFE_CAST(REGEXP_EXTRACT(block, r'(?s)<amount>(.*?)</amount>') AS FLOAT64) AS amount,
        SAFE_CAST(REGEXP_EXTRACT(block, r'(?s)<runningBalance>(.*?)</runningBalance>') AS FLOAT64) AS running_balance

    FROM transaction_blocks
),

tx_typed AS (
    SELECT
        *,
        SAFE.PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*S%Ez', post_date_raw) AS post_date,
        -- Synthetic key: AccountScore gives no native transaction_id.
        -- Revisit if collision rate turns out non-trivial once this is running for real.
        TO_HEX(SHA256(CONCAT(
            IFNULL(account_id, ''), '|', IFNULL(post_date_raw, ''), '|',
            IFNULL(description, ''), '|', IFNULL(CAST(amount AS STRING), ''), '|',
            IFNULL(CAST(running_balance AS STRING), '')
        ))) AS transaction_id
    FROM tx
)

SELECT *
FROM tx_typed
QUALIFY ROW_NUMBER() OVER (PARTITION BY transaction_id ORDER BY search_date DESC) = 1
-- As with the Plaid model: duplicates may still exist if the same transaction
-- reappears across searches outside the incremental load window.
