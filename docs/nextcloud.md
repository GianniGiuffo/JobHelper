# Nextcloud WebDAV opzionale

`NEXTCLOUD_ENABLED=false` per default. Nessun accesso ai file Nextcloud avviene durante l'upload normale o la ricerca. Per abilitare imposta `NEXTCLOUD_WEBDAV_URL` alla **sola cartella autorizzata**, ad esempio `https://cloud.example.org/remote.php/dav/files/utente/JobHunter`; la cartella deve già esistere. Crea una app password dedicata e monta `NEXTCLOUD_USER_FILE` e `NEXTCLOUD_APP_PASSWORD_FILE` come secret nell'adattatore.

Esempio overlay locale, file conservati sotto `secrets/`:

```yaml
services:
  hunter:
    environment:
      NEXTCLOUD_USER_FILE: /run/secrets/nextcloud_user
      NEXTCLOUD_APP_PASSWORD_FILE: /run/secrets/nextcloud_password
    secrets: [nextcloud_user, nextcloud_password]
secrets:
  nextcloud_user:
    file: ./secrets/nextcloud_user
  nextcloud_password:
    file: ./secrets/nextcloud_password
```

I file devono essere leggibili dall'utente container; mantieni privata la cartella sul server. Usa la stessa tecnica per Stirling. La credenziale n8n Header Auth serve solo a raggiungere l'adattatore, non è una password Nextcloud.

### Import di un CV

Il workflow `12-nextcloud-import` riceve, tramite Execute Sub-workflow:

```json
{"path":"cv-fittizio.pdf","parameters":{"profile_name":"CV da cartella autorizzata","city":"Torino","radius_km":30}}
```

Esegue GET del PDF e crea un job, poi avvia il runner senza attesa. Il CV di quell'import resta distinto dagli altri. Non è un file picker pubblico né una lista dell'intero account. Per un test in editor passa questo JSON da un nodo Edit Fields di un workflow temporaneo con un CV sintetico, collega Execute Sub-workflow e seleziona 12; non pubblicare il workflow di test con dati personali.

### Export, soltanto esplicito

Il workflow `14-nextcloud-export` riceve:

```json
{"run_id":"00000000-0000-4000-8000-000000000001","path":"report-nuovo.json","format":"json","confirm_export":true}
```

Sostituisci l'identificativo dimostrativo con uno esistente. Nessun workflow di ricerca richiama automaticamente l'export Nextcloud. Il server richiede `confirm_export=true`, invia soltanto il report CSV/JSON e usa `If-None-Match: *` per evitare sovrascritture. Un 412 indica un nome già esistente: scegline uno nuovo. I sottopercorsi devono già esistere; non sono creati automaticamente.

Non ci sono DELETE, sincronizzazione, modifica di file esistenti, contatti/calendari o Nextcloud Mail. Percorsi assoluti, traversal `..`, backslash e encoding percentuale sono rifiutati. Viene usata l'[API WebDAV ufficiale](https://docs.nextcloud.com/server/stable/developer_manual/client_apis/WebDAV/basic.html). Se pubblichi o condividi il report, valuta separatamente i dati professionali contenuti.
