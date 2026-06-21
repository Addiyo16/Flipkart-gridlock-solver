import os
import json

def main():
    brain_dir = r"C:\Users\ashok\.gemini\antigravity\brain"
    past_session = "9a68881f-9f42-497a-9b69-5e622236c737"
    msg_path = os.path.join(brain_dir, past_session, ".system_generated", "messages", "8ebf1d4c-292d-4bd3-bcd2-e98335b80a45.json")
    
    if os.path.exists(msg_path):
        with open(msg_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print("Message Keys:", data.keys())
            print("Sender/Receiver:", data.get('sender'), "->", data.get('recipient'))
            # check content
            content = data.get('content', '')
            print("Content:\n", content)
    else:
        print("Message file does not exist.")

if __name__ == '__main__':
    main()
