# Diagnostica

Prima di un CV reale esegui `11-healthcheck`. La diagnostica controlla raggiungibilità, tag Ollama e presenza endpoint OCR se abilitato; non esegue ricerche web, non scarica modelli, non scrive su Nextcloud e non certifica prestazioni GPU. I contatori, gli stati e gli errori strutturati si leggono nel form risultati o nel JSON.

| Sintomo / codice | Controllo |
|---|---|
| Il form non è accessibile | Usa il Production URL di un workflow pubblicato; accedi come proprietario. Controlla proxy/cookie HTTPS e Form Trigger 2.6. |
| Credenziale mancante | Associa Header Auth ai nodi HTTP; `Authorization` deve avere `Bearer ` e il token interno. Non pubblicare il token negli export. |
| Sotto-workflow non trovato | Rimappa gli ID nei nodi Execute Sub-workflow dopo import; guarda `config/workflow-ids.json` come elenco dei nomi. |
| Host `hunter` non risolto | n8n e hunter devono condividere una rete/alias Docker; da n8n nativo usa loopback con overlay locale. |
| `service_unreachable_or_timeout` | Verifica URL di integrazione, DNS nel container, firewall LAN, PC Ollama acceso e tag caricato. Nessun uso implicito di localhost per il PC remoto. |
| SearXNG 403 | Abilita `search.formats: [html,json]` nell'istanza effettivamente usata. Il Compose già lo include. Alcuni motori possono essere non disponibili anche se SearXNG risponde. |
| `llm_invalid_json_after_repair` | Controlla modello, versione Ollama, JSON Schema e contesto. La riparazione avviene una sola volta. Prova un CV sintetico breve. |
| `no_safe_professional_query_terms_extend_vocabulary` | Estendi `config/search-vocabulary.txt` con termini professionali pertinenti e ricostruisci hunter. Non inserire nomi o recapiti. |
| `plan_has_no_safe_queries` | Il modello non ha rispettato allowed_terms; prova modello/prompt su fixture e registra il caso, senza inviare il CV al web. |
| `ocr_required_enable_stirling_or_upload_text_pdf` | PDF scansito/illeggibile: carica PDF testuale o configura OCR opzionale. |
| `service_http_401` / `402` OCR | Controlla chiave, OpenAPI, versione e abilitazione API Stirling. Nessun fallback cloud. |
| `ssrf_blocked` | URL o redirect risolve una rete non pubblica. Non disattivare il controllo per un'azienda; correggi la fonte o verifica manualmente. |
| `robots_disallowed` / `robots_unavailable_refused` | Il sito non consente o non permette di verificare l'accesso. Sarà conservata una scheda da verificare, senza forzare scraping. |
| `cross_origin_redirect_refused` | Redirect verso un altro host: controlla manualmente il dominio ufficiale. Il sistema non presume la sua policy robots. |
| `crawl4ai_extraction_failed` | Verifica token e versione 0.9.5; esegui lo smoke test raw descritto in `tests/README.md`. Pagine solo JavaScript possono non fornire prove. |
| `search_budget_exhausted` | Il budget totale comprende discovery e query annunci. Le altre aziende restano; il job può essere partial. Aumenta solo entro i limiti installazione e della fonte. |
| Job fermo `queued` | Può essere in attesa di un job running o essere rimasto senza runner dopo un riavvio. Richiama runner con quel `run_id` da un workflow temporaneo; claim evita duplicazioni. |
| Job `running` dopo stop n8n | Il watchdog chiude alla deadline; conserva risultati già salvati. Non è implementata la ripresa automatica a metà chiamata. |
| Distanza vuota | Nessun indirizzo operativo citato, geocoding assente/errore o centro non geocodificato. Non equivale a 0 km. |
| Nextcloud 412 | Export omonimo già esistente: scegli un nuovo nome. Nessuna sovrascrittura automatica. |
| Bozze assenti | Default OFF. Con ON servono fatti e score almeno `EMAIL_DRAFT_MIN_FIT`; i normali risultati non dipendono dal successo di una bozza. |

### Riproduzione offline

Esegui `python -m pytest -q`. Gli esempi sono fittizi, senza contatti reali. Per un bug allega stato/error code, versione e fixture sintetica. Non allegare database, `.env`, PDF reali o dump di esecuzioni. Per aggiornare gli schemi esegui `python -m scripts.generate_schemas`; per gli export `python scripts/generate_workflows.py`. Ogni modifica al generatore deve essere accompagnata dagli artefatti rigenerati.
