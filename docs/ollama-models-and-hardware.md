# Ollama sul PC della LAN

Il server n8n può rimanere su Debian; il modello può girare sul PC con GPU della rete privata. Non serve un secondo modello per il secondo agente. Configura entrambi i tag in `.env`; l'API interna usa `/api/chat`, JSON Schema, `stream=false`, `think=false`, temperatura 0, contesto iniziale 8192 e massimo 2200 token in uscita. Il flag `think` richiede un modello/Ollama compatibile; scegli una versione locale che supporti questo contratto ed esegui il test di estrazione prima del pilota.

1. Installa Ollama sul PC con la procedura ufficiale. Esegui `ollama pull qwen3.5:4b` e `ollama list`. Il [tag ufficiale](https://ollama.com/library/qwen3.5:4b) consultato è di circa 4 GB complessivi; il file modello quantizzato è circa 3,3 GB. Download e memoria operativa sono quantità diverse.
   Imposta anche `OLLAMA_NO_CLOUD=1` e riavvia Ollama per disabilitare le funzionalità cloud secondo l'FAQ ufficiale. Utilizza tag scaricati localmente, non varianti cloud.
2. Per ascoltare sulla LAN configura `OLLAMA_HOST` secondo l'[FAQ ufficiale](https://docs.ollama.com/faq) e riavvia il servizio. Un bind ampio richiede un firewall che permetta soltanto il server n8n/adattatore. Non aprire la porta 11434 sul router Internet. Tailscale o un proxy privato autenticato sono alternative.
3. Dal server verifica il percorso fino al PC e poi configura `OLLAMA_BASE_URL=http://indirizzo-lan:11434`. Da un container `localhost` indica quel container. `host.docker.internal` nel Compose indica invece l'host Docker tramite host-gateway: è corretto solo se Ollama gira su quell'host.
4. Esegui `11-healthcheck`; il modello di ricerca deve risultare installato. Il controllo `/api/tags` non prova che la GPU disponga di memoria sufficiente per caricare il modello.

Una RTX 2070 Super da 8 GB può essere un punto di partenza per un modello piccolo quantizzato, ma non viene garantita una latenza o un contesto specifico. Mantieni margine per sistema/desktop e misura con `ollama ps` e strumenti GPU. In CPU il processo può impiegare molto di più; aumenta `OLLAMA_TIMEOUT` e `MAX_TOTAL_RUNTIME` soltanto dopo una misura. Valuta `qwen3.5:2b` se disponibile localmente; non è una garanzia di qualità equivalente.

Non viene scaricato alcun modello automaticamente dal Compose e non è installato un altro Ollama sul server. Il pilota deve registrare versione Ollama, tag/digest modello, velocità, JSON validi dopo 0/1 riparazioni, errori su almeno due CV sintetici e correttezza delle evidenze. Nessun benchmark è inventato in questa repo.
