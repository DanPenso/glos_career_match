"use client";

import { useState } from "react";
import type { AgeBand, IntakeForm, MatchMode, TaxonomyResponse } from "@/lib/types";

type Props = {
  taxonomy: TaxonomyResponse;
  onSubmit: (form: IntakeForm) => void;
  busy?: boolean;
  busyMode?: MatchMode | null;
};

const FALLBACK_AGE_BANDS: { id: AgeBand; label: string }[] = [
  { id: "under_16", label: "Under 16" },
  { id: "16_17", label: "16–17" },
  { id: "18_24", label: "18–24" },
  { id: "25_plus", label: "25+" },
  { id: "prefer_not", label: "Prefer not to say" },
];

function InterestTile({
  label,
  icon,
  selected,
  onClick,
}: {
  label: string;
  icon?: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={`flex flex-col items-center gap-2 rounded-2xl border p-3 text-center transition ${
        selected
          ? "border-[var(--accent-ink)] bg-[var(--accent)] text-[var(--accent-ink)] shadow-[0_3px_0_0_var(--trust)]"
          : "border-[var(--line)] bg-[var(--surface)] text-[var(--ink)] hover:border-[var(--trust)]"
      }`}
    >
      {icon ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={icon}
          alt=""
          width={96}
          height={96}
          className="h-16 w-16 rounded-xl object-contain sm:h-20 sm:w-20"
        />
      ) : null}
      <span className="text-xs font-semibold leading-snug sm:text-sm">{label}</span>
    </button>
  );
}

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

function groupById(
  groups: { id?: string; title: string; items: string[] }[] | undefined,
  id: string,
): string[] {
  const byId = groups?.find((g) => g.id === id);
  if (byId?.items?.length) return byId.items;
  const byTitle = groups?.find((g) =>
    id === "study"
      ? /work or study/i.test(g.title)
      : /enjoy|things you do/i.test(g.title),
  );
  return byTitle?.items ?? [];
}

const ENJOY_MAX = 5;
const STUDY_MAX = 5;

function allowsAi(ageBand: string): boolean {
  return ageBand === "16_17" || ageBand === "18_24" || ageBand === "25_plus";
}

