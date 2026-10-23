import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { getToken } from "../lib/auth";
import { mockApi, renderWithApp } from "../test/render";
import LoginPage from "./LoginPage";

describe("LoginPage", () => {
  it("stores the token after a successful login", async () => {
    const calls = mockApi({ "POST /auth/login": [200, { token: "t0k", expiresAt: "2099-01-01T00:00:00Z" }] });
    renderWithApp(<LoginPage />, "/login");
    await userEvent.type(screen.getByLabelText("Password"), "secret password");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    await screen.findByRole("button", { name: "Log in" }).catch(() => null);
    expect(calls[0]).toEqual({ method: "POST", path: "/auth/login", body: { password: "secret password" } });
    expect(getToken()).toBe("t0k");
  });

  it("explains a wrong password", async () => {
    mockApi({ "POST /auth/login": [401, { error: { code: "wrong_password", message: "wrong password" } }] });
    renderWithApp(<LoginPage />, "/login");
    await userEvent.type(screen.getByLabelText("Password"), "nope");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Wrong password");
    expect(getToken()).toBeNull();
  });
});
