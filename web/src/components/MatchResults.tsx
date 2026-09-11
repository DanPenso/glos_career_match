"use client";

import { useState, type ReactNode } from "react";
import { FiveStepPlan } from "@/components/FiveStepPlan";
import { PersonaFitPanel } from "@/components/PersonaFit";
import { ReadAloudButton } from "@/components/ReadAloudButton";
import {
  MilitaryAgeNotice,
  SafeguardingHelp,
} from "@/components/SafeguardingHelp";
import type {
  MatchCompany,
  MatchMode,
  MatchResponse,
  Pathway,
} from "@/lib/types";

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
          fontFamily: "var(--font-display), var(--font-body), system-ui, sans-serif",
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
  title?: string;
  caption?: string;
  pathways: Pathway[];
}) {
  return (
    <div className="space-y-3">
      {title ? (
        <div>
          <h3 className="font-display text-2xl text-[var(--ink)]">{title}</h3>
          {caption ? (
            <p className="mt-1 text-sm text-[var(--ink-muted)]">{caption}</p>
          ) : null}
        </div>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
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

function modeCopy(mode: MatchMode | undefined) {
  if (mode === "education") {
    return {
      title: "Your top course matches",
      caption:
        "FE/HE options across Gloucestershire and Bristol from National Careers Service open data — check the provider for current intake.",
      thirdLabel: "What level / type is this?",
      thirdHint:
        "Shows course type where known (e.g. NVQ, Skills Bootcamp, T Level, BTEC) plus level from the open course directory.",
      advice: [
        "Treat these as options, not a verdict.",
        "Confirm entry requirements and start dates with the provider.",
        "Use Find a course / the provider website for live availability.",
        "Pick one small next step this month, then talk it through with an adviser.",
      ],
    };
  }
  if (mode === "military") {
    return {
      title: "Military pathways to explore",
      caption:
        "Guidance only — not official recruitment advice. Always verify roles and eligibility on official Armed Forces careers sites.",
      thirdLabel: "Service",
      thirdHint: "Which service this pathway sits in.",
      advice: [
        "These are exploration pathways, not offers of employment.",
        "Check current roles on the official Army, Royal Navy or RAF careers sites.",
        "For funded learning while serving, confirm ELC eligibility on ELCAS with Education Staff.",
        "Speak to a careers adviser or recruiter before making decisions.",
      ],
    };
  }
  return {
    title: "Your top employer matches",
    caption:
      "Options to explore — not a final decision. Check live vacancies before you apply.",
    thirdLabel: "Live roles on this card?",
    thirdHint:
      "This demo is not a jobs board. Check the employer careers page for current openings.",
    advice: [
      "Treat these as options, not a verdict.",
      "Follow a training route — not only a brand name.",
      "Verify openings on the employer website.",
      "Pick one small step this month, then talk it through with an adviser.",
    ],
  };
}

type ResultsTab = "matches" | "cluster" | "training" | "online";

function MatchCard({
  match,
  mode,
  copy,
  children,
}: {
  match: MatchCompany;
  mode: MatchMode;
  copy: ReturnType<typeof modeCopy>;
  children?: ReactNode;
}) {
  const hasOpenApprenticeship = Boolean(match.open_now && match.open_url);
  const hasOpenJob = Boolean(match.jobs_open_now && match.jobs_open_url);
  return (
    <article className="relative space-y-5 rounded-3xl border border-[var(--line)] bg-[var(--surface)] p-5 sm:p-7">
      {hasOpenApprenticeship || hasOpenJob ? (
        <div className="absolute right-3 top-3 z-10 flex max-w-[min(100%-1.5rem,15rem)] flex-col items-end gap-1">
          {hasOpenApprenticeship ? (
            <a
              href={match.open_url}
              target="_blank"
              rel="noreferrer"
              title={
                match.open_source === "ncs_live_directory"
                  ? "Listed as open in the National Careers Service course directory"
                  : "Listed as open on Find an apprenticeship"
              }
              className="rounded-full bg-[var(--open)] px-3 py-1 text-center text-xs font-bold leading-tight text-[var(--open-ink)] shadow-sm hover:brightness-95"
            >
              {match.open_label || "Open opportunities"}
              {(match.open_count || 1) > 1
                ? ` +${(match.open_count || 1) - 1}`
                : ""}
            </a>
          ) : null}
          {hasOpenJob ? (
            <a
              href={match.jobs_open_url}
              target="_blank"
              rel="noreferrer"
              title="Listed as open on Reed"
              className="rounded-full bg-[var(--jobs)] px-3 py-1 text-center text-xs font-bold leading-tight text-[var(--jobs-ink)] shadow-sm hover:brightness-95"
            >
              {match.jobs_open_label || "Open jobs"}
              {(match.jobs_open_count || 1) > 1
                ? ` +${(match.jobs_open_count || 1) - 1}`
                : ""}
            </a>
          ) : null}
        </div>
      ) : null}
      <header
        className={`space-y-2 ${
          hasOpenApprenticeship || hasOpenJob
            ? hasOpenApprenticeship && hasOpenJob
              ? "pr-2 pt-16 sm:pr-44 sm:pt-0"
              : "pr-2 pt-8 sm:pr-44 sm:pt-0"
            : ""
        }`}
      >
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--trust)]">
          <span className="mr-2 inline-block rounded-full bg-[var(--accent)] px-2 py-0.5 text-[var(--accent-ink)]">
            Match
          </span>
          {match.overall_label}
        </p>
        <h3 className="font-display text-3xl text-[var(--ink)]">
          {match.name}
        </h3>
        <p className="text-sm text-[var(--ink-muted)]">
          {mode === "education" && match.provider
            ? `${match.provider} · ${match.town}`
            : match.town}
          {mode === "education" && match.course_type_label ? (
            <>
              {" · "}
              <span className="font-medium text-[var(--trust)]">
                {match.course_type_label}
              </span>
            </>
          ) : null}
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
        {match.open_now &&
        match.open_titles &&
        match.open_titles.length > 1 ? (
          <p className="text-xs text-[var(--ink-muted)]">
            Also listed: {match.open_titles.slice(1).join(" · ")}
          </p>
        ) : null}
        {match.jobs_open_now &&
        match.jobs_open_titles &&
        match.jobs_open_titles.length ? (
          <p className="text-xs text-[var(--ink-muted)]">
            Jobs on Reed: {match.jobs_open_titles.join(" · ")}
          </p>
        ) : null}
        {match.summary ? (
          <p className="text-sm text-[var(--ink)]">{match.summary}</p>
        ) : null}
      </header>

      <div className="grid gap-3 sm:grid-cols-3">
        <SignalStat
          label="How well does the sector fit my interests and experience?"
          value={match.sector_fit_label || "Worth exploring"}
          score={match.sector_score ?? 0}
        />
        <SignalStat
          label={
            mode === "education"
              ? "How well does this course route fit yours?"
              : mode === "military"
                ? "How well does this entry route fit yours?"
                : "How well does their route fit yours?"
          }
          value={match.entry_fit_label || "Worth exploring"}
          score={match.entry_score ?? 0}
        />
        <SignalStat
          label={copy.thirdLabel}
          value={match.hiring_label || "Check details"}
          score={
            mode === "work"
              ? 0.35
              : Math.min(1, (match.sector_score ?? 0) * 0.9 + 0.15)
          }
        />
      </div>
      <p className="text-xs text-[var(--ink-muted)]">{copy.thirdHint}</p>
      {children}
    </article>
  );
}

function SectionPills({
  tab,
  onChange,
}: {
  tab: ResultsTab;
  onChange: (next: ResultsTab) => void;
}) {
  const items: { id: ResultsTab; label: string }[] = [
    { id: "matches", label: "Top 3 Matches" },
    { id: "cluster", label: "Clustered Group" },
    { id: "training", label: "Training Routes" },
    { id: "online", label: "Online Courses" },
  ];
  return (
    <div className="flex gap-2 overflow-x-auto pb-1">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onChange(item.id)}
          className={`shrink-0 rounded-full px-4 py-2 text-sm transition ${
            tab === item.id
              ? "bg-[var(--ink)] text-[var(--paper)]"
              : "bg-[var(--surface)] text-[var(--ink)] ring-1 ring-[var(--line)]"
          }`}
        >
          {item.label}
        </button>
      ))}
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
  const [tab, setTab] = useState<ResultsTab>("matches");
  const match = data.matches[active];
  const mode = data.mode || "work";
  const copy = modeCopy(mode);
  const micros = data.microcredentials || [];
  const online = data.online_courses || [];
  const training = (
    data.training_routes?.length ? data.training_routes : data.pathways || []
  ).slice(0, 4);

  const heading =
    tab === "cluster"
      ? "Your career group"
      : tab === "training"
        ? "Training routes for you"
        : tab === "online"
          ? "Online courses to build skills"
          : copy.title;
  const caption =
    tab === "cluster"
      ? "How your answers sit next to other profiles in the model — not a job verdict."
      : tab === "training"
        ? "Ranked using your interests and your closest career groups in the model."
        : tab === "online"
          ? data.online_courses_disclaimer ||
            "Curated suggestions with links to Coursera or Udemy search results. Check prices and availability on the platform."
          : copy.caption;

  return (
    <section className="space-y-6 animate-in">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-display text-3xl text-[var(--ink)]">{heading}</h2>
          <p className="mt-1 text-sm text-[var(--ink-muted)]">{caption}</p>
          {tab === "matches" && data.data_note ? (
            <p className="mt-2 text-xs text-[var(--ink-muted)]">
              {data.data_note}
            </p>
          ) : null}
        </div>
        <button type="button" className="btn-ghost" onClick={onReset}>
          Start again
        </button>
      </div>

      <SectionPills tab={tab} onChange={setTab} />

      {data.safety_referral_suggested ? <SafeguardingHelp /> : null}
      {data.military_age_notice ? <MilitaryAgeNotice /> : null}

      {tab === "cluster" ? (
        <PersonaFitPanel
          persona={data.persona}
          blurb={data.persona_blurb}
          disclaimer={data.persona_disclaimer}
          runnerUp={data.runner_up}
          fit={data.persona_fit}
          map2d={data.persona_map_2d}
          learningEventId={data.learning_event_id}
        />
      ) : null}

      {tab === "training" ? (
        training.length || (mode === "military" && micros.length) ? (
          <div className="space-y-8">
            {training.length ? (
              <PathwayGrid pathways={training} />
            ) : null}
            {mode === "military" && micros.length ? (
              <div className="space-y-3">
                <div>
                  <h3 className="font-display text-2xl text-[var(--ink)]">
                    Local micro-credentials to explore
                  </h3>
                  <p className="mt-1 text-sm text-[var(--ink-muted)]">
                    Short / Level 3+ courses near Gloucestershire and Bristol from
                    National Careers Service open data. This demo does{" "}
                    <strong>not</strong> confirm Enhanced Learning Credit (ELC)
                    approval — always check{" "}
                    <a
                      className="underline decoration-[var(--accent)]"
                      href="https://www.enhancedlearningcredits.com/"
                      target="_blank"
                      rel="noreferrer"
                    >
                      ELCAS
                    </a>{" "}
                    and your Education Staff.
                  </p>
                </div>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {micros.map((c) => (
                    <div
                      key={c.cred_id}
                      className="rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-4 shadow-sm"
                    >
                      <p className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--trust)]">
                        <span className="rounded-full bg-[var(--accent)] px-2 py-0.5 text-[var(--accent-ink)]">
                          Check ELCAS
                        </span>
                      </p>
                      <h4 className="border-b border-[var(--line)] pb-2 font-semibold text-[var(--ink)]">
                        {c.title}
                      </h4>
                      <p className="mt-2 text-xs text-[var(--ink-muted)]">
                        {c.provider}
                        {c.town ? ` · ${c.town}` : ""}
                        {c.level ? ` · ${c.level}` : ""}
                      </p>
                      <p className="mt-2 text-sm text-[var(--ink-muted)]">
                        {(c.summary || "").slice(0, 160)}
                        {(c.summary || "").length > 160 ? "…" : ""}
                      </p>
                      {c.website ? (
                        <a
                          href={c.website}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-2 inline-block text-sm underline decoration-[var(--accent)]"
                        >
                          Course / provider link
                        </a>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        ) : (
          <p className="text-sm text-[var(--ink-muted)]">
            No training routes for this profile yet.
          </p>
        )
      ) : null}

      {tab === "online" ? (
        online.length ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {online.map((c, i) => (
              <div
                key={c.course_id || c.title}
                className="rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-4 shadow-sm"
              >
                <p className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--trust)]">
                  <span className="rounded-full bg-[var(--accent)] px-2 py-0.5 text-[var(--accent-ink)]">
                    #{i + 1} {c.provider || "Online"}
                  </span>
                </p>
                <h4 className="border-b border-[var(--line)] pb-2 font-semibold text-[var(--ink)]">
                  {c.title}
                </h4>
                <p className="mt-2 text-sm text-[var(--ink-muted)]">
                  {c.description}
                </p>
                {c.url ? (
                  <a
                    href={c.url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-3 inline-block text-sm font-medium underline decoration-[var(--accent)]"
                  >
                    View on {c.provider || "platform"}
                  </a>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-[var(--ink-muted)]">
            No online course suggestions for this profile yet.
          </p>
        )
      ) : null}

      {tab === "matches" ? (
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
              {m.open_now ? (
                <span
                  className="ml-2 inline-block h-2 w-2 rounded-full bg-[var(--open)] align-middle"
                  title="Open opportunities"
                  aria-label="Open opportunities"
                />
              ) : null}
              {m.jobs_open_now ? (
                <span
                  className="ml-2 inline-block h-2 w-2 rounded-full bg-[var(--jobs)] align-middle"
                  title="Open jobs"
                  aria-label="Open jobs"
                />
              ) : null}
            </button>
          ))}
        </div>
      ) : null}

      {tab === "matches" && match ? (
        <MatchCard match={match} mode={mode} copy={copy}>
          {data.briefings_enabled && match.briefing_markdown ? (
            <div className="space-y-2">
              <div className="flex justify-end">
                <ReadAloudButton
                  key={`brief-${match.company_id || match.name}`}
                  text={match.briefing_markdown}
                  label="Read aloud"
                />
              </div>
              <SimpleMarkdown text={match.briefing_markdown} />
            </div>
          ) : data.briefings_enabled ? (
            <p className="text-sm text-[var(--ink-muted)]">
              AI match report unavailable right now. You still have your top
              matches and training routes above.
            </p>
          ) : null}

          <FiveStepPlan
            key={String(match.company_id || match.name)}
            mode={mode}
            match={match}
            leaver={(data.leaver || {}) as Record<string, unknown>}
            enabled={Boolean(data.plans_enabled)}
          />
        </MatchCard>
      ) : null}

      {tab === "matches" ? (
        <details className="rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-4">
          <summary className="cursor-pointer font-display text-lg text-[var(--ink)]">
            How to use this advice
          </summary>
          <ul className="mt-3 space-y-2 text-sm text-[var(--ink-muted)]">
            {copy.advice.map((line) => (
              <li key={line}>{line}</li>
            ))}
            {mode === "work" ? (
              <li>
                Verify openings on{" "}
                {match?.website ? (
                  <a
                    className="underline decoration-[var(--accent)]"
                    href={match.website}
                    target="_blank"
                    rel="noreferrer"
                  >
                    the employer website
                  </a>
                ) : (
                  <a
                    className="underline decoration-[var(--accent)]"
                    href="https://www.findapprenticeship.service.gov.uk/"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Find an apprenticeship
                  </a>
                )}
                .
              </li>
            ) : null}
            {mode === "military" ? (
              <li>
                Check ELC courses via{" "}
                <a
                  className="underline decoration-[var(--accent)]"
                  href="https://www.enhancedlearningcredits.com/"
                  target="_blank"
                  rel="noreferrer"
                >
                  ELCAS
                </a>
                .
              </li>
            ) : null}
          </ul>
        </details>
      ) : null}
    </section>
  );
}
