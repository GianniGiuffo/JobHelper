import csv
import io
import json

CSV_FIELDS = "run_id,cv_profile,company_name,company_website,industry,city,distance_km,suggested_role,fit_score,fit_reason,vacancies_status,vacancy_title,vacancy_url,contact_name,contact_role,contact_email,general_email,contact_source_url,company_source_url,checked_at,application_status,notes".split(",")


def safe_cell(value):
    value = "" if value is None else str(value)
    # Excel/LibreOffice formula injection, including leading whitespace/control characters.
    if value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def export(store, run_id, fmt):
    run = store.get(run_id)
    results = store.results(run_id)
    if fmt == "json":
        payload = {**store.summary(run_id), "parameters": run["data"]["params"],
                   "profile_id": run["data"].get("profile_id"), "results": results,
                   "origin_geocoding": run["data"].get("origin", {}),
                   "geocoding_attribution": "© OpenStreetMap contributors, ODbL; https://www.openstreetmap.org/copyright",
                   "excluded": [{"company_id": cid, "reason": ctx["excluded"]} for cid, ctx in
                       run["data"]["companies"].items() if ctx.get("excluded")]}
        return json.dumps(payload, ensure_ascii=False, indent=2).encode(), "application/json"
    if fmt != "csv":
        raise ValueError("Formato non supportato")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, CSV_FIELDS)
    writer.writeheader()
    for company in results:
        fit = company.get("fit") or {}
        vacancies = company.get("vacancies", {})
        openings = vacancies.get("items", [])
        contacts = company.get("contacts", [])
        # One row per company; structured detail remains lossless in JSON.
        row = dict(zip(CSV_FIELDS, [
            run_id, run["data"]["params"]["profile_name"], company["company_name"], company["website"],
            company.get("industry"), company["location"].get("city"), company["location"].get("distance_km"),
            " | ".join(fit.get("suggested_roles", [])), fit.get("score"), fit.get("reason"), vacancies.get("status"),
            " | ".join(o["title"] for o in openings), " | ".join(o["source_url"] for o in openings),
            " | ".join(c["person_name"] for c in contacts if c.get("person_name")),
            " | ".join(c["role"] for c in contacts if c.get("role")),
            " | ".join(c["email"] for c in contacts if c.get("email") and c["category"] != "general"),
            " | ".join(c["email"] for c in contacts if c.get("email") and c["category"] == "general"),
            " | ".join(dict.fromkeys(c["source_url"] for c in contacts)), " | ".join(company["source_urls"]),
            company["checked_at"], company["application_status"], " | ".join(company["notes"])
        ]))
        writer.writerow({key: safe_cell(value) for key, value in row.items()})
    return output.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8"
