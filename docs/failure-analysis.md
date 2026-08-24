# Failure analysis

Updated during build:

1. **Circular synthetic labels (rejected early)**  
   A linear `label = f(features)` generator would make metrics meaningless. Replaced with archetype priors + hidden noise + flips.

2. **Random split risk**  
   Avoided. Temporal months + independent seeds for train/val/test.

3. **LLM as classifier temptation**  
   Rejected. LLM only writes evidence packages after deterministic routing to `RECOMMEND_CONTEST`.

4. **Missing API key during demo**  
   Mitigated with a grounded template assembler labelled `template_fallback`, plus three seeded desk cases.

5. **Threshold overfit to test**  
   Cost-optimal threshold selected on validation; test evaluated once via `--final-test`.

6. **Cost-optimal threshold collapsing the review band**  
   With FN ≫ FP, binary cost optimum pushed near zero and almost every case looked contestable. Fixed by separating **binary cost-optimal metrics** from explicit **policy tier bands** (0.35 / 0.65) for the desk workflow.
