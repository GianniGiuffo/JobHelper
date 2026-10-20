# AI Job Hunter — Specifica funzionale e tecnica per Codex

**Versione:** 1.0 — 20 ottobre 2026  
**Lingua del progetto:** italiano (interfaccia e documentazione iniziali)  
**Stato:** specifica di sviluppo; non è ancora un'implementazione  
**Obiettivo:** realizzare un progetto self-hosted, modulare e distribuibile tramite GitHub per cercare aziende compatibili con uno o più curriculum, verificare opportunità lavorative e raccogliere contatti professionali, **senza inviare candidature**.

> **ISTRUZIONE PER CODEX.** Tratta questo documento come il brief di prodotto e il contratto di implementazione. Costruisci un MVP effettivamente eseguibile, non solo un'architettura teorica. Distingui i requisiti obbligatori dalle estensioni. Se una funzione dipende da credenziali, servizi non presenti o dati reali, implementa un adattatore configurabile e test con dati fittizi; non inventare configurazioni o risultati. Non rompere né sovrascrivere l'istanza n8n o i container già esistenti dell'utilizzatore.

---

## 1. Contesto e finalità

L'utilizzatore ha già un **server Debian con n8n in esecuzione**, oltre a diversi servizi self-hosted, fra cui **Nextcloud** e **Stirling PDF**. È interessato a sfruttare **un modello linguistico locale, possibilmente tramite Ollama**, per cercare opportunità lavorative nei dintorni di una località scelta. Il punto di partenza è **Torino**, ma la località e il raggio devono diventare configurabili.

L'idea non è un banale aggregatore di annunci: il sistema deve **partire dal contenuto del CV**, dedurre ruoli e competenze compatibili, scoprire aziende che potrebbero avere bisogno di quel profilo, analizzarne attività e tecnologie e cercare eventuali annunci già pubblicati. **Un'azienda adatta deve restare nei risultati anche in assenza di annunci**, perché l'utilizzatore intende inviare eventuali candidature spontanee personalmente.

Si cercano soprattutto opportunità junior o entry-level nelle aree evidenziate dai curriculum, ad esempio sviluppo software, C#/Unity, Blender/3D, informatica, assistenza hardware o altri settori che emergano dal CV. Questi sono **esempi, non filtri obbligatori**: il sistema non deve essere limitato al proprietario originale, né a una lista codificata di professioni.

### Cosa deve fare l'intelligenza artificiale

- Analizzare semanticamente un CV selezionato, senza dipendere da un unico modello di curriculum.
- Proporre categorie professionali, competenze, ruoli, sinonimi e **strategie di ricerca** coerenti con quel CV.
- Decidere quali query eseguire e quali aziende approfondire, entro **limiti controllati** di chiamate, pagine, tempi e costo computazionale.
- Interpretare contenuti estratti da siti e annunci, valutando la corrispondenza con il CV.
- Estrarre informazioni con **fonti verificabili** e identificare eventuali dati mancanti o incerti.
- In un secondo agente separato, già implementato ma **disabilitato per impostazione predefinita**, produrre bozze di email personalizzate. **Non inviarle mai**.

L'AI **non deve sostituire** i crawler, i motori di ricerca, gli strumenti PDF, la geolocalizzazione o il database: deve coordinarne intelligentemente l'uso e analizzare i risultati. Non è richiesto addestramento o fine-tuning nella prima fase.

---

## 2. Decisioni già prese (non chiedere nuovamente)

| Tema | Decisione |
|---|---|
| Distribuzione | Repository GitHub con file esportabili, configurazione e guida di installazione. |
| Multiutente | **Non necessario**: ciascuna persona esegue una propria installazione isolata sul proprio computer/server. Niente account multipli o permessi per condividere un'istanza. |
| n8n | **Orchestratore principale**, riutilizzando dove possibile un'istanza già installata. |
| Interfaccia iniziale | **n8n Forms**, senza scrivere una SPA o un front-end separato. |
| Avvio | Form compilabile con pulsante esplicito **«Avvia ricerca»**. |
| CV | Caricamento parametrico a ogni ricerca oppure selezione di un CV già importato, se la funzione è implementabile senza UI complessa. Più CV distinti nella stessa installazione. |
| Geografia | Località predefinita **Torino**, raggio in km configurabile, aziende ordinate quando possibile per prossimità verificata. |
| Annunci | Cercare annunci attivi e pagine «Lavora con noi», **ma conservare anche aziende prive di offerte trovate**. |
| Contatti | Email di candidatura/aziendale e, quando pubblicati, nominativi e contatti professionali di titolare, HR o responsabile tecnico. |
| Candidature | **Mai invio automatico**. L'utente sceglie personalmente se contattare l'azienda. |
| Secondo agente AI | **Da realizzare fin dall'inizio**, per generare automaticamente bozze quando abilitato; `EMAIL_DRAFT_ENABLED=false` per default. Nessun invio. |
| Integrazioni | Stirling PDF e Nextcloud **opzionali**, funzionanti se già disponibili; non requisiti bloccanti. |
| Privacy | Elaborazione del CV tramite LLM locale; i siti web esterni ricevono richieste di ricerca/navigazione, non l'intero CV. |
| Dimensione MVP | Prima prova con circa **20 aziende**, valore configurabile. |

### Esplicitamente fuori scope per il primo rilascio

- Gestione centralizzata di molti utenti su una sola installazione.
- Invio di email, autenticazione SMTP per candidarsi, campagne di massa e applicazione automatica agli annunci.
- Accessi automatizzati a LinkedIn, scraping di profili dietro login, CAPTCHA bypass o metodi contrari ai termini dei siti.
- Dashboard complessa con React/Vue, salvo futura decisione esplicita.
- Fine-tuning, addestramento da zero, uso necessario di API LLM a pagamento.
- Monitoraggio automatico continuo di offerte (possibile estensione successiva).

---

## 3. Esperienza utente: il sito iniziale

L'utente apre l'URL di **n8n Form Trigger** in modalità produzione, vede un modulo web e può configurare la ricerca senza aprire l'editor dei workflow.

