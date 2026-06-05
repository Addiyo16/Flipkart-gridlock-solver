import os
import pandas as pd

def main():
    paths = [
        r"C:\Users\ashok\.gemini\submission_final.csv",
        r"C:\Users\ashok\.gemini\antigravity\scratch\submission_final.csv",
        r"C:\Users\ashok\.gemini\antigravity\scratch\traffic-prediction\submission.csv",
        r"C:\Users\ashok\.gemini\antigravity\scratch\traffic-prediction\submission_ensemble_all.csv",
        r"C:\Users\ashok\.gemini\antigravity\scratch\traffic-prediction\submission_final.csv"
    ]
    
    for p in paths:
        if os.path.exists(p):
            stat = os.stat(p)
            df = pd.read_csv(p)
            print(f"\nPath: {p}")
            print(f"  Size: {stat.st_size} bytes")
            print(f"  Modified Time: {stat.st_mtime}")
            print(f"  Shape: {df.shape}")
            print(f"  Demand Mean: {df['demand'].mean():.6f}")
            print(f"  Demand Min:  {df['demand'].min():.6f}")
            print(f"  Demand Max:  {df['demand'].max():.6f}")
            print(f"  Head:\n", df.head(3))
        else:
            print(f"\nPath does not exist: {p}")

if __name__ == '__main__':
    main()
