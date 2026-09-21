# B03-F pilot reconstruction and Opus 5 adjudication pass

Status: **v2 pilot reservation recovered byte-identically; Opus 5 adjudication
first pass recorded; lead review complete; 61 rows escalated to Carlos. Zero
final labels exist; `authorizes_consumption` is false throughout.**

This milestone records the 2026-09-21 recovery of the approved v2 evaluation
pilot after its local working artifacts were lost, plus the subsequent
model-assisted adjudication pass (AIE-511). Every step below is receipt-bound;
all private artifacts live under
`~/.local/share/raylo-txncat/benchmark-eval-pilot/reconstruction-2026-09-21/`
(directories `0700`, files `0600`, retention owner Carlos).

## 1. Provider recovery

The original batch artifacts were recovered read-only from the provider APIs:

- Anthropic Message Batch `msgbatch_01GFrYE77BM3Rao63Ehks4GP` — 500 results,
  all succeeded.
- Gemini — 11 batches listed and retrieved (three attempt waves per model plus
  synthetic acceptance batches); all responses retrievable.

Parsing reused the production strict parser in `annotation_pilot.py`. Final
valid votes: Sonnet 5 = 500, Gemini 3.8 Flash = 499, Gemini 3.7 Flash = 499.

**Accepted discrepancy:** each Gemini model has exactly one item whose
attempt-1 response failed with `MAX_TOKENS` and was omitted from the attempt-2
retry batch, and appears in no later batch. Both items have valid votes in the
other two streams. No fourth attempt exists; the retry cap of three was
respected and no provider calls were made to repair the gap.

Three-way comparison: 259 unanimous (235 labelled / 11 ambiguous /
13 insufficient evidence), 239 disagreement, 2 incomplete → 265 review rows,
versus the reviewed milestone's 261/239/0 → 263. The difference is exactly the
two missing Gemini votes; both affected items are otherwise unanimous-labelled.
Recorded in `votes/votes-receipt.json` (`milestone_match: false`); nothing was
synthesised.

## 2. Re-identification of the 500 rows

`tools/benchmark/recover_eval_pilot_membership.py` re-executed the pinned
candidate draw's identity join (BigQuery job
`txncat_pilot_recover_9803b1e5-1434-46d1-955c-403c3a5bcead`; 9,008,761,395
bytes dry-run, 9,009,364,992 billed; recovery SQL sha `d0c151e2…`). It returned
500/500 rows, 474 distinct accounts, 464 distinct customers, zero missing
pilot IDs, pilot-ID set sha `9074da7b…`, bound to the pinned candidate result
sha `f9c549ee…`.

## 3. Exposure index rebuild

`tools/benchmark/benchmark_build_index.py` rebuilt the B02 index using the
existing archived identity key (`benchmark-private-20260916-v1`; no
`--create-key`). The resulting `receipt.json` matches the archived receipt on
every field: `database_sha256` `61cc0a42…` (**byte-identical** 2.1 GB SQLite),
`key_check` `49105456…`, inventory sha `bb0c02de…`, and all five source entries
(row counts, hashes, purposes, projections). `benchmark_verify_index.py`
re-ran all 40 historical-overlap checks against the B01 audit directory —
all passed.

## 4. View reconstruction — fingerprint all pass

`tools/benchmark/reconstruct_eval_pilot_views.py` re-profiles the 500 recovered
rows against the rebuilt index and merchant screen, then re-runs the
deterministic whole-customer allocation (`eval-pilot-v1`, 250/150/100, max 4
rows per customer, no prior membership). The reconstructed assignment passes
every fingerprint check:

| Check | Expected | Actual |
| --- | --- | --- |
| primary views (rep/unseen/unfamiliar) | 250/150/100 | 250/150/100 |
| distinct customers | 464 | 464 |
| max rows per customer | ≤4 | 4 |
| view tags (rep/unseen/unfamiliar) | 500/389/156 | 500/389/156 |
| unfamiliar ⊆ unseen | yes | yes |
| historical input overlap (rep/unseen/unfamiliar) | 111/0/0 | 111/0/0 |
| disagreement by view | 109/71/59 | 109/71/59 |
| abstention by view | 11/5/8 | 11/5/8 |
| unanimous labelled (incomplete restored) | 130/74/33 | 130/74/33 |

The two incomplete items land in `representative` and `unseen_input`.

Regenerated `pilot.jsonl` sha256 `fc5c626c…` and `membership.csv` sha256
`0afb4155…` are **byte-identical to the approved v2 artifacts** — the
reservation is fully recovered, including row order.

## 5. Opus 5 adjudication pass (AIE-511)

`tools/benchmark/adjudicate_pilot_opus.py` ran a model-assisted first pass over
the 265 review rows with `claude-opus-5`, Anthropic Message Batches only,
per-item alias blinding (annotator A/B/C order shuffled per item), and strict
`ProposedAdjudication` schema validation.

- Synthetic acceptance attempt 1 (`msgbatch_01AK3qyS9itM1GtZFCWq4NUW`): 10/10
  API-errored on a deprecated `temperature` parameter; the instrument was
  corrected, prompts unchanged.
- Synthetic acceptance v2 (`msgbatch_015xUFcA91sJo3v2oEuUtrhs`): 10/10
  strict-valid.
- Real run (`msgbatch_016mzC71m6c29kcUZDm3aCXU`): 265/265 valid on attempt 1,
  zero retries; 3,512,668 input / 88,684 output tokens.
- Outcomes: 156 labelled / 83 ambiguous / 26 insufficient evidence; by primary
  view representative 75/41/5, unseen-input 43/24/10, unfamiliar 38/18/11.
- System prompt sha `5c2cb63d…`, response schema sha `e67b52be…`.

Opus proposals are adjudication aids, **not independent votes**; the
`ProposedAdjudication` contract (`benchmark_annotation.py`) forbids
`is_independent_vote` and `is_human_gold`.

## 6. Lead review and Carlos escalation queue

The lead reviewed all 265 proposals: 204 agree / 33 disagree / 28 unsure.
61 rows escalate to Carlos (representative 31, unseen-input 19,
unfamiliar-merchant 11). Six policy groups await rulings: A named-individual
counterparty (101 rows), B sort-code transfers (4), C pot withdrawals (4),
D intermediary with visible merchant (9), E daily overdraft interest (6),
F mobile-channel mechanism (7). The review workbook
(`carlos_adjudication_review_2026-09-21.xlsx`) carries editable ruling fields
with dropdown validation; `workbook-receipt.json` binds it to all inputs.
`carlos_decisions=0`, `final_labels_created=0`.

## 7. Deviations recorded

- Model-assisted first pass replaces the originally planned blind first
  review — approved by Carlos 2026-09-21.
- Opus is not an independent vote; its proposals never enter the three-vote
  comparison.
- Two items carry incomplete vote tuples (accepted, unrepaired).

## Retention and authorization

All private artifacts remain under the reconstruction root with owner-only
permissions. The full file inventory with sha256s is in `verification.json`.
Nothing in this packet authorizes consumption, creates labels, trains or
selects models, or modifies cloud state. Next gate: Carlos's 61 escalated
decisions plus six policy rulings, then the AIE-512 receipt-bound importer.
