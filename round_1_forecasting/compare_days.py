import os
import pandas as pd
import numpy as np

def main():
    dataset_dir = r"C:\Users\ashok\.gemini\antigravity\dataset\dataset"
    train = pd.read_csv(os.path.join(dataset_dir, "train.csv"))
    
    # Let's filter times between 00:00 and 02:00
    def time_to_minutes(ts):
        parts = ts.split(':')
        return int(parts[0]) * 60 + int(parts[1]) if len(parts) == 2 else 0
        
    train['minutes'] = train['timestamp'].apply(time_to_minutes)
    
    # Overlapping period: day 48 and day 49, minutes <= 120 (00:00 to 02:00)
    overlap = train[train['minutes'] <= 120]
    
    d48_overlap = overlap[overlap['day'] == 48]
    d49_overlap = overlap[overlap['day'] == 49]
    
    print("Day 48 overlap rows:", len(d48_overlap))
    print("Day 49 overlap rows:", len(d49_overlap))
    
    # Merge on geohash and minutes
    merged = pd.merge(d48_overlap, d49_overlap, on=['geohash', 'minutes'], suffixes=('_d48', '_d49'))
    print("Merged rows:", len(merged))
    
    if len(merged) > 0:
        ratio = merged['demand_d49'] / (merged['demand_d48'] + 1e-5)
        print("Mean ratio (d49 / d48):", ratio.mean())
        print("Median ratio (d49 / d48):", ratio.median())
        print("Sum of demand d48:", merged['demand_d48'].sum())
        print("Sum of demand d49:", merged['demand_d49'].sum())
        print("Ratio of sums:", merged['demand_d49'].sum() / merged['demand_d48'].sum())
        
        # Check overall demand means
        print("Overall Day 48 mean:", train[train['day'] == 48]['demand'].mean())
        print("Overall Day 49 train mean:", train[train['day'] == 49]['demand'].mean())
        print("Overlap Day 48 mean:", d48_overlap['demand'].mean())
        print("Overlap Day 49 mean:", d49_overlap['demand'].mean())

if __name__ == '__main__':
    main()
