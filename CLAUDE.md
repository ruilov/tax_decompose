# CLAUDE.md

## 1. Project Overview 

This project translates filed federal/state tax returns and supporting documentation into a Python codebase that reproduces the return values for each year. Goals:
1. Clarify how taxes are calculated
2. Enable calculation of marginal tax rates
3. Spot differences between years

The repository is split into:
- `public/` for code, policies, and documentation that may be shared.
- `private/` for taxpayer-specific data and source documents.
All real filed returns and supporting PDFs live under `private/returns/`.

### Non-Goals
- Not tax advice or a filing product.
- No PDF-parsing pipeline as the primary source of truth; correctness comes from explicit inputs + code.
- Do not reorganize the user's original tax folders.

### Task Menu (Agent Capabilities)
The agent can work on the following task types:
- **Task A: PDF Reading & OCR Setup** — check installed PDF/OCR tools, request permission to install what’s missing, and document working tools. Use: “Set up PDF reading and OCR.”
- **Task B: Bootstrap Codebase** — create the core files and seed total tax inputs from PDFs. Use: “Start the code base” and specify the tax year and which PDFs contain total tax values.
- **Task C: Open Issues Summary** — summarize open inputs and unresolved issues. Use: “Summarize open issues and inputs” and optionally name the year.
- **Task D: Time-Boxed Decomposition Loop** — iterate backwards from totals under a time limit. Use: “Run a time‑boxed decomposition loop for X minutes” and name the starting total (federal/state).
- **Task E: Deduplicate Inputs** — consolidate repeated values into single tagged items. Use: “Deduplicate inputs” and optionally constrain to a file/year or a specific amount.
- **Task F: Input Verification Loop** — verify each input against its source and mark as checked. Use: “Verify inputs for X minutes” and confirm order (default: file order) plus any skip rules.
- **Task G: Marginal Rate Table** — compute numerical marginal tax rates per input or per tag, split by federal and each state. Use: “Generate marginal rate table” and specify year + mode (`input` or `tag`).

### Sensitivity
- Treat all tax information as sensitive.
- Never paste full returns or large document excerpts.
- Use placeholders or redacted values in examples unless the user explicitly provides real numbers.
- Never assume paths or invent filenames.
- Keep all taxpayer-specific values and source docs in `private/` only.
- Never copy `private/inputs_YYYY.json`, `private/expected_YYYY.json`, or anything under `private/returns/` into `public/`.
- Before publishing from `public/`, run a final file allowlist check and sensitive-content grep.

---

## 2. Project Structure

### Files
- `public/tax.py` — Year-agnostic calculation functions (federal + state in one file)
- `public/policy_YYYY.json` — Tax law parameters (rates, thresholds, etc.)
- `public/test_tax.py` — Year-agnostic test suite
- `public/marginal_tax_run.py` — Utility runner for marginal tables
- `public/CLAUDE.md` — This workflow/spec document
- `private/inputs_YYYY.json` — Factual input values from tax documents
- `private/expected_YYYY.json` — Filed values for test validation
- `private/returns/YYYY/` — Source PDF tax returns

### Testing Architecture (Current)
- `test_tax.py` is registry-driven: each expected path maps to one registered test function.
- `test_expected_values()` is the single orchestrator: it iterates all expected paths for each year in `YEARS` and fails if any expected path has no registered test.
- Compute checks are built into `tax.py` top-level compute functions via `set_compute_checks_mode(...)` + `_check_compute_line(...)`.
- In test mode, compute checks are enabled so intermediate lines are validated against `private/expected_YYYY.json` while totals are being computed.
- Keep tests for both top-level totals registered and active:
  - `federal.compute_total_tax`
  - `ny.compute_total_tax`

### Function Naming
Include jurisdiction + form + line (or worksheet output):
```
federal_1040_line_11_agi(...)
federal_sched1_line_08_other_income(...)
state_CA_form540_line_19_taxable_income(...)
```

