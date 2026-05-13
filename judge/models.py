"""Data models for the code judge."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, List, Optional


class Verdict(str, Enum):
    """Possible outcomes for a judged submission."""

    CORRECT = "CORRECT"
    WRONG_ANSWER = "WRONG_ANSWER"
    PARTIAL = "PARTIAL"
    TIME_LIMIT_EXCEEDED = "TIME_LIMIT_EXCEEDED"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    GUIDELINE_VIOLATION = "GUIDELINE_VIOLATION"
    ERROR = "ERROR"


@dataclass
class TestCase:
    """A single input/output pair used to evaluate a submission.

    Attributes:
        input_data: The input to feed to the code under test.
        expected_output: The expected output produced by correct code.
        weight: Relative weight of this test case when computing a score
            (default 1.0).  All weights are normalised before scoring.
        description: Optional human-readable label for this test case.
    """

    input_data: str
    expected_output: str
    weight: float = 1.0
    description: Optional[str] = None


@dataclass
class JudgeParameters:
    """Configuration knobs for a judging run.

    Attributes:
        time_limit: Maximum wall-clock seconds allowed per test case.
        memory_limit_mb: Maximum resident-set-size in megabytes (0 = unlimited).
        test_cases: Ordered list of test cases to run.
        language: Programming language of the submission (e.g. ``"python"``).
        allow_partial_score: When ``True`` the judge computes a fractional score
            instead of requiring all test cases to pass.
    """

    time_limit: float = 5.0
    memory_limit_mb: int = 256
    test_cases: List[TestCase] = field(default_factory=list)
    language: str = "python"
    allow_partial_score: bool = True


@dataclass
class Guideline:
    """A named rule that a submission must satisfy.

    The ``check`` callable receives the raw source code (and optionally the
    combined stdout of all test-case runs) and returns ``(passed, message)``.

    Attributes:
        name: Short identifier for the rule (e.g. ``"no_globals"``).
        description: Human-readable explanation shown in feedback.
        check: ``(source_code: str) -> (passed: bool, message: str)``
        is_required: When ``True`` a violation immediately marks the verdict as
            :attr:`Verdict.GUIDELINE_VIOLATION` regardless of test results.
    """

    name: str
    description: str
    check: Callable[[str], tuple[bool, str]]
    is_required: bool = True


@dataclass
class GuidelineResult:
    """Outcome of evaluating one :class:`Guideline` against a submission."""

    guideline_name: str
    passed: bool
    message: str


@dataclass
class TestCaseResult:
    """Outcome of running one :class:`TestCase`."""

    test_case: TestCase
    actual_output: str
    passed: bool
    execution_time: float
    verdict: Verdict
    earned_fraction: float = 1.0
    error_message: Optional[str] = None


@dataclass
class JudgeResult:
    """Aggregated result returned by :class:`~judge.judge.Judge`.

    Attributes:
        verdict: Final verdict for the submission.
        score: Normalised score in *[0.0, 1.0]*.
        feedback: Single human-readable summary sentence.
        test_case_results: Per-test-case breakdown.
        guideline_results: Per-guideline breakdown.
        details: Arbitrary extra information (useful for debugging).
    """

    verdict: Verdict
    score: float
    feedback: str
    test_case_results: List[TestCaseResult] = field(default_factory=list)
    guideline_results: List[GuidelineResult] = field(default_factory=list)
    details: Any = None
