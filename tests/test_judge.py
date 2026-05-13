"""Unit tests for the code judge package."""

import pytest

from judge import (
    DEFAULT_GUIDELINES,
    ERDOC_GUIDELINES,
    Judge,
    JudgeParameters,
    OutputChecker,
    RuleEngine,
    TestCase,
    Verdict,
    make_guideline,
)
from judge.runner import CodeRunner


# ---------------------------------------------------------------------------
# OutputChecker tests
# ---------------------------------------------------------------------------


class TestOutputChecker:
    def setup_method(self):
        self.checker = OutputChecker()

    def test_exact_match(self):
        passed, msg = self.checker.check_exact("hello", "hello")
        assert passed
        assert msg == ""

    def test_exact_whitespace_normalised(self):
        passed, _ = self.checker.check_exact("  hello  world\n", "hello world")
        assert passed

    def test_exact_mismatch(self):
        passed, msg = self.checker.check_exact("foo", "bar")
        assert not passed
        assert "foo" in msg or "bar" in msg

    def test_token_match(self):
        passed, _ = self.checker.check_token("1  2\n3", "1 2 3")
        assert passed

    def test_token_mismatch(self):
        passed, msg = self.checker.check_token("1 2 3", "1 2 4")
        assert not passed
        assert msg != ""

    def test_contains_match(self):
        passed, _ = self.checker.check_contains("line1\nline2\nline3", "line2")
        assert passed

    def test_contains_missing(self):
        passed, msg = self.checker.check_contains("only this", "missing line")
        assert not passed
        assert "missing line" in msg


# ---------------------------------------------------------------------------
# CodeRunner tests
# ---------------------------------------------------------------------------


class TestCodeRunner:
    def test_simple_python(self):
        runner = CodeRunner(language="python", time_limit=5.0)
        result = runner.run("print('hello')")
        assert result.stdout == "hello"
        assert result.return_code == 0
        assert not result.timed_out

    def test_stdin_forwarded(self):
        runner = CodeRunner(language="python", time_limit=5.0)
        result = runner.run("print(input())", input_data="world")
        assert result.stdout == "world"

    def test_runtime_error(self):
        runner = CodeRunner(language="python", time_limit=5.0)
        result = runner.run("raise ValueError('boom')")
        assert result.return_code != 0
        assert "boom" in result.stderr

    def test_time_limit_exceeded(self):
        runner = CodeRunner(language="python", time_limit=0.5)
        result = runner.run("import time; time.sleep(10)")
        assert result.timed_out

    def test_unsupported_language_raises(self):
        with pytest.raises(ValueError, match="Unsupported language"):
            CodeRunner(language="cobol")


# ---------------------------------------------------------------------------
# RuleEngine / guideline tests
# ---------------------------------------------------------------------------


class TestRuleEngine:
    def test_default_guidelines_pass_for_nonempty(self):
        engine = RuleEngine(DEFAULT_GUIDELINES)
        results = engine.evaluate("print('hello')")
        assert all(r.passed for r in results if r.guideline_name == "non_empty")

    def test_empty_submission_fails_required(self):
        engine = RuleEngine(DEFAULT_GUIDELINES)
        results = engine.evaluate("   ")
        assert engine.has_required_violations(results)
        non_empty_result = next(r for r in results if r.guideline_name == "non_empty")
        assert not non_empty_result.passed

    def test_make_guideline_custom(self):
        def _no_todos(source):
            if "TODO" in source:
                return False, "Remove TODO comments."
            return True, ""

        g = make_guideline("no_todos", "No TODO comments allowed.", _no_todos)
        engine = RuleEngine([g])
        results = engine.evaluate("x = 1  # TODO: fix this")
        assert not results[0].passed

    def test_erdoc_requires_entity(self):
        engine = RuleEngine(ERDOC_GUIDELINES)
        results = engine.evaluate("relationship R { ... }")
        assert engine.has_required_violations(results)

    def test_erdoc_requires_relationship(self):
        engine = RuleEngine(ERDOC_GUIDELINES)
        results = engine.evaluate("entity E { key id }")
        assert engine.has_required_violations(results)

    def test_erdoc_valid_minimal(self):
        engine = RuleEngine(ERDOC_GUIDELINES)
        source = "entity Person { key ssn }\nrelationship Knows { }"
        results = engine.evaluate(source)
        assert not engine.has_required_violations(results)

    def test_erdoc_duplicate_entities(self):
        engine = RuleEngine(ERDOC_GUIDELINES)
        source = (
            "entity Person { key ssn }\n"
            "entity Person { key id }\n"
            "relationship Knows { }"
        )
        results = engine.evaluate(source)
        dup_result = next(r for r in results if r.guideline_name == "no_duplicate_entities")
        assert not dup_result.passed


