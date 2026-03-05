
import os
BASE = "E:/Speaking_Bot/speaking_bot"

def wf(p, c):
    fp = os.path.join(BASE, p.replace("/", os.sep))
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    open(fp, "w", encoding="utf-8").write(c)
    print("OK:", p)

print("Master script loaded OK")
