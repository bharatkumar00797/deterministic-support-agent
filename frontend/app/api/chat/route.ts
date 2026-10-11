import { NextResponse } from "next/server";
import { runChat, type CaseSnapshot } from "@/lib/deterministic-agent";

export const dynamic = "force-dynamic";

const upstream = (process.env.SUPPORT_API_URL || "").replace(/\/$/, "");

export async function POST(request: Request) {
  const body = (await request.json()) as {
    message?: string;
    thread_id?: string | null;
    approve?: boolean | null;
    snapshot?: CaseSnapshot | null;
    customer_id?: string;
  };

  // Server-only. The browser must not be given a localhost API URL:
  // that is the failure that kept sending production at a laptop.
  if (upstream) {
    try {
      const res = await fetch(`${upstream}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        const data = await res.json();
        return NextResponse.json({ ...data, engine: data.engine || "langgraph" });
      }
    } catch {
      // The in-process rules below match the graph, so a down API still answers.
    }
  }

  const result = runChat({
    message: body.message,
    thread_id: body.thread_id,
    approve: body.approve,
    snapshot: body.snapshot,
  });

  return NextResponse.json(result);
}