### 3.1 Campi del modulo

| Campo visibile | Tipo suggerito | Predefinito | Requisito |
|---|---|---|---|
| Curriculum | Upload file PDF | — | Obbligatorio per la prima ricerca; riuso di profili opzionale in MVP. |
| Nome del profilo / CV | Testo | Derivato dal file | Utile per distinguere CV «Software» e CV «3D». |
| Città / località di partenza | Testo | Torino | Obbligatorio. |
| Raggio massimo | Numero, km | 30 | Obbligatorio; validare > 0 e limite configurabile. |
| Numero massimo di aziende | Numero | 20 | Obbligatorio; applicare un tetto sicuro configurabile. |
| Settori e professioni | Automatici / testo aggiuntivo | Automatici da CV | Consentire eventuali suggerimenti manuali o esclusioni. |
| Cerca anche aziende senza offerte | Checkbox | **Sì** | In pratica il valore predefinito deve sempre mantenerle. |
| Compatibilità minima | Numero 0–100 | 0 (nessuna esclusione) | Il punteggio è indicativo. |
| Preferenza lingua ricerca | Scelta | Italiano, con fallback inglese | Il CV può essere in italiano o in inglese. |
| Note / vincoli | Testo facoltativo | Vuoto | Esempio: «junior, no trasferte». |
| Generazione automatica bozze | **Non visibile / disabilitata in MVP** | **OFF** | Il relativo workflow esiste ma non viene richiamato. |

**Pulsante:** impostare `Button Label = Avvia ricerca` nel Form Trigger, senza simulare un bottone HTML. Titolo suggerito: **AI Job Hunter — Nuova ricerca**.

**Validazioni:** accettare solo file consentiti (MVP: PDF), dimensione massima configurabile, valori numerici dentro soglie sicure, località non vuota, input testuale sanitizzato. Nessun CV deve finire negli URL o nei log pubblici.

### 3.2 Dopo il clic: richiesta asincrona

La ricerca può richiedere minuti e non deve mantenere una singola richiesta web aperta fino alla fine.

1. Il Form Trigger riceve il CV e i parametri.
2. Un workflow breve valida i dati, memorizza un record `job` con `status=queued` e genera un `run_id` univoco.
3. Avvia il workflow di ricerca **in modo asincrono**, senza attenderne il completamento.
4. Mostra una schermata di conferma: «Ricerca avviata», identificativo e indicazioni per consultare i risultati.
5. Un workflow separato porta `queued → running → completed / partial / failed`, aggiornando contatori ed errori.

**MVP per vedere i risultati:** Data Tables di n8n + esportazione CSV/JSON, con un semplice **secondo form di consultazione** (per `run_id`) se possibile senza codice. Si può usare n8n Form Ending per un riepilogo o per un link a una pagina di stato. **Non presentare i n8n Forms come una dashboard interattiva completa**; la dashboard sofisticata resta futura.

Requisiti tecnici: evitare che un errore o un timeout nel processo di ricerca annulli il messaggio di conferma del form; evitare avvii doppi per un doppio clic; possibilità di riprendere o almeno rilanciare una ricerca senza duplicare aziende.

---

## 4. Architettura proposta

```text
Browser dell'utilizzatore
        |
        v
n8n Form Trigger  -- upload CV, Torino, raggio, limiti -- [Avvia ricerca]
        |
        v
n8n: validate + create job + start background workflow
        |                                 |
        |                                 v
        |                         Workflow AI Job Hunter
        |                                 |
        |                    +------------+-------------+
        |                    |            |             |
        |                CV parser    Discovery     Data storage
        |                    |            |             |
        |      +-------------+            |             +--> CSV/JSON
        |      |                          |
        v      v                          v
   Job status  Ollama <---- n8n AI agents / structured prompts
               |                  |             |
               |                SearXNG       Crawl4AI
               |                  |             |
               |                 Internet pubblico
               |
        [Agent B: email drafting] ← feature flag OFF per default
               |
          Soltanto bozze locali

Integrazioni facoltative per i documenti:
Nextcloud (WebDAV: importa CV)    Stirling PDF (OCR su PDF scansiti)
```

**Componenti richiesti per il funzionamento completo dell'MVP:**

- **n8n**: Forms, nodi AI e orchestrazione, nodi HTTP Request, esecuzione di sotto-workflow, Data Tables.
- **Ollama**: inference locale di modelli configurabili. Può essere sullo stesso host o su un altro dispositivo raggiungibile in rete privata.
- **SearXNG**: motore metasearch self-hosted con output JSON abilitato; oppure adapter alternativo per ricerche documentate e legittime.
- **Crawl4AI**: estrazione di pagine web tramite servizio HTTP self-hosted, con timeout e limite di pagine.

**Componenti facoltativi:**

- **Stirling PDF**: OCR/normalizzazione dei PDF quando l'estrazione nativa è insufficiente.
- **Nextcloud**: recupero/archiviazione di CV o report con WebDAV, solo se l'utente opta esplicitamente per questa integrazione.
- **NocoDB**, PostgreSQL e una UI dedicata: evoluzioni future, non dipendenze del primo rilascio.

### Scelta fondamentale: AI agente, workflow controllato

L'agente deve **scegliere concretamente query, categorie, priorità e approfondimenti**; non ridurlo a un classificatore che dà un punteggio su liste fisse. Tuttavia, **n8n controlla budget e permessi**: un modello non può decidere autonomamente di visitare migliaia di siti, eseguire script arbitrari, inviare email o leggere servizi privati non previsti. Ogni tool è esplicitamente consentito e i dati AI sono validati con schema.

---

## 5. Workflow separati e contratti tra moduli

Creare sotto-workflow n8n importabili e riusabili tramite **Execute Sub-workflow**, con I/O JSON dichiarati e test. I nomi sottostanti sono proposti; se una versione di n8n impone vincoli diversi, documentare l'adattamento.

