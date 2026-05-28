from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from .auth import CurrentUser, get_current_user
from .config import Settings, get_settings
from .db import Base, configure_database, get_db
from .models import (
    AlertDelivery,
    JobPosting,
    MatchResult,
    Profile,
    Source,
    Subscription,
)
from .schemas import (
    AlertResponse,
    JobResponse,
    MatchResponse,
    MonitorSummary,
    ProfileResponse,
    ProfileUpdate,
    SourceResponse,
    SubscriptionCreate,
    SubscriptionResponse,
    SubscriptionUpdate,
    TelegramLinkResponse,
)
from .services.intelligence import extract_profile
from .services.monitor import run_monitor
from .services.notifications import complete_telegram_link, create_telegram_link
from .services.resume import read_resume_pdf
from .services.sources import seed_catalog, source_from_official_url


def _source_response(source: Source) -> SourceResponse:
    return SourceResponse(
        id=source.id,
        key=source.key,
        company=source.company,
        adapter=source.adapter,
        config=source.config,
        is_catalog=source.is_catalog,
    )


def _profile_response(profile: Profile) -> ProfileResponse:
    return ProfileResponse(
        id=profile.id,
        email=profile.email,
        skills=profile.skills,
        target_role_families=profile.target_role_families,
        education_level=profile.education_level,
        experience_indicators=profile.experience_indicators,
        preferred_locations=profile.preferred_locations,
        remote_preference=profile.remote_preference,
        eligibility_notes=profile.eligibility_notes,
        confirmed=profile.confirmed,
        extraction_provider=profile.extraction_provider,
        extracted_at=profile.extracted_at,
    )


def _subscription_response(subscription: Subscription) -> SubscriptionResponse:
    return SubscriptionResponse(
        id=subscription.id,
        enabled=subscription.enabled,
        notify_all_new_roles=subscription.notify_all_new_roles,
        initialized_at=subscription.initialized_at,
        source=_source_response(subscription.source),
    )


