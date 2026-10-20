"""Parser PDF in processo terminabile; stdin/stdout privati, niente log del CV."""
import io
import json
import sys
from pypdf import PdfReader

try:
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (384 * 1024 * 1024, 384 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (25, 25))
except ImportError:
    pass  # Windows development: subprocess timeout remains active.


def extract(data):
    if not data.startswith(b"%PDF-"):
        raise ValueError("invalid_pdf")
    reader = PdfReader(io.BytesIO(data), strict=True)
    if reader.is_encrypted:
        raise ValueError("encrypted_pdf")
    if len(reader.pages) > 30:
        raise ValueError("too_many_pdf_pages")
    chunks = []
    for page in reader.pages:
        chunks.append((page.extract_text() or "")[:12000])
    text = "\n".join(chunks)[:50000]
    if len(text.strip()) < 80 or sum(c.isalpha() for c in text) < 50:
        raise ValueError("ocr_required")
    return text


if __name__ == "__main__":
    try:
        print(json.dumps({"text": extract(sys.stdin.buffer.read(20_000_001))}, ensure_ascii=True))
    except Exception as exc:
        code = str(exc) if isinstance(exc, ValueError) else "pdf_parse_failed"
        print(json.dumps({"error": code}))
        sys.exit(1)
