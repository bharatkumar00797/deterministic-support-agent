export type Intent =
  | "refund"
  | "cancel"
  | "update_account"
  | "order_status"
  | "escalate"
  | "other";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ProposedAction {
  tool: "process_refund" | "cancel_subscription" | "update_account";
  args: Record<string, string | number>;
}

export interface AuditEvent {
  step: string;
  detail: string;
}

export interface Ledger {
  refunded: string[];
  cancelled: boolean;
  email: string;
  phone: string;
  address: string;
}

export interface CaseFile {
  threadId: string;
  customerId: string;
  customerName: string;
  intent: Intent | null;
  step: string;
  needsApproval: boolean;
  proposed: ProposedAction | null;
  approved: boolean | null;
  toolResult: Record<string, unknown> | null;
  error: string | null;
  messages: ChatMessage[];
  audit: AuditEvent[];
  ledger: Ledger;
}

export interface CatalogOrder {
  id: string;
  item: string;
  amount: number;
  status: "delivered" | "refunded" | "shipped";
}

export const ORDERS: CatalogOrder[] = [
  { id: "ORD-12345", item: "Wool overshirt", amount: 49.99, status: "delivered" },
  { id: "ORD-77821", item: "Leather weekender", amount: 129, status: "refunded" },
  { id: "ORD-44002", item: "Linen socks, 3-pack", amount: 18.5, status: "shipped" },
];

export const SUBSCRIPTION = {
  id: "SUB-98765",
  name: "Northline Plus",
  price: 12,
};

const GREETING =
  "Mira Sen is on the line. I can refund an order, cancel Northline Plus, check a shipment, or change the account. Risky tools stop at the gate until you approve them.";

export function createCase(): CaseFile {
  return {
    threadId: "THR-1042",
    customerId: "CUST-DEMO-001",
    customerName: "Mira Sen",
    intent: null,
    step: "ready",
    needsApproval: false,
    proposed: null,
    approved: null,
    toolResult: null,
    error: null,
    messages: [{ role: "assistant", content: GREETING }],
    audit: [{ step: "Open", detail: "Case opened for Mira Sen" }],
    ledger: {
      refunded: ["ORD-77821"],
      cancelled: false,
      email: "mira.sen@northline.test",
      phone: "+1 415 555 0142",
      address: "18 Harbor Lane, Oakland",
    },
  };
}

export function applyTurn(
  prev: CaseFile,
  raw: string,
  decision?: boolean | null,
): CaseFile {
  const text = raw.trim();
  const next: CaseFile = {
    ...prev,
    messages: [...prev.messages],
    audit: [...prev.audit],
    ledger: {
      ...prev.ledger,
      refunded: [...prev.ledger.refunded],
    },
    error: null,
  };

  if (text) next.messages.push({ role: "user", content: text });

  if (prev.step === "awaiting_approval" && decision != null) {
    return resolveGate(next, prev, decision);
  }

  const intent = classify(text);
  next.intent = intent;
  next.approved = null;
  next.proposed = null;
  next.needsApproval = false;
  next.toolResult = null;
  next.audit.push({ step: "Classify", detail: labelIntent(intent) });

  if (intent === "refund") return proposeRefund(next, text);
  if (intent === "cancel") return proposeCancel(next, text);
  if (intent === "update_account") return runUpdate(next, text);
  if (intent === "order_status") return runStatus(next, text);
  if (intent === "escalate") return runEscalate(next);
  return askClarify(next);
}

function resolveGate(next: CaseFile, prev: CaseFile, approved: boolean): CaseFile {
  const proposed = prev.proposed;
  next.proposed = proposed;
  next.intent = prev.intent;
  next.approved = approved;

  if (!approved || !proposed) {
    next.needsApproval = false;
    next.step = "rejected";
    const tool = proposed?.tool ?? "the proposed tool";
    const reply = `Rejected. ${tool} was not executed. Mira's ledger is unchanged.`;
    next.messages.push({ role: "assistant", content: reply });
    next.audit.push({ step: "Gate", detail: "Human rejected the proposal" });
    return next;
  }

  next.needsApproval = false;
  next.audit.push({ step: "Gate", detail: "Human approved the proposal" });
  return finishExecute(next, proposed);
}

