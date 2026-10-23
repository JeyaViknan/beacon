import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { mockApi, renderWithApp } from "../test/render";
import ProductFormPage from "./ProductFormPage";

describe("ProductFormPage", () => {
  it("shows validation errors before calling the API", async () => {
    const calls = mockApi({});
    renderWithApp(<ProductFormPage mode="create" />, "/new");
    await userEvent.type(screen.getByLabelText("URL to check"), "ftp://example.com");
    await userEvent.click(screen.getByRole("button", { name: "Add product" }));
    expect(await screen.findByText("Give the product a name")).toBeInTheDocument();
    expect(screen.getByText("Use a full http:// or https:// address")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST")).toEqual([]);
  });

  it("creates a product with cleaned values", async () => {
    const calls = mockApi({ "POST /products": [201, { id: "NEW1" }] });
    renderWithApp(<ProductFormPage mode="create" />, "/new");
    await userEvent.type(screen.getByLabelText("Name"), "Nankiv");
    await userEvent.type(screen.getByLabelText("URL to check"), "https://nankiv.example/health");
    await userEvent.type(screen.getByLabelText("Stack"), "React, AWS");
    await userEvent.click(screen.getByRole("button", { name: "Add product" }));
    await screen.findByRole("button", { name: /Add product|Saving/ });
    const post = calls.find((c) => c.method === "POST");
    expect(post?.body).toMatchObject({
      name: "Nankiv",
      checkUrl: "https://nankiv.example/health",
      kind: "personal",
      keyword: null,
      liveUrl: null,
      stack: ["React", "AWS"],
      timeoutMs: 10000,
      intervalMin: 1,
    });
  });

  it("puts an SSRF rejection from the API on the URL field", async () => {
    mockApi({
      "POST /products": [422, { error: { code: "url_not_allowed", message: "internal.example resolves to a non-public address (10.0.0.7)" } }],
    });
    renderWithApp(<ProductFormPage mode="create" />, "/new");
    await userEvent.type(screen.getByLabelText("Name"), "Internal");
    await userEvent.type(screen.getByLabelText("URL to check"), "https://internal.example/");
    await userEvent.click(screen.getByRole("button", { name: "Add product" }));
    expect(await screen.findByText(/Beacon won't check this address/)).toBeInTheDocument();
  });
});