### Starting a New Year
1. Create `private/inputs_YYYY.json`, `public/policy_YYYY.json`, `private/expected_YYYY.json`
2. Use the shared `tax.py` + `test_tax.py` (do not fork by year unless absolutely required)
3. Locate total tax (federal and NY state) for the new year and add them to `private/inputs_YYYY.json` as **derived** inputs
4. Add tags to those derived totals so tests can reference them (e.g., `form_1040_line_24_total_tax`, `ny_it201_line_62_total_taxes`)
5. Start implementing from the final output (total tax) backwards
6. Decompose using the existing code first; only introduce changes when required by new-year differences
7. Avoid branching on tax year; treat year-specific differences as input/policy data unless unavoidable

### File Templates

**tax.py:**
```python
from decimal import Decimal, ROUND_HALF_UP

def round_to_dollars(amount: Decimal) -> Decimal:
    """Round to nearest dollar using ROUND_HALF_UP."""
    return amount.quantize(Decimal('1'), rounding=ROUND_HALF_UP)

# Individual line calculation functions...

def compute_federal_total_tax(inputs: dict, policy: dict) -> Decimal:
    """Top-level function that computes federal total tax from all inputs."""
    ...

def compute_ny_total_tax(inputs: dict, policy: dict) -> Decimal:
    """Top-level function that computes NY total tax from all inputs."""
    ...

def compute_all_taxes(inputs: dict, policy: dict) -> dict:
    """Returns dict with 'federal', 'ny', and 'total' keys."""
    ...

def marginal_rate_table_by_input(inputs: dict, policy: dict, delta=Decimal('1000')) -> str:
    """Pipe-delimited marginal rate table with one row per input."""

def marginal_rate_table_by_tag(inputs: dict, policy: dict, delta=Decimal('1000')) -> str:
    """Pipe-delimited marginal rate table with one row per tag."""

def marginal_rate_table(inputs: dict, policy: dict, delta=Decimal('1000')) -> str:
    """Backward-compatible alias (currently by-tag)."""
    ...
```

**test_tax.py:**
```python
# Loader functions
def load_inputs(year): ...
def load_policy(year): ...
def load_expected(year): ...

# Helper functions
def verify_and_print(description, result, expected): ...
def extract_nested(data, path): ...
def create_test(description, func, prepare_args, expected_path): ...

# Declarative test definitions
test_federal_schedule_se_line_6 = create_test(...)

# Top-level test (driven by expected values)
def test_expected_values(): ...

if __name__ == '__main__':
    test_expected_values()
```

---

## 3. Data Files

For each tax year, maintain three separate JSON files with hard separation between facts, policy, and expected values. All monetary values in JSON must be strings (e.g., `"13375"`) to preserve exact decimal representation.

### `private/inputs_YYYY.json` (facts)
Contains only factual values from documents (W-2 boxes, 1099 totals, withholding, prior-year carryovers, filing status, etc.). No policy thresholds or bracket cutoffs. Only include non-zero values — omit lines that are zero. Calculated intermediate values may appear temporarily and be decomposed later.

**Structure: dictionary of sources**
Top-level is a dictionary keyed by source file path (or `UNKNOWN` / `DERIVED`). Each value is a flat list of items from that source. Each item is an object with:
- `Amount` (string): the value, always stored as a string
- `Explanation` (string): short human-readable purpose
- `Tags` (list of strings): **used by code** to select/aggregate inputs
- `Path` (string): **metadata only** describing where the number appears inside the source file

**Formatting rules:**
- Item key order must be: `Tags`, `Amount`, `Path`, `Explanation` (any extra fields like `Checked` go last).
- `Tags` must be rendered on a single line for compactness.
- Within each source list, sort items by descending absolute `Amount` (non-numeric amounts go last).

**Source traceability rules:**
- Use the source file path as the dictionary key when available.
- Use `UNKNOWN` only after a good-faith search.
- Use `DERIVED` for temporary balancing items and include the arithmetic in `Explanation`.
- `Path` is a human aid only; it should not be used in code.
- Make `Path` specific enough to re-find the value quickly (form/page/line or statement reference when available).
- Amount precision rule: store exact source precision by default; if a value must be rounded to match whole-dollar return lines and compute checks, store the rounded value and state the rounding choice in `Explanation`.
**Important:** The filed tax return PDF is **not** a valid source. If the only known origin is the return itself, keep the item under `DERIVED` with a clear placeholder explanation and the tag needed by code/tests.

