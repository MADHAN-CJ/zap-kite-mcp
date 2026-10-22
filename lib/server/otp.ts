import { HttpError } from "./auth";
import { otpHash } from "./crypto";
import { execute, one, query } from "./db";
import { sendEmail } from "./email";
import { loginCodeEmail } from "./emails";

const OTP_TTL_S = 600;
const OTP_COOLDOWN_S = 45;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const normalize = (email: string) => email.trim().toLowerCase();

function isDevLogin(email: string): boolean {
  const dev = process.env.DEV_LOGIN_EMAIL?.trim().toLowerCase();
  return Boolean(dev && process.env.DEV_LOGIN_CODE) && email === dev;
}

export async function requestOtp(rawEmail: string): Promise<void> {
  const email = normalize(rawEmail);
  if (!EMAIL_RE.test(email)) throw new HttpError(400, "Enter a valid email address.");
  if (isDevLogin(email)) return;
  const recent = await one(
    "SELECT id FROM otps WHERE email = $1 AND created_at > now() - make_interval(secs => $2)",
    [email, OTP_COOLDOWN_S],
  );
  if (recent)
    throw new HttpError(429, "A code was just sent. Wait a moment before requesting another.");
  const code = String(Math.floor(100000 + Math.random() * 900000));
  await execute(
    "INSERT INTO otps (email, code_hash, expires_at) VALUES ($1, $2, now() + make_interval(secs => $3))",
    [email, otpHash(code, email), OTP_TTL_S],
  );
  const ok = await sendEmail(email, loginCodeEmail(code));
  if (!ok) throw new HttpError(502, "Could not send the login code. Try again in a moment.");
}

export async function verifyOtp(
  rawEmail: string,
  rawCode: string,
): Promise<{ userId: string; email: string }> {
  const email = normalize(rawEmail);
  const code = rawCode.trim();
  const valid = isDevLogin(email)
    ? code === process.env.DEV_LOGIN_CODE
    : (
        await query<{ id: string }>(
          "UPDATE otps SET consumed_at = now() WHERE email = $1 AND code_hash = $2 " +
            "AND consumed_at IS NULL AND expires_at > now() RETURNING id",
          [email, otpHash(code, email)],
        )
      ).length > 0;
  if (!valid) throw new HttpError(401, "Invalid or expired code.");
  const user = await one<{ id: string; email: string }>(
    "INSERT INTO users (email) VALUES ($1) ON CONFLICT (email) DO UPDATE SET email = excluded.email " +
      "RETURNING id, email",
    [email],
  );
  if (!user) throw new HttpError(500, "Could not create the account.");
  return { userId: user.id, email: user.email };
}
