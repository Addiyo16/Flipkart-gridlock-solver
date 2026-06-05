import os

def main():
    path = r"C:\Users\ashok\.gemini\antigravity\scratch\test_ratio_model_perfect.py"
    if os.path.exists(path):
        with open(path, 'rb') as f:
            content = f.read()
        print("Total bytes:", len(content))
        print("Null bytes:", content.count(b'\x00'))
        print("Space bytes:", content.count(b' '))
        print("Newline bytes:", content.count(b'\n'))
        # Find first non-space, non-null, non-newline byte
        for idx, b in enumerate(content):
            if b not in [0, 32, 10, 13]:
                print(f"First interesting byte at index {idx}: value {b} ({chr(b)})")
                # print 200 bytes from here
                print(content[idx:idx+200])
                break
        else:
            print("No interesting bytes found.")
    else:
        print("File does not exist.")

if __name__ == '__main__':
    main()
