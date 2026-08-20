import requests
import pandas as pd
import numpy as np
import time
from datetime import datetime

states_coords = {
    'Gujarat': (22.2587, 71.1924),
    'Haryana': (29.0588, 76.0856),
    'Maharashtra': (19.7515, 75.7139),
    'Punjab': (31.1471, 75.3412),
    'Uttar Pradesh': (26.8467, 80.9462)
}

parameters = [
    "ALLSKY_SFC_PAR_TOT", "ALLSKY_SFC_SW_DWN", "GWETPROF", "GWETROOT",
    "GWETTOP", "PRECTOTCORR", "QV2M", "RH2M", "T2M", "T2M_MAX",
    "T2M_MIN", "T2M_RANGE", "WS10M"
]
param_string = ",".join(parameters)

start_year = 2007
# Try current year first
target_end_year = datetime.now().year

all_state_data = []

def fetch_nasa_data(lat, lon, start, end):
    """Helper function to fetch data and handle API errors."""
    url = (
        f"https://power.larc.nasa.gov/api/temporal/monthly/point?"
        f"parameters={param_string}&community=AG&longitude={lon}&latitude={lat}"
        f"&start={start}&end={end}&format=JSON"
    )
    response = requests.get(url)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"  -> API Error {response.status_code}: {response.text}")
        return None

print(f"Attempting to fetch data from NASA POWER API (2007 to {target_end_year})...")

for state, (lat, lon) in states_coords.items():
    print(f"\nProcessing {state}...")

    # Attempt to fetch with target end year
    data = fetch_nasa_data(lat, lon, start_year, target_end_year)

    # Fallback to previous year if current year fails (likely due to 2026 not being ready)
    if data is None:
        fallback_year = target_end_year - 1
        print(f"  -> Retrying {state} with end year {fallback_year}...")
        time.sleep(2) # Prevent rate limiting
        data = fetch_nasa_data(lat, lon, start_year, fallback_year)

    if data is None:
        print(f"  -> Critical Failure: Could not fetch data for {state} even with fallback.")
        continue # Skip this state if it still fails

    # Process JSON response
    monthly_data = {}
    for param in parameters:
        monthly_data[param] = data['properties']['parameter'][param]

    df_temp = pd.DataFrame(monthly_data)
    df_temp.index.name = 'YearMonth'
    df_temp.reset_index(inplace=True)

    df_temp = df_temp[~df_temp['YearMonth'].str.endswith('13')].copy()
    df_temp['Year'] = df_temp['YearMonth'].str[:4].astype(int)
    df_temp['Month'] = df_temp['YearMonth'].str[4:].astype(int)
    df_temp.replace(-999.0, np.nan, inplace=True)

    # KHARIF
    kharif_df = df_temp[df_temp['Month'].isin([6, 7, 8, 9, 10])].copy()
    kharif_counts = kharif_df.groupby('Year')['Month'].count()
    valid_kharif_years = kharif_counts[kharif_counts == 5].index
    kharif_df = kharif_df[kharif_df['Year'].isin(valid_kharif_years)]

    kharif_agg = kharif_df.groupby('Year')[parameters].mean().reset_index()
    kharif_agg.columns = ['year'] + [f"{p}_Kharif" for p in parameters]

    # RABI
    rabi_df = df_temp[df_temp['Month'].isin([11, 12, 1, 2, 3, 4])].copy()
    rabi_df['Crop_Year'] = rabi_df.apply(
        lambda row: row['Year'] - 1 if row['Month'] <= 4 else row['Year'],
        axis=1
    )
    rabi_counts = rabi_df.groupby('Crop_Year')['Month'].count()
    valid_rabi_years = rabi_counts[rabi_counts == 6].index
    rabi_df = rabi_df[rabi_df['Crop_Year'].isin(valid_rabi_years)]

    rabi_agg = rabi_df.groupby('Crop_Year')[parameters].mean().reset_index()
    rabi_agg.columns = ['year'] + [f"{p}_Rabi" for p in parameters]

    state_final = pd.merge(kharif_agg, rabi_agg, on='year', how='inner')
    state_final.insert(1, 'state', state)
    all_state_data.append(state_final)

    time.sleep(2)

if len(all_state_data) > 0:
    final_dataset = pd.concat(all_state_data, ignore_index=True)
    final_dataset.sort_values(by=['year', 'state'], ascending=[True, True], inplace=True)
    final_dataset.reset_index(drop=True, inplace=True)

    final_dataset.to_csv("party_A_weather_latest.csv", index=False)
    print("\nData saved to party_A_weather_latest.csv successfully!")
    print(f"Total Rows: {len(final_dataset)}")
    print(f"Available Complete Crop Years: {final_dataset['year'].min()} to {final_dataset['year'].max()}")
else:
    print("\nScript failed to generate any data. Please check the API error messages above.")