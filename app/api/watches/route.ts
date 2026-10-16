import { errorResponse, requireUser } from "@/lib/server/auth";
import { listWatches } from "@/lib/server/watches";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  try {
    const user = await requireUser(req);
    return Response.json({ watches: await listWatches(user.userId) });
  } catch (e) {
    return errorResponse(e);
  }
}
