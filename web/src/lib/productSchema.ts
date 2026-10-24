import { z } from "zod";
import type { Product, ProductInput } from "./types";

// Same rules as the API's ProductInput (HANDOVER §3.3), so mistakes show up before saving.

const STATUS_PART = /^(\d{3})(?:-(\d{3}))?$/;

function validStatusSpec(spec: string): boolean {
  const parts = spec.replace(/\s+/g, "").split(",");
  return parts.every((part) => {
    const m = STATUS_PART.exec(part);
    if (!m) return false;
    const low = Number(m[1]);
    const high = Number(m[2] ?? m[1]);
    return low >= 100 && low <= high && high <= 599;
  });
}

/** "myapp.vercel.app" -> "https://myapp.vercel.app"; anything with a scheme is left alone. */
export function withScheme(value: string): string {
  const v = value.trim();
  return v === "" || v.includes("://") ? v : `https://${v}`;
}

function isHttpUrl(value: string): boolean {
  try {
    const url = new URL(withScheme(value));
    return (url.protocol === "http:" || url.protocol === "https:") && url.hostname !== "" && !url.username;
  } catch {
    return false;
  }
}

/** A product added with just a link is named after its site: "https://www.nankiv.app/health" -> "nankiv.app". */
export function nameFromUrl(value: string): string {
  try {
    return new URL(withScheme(value)).hostname.replace(/^www\./, "").slice(0, 60);
  } catch {
    return "";
  }
}

const BAD_URL = "Use a web address like myapp.vercel.app or https://example.com/health";

const httpUrl = z.string().trim().min(1, "Paste the link to check").max(2048).refine(isHttpUrl, BAD_URL);

const optionalUrl = z
  .string()
  .trim()
  .max(2048)
  .refine((v) => v === "" || isHttpUrl(v), BAD_URL);

const int = (min: number, max: number, what: string) =>
  z
    .number({ invalid_type_error: `Enter ${what}` })
    .int(`Use a whole number`)
    .min(min, `Minimum is ${min}`)
    .max(max, `Maximum is ${max}`);

export const productSchema = z
  .object({
    name: z.string().trim().max(60, "60 characters at most"), // blank: named after the site
    kind: z.enum(["personal", "client"]),
    note: z.string().trim().max(280, "280 characters at most"),
    checkUrl: httpUrl,
    method: z.enum(["GET", "HEAD"]),
    expectedStatus: z
      .string()
      .trim()
      .min(1, "Enter the expected status, e.g. 200-399")
      .refine(validStatusSpec, "Use codes or ranges like 200-399 or 200,301"),
    keyword: z.string().trim().max(200, "200 characters at most"),
    timeoutMs: int(1000, 15000, "a timeout in ms"),
    intervalMin: z.union([z.literal(1), z.literal(5)]),
    latencyWarnMs: int(100, 60000, "a latency in ms"),
    openAfter: int(1, 5, "a number of checks"),
    resolveAfter: int(1, 5, "a number of checks"),
    sloTarget: z
      .number({ invalid_type_error: "Enter a percentage" })
      .min(90, "Minimum is 90")
      .max(99.99, "Maximum is 99.99"),
    liveUrl: optionalUrl,
    githubUrl: optionalUrl,
    stackText: z
      .string()
      .refine((v) => splitTags(v).length <= 8, "8 tags at most")
      .refine((v) => splitTags(v).every((t) => t.length <= 30), "Each tag is 30 characters at most"),
    sortOrder: int(0, 99999, "a sort order"),
  })
  .refine((v) => !(v.method === "HEAD" && v.keyword !== ""), {
    path: ["keyword"],
    message: "Keyword checks need GET (HEAD responses have no body)",
  });

export type ProductFormValues = z.infer<typeof productSchema>;

export function splitTags(text: string): string[] {
  const seen = new Set<string>();
  const tags: string[] = [];
  for (const raw of text.split(",")) {
    const tag = raw.trim();
    if (tag && !seen.has(tag.toLowerCase())) {
      seen.add(tag.toLowerCase());
      tags.push(tag);
    }
  }
  return tags;
}

export const DEFAULT_FORM: ProductFormValues = {
  name: "",
  kind: "personal",
  note: "",
  checkUrl: "",
  method: "GET",
  expectedStatus: "200-399",
  keyword: "",
  timeoutMs: 10000,
  intervalMin: 1,
  latencyWarnMs: 2000,
  openAfter: 2,
  resolveAfter: 2,
  sloTarget: 99.5,
  liveUrl: "",
  githubUrl: "",
  stackText: "",
  sortOrder: 100,
};

export function productToForm(p: Product): ProductFormValues {
  return {
    name: p.name,
    kind: p.kind,
    note: p.note,
    checkUrl: p.checkUrl,
    method: p.method,
    expectedStatus: p.expectedStatus,
    keyword: p.keyword ?? "",
    timeoutMs: p.timeoutMs,
    intervalMin: p.intervalMin,
    latencyWarnMs: p.latencyWarnMs,
    openAfter: p.openAfter,
    resolveAfter: p.resolveAfter,
    sloTarget: p.sloTarget,
    liveUrl: p.liveUrl ?? "",
    githubUrl: p.githubUrl ?? "",
    stackText: p.stack.join(", "),
    sortOrder: p.sortOrder,
  };
}

export function formToInput(v: ProductFormValues): ProductInput {
  return {
    name: v.name.trim() || nameFromUrl(v.checkUrl),
    kind: v.kind,
    note: v.note.trim(),
    checkUrl: withScheme(v.checkUrl),
    method: v.method,
    expectedStatus: v.expectedStatus.replace(/\s+/g, ""),
    keyword: v.keyword.trim() || null,
    timeoutMs: v.timeoutMs,
    intervalMin: v.intervalMin,
    latencyWarnMs: v.latencyWarnMs,
    openAfter: v.openAfter,
    resolveAfter: v.resolveAfter,
    sloTarget: v.sloTarget,
    liveUrl: withScheme(v.liveUrl) || null,
    githubUrl: withScheme(v.githubUrl) || null,
    stack: splitTags(v.stackText),
    sortOrder: v.sortOrder,
  };
}
