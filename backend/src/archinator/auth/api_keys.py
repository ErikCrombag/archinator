from __future__ import annotations
import hashlib
import secrets
from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

from .models import Base, ApiKey
from ..config import settings

_engine = create_async_engine(f"sqlite+aiosqlite:///{settings.db_path}", echo=False)
_SessionLocal = async_sessionmaker(_engine, expire_on_commit=False)


async def init_db() -> None:
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with _SessionLocal() as session:
        yield session


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def create_key(name: str, created_by: str = "admin") -> tuple[str, ApiKey]:
    """Returns (raw_key, ApiKey record). Raw key is shown once — not stored."""
    raw = "ark_" + secrets.token_urlsafe(32)
    key_hash = _hash_key(raw)
    prefix = raw[:12]
    record = ApiKey(name=name, key_hash=key_hash, key_prefix=prefix, created_by=created_by)
    async with _SessionLocal() as session:
        session.add(record)
        await session.commit()
        await session.refresh(record)
    return raw, record


async def validate_key(raw: str) -> ApiKey | None:
    """Returns the ApiKey record if valid and active, else None. Updates usage stats."""
    key_hash = _hash_key(raw)
    async with _SessionLocal() as session:
        result = await session.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.active == True)
        )
        record = result.scalar_one_or_none()
        if record:
            record.last_used_at = datetime.now(timezone.utc)
            record.use_count += 1
            await session.commit()
    return record


async def revoke_key(key_id: int) -> bool:
    async with _SessionLocal() as session:
        result = await session.execute(select(ApiKey).where(ApiKey.id == key_id))
        record = result.scalar_one_or_none()
        if not record:
            return False
        record.active = False
        await session.commit()
    return True


async def list_keys() -> list[ApiKey]:
    async with _SessionLocal() as session:
        result = await session.execute(select(ApiKey).order_by(ApiKey.created_at.desc()))
        return list(result.scalars().all())
