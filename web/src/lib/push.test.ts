import { describe, expect, it } from "vitest";
import { urlBase64ToUint8Array } from "./push";

describe("urlBase64ToUint8Array", () => {
  it("decodes base64url without padding", () => {
    // "hello?" in base64url is aGVsbG8_ ("?" encodes to "_")
    expect(Array.from(urlBase64ToUint8Array("aGVsbG8_"))).toEqual([104, 101, 108, 108, 111, 63]);
  });

  it("decodes a 65-byte uncompressed P-256 public key", () => {
    const key = "B" + "A".repeat(86);
    expect(urlBase64ToUint8Array(key).length).toBe(65);
  });
});
