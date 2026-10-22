import { readFileSync } from "node:fs";
import path from "node:path";

/** Transactional emails in the /markets brand: HTML plus a plain-text twin. */

const INK = "#20251b";
const MUTED = "#62675f";
const SURFACE = "#f7f6f2";
const BORDER = "#e4e7dc";
const BUTTON = "#171a17";
const SERIF = "'Libre Baskerville', Georgia, 'Times New Roman', serif";
const SANS = "Onest, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif";
const MONO = "'Departure Mono', ui-monospace, Menlo, Consolas, monospace";

export interface Email {
  subject: string;
  html: string;
  text: string;
}

const esc = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

let logomarkPaths: string | null = null;
function logomark(): string {
  if (logomarkPaths === null) {
    try {
      const svg = readFileSync(
        path.join(process.cwd(), "public/brand/markets-logomark-mono.svg"),
        "utf8",
      );
      logomarkPaths = (svg.match(/<path[^>]*\/>/g) ?? []).join("");
    } catch {
      logomarkPaths = "";
    }
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" width="62" height="32" viewBox="0 0 341 174" fill="#34432e" role="img" aria-label="/markets">${logomarkPaths}</svg>`;
}

function shell(preheader: string, headline: string, body: string, footer: string): string {
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<meta name="color-scheme" content="light"><title>${esc(headline)}</title></head>
<body style="margin:0;padding:0;background:#ffffff;color:${INK}">
<div style="display:none;max-height:0;overflow:hidden;opacity:0">${esc(preheader)}</div>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#ffffff">
<tr><td align="center" style="padding:32px 16px">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:520px">
<tr><td style="padding:0 0 28px">
  <table role="presentation" cellspacing="0" cellpadding="0"><tr>
    <td style="padding-right:10px;vertical-align:middle">${logomark()}</td>
    <td style="vertical-align:middle"><span style="font-family:${SANS};font-size:18px;font-weight:600;color:${INK};letter-spacing:-.01em">/markets</span></td>
  </tr></table>
</td></tr>
<tr><td style="padding:0 0 12px;font-family:${SERIF};font-size:30px;line-height:1.2;font-weight:500;letter-spacing:-.02em;color:${INK}">${headline}</td></tr>
<tr><td style="font-family:${SANS};font-size:16px;line-height:1.65;color:${INK}">${body}</td></tr>
<tr><td style="padding:32px 0 0;border-top:1px solid ${BORDER};font-family:${SANS};font-size:13px;line-height:1.6;color:${MUTED}">${footer}</td></tr>
</table></td></tr></table></body></html>`;
}

export function loginCodeEmail(code: string): Email {
  const codeHtml = `<div style="margin:8px 0 24px;padding:20px 24px;border-radius:14px;background:${SURFACE};font-family:${MONO};font-size:34px;letter-spacing:.32em;color:${INK};text-align:center">${esc(code)}</div>`;
  const body =
    `<p style="margin:0 0 16px">Enter this code to sign in. It expires in 10 minutes.</p>${codeHtml}` +
    `<p style="margin:0 0 16px;color:${MUTED}">If you didn't request it, ignore this email. Nobody can use the code without your inbox.</p>`;
  const footer = "/markets is read-only. It can never place, change or cancel an order.";
  return {
    subject: `${code} is your /markets login code`,
    html: shell(`Your login code is ${code}`, "Your login code", body, footer),
    text:
      `Your /markets login code is ${code}. It expires in 10 minutes.\n\n` +
      "If you didn't request it, ignore this email.\n\n" +
      footer,
  };
}

export { BUTTON, INK, MONO, MUTED, SANS, SERIF, SURFACE };
