import os
import pandas as pd

def main():
    dataset_dir = r"C:\Users\ashok\.gemini\antigravity\dataset\dataset"
    test_path = os.path.join(dataset_dir, "test.csv")
    train_path = os.path.join(dataset_dir, "train.csv")
    
    test = pd.read_csv(test_path)
    train = pd.read_csv(train_path)
    
    print("=== Test Set ===")
    print("Shape:", test.shape)
    print("Unique days:", test['day'].unique())
    print("Unique timestamps count:", test['timestamp'].nunique())
    print("Min timestamp:", test['timestamp'].min())
    print("Max timestamp:", test['timestamp'].max())
    
    print("\n=== Train Set ===")
    print("Shape:", train.shape)
    print("Unique days:", train['day'].unique())
    print("Day 48 timestamp count:", train[train['day'] == 48]['timestamp'].nunique())
    print("Day 48 min timestamp:", train[train['day'] == 48]['timestamp'].min())
    print("Day 48 max timestamp:", train[train['day'] == 48]['timestamp'].max())
    print("Day 49 timestamp count:", train[train['day'] == 49]['timestamp'].nunique())
    print("Day 49 min timestamp:", train[train['day'] == 49]['timestamp'].min())
    print("Day 49 max timestamp:", train[train['day'] == 49]['timestamp'].max())
    
    print("\n=== Sample of Test Timestamps ===")
    print(test['timestamp'].value_counts().sort_index().head(20))
    print(test['timestamp'].value_counts().sort_index().tail(20))

if __name__ == '__main__':
    main()
