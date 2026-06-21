import os
import pandas as pd
import numpy as np

def main():
    dataset_dir = r"C:\Users\ashok\.gemini\antigravity\dataset\dataset"
    train = pd.read_csv(os.path.join(dataset_dir, "train.csv"))
    
    def time_to_minutes(ts):
        parts = ts.split(':')
        return int(parts[0]) * 60 + int(parts[1]) if len(parts) == 2 else 0
        
    train['minutes'] = train['timestamp'].apply(time_to_minutes)
    overlap = train[train['minutes'] <= 120]
    
    d48 = overlap[overlap['day'] == 48]
    d49 = overlap[overlap['day'] == 49]
    
    merged = pd.merge(d48, d49, on=['geohash', 'minutes'], suffixes=('_d48', '_d49'))
    
    # Let's aggregate by hour
    merged['hour'] = merged['minutes'] // 60
    
    print("Ratio of sums by hour:")
    for h in sorted(merged['hour'].unique()):
        h_df = merged[merged['hour'] == h]
        ratio = h_df['demand_d49'].sum() / h_df['demand_d48'].sum()
        print(f"  Hour {h}: {ratio:.4f} (d48 sum: {h_df['demand_d48'].sum():.2f}, d49 sum: {h_df['demand_d49'].sum():.2f})")
        
    # Let's aggregate by road type
    print("\nRatio of sums by RoadType:")
    for rt in merged['RoadType_d49'].unique():
        rt_df = merged[merged['RoadType_d49'] == rt]
        if len(rt_df) > 0 and rt_df['demand_d48'].sum() > 0:
            ratio = rt_df['demand_d49'].sum() / rt_df['demand_d48'].sum()
            print(f"  RoadType {rt}: {ratio:.4f} (d48 sum: {rt_df['demand_d48'].sum():.2f}, d49 sum: {rt_df['demand_d49'].sum():.2f})")
            
    # Let's look at geohash-level ratio distribution
    geo_stats = merged.groupby('geohash')[['demand_d48', 'demand_d49']].sum()
    geo_stats['ratio'] = geo_stats['demand_d49'] / (geo_stats['demand_d48'] + 1e-5)
    print("\nGeohash ratio statistics (for geohashes with d48 demand > 0.1):")
    valid_geos = geo_stats[geo_stats['demand_d48'] > 0.1]
    print(valid_geos['ratio'].describe())

if __name__ == '__main__':
    main()