function proposeRefund(next: CaseFile, text: string): CaseFile {
  const orderId = extractOrderId(text);
  if (!orderId) {
    next.step = "needs_detail";
    next.messages.push({
      role: "assistant",
      content:
        "Which order should I refund? This account has ORD-12345 (wool overshirt, $49.99) and ORD-44002 (linen socks, $18.50). ORD-77821 is already refunded.",
    });
    next.audit.push({ step: "Propose", detail: "Blocked: missing order id" });
    return next;
  }

  const known = ORDERS.find((order) => order.id === orderId);
  if (next.ledger.refunded.includes(orderId) || known?.status === "refunded") {
    next.step = "completed";
    next.needsApproval = false;
    next.proposed = null;
    next.messages.push({
      role: "assistant",
      content: `${orderId}${known ? ` (${known.item})` : ""} is already refunded. I will not open another gate for it.`,
    });
    next.audit.push({ step: "Propose", detail: `Blocked: ${orderId} already refunded` });
    return next;
  }

  const amount = extractAmount(text) ?? known?.amount ?? null;
  if (amount == null) {
    next.step = "needs_detail";
    next.messages.push({
      role: "assistant",
      content: `I don't have a balance for ${orderId}. Tell me the refund amount, or use an order on this account.`,
    });
    return next;
  }

  const proposed: ProposedAction = {
    tool: "process_refund",
    args: {
      order_id: orderId,
      amount,
      reason: "Customer requested refund",
      customer_id: next.customerId,
    },
  };
  next.proposed = proposed;
  next.needsApproval = true;
  next.step = "awaiting_approval";
  const item = known ? ` (${known.item})` : "";
  next.messages.push({
    role: "assistant",
    content: `I will not move money yet. Proposed process_refund for ${orderId}${item} at $${amount.toFixed(2)}. Approve to execute, or reject to leave the ledger alone.`,
  });
  next.audit.push({
    step: "Propose",
    detail: `process_refund ${orderId} $${amount.toFixed(2)}`,
  });
  next.audit.push({ step: "Gate", detail: "Waiting on approve or reject" });
  return next;
}

function proposeCancel(next: CaseFile, _text: string): CaseFile {
  const proposed: ProposedAction = {
    tool: "cancel_subscription",
    args: {
      customer_id: next.customerId,
      subscription_id: SUBSCRIPTION.id,
      reason: "Customer requested cancellation",
    },
  };
  next.proposed = proposed;
  next.needsApproval = true;
  next.step = "awaiting_approval";
  next.messages.push({
    role: "assistant",
    content: `Proposed cancel_subscription for ${SUBSCRIPTION.name} (${SUBSCRIPTION.id}, $${SUBSCRIPTION.price}/mo). This does not run until you approve.`,
  });
  next.audit.push({
    step: "Propose",
    detail: `cancel_subscription ${SUBSCRIPTION.id}`,
  });
  next.audit.push({ step: "Gate", detail: "Waiting on approve or reject" });
  return next;
}

function runUpdate(next: CaseFile, text: string): CaseFile {
  const email = extractEmail(text);
  const phone = extractPhone(text);
  const address = extractAddress(text);
  if (!email && !phone && !address) {
    next.step = "needs_detail";
    next.messages.push({
      role: "assistant",
      content:
        "What should I change? Send a new email, a phone number, or a line that starts with “address:”.",
    });
    next.audit.push({ step: "Propose", detail: "Blocked: no field to update" });
    return next;
  }

  const args: Record<string, string | number> = { customer_id: next.customerId };
  if (email) args.email = email;
  if (phone) args.phone = phone;
  if (address) args.address = address;
  return finishExecute(next, { tool: "update_account", args });
}

function runStatus(next: CaseFile, text: string): CaseFile {
  const orderId = extractOrderId(text);
  if (!orderId) {
    next.step = "needs_detail";
    const lines = ORDERS.map(
      (order) => `${order.id} · ${order.item} · ${displayStatus(next, order)}`,
    ).join("\n");
    next.messages.push({
      role: "assistant",
      content: `Which order? On this account:\n${lines}`,
    });
    return next;
  }
  const known = ORDERS.find((order) => order.id === orderId);
  next.step = "completed";
  if (!known) {
    next.messages.push({
      role: "assistant",
      content: `No order ${orderId} belongs to ${next.customerName}.`,
    });
    next.audit.push({ step: "Reply", detail: `Unknown order ${orderId}` });
    return next;
  }
  const status = displayStatus(next, known);
  next.messages.push({
    role: "assistant",
    content: `${known.id} · ${known.item} · $${known.amount.toFixed(2)} · ${status}. No tool was required.`,
  });
  next.audit.push({ step: "Reply", detail: `${known.id} is ${status}` });
  return next;
}

