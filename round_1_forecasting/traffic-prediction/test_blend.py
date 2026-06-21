# test_blend.py - Train and evaluate enhanced target encoding model

import os
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score
from sklearn.preprocessing import LabelEncoder
import lightgbm as lgb
import xgboost as xgb
from catboost import CatBoostRegressor

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
    
    # Process features
    train['minutes'] = train['timestamp'].apply(time_to_minutes)
    train['hour'] = train['minutes'] // 60
    
    # Decodes coordinates
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
    
    train['geo_time'] = train['geohash'].astype(str) + '_' + train['timestamp'].astype(str)
    train['geo_hour'] = train['geohash'].astype(str) + '_' + train['hour'].astype(str)
    
    # Impute Temperature
    geo_temp = train.groupby('geohash')['Temperature'].transform('mean')
    train['Temperature'] = train['Temperature'].fillna(geo_temp)
    train['Temperature'] = train['Temperature'].fillna(train['Temperature'].mean())
    
    # Categoricals clean
    train['RoadType'] = train['RoadType'].fillna('Unknown')
    train['Weather'] = train['Weather'].fillna('Unknown')
    
    cat_cols = ['RoadType', 'LargeVehicles', 'Landmarks', 'Weather', 'geohash', 'geohash_3', 'geohash_4', 'geohash_5', 'timestamp', 'geo_time', 'geo_hour']
    for col in cat_cols:
        le = LabelEncoder()
        train[col] = le.fit_transform(train[col].astype(str))
        
    # Apply Target Encodings
    tr_geo, val_geo, _ = get_target_encoding(train, train, train, 'geohash', 'demand', smoothing=20)
    tr_time, val_time, _ = get_target_encoding(train, train, train, 'timestamp', 'demand', smoothing=20)
    tr_geotime, val_geotime, _ = get_target_encoding(train, train, train, 'geo_time', 'demand', smoothing=20)
    tr_geohour, val_geohour, _ = get_target_encoding(train, train, train, 'geo_hour', 'demand', smoothing=20)
    
    train['geohash_te'] = tr_geo
    train['timestamp_te'] = tr_time
    train['geo_time_te'] = tr_geotime
    train['geo_hour_te'] = tr_geohour
    
    features = ['geohash', 'geohash_3', 'geohash_4', 'geohash_5', 'timestamp', 'geo_time', 'geo_hour',
                'RoadType', 'NumberofLanes', 'LargeVehicles', 'Landmarks', 'Temperature', 'Weather',
                'latitude', 'longitude', 'minutes', 'hour', 'time_sin', 'time_cos', 'day',
                'geohash_te', 'timestamp_te', 'geo_time_te', 'geo_hour_te']
                
    X = train[features].values
    y = train['demand'].values
    
    d49_indices = train[train['day'] == 49].index.values
    
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    oof_lgb = np.zeros(len(X))
    oof_xgb = np.zeros(len(X))
    
    print("Training models...")
    for fold, (train_idx, val_idx) in enumerate(kf.split(X, y)):
        X_tr, y_tr = X[train_idx], y[train_idx]
        X_va, y_va = X[val_idx], y[val_idx]
        
        # LGB
        model_lgb = lgb.LGBMRegressor(n_estimators=1000, learning_rate=0.03, max_depth=9, num_leaves=127, random_state=42, verbose=-1)
        model_lgb.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], callbacks=[lgb.early_stopping(50, verbose=False)])
        oof_lgb[val_idx] = model_lgb.predict(X_va)
        
        # XGB
        model_xgb = xgb.XGBRegressor(n_estimators=1000, learning_rate=0.03, max_depth=8, random_state=42, early_stopping_rounds=50, tree_method='hist')
        model_xgb.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], verbose=False)
        oof_xgb[val_idx] = model_xgb.predict(X_va)
        
        print(f"Fold {fold+1} finished.")
        
    r2_all_lgb = r2_score(y, oof_lgb)
    r2_all_xgb = r2_score(y, oof_xgb)
    
    r2_d49_lgb = r2_score(y[d49_indices], oof_lgb[d49_indices])
    r2_d49_xgb = r2_score(y[d49_indices], oof_xgb[d49_indices])
    
    blend = oof_lgb * 0.4 + oof_xgb * 0.6
    r2_all_blend = r2_score(y, blend)
    r2_d49_blend = r2_score(y[d49_indices], blend[d49_indices])
    
    print(f"Overall R2 - LGB: {r2_all_lgb:.5f} | XGB: {r2_all_xgb:.5f} | Blend: {r2_all_blend:.5f}")
    print(f"Day 49 R2  - LGB: {r2_d49_lgb:.5f} | XGB: {r2_d49_xgb:.5f} | Blend: {r2_d49_blend:.5f}")

if __name__ == '__main__':
    main()
