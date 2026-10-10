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

function chatUrl(): string {
  if (!configured) return "/api/chat";
  try {
    const host = new URL(configured).hostname;
    const pointsAtLoopback = host === "localhost" || host === "127.0.0.1";
    const pageHost = typeof window === "undefined" ? "" : window.location.hostname;
    const pageIsLoopback = pageHost === "localhost" || pageHost === "127.0.0.1";
    // A baked-in localhost URL is what made production call a backend
    // that does not exist in the browser. Same-origin /api/chat holds the case.
    if (pointsAtLoopback && !pageIsLoopback) return "/api/chat";
  } catch {
    return "/api/chat";
  }
  return `${configured}/chat`;
}

export async function sendMessage(
  message: string,
  threadId?: string | null,
  approve?: boolean | null,
  customerId?: string,
  snapshot?: CaseSnapshot | null,
): Promise<ChatResponse> {
  const res = await fetch(chatUrl(), {
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
