import hashlib
import re
from datetime import datetime
from urllib.parse import parse_qs, quote, urlparse

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Source, SourceAdapter


class NormalizedJob(BaseModel):
    external_id: str
    company: str
    title: str
    location: str | None = None
    employment_type: str | None = None
    description: str | None = None
    canonical_url: str
    apply_url: str
    published_at: datetime | None = None

    @property
    def identity_hash(self) -> str:
        return hashlib.sha256(self.canonical_url.encode("utf-8")).hexdigest()

    @property
    def content_hash(self) -> str:
        content = "|".join(
            [
                self.title,
                self.location or "",
                self.employment_type or "",
                self.description or "",
                self.apply_url,
            ]
        )
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _datetime_or_none(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class BaseAdapter:
    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client

    async def fetch(self, source: Source) -> list[NormalizedJob]:
        raise NotImplementedError

    async def _get(self, url: str) -> httpx.Response:
        if self.client:
            response = await self.client.get(url)
        else:
            async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
                response = await client.get(url)
        response.raise_for_status()
        return response


class AshbyAdapter(BaseAdapter):
    async def fetch(self, source: Source) -> list[NormalizedJob]:
        board = source.config["board_name"]
        url = f"https://api.ashbyhq.com/posting-api/job-board/{quote(board)}"
        jobs = self._jobs_from_payload((await self._get(url)).json(), source.company)
        return jobs

    @staticmethod
    def _jobs_from_payload(payload: dict, company: str) -> list[NormalizedJob]:
        results = []
        for job in payload.get("jobs", []):
            if job.get("isListed") is False:
                continue
            apply_url = job.get("applyUrl") or job.get("jobUrl")
            canonical_url = job.get("jobUrl") or apply_url
            if not canonical_url or not apply_url:
                continue
            external_id = canonical_url.rstrip("/").split("/")[-1]
            results.append(
                NormalizedJob(
                    external_id=external_id,
                    company=company,
                    title=job.get("title", "Untitled role"),
                    location=job.get("location"),
                    employment_type=job.get("employmentType"),
                    description=job.get("descriptionPlain"),
                    canonical_url=canonical_url,
                    apply_url=apply_url,
                    published_at=_datetime_or_none(job.get("publishedAt")),
                )
            )
        return results


class GreenhouseAdapter(BaseAdapter):
    async def fetch(self, source: Source) -> list[NormalizedJob]:
        token = source.config["board_token"]
        url = f"https://boards-api.greenhouse.io/v1/boards/{quote(token)}/jobs?content=true"
        payload = (await self._get(url)).json()
        return [
            NormalizedJob(
                external_id=str(job["id"]),
                company=source.company,
                title=job.get("title", "Untitled role"),
                location=(job.get("location") or {}).get("name"),
                description=BeautifulSoup(job.get("content", ""), "html.parser").get_text(" ", strip=True),
                canonical_url=job["absolute_url"],
                apply_url=job["absolute_url"],
                published_at=_datetime_or_none(job.get("updated_at")),
            )
            for job in payload.get("jobs", [])
            if job.get("absolute_url")
        ]


class LeverAdapter(BaseAdapter):
    async def fetch(self, source: Source) -> list[NormalizedJob]:
        site = source.config["site"]
        url = f"https://api.lever.co/v0/postings/{quote(site)}?mode=json"
        payload = (await self._get(url)).json()
        results = []
        for job in payload:
            canonical = job.get("hostedUrl") or job.get("applyUrl")
            apply_url = job.get("applyUrl") or canonical
            if not canonical or not apply_url:
                continue
            categories = job.get("categories") or {}
            description = BeautifulSoup(job.get("descriptionPlain") or job.get("description", ""), "html.parser").get_text(" ", strip=True)
            results.append(
                NormalizedJob(
                    external_id=str(job.get("id") or canonical.rstrip("/").split("/")[-1]),
                    company=source.company,
                    title=job.get("text", "Untitled role"),
                    location=categories.get("location"),
                    employment_type=categories.get("commitment"),
                    description=description,
                    canonical_url=canonical,
                    apply_url=apply_url,
                )
            )
        return results


class GoogleCareersAdapter(BaseAdapter):
    """Best-effort official-page adapter; failures are surfaced without bypass attempts."""

    async def fetch(self, source: Source) -> list[NormalizedJob]:
        query = quote(source.config.get("query", "software engineer intern"))
        url = f"https://www.google.com/about/careers/applications/jobs/results?q={query}"
        response = await self._get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        results: list[NormalizedJob] = []
        seen: set[str] = set()
        for link in soup.select('a[href*="/jobs/results/"]'):
            href = link.get("href", "")
            title = link.get_text(" ", strip=True)
            if not title or href in seen:
                continue
            seen.add(href)
            canonical = href if href.startswith("http") else f"https://www.google.com{href}"
            external_id = canonical.split("/jobs/results/", 1)[-1].split("-", 1)[0]
            results.append(
                NormalizedJob(
                    external_id=external_id or hashlib.sha256(canonical.encode()).hexdigest(),
                    company=source.company,
                    title=title,
                    canonical_url=canonical,
                    apply_url=canonical,
                )
            )
        return results


ADAPTERS = {
    SourceAdapter.ASHBY: AshbyAdapter,
    SourceAdapter.GREENHOUSE: GreenhouseAdapter,
    SourceAdapter.LEVER: LeverAdapter,
    SourceAdapter.GOOGLE: GoogleCareersAdapter,
}


CATALOG = [
    {
        "key": "openai-careers",
        "company": "OpenAI",
        "adapter": SourceAdapter.ASHBY,
        "config": {"board_name": "openai"},
    },
    {
        "key": "anthropic-careers",
        "company": "Anthropic",
        "adapter": SourceAdapter.GREENHOUSE,
        "config": {"board_token": "anthropic"},
    },
    {
        "key": "perplexity-careers",
        "company": "Perplexity",
        "adapter": SourceAdapter.GREENHOUSE,
        "config": {"board_token": "perplexity"},
    },
    {
        "key": "scaleai-careers",
        "company": "Scale AI",
        "adapter": SourceAdapter.GREENHOUSE,
        "config": {"board_token": "scaleai"},
    },
    {
        "key": "cohere-careers",
        "company": "Cohere",
        "adapter": SourceAdapter.GREENHOUSE,
        "config": {"board_token": "cohere"},
    },
    {
        "key": "elevenlabs-careers",
        "company": "ElevenLabs",
        "adapter": SourceAdapter.LEVER,
        "config": {"site": "elevenlabs"},
    },
    {
        "key": "huggingface-careers",
        "company": "Hugging Face",
        "adapter": SourceAdapter.GREENHOUSE,
        "config": {"board_token": "huggingface"},
    },
    {
        "key": "characterai-careers",
        "company": "Character.ai",
        "adapter": SourceAdapter.GREENHOUSE,
        "config": {"board_token": "characterai"},
    },
    {
        "key": "google-careers-india-software",
        "company": "Google",
        "adapter": SourceAdapter.GOOGLE,
        "config": {"query": "software engineer intern India"},
    },
]


def seed_catalog(db: Session) -> None:
    for item in CATALOG:
        existing = db.scalar(select(Source).where(Source.key == item["key"]))
        if not existing:
            db.add(Source(**item, is_catalog=True))
    db.commit()


def source_from_official_url(url: str, company_name: str | None = None) -> dict:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    parts = [part for part in parsed.path.split("/") if part]
    company = company_name or (parts[0].replace("-", " ").title() if parts else host)
    if host in {"jobs.ashbyhq.com", "api.ashbyhq.com"}:
        board = parts[-1] if "job-board" in parts else (parts[0] if parts else None)
        if not board:
            raise ValueError("Ashby board URL does not include a board name.")
        return {
            "key": f"ashby:{board.lower()}",
            "company": company,
            "adapter": SourceAdapter.ASHBY,
            "config": {"board_name": board},
        }
    if "greenhouse.io" in host:
        if not parts:
            raise ValueError("Greenhouse board URL does not include a board token.")
        token = parts[0] if parts[0] != "v1" else parts[2]
        return {
            "key": f"greenhouse:{token.lower()}",
            "company": company,
            "adapter": SourceAdapter.GREENHOUSE,
            "config": {"board_token": token},
        }
    if host == "jobs.lever.co" or host == "api.lever.co":
        if not parts:
            raise ValueError("Lever URL does not include a company site name.")
        site = parts[-1] if "postings" in parts else parts[0]
        return {
            "key": f"lever:{site.lower()}",
            "company": company,
            "adapter": SourceAdapter.LEVER,
            "config": {"site": site},
        }
    if "google.com" in host and "/careers/" in parsed.path:
        query = parse_qs(parsed.query).get("q", ["software engineer intern"])[0]
        return {
            "key": f"google:{hashlib.sha256(query.encode()).hexdigest()[:12]}",
            "company": company_name or "Google",
            "adapter": SourceAdapter.GOOGLE,
            "config": {"query": query},
        }
    raise ValueError("Supported official sources are Ashby, Greenhouse, Lever and Google Careers.")


def adapter_for(source: Source, client: httpx.AsyncClient | None = None) -> BaseAdapter:
    return ADAPTERS[source.adapter](client=client)

