# test_all_lags.py - Training on all data with NaN lags for Day 48

import os
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score
from sklearn.preprocessing import LabelEncoder
import lightgbm as lgb

def time_to_minutes(ts):
    parts = ts.split(':')
    return int(parts[0]) * 60 + int(parts[1]) if len(parts) == 2 else 0

def main():
    dataset_dir = r"C:\Users\ashok\.gemini\antigravity\dataset\dataset"
    train = pd.read_csv(os.path.join(dataset_dir, "train.csv"))
    
    # Process time
    train['minutes'] = train['timestamp'].apply(time_to_minutes)
    
    # References for Day 48
    d48 = train[train['day'] == 48].copy()
    d48_dict = {(row['geohash'], row['minutes']): row['demand'] for _, row in d48.iterrows()}
    d48_geo_mean = d48.groupby('geohash')['demand'].mean().to_dict()
    
    # Initialize lag columns to NaN
    lag_offsets = [0, -15, 15, -30, 30]
    lag_cols = []
    
    for offset in lag_offsets:
        col_name = f'demand_lag_{offset}m' if offset != 0 else 'demand_lag_24h'
        if offset > 0:
            col_name = f'demand_lag_+{offset}m'
        elif offset < 0:
            col_name = f'demand_lag_{offset}m'
            
        train[col_name] = np.nan
        lag_cols.append(col_name)
        
    train['geo_mean_yesterday'] = np.nan
    
    # Assign lag values only to Day 49 records
    is_d49 = train['day'] == 49
    
    # For Day 49, map lags
    for offset, col_name in zip(lag_offsets, lag_cols):
        # Map values using dictionary
        mapped = [d48_dict.get((geo, max(0, min(1425, m + offset))), np.nan) 
                  for geo, m in zip(train.loc[is_d49, 'geohash'], train.loc[is_d49, 'minutes'])]
        train.loc[is_d49, col_name] = mapped
        
    train.loc[is_d49, 'geo_mean_yesterday'] = train.loc[is_d49, 'geohash'].map(d48_geo_mean)
    
    # Preprocess categoricals
    train['RoadType'] = train['RoadType'].fillna('Unknown')
    train['Weather'] = train['Weather'].fillna('Unknown')
    
    cat_cols = ['RoadType', 'LargeVehicles', 'Landmarks', 'Weather', 'geohash']
    for col in cat_cols:
        le = LabelEncoder()
        train[col] = le.fit_transform(train[col].astype(str))
        
    # Let's decode coordinates as well
    base32 = '0123456789bcdefghjkmnpqrstuvwxyz'
    decoder = {char: idx for idx, char in enumerate(base32)}
    
    def decode_geohash(geohash):
        lat_interval = (-90.0, 90.0)
        lon_interval = (-180.0, 180.0)
        is_even = True
        for char in geohash:
            if char not in decoder: continue
            val = decoder[char]
            for i in range(4, -1, -1):
                bit = (val >> i) & 1
                if is_even:
                    mid = (lon_interval[0] + lon_interval[1]) / 2
                    if bit == 1: lon_interval = (mid, lon_interval[1])
                    else: lon_interval = (lon_interval[0], mid)
                else:
                    mid = (lat_interval[0] + lat_interval[1]) / 2
                    if bit == 1: lat_interval = (mid, lat_interval[1])
                    else: lat_interval = (lat_interval[0], mid)
                is_even = not is_even
        lat = (lat_interval[0] + lat_interval[1]) / 2
        lon = (lon_interval[0] + lon_interval[1]) / 2
        return lat, lon

    # Read original file to decode geohashes (before encoding)
    train_orig = pd.read_csv(os.path.join(dataset_dir, "train.csv"))
    coords = train_orig['geohash'].apply(decode_geohash)
    train['latitude'] = [c[0] for c in coords]
    train['longitude'] = [c[1] for c in coords]
    
    # Feature list
    features = ['geohash', 'minutes', 'RoadType', 'NumberofLanes', 'LargeVehicles', 'Landmarks',
                'latitude', 'longitude', 'day',
                'demand_lag_24h', 'demand_lag_-15m', 'demand_lag_+15m', 'demand_lag_-30m', 'demand_lag_+30m',
                'geo_mean_yesterday']
                
    X = train[features].values
    y = train['demand'].values
    
    # We evaluate only on Day 49 records because the test set is Day 49!
    # So we compute validation R2 ONLY on Day 49 rows.
    # To do this, we can train on Day 48 + Day 49, and evaluate on Day 49 validation splits.
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    oof = np.zeros(len(X))
    
    # We track indices of Day 49 records in train
    d49_indices = train[train['day'] == 49].index.values
    
    for fold, (train_idx, val_idx) in enumerate(kf.split(X, y)):
        X_tr, y_tr = X[train_idx], y[train_idx]
        X_va, y_va = X[val_idx], y[val_idx]
        
        model = lgb.LGBMRegressor(n_estimators=1000, learning_rate=0.03, random_state=42, verbose=-1)
        model.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], callbacks=[lgb.early_stopping(50, verbose=False)])
        oof[val_idx] = model.predict(X_va)
        
    # Compute R2 score on Day 49 rows
    y_true_d49 = y[d49_indices]
    y_pred_d49 = oof[d49_indices]
    
    r2_d49 = r2_score(y_true_d49, y_pred_d49)
    print(f"Validation R2 on Day 49: {r2_d49:.5f} (HE Score: {r2_d49*100:.3f})")

if __name__ == '__main__':
    main()
