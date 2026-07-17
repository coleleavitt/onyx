#!/usr/bin/env python3
"""Layered diagnostic for the SharePoint internal-search pipeline.

Checks each layer in dependency order so a failure pinpoints the broken
component instead of just reporting "no results":

1. indexed-sources reports sharepoint      -> connector/indexing bookkeeping
2. admin keyword search returns docs       -> OpenSearch index + keyword retrieval
3. model server /api/health on :9000       -> query embedding service
4. /api/search with sharepoint filter      -> full SearchTool pipeline (embedding
                                              + hybrid retrieval + filters)

Layer 4 failing while 1-3 pass means a real search-pipeline regression.
Layer 3 failing reproduces the 2026-07-16 outage where chat showed
"No results found" because the model server on port 9000 was down.
"""
from __future__ import annotations

import os

import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:3000").rstrip("/")
MODEL_SERVER_URL = os.environ.get("MODEL_SERVER_URL", "http://127.0.0.1:9000")
USER_EMAIL = os.environ["EMAIL"]
USER_PASSWORD = os.environ["PASSWORD"]
HOLIDAY_QUERY = "what is my next company holiday?"


def login(email: str, password: str) -> requests.Session:
    session = requests.Session()
    response = session.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": email, "password": password},
        timeout=20,
    )
    assert response.status_code == 204, response.text
    return session


def main() -> None:
    session = login(USER_EMAIL, USER_PASSWORD)

    # Layer 1: connector bookkeeping says sharepoint is indexed
    response = session.get(f"{BASE_URL}/api/manage/indexed-sources", timeout=20)
    assert response.ok, f"indexed-sources -> {response.status_code}: {response.text[:300]}"
    sources = response.json()["sources"]
    assert "sharepoint" in sources, (
        f"LAYER 1 FAILED (connector/indexing): sharepoint not in indexed sources "
        f"{sources}. Check the sharepoint connector and index attempts."
    )

    # Layer 2: keyword retrieval straight against the document index
    response = session.post(
        f"{BASE_URL}/api/admin/search",
        json={"query": "holiday", "filters": {"source_type": ["sharepoint"]}},
        timeout=60,
    )
    assert response.ok, (
        f"LAYER 2 FAILED (document index): admin/search -> {response.status_code}: "
        f"{response.text[:300]}"
    )
    documents = response.json()["documents"]
    assert documents, (
        "LAYER 2 FAILED (document index): keyword retrieval returned no sharepoint "
        "docs for 'holiday'. Chunks are missing or filtered out in OpenSearch."
    )

    # Layer 3: the query-embedding model server must be up
    try:
        health = requests.get(f"{MODEL_SERVER_URL}/api/health", timeout=10)
        model_server_ok = health.ok
    except requests.RequestException:
        model_server_ok = False
    assert model_server_ok, (
        f"LAYER 3 FAILED (model server): {MODEL_SERVER_URL}/api/health unreachable. "
        "Chat search embeds queries through this service; when it is down the "
        "search tool silently reports 'No results found'. Restart it with: "
        "cd backend && .venv/bin/uvicorn model_server.main:app --port 9000"
    )

    # Layer 4: the full SearchTool pipeline (same path the chat tool uses)
    response = session.post(
        f"{BASE_URL}/api/search",
        json={"query": HOLIDAY_QUERY, "sources": ["sharepoint"]},
        timeout=150,
    )
    assert response.ok, (
        f"LAYER 4 FAILED (search pipeline): /api/search -> {response.status_code}: "
        f"{response.text[:300]}"
    )
    results = response.json()["results"]
    assert results, (
        "LAYER 4 FAILED (search pipeline): /api/search returned zero results for a "
        "sharepoint-filtered holiday query even though layers 1-3 are healthy. "
        "Debug SearchTool / SearchPipeline filter construction."
    )
    assert any(r["source_type"] == "sharepoint" for r in results), (
        f"LAYER 4 FAILED: results are not from sharepoint: "
        f"{[r['source_type'] for r in results]}"
    )

    print(
        f"sharepoint search diagnostic passed: {len(documents)} keyword docs, "
        f"{len(results)} pipeline results"
    )


if __name__ == "__main__":
    main()
