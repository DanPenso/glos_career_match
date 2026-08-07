import type {
  ActionPlan,
  IntakeForm,
  MatchCompany,
  MatchMode,
  MatchResponse,
  PlanBreakdown,
  PlanStep,
  TaxonomyResponse,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";

export async function fetchTaxonomy(): Promise<TaxonomyResponse> {
  const res = await fetch(`${API_BASE}/taxonomy`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Could not load options (${res.status}). Is the API running?`);
  }
  return res.json();
}

export async function fetchMatch(form: IntakeForm): Promise<MatchResponse> {
  const res = await fetch(`${API_BASE}/match`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...form, mode: form.mode || "work", top_n: 3 }),
  });
  if (!res.ok) {
    let detail = `Match failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function sendPersonaFeedback(
  eventId: string,
  helpful: boolean,
): Promise<void> {
  const res = await fetch(`${API_BASE}/feedback/persona`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ event_id: eventId, helpful }),
  });
  if (!res.ok) {
    throw new Error(`Feedback failed (${res.status})`);
  }
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (data?.detail) detail = String(data.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function fetchPlanGenerate(input: {
  mode: MatchMode;
  leaver: Record<string, unknown>;
  match: MatchCompany;
  use_gemini_plan: boolean;
}): Promise<ActionPlan> {
  return postJson("/plan/generate", input);
}

export async function fetchPlanBreakdown(input: {
  mode: MatchMode;
  leaver: Record<string, unknown>;
  match: MatchCompany;
  step: PlanStep;
  sibling_steps?: PlanStep[];
  step_families?: Record<string, string>;
  use_gemini_plan: boolean;
}): Promise<PlanBreakdown> {
  return postJson("/plan/breakdown", input);
}

export async function fetchPlanChat(input: {
  mode: MatchMode;
  leaver: Record<string, unknown>;
  match: MatchCompany;
  step: PlanStep;
  breakdown?: PlanBreakdown;
  history: { role: "user" | "assistant"; content: string }[];
  message: string;
  use_gemini_plan: boolean;
}): Promise<{ reply_markdown: string; source?: string }> {
  return postJson("/plan/chat", input);
}