def _match_response(match: MatchResult | None) -> MatchResponse | None:
    if not match:
        return None
    return MatchResponse(
        score=match.score,
        verdict=match.verdict,
        eligible=match.eligible,
        matched_skills=match.matched_skills,
        missing_requirements=match.missing_requirements,
        eligibility_warning=match.eligibility_warning,
        notification_reason=match.notification_reason,
        provider=match.provider,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_database(app, app_settings)
        Base.metadata.create_all(bind=app.state.engine)
        with app.state.session_factory() as db:
            seed_catalog(db)
        yield
        app.state.engine.dispose()

    app = FastAPI(
        title="RoleDrop Radar API",
        version="0.1.0",
        description="Resume-matched alerts for newly published roles from official sources.",
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    allowed_origins = [app_settings.frontend_url]
    if app_settings.is_development:
        allowed_origins.extend(["http://localhost:5173", "http://127.0.0.1:5173"])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(dict.fromkeys(allowed_origins)),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "service": "roledrop-radar"}

    @app.get("/api/profile", response_model=ProfileResponse | None)
    def get_profile(
        user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
    ):
        profile = db.scalar(select(Profile).where(Profile.user_id == user.id))
        return _profile_response(profile) if profile else None

    @app.post("/api/profile/resume", response_model=ProfileResponse)
    async def upload_resume(
        resume: UploadFile = File(...),
        user: CurrentUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        text = await read_resume_pdf(resume)
        extracted, provider = await extract_profile(text, app_settings)
        profile = db.scalar(select(Profile).where(Profile.user_id == user.id))
        if not profile:
            profile = Profile(user_id=user.id)
            db.add(profile)
        profile.email = user.email
        for field, value in extracted.model_dump().items():
            setattr(profile, field, value)
        profile.extracted_text_preview = text[:600]
        profile.extraction_provider = provider
        profile.confirmed = False
        profile.extracted_at = datetime.now().astimezone()
        db.commit()
        db.refresh(profile)
        return _profile_response(profile)

    @app.put("/api/profile", response_model=ProfileResponse)
    def update_profile(
        payload: ProfileUpdate,
        user: CurrentUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        profile = db.scalar(select(Profile).where(Profile.user_id == user.id))
        if not profile:
            raise HTTPException(status_code=404, detail="Upload a resume first.")
        for field, value in payload.model_dump().items():
            setattr(profile, field, value)
        profile.email = user.email or profile.email
        db.commit()
        db.refresh(profile)
        return _profile_response(profile)

    @app.get("/api/sources/catalog", response_model=list[SourceResponse])
    def catalog(
        _: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
    ):
        sources = db.scalars(select(Source).where(Source.is_catalog.is_(True)).order_by(Source.company))
        return [_source_response(source) for source in sources]

    @app.get("/api/subscriptions", response_model=list[SubscriptionResponse])
    def subscriptions(
        user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
    ):
        rows = db.scalars(
            select(Subscription)
            .where(Subscription.user_id == user.id)
            .options(joinedload(Subscription.source))
            .order_by(desc(Subscription.created_at))
        )
        return [_subscription_response(row) for row in rows]

    @app.post("/api/subscriptions", response_model=SubscriptionResponse, status_code=201)
    def create_subscription(
        payload: SubscriptionCreate,
        user: CurrentUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        profile = db.scalar(select(Profile).where(Profile.user_id == user.id))
        if not profile or not profile.confirmed:
            raise HTTPException(status_code=409, detail="Confirm your extracted profile before monitoring.")
        if bool(payload.catalog_key) == bool(payload.official_board_url):
            raise HTTPException(status_code=400, detail="Choose a catalog source or provide one official URL.")
        if payload.catalog_key:
            source = db.scalar(select(Source).where(Source.key == payload.catalog_key, Source.is_catalog.is_(True)))
            if not source:
                raise HTTPException(status_code=404, detail="Catalog source not found.")
        else:
            try:
                source_values = source_from_official_url(
                    str(payload.official_board_url), payload.company_name
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            source = db.scalar(select(Source).where(Source.key == source_values["key"]))
            if not source:
                source = Source(**source_values, is_catalog=False)
                db.add(source)
                db.flush()
        subscription = Subscription(
            user_id=user.id,
            source_id=source.id,
            notify_all_new_roles=payload.notify_all_new_roles,
        )
        db.add(subscription)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="You already monitor this source.") from exc
        db.refresh(subscription)
        subscription.source = source
        return _subscription_response(subscription)

    @app.patch("/api/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
    def update_subscription(
        subscription_id: str,
        payload: SubscriptionUpdate,
        user: CurrentUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        subscription = db.scalar(
            select(Subscription)
            .where(Subscription.id == subscription_id, Subscription.user_id == user.id)
            .options(joinedload(Subscription.source))
        )
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found.")
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(subscription, field, value)
        db.commit()
        db.refresh(subscription)
        return _subscription_response(subscription)

    @app.get("/api/jobs", response_model=list[JobResponse])
    def jobs(
        user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
    ):
        rows = db.execute(
            select(JobPosting, MatchResult)
            .join(Subscription, Subscription.source_id == JobPosting.source_id)
            .outerjoin(
                MatchResult,
                (MatchResult.job_posting_id == JobPosting.id)
                & (MatchResult.subscription_id == Subscription.id),
            )
            .where(Subscription.user_id == user.id)
            .order_by(desc(JobPosting.observed_at), desc(MatchResult.score))
        ).all()
        return [
            JobResponse(
                id=job.id,
                company=job.company,
                title=job.title,
                location=job.location,
                employment_type=job.employment_type,
                description=job.description,
                canonical_url=job.canonical_url,
                apply_url=job.apply_url,
                published_at=job.published_at,
                observed_at=job.observed_at,
                match=_match_response(match),
            )
            for job, match in rows
        ]

    @app.get("/api/alerts", response_model=list[AlertResponse])
    def alerts(
        user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
    ):
        rows = db.execute(
            select(AlertDelivery, MatchResult, JobPosting)
            .join(MatchResult, MatchResult.id == AlertDelivery.match_result_id)
            .join(JobPosting, JobPosting.id == MatchResult.job_posting_id)
            .where(AlertDelivery.user_id == user.id)
            .order_by(desc(AlertDelivery.created_at))
        ).all()
        return [
            AlertResponse(
                id=alert.id,
                job_title=job.title,
                company=job.company,
                score=match.score,
                channel_type=alert.channel_type,
                status=alert.status,
                error=alert.error,
                created_at=alert.created_at,
                sent_at=alert.sent_at,
            )
            for alert, match, job in rows
        ]

    @app.post("/api/integrations/telegram/link", response_model=TelegramLinkResponse)
    def telegram_link(
        user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
    ):
        token, expires = create_telegram_link(db, user.id, app_settings)
        start_url = (
            f"https://t.me/{app_settings.telegram_bot_username}?start={token}"
            if app_settings.telegram_bot_username
            else None
        )
        return TelegramLinkResponse(
            start_url=start_url,
            token=token,
            expires_at=expires,
            instructions="Open the bot link and press Start within 30 minutes to enable Telegram alerts.",
        )

    @app.post("/webhooks/telegram")
    def telegram_webhook(
        update: dict,
        x_telegram_bot_api_secret_token: str | None = Header(default=None),
        db: Session = Depends(get_db),
    ):
        if app_settings.telegram_webhook_secret and (
            x_telegram_bot_api_secret_token != app_settings.telegram_webhook_secret
        ):
            raise HTTPException(status_code=401, detail="Invalid webhook secret.")
        message = update.get("message") or {}
        chat_id = str((message.get("chat") or {}).get("id", ""))
        text = str(message.get("text", ""))
        if not chat_id or not text.startswith("/start "):
            return {"linked": False}
        linked = complete_telegram_link(db, text.split(" ", 1)[1].strip(), chat_id)
        return {"linked": linked}

    @app.post("/api/monitor/run", response_model=MonitorSummary)
    async def trigger_monitor(
        x_monitor_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None),
        x_demo_user: str | None = Header(default=None),
        db: Session = Depends(get_db),
    ):
        is_frontend_session = bool(authorization or x_demo_user)
        if app_settings.monitor_api_key and x_monitor_key != app_settings.monitor_api_key and not is_frontend_session:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid monitor key.")
        if not app_settings.monitor_api_key and not app_settings.is_development and not is_frontend_session:
            raise HTTPException(status_code=503, detail="Monitor execution is not configured.")
        return await run_monitor(db, app_settings)

    return app


app = create_app()
