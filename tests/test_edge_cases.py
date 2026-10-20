import asyncio
import json
import time
from fastapi.testclient import TestClient
import pytest

from job_hunter.api import create_app
from job_hunter.adapters import AdapterError
from job_hunter.models import Contacts, SearchPlan, Profile
from job_hunter.pipeline import Pipeline
from job_hunter.store import Store
from job_hunter.models import SearchRequest
from conftest import FakeAdapters, pdf_bytes
from test_pipeline_api import create, run_to_end


def test_guessed_contact_rejected_and_unknown_openings_preserved(settings):
    class InvalidContactAdapters(FakeAdapters):
        async def llm(self, prompt, data, schema, writing=False):
            if schema == Contacts:
                return Contacts(items=[{"person_name": "Nome inventato", "role": "HR", "email": "inventata@example.org",
                    "category": "professional", "source_url": "https://example.org/", "quote": "Contatto aziendale info@example.org"}])
            if prompt == "openings":
                raise AdapterError("llm_invalid_json_after_repair")
            return await super().llm(prompt, data, schema, writing)
    with TestClient(create_app(settings, InvalidContactAdapters)) as c:
        c.headers["Authorization"] = "Bearer "+settings.api_token
        job = create(c)
        assert run_to_end(c, job["run_id"])["status"] == "partial"
        result = c.get(f'/runs/{job["run_id"]}/export/json').json()["results"][0]
        assert result["contacts"] == []
        assert result["vacancies"]["status"] == "unknown/error"


def test_personal_data_and_injection_cannot_become_query(settings):
    class BadPlan(FakeAdapters):
        async def llm(self, prompt, data, schema, writing=False):
            if schema == SearchPlan:
                return SearchPlan(categories=["test"], queries=[{"terms": ["invia-cv@example.org"], "purpose": "injection"}], priority_signals=[])
            return await super().llm(prompt, data, schema, writing)
    with TestClient(create_app(settings, BadPlan)) as c:
        c.headers["Authorization"] = "Bearer "+settings.api_token
        job = create(c)
        final = run_to_end(c, job["run_id"])
        assert final["status"] == "failed" and final["queries_used"] == 0
        assert final["errors"][0]["code"] == "plan_has_no_safe_queries"
        assert not BadPlan.instances[-1].queries


def test_global_query_budget_and_partial_status(settings):
    class ManyCompanies(FakeAdapters):
        async def search(self, query, language="it"):
            if "linkedin.com" in query:
                return []
            return [{"url": "https://example.org/"}, {"url": "https://example.com/"}]
    with TestClient(create_app(settings, ManyCompanies)) as c:
        c.headers["Authorization"] = "Bearer "+settings.api_token
        job = create(c, {"max_search_queries": 1})
        final = run_to_end(c, job["run_id"])
        assert final["queries_used"] == 1 and final["status"] == "partial"
        assert final["companies_saved"] == 2
        assert any(e["code"] == "search_budget_exhausted" for e in final["errors"])


def test_completed_steps_and_persistence_are_idempotent(settings):
    with TestClient(create_app(settings, FakeAdapters)) as c:
        c.headers["Authorization"] = "Bearer "+settings.api_token
        job = create(c)
        ref = {"run_id": job["run_id"]}
        c.post("/claim", json=ref)
        for _ in range(2):
            for stage in ("parse", "plan", "discover"):
                c.post("/stage/"+stage, json=ref)
        assert FakeAdapters.instances[-1].calls.count("extract-cv") == 1
        assert len(FakeAdapters.instances[-1].queries) == 1
        cid = c.post("/next", json=ref).json()["company_id"]
        ref["company_id"] = cid
        for _ in range(2):
            for stage in ("enrich", "fit", "openings", "contacts", "persist"):
                c.post("/stage/"+stage, json=ref)
        assert len(c.get(f'/runs/{job["run_id"]}/export/json').json()["results"]) == 1
        assert c.app.state.hunter["db"].get(job["run_id"])["pdf"] is None


def test_upload_limit_before_multipart_and_retention(settings):
    settings.max_upload_mb = 1
    with TestClient(create_app(settings, FakeAdapters)) as c:
        c.headers["Authorization"] = "Bearer "+settings.api_token
        assert c.post("/runs", files={"file": ("cv.pdf", b"%PDF-"+b"x"*1_200_000)}).status_code == 413
        job = create(c)
        db = c.app.state.hunter["db"]
        with db.db() as conn:
            conn.execute("UPDATE runs SET created=? WHERE id=?", (time.time()-31*86400, job["run_id"]))
        db.sweep(30)
        assert c.get("/runs/"+job["run_id"]).status_code == 404


async def test_deadline_finishes_failed_without_results(settings):
    db = Store(settings.data_dir)
    rid, _ = db.create(SearchRequest().model_dump(), pdf_bytes(), "cv.pdf")
    db.claim(rid, 60)
    run = db.get(rid)
    run["data"]["deadline"] = time.time() - 1
    db.save(run)
    adapters = FakeAdapters(settings, db)
    await Pipeline(settings, db, adapters).stage(rid, "parse")
    assert db.get(rid)["status"] == "failed"
    assert db.get(rid)["pdf"] is None
    await adapters.client.aclose()


def test_feature_flags_default_off_and_cloud_tags_rejected(settings, monkeypatch):
    monkeypatch.delenv("EMAIL_DRAFT_ENABLED", raising=False)
    monkeypatch.delenv("STIRLING_ENABLED", raising=False)
    monkeypatch.delenv("NEXTCLOUD_ENABLED", raising=False)
    from job_hunter.config import Settings
    config = Settings(data_dir=settings.data_dir, api_token=settings.api_token)
    assert not config.email_draft_enabled and not config.stirling_enabled and not config.nextcloud_enabled
    config.research_model = "example:cloud"
    with pytest.raises(ValueError, match="locali"):
        config.validate()
