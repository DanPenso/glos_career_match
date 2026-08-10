"use client";

import { Fragment, useState, type ReactNode } from "react";
import {
  fetchPlanBreakdown,
  fetchPlanChat,
  fetchPlanGenerate,
} from "@/lib/api";
import type {
  MatchCompany,
  MatchMode,
  PlanBreakdown,
  PlanStep,
} from "@/lib/types";

const SOURCE_LINK_RULES: { pattern: RegExp; href: string }[] = [
  { pattern: /\bUCAS\b/i, href: "https://www.ucas.com/" },
  {
    pattern: /National Careers Service/i,
    href: "https://nationalcareers.service.gov.uk/",
  },
  { pattern: /\bProspects\b/i, href: "https://www.prospects.ac.uk/" },
  {
    pattern: /Find an apprenticeship/i,
    href: "https://www.findapprenticeship.service.gov.uk/",
  },
  {
    pattern: /\bGatsby\b/i,
    href: "https://www.gatsby.org.uk/education/focus-areas/good-career-guidance",
  },
  {
    pattern: /Armed Forces careers/i,
    href: "https://www.armedforcescareers.mod.uk/",
  },
];

function cleanLinkLabel(url: string): string {
  try {
    const host = new URL(url).hostname.replace(/^www\./, "");
    return host || "Open page";
  } catch {
    return "Open page";
  }
}

function ExternalLink({
  href,
  children,
}: {
  href: string;
  children: ReactNode;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="font-medium text-[var(--trust)] underline decoration-[var(--accent)] underline-offset-2"
    >
      {children}
    </a>
  );
}

/** Render inline markdown links, bare URLs (as hostname), and light bold. */
function InlineRichText({ text }: { text: string }) {
  const parts: ReactNode[] = [];
  // [label](url) or bare http(s) URL; trailing sentence punctuation stays outside the link
  const token =
    /(\[([^\]]+)\]\((https?:\/\/[^)\s]+)\))|(https?:\/\/[^\s<>"'\)\]]+)/gi;
  let last = 0;
  let match: RegExpExecArray | null;
  let key = 0;
  while ((match = token.exec(text)) !== null) {
    if (match.index > last) {
      parts.push(
        <Fragment key={`t-${key++}`}>
          {text.slice(last, match.index)}
        </Fragment>,
      );
    }
    if (match[1]) {
      parts.push(
        <ExternalLink key={`a-${key++}`} href={match[3]}>
          {match[2]}
        </ExternalLink>,
      );
    } else {
      let url = match[4];
      let trailing = "";
      while (/[.,;:!?)]$/.test(url)) {
        trailing = url.slice(-1) + trailing;
        url = url.slice(0, -1);
      }
      parts.push(
        <ExternalLink key={`a-${key++}`} href={url}>
          {cleanLinkLabel(url)}
        </ExternalLink>,
      );
      if (trailing) {
        parts.push(<Fragment key={`p-${key++}`}>{trailing}</Fragment>);
      }
    }
    last = match.index + match[0].length;
  }
  if (last < text.length) {
    parts.push(<Fragment key={`t-${key++}`}>{text.slice(last)}</Fragment>);
  }
  return <>{parts.length ? parts : text}</>;
}

