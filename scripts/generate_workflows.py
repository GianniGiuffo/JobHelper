"""Genera gli export n8n, senza segreti, dati pinned o ID di credenziali."""
import argparse
import json
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parents[1]
IDS = {name: "ajh" + uuid.uuid5(uuid.NAMESPACE_URL, "ai-job-hunter/" + name).hex[:13] for name in (
    "00-ui-start", "01-cv-parse", "02-ai-plan", "03-company-discovery", "04-company-enrich", "05-ai-fit",
    "06-job-openings", "07-professional-contacts", "08-persist-export", "09-email-drafts", "10-status-results",
    "11-healthcheck", "runner", "12-nextcloud-import", "13-data-table-sync", "14-nextcloud-export")}


def node(name, kind, params, version=1, x=0, y=0):
    return {"id": str(uuid.uuid5(uuid.NAMESPACE_URL, name+kind)), "name": name,
            "type": "n8n-nodes-base."+kind, "typeVersion": version, "position": [x, y], "parameters": params}


def trigger():
    return node("Input", "executeWorkflowTrigger", {"inputSource": "passthrough"}, 1.1)


def http(name, path, method="POST", body=True):
    params = {"method": method, "url": BASE+path, "authentication": "genericCredentialType",
              "genericAuthType": "httpHeaderAuth", "options": {"timeout": 1900000}}
    if body:
        params.update({"sendBody": True, "specifyBody": "json", "jsonBody": "={{ { run_id: $json.run_id, ...($json.company_id ? {company_id: $json.company_id} : {}) } }}"})
    return node(name, "httpRequest", params, 4.2)


def execute(name, target, wait=True):
    return node(name, "executeWorkflow", {"source": "database", "workflowId": {"__rl": True, "value": IDS[target], "mode": "id"},
                  "mode": "once", "options": {"waitForSubWorkflow": wait}}, 1.3)


def condition(name, field):
    return node(name, "if", {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
        "conditions": [{"id": "check", "leftValue": "={{ $json."+field+" }}", "rightValue": True,
                       "operator": {"type": "boolean", "operation": "true", "singleValue": True}}], "combinator": "and"}, "options": {}}, 2.2)


def form(title, slug, fields, button):
    result = node("Modulo", "formTrigger", {"authentication": "n8nUserAuth", "formTitle": title,
        "formDescription": "Installazione personale. Nessun invio di email o candidature. I siti senza offerte restano nei risultati. Geocodifica © OpenStreetMap contributors (ODbL): https://www.openstreetmap.org/copyright",
        "formFields": {"values": fields}, "responseMode": "lastNode",
        "options": {"path": slug, "buttonLabel": button, "includeUserInOutput": False}}, 2.6)
    result["webhookId"] = str(uuid.uuid5(uuid.NAMESPACE_URL, slug))
    return result


def field(name, label, kind="text", default=None, required=True, **other):
    result = {"fieldName": name, "fieldLabel": label, "fieldType": kind, "requiredField": required, **other}
    if default is not None:
        result["defaultValue"] = str(default)
    return result


def ending(name, message):
    result = node(name, "form", {"operation": "completion", "respondWith": "text",
              "completionTitle": name, "completionMessage": message, "options": {}}, 2.5)
    result["webhookId"] = str(uuid.uuid5(uuid.NAMESPACE_URL, name))
    return result


