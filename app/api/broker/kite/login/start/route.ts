import { errorResponse, requireUser } from "@/lib/server/auth";
import { loginUrl } from "@/lib/server/kite";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  try {
    const user = await requireUser(req);
    return Response.json({ loginUrl: await loginUrl(user.userId) });
  } catch (e) {
    return errorResponse(e);
  }
}