function SimpleMarkdown({ text }: { text: string }) {
  const blocks = text.split(/\n\n+/).filter(Boolean);
  return (
    <div className="space-y-2 text-sm text-[var(--ink)]">
      {blocks.map((block, i) => {
        const line = block.trim();
        if (line.startsWith("### ")) {
          return (
            <h5 key={i} className="font-display text-lg text-[var(--ink)]">
              <InlineRichText text={line.replace(/^###\s+/, "")} />
            </h5>
          );
        }
        if (line.startsWith("## ")) {
          return (
            <h4 key={i} className="font-display text-xl text-[var(--ink)]">
              <InlineRichText text={line.replace(/^##\s+/, "")} />
            </h4>
          );
        }
        if (/^\d+\.\s/.test(line) || line.startsWith("- ")) {
          const items = line.split("\n").filter(Boolean);
          return (
            <ul key={i} className="list-disc space-y-1 pl-5">
              {items.map((item, j) => (
                <li key={j}>
                  <InlineRichText
                    text={item.replace(/^\d+\.\s*/, "").replace(/^-\s*/, "")}
                  />
                </li>
              ))}
            </ul>
          );
        }
        return (
          <p key={i} className="leading-relaxed">
            <InlineRichText text={line} />
          </p>
        );
      })}
    </div>
  );
}

function SourcesUsed({
  sources,
  matchWebsite,
}: {
  sources: string[];
  matchWebsite?: string;
}) {
  return (
    <p className="text-xs text-[var(--ink-muted)]">
      Based on:{" "}
      {sources.map((src, i) => {
        const nodes: ReactNode[] = [];
        let cursor = 0;
        const hits: { start: number; end: number; label: string; href: string }[] =
          [];

        for (const rule of SOURCE_LINK_RULES) {
          const m = src.match(rule.pattern);
          if (m?.index != null) {
            hits.push({
              start: m.index,
              end: m.index + m[0].length,
              label: m[0],
              href: rule.href,
            });
          }
        }
        if (matchWebsite) {
          const m = src.match(/provider course pages|Organisation website/i);
          if (m?.index != null) {
            hits.push({
              start: m.index,
              end: m.index + m[0].length,
              label: m[0],
              href: matchWebsite,
            });
          }
        }
        hits.sort((a, b) => a.start - b.start);

        let key = 0;
        for (const hit of hits) {
          if (hit.start < cursor) continue;
          if (hit.start > cursor) nodes.push(src.slice(cursor, hit.start));
          nodes.push(
            <ExternalLink key={`${i}-${key++}`} href={hit.href}>
              {hit.label}
            </ExternalLink>,
          );
          cursor = hit.end;
        }
        if (cursor < src.length) nodes.push(src.slice(cursor));

        return (
          <Fragment key={i}>
            {i > 0 ? "; " : null}
            {nodes.length ? nodes : src}
          </Fragment>
        );
      })}
    </p>
  );
}

type Props = {
  mode: MatchMode;
  match: MatchCompany;
  leaver: Record<string, unknown>;
  enabled: boolean;
};

export function FiveStepPlan({ mode, match, leaver, enabled }: Props) {
  const [planId, setPlanId] = useState<string | null>(null);
  const [steps, setSteps] = useState<PlanStep[]>([]);
  const [stepFamilies, setStepFamilies] = useState<Record<string, string>>({});
  const [disclaimer, setDisclaimer] = useState("");
  const [source, setSource] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [openStepId, setOpenStepId] = useState<string | null>(null);
  const [breakdowns, setBreakdowns] = useState<Record<string, PlanBreakdown>>(
    {},
  );
  const [breakBusy, setBreakBusy] = useState<string | null>(null);
  const [chats, setChats] = useState<
    Record<string, { role: "user" | "assistant"; content: string }[]>
  >({});
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [chatBusy, setChatBusy] = useState<string | null>(null);

  async function createPlan() {
    if (!enabled) {
      setError(
        "Turn on “AI 5-step action plans (Gemini)” under “Must be checked for AI responses!”, then run a new match.",
      );
      return;
    }
    setBusy(true);
    setError("");
    try {
      const data = await fetchPlanGenerate({
        mode,
        leaver,
        match,
        use_gemini_plan: true,
      });
      setPlanId(data.plan_id);
      setSteps(data.steps || []);
      setStepFamilies(data.step_families || {});
      setDisclaimer(data.disclaimer || "");
      setSource(data.source || "");
      setOpenStepId(null);
      setBreakdowns({});
      setChats({});
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create plan");
    } finally {
      setBusy(false);
    }
  }

  async function breakDown(step: PlanStep) {
    setOpenStepId(step.id);
    if (breakdowns[step.id]) return;
    setBreakBusy(step.id);
    setError("");
    try {
      const data = await fetchPlanBreakdown({
        mode,
        leaver,
        match,
        step,
        sibling_steps: steps,
        step_families: stepFamilies,
        use_gemini_plan: true,
      });
      setBreakdowns((prev) => ({ ...prev, [step.id]: data }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not break down step");
    } finally {
      setBreakBusy(null);
    }
  }

  async function sendChat(step: PlanStep) {
    const message = (drafts[step.id] || "").trim();
    if (!message) return;
    const history = chats[step.id] || [];
    if (history.filter((t) => t.role === "user").length >= 5) {
      setError("You can ask up to 5 questions on each step in this demo.");
      return;
    }
    setChatBusy(step.id);
    setError("");
    const nextHistory = [...history, { role: "user" as const, content: message }];
    setChats((prev) => ({ ...prev, [step.id]: nextHistory }));
    setDrafts((prev) => ({ ...prev, [step.id]: "" }));
    try {
      const data = await fetchPlanChat({
        mode,
        leaver,
        match,
        step,
        breakdown: breakdowns[step.id],
        history: nextHistory,
        message,
        use_gemini_plan: true,
      });
      setChats((prev) => ({
        ...prev,
        [step.id]: [
          ...(prev[step.id] || nextHistory),
          { role: "assistant", content: data.reply_markdown },
        ],
      }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Chat failed");
    } finally {
      setChatBusy(null);
    }
  }

  return (
    <div className="space-y-4 border-t border-[var(--line)] pt-5">
      {!planId ? (
        <div className="space-y-2">
          <button
            type="button"
            className="btn-primary w-full sm:w-auto"
            disabled={busy}
            onClick={createPlan}
          >
            {busy ? "Building your plan…" : "Create my 5-step plan"}
          </button>
          <p className="text-xs text-[var(--ink-muted)]">
            Uses Google Gemini when enabled. Guidance only — check official
            websites before you act.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          <div>
            <h4 className="font-display text-2xl text-[var(--ink)]">
              Your 5-step plan
              {match.name ? ` for ${match.name}` : ""}
            </h4>
            <p className="mt-1 text-xs text-[var(--ink-muted)]">
              {disclaimer}
              {source ? ` · Source: ${source}` : ""}
            </p>
          </div>

          <div className="space-y-3">
            {steps.map((step, idx) => {
              const open = openStepId === step.id;
              const bd = breakdowns[step.id];
              const thread = chats[step.id] || [];
              return (
                <div
                  key={step.id}
                  className="rounded-2xl border border-[var(--line)] bg-[var(--paper)] p-4 shadow-sm"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--trust)]">
                        Step {idx + 1}
                        {step.timeframe ? ` · ${step.timeframe}` : ""}
                      </p>
                      <h5 className="mt-1 font-display text-xl text-[var(--ink)]">
                        {step.title}
                      </h5>
                      <p className="mt-1 text-sm text-[var(--ink-muted)]">
                        <InlineRichText text={step.summary} />
                      </p>
                    </div>
                    <button
                      type="button"
                      className="rounded-full border border-[var(--trust)] bg-[var(--surface)] px-3 py-1.5 text-sm font-medium text-[var(--ink)] hover:bg-[var(--accent)] hover:text-[var(--accent-ink)]"
                      disabled={breakBusy === step.id}
                      onClick={() => {
                        if (open) {
                          setOpenStepId(null);
                          return;
                        }
                        void breakDown(step);
                      }}
                    >
                      {breakBusy === step.id
                        ? "Breaking it down…"
                        : open
                          ? "Hide breakdown"
                          : "Break it down for me"}
                    </button>
                  </div>

                  {open ? (
                    <div className="mt-4 space-y-3 border-t border-[var(--line)] pt-4">
                      {bd ? (
                        <>
                          {bd.profile_hooks?.length || bd.why_this_step ? (
                            <div className="rounded-xl bg-[var(--surface)] px-3 py-2 text-sm text-[var(--ink)]">
                              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--trust)]">
                                For you
                              </p>
                              {bd.why_this_step ? (
                                <p className="mt-1 leading-relaxed">
                                  {bd.why_this_step}
                                </p>
                              ) : null}
                              {bd.profile_hooks?.length ? (
                                <p className="mt-1 text-xs text-[var(--ink-muted)]">
                                  Using: {bd.profile_hooks.join(" · ")}
                                </p>
                              ) : null}
                            </div>
                          ) : null}
                          <SimpleMarkdown text={bd.detail_markdown} />
                          {bd.sources_used?.length ? (
                            <SourcesUsed
                              sources={bd.sources_used}
                              matchWebsite={match.website}
                            />
                          ) : null}
                        </>
                      ) : (
                        <p className="text-sm text-[var(--ink-muted)]">
                          Loading a clearer breakdown…
                        </p>
                      )}

                      <div className="space-y-2 rounded-xl bg-[var(--surface)] p-3">
                        <p className="text-xs font-medium text-[var(--ink-muted)]">
                          Ask about this step
                        </p>
                        <div className="max-h-40 space-y-2 overflow-y-auto">
                          {thread.map((t, i) => (
                            <div
                              key={`${step.id}-${i}`}
                              className={`rounded-lg px-3 py-2 text-sm ${
                                t.role === "user"
                                  ? "bg-[var(--accent)]/20 text-[var(--ink)]"
                                  : "bg-[var(--paper)] text-[var(--ink)] ring-1 ring-[var(--line)]"
                              }`}
                            >
                              <SimpleMarkdown text={t.content} />
                            </div>
                          ))}
                        </div>
                        <div className="flex flex-col gap-2 sm:flex-row">
                          <input
                            className="field flex-1"
                            placeholder="e.g. What should I say in the enquiry?"
                            value={drafts[step.id] || ""}
                            onChange={(e) =>
                              setDrafts((prev) => ({
                                ...prev,
                                [step.id]: e.target.value,
                              }))
                            }
                            onKeyDown={(e) => {
                              if (e.key === "Enter") {
                                e.preventDefault();
                                void sendChat(step);
                              }
                            }}
                            disabled={chatBusy === step.id}
                          />
                          <button
                            type="button"
                            className="btn-primary"
                            disabled={chatBusy === step.id}
                            onClick={() => void sendChat(step)}
                          >
                            {chatBusy === step.id ? "Sending…" : "Ask"}
                          </button>
                        </div>
                      </div>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {error ? <p className="text-sm text-red-700">{error}</p> : null}
    </div>
  );
}
