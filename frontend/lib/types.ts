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

export const PROMPTS = [
  "Refund order 12345",
  "Cancel my subscription",
  "Where is order 44002?",
  "Update my email address to mira@example.com",
];
