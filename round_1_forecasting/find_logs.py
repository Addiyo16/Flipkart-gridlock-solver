import os

def main():
    brain_dir = r"C:\Users\ashok\.gemini\antigravity\brain"
    past_session = "9a68881f-9f42-497a-9b69-5e622236c737"
    target_dir = os.path.join(brain_dir, past_session)
    
    if not os.path.exists(target_dir):
        print(f"Directory {target_dir} does not exist.")
        return
        
    print(f"Listing all files recursively in {target_dir}:")
    for root, dirs, files in os.walk(target_dir):
        for f in files:
            path = os.path.join(root, f)
            size = os.path.getsize(path)
            rel = os.path.relpath(path, target_dir)
            print(f"- {rel} ({size} bytes)")
            
if __name__ == '__main__':
    main()
