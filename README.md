# Memoria

Memoria 2026 — Corrector automático de modelos Entidad-Relación con la herramienta ERdoc.

## Code Judge

The `judge/` package provides the base infrastructure for automatically
evaluating code submissions.  It can decide whether a submission is
**correct**, **partially correct**, or **incorrect** based on configurable
test cases and guidelines.

### Architecture

| Module | Responsibility |
|--------|---------------|
| `judge/models.py` | Data classes: `Verdict`, `TestCase`, `JudgeParameters`, `Guideline`, `JudgeResult` |
| `judge/runner.py` | `CodeRunner` — executes code in a subprocess with time/memory limits |
| `judge/checker.py` | `OutputChecker` — compares actual vs. expected output (exact / token / contains) |
| `judge/rules.py` | `RuleEngine` + built-in guidelines including ERdoc-specific rules |
| `judge/judge.py` | `Judge` — orchestrates the full evaluation pipeline |

### Quick start

```python
from judge import Judge, JudgeParameters, TestCase, Verdict

# Define test cases
params = JudgeParameters(
    test_cases=[
        TestCase(input_data="3\n", expected_output="9"),
        TestCase(input_data="4\n", expected_output="16"),
    ],
    time_limit=2.0,
    language="python",
)

# Create a judge and evaluate a submission
judge = Judge(parameters=params)
result = judge.judge("n = int(input()); print(n ** 2)")

print(result.verdict)   # Verdict.CORRECT
print(result.score)     # 1.0
print(result.feedback)  # "All test cases passed. Passed 2/2 test cases (100.0%)."
```

### Verdicts

| Verdict | Meaning |
|---------|---------|
| `CORRECT` | All test cases passed |
| `WRONG_ANSWER` | Output did not match expected |
| `PARTIAL` | Some test cases passed (when `allow_partial_score=True`) |
| `TIME_LIMIT_EXCEEDED` | Execution exceeded `time_limit` seconds |
| `RUNTIME_ERROR` | Submission crashed (non-zero exit code) |
| `GUIDELINE_VIOLATION` | A required guideline was violated |
| `ERROR` | Internal judge error |

### Guidelines

Guidelines are predicates over the raw source code.  Two ready-made
collections are exported:

- **`DEFAULT_GUIDELINES`** — non-empty submission, line-length check.
- **`ERDOC_GUIDELINES`** — extends the defaults with ER-model rules
  (requires at least one `entity` and one `relation`/`relationship`, unique entity names,
  key attributes present).

Custom guidelines can be added with `make_guideline()`:

```python
from judge import make_guideline, Judge, JudgeParameters

def no_globals(source):
    if "global " in source:
        return False, "Global variables are not allowed."
    return True, ""

g = make_guideline("no_globals", "Avoid global variables.", no_globals)
judge = Judge(parameters=JudgeParameters(), guidelines=[g])
```

### Running the tests

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```
