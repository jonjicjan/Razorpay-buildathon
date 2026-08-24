# Data strategy

**The dataset is synthetic and is used to validate the system methodology, not to claim production-level chargeback performance.**

## Non-circular generation

Labels are **not** `f(features)`.

Each row is drawn from an archetype with:

- overlapping feature distributions
- an archetype-level win-rate prior
- a hidden adjudicator factor (never a model feature)
- random procedural flips (~10%)
- random missingness
- a late-period drift archetype (months 9–12 only)

Train / val / test use **independent RNG seeds**.

## Temporal split

| Split | Months | Seed |
|---|---|---|
| Train | 1–8 | 101 |
| Validation | 9–10 | 202 |
| Held-out test | 11–12 | 303 |

Thresholds are chosen on validation. Test is touched once with `--final-test`.

## Leakage blocklist

See `data/synthetic/archetypes.yaml` and `ml/features/schema.py`.
