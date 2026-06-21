import os
import zipfile

def main():
    zip_path = r"C:\Users\ashok\.gemini\traffic_gridlock_submission.zip"
    
    # Files to include in the root of the ZIP
    files_to_add = {
        r"C:\Users\ashok\.gemini\antigravity\scratch\traffic-prediction\approach.txt": "approach.txt",
        r"C:\Users\ashok\.gemini\antigravity\scratch\traffic-prediction\train.py": "train.py",
        r"C:\Users\ashok\.gemini\antigravity\scratch\traffic-prediction\traffic_prediction.ipynb": "traffic_prediction.ipynb"
    }
    
    # Directory to include recursively
    proto_dir = r"C:\Users\ashok\.gemini\antigravity\scratch\gridlock-solver"
    
    print(f"Creating ZIP archive at: {zip_path}")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Add root files
        for src, dest in files_to_add.items():
            if os.path.exists(src):
                zipf.write(src, dest)
                print(f"  Added: {src} -> {dest}")
            else:
                print(f"  WARNING: File not found: {src}")
                
        # Add prototype directory
        if os.path.exists(proto_dir):
            for root, dirs, files in os.walk(proto_dir):
                for file in files:
                    # Exclude python cache
                    if '__pycache__' in root or file.endswith('.pyc'):
                        continue
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, os.path.dirname(proto_dir))
                    zipf.write(full_path, rel_path)
                    print(f"  Added: {full_path} -> {rel_path}")
        else:
            print(f"  WARNING: Prototype directory not found: {proto_dir}")
            
    print(f"\nZIP file successfully created at: {zip_path}")

if __name__ == '__main__':
    main()
