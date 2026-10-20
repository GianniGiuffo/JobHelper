import json
from pathlib import Path
import subprocess
import sys
import yaml

from job_hunter.models import SCHEMAS

ROOT = Path(__file__).resolve().parents[1]


def test_workflow_references_connections_and_privacy():
    workflows = [json.loads(p.read_text(encoding="utf-8")) for p in (ROOT/"workflows").glob("*.json")]
    ids = {w["id"] for w in workflows}
    assert len(workflows) == 16 and len(ids) == 16
    for workflow in workflows:
        assert workflow["active"] is False and not workflow["pinData"]
        settings = workflow["settings"]
        assert settings["saveDataSuccessExecution"] == settings["saveDataErrorExecution"] == "none"
        assert settings["saveManualExecutions"] is False
        names = {n["name"] for n in workflow["nodes"]}
        for node in workflow["nodes"]:
            assert "credentials" not in node
            if node["type"] == "n8n-nodes-base.executeWorkflow":
                assert node["parameters"]["workflowId"]["value"] in ids
            if node["type"] == "n8n-nodes-base.formTrigger":
                assert node["parameters"]["authentication"] == "n8nUserAuth"
            assert not any(word in node["type"].lower() for word in ("smtp", "sendemail", "gmail", "emailsend"))
        for source, edges in workflow["connections"].items():
            assert source in names
            for output in edges["main"]:
                for edge in output:
                    assert edge["node"] in names
    start = next(w for w in workflows if w["name"].endswith("00-ui-start"))
    trigger = start["nodes"][0]["parameters"]
    assert trigger["options"]["buttonLabel"] == "Avvia ricerca"
    fields = {f["fieldName"]: f for f in trigger["formFields"]["values"]}
    assert fields["city"]["defaultValue"] == "Torino"
    assert fields["radius_km"]["defaultValue"] == "30"
    assert start["nodes"][2]["parameters"]["options"]["waitForSubWorkflow"] is False


def test_generated_schemas_match_validators():
    for name, model in SCHEMAS.items():
        schema = json.loads((ROOT/"schemas"/(name+".schema.json")).read_text(encoding="utf-8"))
        schema.pop("$schema")
        assert schema == model.model_json_schema()


def test_compose_has_no_public_adapter_ports_or_existing_n8n_replacement():
    addons = yaml.safe_load((ROOT/"compose.addons.yml").read_text(encoding="utf-8"))
    assert "n8n" not in addons["services"]
    for service in addons["services"].values():
        assert not service.get("ports")
        assert service.get("mem_limit")
        assert not service.get("container_name")
        assert not service.get("privileged")
    standalone = yaml.safe_load((ROOT/"compose.standalone.yml").read_text(encoding="utf-8"))
    assert "127.0.0.1" in standalone["services"]["n8n"]["ports"][0]
    assert "latest" not in json.dumps(addons) + json.dumps(standalone)


def test_public_repository_scan():
    subprocess.run([sys.executable, "scripts/check_public_files.py"], cwd=ROOT, check=True)
