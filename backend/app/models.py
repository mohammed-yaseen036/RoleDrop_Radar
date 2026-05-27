import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


class SourceAdapter(str, enum.Enum):
    ASHBY = "ashby"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    GOOGLE = "google"


class ChannelType(str, enum.Enum):
    EMAIL = "email"
    TELEGRAM = "telegram"


class DeliveryStatus(str, enum.Enum):
    SENT = "sent"
    FAILED = "failed"
    SKIPPED_CONFIGURATION = "skipped_configuration"


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(320))
    skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    target_role_families: Mapped[list[str]] = mapped_column(JSON, default=list)
    education_level: Mapped[str | None] = mapped_column(String(255))
    experience_indicators: Mapped[list[str]] = mapped_column(JSON, default=list)
    preferred_locations: Mapped[list[str]] = mapped_column(JSON, default=list)
    remote_preference: Mapped[bool] = mapped_column(Boolean, default=True)
    eligibility_notes: Mapped[list[str]] = mapped_column(JSON, default=list)
    extracted_text_preview: Mapped[str | None] = mapped_column(Text)
    extraction_provider: Mapped[str] = mapped_column(String(40), default="deterministic")
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    company: Mapped[str] = mapped_column(String(200))
    adapter: Mapped[SourceAdapter] = mapped_column(Enum(SourceAdapter))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    is_catalog: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="source")
    postings: Mapped[list["JobPosting"]] = relationship(back_populates="source")


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("user_id", "source_id", name="uq_subscription_user_source"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_all_new_roles: Mapped[bool] = mapped_column(Boolean, default=False)
    initialized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    source: Mapped["Source"] = relationship(back_populates="subscriptions")
    matches: Mapped[list["MatchResult"]] = relationship(back_populates="subscription")


class JobPosting(Base):
    __tablename__ = "job_postings"
    __table_args__ = (UniqueConstraint("source_id", "external_id", name="uq_posting_source_external"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(255))
    identity_hash: Mapped[str] = mapped_column(String(64), index=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    company: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(500))
    location: Mapped[str | None] = mapped_column(String(500))
    employment_type: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    canonical_url: Mapped[str] = mapped_column(Text)
    apply_url: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    source: Mapped["Source"] = relationship(back_populates="postings")
    matches: Mapped[list["MatchResult"]] = relationship(back_populates="job_posting")


class MatchResult(Base):
    __tablename__ = "match_results"
    __table_args__ = (
        UniqueConstraint("subscription_id", "job_posting_id", name="uq_match_subscription_job"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("subscriptions.id"), index=True)
    job_posting_id: Mapped[str] = mapped_column(ForeignKey("job_postings.id"), index=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    verdict: Mapped[str] = mapped_column(String(40), default="review")
    eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    matched_skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    missing_requirements: Mapped[list[str]] = mapped_column(JSON, default=list)
    eligibility_warning: Mapped[str | None] = mapped_column(Text)
    notification_reason: Mapped[str] = mapped_column(Text, default="")
    provider: Mapped[str] = mapped_column(String(40), default="deterministic")
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    subscription: Mapped["Subscription"] = relationship(back_populates="matches")
    job_posting: Mapped["JobPosting"] = relationship(back_populates="matches")


class NotificationChannel(Base):
    __tablename__ = "notification_channels"
    __table_args__ = (UniqueConstraint("user_id", "channel_type", name="uq_user_channel_type"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    channel_type: Mapped[ChannelType] = mapped_column(Enum(ChannelType))
    destination: Mapped[str | None] = mapped_column(String(500))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    link_token_hash: Mapped[str | None] = mapped_column(String(64))
    link_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AlertDelivery(Base):
    __tablename__ = "alert_deliveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    match_result_id: Mapped[str] = mapped_column(ForeignKey("match_results.id"), index=True)
    channel_type: Mapped[ChannelType] = mapped_column(Enum(ChannelType))
    destination: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[DeliveryStatus] = mapped_column(Enum(DeliveryStatus))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MonitorRun(Base):
    __tablename__ = "monitor_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(40), default="running")
    jobs_seen: Mapped[int] = mapped_column(Integer, default=0)
    new_jobs: Mapped[int] = mapped_column(Integer, default=0)
    alerts_attempted: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)

