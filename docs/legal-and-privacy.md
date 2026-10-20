# Privacy e uso delle fonti

Il CV viene inviato dal browser al form n8n e poi all'adattatore privato; il testo estratto va esclusivamente all'Ollama configurato nella rete locale. Assicurati che endpoint e tag del modello siano realmente locali. Il sistema non dichiara assenza di traffico esterno: SearXNG interroga motori esterni, il fetch accede ai siti pubblici e Nominatim riceve località e indirizzi professionali aziendali.

Le query derivate dal CV sono costruite da termini del vocabolario professionale autorizzato. Nomi, email e telefoni del CV non vengono usati come query. I suggerimenti manuali sono analizzati dal modello locale, ma i termini delle query restano vincolati allo stesso vocabolario. Nessun dato del CV è inserito in un URL di stato o di download. Il `run_id` è un UUID e non sostituisce l'autenticazione.

### Accesso e conservazione

- Forms richiede autenticazione n8n; API interna con bearer token e nessuna porta pubblica per default. Usa LAN privata, Tailscale o reverse proxy HTTPS autenticato; non esporre un form anonimo su Internet.
- `.env`, secret, database, PDF e report personali sono esclusi da Git. I JSON non contengono credenziali locali, dati di esecuzione o CV. La CI controlla pattern di token e email personali riconoscibili; una scansione automatica non può garantire di riconoscere tutti i dati sensibili.
- `RETAIN_ORIGINAL_PDF=false`: il campo PDF viene svuotato dopo il parsing, o in caso di errore terminale/timeout. Prima del parsing il PDF queued deve esistere per poterlo elaborare. Con true resta fino alla retention/cancellazione.
- Il testo grezzo del CV non viene mantenuto dopo la chiamata di estrazione; il profilo professionale derivato, hash documento e risultati restano **30 giorni** (`RETENTION_DAYS`), compresi eventuali nomi del file/profilo scelti dall'utente. Non usare dati personali nei nomi se non necessari.
- Cache pubblica URL/robots: 24 ore; geocoding: 30 giorni. I dati eliminati da SQLite non sono automaticamente eliminati da backup, CSV scaricati, copie Nextcloud, proiezioni Data Tables, storage binario temporaneo o log dell'istanza n8n. Imposta retention coerente anche lì.
- `DELETE /runs/{run_id}`, con credenziale interna, elimina la ricerca e i suoi risultati quando non è running; attende la conclusione/timeout per un job in corso. SQLite usa secure_delete e checkpoint del WAL; questo non promette cancellazione forense su SSD o backup.
- Gli export disabilitano il salvataggio delle esecuzioni n8n; l'adattatore disabilita gli access log e non restituisce body HTTP o testo del CV negli errori pubblici. Valuta separatamente log di proxy, Docker e servizi opzionali. Non fare debug/pinning con CV reali nell'editor n8n.

### Fonti e recapiti professionali

Si leggono pagine pubbliche ufficiali e risultati indicizzati; nessun login LinkedIn/Indeed, automazione di profili privati, CAPTCHA bypass, scraping massivo o costruzione di indirizzi email. Robots è controllato prima del download; 401/403 e blocchi non vengono aggirati. Se robots non è disponibile in modo affidabile il sito non è letto. I siti possono imporre condizioni aggiuntive: la presenza online di un dato non equivale a permesso per qualsiasi riuso.

Si conservano fonte, citazione, data di controllo e livello di verifica. Un nominativo deve avere un ruolo professionale esplicito; un'email deve essere pubblicata nella citazione. Il modello può comunque classificare male un contenuto: revisiona nominativi e recapiti prima di usarli. Non vengono raccolti rubriche private o recapiti personali dedotti. Nessun risultato è una verifica legale dell'azienda o del rapporto di lavoro.

La [policy di Nominatim pubblico](https://operations.osmfoundation.org/policies/nominatim/) limita a 1 richiesta/s, richiede identificazione applicazione, cache e attribuzione, e vieta usi sistematici. Questa installazione lo usa per ricerche occasionali avviate dall'utilizzatore, con attesa minima di 1,1 s e cache; nessun monitoraggio pianificato. Se le ricerche diventano regolari o voluminose configura un provider dedicato. Non inviare indirizzi personali o materiale confidenziale. Attribuzione: © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), ODbL.

Il software non determina automaticamente la base giuridica di un trattamento o le condizioni per condividere liste di contatti. Prima di riutilizzi su larga scala, diffusione o usi professionali valuta il [testo GDPR](https://eur-lex.europa.eu/eli/reg/2016/679/oj) e le regole applicabili. La generazione di una bozza non autorizza l'invio. Il progetto non contiene client SMTP, integrazioni di invio o candidature automatiche.

### Contenuti non attendibili

PDF, pagine, snippet e output LLM sono dati non attendibili. Non vengono eseguiti comandi, script scelti dal modello o URL arbitrari proposti nei prompt. Gli URL pubblici sono validati su DNS/redirect e collegati a socket con IP fissato; indirizzi privati, riservati, multicast, loopback e metadata sono bloccati. Gli endpoint delle integrazioni LAN sono scelti dall'amministratore, non dalle pagine web.

Crawl4AI riceve HTML ripulito in modalità raw, senza browser processing, hook o estrazione LLM remota. Non si promette immunità completa alla prompt injection: schema, gate dei tool, citazioni e budget limitano gli effetti, mentre score e bozze restano proposte da revisionare.
