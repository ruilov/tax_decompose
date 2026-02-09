"""
Federal Form 1040 calculations for tax year 2024.

This module implements pure functions to compute line items from Form 1040.
"""

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

_COMPUTE_CHECKS_ENABLED = False
_COMPUTE_CHECKS_EXPECTED: dict | None = None
_COMPUTE_CHECKS_CONTEXT: str | None = None


def round_to_dollars(amount: Decimal) -> Decimal:
    """
    Round a Decimal amount to the nearest dollar.

    Uses ROUND_HALF_UP (standard rounding: 0.5 rounds up).

    Args:
        amount: The amount to round

    Returns:
        Amount rounded to nearest dollar
    """
    return amount.quantize(Decimal('1'), rounding=ROUND_HALF_UP)


def build_inputs_index(inputs: dict | list[dict]) -> dict:
    """
    Build lookup indexes for inputs grouped by source.

    Inputs may be either:
    - dict[str, list[dict]] keyed by source, or
    - flat list[dict] (legacy)

    Returns:
        dict with keys: by_tag
    """
    by_tag: dict[str, list[dict]] = defaultdict(list)
    if isinstance(inputs, dict):
        items_iter = (item for items in inputs.values() for item in items)
    else:
        items_iter = iter(inputs)
    for item in items_iter:
        for tag in item.get('Tags', []):
            by_tag[tag].append(item)
    return {'by_tag': by_tag}


def tag_total(
    index: dict,
    tag: str,
    required: bool = False,
    round_each: bool = False,
) -> Decimal:
    items = list(index['by_tag'].get(tag, []))
    if required and not items:
        raise ValueError(f"Expected at least 1 item for tag '{tag}', found 0")
    if round_each:
        return sum(
            (round_to_dollars(Decimal(item['Amount'])) for item in items),
            Decimal('0'),
        )
    return sum((Decimal(item['Amount']) for item in items), Decimal('0'))


def set_compute_checks_mode(
    enabled: bool,
    expected_values: dict | None = None,
    context: str | None = None,
) -> None:
    """
    Toggle internal compute-line checks against expected values.

    When enabled, compute_federal_total_tax() and compute_ny_total_tax()
    validate selected intermediate lines against expected json values.
    """
    global _COMPUTE_CHECKS_ENABLED
    global _COMPUTE_CHECKS_EXPECTED
    global _COMPUTE_CHECKS_CONTEXT
    _COMPUTE_CHECKS_ENABLED = enabled
    _COMPUTE_CHECKS_EXPECTED = expected_values if enabled else None
    _COMPUTE_CHECKS_CONTEXT = context if enabled else None


def _expected_decimal_for_path(path: str) -> Decimal | None:
    if not _COMPUTE_CHECKS_ENABLED or _COMPUTE_CHECKS_EXPECTED is None:
        return None

    node = _COMPUTE_CHECKS_EXPECTED
    for key in path.split('.'):
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    try:
        return Decimal(str(node))
    except Exception:
        return None


def _check_compute_line(path: str, actual: Decimal) -> None:
    expected = _expected_decimal_for_path(path)
    if expected is None:
        return
    if actual != expected:
        prefix = f"[{_COMPUTE_CHECKS_CONTEXT}] " if _COMPUTE_CHECKS_CONTEXT else ""
        raise AssertionError(f"{prefix}{path}: expected {expected}, got {actual}")


def federal_schedule_se_line_2_schedule_c_and_k1_profit(
    k1_box_14a_self_employment_earnings: Decimal,
    k1_box_12_section_179_deduction: Decimal,
) -> Decimal:
    """
    Calculate net SE income from K-1 partnerships (Schedule SE, line 2).

    Form/Line: Schedule SE (Form 1040), Part I, line 2
    Formula: K-1 Box 14A (SE earnings) - K-1 Box 12 (Section 179 deduction)

    This is a simplified calculation for a single K-1 source.
    Section 179 deductions reduce self-employment income for SE tax purposes.

    Source documents:
    - K-1 Box 14A and Box 12 from a partnership Schedule K-1 source file

    Args:
        k1_box_14a_self_employment_earnings: Self-employment earnings from K-1 Box 14A
        k1_box_12_section_179_deduction: Section 179 deduction from K-1 Box 12

    Returns:
        Net self-employment income for Schedule SE line 2
    """
    return k1_box_14a_self_employment_earnings - k1_box_12_section_179_deduction


def federal_schedule_se_line_6_total_se_earnings(
    line_2_schedule_c_and_k1_profit: Decimal,
    policy: dict,
) -> Decimal:
    """
    Calculate total SE earnings (Schedule SE, line 6).

    Form/Line: Schedule SE (Form 1040), Part I, line 6
    Formula: line 2 × 0.9235 (simplified when lines 1a, 1b, 4b, 5b are zero)

    This is a simplified calculation that assumes:
    - Line 1a (farm profit) = 0
    - Line 1b (farm payments) = 0
    - Line 4b (other SE income) = 0
    - Line 5b (church employee income) = 0

    The full calculation would be:
    - Line 3 = 1a + 1b + 2
    - Line 4a = Line 3 × 0.9235
    - Line 4c = 4a + 4b
    - Line 6 = 4c + 5b

    Dependencies:
    - line_2_schedule_c_and_k1_profit: Net profit from Schedule C and K-1
    - policy['self_employment_tax']['earnings_factor']: SE earnings factor (0.9235)

    Args:
        line_2_schedule_c_and_k1_profit: Schedule C and K-1 profit
        policy: Policy configuration dict

    Returns:
        Total self-employment earnings subject to SE tax
    """
    earnings_factor = Decimal(policy['self_employment_tax']['earnings_factor'])
    if line_2_schedule_c_and_k1_profit > 0:
        earnings = line_2_schedule_c_and_k1_profit * earnings_factor
        return round_to_dollars(earnings)
    return line_2_schedule_c_and_k1_profit


def federal_schedule_se_line_10_social_security_tax(
    line_6_self_employment_earnings: Decimal,
    policy: dict,
) -> Decimal:
    """
    Calculate Social Security portion of self-employment tax (Schedule SE, line 10).

    Form/Line: Schedule SE (Form 1040), line 10
    Formula: min(line 6, SS wage base) × SS rate, rounded to nearest dollar

    This is a simplified calculation that assumes line 8d (W-2 SS wages) = 0,
    so line 9 = SS wage base directly.

    Dependencies:
    - line_6_self_employment_earnings: Total SE earnings subject to SE tax
    - policy['self_employment_tax']['social_security_wage_base']: SS wage base
    - policy['self_employment_tax']['social_security_rate']: SS tax rate

    Args:
        line_6_self_employment_earnings: Self-employment earnings from line 6
        policy: Policy configuration dict

    Returns:
        Social Security tax on self-employment income
    """
    ss_wage_base = Decimal(policy['self_employment_tax']['social_security_wage_base'])
    social_security_rate = Decimal(policy['self_employment_tax']['social_security_rate'])
    taxable_amount = min(line_6_self_employment_earnings, ss_wage_base)
    tax = taxable_amount * social_security_rate
    return round_to_dollars(tax)


def federal_schedule_se_line_11_medicare_tax(
    line_6_self_employment_earnings: Decimal,
    policy: dict,
) -> Decimal:
    """
    Calculate Medicare portion of self-employment tax (Schedule SE, line 11).

    Form/Line: Schedule SE (Form 1040), line 11
    Formula: line 6 × Medicare rate (2.9%), rounded to nearest dollar

    Unlike Social Security, Medicare has no wage base cap - all SE earnings
    are subject to Medicare tax.

    Dependencies:
    - line_6_self_employment_earnings: Total SE earnings from line 6
    - policy['self_employment_tax']['medicare_rate']: Medicare tax rate (0.029)

    Args:
        line_6_self_employment_earnings: Self-employment earnings from line 6
        policy: Policy configuration dict

    Returns:
        Medicare tax on self-employment income
    """
    medicare_rate = Decimal(policy['self_employment_tax']['medicare_rate'])
    tax = line_6_self_employment_earnings * medicare_rate
    return round_to_dollars(tax)


def federal_schedule_se_line_12_self_employment_tax(
    line_10_social_security_portion: Decimal,
    line_11_medicare_portion: Decimal,
) -> Decimal:
    """
    Calculate total self-employment tax (Schedule SE, line 12).

    Form/Line: Schedule SE (Form 1040), line 12
    Formula: line 10 + line 11

    Dependencies:
    - line_10_social_security_portion: SS tax (12.4% on earnings subject to SS tax)
    - line_11_medicare_portion: Medicare tax (2.9% on all SE earnings)

    Args:
        line_10_social_security_portion: Social security portion of SE tax
        line_11_medicare_portion: Medicare portion of SE tax

    Returns:
        Total self-employment tax
    """
    return line_10_social_security_portion + line_11_medicare_portion


def federal_form_8959_line_18_additional_medicare_tax(
    w2_medicare_wages: Decimal,
    schedule_se_line_6_se_earnings: Decimal,
    policy: dict,
) -> Decimal:
    """
    Calculate Additional Medicare Tax (Form 8959, line 18).

    Form/Line: Form 8959, line 18
    Formula: Sum of Additional Medicare Tax on:
    - Part I (W-2 wages over threshold) - lines 1-7
    - Part II (SE income over remaining threshold) - lines 8-13
    - Part III (RRTA compensation) - lines 14-17 (assumed 0)

    The threshold is shared across all income types. W-2 wages are considered
    first, then SE income uses the remaining threshold.

    For MFJ with W-2 wages below threshold:
    - Line 6 (W-2 wages over threshold) = 0
    - Line 7 (Part I tax) = 0
    - Line 11 (remaining threshold) = threshold - W-2 wages
    - Line 12 (SE income over remaining threshold) = max(0, SE earnings - line 11)
    - Line 13 (Part II tax) = line 12 × 0.9%

    Dependencies:
    - w2_medicare_wages: Total Medicare wages from W-2 box 5 (all W-2s)
    - schedule_se_line_6_se_earnings: SE earnings from Schedule SE line 6
    - policy['additional_medicare_tax']['rate']: 0.9%
    - policy['additional_medicare_tax']['threshold']: $250,000

    Args:
        w2_medicare_wages: Total Medicare wages from W-2 box 5 (all W-2s)
        schedule_se_line_6_se_earnings: SE earnings from Schedule SE line 6
        policy: Policy configuration dict

    Returns:
        Total Additional Medicare Tax
    """
    amt_policy = policy['additional_medicare_tax']
    rate = Decimal(amt_policy['rate'])

    threshold = Decimal(amt_policy['threshold'])

    # Part I: Additional Medicare Tax on W-2 wages (lines 1-7)
    w2_over_threshold = max(Decimal('0'), w2_medicare_wages - threshold)
    part1_tax = round_to_dollars(w2_over_threshold * rate)

    # Part II: Additional Medicare Tax on SE income (lines 8-13)
    # Remaining threshold after W-2 wages
    remaining_threshold = max(Decimal('0'), threshold - w2_medicare_wages)
    se_over_threshold = max(Decimal('0'), schedule_se_line_6_se_earnings - remaining_threshold)
    part2_tax = round_to_dollars(se_over_threshold * rate)

    # Part III: RRTA compensation (assumed 0)
    part3_tax = Decimal('0')

    # Line 18: Total Additional Medicare Tax
    return part1_tax + part2_tax + part3_tax


def federal_form_8960_line_12_net_investment_income(
    line_8_total_investment_income: Decimal,
    line_11_total_deductions_and_modifications: Decimal = Decimal('0'),
) -> Decimal:
    """
    Calculate net investment income (Form 8960, line 12).

    Form/Line: Form 8960, line 12
    Formula: line 8 - line 11

    This is a simplified calculation that assumes:
    - Line 11 (total deductions and modifications) = 0

    Dependencies:
    - line_8_total_investment_income: Form 8960 line 8
    - line_11_total_deductions_and_modifications: Form 8960 line 11 (assumed 0)

    Args:
        line_8_total_investment_income: Total investment income
        line_11_total_deductions_and_modifications: Total deductions/modifications

    Returns:
        Net investment income (line 12)
    """
    return line_8_total_investment_income - line_11_total_deductions_and_modifications


def federal_form_8960_line_9a_investment_interest_expense(
    index: dict,
) -> Decimal:
    """
    Calculate Form 8960 line 9a investment interest expense.

    Form/Line: Form 8960, line 9a
    Formula: Sum of investment interest expense items, rounded to nearest dollar

    Dependencies:
    - investment_interest_expense_items: Investment interest expense amounts

    Args:
        investment_interest_expense_items: List of investment interest expense amounts

    Returns:
        Total investment interest expense (line 9a)
    """
    total = tag_total(index, 'form_8960_line_9a_investment_interest_expense')
    return round_to_dollars(total)


def federal_form_8960_line_9c_misc_investment_expenses(
    index: dict,
) -> Decimal:
    """
    Calculate Form 8960 line 9c miscellaneous investment expenses.

    Form/Line: Form 8960, line 9c
    Formula: Sum of misc investment expense items, rounded to nearest dollar

    Dependencies:
    - misc_investment_expense_items: Misc investment expense amounts

    Args:
        misc_investment_expense_items: List of misc investment expense amounts

    Returns:
        Total miscellaneous investment expenses (line 9c)
    """
    total = tag_total(index, 'form_8960_line_9c_misc_investment_expenses')
    return round_to_dollars(total)


def federal_form_8960_line_9b_state_local_foreign_income_tax(
    index: dict,
    policy: dict,
) -> Decimal:
    """
    Calculate Form 8960 line 9b state, local, and foreign income tax.

    Form/Line: Form 8960, line 9b
    Formula: min(sum(state/local/foreign taxes), SALT cap), rounded to nearest dollar

    Dependencies:
    - state_local_foreign_tax_items: State/local/foreign income tax payments
    - policy['state_local_tax_deduction']: SALT cap values

    Args:
        state_local_foreign_tax_items: List of tax payment amounts
        policy: Policy configuration dict

    Returns:
        Capped state/local/foreign income tax amount (line 9b)
    """
    total = tag_total(index, 'form_8960_line_9b_state_local_foreign_income_tax')
    cap_policy = policy['state_local_tax_deduction']
    cap = Decimal(cap_policy['cap'])
    return round_to_dollars(min(total, cap))


def federal_form_8960_line_9d_total_investment_expenses(
    line_9a_investment_interest_expense: Decimal,
    line_9b_state_local_foreign_income_tax: Decimal,
    line_9c_misc_investment_expenses: Decimal,
) -> Decimal:
    """
    Calculate Form 8960 line 9d total investment expenses.

    Form/Line: Form 8960, line 9d
    Formula: line 9a + line 9b + line 9c

    Args:
        line_9a_investment_interest_expense: Line 9a amount
        line_9b_state_local_foreign_income_tax: Line 9b amount
        line_9c_misc_investment_expenses: Line 9c amount

    Returns:
        Total investment expenses (line 9d)
    """
    return (
        line_9a_investment_interest_expense +
        line_9b_state_local_foreign_income_tax +
        line_9c_misc_investment_expenses
    )


def federal_form_8960_line_11_total_deductions_and_modifications(
    line_9d_total_investment_expenses: Decimal,
    line_10_additional_modifications: Decimal = Decimal('0'),
) -> Decimal:
    """
    Calculate Form 8960 line 11 total deductions and modifications.

    Form/Line: Form 8960, line 11
    Formula: line 9d + line 10

    Args:
        line_9d_total_investment_expenses: Line 9d amount
        line_10_additional_modifications: Line 10 amount (default 0)

    Returns:
        Total deductions and modifications (line 11)
    """
    return line_9d_total_investment_expenses + line_10_additional_modifications


def federal_schedule_b_line_1_taxable_interest(
    index: dict,
) -> Decimal:
    """
    Calculate total taxable interest (Schedule B, line 1).

    Form/Line: Schedule B (Form 1040), line 1
    Formula: Sum of interest income items, rounded to nearest dollar

    Dependencies:
    - interest_income_items: Interest income amounts from statements and K-1s

    Args:
        interest_income_items: List of interest income amounts

    Returns:
        Total taxable interest (Schedule B, line 1)
    """
    total = tag_total(index, 'schedule_b_interest')
    return round_to_dollars(total)


def federal_schedule_b_line_6_ordinary_dividends(
    index: dict,
) -> Decimal:
    """
    Calculate total ordinary dividends (Schedule B, line 6).

    Form/Line: Schedule B (Form 1040), line 6
    Formula: Sum of ordinary dividend items, rounded to nearest dollar

    Dependencies:
    - ordinary_dividend_items: Ordinary dividend amounts from statements and K-1s

    Args:
        ordinary_dividend_items: List of ordinary dividend amounts

    Returns:
        Total ordinary dividends (Schedule B, line 6)
    """
    total = tag_total(index, 'schedule_b_ordinary_dividends')
    return round_to_dollars(total)


def federal_schedule_e_line_29a_total_nonpassive_income(
    index: dict,
) -> Decimal:
    """
    Calculate Schedule E line 29a total nonpassive income.

    Form/Line: Schedule E (Form 1040), line 29a, column (k)
    Formula: Sum of nonpassive income items, rounded to nearest dollar

    Dependencies:
    - nonpassive_income_items: Nonpassive income amounts from Schedule K-1s

    Args:
        nonpassive_income_items: List of nonpassive income amounts

    Returns:
        Total nonpassive income (line 29a, column k)
    """
    total = (
        tag_total(index, 'schedule_e_nonpassive_income')
        + schedule_e_nonpassive_income_from_k1_components(index)
    )
    return round_to_dollars(total)


def schedule_e_nonpassive_income_from_k1_components(
    index: dict,
) -> Decimal:
    """
    Compute Schedule E nonpassive income from K-1 components.

    Formula: sum(ordinary business income) + sum(guaranteed payments)

    Dependencies:
    - ordinary_income_items: K-1 ordinary business income (e.g., Box 1)
    - guaranteed_payments_items: K-1 guaranteed payments (e.g., Box 4a)

    Args:
        ordinary_income_items: List of ordinary business income amounts
        guaranteed_payments_items: List of guaranteed payment amounts

    Returns:
        Derived nonpassive income amount to feed Schedule E line 29a
    """
    total_ordinary = tag_total(index, 'mctmt_base_ordinary_income')
    total_guaranteed = tag_total(index, 'mctmt_base_guaranteed_payments')
    return total_ordinary + total_guaranteed


def federal_schedule_e_line_29b_total_nonpassive_loss_allowed(
    index: dict,
) -> Decimal:
    """
    Calculate Schedule E line 29b total nonpassive loss allowed.

    Form/Line: Schedule E (Form 1040), line 29b, column (i)
    Formula: Sum of nonpassive loss allowed items, rounded to nearest dollar

    Dependencies:
    - nonpassive_loss_allowed_items: Nonpassive loss allowed amounts from statements/K-1s

    Args:
        nonpassive_loss_allowed_items: List of nonpassive loss allowed amounts

    Returns:
        Total nonpassive loss allowed (line 29b, column i)
    """
    total = tag_total(index, 'schedule_e_line_29b_nonpassive_loss_allowed')
    return round_to_dollars(total)


def federal_schedule_e_line_29b_total_section_179_deduction(
    index: dict,
) -> Decimal:
    """
    Calculate Schedule E line 29b total section 179 deduction.

    Form/Line: Schedule E (Form 1040), line 29b, column (j)
    Formula: Sum of section 179 deduction items, rounded to nearest dollar

    Dependencies:
    - section_179_deduction_items: Section 179 deduction amounts from Schedule K-1s

    Args:
        section_179_deduction_items: List of section 179 deduction amounts

    Returns:
        Total section 179 deduction (line 29b, column j)
    """
    total = tag_total(index, 'section_179_deduction')
    return round_to_dollars(total)


