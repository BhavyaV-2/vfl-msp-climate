# Data Card: Three-Party MSP Climate-Responsiveness Dataset

This data card documents the three raw CSV files in `data/`, which together form the vertically-partitioned dataset used in the paper *"Vertical Federated Learning with Season-Split Architecture for Causal Assessment of Climate Responsiveness in India's Minimum Support Price Policy."*

## Summary

| | |
|---|---|
| **States** | 5 — Gujarat, Haryana, Maharashtra, Punjab, Uttar Pradesh |
| **Crops** | 19 — Bajra, Barley, Cotton, Gram, Groundnut, Jowar, Maize, Masoor, Moong, Paddy, Ragi, Rapeseed & Mustard, Safflower, Sesame, Soybean, Sunflower, Tur, Urad, Wheat |
| **Seasons** | 2 — Kharif, Rabi |
| **Years** | 16 — 2007–2022 |
| **Alignment key** | `(year, state, crop, season)` for Parties B and C; `(year, state)` for Party A |
| **Personal/farmer-level data** | None — all records are aggregated state-crop-year(-season) statistics from public sources |

## File 1: `party_A_weather.csv` — Climate/structural (Party A)

**Source**: NASA POWER Agroclimatology archive, queried at fixed geographic centroids per state (Gujarat 22.26°N/71.19°E, Haryana 29.06°N/76.09°E, Maharashtra 19.75°N/75.71°E, Punjab 31.15°N/75.34°E, Uttar Pradesh 26.85°N/80.95°E).

**Granularity**: one row per `(year, state)` — 5 states × 16 years = **80 rows**. This is *not* crop- or season-specific at the row level; instead, each row carries both Kharif- and Rabi-season aggregates as separate columns.

**Columns** (28 total):
- `year` (int, 2007–2022), `state` (string)
- 13 monthly NASA POWER parameters, each aggregated twice — once as a **Kharif-season mean** (June–October of year *t*) and once as a **Rabi-season mean** (November of year *t* through April of year *t*+1, indexed to sowing year *t*), suffixed `_Kharif` / `_Rabi`:
  - `ALLSKY_SFC_PAR_TOT` — photosynthetically active radiation
  - `ALLSKY_SFC_SW_DWN` — shortwave downward radiation
  - `GWETPROF`, `GWETROOT`, `GWETTOP` — soil wetness (profile / root zone / surface)
  - `PRECTOTCORR` — corrected total precipitation
  - `QV2M` — specific humidity at 2m
  - `RH2M` — relative humidity at 2m
  - `T2M`, `T2M_MAX`, `T2M_MIN`, `T2M_RANGE` — temperature at 2m (mean/max/min/range)
  - `WS10M` — wind speed at 10m

**Missing values**: none observed in the raw file.

**Note on paper's Party A feature count (63)**: the raw file above contains 26 weather columns (13 parameters × 2 seasons). The paper's model input (63 features) additionally includes 3 structural covariates, 8 binary shock/season indicator flags, and 26 interaction terms — these are engineered downstream in `preprocessing/party_A_weather_prep.py` / the notebook, not present in the raw CSV.

**Provenance caveat**: NASA POWER natively spans 2007–2024; this extract is truncated to 2007–2022 to match Party C's (DES) coverage window after the three-party join.

## File 2: `party_B_economic.csv` — Economic (Party B)

**Source**: Commission for Agricultural Costs and Prices (CACP) published reports, manually digitized across 41 season-year report files.

**Granularity**: one row per `(year, state, crop, season)` — **1,353 rows**.

**Columns** (6 total):
- `year` (int, 2007–2022), `state` (string), `crop` (string), `season` (string: Kharif/Rabi)
- `c2` (float) — Cost of Cultivation, Rs/Quintal, as computed by CACP (includes imputed value of family labor, rent, and interest on fixed capital)
- `msp` (float) — Minimum Support Price, Rs/Quintal, as announced by the Government of India

**Missing values**: none in this file — values that were unavailable in the original CACP reports have already been gap-filled per the paper's stated procedure: (1) national-mean C2 substitution across reporting states for that crop-year, then (2) linear interpolation with edge back/forward-fill. **35.7% of `c2` records in the paper's analysis are gap-filled** by this procedure.

**Note on the imputation flag**: the paper's model input (Party B, 2 features) includes an `c2_is_imputed` binary flag marking gap-filled rows. That flag is not a column in this raw file — it is derived and attached during preprocessing (`preprocessing/party_B_economic_prep.py`), since gap-filling happens as part of the digitization/cleaning pipeline rather than being recorded at source.

**Endogeneity note**: MSP (`msp`) is the outcome variable in the causal battery (Section 5 of the paper) and is *deliberately excluded* from the VFL model's predictive feature set, to avoid the endogeneity contamination documented in prior yield-prediction literature (features correlated with the trend inflating attribution to policy cost).

## File 3: `party_C_production.csv` — Production (Party C)

**Source**: Directorate of Economics and Statistics (DES) district-level workbooks, aggregated to state level.

**Granularity**: one row per `(year, state, crop, season)` — **1,353 rows** (same key space as Party B, pre-cleaning).

**Columns** (7 total):
- `year` (int, 2007–2022), `state` (string), `crop` (string), `season` (string: Kharif/Rabi)
- `Area (Hectare)` (float) — sown area
- `Production (Tonnes)` (float) — total production
- `Yield (Tonne/Hectare)` (float) — recomputed as `Production / Area` **after** state-level aggregation (not averaged from district-level yields, to avoid incorrectly equal-weighting small and large districts)

**Missing values**: **4 missing values** across the `Area`, `Production`, and `Yield` columns combined, in the raw extract.

**Unit conversion note**: per the paper, cotton production reported in bales by DES is converted to tonnes using the factor 25/147 prior to this extract.

## Downstream processing (not in raw files, see `preprocessing/` and notebook)

The paper's analysis dataset is built from these three files as follows:
1. **Join**: inner join on `(year, state, crop, season)` across all three parties → 1,353 records.
2. **Cleaning**: remove 2 null-yield rows (→1,351); drop 81 first-year lag-NaN rows per state-crop series, since the deviation target requires a prior-year trend fit (→1,270); trim 99th-percentile yield outliers (→~1,256 final records).
3. **Deviation target**: log-yield deviation from a per-crop-state linear trend fit exclusively on 2007–2019 training years (see paper Eq. 1).
4. **Temporal split**: 2007–2019 (~1,011 records) train / 2020–2022 (~245 records) validation, with all scaling parameters and baselines fit on training data only.
5. **Key alignment for federated training**: in the paper's VFL setup, records are aligned via SHA-256 hashed private-set-intersection on the composite key, consistent with the vertical-partition threat model — raw features are never centralized across parties A and B.

## Ethics and licensing

All three source files are derived from public government/institutional data (NASA POWER, CACP reports, DES workbooks). No personal, farmer-level, or otherwise individually identifiable data is included at any stage. Reuse should credit the original data providers:
- NASA POWER: Chandler, W.S. et al., 2018. *NASA POWER: Prediction of Worldwide Energy Resources.* NASA Langley Research Center.
- CACP: Government of India, Commission for Agricultural Costs and Prices, published season-wise reports.
- DES: Government of India, Directorate of Economics and Statistics, district-level workbooks.
