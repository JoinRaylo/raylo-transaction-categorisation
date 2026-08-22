# Rent feature IV: before vs after the R13 fix

Persistence feature (COUNT DISTINCT months with a rent transaction), computed two ways on the same 83873-proposal outcome cohort: OLD = crosswalk as it stood before today's R13 fix, NEW = with R13 (targeted rent-keyword rule) enabled. 16282 of 194877 candidate transactions changed leaf assignment.

| Outcome | Old IV | New IV | Change |
|---|---|---|---|
| month3_1plus_pia | 0.0086 | 0.0085 | -0.0001 |
| month12_1plus_pia | 0.0068 | 0.0067 | -0.0001 |
| month12_3plus_pia | 0.0071 | 0.0071 | -0.0001 |

For reference, mortgage's persistence IV (existing, unaffected by this fix) is documented at 0.0653 -- the original comparison point for the 'rent gap'.

**Why IV is flat despite a real coverage fix:** only 485 of 83,873 proposals (0.6%) had their persistence count change at all; 239 went from 0 to 1+ months. R13 fixed 16,282 transaction-level misclassifications, but most belong to proposals that already had rent detected in at least one other month via the native crosswalk -- so the binary/count signal at proposal level barely moves. The fix is still worth keeping (better per-transaction accuracy, cleaner audit trail for fair-lending review), it just isn't a risk-model win on its own.
