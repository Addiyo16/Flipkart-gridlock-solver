import os
import json

def main():
    transcript_path = r"C:\Users\ashok\.gemini\antigravity\brain\9a68881f-9f42-497a-9b69-5e622236c737\.system_generated\logs\transcript.jsonl"
    with open(transcript_path, 'r', encoding='utf-8') as f:
        for idx, line in enumerate(f):
            try:
                obj = json.loads(line)
                content = obj.get('content', '')
                if any(x in content for x in ['91.102', '91.1', '91.10247']):
                    print(f"Step {obj.get('step_index')}: {content[:300]}...")
            except Exception as e:
                pass

if __name__ == '__main__':
    main()
