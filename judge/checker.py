"""Output comparison strategies for the code judge."""

import re
from typing import Tuple


class OutputChecker:
    """Compares actual program output against expected output.

    Two built-in strategies are provided:

    * **exact** – whitespace-normalised character-by-character comparison.
    * **token** – splits both strings on whitespace and compares the
      resulting token sequences (order-sensitive).

    Additional strategies can be added by sub-classing or monkey-patching.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_exact(self, actual: str, expected: str) -> Tuple[bool, str]:
        """Return ``(True, "")`` when outputs match after whitespace normalisation.

        Parameters
        ----------
        actual:
            The output produced by the submission.
        expected:
            The reference output.

        Returns
        -------
        tuple[bool, str]
            ``(passed, message)`` where *message* is empty on success or
            contains a diff hint on failure.
        """
        norm_actual = self._normalise(actual)
        norm_expected = self._normalise(expected)
        if norm_actual == norm_expected:
            return True, ""
        return False, (
            f"Expected:\n{norm_expected}\n\nGot:\n{norm_actual}"
        )

    def check_token(self, actual: str, expected: str) -> Tuple[bool, str]:
        """Return ``(True, "")`` when token sequences match.

        Splitting on any whitespace makes this strategy insensitive to
        differences in spacing, tabs, or newlines between tokens.
        """
        actual_tokens = actual.split()
        expected_tokens = expected.split()
        if actual_tokens == expected_tokens:
            return True, ""
        return False, (
            f"Token mismatch.\nExpected tokens: {expected_tokens}\n"
            f"Got tokens:      {actual_tokens}"
        )

    def check_contains(self, actual: str, expected: str) -> Tuple[bool, str]:
        """Return ``(True, "")`` when every expected line appears in *actual*.

        Useful when the submission may print extra diagnostic lines.
        """
        expected_lines = [l.strip() for l in expected.splitlines() if l.strip()]
        actual_lower = actual.lower()
        missing = [
            line for line in expected_lines
            if line.lower() not in actual_lower
        ]
        if not missing:
            return True, ""
        return False, f"Missing expected lines: {missing}"

    def check_er_structural(self, actual: str, expected: str) -> Tuple[bool, str, float]:
        """Compare ER-model texts by structural counts, independent from names.

        Evaluates four dimensions:
        - entities
        - relationships (``relation`` or ``relationship``)
        - attributes
        - primary keys (``key``/``pkey``)

        Returns ``(passed, message, score)`` where *score* is in ``[0, 1]`` and
        uses weighted penalties by conceptual importance.
        """
        actual_m = self._extract_er_metrics(actual)
        expected_m = self._extract_er_metrics(expected)

        weights = {
            "entities": 0.35,
            "relationships": 0.30,
            "primary_keys": 0.25,
            "attributes": 0.10,
        }

        per_dim_score = {
            key: self._count_similarity(actual_m[key], expected_m[key])
            for key in weights
        }
        score = sum(weights[key] * per_dim_score[key] for key in weights)

        exact_match = all(actual_m[k] == expected_m[k] for k in weights)
        if exact_match:
            return True, "", 1.0

        return (
            False,
            (
                "ER structural mismatch. "
                f"Expected={expected_m}, Got={actual_m}, "
                f"weighted_score={score:.3f}"
            ),
            score,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise(text: str) -> str:
        """Collapse all whitespace runs to single spaces and strip edges."""
        return re.sub(r"\s+", " ", text.strip())

    @staticmethod
    def _count_similarity(actual_count: int, expected_count: int) -> float:
        if expected_count == 0:
            return 1.0 if actual_count == 0 else 0.0
        gap = abs(actual_count - expected_count) / expected_count
        return max(0.0, 1.0 - gap)

    def _extract_er_metrics(self, text: str) -> dict[str, int]:
        clean = self._strip_comments(text)
        entity_blocks = re.findall(
            r"\bentity\s+\w+(?:\s+(?:extends|depends\s+on)\s+\w+)?\s*\{(.*?)\}",
            clean,
            re.IGNORECASE | re.DOTALL,
        )
        relationship_blocks = re.findall(
            r"\b(?:relation|relationship)\s+\w+\s*\([^)]*\)\s*\{(.*?)\}",
            clean,
            re.IGNORECASE | re.DOTALL,
        )
        entity_count = len(
            re.findall(
                r"^\s*entity\s+\w+(?:\s+(?:extends|depends\s+on)\s+\w+)?\s*\{",
                clean,
                re.IGNORECASE | re.MULTILINE,
            )
        )
        relationship_count = len(
            re.findall(
                r"^\s*(?:relation|relationship)\s+\w+\s*\(",
                clean,
                re.IGNORECASE | re.MULTILINE,
            )
        )

        all_attribute_lines = []
        for block in entity_blocks + relationship_blocks:
            for raw_line in block.splitlines():
                line = raw_line.strip()
                if line:
                    all_attribute_lines.append(line)

        primary_keys = sum(
            1 for line in all_attribute_lines if re.search(r"\b(?:key|pkey)\b", line, re.IGNORECASE)
        )

        return {
            "entities": entity_count,
            "relationships": relationship_count,
            "attributes": len(all_attribute_lines),
            "primary_keys": primary_keys,
        }

    @staticmethod
    def _strip_comments(text: str) -> str:
        cleaned_lines = []
        for line in text.splitlines():
            line = re.sub(r"//.*$", "", line)
            line = re.sub(r"#.*$", "", line)
            cleaned_lines.append(line)
        return "\n".join(cleaned_lines)
