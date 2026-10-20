from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SearchRequest(Strict):
    profile_name: str = Field(default="CV", min_length=1, max_length=100)
    city: str = Field(default="Torino", min_length=1, max_length=120)
    radius_km: float = Field(default=30, gt=0, le=1000)
    max_companies: int = Field(default=20, ge=1, le=100)
    max_search_queries: int = Field(default=25, ge=1, le=100)
    max_pages_per_company: int = Field(default=6, ge=1, le=10)
    min_fit_score: int = Field(default=0, ge=0, le=100)
    include_companies_without_jobs: Literal[True] = True
    language: Literal["it", "en"] = "it"
    sectors: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=500)


class Evidence(Strict):
    claim: str = Field(max_length=300)
    quote: str = Field(min_length=3, max_length=500)


class Profile(Strict):
    language: Literal["it", "en", "other"]
    skills: list[str] = Field(max_length=30)
    technologies: list[str] = Field(max_length=30)
    projects: list[str] = Field(max_length=10)
    experiences: list[str] = Field(max_length=10)
    education: list[str] = Field(max_length=10)
    languages: list[str] = Field(max_length=10)
    preferred_roles: list[str] = Field(max_length=10)
    adjacent_roles: list[str] = Field(max_length=10)
    seniority: str = Field(max_length=100)
    constraints: list[str] = Field(max_length=10)
    evidence_spans: list[Evidence] = Field(min_length=1, max_length=30)
    warnings: list[str] = Field(max_length=20)


class Query(Strict):
    terms: list[str] = Field(min_length=1, max_length=5)
    purpose: str = Field(max_length=200)


class SearchPlan(Strict):
    categories: list[str] = Field(min_length=1, max_length=10)
    queries: list[Query] = Field(min_length=1, max_length=25)
    priority_signals: list[str] = Field(max_length=15)


class Fact(Strict):
    kind: Literal["name", "industry", "activity", "technology", "address", "career", "person"]
    value: str = Field(min_length=1, max_length=300)
    quote: str = Field(min_length=3, max_length=600)
    source_url: str = Field(max_length=2048)


class Facts(Strict):
    facts: list[Fact] = Field(max_length=40)
    priority_urls: list[str] = Field(max_length=6)


class Fit(Strict):
    score: int = Field(ge=0, le=100)
    confidence: Literal["low", "medium", "high"]
    fit_level: Literal["alto", "medio", "basso", "da_verificare"]
    suggested_roles: list[str] = Field(max_length=10)
    matched_skills: list[str] = Field(max_length=30)
    missing_skills: list[str] = Field(max_length=30)
    reason: str = Field(max_length=1200)
    evidence_urls: list[str] = Field(max_length=10)


class Opening(Strict):
    title: str = Field(min_length=1, max_length=200)
    source_url: str
    quote: str = Field(min_length=3, max_length=600)
    status: Literal["possibly_open", "closed"]
    location: str | None
    published_at: str | None
    expires_at: str | None


class Openings(Strict):
    items: list[Opening] = Field(max_length=20)


class Contact(Strict):
    person_name: str | None
    role: str | None
    email: str | None
    category: Literal["recruiting", "general", "professional"]
    source_url: str
    quote: str = Field(min_length=3, max_length=600)


class Contacts(Strict):
    items: list[Contact] = Field(max_length=20)


class Draft(Strict):
    subject: str = Field(min_length=3, max_length=200)
    body_text: str = Field(min_length=20, max_length=5000)
    language: Literal["it", "en"]
    tailoring_facts: list[str] = Field(max_length=10)
    source_urls: list[str] = Field(max_length=10)
    warnings: list[str] = Field(max_length=10)
    status: Literal["draft"]


class Company(Strict):
    company_id: str
    company_name: str
    website: str
    industry: str | None = None
    facts: list[Fact] = Field(default_factory=list)
    location: dict = Field(default_factory=lambda: {"city": None, "distance_km": None, "location_status": "unverified"})
    fit: Fit | None = None
    vacancies: dict = Field(default_factory=lambda: {"status": "not_found", "items": []})
    contacts: list[dict] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    checked_at: str
    is_spontaneous_application_candidate: bool = True
    application_status: str = "da_valutare"
    notes: list[str] = Field(default_factory=list)
    email_draft: Draft | None = None


SCHEMAS = {"profile": Profile, "search-request": SearchRequest, "search-plan": SearchPlan,
           "company": Company, "draft": Draft, "facts": Facts, "fit": Fit,
           "openings": Openings, "contacts": Contacts}
