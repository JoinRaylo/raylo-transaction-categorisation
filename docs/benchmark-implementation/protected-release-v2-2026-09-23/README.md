# Protected release v2: the benchmark, not just the pilot (2026-09-23)

The training-data protection gate (B04, AIE-513) used to protect only the 500-row
AIE-512 pilot. It now protects the combined membership that will be scored: the
2,000-row benchmark plus the 1,295 new rows of the expansion draft being labelled
to join it. That is 3,295 transactions, 2,832 accounts and 2,695 customers.

- **Binding schema v2.** `membership_sha256` is the membership that every guard,
  receipt and promotion check protects. The pilot's frozen outcome publication is
  still verified against the membership it was frozen with
  (`publication_membership_sha256`). v1 bindings behave exactly as before.
- **Protection only grows.** `verify_protected_superset` confirmed when the
  release was pinned that every pilot transaction, account and customer is
  protected, with unchanged account→customer links. See
  [`pin-evidence.json`](pin-evidence.json).
- **Consequence.** Receipts issued under the v1 binding no longer verify, so every
  learning input must come from a guarded rebuild. That was already required,
  because no pre-B04 training artefact carries receipts.

The private combined membership file is kept outside Git at
`~/.local/share/raylo-txncat/benchmark-protected-3295-2026-09-23/protected-membership.csv`
(mode 0600).
