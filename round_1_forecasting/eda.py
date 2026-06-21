import os
import pandas as pd
import numpy as np

def main():
    dataset_dir = r"C:\Users\ashok\.gemini\antigravity\dataset\dataset"
    train = pd.read_csv(os.path.join(dataset_dir, "train.csv"))
    test = pd.read_csv(os.path.join(dataset_dir, "test.csv"))
    
    print("Train Shape:", train.shape)
    print("Test Shape:", test.shape)
    
    print("\nTrain Columns:", list(train.columns))
    print("Test Columns:", list(test.columns))
    
    print("\nUnique Days in Train:", sorted(train['day'].unique()))
    print("Unique Days in Test:", sorted(test['day'].unique()))
    
    print("\nTrain Days info:")
    for d in sorted(train['day'].unique()):
        day_df = train[train['day'] == d]
        print(f"  Day {d}: {len(day_df)} rows, times from {day_df['timestamp'].min()} to {day_df['timestamp'].max()}")
        
    print("\nTest Days info:")
    for d in sorted(test['day'].unique()):
        day_df = test[test['day'] == d]
        print(f"  Day {d}: {len(day_df)} rows, times from {day_df['timestamp'].min()} to {day_df['timestamp'].max()}")
        
    print("\nTrain geohashes:", train['geohash'].nunique())
    print("Test geohashes:", test['geohash'].nunique())
    overlap = len(set(train['geohash']).intersection(set(test['geohash'])))
    print("Geohash overlap between train and test:", overlap)
    
    # Missing values
    print("\nMissing values in train:")
    print(train.isnull().sum()[train.isnull().sum() > 0])
    
    print("\nMissing values in test:")
    print(test.isnull().sum()[test.isnull().sum() > 0])

if __name__ == '__main__':
    main()
