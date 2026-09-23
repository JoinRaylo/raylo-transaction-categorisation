"""Guarded rebuild of the MLM pretraining corpus (2026-09-23).

Replaces the gated-off ``build_corpus.py pretrain`` for the TxCat-1 retrain.
The original was a GROUP BY text-frequency export with no identity, so the
encoder saw protected benchmark narratives.  This rebuild keeps the same
sentence format, sources and amount buckets, and protects the pinned release
(the 3,295-row benchmark membership) in four layers:

1. **Inside BigQuery, before aggregation.**
   - Plaid rows are excluded by exact event, account, customer and the
     checkouts of protected users.  Customers are resolved directly or through
     checkout → user → customer when the row lacks one.
   - Rows whose customer cannot be resolved, or whose account resolves to more
     than one customer, fail closed.
   - Equifax rows whose ``ExternalReference`` is a protected user's checkout
     are excluded.  Equifax customer IDs are a separate namespace with no Raylo
     link, and that is recorded, not hidden.
2. **One representative identity per sentence.**  Each aggregated sentence
   keeps one representative source row, chosen deterministically from its
   surviving rows.
3. **The canonical B04 guard.**  Every shard's representative rows pass
   ``eval_protection.apply`` for ``domain_pretraining``.  The shard is then
   receipted with a signed v4 artifact receipt.  Any exclusion at this stage
   means the BigQuery layer disagreed with the pinned release, so the build
   stops.
4. **Exact text.**  Any sentence whose (direction, merchant, description)
   equals a protected transaction's is dropped, whatever its source or
   customer.

The BigQuery protected table is checked against the pinned membership
(sorted event-key digest, accounts, customers) before any query runs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "transformer"))

import eval_protection  # noqa: E402
from build_corpus import AMT_CASE, EQX, PLAID, _client, _run, sentence  # noqa: E402

OUT = ROOT / "outputs" / "transformer" / "pretrain_guarded"
CONSUMER = "transformer.build_pretrain_guarded"
PURPOSE = "domain_pretraining"
PROTECTED_TABLE = "`raylo-production.txncat_eval_protected.benchmark_protected_3295_v1`"
CHECKOUTS = "`raylo-production.dbt_production.stg_raylo_production__checkouts`"
USERS = "`raylo-production.dbt_production.stg_raylo_production__users`"
SHARD_ROWS = 1_000_000


def _event_key(account_id: str, transaction_id: str) -> str:
    return hashlib.sha256(f"plaid:{account_id}:{transaction_id}".encode()).hexdigest()


def verify_protected_table(protection) -> dict:
    """The BigQuery table the SQL layer trusts must equal the pinned membership."""

    local_keys = sorted(_event_key(a, t) for a, t in protection.events)
    local = {
        "rows": protection.rows,
        "accounts": len(protection.accounts),
        "customers": len(protection.customers),
        "sorted_key_digest": hashlib.sha256("\n".join(local_keys).encode()).hexdigest(),
    }
    row = _run(
        f"""SELECT COUNT(*) AS row_count, COUNT(DISTINCT account_id) AS accounts,
       COUNT(DISTINCT customer_id) AS customers,
       COUNTIF(event_key != TO_HEX(SHA256(CONCAT('plaid:', account_id, ':', transaction_id))))
         AS bad_keys,
       TO_HEX(SHA256(STRING_AGG(event_key, '\\n' ORDER BY event_key))) AS sorted_key_digest
FROM {PROTECTED_TABLE}""",
        "protected-table-check",
    ).iloc[0]
    remote = {
        "rows": int(row["row_count"]),
        "accounts": int(row["accounts"]),
        "customers": int(row["customers"]),
        "sorted_key_digest": row["sorted_key_digest"],
    }
    if remote != local or int(row["bad_keys"]):
        raise RuntimeError(f"BigQuery protected table differs from the pinned release: {remote}")
    return local


PLAID_FLAGGED = f"""
WITH p AS (SELECT * FROM {PROTECTED_TABLE}),
c AS (SELECT TRIM(checkout_id) AS checkout_id, ANY_VALUE(TRIM(user_id)) AS user_id,
             COUNT(DISTINCT TRIM(user_id)) AS nu
      FROM {CHECKOUTS} WHERE NULLIF(TRIM(checkout_id), '') IS NOT NULL GROUP BY 1),
