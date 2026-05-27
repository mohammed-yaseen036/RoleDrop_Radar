import json
import re
from collections import OrderedDict

import httpx
from pydantic import BaseModel, Field

from ..config import Settings
from ..models import JobPosting, Profile
from ..schemas import ProfileData


KNOWN_SKILLS = [
    "python",
    "fastapi",
    "flask",
    "react",
    "typescript",
    "javascript",
    "sql",
    "postgresql",
    "mongodb",
    "docker",
    "aws",
    "gcp",
    "machine learning",
    "deep learning",
    "pytorch",
    "tensorflow",
    "llm",
    "rag",
    "nlp",
    "git",
    "rest api",
]

ROLE_TERMS = {
    "Backend Engineering": ["backend", "api", "fastapi", "flask", "python"],
    "Full-Stack Engineering": ["full stack", "full-stack", "react", "typescript"],
    "AI/ML Engineering": ["ai", "machine learning", "ml", "deep learning", "nlp", "llm", "rag"],
    "GenAI/LLM Engineering": ["llm", "rag", "generative ai", "genai"],
    "Software Engineering": ["software engineer", "developer", "programming"],
}


class MatchAssessment(BaseModel):
    score: int = Field(ge=0, le=100)
    verdict: str
    eligible: bool
    matched_skills: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    eligibility_warning: str | None = None
    notification_reason: str
    provider: str = "deterministic"


def _unique(values: list[str]) -> list[str]:
    return list(OrderedDict.fromkeys(value for value in values if value))


def deterministic_profile(text: str) -> ProfileData:
    lowered = text.lower()
    skills = [skill for skill in KNOWN_SKILLS if skill in lowered]
    roles = [
        role
        for role, indicators in ROLE_TERMS.items()
        if any(indicator in lowered for indicator in indicators)
    ]
    locations = [
        location
        for location in ["Hyderabad", "Bengaluru", "India", "Remote"]
        if location.lower() in lowered
    ]
    education = "B.Tech / Computer Science student" if re.search(r"b\.?\s*tech|computer science|cse", lowered) else None
    indicators = []
    if "leetcode" in lowered:
        indicators.append("Data structures and algorithms practice")
    if "github" in lowered:
        indicators.append("Project portfolio available")
    return ProfileData(
        skills=_unique(skills),
        target_role_families=roles or ["Software Engineering", "AI/ML Engineering"],
        education_level=education,
        experience_indicators=indicators,
        preferred_locations=locations or ["India", "Remote"],
        remote_preference="remote" in lowered or not locations,
        eligibility_notes=["Verify graduation-year and work-authorization requirements per role."],
    )


async def _gemini_structured(
    settings: Settings,
    prompt: str,
    schema: dict,
) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": schema,
            "temperature": 0.1,
        },
    }
    headers = {"x-goog-api-key": settings.gemini_api_key or ""}
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(url, json=payload, headers=headers)
    response.raise_for_status()
    text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)


async def _ollama_json(settings: Settings, prompt: str) -> dict:
    payload = {"model": settings.ollama_model, "prompt": prompt, "format": "json", "stream": False}
    # Lower connection timeout to 1.2s to failover instantly if Ollama is not active
    timeout = httpx.Timeout(10.0, connect=1.2)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(f"{settings.ollama_base_url}/api/generate", json=payload)
    response.raise_for_status()
    return json.loads(response.json()["response"])


async def extract_profile(text: str, settings: Settings) -> tuple[ProfileData, str]:
    prompt = (
        "Extract a candidate profile from this resume. Return concise skills and suitable early-career "
        "role families. Do not invent experience or eligibility. Resume:\n\n" + text[:14000]
    )
    if settings.gemini_api_key:
        try:
            return ProfileData.model_validate(
                await _gemini_structured(settings, prompt, ProfileData.model_json_schema())
            ), "gemini"
        except Exception:
            pass
    if settings.enable_ollama:
        try:
            return ProfileData.model_validate(await _ollama_json(settings, prompt)), "ollama"
        except Exception:
            pass
    return deterministic_profile(text), "deterministic"


def deterministic_match(profile: Profile, job: JobPosting) -> MatchAssessment:
    searchable = f"{job.title} {job.description or ''}".lower()
    title = job.title.lower()
    profile_skills = [skill.lower() for skill in profile.skills]
    matched = [skill for skill in profile.skills if skill.lower() in searchable]
    senior = any(word in title for word in ["senior", "staff", "principal", "manager", "lead "])
    student_role = any(word in title for word in ["intern", "graduate", "new grad", "entry", "associate"])
    role_hit = any(
        role.lower().split("/")[0].replace(" engineering", "") in searchable
        for role in profile.target_role_families
    )
    location_text = (job.location or "").lower()
    location_hit = not profile.preferred_locations or any(
        place.lower() in location_text or place.lower() == "remote" and "remote" in location_text
        for place in profile.preferred_locations
    )
    if not job.location:
        location_hit = True

    score = min(55, len(matched) * 12) + (20 if role_hit else 0) + (15 if student_role else 0)
    score += 10 if location_hit else -15
    warning = None
    eligible = True
    if senior:
        score = min(score, 35)
        warning = "Role appears senior-level for an early-career profile."
        eligible = False
    elif not location_hit:
        warning = "Role location does not match current preferences."
        eligible = False
    elif not student_role and score < 55:
        warning = "Review experience and graduation requirements before applying."

    score = max(0, min(100, score))
    if eligible and score >= 75:
        verdict = "high_fit"
    elif eligible and score >= 50:
        verdict = "review"
    else:
        verdict = "low_fit"
    reason = (
        f"Matches {', '.join(matched[:4]) or 'your target role interests'}"
        + (" and appears suitable for early-career applicants." if student_role else ".")
    )
    return MatchAssessment(
        score=score,
        verdict=verdict,
        eligible=eligible,
        matched_skills=matched,
        missing_requirements=[] if matched else profile_skills[:3],
        eligibility_warning=warning,
        notification_reason=reason,
    )


async def assess_match(
    profile: Profile, job: JobPosting, settings: Settings, allow_ai: bool = True
) -> MatchAssessment:
    fallback = deterministic_match(profile, job)
    if not allow_ai or not fallback.eligible or fallback.score < 35 or not settings.gemini_api_key:
        return fallback
    prompt = (
        "Evaluate an early-career candidate against a job. Be conservative about eligibility. "
        "Use 0-100 score, verdict high_fit/review/low_fit, and do not claim guaranteed selection.\n"
        f"Candidate profile: skills={profile.skills}; role families={profile.target_role_families}; "
        f"education={profile.education_level}; preferences={profile.preferred_locations}\n"
        f"Job: {job.title}; location={job.location}; type={job.employment_type}; "
        f"description={(job.description or '')[:7000]}"
    )
    try:
        assessment = MatchAssessment.model_validate(
            await _gemini_structured(settings, prompt, MatchAssessment.model_json_schema())
        )
        assessment.provider = "gemini"
        return assessment
    except Exception:
        return fallback