**Deduplication rule (important):**
- If the same numeric amount is used for multiple purposes, **store it once** and attach multiple `Tags`.
- Code should rely on `Tags` for grouping and selection. Do not duplicate entries for different uses.
**Removal rule (very important):**
- Once an input is fully decomposed into upstream components and a function/test exists for the computed line, **remove that input from `DERIVED`**.
- Any input item with an empty `Tags` list is **unused** by code/tests and should be deleted unless it is temporarily required as a placeholder (in which case add the correct tag).
- Treat source replacement as one atomic task: add source-backed replacement(s) with the same tag(s), remove the corresponding `DERIVED` placeholder, then run the full test suite.

Example:
```json
{
  "returns/YYYY/K1s/partnership_k1_example.pdf": [
    {
      "Amount": "1301",
      "Explanation": "Ordinary dividends that are fully qualified; used for Schedule B line 6 and Form 1040 line 3a.",
      "Tags": ["schedule_b_ordinary_dividends", "form_1040_line_3a_qualified_dividends"],
      "Path": "Boxes 6a and 6b (Ordinary and Qualified dividends)"
    }
  ],
  "returns/YYYY/supporting_docs/w2_example.pdf": [
    {
      "Amount": "2873.36",
      "Explanation": "W-2 amount used for Form 1040 wages and Additional Medicare Tax wages.",
      "Tags": ["form_1040_line_1z_wages", "w2_box_5_medicare_wages"],
      "Path": "Box 1 and Box 5 (Wages and Medicare wages)"
    }
  ]
}
```

### `public/policy_YYYY.json` (tax law parameters)
Contains only year-specific tax law parameters: brackets, rates, standard deduction, credit parameters, phaseout thresholds, inflation-adjusted limits. No taxpayer-specific facts.

```json
{
  "year": 2024,
  "self_employment_tax": {
    "social_security_rate": "0.124",
    "medicare_rate": "0.029",
    "social_security_wage_base": "65865"
  }
}
```

### `private/expected_YYYY.json` (filed values for validation)
Contains actual filed values used for test validation. Only include values that have corresponding test functions.
Any metadata should be under keys prefixed with `_` (e.g., `_metadata`) and will be ignored by tests.

Expected-value sourcing rules:
- Values must come from filed return PDFs (and their attached statements/forms), not from computed outputs.
- Do not backfill expected values from `tax.py` or test results.
- If a return line is not yet sourced from documents, do not invent values; leave it out until sourced.

```json
{
  "year": 2024,
  "federal": {
    "schedule_se": {
      "line_6_total_se_earnings": "213",
      "line_10_social_security_portion": "1232",
      "line_12_self_employment_tax": "12342"
    },
    "form_1040": {
      "line_24_total_tax": "5765"
    }
  }
}
```

---

## 4. Implementation Rules

### Purity
Computation functions must be pure: no file I/O, no environment reads, no network, deterministic given `inputs` + `policy`. Keep loading code separate from compute code.

### Money and Rounding
- Use `Decimal` for all money. Never use floats for money. Parse from strings in JSON.
- Centralize rounding in `round_to_dollars(amount: Decimal) -> Decimal` using `ROUND_HALF_UP`.

### No Hard-Coded Parameters
Never hard-code numeric parameters (rates, thresholds, split rates, formula parameters) in function code. Always extract from the `policy` dict. Document which policy keys are used in each function's docstring `Dependencies` section.

### Docstrings
Write docstrings that include:
- Form/line reference
- Brief formula description
- Dependencies (including which policy keys are used)
- Any simplifying assumptions (e.g., zero inputs omitted)

### Simplicity
- Implement one return line / worksheet output per function.
- Compose via upstream function calls rather than duplicating formulas.
- Keep functions small and testable.
- Use type hints.
- When a line has many potential inputs but most are zero, simplify the function to only take the non-zero ones. If a future year has non-zero values, add the inputs back then.
- All tag-based input loading must go through `tag_total(...)`. Do not add alternate tag access helpers.
- Path loading for JSON files should be file-relative and respect the repo split:
  - `public/` for policy files
  - `private/` for inputs/expected

