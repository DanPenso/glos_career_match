"""Shared presentation labels for match fit / hiring signals."""

from __future__ import annotations

from typing import Any


def fit_label(score: float) -> str:
    s = float(score)
    if s >= 0.55:
        return "Strong"
    if s >= 0.30:
        return "Good"
    return "Worth exploring"


def hiring_label(row: dict[str, Any]) -> str:
    signal = str(row.get("hiring_signal", "")).strip().lower()
    if signal == "high" or float(row.get("hiring_score", 0) or 0) >= 0.85:
        return "Often hiring"
    if signal == "medium" or float(row.get("hiring_score", 0) or 0) >= 0.5:
        return "Sometimes hiring"
    return "Check current openings"


def overall_label(rank: int) -> str:
    if rank == 0:
        return "Your strongest match"
    if rank == 1:
        return "A strong option"
    return "Also worth a look"
