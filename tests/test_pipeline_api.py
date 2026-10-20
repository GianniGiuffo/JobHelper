import asyncio
import csv
import io
import json
import time
import httpx
import pytest
from fastapi.testclient import TestClient

from job_hunter.api import create_app
from job_hunter.models import SearchRequest
from job_hunter.store import Store
from job_hunter.pipeline import Pipeline, safe_terms
from conftest import FakeAdapters, pdf_bytes


def create(client, params=None, pdf=None):
    response = client.post("/runs", files={"file": ("cv.pdf", pdf or pdf_bytes(), "application/pdf")},
                           data={"parameters": json.dumps(params or {})})
    assert response.status_code == 202, response.text
    return response.json()


def run_to_end(client, run_id):
    reference = {"run_id": run_id}
    assert client.post("/claim", json=reference).json()["ready"]
    for stage in ("parse", "plan", "discover"):
        assert client.post("/stage/"+stage, json=reference).status_code == 200
    while True:
        nxt = client.post("/next", json=reference).json()
        if not nxt["has_company"]:
            break
        for stage in ("enrich", "fit", "openings", "contacts", "draft", "persist"):
            response = client.post("/stage/"+stage, json={"run_id": run_id, "company_id": nxt["company_id"]})
            assert response.status_code == 200, response.text
    return client.post("/finish", json=reference).json()


@pytest.fixture
def client(settings):
    FakeAdapters.fail_crawl = False
    with TestClient(create_app(settings, FakeAdapters)) as c:
        c.headers["Authorization"] = "Bearer " + settings.api_token
        yield c


def test_complete_pdf_to_export_without_optional_services(client):
    job = create(client)
    assert job["status"] == "queued"
    assert client.get("/runs/"+job["run_id"]).json()["companies_saved"] == 0
    final = run_to_end(client, job["run_id"])
    assert final["status"] == "completed", final
    assert final["companies_saved"] == 1
    data = client.get(f'/runs/{job["run_id"]}/export/json').json()
    company = data["results"][0]
    assert company["vacancies"]["status"] == "not_found"
    assert company["is_spontaneous_application_candidate"] is True
    assert company["contacts"][0]["email"] == "info@example.org"
    assert company["location"]["distance_km"] < 1
    assert "email_draft" not in company
    assert "draft-email" not in FakeAdapters.instances[-1].calls
    assert "Python" not in json.dumps(data) or "cv_text" not in json.dumps(data)
    csv_data = client.get(f'/runs/{job["run_id"]}/export/csv')
    assert "attachment" in csv_data.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(csv_data.content.decode("utf-8-sig"))))
    assert len(rows) == 1 and rows[0]["vacancies_status"] == "not_found"


def test_draft_on_is_local_draft_only(settings):
    settings.email_draft_enabled = True
    with TestClient(create_app(settings, FakeAdapters)) as c:
        c.headers["Authorization"] = "Bearer "+settings.api_token
        job = create(c)
        run_to_end(c, job["run_id"])
        result = c.get(f'/runs/{job["run_id"]}/export/json').json()["results"][0]
        assert result["email_draft"]["status"] == "draft"
        assert FakeAdapters.instances[-1].calls.count("draft-email") == 1


def test_double_submission_and_claim_are_idempotent(client):
    pdf = pdf_bytes()
    a, b = create(client, pdf=pdf), create(client, pdf=pdf)
    assert a["run_id"] == b["run_id"]
    assert b["created"] is False
    ref = {"run_id": a["run_id"]}
    assert client.post("/claim", json=ref).json()["ready"]
    assert not client.post("/claim", json=ref).json()["ready"]
    other = create(client, {"city": "Milano"})
    assert client.post("/claim", json={"run_id": other["run_id"]}).json()["busy"]


def test_two_cvs_different_plans_and_isolated_runs(client):
    first = create(client)
    second = create(client, pdf=pdf_bytes("CV FITTIZIO Excel per amministrazione e contabilità. Progetto di prova con Excel, bilanci e contabilità, senza dati personali."))
    run_to_end(client, first["run_id"])
    first_query = FakeAdapters.instances[-1].queries[0]
    run_to_end(client, second["run_id"])
    later = FakeAdapters.instances[-1].queries
    assert first_query != later[2]
    a = client.get(f'/runs/{first["run_id"]}/export/json').json()
    b = client.get(f'/runs/{second["run_id"]}/export/json').json()
    assert a["profile_id"] != b["profile_id"]


