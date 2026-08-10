import Link from "next/link";

export default function HelpPage() {
  return (
    <main className="mx-auto min-h-screen max-w-3xl px-5 py-10 sm:px-8">
      <h1 className="font-display text-4xl text-[var(--ink)]">Need help?</h1>
      <p className="mt-3 text-sm text-[var(--ink-muted)]">
        MatchKite is a careers matching demo for Bristol and Gloucestershire. It
        cannot support personal safety or mental health.
      </p>

      <section className="mt-8 space-y-3 rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-5">
        <h2 className="font-display text-2xl text-[var(--ink)]">
          If you need help now
        </h2>
        <ul className="space-y-2 text-sm text-[var(--ink)]">
          <li>
            If you are in <strong>immediate danger</strong>, call{" "}
            <strong>999</strong>
          </li>
          <li>
            <strong>Childline</strong> (under 19): <strong>0800 1111</strong> ·{" "}
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
            <strong>Samaritans</strong>: <strong>116 123</strong> ·{" "}
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
            For careers help in person, ask a teacher, tutor, or local careers
            adviser
          </li>
        </ul>
      </section>

      <section className="mt-8 space-y-2">
        <h2 className="font-display text-2xl text-[var(--ink)]">Age</h2>
        <p className="text-sm text-[var(--ink-muted)]">
          MatchKite is for people aged 16 and over. We ask for a self-declared age
          band (not ID). Under 16s are asked to use the tool with a parent, carer,
          teacher, or careers adviser instead.
        </p>
      </section>

      <p className="mt-10 text-sm">
        <Link href="/" className="underline decoration-[var(--accent)]">
          Back to MatchKite
        </Link>
        {" · "}
        <Link href="/privacy" className="underline decoration-[var(--accent)]">
          Privacy notice
        </Link>
      </p>
    </main>
  );
}
