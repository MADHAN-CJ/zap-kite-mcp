import { errorResponse, requireUser } from "@/lib/server/auth";
import { brokerStatus, disconnect } from "@/lib/server/broker";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  try {
    const user = await requireUser(req);
    return Response.json(await brokerStatus(user.userId));
  } catch (e) {
    return errorResponse(e);
  }
}

export async function DELETE(req: Request) {
  try {
    const user = await requireUser(req);
    await disconnect(user.userId);
    return Response.json(await brokerStatus(user.userId));
  } catch (e) {
    return errorResponse(e);
  }
}
