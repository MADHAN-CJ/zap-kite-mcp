import { HttpError } from "@/lib/server/auth";
import { storeSession } from "@/lib/server/broker";
import { exchangeRequestToken, userFromState } from "@/lib/server/kite";

export const dynamic = "force-dynamic";

const PUBLISHER_DONE = `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width"><title>Done</title></head>
<body style="font-family:system-ui,sans-serif;padding:32px;color:#20251b">
<p>Done. You can close this window and return to /markets.</p>
<script>window.close()</script></body></html>`;

/**
 * Zerodha redirects here after login; the signed `state` names the /markets user. The Kite
 * Publisher popup lands here too, without `state`, after the user places or abandons an order.
 */
export async function GET(req: Request) {
  const url = new URL(req.url);
  const home = new URL("/", url.origin);
  const status = url.searchParams.get("status");
  const requestToken = url.searchParams.get("request_token");
  if (!url.searchParams.get("state")) {
    return new Response(PUBLISHER_DONE, { headers: { "content-type": "text/html" } });
  }
  if ((status && status !== "success") || !requestToken) {
    home.searchParams.set("error", "Zerodha login was cancelled.");
    return Response.redirect(home, 303);
  }
  try {
    const userId = await userFromState(url.searchParams.get("state"));
    const session = await exchangeRequestToken(requestToken);
    await storeSession(userId, session);
    home.searchParams.set("connected", "1");
  } catch (e) {
    const message = e instanceof HttpError ? e.message : "Zerodha login failed.";
    if (!(e instanceof HttpError)) console.error("[kite callback]", e);
    home.searchParams.set("error", message);
  }
  return Response.redirect(home, 303);
}
