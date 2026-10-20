# Milestone e prove

La specifica originale `AI_Job_Hunter_SPEC_Codex.md` resta il brief.

1. **Audit e contratti**: repo iniziale priva di codice/commit; Python 3.11 e Node disponibili, Docker/n8n/servizi LAN non disponibili in questo ambiente. Consultate API e sorgenti ufficiali. Approvati dall'utilizzatore servizio Python interno con SQLite e licenza MIT. n8n mantiene Forms e orchestrazione. Le Data Tables diventano una proiezione opzionale; SQLite è l'archivio autorevole. L'estrazione PDF interna con pypdf permette controllo upload e OCR senza propagare testo e PDF nei sotto-workflow n8n.
2. **MVP**: Forms, creazione asincrona job, pipeline modulare, adapter, persistenza ed export, agente B con flag OFF.
3. **Robustezza**: fixture offline, test API, privacy, SSRF, idempotenza, budget, documentazione e CI.

Il pilota con CV reale e 20 aziende richiede servizi configurati e autorizzazione del CV; non equivale ai test con fixture. Non dichiarare verificati import, esecuzione Docker o qualità del modello senza la corrispondente prova.

## Verifica locale del 20 ottobre 2026

- 67 test offline passati su Windows/Python 3.11, con dipendenze vincolate in `requirements.lock` e report JUnit generato localmente. Una deprecazione upstream riguarda il trasporto HTTPX del solo TestClient, non l'esecuzione dell'app.
- Scansione file pubblicabili senza token o email personali riconosciuti; schemi coerenti con i validatori e collegamenti dei 16 workflow verificati.
- Test di integrazione container predisposti in CI: import n8n, contratto Crawl4AI raw e avvio Compose/adattatore/SearXNG. Esito da leggere nelle Actions dopo pubblicazione; non eseguiti localmente perché Docker non è disponibile.
- Prima esecuzione CI: test offline, import reale dei 16 workflow in n8n 2.44.4 e build/avvio adattatore + SearXNG passati. Lo smoke test Crawl4AI ha rilevato che `base_url` e `process_in_browser`, anche falso, sono vietati nel contratto HTTP 0.9.5; adattatore corretto per usare il default raw senza browser e mantenere l'URL fonte fuori dal payload del crawler. Nuova verifica del container richiesta prima di chiudere il collaudo.
- Nessun CV reale elaborato, nessun servizio LAN modificato, nessuna email o candidatura inviata.

La scelta Nominatim pubblico per uso occasionale, con cache/rate limit/attribuzione e policy, è stata confermata dall'utilizzatore. L'uso periodico o sistematico richiede un provider dedicato.

## Contratti consultati

- [n8n Form Trigger](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.formtrigger/): pulsante nativo, default, autenticazione, `options.path`.
- [Execute Sub-workflow](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.executeworkflow/): `waitForSubWorkflow=false` per il runner.
- [Form Ending](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.form/): testo o download binario.
- [Ollama chat](https://docs.ollama.com/api/chat): `format` JSON Schema, `stream=false`, modelli locali configurabili.
- [SearXNG search](https://docs.searxng.org/dev/search_api.html): `/search`, JSON abilitato.
- [Crawl4AI self hosting](https://docs.crawl4ai.com/core/self-hosting/) e [sorgente v0.9.5](https://github.com/unclecode/crawl4ai/blob/v0.9.5/crawl4ai/async_crawler_strategy.py): elaborazione raw HTML senza navigazione browser.
- [Stirling API](https://docs.stirlingpdf.com/API/): disponibilità OCR da verificare nell'OpenAPI dell'istanza.
- [Nextcloud WebDAV](https://docs.nextcloud.com/server/stable/developer_manual/client_apis/WebDAV/basic.html): GET/PUT con app password e cartella limitata.

Versioni target: n8n 2.44.4 (nodes-base 2.44.2), Crawl4AI 0.9.5. Non sono una dichiarazione di compatibilità con versioni n8n precedenti.
