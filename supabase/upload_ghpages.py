import base64, json, subprocess, sys, os

REPO = "ThreepleS/ai-app-frontend"
BRANCH = "gh-pages"
LOCAL = r"C:\Users\ThreepleS\Desktop\my_projects\TgAiPlus\openrouter-telegram-bot\gh-pages"

def get_sha(path):
    out = subprocess.run(
        ["gh", "api", f"repos/{REPO}/contents/{path}?ref={BRANCH}"],
        capture_output=True, text=True)
    if out.returncode != 0:
        return None  # файла нет
    return json.loads(out.stdout).get("sha")

def upload(path, msg):
    full = os.path.join(LOCAL, path)
    with open(full, "rb") as f:
        content = base64.b64encode(f.read()).decode("ascii")
    sha = get_sha(path)
    body = {
        "message": msg,
        "content": content,
        "branch": BRANCH,
    }
    if sha:
        body["sha"] = sha
    out = subprocess.run(
        ["gh", "api", f"repos/{REPO}/contents/{path}", "--method", "PUT",
         "-H", "Accept: application/vnd.github+json",
         "--input", "-"],
        input=json.dumps(body), capture_output=True, text=True)
    if out.returncode == 0:
        print(f"OK  {path} (sha={sha is not None})")
    else:
        print(f"ERR {path}: {out.stderr[:300]}")

upload("index.html", "update frontend: Edge Functions backend")
upload("admin.html", "update admin: Edge Functions backend")
