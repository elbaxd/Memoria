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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise(text: str) -> str:
        """Collapse all whitespace runs to single spaces and strip edges."""
        return re.sub(r"\s+", " ", text.strip())
