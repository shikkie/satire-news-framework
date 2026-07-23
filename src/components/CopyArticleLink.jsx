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

/**
 * Share chrome: copy this article's canonical URL.
 * Only copy-link for now; other networks later (issue #5).
 */
export default function CopyArticleLink({ slug }) {
  const [status, setStatus] = useState("idle"); // idle | copied | error

  useEffect(() => {
    if (status !== "copied") return undefined;
    const t = window.setTimeout(() => setStatus("idle"), 2000);
    return () => window.clearTimeout(t);
  }, [status]);

  if (!slug) return null;

  const url = articleShareUrl(slug);

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

  const label =
    status === "copied" ? "Copied!" : status === "error" ? "Copy failed" : "Copy link";

  return (
    <div className="share-bar" role="group" aria-label="Share">
      <button
        type="button"
        className={`share-btn share-btn-copy${status === "copied" ? " is-copied" : ""}`}
        onClick={onCopy}
        aria-live="polite"
      >
        <span className="share-btn-icon" aria-hidden="true">
          {status === "copied" ? "✓" : "🔗"}
        </span>
        {label}
      </button>
    </div>
  );
}
