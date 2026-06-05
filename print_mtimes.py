import os
import datetime

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
            t = os.path.getmtime(p)
            dt = datetime.datetime.fromtimestamp(t)
            print(f"{p}: {dt}")
        else:
            print(f"{p}: DOES NOT EXIST")

if __name__ == '__main__':
    main()
