import { describe, expect, it } from "vitest";
import { clampCrop } from "./scan-pdf";

describe("clampCrop", () => {
  it("keeps a normal crop", () => {
    expect(clampCrop({ x: 0.1, y: 0.2, w: 0.5, h: 0.4 })).toEqual({ x: 0.1, y: 0.2, w: 0.5, h: 0.4 });
  });

  it("rejects inverted or overflowing boxes", () => {
    const crop = clampCrop({ x: 0.9, y: 0.9, w: 0.5, h: 0.5 });
    expect(crop.x + crop.w).toBeLessThanOrEqual(1.0001);
    expect(crop.y + crop.h).toBeLessThanOrEqual(1.0001);
    expect(crop.w).toBeGreaterThanOrEqual(0.05);
  });
});
