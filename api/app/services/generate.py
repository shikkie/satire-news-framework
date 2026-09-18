"""Run a host Grok agent with the CMS article skill, then import into Mongo."""

from __future__ import annotations

import logging
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask
from pymongo.database import Database

from app.config import Config
from app.db import get_db, utcnow
from app.services.acp_grok import AcpGrokSession, format_acp_event
from app.services.articles import is_placeholder_slug, validate_slug
from app.services.media_store import MediaStore
from app.services.seed_import import find_article_folder, merge_folder_into_article

log = logging.getLogger(__name__)

_MAX_LOG_LINES = 250
CMS_SKILL = "skill/satire-news-cms-article-generator/SKILL.md"
CMS_OK_RE = re.compile(
    r"CMS_GENERATE_OK\s+slug=([a-z0-9](?:[a-z0-9-]*[a-z0-9])?)",
    re.I,
)


def generate_configured(cfg: Config) -> bool:
    return bool(cfg.grok_bin and Path(cfg.grok_bin).is_file())


def compose_generate_brief(
    slug: str,
    prompt: str,
    *,
    invent_slug: bool = False,
    taken_slugs: list[str] | None = None,
) -> str:
    taken = ", ".join(sorted({s for s in (taken_slugs or []) if s})[:80]) or "(none)"
    if invent_slug:
        slug_rules = (
            "Invent a unique kebab-case slug from the headline "
            "(a-z, 0-9, hyphens; start/end alphanumeric).\n"
            f"Do NOT use these existing slugs: {taken}\n"
            "Do NOT use a slug starting with draft-.\n"
            "Write articles/<your-slug>/article.md and assets under "
            "articles/<your-slug>/assets/.\n"
            "Final line MUST be: CMS_GENERATE_OK slug=<your-slug> "
            "files=articles/<your-slug>/article.md\n"
        )
    else:
        slug_rules = (
            f"REQUIRED slug: {slug}\n"
            f"Write articles/{slug}/article.md and assets under articles/{slug}/assets/.\n"
            "Do not use a different slug.\n"
            f"Final line: CMS_GENERATE_OK slug={slug} files=articles/{slug}/article.md\n"
        )
    return (
        f"Follow {CMS_SKILL} exactly. This is an Agent News CMS generate job.\n"
        f"{slug_rules}"
        "Do not git commit or push. Do not publish.\n"
        "Do not use the GitHub Pages / preview-server workflow.\n\n"
        f"USER BRIEF:\n{prompt.strip()}\n"
    )


def slug_from_generation_text(doc: dict[str, Any]) -> str | None:
    gen = doc.get("generation") or {}
    blobs: list[str] = []
    for ev in reversed(gen.get("events") or []):
        if isinstance(ev, dict):
            blobs.append(str(ev.get("text") or ""))
    for line in reversed(gen.get("logs") or []):
        blobs.append(str(line))
    for text in blobs:
        m = CMS_OK_RE.search(text)
        if m:
            try:
                return validate_slug(m.group(1))
            except ValueError:
                continue
    return None


def newest_article_folder(articles_dir: Path, *, after: datetime | None, exclude: set[str]) -> Path | None:
    if not articles_dir.is_dir():
        return None
    best: tuple[float, Path] | None = None
    after_ts = after.timestamp() if after is not None else 0.0
    for folder in articles_dir.iterdir():
        if not folder.is_dir() or folder.name in exclude:
            continue
        md = folder / "article.md"
        if not md.is_file():
            continue
        mtime = md.stat().st_mtime
        if mtime < after_ts - 5:
            continue
        if best is None or mtime > best[0]:
            best = (mtime, folder)
    return None if best is None else best[1]


def _append_log(db: Database, slug: str, line: str) -> None:
    record_event(db, slug, "status", line)


def record_event(
    db: Database,
    slug: str,
    kind: str,
    text: str,
    extra: dict[str, Any] | None = None,
) -> None:
    extra = extra or {}
    text = (text or "").rstrip()
    if not text and kind != "tool":
        return
    line = format_acp_event(kind, text, extra)[:2000]
    event = {
        "kind": kind,
        "text": text[:2000],
        "name": extra.get("name") or "",
        "status": extra.get("status") or "",
        "at": utcnow().isoformat().replace("+00:00", "Z"),
    }
    db.articles.update_one(
        {"slug": slug},
        {
            "$push": {
                "generation.logs": {"$each": [line], "$slice": -_MAX_LOG_LINES},
                "generation.events": {"$each": [event], "$slice": -_MAX_LOG_LINES},
            },
            "$set": {"generation.updated_at": utcnow()},
        },
    )


