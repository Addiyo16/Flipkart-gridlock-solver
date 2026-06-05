# test_lags.py - Test script to verify lag features performance

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
    test = pd.read_csv(os.path.join(dataset_dir, "test.csv"))
    
    # Preprocess
    train['minutes'] = train['timestamp'].apply(time_to_minutes)
    test['minutes'] = test['timestamp'].apply(time_to_minutes)
    
    # Create reference for Day 48
    d48 = train[train['day'] == 48].copy()
    
    # Compute mean demand of geohash on day 48
    d48_geo_mean = d48.groupby('geohash')['demand'].mean().to_dict()
    
    # Pivot Day 48 to easily query any (geohash, minutes)
    d48_pivot = d48.pivot(index='geohash', columns='minutes', values='demand').fillna(0.0)
    
    # Function to get lag demand
    def get_lag_feature(df, offset_minutes):
        # We query the pivot table.
        # For a given geohash and minutes, the lag minutes on Day 48 is (minutes + offset_minutes)
        # Note: if minutes + offset is outside 0..1425, we clamp or wrap
        lags = []
        for idx, row in df.iterrows():
            geo = row['geohash']
            target_min = row['minutes'] + offset_minutes
            # clamp to 0..1425
            target_min = max(0, min(1425, target_min))
            
            if geo in d48_pivot.index:
                # Find the closest available timestamp in the pivot columns
                # Since minutes are multiples of 15, target_min should match directly
                # If not present, get 0.0
                val = d48_pivot.loc[geo, target_min] if target_min in d48_pivot.columns else 0.0
                lags.append(val)
            else:
                lags.append(0.0)
        return lags

    print("Engineering lag features...")
    # Let's compute lag features for train and test
    # We will do it for the train set first to see CV score
    train_df = train.copy()
    
    train_df['demand_lag_24h'] = get_lag_feature(train_df, 0)
    train_df['demand_lag_23h45m'] = get_lag_feature(train_df, -15)
    train_df['demand_lag_24h15m'] = get_lag_feature(train_df, 15)
    train_df['demand_lag_23h30m'] = get_lag_feature(train_df, -30)
    train_df['demand_lag_24h30m'] = get_lag_feature(train_df, 30)
    
    train_df['geo_mean_yesterday'] = train_df['geohash'].map(d48_geo_mean).fillna(0.0)
    
    # Feature list
    train_df['RoadType'] = train_df['RoadType'].fillna('Unknown')
    train_df['Weather'] = train_df['Weather'].fillna('Unknown')
    
    # Standard label encoding
    cat_cols = ['RoadType', 'LargeVehicles', 'Landmarks', 'Weather', 'geohash']
    for col in cat_cols:
        le = LabelEncoder()
        train_df[col] = le.fit_transform(train_df[col].astype(str))
        
    features = ['geohash', 'day', 'minutes', 'RoadType', 'NumberofLanes', 'LargeVehicles', 'Landmarks', 
                'demand_lag_24h', 'demand_lag_23h45m', 'demand_lag_24h15m', 'demand_lag_23h30m', 'demand_lag_24h30m',
                'geo_mean_yesterday']
                
    X = train_df[features].values
    y = train_df['demand'].values
    
    # Evaluate with LightGBM CV
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    oof = np.zeros(len(X))
    
    print("Training LightGBM CV...")
    for fold, (train_idx, val_idx) in enumerate(kf.split(X, y)):
        X_tr, y_tr = X[train_idx], y[train_idx]
        X_va, y_va = X[val_idx], y[val_idx]
        
        model = lgb.LGBMRegressor(n_estimators=500, learning_rate=0.05, random_state=42, verbose=-1)
        model.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], callbacks=[lgb.early_stopping(30, verbose=False)])
        oof[val_idx] = model.predict(X_va)
        
    r2 = r2_score(y, oof)
    print(f"Validation R2 with lags: {r2:.5f} (HE Score: {r2*100:.3f})")

if __name__ == '__main__':
    main()