function runEscalate(next: CaseFile): CaseFile {
  next.step = "completed";
  next.messages.push({
    role: "assistant",
    content:
      "Opened a human queue ticket HQ-221 for Mira Sen. No refund, cancel, or account tool was called.",
  });
  next.audit.push({ step: "Reply", detail: "Escalated to HQ-221" });
  return next;
}

function askClarify(next: CaseFile): CaseFile {
  next.step = "completed";
  next.messages.push({
    role: "assistant",
    content:
      "I didn't take an action. Ask for a refund, a cancellation, an order status, or an account change. Example: “Refund order 12345”.",
  });
  next.audit.push({ step: "Reply", detail: "No matching intent" });
  return next;
}

function finishExecute(next: CaseFile, proposed: ProposedAction): CaseFile {
  next.proposed = proposed;
  const result = execute(next, proposed);
  next.toolResult = result.data;
  next.audit.push({ step: "Execute", detail: result.message });
  if (!result.ok) {
    next.error = result.message;
    next.step = "error";
    next.messages.push({
      role: "assistant",
      content: `Stopped before any change. ${result.message}`,
    });
    return next;
  }
  next.step = "completed";
  next.messages.push({ role: "assistant", content: result.message });
  next.audit.push({ step: "Reply", detail: "Turn closed" });
  return next;
}

function execute(
  next: CaseFile,
  proposed: ProposedAction,
): { ok: boolean; message: string; data: Record<string, unknown> } {
  if (proposed.tool === "process_refund") {
    const orderId = String(proposed.args.order_id);
    const amount = Number(proposed.args.amount);
    if (!(amount > 0) || amount > 5000) {
      return {
        ok: false,
        message: `Refunds must be between $0.01 and $5,000. $${amount} is outside policy.`,
        data: {},
      };
    }
    const known = ORDERS.find((order) => order.id === orderId);
    if (!known) {
      return { ok: false, message: `No order ${orderId} on this account.`, data: {} };
    }
    if (next.ledger.refunded.includes(orderId) || known.status === "refunded") {
      return {
        ok: false,
        message: `${orderId} (${known.item}) is already refunded.`,
        data: {},
      };
    }
    if (Math.abs(amount - known.amount) > 0.009) {
      return {
        ok: false,
        message: `$${amount.toFixed(2)} does not match the ${orderId} total of $${known.amount.toFixed(2)}.`,
        data: {},
      };
    }
    next.ledger.refunded.push(orderId);
    const refundId = `ref_${orderId}_1042`;
    return {
      ok: true,
      message: `Refunded $${amount.toFixed(2)} on ${orderId} (${known.item}). Reference ${refundId}.`,
      data: { status: "success", refund_id: refundId, amount, order_id: orderId },
    };
  }

  if (proposed.tool === "cancel_subscription") {
    if (next.ledger.cancelled) {
      return {
        ok: false,
        message: `${SUBSCRIPTION.id} is already cancelled.`,
        data: {},
      };
    }
    next.ledger.cancelled = true;
    return {
      ok: true,
      message: `Cancelled ${SUBSCRIPTION.name} (${SUBSCRIPTION.id}). It will not renew.`,
      data: { status: "success", subscription_id: SUBSCRIPTION.id },
    };
  }

  const fields: string[] = [];
  if (typeof proposed.args.email === "string") {
    next.ledger.email = proposed.args.email;
    fields.push("email");
  }
  if (typeof proposed.args.phone === "string") {
    next.ledger.phone = proposed.args.phone;
    fields.push("phone");
  }
  if (typeof proposed.args.address === "string") {
    next.ledger.address = proposed.args.address;
    fields.push("address");
  }
  if (!fields.length) {
    return { ok: false, message: "No account field was provided.", data: {} };
  }
  return {
    ok: true,
    message: `Updated ${fields.join(", ")} for ${next.customerName}.`,
    data: { status: "success", updated_fields: fields },
  };
}

