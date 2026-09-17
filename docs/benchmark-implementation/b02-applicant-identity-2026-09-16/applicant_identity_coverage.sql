-- Aggregate-only coverage probe for the retained missing-user cohort.
-- The private runner binds @checkout_ids from the links receipt. The final
-- result contains counts only; no identifier/contact value is returned.
--
-- Raw Airbyte CDC rows are joined only to the 49-checkout cohort. Current
-- records are the latest row per source primary key ordered by updated_at,
-- _airbyte_extracted_at, and _airbyte_raw_id, excluding a latest row whose
-- _ab_cdc_deleted_at is non-null. Raw-row counts are computed independently
-- before row-number reduction, so repeats and missing current rows remain
-- visible. Customers are deduplicated globally before email matching.

WITH cohort AS (
    SELECT checkout_id
    FROM UNNEST(@checkout_ids) AS checkout_id
    WHERE NULLIF(TRIM(checkout_id), '') IS NOT NULL
    GROUP BY checkout_id
)

, checkouts_raw AS (
    SELECT
        c.id AS checkout_id
        , c.user_id
        , c.updated_at
        , c._airbyte_extracted_at
        , c._airbyte_raw_id
        , c._ab_cdc_deleted_at
    FROM `raylo-production.airbyte_raylo_prod.checkouts` AS c
    JOIN cohort AS h ON h.checkout_id = c.id
    WHERE NULLIF(TRIM(c.id), '') IS NOT NULL
)

, checkouts_current AS (
    SELECT *
    FROM checkouts_raw
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY checkout_id
        ORDER BY updated_at DESC, _airbyte_extracted_at DESC, _airbyte_raw_id DESC
    ) = 1
)

, checkout_raw_counts AS (
    SELECT
        h.checkout_id
        , COUNT(r.checkout_id) AS raw_rows
        , COUNTIF(
            r.checkout_id IS NOT NULL
            AND r._ab_cdc_deleted_at IS NULL
        ) AS active_raw_rows
    FROM cohort AS h
    LEFT JOIN checkouts_raw AS r ON r.checkout_id = h.checkout_id
    GROUP BY h.checkout_id
)

, checkout_current_counts AS (
    SELECT
        h.checkout_id
        , COUNT(c.checkout_id) AS current_rows
        , COUNTIF(NULLIF(TRIM(c.user_id), '') IS NOT NULL)
            AS current_user_id_rows
    FROM cohort AS h
    LEFT JOIN checkouts_current AS c
        ON c.checkout_id = h.checkout_id
       AND c._ab_cdc_deleted_at IS NULL
    GROUP BY h.checkout_id
)

, user_ids AS (
    SELECT DISTINCT NULLIF(TRIM(user_id), '') AS user_id
    FROM checkouts_current
    WHERE _ab_cdc_deleted_at IS NULL
      AND NULLIF(TRIM(user_id), '') IS NOT NULL
)

, users_raw AS (
    SELECT
        u.id AS user_id
        , u.customer_id
        , u.updated_at
        , u._airbyte_extracted_at
        , u._airbyte_raw_id
        , u._ab_cdc_deleted_at
    FROM `raylo-production.airbyte_raylo_prod.users` AS u
    JOIN user_ids AS i ON i.user_id = u.id
)

, users_current AS (
    SELECT *
    FROM users_raw
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY user_id
        ORDER BY updated_at DESC, _airbyte_extracted_at DESC, _airbyte_raw_id DESC
    ) = 1
)

, user_counts AS (
    SELECT
        h.checkout_id
        , COUNTIF(
            NULLIF(TRIM(c.user_id), '') IS NOT NULL
            AND u.user_id IS NULL
        ) AS missing_referenced_user_rows
        , COUNT(DISTINCT NULLIF(TRIM(u.user_id), '')) AS user_id_count
        , COUNT(DISTINCT NULLIF(TRIM(u.customer_id), ''))
            AS current_user_customer_count
    FROM cohort AS h
    LEFT JOIN checkouts_current AS c
        ON c.checkout_id = h.checkout_id
       AND c._ab_cdc_deleted_at IS NULL
    LEFT JOIN users_current AS u
        ON u.user_id = c.user_id
       AND u._ab_cdc_deleted_at IS NULL
    GROUP BY h.checkout_id
)

