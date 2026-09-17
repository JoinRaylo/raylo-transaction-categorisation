# Reproducing CREDIT-PAYROLL-001

Run from the monorepo worktree `/private/tmp/txncat-d2-worktree`, with the source
commits recorded in RECORD.md and the original private model/evaluation files.
The app interpreter is Python 3.12; the separately specified research interpreter
is Python 3.14. Do not substitute the original monorepo checkout on another branch.

The candidate source of truth is research's single appended CSV row. Regenerate
its SQL with `python -B src/generate_crosswalk_sql.py` in the research checkout.
No cloud calls or training-data regeneration are needed.

## Derive the candidate locally

```sh
PYTHONPATH=apps/ob-txn-categoriser/src:lib/raylo-txncat/src \
/private/tmp/txncat-c2-env/bin/python apps/ob-txn-categoriser/scripts/derive_payroll_candidate.py \
  --parent /private/tmp/txncat-b4-bundles/a2553f3462205963254b0fb1ad9dff6d64e1399abdecaab93977265908c7f23d \
  --research-root /Users/carlosnoblejesus/Repos/raylo-transaction-categorisation \
  --output /private/tmp/txncat-payroll-candidate-bundles
```

The derivation refuses any other CSV change or source-definition drift. It reuses
verified parent bytes, records the new CSV and source commit, and preserves parent
model/selection/golden lineage. Parent and candidate cannot overwrite one another.
The recorded candidate was built from research c0868b7 with its documented
unrelated dirty patch. A clean checkout or later commit changes provenance and
therefore the bundle SHA; verify operational payloads and use the emitted SHA in
commands rather than misrepresenting that as the recorded artefact.

## Full evaluation and research replay

Commands below are the exact captured invocations. Set
`PYTHONDONTWRITEBYTECODE=1` and
`PYTHONPATH=/private/tmp/txncat-d2-worktree/apps/ob-txn-categoriser/src:/private/tmp/txncat-d2-worktree/lib/raylo-txncat/src`.
Use new, empty output directories when repeating them.

Monorepo worktree:

```sh
/private/tmp/txncat-c2-env/bin/python apps/ob-txn-categoriser/scripts/run_evaluations.py --monorepo-root /private/tmp/txncat-d2-worktree --research-root /Users/carlosnoblejesus/Repos/raylo-transaction-categorisation --research-python /Users/carlosnoblejesus/Repos/raylo-transaction-categorisation/.venv/bin/python --bundle /private/tmp/txncat-payroll-candidate-bundles/ad825a7ad1f5ef5060fe282d1b4c864c55d142982d78a3387350e1bedac3cc41 --bundle-sha ad825a7ad1f5ef5060fe282d1b4c864c55d142982d78a3387350e1bedac3cc41 --output /private/tmp/txncat-payroll-candidate-eval-v1 --baseline /private/tmp/txncat-waterfall-baseline-20260915-v2
```

Research checkout (the mirrored runner; same sources, data, heads and baseline):

```sh
/private/tmp/txncat-c2-env/bin/python tools/waterfall-evaluation/run_evaluations.py --monorepo-root /private/tmp/txncat-d2-worktree --research-root /Users/carlosnoblejesus/Repos/raylo-transaction-categorisation --research-python /Users/carlosnoblejesus/Repos/raylo-transaction-categorisation/.venv/bin/python --bundle /private/tmp/txncat-payroll-candidate-bundles/ad825a7ad1f5ef5060fe282d1b4c864c55d142982d78a3387350e1bedac3cc41 --bundle-sha ad825a7ad1f5ef5060fe282d1b4c864c55d142982d78a3387350e1bedac3cc41 --output /private/tmp/txncat-payroll-research-replay-v1 --baseline /private/tmp/txncat-waterfall-baseline-20260915-v2
```

The preserved baseline predates the candidate CSV. To rerun it, use its original
research source snapshot and parent bundle; do not bypass source verification by
pointing a parent bundle at a changed CSV. The unchanged evaluation-code hashes
allow comparison with the retained, complete v2 baseline. Any future harness or
inventory change requires rerunning both sides with the revised definition.

## Additional checks

Install `google-re2==1.1.20251105` in the isolated directory
`/private/tmp/txncat-payroll-re2`, without changing runtime dependencies. Run with
that directory appended to the PYTHONPATH above:

```sh
/private/tmp/txncat-c2-env/bin/python apps/ob-txn-categoriser/scripts/verify_payroll_candidate.py \
  --parent /private/tmp/txncat-b4-bundles/a2553f3462205963254b0fb1ad9dff6d64e1399abdecaab93977265908c7f23d \
  --candidate /private/tmp/txncat-payroll-candidate-bundles/ad825a7ad1f5ef5060fe282d1b4c864c55d142982d78a3387350e1bedac3cc41 \
  --research-root /Users/carlosnoblejesus/Repos/raylo-transaction-categorisation \
  --monorepo-root /private/tmp/txncat-d2-worktree \
  --report /private/tmp/txncat-payroll-targeted-v1.json
```

Independent complete-record review (stdlib only):

```sh
python apps/ob-txn-categoriser/research/waterfall-changes/credit-payroll-001/review.py \
  --baseline /private/tmp/txncat-waterfall-baseline-20260915-v2 \
  --candidate /private/tmp/txncat-payroll-candidate-eval-v1 \
  --replay /private/tmp/txncat-payroll-research-replay-v1 \
  --output /private/tmp/txncat-payroll-review-v1.json
```

The coverage audit uses `inventory_sources` and `adapt` from the unchanged runner
on all 15 permitted tasks. For each adapted source, it counts rows whose original
merchant lower/trim equals `waitrose` and direction equals `credit`, then counts
complete-narrative matches to the predeclared regex; gold labels are aggregated
without alteration. Every count is zero. Merchant-only inputs retain unknown
direction and do not become invented credit examples. Dataset hashes and task
adapters are exactly those in summary.json, not a new data extract.

No commands in this record publish an artefact or deploy a service. Promotion
requires its own release pins, signed staging checks and explicit decision.
