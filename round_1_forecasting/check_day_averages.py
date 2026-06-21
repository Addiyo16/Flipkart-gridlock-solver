import os
import pandas as pd

def main():
    dataset_dir = r"C:\Users\ashok\.gemini\antigravity\dataset\dataset"
    train = pd.read_csv(os.path.join(dataset_dir, "train.csv"))
    
    # Filter for 0:00 to 2:00
    def time_to_minutes(ts):
        parts = ts.split(':')
        return int(parts[0]) * 60 + int(parts[1]) if len(parts) == 2 else 0
        
    train['minutes'] = train['timestamp'].apply(time_to_minutes)
    morning = train[train['minutes'] <= 120]
    
    d48_morning = morning[morning['day'] == 48]
    d49_morning = morning[morning['day'] == 49]
    
    print("=== Morning (0:00 - 2:00) Averages ===")
    print("Day 48 morning mean demand:", d48_morning['demand'].mean())
    print("Day 49 morning mean demand:", d49_morning['demand'].mean())
    print("Ratio Day 49 / Day 48 morning:", d49_morning['demand'].mean() / d48_morning['demand'].mean())
    
    print("\n=== Average demand by timestamp ===")
    d48_ts = d48_morning.groupby('timestamp')['demand'].mean()
    d49_ts = d49_morning.groupby('timestamp')['demand'].mean()
    
    df_compare = pd.DataFrame({
        'Day 48 Mean': d48_ts,
        'Day 49 Mean': d49_ts
    })
    df_compare['Ratio'] = df_compare['Day 49 Mean'] / df_compare['Day 48 Mean']
    print(df_compare)

if __name__ == '__main__':
    main()
