import { describe, expect, it } from "vitest";
import { API_BASE, isNativeApp, tapFeedback } from "./platform";

describe("platform (web)", () => {
  it("is not native in the browser and calls the API on the same origin", () => {
    expect(isNativeApp()).toBe(false);
    expect(API_BASE).toBe("");
  });

  it("haptics are a no-op on the web", async () => {
    await expect(tapFeedback()).resolves.toBeUndefined();
  });
});
