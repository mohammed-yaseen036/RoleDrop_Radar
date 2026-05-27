import httpx
import pytest

from app.models import Source, SourceAdapter
from app.services.sources import AshbyAdapter, source_from_official_url


def test_recognizes_supported_official_board_urls():
    ashby = source_from_official_url("https://jobs.ashbyhq.com/openai", "OpenAI")
    greenhouse = source_from_official_url("https://boards.greenhouse.io/example", "Example")
    lever = source_from_official_url("https://jobs.lever.co/acme", "Acme")

    assert ashby["adapter"] == SourceAdapter.ASHBY and ashby["config"]["board_name"] == "openai"
    assert greenhouse["adapter"] == SourceAdapter.GREENHOUSE
    assert lever["adapter"] == SourceAdapter.LEVER


def test_rejects_arbitrary_crawler_url():
    with pytest.raises(ValueError):
        source_from_official_url("https://www.linkedin.com/jobs/search/")


@pytest.mark.asyncio
async def test_ashby_adapter_normalizes_public_payload():
    payload = {
        "jobs": [
            {
                "title": "Software Engineering Intern",
                "location": "India",
                "employmentType": "Intern",
                "descriptionPlain": "Build Python APIs.",
                "publishedAt": "2026-05-25T10:00:00Z",
                "jobUrl": "https://jobs.ashbyhq.com/acme/abc",
                "applyUrl": "https://jobs.ashbyhq.com/acme/abc/application",
                "isListed": True,
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert "posting-api/job-board/acme" in str(request.url)
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        source = Source(key="acme", company="Acme", adapter=SourceAdapter.ASHBY, config={"board_name": "acme"})
        jobs = await AshbyAdapter(client).fetch(source)

    assert jobs[0].external_id == "abc"
    assert jobs[0].company == "Acme"
    assert jobs[0].published_at is not None

