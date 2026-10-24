import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { mockApi, renderWithApp } from "../test/render";
import SettingsPage from "./SettingsPage";

// Pretend we are inside the native iOS app (Capacitor).
vi.mock("@capacitor/core", () => ({ Capacitor: { isNativePlatform: () => true } }));

const settings = {
  settings: { quorum: null, pushEnabled: true, emailEnabled: true, pagerdutyEnabled: false },
  channels: { pushDevices: 1, email: true, pagerduty: false, vapid: true, healthchecks: false },
  demo: "healthy",
  version: "abc1234",
  region: "ap-south-1",
};

describe("SettingsPage in the native app", () => {
  it("explains where alerts arrive instead of offering Web Push", async () => {
    mockApi({ "GET /settings": [200, settings], "GET /health": [200, { status: "ok", version: "abc1234", time: "" }] });
    renderWithApp(<SettingsPage />, "/settings");
    expect(await screen.findByText(/Alerts reach you by/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Enable notifications/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send Test Notification" })).toBeInTheDocument();
  });
});
