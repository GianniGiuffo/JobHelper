from dataclasses import dataclass, field
from pathlib import Path
import os


def secret(name: str) -> str:
    path = os.getenv(name + "_FILE")
    return Path(path).read_text(encoding="utf-8").strip() if path else os.getenv(name, "")


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", "/data")))
    api_token: str = field(default_factory=lambda: secret("HUNTER_API_TOKEN"))
    ollama_url: str = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434"))
    research_model: str = field(default_factory=lambda: os.getenv("OLLAMA_RESEARCH_MODEL", "qwen3.5:4b"))
    writing_model: str = field(default_factory=lambda: os.getenv("OLLAMA_WRITING_MODEL", "qwen3.5:4b"))
    ollama_timeout: int = field(default_factory=lambda: int(os.getenv("OLLAMA_TIMEOUT", "120")))
    num_ctx: int = field(default_factory=lambda: int(os.getenv("OLLAMA_NUM_CTX", "8192")))
    searx_url: str = field(default_factory=lambda: os.getenv("SEARXNG_BASE_URL", "http://searxng:8080"))
    crawl_url: str = field(default_factory=lambda: os.getenv("CRAWL4AI_BASE_URL", "http://crawl4ai:11235"))
    crawl_token: str = field(default_factory=lambda: secret("CRAWL4AI_API_TOKEN"))
    geocode_url: str = field(default_factory=lambda: os.getenv("GEOCODER_BASE_URL", "https://nominatim.openstreetmap.org"))
    user_agent: str = field(default_factory=lambda: os.getenv("HTTP_USER_AGENT", "AIJobHunter/0.1 (private self-hosted research)"))
    stirling_enabled: bool = field(default_factory=lambda: os.getenv("STIRLING_ENABLED", "false").lower() == "true")
    stirling_url: str = field(default_factory=lambda: os.getenv("STIRLING_BASE_URL", ""))
    stirling_key: str = field(default_factory=lambda: secret("STIRLING_API_KEY"))
    ocr_languages: str = field(default_factory=lambda: os.getenv("STIRLING_OCR_LANGUAGES", "ita,eng"))
    nextcloud_enabled: bool = field(default_factory=lambda: os.getenv("NEXTCLOUD_ENABLED", "false").lower() == "true")
    nextcloud_url: str = field(default_factory=lambda: os.getenv("NEXTCLOUD_WEBDAV_URL", ""))
    nextcloud_user: str = field(default_factory=lambda: secret("NEXTCLOUD_USER"))
    nextcloud_password: str = field(default_factory=lambda: secret("NEXTCLOUD_APP_PASSWORD"))
    email_draft_enabled: bool = field(default_factory=lambda: os.getenv("EMAIL_DRAFT_ENABLED", "false").lower() == "true")
    draft_min_fit: int = field(default_factory=lambda: int(os.getenv("EMAIL_DRAFT_MIN_FIT", "60")))
    max_upload_mb: int = field(default_factory=lambda: int(os.getenv("MAX_UPLOAD_MB", "10")))
    max_companies: int = field(default_factory=lambda: int(os.getenv("MAX_COMPANIES", "50")))
    max_queries: int = field(default_factory=lambda: int(os.getenv("MAX_SEARCH_QUERIES", "25")))
    max_pages: int = field(default_factory=lambda: int(os.getenv("MAX_PAGES_PER_COMPANY", "6")))
    max_runtime: int = field(default_factory=lambda: int(os.getenv("MAX_TOTAL_RUNTIME", "1800")))
    max_radius: int = field(default_factory=lambda: int(os.getenv("MAX_RADIUS_KM", "300")))
    retention_days: int = field(default_factory=lambda: int(os.getenv("RETENTION_DAYS", "30")))
    retain_pdf: bool = field(default_factory=lambda: os.getenv("RETAIN_ORIGINAL_PDF", "false").lower() == "true")
    cache_hours: int = field(default_factory=lambda: int(os.getenv("CACHE_HOURS", "24")))

    def validate(self):
        if len(self.api_token) < 32:
            raise ValueError("Configurare HUNTER_API_TOKEN_FILE: almeno 32 caratteri")
        if any(":cloud" in m.lower() or "-cloud" in m.lower() for m in (self.research_model, self.writing_model)):
            raise ValueError("Sono consentiti solo tag di modelli locali, non cloud")
        for name in ("max_upload_mb", "max_companies", "max_queries", "max_pages", "max_runtime", "max_radius", "retention_days"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} deve essere positivo")
