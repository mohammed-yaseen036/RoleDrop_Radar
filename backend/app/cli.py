import argparse
import asyncio
import json

from .config import get_settings
from .db import Base, create_db_engine
from .services.monitor import run_monitor
from .services.sources import seed_catalog
from sqlalchemy.orm import sessionmaker


async def monitor_command() -> int:
    settings = get_settings()
    engine = create_db_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session_factory() as db:
        seed_catalog(db)
        summary = await run_monitor(db, settings)
    print(json.dumps(summary.model_dump(), indent=2))
    engine.dispose()
    return 1 if summary.failed_sources else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="RoleDrop Radar scheduled jobs")
    parser.add_argument("command", choices=["monitor"])
    args = parser.parse_args()
    if args.command == "monitor":
        return asyncio.run(monitor_command())
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

