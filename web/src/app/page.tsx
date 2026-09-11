"use client";

import { useEffect, useState } from "react";
import { IntakeFormView } from "@/components/IntakeForm";
import { MatchResults } from "@/components/MatchResults";
import { fetchMatch, fetchTaxonomy } from "@/lib/api";
import type {
  IntakeForm,
  MatchMode,
  MatchResponse,
  TaxonomyResponse,
} from "@/lib/types";

export default function HomePage() {
  const [taxonomy, setTaxonomy] = useState<TaxonomyResponse | null>(null);
  const [loadError, setLoadError] = useState("");
  const [busy, setBusy] = useState(false);
  const [busyMode, setBusyMode] = useState<MatchMode | null>(null);
  const [matchError, setMatchError] = useState("");
  const [results, setResults] = useState<MatchResponse | null>(null);

  useEffect(() => {
    fetchTaxonomy()
      .then(setTaxonomy)
      .catch((e: Error) => setLoadError(e.message));
  }, []);

  async function onSubmit(form: IntakeForm) {
    setBusy(true);
    setBusyMode(form.mode || "work");
    setMatchError("");
    try {
      const data = await fetchMatch(form);
      setResults(data);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setMatchError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
      setBusyMode(null);
    }
  }

  return (
    <main className="min-h-screen">
      <header className="relative overflow-hidden bg-[var(--hero-deep)] text-[var(--paper)]">
        <div
          className="pointer-events-none absolute inset-0 opacity-40"
          style={{
            background:
              "radial-gradient(600px 280px at 80% 20%, var(--hero-glow), transparent 60%)",
          }}
        />
        <div className="page-shell relative flex flex-col gap-3 pb-6 pt-6 sm:gap-4 sm:pb-8 sm:pt-8 lg:flex-row lg:items-end lg:justify-between lg:gap-12">
          <div className="flex items-center gap-4">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/matchkite-badge.png?v=8"
              alt="MatchKite"
              width={96}
              height={96}
              className="h-24 w-24 shrink-0 rounded-full bg-[var(--paper)] ring-1 ring-[var(--paper)] ring-offset-1 ring-offset-[var(--hero-deep)] shadow-sm"
            />
            <div className="flex flex-col items-start">
              <h1 className="font-display text-3xl leading-tight tracking-tight sm:text-4xl">
                MatchKite
              </h1>
              <span className="mt-1.5 inline-flex rounded-full border border-[var(--accent)]/40 bg-[var(--accent)]/15 px-3 py-1 text-xs font-semibold tracking-wide text-[var(--accent)]">
                Bristol and Glos
              </span>
            </div>
          </div>
          <div className="max-w-xl lg:max-w-lg">
            <p className="font-display text-xl leading-snug tracking-tight text-[var(--paper)] sm:text-2xl">
              Ready for your career to take flight?
            </p>
            <p className="mt-2 text-sm text-[var(--paper)]/85 sm:text-base">
              Tell us what you’re into, and we’ll match you to local jobs, courses,
              training, or military pathways in Bristol and Gloucestershire —
              helping your career take off from wherever you are.
            </p>
          </div>
        </div>
      </header>

      <div className="page-shell py-7 sm:py-8">
        {results ? (
          <MatchResults data={results} onReset={() => setResults(null)} />
        ) : (
          <section id="intake" className="space-y-6">
            <div>
              <h2 className="font-display text-3xl text-[var(--ink)]">
                Tell us about you
              </h2>
              <p className="mt-2 text-sm text-[var(--ink-muted)]">
                Live demo — guidance only. Pick work matches, education matches,
                or military pathways after you complete the form. You control
                whether AI match reports and anonymous learning signals are
                enabled.
                <a
                  href="/privacy"
                  className="ml-1 underline decoration-[var(--accent)]"
                >
                  Read privacy notice
                </a>
                .
              </p>
            </div>

            {loadError ? (
              <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-900">
                {loadError}
                <p className="mt-2">
                  Start the API from the project root:
                  <br />
                  <code className="text-xs">
                    .venv\Scripts\uvicorn api.main:app --reload --port 8000
                  </code>
                </p>
              </div>
            ) : null}

            {taxonomy ? (
              <IntakeFormView
                taxonomy={taxonomy}
                onSubmit={onSubmit}
                busy={busy}
                busyMode={busyMode}
              />
            ) : !loadError ? (
              <p className="text-sm text-[var(--ink-muted)]">Loading options…</p>
            ) : null}

            {matchError ? (
              <p className="text-sm text-red-700">{matchError}</p>
            ) : null}
          </section>
        )}
      </div>

      <footer className="page-shell pb-12 text-xs text-[var(--ink-muted)]">
        Non-commercial demo · MIT · DfE / Companies House / National Careers
        Service data under OGL — see DATA.md ·
        <a href="/privacy" className="ml-1 underline decoration-[var(--accent)]">
          Privacy
        </a>
        {" · "}
        <a href="/help" className="underline decoration-[var(--accent)]">
          Need help?
        </a>
      </footer>
    </main>
  );
}