def federal_schedule_e_line_30_total_income(
    line_29a_nonpassive_income: Decimal,
) -> Decimal:
    """
    Calculate Schedule E line 30 total income.

    Form/Line: Schedule E (Form 1040), line 30
    Formula: line 29a column (k)

    Dependencies:
    - line_29a_nonpassive_income: Schedule E line 29a column (k)

    Args:
        line_29a_nonpassive_income: Total nonpassive income

    Returns:
        Total income (line 30)
    """
    return round_to_dollars(line_29a_nonpassive_income)


def federal_schedule_e_line_31_total_losses(
    line_29b_nonpassive_loss_allowed: Decimal,
    line_29b_section_179_deduction: Decimal = Decimal('0'),
) -> Decimal:
    """
    Calculate Schedule E line 31 total losses/deductions.

    Form/Line: Schedule E (Form 1040), line 31
    Formula: -(line 29b columns (i) + (j))

    Dependencies:
    - line_29b_nonpassive_loss_allowed: Schedule E line 29b column (i)
    - line_29b_section_179_deduction: Schedule E line 29b column (j)

    Args:
        line_29b_nonpassive_loss_allowed: Total nonpassive loss allowed
        line_29b_section_179_deduction: Total section 179 deduction

    Returns:
        Total losses/deductions as a negative amount (line 31)
    """
    total = (
        line_29b_nonpassive_loss_allowed +
        line_29b_section_179_deduction
    )
    return -round_to_dollars(total)


def federal_schedule_e_line_32_total_partnership_income(
    line_30_total_income: Decimal,
    line_31_total_losses: Decimal,
) -> Decimal:
    """
    Calculate Schedule E line 32 total partnership income.

    Form/Line: Schedule E (Form 1040), line 32
    Formula: line 30 + line 31

    Dependencies:
    - line_30_total_income: Schedule E line 30
    - line_31_total_losses: Schedule E line 31 (negative)

    Args:
        line_30_total_income: Total income from line 30
        line_31_total_losses: Total losses/deductions from line 31

    Returns:
        Total partnership income (line 32)
    """
    return line_30_total_income + line_31_total_losses


def federal_schedule_1_line_5_rental_real_estate_income(
    schedule_e_line_32_total_partnership_income: Decimal,
) -> Decimal:
    """
    Calculate Schedule 1 line 5 rental real estate and partnership income.

    Form/Line: Schedule 1 (Form 1040), line 5
    Formula: Schedule E line 32

    Dependencies:
    - schedule_e_line_32_total_partnership_income: Schedule E line 32

    Args:
        schedule_e_line_32_total_partnership_income: Schedule E line 32 total

    Returns:
        Schedule 1 line 5 amount
    """
    return schedule_e_line_32_total_partnership_income


def federal_schedule_1_line_10_additional_income(
    line_5_rental_real_estate_income: Decimal,
    other_additional_income: Decimal = Decimal('0'),
) -> Decimal:
    """
    Calculate Schedule 1 line 10 additional income.

    Form/Line: Schedule 1 (Form 1040), line 10
    Formula: line 5 + other additional income items

    This is a simplified calculation that assumes:
    - Other additional income items are zero

    Dependencies:
    - line_5_rental_real_estate_income: Schedule 1 line 5

    Args:
        line_5_rental_real_estate_income: Schedule 1 line 5 amount
        other_additional_income: Other additional income items (assumed 0)

    Returns:
        Schedule 1 line 10 amount
    """
    total = line_5_rental_real_estate_income + other_additional_income
    return round_to_dollars(total)


def federal_schedule_1_line_15_deductible_self_employment_tax(
    schedule_se_line_12_self_employment_tax: Decimal,
) -> Decimal:
    """
    Calculate Schedule 1 line 15 deductible part of self-employment tax.

    Form/Line: Schedule 1 (Form 1040), line 15
    Formula: 1/2 of Schedule SE line 12, rounded to nearest dollar

    Dependencies:
    - schedule_se_line_12_self_employment_tax: Schedule SE line 12

    Args:
        schedule_se_line_12_self_employment_tax: Schedule SE line 12 amount

    Returns:
        Schedule 1 line 15 amount
    """
    return round_to_dollars(schedule_se_line_12_self_employment_tax / Decimal('2'))


def federal_schedule_1_line_16_self_employed_retirement_contributions(
    index: dict,
) -> Decimal:
    """
    Calculate Schedule 1 line 16 self-employed retirement contributions.

    Form/Line: Schedule 1 (Form 1040), line 16
    Formula: Sum of contribution items, rounded to nearest dollar

    Dependencies:
    - contribution_items: Contribution amounts from statements/K-1s

    Args:
        contribution_items: List of contribution amounts

    Returns:
        Schedule 1 line 16 amount
    """
    total = tag_total(index, 'schedule_1_line_16_self_employed_retirement')
    return round_to_dollars(total)


def federal_schedule_1_line_17_self_employed_health_insurance(
    index: dict,
) -> Decimal:
    """
    Calculate Schedule 1 line 17 self-employed health insurance deduction.

    Form/Line: Schedule 1 (Form 1040), line 17
    Formula: Sum of insurance items, rounded to nearest dollar

    Dependencies:
    - insurance_items: Insurance amounts from statements/K-1s

    Args:
        insurance_items: List of insurance amounts

    Returns:
        Schedule 1 line 17 amount
    """
    total = tag_total(index, 'schedule_1_line_17_self_employed_health_insurance')
    return round_to_dollars(total)


def federal_schedule_1_line_26_adjustments_to_income(
    line_15_deductible_self_employment_tax: Decimal,
    line_16_self_employed_retirement_contributions: Decimal,
    line_17_self_employed_health_insurance: Decimal,
    other_adjustments: Decimal = Decimal('0'),
) -> Decimal:
    """
    Calculate Schedule 1 line 26 adjustments to income.

    Form/Line: Schedule 1 (Form 1040), line 26
    Formula: sum of line 15, line 16, line 17, and other adjustments

    This is a simplified calculation that assumes:
    - Other adjustments are zero

    Dependencies:
    - line_15_deductible_self_employment_tax: Schedule 1 line 15
    - line_16_self_employed_retirement_contributions: Schedule 1 line 16
    - line_17_self_employed_health_insurance: Schedule 1 line 17

    Args:
        line_15_deductible_self_employment_tax: Line 15 amount
        line_16_self_employed_retirement_contributions: Line 16 amount
        line_17_self_employed_health_insurance: Line 17 amount
        other_adjustments: Other adjustments (assumed 0)

    Returns:
        Schedule 1 line 26 amount
    """
    total = (
        line_15_deductible_self_employment_tax +
        line_16_self_employed_retirement_contributions +
        line_17_self_employed_health_insurance +
        other_adjustments
    )
    return round_to_dollars(total)


def federal_form_6781_line_7_total_gain_loss_1256(
    index: dict,
) -> Decimal:
    """
    Calculate Form 6781 line 7 total gain or (loss) for section 1256 contracts.

    Form/Line: Form 6781, line 7
    Formula: Sum of net gain/loss amounts, rounded to nearest dollar

    Dependencies:
    - contracts_net_gain_loss: Net gain/loss amounts from section 1256 statements

    Args:
        contracts_net_gain_loss: List of net gain/loss amounts

    Returns:
        Total section 1256 gain/loss (line 7)
    """
    total = tag_total(index, 'section_1256_contracts')
    return round_to_dollars(total)


def federal_form_6781_line_8_short_term_portion(
    line_7_total_gain_loss: Decimal,
    policy: dict,
) -> Decimal:
    """
    Calculate Form 6781 line 8 short-term portion.

    Form/Line: Form 6781, line 8
    Formula: line 7 * short_term_rate

    Dependencies:
    - policy['section_1256']['short_term_rate']

    Args:
        line_7_total_gain_loss: Form 6781 line 7 total gain/loss
        policy: Tax policy dictionary

    Returns:
        Short-term portion (line 8)
    """
    short_term_rate = Decimal(policy['section_1256']['short_term_rate'])
    return round_to_dollars(line_7_total_gain_loss * short_term_rate)


def federal_form_6781_line_9_long_term_portion(
    line_7_total_gain_loss: Decimal,
    policy: dict,
) -> Decimal:
    """
    Calculate Form 6781 line 9 long-term portion.

    Form/Line: Form 6781, line 9
    Formula: line 7 * long_term_rate

    Dependencies:
    - policy['section_1256']['long_term_rate']

    Args:
        line_7_total_gain_loss: Form 6781 line 7 total gain/loss
        policy: Tax policy dictionary

    Returns:
        Long-term portion (line 9)
    """
    long_term_rate = Decimal(policy['section_1256']['long_term_rate'])
    return round_to_dollars(line_7_total_gain_loss * long_term_rate)


def federal_schedule_d_line_1a_short_term_gain(
    index: dict,
) -> Decimal:
    """
    Calculate Schedule D line 1a short-term gain/loss.

    Form/Line: Schedule D (Form 1040), line 1a
    Formula: Sum of (proceeds - cost basis) + adjustments, rounded to nearest dollar

    Dependencies:
    - short_term_transactions: List of (proceeds, cost basis) tuples
    - short_term_adjustments: Adjustment amounts from Form 8949 column (g)

    Args:
        short_term_transactions: Short-term transactions with proceeds and basis
        short_term_adjustments: Optional list of adjustment amounts

    Returns:
        Net short-term gain/loss for line 1a
    """
    proceeds = tag_total(index, 'schedule_d_line_1a_proceeds')
    cost_basis = tag_total(index, 'schedule_d_line_1a_cost_basis')
    total = proceeds - cost_basis
    total += tag_total(index, 'schedule_d_line_1a_adjustments')
    return round_to_dollars(total)


def federal_schedule_d_line_3_short_term_section_1061_adjustment(
    index: dict,
) -> Decimal:
    """
    Calculate Schedule D line 3 short-term section 1061 adjustment.

    Form/Line: Schedule D (Form 1040), line 3
    Formula: Sum of section 1061 adjustments, rounded to nearest dollar

    Dependencies:
    - section_1061_adjustments: Section 1061 adjustment amounts

    Args:
        section_1061_adjustments: List of section 1061 adjustment amounts

    Returns:
        Total section 1061 short-term adjustment
    """
    total = tag_total(index, 'schedule_d_section_1061_adjustment')
    return round_to_dollars(total)


def federal_schedule_d_line_4_short_term_from_6781(
    form_6781_line_8_short_term_portion: Decimal,
) -> Decimal:
    """
    Calculate Schedule D line 4 short-term gain from Form 6781.

    Form/Line: Schedule D (Form 1040), line 4
    Formula: Form 6781 line 8

    Dependencies:
    - form_6781_line_8_short_term_portion: Form 6781 line 8

    Args:
        form_6781_line_8_short_term_portion: Short-term portion from Form 6781

    Returns:
        Schedule D line 4 amount
    """
    return form_6781_line_8_short_term_portion


def federal_schedule_d_line_5_short_term_k1_gain(
    index: dict,
) -> Decimal:
    """
    Calculate Schedule D line 5 short-term K-1 gains.

    Form/Line: Schedule D (Form 1040), line 5
    Formula: Sum of K-1 short-term capital gains, rounded to nearest dollar

    Dependencies:
    - k1_short_term_gains: Short-term gains from Schedule K-1s

    Args:
        k1_short_term_gains: List of short-term capital gain amounts

    Returns:
        Total short-term K-1 gains (line 5)
    """
    total = tag_total(index, 'schedule_d_k1_short_term_gains')
    return round_to_dollars(total)


def federal_schedule_d_line_7_net_short_term_gain(
    line_1a_short_term_gain: Decimal,
    line_3_short_term_adjustment: Decimal,
    line_4_short_term_from_6781: Decimal,
    line_5_short_term_k1_gain: Decimal,
    line_6_short_term_loss_carryover: Decimal = Decimal('0'),
) -> Decimal:
    """
    Calculate Schedule D line 7 net short-term gain/loss.

    Form/Line: Schedule D (Form 1040), line 7
    Formula: line 1a + line 3 + line 4 + line 5 + line 6

    This is a simplified calculation that assumes:
    - Lines 1b and 2 are zero

    Dependencies:
    - line_1a_short_term_gain: Schedule D line 1a
    - line_3_short_term_adjustment: Schedule D line 3
    - line_4_short_term_from_6781: Schedule D line 4
    - line_5_short_term_k1_gain: Schedule D line 5
    - line_6_short_term_loss_carryover: Schedule D line 6 (assumed 0)

    Args:
        line_1a_short_term_gain: Line 1a amount
        line_3_short_term_adjustment: Line 3 amount
        line_4_short_term_from_6781: Line 4 amount
        line_5_short_term_k1_gain: Line 5 amount
        line_6_short_term_loss_carryover: Line 6 amount

    Returns:
        Net short-term capital gain/loss (line 7)
    """
    return (
        line_1a_short_term_gain +
        line_3_short_term_adjustment +
        line_4_short_term_from_6781 +
        line_5_short_term_k1_gain +
        line_6_short_term_loss_carryover
    )


def federal_schedule_d_line_10_long_term_section_1061_adjustment(
    index: dict,
) -> Decimal:
    """
    Calculate Schedule D line 10 long-term section 1061 adjustment.

    Form/Line: Schedule D (Form 1040), line 10
    Formula: Negative of total section 1061 adjustments

    Dependencies:
    - section_1061_adjustments: Section 1061 adjustment amounts

    Args:
        section_1061_adjustments: List of section 1061 adjustment amounts

    Returns:
        Long-term section 1061 adjustment (line 10)
    """
    total = tag_total(index, 'schedule_d_section_1061_adjustment')
    return -round_to_dollars(total)


def federal_schedule_d_line_11_long_term_from_6781_and_4797(
    form_6781_line_9_long_term_portion: Decimal,
    index: dict,
) -> Decimal:
    """
    Calculate Schedule D line 11 long-term gains from Form 6781 and 4797.

    Form/Line: Schedule D (Form 1040), line 11
    Formula: Form 6781 line 9 + total section 1231 gains, rounded to dollars

    Dependencies:
    - form_6781_line_9_long_term_portion: Form 6781 line 9
    - section_1231_gains: Section 1231 gains from Schedule K-1s

    Args:
        form_6781_line_9_long_term_portion: Long-term portion from Form 6781
        section_1231_gains: List of section 1231 gain amounts

    Returns:
        Total long-term gains for line 11
    """
    total_section_1231 = tag_total(index, 'section_1231_gains')
    return round_to_dollars(form_6781_line_9_long_term_portion + total_section_1231)


def federal_schedule_d_line_12_long_term_k1_gain(
    index: dict,
) -> Decimal:
    """
    Calculate Schedule D line 12 long-term K-1 gains.

    Form/Line: Schedule D (Form 1040), line 12
    Formula: Sum of K-1 long-term capital gains, rounded to nearest dollar

    Dependencies:
    - k1_long_term_gains: Long-term gains from Schedule K-1s

    Args:
        k1_long_term_gains: List of long-term capital gain amounts

    Returns:
        Total long-term K-1 gains (line 12)
    """
    total = tag_total(index, 'schedule_d_k1_long_term_gains')
    return round_to_dollars(total)


def federal_schedule_d_line_15_net_long_term_gain(
    line_10_long_term_adjustment: Decimal,
    line_11_long_term_from_6781_and_4797: Decimal,
    line_12_long_term_k1_gain: Decimal,
) -> Decimal:
    """
    Calculate Schedule D line 15 net long-term gain/loss.

    Form/Line: Schedule D (Form 1040), line 15
    Formula: line 10 + line 11 + line 12

    Dependencies:
    - line_10_long_term_adjustment: Schedule D line 10
    - line_11_long_term_from_6781_and_4797: Schedule D line 11
    - line_12_long_term_k1_gain: Schedule D line 12

    Args:
        line_10_long_term_adjustment: Line 10 amount
        line_11_long_term_from_6781_and_4797: Line 11 amount
        line_12_long_term_k1_gain: Line 12 amount

    Returns:
        Net long-term capital gain/loss (line 15)
    """
    return (
        line_10_long_term_adjustment +
        line_11_long_term_from_6781_and_4797 +
        line_12_long_term_k1_gain
    )


def federal_schedule_d_line_16_net_capital_gain(
    line_7_net_short_term_gain: Decimal,
    line_15_net_long_term_gain: Decimal,
) -> Decimal:
    """
    Calculate Schedule D line 16 net capital gain/loss.

    Form/Line: Schedule D (Form 1040), line 16
    Formula: line 7 + line 15

    Dependencies:
    - line_7_net_short_term_gain: Schedule D line 7
    - line_15_net_long_term_gain: Schedule D line 15

    Args:
        line_7_net_short_term_gain: Line 7 amount
        line_15_net_long_term_gain: Line 15 amount

    Returns:
        Net capital gain/loss (line 16)
    """
    return line_7_net_short_term_gain + line_15_net_long_term_gain


def federal_form_8960_line_1_taxable_interest(
    taxable_interest: Decimal,
) -> Decimal:
    """
    Calculate taxable interest (Form 8960, line 1).

    Form/Line: Form 8960, line 1
    Formula: Taxable interest from Schedule B, line 1

    Dependencies:
    - taxable_interest: Total taxable interest (Schedule B line 1)

    Args:
        taxable_interest: Taxable interest amount from Schedule B

    Returns:
        Taxable interest (line 1)
    """
    return taxable_interest


def federal_form_8960_line_2_ordinary_dividends(
    ordinary_dividends: Decimal,
) -> Decimal:
    """
    Calculate ordinary dividends (Form 8960, line 2).

    Form/Line: Form 8960, line 2
    Formula: Ordinary dividends from Schedule B, line 6

    Dependencies:
    - ordinary_dividends: Total ordinary dividends (Schedule B line 6)

    Args:
        ordinary_dividends: Ordinary dividends amount from Schedule B

    Returns:
        Ordinary dividends (line 2)
    """
    return ordinary_dividends


def federal_form_8960_line_4a_rental_real_estate_royalties_partnerships(
    schedule_e_line_32_total_partnership_income: Decimal,
) -> Decimal:
    """
    Calculate Form 8960 line 4a (rentals/partnerships).

    Form/Line: Form 8960, line 4a
    Formula: Schedule E line 32 (total partnership and S corporation income)

    Dependencies:
    - schedule_e_line_32_total_partnership_income: Schedule E line 32

    Args:
        schedule_e_line_32_total_partnership_income: Schedule E line 32 total

    Returns:
        Form 8960 line 4a amount
    """
    return schedule_e_line_32_total_partnership_income


def federal_form_8960_line_4b_adjustment_nonsection_1411(
    nonpassive_income: Decimal,
    nonpassive_losses_allowed: Decimal = Decimal('0'),
    section_179_deduction: Decimal = Decimal('0'),
    additional_nonpassive_deductions: Decimal = Decimal('0'),
) -> Decimal:
    """
    Calculate Form 8960 line 4b adjustment for non-section 1411 trade/business.

    Form/Line: Form 8960, line 4b
    Formula: -(nonpassive income - nonpassive deductions)

    Line 4b removes net income (or loss) from a non-section 1411 trade or business
    included on line 4a so that only passive activity income remains on line 4c.

    Dependencies:
    - nonpassive_income: Nonpassive income included on line 4a
    - nonpassive_losses_allowed: Nonpassive losses allowed (Schedule E line 29b col i)
    - section_179_deduction: Section 179 deductions included on line 4a
    - additional_nonpassive_deductions: Other deductible adjustments to nonpassive income

    Args:
        nonpassive_income: Total nonpassive income included on line 4a
        nonpassive_losses_allowed: Total nonpassive losses allowed
        section_179_deduction: Total section 179 deduction
        additional_nonpassive_deductions: List of other nonpassive deductions

    Returns:
        Form 8960 line 4b total adjustment (negative for net income)
    """
    total_deductions = (
        nonpassive_losses_allowed
        + section_179_deduction
        + additional_nonpassive_deductions
    )
    net_nonpassive = nonpassive_income - total_deductions
    return -round_to_dollars(net_nonpassive)


