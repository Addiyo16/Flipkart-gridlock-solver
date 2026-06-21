import os

def main():
    brain_dir = r"C:\Users\ashok\.gemini\antigravity\brain"
    past_session = "9a68881f-9f42-497a-9b69-5e622236c737"
    tasks_dir = os.path.join(brain_dir, past_session, ".system_generated", "tasks")
    
    logs_to_read = ["task-80.log", "task-164.log", "task-198.log", "task-216.log", "task-232.log"]
    
    for log_name in logs_to_read:
        path = os.path.join(tasks_dir, log_name)
        if os.path.exists(path):
            print(f"\n==================== {log_name} ====================")
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                print(f.read())
        else:
            print(f"Log {log_name} does not exist.")

if __name__ == '__main__':
    main()