| File | Modulo | Input essenziale | Output essenziale |
|---|---|---|---|
| `00-ui-start.json` | Form + validazione + creazione job + avvio asincrono | CV binario, parametri | `run_id`, conferma |
| `01-cv-parse.json` | Estrazione testo e profilo | PDF, lingua, OCR settings | `profile` con evidenze dal CV |
| `02-ai-plan.json` | **Agente A**: pianificazione query e settori | `profile`, area, budget | `search_plan` strutturato |
| `03-company-discovery.json` | SearXNG → URL/aziende candidate | `search_plan` | aziende candidate + fonti |
| `04-company-enrich.json` | Crawl4AI → attività, tecnologie, località | URL verificati | `company_facts` + prove |
| `05-ai-fit.json` | **Agente A**: abbinamento CV–azienda | `profile`, `company_facts` | fit, ruoli, motivazione |
| `06-job-openings.json` | Ricerca opportunità pubbliche | società, ruoli suggeriti | offerte e stato verifica |
| `07-professional-contacts.json` | Ricerca contatti professionali | società, fonti | contatti con fonte e confidenza |
| `08-persist-export.json` | Deduplica, archivio, esportazione | output validati | record + CSV/JSON |
| `09-email-drafts.json` | **Agente B**: bozze email personalizzate | CV, azienda, referente | bozza con oggetto/testo; **OFF** |
| `10-status-results.json` | Consultazione per `run_id` | identificativo ricerca | stato, sintesi, risultati |
| `11-healthcheck.json` | Test servizi e diagnostica | URL configurati | report per dipendenze |

Un eventuale `runner.json` orchestra i moduli da 01 a 08, con loop/batching sulle aziende. Distinguere ogni modulo dalla configurazione d'installazione. **Non tenere un singolo agente libero con accesso illimitato a tutto**.

### Stato e resilienza

