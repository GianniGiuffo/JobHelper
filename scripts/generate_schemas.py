"""Schemi e default derivati dai validatori effettivamente usati dal servizio."""
import json
from pathlib import Path
from job_hunter.models import SCHEMAS, SearchRequest

ROOT = Path(__file__).resolve().parents[1]
(ROOT/"schemas").mkdir(exist_ok=True)
for name, model in SCHEMAS.items():
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", **model.model_json_schema()}
    (ROOT/"schemas"/(name+".schema.json")).write_text(json.dumps(schema, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
(ROOT/"config/defaults.example.json").write_text(json.dumps(SearchRequest().model_dump(), ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