def _set_generation(db: Database, slug: str, **fields: Any) -> None:
    sets = {f"generation.{k}": v for k, v in fields.items()}
    sets["generation.updated_at"] = utcnow()
    db.articles.update_one({"slug": slug}, {"$set": sets})


def _run_grok(cfg: Config, db: Database, slug: str, brief: str) -> int:
    timeout = max(60, int(cfg.grok_timeout_seconds or 3600))
    cwd = cfg.grok_cwd or str(Path(cfg.seed_articles_dir).resolve().parents[0])

    def on_event(kind: str, text: str, extra: dict[str, Any]) -> None:
        record_event(db, slug, kind, text, extra)

    session = AcpGrokSession(
        cfg.grok_bin,
        cwd=cwd,
        on_event=on_event,
        timeout_s=timeout,
        model=cfg.grok_model or "",
    )
    session.run_prompt(brief)
    return 0


def run_generate_job(cfg: Config, slug: str) -> None:
    db = get_db(cfg)
    doc = db.articles.find_one({"slug": slug})
    if not doc:
        return
    prompt = (doc.get("creation_prompt") or "").strip()
    try:
        if not prompt:
            raise RuntimeError("creation_prompt is empty")
        if not generate_configured(cfg):
            raise RuntimeError(f"grok binary not found: {cfg.grok_bin or '(unset)'}")
        invent = bool(doc.get("placeholder") or is_placeholder_slug(slug))
        articles_dir = Path(cfg.seed_articles_dir)
        alt_dir = Path(cfg.grok_cwd or ".") / "articles"
        taken = {d.name for d in articles_dir.iterdir() if d.is_dir()} if articles_dir.is_dir() else set()
        taken.update(a["slug"] for a in db.articles.find({}, {"slug": 1}) if a.get("slug"))
        taken.discard(slug)
        started = utcnow()
        brief = compose_generate_brief(
            slug,
            prompt,
            invent_slug=invent,
            taken_slugs=sorted(taken),
        )
        code = _run_grok(cfg, db, slug, brief)
        doc = db.articles.find_one({"slug": slug}) or doc
        invented = slug_from_generation_text(doc) if invent else None
        folder = find_article_folder(articles_dir, invented or slug, slug)
        if folder is None:
            folder = find_article_folder(alt_dir, invented or slug, slug)
        if folder is None and invent:
            folder = newest_article_folder(articles_dir, after=started, exclude=taken)
            if folder is None:
                folder = newest_article_folder(alt_dir, after=started, exclude=taken)
        if folder is None:
            raise RuntimeError(
                f"grok exited {code} but articles/{invented or slug}/article.md was not found"
            )
        final_slug = slug if not invent else folder.name
        store = MediaStore(cfg)
        merge_folder_into_article(
            cfg, db, store, folder, target_slug=slug, edited_by="grok"
        )
        if invent and final_slug != slug:
            if db.articles.find_one({"slug": final_slug}):
                raise RuntimeError(f"generated slug already exists: {final_slug}")
            src = db.articles.find_one({"slug": slug})
            copy = {k: v for k, v in (src or {}).items() if k != "_id"}
            copy["slug"] = final_slug
            copy["placeholder"] = False
            db.articles.insert_one(copy)
            record_event(db, slug, "status", f"Using AI slug {final_slug}", {})
            _set_generation(
                db,
                final_slug,
                status="ok",
                finished_at=utcnow(),
                error="",
                article_url=cfg.article_page_url(final_slug),
                final_slug=final_slug,
            )
        _set_generation(
            db,
            slug,
            status="ok",
            finished_at=utcnow(),
            error="",
            article_url=cfg.article_page_url(final_slug),
            final_slug=final_slug,
        )
        _append_log(db, slug, "Imported generated files into this draft.")
    except Exception as exc:
        log.warning("generate %s failed: %s", slug, exc)
        _set_generation(db, slug, status="error", finished_at=utcnow(), error=str(exc))
        _append_log(db, slug, f"ERROR: {exc}")


def start_generate(app: Flask, slug: str) -> None:
    cfg = app.config["APP_CONFIG"]

    def _worker() -> None:
        with app.app_context():
            run_generate_job(cfg, slug)

    threading.Thread(target=_worker, name=f"generate-{slug}", daemon=True).start()
