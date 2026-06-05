import os
import json

def main():
    msg_dir = r"C:\Users\ashok\.gemini\antigravity\brain\9a68881f-9f42-497a-9b69-5e622236c737\.system_generated\messages"
    if not os.path.exists(msg_dir):
        print("Directory does not exist.")
        return
        
    print(f"Scanning all message files in: {msg_dir}")
    
    found = 0
    files = sorted(os.listdir(msg_dir))
    for f in files:
        if not f.endswith('.json') or f in ['cursor.json', 'read.json']:
            continue
        path = os.path.join(msg_dir, f)
        try:
            with open(path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                content = str(data.get('content', ''))
                sender = data.get('sender', '') or data.get('source', '')
                
                # Check for patterns
                if any(x in content.lower() for x in ['score', 'r2', 'submission', 'result', '88.', '90.', '94.', '99.']):
                    found += 1
                    print(f"\n==================== {f} ({sender}) ====================")
                    # print first 500 chars
                    print(content[:600])
                    if len(content) > 600:
                        print("... [TRUNCATED]")
        except Exception as e:
            pass
            
    print(f"\nTotal messages found: {found}")

if __name__ == '__main__':
    main()
