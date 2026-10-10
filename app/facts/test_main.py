"""Offline tests for the facts service.

All outbound HTTP (Wikipedia reads, counter POSTs) is mocked, so the suite
runs without network and without the counter service.
"""

from fastapi.testclient import TestClient

import main


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"fake HTTP {self.status_code}")


def summary_payload(extract, source_url):
    return {
        "extract": extract,
        "content_urls": {"desktop": {"page": source_url}},
    }


def counter_ok_response():
    return FakeResponse(200, {"words": 3, "characters": 12, "uniqueWords": 3})


def use_client():
    return TestClient(main.app)


# --- health ---------------------------------------------------------------


def test_health():
    response = use_client().get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# --- topic handling -------------------------------------------------------


def test_facts_without_topic_is_rejected():
    response = use_client().get("/facts")
    assert response.status_code == 400
    assert response.json() == {"error": "topic is required"}


def test_facts_with_whitespace_topic_is_rejected():
    response = use_client().get("/facts", params={"topic": "   "})
    assert response.status_code == 400
    assert response.json() == {"error": "topic is required"}


def test_facts_success(monkeypatch):
    monkeypatch.setattr(
        main.requests,
        "get",
        lambda *a, **k: FakeResponse(200, summary_payload("Octopuses are molluscs.", "https://en.wikipedia.org/wiki/Octopus")),
    )
    monkeypatch.setattr(main.requests, "post", lambda *a, **k: counter_ok_response())

    response = use_client().get("/facts", params={"topic": "octopus"})
    assert response.status_code == 200
    body = response.json()
    assert body["topic"] == "octopus"
    assert body["facts"] == "Octopuses are molluscs."
    assert body["sourceUrl"] == "https://en.wikipedia.org/wiki/Octopus"
    assert body["counts"] == {"words": 3, "characters": 12, "uniqueWords": 3}


def test_facts_topic_is_trimmed(monkeypatch):
    seen_urls = []

    def fake_get(url, *args, **kwargs):
        seen_urls.append(url)
        return FakeResponse(200, summary_payload("text", "https://source"))

    monkeypatch.setattr(main.requests, "get", fake_get)
    monkeypatch.setattr(main.requests, "post", lambda *a, **k: counter_ok_response())

    response = use_client().get("/facts", params={"topic": "  octopus  "})
    assert response.status_code == 200
    assert response.json()["topic"] == "octopus"
    # trimmed (and URL-encoded) before the upstream call — no raw spaces
    assert seen_urls == [main.SUMMARY_URL.format("octopus")]


def test_facts_opensearch_fallback(monkeypatch):
    """A summary miss is retried once with the title opensearch suggests."""

    def fake_get(url, *args, **kwargs):
        if "api.php" in url:  # opensearch
            return FakeResponse(200, ["octopus", ["Octopus"]])
        if "Octopus" in url:  # second summary attempt, now with the real title
            return FakeResponse(200, summary_payload("Eight-armed mollusc.", "https://en.wikipedia.org/wiki/Octopus"))
        return FakeResponse(404)  # first summary attempt misses

    monkeypatch.setattr(main.requests, "get", fake_get)
    monkeypatch.setattr(main.requests, "post", lambda *a, **k: counter_ok_response())

    response = use_client().get("/facts", params={"topic": "octopuss"})
    assert response.status_code == 200
    body = response.json()
    assert body["facts"] == "Eight-armed mollusc."
    assert body["sourceUrl"] == "https://en.wikipedia.org/wiki/Octopus"


def test_facts_total_miss_returns_template(monkeypatch):
    monkeypatch.setattr(main.requests, "get", lambda *a, **k: FakeResponse(404))
    monkeypatch.setattr(main.requests, "post", lambda *a, **k: counter_ok_response())

    response = use_client().get("/facts", params={"topic": "zzz"})
    assert response.status_code == 200
    body = response.json()
    assert body["facts"] == "No facts found for 'zzz'. Try another topic."
    assert body["sourceUrl"] is None


# --- counter wiring + degradation ------------------------------------------


def test_counter_url_env_is_honored(monkeypatch):
    posted = []

    def fake_post(url, *args, **kwargs):
        posted.append(url)
        return counter_ok_response()

    monkeypatch.setattr(main.requests, "post", fake_post)
    monkeypatch.setattr(
        main.requests,
        "get",
        lambda *a, **k: FakeResponse(200, summary_payload("some facts", "https://source")),
    )
    monkeypatch.setenv("COUNTER_URL", "http://counter-test:3999/")

    response = use_client().get("/facts", params={"topic": "x"})
    assert response.status_code == 200
    assert posted == ["http://counter-test:3999/count"]  # trailing slash stripped, /count appended


def test_counter_down_degrades_to_null_counts(monkeypatch):
    monkeypatch.setattr(
        main.requests,
        "get",
        lambda *a, **k: FakeResponse(200, summary_payload("some facts", "https://source")),
    )

    def broken_post(url, *args, **kwargs):
        raise ConnectionError("counter is down")

    monkeypatch.setattr(main.requests, "post", broken_post)

    response = use_client().get("/facts", params={"topic": "x"})
    assert response.status_code == 200  # counter failure must not fail /facts
    assert response.json()["counts"] is None
