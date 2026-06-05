# test_day49.py - Training and validating strictly on Day 49

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
    
    # Split days
    d48 = train[train['day'] == 48].copy()
    d49 = train[train['day'] == 49].copy()
    
    # Process time
    d48['minutes'] = d48['timestamp'].apply(time_to_minutes)
    d49['minutes'] = d49['timestamp'].apply(time_to_minutes)
    
    # Build dictionary reference of Day 48 demand
    d48_dict = {(row['geohash'], row['minutes']): row['demand'] for _, row in d48.iterrows()}
    d48_geo_mean = d48.groupby('geohash')['demand'].mean().to_dict()
    
    # Map lag features for Day 49 only
    def get_lag(df, offset):
        return [d48_dict.get((geo, max(0, min(1425, m + offset))), 0.0) for geo, m in zip(df['geohash'], df['minutes'])]
        
    d49['demand_lag_24h'] = get_lag(d49, 0)
    d49['demand_lag_-15m'] = get_lag(d49, -15)
    d49['demand_lag_+15m'] = get_lag(d49, 15)
    d49['demand_lag_-30m'] = get_lag(d49, -30)
    d49['demand_lag_+30m'] = get_lag(d49, 30)
    d49['geo_mean_yesterday'] = d49['geohash'].map(d48_geo_mean).fillna(0.0)
    
    # Categorical preprocessing
    d49['RoadType'] = d49['RoadType'].fillna('Unknown')
    d49['Weather'] = d49['Weather'].fillna('Unknown')
    
    cat_cols = ['RoadType', 'LargeVehicles', 'Landmarks', 'Weather', 'geohash']
    for col in cat_cols:
        le = LabelEncoder()
        d49[col] = le.fit_transform(d49[col].astype(str))
        
    features = ['geohash', 'minutes', 'RoadType', 'NumberofLanes', 'LargeVehicles', 'Landmarks',
                'demand_lag_24h', 'demand_lag_-15m', 'demand_lag_+15m', 'demand_lag_-30m', 'demand_lag_+30m',
                'geo_mean_yesterday']
                
    X = d49[features].values
    y = d49['demand'].values
    
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    oof = np.zeros(len(X))
    
    for fold, (train_idx, val_idx) in enumerate(kf.split(X, y)):
        X_tr, y_tr = X[train_idx], y[train_idx]
        X_va, y_va = X[val_idx], y[val_idx]
        
        model = lgb.LGBMRegressor(n_estimators=300, learning_rate=0.05, random_state=42, verbose=-1)
        model.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], callbacks=[lgb.early_stopping(20, verbose=False)])
        oof[val_idx] = model.predict(X_va)
        
    r2 = r2_score(y, oof)
    print(f"Validation R2 (Day 49 only): {r2:.5f} (HE Score: {r2*100:.3f})")

if __name__ == '__main__':
    main()
