"use client";

import { useState, useRef, useEffect } from "react";
import { sendMessage, ChatMessage, ChatResponse } from "@/lib/api";
import { Bot, User, Send, CheckCircle, XCircle, Loader2, Shield } from "lucide-react";
import clsx from "clsx";

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "Hi! I'm your deterministic support agent. I can help with refunds, cancellations, and account updates. What do you need today?",
    },
  ]);
  const [input, setInput] = useState("");
  const [threadId, setThreadId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [needsApproval, setNeedsApproval] = useState(false);
  const [proposedAction, setProposedAction] = useState<ChatResponse["proposed_action"]>(null);
  const [currentStep, setCurrentStep] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, needsApproval]);

  const handleSend = async (text?: string, approve?: boolean | null) => {
    const msg = text ?? input.trim();
    if (!msg && approve === undefined) return;

    if (msg) {
      setMessages((prev) => [...prev, { role: "user", content: msg }]);
      setInput("");
    }

    setLoading(true);
    setError(null);
    setNeedsApproval(false);

    try {
      const res = await sendMessage(msg || "continue", threadId, approve);
      setThreadId(res.thread_id);
      setCurrentStep(res.current_step);
      setNeedsApproval(res.needs_approval && res.current_step === "awaiting_approval");
      setProposedAction(res.proposed_action);

      // Append only new assistant messages
      const newAssistant = res.messages.filter((m) => m.role === "assistant");
      if (newAssistant.length) {
        setMessages((prev) => {
          // Avoid duplicating the last assistant message if it's the same
          const last = prev[prev.length - 1];
          const toAdd = newAssistant.filter(
            (m) => !(last && last.role === "assistant" && last.content === m.content)
          );
          return [...prev, ...toAdd];
        });
      }
    } catch (err: any) {
      setError(err.message || "Failed to reach the agent");
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = () => handleSend("approve", true);
  const handleReject = () => handleSend("reject", false);

  return (
    <div className="min-h-screen flex flex-col max-w-3xl mx-auto bg-white shadow-xl">
      {/* Header */}
      <header className="border-b border-slate-200 px-5 py-4 flex items-center gap-3 bg-slate-900 text-white">
        <div className="p-2 bg-sky-500/20 rounded-lg">
          <Shield className="w-5 h-5 text-sky-400" />
        </div>
        <div>
          <h1 className="font-semibold">Deterministic Support Agent</h1>
          <p className="text-xs text-slate-400">
            LangGraph · Code-controlled actions · HITL approvals
          </p>
        </div>
        {currentStep && (
          <span className="ml-auto text-xs bg-slate-700 px-2 py-1 rounded">
            step: {currentStep}
          </span>
        )}
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        {messages.map((m, i) => (
          <div
            key={i}
            className={clsx(
              "flex gap-3",
              m.role === "user" ? "justify-end" : "justify-start"
            )}
          >
            {m.role === "assistant" && (
              <div className="w-8 h-8 rounded-full bg-sky-100 flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4 text-sky-600" />
              </div>
            )}
            <div
              className={clsx(
                "max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
                m.role === "user"
                  ? "bg-sky-600 text-white rounded-br-md"
                  : "bg-slate-100 text-slate-800 rounded-bl-md"
              )}
            >
              <div className="whitespace-pre-wrap">{m.content}</div>
            </div>
            {m.role === "user" && (
              <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center shrink-0">
                <User className="w-4 h-4 text-slate-600" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-sky-100 flex items-center justify-center">
              <Loader2 className="w-4 h-4 text-sky-600 animate-spin" />
            </div>
            <div className="bg-slate-100 rounded-2xl rounded-bl-md px-4 py-3 text-sm text-slate-500">
              Thinking…
            </div>
          </div>
        )}

        {/* Approval card */}
        {needsApproval && proposedAction && !loading && (
          <div className="ml-11 border border-amber-200 bg-amber-50 rounded-xl p-4 space-y-3">
            <div className="text-sm font-medium text-amber-900">
              Approval required
            </div>
            <div className="text-xs text-amber-800 font-mono bg-white/60 p-2 rounded">
              Tool: <strong>{proposedAction.tool}</strong>
              <pre className="mt-1 text-[11px]">
                {JSON.stringify(proposedAction.args, null, 2)}
              </pre>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleApprove}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 text-white text-sm font-medium rounded-lg hover:bg-emerald-700"
              >
                <CheckCircle className="w-4 h-4" /> Approve
              </button>
              <button
                onClick={handleReject}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-300 text-slate-700 text-sm font-medium rounded-lg hover:bg-slate-50"
              >
                <XCircle className="w-4 h-4" /> Reject
              </button>
            </div>
          </div>
        )}

        {error && (
          <div className="ml-11 text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
            {error}
            <div className="text-xs mt-1 text-red-500">
              Make sure the backend is running on port 8001.
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-slate-200 p-4 bg-white">
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
            placeholder="Ask for a refund, cancel a subscription…"
            disabled={loading || needsApproval}
            className="flex-1 border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500 disabled:bg-slate-50"
          />
          <button
            type="submit"
            disabled={loading || !input.trim() || needsApproval}
            className="px-4 py-2.5 bg-sky-600 text-white rounded-xl hover:bg-sky-700 disabled:opacity-50 transition"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
        <p className="text-[11px] text-slate-400 mt-2 text-center">
          Try: “I want a refund for order 12345” or “Cancel my subscription”
        </p>
      </div>
    </div>
  );
}
