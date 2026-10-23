import { describe, expect, it } from "vitest";
import { DEFAULT_FORM, formToInput, productSchema, splitTags } from "./productSchema";

const valid = { ...DEFAULT_FORM, name: "Nankiv", checkUrl: "https://nankiv.example/health" };

function errorsFor(override: Partial<typeof valid>): string[] {
  const result = productSchema.safeParse({ ...valid, ...override });
  return result.success ? [] : result.error.issues.map((i) => i.path.join("."));
}

describe("productSchema", () => {
  it("accepts the defaults plus a name and URL", () => {
    expect(productSchema.safeParse(valid).success).toBe(true);
  });

  it.each([
    [{ name: "" }, "name"],
    [{ name: "x".repeat(61) }, "name"],
    [{ note: "x".repeat(281) }, "note"],
    [{ checkUrl: "ftp://example.com" }, "checkUrl"],
    [{ checkUrl: "example.com" }, "checkUrl"],
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

  it("splitTags drops blanks and duplicates", () => {
    expect(splitTags(" a, ,A,b")).toEqual(["a", "b"]);
  });
});
