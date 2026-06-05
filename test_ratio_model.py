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

def decode_geohash(geohash):
    base32 = '0123456789bcdefghjkmnpqrstuvwxyz'
    decoder = {char: idx for idx, char in enumerate(base32)}
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
    
    y_train = train['demand'].values
    
    # Preprocess
    train['RoadType'] = train['RoadType'].fillna('Unknown')
    train['Weather'] = train['Weather'].fillna('Unknown')
    train['is_day_49'] = (train['day'] == 49).astype(int)
    
    coords = train['geohash'].apply(decode_geohash)
    train['latitude'] = [c[0] for c in coords]
    train['longitude'] = [c[1] for c in coords]
    
    train['geohash_3'] = train['geohash'].str[:3]
    train['geohash_4'] = train['geohash'].str[:4]
    train['geohash_5'] = train['geohash'].str[:5]
    
    train['minutes'] = train['timestamp'].apply(time_to_minutes)
    train['hour'] = train['minutes'] // 60
    train['time_sin'] = np.sin(2 * np.pi * train['minutes'] / 1440.0)
    train['time_cos'] = np.cos(2 * np.pi * train['minutes'] / 1440.0)
    
    train['geo_time'] = train['geohash'].astype(str) + '_' + train['timestamp'].astype(str)
    
    # Impute Temperature
    geo_temp = train.groupby('geohash')['Temperature'].transform('mean')
    train['Temperature'] = train['Temperature'].fillna(geo_temp)
    train['Temperature'] = train['Temperature'].fillna(train['Temperature'].mean())
    
    # Label encode
    cat_cols = ['RoadType', 'LargeVehicles', 'Landmarks', 'Weather', 'geohash', 'geohash_3', 'geohash_4', 'geohash_5', 'timestamp', 'geo_time']
    for col in cat_cols:
        le = LabelEncoder()
        train[col] = le.fit_transform(train[col].astype(str))
        
    # Target encoding using OOF strategy
    # Note: we must only target encode on Day 48 data when predicting Day 49 validation records,
    # otherwise Day 49 validation records will leak their own scale.
    # To do this cleanly and leak-free:
    # 1. We compute target encodings using ONLY Day 48 data!
    # Let's see: if we compute TE on Day 48 only, does it cover Day 49?
    # Yes, because Day 49 has the same geohashes and times.
    # This is 100% leak-free!
    print("Computing target encodings using Day 48 only...")
    d48_train = train[train['day'] == 48].copy()
    
    for col in ['geohash', 'timestamp', 'geo_time']:
        global_mean = d48_train['demand'].mean()
        stats = d48_train.groupby(col)['demand'].agg(['count', 'mean'])
        smooth_mean = (stats['count'] * stats['mean'] + 20 * global_mean) / (stats['count'] + 20)
        smooth_mean = smooth_mean.to_dict()
        train[col + '_te'] = train[col].map(smooth_mean).fillna(global_mean)
        
    # Let's define the ratio target variable:
    # y_diff = log(demand + 0.01) - log(geo_time_te + 0.01)
    train['y_diff'] = np.log(train['demand'] + 0.01) - np.log(train['geo_time_te'] + 0.01)
    
    features = ['geohash', 'day', 'timestamp', 'RoadType', 'NumberofLanes', 'LargeVehicles', 'Landmarks', 'Temperature', 'Weather',
                'latitude', 'longitude', 'geohash_3', 'geohash_4', 'geohash_5', 'minutes', 'hour', 'time_sin', 'time_cos', 'geo_time',
                'geohash_te', 'timestamp_te', 'geo_time_te', 'is_day_49']
                
    X = train[features].values
    y = train['y_diff'].values
    y_orig = train['demand'].values
    geo_time_te = train['geo_time_te'].values
    
    d49_train_indices = train[train['day'] == 49].index.values
    
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    oof_diff = np.zeros(len(X))
    
    print("\n--- Training LightGBM on log-ratio ---")
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
        oof_diff[val_idx] = model.predict(X_va)
        
    # Reconstruct original demand predictions:
    # pred_demand = exp(oof_diff + log(geo_time_te + 0.01)) - 0.01
    oof_pred = np.exp(oof_diff + np.log(geo_time_te + 0.01)) - 0.01
    oof_pred = np.clip(oof_pred, 0.0, 1.0)
    
    # Calculate R2 on Day 49 OOF records
    r2_d49 = r2_score(y_orig[d49_train_indices], oof_pred[d49_train_indices])
    print(f"\nDay 49 OOF R2: {r2_d49:.5f} (HackerEarth Score Estimate: {max(0, 100 * r2_d49):.3f})")
    
    # Let's check Day 48 OOF R2 just to see
    d48_train_indices = train[train['day'] == 48].index.values
    r2_d48 = r2_score(y_orig[d48_train_indices], oof_pred[d48_train_indices])
    print(f"Day 48 OOF R2: {r2_d48:.5f}")
    
if __name__ == '__main__':
    main()
