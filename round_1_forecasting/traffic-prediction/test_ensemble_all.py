# test_ensemble_all.py - Train full ensemble on Day 48 + Day 49, validate on Day 49
import os
import gc
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score
from sklearn.preprocessing import LabelEncoder
import lightgbm as lgb
import xgboost as xgb
from catboost import CatBoostRegressor

# 1. Base32 Geohash Decoder
def decode_geohash(geohash):
    base32 = '0123456789bcdefghjkmnpqrstuvwxyz'
    decoder = {char: idx for idx, char in enumerate(base32)}
    lat_interval = (-90.0, 90.0)
    lon_interval = (-180.0, 180.0)
    is_even = True
    for char in geohash:
        if char not in decoder:
            continue
        val = decoder[char]
        for i in range(4, -1, -1):
            bit = (val >> i) & 1
            if is_even:
                mid = (lon_interval[0] + lon_interval[1]) / 2
                if bit == 1:
                    lon_interval = (mid, lon_interval[1])
                else:
                    lon_interval = (lon_interval[0], mid)
            else:
                mid = (lat_interval[0] + lat_interval[1]) / 2
                if bit == 1:
                    lat_interval = (mid, lat_interval[1])
                else:
                    lat_interval = (lat_interval[0], mid)
            is_even = not is_even
    lat = (lat_interval[0] + lat_interval[1]) / 2
    lon = (lon_interval[0] + lon_interval[1]) / 2
    return lat, lon

