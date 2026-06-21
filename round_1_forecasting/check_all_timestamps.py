import os
import pandas as pd

def main():
    dataset_dir = r"C:\Users\ashok\.gemini\antigravity\dataset\dataset"
    test = pd.read_csv(os.path.join(dataset_dir, "test.csv"))
    train = pd.read_csv(os.path.join(dataset_dir, "train.csv"))
    
    t48 = set(train[train['day'] == 48]['timestamp'].unique())
    t49_tr = set(train[train['day'] == 49]['timestamp'].unique())
    t49_te = set(test['timestamp'].unique())
    
    print("Day 48 unique timestamps count:", len(t48))
    print("Day 49 Train unique timestamps count:", len(t49_tr))
    print("Day 49 Test unique timestamps count:", len(t49_te))
    
    print("\nIntersection of Day 49 Train & Test:", t49_tr.intersection(t49_te))
    print("Are all Day 49 Train in Day 48?", t49_tr.issubset(t48))
    print("Are all Day 49 Test in Day 48?", t49_te.issubset(t48))
    
    print("\nUnion of Day 49 Train & Test:", len(t49_tr.union(t49_te)))
    
    missing_from_48 = t49_te.difference(t48)
    print("Day 49 Test timestamps missing from Day 48:", missing_from_48)

    # Let's print the sorted timestamps in Day 49 Test
    def time_to_minutes(ts):
        parts = ts.split(':')
        return int(parts[0]) * 60 + int(parts[1]) if len(parts) == 2 else 0

    sorted_te = sorted(list(t49_te), key=time_to_minutes)
    print("\nSorted Day 49 Test timestamps:")
    for ts in sorted_te:
        print(f"  {ts} (minutes: {time_to_minutes(ts)})")

if __name__ == '__main__':
    main()