---

## 5. Function Patterns

### Signatures
Functions accept individual input values as `Decimal` plus the complete `policy: dict`. Functions extract specific policy values internally.

```python
def federal_schedule_se_line_10_social_security_tax(
    line_6_self_employment_earnings: Decimal,
    policy: dict,
) -> Decimal:
    """Calculate SS portion of SE tax.

    Dependencies:
    - policy['self_employment_tax']['social_security_wage_base']
    - policy['self_employment_tax']['social_security_rate']
    """
    ss_wage_base = Decimal(policy['self_employment_tax']['social_security_wage_base'])
    social_security_rate = Decimal(policy['self_employment_tax']['social_security_rate'])
    taxable_amount = min(line_6_self_employment_earnings, ss_wage_base)
    return round_to_dollars(taxable_amount * social_security_rate)
```

### Top-Level Compute Functions
Each year has one top-level compute function per jurisdiction:
- `compute_federal_total_tax(inputs, policy)` — returns Form 1040 line 24
- `compute_ny_total_tax(inputs, policy)` — returns IT-201 line 62

Each state compute function recomputes the federal intermediates it needs (e.g., line 9 total income, schedule 1 adjustments) from `inputs` rather than accepting them as parameters. This keeps each function self-contained.

A convenience wrapper `compute_all_taxes(inputs, policy)` calls all jurisdiction functions and returns a dict with `federal`, `ny` (or other state keys), and `total`.

### Marginal Tax Rate
Use numerical differentiation with two table modes:
1. `marginal_rate_table_by_input(inputs, policy, delta)` for one row per input item.
2. `marginal_rate_table_by_tag(inputs, policy, delta)` for one row per tag.

`marginal_rate_table(...)` remains as a backward-compatible alias.

By-input mode:
- Perturbs one input `Amount` by `+/- delta` (default $1000), recomputes taxes, reports central-difference marginals.

By-tag mode:
- One row per tag with columns: `Tag`, `Num Inputs`, `Sources+Paths`, `Amount`, `Marginal Federal`, state marginals, `Marginal Total`.
- Shock implementation must use a synthetic one-tag input row (`+delta` / `-delta`) so only the target tag total is perturbed.
- Do not distribute tag shocks across existing rows when rows carry multiple tags.

Marginal outputs are local derivatives at the current return point and can differ by year due to branch/regime changes (for example, Schedule D worksheet branches when net long-term gains are positive vs negative).

---

## 6. Test Patterns

### Philosophy
Tests are the contract: computed values must match the filed return. Add tests incrementally as functions are implemented. Always run the test suite after any code or data change unless the user says not to.

### Test Layers
1. **Anchor tests** (high value, implement early): AGI, taxable income, total tax, total payments, refund/amount owed, state equivalents
2. **Milestone tests** as the graph grows: wages, interest, dividends, capital gains, deductions, key credits
3. **Edge tests** for tricky rules: phaseouts, AMT, NIIT, state-specific quirks

### Factory Pattern
Tests use `create_test()` to eliminate boilerplate and register each test to an expected value path:

```python
def create_test(description, func, prepare_args, expected_path):
    def test_func():
        inputs = load_inputs()
        policy = load_policy()
        expected_values = load_expected()
        kwargs = prepare_args(inputs, policy)
        result = func(**kwargs)
        expected = Decimal(extract_nested(expected_values, expected_path))
        verify_and_print(description, result, expected)
        return result
    return test_func

test_federal_schedule_se_line_6 = create_test(
    description="Schedule SE Line 6 (Total SE Earnings)",
    func=federal_schedule_se_line_6_total_se_earnings,
    prepare_args=lambda inputs, policy: {
        'line_2_schedule_c_and_k1_profit': Decimal(inputs['federal']['schedule_se']['line_2_schedule_c_and_k1_profit']),
        'policy': policy,
    },
    expected_path="federal.schedule_se.line_6_total_se_earnings",
)
```

Tests can call other tests to get computed values for dependent calculations.