export function IntakeFormView({ taxonomy, onSubmit, busy, busyMode }: Props) {
  const intake = taxonomy.intake;
  const ageBands = intake.age_bands?.length
    ? intake.age_bands
    : FALLBACK_AGE_BANDS;
  const [ageBand, setAgeBand] = useState("");
  const [youthGuidanceOk, setYouthGuidanceOk] = useState(false);
  const [leaverType, setLeaverType] = useState(intake.leaver_types[0] ?? "");
  const [location, setLocation] = useState(intake.locations[0] ?? "");
  const [qualification, setQualification] = useState(
    intake.qualification_levels[0] ?? "",
  );
  const [availability, setAvailability] = useState(intake.availability[0] ?? "");
  const [enjoyPicks, setEnjoyPicks] = useState<string[]>([]);
  const [studyPicks, setStudyPicks] = useState<string[]>([]);
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
  const [liveOpportunitiesOnly, setLiveOpportunitiesOnly] = useState(false);
  const [error, setError] = useState("");

  const under16 = ageBand === "under_16";
  const aiAllowed = allowsAi(ageBand);
  const needsYouthTick = ageBand === "16_17";
  const showHealthNote = barriers.some((b) => /health|disability/i.test(b));
  const studyAreas = groupById(intake.interest_groups, "study");
  const enjoyActivities =
    groupById(intake.interest_groups, "enjoy").length > 0
      ? groupById(intake.interest_groups, "enjoy")
      : (intake.interests || []).filter((item) => !studyAreas.includes(item));
  const passionSet = new Set(intake.passions);
  const enjoyItems = [...enjoyActivities, ...intake.passions];
  const formReady = Boolean(ageBand) && !under16;
  const selectedInterests = [
    ...enjoyPicks.filter((item) => !passionSet.has(item)),
    ...studyPicks,
  ];
  const selectedPassions = enjoyPicks.filter((item) => passionSet.has(item));

  function submitMode(mode: MatchMode) {
    if (!ageBand) {
      setError("Please tell us your age band first.");
      return;
    }
    if (under16) {
      setError(
        "MatchKite is for people aged 16 and over. Ask a parent, carer, teacher, or careers adviser to help.",
      );
      return;
    }
    if (!selectedInterests.length) {
      setError("Pick at least one thing you enjoy doing, or a work / study area.");
      return;
    }
    if (
      needsYouthTick &&
      (useOpenAIBriefing || useGeminiPlan) &&
      !youthGuidanceOk
    ) {
      setError(
        "If you turn on AI help under 18, please confirm you understand it is guidance only.",
      );
      return;
    }
    setError("");
    onSubmit({
      leaver_type: leaverType,
      location,
      age_band: ageBand,
      courses: [],
      interests: selectedInterests,
      passions: selectedPassions,
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
      use_openai_briefing: aiAllowed && useOpenAIBriefing,
      use_gemini_plan: aiAllowed && useGeminiPlan,
      allow_anonymous_logging: allowAnonymousLogging,
      live_opportunities_only: mode !== "military" && liveOpportunitiesOnly,
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
    >
      <fieldset className="space-y-3 rounded-2xl border border-[var(--line)] bg-[var(--paper)] p-4">
        <legend className="text-sm font-medium text-[var(--ink-muted)]">
          How old are you?
        </legend>
        <p className="text-xs text-[var(--ink-muted)]">
          Self-declared only — we do not verify ID. MatchKite is built for ages
          16+.
        </p>
        <div className="flex flex-wrap gap-2">
          {ageBands.map((band) => (
            <Chip
              key={band.id}
              label={band.label}
              selected={ageBand === band.id}
              onClick={() => {
                setAgeBand(band.id);
                setError("");
                if (band.id === "under_16" || band.id === "prefer_not") {
                  setUseOpenAIBriefing(false);
                  setUseGeminiPlan(false);
                }
                if (band.id !== "16_17") setYouthGuidanceOk(false);
              }}
            />
          ))}
        </div>
        {under16 ? (
          <p className="text-sm text-[var(--ink)]">
            Thanks for saying. MatchKite is for people aged{" "}
            <strong>16 and over</strong>. Please ask a parent, carer, teacher,
            or careers adviser to help you explore options.
          </p>
        ) : null}
        {ageBand === "prefer_not" ? (
          <p className="text-sm text-[var(--ink-muted)]">
            You can still explore matches. AI reports and action plans stay off
            unless you choose an age band of 16 or over.
          </p>
        ) : null}
        {ageBand === "16_17" ? (
          <p className="text-sm text-[var(--ink-muted)]">
            If you explore military pathways, check official Armed Forces sites
            for entry ages. Talk options through with a parent, carer, or careers
            adviser.
          </p>
        ) : null}
      </fieldset>

      {formReady ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
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
              <span className="font-medium text-[var(--ink-muted)]">
                Based near
              </span>
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
              <span className="font-medium text-[var(--ink-muted)]">
                Availability
              </span>
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

          <label className="flex items-start gap-3 rounded-2xl border border-[var(--line)] bg-[var(--paper)] p-4 text-sm text-[var(--ink)]">
            <input
              type="checkbox"
              className="mt-1"
              checked={liveOpportunitiesOnly}
              onChange={(e) => setLiveOpportunitiesOnly(e.target.checked)}
            />
            <span>
              <span className="font-medium">
                Only show options with live apprenticeship opportunities
              </span>
              <span className="mt-1 block text-xs text-[var(--ink-muted)]">
                Work matches: open apprenticeships on Find an apprenticeship.
                Education matches: courses listed as live in the National
                Careers Service directory. Leave this unticked if you just want
                local options. Does not apply to military pathways.
              </span>
            </span>
          </label>

          <fieldset className="space-y-3">
            <legend className="text-sm font-medium text-[var(--ink-muted)]">
              What you enjoy (up to {ENJOY_MAX})
            </legend>
            <p className="text-xs text-[var(--ink-muted)]">
              Mix things you do a lot with how you like to spend your energy —
              {" "}
              {ENJOY_MAX} picks in this section.
            </p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
              {enjoyItems.map((item) => (
                <InterestTile
                  key={item}
                  label={item}
                  icon={intake.interest_icons?.[item]}
                  selected={enjoyPicks.includes(item)}
                  onClick={() =>
                    setEnjoyPicks(toggle(enjoyPicks, item, ENJOY_MAX))
                  }
                />
              ))}
            </div>
          </fieldset>

          {studyAreas.length ? (
          <fieldset className="space-y-3">
            <legend className="text-sm font-medium text-[var(--ink-muted)]">
              Work or study areas (up to {STUDY_MAX})
            </legend>
            <p className="text-xs text-[var(--ink-muted)]">
              Subjects or industries you might want to work in. You can skip
              this if you only know what you enjoy doing.
            </p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
              {studyAreas.map((item) => (
                <InterestTile
                  key={item}
                  label={item}
                  icon={intake.interest_icons?.[item]}
                  selected={studyPicks.includes(item)}
                  onClick={() =>
                    setStudyPicks(toggle(studyPicks, item, STUDY_MAX))
                  }
                />
              ))}
            </div>
          </fieldset>
          ) : null}

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
                    {showHealthNote ? (
                      <p className="text-xs text-[var(--ink-muted)]">
                        This helps matching. It is not medical advice — check
                        official course or employer pages and support services.
                      </p>
                    ) : null}
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
            {!aiAllowed ? (
              <p className="text-sm text-[var(--ink-muted)]">
                AI reports and action plans need a declared age band of 16 or over.
              </p>
            ) : (
              <>
                <label className="flex items-start gap-3 text-sm text-[var(--ink)]">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={useOpenAIBriefing}
                    onChange={(e) => setUseOpenAIBriefing(e.target.checked)}
                  />
                  <span>
                    Generate AI match reports for your top matches (OpenAI). Works
                    for work, education, and military pathways — linked to your
                    profile. Off by default.
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
                    Enable AI 5-step action plans (Google Gemini) on each match —
                    including “break it down” and follow-up questions. Off by
                    default.
                  </span>
                </label>
                {needsYouthTick && (useOpenAIBriefing || useGeminiPlan) ? (
                  <label className="flex items-start gap-3 text-sm text-[var(--ink)]">
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={youthGuidanceOk}
                      onChange={(e) => setYouthGuidanceOk(e.target.checked)}
                    />
                    <span>
                      I understand AI help is guidance only — not official careers
                      or recruitment advice. I can check details with a trusted adult.
                    </span>
                  </label>
                ) : null}
              </>
            )}
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
            <button type="submit" className="btn-primary" disabled={busy}>
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
            data (OGL). Military pathways are guidance only — not official
            recruitment advice.
          </p>
        </>
      ) : (
        <>
          {error ? <p className="text-sm text-red-700">{error}</p> : null}
          {!ageBand ? (
            <p className="text-sm text-[var(--ink-muted)]">
              Choose an age band to continue.
            </p>
          ) : null}
        </>
      )}
    </form>
  );
}
