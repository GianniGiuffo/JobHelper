import asyncio
from contextlib import asynccontextmanager, suppress
import hmac
import json
import os
import time
import uuid
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, ValidationError

from .config import Settings
from .store import Store
from .adapters import Adapters, AdapterError
from .models import SearchRequest
from .pipeline import Pipeline
from .exports import export
from .body_limit import BodyLimitMiddleware


class Reference(BaseModel):
    run_id: uuid.UUID
    company_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{24}$")


class DavImport(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    parameters: SearchRequest = Field(default_factory=SearchRequest)


class DavExport(Reference):
    path: str = Field(min_length=1, max_length=500)
    format: Literal["csv", "json"] = "json"
    confirm_export: Literal[True]


def create_app(settings=None, adapters_factory=Adapters):
    s = settings or Settings()
    lock = asyncio.Lock()
    state = {}

    @asynccontextmanager
    async def lifespan(app):
        s.validate()
        os.umask(0o077)
        db = Store(s.data_dir)
        adapter = adapters_factory(s, db)
        state.update(db=db, adapter=adapter, pipeline=Pipeline(s, db, adapter))

        async def maintenance():
            while True:
                async with lock:
                    db.sweep(s.retention_days)
                await asyncio.sleep(30)

        task = asyncio.create_task(maintenance())
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            await adapter.client.aclose()

    app = FastAPI(title="AI Job Hunter — API interna", docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)
    app.add_middleware(BodyLimitMiddleware, max_bytes=s.max_upload_mb * 1024 * 1024 + 65536)

    def authenticated(authorization: str = Header(default="")):
        if not hmac.compare_digest(authorization.encode(), ("Bearer " + s.api_token).encode()):
            raise HTTPException(401, "Autenticazione richiesta")

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({"detail": "Ricerca o azienda inesistente"}, status_code=404)

    @app.exception_handler(AdapterError)
    async def adapter_error(request, exc):
        return JSONResponse({"detail": str(exc)[:120]}, status_code=422)

    @app.exception_handler(Exception)
    async def internal_error(request, exc):
        # Do not return exception text, HTTP bodies, request input or CV content.
        return JSONResponse({"detail": "Errore interno; controllare lo stato della ricerca"}, status_code=500)

    @app.get("/live")
    def live():
        return {"status": "ok", "version": "0.1.0"}

    auth = [Depends(authenticated)]

    def validate_params(params):
        for name, cap in (("radius_km", s.max_radius), ("max_companies", s.max_companies),
                          ("max_search_queries", s.max_queries), ("max_pages_per_company", s.max_pages)):
            if getattr(params, name) > cap:
                raise HTTPException(422, f"{name}: limite installazione {cap}")
        # Input constraints are plain text; never interpret markup, shell or instructions.
        for value in (params.city, params.notes, params.sectors, params.profile_name):
            if any(ord(c) < 32 and c not in "\n\t" for c in value) or "<" in value or ">" in value:
                raise HTTPException(422, "Usare testo semplice senza markup o caratteri di controllo")

    def enqueue(pdf, params, filename):
        validate_params(params)
        if not pdf.startswith(b"%PDF-") or len(pdf) > s.max_upload_mb * 1024 * 1024:
            raise HTTPException(422, "PDF non valido o troppo grande")
        filename = Path(filename.replace("\\", "/")).name[:120]
        run_id, created = state["db"].create(params.model_dump(), pdf, filename)
        return {"run_id": run_id, "status": state["db"].get(run_id)["status"], "created": created}

    @app.post("/runs", dependencies=auth, status_code=202)
    async def create_run(file: UploadFile = File(...), parameters: str = Form("{}")):
        try:
            params = SearchRequest.model_validate_json(parameters)
        except ValidationError:
            raise HTTPException(422, "Parametri di ricerca non validi") from None
        if not (file.filename or "").lower().endswith(".pdf"):
            raise HTTPException(422, "Caricare un file .pdf")
        data = await file.read(s.max_upload_mb * 1024 * 1024 + 1)
        await file.close()
        return enqueue(data, params, file.filename)

    @app.post("/runs/import", dependencies=auth, status_code=202)
    async def import_run(body: DavImport):
        validate_params(body.parameters)
        pdf = await state["adapter"].dav_import(body.path)
        return enqueue(pdf, body.parameters, body.path)

    @app.post("/claim", dependencies=auth)
    async def claim(body: Reference):
        ready, busy = state["db"].claim(str(body.run_id), s.max_runtime)
        return {"run_id": str(body.run_id), "ready": ready, "busy": busy}

    @app.post("/stage/{name}", dependencies=auth)
    async def stage(name: Literal["parse", "plan", "discover", "enrich", "fit", "openings", "contacts", "draft", "persist"], body: Reference):
        if name in ("enrich", "fit", "openings", "contacts", "draft", "persist") and not body.company_id:
            raise HTTPException(422, "company_id richiesto")
        async with lock:
            return await state["pipeline"].stage(str(body.run_id), name, body.company_id)

    @app.post("/next", dependencies=auth)
    async def next_company(body: Reference):
        async with lock:
            return state["pipeline"].next_company(str(body.run_id))

    @app.post("/finish", dependencies=auth)
    async def finish(body: Reference):
        async with lock:
            return state["pipeline"].finish(str(body.run_id))

    @app.get("/runs/{run_id}", dependencies=auth)
    async def status(run_id: uuid.UUID):
        # WAL reads don't wait for slow research requests; confirmation/status remain fast.
        return state["db"].summary(str(run_id))

    @app.get("/runs/{run_id}/export/{fmt}", dependencies=auth)
    async def download(run_id: uuid.UUID, fmt: Literal["csv", "json"]):
        data, content_type = export(state["db"], str(run_id), fmt)
        return Response(data, media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{run_id}.{fmt}"', "Cache-Control": "no-store"})

    @app.post("/export/nextcloud", dependencies=auth)
    async def export_dav(body: DavExport):
        data, typ = export(state["db"], str(body.run_id), body.format)
        await state["adapter"].dav_export(body.path, data, typ)
        return {"run_id": str(body.run_id), "exported": True}

    @app.delete("/runs/{run_id}", dependencies=auth)
    async def delete_run(run_id: uuid.UUID):
        async with lock:
            run = state["db"].get(str(run_id))
            if run["status"] == "running":
                raise HTTPException(409, "Attendere la fine o il timeout della ricerca")
            state["db"].delete(str(run_id))
        return {"deleted": True}

    @app.get("/health", dependencies=auth)
    async def health():
        a = state["adapter"]
        checks = {}
        endpoints = {"ollama": (s.ollama_url, "/api/tags"), "searxng": (s.searx_url, "/healthz"),
                     "crawl4ai": (s.crawl_url, "/health")}
        if s.stirling_enabled:
            endpoints["stirling"] = (s.stirling_url, "/v1/api-docs")
        for service, (base, path) in endpoints.items():
            try:
                headers = {"X-API-KEY": s.stirling_key} if service == "stirling" and s.stirling_key else {}
                response = await a.request("GET", base.rstrip("/") + path, headers=headers, timeout=5)
                checks[service] = {"reachable": True}
                if service == "ollama":
                    names = [m["name"] for m in response.json().get("models", [])]
                    checks[service]["research_model_installed"] = s.research_model in names
                    checks[service]["writing_model_installed"] = s.writing_model in names
                if service == "stirling":
                    checks[service]["ocr_available"] = "/api/v1/misc/ocr-pdf" in response.json().get("paths", {})
            except Exception:
                checks[service] = {"reachable": False, "error": "unreachable_or_incompatible"}
        checks["nextcloud"] = {"enabled": s.nextcloud_enabled, "note": "Verifica credenziali con import esplicito, nessuna scrittura automatica"}
        return {"services": checks, "email_draft_enabled": s.email_draft_enabled,
                "limits": {"max_companies": s.max_companies, "max_search_queries": s.max_queries,
                           "max_pages_per_company": s.max_pages, "max_total_runtime": s.max_runtime}}

    app.state.hunter = state
    return app


app = create_app()
