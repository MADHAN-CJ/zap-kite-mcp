import { createCipheriv, createDecipheriv, createHash, createHmac, randomBytes } from "node:crypto";

/**
 * Byte-compatible with src/zap_kite_mcp/crypto.py: the Python server decrypts tokens this app
 * stores and verifies login codes this app hashes.
 */

const VERSION = "v1";

function requireSecret(name: "SESSION_SECRET" | "CREDS_ENCRYPTION_KEY"): string {
  const value = process.env[name];
  if (!value || value.length < 32) {
    throw new Error(`${name} must be set to at least 32 characters.`);
  }
  return value;
}

const b64url = (buf: Buffer): string => buf.toString("base64url");
const unb64url = (text: string): Buffer => Buffer.from(text, "base64url");

function aesKey(secret: string): Buffer {
  return createHash("sha256").update(secret).digest();
}

export function encrypt(plaintext: string, secret = requireSecret("CREDS_ENCRYPTION_KEY")): string {
  const nonce = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", aesKey(secret), nonce);
  const sealed = Buffer.concat([
    cipher.update(plaintext, "utf8"),
    cipher.final(),
    cipher.getAuthTag(),
  ]);
  return `${VERSION}:${b64url(nonce)}:${b64url(sealed)}`;
}

export function decrypt(stored: string, secret = requireSecret("CREDS_ENCRYPTION_KEY")): string {
  const [version, nonce, sealed] = stored.split(":");
  if (version !== VERSION || !nonce || !sealed) {
    throw new Error(`unsupported ciphertext version ${version ?? ""}`);
  }
  const data = unb64url(sealed);
  const decipher = createDecipheriv("aes-256-gcm", aesKey(secret), unb64url(nonce));
  decipher.setAuthTag(data.subarray(data.length - 16));
  return Buffer.concat([
    decipher.update(data.subarray(0, data.length - 16)),
    decipher.final(),
  ]).toString("utf8");
}

function mac(secret: string, purpose: string, message: string): Buffer {
  const key = createHash("sha256").update(`${purpose}:${secret}`).digest();
  return createHmac("sha256", key).update(message).digest();
}

export function otpHash(
  code: string,
  email: string,
  secret = requireSecret("SESSION_SECRET"),
): string {
  return mac(secret, "otp", `${code}:${email.toLowerCase()}`).toString("hex");
}

export function sessionKey(): Uint8Array {
  return new Uint8Array(
    createHash("sha256")
      .update(`web-session:${requireSecret("SESSION_SECRET")}`)
      .digest(),
  );
}
