export default function PrivacyPage() {
  return (
    <main className="mx-auto min-h-screen max-w-3xl px-5 py-10 sm:px-8">
      <h1 className="font-display text-4xl text-[var(--ink)]">Privacy notice</h1>
      <p className="mt-3 text-sm text-[var(--ink-muted)]">
        MatchKite is a non-commercial demo for Gloucestershire careers guidance. It
        gives guidance only and is not an official careers service.
      </p>

      <section className="mt-6 space-y-2">
        <h2 className="font-display text-2xl text-[var(--ink)]">What we process</h2>
        <p className="text-sm text-[var(--ink-muted)]">
          Intake choices such as interests, courses, work-experience signals, optional
          notes (for example a short goal or proud example), barriers/must-haves you
          choose to share, and model outputs used to rank local employers and pathways.
        </p>
      </section>

      <section className="mt-6 space-y-2">
        <h2 className="font-display text-2xl text-[var(--ink)]">What we do not collect</h2>
        <p className="text-sm text-[var(--ink-muted)]">
          No name, email, phone number, or contact details are required to use the demo.
        </p>
      </section>

      <section className="mt-6 space-y-2">
        <h2 className="font-display text-2xl text-[var(--ink)]">AI briefing consent</h2>
        <p className="text-sm text-[var(--ink-muted)]">
          AI briefings are optional and off by default. If you opt in, intake context and
          matched employer, course, or military pathway context are sent to OpenAI to
          generate briefing text.
        </p>
      </section>

      <section className="mt-6 space-y-2">
        <h2 className="font-display text-2xl text-[var(--ink)]">AI action-plan consent</h2>
        <p className="text-sm text-[var(--ink-muted)]">
          5-step action plans are optional and off by default. If you opt in, intake
          context and the selected match are sent to Google Gemini to generate steps,
          breakdowns, and short chat replies. Do not enter personal contact details in
          the chat box.
        </p>
      </section>

      <section className="mt-6 space-y-2">
        <h2 className="font-display text-2xl text-[var(--ink)]">Anonymous learning data</h2>
        <p className="text-sm text-[var(--ink-muted)]">
          Anonymous interests and work-style signals can be used to improve clustering when
          you opt in. You can opt out before submitting.
        </p>
      </section>

      <section className="mt-6 space-y-2">
        <h2 className="font-display text-2xl text-[var(--ink)]">Retention</h2>
        <p className="text-sm text-[var(--ink-muted)]">
          Anonymous live-learning events are retained for up to 180 days by default, then
          pruned automatically. This can be configured by the operator.
        </p>
      </section>

      <section className="mt-6 space-y-2">
        <h2 className="font-display text-2xl text-[var(--ink)]">Data sources</h2>
        <p className="text-sm text-[var(--ink-muted)]">
          Employer context includes DfE and Companies House public-sector information under
          the Open Government Licence and curated project data. See `DATA.md` for full
          attribution.
        </p>
      </section>

      <p className="mt-8 text-xs text-[var(--ink-muted)]">
        Last updated: 2026-08-04
      </p>
    </main>
  );
}
