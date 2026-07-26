"""Article document helpers, version history, serialization."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from pymongo.database import Database

from app.config import Config
from app.db import utcnow

SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,80}[a-z0-9])?$")
STATUSES = frozenset({"draft", "published", "scheduled"})


def validate_slug(slug: str) -> str:
    s = (slug or "").strip().lower()
    if not SLUG_RE.match(s):
        raise ValueError(
            "slug must be lowercase alphanumeric with hyphens "
            "(start/end alphanumeric, max ~82 chars)"
        )
    return s


def _iso(dt: Any) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.isoformat().replace("+00:00", "Z")
    return str(dt)


def serialize_article(
    doc: dict[str, Any],
    *,
    include_body: bool = True,
    include_versions: bool = False,
    public: bool = False,
) -> dict[str, Any]:
    """Shape compatible with existing SPA (+ admin extras)."""
    media = doc.get("media") or []
    hero_name = doc.get("hero") or ""
    hero_url = ""
    if hero_name:
        if str(hero_name).startswith("http"):
            hero_url = hero_name
        else:
            for m in media:
                if m.get("name") == hero_name or m.get("name") == Path_stem(hero_name):
                    hero_url = m.get("url") or ""
                    break
            if not hero_url:
                # bare filename match
                base = Path_stem(hero_name)
                for m in media:
                    if Path_stem(m.get("name") or "") == base or base in (
                        m.get("key") or ""
                    ):
                        hero_url = m.get("url") or ""
                        break

    published_at = doc.get("published_at")
    date_str = doc.get("date") or ""
    if not date_str and published_at:
        if isinstance(published_at, datetime):
            date_str = published_at.date().isoformat()
        else:
            date_str = str(published_at)[:10]

    out: dict[str, Any] = {
        "slug": doc.get("slug"),
        "title": doc.get("title") or doc.get("slug"),
        "dek": doc.get("dek") or "",
        "author": doc.get("author") or "Staff",
        "date": date_str,
        "published": _iso(published_at) or doc.get("published") or "",
        "section": doc.get("section") or "News",
        "hero": hero_url or hero_name,
        "tags": doc.get("tags") or [],
        "disclaimer": doc.get("disclaimer", True),
        "media": media,
        "agent_source": doc.get("agent_source") or "grok",
        "status": doc.get("status") or "draft",
        "created_at": _iso(doc.get("created_at")),
        "updated_at": _iso(doc.get("updated_at")),
        "published_at": _iso(published_at),
    }
    if include_body:
        out["body"] = doc.get("markdown") or doc.get("body") or ""
        out["markdown"] = out["body"]
    if include_versions:
        versions = doc.get("versions") or []
        out["versions"] = [
            {
                "version": v.get("version"),
                "markdown": v.get("markdown"),
                "title": v.get("title"),
                "edited_by": v.get("edited_by"),
                "edited_at": _iso(v.get("edited_at")),
                "reason": v.get("reason") or "",
            }
            for v in versions
        ]
    if public and out.get("status") != "published":
        return out  # caller should 404; keep shape for admin
    return out


def Path_stem(name: str) -> str:
    # local helper to avoid importing pathlib everywhere for simple stems
    n = (name or "").replace("\\", "/").split("/")[-1]
    if "." in n:
        return n.rsplit(".", 1)[0]
    return n


def resolve_media_url(doc: dict[str, Any], ref: str) -> str:
    """Resolve markdown image ref (name, relative path, or absolute URL)."""
    if not ref:
        return ""
    raw = str(ref).strip()
    if raw.startswith("http://") or raw.startswith("https://") or raw.startswith("data:"):
        return raw
    media = doc.get("media") or []
    # strip assets/ prefix and extension variants
    clean = raw.replace("\\", "/").lstrip("./")
    if clean.startswith("assets/"):
        clean = clean[len("assets/") :]
    stem = Path_stem(clean)
    for m in media:
        name = m.get("name") or ""
        key = m.get("key") or ""
        url = m.get("url") or ""
        if name == clean or name == stem or Path_stem(name) == stem:
            return url
        if clean in key or key.endswith(f"/{clean}") or key.endswith(f"/{Path_stem(clean)}"):
            return url
        if url.endswith(f"/{clean}"):
            return url
    return raw


def next_version_entry(
    *,
    version: int,
    markdown: str,
    title: str,
    edited_by: str,
    reason: str = "",
) -> dict[str, Any]:
    return {
        "version": version,
        "markdown": markdown,
        "title": title,
        "edited_by": edited_by,
        "edited_at": utcnow(),
        "reason": reason or "",
    }


def create_article(
    db: Database,
    payload: dict[str, Any],
    *,
    edited_by: str,
    cfg: Config,
) -> dict[str, Any]:
    slug = validate_slug(payload["slug"])
    if db.articles.find_one({"slug": slug}):
        raise ValueError(f"slug already exists: {slug}")
    now = utcnow()
    status = payload.get("status") or "draft"
    if status not in STATUSES:
        raise ValueError(f"invalid status: {status}")
    markdown = payload.get("markdown") or payload.get("body") or ""
    title = payload.get("title") or slug
    versions = [
        next_version_entry(
            version=1,
            markdown=markdown,
            title=title,
            edited_by=edited_by,
            reason=payload.get("reason") or "initial create",
        )
    ]
    published_at = payload.get("published_at")
    if status == "published" and not published_at:
        published_at = now
    doc = {
        "slug": slug,
        "title": title,
        "dek": payload.get("dek") or "",
        "author": payload.get("author") or "Staff",
        "date": payload.get("date")
        or (
            published_at.date().isoformat()
            if isinstance(published_at, datetime)
            else ""
        ),
        "section": payload.get("section") or "News",
        "tags": payload.get("tags") or [],
        "disclaimer": payload.get("disclaimer", True),
        "hero": payload.get("hero") or "",
        "markdown": markdown,
        "media": payload.get("media") or [],
        "agent_source": payload.get("agent_source") or "grok",
        "status": status,
        "published_at": published_at,
        "created_at": now,
        "updated_at": now,
        "versions": versions,
    }
    db.articles.insert_one(doc)
    return doc


def update_article(
    db: Database,
    slug: str,
    payload: dict[str, Any],
    *,
    edited_by: str,
) -> dict[str, Any]:
    doc = db.articles.find_one({"slug": slug})
    if not doc:
        raise KeyError(slug)
    now = utcnow()
    updates: dict[str, Any] = {"updated_at": now}
    for field in (
        "title",
        "dek",
        "author",
        "date",
        "section",
        "tags",
        "disclaimer",
        "hero",
        "media",
        "agent_source",
        "status",
        "published_at",
    ):
        if field in payload:
            updates[field] = payload[field]

    if "status" in updates and updates["status"] not in STATUSES:
        raise ValueError(f"invalid status: {updates['status']}")

    new_md = None
    if "markdown" in payload or "body" in payload:
        new_md = payload.get("markdown") if "markdown" in payload else payload.get("body")
        updates["markdown"] = new_md

    # Version snapshot when markdown or title changes
    title_changed = "title" in updates and updates["title"] != doc.get("title")
    md_changed = new_md is not None and new_md != doc.get("markdown")
    if title_changed or md_changed:
        versions = list(doc.get("versions") or [])
        next_ver = (versions[-1]["version"] + 1) if versions else 1
        versions.append(
            next_version_entry(
                version=next_ver,
                markdown=updates.get("markdown", doc.get("markdown") or ""),
                title=updates.get("title", doc.get("title") or slug),
                edited_by=edited_by,
                reason=payload.get("reason") or "edit",
            )
        )
        updates["versions"] = versions

    if updates.get("status") == "published" and not updates.get("published_at") and not doc.get(
        "published_at"
    ):
        updates["published_at"] = now
        if not updates.get("date") and not doc.get("date"):
            updates["date"] = now.date().isoformat()

    db.articles.update_one({"slug": slug}, {"$set": updates})
    return db.articles.find_one({"slug": slug})  # type: ignore[return-value]


def search_articles(
    db: Database,
    *,
    q: str | None = None,
    status: str | None = None,
    public_only: bool = False,
    sort: str = "published_at",
    limit: int = 100,
    skip: int = 0,
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {}
    if public_only:
        query["status"] = "published"
    elif status:
        query["status"] = status
    if q:
        # Prefer text index; fallback regex for mongomock
        try:
            query["$text"] = {"$search": q}
            cursor = (
                db.articles.find(query, {"score": {"$meta": "textScore"}})
                .sort([("score", {"$meta": "textScore"})])
                .skip(skip)
                .limit(min(limit, 500))
            )
            return list(cursor)
        except Exception:  # noqa: BLE001
            query.pop("$text", None)
            query["$or"] = [
                {"title": {"$regex": q, "$options": "i"}},
                {"dek": {"$regex": q, "$options": "i"}},
                {"markdown": {"$regex": q, "$options": "i"}},
                {"slug": {"$regex": q, "$options": "i"}},
            ]

    sort_field = sort if sort in ("created_at", "updated_at", "published_at") else "published_at"
    cursor = (
        db.articles.find(query)
        .sort([(sort_field, -1), ("slug", 1)])
        .skip(skip)
        .limit(min(limit, 500))
    )
    return list(cursor)