, customer_info_raw AS (
    SELECT
        ci.id AS checkout_customer_info_id
        , ci.checkout_id
        , ci.canonical_email
        , ci.updated_at
        , ci._airbyte_extracted_at
        , ci._airbyte_raw_id
        , ci._ab_cdc_deleted_at
    FROM `raylo-production.airbyte_raylo_prod.checkout_customer_infos` AS ci
    JOIN cohort AS h ON h.checkout_id = ci.checkout_id
    WHERE NULLIF(TRIM(ci.id), '') IS NOT NULL
)

, customer_info_current AS (
    SELECT *
    FROM customer_info_raw
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY checkout_customer_info_id
        ORDER BY updated_at DESC, _airbyte_extracted_at DESC, _airbyte_raw_id DESC
    ) = 1
)

, customer_info_raw_counts AS (
    SELECT
        h.checkout_id
        , COUNT(r.checkout_customer_info_id) AS raw_rows
        , COUNTIF(
            r.checkout_customer_info_id IS NOT NULL
            AND r._ab_cdc_deleted_at IS NULL
        ) AS active_raw_rows
    FROM cohort AS h
    LEFT JOIN customer_info_raw AS r
        ON r.checkout_id = h.checkout_id
    GROUP BY h.checkout_id
)

, customer_info_current_counts AS (
    SELECT
        h.checkout_id
        , COUNT(c.checkout_customer_info_id) AS current_rows
        , COUNTIF(
            CASE
                WHEN TRIM(COALESCE(c.canonical_email, '')) = '' THEN NULL
                ELSE c.canonical_email
            END IS NOT NULL
        ) AS nonblank_canonical_email_rows
    FROM cohort AS h
    LEFT JOIN customer_info_current AS c
        ON c.checkout_id = h.checkout_id
       AND c._ab_cdc_deleted_at IS NULL
    GROUP BY h.checkout_id
)

, customer_info_email_values AS (
    SELECT
        checkout_id
        , ARRAY_AGG(
            DISTINCT CASE
                WHEN TRIM(COALESCE(canonical_email, '')) = '' THEN NULL
                ELSE canonical_email
            END IGNORE NULLS
        ) AS email_values
    FROM customer_info_current
    WHERE _ab_cdc_deleted_at IS NULL
    GROUP BY checkout_id
)

, customers_raw AS (
    SELECT
        cu.id AS customer_id
        , cu.canonical_email
        , cu.updated_at
        , cu._airbyte_extracted_at
        , cu._airbyte_raw_id
        , cu._ab_cdc_deleted_at
    FROM `raylo-production.airbyte_raylo_prod.customers` AS cu
    WHERE NULLIF(TRIM(cu.id), '') IS NOT NULL
)

, customers_current AS (
    SELECT *
    FROM customers_raw
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY customer_id
        ORDER BY updated_at DESC, _airbyte_extracted_at DESC, _airbyte_raw_id DESC
    ) = 1
)

, customers_for_cohort AS (
    SELECT cu.*
    FROM customers_current AS cu
    JOIN customer_info_email_values AS e
        ON cu.canonical_email IN UNNEST(
            IFNULL(e.email_values, ARRAY<STRING>[])
        )
    WHERE cu._ab_cdc_deleted_at IS NULL
)

