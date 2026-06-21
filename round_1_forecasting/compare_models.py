# compare_models.py - Compare Day 49-only model vs Day 48+Day 49 model predictions
import os
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold
from sklearn.preprocessing import LabelEncoder
import lightgbm as lgb

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

def time_to_minutes(ts):
    parts = ts.split(':')
    return int(parts[0]) * 60 + int(parts[1]) if len(parts) == 2 else 0

def run_model(train_only_d49):
    dataset_dir = r"C:\Users\ashok\.gemini\antigravity\dataset\dataset"
    train = pd.read_csv(os.path.join(dataset_dir, "train.csv"))
    test = pd.read_csv(os.path.join(dataset_dir, "test.csv"))
    
    y_train = train['demand'].values
    test_indices = test['Index'].values
    
    df = pd.concat([train.drop(columns=['demand']), test], axis=0).reset_index(drop=True)
    df['RoadType'] = df['RoadType'].fillna('Unknown')
    df['Weather'] = df['Weather'].fillna('Unknown')
    
    coords = df['geohash'].apply(decode_geohash)
    df['latitude'] = [c[0] for c in coords]
    df['longitude'] = [c[1] for c in coords]
    
    df['geohash_3'] = df['geohash'].str[:3]
    df['geohash_4'] = df['geohash'].str[:4]
    df['geohash_5'] = df['geohash'].str[:5]
    
    df['minutes'] = df['timestamp'].apply(time_to_minutes)
    df['hour'] = df['minutes'] // 60
    df['time_sin'] = np.sin(2 * np.pi * df['minutes'] / 1440.0)
    df['time_cos'] = np.cos(2 * np.pi * df['minutes'] / 1440.0)
    
    geo_temp = df.groupby('geohash')['Temperature'].transform('mean')
    df['Temperature'] = df['Temperature'].fillna(geo_temp)
    df['Temperature'] = df['Temperature'].fillna(df['Temperature'].mean())
    
    # Lags
    train['minutes'] = train['timestamp'].apply(time_to_minutes)
    d48 = train[train['day'] == 48].copy()
    d48_dict = {(row['geohash'], row['minutes']): row['demand'] for _, row in d48.iterrows()}
    d48_geo_mean = d48.groupby('geohash')['demand'].mean().to_dict()
    global_mean_d48 = d48['demand'].mean()
    
    lag_offsets = [0, -15, 15, -30, 30, -45, 45, -60, 60]
    lag_cols = []
    for offset in lag_offsets:
        col_name = f'lag_{offset}'
        df[col_name] = np.nan
        lag_cols.append(col_name)
    df['geo_mean_yesterday'] = np.nan
    
    is_future = df['day'] >= 49
    for offset, col_name in zip(lag_offsets, lag_cols):
        mapped = [d48_dict.get((geo, max(0, min(1425, m + offset))), np.nan) for geo, m in zip(df.loc[is_future, 'geohash'], df.loc[is_future, 'minutes'])]
        df.loc[is_future, col_name] = mapped
    df.loc[is_future, 'geo_mean_yesterday'] = df.loc[is_future, 'geohash'].map(d48_geo_mean)
    df['geo_mean_yesterday'] = df['geo_mean_yesterday'].fillna(global_mean_d48)
    
    cat_cols = ['RoadType', 'LargeVehicles', 'Landmarks', 'Weather', 'geohash', 'geohash_3', 'geohash_4', 'geohash_5', 'timestamp']
    for col in cat_cols:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col].astype(str))
        
    X_train_df = df.iloc[:len(train)].copy()
    X_test_df = df.iloc[len(train):].copy()
    
    features = ['geohash', 'geohash_3', 'geohash_4', 'geohash_5', 'timestamp',
                'RoadType', 'NumberofLanes', 'LargeVehicles', 'Landmarks', 'Temperature', 'Weather',
                'latitude', 'longitude', 'minutes', 'time_sin', 'time_cos', 'day',
                'geo_mean_yesterday'] + lag_cols
                
    if train_only_d49:
        train_mask = X_train_df['day'] == 49
        X_train_filtered = X_train_df[train_mask].copy()
        y_train_filtered = y_train[train_mask]
    else:
        X_train_filtered = X_train_df
        y_train_filtered = y_train
        
    X_tr_np = X_train_filtered[features].values
    X_te_np = X_test_df[features].values
    
    # Train simple LightGBM
    model = lgb.LGBMRegressor(n_estimators=300, learning_rate=0.05, random_state=42, verbose=-1)
    model.fit(X_tr_np, y_train_filtered)
    preds = model.predict(X_te_np)
    return np.clip(preds, 0.0, 1.0)

def main():
    print("Running Day 49-only model...")
    p_d49 = run_model(train_only_d49=True)
    
    print("Running Day 48+Day 49 model...")
    p_all = run_model(train_only_d49=False)
    
    print("\n--- Comparison ---")
    print("Are predictions identical:", np.array_equal(p_d49, p_all))
    print("Correlation:", np.corrcoef(p_d49, p_all)[0, 1])
    print("Mean absolute difference:", np.mean(np.abs(p_d49 - p_all)))
    print("Max absolute difference:", np.max(np.abs(p_d49 - p_all)))
    
if __name__ == '__main__':
    main()
