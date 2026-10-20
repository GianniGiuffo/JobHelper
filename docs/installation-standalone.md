# Installazione autonoma

Target: server Linux con Docker Engine e plugin Compose, Python 3 per il bootstrap, Ollama su PC della LAN. Non sono richiesti Nextcloud, Stirling, GPU sul server, Redis esterno o database separato. Una propria istanza n8n è creata esclusivamente da questo overlay.

1. Clona la repo e scegli una cartella privata. Esegui `python3 scripts/setup.py`: crea `.env` e `secrets/` solo se assenti, senza mostrare segreti. La cartella secrets è 0700 su Linux; i singoli file sono leggibili dai container non root. Non spostare questi file in una cartella pubblica. Su Windows proteggi la cartella con ACL del tuo utente.
2. In `.env`, imposta `OLLAMA_BASE_URL` con indirizzo **LAN del PC con Ollama**, senza usare `localhost` del container. I due modelli devono risultare in `ollama list` su quel PC. Configura firewall e ascolto come nella guida hardware.
3. Esegui `docker compose -f compose.addons.yml -f compose.standalone.yml config --quiet`, poi `docker compose -f compose.addons.yml -f compose.standalone.yml up -d --build`.
4. Apri `http://localhost:5678` dal server o usa tunnel SSH `ssh -L 5678:localhost:5678 utente@server`. Crea l'account proprietario n8n. Per LAN/Tailscale configura un reverse proxy HTTPS e imposta correttamente `WEBHOOK_URL` e `N8N_EDITOR_BASE_URL` in un overlay locale; mantieni cookie sicuri. Solo durante una prova HTTP locale esplicita puoi impostare `N8N_SECURE_COOKIE=false`.
5. Importa i workflow, configura la credenziale interna e controlla i collegamenti: [procedura](configuring-n8n-and-credentials.md). Non pubblicare i Forms prima di associare credenziali e workflow.
6. Esegui il workflow healthcheck. Poi pubblica `00-ui-start` e `10-status-results`, apri i rispettivi **Production URL** con il proprietario autenticato. Avvia con un CV testuale autorizzato. Conserva il `run_id` mostrato e usa il secondo form.

### Dimensionamento e storage

I limiti Compose riservano al massimo circa 4,3 GiB complessivi per n8n, adattatore, SearXNG e crawler; sono tetti, non una misura di consumo effettivo. Occorre margine per sistema, Docker e servizi già presenti. Il modello Ollama sul PC richiede RAM/VRAM aggiuntiva. Su server da 16 GB già impegnato riduci limiti di ricerca e misura prima di aumentare concorrenza. Immagini e modelli possono occupare diversi GB; prevedi spazio anche per volumi e backup.

È pubblicata solo la porta n8n, **127.0.0.1:5678** per default. `hunter:8000`, `searxng:8080` e `crawl4ai:11235` sono sulla rete Docker privata del progetto. Nessuna porta Ollama viene pubblicata da questo Compose.

Volumi nominati: `hunter_data` (SQLite, PDF temporanei e dati derivati) e `n8n_data` (configurazione/credenziali n8n). Il prefisso reale dipende dal progetto Compose. Fai backup privati e cifrati; ferma prima i servizi per una copia coerente di SQLite. Non usare comandi che eliminino volumi per aggiornare.

### Aggiornamenti

Immagini versionate, SearXNG anche per digest. Il tag non è garanzia immutabile per gli altri componenti: registra il digest risolto nel collaudo locale. Prima di aggiornare n8n o il crawler esegui CI/import in un ambiente isolato e verifica un CV sintetico. Non eseguire import ripetuti alla cieca su workflow personalizzati: gli ID stabili aggiornano gli stessi workflow.
