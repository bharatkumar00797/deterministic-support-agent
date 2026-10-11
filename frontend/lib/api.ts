import type { CaseSnapshot, ChatMessage } from "@/lib/types";

export type { CaseSnapshot, ChatMessage };

// The Python API is the only agent. There is no second copy to fall back to.
const PUBLIC_API = "https://deterministic-support-api.vercel.app";

export interface ChatResponse {
  thread_id: string;
  messages: ChatMessage[];
  current_step: string;
  needs_approval: boolean;
  proposed_action?: {
    tool: string;
    args: Record<string, any>;
  } | null;
  tool_result?: Record<string, any> | null;
  snapshot?: CaseSnapshot | null;
  engine?: string | null;
}

export function apiBase(): string {
  const configured = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/+$/, "");
  if (configured) return configured;
  if (typeof window !== "undefined" && window.location.hostname === "localhost") {
    return "http://localhost:8001";
  }
  return PUBLIC_API;
}

export async function sendMessage(
  message: string,
  threadId?: string | null,
  approve?: boolean | null,
  customerId?: string,
  snapshot?: CaseSnapshot | null,
): Promise<ChatResponse> {
  const base = apiBase();
  let res: Response;
  try {
    res = await fetch(`${base}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        thread_id: threadId || undefined,
        customer_id: customerId || undefined,
        approve: approve ?? undefined,
        snapshot: snapshot ?? undefined,
      }),
    });
  } catch {
    throw new Error(`Could not reach the support API at ${base}. Nothing was changed.`);
  }
  if (!res.ok) {
    throw new Error(`The support API returned HTTP ${res.status}. Nothing was changed.`);
  }
  return res.json();
}
