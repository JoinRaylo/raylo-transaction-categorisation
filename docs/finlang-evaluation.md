# FinLang — viability assessment for the unified transaction categorisation project

**Date:** 2026-08-23 · **Author:** Carlos (with Claude) · **Verdict: not suitable as a component of this pipeline. Two of its ideas are worth stealing.**

---

## 0. Which "FinLang"? (the name is overloaded three ways)

| Candidate | What it is | Relevance here |
|---|---|---|
| **FinLang Ltd — `finlang`** ([finlang.io](https://www.finlang.io/), [GitHub](https://github.com/FinLang-Ltd/finlang)) | A deterministic DSL + Python CLI for **bank-transaction categorisation by hand-written rules**. Explicitly pitched as "replaces opaque ML categorisation". | **This is the one that matters** — same problem, opposite philosophy. Assessed in full below. |
| **FinLang (Hugging Face org)** — `finance-embeddings-investopedia`, `finance-chat-model-investopedia` | A bge-base embedding fine-tune and a Mistral-7B instruct fine-tune, both trained on Investopedia content. | Plausible drop-in for the MiniLM encoder in `distillation_bakeoff.py`. **Blocked on licensing** — see §6. |
| **FinLangNet** ([arXiv:2404.13004](https://arxiv.org/abs/2404.13004)) | A credit-risk *sequence* model (DiDi), ACL 2026. Not categorisation. | Not this project, but relevant to the risk-model side — see §7. |

Everything from §1 to §5 is about the **rules engine**, since that is the one that directly targets our problem.

---

## 1. What FinLang (the rules engine) actually is

A single-vendor open-source project: **FinLang Ltd, Auchterarder, Scotland** (ICO reg. ZB998843).

| Fact | Value |
|---|---|
| Repo created | 2025-09-18 |
| Last push | 2026-07-26 |
| Stars / forks / open issues | 13 / 0 / 0 |
| Version | 0.8.3 (pre-1.0) |
| Language / deps | Python, `pandas>=2.0` only (optional `pyarrow`, `fastapi`) |
| Size | 28 Python files, ~6,200 LOC |
| Licence | **AGPL-3.0-only**, dual-licensed commercially |
| Commercial pricing | Team £1,200/yr · "Banking Pack v1.0" (92 rules) £499 one-off · Enterprise POA |
| Surfaces | CLI over CSV · Python-via-subprocess · self-hosted FastAPI wrapper |

Verified working: installed 0.8.3 from PyPI into a clean venv on Python 3.14 / pandas 3.0.5 and ran every test below. It installs cleanly and does what it says.

### The DSL, precisely

```fin
rule "GROCERIES: Tesco" {
  match:
    - counterparty ~ "*TESCO*"
    - amount in -500.00 .. -1.00
  set:
    - category = "Groceries"
    - flags += "Supermarket"
}
```

Read from `src/finlang/engine/finlang_engine.py`, not from the marketing page:

- **Matchable fields are a fixed closed set of six**: `counterparty`, `memo`, `amount`, `category`, `flags`, `status`. You cannot add a field.
- **Three operators only**: `==` (case-insensitive exact), `~` (glob wildcard, `*` only), `in` (numeric range, **`amount` only**).
- **No regex. No OR inside a rule** (conditions are AND-ed; OR means duplicating the rule). **No date comparison** — `date` is parsed but not matchable.
- Actions can set `category`/`status`/`memo`/`exclude`; `flags` is append-only and cannot contain whitespace.
- **Execution model**: every rule is evaluated against every row, in file order, as a vectorised pandas mask. **Last matching rule wins** for `category`; flags accumulate. There is no first-match-wins/stop.

---

## 2. Empirical test: our dictionary, our gold set, our numbers

Rather than reason about it, I compiled our real assets into FinLang and ran them.

### 2a. Does it express the T4 merchant dictionary? Yes.

Generated a `.fin` rulepack from all **18,825 entries** of `taxonomy/merchant_dictionary.csv` (one `counterparty == "<key>"` rule each — a faithful translation, since T4 in `sql/apply_crosswalk.sql` joins on `LOWER(TRIM(vendor))` and FinLang's `==` is case-insensitive). Zero keys needed escaping. It parsed and ran without error.

Scored against `data/gold_v2_slm_eval_holdout.csv` (1,055 real transactions):

| Metric | Result |
|---|---|
| Rows given a category | 359 / 1,055 = **34.0%** |
| Precision on covered rows | **94.7%** |
| Overall leaf accuracy | **32.2%** |

That is a faithful reproduction of what T4 alone achieves — high precision, low coverage — and it lands almost exactly on TF-IDF v2 (32.0%) on the same set, versus **84.2% for Gemini 3.7 Flash**. FinLang is a competent executor of a dictionary. It does nothing whatsoever about the 66% of that holdout that is long-tail text, which §5 of `CLAUDE.md` identifies as the actual problem.

### 2b. Is the precedence waterfall expressible? Yes — inverted.

FinLang's last-write-wins is the mirror image of our highest-tier-wins, but guarding on `category == ""` reproduces it. Demonstrated end-to-end, including the Tesco/Tesco Bank T2 fix:

```fin
rule "T6 fallback"        { match: - category == ""                                    set: - category = "unclassified" }
rule "T4 dictionary"      { match: - counterparty == "tesco"
                                   - category == "unclassified"                        set: - category = "groceries" }
rule "T2 narrative override" { match: - counterparty == "tesco"
                                      - memo ~ "*tesco bank*"                          set: - category = "financial_institution_unspecified"
                                                                                            - flags += "T2_override" }
```

Output was correct on all three probe rows: the store card → `groceries`, the Tesco Bank direct debit → `financial_institution_unspecified` with the override flag, the unknown merchant → `unclassified`. **T1, T2, T4, T6 and T7 are all representable.**

### 2c. What breaks: T3 and T5.

**T3 (mechanism-override primaries)** reads Equifax's `PrimaryCategoryDescription`. There is no field for it — the six canonical fields are hard-coded. You would have to smuggle the provider category into `memo` and glob-match it, which corrupts the field that T2 needs for narrative disambiguation. T3 is 4.10% of Equifax volume and, per `CLAUDE.md` §4, exists precisely because merchant-level matching gets it wrong.

**T5 (deterministic regex rules)** is worse, because it fails *silently and in the dangerous direction*. Our rules use word boundaries, anchors and alternation — `^[a-z]\s+[a-z]{2,}$` (initial + surname), `\b(bet|betting|bookmaker)\b`, `\b(lottery|lotto)\b`. None are expressible in globs. The only available translation is a substring glob, and I measured what that costs on our own dictionary:

> A `*bet*` rule matches **81** of our 18,825 dictionary merchants. The word-boundary regex matches **15**. Of the 67 glob-only hits, **49 are not gambling at all** — `bethany smith`, `elizabeth gray bday`, `nicola leadbetter`, `daniel bethell`, `nisbets`, `better`, `gll better`, `christopher betts ctc`. 35 of them are `transfer_p2p`.

Wrongly flagging people named Bethany as gambling spend, inside a credit decision, is the exact class of failure §3 of `CLAUDE.md` guards against — and gambling subtypes are the one place the taxonomy forbids aggregation (`Lottery` IV 0.0498 vs 0.0053 combined). This is not a theoretical objection; it is 49 merchants in the dictionary we already have.

*(Side finding from the same measurement, unrelated to FinLang: our own `\b(bet|betting|bookmaker)\b` regex missed `skybet`, `bet365`, `betfred`, `betfair`, `betvictor`, `betway`, `unibet` and `betuk` — every glued brand name. All eight were caught by T4, so nothing was mislabelled, but R07's stated job is "fallback if operator not in dictionary", which is exactly the case where glued morphology matters. **Fixed 2026-08-23**: R07 now also matches digit suffixes (`bet365`, `bet 365`) and known prefix/suffix forms. Validated against all 18,825 dictionary merchants — 24 hits, **0 non-gambling false positives** — and deliberately kept as an explicit alternation rather than a loose contains, for the reason measured directly above. `sql/apply_crosswalk.sql` regenerated; `pytest tests/` green.)*

### 2d. Throughput: the headline number does not survive a real rulepack

The advertised "217K rows/s" is real — and is measured with **one rule**. `benchmarks/bench_finlang_harness.py` writes a single `*TESCO*` rule as its fixture. Since the engine evaluates every rule against every row, throughput scales inversely with rule count. Measured on this laptop:

| Ruleset | Rows | Wall time | Rows/sec |
|---|---|---|---|
| 1 glob rule | 200,000 | 0.78 s | ~258,000 |
| 18,825 exact (`==`) rules | 200,000 | 71.2 s | ~2,810 |
| 18,825 substring (`~ "*x*"`) rules | 20,000 | 16.7 s | ~1,200 |

Extrapolated to our tables, single-threaded:

| Table | Rows | Exact rules | Substring rules |
|---|---|---|---|
| Plaid (live) | 4,279,707 | ~25 min | ~1 hr |
| Equifax dump | 73,246,476 | ~7 hr | ~17 hr |

Not disqualifying for batch work, but it is two orders of magnitude off the advertised figure once you load a real dictionary, and it is the wrong shape: BigQuery does this join in seconds because a dictionary lookup should be a hash join, not 18,825 sequential full-column scans.

---

## 3. Architectural fit

This is the objection that would matter even if everything above were perfect.

Our pipeline is **BigQuery SQL** (`sql/apply_crosswalk.sql`), destined for dbt, over 77M rows across two providers. FinLang is a **Python CLI that reads and writes CSV files**. Adopting it means export → local/containerised CLI → re-import, for every run, with the categorisation logic living outside the warehouse and outside dbt's lineage. It would replace a SQL `CASE`/join expression that already works, runs where the data is, and is already tested by `pytest tests/`, with a file-shuffling round trip.

The self-hosted FastAPI wrapper is per-request, which is a worse fit again for batch scoring at proposal time.

---

## 4. Verification claims vs the public repo

Worth noting for anyone weighing the vendor: finlang.io advertises "168 tests across 10 gates per release" and "20 million verified rows across three deterministic runs with zero mismatches". The public repository contains **11 test functions** (`tests/test_cli_smoke.py` plus three contract files); `pyproject.toml` excludes a `test_suite` directory that is not shipped. The claims may well be true — they simply cannot be checked from the open-source artefact, which matters if the audit trail is the reason you are buying it.

---

## 5. Where the rules engine is genuinely good

Being fair to it — the design is thoughtful and the code is clean:

- **Determinism is real and provable.** No network, no randomness, byte-identical output. That is a genuine advantage over our Gemini tier, which we have *measured* as non-deterministic at temperature 0 (5/40 rows flipped between identical calls).
- **`--reconcile` is the best idea in the product.** It diffs a rule-attributed output against an external ML classification row by row, and detects orphans — rows the ML pipeline dropped or invented. This is precisely the "challenge layer" shape our §12 continuous-improvement loop describes, and it is a pattern worth copying into `confusion_analysis.py` regardless of whether we ever install FinLang.
- **Rule-attributed audit output** (every row carries the rule that produced it, plus SHA-256 integrity files and HTML impact reports). We already have the important half of this in `resolution_tier`; the *impact* report — "show me which rows this rule change would move, before I merge it" — is the half we don't have, and it maps directly onto merging a production-labelling tranche.
- Sensible defensive touches: flags are append-only, whitespace in flags is a parse error, audit key ordering is deterministic to survive hash randomisation.

---

## 6. The Hugging Face "FinLang" models — blocked on licence

If what was meant was the embedding model, the answer is short.

`FinLang/finance-embeddings-investopedia` is a bge-base-en-v1.5 fine-tune (768-dim, 0.1B params, ~17.4k downloads/month) and `FinLang/finance-chat-model-investopedia` is a Mistral-7B-v0.1 instruct fine-tune. Both are **CC-BY-NC-4.0** and both model cards state "for research purposes only". **Non-commercial licences rule them out for a lender's credit decisioning**, whatever they score. The org has also been dormant since June 2024, with the promised v2 never shipped.

Setting licensing aside, the case for trying one was reasonable: swapping the encoder in `distillation_bakeoff.py` is a one-line change (`EMBED_MODEL_NAME`), and FinMTEB ([arXiv:2502.10990](https://arxiv.org/abs/2502.10990)) does find that finance-adapted embeddings beat general ones (Fin-E5 0.6767 vs e5-mistral-7b 0.6475; FinBERT beats BERT by 15.6%). But the same paper contains the finding that should temper expectations here: **bag-of-words beats every dense architecture on financial STS**, because financial text is full of boilerplate and specialist tokens that reward exact matching. That is our own result exactly — TF-IDF character n-grams 32.0% vs MiniLM embeddings 27.6%. And "finance domain" in FinMTEB/Investopedia terms means analyst prose and encyclopaedia entries, not `3765 16JAN23 CD TESCO STORES 3213 STEVENAGE GB`. If we ever revisit the embedding arm, **Fin-E5 (permissively licensed, and the actual FinMTEB leader) is the model to try, not FinLang.**

---

## 7. FinLangNet — different problem, worth a bookmark

[arXiv:2404.13004](https://arxiv.org/abs/2404.13004), ACL 2026 oral, deployed at DiDi. Reformulates credit scoring as multi-scale sequential learning: a DeepFM tabular module plus a sequence module with a dual-prompt mechanism, reporting **+6.3pp KS and a 9.9% reduction in bad debt rate against a production XGBoost system**.

Not a categorisation tool, so out of scope for this evaluation — but it sits in the same family as the nuFormer / transaction-transformer work already logged in `docs/open-banking-ai-research.md`, and the KS improvement is the kind of number Experiment 3 will be judged against. **No public code, so it is a reading reference, not a dependency.** Note also that its premise is long behavioural sequences, which collides head-on with the 90-day Plaid cap documented in §10 — another argument for fixing that request parameter.

---

## 8. Recommendation

**Do not adopt FinLang.** The blocking reasons, in order:

1. **It cannot express T5 or T3**, and its failure mode on T5 is silent over-matching in a fair-lending-sensitive category — 49 demonstrated false positives in our own dictionary.
2. **Architectural mismatch.** CSV CLI versus BigQuery/dbt over 77M rows; ~2,800 rows/s with a real rulepack against a SQL hash join.
3. **It solves the part we have already solved.** T4 works. The open problem is the long tail (65% of unmatched Plaid volume, 135,820 merchant strings), and a rules engine is definitionally silent there — its own answer is `finlang-suggest`, which emits `*TOKEN*` fuzzy rules by default, i.e. exactly the over-matching pattern measured in §2c.
4. **Vendor risk** for something load-bearing: v0.8.3, 13 stars, 0 forks, one company, unverifiable test claims, AGPL requiring a legal review or a commercial licence.

**Do take two things from it, at zero cost:**

- **Add a reconcile/challenge step to `confusion_analysis.py`** — orphan detection (rows a pipeline dropped or invented) is a class of error our current accuracy-and-confusion reporting cannot see at all.
- **Add a pre-merge impact report to the tranche workflow** — "which rows does this dictionary/rule change move, and from what to what", produced before merging rather than discovered afterwards. This is the generalised form of how the Tesco/Tesco Bank bug was found, and §12 already calls for exactly this loop.

Neither requires installing anything.

---

### Reproducing the measurements

Everything in §2 was produced with the scratch scripts in this session (dictionary → `.fin` compiler, gold-set harness, throughput harness). None are committed, since the conclusion is "don't adopt" — the numbers above are the deliverable. If FinLang is ever reconsidered, the compiler is ~20 lines: emit one `rule` block per `taxonomy/merchant_dictionary.csv` row with `counterparty == "<normalised_merchant>"` → `category = "<detailed_category>"`, feed a CSV with columns `date,counterparty,memo,amount,category,flags`, and score the `category` column against `gold_leaf`.