### Expected-Driven Runner
`test_expected_values()` loads each `private/expected_YYYY.json`, enumerates every expected value path, and runs the registered test for that path. Missing tests fail fast.
This ensures every expected value has a test and that all years in `YEARS` are exercised.
Both `pytest` and `python test_tax.py` should run through `test_expected_values()` only.

### Internal Compute Checks (Required)
- Keep compute-line assertions active in top-level compute functions:
  - `compute_federal_total_tax`
  - `compute_ny_total_tax`
- In tests, enable compute-check mode so intermediate lines are validated against expected values as the compute graph executes.
- This is required to prevent disconnects where individual line tests pass but top-level compute paths diverge.

### What Each Test Must Do
- Load inputs, policy, and expected values from JSON (no hardcoded values)
- Extract and convert input values to `Decimal`
- Pass the complete policy dict to functions
- Assert computed value matches expected value
- Return computed value for use by downstream tests
Notes:
- If a line is not yet decomposed for a year, you may temporarily source it from `private/inputs_YYYY.json` using a tag.
- Do not use skip-based test patterns for missing year data; expected-driven coverage should fail if a path is expected but untested.
- Tests should not hardcode year names or jurisdictions; they should operate on expected paths.

---

## 7. Workflow

### Task A: PDF Reading & OCR Setup
1. Check the system for installed PDF text extraction and OCR tools.
2. If tools are missing or insufficient, ask the user for permission to install specific tools.
3. When a tool works successfully and is not yet documented here, document it.

Known working tools:
- `pdftotext` (Poppler) for text-based PDFs
- `pdftoppm` and `pdfimages` (Poppler) for image extraction

### Task B: Bootstrap Codebase
1. Create `private/inputs_YYYY.json`, `public/policy_YYYY.json`, `private/expected_YYYY.json`
2. Ensure shared `tax.py` contains `round_to_dollars()` and top-level compute functions
3. Ensure `test_tax.py` has loader/helpers and `test_expected_values()`
4. Identify total tax items in the PDFs and add them as inputs

### Task C: Open Issues Summary
Summarize:
- inputs still marked `UNKNOWN` or `DERIVED`
- duplicate values not yet consolidated
- missing source documents needed to proceed

### Task D: Time-Boxed Decomposition Loop
When the user specifies a time limit for recursive decomposition:
1. Add the requested tasks explicitly. If none identified yet, start with total tax paid federal and for each state. If the inputs JSON already has partial work, summarize open inputs and issues first.
2. For each task, implement the calculation from upstream inputs. Run all tests when you finish a task, before starting a new task.
3. If intermediate inputs come directly from the return, add new tasks to decompose them.
4. Continue recursively until the time limit is reached or user input is needed.
5. Check the clock after each task and report timestamps.
6. Summarize what was completed and what remains.
7. After each loop, list all outstanding inputs and issues, including placeholders, derived values, and missing source documents.
Notes:
- Prefer itemized input lists grouped under each source key for multi-document totals.
- When a value must be derived as a placeholder, state the exact arithmetic used and call out the missing source document.

### Decomposition Tasks
There are 2 types of decomposition tasks
1) Remove an input X from DERIVED and add new inputs [Y] to DERIVED. This can be done when tax.py has a function to calculate X in terms of [Y]. The testing code may need to be modified to use tag_or_else.
2) Remove an input X from DERIVED and add inputs [Y] to various sources, where [Y] has the same tag as X. File names of the supporting sources may give you a clue as to where to search for the source of the input.

In each of these tasks, think about whether the input X should be added to expected_[YYYY].json. If a test already exists for it in test_tax.py then that's a major clue that you should add a test. 
Critical consistency rule:
- Never keep the same line as both:
  - an expected tested output in `private/expected_YYYY.json`, and
  - a return-placeholder input in `DERIVED` with the same semantic role.
- If a line is now computed and tested, remove its direct return-placeholder from `DERIVED`.
- Minimize formatting-only churn in `private/inputs_YYYY.json` edits. Prefer targeted edits (small patches) over full-file rewrites to avoid accidental style regressions.