def federal_form_8960_line_4c_net_income_from_rentals(
    line_4a_rental_real_estate_royalties_partnerships: Decimal,
    line_4b_adjustment_nonsection_1411: Decimal,
) -> Decimal:
    """
    Calculate net income from rentals/partnerships (Form 8960, line 4c).

    Form/Line: Form 8960, line 4c
    Formula: line 4a + line 4b

    Dependencies:
    - line_4a_rental_real_estate_royalties_partnerships: Form 8960 line 4a
    - line_4b_adjustment_nonsection_1411: Form 8960 line 4b

    Args:
        line_4a_rental_real_estate_royalties_partnerships: Rental/royalty/partnership income
        line_4b_adjustment_nonsection_1411: Adjustment for non-section 1411 trade/business

    Returns:
        Net income from rentals/partnerships (line 4c)
    """
    return line_4a_rental_real_estate_royalties_partnerships + line_4b_adjustment_nonsection_1411


def federal_form_8960_line_5a_net_gain_loss_disposition(
    schedule_d_line_16_net_capital_gain: Decimal,
) -> Decimal:
    """
    Calculate Form 8960 line 5a net gain/loss from disposition of property.

    Form/Line: Form 8960, line 5a
    Formula: Schedule D line 16 (net capital gain)

    Dependencies:
    - schedule_d_line_16_net_capital_gain: Schedule D line 16

    Args:
        schedule_d_line_16_net_capital_gain: Schedule D line 16 amount

    Returns:
        Form 8960 line 5a amount
    """
    return schedule_d_line_16_net_capital_gain


def federal_form_8960_line_5d_net_gain_loss_disposition(
    line_5a_net_gain_loss_disposition: Decimal,
    line_5b_gain_not_subject_to_niit: Decimal = Decimal('0'),
    line_5c_adjustment_disposition_partnership_interest: Decimal = Decimal('0'),
) -> Decimal:
    """
    Calculate net gain/loss from disposition of property (Form 8960, line 5d).

    Form/Line: Form 8960, line 5d
    Formula: line 5a + line 5b + line 5c

    This is a simplified calculation that assumes:
    - Line 5b (not subject to NIIT) = 0
    - Line 5c (partnership/S corp adjustment) = 0

    Dependencies:
    - line_5a_net_gain_loss_disposition: Form 8960 line 5a
    - line_5b_gain_not_subject_to_niit: Form 8960 line 5b (assumed 0)
    - line_5c_adjustment_disposition_partnership_interest: Form 8960 line 5c (assumed 0)

    Args:
        line_5a_net_gain_loss_disposition: Net gain/loss from dispositions
        line_5b_gain_not_subject_to_niit: Gain not subject to NIIT
        line_5c_adjustment_disposition_partnership_interest: Partnership/S corp adjustment

    Returns:
        Net gain/loss from disposition of property (line 5d)
    """
    return (
        line_5a_net_gain_loss_disposition +
        line_5b_gain_not_subject_to_niit +
        line_5c_adjustment_disposition_partnership_interest
    )


def federal_form_1040_line_1z_wages(
    index: dict,
) -> Decimal:
    """
    Calculate Form 1040 line 1z total wages.

    Form/Line: Form 1040, line 1z
    Formula: Sum of W-2 box 1 wages, rounded to nearest dollar

    Dependencies:
    - w2_box_1_wages: W-2 box 1 wage amounts

    Args:
        w2_box_1_wages: List of W-2 box 1 wages

    Returns:
        Total wages (line 1z)
    """
    total = tag_total(index, 'form_1040_line_1z_wages', round_each=True)
    return total


def federal_form_1040_line_9_total_income(
    line_1z_wages: Decimal,
    line_2b_taxable_interest: Decimal,
    line_3b_ordinary_dividends: Decimal,
    line_5b_pensions_annuities: Decimal,
    line_7_capital_gain_loss: Decimal,
    line_8_additional_income: Decimal,
) -> Decimal:
    """
    Calculate Form 1040 line 9 total income.

    Form/Line: Form 1040, line 9
    Formula: sum of lines 1z, 2b, 3b, 5b, 7, and 8 (simplified)

    This is a simplified calculation that assumes:
    - Lines 4b and 6b are zero

    Dependencies:
    - line_1z_wages: Form 1040 line 1z
    - line_2b_taxable_interest: Form 1040 line 2b
    - line_3b_ordinary_dividends: Form 1040 line 3b
    - line_5b_pensions_annuities: Form 1040 line 5b
    - line_7_capital_gain_loss: Form 1040 line 7
    - line_8_additional_income: Form 1040 line 8

    Args:
        line_1z_wages: Total wages
        line_2b_taxable_interest: Taxable interest
        line_3b_ordinary_dividends: Ordinary dividends
        line_5b_pensions_annuities: Taxable pensions/annuities
        line_7_capital_gain_loss: Capital gain/loss
        line_8_additional_income: Additional income from Schedule 1

    Returns:
        Total income (line 9)
    """
    total = (
        line_1z_wages +
        line_2b_taxable_interest +
        line_3b_ordinary_dividends +
        line_5b_pensions_annuities +
        line_7_capital_gain_loss +
        line_8_additional_income
    )
    return round_to_dollars(total)


def federal_form_1040_line_11_adjusted_gross_income(
    line_9_total_income: Decimal,
    line_10_adjustments_to_income: Decimal,
) -> Decimal:
    """
    Calculate Form 1040 line 11 adjusted gross income.

    Form/Line: Form 1040, line 11
    Formula: line 9 - line 10

    Dependencies:
    - line_9_total_income: Form 1040 line 9
    - line_10_adjustments_to_income: Form 1040 line 10 (Schedule 1 line 26)

    Args:
        line_9_total_income: Total income (line 9)
        line_10_adjustments_to_income: Adjustments to income (line 10)

    Returns:
        Adjusted gross income (line 11)
    """
    return line_9_total_income - line_10_adjustments_to_income


def federal_form_1040_line_3a_qualified_dividends(
    index: dict,
) -> Decimal:
    """
    Calculate Form 1040 line 3a qualified dividends.

    Form/Line: Form 1040, line 3a
    Formula: Sum of qualified dividend items, rounded to nearest dollar

    Dependencies:
    - qualified_dividend_items: Qualified dividend amounts

    Args:
        qualified_dividend_items: List of qualified dividend amounts

    Returns:
        Qualified dividends (line 3a)
    """
    total = tag_total(index, 'form_1040_line_3a_qualified_dividends')
    return round_to_dollars(total)


def federal_form_1040_line_12_standard_deduction(
    policy: dict,
    line_12_deduction_override: Decimal | None = None,
) -> Decimal:
    """
    Calculate Form 1040 line 12 standard deduction.

    Form/Line: Form 1040, line 12
    Formula: Standard deduction

    Dependencies:
    - policy['standard_deduction']

    Args:
        policy: Tax policy dictionary

    Returns:
        Standard deduction amount (line 12)
    """
    if line_12_deduction_override is not None:
        return round_to_dollars(line_12_deduction_override)
    standard_deduction = Decimal(policy['standard_deduction'])
    return standard_deduction


def federal_form_1040_line_14_total_deductions(
    line_12_standard_deduction: Decimal,
    line_13_qbi_deduction: Decimal = Decimal('0'),
) -> Decimal:
    """
    Calculate Form 1040 line 14 total deductions.

    Form/Line: Form 1040, line 14
    Formula: line 12 + line 13

    This is a simplified calculation that assumes:
    - Line 13 (QBI deduction) is zero

    Dependencies:
    - line_12_standard_deduction: Form 1040 line 12
    - line_13_qbi_deduction: Form 1040 line 13 (assumed 0)

    Args:
        line_12_standard_deduction: Standard deduction
        line_13_qbi_deduction: QBI deduction

    Returns:
        Total deductions (line 14)
    """
    return line_12_standard_deduction + line_13_qbi_deduction


def federal_form_1040_line_15_taxable_income(
    line_11_adjusted_gross_income: Decimal,
    line_14_total_deductions: Decimal,
) -> Decimal:
    """
    Calculate Form 1040 line 15 taxable income.

    Form/Line: Form 1040, line 15
    Formula: line 11 - line 14

    Dependencies:
    - line_11_adjusted_gross_income: Form 1040 line 11
    - line_14_total_deductions: Form 1040 line 14

    Args:
        line_11_adjusted_gross_income: Adjusted gross income
        line_14_total_deductions: Total deductions

    Returns:
        Taxable income (line 15)
    """
    return line_11_adjusted_gross_income - line_14_total_deductions


