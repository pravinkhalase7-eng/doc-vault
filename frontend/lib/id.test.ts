import { describe, expect, it, vi } from "vitest";
import { newId } from "./id";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

describe("newId", () => {
  it("returns a UUID when randomUUID exists", () => {
    expect(newId()).toMatch(UUID_RE);
  });

  it("still returns a UUID when randomUUID is missing", () => {
    const original = crypto.randomUUID;
    // @ts-expect-error — simulate an insecure HTTP origin
    crypto.randomUUID = undefined;
    try {
      expect(newId()).toMatch(UUID_RE);
      expect(newId()).not.toBe(newId());
    } finally {
      crypto.randomUUID = original;
    }
  });

  it("falls back when Web Crypto is absent", () => {
    vi.stubGlobal("crypto", undefined);
    try {
      expect(newId()).toMatch(UUID_RE);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
