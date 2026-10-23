import { describe, expect, it } from "vitest";
import { type InstallEnv, isIOS, shouldShowInstallTip } from "./install";

const IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1";
const MAC = "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_0) AppleWebKit/605.1.15 Version/18.0 Safari/605.1.15";

const env = (over: Partial<InstallEnv>): InstallEnv => ({
  userAgent: IPHONE,
  platform: "iPhone",
  maxTouchPoints: 5,
  standalone: false,
  displayModeStandalone: false,
  dismissed: false,
  ...over,
});

describe("install tip", () => {
  it("shows in iPhone Safari before installing", () => {
    expect(shouldShowInstallTip(env({}))).toBe(true);
  });

  it.each([
    ["installed (navigator.standalone)", { standalone: true }],
    ["installed (display-mode)", { displayModeStandalone: true }],
    ["dismissed", { dismissed: true }],
    ["desktop Mac", { userAgent: MAC, platform: "MacIntel", maxTouchPoints: 0, standalone: undefined }],
  ])("hides when %s", (_label, over) => {
    expect(shouldShowInstallTip(env(over))).toBe(false);
  });

  it("treats iPadOS (Mac UA with touch) as iOS", () => {
    expect(isIOS({ userAgent: MAC, platform: "MacIntel", maxTouchPoints: 5 })).toBe(true);
  });
});