def _qualified_dividends_capital_gain_worksheet_lines_3_to_5(
    line_1_taxable_income: Decimal,
    line_2_qualified_dividends: Decimal,
    schedule_d_line_15: Decimal,
    schedule_d_line_16: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    line_3 = Decimal('0')
    if schedule_d_line_15 > 0 and schedule_d_line_16 > 0:
        line_3 = min(schedule_d_line_15, schedule_d_line_16)
    line_4 = line_2_qualified_dividends + line_3
    line_5 = max(line_1_taxable_income - line_4, Decimal('0'))
    return line_3, line_4, line_5


def federal_form_1040_tax_computation_worksheet_tax(
    taxable_income: Decimal,
    policy: dict,
) -> Decimal:
    """
    Calculate tax using the Tax Computation Worksheet (Form 1040 instructions).

    Form/Line: Tax Computation Worksheet (Form 1040 instructions)
    Formula: taxable_income * rate - subtract_amount

    Dependencies:
    - policy['tax_computation_worksheet']['min_income']
    - policy['tax_computation_worksheet']['sections']

    Args:
        taxable_income: Taxable income to compute tax on
        policy: Tax policy dictionary

    Returns:
        Tax computed per worksheet
    """
    worksheet = policy['tax_computation_worksheet']
    min_income = Decimal(worksheet['min_income'])
    if taxable_income < min_income:
        raise ValueError(
            "Tax computation worksheet applies to amounts at or above "
            f"{min_income}. Got {taxable_income}."
        )

    sections = worksheet['sections']
    for row in sections:
        row_min = Decimal(row['min'])
        row_max = row['max']
        if row_max is not None:
            row_max = Decimal(row_max)
        if taxable_income >= row_min and (row_max is None or taxable_income <= row_max):
            rate = Decimal(row['rate'])
            subtract_amount = Decimal(row['subtract_amount'])
            tax = taxable_income * rate - subtract_amount
            return round_to_dollars(tax)

    raise ValueError(f"No tax computation worksheet row matched income {taxable_income}.")


def federal_form_1040_qualified_dividends_capital_gain_worksheet_line_22_tax_on_line_5(
    line_1_taxable_income: Decimal,
    line_2_qualified_dividends: Decimal,
    schedule_d_line_15: Decimal,
    schedule_d_line_16: Decimal,
    policy: dict,
) -> Decimal:
    """
    Calculate Qualified Dividends and Capital Gain Tax Worksheet line 22.

    Form/Line: Qualified Dividends and Capital Gain Tax Worksheet, line 22
    Formula: Tax computation worksheet on line 5

    Dependencies:
    - line_1_taxable_income: Form 1040 line 15
    - line_2_qualified_dividends: Form 1040 line 3a
    - schedule_d_line_15: Schedule D line 15
    - schedule_d_line_16: Schedule D line 16
    - policy['tax_computation_worksheet']

    Args:
        line_1_taxable_income: Taxable income
        line_2_qualified_dividends: Qualified dividends
        schedule_d_line_15: Schedule D line 15
        schedule_d_line_16: Schedule D line 16
        policy: Tax policy dictionary

    Returns:
        Worksheet line 22 amount (tax on line 5)
    """
    _, _, line_5 = _qualified_dividends_capital_gain_worksheet_lines_3_to_5(
        line_1_taxable_income,
        line_2_qualified_dividends,
        schedule_d_line_15,
        schedule_d_line_16,
    )
    return federal_form_1040_tax_computation_worksheet_tax(
        taxable_income=line_5,
        policy=policy,
    )


def federal_form_1040_qualified_dividends_capital_gain_worksheet_line_24_tax_on_line_1(
    line_1_taxable_income: Decimal,
    policy: dict,
) -> Decimal:
    """
    Calculate Qualified Dividends and Capital Gain Tax Worksheet line 24.

    Form/Line: Qualified Dividends and Capital Gain Tax Worksheet, line 24
    Formula: Tax computation worksheet on line 1

    Dependencies:
    - line_1_taxable_income: Form 1040 line 15
    - policy['tax_computation_worksheet']

    Args:
        line_1_taxable_income: Taxable income
        policy: Tax policy dictionary

    Returns:
        Worksheet line 24 amount (tax on line 1)
    """
    return federal_form_1040_tax_computation_worksheet_tax(
        taxable_income=line_1_taxable_income,
        policy=policy,
    )


def federal_form_1040_qualified_dividends_capital_gain_worksheet_line_25(
    line_1_taxable_income: Decimal,
    line_2_qualified_dividends: Decimal,
    schedule_d_line_15: Decimal,
    schedule_d_line_16: Decimal,
    policy: dict,
) -> Decimal:
    """
    Calculate Qualified Dividends and Capital Gain Tax Worksheet line 25.

    Form/Line: Qualified Dividends and Capital Gain Tax Worksheet, line 25
    Formula: min(line 23, line 24)

    Dependencies:
    - line_1_taxable_income: Form 1040 line 15
    - line_2_qualified_dividends: Form 1040 line 3a
    - schedule_d_line_15: Schedule D line 15
    - schedule_d_line_16: Schedule D line 16
    - worksheet line 22 (tax on line 5)
    - worksheet line 24 (tax on line 1)
    - policy['capital_gains'] thresholds and rates

    Args:
        line_1_taxable_income: Taxable income
        line_2_qualified_dividends: Qualified dividends
        schedule_d_line_15: Schedule D line 15
        schedule_d_line_16: Schedule D line 16
        policy: Tax policy dictionary

    Returns:
        Worksheet line 25 amount (tax on all taxable income)
    """
    line_3, line_4, line_5 = _qualified_dividends_capital_gain_worksheet_lines_3_to_5(
        line_1_taxable_income,
        line_2_qualified_dividends,
        schedule_d_line_15,
        schedule_d_line_16,
    )
    line_22_tax_on_line_5 = federal_form_1040_qualified_dividends_capital_gain_worksheet_line_22_tax_on_line_5(
        line_1_taxable_income,
        line_2_qualified_dividends,
        schedule_d_line_15,
        schedule_d_line_16,
        policy,
    )
    line_24_tax_on_line_1 = federal_form_1040_qualified_dividends_capital_gain_worksheet_line_24_tax_on_line_1(
        line_1_taxable_income,
        policy,
    )

    zero_rate_threshold = Decimal(policy['capital_gains']['zero_rate_threshold'])
    line_7 = min(line_1_taxable_income, zero_rate_threshold)
    line_8 = min(line_5, line_7)
    line_9 = line_7 - line_8

    line_10 = min(line_1_taxable_income, line_4)
    line_12 = line_10 - line_9

    twenty_rate_threshold = Decimal(policy['capital_gains']['twenty_rate_threshold'])
    line_14 = min(line_1_taxable_income, twenty_rate_threshold)
    line_15 = line_5 + line_9
    line_16 = max(line_14 - line_15, Decimal('0'))
    line_17 = min(line_12, line_16)

    rate_15 = Decimal(policy['capital_gains']['rate_15'])
    rate_20 = Decimal(policy['capital_gains']['rate_20'])
    line_18 = round_to_dollars(line_17 * rate_15)
    line_19 = line_9 + line_17
    line_20 = line_10 - line_19
    line_21 = round_to_dollars(line_20 * rate_20)
    line_23 = round_to_dollars(line_18 + line_21 + line_22_tax_on_line_5)

    return min(line_23, line_24_tax_on_line_1)

def federal_form_1040_line_5b_pensions_annuities(
    index: dict,
) -> Decimal:
    """
    Calculate Form 1040 line 5b taxable pensions and annuities.

    Form/Line: Form 1040, line 5b
    Formula: Sum of pension/annuity taxable amounts, rounded to nearest dollar

    Dependencies:
    - pension_items: Taxable pension/annuity amounts

    Args:
        pension_items: List of taxable pension/annuity amounts

    Returns:
        Taxable pensions/annuities (line 5b)
    """
    total = tag_total(index, 'form_1040_line_5b_pensions')
    return round_to_dollars(total)


def federal_form_1040_line_16_tax(
    line_16_tax_from_worksheet: Decimal,
) -> Decimal:
    """
    Calculate Form 1040 line 16 tax.

    Form/Line: Form 1040, line 16
    Formula: Amount from tax worksheet

    Dependencies:
    - line_16_tax_from_worksheet: Tax amount from worksheet

    Args:
        line_16_tax_from_worksheet: Tax amount from worksheet

    Returns:
        Tax amount (line 16)
    """
    return line_16_tax_from_worksheet


def ny_it201_line_39_nys_tax_on_line_38(
    worksheet_line_3_tax_from_rate_schedule: Decimal,
    worksheet_line_4_recapture_base_amount: Decimal,
    worksheet_line_9_incremental_benefit_addback: Decimal,
) -> Decimal:
    """
    Calculate NY IT-201 line 39 (NYS tax on line 38 amount).

    Form/Line: NY IT-201, line 39
    Formula: Statement 2 (Tax Computation Worksheet 4) line 10
             = line 3 + line 4 + line 9

    Dependencies:
    - worksheet_line_3_tax_from_rate_schedule: Statement 2, line 3
    - worksheet_line_4_recapture_base_amount: Statement 2, line 4
    - worksheet_line_9_incremental_benefit_addback: Statement 2, line 9

    Args:
        worksheet_line_3_tax_from_rate_schedule: NYS tax from rate schedule
        worksheet_line_4_recapture_base_amount: Recapture base amount
        worksheet_line_9_incremental_benefit_addback: Incremental benefit addback

    Returns:
        Line 39 NYS tax on line 38 amount
    """
    return (
        worksheet_line_3_tax_from_rate_schedule
        + worksheet_line_4_recapture_base_amount
        + worksheet_line_9_incremental_benefit_addback
    )


def ny_it201_statement_2_line_3_tax_from_rate_schedule(
    line_38_ny_taxable_income: Decimal,
    policy: dict,
) -> Decimal:
    """
    Calculate Statement 2 (Tax Computation Worksheet 4) line 3.

    Form/Line: Statement 2, line 3 (Tax Computation Worksheet 4)
    Formula: Apply NYS tax rate schedule to NY taxable income

    Dependencies:
    - line_38_ny_taxable_income: IT-201 line 38
    - policy['ny_nys_tax_rate_schedule']

    Args:
        line_38_ny_taxable_income: NY taxable income
        policy: Policy dictionary with NYS tax schedule

    Returns:
        Statement 2 line 3 tax from rate schedule
    """
    taxable_income = max(line_38_ny_taxable_income, Decimal('0'))
    schedule = policy.get('ny_nys_tax_rate_schedule', [])
    for row in schedule:
        row_min = Decimal(row['min'])
        row_max = row['max']
        if row_max is not None:
            row_max = Decimal(row_max)
        if taxable_income >= row_min and (row_max is None or taxable_income <= row_max):
            base_tax = Decimal(row['base_tax'])
            rate = Decimal(row['rate'])
            tax = base_tax + (taxable_income - row_min) * rate
            return round_to_dollars(tax)

    raise ValueError(f"No NYS tax schedule row matched income {taxable_income}.")


def ny_it201_statement_2_line_4_recapture_base_amount(
    policy: dict,
) -> Decimal:
    """
    Return Statement 2 (Tax Computation Worksheet 4) line 4 recapture base amount.

    Form/Line: Statement 2, line 4 (Tax Computation Worksheet 4)
    Formula: Constant per instructions

    Dependencies:
    - policy['ny_tax_computation_worksheet_4']['recapture_base_amount']

    Args:
        policy: Policy dictionary with worksheet constants

    Returns:
        Statement 2 line 4 recapture base amount
    """
    worksheet = policy.get('ny_tax_computation_worksheet_4', {})
    return Decimal(worksheet['recapture_base_amount'])


def ny_it201_statement_2_line_9_incremental_benefit_addback(
    policy: dict,
) -> Decimal:
    """
    Return Statement 2 (Tax Computation Worksheet 4) line 9 incremental benefit addback.

    Form/Line: Statement 2, line 9 (Tax Computation Worksheet 4)
    Formula: Constant per instructions

    Dependencies:
    - policy['ny_tax_computation_worksheet_4']['incremental_benefit_addback']

    Args:
        policy: Policy dictionary with worksheet constants

    Returns:
        Statement 2 line 9 incremental benefit addback
    """
    worksheet = policy.get('ny_tax_computation_worksheet_4', {})
    return Decimal(worksheet['incremental_benefit_addback'])


def ny_it112r_line_22_total_income(
    line_33_ny_adjusted_gross_income: Decimal,
) -> Decimal:
    """
    Calculate IT-112-R line 22, column A (total income).

    Form/Line: IT-112-R, line 22 column A
    Formula: NY adjusted gross income

    Dependencies:
    - line_33_ny_adjusted_gross_income: IT-201 line 33

    Args:
        line_33_ny_adjusted_gross_income: NY adjusted gross income

    Returns:
        Line 22 total income (column A)
    """
    return line_33_ny_adjusted_gross_income


def ny_it112r_line_22_other_state_income(
    line_22_other_state_income_items: list[dict],
) -> Decimal:
    """
    Calculate IT-112-R line 22, column B (other-state income).

    Form/Line: IT-112-R, line 22 column B
    Formula: sum of other-state income items

    Args:
        line_22_other_state_income_items: List of other-state income items

    Returns:
        Line 22 other-state income (column B)
    """
    total = Decimal("0")
    for item in line_22_other_state_income_items:
        total += Decimal(item["amount"])
    return total


def ny_it112r_line_24_total_other_state_tax(
    line_24_total_other_state_tax_items: list[dict],
) -> Decimal:
    """
    Calculate IT-112-R line 24 (total other state tax).

    Form/Line: IT-112-R, line 24
    Formula: sum of other-state tax items

    Args:
        line_24_total_other_state_tax_items: List of other-state tax items

    Returns:
        Line 24 total other-state tax
    """
    total = Decimal("0")
    for item in line_24_total_other_state_tax_items:
        total += Decimal(item["amount"])
    return total


def ny_it112r_line_26_ratio(
    line_22_total_income: Decimal,
    line_22_other_state_income: Decimal,
) -> Decimal:
    """
    Calculate IT-112-R line 26 ratio (other-state income / total income).

    Form/Line: IT-112-R, line 26
    Formula: line 22 column B / line 22 column A (rounded to 4 decimals)

    Dependencies:
    - line_22_total_income: IT-112-R line 22 column A
    - line_22_other_state_income: IT-112-R line 22 column B

    Args:
        line_22_total_income: Total income
        line_22_other_state_income: Other-state income

    Returns:
        Line 26 ratio rounded to 4 decimals
    """
    if line_22_total_income == 0:
        return Decimal('0')
    ratio = line_22_other_state_income / line_22_total_income
    return ratio.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


def ny_it112r_line_27_ny_tax_times_ratio(
    line_25_ny_tax_payable: Decimal,
    line_26_ratio: Decimal,
) -> Decimal:
    """
    Calculate IT-112-R line 27 (NY tax times ratio).

    Form/Line: IT-112-R, line 27
    Formula: line 25 * line 26

    Dependencies:
    - line_25_ny_tax_payable: IT-112-R line 25
    - line_26_ratio: IT-112-R line 26

    Args:
        line_25_ny_tax_payable: NY tax payable
        line_26_ratio: Ratio of other-state income to total income

    Returns:
        Line 27 amount
    """
    return round_to_dollars(line_25_ny_tax_payable * line_26_ratio)


def ny_it112r_line_28_smaller_of_line24_or_27(
    line_24_total_other_state_tax: Decimal,
    line_27_ny_tax_times_ratio: Decimal,
) -> Decimal:
    """
    Calculate IT-112-R line 28 (smaller of lines 24 and 27).

    Form/Line: IT-112-R, line 28
    Formula: min(line 24, line 27)

    Dependencies:
    - line_24_total_other_state_tax: IT-112-R line 24
    - line_27_ny_tax_times_ratio: IT-112-R line 27

    Args:
        line_24_total_other_state_tax: Other state tax imposed
        line_27_ny_tax_times_ratio: NY tax times ratio

    Returns:
        Line 28 amount
    """
    return min(line_24_total_other_state_tax, line_27_ny_tax_times_ratio)


def ny_it112r_line_30_total_credit(
    line_28_smaller_of_line24_or_27: Decimal,
) -> Decimal:
    """
    Calculate IT-112-R line 30 (total credit from all IT-112-R forms).

    Form/Line: IT-112-R, line 30
    Formula: line 28 + line 29

    Assumptions:
    - line 29 (additional IT-112-R/IT-112-C forms) is zero for 2024

    Dependencies:
    - line_28_smaller_of_line24_or_27: IT-112-R line 28

    Args:
        line_28_smaller_of_line24_or_27: Line 28 amount

    Returns:
        Line 30 total credit
    """
    return line_28_smaller_of_line24_or_27


def ny_it112r_line_34_resident_credit(
    line_30_total_credit: Decimal,
    line_25_ny_tax_payable: Decimal,
) -> Decimal:
    """
    Calculate IT-112-R line 34 (resident credit allowed).

    Form/Line: IT-112-R, line 34
    Formula: min(line 30, line 33)

    Assumptions:
    - line 32 (other credits before this credit) is zero for 2024
    - line 33 equals line 25 when line 32 is zero

    Dependencies:
    - line_30_total_credit: IT-112-R line 30
    - line_25_ny_tax_payable: IT-112-R line 25

    Args:
        line_30_total_credit: Total credit from IT-112-R
        line_25_ny_tax_payable: NY tax payable

    Returns:
        Line 34 resident credit
    """
    return min(line_30_total_credit, line_25_ny_tax_payable)


def ny_it201_line_38_ny_taxable_income(
    line_35_ny_taxable_income_before_exemptions: Decimal,
    line_36_dependent_exemptions: Decimal,
) -> Decimal:
    """
    Calculate NY IT-201 line 38 (NY taxable income).

    Form/Line: NY IT-201, line 38
    Formula: line 35 - line 36

    Dependencies:
    - line_35_ny_taxable_income_before_exemptions: IT-201 line 35
    - line_36_dependent_exemptions: IT-201 line 36

    Args:
        line_35_ny_taxable_income_before_exemptions: NY taxable income before exemptions
        line_36_dependent_exemptions: Dependent exemptions

    Returns:
        Line 38 NY taxable income
    """
    return line_35_ny_taxable_income_before_exemptions - line_36_dependent_exemptions


def ny_it201_line_35_ny_taxable_income_before_exemptions(
    line_33_ny_adjusted_gross_income: Decimal,
    line_34_standard_deduction: Decimal,
) -> Decimal:
    """
    Calculate NY IT-201 line 35 (NY taxable income before exemptions).

    Form/Line: NY IT-201, line 35
    Formula: line 33 - line 34

    Dependencies:
    - line_33_ny_adjusted_gross_income: IT-201 line 33
    - line_34_standard_deduction: IT-201 line 34

    Args:
        line_33_ny_adjusted_gross_income: New York adjusted gross income
        line_34_standard_deduction: Standard (or itemized) deduction

    Returns:
        Line 35 NY taxable income before exemptions
    """
    return line_33_ny_adjusted_gross_income - line_34_standard_deduction


def ny_it201_line_33_ny_adjusted_gross_income(
    line_24_ny_total_income: Decimal,
    line_32_ny_total_subtractions: Decimal,
) -> Decimal:
    """
    Calculate NY IT-201 line 33 (NY adjusted gross income).

    Form/Line: NY IT-201, line 33
    Formula: line 24 - line 32

    Dependencies:
    - line_24_ny_total_income: IT-201 line 24
    - line_32_ny_total_subtractions: IT-201 line 32

    Args:
        line_24_ny_total_income: NY total income (line 24)
        line_32_ny_total_subtractions: NY subtractions (line 32)

    Returns:
        Line 33 NY adjusted gross income
    """
    return line_24_ny_total_income - line_32_ny_total_subtractions


def ny_it201_line_28_us_gov_bond_interest(
    line_28_us_gov_bond_interest_items: list[dict],
    policy: dict,
) -> Decimal:
    """
    Calculate NY IT-201 line 28 (Interest income on U.S. government bonds).

    Form/Line: NY IT-201, line 28
    Formula: sum(item.amount * policy percentage for each eligible fund), rounded

    Dependencies:
    - policy['ny_us_gov_bond_interest_percentages']: mapping of fund key -> percentage

    Assumptions:
    - Items are limited to funds that report U.S. government obligations percentages.
    - Item amounts are total ordinary dividends for each fund from 1099-DIV detail.

    Args:
        line_28_us_gov_bond_interest_items: List of items with fund key and amount
        policy: Policy config dict

    Returns:
        Line 28 U.S. government bond interest subtraction
    """
    percentages = policy["ny_us_gov_bond_interest_percentages"]
    total = Decimal("0")
    for item in line_28_us_gov_bond_interest_items:
        fund = item["fund"]
        amount = Decimal(item["amount"])
        percentage = Decimal(percentages[fund])
        total += amount * percentage
    return round_to_dollars(total)


def ny_it201_line_32_ny_total_subtractions(
    line_28_us_gov_bond_interest: Decimal,
) -> Decimal:
    """
    Calculate NY IT-201 line 32 (New York total subtractions).

    Form/Line: NY IT-201, line 32
    Formula: sum of lines 25 through 31

    Assumptions:
    - lines 25, 26, 27, 29, 30, 31 are zero for 2024

    Dependencies:
    - line_28_us_gov_bond_interest: IT-201 line 28

    Args:
        line_28_us_gov_bond_interest: Interest income on U.S. government bonds

    Returns:
        Line 32 NY total subtractions
    """
    return line_28_us_gov_bond_interest


def ny_it201_line_19_federal_agi(
    line_17_total_federal_income: Decimal,
    line_18_federal_adjustments: Decimal,
) -> Decimal:
    """
    Calculate NY IT-201 line 19 (federal adjusted gross income).

    Form/Line: NY IT-201, line 19
    Formula: line 17 - line 18

    Dependencies:
    - line_17_total_federal_income: IT-201 line 17
    - line_18_federal_adjustments: IT-201 line 18

    Args:
        line_17_total_federal_income: Total federal income
        line_18_federal_adjustments: Total federal adjustments to income

    Returns:
        Line 19 federal adjusted gross income
    """
    return line_17_total_federal_income - line_18_federal_adjustments


def ny_it201_line_24_ny_total_income(
    line_19_federal_agi: Decimal,
    line_21_public_employee_414h: Decimal = Decimal('0'),
    line_22_ny_529_distributions: Decimal = Decimal('0'),
    line_23_other_additions: Decimal = Decimal('0'),
) -> Decimal:
    """
    Calculate NY IT-201 line 24 (New York total income).

    Form/Line: NY IT-201, line 24
    Formula: line 19 + line 21 + line 22 + line 23

    Assumptions:
    - line 20 (state/local bond interest) is zero for 2024
    - line 20 is excluded from this helper and remains zero for 2024

    Dependencies:
    - line_19_federal_agi: IT-201 line 19
    - line_21_public_employee_414h: IT-201 line 21
    - line_22_ny_529_distributions: IT-201 line 22
    - line_23_other_additions: IT-201 line 23 (IT-225 line 9)

    Args:
        line_19_federal_agi: Federal adjusted gross income
        line_21_public_employee_414h: Public employee 414(h) retirement contributions
        line_22_ny_529_distributions: NY 529 college savings distributions
        line_23_other_additions: Other NY additions

    Returns:
        Line 24 NY total income
    """
    return (
        line_19_federal_agi
        + line_21_public_employee_414h
        + line_22_ny_529_distributions
        + line_23_other_additions
    )


def ny_it201_line_23_other_additions(
    it225_line_9_total_additions: Decimal,
) -> Decimal:
    """
    Calculate NY IT-201 line 23 (other additions).

    Form/Line: NY IT-201, line 23
    Formula: IT-225 line 9

    Dependencies:
    - it225_line_9_total_additions: NY IT-225, line 9

    Args:
        it225_line_9_total_additions: Total additions from IT-225

    Returns:
        Line 23 other additions
    """
    return it225_line_9_total_additions


def ny_it225_line_1a_additions(
    line_1a_additions_items: list[dict],
) -> Decimal:
    """
    Calculate NY IT-225 line 1a (New York State additions, Part 1).

    Form/Line: NY IT-225, line 1a
    Formula: sum of Part 1 additions items

    Args:
        line_1a_additions_items: List of additions items with amounts

    Returns:
        Line 1a additions total
    """
    total = Decimal("0")
    for item in line_1a_additions_items:
        total += Decimal(item["amount"])
    return total


def ny_it225_line_5a_additions(
    line_5a_additions_items: list[dict],
) -> Decimal:
    """
    Calculate NY IT-225 line 5a (New York State additions, Part 2).

    Form/Line: NY IT-225, line 5a
    Formula: sum of Part 2 additions items (line 5a)

    Args:
        line_5a_additions_items: List of additions items with amounts

    Returns:
        Line 5a additions total
    """
    total = Decimal("0")
    for item in line_5a_additions_items:
        total += Decimal(item["amount"])
    return total


def ny_it225_line_5b_additions(
    line_5b_additions_items: list[dict],
) -> Decimal:
    """
    Calculate NY IT-225 line 5b (New York State additions, Part 2).

    Form/Line: NY IT-225, line 5b
    Formula: sum of Part 2 additions items (line 5b)

    Args:
        line_5b_additions_items: List of additions items with amounts

    Returns:
        Line 5b additions total
    """
    total = Decimal("0")
    for item in line_5b_additions_items:
        total += Decimal(item["amount"])
    return total


def ny_it225_line_9_total_additions(
    line_4_total_part1_additions: Decimal,
    line_8_total_part2_additions: Decimal,
) -> Decimal:
    """
    Calculate NY IT-225 line 9 (total additions).

    Form/Line: NY IT-225, line 9
    Formula: line 4 + line 8

    Dependencies:
    - line_4_total_part1_additions: IT-225 line 4
    - line_8_total_part2_additions: IT-225 line 8

    Args:
        line_4_total_part1_additions: Total additions from Part 1
        line_8_total_part2_additions: Total additions from Part 2

    Returns:
        Line 9 total additions
    """
    return line_4_total_part1_additions + line_8_total_part2_additions


def ny_it225_line_8_total_part2_additions(
    line_6_total_part2_additions: Decimal,
) -> Decimal:
    """
    Calculate NY IT-225 line 8 (total Part 2 additions).

    Form/Line: NY IT-225, line 8
    Formula: line 6 + line 7

    Assumptions:
    - line 7 (additional IT-225 forms) is zero for 2024

    Dependencies:
    - line_6_total_part2_additions: IT-225 line 6

    Args:
        line_6_total_part2_additions: Total additions from Part 2

    Returns:
        Line 8 total Part 2 additions
    """
    return line_6_total_part2_additions


def ny_it225_line_6_total_part2_additions(
    line_5a_additions: Decimal,
    line_5b_additions: Decimal,
) -> Decimal:
    """
    Calculate NY IT-225 line 6 (total Part 2 additions).

    Form/Line: NY IT-225, line 6
    Formula: sum of line 5a through 5g

    Assumptions:
    - lines 5c through 5g are zero for 2024

    Dependencies:
    - line_5a_additions: IT-225 line 5a
    - line_5b_additions: IT-225 line 5b

    Args:
        line_5a_additions: Part 2 additions line 5a
        line_5b_additions: Part 2 additions line 5b

    Returns:
        Line 6 total Part 2 additions
    """
    return line_5a_additions + line_5b_additions


def ny_it225_line_4_total_part1_additions(
    line_2_total_part1_additions: Decimal,
) -> Decimal:
    """
    Calculate NY IT-225 line 4 (total Part 1 additions).

    Form/Line: NY IT-225, line 4
    Formula: line 2 + line 3

    Assumptions:
    - line 3 (additional IT-225 forms) is zero for 2024

    Dependencies:
    - line_2_total_part1_additions: IT-225 line 2

    Args:
        line_2_total_part1_additions: Total additions from Part 1

    Returns:
        Line 4 total Part 1 additions
    """
    return line_2_total_part1_additions


def ny_it225_line_2_total_part1_additions(
    line_1a_additions: Decimal,
) -> Decimal:
    """
    Calculate NY IT-225 line 2 (total Part 1 additions).

    Form/Line: NY IT-225, line 2
    Formula: sum of line 1a through 1g

    Assumptions:
    - lines 1b through 1g are zero for 2024

    Dependencies:
    - line_1a_additions: IT-225 line 1a

    Args:
        line_1a_additions: Part 1 additions line 1a

    Returns:
        Line 2 total Part 1 additions
    """
    return line_1a_additions


def ny_it201_line_18_federal_adjustments(
    federal_schedule_1_line_26_adjustments_to_income: Decimal,
) -> Decimal:
    """
    Calculate NY IT-201 line 18 (total federal adjustments to income).

    Form/Line: NY IT-201, line 18
    Formula: federal Schedule 1 line 26

    Dependencies:
    - federal_schedule_1_line_26_adjustments_to_income: Federal Schedule 1, line 26

    Args:
        federal_schedule_1_line_26_adjustments_to_income: Federal adjustments to income

    Returns:
        Line 18 total federal adjustments
    """
    return federal_schedule_1_line_26_adjustments_to_income


def ny_it201_line_17_total_federal_income(
    federal_form_1040_line_9_total_income: Decimal,
) -> Decimal:
    """
    Calculate NY IT-201 line 17 (total federal income).

    Form/Line: NY IT-201, line 17
    Formula: federal Form 1040 line 9

    Dependencies:
    - federal_form_1040_line_9_total_income: Federal Form 1040, line 9

    Args:
        federal_form_1040_line_9_total_income: Federal total income

    Returns:
        Line 17 total federal income
    """
    return federal_form_1040_line_9_total_income


def ny_it201_line_36_dependent_exemptions(
    dependents_count: Decimal,
    policy: dict,
) -> Decimal:
    """
    Calculate NY IT-201 line 36 (dependent exemptions).

    Form/Line: NY IT-201, line 36
    Formula: dependents_count * exemption_amount

    Dependencies:
    - policy['ny_dependent_exemption_amount']: Exemption amount per dependent

    Args:
        dependents_count: Number of dependents
        policy: Policy configuration with NY exemption amount

    Returns:
        Line 36 dependent exemptions
    """
    exemption_amount = Decimal(policy['ny_dependent_exemption_amount'])
    return dependents_count * exemption_amount


def ny_it201_line_34_standard_deduction(
    policy: dict,
) -> Decimal:
    """
    Calculate NY IT-201 line 34 (standard deduction).

    Form/Line: NY IT-201, line 34
    Formula: Policy constant

    Assumptions:
    - Uses the standard deduction value from policy

    Dependencies:
    - policy['ny_standard_deduction']: NY standard deduction

    Args:
        policy: Policy configuration with NY standard deduction table

    Returns:
        Line 34 standard deduction
    """
    return Decimal(policy['ny_standard_deduction'])


def ny_it201_line_43_nys_credits_total(
    line_41_resident_credit: Decimal,
) -> Decimal:
    """
    Calculate NY IT-201 line 43 (total NYS nonrefundable credits).

    Form/Line: NY IT-201, line 43
    Formula: line 40 + line 41 + line 42

    Assumptions:
    - line 40 (NYS household credit) is zero for 2024
    - line 42 (other NYS nonrefundable credits) is zero for 2024

    Dependencies:
    - line_41_resident_credit: IT-201 line 41

    Args:
        line_41_resident_credit: Resident credit

    Returns:
        Line 43 total NYS credits
    """
    return line_41_resident_credit


def ny_it201_line_41_resident_credit(
    it112r_line_34_resident_credit: Decimal,
) -> Decimal:
    """
    Calculate NY IT-201 line 41 (resident credit).

    Form/Line: NY IT-201, line 41
    Formula: Form IT-112-R line 34

    Dependencies:
    - it112r_line_34_resident_credit: IT-112-R line 34

    Args:
        it112r_line_34_resident_credit: Resident credit from IT-112-R

    Returns:
        Line 41 resident credit
    """
    return it112r_line_34_resident_credit


def ny_it201_line_44_ny_state_tax_after_credits(
    line_39_nys_tax_on_line_38: Decimal,
    line_43_nys_credits_total: Decimal,
) -> Decimal:
    """
    Calculate NY IT-201 line 44 (NYS tax after credits).

    Form/Line: NY IT-201, line 44
    Formula: line 39 - line 43

    Dependencies:
    - line_39_nys_tax_on_line_38: IT-201 line 39
    - line_43_nys_credits_total: IT-201 line 43

    Args:
        line_39_nys_tax_on_line_38: NYS tax on line 38
        line_43_nys_credits_total: Total NYS credits

    Returns:
        Line 44 NYS tax after credits
    """
    return line_39_nys_tax_on_line_38 - line_43_nys_credits_total


def ny_it201_line_46_total_ny_state_taxes(
    line_44_ny_state_tax_after_credits: Decimal,
) -> Decimal:
    """
    Calculate NY IT-201 line 46 (total New York State taxes).

    Form/Line: NY IT-201, line 46
    Formula: line 44 + line 45

    Assumptions:
    - line 45 (net other NYS taxes) is zero for 2024

    Dependencies:
    - line_44_ny_state_tax_after_credits: IT-201 line 44

    Args:
        line_44_ny_state_tax_after_credits: NYS tax after credits

    Returns:
        Line 46 total NYS taxes
    """
    return line_44_ny_state_tax_after_credits


def ny_it201_line_54_nyc_tax_after_credits(
    line_52_nyc_tax_before_credits: Decimal,
    line_53_nyc_nonrefundable_credits: Decimal,
) -> Decimal:
    """
    Calculate NY IT-201 line 54 (NYC tax after credits).

    Form/Line: NY IT-201, line 54
    Formula: line 52 - line 53

    Dependencies:
    - line_52_nyc_tax_before_credits: IT-201 line 52
    - line_53_nyc_nonrefundable_credits: IT-201 line 53

    Args:
        line_52_nyc_tax_before_credits: NYC tax before credits
        line_53_nyc_nonrefundable_credits: NYC nonrefundable credits

    Returns:
        Line 54 NYC tax after credits
    """
    return line_52_nyc_tax_before_credits - line_53_nyc_nonrefundable_credits


def ny_it201_line_52_nyc_tax_before_credits(
    line_49_nyc_tax_after_household_credit: Decimal,
) -> Decimal:
    """
    Calculate NY IT-201 line 52 (NYC tax before credits).

    Form/Line: NY IT-201, line 52
    Formula: line 49 + line 50 + line 51

    Assumptions:
    - line 50 (part-year NYC resident tax) is zero for 2024
    - line 51 (other NYC taxes) is zero for 2024

    Dependencies:
    - line_49_nyc_tax_after_household_credit: IT-201 line 49

    Args:
        line_49_nyc_tax_after_household_credit: NYC tax after household credit

    Returns:
        Line 52 NYC tax before credits
    """
    return line_49_nyc_tax_after_household_credit


def ny_it219_line_7_beneficiary_ubt_credit(
    line_7_beneficiary_ubt_credit_items: list[dict],
) -> Decimal:
    """
    Calculate IT-219 line 7 (beneficiary share of NYC UBT credit).

    Form/Line: IT-219, line 7
    Formula: sum of beneficiary UBT credit items

    Args:
        line_7_beneficiary_ubt_credit_items: List of UBT credit items

    Returns:
        Line 7 beneficiary UBT credit total
    """
    total = Decimal("0")
    for item in line_7_beneficiary_ubt_credit_items:
        total += Decimal(item["amount"])
    return total


def ny_it219_line_9_taxable_income(
    line_47_nyc_taxable_income: Decimal,
) -> Decimal:
    """
    Calculate IT-219 line 9 (taxable income for UBT credit factor).

    Form/Line: IT-219, line 9
    Formula: NY IT-201 line 47

    Args:
        line_47_nyc_taxable_income: IT-201 line 47

    Returns:
        Line 9 taxable income
    """
    return line_47_nyc_taxable_income


def ny_it219_line_10_income_factor(
    line_9_taxable_income: Decimal,
    policy: dict,
) -> Decimal:
    """
    Calculate IT-219 line 10 (income factor).

    Form/Line: IT-219, line 10
    Formula: factor based on taxable income thresholds

    Dependencies:
    - policy['ny_it219_income_factor'] with thresholds and factors

    Args:
        line_9_taxable_income: IT-219 line 9 taxable income
        policy: Policy dictionary

    Returns:
        Line 10 income factor
    """
    params = policy['ny_it219_income_factor']
    lower_threshold = Decimal(params['lower_threshold'])
    upper_threshold = Decimal(params['upper_threshold'])
    lower_factor = Decimal(params['lower_factor'])
    upper_factor = Decimal(params['upper_factor'])
    if line_9_taxable_income <= lower_threshold:
        return lower_factor
    if line_9_taxable_income >= upper_threshold:
        return upper_factor
    slope = (upper_factor - lower_factor) / (upper_threshold - lower_threshold)
    factor = lower_factor + (line_9_taxable_income - lower_threshold) * slope
    return factor.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


def ny_it219_line_8_total_ubt_credit(
    line_7_beneficiary_ubt_credit: Decimal,
) -> Decimal:
    """
    Calculate IT-219 line 8 (total UBT credit).

    Form/Line: IT-219, line 8
    Formula: line 5 + line 6 + line 7 (line 7 only for this return)

    Args:
        line_7_beneficiary_ubt_credit: Beneficiary UBT credit (line 7)

    Returns:
        Line 8 total UBT credit
    """
    return line_7_beneficiary_ubt_credit


def ny_it219_line_11_income_based_credit(
    line_8_total_ubt_credit: Decimal,
    line_10_income_factor: Decimal,
) -> Decimal:
    """
    Calculate IT-219 line 11 (income-based credit amount).

    Form/Line: IT-219, line 11
    Formula: line 8 * line 10 (rounded to dollars)

    Dependencies:
    - line_10_income_factor: IT-219 line 10

    Args:
        line_8_total_ubt_credit: Total UBT credit
        line_10_income_factor: Income-based factor

    Returns:
        Line 11 income-based credit amount
    """
    return round_to_dollars(line_8_total_ubt_credit * line_10_income_factor)


def ny_it219_line_15_total_tax(
    line_12_nyc_tax_less_household_credit: Decimal,
) -> Decimal:
    """
    Calculate IT-219 line 15 (total tax for limitation).

    Form/Line: IT-219, line 15
    Formula: line 12 + line 13 + line 14 (line 12 only for this return)

    Args:
        line_12_nyc_tax_less_household_credit: NYC tax less household credit

    Returns:
        Line 15 total tax for limitation
    """
    return line_12_nyc_tax_less_household_credit


def ny_it219_line_16_resident_ubt_credit(
    line_11_income_based_credit: Decimal,
    line_15_total_tax: Decimal,
) -> Decimal:
    """
    Calculate IT-219 line 16 (resident UBT credit).

    Form/Line: IT-219, line 16
    Formula: lesser of line 11 or line 15

    Args:
        line_11_income_based_credit: IT-219 line 11
        line_15_total_tax: IT-219 line 15

    Returns:
        Line 16 resident UBT credit
    """
    return min(line_11_income_based_credit, line_15_total_tax)


def ny_it201_att_line_8_nyc_resident_ubt_credit(
    it219_line_16_resident_ubt_credit: Decimal,
) -> Decimal:
    """
    Calculate IT-201-ATT line 8 (NYC resident UBT credit).

    Form/Line: IT-201-ATT, line 8
    Formula: IT-219 line 16

    Args:
        it219_line_16_resident_ubt_credit: IT-219 line 16

    Returns:
        Line 8 NYC resident UBT credit
    """
    return it219_line_16_resident_ubt_credit


def ny_it201_att_line_10_total_nyc_nonrefundable_credits(
    line_8_nyc_resident_ubt_credit: Decimal,
) -> Decimal:
    """
    Calculate IT-201-ATT line 10 (total NYC nonrefundable credits).

    Form/Line: IT-201-ATT, line 10
    Formula: line 8 + line 9 + line 9a

    Assumptions:
    - line 9 (NYC accumulation distribution credit) is zero for 2024
    - line 9a (part-year resident NYC child/dependent care credit) is zero for 2024

    Dependencies:
    - line_8_nyc_resident_ubt_credit: IT-201-ATT line 8

    Args:
        line_8_nyc_resident_ubt_credit: NYC resident UBT credit

    Returns:
        Line 10 total NYC nonrefundable credits
    """
    return line_8_nyc_resident_ubt_credit


def ny_it201_att_line_12_other_refundable_credits(
    line_12_other_refundable_credits_items: list[dict],
) -> Decimal:
    """
    Calculate IT-201-ATT line 12 (other refundable credits).

    Form/Line: IT-201-ATT, line 12
    Formula: sum of line 12a-12l items

    Args:
        line_12_other_refundable_credits_items: List of refundable credit items

    Returns:
        Line 12 total other refundable credits
    """
    total = Decimal("0")
    for item in line_12_other_refundable_credits_items:
        total += Decimal(item["amount"])
    return total


def ny_it201_att_line_13_total_refundable_credits(
    line_12_other_refundable_credits: Decimal,
) -> Decimal:
    """
    Calculate IT-201-ATT line 13 (total refundable credits).

    Form/Line: IT-201-ATT, line 13
    Formula: line 11 + line 12 (line 11 is zero for this return)

    Args:
        line_12_other_refundable_credits: IT-201-ATT line 12

    Returns:
        Line 13 total refundable credits
    """
    return line_12_other_refundable_credits


def ny_it201_att_line_14_total_refundable_credits(
    line_13_total_refundable_credits: Decimal,
) -> Decimal:
    """
    Calculate IT-201-ATT line 14 (total refundable credits).

    Form/Line: IT-201-ATT, line 14
    Formula: Amount from line 13

    Args:
        line_13_total_refundable_credits: IT-201-ATT line 13

    Returns:
        Line 14 total refundable credits
    """
    return line_13_total_refundable_credits


def ny_it201_att_line_18_total_other_refundable_credits(
    line_14_total_refundable_credits: Decimal,
) -> Decimal:
    """
    Calculate IT-201-ATT line 18 (total other refundable credits).

    Form/Line: IT-201-ATT, line 18
    Formula: line 14 + line 15 + line 16 + line 17 + line 17a (line 14 only)

    Args:
        line_14_total_refundable_credits: IT-201-ATT line 14

    Returns:
        Line 18 total other refundable credits
    """
    return line_14_total_refundable_credits


def ny_it201_line_71_other_refundable_credits(
    it201_att_line_18_total_other_refundable_credits: Decimal,
) -> Decimal:
    """
    Calculate NY IT-201 line 71 (other refundable credits).

    Form/Line: IT-201, line 71
    Formula: IT-201-ATT line 18

    Args:
        it201_att_line_18_total_other_refundable_credits: IT-201-ATT line 18

    Returns:
        Line 71 other refundable credits
    """
    return it201_att_line_18_total_other_refundable_credits


def ny_it201_line_53_nyc_nonrefundable_credits(
    it201_att_line_10_total_nyc_nonrefundable_credits: Decimal,
) -> Decimal:
    """
    Calculate NY IT-201 line 53 (NYC nonrefundable credits).

    Form/Line: NY IT-201, line 53
    Formula: IT-201-ATT line 10

    Dependencies:
    - it201_att_line_10_total_nyc_nonrefundable_credits: IT-201-ATT line 10

    Args:
        it201_att_line_10_total_nyc_nonrefundable_credits: Total NYC credits

    Returns:
        Line 53 NYC nonrefundable credits
    """
    return it201_att_line_10_total_nyc_nonrefundable_credits


def ny_it201_line_47_nyc_taxable_income(
    line_38_ny_taxable_income: Decimal,
) -> Decimal:
    """
    Calculate NY IT-201 line 47 (NYC taxable income).

    Form/Line: NY IT-201, line 47
    Formula: line 38 (for full-year NYC residents)

    Assumptions:
    - Full-year NYC resident return, so line 47 equals line 38

    Dependencies:
    - line_38_ny_taxable_income: IT-201 line 38

    Args:
        line_38_ny_taxable_income: NY taxable income

    Returns:
        Line 47 NYC taxable income
    """
    return line_38_ny_taxable_income


def ny_it201_line_47a_nyc_resident_tax(
    line_47_nyc_taxable_income: Decimal,
    policy: dict,
) -> Decimal:
    """
    Calculate NY IT-201 line 47a (NYC resident tax).

    Form/Line: NY IT-201, line 47a
    Formula: NYC tax rate schedule applied to line 47

    Dependencies:
    - line_47_nyc_taxable_income: IT-201 line 47
    - policy['nyc_resident_tax_rate_schedule']

    Args:
        line_47_nyc_taxable_income: NYC taxable income
        policy: Policy dictionary with NYC tax schedule

    Returns:
        Line 47a NYC resident tax
    """
    taxable_income = max(line_47_nyc_taxable_income, Decimal('0'))
    schedule = policy.get('nyc_resident_tax_rate_schedule', [])
    for row in schedule:
        row_min = Decimal(row['min'])
        row_max = row['max']
        if row_max is not None:
            row_max = Decimal(row_max)
        if taxable_income >= row_min and (row_max is None or taxable_income <= row_max):
            base_tax = Decimal(row['base_tax'])
            rate = Decimal(row['rate'])
            tax = base_tax + (taxable_income - row_min) * rate
            return round_to_dollars(tax)

    raise ValueError(f"No NYC tax schedule row matched income {taxable_income}.")


def ny_it201_line_49_nyc_tax_after_household_credit(
    line_47a_nyc_resident_tax: Decimal,
) -> Decimal:
    """
    Calculate NY IT-201 line 49 (NYC tax after household credit).

    Form/Line: NY IT-201, line 49
    Formula: line 47a - line 48

    Assumptions:
    - line 48 (NYC household credit) is zero for 2024

    Dependencies:
    - line_47a_nyc_resident_tax: IT-201 line 47a

    Args:
        line_47a_nyc_resident_tax: NYC resident tax

    Returns:
        Line 49 NYC tax after household credit
    """
    return line_47a_nyc_resident_tax


def ny_it201_line_54c_mctmt_zone_1(
    line_54a_mctmt_net_earnings_zone_1: Decimal,
    policy: dict,
) -> Decimal:
    """
    Calculate NY IT-201 line 54c (MCTMT for Zone 1).

    Form/Line: NY IT-201, line 54c
    Formula: line 54a * MCTMT Zone 1 rate

    Dependencies:
    - line_54a_mctmt_net_earnings_zone_1: IT-201 line 54a
    - policy['ny_mctmt_rates']['zone_1']

    Args:
        line_54a_mctmt_net_earnings_zone_1: MCTMT net earnings base for Zone 1
        policy: Policy dictionary with MCTMT rates

    Returns:
        Line 54c MCTMT for Zone 1
    """
    rate = Decimal(policy['ny_mctmt_rates']['zone_1'])
    return round_to_dollars(line_54a_mctmt_net_earnings_zone_1 * rate)


def ny_it2105_9_worksheet_4a_line_1_net_earnings_zone_1(
    worksheet_4a_line_1_net_earnings_zone_1_items: list[dict],
    policy: dict,
) -> Decimal:
    """
    Calculate IT-2105.9 Worksheet 4a line 1 (net earnings in Zone 1).

    Form/Line: IT-2105.9 Worksheet 4a, line 1
    Formula: sum((ordinary business income + guaranteed payments) * earnings factor)

    Dependencies:
    - policy['ny_mctmt']['earnings_factor']

    Assumptions:
    - Inputs are already MCTD Zone 1-eligible (no additional allocation applied).

    Args:
        worksheet_4a_line_1_net_earnings_zone_1_items: List of partnership items
        policy: Policy dictionary with MCTMT earnings factor

    Returns:
        Worksheet 4a line 1 net earnings for Zone 1
    """
    earnings_factor = Decimal(policy["ny_mctmt"]["earnings_factor"])
    total = Decimal("0")
    for item in worksheet_4a_line_1_net_earnings_zone_1_items:
        ordinary_income = Decimal(item["ordinary_business_income"])
        guaranteed_payments = Decimal(item["guaranteed_payments_services"])
        total += (ordinary_income + guaranteed_payments) * earnings_factor
    return round_to_dollars(total)


def ny_it201_line_54a_mctmt_net_earnings_zone_1(
    it2105_9_worksheet_4a_line_1_net_earnings_zone_1: Decimal,
) -> Decimal:
    """
    Calculate NY IT-201 line 54a (MCTMT net earnings base, Zone 1).

    Form/Line: NY IT-201, line 54a
    Formula: IT-2105.9 Worksheet 4a, line 1 (column d)

    Args:
        it2105_9_worksheet_4a_line_1_net_earnings_zone_1: Worksheet 4a line 1

    Returns:
        Line 54a MCTMT net earnings base for Zone 1
    """
    return it2105_9_worksheet_4a_line_1_net_earnings_zone_1


def ny_it201_line_54e_mctmt_total(
    line_54c_mctmt_zone_1: Decimal,
) -> Decimal:
    """
    Calculate NY IT-201 line 54e (total MCTMT).

    Form/Line: NY IT-201, line 54e
    Formula: line 54c + line 54d

    Assumptions:
    - line 54d (Zone 2 MCTMT) is zero for 2024

    Dependencies:
    - line_54c_mctmt_zone_1: IT-201 line 54c

    Args:
        line_54c_mctmt_zone_1: MCTMT for Zone 1

    Returns:
        Line 54e total MCTMT
    """
    return line_54c_mctmt_zone_1


def ny_it201_line_58_total_nyc_yonkers_mctmt(
    line_54_nyc_tax_after_credits: Decimal,
    line_54e_mctmt_total: Decimal,
) -> Decimal:
    """
    Calculate NY IT-201 line 58 (total NYC/Yonkers taxes and MCTMT).

    Form/Line: NY IT-201, line 58
    Formula: line 54 + line 54e + line 55 + line 56 + line 57

    Assumptions:
    - line 55 (Yonkers resident income tax surcharge) is zero for 2024
    - line 56 (Yonkers nonresident earnings tax) is zero for 2024
    - line 57 (part-year Yonkers resident surcharge) is zero for 2024

    Dependencies:
    - line_54_nyc_tax_after_credits: IT-201 line 54
    - line_54e_mctmt_total: IT-201 line 54e

    Args:
        line_54_nyc_tax_after_credits: NYC tax after credits
        line_54e_mctmt_total: MCTMT total

    Returns:
        Line 58 total NYC/Yonkers taxes and MCTMT
    """
    return line_54_nyc_tax_after_credits + line_54e_mctmt_total


def ny_it201_line_61_total_taxes(
    line_46_total_ny_state_taxes: Decimal,
    line_58_total_nyc_yonkers_mctmt: Decimal,
) -> Decimal:
    """
    Calculate NY IT-201 line 61 (total taxes).

    Form/Line: NY IT-201, line 61
    Formula: line 46 + line 58 + line 59 + line 60

    Assumptions:
    - line 59 (sales/use tax) is zero for 2024
    - line 60 (voluntary contributions) is zero for 2024

    Dependencies:
    - line_46_total_ny_state_taxes: IT-201 line 46
    - line_58_total_nyc_yonkers_mctmt: IT-201 line 58

    Args:
        line_46_total_ny_state_taxes: Total NYS taxes
        line_58_total_nyc_yonkers_mctmt: Total NYC/Yonkers taxes and MCTMT

    Returns:
        Line 61 total taxes
    """
    return line_46_total_ny_state_taxes + line_58_total_nyc_yonkers_mctmt


def ny_it201_line_62_total_taxes(
    line_61_total_taxes: Decimal,
) -> Decimal:
    """
    Calculate NY IT-201 line 62 (total taxes).

    Form/Line: NY IT-201, line 62
    Formula: line 61

    Dependencies:
    - line_61_total_taxes: NY IT-201 line 61 (total taxes)

    Args:
        line_61_total_taxes: Total NYS/NYC/Yonkers taxes

    Returns:
        Line 62 total taxes
    """
    return line_61_total_taxes


def federal_form_1040_line_18_tax_and_amounts(
    line_16_tax: Decimal,
    line_17_schedule_2_line_3: Decimal = Decimal('0'),
) -> Decimal:
    """
    Calculate Form 1040 line 18 tax and amounts.

    Form/Line: Form 1040, line 18
    Formula: line 16 + line 17

    This is a simplified calculation that assumes:
    - Line 17 (Schedule 2 line 3) is zero

    Dependencies:
    - line_16_tax: Form 1040 line 16
    - line_17_schedule_2_line_3: Form 1040 line 17 (assumed 0)

    Args:
        line_16_tax: Tax amount from line 16
        line_17_schedule_2_line_3: Schedule 2 line 3 amount

    Returns:
        Tax and amounts (line 18)
    """
    return line_16_tax + line_17_schedule_2_line_3


def federal_form_1040_line_21_total_credits(
    line_19_child_tax_credit: Decimal = Decimal('0'),
    line_20_schedule_3_line_8: Decimal = Decimal('0'),
) -> Decimal:
    """
    Calculate Form 1040 line 21 total credits.

    Form/Line: Form 1040, line 21
    Formula: line 19 + line 20

    Dependencies:
    - line_19_child_tax_credit: Form 1040 line 19
    - line_20_schedule_3_line_8: Form 1040 line 20 (Schedule 3 line 8)

    Args:
        line_19_child_tax_credit: Child tax credit / other dependents credit
        line_20_schedule_3_line_8: Total nonrefundable credits from Schedule 3

    Returns:
        Total credits (line 21)
    """
    return line_19_child_tax_credit + line_20_schedule_3_line_8


def federal_form_1040_line_22_tax_after_credits(
    line_18_tax_and_amounts: Decimal,
    line_21_total_credits: Decimal = Decimal('0'),
) -> Decimal:
    """
    Calculate Form 1040 line 22 tax after credits.

    Form/Line: Form 1040, line 22
    Formula: line 18 - line 21

    This is a simplified calculation that assumes:
    - Line 21 (total credits) is zero for this return

    Dependencies:
    - line_18_tax_and_amounts: Form 1040 line 18
    - line_21_total_credits: Form 1040 line 21 (assumed 0)

    Args:
        line_18_tax_and_amounts: Tax and amounts (line 18)
        line_21_total_credits: Total credits (line 21)

    Returns:
        Tax after credits (line 22)
    """
    return line_18_tax_and_amounts - line_21_total_credits


def federal_form_8960_line_8_total_investment_income(
    line_1_taxable_interest: Decimal,
    line_2_ordinary_dividends: Decimal,
    line_3_annuities: Decimal = Decimal('0'),
    line_4c_net_income_from_rentals: Decimal = Decimal('0'),
    line_5d_net_gain_loss_disposition: Decimal = Decimal('0'),
    line_6_adjustments_cfc_pfic: Decimal = Decimal('0'),
    line_7_other_modifications: Decimal = Decimal('0'),
) -> Decimal:
    """
    Calculate total investment income (Form 8960, line 8).

    Form/Line: Form 8960, line 8
    Formula: Sum of lines 1, 2, 3, 4c, 5d, 6, and 7

    This is a simplified calculation that assumes:
    - Line 3 (annuities) = 0
    - Line 6 (CFC/PFIC adjustments) = 0
    - Line 7 (other modifications) = 0

    Dependencies:
    - line_1_taxable_interest: Form 8960 line 1
    - line_2_ordinary_dividends: Form 8960 line 2
    - line_4c_net_income_from_rentals: Form 8960 line 4c
    - line_5d_net_gain_loss_disposition: Form 8960 line 5d

    Args:
        line_1_taxable_interest: Taxable interest
        line_2_ordinary_dividends: Ordinary dividends
        line_3_annuities: Annuities (assumed 0)
        line_4c_net_income_from_rentals: Net income from rentals/partnerships
        line_5d_net_gain_loss_disposition: Net gain/loss from dispositions
        line_6_adjustments_cfc_pfic: CFC/PFIC adjustments (assumed 0)
        line_7_other_modifications: Other modifications (assumed 0)

    Returns:
        Total investment income (line 8)
    """
    return (
        line_1_taxable_interest +
        line_2_ordinary_dividends +
        line_3_annuities +
        line_4c_net_income_from_rentals +
        line_5d_net_gain_loss_disposition +
        line_6_adjustments_cfc_pfic +
        line_7_other_modifications
    )


def federal_form_8960_line_13_modified_adjusted_gross_income(
    form_1040_line_11_adjusted_gross_income: Decimal,
) -> Decimal:
    """
    Calculate modified adjusted gross income (Form 8960, line 13).

    Form/Line: Form 8960, line 13
    Formula: Form 1040, line 11 (AGI)

    Dependencies:
    - form_1040_line_11_adjusted_gross_income: Form 1040 line 11

    Args:
        form_1040_line_11_adjusted_gross_income: Adjusted gross income

    Returns:
        Modified adjusted gross income (line 13)
    """
    return form_1040_line_11_adjusted_gross_income


def federal_form_8960_line_15_modified_agi_over_threshold(
    line_13_modified_adjusted_gross_income: Decimal,
    policy: dict,
) -> Decimal:
    """
    Calculate modified AGI over threshold (Form 8960, line 15).

    Form/Line: Form 8960, line 15
    Formula: line 13 - line 14, floored at zero

    Dependencies:
    - line_13_modified_adjusted_gross_income: Form 8960 line 13
    - policy['net_investment_income_tax']['threshold']

    Args:
        line_13_modified_adjusted_gross_income: Modified AGI
        policy: Policy configuration dict

    Returns:
        Modified AGI over threshold (line 15)
    """
    niit_policy = policy['net_investment_income_tax']
    threshold = Decimal(niit_policy['threshold'])
    return max(Decimal('0'), line_13_modified_adjusted_gross_income - threshold)


def federal_form_8960_line_16_smaller_of_line_12_or_15(
    line_12_net_investment_income: Decimal,
    line_15_modified_agi_over_threshold: Decimal,
) -> Decimal:
    """
    Calculate Form 8960 line 16.

    Form/Line: Form 8960, line 16
    Formula: smaller of line 12 or line 15

    Dependencies:
    - line_12_net_investment_income: Form 8960 line 12
    - line_15_modified_agi_over_threshold: Form 8960 line 15

    Args:
        line_12_net_investment_income: Net investment income
        line_15_modified_agi_over_threshold: Modified AGI over threshold

    Returns:
        Line 16 amount
    """
    return min(line_12_net_investment_income, line_15_modified_agi_over_threshold)


def federal_form_8960_line_17_net_investment_income_tax(
    line_16_smaller_of_line_12_or_15: Decimal,
    policy: dict,
) -> Decimal:
    """
    Calculate Net Investment Income Tax (Form 8960, line 17).

    Form/Line: Form 8960, line 17
    Formula: line 16 × 3.8%, rounded to nearest dollar

    Dependencies:
    - line_16_smaller_of_line_12_or_15: Form 8960 line 16
    - policy['net_investment_income_tax']['rate']: 3.8%

    Args:
        line_16_smaller_of_line_12_or_15: Form 8960 line 16 amount
        policy: Policy configuration dict

    Returns:
        Net investment income tax
    """
    rate = Decimal(policy['net_investment_income_tax']['rate'])
    tax = line_16_smaller_of_line_12_or_15 * rate
    return round_to_dollars(tax)


def federal_schedule_2_line_12_net_investment_income_tax(
    form_8960_line_17_net_investment_income_tax: Decimal,
) -> Decimal:
    """
    Calculate Net Investment Income Tax (Schedule 2, line 12).

    Form/Line: Schedule 2 (Form 1040), line 12
    Formula: Form 8960, line 17

    Dependencies:
    - form_8960_line_17_net_investment_income_tax: Net investment income tax

    Args:
        form_8960_line_17_net_investment_income_tax: Form 8960 line 17 amount

    Returns:
        Net investment income tax for Schedule 2, line 12
    """
    return form_8960_line_17_net_investment_income_tax


def federal_schedule_2_line_21_other_taxes(
    line_4_self_employment_tax: Decimal = Decimal('0'),
    line_7_additional_ss_medicare_tax: Decimal = Decimal('0'),
    line_8_ira_tax: Decimal = Decimal('0'),
    line_9_household_employment_tax: Decimal = Decimal('0'),
    line_10_homebuyer_credit_repayment: Decimal = Decimal('0'),
    line_11_additional_medicare_tax: Decimal = Decimal('0'),
    line_12_net_investment_income_tax: Decimal = Decimal('0'),
    line_13_uncollected_ss_medicare_rrta: Decimal = Decimal('0'),
    line_14_installment_interest: Decimal = Decimal('0'),
    line_15_deferred_gain_interest: Decimal = Decimal('0'),
    line_16_low_income_housing_recapture: Decimal = Decimal('0'),
    line_18_recapture_net_epe: Decimal = Decimal('0'),
    line_19_section_965_installment: Decimal = Decimal('0'),
) -> Decimal:
    """
    Calculate total other taxes (Schedule 2, line 21).

    Form/Line: Schedule 2 (Form 1040), line 21
    Formula: Sum of lines 4, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, and 19

    Dependencies:
    - Various tax components from Schedule 2, Part II

    Args:
        line_4_self_employment_tax: Self-employment tax from Schedule SE
        line_7_additional_ss_medicare_tax: Total additional SS and Medicare tax
        line_8_ira_tax: Additional tax on IRAs or other tax-favored accounts
        line_9_household_employment_tax: Household employment taxes from Schedule H
        line_10_homebuyer_credit_repayment: Repayment of first-time homebuyer credit
        line_11_additional_medicare_tax: Additional Medicare Tax from Form 8959
        line_12_net_investment_income_tax: Net investment income tax from Form 8960
        line_13_uncollected_ss_medicare_rrta: Uncollected SS/Medicare or RRTA tax
        line_14_installment_interest: Interest on tax due on installment income
        line_15_deferred_gain_interest: Interest on deferred tax on gain
        line_16_low_income_housing_recapture: Recapture of low-income housing credit
        line_18_recapture_net_epe: Recapture of net EPE from Form 4255
        line_19_section_965_installment: Section 965 net tax liability installment

    Returns:
        Total other taxes amount
    """
    return (
        line_4_self_employment_tax +
        line_7_additional_ss_medicare_tax +
        line_8_ira_tax +
        line_9_household_employment_tax +
        line_10_homebuyer_credit_repayment +
        line_11_additional_medicare_tax +
        line_12_net_investment_income_tax +
        line_13_uncollected_ss_medicare_rrta +
        line_14_installment_interest +
        line_15_deferred_gain_interest +
        line_16_low_income_housing_recapture +
        line_18_recapture_net_epe +
        line_19_section_965_installment
    )


def federal_1040_line_23_other_taxes(
    schedule_2_line_21_total_other_taxes: Decimal,
) -> Decimal:
    """
    Calculate other taxes (Form 1040, line 23).

    Form/Line: Form 1040, line 23
    Formula: Value from Schedule 2, line 21

    Dependencies:
    - schedule_2_line_21_total_other_taxes: Schedule 2, line 21

    Args:
        schedule_2_line_21_total_other_taxes: Total other taxes from Schedule 2

    Returns:
        Other taxes amount (pass-through from Schedule 2, line 21)
    """
    return schedule_2_line_21_total_other_taxes


def federal_1040_line_24_total_tax(
    line_22_tax_after_credits: Decimal,
    line_23_other_taxes: Decimal,
) -> Decimal:
    """
    Calculate total tax (Form 1040, line 24).

    Form/Line: Form 1040, line 24
    Formula: line 22 + line 23

    Dependencies:
    - line_22_tax_after_credits: Form 1040, line 22 (tax after credits)
    - line_23_other_taxes: Form 1040, line 23 (from Schedule 2, line 21)

    Args:
        line_22_tax_after_credits: Tax amount after subtracting credits
        line_23_other_taxes: Other taxes from Schedule 2

    Returns:
        Total tax amount
    """
    return line_22_tax_after_credits + line_23_other_taxes


def compute_federal_total_tax(inputs: dict, policy: dict) -> Decimal:
    """
    Compute the complete federal total tax from raw inputs.

    This top-level function orchestrates all the calculation steps,
    computing intermediate values in the correct order and returning
    the final total tax (Form 1040, line 24).

    Form/Line: Form 1040, line 24 (final result)

    Args:
        inputs: Input data dict containing all factual values
        policy: Policy configuration dict containing tax law parameters

    Returns:
        Total federal tax amount
    """
    # Build lookup index for flat inputs list
    index = build_inputs_index(inputs)

    # K-1 inputs (partnership source)
    k1_box_14a = tag_total(index, 'schedule_se_k1_box_14a_self_employment_earnings', required=True)
    k1_box_12 = tag_total(index, 'section_179_deduction', required=True)

    # Schedule SE Line 2: Net SE income from K-1
    line_2_sched_c_k1 = federal_schedule_se_line_2_schedule_c_and_k1_profit(
        k1_box_14a, k1_box_12
    )

    # Schedule SE Line 6: Total SE earnings (simplified)
    line_6_se_earnings = federal_schedule_se_line_6_total_se_earnings(
        line_2_sched_c_k1, policy
    )

    # Schedule SE Line 10: Social security tax
    line_10_ss_tax = federal_schedule_se_line_10_social_security_tax(
        line_6_se_earnings, policy
    )

    # Schedule SE Line 11: Medicare tax
    line_11_medicare = federal_schedule_se_line_11_medicare_tax(
        line_6_se_earnings, policy
    )

    # Schedule SE Line 12: Total self-employment tax
    line_12_se_tax = federal_schedule_se_line_12_self_employment_tax(
        line_10_ss_tax, line_11_medicare
    )

    # Schedule 1 Part II: Adjustments to income
    line_15_deductible_se_tax = federal_schedule_1_line_15_deductible_self_employment_tax(
        line_12_se_tax
    )
    line_16_retirement = federal_schedule_1_line_16_self_employed_retirement_contributions(
        index
    )
    line_17_health_insurance = federal_schedule_1_line_17_self_employed_health_insurance(
        index
    )
    line_26_adjustments = federal_schedule_1_line_26_adjustments_to_income(
        line_15_deductible_se_tax,
        line_16_retirement,
        line_17_health_insurance,
    )

    # Form 8959: Additional Medicare Tax
    w2_medicare_wages = tag_total(index, 'w2_box_5_medicare_wages')
    line_11_add_medicare = federal_form_8959_line_18_additional_medicare_tax(
        w2_medicare_wages, line_6_se_earnings, policy
    )

    # Form 8960: Net Investment Income Tax
    line_1_sched_b_interest = federal_schedule_b_line_1_taxable_interest(
        index
    )
    line_6_sched_b_ordinary_dividends = federal_schedule_b_line_6_ordinary_dividends(
        index
    )
    line_1_taxable_interest = federal_form_8960_line_1_taxable_interest(
        line_1_sched_b_interest
    )
    line_2_ordinary_dividends = federal_form_8960_line_2_ordinary_dividends(
        line_6_sched_b_ordinary_dividends
    )
    line_29a_nonpassive_income = federal_schedule_e_line_29a_total_nonpassive_income(
        index
    )
    line_29b_nonpassive_loss_allowed = federal_schedule_e_line_29b_total_nonpassive_loss_allowed(
        index
    )
    line_29b_section_179_deduction = federal_schedule_e_line_29b_total_section_179_deduction(
        index
    )
    line_30_total_income = federal_schedule_e_line_30_total_income(
        line_29a_nonpassive_income
    )
    line_31_total_losses = federal_schedule_e_line_31_total_losses(
        line_29b_nonpassive_loss_allowed,
        line_29b_section_179_deduction=line_29b_section_179_deduction,
    )
    line_32_total_partnership_income = federal_schedule_e_line_32_total_partnership_income(
        line_30_total_income,
        line_31_total_losses,
    )
    line_5_schedule_1_rental_income = federal_schedule_1_line_5_rental_real_estate_income(
        line_32_total_partnership_income
    )
    line_10_schedule_1_additional_income = federal_schedule_1_line_10_additional_income(
        line_5_schedule_1_rental_income
    )
    line_4a_rentals_partnerships = (
        federal_form_8960_line_4a_rental_real_estate_royalties_partnerships(
            line_32_total_partnership_income
        )
    )
    line_4b_additional_deductions = tag_total(index, 'form_8960_line_4b_additional_nonpassive_deductions')
    line_4b_adjustment = federal_form_8960_line_4b_adjustment_nonsection_1411(
        nonpassive_income=line_29a_nonpassive_income,
        section_179_deduction=line_29b_section_179_deduction,
        additional_nonpassive_deductions=line_4b_additional_deductions,
    )
    line_4c_net_income = federal_form_8960_line_4c_net_income_from_rentals(
        line_4a_rentals_partnerships, line_4b_adjustment
    )
    form_6781_line_7_total = federal_form_6781_line_7_total_gain_loss_1256(
        index
    )
    form_6781_line_8_short_term = federal_form_6781_line_8_short_term_portion(
        form_6781_line_7_total, policy
    )
    form_6781_line_9_long_term = federal_form_6781_line_9_long_term_portion(
        form_6781_line_7_total, policy
    )
    schedule_d_line_1a = federal_schedule_d_line_1a_short_term_gain(
        index
    )
    schedule_d_line_3 = federal_schedule_d_line_3_short_term_section_1061_adjustment(
        index
    )
    schedule_d_line_4 = federal_schedule_d_line_4_short_term_from_6781(
        form_6781_line_8_short_term
    )
    schedule_d_line_5 = federal_schedule_d_line_5_short_term_k1_gain(
        index
    )
    schedule_d_line_7 = federal_schedule_d_line_7_net_short_term_gain(
        schedule_d_line_1a,
        schedule_d_line_3,
        schedule_d_line_4,
        schedule_d_line_5,
    )
    schedule_d_line_10 = federal_schedule_d_line_10_long_term_section_1061_adjustment(
        index
    )
    schedule_d_line_11 = federal_schedule_d_line_11_long_term_from_6781_and_4797(
        form_6781_line_9_long_term,
        index,
    )
    schedule_d_line_12 = federal_schedule_d_line_12_long_term_k1_gain(
        index
    )
    schedule_d_line_15 = federal_schedule_d_line_15_net_long_term_gain(
        schedule_d_line_10,
        schedule_d_line_11,
        schedule_d_line_12,
    )
    schedule_d_line_16 = federal_schedule_d_line_16_net_capital_gain(
        schedule_d_line_7,
        schedule_d_line_15,
    )
    line_5a_net_gain = federal_form_8960_line_5a_net_gain_loss_disposition(
        schedule_d_line_16
    )
    line_5d_net_gain = federal_form_8960_line_5d_net_gain_loss_disposition(
        line_5a_net_gain
    )
    line_8_total_investment_income = federal_form_8960_line_8_total_investment_income(
        line_1_taxable_interest,
        line_2_ordinary_dividends,
        line_4c_net_income_from_rentals=line_4c_net_income,
        line_5d_net_gain_loss_disposition=line_5d_net_gain,
    )
    line_9a_investment_interest_expense = federal_form_8960_line_9a_investment_interest_expense(
        index
    )
    line_9b_state_local_foreign_income_tax = federal_form_8960_line_9b_state_local_foreign_income_tax(
        index,
        policy,
    )
    line_9c_misc_investment_expenses = federal_form_8960_line_9c_misc_investment_expenses(
        index
    )
    line_9d_total_investment_expenses = federal_form_8960_line_9d_total_investment_expenses(
        line_9a_investment_interest_expense,
        line_9b_state_local_foreign_income_tax,
        line_9c_misc_investment_expenses,
    )
    line_11_total_deductions_and_modifications = (
        federal_form_8960_line_11_total_deductions_and_modifications(
            line_9d_total_investment_expenses
        )
    )
    line_12_net_investment_income = federal_form_8960_line_12_net_investment_income(
        line_8_total_investment_income,
        line_11_total_deductions_and_modifications,
    )
    # Form 1040 Line 1z: Wages
    line_1z_wages = federal_form_1040_line_1z_wages(index)

    # Form 1040 Line 9: Total income
    line_2b_taxable_interest = line_1_sched_b_interest
    line_3b_ordinary_dividends = line_6_sched_b_ordinary_dividends
    line_5b_pensions = federal_form_1040_line_5b_pensions_annuities(
        index
    )
    line_7_capital_gain_loss = schedule_d_line_16
    line_8_additional_income = line_10_schedule_1_additional_income
    line_9_total_income = federal_form_1040_line_9_total_income(
        line_1z_wages,
        line_2b_taxable_interest,
        line_3b_ordinary_dividends,
        line_5b_pensions,
        line_7_capital_gain_loss,
        line_8_additional_income,
    )

    # Form 1040 Line 11: Adjusted gross income
    line_11_agi_override = tag_total(index, 'form_1040_line_11_adjusted_gross_income')
    if line_11_agi_override != Decimal('0'):
        line_11_agi = round_to_dollars(
            line_11_agi_override
        )
    else:
        line_11_agi = federal_form_1040_line_11_adjusted_gross_income(
            line_9_total_income,
            line_26_adjustments,
        )

    # Form 1040 Line 3a: Qualified dividends
    line_3a_qualified_dividends = federal_form_1040_line_3a_qualified_dividends(
        index
    )

    # Form 1040 Lines 12, 14, 15: Deductions and taxable income
    line_12_deduction_override_items = tag_total(index, 'form_1040_line_12_deductions')
    line_12_deduction_override = None
    if line_12_deduction_override_items != Decimal('0'):
        # Schedule A line 5e SALT is formula-driven: min(line 5d, SALT cap).
        # Use the same capped state/local/foreign tax amount already computed for
        # Form 8960 line 9b to avoid hardcoding a return placeholder input.
        line_12_deduction_override = (
            line_12_deduction_override_items
            + line_9b_state_local_foreign_income_tax
        )
    line_12_standard_deduction = federal_form_1040_line_12_standard_deduction(
        policy,
        line_12_deduction_override=line_12_deduction_override,
    )
    line_13_qbi_direct = tag_total(index, 'form_1040_line_13_qbi_deduction')
    line_13_qbi_section_199a_dividends = tag_total(index, 'form_1099_div_box_5_section_199a_dividends')
    line_13_qbi_deduction = line_13_qbi_direct + round_to_dollars(
        line_13_qbi_section_199a_dividends * Decimal('0.20')
    )
    line_14_total_deductions = federal_form_1040_line_14_total_deductions(
        line_12_standard_deduction,
        line_13_qbi_deduction=line_13_qbi_deduction,
    )
    line_15_taxable_income = federal_form_1040_line_15_taxable_income(
        line_11_agi,
        line_14_total_deductions,
    )
    line_13_modified_agi = federal_form_8960_line_13_modified_adjusted_gross_income(line_11_agi)
    line_15_agi_over_threshold = federal_form_8960_line_15_modified_agi_over_threshold(
        line_13_modified_agi, policy
    )
    line_16_niit_base = federal_form_8960_line_16_smaller_of_line_12_or_15(
        line_12_net_investment_income, line_15_agi_over_threshold
    )
    line_17_niit = federal_form_8960_line_17_net_investment_income_tax(
        line_16_niit_base, policy
    )
    line_12_niit = federal_schedule_2_line_12_net_investment_income_tax(line_17_niit)

    # Schedule 2 Line 21: Other taxes
    line_21_other_taxes = federal_schedule_2_line_21_other_taxes(
        line_4_self_employment_tax=line_12_se_tax,
        line_11_additional_medicare_tax=line_11_add_medicare,
        line_12_net_investment_income_tax=line_12_niit,
    )

    # Form 1040 Line 23: Other taxes (pass-through)
    line_23_other_taxes = federal_1040_line_23_other_taxes(line_21_other_taxes)

    # Qualified dividends and capital gain tax worksheet (line 25)
    worksheet_line_25 = federal_form_1040_qualified_dividends_capital_gain_worksheet_line_25(
        line_1_taxable_income=line_15_taxable_income,
        line_2_qualified_dividends=line_3a_qualified_dividends,
        schedule_d_line_15=schedule_d_line_15,
        schedule_d_line_16=schedule_d_line_16,
        policy=policy,
    )

    # Form 1040 Line 16 and 18: Tax and amounts
    line_16_tax_input = tag_total(index, 'form_1040_line_16_tax')
    if line_16_tax_input != Decimal('0'):
        line_16_tax = federal_form_1040_line_16_tax(
            line_16_tax_input
        )
    else:
        line_16_tax = federal_form_1040_line_16_tax(worksheet_line_25)
    line_18_tax_and_amounts = federal_form_1040_line_18_tax_and_amounts(line_16_tax)

    # Form 1040 Lines 21 and 22: Credits and tax after credits
    line_19_child_tax_credit = tag_total(index, 'form_1040_line_19_child_tax_credit')
    line_20_schedule_3_line_8 = tag_total(index, 'form_1116_foreign_taxes_paid')
    line_21_total_credits = federal_form_1040_line_21_total_credits(
        line_19_child_tax_credit,
        line_20_schedule_3_line_8,
    )
    line_22_tax_after_credits = federal_form_1040_line_22_tax_after_credits(
        line_18_tax_and_amounts,
        line_21_total_credits,
    )

    # Form 1040 Line 24: Total tax (final result)
    total_tax = federal_1040_line_24_total_tax(line_22_tax_after_credits, line_23_other_taxes)

    _check_compute_line('federal.schedule_se.line_2_schedule_c_and_k1_profit', line_2_sched_c_k1)
    _check_compute_line('federal.schedule_se.line_6_total_se_earnings', line_6_se_earnings)
    _check_compute_line('federal.schedule_se.line_10_social_security_portion', line_10_ss_tax)
    _check_compute_line('federal.schedule_se.line_11_medicare_portion', line_11_medicare)
    _check_compute_line('federal.schedule_se.line_12_self_employment_tax', line_12_se_tax)

    _check_compute_line('federal.schedule_1.line_5_rental_real_estate_income', line_5_schedule_1_rental_income)
    _check_compute_line('federal.schedule_1.line_10_additional_income', line_10_schedule_1_additional_income)
    _check_compute_line('federal.schedule_1.line_15_deductible_self_employment_tax', line_15_deductible_se_tax)
    _check_compute_line('federal.schedule_1.line_16_self_employed_retirement_contributions', line_16_retirement)
    _check_compute_line('federal.schedule_1.line_17_self_employed_health_insurance', line_17_health_insurance)
    _check_compute_line('federal.schedule_1.line_26_adjustments_to_income', line_26_adjustments)

    _check_compute_line('federal.form_8959.line_18_additional_medicare_tax', line_11_add_medicare)

    _check_compute_line('federal.schedule_b.line_1_taxable_interest', line_1_sched_b_interest)
    _check_compute_line('federal.schedule_b.line_6_ordinary_dividends', line_6_sched_b_ordinary_dividends)

    _check_compute_line('federal.schedule_e.line_29a_total_nonpassive_income', line_29a_nonpassive_income)
    _check_compute_line('federal.schedule_e.line_29b_total_nonpassive_loss_allowed', line_29b_nonpassive_loss_allowed)
    _check_compute_line('federal.schedule_e.line_29b_total_section_179_deduction', line_29b_section_179_deduction)
    _check_compute_line('federal.schedule_e.line_30_total_income', line_30_total_income)
    _check_compute_line('federal.schedule_e.line_31_total_losses', line_31_total_losses)
    _check_compute_line('federal.schedule_e.line_32_total_partnership_income', line_32_total_partnership_income)

    _check_compute_line('federal.form_6781.line_7_total_gain_loss_1256', form_6781_line_7_total)
    _check_compute_line('federal.form_6781.line_8_short_term_portion', form_6781_line_8_short_term)
    _check_compute_line('federal.form_6781.line_9_long_term_portion', form_6781_line_9_long_term)

    _check_compute_line('federal.schedule_d.line_1a_short_term_gain', schedule_d_line_1a)
    _check_compute_line('federal.schedule_d.line_3_short_term_section_1061_adjustment', schedule_d_line_3)
    _check_compute_line('federal.schedule_d.line_4_short_term_from_6781', schedule_d_line_4)
    _check_compute_line('federal.schedule_d.line_5_short_term_k1_gain', schedule_d_line_5)
    _check_compute_line('federal.schedule_d.line_7_net_short_term_gain', schedule_d_line_7)
    _check_compute_line('federal.schedule_d.line_10_long_term_section_1061_adjustment', schedule_d_line_10)
    _check_compute_line('federal.schedule_d.line_11_long_term_from_6781_and_4797', schedule_d_line_11)
    _check_compute_line('federal.schedule_d.line_12_long_term_k1_gain', schedule_d_line_12)
    _check_compute_line('federal.schedule_d.line_15_net_long_term_gain', schedule_d_line_15)
    _check_compute_line('federal.schedule_d.line_16_net_capital_gain', schedule_d_line_16)

    _check_compute_line('federal.form_8960.line_1_taxable_interest', line_1_taxable_interest)
    _check_compute_line('federal.form_8960.line_2_ordinary_dividends', line_2_ordinary_dividends)
    _check_compute_line('federal.form_8960.line_4a_rental_real_estate_royalties_partnerships', line_4a_rentals_partnerships)
    _check_compute_line('federal.form_8960.line_4b_adjustment_nonsection_1411', line_4b_adjustment)
    _check_compute_line('federal.form_8960.line_4c_net_income_from_rentals', line_4c_net_income)
    _check_compute_line('federal.form_8960.line_5a_net_gain_loss_disposition', line_5a_net_gain)
    _check_compute_line('federal.form_8960.line_5d_net_gain_loss_disposition', line_5d_net_gain)
    _check_compute_line('federal.form_8960.line_8_total_investment_income', line_8_total_investment_income)
    _check_compute_line('federal.form_8960.line_9a_investment_interest_expense', line_9a_investment_interest_expense)
    _check_compute_line('federal.form_8960.line_9b_state_local_foreign_income_tax', line_9b_state_local_foreign_income_tax)
    _check_compute_line('federal.form_8960.line_9c_misc_investment_expenses', line_9c_misc_investment_expenses)
    _check_compute_line('federal.form_8960.line_12_net_investment_income', line_12_net_investment_income)
    _check_compute_line('federal.form_8960.line_13_modified_adjusted_gross_income', line_13_modified_agi)
    _check_compute_line('federal.form_8960.line_15_modified_agi_over_threshold', line_15_agi_over_threshold)
    _check_compute_line('federal.form_8960.line_16_smaller_of_line_12_or_15', line_16_niit_base)
    _check_compute_line('federal.form_8960.line_17_net_investment_income_tax', line_17_niit)

    _check_compute_line('federal.schedule_2.line_12_net_investment_income_tax', line_12_niit)
    _check_compute_line('federal.schedule_2.line_21_other_taxes', line_21_other_taxes)

    _check_compute_line('federal.form_1040.line_1z_wages', line_1z_wages)
    _check_compute_line('federal.form_1040.line_3a_qualified_dividends', line_3a_qualified_dividends)
    _check_compute_line('federal.form_1040.line_5b_pensions_annuities', line_5b_pensions)
    _check_compute_line('federal.form_1040.line_9_total_income', line_9_total_income)
    _check_compute_line('federal.form_1040.line_10_adjustments_to_income', line_26_adjustments)
    _check_compute_line('federal.form_1040.line_11_adjusted_gross_income', line_11_agi)
    _check_compute_line('federal.form_1040.line_12_standard_deduction', line_12_standard_deduction)
    _check_compute_line('federal.form_1040.line_14_total_deductions', line_14_total_deductions)
    _check_compute_line('federal.form_1040.line_15_taxable_income', line_15_taxable_income)
    _check_compute_line('federal.form_1040_qualified_dividends_capital_gain_worksheet.line_25_tax_on_all_income', worksheet_line_25)
    _check_compute_line('federal.form_1040.line_16_tax', line_16_tax)
    _check_compute_line('federal.form_1040.line_18_tax_and_amounts', line_18_tax_and_amounts)
    _check_compute_line('federal.form_1040.line_21_total_credits', line_21_total_credits)
    _check_compute_line('federal.form_1040.line_22_tax_after_credits', line_22_tax_after_credits)
    _check_compute_line('federal.form_1040.line_23_other_taxes', line_23_other_taxes)
    _check_compute_line('federal.form_1040.line_24_total_tax', total_tax)
    _check_compute_line('federal.compute_total_tax', total_tax)

    return total_tax


def compute_ny_total_tax(inputs: dict, policy: dict) -> Decimal:
    """
    Compute the complete NY total tax from raw inputs.

    This top-level function orchestrates all the NY calculation steps,
    computing intermediate values in the correct order and returning
    the final total tax (IT-201, line 62).

    Form/Line: NY IT-201, line 62 (final result)

    Args:
        inputs: Input data dict containing all factual values
        policy: Policy configuration dict containing tax law parameters

    Returns:
        Total NY tax amount (IT-201 line 62)
    """
    index = build_inputs_index(inputs)
    # === Federal intermediates needed by NY ===

    # K-1 inputs
    k1_box_14a = tag_total(index, 'schedule_se_k1_box_14a_self_employment_earnings', required=True)
    k1_box_12 = tag_total(index, 'section_179_deduction', required=True)

    # Schedule SE
    line_2_sched_c_k1 = federal_schedule_se_line_2_schedule_c_and_k1_profit(
        k1_box_14a, k1_box_12
    )
    line_6_se_earnings = federal_schedule_se_line_6_total_se_earnings(
        line_2_sched_c_k1, policy
    )
    line_10_ss_tax = federal_schedule_se_line_10_social_security_tax(
        line_6_se_earnings, policy
    )
    line_11_medicare = federal_schedule_se_line_11_medicare_tax(
        line_6_se_earnings, policy
    )
    line_12_se_tax = federal_schedule_se_line_12_self_employment_tax(
        line_10_ss_tax, line_11_medicare
    )

    # Schedule 1 adjustments
    line_15_deductible_se_tax = federal_schedule_1_line_15_deductible_self_employment_tax(
        line_12_se_tax
    )
    line_16_retirement = federal_schedule_1_line_16_self_employed_retirement_contributions(
        index
    )
    line_17_health_insurance = federal_schedule_1_line_17_self_employed_health_insurance(
        index
    )
    line_26_adjustments = federal_schedule_1_line_26_adjustments_to_income(
        line_15_deductible_se_tax,
        line_16_retirement,
        line_17_health_insurance,
    )

    # Schedule B, Schedule D, Schedule E, Schedule 1 income
    line_1_sched_b_interest = federal_schedule_b_line_1_taxable_interest(
        index
    )
    line_6_sched_b_ordinary_dividends = federal_schedule_b_line_6_ordinary_dividends(
        index
    )
    line_29a_nonpassive_income = federal_schedule_e_line_29a_total_nonpassive_income(
        index
    )
    line_29b_nonpassive_loss_allowed = federal_schedule_e_line_29b_total_nonpassive_loss_allowed(
        index
    )
    line_29b_section_179_deduction = federal_schedule_e_line_29b_total_section_179_deduction(
        index
    )
    line_30_total_income = federal_schedule_e_line_30_total_income(
        line_29a_nonpassive_income
    )
    line_31_total_losses = federal_schedule_e_line_31_total_losses(
        line_29b_nonpassive_loss_allowed,
        line_29b_section_179_deduction=line_29b_section_179_deduction,
    )
    line_32_total_partnership_income = federal_schedule_e_line_32_total_partnership_income(
        line_30_total_income,
        line_31_total_losses,
    )
    line_5_schedule_1_rental_income = federal_schedule_1_line_5_rental_real_estate_income(
        line_32_total_partnership_income
    )
    line_10_schedule_1_additional_income = federal_schedule_1_line_10_additional_income(
        line_5_schedule_1_rental_income
    )

    # Schedule D
    form_6781_line_7_total = federal_form_6781_line_7_total_gain_loss_1256(
        index
    )
    form_6781_line_8_short_term = federal_form_6781_line_8_short_term_portion(
        form_6781_line_7_total, policy
    )
    form_6781_line_9_long_term = federal_form_6781_line_9_long_term_portion(
        form_6781_line_7_total, policy
    )
    schedule_d_line_1a = federal_schedule_d_line_1a_short_term_gain(
        index,
    )
    schedule_d_line_3 = federal_schedule_d_line_3_short_term_section_1061_adjustment(
        index
    )
    schedule_d_line_4 = federal_schedule_d_line_4_short_term_from_6781(
        form_6781_line_8_short_term
    )
    schedule_d_line_5 = federal_schedule_d_line_5_short_term_k1_gain(
        index
    )
    schedule_d_line_7 = federal_schedule_d_line_7_net_short_term_gain(
        schedule_d_line_1a,
        schedule_d_line_3,
        schedule_d_line_4,
        schedule_d_line_5,
    )
    schedule_d_line_10 = federal_schedule_d_line_10_long_term_section_1061_adjustment(
        index
    )
    schedule_d_line_11 = federal_schedule_d_line_11_long_term_from_6781_and_4797(
        form_6781_line_9_long_term,
        index,
    )
    schedule_d_line_12 = federal_schedule_d_line_12_long_term_k1_gain(
        index
    )
    schedule_d_line_15 = federal_schedule_d_line_15_net_long_term_gain(
        schedule_d_line_10,
        schedule_d_line_11,
        schedule_d_line_12,
    )
    schedule_d_line_16 = federal_schedule_d_line_16_net_capital_gain(
        schedule_d_line_7,
        schedule_d_line_15,
    )

    # Form 1040 total income
    line_1z_wages = federal_form_1040_line_1z_wages(index)
    line_5b_pensions = federal_form_1040_line_5b_pensions_annuities(
        index
    )
    line_9_total_income = federal_form_1040_line_9_total_income(
        line_1z_wages,
        line_1_sched_b_interest,
        line_6_sched_b_ordinary_dividends,
        line_5b_pensions,
        schedule_d_line_16,
        line_10_schedule_1_additional_income,
    )

    # === NY computation chain ===

    # IT-201 Lines 17-19: Federal income → NY AGI
    it201_line_17 = ny_it201_line_17_total_federal_income(line_9_total_income)
    it201_line_18 = ny_it201_line_18_federal_adjustments(line_26_adjustments)
    it201_line_19 = ny_it201_line_19_federal_agi(it201_line_17, it201_line_18)

    # IT-225: NY additions
    it225_line_1a_items = [{'amount': str(tag_total(index, 'ny_it_201_att_line_12_amount'))}]
    it225_line_1a = ny_it225_line_1a_additions(it225_line_1a_items)
    it225_line_2 = ny_it225_line_2_total_part1_additions(it225_line_1a)
    it225_line_4 = ny_it225_line_4_total_part1_additions(it225_line_2)

    it225_line_5a_items = [{'amount': str(tag_total(index, 'ny_it_225_line_5a_addition'))}]
    it225_line_5a = ny_it225_line_5a_additions(it225_line_5a_items)
    it225_line_5b_items = [{'amount': str(tag_total(index, 'ny_it_225_line_5b_addition'))}]
    it225_line_5b = ny_it225_line_5b_additions(it225_line_5b_items)
    it225_line_6 = ny_it225_line_6_total_part2_additions(it225_line_5a, it225_line_5b)
    it225_line_8 = ny_it225_line_8_total_part2_additions(it225_line_6)
    it225_line_9 = ny_it225_line_9_total_additions(it225_line_4, it225_line_8)

    # IT-201 Lines 23-38: NY income → NY taxable income
    it201_line_23 = ny_it201_line_23_other_additions(it225_line_9)
    it201_line_21 = tag_total(index, 'ny_it_201_line_21_public_employee_414h')
    it201_line_22 = tag_total(index, 'ny_it_201_line_22_ny_529_distributions')
    it201_line_24 = ny_it201_line_24_ny_total_income(
        it201_line_19,
        line_21_public_employee_414h=it201_line_21,
        line_22_ny_529_distributions=it201_line_22,
        line_23_other_additions=it201_line_23,
    )

    # Subtractions
    line_28_items = []
    for fund in policy.get('ny_us_gov_bond_interest_percentages', {}):
        fund_total = tag_total(
            index, f'ny_it_201_line_28_us_gov_bond_interest_items_{fund}'
        )
        line_28_items.append({'fund': fund, 'amount': fund_total})
    it201_line_28 = ny_it201_line_28_us_gov_bond_interest(line_28_items, policy)
    it201_line_32 = ny_it201_line_32_ny_total_subtractions(it201_line_28)
    it201_line_33 = ny_it201_line_33_ny_adjusted_gross_income(it201_line_24, it201_line_32)
    it201_line_34 = ny_it201_line_34_standard_deduction(policy)
    it201_line_35 = ny_it201_line_35_ny_taxable_income_before_exemptions(
        it201_line_33, it201_line_34
    )
    dependents_count = tag_total(index, 'ny_dependents_count', required=True)
    it201_line_36 = ny_it201_line_36_dependent_exemptions(dependents_count, policy)
    it201_line_38 = ny_it201_line_38_ny_taxable_income(it201_line_35, it201_line_36)

    # === NYS tax (line 39-46) ===
    stmt2_line_3 = ny_it201_statement_2_line_3_tax_from_rate_schedule(
        it201_line_38, policy
    )
    stmt2_line_4 = ny_it201_statement_2_line_4_recapture_base_amount(policy)
    stmt2_line_9 = ny_it201_statement_2_line_9_incremental_benefit_addback(policy)
    it201_line_39 = ny_it201_line_39_nys_tax_on_line_38(
        stmt2_line_3, stmt2_line_4, stmt2_line_9
    )

    # IT-112-R: Resident credit
    it112r_line_22_total = ny_it112r_line_22_total_income(it201_line_33)
    it112r_line_22_other_state_items = [{'amount': str(tag_total(index, 'ny_it_112_r_line_22_other_state_income'))}]
    it112r_line_22_other = ny_it112r_line_22_other_state_income(
        it112r_line_22_other_state_items
    )
    it112r_line_24_items = [{'amount': str(tag_total(index, 'ny_it_112_r_line_24_other_state_tax'))}]
    it112r_line_24 = ny_it112r_line_24_total_other_state_tax(it112r_line_24_items)
    it112r_line_26 = ny_it112r_line_26_ratio(it112r_line_22_total, it112r_line_22_other)
    it112r_line_27 = ny_it112r_line_27_ny_tax_times_ratio(it201_line_39, it112r_line_26)
    it112r_line_28 = ny_it112r_line_28_smaller_of_line24_or_27(
        it112r_line_24, it112r_line_27
    )
    it112r_line_30 = ny_it112r_line_30_total_credit(it112r_line_28)
    it112r_line_34 = ny_it112r_line_34_resident_credit(it112r_line_30, it201_line_39)

    it201_line_41 = ny_it201_line_41_resident_credit(it112r_line_34)
    it201_line_43 = ny_it201_line_43_nys_credits_total(it201_line_41)
    it201_line_44 = ny_it201_line_44_ny_state_tax_after_credits(
        it201_line_39, it201_line_43
    )
    it201_line_46 = ny_it201_line_46_total_ny_state_taxes(it201_line_44)

    # === NYC tax (lines 47-54) ===
    it201_line_47 = ny_it201_line_47_nyc_taxable_income(it201_line_38)
    it201_line_47a = ny_it201_line_47a_nyc_resident_tax(
        it201_line_47, policy
    )
    it201_line_49 = ny_it201_line_49_nyc_tax_after_household_credit(it201_line_47a)

    # IT-219: UBT credit
    ubt_credit_items = [{'amount': str(tag_total(index, 'ny_it_219_line_7_ubt_credit'))}]
    it219_line_7 = ny_it219_line_7_beneficiary_ubt_credit(ubt_credit_items)
    it219_line_8 = ny_it219_line_8_total_ubt_credit(it219_line_7)
    it219_line_9 = ny_it219_line_9_taxable_income(it201_line_47)
    it219_line_10 = ny_it219_line_10_income_factor(it219_line_9, policy)
    it219_line_11 = ny_it219_line_11_income_based_credit(it219_line_8, it219_line_10)
    it219_line_15 = ny_it219_line_15_total_tax(it201_line_49)
    it219_line_16 = ny_it219_line_16_resident_ubt_credit(it219_line_11, it219_line_15)

    # NYC credits and final NYC tax
    att_line_8 = ny_it201_att_line_8_nyc_resident_ubt_credit(it219_line_16)
    att_line_10 = ny_it201_att_line_10_total_nyc_nonrefundable_credits(att_line_8)
    it201_line_53 = ny_it201_line_53_nyc_nonrefundable_credits(att_line_10)
    it201_line_52 = ny_it201_line_52_nyc_tax_before_credits(it201_line_49)
    it201_line_54 = ny_it201_line_54_nyc_tax_after_credits(it201_line_52, it201_line_53)

    # === MCTMT (lines 54a-54e) ===
    mctmt_items = [
        {
            'ordinary_business_income': tag_total(index, 'mctmt_base_ordinary_income', required=True),
            'guaranteed_payments_services': tag_total(index, 'mctmt_base_guaranteed_payments', required=True),
        }
    ]
    worksheet_4a_line_1 = ny_it2105_9_worksheet_4a_line_1_net_earnings_zone_1(
        mctmt_items, policy
    )
    it201_line_54a = ny_it201_line_54a_mctmt_net_earnings_zone_1(worksheet_4a_line_1)
    it201_line_54c = ny_it201_line_54c_mctmt_zone_1(it201_line_54a, policy)
    it201_line_54e = ny_it201_line_54e_mctmt_total(it201_line_54c)

    # === Total NY taxes ===
    it201_line_58 = ny_it201_line_58_total_nyc_yonkers_mctmt(it201_line_54, it201_line_54e)
    it201_line_61 = ny_it201_line_61_total_taxes(it201_line_46, it201_line_58)
    it201_line_62 = ny_it201_line_62_total_taxes(it201_line_61)

    _check_compute_line('ny.it_201.line_17_total_federal_income', it201_line_17)
    _check_compute_line('ny.it_201.line_18_federal_adjustments', it201_line_18)
    _check_compute_line('ny.it_201.line_19_federal_agi', it201_line_19)
    _check_compute_line('ny.it_225.line_1a_additions', it225_line_1a)
    _check_compute_line('ny.it_225.line_2_total_part1_additions', it225_line_2)
    _check_compute_line('ny.it_225.line_4_total_part1_additions', it225_line_4)
    _check_compute_line('ny.it_225.line_5a_additions', it225_line_5a)
    _check_compute_line('ny.it_225.line_5b_additions', it225_line_5b)
    _check_compute_line('ny.it_225.line_6_total_part2_additions', it225_line_6)
    _check_compute_line('ny.it_225.line_8_total_part2_additions', it225_line_8)
    _check_compute_line('ny.it_225.line_9_total_additions', it225_line_9)
    _check_compute_line('ny.it_201.line_23_other_additions', it201_line_23)
    _check_compute_line('ny.it_201.line_24_ny_total_income', it201_line_24)
    _check_compute_line('ny.it_201.line_28_us_gov_bond_interest', it201_line_28)
    _check_compute_line('ny.it_201.line_32_ny_total_subtractions', it201_line_32)
    _check_compute_line('ny.it_201.line_33_ny_adjusted_gross_income', it201_line_33)
    _check_compute_line('ny.it_201.line_34_standard_deduction', it201_line_34)
    _check_compute_line('ny.it_201.line_35_ny_taxable_income_before_exemptions', it201_line_35)
    _check_compute_line('ny.it_201.line_36_dependent_exemptions', it201_line_36)
    _check_compute_line('ny.it_201.line_38_ny_taxable_income', it201_line_38)
    _check_compute_line('ny.it_201.statement_2_tax_computation_worksheet_4.line_3_tax_from_rate_schedule', stmt2_line_3)
    _check_compute_line('ny.it_201.statement_2_tax_computation_worksheet_4.line_4_recapture_base_amount', stmt2_line_4)
    _check_compute_line('ny.it_201.statement_2_tax_computation_worksheet_4.line_9_incremental_benefit_addback', stmt2_line_9)
    _check_compute_line('ny.it_201.line_39_nys_tax_on_line_38', it201_line_39)
    _check_compute_line('ny.it_112_r.line_22_total_income', it112r_line_22_total)
    _check_compute_line('ny.it_112_r.line_22_other_state_income', it112r_line_22_other)
    _check_compute_line('ny.it_112_r.line_24_total_other_state_tax', it112r_line_24)
    _check_compute_line('ny.it_112_r.line_26_ratio', it112r_line_26)
    _check_compute_line('ny.it_112_r.line_27_ny_tax_times_ratio', it112r_line_27)
    _check_compute_line('ny.it_112_r.line_28_smaller_of_line24_or_27', it112r_line_28)
    _check_compute_line('ny.it_112_r.line_30_total_credit', it112r_line_30)
    _check_compute_line('ny.it_112_r.line_34_resident_credit', it112r_line_34)
    _check_compute_line('ny.it_201.line_41_resident_credit', it201_line_41)
    _check_compute_line('ny.it_201.line_43_nys_credits_total', it201_line_43)
    _check_compute_line('ny.it_201.line_44_ny_state_tax_after_credits', it201_line_44)
    _check_compute_line('ny.it_201.line_46_total_ny_state_taxes', it201_line_46)
    _check_compute_line('ny.it_201.line_47_nyc_taxable_income', it201_line_47)
    _check_compute_line('ny.it_201.line_47a_nyc_resident_tax', it201_line_47a)
    _check_compute_line('ny.it_201.line_49_nyc_tax_after_household_credit', it201_line_49)
    _check_compute_line('ny.it_219.line_7_beneficiary_ubt_credit', it219_line_7)
    _check_compute_line('ny.it_219.line_8_total_ubt_credit', it219_line_8)
    _check_compute_line('ny.it_219.line_9_taxable_income', it219_line_9)
    _check_compute_line('ny.it_219.line_10_income_factor', it219_line_10)
    _check_compute_line('ny.it_219.line_11_income_based_credit', it219_line_11)
    _check_compute_line('ny.it_219.line_15_total_tax', it219_line_15)
    _check_compute_line('ny.it_219.line_16_resident_ubt_credit', it219_line_16)
    _check_compute_line('ny.it_201_att.line_8_nyc_resident_ubt_credit', att_line_8)
    _check_compute_line('ny.it_201_att.line_10_total_nyc_nonrefundable_credits', att_line_10)
    _check_compute_line('ny.it_201.line_52_nyc_tax_before_credits', it201_line_52)
    _check_compute_line('ny.it_201.line_53_nyc_nonrefundable_credits', it201_line_53)
    _check_compute_line('ny.it_201.line_54_nyc_tax_after_credits', it201_line_54)
    _check_compute_line('ny.it_2105_9.worksheet_4a_line_1_net_earnings_zone_1', worksheet_4a_line_1)
    _check_compute_line('ny.it_201.line_54a_mctmt_net_earnings_zone_1', it201_line_54a)
    _check_compute_line('ny.it_201.line_54c_mctmt_zone_1', it201_line_54c)
    _check_compute_line('ny.it_201.line_54e_mctmt_total', it201_line_54e)
    _check_compute_line('ny.it_201.line_58_total_nyc_yonkers_mctmt', it201_line_58)
    _check_compute_line('ny.it_201.line_61_total_taxes', it201_line_61)
    _check_compute_line('ny.it_201.line_62_total_taxes', it201_line_62)
    _check_compute_line('ny.compute_total_tax', it201_line_62)

    return it201_line_62


def compute_all_taxes(inputs: dict, policy: dict) -> dict:
    """
    Compute federal and NY total taxes from raw inputs.

    Returns:
        Dict with 'federal', 'ny', and 'total' keys.
    """
    federal = compute_federal_total_tax(inputs, policy)
    ny = compute_ny_total_tax(inputs, policy)
    return {
        'federal': federal,
        'ny': ny,
        'total': federal + ny,
    }


def _marginal_state_totals() -> dict:
    return {
        'NY': compute_ny_total_tax,
    }


def _compute_marginals(plus_inputs: dict, minus_inputs: dict, policy: dict, delta: Decimal) -> tuple:
    state_totals = _marginal_state_totals()

    federal_plus = compute_federal_total_tax(plus_inputs, policy)
    federal_minus = compute_federal_total_tax(minus_inputs, policy)
    marginal_federal = (federal_plus - federal_minus) / (delta * 2)

    state_marginals = []
    for state, func in state_totals.items():
        state_plus = func(plus_inputs, policy)
        state_minus = func(minus_inputs, policy)
        state_marginals.append((state_plus - state_minus) / (delta * 2))

    marginal_total = marginal_federal + sum(state_marginals, Decimal('0'))
    return marginal_federal, state_marginals, marginal_total


def marginal_rate_table_by_input(inputs: dict, policy: dict, delta: Decimal = Decimal('1000')) -> str:
    """
    Compute marginal tax rates by input item using numerical differentiation.
    """
    import copy
    from pathlib import Path

    if delta <= 0:
        raise ValueError('delta must be positive')

    state_totals = _marginal_state_totals()
    headers = ['Source', 'Path', 'Tags', 'Explanation', 'Amount', 'Marginal Federal']
    headers.extend([f'Marginal {state}' for state in state_totals])
    headers.append('Marginal Total')
    lines = ['|'.join(headers)]

    for source, items in inputs.items():
        if not isinstance(items, list):
            continue
        source_filename = Path(source).name
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            path = str(item.get('Path', '')).strip()
            tags = ' - '.join(item.get('Tags', []))
            explanation = str(item.get('Explanation', ''))
            amount_str = str(item.get('Amount', ''))

            try:
                amount = Decimal(amount_str)
            except Exception:
                row = [source_filename, path, tags, explanation, amount_str, '']
                row.extend([''] * len(state_totals))
                row.append('')
                lines.append('|'.join(row))
                continue

            plus_inputs = copy.deepcopy(inputs)
            minus_inputs = copy.deepcopy(inputs)
            plus_inputs[source][i]['Amount'] = str(amount + delta)
            minus_inputs[source][i]['Amount'] = str(amount - delta)

            marginal_federal, state_marginals, marginal_total = _compute_marginals(
                plus_inputs, minus_inputs, policy, delta
            )

            row = [
                source_filename,
                path,
                tags,
                explanation,
                amount_str,
                str(marginal_federal),
            ]
            row.extend(str(value) for value in state_marginals)
            row.append(str(marginal_total))
            lines.append('|'.join(row))

    return '\n'.join(lines)


def marginal_rate_table_by_tag(inputs: dict, policy: dict, delta: Decimal = Decimal('1000')) -> str:
    """
    Compute marginal tax rates by tag using numerical differentiation.
    """
    import copy
    from pathlib import Path

    if delta <= 0:
        raise ValueError('delta must be positive')

    state_totals = _marginal_state_totals()
    headers = ['Tag', 'Num Inputs', 'Sources+Paths', 'Amount', 'Marginal Federal']
    headers.extend([f'Marginal {state}' for state in state_totals])
    headers.append('Marginal Total')
    lines = ['|'.join(headers)]

    tagged_items: dict[str, list[dict]] = defaultdict(list)
    for source, items in inputs.items():
        if not isinstance(items, list):
            continue
        source_filename = Path(source).name
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            for tag in item.get('Tags', []):
                tagged_items[tag].append(
                    {
                        'source': source,
                        'index': i,
                        'item': item,
                        'source_filename': source_filename,
                    }
                )

    for tag in sorted(tagged_items.keys()):
        records = tagged_items[tag]
        num_inputs = len(records)
        source_path_parts = []
        numeric_records = []
        total_amount = Decimal('0')

        for record in records:
            item = record['item']
            path = str(item.get('Path', '')).strip()
            source_and_path = (
                record['source_filename'] if not path else f"{record['source_filename']}: {path}"
            )
            source_path_parts.append(source_and_path)

            try:
                amount = Decimal(str(item.get('Amount')))
            except Exception:
                continue
            numeric_records.append(record)
            total_amount += amount

        sources_paths = ' - '.join(source_path_parts)

        if not numeric_records:
            row = [tag, str(num_inputs), sources_paths, str(total_amount), '']
            row.extend([''] * len(state_totals))
            row.append('')
            lines.append('|'.join(row))
            continue

        plus_inputs = copy.deepcopy(inputs)
        minus_inputs = copy.deepcopy(inputs)

        # Shock only the target tag via a synthetic one-tag row so we do not
        # perturb amounts tied to other tags on shared input rows.
        shock_source = '__MARGINAL_SHOCK__'
        while shock_source in plus_inputs or shock_source in minus_inputs:
            shock_source += '_X'
        plus_inputs[shock_source] = [
            {
                'Tags': [tag],
                'Amount': str(delta),
                'Path': 'Synthetic marginal shock (+delta)',
                'Explanation': 'Synthetic row for tag marginal calculation',
            }
        ]
        minus_inputs[shock_source] = [
            {
                'Tags': [tag],
                'Amount': str(-delta),
                'Path': 'Synthetic marginal shock (-delta)',
                'Explanation': 'Synthetic row for tag marginal calculation',
            }
        ]

        marginal_federal, state_marginals, marginal_total = _compute_marginals(
            plus_inputs, minus_inputs, policy, delta
        )

        row = [tag, str(num_inputs), sources_paths, str(total_amount), str(marginal_federal)]
        row.extend(str(value) for value in state_marginals)
        row.append(str(marginal_total))
        lines.append('|'.join(row))

    return '\n'.join(lines)


def marginal_rate_table(inputs: dict, policy: dict, delta: Decimal = Decimal('1000')) -> str:
    """
    Backward-compatible default: marginal table by tag.
    """
    return marginal_rate_table_by_tag(inputs, policy, delta)
