from fastapi.testclient import TestClient

from backend.app.main import app


def test_healthz():
    c = TestClient(app)
    r = c.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_root_serves_ui_if_present():
    c = TestClient(app)
    r = c.get("/")
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert "Open the UI search box" in r.text


def test_index_search_query_roundtrip():
    c = TestClient(app)

    r = c.post("/v1/index", json={"text": "The capital of France is Paris.", "metadata": {"topic": "geo"}})
    assert r.status_code == 200
    doc_id = r.json()["id"]
    assert doc_id

    r = c.post("/v1/search", json={"q": "capital france", "k": 3})
    assert r.status_code == 200
    matches = r.json()["matches"]
    assert len(matches) >= 1
    assert matches[0]["id"] == doc_id

    r = c.post("/v1/query", json={"q": "What is the capital of France?", "top_k": 3})
    assert r.status_code == 200
    data = r.json()
    assert "answer" in data
    assert data["provider"] in {"stub", "openai", "transformers"}


def test_generate_endpoint_returns_files():
    c = TestClient(app)
    r = c.post("/v1/generate", json={"prompt": "Create a README for a hello world project", "max_files": 3})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["files"], list)
    assert len(data["files"]) >= 1
    assert "path" in data["files"][0]
    assert "content" in data["files"][0]