- Gestire stati `queued`, `running`, `completed`, `partial`, `failed`, `cancelled` (l'ultimo solo se supportato davvero).
- Salvare successi parziali anche quando il sito di una singola azienda fallisce.
- Retry limitati con backoff per HTTP 429/5xx; registrare errori senza bloccare l'intera ricerca.
- Cache URL, hash CV e dettagli aziende, con ultima data di verifica per evitare richieste ripetute.
- Timeout per endpoint, limite richieste contemporanee, `max_pages_per_company`, `max_search_queries`, `max_total_runtime` configurabili.
- Output LLM a **JSON strutturato**, validato prima di persistere; errori di parsing gestiti con un solo tentativo correttivo e fallback sicuro.

---

## 6. Curriculum: ingestion, più profili e integrazione PDF

**Il CV caricato nella ricerca è il riferimento prioritario.** Lo stesso utente può usare CV differenti per ricerche differenti; non mescolare mai automaticamente competenze di un CV con un altro.

### Pipeline documentale

1. Ricevere il PDF dal Form Trigger come file binario, applicando limiti di dimensione.
2. Estrarre testo e metadati tramite il nodo n8n **Extract From File → Extract From PDF**.
3. Valutare se il testo è plausibile e sufficiente: presenza di parole, densità minima, assenza di pagine essenzialmente vuote o testo illeggibile. Documentare che l'euristica può sbagliare.
4. Se serve OCR e `STIRLING_ENABLED=true`, inviare il PDF a **Stirling PDF** tramite `HTTP Request`, ottenere un PDF ricercabile e ripetere l'estrazione nativa del testo.
5. Se l'OCR non è disponibile, restituire un errore chiaro o una richiesta di fornire un PDF testuale; **non interpretare un PDF vuoto come curriculum privo di competenze**.
6. Passare il testo all'LLM locale per estrarre dati in uno schema documentato.
7. Salvare identificativo, nome del profilo, hash documento, lingua, testo/profilo derivato e data; decidere con impostazione se conservare il PDF originale o cancellarlo dopo l'elaborazione.

Esempi di campi `profile`: `id`, `source_cv_name`, `language`, `skills`, `technologies`, `projects`, `experiences`, `education`, `languages`, `preferred_roles`, `adjacent_roles`, `seniority`, `constraints`, `evidence_spans`, `warnings`.

**Non inventare** titoli, esperienza lavorativa, competenze o anni di esperienza. Le proposte di ruoli adiacenti devono risultare come **inferenze** distinte dai dati espliciti del CV.

### Stirling PDF: adattatore opzionale

- Variabili configurabili: `STIRLING_ENABLED`, `STIRLING_BASE_URL`, credenziali tramite n8n e lingua OCR `ita`, `eng` o entrambe.
- L'API documentata espone l'OCR come `POST /api/v1/misc/ocr-pdf`, `multipart/form-data` con `fileInput`, `languages` ripetibili, eventuale `ocrType=skip-text`, risposta PDF processato.
- Quando è abilitata l'autenticazione, usare l'header `X-API-KEY` e custodire la chiave nelle credenziali di n8n, non in JSON pubblicati su GitHub.
- Verificare all'avvio che l'endpoint sia **effettivamente disponibile nella versione installata** (`/swagger-ui/index.html` o `/v1/api-docs`) e che il piano/la configurazione self-hosted consenta chiamate API di automazione. Gestire esplicitamente `401`, `402`, timeout e OCR non disponibile, senza rendere Stirling PDF un prerequisito.
- Non affidare a Stirling PDF la «comprensione semantica» del CV: fa parte della **preparazione e conversione del documento**, mentre Ollama lo interpreta.

### Nextcloud: adattatore opzionale

- `NEXTCLOUD_ENABLED=false` per default.
- Utilizzare **WebDAV** per scegliere/scaricare CV da una cartella autorizzata e, **solo su scelta esplicita**, caricare report/esportazioni.
- Endpoint di base: `/remote.php/dav/files/{user}/...` con utente e **app password** custoditi nelle credenziali n8n.
- L'utente deve poter lavorare **senza Nextcloud** con l'upload dal form.
- Non utilizzare contatti/calendario Nextcloud, non modificare o cancellare dati e non copiare automaticamente i CV su Nextcloud.

---

## 7. Agente A: ricerca intelligente di aziende

### 7.1 Creazione di una strategia dal CV

Da competenze, progetti, ruolo desiderato e seniority, Ollama produce:

- Categorie di aziende potenzialmente interessanti, incluse aziende che sviluppano software/strumenti internamente pur non essendo software house.
- Ruoli compatibili **diretti** e ruoli **adiacenti** motivati.
- Query in italiano e, dove utile, in inglese.
- Sinonimi, tecnologie, siti e segnali osservabili da cercare.
- Priorità tra ricerche, tenendo conto di prossimità e limitazione del numero di risultati.

Esempio indicativo per un CV con Unity/C#/Blender: cercare studi videogiochi, simulatori, digital twin, visualizzazione 3D, software C#, aziende con reparti IT; non assumere che tutte queste attività siano pertinenti senza verificarne il sito.

### 7.2 Discovery con SearXNG

- Chiamare il servizio self-hosted tramite `/search?q=...&format=json` (configurare il formato JSON nel suo `settings.yml`: se non abilitato, SearXNG può rispondere `403`).
- Ricercare **aziende**, non solo pagine di annunci.
- Estrarre URL ufficiali, nome, località e riferimenti; deduplicare domini e nomi normalizzati.
- Non includere CV completo o informazioni personali identificanti nelle query inviate ai motori di ricerca.
- Tenere traccia di query e URL fonte, distinguendo dominio aziendale da portali/directory.

### 7.3 Analisi delle aziende con Crawl4AI

Per ciascuna azienda promettente, leggere con limiti rigorosi solo le pagine rilevanti: home, «Chi siamo», «Servizi», «Prodotti», «Tecnologie», «Carriere/Lavora con noi», «Contatti», «Team». Estrarre testo o Markdown, riducendo rumore e script. Non esplorare indefinitamente l'intero sito.

L'AI deve rispondere a domande concrete:

- Che cosa fa l'azienda e in quale settore opera?
- Quali prodotti/servizi/tecnologie sono **effettivamente documentati**?
- Quale mansione potrebbe realisticamente valorizzare il CV? Con quali competenze e lacune?
- Dove si trova la **sede operativa utile**, distinguendola da sede legale e sedi remote?
- L'azienda sembra esistere ed essere pertinente? Ci sono fonti sufficienti per affermarlo?

### 7.4 Località, raggio, vicinanza

L'MVP deve già **accettare città e raggio**, non solo registrarli. Geocodificare località e sede dell'azienda tramite provider configurabile e conforme alle rispettive condizioni d'uso; preferire coordinate/cache già disponibili. Distanza calcolata inizialmente **in linea d'aria** (Haversine), etichettata in modo chiaro, e non confonderla con km stradali o tempi di viaggio.

- Default: centro della località **Torino**, raggio **30 km**, parametri modificabili.
- Quando una sede è nota, applicare il filtro geografico e ordinare per distanza crescente, **senza perdere la pertinenza professionale**.
- Quando sede o coordinate non sono verificabili, segnare `distance_km=null` e `location_status=unverified`, senza inventare una distanza; distinguere queste aziende in un elenco secondario da confermare.
- Gestire aziende con più sedi, remoto/ibrido e indirizzi fuori regione senza dare per scontato che un'annuncio sia riferito alla sede vicina.
- Permettere in futuro la sostituzione della distanza in linea d'aria con calcolo su strada, senza cambiare i workflow centrali.

### 7.5 Matching e punteggio

L'AI assegna `fit_score` 0–100 **indicativo, non scientifico**, con campi:

- `matched_skills`, `missing_skills`, `suggested_roles`, `fit_explanation`.
- `evidence_urls` e note sulle affermazioni senza evidenze.
- `confidence` e `fit_level` («alto/medio/basso/da verificare»), separati dal punteggio.

Non imporre un punteggio minimo che nasconda aziende utili per candidature spontanee, a meno che l'utente lo scelga. Su dati insufficienti assegnare «da verificare» invece di un punteggio arbitrariamente alto.

---

## 8. Ricerca annunci e contatti: distinguere i due casi

### 8.1 Offerte di lavoro

Per ogni azienda pertinente:

1. Controllare prima la pagina ufficiale **Careers / Lavora con noi**.
2. Cercare tramite SearXNG risultati pubblici indicizzati su **LinkedIn Jobs**, **Indeed** e altri portali, quando reperibili legittimamente.
3. Verificare collegamento all'azienda, ruolo, località, URL ufficiale o annuncio, ed eventuale **data di pubblicazione/scadenza** se pubblicata.
4. Non dichiarare un annuncio «attivo» solo perché una vecchia pagina è indicizzata: usare categorie `verified_open`, `possibly_open`, `closed`, `not_found`, `unknown/error` con motivazione e ultima verifica.
5. Anche con `not_found` la scheda aziendale resta salvata; quello è il caso di **candidatura spontanea**.

**LinkedIn/Indeed:** non automatizzare login, estrazione massiva di profili, aggiramento CAPTCHA o contenuti non accessibili. Memorizzare URL dei risultati pubblici e usare fonti ufficiali quando disponibili. Nessuna pretesa di copertura esaustiva di annunci non indicizzati.

### 8.2 Referenti e contatti aziendali

Cercare in ordine sensato: `careers@`, `jobs@` o email di recruiting **pubblicate**, modulo di candidatura, email generale `info@`, nominativi di HR, titolare/fondatore, responsabile tecnico o hiring manager, recapiti professionali diretti **solo quando esplicitamente pubblicati**.

Ogni contatto contiene: `person_name`, `role`, `public_business_email` (o null), `company_general_email`, `contact_page_url`, `source_url`, `verified_at`, `confidence`, `notes`. **Non generare o indovinare indirizzi email** da pattern tipo `nome.cognome@...` e non cercare recapiti personali non professionali. Se si trova soltanto il nome del titolare, conservarlo con la fonte e usare l'email aziendale generale, senza fingere di avere un recapito diretto.

La scheda finale deve far capire immediatamente: **«offerta pubblica trovata»** oppure **«potenziale candidatura spontanea»**, con tutte le sfumature di incertezza.

---

## 9. Agente B: bozze email (implementato ora, OFF in produzione)

**Requisito:** creare il workflow `09-email-drafts.json`, con prompt, schema d'output, chiamata Ollama, validazione, test e persistenza di bozze. **Disabilitarne ogni esecuzione nell'MVP reale tramite `EMAIL_DRAFT_ENABLED=false`**.

Quando verrà abilitato:

- Al termine dell'analisi di un'azienda, potrà **generare automaticamente una bozza**, ma soltanto per le aziende selezionate in base ai criteri configurabili.
- Input: il **CV specificamente selezionato**, fatti verificati sull'azienda, ruolo suggerito, eventuale offerta, referente pubblicamente noto, tono/lingua personalizzabili.
- Output: `subject`, `body_text`, `language`, `tailoring_facts`, `source_urls`, `warnings`, `status=draft`.
- Distinguere «risposta a offerta» da «candidatura spontanea».
- Non inventare progetti, risultati, certificazioni, ruoli, anni di esperienza o conoscenze personali con il referente.
- **Nessuna integrazione che invii email**, nessun SMTP, Gmail o Nextcloud Mail sender, nessun pulsante «invia» e nessuna schedulazione di invio. L'utilizzatore copia e modifica la bozza manualmente.
- Riutilizzare se possibile **lo stesso modello Ollama** con un prompt/agente separato, evitando di richiedere un secondo modello o una seconda GPU.

**Test obbligatorio:** con flag OFF non deve essere eseguita alcuna chiamata all'agente B; con flag ON e dati di prova l'agente produce una bozza salvata e **zero email spedite**.

---

## 10. Modelli AI locali e risorse

### Raccomandazione di partenza, non vincolo architetturale

- Provider LLM: **Ollama** via URL configurabile.
- Modello di test principale: **`qwen3.5:4b`**, disponibile tramite Ollama; usare l'esatto tag dopo aver verificato la versione locale. Il download quantizzato è dell'ordine di **3,3–4 GB**, ma **VRAM/RAM operativa e cache KV richiedono margine aggiuntivo**.
- Alternativa con meno memoria: `qwen3.5:2b`; possibile valutare altri modelli piccoli capaci di istruzioni, JSON e tool calling in italiano. Il progetto non deve dipendere da Qwen.
- L'utente può eseguire Ollama sul proprio server Debian (CPU, più lento) o su un **PC fisso con RTX 2070 Super 8 GB**, mentre n8n resta sul server. Il progetto deve ammettere entrambe le topologie.
- **Non presumere** che un contesto dichiarato molto grande possa essere caricato in 8 GB di VRAM: usare chunk di pagine, riduzione del testo e contesto configurato conservativamente.
- Benchmark/valutazioni prima di proclamare un modello «il migliore»: estrazione di 3 CV di test, pianificazione query, JSON valido, valutazione di 10 aziende, gestione di contenuti rumorosi, velocità e RAM/VRAM.

**Variabili:** `OLLAMA_BASE_URL`, `OLLAMA_RESEARCH_MODEL`, `OLLAMA_WRITING_MODEL`, `OLLAMA_TIMEOUT`, `OLLAMA_NUM_CTX` (se supportato dalle chiamate), limite di concorrenza. I due agenti possono puntare allo stesso tag di modello.

**Sicurezza:** se Ollama è su un'altra macchina, esporlo **solo sulla LAN privata o su Tailscale**, con firewall o proxy appropriato; non pubblicare liberamente `11434` su Internet. I CV vanno al modello locale, non a provider terzi.

---

## 11. Persistenza, deduplica ed esportazione

**MVP:** usare le **n8n Data Tables** per metadati strutturati e stato dei job; conservare i PDF in uno storage privato temporaneo o persistente secondo configurazione, senza inserirne i byte nel database tabellare. Le Data Tables hanno limiti di dimensione e non sostituiscono un DB relazionale per grandi volumi. Garantire un'esportazione **CSV e JSON** consultabile, e architettura sostituibile con SQLite/PostgreSQL in futuro.

### Entità minime

- `cv_profiles`: `profile_id`, nome, hash, lingua, data caricamento, profilo strutturato, riferimento al file.
- `search_runs`: `run_id`, `profile_id`, `params_json`, stato, contatori, inizio/fine, errore.
- `companies`: `company_id`, nome, dominio canonico, sito, descrizione, settore, sede, coordinate, fonti e ultimo controllo.
- `run_results`: chiave `(run_id, company_id)`, fit, motivazione, distanza, priorità e stato di analisi.
- `job_openings`: `opening_id`, `company_id`, titolo, posizione, URL, `opening_status`, date note, ultima verifica.
- `contacts`: `contact_id`, `company_id`, nome/ruolo/email, categoria e fonte.
- `email_drafts`: `draft_id`, `run_id`, `company_id`, testo e stato, **utilizzata soltanto a flag ON**.

Se un limite tecnico delle Data Tables rende scomoda questa normalizzazione, Codex può adottare una forma semplificata e documentata, **purché non perda la relazione CV → ricerca → azienda → fonti** e la portabilità di export.

### Identificazione e deduplica

- Aziende: dominio ufficiale normalizzato + denominazione verificata, con cautela verso gruppi aziendali e domini multipli.
- Offerte: URL canonico e/o identificatore offerta verificato.
- Contatti: `(azienda, nome, ruolo, email)` normalizzati e collegati alla fonte.
- Ricerche ripetute: non creare duplicati non necessari, aggiornare `last_checked` e preservare lo storico per `run_id`.

### Campi essenziali del CSV finale

`run_id, cv_profile, company_name, company_website, industry, city, distance_km, suggested_role, fit_score, fit_reason, vacancies_status, vacancy_title, vacancy_url, contact_name, contact_role, contact_email, general_email, contact_source_url, company_source_url, checked_at, application_status, notes`

Il campo `application_status` è modificabile manualmente (per esempio `da_valutare`, `da_contattare`, `contattata`, `colloquio`, `scartata`) e **non implica invio da parte dell'app**. Se le tabelle non offrono comodamente modifiche tramite modulo, documentare l'uso dell'editor n8n Data Tables o del CSV.

---

## 12. Formati d'interscambio: esempio di una ricerca

Configurazione in ingresso (schema illustrativo; Codex dovrà definirne e validarne una versione stabile):

```json
{
  "profile_id": "cv-software-001",
  "location": { "city": "Torino", "radius_km": 30, "distance_mode": "straight_line" },
  "max_companies": 20,
  "max_search_queries": 25,
  "max_pages_per_company": 6,
  "include_companies_without_jobs": true,
  "min_fit_score": 0,
  "language_priority": ["it", "en"],
  "career_preferences": { "level": "junior", "include_adjacent_roles": true },
  "features": { "stirling_ocr": false, "nextcloud": false, "email_drafts": false }
}
```

Esempio del record di risultato **fittizio**:

```json
{
  "run_id": "run-example-001",
  "company_id": "example-software",
  "company_name": "Azienda Dimostrativa S.r.l.",
  "website": "https://example.org",
  "location": { "city": "Torino", "distance_km": null, "verified": false },
  "suggested_roles": ["Junior C# developer"],
  "fit": {
    "score": 78,
    "confidence": "medium",
    "reason": "Ipotesi basata su competenze C# presenti nel CV e su un prodotto documentato nel sito.",
    "matched_skills": ["C#"],
    "missing_skills": []
  },
  "vacancies": { "status": "not_found", "items": [], "checked_at": "2026-10-20" },
  "contacts": {
    "general_email": null,
    "people": []
  },
  "source_urls": ["https://example.org"],
  "is_spontaneous_application_candidate": true,
  "notes": ["Dati dimostrativi: non corrispondono a un'azienda verificata"]
}
```

Codex deve usare **JSON Schema o equivalente**, normalizzare `null` e campi mancanti e testare l'output degli agenti. Non usare il punteggio 78 o i nomi dell'esempio come risultati reali.

---

## 13. Distribuzione su GitHub: repository riproducibile

Struttura raccomandata:

```text
ai-job-hunter/
├── README.md
├── LICENSE
├── .gitignore
├── .env.example
├── compose.standalone.yml        # installazione completa, senza servizi esterni
├── compose.addons.yml            # solo componenti necessari accanto a n8n esistente
├── config/
│   ├── searxng/settings.yml      # JSON abilitato; chiavi da env/secrets
│   └── defaults.example.json
├── workflows/
│   ├── 00-ui-start.json
│   ├── 01-cv-parse.json
│   ├── 02-ai-plan.json
│   ├── 03-company-discovery.json
│   ├── 04-company-enrich.json
│   ├── 05-ai-fit.json
│   ├── 06-job-openings.json
│   ├── 07-professional-contacts.json
│   ├── 08-persist-export.json
│   ├── 09-email-drafts.json
│   ├── 10-status-results.json
│   ├── 11-healthcheck.json
│   └── runner.json
├── prompts/
│   ├── extract-cv.md
│   ├── plan-search.md
│   ├── evaluate-company.md
│   ├── find-evidence.md
│   └── draft-email.md
├── schemas/
│   ├── profile.schema.json
│   ├── search-request.schema.json
│   ├── search-plan.schema.json
│   ├── company.schema.json
│   └── draft.schema.json
├── examples/
│   ├── fake-cv.txt
│   ├── fake-company.json
│   └── fake-output.csv
├── tests/
│   ├── fixtures/
│   ├── README.md
│   └── ...
└── docs/
    ├── installation-standalone.md
    ├── installation-existing-n8n.md
    ├── configuring-n8n-and-credentials.md
    ├── ollama-models-and-hardware.md
    ├── stirling-pdf.md
    ├── nextcloud.md
    ├── architecture-and-contracts.md
    ├── legal-and-privacy.md
    └── troubleshooting.md
```

### 13.1 Due installazioni documentate

**A. Standalone (per gli amici):** guida passo-passo per Docker/Compose che avvia una propria istanza di n8n + SearXNG + Crawl4AI e, se opportuno, Ollama. Indicare chiaramente requisiti RAM/CPU, storage, porte, volumi, prima configurazione di n8n e download del modello. Non assumere GPU NVIDIA su tutti i computer.

**B. Existing n8n (per l'utilizzatore attuale):** **non reinstallare n8n**; avviare soltanto i servizi mancanti, collegandoli alla stessa rete Docker o a endpoint LAN/Tailscale già esistenti. Spiegare come risolvere nomi host, porte e accesso a Ollama/Stirling/Nextcloud. Niente modifiche distruttive ai container correnti.

**Configurazione:** `.env.example` con soli valori fittizi; credenziali sempre in secret store/credenziali n8n. Fare un controllo iniziale degli endpoint via healthcheck.

### 13.2 Importazione workflow

- Consegnare file **JSON n8n realmente importabili**, con collegamenti tra nodi coerenti e versioni compatibili documentate; non semplici pseudoworkflow.
- Documentare la procedura di importazione manuale e collegamento delle **credenziali locali** e dei sotto-workflow (gli ID possono cambiare tra installazioni).
- Quando realistico, aggiungere script di bootstrap idempotenti che semplifichino installazione e verifiche, ma non obbligare a pubblicare API n8n.
- **Pulire ogni export:** nomi/ID di credenziali che rivelano informazioni, URL personali, token embedded, dati di esecuzione «pinned», esempi con CV veri. Nessun `.env` reale nel repository.
- Aggiungere un controllo in CI che rifiuti accidentalmente chiavi/token e dati personali evidenti.

### 13.3 Documentazione e licenze

- README con scopo, limiti, prerequisiti, quick start, screenshot soltanto se reali, flowchart, configurazione dell'MVP e contributi.
- Licenza del **codice originale del progetto** da scegliere e documentare; non attribuire a n8n una licenza MIT/Apache. n8n è distribuito con modello di licenza **fair-code** e l'eventuale futuro servizio commerciale condiviso richiede verifica delle condizioni vigenti.
- Elencare le licenze e le dipendenze principali di componenti e modelli, senza presumere che siano tutte identiche.

---

## 14. Privacy, conformità e sicurezza

Il progetto tratta CV, dati professionali e possibili nomi di referenti: implementare protezioni fin dall'MVP.

- Privilegiare l'accesso all'interfaccia tramite rete locale privata/Tailscale; **non esporre un form anonimo su Internet** senza autenticazione, rate limit, protezioni upload e analisi dei rischi.
- Usare l'autenticazione disponibile in n8n Form Trigger (ad esempio **n8n User Auth** o **Basic Auth**) secondo il contesto d'uso.
- Non pubblicare n8n editor, API di Ollama, Stirling PDF o Crawl4AI senza protezione.
- Validare input, dimensione dei file, URL e redirect. Bloccare SSRF (localhost, IP privati, metadata endpoints, redirect verso reti interne) quando si visitano **URL scoperti sul web**. Le URL delle integrazioni interne sono invece allowlist configurate dall'amministratore.
- Considerare **contenuto dei siti e dei PDF come dati non attendibili**: proteggersi da istruzioni di prompt injection, esfiltrazione o richieste di eseguire comandi.
- Non usare scraping aggressivo; rispettare termini dei servizi, robots/rate limit quando applicabili e condizioni dei provider di geocodifica.
- Non dichiarare la totale assenza di trasferimenti esterni: l'inference resta locale, ma ricerca web e scraping comportano connessioni verso Internet.
- Fare retention configurabile dei PDF originali, del testo estratto e dei log; evitare che i CV finiscano nei log completi delle esecuzioni n8n o in errori pubblicamente visibili.
- Conservare nominativi e recapiti **professionali pubblici** solo per la finalità dichiarata; fonti, date e possibilità di cancellazione/aggiornamento. Valutare GDPR e regole applicabili prima di condividere dati o utilizzare i contatti su larga scala.
- La scrittura delle bozze email non deve costituire consenso all'invio.

---

## 15. Requisiti non funzionali

- **Riproducibilità:** una persona con Docker e Ollama (o con URL LLM esistente) può avviare l'MVP seguendo il README, senza copiare credenziali altrui.
- **Modularità:** poter sostituire modello, tool di ricerca, crawler, OCR, database e motore geografico senza riscrivere il resto.
- **Basse risorse:** default conservativi per un server domestico con ~16 GB RAM già impegnata da altri servizi; niente crawler altamente paralleli per default. Permettere Ollama esterno.
- **Trasparenza:** ogni affermazione su offerte, azienda e contatti ha URL, data e livello di verifica.
- **Osservabilità:** healthcheck, progresso, contatori aziende esaminate, HTTP retries, fallimenti, durata e versioni dei componenti; non loggare il CV integrale.
- **Resilienza:** una singola azienda con sito bloccato o down non blocca tutte le altre; conservare progressi parziali.
- **Testabilità:** fixture e fake API per testare la logica senza contattare siti reali o usare dati privati.
- **Portabilità:** esportazione CSV/JSON con encoding UTF-8 e campi documentati.

---

## 16. Casi di test e criteri di accettazione

### Test funzionali

1. **Form e bottone:** la pagina n8n espone upload PDF, Torino come default, raggio modificabile e pulsante con etichetta **«Avvia ricerca»**.
2. **Profili diversi:** caricando due CV fittizi distinti, l'agente produce piani di ricerca differenti e le rispettive ricerche restano legate al CV scelto.
3. **PDF testuale:** estrae il contenuto senza passare obbligatoriamente da Stirling.
4. **PDF scansito:** con Stirling configurato tenta OCR e poi estrae il testo; con Stirling disattivo presenta un errore comprensibile, senza inventare contenuti.
5. **Geografia:** 30 km da Torino e 50 km da un'altra città modificano l'insieme filtrato/sortato; le aziende senza coordinate non ottengono distanze inventate.
6. **AI nella discovery:** le query dipendono realmente dalle competenze CV e non sono una lista hardcoded uguale per tutti.
7. **Azienda senza offerte:** compare nel CSV e nell'archivio come possibile candidatura spontanea, non viene esclusa.
8. **Offerta con prova:** l'output contiene URL verificabile e stato/data affidabili; se non è possibile verificare, usa stato incerto.
9. **Contatto non verificato:** il sistema non crea email o nomi fittizi; salva `null` e fonte/nota.
10. **Email OFF:** nessuna chiamata agente B, nessuna bozza reale in ricerca normale e nessun invio.
11. **Email ON nei test:** su fixture crea oggetto e testo di email in stato `draft`, **senza spedizione**.
12. **Servizi opzionali OFF:** Nextcloud e Stirling non sono necessari per elaborare un PDF testuale.
13. **Errore di scraping:** un `403`, `429` o sito offline produce un risultato parziale/errore annotato, non fallimento globale.
14. **Ricerca asincrona:** la schermata di conferma compare dopo l'avvio del job e non aspetta la scansione completa.
15. **Doppio avvio e deduplica:** nessuna duplicazione massiva di record per stessa azienda/URL.
16. **Installazione pulita:** JSON importabili e con credenziali rimappabili; nessun segreto presente nel repository.
17. **Esportazione:** CSV/JSON corretti e contenenti azienda, sito, ruolo, contatti, stato offerte, URL fonti, punteggio, distanza e `run_id`.

### Prova pilota non distruttiva

Eseguire una ricerca di massimo **20 aziende nell'area di Torino** con CV autorizzato e controllare manualmente su un sottoinsieme la correttezza di aziende, offerte, referenti e valutazioni. **Non considerare un job «riuscito» soltanto perché sono state generate 20 righe**: misurare pertinenza reale, prove disponibili, duplicati e falsi positivi. Un test live richiede che l'utente configuri i servizi e autorizzi l'uso del suo CV.

---

## 17. Fasi di sviluppo richieste a Codex

### Fase 0 — Audit tecnico, senza modifiche distruttive

- Controllare versione n8n, node supportati, modalità d'installazione e indirizzi dei servizi **solo se l'ambiente è accessibile**.
- Verificare i contratti API correnti per n8n, Ollama, SearXNG, Crawl4AI e Stirling PDF, preferendo documentazione ufficiale e immagini Docker versionate.
- Evidenziare eventuali incompatibilità e scegliere adattamenti semplici. Non inventare configurazioni della macchina né assumere accesso ai servizi personali.

### Fase 1 — MVP completo e dimostrabile

- Repository e configurazione esempi.
- Form n8n con pulsante, input validati, job asincrono e ID ricerca.
- Estrazione CV PDF testuale, agente A, SearXNG, Crawl4AI, matching, annunci, contatti e salvataggio.
- Una vista/consultazione di stato semplice, Data Tables, export CSV/JSON.
- Integrazioni facoltative Stirling PDF e Nextcloud con modalità OFF.
- Workflow agente B **interamente implementato ma disattivato**, con test offline.
- Documentazione per n8n già presente e installazione standalone.

### Fase 2 — Robustezza e qualità

- Test end-to-end con mock, deduplica, geocodifica con cache, gestione retry, error handling, controllo budget e privacy.
- Test su 20 aziende con revisione manuale, benchmark del modello locale, ottimizzazione memoria.

### Fase 3 — Estensioni da valutare, non avviare senza richiesta

- Dashboard completa separata da n8n, visualizzazione dettagliata progressi, storico più ricco, database relazionale.
- Ricerche programmate, notifiche nuovi annunci, distanza stradale, selezione/attivazione bozze email da UI.
- Eventuale versione multiutente centralizzata, distinta dal semplice software GitHub installabile localmente.

---

## 18. Deliverable obbligatori (Definition of Done)

Codex deve consegnare **file reali** e verificabili, non soltanto spiegazioni:

1. Repo popolato con README, guida, esempio di configurazione e istruzioni di avvio.
2. Workflow **validi e importabili** in n8n, con ID e credenziali da associare esplicitamente dopo l'import.
3. Docker Compose **standalone** e **addons per n8n già esistente**, o alternative motivate quando Compose non è adatto.
4. Prompt versionati e schema JSON per profili, piani, aziende e email.
5. Procedura guidata per usare Ollama ed eventualmente usare un host remoto privato.
6. Form n8n con bottone **Avvia ricerca**, esecuzione asincrona, archivio ed esportazione dati.
7. **Agente A operativo**; **agente B sviluppato ma OFF**, senza meccanismi d'invio.
8. Connettori Stirling PDF e Nextcloud opzionali, con test e messaggi di errore utili.
9. Test con fixture, istruzioni per eseguirli e limiti noti.
10. Nessun dato personale, token, credenziale o risultato inventato spacciato per reale.

**Modalità di lavoro richiesta a Codex:** implementare una fase alla volta, far partire i test, documentare ciò che funziona realmente e ciò che richiede configurazione locale. Se una funzione risulta impossibile senza codice o senza un servizio esterno, proporre la **minima alternativa compatibile** con l'architettura invece di aggiungere subito un'app separata complessa.

---

## 19. Riferimenti ufficiali per l'implementazione (verificati il 20/10/2026)

- **n8n Form Trigger, upload e «Button Label»:** https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.formtrigger/
- **n8n Form / Form Ending:** https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.form/
- **n8n Extract From File (PDF):** https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.extractfromfile/
- **n8n Data Tables:** https://docs.n8n.io/build/work-with-data/data-tables/
- **n8n import/export JSON e avvertenze credenziali:** https://docs.n8n.io/build/manage-workflows/export-and-import/
- **SearXNG API JSON:** https://docs.searxng.org/dev/search_api.html
- **SearXNG installazione/configurazione:** https://docs.searxng.org/admin/installation-searxng.html
- **Crawl4AI self-hosted/API:** https://docs.crawl4ai.com/core/self-hosting/
- **Stirling PDF API, OCR, auth e processing allowance:** https://docs.stirlingpdf.com/API/
- **Stirling PDF tool availability:** https://docs.stirlingpdf.com/Server/Customisation/Features-and-Endpoints/
- **Nextcloud WebDAV:** https://docs.nextcloud.com/server/stable/developer_manual/client_apis/WebDAV/basic.html
- **Modelli Ollama Qwen 3.5:** https://ollama.com/library/qwen3.5

**Nota:** API, feature, licenze e versioni possono cambiare. Il codice deve bloccare versioni/testarle e non presumere che ogni container o modello abbia le stesse capacità di un altro.

---

## 20. Brief sintetico da dare a Codex

> Sviluppa «AI Job Hunter», applicazione self-hosted per singolo utilizzatore **per installazione**, con n8n come orchestratore e **n8n Forms come sito iniziale**. L'utente carica un CV PDF, sceglie località (Torino di default), raggio in km, limiti di ricerca e clicca **«Avvia ricerca»**. Un agente locale su Ollama analizza il CV, pianifica query e scopre aziende tramite SearXNG, legge siti con Crawl4AI, valuta pertinenza e distanza, cerca annunci pubblici su siti ufficiali e risultati indicizzati di LinkedIn/Indeed, poi raccoglie email e nominativi professionali pubblici e salva risultati con fonti. **Anche le aziende senza annunci restano nei risultati.** La ricerca è asincrona con stato e CSV/JSON esportabili. Supporta facoltativamente Stirling PDF per OCR e Nextcloud per import/export via WebDAV; deve funzionare anche senza questi servizi. Predisponi un **secondo agente per bozze email completamente implementato ma disabilitato con `EMAIL_DRAFT_ENABLED=false`**. **Non inviare mai candidature o email.** Pubblica in GitHub workflow JSON importabili, Compose per installazioni autonome e per chi ha già n8n, configurazioni esempio, prompt, schemi, documentazione e test. Rispetta privacy, uso legittimo delle fonti e risorse di un server domestico. Procedi per milestone verificabili senza introdurre fin d'ora multiutenza o una dashboard front-end separata.