# ---------------------------------------------------------------------------
# Judge integration tests
# ---------------------------------------------------------------------------


class TestJudge:
    def _make_params(self, test_cases, time_limit=5.0, allow_partial=True):
        return JudgeParameters(
            test_cases=test_cases,
            time_limit=time_limit,
            allow_partial_score=allow_partial,
        )

    def test_correct_submission(self):
        params = self._make_params(
            [TestCase(input_data="3\n", expected_output="9")]
        )
        judge = Judge(parameters=params)
        result = judge.judge("n = int(input()); print(n ** 2)")
        assert result.verdict == Verdict.CORRECT
        assert result.score == pytest.approx(1.0)

    def test_wrong_answer(self):
        params = self._make_params(
            [TestCase(input_data="3\n", expected_output="9")]
        )
        judge = Judge(parameters=params)
        result = judge.judge("print(0)")
        assert result.verdict == Verdict.WRONG_ANSWER
        assert result.score == pytest.approx(0.0)

    def test_runtime_error_verdict(self):
        params = self._make_params(
            [TestCase(input_data="", expected_output="ok")]
        )
        judge = Judge(parameters=params)
        result = judge.judge("raise RuntimeError('oops')")
        assert result.verdict == Verdict.RUNTIME_ERROR

    def test_time_limit_exceeded_verdict(self):
        params = self._make_params(
            [TestCase(input_data="", expected_output="done")],
            time_limit=0.5,
        )
        judge = Judge(parameters=params)
        result = judge.judge("import time; time.sleep(10)")
        assert result.verdict == Verdict.TIME_LIMIT_EXCEEDED

    def test_partial_score(self):
        params = self._make_params(
            [
                TestCase(input_data="2\n", expected_output="4"),
                TestCase(input_data="3\n", expected_output="9"),
            ]
        )
        # Submission only handles input == 2
        judge = Judge(parameters=params)
        result = judge.judge("n = int(input()); print(4 if n == 2 else 0)")
        assert result.verdict == Verdict.PARTIAL
        assert 0.0 < result.score < 1.0

    def test_guideline_violation_short_circuits(self):
        params = self._make_params(
            [TestCase(input_data="", expected_output="")]
        )
        judge = Judge(parameters=params)
        result = judge.judge("")  # empty submission
        assert result.verdict == Verdict.GUIDELINE_VIOLATION
        assert result.score == pytest.approx(0.0)

    def test_no_test_cases_returns_correct(self):
        judge = Judge()
        result = judge.judge("x = 1")
        assert result.verdict == Verdict.CORRECT
        assert result.score == pytest.approx(1.0)

    def test_weighted_test_cases(self):
        params = self._make_params(
            [
                TestCase(input_data="1\n", expected_output="1", weight=1.0),
                TestCase(input_data="2\n", expected_output="4", weight=3.0),
            ]
        )
        # Only passes the first (weight=1), fails the second (weight=3)
        judge = Judge(parameters=params)
        result = judge.judge("n = int(input()); print(1)")
        assert result.score == pytest.approx(1.0 / 4.0)

    def test_token_check_strategy(self):
        params = self._make_params(
            [TestCase(input_data="", expected_output="1 2 3")]
        )
        judge = Judge(parameters=params, check_strategy="token")
        result = judge.judge("print('1  2  3')")
        assert result.verdict == Verdict.CORRECT

    def test_custom_guideline_integrated(self):
        def _no_print(source):
            if "print(" in source:
                return False, "Use sys.stdout instead of print()."
            return True, ""

        g = make_guideline("no_print", "Avoid built-in print().", _no_print, is_required=True)
        params = self._make_params(
            [TestCase(input_data="", expected_output="")]
        )
        judge = Judge(parameters=params, guidelines=[g])
        result = judge.judge("import sys; sys.stdout.write('hi')")
        assert result.verdict != Verdict.GUIDELINE_VIOLATION

        result_bad = judge.judge("print('hi')")
        assert result_bad.verdict == Verdict.GUIDELINE_VIOLATION
