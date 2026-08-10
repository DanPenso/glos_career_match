"use client";

import { useMemo, useState } from "react";
import type { IntakeForm, MatchMode, TaxonomyResponse } from "@/lib/types";

type Props = {
  taxonomy: TaxonomyResponse;
  onSubmit: (form: IntakeForm) => void;
  busy?: boolean;
  busyMode?: MatchMode | null;
};

function Chip({
  label,
  selected,
  onClick,
}: {
  label: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-3 py-1.5 text-sm font-medium transition ${
        selected
          ? "border-[var(--accent-ink)] bg-[var(--accent)] text-[var(--accent-ink)] shadow-[0_2px_0_0_var(--trust)]"
          : "border-[var(--line)] bg-[var(--surface)] text-[var(--ink)] hover:border-[var(--trust)]"
      }`}
    >
      {label}
    </button>
  );
}

function toggle(list: string[], value: string, max?: number): string[] {
  if (list.includes(value)) return list.filter((x) => x !== value);
  if (max && list.length >= max) return list;
  return [...list, value];
}

export function IntakeFormView({ taxonomy, onSubmit, busy, busyMode }: Props) {
  const intake = taxonomy.intake;
  const [leaverType, setLeaverType] = useState(intake.leaver_types[0] ?? "");
  const [location, setLocation] = useState(intake.locations[0] ?? "");
  const [qualification, setQualification] = useState(
    intake.qualification_levels[0] ?? "",
  );
  const [availability, setAvailability] = useState(intake.availability[0] ?? "");
  const [courses, setCourses] = useState<string[]>([]);
  const [interests, setInterests] = useState<string[]>([]);
  const [passions, setPassions] = useState<string[]>([]);
  const [experience, setExperience] = useState<string[]>([]);
  const [showMoreAboutYou, setShowMoreAboutYou] = useState(false);
  const [proudExample, setProudExample] = useState("");
  const [goalSentence, setGoalSentence] = useState("");
  const [barriers, setBarriers] = useState<string[]>([]);
  const [mustHaves, setMustHaves] = useState<string[]>([]);
  const [supportAvailable, setSupportAvailable] = useState<string[]>([]);
  const [applyReadiness, setApplyReadiness] = useState("");
  const [useOpenAIBriefing, setUseOpenAIBriefing] = useState(false);
  const [useGeminiPlan, setUseGeminiPlan] = useState(false);
  const [allowAnonymousLogging, setAllowAnonymousLogging] = useState(true);
  const [error, setError] = useState("");

  const courseChoices = useMemo(() => {
    const t = leaverType.toLowerCase();
    if (
      t.includes("university") ||
      t.includes("postgraduate") ||
      t.includes("graduate")
    ) {
      return intake.course_areas.university;
    }
    return intake.course_areas.school_college;
  }, [intake, leaverType]);

  function submitMode(mode: MatchMode) {
    if (!interests.length && !courses.length) {
      setError("Pick at least one interest or course.");
      return;
    }
    setError("");
    onSubmit({
      leaver_type: leaverType,
      location,
      courses,
      interests,
      passions,
      work_experience: experience,
      qualification_level: qualification,
      availability,
      proud_example: proudExample.trim().slice(0, 500),
      goal_sentence: goalSentence.trim().slice(0, 160),
      barriers,
      must_haves: mustHaves,
      support_available: supportAvailable,
      apply_readiness: applyReadiness,
      psych_answers: {},
      use_openai_briefing: useOpenAIBriefing,
      use_gemini_plan: useGeminiPlan,
      allow_anonymous_logging: allowAnonymousLogging,
      mode,
    });
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submitMode("work");
      }}
      className="space-y-8"
    >      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block space-y-1.5 text-sm">
          <span className="font-medium text-[var(--ink-muted)]">I am a…</span>
          <select
            className="field"
            value={leaverType}
            onChange={(e) => setLeaverType(e.target.value)}
          >
            {intake.leaver_types.map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </label>
        <label className="block space-y-1.5 text-sm">
          <span className="font-medium text-[var(--ink-muted)]">Based near</span>
          <select
            className="field"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
          >
            {intake.locations.map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </label>
        <label className="block space-y-1.5 text-sm">
          <span className="font-medium text-[var(--ink-muted)]">
            Qualifications so far
          </span>
          <select
            className="field"
            value={qualification}
            onChange={(e) => setQualification(e.target.value)}
          >
            {intake.qualification_levels.map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </label>
        <label className="block space-y-1.5 text-sm">
          <span className="font-medium text-[var(--ink-muted)]">Availability</span>
          <select
            className="field"
            value={availability}
            onChange={(e) => setAvailability(e.target.value)}
          >
            {intake.availability.map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </label>
      </div>

      <fieldset className="space-y-3">
        <legend className="text-sm font-medium text-[var(--ink-muted)]">
          Interests (up to 5)
        </legend>
        <div className="flex flex-wrap gap-2">
          {intake.interests.map((item) => (
            <Chip
              key={item}
              label={item}
              selected={interests.includes(item)}
              onClick={() => setInterests(toggle(interests, item, 5))}
            />
          ))}
        </div>
      </fieldset>

      <fieldset className="space-y-3">
        <legend className="text-sm font-medium text-[var(--ink-muted)]">
          Courses (optional)
        </legend>
        <div className="flex flex-wrap gap-2">
          {courseChoices.map((item) => (
            <Chip
              key={item}
              label={item}
              selected={courses.includes(item)}
              onClick={() => setCourses(toggle(courses, item))}
            />
          ))}
        </div>
      </fieldset>

      <fieldset className="space-y-3">
        <legend className="text-sm font-medium text-[var(--ink-muted)]">
          What you enjoy (up to 4)
        </legend>
        <div className="flex flex-wrap gap-2">
          {intake.passions.map((item) => (
            <Chip
              key={item}
              label={item}
              selected={passions.includes(item)}
              onClick={() => setPassions(toggle(passions, item, 4))}
            />
          ))}
        </div>
      </fieldset>

      <fieldset className="space-y-3">
        <legend className="text-sm font-medium text-[var(--ink-muted)]">
          Experience so far
        </legend>
        <div className="flex flex-wrap gap-2">
          {intake.work_experience_types.map((item) => (
            <Chip
              key={item}
              label={item}
              selected={experience.includes(item)}
              onClick={() => setExperience(toggle(experience, item))}
            />
          ))}
        </div>
      </fieldset>

      <div className="space-y-3 rounded-2xl border border-dashed border-[var(--line)] bg-[var(--surface)] p-4">
        <button
          type="button"
          className="flex w-full items-center justify-between gap-3 text-left"
          onClick={() => setShowMoreAboutYou((v) => !v)}
          aria-expanded={showMoreAboutYou}
        >
          <span>
            <span className="block text-sm font-medium text-[var(--ink)]">
              Add a bit more about you (optional)
            </span>
            <span className="mt-0.5 block text-xs text-[var(--ink-muted)]">
              Helps AI advice and plans feel more personal — skip if you prefer.
            </span>
          </span>
          <span className="text-sm font-medium text-[var(--trust)]">
            {showMoreAboutYou ? "Hide" : "Show"}
          </span>
        </button>

        {showMoreAboutYou ? (
          <div className="space-y-5 border-t border-[var(--line)] pt-4">
            <label className="block space-y-1.5 text-sm">
              <span className="font-medium text-[var(--ink-muted)]">
                In one sentence, what are you looking for?
              </span>
              <input
                className="field"
                value={goalSentence}
                maxLength={160}
                placeholder="e.g. A local cyber apprenticeship with clear training"
                onChange={(e) => setGoalSentence(e.target.value)}
              />
              <span className="text-xs text-[var(--ink-muted)]">
                {goalSentence.trim().length}/160
              </span>
            </label>

            <label className="block space-y-1.5 text-sm">
              <span className="font-medium text-[var(--ink-muted)]">
                One thing you’re proud of
              </span>
              <textarea
                className="field min-h-[88px]"
                value={proudExample}
                maxLength={500}
                placeholder="School, job, volunteering, home, or a project — what you did and what happened"
                onChange={(e) => setProudExample(e.target.value)}
              />
              <span className="text-xs text-[var(--ink-muted)]">
                {proudExample.trim().length}/500 · Used for CV / STAR-style tips
              </span>
            </label>

            {(intake.barriers?.length ?? 0) > 0 ? (
              <fieldset className="space-y-3">
                <legend className="text-sm font-medium text-[var(--ink-muted)]">
                  What might get in the way? (optional)
                </legend>
                <div className="flex flex-wrap gap-2">
                  {intake.barriers!.map((item) => (
                    <Chip
                      key={item}
                      label={item}
                      selected={barriers.includes(item)}
                      onClick={() => setBarriers(toggle(barriers, item, 6))}
                    />
                  ))}
                </div>
              </fieldset>
            ) : null}

            {(intake.must_haves?.length ?? 0) > 0 ? (
              <fieldset className="space-y-3">
                <legend className="text-sm font-medium text-[var(--ink-muted)]">
                  Must-haves for your next step (optional)
                </legend>
                <div className="flex flex-wrap gap-2">
                  {intake.must_haves!.map((item) => (
                    <Chip
                      key={item}
                      label={item}
                      selected={mustHaves.includes(item)}
                      onClick={() => setMustHaves(toggle(mustHaves, item, 6))}
                    />
                  ))}
                </div>
              </fieldset>
            ) : null}

            {(intake.support_available?.length ?? 0) > 0 ? (
              <fieldset className="space-y-3">
                <legend className="text-sm font-medium text-[var(--ink-muted)]">
                  Who can support you? (optional)
                </legend>
                <div className="flex flex-wrap gap-2">
                  {intake.support_available!.map((item) => (
                    <Chip
                      key={item}
                      label={item}
                      selected={supportAvailable.includes(item)}
                      onClick={() =>
                        setSupportAvailable(toggle(supportAvailable, item, 4))
                      }
                    />
                  ))}
                </div>
              </fieldset>
            ) : null}

            {(intake.apply_readiness?.length ?? 0) > 0 ? (
              <fieldset className="space-y-3">
                <legend className="text-sm font-medium text-[var(--ink-muted)]">
                  How ready do you feel to apply?
                </legend>
                <div className="flex flex-wrap gap-2">
                  {intake.apply_readiness!.map((item) => (
                    <Chip
                      key={item}
                      label={item}
                      selected={applyReadiness === item}
                      onClick={() =>
                        setApplyReadiness(applyReadiness === item ? "" : item)
                      }
                    />
                  ))}
                </div>
              </fieldset>
            ) : null}
          </div>
        ) : null}
      </div>

      <fieldset className="space-y-3 rounded-2xl border border-[var(--line)] bg-[var(--paper)] p-4">
        <legend className="text-sm font-medium text-[var(--ink-muted)]">
          Must be checked for AI responses!
        </legend>
        <label className="flex items-start gap-3 text-sm text-[var(--ink)]">
          <input
            type="checkbox"
            className="mt-1"
            checked={useOpenAIBriefing}
            onChange={(e) => setUseOpenAIBriefing(e.target.checked)}
          />
          <span>
            Generate AI match reports for your top matches (OpenAI). Works for work,
            education, and military pathways — linked to your profile. Off by default.
          </span>
        </label>
        <label className="flex items-start gap-3 text-sm text-[var(--ink)]">
          <input
            type="checkbox"
            className="mt-1"
            checked={useGeminiPlan}
            onChange={(e) => setUseGeminiPlan(e.target.checked)}
          />
          <span>
            Enable AI 5-step action plans (Google Gemini) on each match — including
            “break it down” and follow-up questions. Off by default.
          </span>
        </label>
        <label className="flex items-start gap-3 text-sm text-[var(--ink)]">
          <input
            type="checkbox"
            className="mt-1"
            checked={allowAnonymousLogging}
            onChange={(e) => setAllowAnonymousLogging(e.target.checked)}
          />
          <span>
            Allow anonymous interests/work-style signals to be logged to improve
            clustering over time.
          </span>
        </label>
      </fieldset>

      {error ? <p className="text-sm text-red-700">{error}</p> : null}

      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
        <button
          type="submit"
          className="btn-primary"
          disabled={busy}
        >
          {busy && busyMode === "work"
            ? useOpenAIBriefing
              ? "Finding work matches & reports…"
              : "Finding work matches…"
            : "Find my work matches"}
        </button>
        <button
          type="button"
          className="btn-primary"
          disabled={busy}
          onClick={() => submitMode("education")}
        >
          {busy && busyMode === "education"
            ? "Finding education matches…"
            : "Find my education matches"}
        </button>
        <button
          type="button"
          className="btn-primary"
          disabled={busy}
          onClick={() => submitMode("military")}
        >
          {busy && busyMode === "military"
            ? "Finding military pathways…"
            : "Military pathways"}
        </button>
      </div>
      <p className="text-xs text-[var(--ink-muted)]">
        Non-commercial demo. Education courses use National Careers Service open
        data (OGL). Military pathways are guidance only — not official recruitment
        advice.
      </p>
    </form>
  );
}
