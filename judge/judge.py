"""Main Judge class — orchestrates running, checking, and guideline evaluation."""

from __future__ import annotations

from typing import List, Optional

from .checker import OutputChecker
from .models import (
    Guideline,
    JudgeParameters,
    JudgeResult,
    TestCaseResult,
    Verdict,
)
from .rules import DEFAULT_GUIDELINES, RuleEngine
from .runner import CodeRunner


class Judge:
    """Evaluate a code submission against test cases and guidelines.

    Usage example::

        from judge import Judge, JudgeParameters, TestCase

        params = JudgeParameters(
            test_cases=[TestCase(input_data="3\\n", expected_output="9")],
            time_limit=2.0,
        )
        judge = Judge(parameters=params)
        result = judge.judge("n = int(input()); print(n ** 2)")
        print(result.verdict, result.score)

    Parameters
    ----------
    parameters:
        Configuration for this judge instance (time/memory limits, test
        cases, language).
    guidelines:
        Ordered list of :class:`~judge.models.Guideline` objects.  When
        ``None`` the :data:`~judge.rules.DEFAULT_GUIDELINES` are used.
    check_strategy:
        One of ``"exact"`` (default), ``"token"``, or ``"contains"``.
        Controls how actual output is compared to expected output.
    """

    def __init__(
        self,
        parameters: Optional[JudgeParameters] = None,
        guidelines: Optional[List[Guideline]] = None,
        check_strategy: str = "exact",
    ) -> None:
        self.parameters = parameters or JudgeParameters()
        self.guidelines = guidelines if guidelines is not None else list(DEFAULT_GUIDELINES)
        self.check_strategy = check_strategy

        self._runner = CodeRunner(
            language=self.parameters.language,
            time_limit=self.parameters.time_limit,
            memory_limit_mb=self.parameters.memory_limit_mb,
        )
        self._checker = OutputChecker()
        self._rule_engine = RuleEngine(self.guidelines)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def judge(self, source_code: str) -> JudgeResult:
        """Evaluate *source_code* and return an aggregated :class:`~judge.models.JudgeResult`.

        The judging pipeline is:

        1. **Guideline check** — apply all guidelines to the raw source.
           Any *required* violation short-circuits to
           :attr:`~judge.models.Verdict.GUIDELINE_VIOLATION`.
        2. **Test execution** — run each test case in a subprocess.
        3. **Scoring** — compute a weighted score across test cases.
        4. **Verdict** — determine the final :class:`~judge.models.Verdict`.
        """
        # Step 1: guidelines
        guideline_results = self._rule_engine.evaluate(source_code)
        if self._rule_engine.has_required_violations(guideline_results):
            violations = [
                r.message for r in guideline_results if not r.passed
            ]
            return JudgeResult(
                verdict=Verdict.GUIDELINE_VIOLATION,
                score=0.0,
                feedback="; ".join(violations),
                guideline_results=guideline_results,
            )

        # Step 2: run test cases
        test_case_results: List[TestCaseResult] = []
        for tc in self.parameters.test_cases:
            run_result = self._runner.run(source_code, tc.input_data)
            tc_result = self._evaluate_run(tc, run_result)
            test_case_results.append(tc_result)

        # Step 3: score
        score = self._compute_score(test_case_results)

        # Step 4: verdict
        verdict = self._determine_verdict(test_case_results, score)
        feedback = self._build_feedback(verdict, score, test_case_results)

        return JudgeResult(
            verdict=verdict,
            score=score,
            feedback=feedback,
            test_case_results=test_case_results,
            guideline_results=guideline_results,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _evaluate_run(self, tc, run_result) -> TestCaseResult:
        from .models import TestCaseResult

        if run_result.timed_out:
            return TestCaseResult(
                test_case=tc,
                actual_output=run_result.stdout,
                passed=False,
                execution_time=run_result.execution_time,
                verdict=Verdict.TIME_LIMIT_EXCEEDED,
                error_message="Time limit exceeded.",
            )

        if run_result.return_code != 0:
            return TestCaseResult(
                test_case=tc,
                actual_output=run_result.stdout,
                passed=False,
                execution_time=run_result.execution_time,
                verdict=Verdict.RUNTIME_ERROR,
                error_message=run_result.stderr or f"Exit code {run_result.return_code}",
            )

        checker_fn = {
            "exact": self._checker.check_exact,
            "token": self._checker.check_token,
            "contains": self._checker.check_contains,
        }.get(self.check_strategy, self._checker.check_exact)

        passed, msg = checker_fn(run_result.stdout, tc.expected_output)
        return TestCaseResult(
            test_case=tc,
            actual_output=run_result.stdout,
            passed=passed,
            execution_time=run_result.execution_time,
            verdict=Verdict.CORRECT if passed else Verdict.WRONG_ANSWER,
            error_message=msg if not passed else None,
        )

    def _compute_score(self, results: List[TestCaseResult]) -> float:
        if not results:
            return 1.0  # no test cases → full score by convention
        total_weight = sum(r.test_case.weight for r in results)
        if total_weight == 0:
            return 0.0
        earned = sum(
            r.test_case.weight for r in results if r.passed
        )
        return earned / total_weight

    def _determine_verdict(
        self, results: List[TestCaseResult], score: float
    ) -> Verdict:
        if not results:
            return Verdict.CORRECT

        # Propagate the "worst" individual verdict.
        for bad_verdict in (
            Verdict.TIME_LIMIT_EXCEEDED,
            Verdict.RUNTIME_ERROR,
        ):
            if any(r.verdict == bad_verdict for r in results):
                return bad_verdict

        if score == 1.0:
            return Verdict.CORRECT
        if score == 0.0:
            return Verdict.WRONG_ANSWER
        if self.parameters.allow_partial_score:
            return Verdict.PARTIAL
        return Verdict.WRONG_ANSWER

    @staticmethod
    def _build_feedback(
        verdict: Verdict,
        score: float,
        results: List[TestCaseResult],
    ) -> str:
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        pct = f"{score * 100:.1f}%"
        base = f"Passed {passed}/{total} test cases ({pct})."

        if verdict == Verdict.CORRECT:
            return f"All test cases passed. {base}"
        if verdict == Verdict.TIME_LIMIT_EXCEEDED:
            return f"Time limit exceeded on one or more test cases. {base}"
        if verdict == Verdict.RUNTIME_ERROR:
            return f"Runtime error on one or more test cases. {base}"
        if verdict == Verdict.PARTIAL:
            return f"Partial solution. {base}"
        return f"Wrong answer. {base}"
