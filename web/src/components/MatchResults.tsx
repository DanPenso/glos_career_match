"use client";

import { useState } from "react";
import { PersonaFitPanel } from "@/components/PersonaFit";
import type { MatchResponse, Pathway } from "@/lib/types";

/** Orange → green traffic shades from a 0–1 signal (no red). */
function signalStyle(score: number): {
  background: string;
  border: string;
  color: string;
} {
  const s = Math.max(0, Math.min(1, Number.isFinite(score) ? score : 0));
  if (s >= 0.7) {
    return { background: "#c8f0d8", border: "#0d5c54", color: "#06332e" };
  }
  if (s >= 0.55) {
    return { background: "#d4f5c8", border: "#2f7a45", color: "#14401f" };
  }
  if (s >= 0.42) {
    return { background: "#e8f5c4", border: "#6a9a2e", color: "#2f4210" };
  }
  if (s >= 0.3) {
    return { background: "#f7ecc0", border: "#c4921a", color: "#5c4208" };
  }
  if (s >= 0.18) {
    return { background: "#fde4c4", border: "#d4892a", color: "#6b3d0a" };
  }
  return { background: "#fcd9b8", border: "#e07a28", color: "#6b3410" };
}

function hiringSignalScore(
  hiringScore?: number,
  hiringSignal?: string,
): number {
  if (typeof hiringScore === "number" && Number.isFinite(hiringScore)) {
    return hiringScore;
  }
  const sig = String(hiringSignal || "").toLowerCase();
  if (sig === "high") return 0.9;
  if (sig === "medium") return 0.55;
  if (sig === "low") return 0.25;
  return 0.2;
}

function SignalStat({
  label,
  value,
  score,
}: {
  label: string;
  value: string;
  score: number;
}) {
  const tone = signalStyle(score);
  return (
    <div
      className="rounded-2xl px-3 py-3 ring-1"
      style={{
        background: tone.background,
        borderColor: tone.border,
        boxShadow: `inset 0 0 0 1px ${tone.border}33`,
      }}
    >
      <p className="text-xs font-medium" style={{ color: tone.color }}>
        {label}
      </p>
      <p
        className="mt-1 text-xl font-semibold"
        style={{
          color: tone.color,
          fontFamily: "var(--font-display), Georgia, serif",
        }}
      >
        {value}
      </p>
    </div>
  );
}

