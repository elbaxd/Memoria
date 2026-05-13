"""Public API for the ``judge`` package."""

from .checker import OutputChecker
from .judge import Judge
from .models import (
    Guideline,
    GuidelineResult,
    JudgeParameters,
    JudgeResult,
    TestCase,
    TestCaseResult,
    Verdict,
)
from .rules import (
    DEFAULT_GUIDELINES,
    ERDOC_GUIDELINES,
    RuleEngine,
    make_guideline,
)
from .runner import CodeRunner, RunResult

__all__ = [
    # Core orchestrator
    "Judge",
    # Models
    "Guideline",
    "GuidelineResult",
    "JudgeParameters",
    "JudgeResult",
    "TestCase",
    "TestCaseResult",
    "Verdict",
    # Rules / guidelines
    "DEFAULT_GUIDELINES",
    "ERDOC_GUIDELINES",
    "RuleEngine",
    "make_guideline",
    # Runner / checker
    "CodeRunner",
    "RunResult",
    "OutputChecker",
]
