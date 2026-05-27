from app.models import JobPosting, Profile
from app.services.intelligence import deterministic_match, deterministic_profile


def test_deterministic_profile_extracts_early_career_signals():
    result = deterministic_profile("B.Tech CSE Python FastAPI React LLM RAG Docker Remote India")
    assert "python" in result.skills
    assert "AI/ML Engineering" in result.target_role_families
    assert result.remote_preference is True


def test_senior_role_is_not_urgent_for_student_profile():
    profile = Profile(
        user_id="one",
        skills=["Python", "FastAPI", "React"],
        target_role_families=["Backend Engineering"],
        preferred_locations=["India"],
    )
    job = JobPosting(
        source_id="source",
        external_id="one",
        identity_hash="a",
        content_hash="b",
        company="Acme",
        title="Senior Backend Engineer",
        location="India",
        description="Python FastAPI React",
        canonical_url="https://example.test/job",
        apply_url="https://example.test/job/apply",
    )
    result = deterministic_match(profile, job)
    assert result.eligible is False
    assert result.score <= 35

