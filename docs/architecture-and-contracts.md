# Architettura e contratti

n8n è l'orchestratore. Il servizio Python interno non esegue ricerche in background autonome: ciascun passo è invocato dai sotto-workflow n8n. Una sola istanza del processo ASGI (`--workers 1`), un solo job running, SQLite in WAL su volume locale. Non aumentare repliche o worker: per farlo servirebbero coordinamento e code diversi, fuori dal perimetro attuale.

### Percorso di una ricerca

`00-ui-start`: Form Trigger autenticato → HTTP multipart `/runs` → Execute Sub-workflow `runner` senza attesa → Form Ending con `run_id`. La conferma dipende solo dalla validazione e persistenza dell'upload e dall'avvio del runner, non dalle chiamate web/LLM. Un doppio upload identico con gli stessi parametri entro 60 secondi restituisce lo stesso ID. Nessuna chiamata lenta della pipeline tiene il lock dell'endpoint di creazione o delle letture di stato.

`runner`: acquisisce lo slot, con Wait di 5 secondi se occupato → moduli 01/02/03 → ciclo aziende 04/05/06/07/09/08 → conclusione. Non ci sono script arbitrari scelti dal modello o tool di invio. La singola chiamata al modulo 09 è sempre protetta dal flag nel servizio; OFF significa **zero chiamate all'agente B**.

| Workflow | Endpoint interno / contratto |
|---|---|
| 01 CV | `/stage/parse`, `run_id`: PDF processato in subprocess terminabile; schema Profile |
| 02 piano | `/stage/plan`: query scelte dall'agente entro vocabolario e budget; SearchPlan |
| 03 discovery | `/stage/discover`: SearXNG JSON, domini canonici e URL fonte |
| 04 azienda | `/stage/enrich`, `company_id`: pagine scelte dall'agente tra link letti, Facts con citazioni |
| 05 fit | `/stage/fit`: Fit con punteggio indicativo e fonti; fallback da verificare |
| 06 annunci | `/stage/openings`: sito già letto + snippet pubblici di portali, Openings |
| 07 contatti | `/stage/contacts`: Contacts professionali, campi controllati nella citazione |
| 08 salvataggio | `/stage/persist`: filtro geografico/fit, upsert per ricerca+azienda |
| 09 bozze | `/stage/draft`: flag OFF prima della chiamata, Draft locale |
| 10 consultazione | GET `/runs/{id}` oppure `/runs/{id}/export/{csv|json}` tramite Forms |
| 11 diagnostica | GET `/health`, controllo reachability/modelli/OpenAPI OCR |
| 12 Nextcloud import | POST `/runs/import`, `path`, `parameters`; poi runner asincrono |
| 13 Data Tables | GET stato e upsert di una proiezione locale, opzionale |
| 14 Nextcloud export | POST `/export/nextcloud`, conferma esplicita e nome file nuovo |

Tutti gli endpoint eccetto `/live` richiedono `Authorization: Bearer …`. Ogni step restituisce **solo** `{run_id, company_id, status}`. Gli oggetti dei modelli sono validati con `extra=forbid`; i contratti pubblicati in `schemas/` sono generati da quegli stessi modelli. Il modulo Draft può essere chiamato anche direttamente, ma il gate lato server resta effettivo.

### Persistenza e relazioni

`runs`: parametri, PDF temporaneo, hash CV/profilo specifico, piano, contatori e contesto per ogni azienda. `results`: chiave `(run_id, company_id)`, dati strutturati, offerte, contatti, fonti ed eventuale bozza. `cache`: pagine/robots a TTL e geocoding a 30 giorni, senza CV. Il `profile_id` è l'hash del PDF; due CV differenti non condividono profili. Il dominio canonico determina l'ID stabile dell'azienda attraverso ricerche distinte, ma ogni ricerca mantiene il proprio snapshot. Non si fondono gruppi aziendali basandosi solo sul nome. I sottodomini possono rappresentare aziende distinte: controllare manualmente i casi dubbi.

Stati supportati: `queued → running → completed / partial / failed`. `cancelled` non viene esposto perché non è implementato. Un watchdog controlla deadline e retention ogni 30 secondi quando il lock di un modulo è disponibile. Gli step sono idempotenti se completati; la persistenza è un upsert. Il budget è salvato prima delle richieste, comprese quelle fallite. In caso di crash di n8n il job running viene chiuso dal watchdog alla deadline. Per un job rimasto queued si può richiamare il runner con il suo ID; per uno terminato rilanciare un nuovo upload dopo la finestra di deduplica. Non c'è una ripresa trasparente a metà chiamata LLM.

Un errore in parse/piano interrompe la ricerca. Un errore di pagina, fit o contatti annota il fallimento e lascia proseguire le altre aziende. Il timeout complessivo chiude come partial se esistono risultati, altrimenti failed. `completed` indica che i passi previsti sono terminati, non che la ricerca è esaustiva o che le aziende sono adatte.

### Geografia, prove ed export

Il centro è la località inserita nel form. Sono geocodificati fino a tre indirizzi operativi aziendali citati dal sito; si usa quello più vicino. Haversine, **non distanza stradale**. Il geocoder può disambiguare male: label, fonte e coordinate restano nel JSON per revisione. Sedi non verificabili sono conservate con distanza nulla e ordinate dopo le altre. Il raggio non filtra gli annunci in modo indipendente: leggere la località di ogni annuncio.

Ogni fatto accettato deve avere citazione letterale presente nella pagina fornita. I contatti devono avere nome, ruolo ed email pubblicati nella stessa citazione quando valorizzati; nessuna email dedotta. Le citazioni non certificano che il sito sia autentico o aggiornato: risultati candidati, score e nomi richiedono revisione. Le pagine consumate nei prompt sono limitate a 2.500 caratteri ciascuna; informazioni oltre il limite possono essere ignorate.

CSV UTF-8 con BOM: una riga per azienda e campi multipli separati da ` | `. JSON: dettagli senza perdita di struttura, offerte, contatti e bozze eventuali. Celle potenzialmente interpretabili come formule sono prefissate con apostrofo. `application_status` parte da `da_valutare`; è modificabile manualmente nel CSV. L'applicazione non aggiorna stati di invio e non importa automaticamente le modifiche al CSV.

### Risorse e confini degli agenti

Default: 20 aziende, tetto installazione 50; 25 query totali (circa metà riservata alla discovery), 6 URL tentati per azienda compresi errori/cache hit, 30 minuti di runtime, 3 tentativi HTTP solo per rete/429/5xx, un solo tentativo di riparazione JSON. Richieste HTTP di retry e robots sono aggiuntive ai contatori pagine/query: il numero di fetch di rete non coincide con pagine lette. LLM e crawler non hanno strumenti shell, file di sistema, posta, credenziali interne o accesso arbitrario alla LAN.

Agente B: stesso modello o tag distinto tramite `OLLAMA_WRITING_MODEL`; prompt indipendente; solo aziende con fatti e score almeno `EMAIL_DRAFT_MIN_FIT` (60). `EMAIL_DRAFT_ENABLED=true` abilita la sola scrittura locale di subject/body, lingua, tailoring_facts, fonti e warnings. La bozza usa il profilo della ricerca, distingue offerta da candidatura spontanea ed è sempre `status=draft`. Una citazione valida non garantisce che il modello non abbia abbellito il testo: revisione manuale obbligata prima di copiarlo in un proprio client.
