# find_past_code.py - Check bytes in transcript.jsonl
def main():
    transcript_path = r"C:\Users\ashok\.gemini\antigravity\brain\9a68881f-9f42-497a-9b69-5e622236c737\.system_generated\logs\transcript.jsonl"
    with open(transcript_path, 'rb') as f:
        content = f.read()
    
    total = len(content)
    nulls = content.count(b'\x00')
    non_nulls = total - nulls
    print(f"Total bytes: {total}")
    print(f"Null bytes: {nulls}")
    print(f"Non-null bytes: {non_nulls}")
    
    if non_nulls > 0:
        # Get first 200 non-null bytes
        clean = content.replace(b'\x00', b'')
        print(f"First 200 non-null bytes: {clean[:200]}")
        print(f"Last 200 non-null bytes: {clean[-200:]}")

if __name__ == '__main__':
    main()