u AS (SELECT TRIM(user_id) AS user_id, ANY_VALUE(TRIM(customer_id)) AS customer_id,
             COUNT(DISTINCT TRIM(customer_id)) AS nc
      FROM {USERS} WHERE NULLIF(TRIM(user_id), '') IS NOT NULL GROUP BY 1),
protected_checkouts AS (
  SELECT checkout_id FROM c WHERE user_id IN (SELECT user_id FROM p WHERE user_id != '')
  UNION DISTINCT SELECT checkout_id FROM p WHERE checkout_id != ''),
r AS (
  SELECT TRIM(t.account_id) AS account_id, TRIM(t.transaction_id) AS transaction_id,
         COALESCE(NULLIF(TRIM(t.customer_id), ''),
                  IF(c.nu = 1 AND u.nc = 1, NULLIF(u.customer_id, ''), NULL)) AS customer_id,
         NULLIF(TRIM(t.checkout_id), '') AS checkout_id,
         LOWER(TRIM(IFNULL(t.merchant_name, ''))) AS merchant,
         LOWER(TRIM(IFNULL(COALESCE(t.original_description, t.transaction_name), ''))) AS description,
         IF(t.amount < 0, 'credit', 'debit') AS direction, ABS(t.amount) AS a
  FROM {PLAID} t
  LEFT JOIN c ON TRIM(t.checkout_id) = c.checkout_id
  LEFT JOIN u ON c.user_id = u.user_id),
acct AS (SELECT account_id, COUNT(DISTINCT customer_id) AS ncust FROM r
         WHERE customer_id IS NOT NULL GROUP BY 1),
flagged AS (
  SELECT r.*, CASE
    WHEN r.customer_id IS NULL THEN 'unlinked_customer'
    WHEN acct.ncust > 1 THEN 'ambiguous_account'
    WHEN TO_HEX(SHA256(CONCAT('plaid:', r.account_id, ':', r.transaction_id)))
         IN (SELECT event_key FROM p) THEN 'protected_event'
    WHEN r.account_id IN (SELECT account_id FROM p) THEN 'protected_account'
    WHEN r.customer_id IN (SELECT customer_id FROM p) THEN 'protected_customer'
    WHEN r.checkout_id IN (SELECT checkout_id FROM protected_checkouts) THEN 'protected_user_checkout'
    ELSE NULL END AS drop_reason
  FROM r LEFT JOIN acct USING (account_id)
  WHERE r.merchant != '' OR r.description != '')
"""

EQX_FLAGGED = f"""
WITH p AS (SELECT * FROM {PROTECTED_TABLE}),
c AS (SELECT TRIM(checkout_id) AS checkout_id, TRIM(user_id) AS user_id FROM {CHECKOUTS}),
protected_refs AS (
  SELECT checkout_id AS ref FROM c WHERE user_id IN (SELECT user_id FROM p WHERE user_id != '')
  UNION DISTINCT SELECT checkout_id FROM p WHERE checkout_id != ''),
r AS (
  SELECT NULLIF(TRIM(CAST(CustomerId AS STRING)), '') AS customer_id,
         CAST(TransactionId AS STRING) AS transaction_id, TRIM(ExternalReference) AS ref,
         LOWER(TRIM(IFNULL(VendorDescription, ''))) AS merchant,
         LOWER(TRIM(IFNULL(Description, ''))) AS description,
         IF(TransactionTypeId = 1, 'credit', 'debit') AS direction, ABS(Amount) AS a
  FROM {EQX}),
flagged AS (
  SELECT r.*, CASE
    WHEN r.customer_id IS NULL THEN 'unlinked_customer'
    WHEN r.ref IN (SELECT ref FROM protected_refs) THEN 'protected_user_checkout'
    ELSE NULL END AS drop_reason
  FROM r WHERE r.merchant != '' OR r.description != '')
