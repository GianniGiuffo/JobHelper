# OCR opzionale con Stirling PDF

`STIRLING_ENABLED=false` permette di usare tutti i PDF testuali senza Stirling. Il parser pypdf è eseguito in un processo separato, massimo 30 pagine, timeout 30 s; su Linux impone anche limiti CPU/memoria. L'euristica minima (80 caratteri e 50 lettere) può sbagliare su PDF malformati o rumorosi. L'estrazione semantica resta responsabilità del modello locale.

Se il testo è insufficiente, OFF produce `ocr_required_enable_stirling_or_upload_text_pdf`. Carica un PDF con testo selezionabile oppure abilita un'istanza Stirling autorizzata. Il sistema non interpreta una scansione vuota come un CV senza competenze.

Per abilitare:

1. Imposta `STIRLING_ENABLED=true`, `STIRLING_BASE_URL` privato e `STIRLING_OCR_LANGUAGES=ita,eng`.
2. Se necessaria, custodisci la chiave in un file privato e montalo con un overlay Compose sotto `/run/secrets/stirling_api_key`; imposta `STIRLING_API_KEY_FILE` al percorso montato. La chiave non va in workflow, prompt o `.env` pubblicabile. In questa implementazione la credenziale risiede nel secret store dell'adattatore, perché è l'adattatore a fare la chiamata.
3. Verifica `/v1/api-docs` dell'istanza. L'adattatore richiede che esponga `/api/v1/misc/ocr-pdf`; invia `fileInput`, `languages` ripetibili e `ocrType=skip-text`, header `X-API-KEY` se configurato, poi estrae nuovamente dal PDF restituito.

401 significa autenticazione da configurare; 402 richiede verifica dell'abilitazione API/piano della versione installata; endpoint assente, timeout o risultato ancora illeggibile sono errori espliciti. Non presumere che ogni distribuzione Stirling abiliti automazioni. Consulta la [documentazione API ufficiale](https://docs.stirlingpdf.com/API/) e l'OpenAPI dell'istanza concreta. La suite simula sia la modalità OFF sia la catena OpenAPI → OCR multipart → nuova estrazione; non dichiara collaudata la tua installazione.

Il PDF originale viene eliminato dal campo privato nel database al termine del parsing salvo `RETAIN_ORIGINAL_PDF=true`. Il risultato OCR non viene archiviato come nuovo documento né caricato su Nextcloud.
