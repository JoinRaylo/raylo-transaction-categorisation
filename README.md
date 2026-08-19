# raylo-transaction-categorisation

Research repo for a single transaction taxonomy across Raylo's Open Banking providers (Equifax and Plaid).

**Status: research. Nothing here is in production.** No dbt model or scheduled job references this repo, and it must stay that way until work is explicitly promoted.

- **Agent context:** [`CLAUDE.md`](CLAUDE.md) — read first
- **Stakeholder write-up:** [Notion doc](https://app.notion.com/p/3bf5bb4b4a6581b6807add39671e56c2)

## Why this exists

The live Open Banking risk model reads Plaid's category names directly. Plaid shipped a new taxonomy version (PFC v2, Dec 2025) after Raylo went live on Plaid, and the same transaction can be relabelled between versions. This repo builds a taxonomy Raylo owns, with provider categories as input evidence rather than as the definition.

## Layout

```
taxonomy/
  taxonomy.csv                    274 detailed leaves -> 29 general categories
  merchant_dictionary.csv         321 merchants, LLM-proposed, pending review
  rules/deterministic_rules.csv   regex rules (personal names, fuel, gambling, crypto)
sql/
  apply_crosswalk.sql             precedence logic, both providers, 393 mappings
src/
  build_taxonomy.py               regenerates taxonomy.csv
  build_merchant_dictionary.py    regenerates merchant_dictionary.csv
  generate_crosswalk_sql.py       regenerates apply_crosswalk.sql from the seeds
  analyse_provider_disagreement.py measures cross-provider leaf conflicts
tests/
  test_taxonomy_integrity.py      run after every taxonomy edit
docs/                             research write-ups (see CLAUDE.md for the summary)
archive/                          superseded / discarded artifacts, kept for provenance
outputs/                          scratch (gitignored)
```

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest tests/ -q          # must pass before and after any taxonomy edit
```

BigQuery project is `raylo-production`, read-only. Write experiment output to a scratch dataset, never `dbt_production`.

## Current state

| Item | Status |
|---|---|
| Taxonomy (274 leaves / 29 generals) | Built, verified — 0 uncovered provider values |
| Crosswalk precedence logic | Built, tested on a 2% sample; all tiers fire |
| Merchant dictionary (321 entries) | Built; 275 high / 30 medium / 16 low confidence — **needs human sign-off** |
| Deterministic regex rules | Written, **not yet wired into the SQL** |
| Dictionary + rules as pipeline tiers | **Not yet integrated** |
| LLM validation experiment | **RESOLVED — GREEN LIGHT.** Human adjudication of all 376 consensus disputes (2026-08-19): corrected accuracy **96.1% leaf / 98.2% general**. By-products: 195 approved dictionary entries, 49 T1/T2 rule candidates, and `data/gold_merchant_labels.csv` (1,563-merchant gold eval set) — see CLAUDE.md §6 |
| Four-field categoriser (name+description+amount+direction) | **Next task** — ML baseline on Equifax raw text vs context-enriched LLM, both evaluated on the gold set, then combined |

## Key numbers

- Equifax: **65.8%** of transactions well-resolved, 34.2% need merchant/ML layers
- Plaid: 100% map to a leaf, but **50.6% land on coarse leaves**; 202 of 274 leaves unreachable from Plaid
- Cross-provider conflict: applying both crosswalks gives **different leaves for 45.2% of shared-merchant volume** — this is why the merchant dictionary must override provider categories
- Dictionary coverage: **88.2%** of Equifax merchant volume vs **47.8%** of Plaid's (measured ceiling with Equifax's full 6,518-vendor list: 41.3%)

## Two things to know before changing anything

1. **Don't prune categories on low IV.** IV is a risk-model feature-selection criterion, not a measure of categorisation quality. An earlier version pruned 274 leaves to 73 on that basis and had to be rebuilt. Use IV to decide where *aggregation* is safe.
2. **Don't aggregate gambling subtypes.** Combined IV 0.0053 vs 0.0498 for lottery alone. There's a test guarding it.
