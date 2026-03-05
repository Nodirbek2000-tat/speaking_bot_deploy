
import os
BASE = "E:/Speaking_Bot/speaking_bot"

def wf(relpath, content):
    full = os.path.join(BASE, relpath.replace("/", os.sep))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)
    print("OK:", relpath)
