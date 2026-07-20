"use client";

import { useMemo, useState } from "react";
import type { IntakeForm, TaxonomyResponse } from "@/lib/types";

type Props = {
  taxonomy: TaxonomyResponse;
  onSubmit: (form: IntakeForm) => void;
  busy?: boolean;
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

export function IntakeFormView({ taxonomy, onSubmit, busy }: Props) {
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
  const [useOpenAIBriefing, setUseOpenAIBriefing] = useState(false);
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

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
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
      psych_answers: {},
      use_openai_briefing: useOpenAIBriefing,
      allow_anonymous_logging: allowAnonymousLogging,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-8">
      <div className="grid gap-4 sm:grid-cols-2">
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
            Qualification level
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

      <fieldset className="space-y-3 rounded-2xl border border-[var(--line)] bg-[var(--paper)] p-4">
        <legend className="text-sm font-medium text-[var(--ink-muted)]">
          Privacy controls
        </legend>
        <label className="flex items-start gap-3 text-sm text-[var(--ink)]">
          <input
            type="checkbox"
            className="mt-1"
            checked={useOpenAIBriefing}
            onChange={(e) => setUseOpenAIBriefing(e.target.checked)}
          />
          <span>
            Generate AI match reports for each employer (OpenAI). If off, you
            still get career groups, training routes, and top matches.
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

      <button type="submit" className="btn-primary" disabled={busy}>
        {busy
          ? useOpenAIBriefing
            ? "Finding matches & writing reports…"
            : "Finding matches…"
          : "Find my matches"}
      </button>
    </form>
  );
}
