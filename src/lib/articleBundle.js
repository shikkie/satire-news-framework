/** Portable article JSON helpers (admin export / import). */

export function stringifyBundle(bundle) {
  return JSON.stringify(bundle);
}

export function parseBundleText(text) {
  const trimmed = (text || "").trim();
  if (!trimmed) {
    throw new Error("Paste or upload a JSON bundle first.");
  }
  let data;
  try {
    data = JSON.parse(trimmed);
  } catch {
    throw new Error("That is not valid JSON.");
  }
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    throw new Error("Bundle must be a JSON object.");
  }
  return data;
}

export function downloadJson(filename, objOrText) {
  const text = typeof objOrText === "string" ? objOrText : JSON.stringify(objOrText);
  const blob = new Blob([text], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return true;
  }
  return false;
}
