import io
import socket
import httpx
import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from job_hunter.config import Settings
from job_hunter.models import Profile, SearchPlan, Facts, Fit, Openings, Contacts, Draft
from job_hunter.adapters import AdapterError


def pdf_bytes(text="CV FITTIZIO - Python e sviluppo software. Progetto dimostrativo Python, SQL, Git e Linux. Nessun dato personale reale."):
    writer = PdfWriter()
    page = writer.add_blank_page(width=595, height=842)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    stream = DecodedStreamObject()
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream.set_data(("BT /F1 12 Tf 40 780 Td (" + escaped + ") Tj ET").encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Test offline: accesso alla rete reale vietato")
    monkeypatch.setattr(socket, "create_connection", blocked)


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path / "data", api_token="test-local-token-" + "x" * 40,
                    ollama_url="http://ollama.local", searx_url="http://searx.local", crawl_url="http://crawl.local")


class FakeAdapters:
    instances = []
    fail_crawl = False
    calls = []

    def __init__(self, settings, store):
        self.s, self.store = settings, store
        self.client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
        self.retries = 0
        self.queries = []
        self.calls = []
        self.instances.append(self)

    async def pdf_text(self, data):
        from job_hunter.adapters import _parse_pdf
        return _parse_pdf(data)

    async def geocode(self, address):
        return {"coordinates": [45.0703, 7.6869] if address == "Torino" else [45.075, 7.69],
                "provider": "fixture", "checked_at": 0}

    async def search(self, query, language="it"):
        self.queries.append(query)
        if "linkedin.com" in query:
            return []
        return [{"url": "https://example.org/", "title": "Impresa Fittizia"},
                {"url": "https://www.example.org/contatti", "title": "duplicato"},
                {"url": "https://linkedin.com/jobs/test", "title": "portale"}]

    async def crawl(self, url):
        if self.fail_crawl:
            raise AdapterError("service_http_403")
        return {"url": url, "text": "Impresa Fittizia: software. Sede operativa Via Esempio 1, Torino. Contatto aziendale info@example.org.",
                "links": ["https://example.org/contatti"], "jsonld": [], "checked_at": 0}

    async def llm(self, prompt, data, schema, writing=False):
        self.calls.append(prompt)
        if schema == Profile:
            skill = "Excel" if "Excel" in data["cv_text"] else "Python"
            return Profile(language="it", skills=[skill], technologies=[skill], projects=[skill+" progetto"],
                experiences=[], education=[], languages=[], preferred_roles=[skill+" junior"], adjacent_roles=[],
                seniority="junior", constraints=[], evidence_spans=[{"claim": skill, "quote": skill}], warnings=[])
        if schema == SearchPlan:
            term = data["allowed_terms"][0]
            return SearchPlan(categories=[term], queries=[{"terms": [term], "purpose": "Aziende compatibili"}], priority_signals=[term])
        if schema == Facts:
            url = data["pages"][0]["url"]
            return Facts(facts=[{"kind": "name", "value": "Impresa Fittizia", "quote": "Impresa Fittizia", "source_url": url},
                {"kind": "industry", "value": "software", "quote": "software", "source_url": url},
                {"kind": "address", "value": "Via Esempio 1, Torino", "quote": "Sede operativa Via Esempio 1, Torino", "source_url": url}],
                priority_urls=["https://example.org/contatti"])
        if schema == Fit:
            return Fit(score=75, confidence="medium", fit_level="medio", suggested_roles=["Sviluppo junior"],
                matched_skills=["Python"], missing_skills=[], reason="Fixture con evidenze", evidence_urls=["https://example.org/"])
        if schema == Openings:
            return Openings(items=[])
        if schema == Contacts:
            return Contacts(items=[{"person_name": None, "role": None, "email": "info@example.org", "category": "general",
                 "source_url": "https://example.org/", "quote": "Contatto aziendale info@example.org"}])
        if schema == Draft:
            assert writing
            return Draft(subject="Bozza candidatura spontanea", body_text="Buongiorno, propongo il mio profilo Python per una valutazione personale.",
                language="it", tailoring_facts=["software"], source_urls=["https://example.org/"], warnings=["Da rivedere manualmente"], status="draft")
        raise AssertionError(schema)
