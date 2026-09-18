import { describe, expect, it } from "vitest";
import { parseBundleText, stringifyBundle } from "./articleBundle.js";

describe("articleBundle", () => {
  it("round-trips JSON text", () => {
    const bundle = {
      format: "agentnews.article.v1",
      article: { slug: "x", title: "X" },
      assets: [],
    };
    const parsed = parseBundleText(stringifyBundle(bundle));
    expect(parsed.article.slug).toBe("x");
  });

  it("rejects empty and invalid JSON", () => {
    expect(() => parseBundleText("")).toThrow(/Paste or upload/);
    expect(() => parseBundleText("not json")).toThrow(/not valid JSON/);
    expect(() => parseBundleText("[]")).toThrow(/JSON object/);
  });
});
