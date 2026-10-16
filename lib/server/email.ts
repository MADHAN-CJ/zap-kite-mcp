const RESEND_URL = "https://api.resend.com/emails";

export async function sendEmail(to: string, subject: string, text: string): Promise<boolean> {
  const key = process.env.RESEND_API_KEY;
  if (!key) {
    console.warn(`[email] RESEND_API_KEY unset; not sent to ${to}: ${subject}\n${text}`);
    return true;
  }
  const res = await fetch(RESEND_URL, {
    method: "POST",
    headers: { authorization: `Bearer ${key}`, "content-type": "application/json" },
    body: JSON.stringify({
      from: process.env.EMAIL_FROM ?? "Zap <no-reply@example.com>",
      to: [to],
      subject,
      text,
    }),
  });
  if (!res.ok) console.error("[email] send failed:", res.status, (await res.text()).slice(0, 200));
  return res.ok;
}
