from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..config import Settings
from ..models import JobPosting, MatchResult, MonitorRun, Profile, Source, Subscription, utcnow
from ..schemas import MonitorSummary
from .intelligence import assess_match
from .notifications import dispatch_alerts
from .sources import NormalizedJob, adapter_for


def upsert_job(db: Session, source: Source, incoming: NormalizedJob) -> tuple[JobPosting, bool, bool]:
    job = db.scalar(
        select(JobPosting).where(
            JobPosting.source_id == source.id,
            JobPosting.external_id == incoming.external_id,
        )
    )
    if not job:
        job = JobPosting(
            source_id=source.id,
            external_id=incoming.external_id,
            identity_hash=incoming.identity_hash,
            content_hash=incoming.content_hash,
            company=incoming.company,
            title=incoming.title,
            location=incoming.location,
            employment_type=incoming.employment_type,
            description=incoming.description,
            canonical_url=incoming.canonical_url,
            apply_url=incoming.apply_url,
            published_at=incoming.published_at,
        )
        db.add(job)
        db.flush()
        return job, True, False
    changed = job.content_hash != incoming.content_hash
    if changed:
        job.content_hash = incoming.content_hash
        job.title = incoming.title
        job.location = incoming.location
        job.employment_type = incoming.employment_type
        job.description = incoming.description
        job.canonical_url = incoming.canonical_url
        job.apply_url = incoming.apply_url
        job.published_at = incoming.published_at
        job.updated_at = utcnow()
    return job, False, changed


async def _evaluate(
    db: Session,
    settings: Settings,
    subscription: Subscription,
    job: JobPosting,
    allow_ai: bool = True,
) -> MatchResult | None:
    profile = db.scalar(
        select(Profile).where(Profile.user_id == subscription.user_id, Profile.confirmed.is_(True))
    )
    if not profile:
        return None
    assessment = await assess_match(profile, job, settings, allow_ai=allow_ai)
    match = db.scalar(
        select(MatchResult).where(
            MatchResult.subscription_id == subscription.id,
            MatchResult.job_posting_id == job.id,
        )
    )
    values = assessment.model_dump()
    if not match:
        match = MatchResult(
            user_id=subscription.user_id,
            subscription_id=subscription.id,
            job_posting_id=job.id,
            **values,
        )
        db.add(match)
    else:
        for key, value in values.items():
            setattr(match, key, value)
        match.evaluated_at = utcnow()
    db.flush()
    return match


async def run_monitor(db: Session, settings: Settings) -> MonitorSummary:
    summary = MonitorSummary()
    sources = list(
        db.scalars(
            select(Source)
            .join(Subscription)
            .where(Subscription.enabled.is_(True))
            .distinct()
        )
    )
    for source in sources:
        summary.sources_checked += 1
        run = MonitorRun(source_id=source.id)
        db.add(run)
        db.commit()
        try:
            incoming_jobs = await adapter_for(source).fetch(source)
            summary.jobs_seen += len(incoming_jobs)
            run.jobs_seen = len(incoming_jobs)
            subscriptions = list(
                db.scalars(
                    select(Subscription)
                    .where(Subscription.source_id == source.id, Subscription.enabled.is_(True))
                    .options(joinedload(Subscription.source))
                )
            )
            first_sync_ids = {sub.id for sub in subscriptions if sub.initialized_at is None}
            for incoming in incoming_jobs:
                job, is_new, changed = upsert_job(db, source, incoming)
                if is_new:
                    summary.new_jobs += 1
                    run.new_jobs += 1
                for subscription in subscriptions:
                    first_sync = subscription.id in first_sync_ids
                    if not first_sync and not is_new and not changed:
                        continue
                    match = await _evaluate(db, settings, subscription, job, allow_ai=not first_sync)
                    if not match or first_sync or (not is_new and not changed):
                        continue
                    should_alert = subscription.notify_all_new_roles or (
                        match.eligible and match.score >= settings.alert_score_threshold
                    )
                    if should_alert:
                        attempted = await dispatch_alerts(db, settings, match)
                        summary.alerts_attempted += attempted
                        run.alerts_attempted += attempted
            for subscription in subscriptions:
                if subscription.id in first_sync_ids:
                    subscription.initialized_at = utcnow()
            run.status = "completed"
            run.completed_at = utcnow()
            db.commit()
        except Exception as exc:
            db.rollback()
            run = db.get(MonitorRun, run.id)
            run.status = "failed"
            run.error = str(exc)[:1000]
            run.completed_at = utcnow()
            db.commit()
            summary.failed_sources.append(source.company)
    return summary
