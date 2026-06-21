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
    
    d48 = train[train['day'] == 48]
    
    # Group by minutes and calculate mean demand
    stats = d48.groupby('minutes')['demand'].mean().reset_index()
    
    print("Day 48 demand curve (every 1 hour):")
    for h in range(24):
        mins = h * 60
        # Average over the hour
        val = stats[(stats['minutes'] >= mins) & (stats['minutes'] < mins + 60)]['demand'].mean()
        print(f"  Hour {h:02d}: {val:.4f}")

if __name__ == '__main__':
    main()
