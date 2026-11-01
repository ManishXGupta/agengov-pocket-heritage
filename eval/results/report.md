# Evaluation report (synthetic data)

These results come from the synthetic test set in `eval/testset.jsonl`. They show that the
governance rules behave as specified in the paper. They are **not** field results.

| Measure | Value |
|---|---|
| cases | 25 |
| G1_approved_source_share | 1.0 |
| G2_sensitive_leak_rate | 0.0 |
| G3_claim_evidence_share | 1.0 |
| G4_correct_abstention | 1.0 |
| G5_escalation_correctness | 1.0 |
| G6_audit_completeness | 1.0 |
| plurality_coverage | 1.0 |
| decision_accuracy | 1.0 |
| curator_tasks | 15 |
| policy_version | cfg-406a5400798f |

| Case | Gap | Expected | Got | T | Q | A | Pass | Note |
|---|---|---|---|---|---|---|---|---|
| t5-1 | G3 | answer | answer | 0.96 | 0.10 | 1 | yes | Table V row 1: photo of the gate mural |
| t5-2 | G3 | answer | answer | 0.91 | 0.12 | 1 | yes | Table V row 2: explore step by step |
| t5-3 | G3 | answer | answer | 0.90 | 0.12 | 1 | yes | Table V row 3: contested origin, two accounts |
| t5-4 | G3 | answer | answer | 0.96 | 0.10 | 1 | yes | Table V row 4: same question by voice in Spanish |
| t5-5 | G2 | refuse | refuse | 0.98 | 0.46 | 0 | yes | Table V row 5: protected location |
| t5-6 | G4 | refuse | refuse | 0.06 | 0.01 | 1 | yes | Table V row 6: object not in passport set |
| g1-1 | G1 | refuse | refuse | 0.32 | 0.01 | 1 | yes | only an unapproved source exists |
| g1-2 | G1 | answer | answer | 0.89 | 0.10 | 1 | yes | withdrawn guidebook claim must be dropped |
| g1-3 | G1 | refuse | refuse | 0.33 | 0.03 | 1 | yes | high match confidence cannot compensate for no approved source |
| g2-1 | G2 | refuse | refuse | 0.44 | 0.28 | 0 | yes | community-restricted practice strand |
| g2-2 | G2 | answer | answer | 0.99 | 0.28 | 1 | yes | public identity only; restricted details withheld |
| g2-3 | G2 | review | review | 0.67 | 0.28 | 1 | yes | donor personal data is internal; record is stale and unapproved |
| g2-4 | G2 | refuse | refuse | 0.97 | 0.03 | 0 | yes | student without recorded consent |
| g2-5 | G2 | review | review | 0.97 | 0.31 | 1 | yes | photo framed around a person: D = 1 lifts Q into the review band |
| g2-6 | G2 | refuse | refuse | 0.97 | 0.01 | 0 | yes | unknown role fails authentication |
| g4-1 | G4 | refuse | refuse | 0.00 | 0.01 | 1 | yes | no candidate at all |
| g4-2 | G4 | refuse | refuse | 0.10 | 0.01 | 1 | yes | just below match threshold |
| g4-3 | G4 | refuse | refuse | 0.19 | 0.01 | 1 | yes | confident match to an object with no passport |
| g4-4 | G4 | answer | answer | 0.90 | 0.01 | 1 | yes | weak but valid match on a strong passport |
| g5-1 | G5 | review | review | 0.63 | 0.14 | 1 | yes | stale, unapproved record goes to a curator |
| g5-2 | G5 | review | review | 0.99 | 0.45 | 1 | yes | even curators need a second review for a sacred location |
| g5-3 | G5 | review | review | 0.65 | 0.30 | 1 | yes |  |
| ans-1 | G3 | answer | answer | 0.97 | 0.03 | 1 | yes | student sees education-level claim |
| ans-2 | G3 | answer | answer | 0.97 | 0.01 | 1 | yes | tourist does not see education-level claim |
| ans-3 | G3 | answer | answer | 0.97 | 0.01 | 1 | yes |  |
