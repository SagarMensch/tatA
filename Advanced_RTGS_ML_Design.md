# Advanced RTGS ML + Mathematical Decisioning Blueprint

This blueprint adds a production-ready, explainable **hybrid ML + rule system** for RTGS reconciliation.

## What is implemented

- **Decision Tree confidence model** for match confidence scoring.
- **Rete-like policy rules** for lane routing (`GREEN`, `YELLOW`, `RED`).
- **Robust math anomaly detector** using MAD (Median Absolute Deviation).
- **Policy outcomes** mapped to business actions:
  - `AUTO_POST_FP25`
  - `AUTO_WRITE_OFF_AND_POST` (≤ ₹10 variance policy)
  - `PARK_AND_NOTIFY_APPROVER`
  - `ESCALATE_TO_CONCERN_TEAM`

## Why this is advanced but safe for finance

- ML gives probabilistic confidence on fuzzy matching.
- Symbolic rules preserve deterministic finance controls.
- Mathematical anomaly scoring catches outlier deltas.
- Every decision is explainable (`reason`, `lane`, `decision`, `confidence`).

## Core module

Implementation lives in `advanced_rtgs_ml_engine.py` and includes:

1. **Feature engineering**
   - amount delta and delta %
   - date gap in days
   - CA exact-match binary feature
   - channel family indicator (RTGS/NEFT/IMPS)
   - text similarity on transaction narration vs customer
   - historical hit ratio

2. **Model layer**
   - Uses `sklearn.tree.DecisionTreeClassifier` if available.
   - Falls back to deterministic weighted scoring when sklearn is unavailable.

3. **Rule layer**
   - Rule priority and first-match policy execution.
   - Allows fast extension for new business policies.

## Suggested next steps for your RTGS production rollout

1. Train with real historical matching labels from SAP (match=1, mismatch=0).
2. Add feature store for per-CA behavior drift and temporal seasonality.
3. Add model calibration and threshold governance for monthly audits.
4. Integrate with SAP posting adapter and exception mailer.
5. Add replay testing on prior month data before go-live.
