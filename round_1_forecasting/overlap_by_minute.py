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
    
    # Group by day and minutes, calculate mean demand
    stats = train.groupby(['day', 'minutes'])['demand'].mean().reset_index()
    
    d48_stats = stats[stats['day'] == 48].rename(columns={'demand': 'demand_d48'})
    d49_stats = stats[stats['day'] == 49].rename(columns={'demand': 'demand_d49'})
    
    merged = pd.merge(d48_stats, d49_stats, on='minutes')
    merged['ratio'] = merged['demand_d49'] / merged['demand_d48']
    
    print("Minute-by-minute demand and ratio:")
    for _, row in merged.iterrows():
        print(f"  Min {int(row['minutes'])} ({int(row['minutes'])//60:02d}:{int(row['minutes'])%60:02d}) -> d48: {row['demand_d48']:.4f}, d49: {row['demand_d49']:.4f}, ratio: {row['ratio']:.4f}")

if __name__ == '__main__':
    main()