def main():
    print("--- Training Ensemble on Day 48 + Day 49, Validating on Day 49 ---")
    
    dataset_dir = r"C:\Users\ashok\.gemini\antigravity\dataset\dataset"
    train_path = os.path.join(dataset_dir, "train.csv")
    test_path = os.path.join(dataset_dir, "test.csv")
    
    print("Loading datasets...")
    train = pd.read_csv(train_path)
    test = pd.read_csv(test_path)
    
    y_train = train['demand'].values
    test_indices = test['Index'].values
    
    df = pd.concat([train.drop(columns=['demand']), test], axis=0).reset_index(drop=True)
    
    print("Preprocessing and Geohash Decoding...")
    df['RoadType'] = df['RoadType'].fillna('Unknown')
    df['Weather'] = df['Weather'].fillna('Unknown')
    
    coords = df['geohash'].apply(decode_geohash)
    df['latitude'] = [c[0] for c in coords]
    df['longitude'] = [c[1] for c in coords]
    
    df['geohash_3'] = df['geohash'].str[:3]
    df['geohash_4'] = df['geohash'].str[:4]
    df['geohash_5'] = df['geohash'].str[:5]
    
    def time_to_minutes(ts):
        parts = ts.split(':')
        return int(parts[0]) * 60 + int(parts[1]) if len(parts) == 2 else 0
        
    df['minutes'] = df['timestamp'].apply(time_to_minutes)
    df['hour'] = df['minutes'] // 60
    df['time_sin'] = np.sin(2 * np.pi * df['minutes'] / 1440.0)
    df['time_cos'] = np.cos(2 * np.pi * df['minutes'] / 1440.0)
    
    geo_temp = df.groupby('geohash')['Temperature'].transform('mean')
    df['Temperature'] = df['Temperature'].fillna(geo_temp)
    df['Temperature'] = df['Temperature'].fillna(df['Temperature'].mean())
    
    # 2. Build 24-Hour Lag Features from Day 48
    print("Building historical lag features (Day 48 reference)...")
    train['minutes'] = train['timestamp'].apply(time_to_minutes)
    d48 = train[train['day'] == 48].copy()
    d48_dict = {(row['geohash'], row['minutes']): row['demand'] for _, row in d48.iterrows()}
    d48_geo_mean = d48.groupby('geohash')['demand'].mean().to_dict()
    global_mean_d48 = d48['demand'].mean()
    
    lag_offsets = [0, -15, 15, -30, 30, -45, 45, -60, 60]
    lag_cols = []
    
    for offset in lag_offsets:
        col_name = f'demand_lag_{offset}m' if offset != 0 else 'demand_lag_24h'
        if offset > 0:
            col_name = f'demand_lag_+{offset}m'
        elif offset < 0:
            col_name = f'demand_lag_{offset}m'
        df[col_name] = np.nan
        lag_cols.append(col_name)
        
    df['geo_mean_yesterday'] = np.nan
    is_future = df['day'] >= 49
    
    for offset, col_name in zip(lag_offsets, lag_cols):
        mapped = [d48_dict.get((geo, max(0, min(1425, m + offset))), np.nan) 
                  for geo, m in zip(df.loc[is_future, 'geohash'], df.loc[is_future, 'minutes'])]
        df.loc[is_future, col_name] = mapped
        
    df.loc[is_future, 'geo_mean_yesterday'] = df.loc[is_future, 'geohash'].map(d48_geo_mean)
    df['geo_mean_yesterday'] = df['geo_mean_yesterday'].fillna(global_mean_d48)
    
    # Derived rolling properties over the lag window
    df['lag_mean'] = np.nan
    df['lag_max'] = np.nan
    df['lag_min'] = np.nan
    df['lag_std'] = np.nan
    
    lag_array_future = df.loc[is_future, lag_cols].values
    df.loc[is_future, 'lag_mean'] = np.nanmean(lag_array_future, axis=1)
    df.loc[is_future, 'lag_max'] = np.nanmax(lag_array_future, axis=1)
    df.loc[is_future, 'lag_min'] = np.nanmin(lag_array_future, axis=1)
    df.loc[is_future, 'lag_std'] = np.nanstd(lag_array_future, axis=1)
    
    df['lag_mean'] = df['lag_mean'].fillna(global_mean_d48)
    df['lag_max'] = df['lag_max'].fillna(global_mean_d48)
    df['lag_min'] = df['lag_min'].fillna(global_mean_d48)
    df['lag_std'] = df['lag_std'].fillna(0.0)
    
    cat_cols = ['RoadType', 'LargeVehicles', 'Landmarks', 'Weather', 'geohash', 'geohash_3', 'geohash_4', 'geohash_5', 'timestamp']
    for col in cat_cols:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col].astype(str))
        
    X_train_df = df.iloc[:len(train)].copy()
    X_test_df = df.iloc[len(train):].copy()
    
    features = ['geohash', 'geohash_3', 'geohash_4', 'geohash_5', 'timestamp',
                'RoadType', 'NumberofLanes', 'LargeVehicles', 'Landmarks', 'Temperature', 'Weather',
                'latitude', 'longitude', 'minutes', 'time_sin', 'time_cos', 'day',
                'geo_mean_yesterday', 'lag_mean', 'lag_max', 'lag_min', 'lag_std'] + lag_cols
                
    X_train_np = X_train_df[features].values
    X_test_np = X_test_df[features].values
    
    d49_indices = X_train_df[X_train_df['day'] == 49].index.values
    
    n_splits = 5
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=42)
    
    oof_lgb = np.zeros(len(X_train_np))
    oof_xgb = np.zeros(len(X_train_np))
    oof_cat = np.zeros(len(X_train_np))
    
    preds_lgb = np.zeros(len(X_test_np))
    preds_xgb = np.zeros(len(X_test_np))
    preds_cat = np.zeros(len(X_test_np))
    
    for fold, (train_idx, val_idx) in enumerate(kf.split(X_train_np, y_train)):
        print(f"\n--- Fold {fold+1} / {n_splits} ---")
        X_tr, y_tr = X_train_np[train_idx], y_train[train_idx]
        X_va, y_va = X_train_np[val_idx], y_train[val_idx]
        
        # 1. LGB
        model_lgb = lgb.LGBMRegressor(
            n_estimators=1000,
            learning_rate=0.03,
            max_depth=8,
            num_leaves=63,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            verbose=-1
        )
        model_lgb.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], callbacks=[lgb.early_stopping(50, verbose=False)])
        oof_lgb[val_idx] = model_lgb.predict(X_va)
        preds_lgb += model_lgb.predict(X_test_np) / n_splits
        
        # 2. XGB
        model_xgb = xgb.XGBRegressor(
            n_estimators=1000,
            learning_rate=0.03,
            max_depth=8,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            early_stopping_rounds=50,
            tree_method='hist'
        )
        model_xgb.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], verbose=False)
        oof_xgb[val_idx] = model_xgb.predict(X_va)
        preds_xgb += model_xgb.predict(X_test_np) / n_splits
        
        # 3. CatBoost
        model_cat = CatBoostRegressor(
            iterations=1200,
            learning_rate=0.03,
            depth=8,
            random_seed=42,
            early_stopping_rounds=50,
            verbose=False
        )
        model_cat.fit(X_tr, y_tr, eval_set=(X_va, y_va))
        oof_cat[val_idx] = model_cat.predict(X_va)
        preds_cat += model_cat.predict(X_test_np) / n_splits
        
        # Eval strictly on Day 49 records in the validation split
        fold_d49_val_idx = np.intersect1d(val_idx, d49_indices)
        if len(fold_d49_val_idx) > 0:
            score_lgb = r2_score(y_train[fold_d49_val_idx], oof_lgb[fold_d49_val_idx])
            score_xgb = r2_score(y_train[fold_d49_val_idx], oof_xgb[fold_d49_val_idx])
            score_cat = r2_score(y_train[fold_d49_val_idx], oof_cat[fold_d49_val_idx])
            print(f"Fold {fold+1} Day 49 Val R2 - LGB: {score_lgb:.5f} | XGB: {score_xgb:.5f} | CAT: {score_cat:.5f}")
            
    r2_lgb = r2_score(y_train[d49_indices], oof_lgb[d49_indices])
    r2_xgb = r2_score(y_train[d49_indices], oof_xgb[d49_indices])
    r2_cat = r2_score(y_train[d49_indices], oof_cat[d49_indices])
    
    oof_blend = oof_lgb * 0.35 + oof_xgb * 0.45 + oof_cat * 0.20
    r2_blend = r2_score(y_train[d49_indices], oof_blend[d49_indices])
    
    print("\n--- Day 49 Validation Summary (Trained on Day 48 + Day 49) ---")
    print(f"LightGBM R2: {r2_lgb:.5f}")
    print(f"XGBoost R2:  {r2_xgb:.5f}")
    print(f"CatBoost R2: {r2_cat:.5f}")
    print(f"Weighted Ensemble Blend R2: {r2_blend:.5f} (Estimated Score: {max(0, 100 * r2_blend):.3f})")
    
    final_preds = preds_lgb * 0.35 + preds_xgb * 0.45 + preds_cat * 0.20
    final_preds = np.clip(final_preds, 0.0, 1.0)
    
    submission = pd.DataFrame({
        'Index': test_indices,
        'demand': final_preds
    })
    submission_path = r"C:\Users\ashok\.gemini\antigravity\scratch\traffic-prediction\submission_ensemble_all.csv"
    submission.to_csv(submission_path, index=False)
    print(f"Saved submission to: {submission_path}")

if __name__ == '__main__':
    main()
