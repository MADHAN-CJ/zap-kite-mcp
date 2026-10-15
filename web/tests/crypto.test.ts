import { describe, expect, it } from "vitest";
import { decrypt, encrypt, otpHash } from "@/lib/server/crypto";

const SECRET = "0123456789abcdef0123456789abcdef";
// Produced by src/zap_kite_mcp/crypto.py with the same secret.
const PYTHON_CIPHERTEXT = "v1:osztS8omxCt-t-Qj:6rOg7k93dR4NLtzOnu4Wn7UeCuHm1JOwlswkFj7DAw9omA";
const PYTHON_OTP_HASH = "9910df133664d5f78bcd454cc46f78b3bbb54daf11e1667c005f4aa4221b35f4";

describe("crypto compatibility with the Python server", () => {
  it("decrypts a Python-produced token", () => {
    expect(decrypt(PYTHON_CIPHERTEXT, SECRET)).toBe("access-token-value");
  });

  it("round-trips and is readable by the same format", () => {
    const stored = encrypt("another-token", SECRET);
    expect(stored.startsWith("v1:")).toBe(true);
    expect(stored.split(":")).toHaveLength(3);
    expect(decrypt(stored, SECRET)).toBe("another-token");
  });

  it("hashes login codes identically", () => {
    expect(otpHash("123456", "Dev@Example.com", SECRET)).toBe(PYTHON_OTP_HASH);
  });

  it("rejects tampering", () => {
    const stored = encrypt("x", SECRET);
    expect(() => decrypt(`${stored.slice(0, -2)}AA`, SECRET)).toThrow();
  });
});