@pytest.mark.parametrize("params", [{"radius_km": 0}, {"max_companies": 51}, {"city": ""}, {"min_fit_score": 101},
    {"city": "<script>"}, {"max_search_queries": 26}, {"include_companies_without_jobs": False}])
def test_invalid_parameters_rejected(client, params):
    response = client.post("/runs", files={"file": ("cv.pdf", pdf_bytes())}, data={"parameters": json.dumps(params)})
    assert response.status_code == 422


def test_invalid_upload_and_auth(client):
    assert client.post("/runs", files={"file": ("cv.exe", b"bad")}).status_code == 422
    assert client.post("/runs", files={"file": ("cv.pdf", b"bad")}).status_code == 422
    assert client.get("/health", headers={"Authorization": "wrong"}).status_code == 401
    assert client.get("/live", headers={"Authorization": "wrong"}).status_code == 200


def test_scan_without_ocr_fails_with_clear_code(client):
    job = create(client, pdf=pdf_bytes(""))
    final = run_to_end(client, job["run_id"])
    assert final["status"] == "failed"
    assert final["errors"][0]["code"] == "ocr_required"


def test_site_403_preserves_partial_company(client):
    FakeAdapters.fail_crawl = True
    job = create(client)
    final = run_to_end(client, job["run_id"])
    assert final["status"] == "partial"
    company = client.get(f'/runs/{job["run_id"]}/export/json').json()["results"][0]
    assert company["location"]["distance_km"] is None
    assert company["fit"]["fit_level"] == "da_verificare"
    assert company["contacts"] == []


def test_geography_and_threshold_apply(client):
    job = create(client, {"radius_km": 0.01})
    run_to_end(client, job["run_id"])
    export = client.get(f'/runs/{job["run_id"]}/export/json').json()
    assert export["results"] == [] and export["excluded"][0]["reason"] == "outside_radius"


def test_minimum_fit_filter(client):
    job = create(client, {"min_fit_score": 80})
    run_to_end(client, job["run_id"])
    export = client.get(f'/runs/{job["run_id"]}/export/json').json()
    assert export["results"] == [] and export["excluded"][0]["reason"] == "below_minimum_fit"


def test_delete_and_retention(client):
    job = create(client)
    assert client.delete("/runs/"+job["run_id"]).status_code == 200
    assert client.get("/runs/"+job["run_id"]).status_code == 404


def test_no_pii_query_terms():
    terms = safe_terms({"skills": ["Python", "Persona Fittizia", "name@example.org", "+391234567890"],
                        "technologies": [], "projects": [], "preferred_roles": []})
    assert terms == ["python"]


def test_watchdog_and_pdf_deletion(settings):
    db = Store(settings.data_dir)
    rid, _ = db.create(SearchRequest().model_dump(), pdf_bytes(), "cv.pdf")
    db.claim(rid, 1)
    run = db.get(rid)
    run["data"]["deadline"] = time.time() - 1
    db.save(run)
    db.sweep(30)
    assert db.get(rid)["status"] == "failed"
    assert db.get(rid)["pdf"] is None


async def test_status_and_enqueue_do_not_wait_for_research(settings):
    app = create_app(settings, FakeAdapters)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                                     headers={"Authorization": "Bearer "+settings.api_token}) as c:
            job = (await c.post("/runs", files={"file": ("cv.pdf", pdf_bytes())})).json()
            await c.post("/claim", json={"run_id": job["run_id"]})
            started = asyncio.Event()
            release = asyncio.Event()
            adapter = app.state.hunter["adapter"]
            original = adapter.pdf_text
            async def slow(data):
                started.set()
                await release.wait()
                return await original(data)
            adapter.pdf_text = slow
            task = asyncio.create_task(c.post("/stage/parse", json={"run_id": job["run_id"]}))
            await started.wait()
            async with asyncio.timeout(1):
                assert (await c.get("/runs/"+job["run_id"])).status_code == 200
                assert (await c.post("/runs", files={"file": ("cv.pdf", pdf_bytes())}, data={"parameters": '{"city":"Milano"}'})).status_code == 202
            release.set()
            await task
