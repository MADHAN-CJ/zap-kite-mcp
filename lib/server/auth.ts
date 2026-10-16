import { jwtVerify, SignJWT } from "jose";
import { sessionKey } from "./crypto";

export class HttpError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

const SESSION_DAYS = 30;

export interface SessionUser {
  userId: string;
  email: string;
}

export async function signSession(user: SessionUser): Promise<string> {
  return new SignJWT({ email: user.email })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(user.userId)
    .setIssuedAt()
    .setExpirationTime(`${SESSION_DAYS}d`)
    .sign(sessionKey());
}

export async function verifySession(token: string): Promise<SessionUser | null> {
  try {
    const { payload } = await jwtVerify(token, sessionKey());
    if (!payload.sub || typeof payload.email !== "string") return null;
    return { userId: payload.sub, email: payload.email };
  } catch {
    return null;
  }
}

export async function requireUser(req: Request): Promise<SessionUser> {
  const header = req.headers.get("authorization");
  const token = header?.startsWith("Bearer ") ? header.slice(7).trim() : null;
  if (!token) throw new HttpError(401, "Sign in to continue.");
  const user = await verifySession(token);
  if (!user) throw new HttpError(401, "Your session has expired. Sign in again.");
  return user;
}

export function errorResponse(e: unknown): Response {
  if (e instanceof HttpError) return Response.json({ error: e.message }, { status: e.status });
  console.error("[api] unhandled error:", e instanceof Error ? e.message : e);
  return Response.json({ error: "Something went wrong." }, { status: 500 });
}
