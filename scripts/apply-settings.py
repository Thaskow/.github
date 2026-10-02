import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "repos.json").read_text(encoding="utf-8"))
ADMIN_ROLE = 5
ACTIONS_APP = 15368

for stream in (sys.stdout, sys.stderr):
    stream.reconfigure(encoding="utf-8", errors="replace")


def gh(*args, input=None, check=True):
    r = subprocess.run(["gh", *args], input=input, capture_output=True, text=True, encoding="utf-8", check=False)
    if check and r.returncode:
        sys.exit(f"gh {' '.join(args[:3])} : {r.stderr.strip()}")
    return r.stdout if not r.returncode else None


def api(path, method="GET", body=None, check=True):
    args = ["api", "-X", method, path]
    if body is not None:
        args += ["--input", "-"]
    out = gh(*args, input=json.dumps(body) if body is not None else None, check=check)
    return json.loads(out) if out and out.strip() else {}


class Run:
    def __init__(self, apply):
        self.apply = apply

    def do(self, repo, what, fn):
        print(f"{repo} : {what}{'' if self.apply else ' (simulation)'}")
        if self.apply:
            fn()


def ruleset_body():
    rs = CONFIG["ruleset"]
    return {
        "name": rs["name"],
        "target": "branch",
        "enforcement": "active",
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "bypass_actors": [{"actor_id": ADMIN_ROLE, "actor_type": "RepositoryRole", "bypass_mode": "pull_request"}],
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {"type": "pull_request", "parameters": {
                "required_approving_review_count": 0,
                "dismiss_stale_reviews_on_push": False,
                "require_code_owner_review": False,
                "require_last_push_approval": False,
                "required_review_thread_resolution": True,
                "allowed_merge_methods": ["squash"],
            }},
            {"type": "required_status_checks", "parameters": {
                "strict_required_status_checks_policy": False,
                "required_status_checks": [{"context": rs["required_check"], "integration_id": ACTIONS_APP}],
            }},
        ],
    }


def rename(run, entry):
    owner, target = entry["name"].split("/")
    current = api(f"repos/{entry['name']}", check=False)
    if not current and entry.get("rename_from"):
        current = api(f"repos/{owner}/{entry['rename_from']}", check=False)
    if not current:
        print(f"{entry['name']} : introuvable")
        return False
    if current["name"] != target:
        run.do(entry["name"], f"renommé depuis {current['name']}",
               lambda: api(f"repos/{owner}/{current['name']}", "PATCH", {"name": target}))
    return True


def configure(run, entry):
    repo, d = entry["name"], CONFIG["defaults"]
    info = api(f"repos/{repo}", check=False)
    if not info:
        print(f"{repo} : introuvable (renommage pas encore appliqué ?)")
        return
    if info.get("archived"):
        print(f"{repo} : archivé, ignoré")
        return
    external, dormant = entry.get("external"), entry["role"] in ("dormant", "profile")

    if d["vulnerability_alerts"]:
        run.do(repo, "alertes Dependabot", lambda: api(f"repos/{repo}/vulnerability-alerts", "PUT"))
        if not dormant:
            run.do(repo, "correctifs de sécurité Dependabot", lambda: api(f"repos/{repo}/automated-security-fixes", "PUT"))
    if info["visibility"] == "public":
        run.do(repo, "secret scanning + push protection", lambda: api(f"repos/{repo}", "PATCH", {"security_and_analysis": {
            "secret_scanning": {"status": "enabled"}, "secret_scanning_push_protection": {"status": "enabled"}}}))
    if external:
        return

    if entry.get("default_branch_from") and info["default_branch"] == entry["default_branch_from"]:
        run.do(repo, f"branche {entry['default_branch_from']} → main",
               lambda: api(f"repos/{repo}/branches/{entry['default_branch_from']}/rename", "POST", {"new_name": "main"}))

    options = {"delete_branch_on_merge": d["delete_branch_on_merge"], "allow_auto_merge": d["auto_merge"], "has_wiki": False}
    if d["squash_only"]:
        options |= {"allow_squash_merge": True, "allow_merge_commit": False, "allow_rebase_merge": False,
                    "squash_merge_commit_title": "PR_TITLE", "squash_merge_commit_message": "PR_BODY"}
    changed = {k: v for k, v in options.items() if info.get(k) != v}
    if changed:
        run.do(repo, f"options {', '.join(sorted(changed))}", lambda: api(f"repos/{repo}", "PATCH", changed))

    days = d["artifact_retention_days"]
    run.do(repo, f"rétention des artefacts et logs : {days} jours",
           lambda: api(f"repos/{repo}/actions/permissions/artifact-and-log-retention", "PUT", {"days": days}, check=False))

    if d["labels"] and not dormant:
        run.do(repo, "labels", lambda: subprocess.run([sys.executable, str(ROOT / "scripts" / "sync-labels.py"), repo], check=True))

    if entry.get("ruleset"):
        body = ruleset_body()
        existing = next((r for r in api(f"repos/{repo}/rulesets") or [] if r["name"] == body["name"]), None)
        if existing:
            run.do(repo, "ruleset main mis à jour", lambda: api(f"repos/{repo}/rulesets/{existing['id']}", "PUT", body))
        else:
            run.do(repo, "ruleset main créé", lambda: api(f"repos/{repo}/rulesets", "POST", body))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--only", nargs="+", metavar="REPO")
    args = p.parse_args()
    run = Run(args.apply)
    entries = [e for e in CONFIG["repos"] if not args.only or e["name"] in args.only]
    for entry in entries:
        if not entry.get("external") and not rename(run, entry):
            continue
    for entry in entries:
        configure(run, entry)
    if not args.apply:
        print("\nSimulation : relancer avec --apply pour appliquer.")


if __name__ == "__main__":
    main()
