# Accanto a n8n già esistente

Non usare `compose.standalone.yml`: quel file aggiunge n8n. Non servono accesso all'API pubblica n8n o modifiche ai volumi dell'istanza esistente.

1. Nella cartella del progetto esegui `python3 scripts/setup.py`, modifica `.env` per Ollama e per eventuali servizi già disponibili.
2. Avvia esclusivamente `docker compose -f compose.addons.yml up -d --build`. Se hai già SearXNG/Crawl4AI, imposta i loro URL e avvia solo il servizio `hunter` con `docker compose -f compose.addons.yml up -d --build --no-deps hunter`. Se manca solo un servizio, nomina esplicitamente `hunter` e quel servizio nel comando. Gli endpoint esistenti devono rispettare i contratti/versioni documentati.
3. Collega l'adattatore alla rete di n8n con un overlay locale, senza ricreare n8n. Esempio, sostituendo il nome con quello realmente esistente:

```yaml
services:
  hunter:
    networks: [hunter, n8n_esistente]
networks:
  n8n_esistente:
    external: true
    name: nome_rete_verificato
```

Avvia con `docker compose -f compose.addons.yml -f compose.local.yml up -d --build`. Usa `docker network ls` e `docker inspect` solo per individuare la rete reale. Se il nome DNS `hunter` collide con un altro servizio, assegna un alias specifico e rigenera gli export con `python scripts/generate_workflows.py --base-url http://alias-scelto:8000` prima dell'import.

4. Se n8n è nativo anziché Docker, un overlay locale può pubblicare **solo su loopback** `127.0.0.1:8000:8000` per hunter; rigenera gli export con `--base-url http://127.0.0.1:8000`. Se n8n è su altra macchina, usa rete privata e proxy autenticato/TLS; non pubblicare l'API su Internet.
5. Importa manualmente i workflow e associa gli ID locali e la credenziale Header Auth come indicato nella [guida](configuring-n8n-and-credentials.md). La configurazione export usa Form Trigger 2.6 disponibile nel target n8n 2.44.4: controlla la tua versione prima di importare. Per una versione precedente con solo Basic Auth occorre un adattamento e un test dedicato, non un aggiornamento automatico dell'istanza.

### Privacy dell'istanza condivisa con altri workflow

Gli export disattivano il salvataggio di esecuzioni riuscite, fallite e manuali per questi workflow. Non cambiare impostazioni globali della tua n8n senza valutarne l'effetto sugli altri workflow. Controlla payload/upload limits, logging di proxy, execution pruning e storage binario della versione effettiva. Non usare test editor con CV reali: l'editor espone gli input all'operatore e può trattenere dati in memoria. Prova prima con fixture.

Le credenziali Stirling/Nextcloud non sono riusate automaticamente da quelle dell'istanza n8n: in questa implementazione le chiamate sono eseguite nell'adattatore e i secret vanno montati lì. Nessun servizio Nextcloud o Stirling è reinstallato.
