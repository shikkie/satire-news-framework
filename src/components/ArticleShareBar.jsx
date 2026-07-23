import { useEffect, useState } from "react";
import { siteOrigin } from "../lib/socialMeta.js";

/**
 * Canonical path-form article URL for the current origin (local or production).
 */
export function articleShareUrl(slug) {
  const origin = siteOrigin();
  return `${origin}/article/${slug}`;
}

function isSecureContext() {
  if (typeof window === "undefined") return false;
  if (window.isSecureContext) return true;
  const { protocol, hostname } = window.location;
  return (
    protocol === "https:" ||
    hostname === "localhost" ||
    hostname === "127.0.0.1" ||
    hostname === "[::1]"
  );
}

/**
 * Copy text to clipboard. Returns { ok, reason? }.
 * Tries Clipboard API, then execCommand; never throws.
 */
export async function copyTextToClipboard(text) {
  const secure = isSecureContext();

  if (secure && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return { ok: true };
    } catch {
      /* try legacy path */
    }
  }

  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.top = "0";
    ta.style.left = "-9999px";
    ta.setAttribute("aria-hidden", "true");
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    ta.setSelectionRange(0, text.length);
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    if (ok) return { ok: true };
  } catch {
    /* fall through to failure */
  }

  let reason;
  if (!secure) {
    reason =
      "Copy to clipboard needs a secure page (HTTPS or localhost). " +
      "This page is not in a secure context, so the browser blocked clipboard access.";
  } else if (!navigator.clipboard?.writeText) {
    reason =
      "This browser does not support automatic clipboard copy (no Clipboard API).";
  } else {
    reason =
      "Clipboard access was denied or copy failed (check browser permissions).";
  }

  return { ok: false, reason };
}

function enc(s) {
  return encodeURIComponent(s ?? "");
}

/**
 * Build share targets for known networks.
 * Mirage.talk has no stable public intent URL — open home + copy draft text.
 */
export function buildShareTargets({ url, title, dek }) {
  const headline = title || "Agent News";
  const blurb = dek ? `${headline} — ${dek}` : headline;
  const textWithUrl = `${blurb}\n\n${url}`;

  return [
    {
      id: "x",
      label: "X",
      href: `https://twitter.com/intent/tweet?url=${enc(url)}&text=${enc(headline)}`,
    },
    {
      id: "bluesky",
      label: "Bluesky",
      href: `https://bsky.app/intent/compose?text=${enc(textWithUrl)}`,
    },
    {
      id: "mirage",
      label: "Mirage.talk",
      // No documented public share intent; open site and hand user a ready paste.
      mode: "copy-and-open",
      openUrl: "https://mirage.talk/",
      pasteText: textWithUrl,
      note:
        "Mirage.talk does not publish a stable web share intent. " +
        "We copy the post text (title + link) and open mirage.talk so you can paste.",
    },
    {
      id: "truth",
      label: "Truth Social",
      // Official publisher share button: truthsocial.com/share?text=&url=
      href: `https://truthsocial.com/share?text=${enc(headline)}&url=${enc(url)}`,
    },
    {
      id: "facebook",
      label: "Facebook",
      href: `https://www.facebook.com/sharer/sharer.php?u=${enc(url)}`,
    },
    {
      id: "reddit",
      label: "Reddit",
      href: `https://www.reddit.com/submit?url=${enc(url)}&title=${enc(headline)}`,
    },
  ];
}

function openShareWindow(href) {
  if (!href) return;
  window.open(href, "_blank", "noopener,noreferrer");
}

/**
 * Article share chrome: copy link + social network openers (issue #5).
 */
export default function ArticleShareBar({ slug, title, dek }) {
  const [status, setStatus] = useState("idle"); // idle | copied | error

  useEffect(() => {
    if (status !== "copied") return undefined;
    const t = window.setTimeout(() => setStatus("idle"), 2000);
    return () => window.clearTimeout(t);
  }, [status]);

  if (!slug) return null;

  const url = articleShareUrl(slug);
  const targets = buildShareTargets({ url, title, dek });

  async function onCopy() {
    const result = await copyTextToClipboard(url);
    if (result.ok) {
      setStatus("copied");
      return;
    }
    setStatus("error");
    const message =
      (result.reason || "Could not copy the link automatically.") +
      "\n\nYou can copy it manually:\n" +
      url;
    window.alert(message);
    window.setTimeout(() => setStatus("idle"), 500);
  }

  async function onMirageShare(target) {
    const result = await copyTextToClipboard(target.pasteText);
    openShareWindow(target.openUrl);
    if (result.ok) {
      window.alert(
        `${target.note}\n\nPost text was copied to your clipboard. Paste it into Mirage.talk.`
      );
      return;
    }
    window.alert(
      `${target.note}\n\n` +
        (result.reason || "Could not copy automatically.") +
        "\n\nPaste this manually:\n" +
        target.pasteText
    );
  }

  const copyLabel =
    status === "copied" ? "Copied!" : status === "error" ? "Copy failed" : "Copy link";

  return (
    <div className="share-bar" role="group" aria-label="Share article">
      <button
        type="button"
        className={`share-btn share-btn-copy${status === "copied" ? " is-copied" : ""}`}
        onClick={onCopy}
        aria-live="polite"
      >
        <span className="share-btn-icon" aria-hidden="true">
          {status === "copied" ? "✓" : "🔗"}
        </span>
        {copyLabel}
      </button>

      {targets.map((t) =>
        t.mode === "copy-and-open" ? (
          <button
            key={t.id}
            type="button"
            className={`share-btn share-btn-net share-btn-${t.id}`}
            onClick={() => onMirageShare(t)}
            title={t.note}
          >
            {t.label}
          </button>
        ) : (
          <a
            key={t.id}
            className={`share-btn share-btn-net share-btn-${t.id}`}
            href={t.href}
            target="_blank"
            rel="noopener noreferrer"
          >
            {t.label}
          </a>
        )
      )}
    </div>
  );
}