### Task E: Deduplicate Inputs
- If the same amount is used for multiple purposes, keep **one** input item and attach multiple `Tags`.
- Update code to use `Tags` rather than duplicate inputs.

### Task F: Input Verification Loop
When verifying inputs against source documents:
1. Use the developer-provided time limit.
2. Process inputs in file order.
3. Skip items with `Source` of `UNKNOWN` or `DERIVED`.
4. Open the source document and confirm the `Amount` appears at the stated `Path`.
5. Verification fallback order: try text extraction first (`pdftotext`), then image rendering/OCR when needed (`pdftoppm`/`pdfimages` + OCR or visual confirmation).
6. Set `Checked` explicitly on each processed item:
   - `Checked: true` when the amount is confirmed in the stated source/path.
   - `Checked: false` when checked but not confirmed (including extraction/OCR failure after fallback).
7. In normal loop mode, if an item cannot be confirmed, skip to the next item unless the developer explicitly requested stop-on-fail behavior.

### Task G: Marginal Rate Table
Implemented in `tax.py` as:
- `marginal_rate_table_by_input(inputs, policy, delta)`
- `marginal_rate_table_by_tag(inputs, policy, delta)`
- `marginal_rate_table(inputs, policy, delta)` (alias)

To run via `marginal_tax_run.py`, set `year` and `mode` in that file (`mode = "input"` or `"tag"`), then execute:
- `python3 public/marginal_tax_run.py`

Direct usage:
```python
from tax import marginal_rate_table_by_input, marginal_rate_table_by_tag
print(marginal_rate_table_by_input(inputs, policy))
print(marginal_rate_table_by_tag(inputs, policy))
```
Output is pipe-delimited. Use a default delta of $1000 to overcome whole-dollar rounding in the tax functions.

### Implementing a New Line
1. Read the actual PDF form page to understand the real structure — never assume form structure without reading it
2. Identify: year, jurisdiction, form/line, expected filed value
3. Determine dependencies: upstream lines, which are facts (inputs) vs policy (config)
4. Start with the line's immediate inputs (even if they're aggregates)
5. Add only non-zero inputs to `private/inputs_YYYY.json`
6. Add the expected value to `private/expected_YYYY.json`
7. Add required policy parameters to `public/policy_YYYY.json`
8. Create the pure function
9. Create a test using `create_test()`
10. Run tests to verify
11. Later, decompose aggregate inputs into their components

When replacing a return-derived input with computed logic:
1. Remove the input from `private/inputs_YYYY.json`
2. Add the computed value to `private/expected_YYYY.json` if it will be tested
3. Add any required parameters to `public/policy_YYYY.json`
4. Add tests for the new lines before wiring them into downstream functions
5. Source expected values from return PDFs/statements, not from computed outputs

Repository hygiene rule:
- `public/` must remain safe to publish.
- Do not move or copy taxpayer-specific raw values, expected return values, or source PDFs into `public/`.

Example progression:
- First: `line_12 = line_10 + line_11` (with line_10 and line_11 as inputs)
- Later: Replace line_10 input with a function that calculates it from its own inputs
- Keep iterating backwards toward raw source document values

### Tracing Where Numbers Come From
Search for the actual number in the PDF. For example, if tracing where `line_2 = 238098` comes from, search the PDF for "238,098" or "238098". This often leads directly to the source statement or supporting schedule.

### Working with External Sources
When a return line references instructions/worksheets not in the local PDFs, use authoritative external sources (e.g., IRS instructions) to parameterize policy values. Prefer relative document references as strings (e.g., `"2019/Federal/Form1040.pdf p.2 line 11"`), not absolute paths.

## 8. Traceability

Every computed value should be explainable with a minimal structured record:

- `label`: e.g., `"Federal 1040 Line 11 (AGI)"`
- `year`
- `value`
- `formula`: short description
- `inputs_used`: list of (name, value)
- `depends_on`: list of upstream computed labels
- `sources`: list of document references (free-form strings)

Implement a lightweight `TraceNode` structure. Each function can optionally emit trace output via one of:
1. `value, trace = func(inputs, cfg, trace=True)`
2. `value = func(inputs, cfg, tracer=tracer_obj)`

Pick one pattern and use it consistently.
