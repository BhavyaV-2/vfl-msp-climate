# Vertical Federated Learning for Causal Assessment of Climate Responsiveness in India's MSP Policy

This repository contains the data, preprocessing, and analysis notebook for the paper *"Vertical Federated Learning with Season-Split Architecture for Causal Assessment of Climate Responsiveness in India's Minimum Support Price Policy"* (submitted to ACM IKDD CODS-COMAD 2026).

## What this project does

India's Minimum Support Price (MSP) is meant to buffer farmers against climate-driven yield shocks, but no prior study has tested — with panel causal methods — whether MSP revisions actually respond to the climate signal they nominally insure against. This project:

1. Builds a **vertical federated learning (VFL)** model with season-split encoders (Kharif/Rabi/structural branches) and FiLM-conditioned crop-group fusion to predict a climate-isolated **yield-deviation target**, keeping the three data parties' raw features from ever being centralized.
2. Runs a **six-test causal identification battery** (doubly-robust panel OLS, a Cragg two-part model, Dumitrescu–Hurlin panel Granger causality, Chow structural-break tests, and a 297-event quasi-experimental event study) against the null hypothesis that MSP does not respond to climate-driven yield deviations.
3. Computes **federated gradient-saliency attribution** to identify which drivers (climate vs. structural vs. policy cost) explain predicted yield deviations, without centralizing raw features.

Headline findings: median per-crop R² = 0.621 (VFL, 2020–2022 holdout), VFL outperforms XGBoost/LightGBM baselines by +0.086 R² on the deviation target, 89.6% of gradient-saliency attribution falls on pure climate drivers, and five of six causal tests fail to reject the null of no MSP climate-responsiveness.

## Repository structure

```
repo/
├── README.md                          # this file
├── data_card.md                       # dataset documentation (schema, provenance, licensing, limitations)
├── data/
│   ├── party_A_weather.csv            # Party A — NASA POWER agroclimatology (climate/structural)
│   ├── party_B_economic.csv           # Party B — CACP cost of cultivation (C2) and MSP
│   └── party_C_production.csv         # Party C — DES area/production/yield
├── preprocessing/
│   ├── data_transformation_party_a.py        # cleaning/aggregation for Party A
│   ├── data_transformation_party_b.py       # cleaning/imputation for Party B
│   ├── data_transformation_party_c.py     # cleaning/aggregation for Party C
└── FINAL_PAPER_NOTEBOOK.ipynb         # end-to-end analysis: EDA → causal battery → VFL model → attribution → conformal prediction
```

## The three-party vertical partition

The dataset is split across three institutionally distinct custodians, aligned on the composite key `(year, state, crop, season)`:

| Party | Source | File | Content |
|---|---|---|---|
| **A** — Climate/structural | NASA POWER Agroclimatology | `party_A_weather.csv` | Seasonal (Kharif/Rabi) weather aggregates per state-year — 26 raw weather features expanded to 63 with structural/binary/interaction terms in preprocessing |
| **B** — Economic | CACP published reports | `party_B_economic.csv` | Cost of cultivation (C2, Rs/Quintal) and MSP (Rs/Quintal) per state-crop-season-year |
| **C** — Production | DES district-level workbooks | `party_C_production.csv` | Area (Ha), Production (Tonnes), and derived Yield (T/Ha) per state-crop-season-year |

Party A is a state-year panel (5 states × 16 years = 80 rows); Parties B and C are state-crop-season-year panels (1,353 rows each before cleaning). See `data_card.md` for full schema and provenance details.

## Important caveats (see paper for full discussion)

- This is a **research-stage, single-machine implementation** of the VFL architecture. No cryptographic secure aggregation or differential-privacy calibration is applied to the exchanged gradient embeddings — production deployment would require both.
- The dataset covers **5 states and ~1,256 records over 16 years**, excluding major rainfed states (Madhya Pradesh, Rajasthan, Odisha) and northeast India. Causal findings speak to short-run shock responsiveness, not long-run climate adaptation.
- MSP is deliberately **excluded** from the model's predictive features to avoid endogeneity contamination of attribution (see Hu et al., cited in the paper).

## License / attribution

All raw data originates from public government and institutional sources: NASA POWER, CACP (Commission for Agricultural Costs and Prices) published reports, and DES (Directorate of Economics and Statistics) workbooks. No personal or farmer-level data is included. See `data_card.md` for source-specific citation details.