, canonical_email_lookup AS (
    SELECT
        h.checkout_id
        , COUNT(DISTINCT NULLIF(TRIM(cu.customer_id), ''))
            AS candidate_customer_count
        , COUNT(DISTINCT IF(
            NULLIF(TRIM(cu.customer_id), '')
                = NULLIF(TRIM(u.customer_id), '')
            AND NULLIF(TRIM(cu.customer_id), '') IS NOT NULL
            , cu.customer_id
            , NULL
        )) AS candidate_matches_actual_count
        , COUNT(DISTINCT NULLIF(TRIM(u.customer_id), ''))
            AS actual_customer_count
    FROM cohort AS h
    LEFT JOIN customer_info_email_values AS e
        ON e.checkout_id = h.checkout_id
    LEFT JOIN customers_for_cohort AS cu
        ON cu.canonical_email IN UNNEST(
            IFNULL(e.email_values, ARRAY<STRING>[])
        )
    LEFT JOIN checkouts_current AS c
        ON c.checkout_id = h.checkout_id
       AND c._ab_cdc_deleted_at IS NULL
    LEFT JOIN users_current AS u
        ON u.user_id = c.user_id
       AND u._ab_cdc_deleted_at IS NULL
    GROUP BY h.checkout_id
)

, per_checkout AS (
    SELECT
        h.checkout_id
        , crc.raw_rows AS checkout_raw_rows
        , crc.active_raw_rows AS checkout_active_raw_rows
        , ccc.current_rows AS checkout_current_rows
        , ccc.current_user_id_rows
        , uc.missing_referenced_user_rows
        , uc.user_id_count
        , uc.current_user_customer_count
        , cir.raw_rows AS customer_info_raw_rows
        , cir.active_raw_rows AS customer_info_active_raw_rows
        , cic.current_rows AS customer_info_current_rows
        , cic.nonblank_canonical_email_rows
        , cel.candidate_customer_count
        , cel.candidate_matches_actual_count
        , cel.actual_customer_count AS email_lookup_actual_customer_count
    FROM cohort AS h
    LEFT JOIN checkout_raw_counts AS crc USING (checkout_id)
    LEFT JOIN checkout_current_counts AS ccc USING (checkout_id)
    LEFT JOIN user_counts AS uc USING (checkout_id)
    LEFT JOIN customer_info_raw_counts AS cir USING (checkout_id)
    LEFT JOIN customer_info_current_counts AS cic USING (checkout_id)
    LEFT JOIN canonical_email_lookup AS cel USING (checkout_id)
)

SELECT
    COUNT(*) AS cohort_rows
    , COUNT(DISTINCT checkout_id) AS cohort_unique_checkouts
    , COUNTIF(checkout_raw_rows = 0) AS missing_checkout_rows
    , COUNTIF(checkout_raw_rows > 1) AS repeated_checkout_rows
    , COUNTIF(checkout_active_raw_rows > 1)
        AS repeated_active_checkout_rows
    , COUNTIF(checkout_current_rows = 0)
        AS missing_current_checkout_rows
    , COUNTIF(current_user_id_rows = 0) AS checkouts_without_user_id
    , COUNTIF(missing_referenced_user_rows > 0)
        AS checkouts_with_missing_referenced_user
    , COUNTIF(current_user_customer_count > 0)
        AS checkouts_with_current_user_customer
    , COUNTIF(customer_info_raw_rows = 0)
        AS missing_customer_info_rows
    , COUNTIF(customer_info_raw_rows > 1)
        AS repeated_customer_info_rows
    , COUNTIF(customer_info_active_raw_rows > 1)
        AS repeated_active_customer_info_rows
    , COUNTIF(customer_info_current_rows = 0)
        AS missing_current_customer_info_rows
    , COUNTIF(nonblank_canonical_email_rows > 0)
        AS checkouts_with_nonblank_canonical_email
    , COUNTIF(candidate_customer_count = 0)
        AS canonical_email_lookup_zero_customers
    , COUNTIF(candidate_customer_count = 1)
        AS canonical_email_lookup_one_customer
    , COUNTIF(candidate_customer_count > 1)
        AS canonical_email_lookup_multiple_customers
    , COUNTIF(
        email_lookup_actual_customer_count > 0
        AND candidate_customer_count > 0
        AND candidate_matches_actual_count = 0
    ) AS canonical_email_lookup_conflicts_with_actual_customer
    , COUNTIF(
        email_lookup_actual_customer_count > 0
        AND candidate_customer_count > 0
        AND candidate_matches_actual_count > 0
    ) AS canonical_email_lookup_agrees_with_actual_customer
FROM per_checkout
