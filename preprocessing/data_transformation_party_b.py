import os
import re
import numpy as np
import pandas as pd

# ==============================================================================
# 1. CONFIGURATION
# ==============================================================================
# Set this to the folder containing your Excel files (use "." if in the same folder)
DATA_FOLDER = "Final Data CSV Files/rabi-kharif"  
PARTY_C_PATH = "party_C_production.csv"
OUTPUT_PARTY_B = "party_B_economic_code.csv"

YEAR_MIN = 2007
YEAR_MAX = 2022

STATE_MAP = {
    "gujarat": "Gujarat", "guj": "Gujarat",
    "maharashtra": "Maharashtra", "mah": "Maharashtra", "mh": "Maharashtra",
    "punjab": "Punjab", "pun": "Punjab", "pb": "Punjab",
    "uttar pradesh": "Uttar Pradesh", "up": "Uttar Pradesh",
    "haryana": "Haryana", "har": "Haryana", "hr": "Haryana",
}

CROP_MAPPING = {
    'Cotton (Kapas)': 'Cotton', 'Cotton(lint)': 'Cotton', 'Kapas': 'Cotton',
    'Groundnut-in-shell': 'Groundnut',
    'Rapeseed/Mustard': 'Rapeseed & Mustard', 'Rapeseed & Mustard': 'Rapeseed & Mustard',
    'Rapeseed &Mustard': 'Rapeseed & Mustard', 'Rapeseed': 'Rapeseed & Mustard',
    'Arhar/Tur': 'Tur', 'Tur (Arhar)': 'Tur', 'Red Gram': 'Tur', 'Pigeon Pea': 'Tur',
    'Masur (Lentil)': 'Masoor', 'Lentil': 'Masoor',
    'Soyabean': 'Soybean',
    'Sesamum': 'Sesame',
    'Paddy': 'Paddy', 'Rice': 'Paddy',
    'Bajra': 'Bajra', 'Jowar': 'Jowar', 'Ragi': 'Ragi', 'Maize': 'Maize',
    'Wheat': 'Wheat', 'Barley': 'Barley',
    'Gram': 'Gram', 'Bengal Gram': 'Gram',
    'Moong': 'Moong', 'Green Gram': 'Moong', 'Moong (Green Gram)': 'Moong',
    'Urad': 'Urad', 'Black Gram': 'Urad',
    'Sunflower': 'Sunflower', 'Sunflowerseed': 'Sunflower',
    'Safflower': 'Safflower',
    'Castor seed': 'Castor',
    'Linseed': 'Linseed', 'Niger seed': 'Niger',
    'Onion': 'Onion', 'Potato': 'Potato', 'Sugarcane': 'Sugarcane',
    'Jute': 'Jute', 'Mesta': 'Mesta',
    'Tobacco': 'Tobacco', 'Guar seed': 'Guar Seed',
    'Chilli': 'Dry Chillies', 'Dry chillies': 'Dry Chillies'
}

# ==============================================================================
# 2. DYNAMIC CACP PARSER HELPERS
# ==============================================================================
def clean_numeric(x):
    if pd.isna(x):
        return None
    val = re.sub(r"[^\d.\-]", "", str(x))
    return float(val) if val else None

def extract_year(text):
    if not text:
        return None
    m = re.search(r"(20\d{2})", str(text))
    if m:
        y = int(m.group(1))
        if 2000 <= y <= 2025:
            return y
    return None

def extract_year_from_filename(fname):
    m = re.search(r"(20\d{2})\s*[--]\s*\d{2}", fname)
    if m:
        return int(m.group(1))
    return extract_year(fname)

def normalize_state(x):
    if pd.isna(x):
        return None
    return STATE_MAP.get(str(x).lower().strip())

def detect_state_column(df):
    for c in df.columns:
        if isinstance(c, str) and "state" in c.lower():
            return c
    first_col = df.columns[0]
    sample = df[first_col].astype(str).str.lower().head(10)
    hits = sample.isin(STATE_MAP.keys()).sum()
    if hits >= 2:
        return first_col
    return None

def detect_columns(df):
    col = {
        "state": detect_state_column(df),
        "crop": None,
        "c2": None,
        "msp": None,
        "year": None,
    }
    for c in df.columns:
        lc = str(c).lower()
        if col["crop"] is None and ("crop" in lc or "commodity" in lc):
            col["crop"] = c
        elif col["year"] is None and "year" in lc:
            col["year"] = c
        elif col["c2"] is None and (("c2" in lc and "cost" in lc) or ("projected c2" in lc)) and "a2+fl" not in lc:
            col["c2"] = c
        elif col["msp"] is None and ("msp" in lc or "implicit price" in lc or "money earned" in lc or "recommended" in lc):
            col["msp"] = c
    return col

def process_sheet(df, filename):
    col = detect_columns(df)
    if not col["state"] or not col["crop"] or not col["msp"]:
        return None
    
    out = pd.DataFrame()
    out["state"] = df[col["state"]].apply(normalize_state)
    out["crop"] = df[col["crop"]]
    out["msp"] = df[col["msp"]].apply(clean_numeric)
    out["c2"] = df[col["c2"]].apply(clean_numeric) if col["c2"] else None
    
    out = out[out["state"].notna()]
    
    # Extract Year from column, headers, or filename
    year = None
    if col["year"]:
        out["year"] = df[col["year"]].apply(extract_year)
    else:
        for k in ["c2", "msp"]:
            if col[k]:
                year = extract_year(col[k])
                if year:
                    break
        if year is None:
            year = extract_year_from_filename(filename)
        out["year"] = year
        
    out = out[out["year"].between(2000, 2025)]
    return out[["year", "state", "crop", "c2", "msp"]]

