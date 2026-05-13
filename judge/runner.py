"""Subprocess-based code runner with configurable time and memory limits."""

import resource
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class RunResult:
    """Raw output from a single execution.

    Attributes:
        stdout: Captured standard output (stripped).
        stderr: Captured standard error (stripped).
        execution_time: Wall-clock seconds consumed by the process.
        return_code: OS exit code of the child process.
        timed_out: ``True`` when the process was killed for exceeding the
            time limit.
    """

    stdout: str
    stderr: str
    execution_time: float
    return_code: int
    timed_out: bool = False


# Map language identifiers to the command used to execute a source file.
_LANGUAGE_COMMANDS: dict[str, list[str]] = {
    "python": [sys.executable],
    "python3": [sys.executable],
    "node": ["node"],
    "javascript": ["node"],
}


class CodeRunner:
    """Executes source code in an isolated subprocess.

    Parameters
    ----------
    language:
        One of the keys in :data:`_LANGUAGE_COMMANDS` (e.g. ``"python"``).
    time_limit:
        Maximum wall-clock seconds before the process is killed.
    memory_limit_mb:
        Maximum resident-set-size in megabytes.  Pass ``0`` to disable.
    """

    def __init__(
        self,
        language: str = "python",
        time_limit: float = 5.0,
        memory_limit_mb: int = 256,
    ) -> None:
        self.language = language.lower()
        self.time_limit = time_limit
        self.memory_limit_mb = memory_limit_mb

        if self.language not in _LANGUAGE_COMMANDS:
            raise ValueError(
                f"Unsupported language '{language}'. "
                f"Supported: {sorted(_LANGUAGE_COMMANDS)}"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, source_code: str, input_data: str = "") -> RunResult:
        """Write *source_code* to a temp file and execute it.

        Parameters
        ----------
        source_code:
            The full text of the program to run.
        input_data:
            Data piped to the program's standard input.

        Returns
        -------
        RunResult
        """
        suffix = self._file_suffix()
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=suffix,
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(source_code)
            tmp_path = Path(tmp.name)

        try:
            return self._execute(tmp_path, input_data)
        finally:
            tmp_path.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _file_suffix(self) -> str:
        suffixes = {
            "python": ".py",
            "python3": ".py",
            "node": ".js",
            "javascript": ".js",
        }
        return suffixes.get(self.language, ".txt")

    def _preexec(self) -> None:
        """Apply OS-level resource limits inside the child process.

        .. warning::
            ``preexec_fn`` is executed in the child process after ``fork()``
            and is **not thread-safe** — only the calling thread is
            duplicated, so locks held by other threads may never be released.
            ``CodeRunner`` must not be used from multi-threaded contexts while
            other threads hold locks (e.g. inside a ``ThreadPoolExecutor``).
            For multi-threaded use, prefer ``ProcessPoolExecutor`` or call
            :meth:`run` from the main thread only.
        """
        if self.memory_limit_mb > 0:
            limit_bytes = self.memory_limit_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))

    def _execute(self, script_path: Path, input_data: str) -> RunResult:
        cmd = _LANGUAGE_COMMANDS[self.language] + [str(script_path)]
        start = time.monotonic()
        timed_out = False

        try:
            proc = subprocess.run(
                cmd,
                input=input_data,
                capture_output=True,
                text=True,
                timeout=self.time_limit,
                preexec_fn=self._preexec,
            )
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            elapsed = time.monotonic() - start
            return RunResult(
                stdout=(exc.stdout or "").strip() if isinstance(exc.stdout, str) else "",
                stderr=(exc.stderr or "").strip() if isinstance(exc.stderr, str) else "",
                execution_time=elapsed,
                return_code=-1,
                timed_out=True,
            )

        elapsed = time.monotonic() - start
        return RunResult(
            stdout=proc.stdout.strip(),
            stderr=proc.stderr.strip(),
            execution_time=elapsed,
            return_code=proc.returncode,
            timed_out=timed_out,
        )
