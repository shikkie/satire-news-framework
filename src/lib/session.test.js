import { beforeEach, describe, expect, it } from "vitest";
import {
  authHeaders,
  clearSession,
  getSessionId,
  getSessionMeta,
  setSession,
} from "./session.js";

describe("session storage", () => {
  beforeEach(() => {
    clearSession();
  });

  it("stores and clears session id", () => {
    expect(getSessionId()).toBe("");
    setSession("abc123", { username: "admin", role: "admin" });
    expect(getSessionId()).toBe("abc123");
    expect(getSessionMeta().username).toBe("admin");
    expect(authHeaders()["X-Session-Id"]).toBe("abc123");
    clearSession();
    expect(getSessionId()).toBe("");
  });
});
