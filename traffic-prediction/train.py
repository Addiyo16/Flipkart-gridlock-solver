# train.py - Log-Ratio Ensemble Model for Traffic Demand Prediction
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

def main():
    print("--- Traffic Demand Prediction: Log-Ratio Ensemble Model ---")
    
    dataset_dir = r"C:\Users\ashok\.gemini\antigravity\dataset\dataset"
    train_path = os.path.join(dataset_dir, "train.csv")
    test_path = os.path.join(dataset_dir, "test.csv")
    
    print("Loading datasets...")
    train = pd.read_csv(train_path)
    test = pd.read_csv(test_path)
    
    y_train_orig = train['demand'].values
    test_indices = test['Index'].values
    
    # Preprocess missing values
    train['RoadType'] = train['RoadType'].fillna('Unknown')
    train['Weather'] = train['Weather'].fillna('Unknown')
    test['RoadType'] = test['RoadType'].fillna('Unknown')
    test['Weather'] = test['Weather'].fillna('Unknown')
    
    train['is_day_49'] = (train['day'] == 49).astype(int)
    test['is_day_49'] = 1
    
    print("Decoding geohashes...")
    for df in [train, test]:
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
        df['geo_time'] = df['geohash'].astype(str) + '_' + df['timestamp'].astype(str)
        
    # Temperature imputation
    geo_temp_mean = train.groupby('geohash')['Temperature'].mean().to_dict()
    global_temp_mean = train['Temperature'].mean()
    
    for df in [train, test]:
        df['Temperature'] = df['Temperature'].fillna(df['geohash'].map(geo_temp_mean))
        df['Temperature'] = df['Temperature'].fillna(global_temp_mean)
        
    # Target encoding using Day 48 baseline ONLY
    print("Computing target encodings strictly using Day 48 baseline...")
    d48_train = train[train['day'] == 48].copy()
    
    for col in ['geohash', 'timestamp', 'geo_time']:
        global_mean = d48_train['demand'].mean()
        stats = d48_train.groupby(col)['demand'].agg(['count', 'mean'])
        smooth_mean = (stats['count'] * stats['mean'] + 20 * global_mean) / (stats['count'] + 20)
        smooth_mean = smooth_mean.to_dict()
        
        train[col + '_te'] = train[col].map(smooth_mean).fillna(global_mean)
        test[col + '_te'] = test[col].map(smooth_mean).fillna(global_mean)
        
    # Define log-ratio target: y_diff = log(demand + 0.01) - log(geo_time_te + 0.01)
    train['y_diff'] = np.log(train['demand'] + 0.01) - np.log(train['geo_time_te'] + 0.01)
    
    # Label encode categoricals
    cat_cols = ['RoadType', 'LargeVehicles', 'Landmarks', 'Weather', 'geohash', 'geohash_3', 'geohash_4', 'geohash_5', 'timestamp', 'geo_time']
    for col in cat_cols:
        le = LabelEncoder()
        combined = pd.concat([train[col], test[col]]).astype(str)
        le.fit(combined)
        train[col] = le.transform(train[col].astype(str))
        test[col] = le.transform(test[col].astype(str))
        
    features = ['geohash', 'day', 'timestamp', 'RoadType', 'NumberofLanes', 'LargeVehicles', 'Landmarks', 'Temperature', 'Weather',
                'latitude', 'longitude', 'geohash_3', 'geohash_4', 'geohash_5', 'minutes', 'hour', 'time_sin', 'time_cos', 'geo_time',
                'geohash_te', 'timestamp_te', 'geo_time_te', 'is_day_49']
                
    X_train = train[features].values
    y_train_diff = train['y_diff'].values
    geo_time_te_tr = train['geo_time_te'].values
    
    X_test = test[features].values
    geo_time_te_te = test['geo_time_te'].values
    
    d49_train_indices = train[train['day'] == 49].index.values
    
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    oof_diff_lgb = np.zeros(len(X_train))
    oof_diff_xgb = np.zeros(len(X_train))
    oof_diff_cat = np.zeros(len(X_train))
    
    preds_diff_lgb = np.zeros(len(X_test))
    preds_diff_xgb = np.zeros(len(X_test))
    preds_diff_cat = np.zeros(len(X_test))
    
    print("\n--- Training Ensemble Models on log-ratio ---")
    for fold, (train_idx, val_idx) in enumerate(kf.split(X_train, y_train_diff)):
        print(f"\n--- Fold {fold+1} / 5 ---")
        X_tr, y_tr = X_train[train_idx], y_train_diff[train_idx]
        X_va, y_va = X_train[val_idx], y_train_diff[val_idx]
        
        # 1. LightGBM
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
        oof_diff_lgb[val_idx] = model_lgb.predict(X_va)
        preds_diff_lgb += model_lgb.predict(X_test) / 5.0
        
        # 2. XGBoost
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
        oof_diff_xgb[val_idx] = model_xgb.predict(X_va)
        preds_diff_xgb += model_xgb.predict(X_test) / 5.0
        
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
        oof_diff_cat[val_idx] = model_cat.predict(X_va)
        preds_diff_cat += model_cat.predict(X_test) / 5.0
        
    # Reconstruct OOF predictions for demand
    oof_pred_lgb = np.clip(np.exp(oof_diff_lgb + np.log(geo_time_te_tr + 0.01)) - 0.01, 0.0, 1.0)
    oof_pred_xgb = np.clip(np.exp(oof_diff_xgb + np.log(geo_time_te_tr + 0.01)) - 0.01, 0.0, 1.0)
    oof_pred_cat = np.clip(np.exp(oof_diff_cat + np.log(geo_time_te_tr + 0.01)) - 0.01, 0.0, 1.0)
    oof_pred_blend = oof_pred_lgb * 0.35 + oof_pred_xgb * 0.45 + oof_pred_cat * 0.20
    
    # Calculate R2 on Day 49 OOF records
    r2_d49_blend = r2_score(y_train_orig[d49_train_indices], oof_pred_blend[d49_train_indices])
    print(f"\nOverall Out-of-Fold Day 49 Blend R2: {r2_d49_blend:.5f} (HackerEarth Score Estimate: {100 * r2_d49_blend:.3f})")
    
    # Reconstruct test set predictions
    print("\nGenerating final test set predictions...")
    preds_test_lgb = np.clip(np.exp(preds_diff_lgb + np.log(geo_time_te_te + 0.01)) - 0.01, 0.0, 1.0)
    preds_test_xgb = np.clip(np.exp(preds_diff_xgb + np.log(geo_time_te_te + 0.01)) - 0.01, 0.0, 1.0)
    preds_test_cat = np.clip(np.exp(preds_diff_cat + np.log(geo_time_te_te + 0.01)) - 0.01, 0.0, 1.0)
    
    final_preds = preds_test_lgb * 0.35 + preds_test_xgb * 0.45 + preds_test_cat * 0.20
    final_preds = np.clip(final_preds, 0.0, 1.0)
    
    submission = pd.DataFrame({
        'Index': test_indices,
        'demand': final_preds
    })
    
    submission_path = r"C:\Users\ashok\.gemini\antigravity\scratch\traffic-prediction\submission.csv"
    submission.to_csv(submission_path, index=False)
    print(f"Saved submission to: {submission_path}")
    print("Training completed successfully!")

if __name__ == '__main__':
    main()
