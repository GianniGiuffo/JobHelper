# Workflow, credenziali e Forms

Importa tutti i 16 JSON in `workflows/`. Tutti sono inizialmente inattivi, senza credenziali incorporate o dati pinned. I workflow numerati 01–09 espongono un input `run_id` e, quando richiesto, `company_id`; il runner collega i moduli con Execute Sub-workflow. Il workflow 09 chiama un endpoint che controlla il flag prima di qualsiasi chiamata a Ollama.

### Import manuale, consigliato su n8n esistente

1. Nell'editor n8n usa **Import from File** per ciascun file. Registra gli ID effettivi mostrati nell'URL dei workflow.
2. Nei nodi **Execute Sub-workflow**, scegli il workflow corrispondente: nel form iniziale e nell'import Nextcloud scegli `runner`; nel runner scegli i moduli 01–09 rispettando i nomi. Lascia **Wait for Sub-Workflow Completion OFF** nei due avvii in background e ON nei moduli del runner. Non attivare salvataggio delle esecuzioni per facilitare il debug con CV reali.
3. Crea in n8n una credenziale **Header Auth**: Name `Authorization`, Value `Bearer ` seguito dal contenuto di `secrets/hunter_api_token`. Leggi il file in modo privato e non incollarlo nella chat, nei JSON o in un URL. Associa la credenziale a **tutti i nodi HTTP Request** dei workflow. I token non vengono passati nei dati tra workflow.
4. Verifica che l'URL interno sia raggiungibile dal container n8n. Il default è `http://hunter:8000`.
5. Form Trigger è configurato con **n8n User Auth**: un solo proprietario per questa installazione. Non viene aggiunto un sistema di account all'applicazione. Pulsante del primo form: **Avvia ricerca**. `options.path` definisce `ai-job-hunter`; secondo form `ai-job-hunter-risultati`. Il Form Ending mostra ID o consegna un file binario.
6. Esegui `11-healthcheck` con la credenziale interna. Prima della prova leggi i limiti e il risultato del controllo modello.
7. Pubblica solo `00-ui-start` e `10-status-results`. I sotto-workflow non hanno trigger pubblici e non richiedono pubblicazione separata per essere chiamati. Usa gli URL produzione mostrati da n8n, senza dedurli da host di esempio.

Gli ID negli export sono deterministici e unici per il progetto. L'import può preservarli o rimapparli secondo versione/modalità. Un import CLI su istanza isolata può usare:

```sh
docker compose -f compose.addons.yml -f compose.standalone.yml exec n8n n8n import:workflow --separate --input=/workflows
```

Non usare questo comando su workflow personalizzati senza backup: un ID uguale può essere aggiornato. Per rigenerare i riferimenti dopo un import manuale, crea un mapping sul modello `config/workflow-ids.json` e usa `python scripts/generate_workflows.py --ids mapping-locale.json --base-url http://hunter:8000`; poi importa gli export in un ambiente di prova. Non pubblicare mapping contenenti URL o ID personali.

### Data Tables facoltative

L'archivio autorevole è SQLite, scelta approvata per atomicità, deduplica e retention. Per vedere metadati nell'editor crea una Data Table con colonne `run_id` e `status` stringa, `companies_saved` e `queries_used` numero. Nel workflow `13-data-table-sync`, scegli quella tabella al posto di `SELECT_LOCAL_DATA_TABLE`. Richiamalo con `{ "run_id": "identificativo-valido" }`, oppure aggiungi un Execute Sub-workflow dopo `Concludi` nel runner. Ripetere l'upsert aggiorna il record per `run_id`.

Questa tabella non contiene CV né sostituisce il CSV/JSON. Se la abiliti, elimina anche i suoi metadati quando cancelli una ricerca: la retention SQLite non può cancellare automaticamente dati aggiunti manualmente a n8n.
