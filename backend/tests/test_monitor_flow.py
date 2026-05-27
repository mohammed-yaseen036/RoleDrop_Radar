from app.services.intelligence import deterministic_match
from app.services.sources import NormalizedJob


def _set_up_candidate(client, headers, monkeypatch):
    monkeypatch.setattr(
        "app.services.resume.extract_text_from_pdf",
        lambda _: (
            "B.Tech Computer Science Python FastAPI React Docker LLM RAG. "
            "Backend Engineering Intern seeking India and remote roles."
        ),
    )
    profile = client.post(
        "/api/profile/resume",
        headers=headers,
        files={"resume": ("resume.pdf", b"%PDF candidate", "application/pdf")},
    ).json()
    payload = {
        "skills": ["Python", "FastAPI", "React"],
        "target_role_families": ["Backend Engineering"],
        "education_level": "B.Tech student",
        "experience_indicators": [],
        "preferred_locations": ["India", "Remote"],
        "remote_preference": True,
        "eligibility_notes": [],
        "confirmed": True,
    }
    assert client.put("/api/profile", headers=headers, json=payload).status_code == 200
    assert client.post("/api/subscriptions", headers=headers, json={"catalog_key": "openai-careers"}).status_code == 201


def test_first_scan_is_silent_then_new_high_fit_job_creates_delivery(client, user_headers, monkeypatch):
    _set_up_candidate(client, user_headers, monkeypatch)
    job_one = NormalizedJob(
        external_id="existing",
        company="OpenAI",
        title="Backend Engineering Intern",
        location="India",
        description="Python FastAPI React internship",
        canonical_url="https://jobs.ashbyhq.com/openai/existing",
        apply_url="https://jobs.ashbyhq.com/openai/existing/application",
    )
    job_two = NormalizedJob(
        external_id="fresh",
        company="OpenAI",
        title="Backend Engineering Intern",
        location="India",
        description="Python FastAPI React internship for new graduates",
        canonical_url="https://jobs.ashbyhq.com/openai/fresh",
        apply_url="https://jobs.ashbyhq.com/openai/fresh/application",
    )
    visible = [job_one]

    class StubAdapter:
        async def fetch(self, source):
            return list(visible)

    allow_ai_values = []

    async def capture_assessment(profile, job, settings, allow_ai=True):
        allow_ai_values.append(allow_ai)
        return deterministic_match(profile, job)

    monkeypatch.setattr("app.services.monitor.adapter_for", lambda source: StubAdapter())
    monkeypatch.setattr("app.services.monitor.assess_match", capture_assessment)
    first = client.post("/api/monitor/run").json()
    assert first["new_jobs"] == 1
    assert client.get("/api/alerts", headers=user_headers).json() == []
    assert allow_ai_values == [False]

    visible.append(job_two)
    second = client.post("/api/monitor/run").json()
    alerts = client.get("/api/alerts", headers=user_headers).json()
    assert second["new_jobs"] == 1
    assert len(alerts) == 1
    assert alerts[0]["status"] == "skipped_configuration"
    assert alerts[0]["channel_type"] == "email"
    jobs = client.get("/api/jobs", headers=user_headers).json()
    assert len(jobs) == 2
    assert jobs[0]["match"]["score"] >= 75
    assert allow_ai_values == [False, True]
