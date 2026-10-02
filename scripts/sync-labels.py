import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

LABELS = json.loads((Path(__file__).resolve().parent.parent / "labels.json").read_text(encoding="utf-8"))
for stream in (sys.stdout, sys.stderr):
    stream.reconfigure(encoding="utf-8", errors="replace")

OBSOLETE = {"accessibility", "duplicate", "good first issue", "help wanted", "invalid", "question", "wontfix", "github_actions", "docker", "python", "javascript"}


def gh(*args, check=True):
    r = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", check=False)
    if check and r.returncode:
        sys.exit(f"gh {' '.join(args)} : {r.stderr.strip()}")
    return r.stdout


def sync(repo):
    current = {l["name"]: l for l in json.loads(gh("label", "list", "-R", repo, "--limit", "200", "--json", "name"))}
    wanted = {l["name"] for l in LABELS}
    for label in LABELS:
        alias = next((a for a in label.get("aliases", []) if a in current and label["name"] not in current), None)
        if alias:
            gh("label", "edit", alias, "-R", repo, "--name", label["name"], "--color", label["color"], "--description", label["description"])
            print(f"{repo} : {alias} → {label['name']}")
        else:
            gh("label", "create", label["name"], "-R", repo, "--color", label["color"], "--description", label["description"], "--force")
    for name in sorted(set(current) - wanted):
        if name not in OBSOLETE:
            continue
        used = gh("api", f"search/issues?q=repo:{repo}+label:%22{quote(name)}%22", "--jq", ".total_count", check=False).strip()
        if used == "0":
            gh("label", "delete", name, "-R", repo, "--yes")
            print(f"{repo} : {name} supprimé")
        else:
            print(f"{repo} : {name} gardé ({used} issue(s)/PR)")
    print(f"{repo} : labels à jour")


for repo in sys.argv[1:]:
    sync(repo)
