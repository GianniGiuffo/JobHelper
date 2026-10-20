import hashlib
import json
import re
import time
from datetime import datetime, timezone, date

from .adapters import AdapterError, ROOT, evidence_valid, normalize, host, is_portal, haversine
from .models import Profile, SearchPlan, Facts, Fit, Openings, Contacts, Draft, Company
from .safe_web import canonical_url


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def safe_terms(profile):
    vocabulary = [x.strip() for x in (ROOT / "config/search-vocabulary.txt").read_text(encoding="utf-8").splitlines()
                  if x.strip() and not x.startswith("#")]
    source = " ".join(profile.get("skills", []) + profile.get("technologies", []) +
                      profile.get("projects", []) + profile.get("preferred_roles", []))
    return [t for t in vocabulary if re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", source, re.I)]


class Pipeline:
    def __init__(self, settings, store, adapters):
        self.s, self.db, self.a = settings, store, adapters

    def error(self, run, stage, exc):
        known = isinstance(exc, (AdapterError,)) or hasattr(exc, "code")
        code = getattr(exc, "code", str(exc)) if known else type(exc).__name__
        run["data"]["errors"].append({"stage": stage, "code": code[:120]})

    async def parse(self, run, company_id=None):
        text = await self.a.pdf_text(run["pdf"])
        profile = await self.a.llm("extract-cv", {"cv_text": text[:18000]}, Profile)
        # Reject fabricated citations rather than silently turning them into facts.
        if any(normalize(e.quote) not in normalize(text) for e in profile.evidence_spans):
            raise AdapterError("cv_evidence_not_in_document")
        profile_data = profile.model_dump()
        # Explicit skills/technologies must occur in CV; adjacent roles remain labeled inferences.
        for key in ("skills", "technologies"):
            profile_data[key] = [s for s in profile_data[key] if normalize(s) in normalize(text)]
        run["data"]["profile"] = profile_data
        run["data"]["profile_id"] = run["data"]["cv_hash"]
        try:
            run["data"]["origin"] = await self.a.geocode(run["data"]["params"]["city"])
        except (ValueError, KeyError) as exc:
            self.error(run, "origin_geocode", exc)
            run["data"]["origin"] = {}

    async def plan(self, run, company_id=None):
        d = run["data"]
        terms = safe_terms(d["profile"])
        if not terms:
            raise AdapterError("no_safe_professional_query_terms_extend_vocabulary")
        result = await self.a.llm("plan-search", {"allowed_terms": terms, "area": d["params"]["city"],
                "preferences": {"sectors": d["params"]["sectors"], "notes": d["params"]["notes"]},
                "budget": d["params"]["max_search_queries"]}, SearchPlan)
        queries = []
        for q in result.queries:
            if all(t.lower() in terms for t in q.terms):
                queries.append({"query": " ".join(q.terms) + " aziende " + d["params"]["city"], "purpose": q.purpose})
        if not queries:
            raise AdapterError("plan_has_no_safe_queries")
        # Reserve some budget for vacancies; user limits remain a strict global ceiling.
        cap = max(1, d["params"]["max_search_queries"] // 2)
        d["plan"] = {"categories": result.categories, "queries": queries[:cap], "priority_signals": result.priority_signals}

    async def search(self, run, query):
        d = run["data"]
        if d["queries_used"] >= d["params"]["max_search_queries"]:
            if not any(e["code"] == "search_budget_exhausted" for e in d["errors"]):
                d["errors"].append({"stage": "search", "code": "search_budget_exhausted"})
            return []
        d["queries_used"] += 1
        self.db.save(run)  # Persist budget before network call, including failures.
        return await self.a.search(query, d["params"]["language"])

    async def discover(self, run, company_id=None):
        d = run["data"]
        seen = set()
        for query in d["plan"]["queries"]:
            try:
                results = await self.search(run, query["query"])
            except (ValueError, KeyError) as exc:
                self.error(run, "discovery", exc)
                continue
            for row in results:
                try:
                    url = canonical_url(row.get("url", ""))
                except ValueError:
                    continue
                domain = host(url)
                if is_portal(url) or domain in seen:
                    continue
                seen.add(domain)
                cid = hashlib.sha256(domain.encode()).hexdigest()[:24]
                root = url.split("/", 3)[:3]
                company = Company(company_id=cid, company_name=domain, website="/".join(root) + "/",
                                  source_urls=[url], checked_at=now_iso(),
                                  notes=["Dominio candidato da verificare; il titolo del motore non è una prova aziendale."]).model_dump()
                d["candidates"].append(cid)
                d["companies"][cid] = {"record": company, "seed": url, "pages": [], "stages": []}
                if len(d["candidates"]) >= d["params"]["max_companies"]:
                    return

    async def read_page(self, run, ctx, url):
        limit = run["data"]["params"]["max_pages_per_company"]
        if len(ctx.setdefault("attempted_urls", [])) >= limit or url in ctx["attempted_urls"]:
            return
        ctx["attempted_urls"].append(url)
        run["data"]["pages_used"] += 1
        self.db.save(run)
        try:
            page = await self.a.crawl(url)
            ctx["pages"].append(page)
            if page["url"] not in ctx["record"]["source_urls"]:
                ctx["record"]["source_urls"].append(page["url"])
        except (ValueError, KeyError) as exc:
            self.error(run, "company_page", exc)
            ctx["record"]["notes"].append("Pagina non leggibile; consultare errori della ricerca.")

    async def extract_facts(self, ctx):
        if not ctx["pages"]:
            return Facts(facts=[], priority_urls=[])
        result = await self.a.llm("find-evidence", {"pages": self.page_data(ctx)}, Facts)
        facts = [f for f in result.facts if evidence_valid(f, ctx["pages"]) and normalize(f.value) in normalize(f.quote)]
        ctx["record"]["facts"] = [f.model_dump() for f in facts]
        for fact in facts:
            if fact.kind == "name":
                ctx["record"]["company_name"] = fact.value
                ctx["record"]["notes"] = [n for n in ctx["record"]["notes"] if not n.startswith("Dominio candidato")]
            if fact.kind == "industry":
                ctx["record"]["industry"] = fact.value
        return result

    @staticmethod
    def page_data(ctx):
        # Bounded total prompt: 6 x 2k chars plus facts, compatible with domestic small models.
        return [{"url": p["url"], "text": p["text"][:2500], "links": p["links"][:35]} for p in ctx["pages"]]

    async def enrich(self, run, company_id):
        ctx = run["data"]["companies"][company_id]
        await self.read_page(run, ctx, ctx["record"]["website"])
        if ctx["seed"] != ctx["record"]["website"]:
            await self.read_page(run, ctx, ctx["seed"])
        try:
            selected = await self.extract_facts(ctx)
            allowed = {u for p in ctx["pages"] for u in p["links"]}
            # The agent chooses concrete pages; deterministic ranking fills gaps only.
            priority = [u for u in selected.priority_urls if u in allowed]
            priority += sorted(allowed - set(priority), key=lambda u: (not bool(re.search(
                r"career|lavora|contatt|team|about|serviz|tecnolog|prodott|chi-siamo|jobs", u, re.I)), u))
            for url in priority:
                await self.read_page(run, ctx, url)
                if len(ctx["attempted_urls"]) >= run["data"]["params"]["max_pages_per_company"]:
                    break
            await self.extract_facts(ctx)
        except (ValueError, KeyError) as exc:
            self.error(run, "facts", exc)
        offices = []
        for fact in [f for f in ctx["record"]["facts"] if f["kind"] == "address"][:3]:
            try:
                geo = await self.a.geocode(fact["value"])
                origin = run["data"].get("origin", {})
                if geo.get("coordinates") and origin.get("coordinates"):
                    offices.append({"city": fact["value"], "distance_km": haversine(origin["coordinates"], geo["coordinates"]),
                        "location_status": "geocoded", "distance_mode": "straight_line", "source_url": fact["source_url"],
                        "geocoding": geo, "note": "Sede estratta dal sito; coordinate del geocoder da confermare."})
            except (ValueError, KeyError) as exc:
                self.error(run, "company_geocode", exc)
        if offices:
            ctx["record"]["location"] = {**min(offices, key=lambda o: o["distance_km"]), "offices": offices}

    async def fit(self, run, company_id):
        ctx = run["data"]["companies"][company_id]
        if not ctx["record"]["facts"]:
            ctx["record"]["fit"] = Fit(score=0, confidence="low", fit_level="da_verificare", suggested_roles=[],
                 matched_skills=[], missing_skills=[], reason="Prove aziendali insufficienti", evidence_urls=[]).model_dump()
            return
        result = await self.a.llm("evaluate-company", {"profile": run["data"]["profile"], "company_facts": ctx["record"]["facts"]}, Fit)
        allowed = set(ctx["record"]["source_urls"])
        if any(u not in allowed for u in result.evidence_urls):
            raise AdapterError("fit_unknown_evidence_url")
        ctx["record"]["fit"] = result.model_dump()

    async def openings(self, run, company_id):
        ctx = run["data"]["companies"][company_id]
        company = ctx["record"]
        indexed = []
        try:
            # Use the PUBLIC company domain, never the personal profile or CV in query.
            indexed = await self.search(run, f'"{host(company["website"])}" (site:linkedin.com/jobs OR site:indeed.com OR site:indeed.it)')
        except (ValueError, KeyError) as exc:
            self.error(run, "openings_search", exc)
        evidence_pages = list(ctx["pages"])
        for row in indexed:
            try:
                url = canonical_url(row["url"])
            except (ValueError, KeyError):
                continue
            content = (row.get("title", "") + " " + row.get("content", ""))[:2500]
            name = normalize(company["company_name"])
            if not is_portal(url) or (name not in normalize(content) and host(company["website"]) not in content.lower()):
                continue
            evidence_pages.append({"url": url, "text": content, "links": []})
        items = []
        if evidence_pages:
            result = await self.a.llm("openings", {"company": company["company_name"], "pages":
                [{"url": p["url"], "text": p["text"][:2500]} for p in evidence_pages]}, Openings)
            seen = set()
            for opening in result.items:
                if not evidence_valid(opening, evidence_pages) or normalize(opening.title) not in normalize(opening.quote):
                    continue
                if opening.source_url in seen:
                    continue
                seen.add(opening.source_url)
                items.append({**opening.model_dump(), "checked_at": now_iso(), "verification": "public_text_or_index_only"})
        company["vacancies"] = {"status": "possibly_open" if any(i["status"] == "possibly_open" for i in items)
            else "closed" if items else "not_found" if ctx["pages"] else "unknown/error",
            "items": items, "checked_at": now_iso(), "note": "Copertura limitata alle pagine lette e ai risultati indicizzati; apertura non confermata."}
        company["is_spontaneous_application_candidate"] = not any(i["status"] == "possibly_open" for i in items)

    async def contacts(self, run, company_id):
        ctx = run["data"]["companies"][company_id]
        if not ctx["pages"]:
            return
        result = await self.a.llm("contacts", {"pages": self.page_data(ctx)}, Contacts)
        seen = set()
        for contact in result.items:
            if not evidence_valid(contact, ctx["pages"]):
                continue
            fields = [contact.person_name, contact.role, contact.email]
            if any(normalize(f) not in normalize(contact.quote) for f in fields if f):
                continue
            if contact.person_name and not contact.role:
                continue
            if contact.email and not re.fullmatch(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", contact.email):
                continue
            key = tuple(fields)
            if key not in seen:
                seen.add(key)
                ctx["record"]["contacts"].append({**contact.model_dump(), "verified_at": now_iso(), "confidence": "quoted_public_business_contact"})

    async def draft(self, run, company_id):
        # The gate precedes all agent-B requests, including direct invocation of its workflow.
        if not self.s.email_draft_enabled:
            return
        ctx = run["data"]["companies"][company_id]
        fit = ctx["record"].get("fit") or {}
        if fit.get("score", 0) < self.s.draft_min_fit or not ctx["record"]["facts"]:
            return
        draft = await self.a.llm("draft-email", {"profile": run["data"]["profile"], "company": ctx["record"],
             "language": run["data"]["params"]["language"], "purpose": "candidatura spontanea" if
             ctx["record"]["is_spontaneous_application_candidate"] else "risposta a possibile offerta"}, Draft, writing=True)
        if any(u not in ctx["record"]["source_urls"] for u in draft.source_urls):
            raise AdapterError("draft_unknown_source")
        ctx["draft"] = draft.model_dump()

    async def persist(self, run, company_id):
        ctx = run["data"]["companies"][company_id]
        company = Company.model_validate(ctx["record"]).model_dump()
        if company.get("email_draft") is None:
            company.pop("email_draft", None)
        distance = company["location"].get("distance_km")
        reason = None
        if distance is not None and distance > run["data"]["params"]["radius_km"]:
            reason = "outside_radius"
        elif (company.get("fit") or {}).get("score", 0) < run["data"]["params"]["min_fit_score"]:
            reason = "below_minimum_fit"
        if reason:
            ctx["excluded"] = reason
        else:
            if distance is None:
                company["notes"].append("Sede e distanza da verificare; conservata nell'elenco secondario.")
            elif company["location"].get("geocoding", {}).get("attribution"):
                company["notes"].append(company["location"]["geocoding"]["attribution"])
            if ctx.get("draft"):
                company["email_draft"] = ctx["draft"]
            self.db.put_result(run["id"], company)
        ctx["saved"] = True
        ctx["pages"] = []  # Minimize retained page bodies (TTL cache remains bounded).

    async def stage(self, run_id, name, company_id=None):
        run = self.db.get(run_id)
        if run["status"] != "running":
            return {"run_id": run_id, "status": run["status"]}
        d = run["data"]
        ctx = d["companies"].get(company_id) if company_id else None
        stages = ctx["stages"] if ctx else d["stages"]
        if name in stages:
            return {"run_id": run_id, "company_id": company_id, "status": run["status"]}
        if company_id and not ctx:
            raise KeyError("Azienda inesistente")
        start_retries = self.a.retries
        try:
            remaining = d["deadline"] - time.time()
            if remaining <= 0:
                raise TimeoutError()
            import asyncio
            async with asyncio.timeout(remaining):
                await getattr(self, name)(run, company_id)
            stages.append(name)
        except Exception as exc:
            self.error(run, name, exc)
            if name in ("parse", "plan") or isinstance(exc, TimeoutError):
                self.db.save(run, "partial" if self.db.results(run_id) else "failed", clear_pdf=not self.s.retain_pdf)
            elif name == "openings" and ctx:
                ctx["record"]["vacancies"] = {"status": "unknown/error", "items": [], "checked_at": now_iso()}
            elif name == "fit" and ctx:
                ctx["record"]["notes"].append("Valutazione AI non disponibile")
        d["http_retries"] += self.a.retries - start_retries
        self.db.save(run, clear_pdf=name == "parse" and not self.s.retain_pdf)
        return {"run_id": run_id, "company_id": company_id, "status": run["status"]}

    def next_company(self, run_id):
        run = self.db.get(run_id)
        if run["status"] == "running":
            for cid in run["data"]["candidates"]:
                if not run["data"]["companies"][cid].get("saved"):
                    return {"run_id": run_id, "company_id": cid, "has_company": True}
        return {"run_id": run_id, "has_company": False}

    def finish(self, run_id):
        run = self.db.get(run_id)
        if run["status"] == "running":
            d = run["data"]
            pending = any(not c.get("saved") for c in d["companies"].values())
            status = "partial" if d["errors"] or pending else "completed"
            if not d["candidates"] and d["errors"]:
                status = "failed"
            self.db.save(run, status, clear_pdf=not self.s.retain_pdf)
        return self.db.summary(run_id)
