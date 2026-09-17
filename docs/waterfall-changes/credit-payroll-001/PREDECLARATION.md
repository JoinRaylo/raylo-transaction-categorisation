# CREDIT-PAYROLL-001 — exact Waitrose payroll credit

Status: proposed for offline evaluation. Declared 15 September 2026 before
candidate implementation, data matching or candidate scores. Owner/reviewer:
Codex, at Carlos's request. This is one evaluation candidate, not a staging release.

## Hypothesis and boundary

The signed synthetic `WAITROSE PAYROLL` credit GBP 1,989.11 incorrectly reaches
T4 groceries. An explicit payroll narrative can disambiguate this merchant
without an amount threshold or a global credit-policy change.

Append exactly one row to research `taxonomy/rules/t2_entity_collisions.csv`:

- rule ID: `waitrose_explicit_payroll`
- merchant: exact normalized `waitrose` (existing trim/lower behaviour)
- direction: `credit`
- narrative regex: `^[ \t\r\n]*waitrose[ \t]+payroll[ \t\r\n]*$`
- leaf: `salary`; tier: `T2_compound_waitrose_explicit_payroll`

Matching is case insensitive. Only the complete two-word narrative is accepted,
with surrounding ASCII whitespace and spaces/tabs between the words. No salary,
wages, reference suffix, fuzzy merchant or amount inference is introduced. This
is intentionally limited to the observed failure; evidence for broader formats
must be evaluated separately. The same CSV is compiled into the app candidate;
the existing Python implementations and SQL generator remain unchanged.

## Precedence and predeclared cases

The row uses the existing T2 CSV position: after existing code-defined collisions,
before Equifax T3 and T4. Native T1 gambling/council/gig overrides still win.
The explicit narrative wins over a generic provider groceries category. As with
existing T2 salary collisions, it also wins over a contradictory Equifax T3
Refund category: test and disclose this priority, rather than quietly implying
that all native categories are preserved. A real correctly-labelled refund that
becomes salary is grounds to reject the candidate.

Positive cases: exact phrase, case/ASCII whitespace variants, small and large
credits (amount irrelevant), Plaid and Equifax. Verify app transaction boundary
and research resolver, plus generated SQL rule semantics.

Negative/ambiguous cases: debit; zero amount at the Plaid boundary (debit);
plain Waitrose credits at GBP 2.99 and GBP 1,989.11; blank/null merchant or
narrative; other merchants; `Waitrose Ltd`; `PAYROLL`, `WAITROSE SALARY`,
`WAITROSE WAGES`, `WAITROSE PAYROLL 123`; pre/suffixed text; non-ASCII whitespace;
refund/refunded, payroll refund/reversal/returned direct debit/standing order;
SkyBet and McDonalds controls. Preserve their complete baseline result, including
rule/tier, unless they meet the exact positive condition and earlier T1 does not win.

## Acceptance declared before measurement

1. Exact target resolves salary at the new T2 rule with both serving heads.
2. Every synthetic case agrees with the declared boundary and precedence; old
   goldens remain byte-identical. Version additional assertions separately.
3. Full permitted suite: all 15 datasets, seven original synthetic examples,
   both heads, every supported view/slice and independent metric verification.
   Use the unchanged evaluation harness against the preserved 15 September v2
   baseline; no candidate-driven relabelling, model/threshold/mask changes,
   selection or locked v5/v6 scoring.
4. Zero correct-to-wrong changes in labelled development data, zero changes
   outside the declared predicate, and zero raw-head/dictionary-only changes.
   No unexplained regression is accepted, regardless of aggregate gains.
5. Zero unexplained app/research differences; regenerate SQL from its unchanged
   generator and verify that the diff is only the four new leaf/tier branches.
6. No extra T5b residual rows; document actual residual and fixed-cohort metrics.
7. Preserve serving bundle `a2553f3462205963254b0fb1ad9dff6d64e1399abdecaab93977265908c7f23d`.
   Build an explicitly derived, immutable local evaluation bundle with parent
   provenance; preserve every model, mask, taxonomy, dictionary, crosswalk and
   golden byte. Only compiled collision rows and provenance may differ.
8. Record and mirror complete results even if rejected. Passing synthetic tests
   with no independently labelled positive examples establishes implementation
   behaviour and regression evidence only, not production accuracy/generalisation.
   No deployment or production-readiness claim follows from this evaluation.

Baseline private run: `/private/tmp/txncat-waterfall-baseline-20260915-v2`.
Monorepo baseline HEAD: `4cc0b1ff95122006681fb6003738906fe7df7eef`.
Research baseline HEAD: local `0767ea8`, based on frozen resolver `f8e47ef3f449309f733620607c05add8bb0b2723`.
Full input, source and environment hashes will be captured by the evaluation
reports. The historical research checkout has unrelated unpublished work;
only this change's files will be staged and its existing history will not be pushed.
