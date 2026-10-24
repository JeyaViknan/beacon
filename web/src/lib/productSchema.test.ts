import { describe, expect, it } from "vitest";
import { DEFAULT_FORM, formToInput, nameFromUrl, productSchema, splitTags, withScheme } from "./productSchema";

const valid = { ...DEFAULT_FORM, name: "Nankiv", checkUrl: "https://nankiv.example/health" };

function errorsFor(override: Partial<typeof valid>): string[] {
  const result = productSchema.safeParse({ ...valid, ...override });
  return result.success ? [] : result.error.issues.map((i) => i.path.join("."));
}

describe("productSchema", () => {
  it("accepts the defaults plus a name and URL", () => {
    expect(productSchema.safeParse(valid).success).toBe(true);
  });

  it("accepts just a link: no name, no scheme", () => {
    expect(errorsFor({ name: "", checkUrl: "myapp.vercel.app" })).toEqual([]);
  });

  it.each([
    [{ name: "x".repeat(61) }, "name"],
    [{ note: "x".repeat(281) }, "note"],
    [{ checkUrl: "" }, "checkUrl"],
    [{ checkUrl: "ftp://example.com" }, "checkUrl"],
    [{ checkUrl: "not a site" }, "checkUrl"],
    [{ checkUrl: "javascript:alert(1)" }, "checkUrl"],
    [{ checkUrl: "https://user:pw@example.com" }, "checkUrl"],
    [{ expectedStatus: "2xx" }, "expectedStatus"],
    [{ expectedStatus: "399-200" }, "expectedStatus"],
    [{ timeoutMs: 500 }, "timeoutMs"],
    [{ timeoutMs: 20000 }, "timeoutMs"],
    [{ timeoutMs: Number.NaN }, "timeoutMs"],
    [{ openAfter: 0 }, "openAfter"],
    [{ resolveAfter: 6 }, "resolveAfter"],
    [{ sloTarget: 89 }, "sloTarget"],
    [{ sloTarget: 100 }, "sloTarget"],
    [{ liveUrl: "javascript:alert(1)" }, "liveUrl"],
    [{ stackText: "a,b,c,d,e,f,g,h,i" }, "stackText"],
    [{ method: "HEAD" as const, keyword: "Welcome" }, "keyword"],
  ])("rejects %o on %s", (override, field) => {
    expect(errorsFor(override)).toContain(field);
  });

  it("accepts status lists and ranges", () => {
    expect(errorsFor({ expectedStatus: "200, 301-302" })).toEqual([]);
  });
});

describe("formToInput", () => {
  it("cleans optional fields and splits tags", () => {
    const input = formToInput({ ...valid, keyword: " ", liveUrl: "", stackText: "React, react, AWS ,", expectedStatus: "200, 301" });
    expect(input.keyword).toBeNull();
    expect(input.liveUrl).toBeNull();
    expect(input.stack).toEqual(["React", "AWS"]);
    expect(input.expectedStatus).toBe("200,301");
  });

  it("names a product after its site and adds https:// when missing", () => {
    const input = formToInput({ ...valid, name: " ", checkUrl: " www.nankiv.app/health ", liveUrl: "nankiv.app" });
    expect(input.name).toBe("nankiv.app");
    expect(input.checkUrl).toBe("https://www.nankiv.app/health");
    expect(input.liveUrl).toBe("https://nankiv.app");
  });

  it("withScheme and nameFromUrl", () => {
    expect(withScheme("cdn.example.net/x")).toBe("https://cdn.example.net/x");
    expect(withScheme("http://a.example")).toBe("http://a.example");
    expect(withScheme("  ")).toBe("");
    expect(nameFromUrl("https://WWW.Example.com:8443/health")).toBe("example.com");
    expect(nameFromUrl("not a site")).toBe("");
  });

  it("splitTags drops blanks and duplicates", () => {
    expect(splitTags(" a, ,A,b")).toEqual(["a", "b"]);
  });
});
