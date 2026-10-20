# Prove verificabili

## Offline, senza siti o CV reali

Installa il progetto in un ambiente Python 3.11 con `pip install -c requirements.lock -e '.[test]'`, poi:

```sh
python -m pytest -q --junitxml=test-results/offline.xml
python scripts/check_public_files.py
python -m scripts.generate_schemas
python scripts/generate_workflows.py
```

`conftest.py` genera PDF testuali sintetici e vieta socket reali durante i test. FastAPI viene eseguito in-process con TestClient/ASGITransport; LLM, search e crawl sono sostituiti da fixture. I test degli adattatori usano MockTransport per verificare richieste, OCR multipart, JSON Schema, retry e WebDAV. Nessuna API esterna è contattata e nessuna email può essere inviata.

Copertura: upload/limiti, stato queued, due CV/piani distinti, deduplica upload/domini/upsert, raggio e score minimo, coordinate sconosciute, 403 e risultati parziali, agente B OFF/ON, OCR OFF e ON, contatti/fonti, export e formule CSV, SSRF/redirect/DNS, contenuti attivi rimossi prima di Crawl4AI, robots, budget e timeout, riferimenti workflow, Compose e coerenza schemi.

Questi test non sostituiscono un'istanza n8n reale e non verificano la pertinenza semantica di un modello vero.

## CI con container reali

`.github/workflows/ci.yml` esegue test e scansione, rigenerazione senza diff, validazione Compose e due job separati:

1. Import CLI dei JSON in un container **n8n 2.44.4 isolato con database temporaneo**. Verifica importabilità, non le tue credenziali né il rendering del form nell'istanza esistente.
2. Richiesta **Crawl4AI 0.9.5 reale** con HTML raw sintetico, senza download di siti esterni. Per ripeterlo localmente avvia un crawler sulla loopback con credenziale temporanea e imposta `CRAWL_TEST_TOKEN`, poi `python scripts/check_crawl_contract.py`.

La CI non usa il tuo server, Ollama, Nextcloud, Stirling o CV personali. Leggi gli esiti di GitHub Actions prima di considerare passati i job dei container.

## Pilota LAN, da eseguire con configurazione e CV autorizzati

- Prima usa un PDF sintetico con i servizi reali: controlla upload, bottone, conferma rapida e ID, stato progressivo, export e assenza di contenuti CV nei log n8n.
- Verifica un PDF testuale con integrazioni OFF; una scansione con OCR OFF deve fallire chiaramente. Solo dopo prova OCR ON sulla tua versione, se disponibile.
- Avvia al massimo 20 aziende, Torino 30 km, con un CV espressamente autorizzato. Non avviare automaticamente questo pilota solo perché i test offline passano.
- Revisiona manualmente un sottoinsieme (ad esempio cinque aziende): dominio ufficiale, attività, sede, distanza plausibile, citazioni, recapiti pubblici e stato annunci. Registra duplicati e falsi positivi; una riga per azienda non prova pertinenza.
- Verifica che aziende senza offerte rimangano, che sedi sconosciute siano distinte, che i portali siano solo risultati indicizzati e che nessuna offerta sia dichiarata attiva senza prova.
- Lascia bozze OFF nel pilota normale. Per provare ON usa dati fittizi, controlla `status=draft` e rivedi ogni frase. Nessun test contiene un trasporto di invio.
- Registra versioni, digest, modello, tempi, picco RAM/VRAM, query/pagine/retry, completezza delle evidenze e limiti riscontrati in un report privato. Pubblica solo statistiche anonime e fixture sintetiche.

## Stato della consegna

La verifica locale iniziale è registrata in `docs/milestones.md`. L'ambiente di sviluppo Windows non dispone di Docker o dei servizi LAN; un risultato locale offline non viene presentato come esecuzione end-to-end dell'installazione n8n reale.

La [CI 6353158](https://github.com/GianniGiuffo/JobHelper/actions/runs/39435030778) ha completato con successo tutti i quattro job: 68 test offline e i tre controlli container descritti sopra. Il pilota con Ollama e fonti web reali rimane distinto e richiede la configurazione locale.
