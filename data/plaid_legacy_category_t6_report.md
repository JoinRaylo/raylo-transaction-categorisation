# Plaid legacy `category` vs PFC detailed as T6 (2026-08-27)

Plaid Asset Reports carry two category systems: the older list field (`category` / live `category_path`, e.g. `["Recreation","Arts and Entertainment","Casinos and Gaming"]`) and PFC v2 (`credit_category_detailed`), which is what T6 uses today. Every distinct live `category_path` is mapped in `taxonomy/plaid_legacy_category_map.csv` (115 keys). Locked v5/v6 not scored. Serving SQL not changed.

Join: gold Plaid rows to `credit_plaid_open_banking_transactions` on normalised merchant + description + abs(amount) + direction. T6-bound = `our_leaf` tier starts with T6 (dictionary and rules already lost).

| set | n | PFC leaf | legacy leaf | PFC general | legacy general | PFC=legacy |
|---|---:|---:|---:|---:|---:|---:|
| All joined Plaid gold with a category_path | 4223 | 19.7% | 18.9% | 48.9% | 43.0% | 41.2% |
| T6-bound (miss T1–T5) with a category_path | 953 | 18.6% | 15.7% | 35.2% | 30.7% | 26.8% |
| holdout (with path) | 613 | 21.7% | 17.0% | 43.1% | 33.9% | 25.4% |
| holdout T6-bound | 274 | 17.2% | 13.5% | 36.1% | 26.6% | 17.9% |
| pipeline (with path) | 1222 | 19.9% | 16.9% | 49.1% | 42.4% | 40.4% |
| pipeline T6-bound | 361 | 18.8% | 15.8% | 33.5% | 26.0% | 24.4% |
| risk (with path) | 641 | 7.8% | 5.8% | 46.3% | 38.8% | 45.2% |
| risk T6-bound | 88 | 23.9% | 22.7% | 25.0% | 22.7% | 36.4% |
| v3 (with path) | 854 | 30.2% | 30.3% | 58.9% | 55.7% | 50.7% |
| v3 T6-bound | 84 | 22.6% | 16.7% | 44.0% | 48.8% | 38.1% |
| v4 (with path) | 893 | 16.8% | 21.7% | 44.8% | 41.1% | 41.0% |
| v4 T6-bound | 146 | 15.1% | 15.1% | 38.4% | 44.5% | 37.0% |

**T6-bound headline:** legacy path 15.7% vs PFC detailed 18.6% (−2.8pp leaf). PFC detailed remains the better fallback on this set.

v4 (unmatched-Plaid volume sample) is the one place the list field looks better **before** T1–T5 (21.7% vs 16.8%). On the T6-bound slice of the same file they **tie** at 15.1%. Risk gold is poor for both (coarse gambling bucket). The two systems agree on only ~27% of T6-bound rows — this is not a relabel of the same tree.

Do **not** switch T6 in `sql/apply_crosswalk.sql`. Keep `credit_category_detailed`.

Scorer: `src/score_plaid_legacy_category.py`.
