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
  // The production bundle inlines NEXT_PUBLIC_API_URL. It is currently
  // https://deterministic-support-api.vercel.app, and that host returns
  // FUNCTION_INVOCATION_FAILED for every path, including /health. The
  // same-origin route already runs the gate. Only a laptop page may call
  // a laptop API.
  if (typeof window === "undefined") return "/api/chat";
  const pageHost = window.location.hostname;
  const pageIsLoopback = pageHost === "localhost" || pageHost === "127.0.0.1";
  if (!pageIsLoopback || !configured) return "/api/chat";
  try {
    const host = new URL(configured).hostname;
    if (host !== "localhost" && host !== "127.0.0.1") return "/api/chat";
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