def write(name, nodes, edges=None):
    connections = {}
    edges = edges if edges is not None else [(a["name"], b["name"], 0) for a, b in zip(nodes, nodes[1:])]
    for source, dest, output in edges:
        outputs = connections.setdefault(source, {"main": []})["main"]
        while len(outputs) <= output:
            outputs.append([])
        outputs[output].append({"node": dest, "type": "main", "index": 0})
    for i, n in enumerate(nodes):
        n["position"] = [240*(i % 7), 220*(i // 7)]
    payload = {"id": IDS[name], "name": "AI Job Hunter / "+name, "active": False, "nodes": nodes,
               "connections": connections, "settings": {"executionOrder": "v1", "saveDataSuccessExecution": "none",
                   "saveDataErrorExecution": "none", "saveExecutionProgress": False, "saveManualExecutions": False,
                   "executionTimeout": 7200, "timezone": "Europe/Rome"}, "pinData": {}}
    (ROOT / "workflows" / (name+".json")).write_text(json.dumps(payload, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def generate():
    (ROOT / "workflows").mkdir(exist_ok=True)
    modules = {"01-cv-parse": "parse", "02-ai-plan": "plan", "03-company-discovery": "discover",
               "04-company-enrich": "enrich", "05-ai-fit": "fit", "06-job-openings": "openings",
               "07-professional-contacts": "contacts", "08-persist-export": "persist", "09-email-drafts": "draft"}
    for name, stage in modules.items():
        write(name, [trigger(), http("Esegui "+stage, "/stage/"+stage)])

    fields = [field("cv", "Curriculum PDF", "file", acceptFileTypes=".pdf", multipleFiles=False),
              field("profile_name", "Nome del profilo / CV", default="CV"), field("city", "Città / località", default="Torino"),
              field("radius_km", "Raggio massimo (km in linea d'aria)", "number", 30),
              field("max_companies", "Numero massimo di aziende", "number", 20),
              field("max_search_queries", "Limite query totali", "number", 25),
              field("max_pages_per_company", "Pagine per azienda", "number", 6),
              field("min_fit_score", "Compatibilità minima (0–100)", "number", 0),
              field("language", "Lingua ricerca", "dropdown", "it", fieldOptions={"values": [{"option": "it"}, {"option": "en"}]}),
              field("sectors", "Suggerimenti settori / esclusioni", required=False),
              field("notes", "Note e vincoli", "textarea", required=False)]
    start = form("AI Job Hunter — Nuova ricerca", "ai-job-hunter", fields, "Avvia ricerca")
    create = http("Crea ricerca", "/runs", body=False)
    keys = [f["fieldName"] for f in fields if f["fieldName"] != "cv"]
    expr = "={{ JSON.stringify({" + ", ".join(k+": "+("Number($json."+k+")" if k in ("radius_km", "max_companies", "max_search_queries", "max_pages_per_company", "min_fit_score") else "$json."+k+" || ''") for k in keys) + "}) }}"
    create["parameters"].update({"sendBody": True, "contentType": "multipart-form-data", "bodyParameters": {"parameters": [
        {"parameterType": "formBinaryData", "name": "file", "inputDataFieldName": "cv"},
        {"name": "parameters", "value": expr}]}, "options": {"timeout": 30000}})
    write("00-ui-start", [start, create, execute("Avvia in background", "runner", False),
          ending("Ricerca avviata", "={{ 'Identificativo: ' + $json.run_id + '<br>Consulta il form ai-job-hunter-risultati per stato e download CSV/JSON. Nessuna email verrà inviata.' }}")])

    calls = [execute("CV", "01-cv-parse"), execute("Piano", "02-ai-plan"), execute("Discovery", "03-company-discovery")]
    company_calls = [execute("Azienda", "04-company-enrich"), execute("Compatibilità", "05-ai-fit"),
                     execute("Annunci", "06-job-openings"), execute("Contatti", "07-professional-contacts"),
                     execute("Bozze solo se abilitate", "09-email-drafts"), execute("Salva risultato", "08-persist-export")]
    nodes = [trigger(), http("Acquisisci slot", "/claim"), condition("Slot disponibile", "ready"),
             condition("In attesa", "busy"), node("Attendi", "wait", {"amount": 5, "unit": "seconds"}, 1.1),
             *calls, http("Prossima azienda", "/next"), condition("Azienda presente", "has_company"),
             *company_calls, http("Concludi", "/finish")]
    edges = [("Input", "Acquisisci slot", 0), ("Acquisisci slot", "Slot disponibile", 0),
             ("Slot disponibile", "CV", 0), ("Slot disponibile", "In attesa", 1),
             ("In attesa", "Attendi", 0), ("Attendi", "Acquisisci slot", 0),
             ("CV", "Piano", 0), ("Piano", "Discovery", 0), ("Discovery", "Prossima azienda", 0),
             ("Prossima azienda", "Azienda presente", 0), ("Azienda presente", "Azienda", 0),
             ("Azienda presente", "Concludi", 1)]
    edges += [(a["name"], b["name"], 0) for a, b in zip(company_calls, company_calls[1:])]
    edges += [(company_calls[-1]["name"], "Prossima azienda", 0)]
    write("runner", nodes, edges)

    f = form("AI Job Hunter — Stato e risultati", "ai-job-hunter-risultati", [field("run_id", "Identificativo ricerca"),
          field("format", "Visualizzazione", "dropdown", "stato", fieldOptions={"values": [
              {"option": "stato"}, {"option": "csv"}, {"option": "json"}]})], "Consulta / scarica")
    route = condition("Solo stato", "is_status")
    route["parameters"]["conditions"]["conditions"][0]["leftValue"] = "={{ $json.format === 'stato' }}"
    stat = http("Leggi stato", "/runs/{{ $json.run_id }}", "GET", False)
    stat["parameters"]["url"] = "="+stat["parameters"]["url"]
    download = http("Scarica export", "/runs/{{ $json.run_id }}/export/{{ $json.format }}", "GET", False)
    download["parameters"]["url"] = "="+download["parameters"]["url"]
    download["parameters"]["options"] = {"response": {"response": {"responseFormat": "file", "outputPropertyName": "data"}}}
    message = ending("Stato ricerca", "={{ JSON.stringify($json).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') }}")
    binary = ending("Export risultati", "Esportazione locale. Nessuna candidatura inviata.")
    binary["parameters"].update({"respondWith": "returnBinary", "inputDataFieldName": "data"})
    write("10-status-results", [f, route, stat, message, download, binary], [
        ("Modulo", "Solo stato", 0), ("Solo stato", "Leggi stato", 0), ("Leggi stato", "Stato ricerca", 0),
        ("Solo stato", "Scarica export", 1), ("Scarica export", "Export risultati", 0)])
    write("11-healthcheck", [node("Avvio manuale", "manualTrigger", {}), http("Diagnostica", "/health", "GET", False)])
    imp = http("Importa CV autorizzato", "/runs/import")
    imp["parameters"]["jsonBody"] = "={{ {path: $json.path, parameters: $json.parameters || {}} }}"
    write("12-nextcloud-import", [trigger(), imp, execute("Avvia in background", "runner", False)])
    exp = http("Esporta report autorizzato", "/export/nextcloud")
    exp["parameters"]["jsonBody"] = "={{ {run_id: $json.run_id, path: $json.path, format: $json.format || 'json', confirm_export: $json.confirm_export === true} }}"
    write("14-nextcloud-export", [trigger(), exp])
    # Optional projection: after creating the Data Table, select its ID locally.
    sync = node("Upsert metadati", "dataTable", {"resource": "row", "operation": "upsert",
        "dataTableId": {"__rl": True, "value": "SELECT_LOCAL_DATA_TABLE", "mode": "id"},
        "matchType": "allConditions", "filters": {"conditions": [{"keyName": "run_id", "condition": "eq", "keyValue": "={{ $json.run_id }}"}]},
        "columns": {"mappingMode": "defineBelow", "value": {"run_id": "={{ $json.run_id }}", "status": "={{ $json.status }}",
                     "companies_saved": "={{ $json.companies_saved }}", "queries_used": "={{ $json.queries_used }}"},
                    "matchingColumns": [], "schema": [
                        {"id": n, "displayName": n, "required": False, "defaultMatch": False, "display": True,
                         "type": "number" if n in ("companies_saved", "queries_used") else "string", "readOnly": False, "removed": False}
                        for n in ("run_id", "status", "companies_saved", "queries_used")],
                    "attemptToConvertTypes": False, "convertFieldsToString": False}, "options": {}}, 1)
    stat2 = http("Leggi stato", "/runs/{{ $json.run_id }}", "GET", False)
    stat2["parameters"]["url"] = "=" + stat2["parameters"]["url"]
    write("13-data-table-sync", [trigger(), stat2, sync])
    (ROOT / "config/workflow-ids.json").write_text(json.dumps(IDS, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://hunter:8000")
    parser.add_argument("--ids", type=Path, help="Mapping di nomi workflow a ID reali dopo import manuale")
    args = parser.parse_args()
    BASE = args.base_url.rstrip("/")
    if args.ids:
        IDS.update(json.loads(args.ids.read_text(encoding="utf-8")))
    generate()