"""


def exclusion_stats() -> dict:
    stats = {}
    for name, flagged in (("plaid", PLAID_FLAGGED), ("equifax", EQX_FLAGGED)):
        df = _run(
            flagged + "SELECT IFNULL(drop_reason, 'kept') AS reason, COUNT(*) AS n "
            "FROM flagged GROUP BY 1",
            f"stats/{name}",
        )
        stats[name] = {r.reason: int(r.n) for r in df.itertuples()}
    return stats


def plaid_groups() -> pd.DataFrame:
    return _run(
        PLAID_FLAGGED
        + f"""SELECT 'plaid' AS provider, merchant, description, direction, {AMT_CASE} AS amt_bucket,
       COUNT(*) AS n,
       ARRAY_AGG(STRUCT(account_id, transaction_id, customer_id)
                 ORDER BY FARM_FINGERPRINT(CONCAT(account_id, ':', transaction_id)) LIMIT 1
                )[OFFSET(0)] AS rep
FROM flagged WHERE drop_reason IS NULL GROUP BY 1, 2, 3, 4, 5""",
        "pretrain/plaid",
    )


def equifax_groups(eqx_sample: int) -> pd.DataFrame:
    total = int(
        _run(
            EQX_FLAGGED
            + f"SELECT COUNT(*) AS n FROM (SELECT 1 FROM flagged WHERE drop_reason IS NULL "
            f"GROUP BY merchant, description, direction, {AMT_CASE})",
            "pretrain/equifax-count",
        ).iloc[0]["n"]
    )
    keep_per_million = min(1_000_000, int(eqx_sample * 1_000_000 / max(total, 1)))
    df = _run(
        EQX_FLAGGED
        + f"""SELECT * FROM (
  SELECT 'equifax' AS provider, merchant, description, direction, {AMT_CASE} AS amt_bucket,
         COUNT(*) AS n,
         ARRAY_AGG(STRUCT(CAST(NULL AS STRING) AS account_id, transaction_id, customer_id)
                   ORDER BY FARM_FINGERPRINT(IFNULL(transaction_id, customer_id)) LIMIT 1
                  )[OFFSET(0)] AS rep
  FROM flagged WHERE drop_reason IS NULL GROUP BY 1, 2, 3, 4, 5)
