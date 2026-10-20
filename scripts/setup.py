"""Bootstrap locale non distruttivo, senza connessioni di rete."""
from pathlib import Path
import os
import secrets

ROOT = Path(__file__).resolve().parents[1]


def main():
    os.umask(0o077)
    folder = ROOT / "secrets"
    folder.mkdir(exist_ok=True)
    folder.chmod(0o700)
    for name in ("hunter_api_token", "crawl_api_token", "n8n_encryption_key"):
        path = folder / name
        if not path.exists():
            path.write_text(secrets.token_hex(32)+"\n", encoding="utf-8")
            # Compose mounts individual files; non-root container users must read them.
            # The 0700 parent keeps the files inaccessible to other users on the host.
            path.chmod(0o444)
    env = ROOT / ".env"
    if not env.exists():
        content = (ROOT / ".env.example").read_text(encoding="utf-8")
        content += "\nSEARXNG_SECRET="+secrets.token_hex(32)+"\n"
        content += "CRAWL4AI_API_TOKEN="+(folder/"crawl_api_token").read_text().strip()+"\n"
        env.write_text(content, encoding="utf-8")
        env.chmod(0o600)
    print("Configurazione locale pronta. File esistenti preservati; nessun segreto stampato.")


if __name__ == "__main__":
    main()
