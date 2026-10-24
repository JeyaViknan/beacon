import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { mockApi, renderWithApp } from "../test/render";
import ProductFormPage from "./ProductFormPage";

describe("ProductFormPage", () => {
  it("shows validation errors before calling the API", async () => {
    const calls = mockApi({});
    renderWithApp(<ProductFormPage mode="create" />, "/new");
    await userEvent.type(screen.getByLabelText("Link to check"), "ftp://example.com");
    await userEvent.click(screen.getByRole("button", { name: "Add and check" }));
    expect(await screen.findByText(/Use a web address like myapp\.vercel\.app/)).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST")).toEqual([]);
  });

  it("adds a product from just a link, named after the site", async () => {
    const calls = mockApi({ "POST /products": [201, { id: "NEW1" }] });
    renderWithApp(<ProductFormPage mode="create" />, "/new");
    await userEvent.type(screen.getByLabelText("Link to check"), "www.myapp.vercel.app");
    expect(screen.getByLabelText("Name (optional)")).toHaveAttribute("placeholder", "myapp.vercel.app");
    await userEvent.click(screen.getByRole("button", { name: "Add and check" }));
    await screen.findByRole("button", { name: /Add and check|Saving/ });
    expect(calls.find((c) => c.method === "POST")?.body).toMatchObject({
      name: "myapp.vercel.app",
      checkUrl: "https://www.myapp.vercel.app",
      kind: "personal",
      expectedStatus: "200-399",
      intervalMin: 1,
    });
  });

  it("creates a product with cleaned values", async () => {
    const calls = mockApi({ "POST /products": [201, { id: "NEW1" }] });
    renderWithApp(<ProductFormPage mode="create" />, "/new");
    await userEvent.type(screen.getByLabelText("Name (optional)"), "Nankiv");
    await userEvent.type(screen.getByLabelText("Link to check"), "https://nankiv.example/health");
    await userEvent.click(screen.getByText("Notes and Links"));
    await userEvent.type(screen.getByLabelText("Stack"), "React, AWS");
    await userEvent.click(screen.getByRole("button", { name: "Add and check" }));
    await screen.findByRole("button", { name: /Add and check|Saving/ });
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

  it("puts an SSRF rejection from the API on the link field", async () => {
    mockApi({
      "POST /products": [422, { error: { code: "url_not_allowed", message: "internal.example resolves to a non-public address (10.0.0.7)" } }],
    });
    renderWithApp(<ProductFormPage mode="create" />, "/new");
    await userEvent.type(screen.getByLabelText("Link to check"), "https://internal.example/");
    await userEvent.click(screen.getByRole("button", { name: "Add and check" }));
    expect(await screen.findByText(/Beacon won't check this address/)).toBeInTheDocument();
  });
});
