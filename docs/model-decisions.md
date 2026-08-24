# Model decisions

- **Rule baseline:** contest only if delivery AND 3DS are present.
- **Logistic regression / shallow tree:** linear and interpretable baselines.
- **XGBoost:** final model for tabular interactions.
- **Not used for classification:** LLM — worse fit for dense tabular features, harder to evaluate honestly.
- **SHAP / gain signals:** model-native importance for analyst-facing “why”, not LLM storytelling about the score.
