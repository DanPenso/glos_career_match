import type { IntakeForm, MatchResponse, TaxonomyResponse } from "./types";

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
    body: JSON.stringify({ ...form, top_n: 3 }),
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
