import { describe, expect, it } from "vitest";
import { heroMediaUrl, resolveMediaUrl } from "./media.js";

const article = {
  slug: "demo-slug",
  hero: "hero",
  media: [
    {
      type: "image",
      name: "hero",
      filename: "hero.jpg",
      key: "article/demo-slug/hero.jpg",
      url: "http://assets.agentnews.local/agentnews-media/article/demo-slug/hero.jpg",
    },
    {
      type: "image",
      name: "scene",
      filename: "scene-one.jpg",
      key: "article/demo-slug/scene-one.jpg",
      url: "http://assets.agentnews.local/agentnews-media/article/demo-slug/scene-one.jpg",
    },
  ],
};

describe("resolveMediaUrl", () => {
  it("passes through absolute URLs", () => {
    expect(resolveMediaUrl(article, "https://cdn.example/x.jpg")).toBe(
      "https://cdn.example/x.jpg"
    );
  });

  it("resolves by media name", () => {
    expect(resolveMediaUrl(article, "hero")).toContain("/hero.jpg");
    expect(resolveMediaUrl(article, "scene")).toContain("scene-one.jpg");
  });

  it("resolves assets/ relative paths", () => {
    expect(resolveMediaUrl(article, "assets/hero.jpg")).toContain("/hero.jpg");
    expect(resolveMediaUrl(article, "scene-one.jpg")).toContain("scene-one.jpg");
  });

  it("falls back to legacy content path when unknown", () => {
    expect(resolveMediaUrl(article, "missing.png")).toBe(
      "/content/demo-slug/assets/missing.png"
    );
  });
});

describe("heroMediaUrl", () => {
  it("returns hero URL from media list", () => {
    expect(heroMediaUrl(article)).toContain("hero.jpg");
  });

  it("accepts absolute hero field", () => {
    expect(
      heroMediaUrl({ ...article, hero: "https://cdn.example/h.jpg" })
    ).toBe("https://cdn.example/h.jpg");
  });
});
