# False-positive economics

Placeholder assumptions (INR), labelled as assumptions — not measured merchant data:

| Symbol | Meaning | Placeholder |
|---|---|---|
| FP | Fight an unwinnable dispute (analyst time + queue cost) | ₹2500 |
| FN | Skip a winnable dispute (discounted recoverable loss) | ₹3500 |

Expected cost at threshold `t`:

```text
cost(t) = FP_count(t) * FP_unit + FN_count(t) * FN_unit
```

We minimize this on the **validation** set for the **binary** contest decision used in formal metrics.

Three-way desk routing (`DO_NOT_FIGHT` / `MANUAL_REVIEW` / `RECOMMEND_CONTEST`) uses explicit **policy bands** (0.35 / 0.65) from `archetypes.yaml`, kept separate from the binary cost-optimal threshold so workflow tiers stay interpretable.
