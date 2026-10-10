import { NextResponse } from "next/server";
import { runChat, type CaseSnapshot } from "@/lib/deterministic-agent";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const body = (await request.json()) as {
    message?: string;
    thread_id?: string | null;
    approve?: boolean | null;
    snapshot?: CaseSnapshot | null;
  };

  const result = runChat({
    message: body.message,
    thread_id: body.thread_id,
    approve: body.approve,
    snapshot: body.snapshot,
  });

  return NextResponse.json(result);
}
