# find_past_scores_in_messages.py - Search for score reports in previous conversation messages
import os
import json

def main():
    msg_dir = r"C:\Users\ashok\.gemini\antigravity\brain\9a68881f-9f42-497a-9b69-5e622236c737\.system_generated\messages"
    print(f"Scanning message files in: {msg_dir}")
    
    found = 0
    for f in os.listdir(msg_dir):
        if not f.endswith('.json') or f in ['cursor.json', 'read.json']:
            continue
        path = os.path.join(msg_dir, f)
        try:
            with open(path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                content = str(data.get('content', ''))
                # check if message is from user
                sender = data.get('sender', '') or data.get('source', '')
                if 'USER' in str(sender).upper() or 'user' in str(sender).lower():
                    # check for score patterns
                    if any(x in content for x in ['90', '91', '92', '93', '94', '95', '96', '97', '98', '99', 'score', 'Score']):
                        found += 1
                        print(f"\n--- Found User Message in {f} ({data.get('timestamp')}) ---")
                        print(content)
        except Exception as e:
            pass
            
    print(f"\nTotal score messages found: {found}")

if __name__ == '__main__':
    main()
