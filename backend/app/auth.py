from dataclasses import dataclass

import httpx
from fastapi import Header, HTTPException, Request, status

from .config import Settings


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str | None


async def get_current_user(
    request: Request,
    authorization: str | None = Header(default=None),
    x_demo_user: str | None = Header(default=None),
    x_demo_email: str | None = Header(default=None),
) -> CurrentUser:
    settings: Settings = request.app.state.settings
    if settings.supabase_auth_enabled:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        headers = {
            "Authorization": authorization,
            "apikey": settings.supabase_anon_key or "",
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{settings.supabase_url}/auth/v1/user", headers=headers)
        if response.status_code != 200:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
        data = response.json()
        return CurrentUser(id=str(data["id"]), email=data.get("email"))

    if settings.is_development:
        return CurrentUser(id=x_demo_user or "demo-user", email=x_demo_email or "demo@example.com")

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Supabase authentication is not configured",
    )

