"""Stateless detection logic: checks, scoring, and the EICAR signature."""
from .checks import Finding, run_all
from .scoring import Verdict, classify

__all__ = ["Finding", "run_all", "Verdict", "classify"]
