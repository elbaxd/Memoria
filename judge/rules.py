"""Built-in guidelines and a rule engine for evaluating source code.

Guidelines are simple predicates that inspect the *source text* of a
submission and return ``(passed: bool, message: str)``.

A handful of general-purpose guidelines are provided out of the box.
Domain-specific guidelines (e.g. for ERdoc ER-model code) can be added
by calling :func:`make_guideline` or by constructing :class:`~judge.models.Guideline`
objects directly and passing them to :class:`~judge.judge.Judge`.
"""

from __future__ import annotations

import re
from typing import Callable, List, Tuple

from .models import Guideline, GuidelineResult


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------


def make_guideline(
    name: str,
    description: str,
    check: Callable[[str], Tuple[bool, str]],
    is_required: bool = True,
) -> Guideline:
    """Convenience wrapper around :class:`~judge.models.Guideline`."""
    return Guideline(name=name, description=description, check=check, is_required=is_required)


# ---------------------------------------------------------------------------
# General-purpose built-in guidelines
# ---------------------------------------------------------------------------


def _check_no_empty_submission(source: str) -> Tuple[bool, str]:
    if source.strip():
        return True, ""
    return False, "Submission is empty."


def _check_line_length(max_length: int = 120) -> Callable[[str], Tuple[bool, str]]:
    def _check(source: str) -> Tuple[bool, str]:
        violations = [
            (i + 1, len(line))
            for i, line in enumerate(source.splitlines())
            if len(line) > max_length
        ]
        if not violations:
            return True, ""
        lines_str = ", ".join(f"line {ln} ({length} chars)" for ln, length in violations[:5])
        return False, f"Lines exceed {max_length} characters: {lines_str}"

    return _check


def _check_no_forbidden_keywords(forbidden: list[str]) -> Callable[[str], Tuple[bool, str]]:
    def _check(source: str) -> Tuple[bool, str]:
        found = [kw for kw in forbidden if re.search(r"\b" + re.escape(kw) + r"\b", source)]
        if not found:
            return True, ""
        return False, f"Forbidden keywords used: {found}"

    return _check


# ---------------------------------------------------------------------------
# ERdoc / ER-model specific guidelines
# ---------------------------------------------------------------------------


def _check_has_entity(source: str) -> Tuple[bool, str]:
    """At least one ``entity`` declaration must be present."""
    if re.search(r"\bentity\b", source, re.IGNORECASE):
        return True, ""
    return False, "No 'entity' declaration found in the ER model."


def _check_has_relationship(source: str) -> Tuple[bool, str]:
    """At least one ``relationship`` declaration must be present."""
    if re.search(r"\brelationship\b", source, re.IGNORECASE):
        return True, ""
    return False, "No 'relationship' declaration found in the ER model."


def _check_entity_has_key(source: str) -> Tuple[bool, str]:
    """Each entity block should declare at least one key attribute."""
    # Heuristic: find entity blocks and check for 'key' keyword inside them.
    entity_blocks = re.findall(
        r"entity\s+\w+\s*\{([^}]*)\}", source, re.IGNORECASE | re.DOTALL
    )
    if not entity_blocks:
        return True, ""  # no blocks to inspect — defer to other guidelines
    missing_key = []
    for i, block in enumerate(entity_blocks):
        if not re.search(r"\bkey\b", block, re.IGNORECASE):
            missing_key.append(i + 1)
    if not missing_key:
        return True, ""
    return False, f"Entity block(s) {missing_key} appear to lack a 'key' attribute."


def _check_no_duplicate_entity_names(source: str) -> Tuple[bool, str]:
    """Entity names must be unique within a model."""
    names = re.findall(r"\bentity\s+(\w+)", source, re.IGNORECASE)
    seen: set[str] = set()
    duplicates: list[str] = []
    for name in names:
        lower = name.lower()
        if lower in seen:
            duplicates.append(name)
        seen.add(lower)
    if not duplicates:
        return True, ""
    return False, f"Duplicate entity names: {duplicates}"


# ---------------------------------------------------------------------------
# Pre-built guideline collections
# ---------------------------------------------------------------------------

#: Minimal set of guidelines applied by default.
DEFAULT_GUIDELINES: List[Guideline] = [
    make_guideline(
        "non_empty",
        "Submission must not be empty.",
        _check_no_empty_submission,
        is_required=True,
    ),
    make_guideline(
        "line_length",
        "Lines must not exceed 120 characters.",
        _check_line_length(120),
        is_required=False,
    ),
]

#: ERdoc-specific guidelines for ER-model submissions.
ERDOC_GUIDELINES: List[Guideline] = DEFAULT_GUIDELINES + [
    make_guideline(
        "has_entity",
        "The model must declare at least one entity.",
        _check_has_entity,
        is_required=True,
    ),
    make_guideline(
        "has_relationship",
        "The model must declare at least one relationship.",
        _check_has_relationship,
        is_required=True,
    ),
    make_guideline(
        "entity_has_key",
        "Every entity must define a key attribute.",
        _check_entity_has_key,
        is_required=True,
    ),
    make_guideline(
        "no_duplicate_entities",
        "Entity names must be unique.",
        _check_no_duplicate_entity_names,
        is_required=True,
    ),
]


# ---------------------------------------------------------------------------
# Rule engine
# ---------------------------------------------------------------------------


class RuleEngine:
    """Evaluates a list of :class:`~judge.models.Guideline` objects against source code.

    Parameters
    ----------
    guidelines:
        The guidelines to apply.  Order matters only for reporting; all
        guidelines are always evaluated.
    """

    def __init__(self, guidelines: List[Guideline]) -> None:
        self.guidelines = guidelines

    def evaluate(self, source_code: str) -> List[GuidelineResult]:
        """Run every guideline against *source_code*.

        Returns
        -------
        List[GuidelineResult]
            One entry per guideline, in the same order as
            :attr:`guidelines`.
        """
        results: List[GuidelineResult] = []
        for guideline in self.guidelines:
            passed, message = guideline.check(source_code)
            results.append(
                GuidelineResult(
                    guideline_name=guideline.name,
                    passed=passed,
                    message=message,
                )
            )
        return results

    def has_required_violations(self, results: List[GuidelineResult]) -> bool:
        """Return ``True`` if any *required* guideline failed."""
        required_names = {g.name for g in self.guidelines if g.is_required}
        return any(
            not r.passed and r.guideline_name in required_names
            for r in results
        )
