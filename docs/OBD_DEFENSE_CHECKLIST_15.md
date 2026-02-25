# OBD Presentation Defense Checklist (15)

1) False-positive cost quantified?
- Current: Partial
- Needed: cost matrix by alert tier

2) False-negative risk quantified?
- Current: Partial
- Needed: FN impact table by domain

3) Stability under missing/irregular data?
- Current: Answerable
- Needed: one screenshot/log proving gate fallback path

4) Vehicle-model generalization proof?
- Current: Not answerable
- Needed: holdout comparison across model groups

5) Threshold rationale?
- Current: Answerable
- Needed: one slide with q99 + alarms/hour derivation

6) Why k_consecutive and cooldown?
- Current: Partial
- Needed: policy sweep rationale table

7) Synthetic metric interpretation boundaries?
- Current: Answerable
- Needed: explicit non-generalization statement in final deck

8) Why this model choice (LSTM vs IF)?
- Current: Answerable
- Needed: keep same-condition KPI table in appendix

9) Policy design reason?
- Current: Answerable
- Needed: concise policy flow diagram

10) Latency SLA?
- Current: Partial
- Needed: target SLA threshold statement + environment-bound disclaimer

11) Reproducibility?
- Current: Answerable
- Needed: pin environment/version hash in runbook

12) Why window=60 / stride=30?
- Current: Partial
- Needed: stride sensitivity summary

13) Usable-window rate?
- Current: Answerable
- Needed: add pass-rate trend chart by trip

14) Event hit rate / time-to-detect?
- Current: Answerable
- Needed: add event-type breakdown table

15) Doc-code consistency guaranteed?
- Current: Partial
- Needed: consistency checklist with owner/date
