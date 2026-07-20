"use client";

import { useEffect, useState } from "react";
import { IntakeFormView } from "@/components/IntakeForm";
import { MatchResults } from "@/components/MatchResults";
import { fetchMatch, fetchTaxonomy } from "@/lib/api";
import type { IntakeForm, MatchResponse, TaxonomyResponse } from "@/lib/types";

export default function HomePage() {
  const [taxonomy, setTaxonomy] = useState<TaxonomyResponse | null>(null);
  const [loadError, setLoadError] = useState("");
  const [busy, setBusy] = useState(false);
  const [matchError, setMatchError] = useState("");
  const [results, setResults] = useState<MatchResponse | null>(null);

  useEffect(() => {
    fetchTaxonomy()
      .then(setTaxonomy)
      .catch((e: Error) => setLoadError(e.message));
  }, []);

  async function onSubmit(form: IntakeForm) {
    setBusy(true);
    setMatchError("");
    try {
      const data = await fetchMatch(form);
      setResults(data);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setMatchError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
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
        <div className="relative mx-auto flex max-w-3xl flex-col gap-4 px-5 pb-14 pt-10 sm:px-8 sm:pt-16">
          <h1 className="font-display text-4xl leading-tight sm:text-5xl">
            Glos Career Match
          </h1>
          <p className="max-w-xl text-base text-[var(--paper)]/85 sm:text-lg">
            Find your next step in Gloucestershire — local employers, training
            routes, and one clear move you can make this month.
          </p>
          {!results ? (
            <a href="#intake" className="btn-primary w-fit">
              Find my matches
            </a>
          ) : null}
        </div>
      </header>

      <div className="mx-auto max-w-3xl px-5 py-10 sm:px-8">
        {results ? (
          <MatchResults data={results} onReset={() => setResults(null)} />
        ) : (
          <section id="intake" className="space-y-6">
            <div>
              <h2 className="font-display text-3xl text-[var(--ink)]">
                Tell us about you
              </h2>
              <p className="mt-2 text-sm text-[var(--ink-muted)]">
                Live demo — guidance only. You control whether AI briefings are
                enabled and whether anonymous learning signals are logged.
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

      <footer className="mx-auto max-w-3xl px-5 pb-12 text-xs text-[var(--ink-muted)] sm:px-8">
        Non-commercial demo · MIT · DfE / Companies House data under OGL — see DATA.md ·
        <a href="/privacy" className="ml-1 underline decoration-[var(--accent)]">
          Privacy
        </a>
      </footer>
    </main>
  );
}
