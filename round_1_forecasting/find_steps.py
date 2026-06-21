import os
import json

def main():
    transcript_path = r"C:\Users\ashok\.gemini\antigravity\brain\9a68881f-9f42-497a-9b69-5e622236c737\.system_generated\logs\transcript.jsonl"
    with open(transcript_path, 'r', encoding='utf-8') as f:
        for idx, line in enumerate(f):
            try:
                obj = json.loads(line)
                step_idx = obj.get('step_index')
                if 40 <= step_idx < 100:
                    print(f"Step {step_idx} ({obj.get('source')}): {obj.get('type')}")
                    # If model, print first 200 chars of thinking/content or tool call
                    if obj.get('source') == 'MODEL':
                        print(f"  Thinking: {obj.get('thinking', '')[:100]}")
                        if obj.get('tool_calls'):
                            for tc in obj.get('tool_calls'):
                                print(f"  Tool Call: {tc['name']} with args {str(tc['args'])[:150]}")
                    elif obj.get('source') == 'USER_EXPLICIT':
                        print(f"  User Request: {obj.get('content', '')[:100]}")
            except Exception as e:
                pass

if __name__ == '__main__':
    main()
