"""Frontmatter parsing used by onboard (no S3 required)."""

from pathlib import Path

from scripts.onboard_content import (
    media_name_from_path,
    parse_md,
    parse_simple_yaml,
    parse_when,
)


def test_parse_simple_yaml_tags():
    text = 'title: "Hi"\ntags: ["a", "b"]\ndisclaimer: true\n'
    data = parse_simple_yaml(text)
    assert data["title"] == "Hi"
    assert data["tags"] == ["a", "b"]
    assert data["disclaimer"] is True


def test_parse_md_roundtrip(tmp_path: Path):
    p = tmp_path / "article.md"
    p.write_text(
        "---\ntitle: T\nauthor: A\n---\n\nBody **here**\n",
        encoding="utf-8",
    )
    meta, body = parse_md(p)
    assert meta["title"] == "T"
    assert "Body" in body


def test_media_name():
    assert media_name_from_path("assets/hero.jpg") == "hero"
    assert media_name_from_path("hero.jpg") == "hero"


def test_parse_when_prefers_published_iso():
    dt = parse_when("2026-07-20T18:30:00Z", "2026-07-19")
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 7
    assert dt.day == 20
    assert dt.hour == 18


def test_parse_when_date_only():
    dt = parse_when(None, "2026-08-01")
    assert dt is not None
    assert dt.date().isoformat() == "2026-08-01"


def test_parse_when_invalid():
    assert parse_when("", "not-a-date") is None
