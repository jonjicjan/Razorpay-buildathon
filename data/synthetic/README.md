# Synthetic chargeback data

**The dataset is synthetic and is used to validate the system methodology, not to claim production-level chargeback performance.**

## What this is

A labelled proxy for *representment winnability*: given a chargeback at notification time, would the merchant have won if they contested?

Labels are **not** computed as `f(features)`. Each row is drawn from an **archetype** with:

1. Overlapping feature distributions (no single flag identifies the class)
2. An archetype-level win-rate **prior**
3. A hidden adjudicator factor that is never a model feature
4. Random 8–12% outcome flips (procedural failure / scheme discretion)
5. Random missingness
6. A new pattern injected only in months 9–12 (temporal drift)

Train, validation, and test are generated with **independent RNG seeds**, then assigned to calendar months. The test file is frozen at generation time.

## How to generate

```bash
python -m data.synthetic.generator
```

Outputs:

- `data/splits/train.csv`
- `data/splits/val.csv`
- `data/splits/test.csv`
- `data/splits/generation_manifest.json`

## Leakage

See `leakage_blocklist` in `archetypes.yaml`. Outcome, archetype name, hidden factors, and adjudication timestamps must never enter the model.
