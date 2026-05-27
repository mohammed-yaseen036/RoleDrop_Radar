import hashlib
import secrets
import smtplib
from datetime import timedelta
from email.message import EmailMessage

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import (
    AlertDelivery,
    ChannelType,
    DeliveryStatus,
    MatchResult,
    NotificationChannel,
    Profile,
    utcnow,
)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_telegram_link(db: Session, user_id: str, settings: Settings) -> tuple[str, object]:
    token = secrets.token_urlsafe(24)
    expires = utcnow() + timedelta(minutes=30)
    channel = db.scalar(
        select(NotificationChannel).where(
            NotificationChannel.user_id == user_id,
            NotificationChannel.channel_type == ChannelType.TELEGRAM,
        )
    )
    if not channel:
        channel = NotificationChannel(user_id=user_id, channel_type=ChannelType.TELEGRAM)
        db.add(channel)
    channel.link_token_hash = token_hash(token)
    channel.link_token_expires_at = expires
    channel.verified_at = None
    channel.destination = None
    db.commit()
    return token, expires


def complete_telegram_link(db: Session, token: str, chat_id: str) -> bool:
    channel = db.scalar(
        select(NotificationChannel).where(
            NotificationChannel.link_token_hash == token_hash(token),
            NotificationChannel.channel_type == ChannelType.TELEGRAM,
        )
    )
    if not channel or not channel.link_token_expires_at or channel.link_token_expires_at < utcnow():
        return False
    channel.destination = chat_id
    channel.verified_at = utcnow()
    channel.link_token_hash = None
    channel.link_token_expires_at = None
    db.commit()
    return True


def _message_for(match: MatchResult) -> tuple[str, str]:
    job = match.job_posting
    subject = f"Apply now: {job.company} posted {job.title} ({match.score}% match)"
    body = (
        f"{job.company} just posted a role that matches your profile.\n\n"
        f"Role: {job.title}\n"
        f"Location: {job.location or 'Not listed'}\n"
        f"Match score: {match.score}/100\n"
        f"Why: {match.notification_reason}\n"
        f"Detected: {job.observed_at.isoformat()}\n\n"
        f"Apply: {job.apply_url}\n\n"
        "RoleDrop Radar helps you apply early; it does not guarantee selection."
    )
    return subject, body


async def _send_telegram(settings: Settings, chat_id: str, subject: str, body: str, apply_url: str) -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError("Telegram bot is not configured.")
    payload = {
        "chat_id": chat_id,
        "text": f"{subject}\n\n{body}",
        "reply_markup": {"inline_keyboard": [[{"text": "Apply now", "url": apply_url}]]},
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage", json=payload
        )
    response.raise_for_status()


def _send_email(settings: Settings, destination: str, subject: str, body: str) -> None:
    if not settings.smtp_username or not settings.smtp_password or not settings.smtp_from:
        raise RuntimeError("SMTP email delivery is not configured.")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from
    message["To"] = destination
    message.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        if settings.smtp_use_tls:
            server.starttls()
        server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)


async def dispatch_alerts(db: Session, settings: Settings, match: MatchResult) -> int:
    profile = db.scalar(select(Profile).where(Profile.user_id == match.user_id))
    channels = list(
        db.scalars(
            select(NotificationChannel).where(
                NotificationChannel.user_id == match.user_id,
                NotificationChannel.enabled.is_(True),
                NotificationChannel.verified_at.is_not(None),
            )
        )
    )
    if profile and profile.email:
        channels.insert(
            0,
            NotificationChannel(
                user_id=match.user_id,
                channel_type=ChannelType.EMAIL,
                destination=profile.email,
                verified_at=utcnow(),
            ),
        )
    subject, body = _message_for(match)
    attempts = 0
    for channel in channels:
        attempts += 1
        status = DeliveryStatus.SENT
        error = None
        sent_at = None
        try:
            if channel.channel_type == ChannelType.EMAIL:
                _send_email(settings, channel.destination or "", subject, body)
            else:
                await _send_telegram(
                    settings, channel.destination or "", subject, body, match.job_posting.apply_url
                )
            sent_at = utcnow()
        except RuntimeError as exc:
            status = DeliveryStatus.SKIPPED_CONFIGURATION
            error = str(exc)
        except Exception as exc:
            status = DeliveryStatus.FAILED
            error = str(exc)[:500]
        db.add(
            AlertDelivery(
                user_id=match.user_id,
                match_result_id=match.id,
                channel_type=channel.channel_type,
                destination=channel.destination,
                status=status,
                error=error,
                sent_at=sent_at,
            )
        )
    db.commit()
    return attempts

