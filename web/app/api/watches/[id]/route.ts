import { z } from "zod";
import { errorResponse, requireUser } from "@/lib/server/auth";
import { mutateWatch } from "@/lib/server/watches";

export const dynamic = "force-dynamic";

const bodySchema = z.object({ action: z.enum(["pause", "resume", "cancel"]) });

export async function PATCH(req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const user = await requireUser(req);
    const { id } = await params;
    const parsed = bodySchema.safeParse(await req.json().catch(() => null));
    if (!parsed.success) {
      return Response.json(
        { error: "Expected { action: pause | resume | cancel }." },
        { status: 400 },
      );
    }
    return Response.json({ watch: await mutateWatch(user.userId, id, parsed.data.action) });
  } catch (e) {
    return errorResponse(e);
  }
}
