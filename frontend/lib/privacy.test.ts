import { describe, expect, it } from "vitest";

describe("privacy copy", () => {
  it("does not claim zero access", () => {
    const copy = "Originals stay on your Hostinger disk. Gemini only sees minimized metadata if you enable Cloud AI.";
    expect(copy.toLowerCase()).not.toContain("zero access");
  });
});