WHERE MOD(ABS(FARM_FINGERPRINT(CONCAT(merchant, '|', description, '|', direction, '|',
                                     amt_bucket))), 1000000) < {keep_per_million}""",
        "pretrain/equifax",
    )
    df.attrs["groups_available"] = total
    df.attrs["keep_per_million"] = keep_per_million
    return df


def protected_texts() -> set[tuple[str, str, str]]:
    """(direction, merchant, description) of every protected transaction, normalised as SQL."""

    private = pathlib.Path(
        os.environ.get(
            "BENCHMARK_PRIVATE_ROOT",
            pathlib.Path.home() / ".local/share/raylo-txncat/benchmark-2000-candidate-2026-09-22",
        )
    )
    texts = set()
    rows_read = 0
    for path, merchant_key in (
        (private / "release/benchmark-candidate.jsonl", "merchant"),
        (private / "expansion/expansion-selection.jsonl", "merchant_name"),
    ):
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                row = json.loads(line)
                rows_read += 1
                description = row.get("description")
                if description is None:
                    description = row.get("transaction_name")
                texts.add(
                    (
                        row["direction"],
                        (row.get(merchant_key) or "").strip().lower(),
                        (description or "").strip().lower(),
                    )
                )
    # Many protected rows share a narrative, so check rows read, not distinct texts.
    if rows_read != 3295:
        raise RuntimeError(f"expected the 3,295 protected rows, read {rows_read}")
    return texts


def main() -> None:
    parser = eval_protection.add_args(argparse.ArgumentParser(description=__doc__))
    parser.add_argument("--eqx-sample", type=int, default=20_000_000)
    parser.add_argument("--output", type=pathlib.Path, default=OUT)
    args = parser.parse_args()
    protection, _publication = eval_protection.load_release(args)
    table_check = verify_protected_table(protection)
    stats = exclusion_stats()
    plaid, eqx = plaid_groups(), equifax_groups(args.eqx_sample)
    df = pd.concat([plaid, eqx], ignore_index=True)
    df["text"] = [
        sentence(d, b, m, s)
        for d, b, m, s in zip(df["direction"], df["amt_bucket"], df["merchant"], df["description"])
    ]
    guarded_texts = protected_texts()
    key = list(zip(df["direction"], df["merchant"], df["description"]))
    text_hit = pd.Series([k in guarded_texts for k in key], index=df.index)
    text_dropped = {p: int((text_hit & (df.provider == p)).sum()) for p in ("plaid", "equifax")}
    df = df[~text_hit]
    before_dedupe = len(df)
    df = df.drop_duplicates("text").sample(frac=1.0, random_state=42).reset_index(drop=True)
    df["account_id"] = [r["account_id"] for r in df["rep"]]
    df["transaction_id"] = [r["transaction_id"] for r in df["rep"]]
    df["customer_id"] = [r["customer_id"] for r in df["rep"]]
    df = df.drop(columns=["rep"])
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    os.chmod(out, 0o700)
    shards = []
    for index, start in enumerate(range(0, len(df), SHARD_ROWS)):
        part = df.iloc[start : start + SHARD_ROWS]
        rows = part[["provider", "account_id", "transaction_id", "customer_id"]].to_dict("records")
        for row in rows:
            if row["provider"] != "plaid":
                row.pop("account_id")
        guarded = eval_protection.apply(rows, args, purpose=PURPOSE)
        if len(guarded) != len(rows) or sum(guarded.guard.excluded.values()):
            raise RuntimeError("B04 guard excluded rows the BigQuery layer kept; stopping")
        path = out / f"pretrain-{index:03d}.parquet"
        part.to_parquet(path, index=False)
        os.chmod(path, 0o600)
        receipt = eval_protection.write_artifact_receipt(
            path, consumer=CONSUMER, purpose=PURPOSE, guard=guarded.guard
        )
        shards.append(
            {
                "path": path.name,
                "rows": len(part),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "receipt": receipt.name,
            }
        )
        print(f"shard {index}: {len(part):,} rows guarded and receipted", file=sys.stderr)
    manifest = {
        "schema_version": "pretrain-guarded-manifest-v1",
        "protected_release": eval_protection.PINNED_BINDING,
        "protected_table": PROTECTED_TABLE.strip("`"),
        "protected_table_check": table_check,
        "sql_sha256": {
            "plaid": hashlib.sha256(PLAID_FLAGGED.encode()).hexdigest(),
            "equifax": hashlib.sha256(EQX_FLAGGED.encode()).hexdigest(),
        },
        "row_exclusion_counts": stats,
        "equifax_sampling": {
            "groups_available": eqx.attrs["groups_available"],
            "keep_per_million": eqx.attrs["keep_per_million"],
            "requested": args.eqx_sample,
        },
        "groups": {"plaid": len(plaid), "equifax": len(eqx)},
        "exact_text_dropped": text_dropped,
        "sentences": len(df),
        "duplicate_texts_dropped": before_dedupe - len(df),
        "by_provider": {p: int((df.provider == p).sum()) for p in ("plaid", "equifax")},
        "credit_share": round(float((df.direction == "credit").mean()), 4),
        "shards": shards,
        "limitations": [
            "Equifax customer IDs are a separate namespace with no Raylo link; only "
            "Equifax references that are protected users' checkouts (and exact "
            "protected text) can be excluded for that source.",
            "Plaid rows without a resolvable customer, or whose account resolves to "
            "several customers, are excluded rather than trusted.",
        ],
        "authorizes_consumption": False,
    }
    manifest_path = out / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    os.chmod(manifest_path, 0o600)
    print(json.dumps({k: v for k, v in manifest.items() if k != "shards"}, indent=1))


if __name__ == "__main__":
    main()
