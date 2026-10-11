"use client";

import { useEffect, useRef, useState } from "react";
import { sendMessage, ChatMessage, ChatResponse, CaseSnapshot } from "@/lib/api";
import { PROMPTS } from "@/lib/deterministic-agent";
import { Bot, CheckCircle, Loader2, Send, Shield, User, XCircle } from "lucide-react";
import clsx from "clsx";

const GREETING =
  "Mira Sen is on the line. Refunds and cancellations stop at the gate until you approve them. Nothing moves until that click.";

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "assistant", content: GREETING },
  ]);
  const [input, setInput] = useState("");
  const [threadId, setThreadId] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<CaseSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [needsApproval, setNeedsApproval] = useState(false);
  const [proposedAction, setProposedAction] = useState<ChatResponse["proposed_action"]>(null);
  const [currentStep, setCurrentStep] = useState("ready");
  const [engine, setEngine] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);
  const snapshotRef = useRef<CaseSnapshot | null>(null);
  const threadRef = useRef<string | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, needsApproval, loading]);

  const handleSend = async (text?: string, approve?: boolean | null) => {
    const msg = (text ?? input).trim();
    if (!msg && approve == null) return;

    if (msg && approve == null) {
      setMessages((prev) => [...prev, { role: "user", content: msg }]);
      setInput("");
    }

    setLoading(true);
    setError(null);

    try {
      const res = await sendMessage(
        msg,
        threadRef.current,
        approve,
        undefined,
        snapshotRef.current,
      );
      threadRef.current = res.thread_id;
      setThreadId(res.thread_id);
      if (res.snapshot) {
        snapshotRef.current = res.snapshot;
        setSnapshot(res.snapshot);
      }
      setCurrentStep(res.current_step);
      if (res.engine) setEngine(res.engine);
      const waiting = Boolean(res.needs_approval && res.current_step === "awaiting_approval");
      setNeedsApproval(waiting);
      setProposedAction(waiting ? res.proposed_action ?? null : null);

      const replies = res.messages.filter((m) => m.role === "assistant");
      if (replies.length) {
        setMessages((prev) => [...prev, ...replies]);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to reach the agent";
      setError(message);
      if (approve == null) {
        setNeedsApproval(Boolean(snapshotRef.current?.needs_approval));
      }
    } finally {
      setLoading(false);
    }
  };

  const ledger = snapshot?.ledger;
  const audit = snapshot?.audit ?? [];

  return (
    <div className="h-dvh bg-slate-100 text-slate-900">
      <div className="mx-auto flex h-dvh max-w-6xl flex-col lg:flex-row">
        <section className="flex min-h-0 flex-1 flex-col bg-white lg:border-r lg:border-slate-200">
          <header className="flex shrink-0 items-center gap-3 border-b border-slate-200 bg-slate-900 px-5 py-4 text-white">
            <div className="rounded-lg bg-sky-500/20 p-2">
              <Shield className="h-5 w-5 text-sky-400" />
            </div>
            <div className="min-w-0">
              <h1 className="font-semibold">Deterministic Support Agent</h1>
              <p className="text-xs text-slate-400">
                Case stays in the browser. Tools run only after Approve.
              </p>
            </div>
            <span className="ml-auto shrink-0 rounded bg-slate-700 px-2 py-1 text-xs">
              step: {currentStep || "ready"}
              {engine === "langgraph" ? " · LangGraph" : engine === "rules" ? " · same rules" : ""}
            </span>
          </header>

          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-5">
            {messages.map((m, i) => (
              <div
                key={i}
                className={clsx("flex gap-3", m.role === "user" ? "justify-end" : "justify-start")}
              >
                {m.role === "assistant" && (
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-sky-100">
                    <Bot className="h-4 w-4 text-sky-600" />
                  </div>
                )}
                <div
                  className={clsx(
                    "max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
                    m.role === "user"
                      ? "rounded-br-md bg-sky-600 text-white"
                      : "rounded-bl-md bg-slate-100 text-slate-800",
                  )}
                >
                  <div className="whitespace-pre-wrap">{m.content}</div>
                </div>
                {m.role === "user" && (
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-200">
                    <User className="h-4 w-4 text-slate-600" />
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="flex gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-sky-100">
                  <Loader2 className="h-4 w-4 animate-spin text-sky-600" />
                </div>
                <div className="rounded-2xl rounded-bl-md bg-slate-100 px-4 py-3 text-sm text-slate-500">
                  Checking the case…
                </div>
              </div>
            )}

            {error && (
              <div className="rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-600">
                {error}
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div className="shrink-0 border-t border-slate-200 bg-white p-4">
            {needsApproval && proposedAction && !loading && (
              <div className="mb-3 rounded-xl border border-amber-200 bg-amber-50 p-4">
                <div className="text-sm font-medium text-amber-950">Approval required before this tool runs</div>
                <div className="mt-2 rounded bg-white/70 p-2 font-mono text-xs text-amber-900">
                  Tool: <strong>{proposedAction.tool}</strong>
                  <pre className="mt-1 text-[11px]">{JSON.stringify(proposedAction.args, null, 2)}</pre>
                </div>
                <div className="mt-3 flex gap-2">
                  <button
                    type="button"
                    onClick={() => handleSend("", true)}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-700"
                  >
                    <CheckCircle className="h-4 w-4" /> Approve
                  </button>
                  <button
                    type="button"
                    onClick={() => handleSend("", false)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    <XCircle className="h-4 w-4" /> Reject
                  </button>
                </div>
              </div>
            )}

            {!needsApproval && (
            <div className="mb-2 flex flex-wrap gap-2">
              {PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  disabled={loading}
                  onClick={() => handleSend(prompt)}
                  className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-600 hover:border-sky-300 hover:text-sky-700 disabled:opacity-40"
                >
                  {prompt}
                </button>
              ))}
            </div>
            )}

            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSend();
              }}
              className="flex gap-2"
            >
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={needsApproval ? "Approve or reject the proposal above" : "Ask for a refund, a cancel, a status…"}
                disabled={loading || needsApproval}
                className="flex-1 rounded-xl border border-slate-200 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500 disabled:bg-slate-50"
              />
              <button
                type="submit"
                disabled={loading || !input.trim() || needsApproval}
                className="rounded-xl bg-sky-600 px-4 py-2.5 text-white hover:bg-sky-700 disabled:opacity-50"
              >
                <Send className="h-4 w-4" />
              </button>
            </form>
          </div>
        </section>

        <aside className="max-h-[40vh] shrink-0 overflow-y-auto border-t border-slate-200 bg-slate-50 p-5 lg:max-h-none lg:w-80 lg:border-t-0">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Case ledger</h2>
          <dl className="mt-3 space-y-2 text-sm">
            <Row label="Customer" value="Mira Sen" />
            <Row label="Thread" value={threadId || "THR-1042"} />
            <Row label="Email" value={ledger?.email || "mira.sen@northline.test"} />
            <Row label="Phone" value={ledger?.phone || "+1 415 555 0142"} />
            <Row label="Address" value={ledger?.address || "18 Harbor Lane, Oakland"} />
            <Row label="Subscription" value={ledger?.cancelled ? "Northline Plus cancelled" : "Northline Plus active"} />
            <Row label="Refunded" value={(ledger?.refunded || ["ORD-77821"]).join(", ")} />
          </dl>

          <h2 className="mt-6 text-xs font-semibold uppercase tracking-wide text-slate-500">Audit</h2>
          <ol className="mt-3 space-y-2">
            {(audit.length ? audit : [{ step: "Open", detail: "Waiting for the first turn" }]).map((event, i) => (
              <li key={i} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                <div className="text-[11px] font-semibold uppercase text-sky-700">{event.step}</div>
                <div className="text-xs text-slate-600">{event.detail}</div>
              </li>
            ))}
          </ol>
        </aside>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right text-slate-800">{value}</dd>
    </div>
  );
}