# ==============================================================================
# 3. UNIFIED PARSER FOR A SINGLE DIRECTORY
# ==============================================================================
def parse_single_folder(folder_path):
    all_data = []
    
    if not os.path.exists(folder_path):
        raise FileNotFoundError(f"Folder '{folder_path}' does not exist.")
        
    files = sorted(os.listdir(folder_path))
    for f in files:
        if not f.endswith((".xls", ".xlsx")):
            continue
            
        fname_lower = f.lower()
        
        # Determine season based on file prefix
        if "rabi" in fname_lower:
            season = "Rabi"
        elif "final" in fname_lower or "kharif" in fname_lower:
            season = "Kharif"
        else:
            continue  # Skip files not matching CACP naming patterns
            
        file_path = os.path.join(folder_path, f)
        print(f"Processing ({season}): {f}...")
        
        try:
            sheets = pd.read_excel(file_path, sheet_name=None)
            for _, df_sheet in sheets.items():
                res = process_sheet(df_sheet, f)
                if res is not None and not res.empty:
                    res["season"] = season
                    all_data.append(res)
        except Exception as e:
            print(f"Error reading {f}: {e}")
            
    if not all_data:
        return pd.DataFrame(columns=["year", "state", "crop", "season", "c2", "msp"])
        
    return pd.concat(all_data, ignore_index=True)

# ==============================================================================
# 4. SKELETON ALIGNMENT & HIERARCHICAL IMPUTATION
# ==============================================================================
def build_party_b():
    # 1. Parse all files from the single folder
    print(f"Parsing files from folder: '{DATA_FOLDER}'...")
    economic_raw = parse_single_folder(DATA_FOLDER)
    economic_raw.columns = [c.lower() for c in economic_raw.columns]
    
    # 2. Normalize crops & filter year range
    economic_raw['crop'] = economic_raw['crop'].astype(str).str.strip()
    economic_raw['crop'] = economic_raw['crop'].apply(
        lambda x: CROP_MAPPING.get(x, CROP_MAPPING.get(x.title(), x.title()))
    )
    economic_raw = economic_raw[(economic_raw['year'] >= YEAR_MIN) & (economic_raw['year'] <= YEAR_MAX)]
    
    # Deduplicate raw extractions to prevent skeleton explosion
    economic_dedup = economic_raw.groupby(['year', 'state', 'crop', 'season'], as_index=False).agg({
        'c2': 'mean',
        'msp': 'max'
    })
    
    # 3. Load Target Skeleton from Party C
    if not os.path.exists(PARTY_C_PATH):
        raise FileNotFoundError(f"'{PARTY_C_PATH}' not found. Please ensure party_C_production.csv is in the directory.")
        
    df_prod = pd.read_csv(PARTY_C_PATH)
    df_prod.columns = [c.lower() for c in df_prod.columns]
    target_skeleton = df_prod[['year', 'state', 'crop', 'season']].drop_duplicates()
    
    # 4. Compute National Price Card (Fallback Tier 1)
    national_prices = economic_dedup.groupby(['year', 'crop', 'season']).agg({
        'c2': 'mean',
        'msp': 'max'
    }).reset_index().rename(columns={'c2': 'c2_national', 'msp': 'msp_national'})
    
    # 5. Merge Skeleton with State Data + National Fallback
    merged = pd.merge(target_skeleton, economic_dedup, on=['year', 'state', 'crop', 'season'], how='left')
    merged = pd.merge(merged, national_prices, on=['year', 'crop', 'season'], how='left')
    
    merged['c2_final'] = merged['c2'].fillna(merged['c2_national'])
    merged['msp_final'] = merged['msp'].fillna(merged['msp_national'])
    
    final_df = merged[['year', 'state', 'crop', 'season', 'c2_final', 'msp_final']].copy()
    final_df.columns = ['year', 'state', 'crop', 'season', 'c2', 'msp']
    
    # 6. Time-Series Interpolation for Residual Gaps (Fallback Tier 2)
    final_df = final_df.sort_values(by=['crop', 'state', 'year'])
    
    def fill_gaps(group):
        group = group.copy()
        group['c2'] = group['c2'].interpolate(method='linear', limit_direction='both').bfill().ffill()
        group['msp'] = group['msp'].interpolate(method='linear', limit_direction='both').bfill().ffill()
        return group
    
    final_df = final_df.groupby('crop', group_keys=False).apply(fill_gaps)
    
    # 7. Final Sort to match Party C row-for-row
    final_df = final_df.sort_values(by=['year', 'state', 'crop', 'season']).reset_index(drop=True)
    
    # Save CSV
    final_df.to_csv(OUTPUT_PARTY_B, index=False)
    print(f"\nSUCCESS: '{OUTPUT_PARTY_B}' generated successfully!")
    print(f"Shape: {final_df.shape} | Nulls: {final_df.isna().sum().sum()}")
    return final_df

if __name__ == "__main__":
    party_b_df = build_party_b()
    print("\nFirst 15 Rows Preview:")
    print(party_b_df.head(15).to_string())