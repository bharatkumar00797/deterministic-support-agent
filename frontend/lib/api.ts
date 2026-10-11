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
  engine?: "rules" | "langgraph" | string | null;
}

export type { CaseSnapshot };

function isLoopback(host: string): boolean {
  return host === "localhost" || host === "127.0.0.1";
}

function chatUrl(): string {
  // A loopback API URL only works when the page itself is on that laptop.
  // A public URL is the LangGraph service. Same-origin /api/chat is the
  // fallback when nothing public is configured.
  if (typeof window === "undefined" || !configured) return "/api/chat";
  let apiHost = "";
  try {
    apiHost = new URL(configured).hostname;
  } catch {
    return "/api/chat";
  }
  const pageIsLoopback = isLoopback(window.location.hostname);
  if (isLoopback(apiHost)) return pageIsLoopback ? `${configured}/chat` : "/api/chat";
  return `${configured}/chat`;
}

async function postChat(url: string, payload: Record<string, unknown>): Promise<ChatResponse> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function sendMessage(
  message: string,
  threadId?: string | null,
  approve?: boolean | null,
  customerId?: string,
  snapshot?: CaseSnapshot | null,
): Promise<ChatResponse> {
  const payload = {
    message,
    thread_id: threadId || undefined,
    customer_id: customerId || undefined,
    approve: approve ?? undefined,
    snapshot: snapshot ?? undefined,
  };
  const primary = chatUrl();
  try {
    return await postChat(primary, payload);
  } catch (err) {
    if (primary === "/api/chat") throw err;
    return postChat("/api/chat", payload);
  }
}
