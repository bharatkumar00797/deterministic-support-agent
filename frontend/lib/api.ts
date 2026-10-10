import type { CaseSnapshot } from "@/lib/deterministic-agent";

const configured = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

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
}

export type { CaseSnapshot };

export async function sendMessage(
  message: string,
  threadId?: string | null,
  approve?: boolean | null,
  customerId?: string,
  snapshot?: CaseSnapshot | null,
): Promise<ChatResponse> {
  const url = configured ? `${configured}/chat` : "/api/chat";
  const res = await fetch(url, {
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

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}
