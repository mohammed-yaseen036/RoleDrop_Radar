from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl

from .models import ChannelType, DeliveryStatus, SourceAdapter


class ProfileData(BaseModel):
    skills: list[str] = Field(default_factory=list)
    target_role_families: list[str] = Field(default_factory=list)
    education_level: str | None = None
    experience_indicators: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    remote_preference: bool = True
    eligibility_notes: list[str] = Field(default_factory=list)


class ProfileResponse(ProfileData):
    id: str
    email: str | None
    confirmed: bool
    extraction_provider: str
    extracted_at: datetime


class ProfileUpdate(ProfileData):
    confirmed: bool = True


class SourceResponse(BaseModel):
    id: str
    key: str
    company: str
    adapter: SourceAdapter
    config: dict
    is_catalog: bool


class SubscriptionCreate(BaseModel):
    catalog_key: str | None = None
    official_board_url: HttpUrl | None = None
    company_name: str | None = Field(default=None, max_length=200)
    notify_all_new_roles: bool = False


class SubscriptionUpdate(BaseModel):
    enabled: bool | None = None
    notify_all_new_roles: bool | None = None


class SubscriptionResponse(BaseModel):
    id: str
    enabled: bool
    notify_all_new_roles: bool
    initialized_at: datetime | None
    source: SourceResponse


class MatchResponse(BaseModel):
    score: int
    verdict: str
    eligible: bool
    matched_skills: list[str]
    missing_requirements: list[str]
    eligibility_warning: str | None
    notification_reason: str
    provider: str


class JobResponse(BaseModel):
    id: str
    company: str
    title: str
    location: str | None
    employment_type: str | None
    description: str | None
    canonical_url: str
    apply_url: str
    published_at: datetime | None
    observed_at: datetime
    match: MatchResponse | None


class TelegramLinkResponse(BaseModel):
    start_url: str | None
    token: str
    expires_at: datetime
    instructions: str


class AlertResponse(BaseModel):
    id: str
    job_title: str
    company: str
    score: int
    channel_type: ChannelType
    status: DeliveryStatus
    error: str | None
    created_at: datetime
    sent_at: datetime | None


class MonitorSummary(BaseModel):
    sources_checked: int = 0
    jobs_seen: int = 0
    new_jobs: int = 0
    alerts_attempted: int = 0
    failed_sources: list[str] = Field(default_factory=list)

