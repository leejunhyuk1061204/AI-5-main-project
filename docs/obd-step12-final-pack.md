# OBD Step12 Final Pack

## 1) Final Candidate (Experiment)
- threshold: `0.87`
- k_consecutive: `3`
- warning: `0.78`
- critical: `0.86`

## 2) Fixed Metrics (Synthetic Benchmark)
- Precision: `0.50`
- Recall: `0.50`
- F1: `0.50`
- FPR: `0.25`
- Confusion Matrix: `TP=3, FP=3, TN=9, FN=3`

## 3) Operation Rule
- The values above are **experiment values** for benchmark comparison.
- Operation policy value (`threshold_policy.json`) is managed separately.
- Final operation lock requires team approval after real labeled replay verification.

## 4) Demo Script (3 min)
1. Problem:
   - Real labeled anomaly data is insufficient, so direct supervised validation is limited.
2. Method:
   - One-class hybrid engine detection (IF + LSTM-AE) + quality gating + policy.
3. Result:
   - Fixed candidate and metrics listed above.
4. Risk/Limit:
   - Trade-off between FPR and Recall in threshold-based detection.
   - Current benchmark is synthetic-heavy; real-labeled validation is next.
5. Next:
   - Expand real labeled set, rerun same pipeline, then lock operation policy.

## 5) Q&A (Top 5)
1. Why synthetic?
   - To quantify policy behavior when real anomaly labels are insufficient.
2. Why one-class?
   - Current dataset structure is normal-dominant.
3. Why not maximize Recall only?
   - That increases FPR and hurts operation reliability.
4. Why this candidate?
   - It gives the best balance under recall-constrained selection.
5. What is next for production?
   - Real-labeled replay validation and policy lock with approval.

## 6) Release Checklist
- [ ] Board status updated (Done/In Progress/Todo)
- [ ] `docs/obd-anomaly-progress.md` locked
- [ ] Step12 smoke logs linked
- [ ] Final commit/push completed
- [ ] Final rehearsal completed
