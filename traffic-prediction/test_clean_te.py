# test_clean_te.py - Test clean lag features with geohash/timestamp target encodings

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

def get_target_encoding(train_df, val_df, test_df, group_col, target_col='demand', smoothing=20):
    global_mean = train_df[target_col].mean()
    stats = train_df.groupby(group_col)[target_col].agg(['count', 'mean'])
    smooth_mean = (stats['count'] * stats['mean'] + smoothing * global_mean) / (stats['count'] + smoothing)
    smooth_mean = smooth_mean.to_dict()
    
    val_encoded = val_df[group_col].map(smooth_mean).fillna(global_mean)
    test_encoded = test_df[group_col].map(smooth_mean).fillna(global_mean)
    
    train_encoded = pd.Series(index=train_df.index, dtype=float)
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    for t_idx, v_idx in kf.split(train_df):
        tr = train_df.iloc[t_idx]
        va = train_df.iloc[v_idx]
        tr_stats = tr.groupby(group_col)[target_col].agg(['count', 'mean'])
        tr_smooth = (tr_stats['count'] * tr_stats['mean'] + smoothing * global_mean) / (tr_stats['count'] + smoothing)
        tr_smooth = tr_smooth.to_dict()
        train_encoded.iloc[v_idx] = va[group_col].map(tr_smooth).fillna(global_mean)
        
    return train_encoded, val_encoded, test_encoded

def main():
    dataset_dir = r"C:\Users\ashok\.gemini\antigravity\dataset\dataset"
    train = pd.read_csv(os.path.join(dataset_dir, "train.csv"))
    
    train['minutes'] = train['timestamp'].apply(time_to_minutes)
    
    # Decodes geohash
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

    coords = train['geohash'].apply(decode_geohash)
    train['latitude'] = [c[0] for c in coords]
    train['longitude'] = [c[1] for c in coords]
    
    train['geohash_3'] = train['geohash'].str[:3]
    train['geohash_4'] = train['geohash'].str[:4]
    train['geohash_5'] = train['geohash'].str[:5]
    
    train['time_sin'] = np.sin(2 * np.pi * train['minutes'] / 1440.0)
    train['time_cos'] = np.cos(2 * np.pi * train['minutes'] / 1440.0)
    
    # Map lag features only for Day 49
    d48 = train[train['day'] == 48].copy()
    d48_dict = {(row['geohash'], row['minutes']): row['demand'] for _, row in d48.iterrows()}
    d48_geo_mean = d48.groupby('geohash')['demand'].mean().to_dict()
    
    lag_offsets = [0, -15, 15, -30, 30, -45, 45, -60, 60]
    lag_cols = []
    for offset in lag_offsets:
        col_name = f'demand_lag_{offset}m' if offset != 0 else 'demand_lag_24h'
        if offset > 0: col_name = f'demand_lag_+{offset}m'
        elif offset < 0: col_name = f'demand_lag_{offset}m'
        train[col_name] = np.nan
        lag_cols.append(col_name)
        
    train['geo_mean_yesterday'] = np.nan
    is_d49 = train['day'] == 49
    
    for offset, col_name in zip(lag_offsets, lag_cols):
        mapped = [d48_dict.get((geo, max(0, min(1425, m + offset))), np.nan) 
                  for geo, m in zip(train.loc[is_d49, 'geohash'], train.loc[is_d49, 'minutes'])]
        train.loc[is_d49, col_name] = mapped
        
    train.loc[is_d49, 'geo_mean_yesterday'] = train.loc[is_d49, 'geohash'].map(d48_geo_mean)
    
    # Derived rolling properties
    train['lag_mean'] = np.nan
    train['lag_max'] = np.nan
    train['lag_min'] = np.nan
    train['lag_std'] = np.nan
    
    lag_array_d49 = train.loc[is_d49, lag_cols].values
    train.loc[is_d49, 'lag_mean'] = np.nanmean(lag_array_d49, axis=1)
    train.loc[is_d49, 'lag_max'] = np.nanmax(lag_array_d49, axis=1)
    train.loc[is_d49, 'lag_min'] = np.nanmin(lag_array_d49, axis=1)
    train.loc[is_d49, 'lag_std'] = np.nanstd(lag_array_d49, axis=1)

    # Impute Temperature
    geo_temp = train.groupby('geohash')['Temperature'].transform('mean')
    train['Temperature'] = train['Temperature'].fillna(geo_temp)
    train['Temperature'] = train['Temperature'].fillna(train['Temperature'].mean())
    
    # Label encode categoricals for model mapping
    train['RoadType'] = train['RoadType'].fillna('Unknown')
    train['Weather'] = train['Weather'].fillna('Unknown')
    
    cat_cols = ['RoadType', 'LargeVehicles', 'Landmarks', 'Weather', 'geohash', 'geohash_3', 'geohash_4', 'geohash_5', 'timestamp']
    for col in cat_cols:
        le = LabelEncoder()
        train[col] = le.fit_transform(train[col].astype(str))
        
    # Apply Target Encoding to geohash and timestamp
    # We do it on train set to verify R2
    tr_geo, val_geo, _ = get_target_encoding(train, train, train, 'geohash', 'demand', smoothing=20)
    tr_time, val_time, _ = get_target_encoding(train, train, train, 'timestamp', 'demand', smoothing=20)
    
    train['geohash_te'] = tr_geo
    train['timestamp_te'] = tr_time
    
    features = ['geohash', 'geohash_3', 'geohash_4', 'geohash_5', 'timestamp',
                'RoadType', 'NumberofLanes', 'LargeVehicles', 'Landmarks', 'Temperature', 'Weather',
                'latitude', 'longitude', 'minutes', 'time_sin', 'time_cos', 'day',
                'geo_mean_yesterday', 'geohash_te', 'timestamp_te',
                'lag_mean', 'lag_max', 'lag_min', 'lag_std'] + lag_cols
                
    X = train[features].values
    y = train['demand'].values
    
    d49_indices = train[train['day'] == 49].index.values
    
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    oof = np.zeros(len(X))
    
    for fold, (train_idx, val_idx) in enumerate(kf.split(X, y)):
        X_tr, y_tr = X[train_idx], y[train_idx]
        X_va, y_va = X[val_idx], y[val_idx]
        
        model = lgb.LGBMRegressor(
            n_estimators=1000,
            learning_rate=0.03,
            max_depth=8,
            num_leaves=63,
            random_state=42,
            verbose=-1
        )
        model.fit(
            X_tr, y_tr,
            eval_set=[(X_va, y_va)],
            callbacks=[lgb.early_stopping(50, verbose=False)]
        )
        oof[val_idx] = model.predict(X_va)
        
    r2_d49 = r2_score(y[d49_indices], oof[d49_indices])
    print(f"Validation R2 on Day 49 with TE: {r2_d49:.5f} (HE Score: {r2_d49*100:.3f})")

if __name__ == '__main__':
    main()
