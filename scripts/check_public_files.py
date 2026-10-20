"""Controllo prudenziale di export e segreti; non sostituisce una revisione umana."""
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    files = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT).decode().split("\0")
    failures = []
    patterns = [r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----", r"gh[pousr]_[A-Za-z0-9]{30,}",
                r"github_pat_[A-Za-z0-9_]{30,}", r"sk-(?:proj-)?[A-Za-z0-9_-]{40,}", r"AKIA[0-9A-Z]{16}"]
    for name in filter(None, files):
        path = ROOT/name
        if name == ".env" or name.startswith(("secrets/", "data/")) or path.suffix.lower() in (".pdf", ".sqlite", ".db"):
            failures.append(name+": file privato non pubblicabile")
            continue
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            if any(re.search(pattern, text) for pattern in patterns):
                failures.append(name+": possibile segreto")
            # Realistic email addresses are forbidden in deliverables; examples use reserved domains.
            for email in re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text):
                domain = email.rsplit("@", 1)[1].lower()
                if not (domain in ("example.org", "example.com", "example.net") or domain.endswith((".example", ".test", ".local", ".invalid"))):
                    failures.append(name+": possibile email personale")
            if name.startswith("workflows/") and path.suffix == ".json":
                workflow = json.loads(text)
                if workflow.get("pinData") or any(n.get("credentials") for n in workflow["nodes"]):
                    failures.append(name+": export contiene dati pinned o riferimenti credenziali")
    if failures:
        raise SystemExit("\n".join(sorted(set(failures))))
    print(f"Controllati {len(list(filter(None, files)))} file pubblicabili; nessun segreto riconosciuto.")


if __name__ == "__main__":
    main()
