"use client";

import type { ReactNode } from "react";

export const HELP_LINKS = [
  {
    label: "999",
    detail: "Immediate danger",
    href: undefined as string | undefined,
  },
  {
    label: "Childline 0800 1111",
    detail: "Under 19",
    href: "https://www.childline.org.uk",
  },
  {
    label: "Samaritans 116 123",
    detail: "Talk to someone",
    href: "https://www.samaritans.org",
  },
] as const;

export function SafeguardingHelp({
  title = "If you need help now",
  compact = false,
}: {
  title?: string;
  compact?: boolean;
}) {
  return (
    <aside
      className={`rounded-xl border border-[var(--line)] bg-[var(--surface)] ${
        compact ? "p-3" : "p-4"
      }`}
      role="note"
    >
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--trust)]">
        {title}
      </p>
      <p
        className={`mt-1 text-[var(--ink)] ${compact ? "text-sm" : "text-sm leading-relaxed"}`}
      >
        MatchKite is only for careers ideas. We cannot support personal safety or
        mental health.
      </p>
      <ul className="mt-2 space-y-1 text-sm text-[var(--ink)]">
        <li>
          If you are in <strong>immediate danger</strong>, call <strong>999</strong>
        </li>
        <li>
          <strong>Childline</strong> (under 19):{" "}
          <strong>0800 1111</strong>
          {" · "}
          <a
            href="https://www.childline.org.uk"
            target="_blank"
            rel="noreferrer"
            className="underline decoration-[var(--accent)]"
          >
            childline.org.uk
          </a>
        </li>
        <li>
          <strong>Samaritans</strong>: <strong>116 123</strong>
          {" · "}
          <a
            href="https://www.samaritans.org"
            target="_blank"
            rel="noreferrer"
            className="underline decoration-[var(--accent)]"
          >
            samaritans.org
          </a>
        </li>
        <li>
          For careers help in person, ask a teacher, tutor, or local careers adviser
        </li>
      </ul>
    </aside>
  );
}

export function MilitaryAgeNotice({ children }: { children?: ReactNode }) {
  return (
    <p className="rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--ink)]">
      {children ||
        "Military pathways here are information only. Entry ages and rules come from official Armed Forces sites. If you are under 18, talk this through with a parent, carer, or careers adviser before taking any next step."}
    </p>
  );
}
