from pathlib import Path


def _upload_profile(client, headers, monkeypatch):
    observed: list[Path] = []

    def fake_extract(path: Path) -> str:
        observed.append(path)
        assert path.exists()
        return (
            "B.Tech Computer Science student. Python FastAPI React REST API Docker. "
            "Built an AI LLM RAG project. Looking for remote India software engineering internships."
        )

    monkeypatch.setattr("app.services.resume.extract_text_from_pdf", fake_extract)
    response = client.post(
        "/api/profile/resume",
        headers=headers,
        files={"resume": ("resume.pdf", b"%PDF mocked resume bytes", "application/pdf")},
    )
    assert response.status_code == 200
    assert observed and not observed[0].exists(), "Uploaded resume must be deleted after extraction."
    return response.json()


def test_resume_extraction_requires_confirmation_and_is_tenant_scoped(client, user_headers, monkeypatch):
    profile = _upload_profile(client, user_headers, monkeypatch)
    assert profile["confirmed"] is False
    assert "python" in profile["skills"]

    rejected = client.post(
        "/api/subscriptions",
        headers=user_headers,
        json={"catalog_key": "openai-careers"},
    )
    assert rejected.status_code == 409

    profile["confirmed"] = True
    for field in ["id", "email", "extraction_provider", "extracted_at"]:
        profile.pop(field)
    confirmed = client.put("/api/profile", headers=user_headers, json=profile)
    assert confirmed.status_code == 200
    created = client.post(
        "/api/subscriptions",
        headers=user_headers,
        json={"catalog_key": "openai-careers"},
    )
    assert created.status_code == 201

    other_headers = {"X-Demo-User": "candidate-two", "X-Demo-Email": "other@example.com"}
    assert client.get("/api/subscriptions", headers=other_headers).json() == []
    assert client.get("/api/jobs", headers=other_headers).json() == []


def test_rejects_non_pdf_resume(client, user_headers):
    response = client.post(
        "/api/profile/resume",
        headers=user_headers,
        files={"resume": ("resume.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 415

