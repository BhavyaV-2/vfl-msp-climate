import os
import tempfile
import zipfile

import numpy as np
import pandas as pd

# ── USER CONFIG ────────────────────────────────────────────────────────────────
ZIP_PATH   = r"/content/Area, Production & Yield.zip"
OUTPUT_CSV = r"party_C_production.csv"

# ── CONSTANTS ──────────────────────────────────────────────────────────────────
TARGET_STATES = {
    'Gujarat', 'Haryana', 'Maharashtra', 'Punjab', 'Uttar Pradesh'
}

YEAR_RANGE = set(range(2007, 2023))          # start-years: 2007-08 … 2022-23

# DES stores Cotton(lint) production in Bales; exact conversion to Tonnes:
#   production_tonnes = production_bales × 25/147
# (verified against all 80 cotton rows in the final CSV)
COTTON_BALE_TO_TONNE = 25 / 147

# Crop renames: DES source name  →  final CSV name
CROP_RENAME = {
    'Rice'              : 'Paddy',
    'Arhar/Tur'         : 'Tur',
    'Sesamum'           : 'Sesame',
    'Cotton(lint)'      : 'Cotton',
    'Rapeseed &Mustard' : 'Rapeseed & Mustard',
    'Moong(Green Gram)' : 'Moong',
    'Soyabean'          : 'Soybean',
}

TARGET_CROPS = {
    'Bajra', 'Barley', 'Cotton', 'Gram', 'Groundnut', 'Jowar',
    'Maize', 'Masoor', 'Moong', 'Paddy', 'Ragi', 'Rapeseed & Mustard',
    'Safflower', 'Sesame', 'Soybean', 'Sunflower', 'Tur', 'Urad', 'Wheat',
}

# Which season each file represents
FILE_SEASON = {
    'kharif_2000-12.xlsx': 'Kharif',
    'kharif_2012-23.xlsx': 'Kharif',
    'rabi_2000-12.xlsx'  : 'Rabi',
    'rabi_2012-23.xlsx'  : 'Rabi',
}


# ── CORE FUNCTION ──────────────────────────────────────────────────────────────
def process_file(xlsx_path: str, season: str) -> pd.DataFrame:
    """
    Read one DES xlsx (3-row multi-level header, district-level data),
    filter to target states + years, and return long-format DataFrame:
        [state, year, crop, season, area, production]
    """
    raw = pd.read_excel(xlsx_path, header=[0, 1, 2])
    mi  = raw.columns                       # pandas MultiIndex

    # ── Flatten MultiIndex columns to plain strings ──
    # Structure: col[0]=crop, col[1]=season, col[2]=measure
    # First 3 columns are State / District / Year identifiers.
    flat_cols = []
    for i, col in enumerate(mi):
        if i < 3:
            flat_cols.append(col[0])         # "State", "District", "Year"
        else:
            flat_cols.append(f'{col[0]}|||{col[2]}')   # "Rice|||Area (Hectare)"
    raw.columns = flat_cols

    sc, dc, yc = 'State', 'District', 'Year'

    # ── Forward-fill merged cells ──
    raw[sc] = raw[sc].ffill().astype(str).str.replace(r'^\d+\.\s*', '', regex=True).str.strip()
    raw[dc] = raw[dc].ffill().astype(str).str.replace(r'^\d+\.\s*', '', regex=True).str.strip()

    # Extract start-year from "YYYY - YYYY+1"
    raw['year'] = pd.to_numeric(
        raw[yc].astype(str).str[:4].str.strip(), errors='coerce'
    )

    # ── Filter to target states and years ──
    mask = raw[sc].isin(TARGET_STATES) & raw['year'].isin(YEAR_RANGE)
    df = raw[mask].copy()
    if df.empty:
        return pd.DataFrame()

    # ── Build a lookup: crop_name → {measure: flat_col_name} ──
    seen: dict = {}
    for col in flat_cols[3:]:
        crop_label, measure = col.split('|||')
        seen.setdefault(crop_label, {})[measure] = col

    # ── Melt each crop into long-format rows ──
    records = []
    for crop_raw, measures in seen.items():
        area_key = next((k for k in measures if 'Area'       in k), None)
        prod_key = next((k for k in measures if 'Production' in k), None)
        if area_key is None or prod_key is None:
            continue

        tmp = df[[sc, 'year', measures[area_key], measures[prod_key]]].copy()
        tmp.columns = ['state', 'year', 'area', 'production']
        tmp['crop']   = crop_raw
        tmp['season'] = season
        records.append(tmp)

    if not records:
        return pd.DataFrame()
    return pd.concat(records, ignore_index=True)


# ── MAIN PIPELINE ──────────────────────────────────────────────────────────────
def main():
    parts = []

    with zipfile.ZipFile(ZIP_PATH) as zf:
        zip_names = zf.namelist()
        for fname, season in FILE_SEASON.items():
            # File may be inside a sub-folder within the zip
            match = next((n for n in zip_names if n.endswith(fname)), None)
            if match is None:
                print(f"WARNING: {fname} not found in zip — skipping.")
                continue

            # openpyxl needs a real file path, so extract to a temp file
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
                tmp.write(zf.read(match))
                tmp_path = tmp.name

            try:
                print(f"Processing {fname} …")
                part = process_file(tmp_path, season)
                if not part.empty:
                    parts.append(part)
                    print(f"  → {len(part):,} rows loaded")
            finally:
                os.unlink(tmp_path)

    # ── Combine all four files ──────────────────────────────────────────────
    df_all = pd.concat(parts, ignore_index=True)

    # ── Rename crops (e.g. "Rice" → "Paddy", "Cotton(lint)" → "Cotton") ──
    df_all['crop'] = df_all['crop'].replace(CROP_RENAME)

    # ── Keep only the 19 target crops ──────────────────────────────────────
    df_all = df_all[df_all['crop'].isin(TARGET_CROPS)].copy()

    # ── Convert Cotton production: Bales → Tonnes ──────────────────────────
    cotton_mask = df_all['crop'] == 'Cotton'
    df_all.loc[cotton_mask, 'production'] = (
        df_all.loc[cotton_mask, 'production'] * COTTON_BALE_TO_TONNE
    )

    # ── Aggregate district-level rows → state-level ─────────────────────────
    # min_count=1 → NaN only when ALL district values were NaN
    agg = (
        df_all
        .groupby(['year', 'state', 'crop', 'season'], as_index=False)
        [['area', 'production']]
        .sum(min_count=1)
    )

    # Drop rows where both area and production are completely missing
    agg = agg.dropna(subset=['area', 'production'], how='all')

    # ── Recompute Yield = Production / Area ─────────────────────────────────
    agg['yield'] = agg['production'] / agg['area']

    # ── Rename columns to final format ──────────────────────────────────────
    agg = agg.rename(columns={
        'area'       : 'Area (Hectare)',
        'production' : 'Production (Tonnes)',
        'yield'      : 'Yield (Tonne/Hectare)',
    })

    # ── Fix dtype ───────────────────────────────────────────────────────────
    agg['year'] = agg['year'].astype(int)

    # ── Sort to match original output order ─────────────────────────────────
    agg = agg.sort_values(
        ['year', 'state', 'crop', 'season']
    ).reset_index(drop=True)

    # ── Save ────────────────────────────────────────────────────────────────
    agg.to_csv(OUTPUT_CSV, index=False)
    print(f"\n✓ Saved {len(agg):,} rows → {OUTPUT_CSV}")
    print(agg.head(10).to_string(index=False))


if __name__ == '__main__':
    main()