"use client";

import { useState } from "react";
import { sendPersonaFeedback } from "@/lib/api";
import type { PersonaFit, PersonaMap2D } from "@/lib/types";

function normalizeMap(map: PersonaMap2D) {
  const pts = [map.you, ...map.centroids];
  const xs = pts.map((p) => p.x);
  const ys = pts.map((p) => p.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const pad = 0.18;
  const dx = maxX - minX || 1;
  const dy = maxY - minY || 1;
  const toSvg = (x: number, y: number) => {
    const nx = (x - minX) / dx;
    const ny = (y - minY) / dy;
    return {
      cx: 14 + nx * (100 - 28) * (1 - pad) + (100 * pad) / 2,
      // flip y so up is higher similarity visually
      cy: 18 + (1 - ny) * (100 - 36) * (1 - pad) + (100 * pad) / 2,
    };
  };
  return toSvg;
}

export function PersonaFitPanel({
  persona,
  blurb,
  disclaimer,
  runnerUp,
  fit,
  map2d,
  learningEventId,
}: {
  persona?: string;
  blurb?: string;
  disclaimer?: string;
  runnerUp?: string | null;
  fit?: PersonaFit[];
  map2d?: PersonaMap2D | null;
  learningEventId?: string | null;
}) {
  const [feedback, setFeedback] = useState<"yes" | "no" | null>(null);
  const [feedbackBusy, setFeedbackBusy] = useState(false);

  if (!persona && !fit?.length) return null;
  const toSvg = map2d ? normalizeMap(map2d) : null;
  const you = map2d && toSvg ? toSvg(map2d.you.x, map2d.you.y) : null;

  async function onFeedback(helpful: boolean) {
    if (!learningEventId || feedbackBusy || feedback) return;
    setFeedbackBusy(true);
    try {
      await sendPersonaFeedback(learningEventId, helpful);
      setFeedback(helpful ? "yes" : "no");
    } catch {
      /* non-blocking */
    } finally {
      setFeedbackBusy(false);
    }
  }

  return (
    <div
      id="career-group"
      className="space-y-5 rounded-3xl border-2 border-[var(--trust)] bg-[var(--surface)] p-5 sm:p-6"
    >
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--trust)]">
          Clustering · your career group
        </p>
        <h3 className="mt-1 font-display text-3xl text-[var(--ink)]">
          {persona}
        </h3>
        {blurb ? (
          <p className="mt-2 text-sm text-[var(--ink-muted)]">{blurb}</p>
        ) : null}
        {runnerUp ? (
          <p className="mt-2 text-sm text-[var(--ink)]">
            You’re also close to <strong>{runnerUp}</strong> — we blended a few
            of those routes into your training list.
          </p>
        ) : null}
        {disclaimer ? (
          <p className="mt-2 text-xs text-[var(--ink-muted)]">{disclaimer}</p>
        ) : null}
        {learningEventId ? (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <p className="text-sm text-[var(--ink-muted)]">
              Does this career group feel right?
            </p>
            {feedback ? (
              <p className="text-sm font-medium text-[var(--trust)]">
                Thanks — that helps improve the model.
              </p>
            ) : (
              <>
                <button
                  type="button"
                  className="btn-ghost text-sm"
                  disabled={feedbackBusy}
                  onClick={() => onFeedback(true)}
                >
                  Yes
                </button>
                <button
                  type="button"
                  className="btn-ghost text-sm"
                  disabled={feedbackBusy}
                  onClick={() => onFeedback(false)}
                >
                  Not really
                </button>
              </>
            )}
          </div>
        ) : null}
      </div>

      <div className="grid gap-8 lg:grid-cols-2 lg:items-start">
        {fit?.length ? (
          <div className="space-y-3">
            <p className="text-sm font-medium text-[var(--ink)]">
              How close you are to each group
            </p>
            <p className="text-xs text-[var(--ink-muted)]">
              Relative closeness in our model (closest group = 100). Not a job
              match percentage.
            </p>
            <ul className="space-y-3">
              {fit.map((row) => (
                <li key={row.persona}>
                  <div className="mb-1 flex items-baseline justify-between gap-2">
                    <span
                      className={`text-sm ${
                        row.is_primary
                          ? "font-semibold text-[var(--ink)]"
                          : "text-[var(--ink-muted)]"
                      }`}
                    >
                      {row.persona}
                      {row.is_primary ? " · closest" : ""}
                      {row.is_runner_up ? " · nearby" : ""}
                    </span>
                    <span className="text-xs font-semibold tabular-nums text-[var(--ink)]">
                      {row.closeness}
                    </span>
                  </div>
                  <div className="h-3 overflow-hidden rounded-full bg-[var(--paper)] ring-1 ring-[var(--line)]">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ${
                        row.is_primary
                          ? "bg-[var(--accent)]"
                          : row.is_runner_up
                            ? "bg-[var(--trust)]"
                            : "bg-[var(--line)]"
                      }`}
                      style={{ width: `${Math.max(6, row.closeness)}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {map2d && you && toSvg ? (
          <div>
            <p className="text-sm font-medium text-[var(--ink)]">
              Where you sit in the model
            </p>
            <p className="mt-1 text-xs text-[var(--ink-muted)]">
              PCA map of the career groups — you are the lime marker.
            </p>
            <svg
              viewBox="0 0 100 100"
              className="mt-3 aspect-square w-full max-w-md rounded-2xl bg-[#eef4f1] ring-1 ring-[var(--line)]"
              role="img"
              aria-label="Map of career groups with your position"
            >
              <defs>
                <radialGradient id="mapGlow" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="#b8f229" stopOpacity="0.4" />
                  <stop offset="100%" stopColor="#b8f229" stopOpacity="0" />
                </radialGradient>
              </defs>
              {/* axis hints */}
              <line
                x1="8"
                y1="92"
                x2="92"
                y2="92"
                stroke="#c5d0cb"
                strokeWidth="0.4"
              />
              <line
                x1="8"
                y1="8"
                x2="8"
                y2="92"
                stroke="#c5d0cb"
                strokeWidth="0.4"
              />
              <circle cx={you.cx} cy={you.cy} r="20" fill="url(#mapGlow)" />
              {map2d.centroids.map((c) => {
                const p = toSvg(c.x, c.y);
                const label = c.persona.split(" ")[0];
                return (
                  <g key={c.persona}>
                    <circle
                      cx={p.cx}
                      cy={p.cy}
                      r={c.is_primary ? 6 : 4.5}
                      fill={c.is_primary ? "#0d5c54" : "#8aa39c"}
                    />
                    <text
                      x={p.cx}
                      y={p.cy - 8}
                      textAnchor="middle"
                      fill="#0f1f1a"
                      style={{ fontSize: "3.6px", fontWeight: 600 }}
                    >
                      {label}
                    </text>
                  </g>
                );
              })}
              <circle
                cx={you.cx}
                cy={you.cy}
                r="5"
                fill="#b8f229"
                stroke="#0f1f1a"
                strokeWidth="1"
              />
              <text
                x={you.cx}
                y={you.cy + 10}
                textAnchor="middle"
                fill="#0f1f1a"
                style={{ fontSize: "3.8px", fontWeight: 700 }}
              >
                You
              </text>
            </svg>
            <p className="mt-2 text-xs text-[var(--ink-muted)]">
              Dark green = your closest group · grey = other groups · lime = you
            </p>
          </div>
        ) : (
          <p className="rounded-2xl bg-[var(--paper)] p-4 text-sm text-[var(--ink-muted)] ring-1 ring-[var(--line)]">
            Cluster map unavailable — restart the API after running{" "}
            <code className="text-xs">scripts/build_persona_model.py</code>.
          </p>
        )}
      </div>
    </div>
  );
}
