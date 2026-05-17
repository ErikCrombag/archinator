"""Async PlantUML → image rendering. JAR primary, kroki.io fallback."""
from __future__ import annotations
import asyncio

import httpx


async def render(source: str, fmt: str, jar_path: str) -> bytes:
    """Render PlantUML source to SVG or PNG.

    fmt: 'svg' or 'png'
    Tries local JAR first; falls back to kroki.io if JAR absent.
    """
    import os
    if os.path.isfile(jar_path):
        return await _render_jar(source, fmt, jar_path)
    return await _render_kroki(source, fmt)


async def _render_jar(source: str, fmt: str, jar_path: str) -> bytes:
    proc = await asyncio.create_subprocess_exec(
        "java", "-jar", jar_path, f"-t{fmt}", "-pipe", "-charset", "UTF-8",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(
        proc.communicate(source.encode("utf-8")), timeout=60
    )
    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"PlantUML JAR error (exit {proc.returncode}): {err[:300]}")
    return stdout


async def _render_kroki(source: str, fmt: str) -> bytes:
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"https://kroki.io/plantuml/{fmt}",
            content=source.encode("utf-8"),
            headers={"Content-Type": "text/plain"},
        )
        r.raise_for_status()
        return r.content