function PathwayGrid({
  title,
  caption,
  pathways,
}: {
  title: string;
  caption?: string;
  pathways: Pathway[];
}) {
  return (
    <div className="space-y-3">
      <div>
        <h3 className="font-display text-2xl text-[var(--ink)]">{title}</h3>
        {caption ? (
          <p className="mt-1 text-sm text-[var(--ink-muted)]">{caption}</p>
        ) : null}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {pathways.map((p) => {
          const short = String(p.summary || "")
            .replace(/\s+/g, " ")
            .trim();
          const clipped =
            short.length > 140 ? `${short.slice(0, 137)}…` : short;
          return (
            <div
              key={p.id || p.title}
              className="rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-4 shadow-sm"
            >
              {p.chip ? (
                <p className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--trust)]">
                  <span className="rounded-full bg-[var(--accent)] px-2 py-0.5 text-[var(--accent-ink)]">
                    {p.chip}
                  </span>
                </p>
              ) : null}
              <h4 className="border-b border-[var(--line)] pb-2 font-semibold text-[var(--ink)]">
                {p.title}
              </h4>
              {p.reason ? (
                <p className="mt-2 text-xs font-medium text-[var(--trust)]">
                  {p.reason}
                </p>
              ) : null}
              <p className="mt-2 text-sm text-[var(--ink-muted)]">{clipped}</p>
              {p.steps?.[0] ? (
                <p className="mt-1.5 text-sm text-[var(--ink-muted)]">
                  Next: {p.steps[0]}
                </p>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function stripDecor(line: string): string {
  return line
    .replace(/^[-*]\s+/, "")
    .replace(/^\d+\.\s+/, "")
    .replace(/\*\*/g, "")
    .trim();
}

function SimpleMarkdown({ text }: { text: string }) {
  const blocks = text.split(/\n\n+/).filter((b) => b.trim());
  return (
    <div className="space-y-3 text-sm leading-relaxed text-[var(--ink)]">
      {blocks.map((block, i) => {
        const lines = block.split("\n").map((l) => l.trimEnd());
        if (lines[0]?.startsWith("# ")) {
          return (
            <h3
              key={i}
              className="font-display text-2xl font-bold text-[var(--ink)]"
            >
              {stripDecor(lines[0].replace(/^#\s+/, ""))}
            </h3>
          );
        }
        if (lines[0]?.startsWith("## ")) {
          const body = lines
            .slice(1)
            .map(stripDecor)
            .filter(Boolean)
            .slice(0, 5);
          return (
            <div
              key={i}
              className="rounded-2xl border border-[var(--line)] bg-[var(--paper)] px-4 py-3 ring-1 ring-[var(--line)]/60"
            >
              <h4 className="border-b border-[var(--line)] pb-2 font-display text-base font-semibold text-[var(--trust)]">
                {stripDecor(lines[0].replace(/^##\s+/, ""))}
              </h4>
              <div className="mt-2 space-y-1.5">
                {body.map((line, j) => (
                  <p key={j} className="text-[var(--ink-muted)]">
                    {line}
                  </p>
                ))}
              </div>
            </div>
          );
        }
        return (
          <p key={i} className="text-[var(--ink-muted)]">
            {lines.map(stripDecor).filter(Boolean).join(" ")}
          </p>
        );
      })}
    </div>
  );
}

export function MatchResults({
  data,
  onReset,
}: {
  data: MatchResponse;
  onReset: () => void;
}) {
  const [active, setActive] = useState(0);
  const match = data.matches[active];

  return (
    <section className="space-y-8 animate-in">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-display text-3xl text-[var(--ink)]">
            Your top matches
          </h2>
          <p className="mt-1 text-sm text-[var(--ink-muted)]">
            Options to explore — not a final decision. Check live vacancies before you apply.
          </p>
        </div>
        <button type="button" className="btn-ghost" onClick={onReset}>
          Start again
        </button>
      </div>

      <PersonaFitPanel
        persona={data.persona}
        blurb={data.persona_blurb}
        disclaimer={data.persona_disclaimer}
        runnerUp={data.runner_up}
        fit={data.persona_fit}
        map2d={data.persona_map_2d}
        learningEventId={data.learning_event_id}
      />

      <details className="rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-4">
        <summary className="cursor-pointer font-display text-lg text-[var(--ink)]">
          How to use this advice
        </summary>
        <ul className="mt-3 space-y-2 text-sm text-[var(--ink-muted)]">
          <li>Treat these as options, not a verdict.</li>
          <li>Follow a training route — not only a brand name.</li>
          <li>
            Verify openings on{" "}
            <a
              className="underline decoration-[var(--accent)]"
              href="https://www.findapprenticeship.service.gov.uk/"
              target="_blank"
              rel="noreferrer"
            >
              Find an apprenticeship
            </a>
            .
          </li>
          <li>Pick one small step this month, then talk it through with an adviser.</li>
        </ul>
      </details>

      {(data.training_routes?.length || data.pathways?.length) ? (
        <PathwayGrid
          title="Training routes for you"
          caption="Ranked using your interests and your closest career groups in the model."
          pathways={(data.training_routes?.length
            ? data.training_routes
            : data.pathways
          ).slice(0, 4)}
        />
      ) : null}

      <div className="flex gap-2 overflow-x-auto pb-1">
        {data.matches.map((m, i) => (
          <button
            key={m.company_id}
            type="button"
            onClick={() => setActive(i)}
            className={`shrink-0 rounded-full px-4 py-2 text-sm transition ${
              i === active
                ? "bg-[var(--ink)] text-[var(--paper)]"
                : "bg-[var(--surface)] text-[var(--ink)] ring-1 ring-[var(--line)]"
            }`}
          >
            #{i + 1} {m.name}
          </button>
        ))}
      </div>

      {match ? (
        <article className="space-y-5 rounded-3xl border border-[var(--line)] bg-[var(--surface)] p-5 sm:p-7">
          <header className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--trust)]">
              <span className="mr-2 inline-block rounded-full bg-[var(--accent)] px-2 py-0.5 text-[var(--accent-ink)]">
                Match
              </span>
              {match.overall_label}
            </p>
            <h3 className="font-display text-3xl text-[var(--ink)]">{match.name}</h3>
            <p className="text-sm text-[var(--ink-muted)]">
              {match.town}
              {match.website ? (
                <>
                  {" · "}
                  <a
                    href={match.website}
                    target="_blank"
                    rel="noreferrer"
                    className="underline decoration-[var(--accent)]"
                  >
                    Website
                  </a>
                </>
              ) : null}
            </p>
            <p className="text-[var(--ink)]">{match.summary}</p>
          </header>

          <div className="grid gap-3 sm:grid-cols-3">
            <SignalStat
              label="How well does the sector fit my interests and experience?"
              value={match.sector_fit_label || "Worth exploring"}
              score={match.sector_score ?? 0}
            />
            <SignalStat
              label="How well does their route fit yours?"
              value={match.entry_fit_label || "Worth exploring"}
              score={match.entry_score ?? 0}
            />
            <SignalStat
              label="Are they hiring for entry roles?"
              value={match.hiring_label || "Check current openings"}
              score={hiringSignalScore(
                match.hiring_score,
                match.hiring_signal,
              )}
            />
          </div>
          <p className="text-xs text-[var(--ink-muted)]">
            Green = stronger signal, orange = softer — compares your top matches,
            not your chances of getting a job.
          </p>

          {data.briefings_enabled && match.briefing_markdown ? (
            <div className="mt-2 space-y-2">
              <p className="text-xs text-[var(--ink-muted)]">
                Match report written with OpenAI
              </p>
              <SimpleMarkdown text={match.briefing_markdown} />
            </div>
          ) : data.briefings_enabled ? (
            <p className="text-sm text-[var(--ink-muted)]">
              AI match report unavailable right now. You still have your top
              matches and training routes above.
            </p>
          ) : null}
        </article>
      ) : null}
    </section>
  );
}
