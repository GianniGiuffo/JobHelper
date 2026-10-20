from fastapi.testclient import TestClient
from job_hunter.api import create_app
from job_hunter.models import Profile
from conftest import FakeAdapters
from test_pipeline_api import create


def test_explicit_professional_facts_cannot_be_invented(settings):
    class Fabrication(FakeAdapters):
        async def llm(self, prompt, data, schema, writing=False):
            value = await super().llm(prompt, data, schema, writing)
            if schema == Profile:
                value.experiences = ["Dieci anni presso Impresa Mai Citata"]
                value.education = ["Dottorato inesistente"]
                value.languages = ["Lingua inventata"]
            return value
    with TestClient(create_app(settings, Fabrication)) as client:
        client.headers["Authorization"] = "Bearer "+settings.api_token
        job = create(client)
        client.post("/claim", json={"run_id": job["run_id"]})
        client.post("/stage/parse", json={"run_id": job["run_id"]})
        profile = client.app.state.hunter["db"].get(job["run_id"])["data"]["profile"]
        assert profile["experiences"] == profile["education"] == profile["languages"] == []
