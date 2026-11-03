"""Aggregate findings into a verdict.

score = min(100, sum of finding points)
score >= SCORE_MALICIOUS  -> "malicious"
score >= SCORE_SUSPICIOUS -> "suspicious"
otherwise                 -> "clean"

Suspicious and malicious files are quarantined; clean files are released.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .. import config
from .checks import Finding


@dataclass
class Verdict:
    verdict: str
    risk_score: int
    reasons: List[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return self.verdict == "clean"

    @property
    def quarantine(self) -> bool:
        return self.verdict in ("suspicious", "malicious")


def classify(
    findings: List[Finding],
    *,
    malicious_at: int | None = None,
    suspicious_at: int | None = None,
) -> Verdict:
    malicious_at = config.SCORE_MALICIOUS if malicious_at is None else malicious_at
    suspicious_at = config.SCORE_SUSPICIOUS if suspicious_at is None else suspicious_at

    score = min(100, sum(f.points for f in findings))
    reasons = [f.reason for f in findings]

    if score >= malicious_at:
        label = "malicious"
    elif score >= suspicious_at:
        label = "suspicious"
    else:
        label = "clean"
        if not reasons:
            reasons = ["no threats detected"]

    return Verdict(verdict=label, risk_score=score, reasons=reasons)