export function classify(text: string): Intent {
  const t = text.toLowerCase();
  if (/\b(refund|money back|chargeback)\b/.test(t)) return "refund";
  if (/\bcancel/.test(t)) return "cancel";
  if (/\b(status|tracking|where is|shipped|delivered)\b/.test(t)) return "order_status";
  if (/\b(human|manager|escalate|supervisor)\b/.test(t)) return "escalate";
  if (/\b(email|address|phone)\b/.test(t) && /\b(update|change|switch|set)\b/.test(t)) {
    return "update_account";
  }
  if (/\b(update|change)\b/.test(t) && /\baccount\b/.test(t)) return "update_account";
  if (/\border\b/.test(t)) return "order_status";
  return "other";
}

function labelIntent(intent: Intent): string {
  switch (intent) {
    case "refund":
      return "Intent: refund";
    case "cancel":
      return "Intent: cancel subscription";
    case "update_account":
      return "Intent: update account";
    case "order_status":
      return "Intent: order status";
    case "escalate":
      return "Intent: escalate";
    default:
      return "Intent: other — no tool";
  }
}

export function extractOrderId(text: string): string | null {
  const coded = text.match(/\bORD[-\s]?(\d{3,})\b/i);
  if (coded) return `ORD-${coded[1]}`;
  const loose = text.match(/\border\s+#?(\d{3,})\b/i);
  if (loose) return `ORD-${loose[1]}`;
  return null;
}

function extractAmount(text: string): number | null {
  const match = text.match(/\$\s?(\d+(?:\.\d{1,2})?)/);
  if (!match) return null;
  return Number(match[1]);
}

function extractEmail(text: string): string | null {
  const match = text.match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i);
  return match ? match[0] : null;
}

function extractPhone(text: string): string | null {
  const match = text.match(/(?:\+\d{1,3}\s?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}/);
  return match ? match[0] : null;
}

function extractAddress(text: string): string | null {
  const match = text.match(/\baddress\s*:\s*(.+)$/i);
  return match ? match[1].trim() : null;
}

function displayStatus(file: CaseFile, order: CatalogOrder): string {
  if (file.ledger.refunded.includes(order.id) || order.status === "refunded") {
    return "refunded";
  }
  return order.status;
}

export const PROMPTS = [
  "Refund order 12345",
  "Cancel my subscription",
  "Where is order 44002?",
  "Change my email to mira.new@northline.test",
];

export interface CaseSnapshot {
  thread_id: string;
  customer_id: string;
  intent: Intent | null;
  current_step: string;
  needs_approval: boolean;
  proposed_action: ProposedAction | null;
  approved: boolean | null;
  ledger: Ledger;
  audit: AuditEvent[];
}

export interface ChatTurnResult {
  thread_id: string;
  messages: ChatMessage[];
  current_step: string;
  needs_approval: boolean;
  proposed_action: ProposedAction | null;
  tool_result: Record<string, unknown> | null;
  snapshot: CaseSnapshot;
}

export function snapshotOf(file: CaseFile): CaseSnapshot {
  return {
    thread_id: file.threadId,
    customer_id: file.customerId,
    intent: file.intent,
    current_step: file.step,
    needs_approval: file.needsApproval,
    proposed_action: file.proposed,
    approved: file.approved,
    ledger: file.ledger,
    audit: file.audit,
  };
}

export function runChat(input: {
  message?: string;
  thread_id?: string | null;
  approve?: boolean | null;
  snapshot?: CaseSnapshot | null;
}): ChatTurnResult {
  const base = createCase();
  const snap = input.snapshot;
  const file: CaseFile = {
    ...base,
    threadId: input.thread_id || snap?.thread_id || base.threadId,
    customerId: snap?.customer_id || base.customerId,
    intent: snap?.intent ?? null,
    step: snap?.current_step || "ready",
    needsApproval: Boolean(snap?.needs_approval),
    proposed: snap?.proposed_action ?? null,
    approved: snap?.approved ?? null,
    toolResult: null,
    error: null,
    messages: [],
    audit: snap?.audit?.length ? snap.audit : [{ step: "Open", detail: "Case opened" }],
    ledger: snap?.ledger
      ? { ...snap.ledger, refunded: [...snap.ledger.refunded] }
      : { ...base.ledger, refunded: [...base.ledger.refunded] },
  };

  const next = applyTurn(file, input.message || "", input.approve);
  const newest = [...next.messages].reverse().find((message) => message.role === "assistant");

  return {
    thread_id: next.threadId,
    messages: newest ? [newest] : [],
    current_step: next.step,
    needs_approval: Boolean(next.needsApproval && next.step === "awaiting_approval"),
    proposed_action: next.proposed,
    tool_result: next.toolResult,
    snapshot: snapshotOf(next),
  };
}
