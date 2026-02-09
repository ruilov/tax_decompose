"""
Tests for tax calculations across supported tax years.
"""

import json
from decimal import Decimal
from pathlib import Path
import sys

import pytest

BASE_DIR = Path(__file__).resolve().parent
PRIVATE_DIR = BASE_DIR.parent / 'private'
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from tax import (
    build_inputs_index,
    tag_total,
    federal_schedule_se_line_2_schedule_c_and_k1_profit,
    federal_schedule_se_line_6_total_se_earnings,
    federal_schedule_se_line_10_social_security_tax,
    federal_schedule_se_line_11_medicare_tax,
    federal_schedule_se_line_12_self_employment_tax,
    federal_form_8959_line_18_additional_medicare_tax,
    federal_schedule_b_line_1_taxable_interest,
    federal_schedule_b_line_6_ordinary_dividends,
    federal_schedule_e_line_29a_total_nonpassive_income,
    federal_schedule_e_line_29b_total_nonpassive_loss_allowed,
    federal_schedule_e_line_29b_total_section_179_deduction,
    federal_schedule_e_line_30_total_income,
    federal_schedule_e_line_31_total_losses,
    federal_schedule_e_line_32_total_partnership_income,
    federal_schedule_1_line_5_rental_real_estate_income,
    federal_schedule_1_line_10_additional_income,
    federal_schedule_1_line_15_deductible_self_employment_tax,
    federal_schedule_1_line_16_self_employed_retirement_contributions,
    federal_schedule_1_line_17_self_employed_health_insurance,
    federal_schedule_1_line_26_adjustments_to_income,
    federal_form_6781_line_7_total_gain_loss_1256,
    federal_form_6781_line_8_short_term_portion,
    federal_form_6781_line_9_long_term_portion,
    federal_schedule_d_line_1a_short_term_gain,
    federal_schedule_d_line_3_short_term_section_1061_adjustment,
    federal_schedule_d_line_4_short_term_from_6781,
    federal_schedule_d_line_5_short_term_k1_gain,
    federal_schedule_d_line_7_net_short_term_gain,
    federal_schedule_d_line_10_long_term_section_1061_adjustment,
    federal_schedule_d_line_11_long_term_from_6781_and_4797,
    federal_schedule_d_line_12_long_term_k1_gain,
    federal_schedule_d_line_15_net_long_term_gain,
    federal_schedule_d_line_16_net_capital_gain,
    federal_form_8960_line_1_taxable_interest,
    federal_form_8960_line_2_ordinary_dividends,
    federal_form_8960_line_4a_rental_real_estate_royalties_partnerships,
    federal_form_8960_line_4b_adjustment_nonsection_1411,
    federal_form_8960_line_4c_net_income_from_rentals,
    federal_form_8960_line_5a_net_gain_loss_disposition,
    federal_form_8960_line_5d_net_gain_loss_disposition,
    federal_form_8960_line_8_total_investment_income,
    federal_form_8960_line_9a_investment_interest_expense,
    federal_form_8960_line_9b_state_local_foreign_income_tax,
    federal_form_8960_line_9c_misc_investment_expenses,
    federal_form_8960_line_12_net_investment_income,
    federal_form_8960_line_9d_total_investment_expenses,
    federal_form_8960_line_11_total_deductions_and_modifications,
    federal_form_8960_line_13_modified_adjusted_gross_income,
    federal_form_8960_line_15_modified_agi_over_threshold,
    federal_form_8960_line_16_smaller_of_line_12_or_15,
    federal_form_8960_line_17_net_investment_income_tax,
    federal_form_1040_line_1z_wages,
    federal_form_1040_line_3a_qualified_dividends,
    federal_form_1040_line_5b_pensions_annuities,
    federal_form_1040_line_9_total_income,
    federal_form_1040_line_11_adjusted_gross_income,
    federal_form_1040_line_12_standard_deduction,
    federal_form_1040_line_14_total_deductions,
    federal_form_1040_line_15_taxable_income,
    federal_form_1040_qualified_dividends_capital_gain_worksheet_line_22_tax_on_line_5,
    federal_form_1040_qualified_dividends_capital_gain_worksheet_line_24_tax_on_line_1,
    federal_form_1040_qualified_dividends_capital_gain_worksheet_line_25,
    federal_form_1040_line_16_tax,
    federal_form_1040_line_18_tax_and_amounts,
    federal_form_1040_line_21_total_credits,
    federal_form_1040_line_22_tax_after_credits,
    federal_schedule_2_line_12_net_investment_income_tax,
    federal_schedule_2_line_21_other_taxes,
    federal_1040_line_23_other_taxes,
    federal_1040_line_24_total_tax,
    ny_it201_line_39_nys_tax_on_line_38,
    ny_it201_line_38_ny_taxable_income,
    ny_it201_line_35_ny_taxable_income_before_exemptions,
    ny_it201_line_33_ny_adjusted_gross_income,
    ny_it201_line_28_us_gov_bond_interest,
    ny_it201_line_32_ny_total_subtractions,
    ny_it201_line_17_total_federal_income,
    ny_it201_line_18_federal_adjustments,
    ny_it201_line_19_federal_agi,
    ny_it201_statement_2_line_3_tax_from_rate_schedule,
    ny_it201_statement_2_line_4_recapture_base_amount,
    ny_it201_statement_2_line_9_incremental_benefit_addback,
    ny_it201_line_24_ny_total_income,
    ny_it201_line_23_other_additions,
    ny_it225_line_1a_additions,
    ny_it225_line_5a_additions,
    ny_it225_line_5b_additions,
    ny_it225_line_2_total_part1_additions,
    ny_it225_line_4_total_part1_additions,
    ny_it225_line_6_total_part2_additions,
    ny_it225_line_8_total_part2_additions,
    ny_it225_line_9_total_additions,
    ny_it201_line_34_standard_deduction,
    ny_it201_line_36_dependent_exemptions,
    ny_it201_line_41_resident_credit,
    ny_it201_line_43_nys_credits_total,
    ny_it201_line_44_ny_state_tax_after_credits,
    ny_it201_line_46_total_ny_state_taxes,
    ny_it112r_line_22_total_income,
    ny_it112r_line_22_other_state_income,
    ny_it112r_line_24_total_other_state_tax,
    ny_it112r_line_26_ratio,
    ny_it112r_line_27_ny_tax_times_ratio,
    ny_it112r_line_28_smaller_of_line24_or_27,
    ny_it112r_line_30_total_credit,
    ny_it112r_line_34_resident_credit,
    ny_it201_line_47_nyc_taxable_income,
    ny_it201_line_47a_nyc_resident_tax,
    ny_it201_line_49_nyc_tax_after_household_credit,
    ny_it201_line_52_nyc_tax_before_credits,
    ny_it201_line_54_nyc_tax_after_credits,
    ny_it219_line_7_beneficiary_ubt_credit,
    ny_it219_line_8_total_ubt_credit,
    ny_it219_line_9_taxable_income,
    ny_it219_line_10_income_factor,
    ny_it219_line_11_income_based_credit,
    ny_it219_line_15_total_tax,
    ny_it219_line_16_resident_ubt_credit,
    ny_it201_att_line_8_nyc_resident_ubt_credit,
    ny_it201_line_54c_mctmt_zone_1,
    ny_it201_line_54e_mctmt_total,
    ny_it201_line_58_total_nyc_yonkers_mctmt,
    ny_it201_line_61_total_taxes,
    ny_it201_line_62_total_taxes,
    ny_it2105_9_worksheet_4a_line_1_net_earnings_zone_1,
    ny_it201_line_54a_mctmt_net_earnings_zone_1,
    ny_it201_att_line_10_total_nyc_nonrefundable_credits,
    ny_it201_att_line_12_other_refundable_credits,
    ny_it201_att_line_13_total_refundable_credits,
    ny_it201_att_line_14_total_refundable_credits,
    ny_it201_att_line_18_total_other_refundable_credits,
    ny_it201_line_53_nyc_nonrefundable_credits,
    ny_it201_line_71_other_refundable_credits,
    compute_federal_total_tax,
    compute_ny_total_tax,
    set_compute_checks_mode,
    round_to_dollars,
)


YEARS = [2023, 2024]
CURRENT_YEAR: int | None = None
TESTS_BY_EXPECTED_PATH: dict[str, callable] = {}
ENABLE_INTERNAL_COMPUTE_CHECKS = True


def _load_json(path: Path) -> dict:
    with path.open('r') as f:
        return json.load(f)


def _inputs_path(year: int) -> Path:
    return PRIVATE_DIR / f'inputs_{year}.json'


def _expected_path(year: int) -> Path:
    return PRIVATE_DIR / f'expected_{year}.json'


def _policy_path(year: int) -> Path:
    return BASE_DIR / f'policy_{year}.json'


def load_inputs(year: int):
    """Load input data for a given year."""
    return _load_json(_inputs_path(year))


def load_policy(year: int):
    """Load policy/config data for a given year."""
    return _load_json(_policy_path(year))


def load_expected(year: int):
    """Load expected values for a given year."""
    return _load_json(_expected_path(year))


def verify_and_print(description: str, result: Decimal, expected: Decimal):
    """Helper to verify calculation matches expected value and print result.

    Args:
        description: Human-readable description of what was calculated
        result: Computed value
        expected: Expected value from filed return
    """
    assert result == expected, f"{description}: expected {expected}, got {result}"
    print(f"✓ {description}: ${result:,}")


def extract_nested(data: dict, path: str) -> str:
    """Extract a value from a nested dict using dot notation.

    Args:
        data: The dict to extract from
        path: Dot-separated path (e.g., "federal.schedule_se.line_9_remaining_ss_wage_base")

    Returns:
        The value at the specified path
    """
    keys = path.split('.')
    result = data
    for key in keys:
        result = result[key]
    return result


def expected_value_for_year(year: int, path: str) -> Decimal | None:
    expected_values = load_expected(year)
    try:
        return Decimal(extract_nested(expected_values, path))
    except Exception:
        return None


def iter_expected_paths(expected_values: dict) -> list[str]:
    """Return dot-paths for all expected values (excluding top-level metadata)."""
    paths: list[str] = []

    def visit(node: dict, prefix: str | None) -> None:
        for key, value in node.items():
            if key.startswith('_'):
                continue
            if prefix is None and not isinstance(value, dict):
                # Skip top-level metadata like "year" and "description".
                continue
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                visit(value, path)
            else:
                paths.append(path)

    visit(expected_values, None)
    return paths


def register_test(expected_path: str, test_func: callable) -> None:
    if expected_path in TESTS_BY_EXPECTED_PATH:
        raise ValueError(f"Duplicate expected path registration: {expected_path}")
    TESTS_BY_EXPECTED_PATH[expected_path] = test_func


def optional_amount_by_tag(index: dict, tag: str) -> Decimal | None:
    total = tag_total(index, tag)
    if total == Decimal('0'):
        return None
    return total


def tag_or_else(index: dict, tag: str, fallback: callable) -> Decimal:
    value = optional_amount_by_tag(index, tag)
    return value if value is not None else fallback()


def create_test(
    description: str,
    func: callable,
    prepare_args: callable,
    expected_path: str,
    register: bool = True,
    use_inputs_index: bool = True,
):
    """Create a test function with common pattern abstracted away.

    Args:
        description: Human-readable description for the test output
        func: The calculation function to test
        prepare_args: Callable that takes (inputs, policy) and returns dict of kwargs for func
        expected_path: Dot-notation path to expected value (e.g., "federal.form_1040.line_24_total_tax")

    Returns:
        A test function with a `.compute()` helper for chaining results
    """
    def compute_value(year: int) -> Decimal:
        inputs_items = load_inputs(year)
        inputs_index = build_inputs_index(inputs_items)
        policy = load_policy(year)
        expected_values = load_expected(year)

        # Prepare arguments for the function
        if use_inputs_index:
            kwargs = prepare_args(inputs_index, policy)
        else:
            kwargs = prepare_args(inputs_items, policy)

        # Call the function being tested
        if ENABLE_INTERNAL_COMPUTE_CHECKS:
            set_compute_checks_mode(True, expected_values, context=str(year))
        try:
            return func(**kwargs)
        finally:
            if ENABLE_INTERNAL_COMPUTE_CHECKS:
                set_compute_checks_mode(False)

    def has_expected(year: int) -> bool:
        return expected_value_for_year(year, expected_path) is not None

    def test_func():
        ran = False
        for year in YEARS:
            inputs_path = _inputs_path(year)
            policy_path = _policy_path(year)
            expected_path_file = _expected_path(year)
            if not (inputs_path.exists() and policy_path.exists() and expected_path_file.exists()):
                continue
            if not has_expected(year):
                continue

            global CURRENT_YEAR
            CURRENT_YEAR = year

            expected = expected_value_for_year(year, expected_path)
            result = compute_value(year)
            # Verify and print
            verify_and_print(f"({year}) {description}", result, expected)
            ran = True

        if not ran:
            raise AssertionError(
                f"No expected value found for {description} in any year"
            )

    test_func.compute = compute_value
    test_func.expected_path = expected_path
    test_func.description = description
    test_func.__test__ = False
    if register:
        register_test(expected_path, test_func)

    return test_func


def computed(test_func: callable) -> Decimal:
    """Compute a dependent value without returning from a pytest test."""
    if CURRENT_YEAR is None:
        raise RuntimeError("CURRENT_YEAR is not set for computed()")
    return test_func.compute(CURRENT_YEAR)


def test_expected_values():
    """
    Drive tests from expected values for each year.

    For each expected value path, find the registered test and verify
    the computed result matches.
    """
    missing: dict[int, list[str]] = {}
    for year in YEARS:
        inputs_path = _inputs_path(year)
        policy_path = _policy_path(year)
        expected_path_file = _expected_path(year)
        if not (inputs_path.exists() and policy_path.exists() and expected_path_file.exists()):
            raise AssertionError(f"Missing inputs/policy/expected for year {year}")

        expected_values = load_expected(year)
        expected_paths = iter_expected_paths(expected_values)
        if not expected_paths:
            raise AssertionError(f"No expected values found for year {year}")

        global CURRENT_YEAR
        CURRENT_YEAR = year

        for path in expected_paths:
            test_func = TESTS_BY_EXPECTED_PATH.get(path)
            if test_func is None:
                missing.setdefault(year, []).append(path)
                continue

            expected = Decimal(extract_nested(expected_values, path))
            result = test_func.compute(year)
            description = f"({year}) {test_func.description} [{path}]"
            verify_and_print(description, result, expected)

    if missing:
        details = "\n".join(
            f"{year}: {', '.join(paths)}" for year, paths in missing.items()
        )
        raise AssertionError(
            "Missing tests for expected values:\n"
            f"{details}"
        )


# Test definitions using the abstracted pattern

test_federal_schedule_se_line_2_schedule_c_and_k1_profit = create_test(
    description="Schedule SE Line 2 (K-1 SE Income)",
    func=federal_schedule_se_line_2_schedule_c_and_k1_profit,
    prepare_args=lambda inputs, policy: {
        'k1_box_14a_self_employment_earnings': tag_total(
            inputs, 'schedule_se_k1_box_14a_self_employment_earnings', required=True
        ),
        'k1_box_12_section_179_deduction': tag_total(
            inputs, 'section_179_deduction', required=True
        ),
    },
    expected_path="federal.schedule_se.line_2_schedule_c_and_k1_profit",
)

test_federal_schedule_se_line_6_total_se_earnings = create_test(
    description="Schedule SE Line 6 (Total SE Earnings)",
    func=federal_schedule_se_line_6_total_se_earnings,
    prepare_args=lambda inputs, policy: {
        'line_2_schedule_c_and_k1_profit': computed(test_federal_schedule_se_line_2_schedule_c_and_k1_profit),
        'policy': policy,
    },
    expected_path="federal.schedule_se.line_6_total_se_earnings",
)

test_federal_schedule_se_line_10_social_security_tax = create_test(
    description="Schedule SE Line 10 (SS Portion)",
    func=federal_schedule_se_line_10_social_security_tax,
    prepare_args=lambda inputs, policy: {
        'line_6_self_employment_earnings': computed(test_federal_schedule_se_line_6_total_se_earnings),
        'policy': policy,
    },
    expected_path="federal.schedule_se.line_10_social_security_portion",
)

test_federal_schedule_se_line_11_medicare_tax = create_test(
    description="Schedule SE Line 11 (Medicare Portion)",
    func=federal_schedule_se_line_11_medicare_tax,
    prepare_args=lambda inputs, policy: {
        'line_6_self_employment_earnings': computed(test_federal_schedule_se_line_6_total_se_earnings),
        'policy': policy,
    },
    expected_path="federal.schedule_se.line_11_medicare_portion",
)

test_federal_schedule_se_line_12_self_employment_tax = create_test(
    description="Schedule SE Line 12 (Self-Employment Tax)",
    func=federal_schedule_se_line_12_self_employment_tax,
    prepare_args=lambda inputs, policy: {
        'line_10_social_security_portion': computed(test_federal_schedule_se_line_10_social_security_tax),
        'line_11_medicare_portion': computed(test_federal_schedule_se_line_11_medicare_tax),
    },
    expected_path="federal.schedule_se.line_12_self_employment_tax",
)

test_federal_form_8959_line_18_additional_medicare_tax = create_test(
    description="Form 8959 Line 18 (Additional Medicare Tax)",
    func=federal_form_8959_line_18_additional_medicare_tax,
    prepare_args=lambda inputs, policy: {
        'w2_medicare_wages': tag_total(inputs, 'w2_box_5_medicare_wages'),
        'schedule_se_line_6_se_earnings': computed(test_federal_schedule_se_line_6_total_se_earnings),        'policy': policy,
    },
    expected_path="federal.form_8959.line_18_additional_medicare_tax",
)

test_federal_schedule_b_line_1_taxable_interest = create_test(
    description="Schedule B Line 1 (Taxable Interest)",
    func=federal_schedule_b_line_1_taxable_interest,
    prepare_args=lambda inputs, policy: {
        'index': inputs,
    },
    expected_path="federal.schedule_b.line_1_taxable_interest",
)

test_federal_schedule_b_line_6_ordinary_dividends = create_test(
    description="Schedule B Line 6 (Ordinary Dividends)",
    func=federal_schedule_b_line_6_ordinary_dividends,
    prepare_args=lambda inputs, policy: {
        'index': inputs,
    },
    expected_path="federal.schedule_b.line_6_ordinary_dividends",
)

test_federal_schedule_e_line_29a_total_nonpassive_income = create_test(
    description="Schedule E Line 29a (Total Nonpassive Income)",
    func=federal_schedule_e_line_29a_total_nonpassive_income,
    prepare_args=lambda inputs, policy: {
        'index': inputs,
    },
    expected_path="federal.schedule_e.line_29a_total_nonpassive_income",
)

test_federal_schedule_e_line_29b_total_nonpassive_loss_allowed = create_test(
    description="Schedule E Line 29b (Total Nonpassive Loss Allowed)",
    func=federal_schedule_e_line_29b_total_nonpassive_loss_allowed,
    prepare_args=lambda inputs, policy: {
        'index': inputs,
    },
    expected_path="federal.schedule_e.line_29b_total_nonpassive_loss_allowed",
)

test_federal_schedule_e_line_29b_total_section_179_deduction = create_test(
    description="Schedule E Line 29b (Total Section 179 Deduction)",
    func=federal_schedule_e_line_29b_total_section_179_deduction,
    prepare_args=lambda inputs, policy: {
        'index': inputs,
    },
    expected_path="federal.schedule_e.line_29b_total_section_179_deduction",
)

test_federal_schedule_e_line_30_total_income = create_test(
    description="Schedule E Line 30 (Total Income)",
    func=federal_schedule_e_line_30_total_income,
    prepare_args=lambda inputs, policy: {
        'line_29a_nonpassive_income': computed(test_federal_schedule_e_line_29a_total_nonpassive_income),
    },
    expected_path="federal.schedule_e.line_30_total_income",
)

test_federal_schedule_e_line_31_total_losses = create_test(
    description="Schedule E Line 31 (Total Losses/Deductions)",
    func=federal_schedule_e_line_31_total_losses,
    prepare_args=lambda inputs, policy: {
        'line_29b_nonpassive_loss_allowed': (
            computed(test_federal_schedule_e_line_29b_total_nonpassive_loss_allowed)
        ),
        'line_29b_section_179_deduction': (
            computed(test_federal_schedule_e_line_29b_total_section_179_deduction)
        ),
    },
    expected_path="federal.schedule_e.line_31_total_losses",
)

test_federal_schedule_e_line_32_total_partnership_income = create_test(
    description="Schedule E Line 32 (Total Partnership Income)",
    func=federal_schedule_e_line_32_total_partnership_income,
    prepare_args=lambda inputs, policy: {
        'line_30_total_income': computed(test_federal_schedule_e_line_30_total_income),
        'line_31_total_losses': computed(test_federal_schedule_e_line_31_total_losses),
    },
    expected_path="federal.schedule_e.line_32_total_partnership_income",
)

test_federal_schedule_1_line_5_rental_real_estate_income = create_test(
    description="Schedule 1 Line 5 (Rental/Partnership Income)",
    func=federal_schedule_1_line_5_rental_real_estate_income,
    prepare_args=lambda inputs, policy: {
        'schedule_e_line_32_total_partnership_income': (
            computed(test_federal_schedule_e_line_32_total_partnership_income)
        ),
    },
    expected_path="federal.schedule_1.line_5_rental_real_estate_income",
)

test_federal_schedule_1_line_10_additional_income = create_test(
    description="Schedule 1 Line 10 (Additional Income)",
    func=federal_schedule_1_line_10_additional_income,
    prepare_args=lambda inputs, policy: {
        'line_5_rental_real_estate_income': (
            computed(test_federal_schedule_1_line_5_rental_real_estate_income)
        ),
    },
    expected_path="federal.schedule_1.line_10_additional_income",
)

test_federal_schedule_1_line_15_deductible_self_employment_tax = create_test(
    description="Schedule 1 Line 15 (Deductible SE Tax)",
    func=federal_schedule_1_line_15_deductible_self_employment_tax,
    prepare_args=lambda inputs, policy: {
        'schedule_se_line_12_self_employment_tax': (
            computed(test_federal_schedule_se_line_12_self_employment_tax)
        ),
    },
    expected_path="federal.schedule_1.line_15_deductible_self_employment_tax",
)

test_federal_schedule_1_line_16_self_employed_retirement_contributions = create_test(
    description="Schedule 1 Line 16 (Self-Employed Retirement Contributions)",
    func=federal_schedule_1_line_16_self_employed_retirement_contributions,
    prepare_args=lambda inputs, policy: {
        'index': inputs,
    },
    expected_path="federal.schedule_1.line_16_self_employed_retirement_contributions",
)

test_federal_schedule_1_line_17_self_employed_health_insurance = create_test(
    description="Schedule 1 Line 17 (Self-Employed Health Insurance)",
    func=federal_schedule_1_line_17_self_employed_health_insurance,
    prepare_args=lambda inputs, policy: {
        'index': inputs,
    },
    expected_path="federal.schedule_1.line_17_self_employed_health_insurance",
)

test_federal_schedule_1_line_26_adjustments_to_income = create_test(
    description="Schedule 1 Line 26 (Adjustments to Income)",
    func=federal_schedule_1_line_26_adjustments_to_income,
    prepare_args=lambda inputs, policy: {
        'line_15_deductible_self_employment_tax': (
            computed(test_federal_schedule_1_line_15_deductible_self_employment_tax)
        ),
        'line_16_self_employed_retirement_contributions': (
            computed(test_federal_schedule_1_line_16_self_employed_retirement_contributions)
        ),
        'line_17_self_employed_health_insurance': (
            computed(test_federal_schedule_1_line_17_self_employed_health_insurance)
        ),
    },
    expected_path="federal.schedule_1.line_26_adjustments_to_income",
)

test_federal_form_1040_line_10_adjustments_to_income = create_test(
    description="Form 1040 Line 10 (Adjustments to Income)",
    func=federal_schedule_1_line_26_adjustments_to_income,
    prepare_args=lambda inputs, policy: {
        'line_15_deductible_self_employment_tax': (
            computed(test_federal_schedule_1_line_15_deductible_self_employment_tax)
        ),
        'line_16_self_employed_retirement_contributions': (
            computed(test_federal_schedule_1_line_16_self_employed_retirement_contributions)
        ),
        'line_17_self_employed_health_insurance': (
            computed(test_federal_schedule_1_line_17_self_employed_health_insurance)
        ),
    },
    expected_path="federal.form_1040.line_10_adjustments_to_income",
)

test_federal_form_6781_line_7_total_gain_loss_1256 = create_test(
    description="Form 6781 Line 7 (Total Section 1256 Gain/Loss)",
    func=federal_form_6781_line_7_total_gain_loss_1256,
    prepare_args=lambda inputs, policy: {
        'index': inputs,
    },
    expected_path="federal.form_6781.line_7_total_gain_loss_1256",
)

test_federal_form_6781_line_8_short_term_portion = create_test(
    description="Form 6781 Line 8 (Short-Term Portion)",
    func=federal_form_6781_line_8_short_term_portion,
    prepare_args=lambda inputs, policy: {
        'line_7_total_gain_loss': computed(test_federal_form_6781_line_7_total_gain_loss_1256),
        'policy': policy,
    },
    expected_path="federal.form_6781.line_8_short_term_portion",
)

test_federal_form_6781_line_9_long_term_portion = create_test(
    description="Form 6781 Line 9 (Long-Term Portion)",
    func=federal_form_6781_line_9_long_term_portion,
    prepare_args=lambda inputs, policy: {
        'line_7_total_gain_loss': computed(test_federal_form_6781_line_7_total_gain_loss_1256),
        'policy': policy,
    },
    expected_path="federal.form_6781.line_9_long_term_portion",
)

test_federal_schedule_d_line_1a_short_term_gain = create_test(
    description="Schedule D Line 1a (Short-Term 1099-B Gain)",
    func=federal_schedule_d_line_1a_short_term_gain,
    prepare_args=lambda inputs, policy: {
        'index': inputs,
    },
    expected_path="federal.schedule_d.line_1a_short_term_gain",
)

test_federal_schedule_d_line_3_short_term_section_1061_adjustment = create_test(
    description="Schedule D Line 3 (Section 1061 Short-Term Adjustment)",
    func=federal_schedule_d_line_3_short_term_section_1061_adjustment,
    prepare_args=lambda inputs, policy: {
        'index': inputs,
    },
    expected_path="federal.schedule_d.line_3_short_term_section_1061_adjustment",
)

test_federal_schedule_d_line_4_short_term_from_6781 = create_test(
    description="Schedule D Line 4 (Short-Term From Form 6781)",
    func=federal_schedule_d_line_4_short_term_from_6781,
    prepare_args=lambda inputs, policy: {
        'form_6781_line_8_short_term_portion': (
            computed(test_federal_form_6781_line_8_short_term_portion)
        ),
    },
    expected_path="federal.schedule_d.line_4_short_term_from_6781",
)

test_federal_schedule_d_line_5_short_term_k1_gain = create_test(
    description="Schedule D Line 5 (Short-Term K-1 Gain)",
    func=federal_schedule_d_line_5_short_term_k1_gain,
    prepare_args=lambda inputs, policy: {
        'index': inputs,
    },
    expected_path="federal.schedule_d.line_5_short_term_k1_gain",
)

test_federal_schedule_d_line_7_net_short_term_gain = create_test(
    description="Schedule D Line 7 (Net Short-Term Gain)",
    func=federal_schedule_d_line_7_net_short_term_gain,
    prepare_args=lambda inputs, policy: (
        {
            'line_1a_short_term_gain': optional_amount_by_tag(
                inputs, 'schedule_d_line_7_net_short_term_gain'
            ),
            'line_3_short_term_adjustment': Decimal('0'),
            'line_4_short_term_from_6781': Decimal('0'),
            'line_5_short_term_k1_gain': Decimal('0'),
        }
        if optional_amount_by_tag(inputs, 'schedule_d_line_7_net_short_term_gain')
        is not None
        else {
            'line_1a_short_term_gain': computed(
                test_federal_schedule_d_line_1a_short_term_gain
            ),
            'line_3_short_term_adjustment': (
                computed(test_federal_schedule_d_line_3_short_term_section_1061_adjustment)
            ),
            'line_4_short_term_from_6781': computed(
                test_federal_schedule_d_line_4_short_term_from_6781
            ),
            'line_5_short_term_k1_gain': computed(
                test_federal_schedule_d_line_5_short_term_k1_gain
            ),
        }
    ),
    expected_path="federal.schedule_d.line_7_net_short_term_gain",
)

test_federal_schedule_d_line_10_long_term_section_1061_adjustment = create_test(
    description="Schedule D Line 10 (Section 1061 Long-Term Adjustment)",
    func=federal_schedule_d_line_10_long_term_section_1061_adjustment,
    prepare_args=lambda inputs, policy: {
        'index': inputs,
    },
    expected_path="federal.schedule_d.line_10_long_term_section_1061_adjustment",
)

test_federal_schedule_d_line_11_long_term_from_6781_and_4797 = create_test(
    description="Schedule D Line 11 (Long-Term From 6781 and 4797)",
    func=federal_schedule_d_line_11_long_term_from_6781_and_4797,
    prepare_args=lambda inputs, policy: {
        'form_6781_line_9_long_term_portion': (
            computed(test_federal_form_6781_line_9_long_term_portion)
        ),
        'index': inputs,
    },
    expected_path="federal.schedule_d.line_11_long_term_from_6781_and_4797",
)

test_federal_schedule_d_line_12_long_term_k1_gain = create_test(
    description="Schedule D Line 12 (Long-Term K-1 Gain)",
    func=federal_schedule_d_line_12_long_term_k1_gain,
    prepare_args=lambda inputs, policy: {
        'index': inputs,
    },
    expected_path="federal.schedule_d.line_12_long_term_k1_gain",
)

test_federal_schedule_d_line_15_net_long_term_gain = create_test(
    description="Schedule D Line 15 (Net Long-Term Gain)",
    func=federal_schedule_d_line_15_net_long_term_gain,
    prepare_args=lambda inputs, policy: (
        {
            'line_10_long_term_adjustment': Decimal('0'),
            'line_11_long_term_from_6781_and_4797': Decimal('0'),
            'line_12_long_term_k1_gain': optional_amount_by_tag(
                inputs, 'schedule_d_line_15_net_long_term_gain'
            ),
        }
        if optional_amount_by_tag(inputs, 'schedule_d_line_15_net_long_term_gain')
        is not None
        else {
            'line_10_long_term_adjustment': (
                computed(test_federal_schedule_d_line_10_long_term_section_1061_adjustment)
            ),
            'line_11_long_term_from_6781_and_4797': (
                computed(test_federal_schedule_d_line_11_long_term_from_6781_and_4797)
            ),
            'line_12_long_term_k1_gain': computed(
                test_federal_schedule_d_line_12_long_term_k1_gain
            ),
        }
    ),
    expected_path="federal.schedule_d.line_15_net_long_term_gain",
)

test_federal_schedule_d_line_16_net_capital_gain = create_test(
    description="Schedule D Line 16 (Net Capital Gain)",
    func=federal_schedule_d_line_16_net_capital_gain,
    prepare_args=lambda inputs, policy: {
        'line_7_net_short_term_gain': computed(test_federal_schedule_d_line_7_net_short_term_gain),
        'line_15_net_long_term_gain': computed(test_federal_schedule_d_line_15_net_long_term_gain),
    },
    expected_path="federal.schedule_d.line_16_net_capital_gain",
)

test_federal_form_8960_line_1_taxable_interest = create_test(
    description="Form 8960 Line 1 (Taxable Interest)",
    func=federal_form_8960_line_1_taxable_interest,
    prepare_args=lambda inputs, policy: {
        'taxable_interest': computed(test_federal_schedule_b_line_1_taxable_interest),
    },
    expected_path="federal.form_8960.line_1_taxable_interest",
)

test_federal_form_8960_line_2_ordinary_dividends = create_test(
    description="Form 8960 Line 2 (Ordinary Dividends)",
    func=federal_form_8960_line_2_ordinary_dividends,
    prepare_args=lambda inputs, policy: {
        'ordinary_dividends': computed(test_federal_schedule_b_line_6_ordinary_dividends),
    },
    expected_path="federal.form_8960.line_2_ordinary_dividends",
)

test_federal_form_8960_line_4a_rental_real_estate_royalties_partnerships = create_test(
    description="Form 8960 Line 4a (Rental/Partnership Income)",
    func=federal_form_8960_line_4a_rental_real_estate_royalties_partnerships,
    prepare_args=lambda inputs, policy: {
        'schedule_e_line_32_total_partnership_income': tag_or_else(
            inputs,
            'schedule_e_line_32_total_partnership_income',
            lambda: computed(test_federal_schedule_e_line_32_total_partnership_income),
        ),
    },
    expected_path="federal.form_8960.line_4a_rental_real_estate_royalties_partnerships",
)

test_federal_form_8960_line_4b_adjustment_nonsection_1411 = create_test(
    description="Form 8960 Line 4b (Non-Section 1411 Adjustment)",
    func=federal_form_8960_line_4b_adjustment_nonsection_1411,
    prepare_args=lambda inputs, policy: {
        **(
            {
                'nonpassive_income': optional_amount_by_tag(
                    inputs, 'schedule_e_line_29a_total_nonpassive_income'
                ),
                'nonpassive_losses_allowed': Decimal('0'),
                'section_179_deduction': Decimal('0'),
                'additional_nonpassive_deductions': Decimal('0'),
            }
            if optional_amount_by_tag(
                inputs, 'schedule_e_line_29a_total_nonpassive_income'
            ) is not None
            else {
                'nonpassive_income': computed(
                    test_federal_schedule_e_line_29a_total_nonpassive_income
                ),
                'nonpassive_losses_allowed': Decimal('0'),
                'section_179_deduction': computed(
                    test_federal_schedule_e_line_29b_total_section_179_deduction
                ),
                'additional_nonpassive_deductions': tag_total(
                    inputs, 'form_8960_line_4b_additional_nonpassive_deductions'
                ),
            }
        ),
    },
    expected_path="federal.form_8960.line_4b_adjustment_nonsection_1411",
)

test_federal_form_8960_line_4c_net_income_from_rentals = create_test(
    description="Form 8960 Line 4c (Net Income From Rentals/Partnerships)",
    func=federal_form_8960_line_4c_net_income_from_rentals,
    prepare_args=lambda inputs, policy: {
        'line_4a_rental_real_estate_royalties_partnerships': (
            computed(test_federal_form_8960_line_4a_rental_real_estate_royalties_partnerships)
        ),
        'line_4b_adjustment_nonsection_1411': (
            computed(test_federal_form_8960_line_4b_adjustment_nonsection_1411)
        ),
    },
    expected_path="federal.form_8960.line_4c_net_income_from_rentals",
)

test_federal_form_8960_line_5a_net_gain_loss_disposition = create_test(
    description="Form 8960 Line 5a (Net Gain/Loss Disposition)",
    func=federal_form_8960_line_5a_net_gain_loss_disposition,
    prepare_args=lambda inputs, policy: {
        'schedule_d_line_16_net_capital_gain': tag_or_else(
            inputs,
            'schedule_d_line_16_net_capital_gain',
            lambda: computed(test_federal_schedule_d_line_16_net_capital_gain),
        ),
    },
    expected_path="federal.form_8960.line_5a_net_gain_loss_disposition",
)

test_federal_form_8960_line_5d_net_gain_loss_disposition = create_test(
    description="Form 8960 Line 5d (Net Gain/Loss Disposition)",
    func=federal_form_8960_line_5d_net_gain_loss_disposition,
    prepare_args=lambda inputs, policy: {
        'line_5a_net_gain_loss_disposition': (
            computed(test_federal_form_8960_line_5a_net_gain_loss_disposition)
        ),
    },
    expected_path="federal.form_8960.line_5d_net_gain_loss_disposition",
)

test_federal_form_8960_line_8_total_investment_income = create_test(
    description="Form 8960 Line 8 (Total Investment Income)",
    func=federal_form_8960_line_8_total_investment_income,
    prepare_args=lambda inputs, policy: {
        'line_1_taxable_interest': tag_or_else(
            inputs,
            'form_8960_line_1_taxable_interest',
            lambda: computed(test_federal_form_8960_line_1_taxable_interest),
        ),
        'line_2_ordinary_dividends': tag_or_else(
            inputs,
            'form_8960_line_2_ordinary_dividends',
            lambda: computed(test_federal_form_8960_line_2_ordinary_dividends),
        ),
        'line_4c_net_income_from_rentals': tag_or_else(
            inputs,
            'form_8960_line_4c_net_income_from_rentals',
            lambda: computed(test_federal_form_8960_line_4c_net_income_from_rentals),
        ),
        'line_5d_net_gain_loss_disposition': tag_or_else(
            inputs,
            'form_8960_line_5d_net_gain_loss_disposition',
            lambda: computed(test_federal_form_8960_line_5d_net_gain_loss_disposition),
        ),
    },
    expected_path="federal.form_8960.line_8_total_investment_income",
)

test_federal_form_8960_line_9a_investment_interest_expense = create_test(
    description="Form 8960 Line 9a (Investment Interest Expense)",
    func=federal_form_8960_line_9a_investment_interest_expense,
    prepare_args=lambda inputs, policy: {
        'index': inputs,
    },
    expected_path="federal.form_8960.line_9a_investment_interest_expense",
)

test_federal_form_8960_line_9b_state_local_foreign_income_tax = create_test(
    description="Form 8960 Line 9b (State/Local/Foreign Income Tax)",
    func=federal_form_8960_line_9b_state_local_foreign_income_tax,
    prepare_args=lambda inputs, policy: {
        'index': inputs,
        'policy': policy,
    },
    expected_path="federal.form_8960.line_9b_state_local_foreign_income_tax",
)

test_federal_form_8960_line_9c_misc_investment_expenses = create_test(
    description="Form 8960 Line 9c (Miscellaneous Investment Expenses)",
    func=federal_form_8960_line_9c_misc_investment_expenses,
    prepare_args=lambda inputs, policy: {
        'index': inputs,
    },
    expected_path="federal.form_8960.line_9c_misc_investment_expenses",
)

test_federal_form_8960_line_12_net_investment_income = create_test(
    description="Form 8960 Line 12 (Net Investment Income)",
    func=federal_form_8960_line_12_net_investment_income,
    prepare_args=lambda inputs, policy: {
        'line_8_total_investment_income': tag_or_else(
            inputs,
            'form_8960_line_8_total_investment_income',
            lambda: computed(test_federal_form_8960_line_8_total_investment_income),
        ),
        'line_11_total_deductions_and_modifications': federal_form_8960_line_11_total_deductions_and_modifications(
            federal_form_8960_line_9d_total_investment_expenses(
                computed(test_federal_form_8960_line_9a_investment_interest_expense),
                computed(test_federal_form_8960_line_9b_state_local_foreign_income_tax),
                computed(test_federal_form_8960_line_9c_misc_investment_expenses),
            )
        ),
    },
    expected_path="federal.form_8960.line_12_net_investment_income",
)

test_federal_form_1040_line_1z_wages = create_test(
    description="Form 1040 Line 1z (Total Wages)",
    func=federal_form_1040_line_1z_wages,
    prepare_args=lambda inputs, policy: {
        'index': inputs,
    },
    expected_path="federal.form_1040.line_1z_wages",
)

test_federal_form_1040_line_3a_qualified_dividends = create_test(
    description="Form 1040 Line 3a (Qualified Dividends)",
    func=federal_form_1040_line_3a_qualified_dividends,
    prepare_args=lambda inputs, policy: {
        'index': inputs,
    },
    expected_path="federal.form_1040.line_3a_qualified_dividends",
)

test_federal_form_1040_line_5b_pensions_annuities = create_test(
    description="Form 1040 Line 5b (Taxable Pensions/Annuities)",
    func=federal_form_1040_line_5b_pensions_annuities,
    prepare_args=lambda inputs, policy: {
        'index': inputs,
    },
    expected_path="federal.form_1040.line_5b_pensions_annuities",
)

test_federal_form_1040_line_9_total_income = create_test(
    description="Form 1040 Line 9 (Total Income)",
    func=federal_form_1040_line_9_total_income,
    prepare_args=lambda inputs, policy: {
        'line_1z_wages': computed(test_federal_form_1040_line_1z_wages),
        'line_2b_taxable_interest': computed(test_federal_schedule_b_line_1_taxable_interest),
        'line_3b_ordinary_dividends': computed(test_federal_schedule_b_line_6_ordinary_dividends),
        'line_5b_pensions_annuities': computed(test_federal_form_1040_line_5b_pensions_annuities),
        'line_7_capital_gain_loss': computed(test_federal_schedule_d_line_16_net_capital_gain),
        'line_8_additional_income': computed(test_federal_schedule_1_line_10_additional_income),
    },
    expected_path="federal.form_1040.line_9_total_income",
)

test_federal_form_1040_line_11_adjusted_gross_income = create_test(
    description="Form 1040 Line 11 (Adjusted Gross Income)",
    func=federal_form_1040_line_11_adjusted_gross_income,
    prepare_args=lambda inputs, policy: {
        'line_9_total_income': computed(test_federal_form_1040_line_9_total_income),
        'line_10_adjustments_to_income': (
            computed(test_federal_schedule_1_line_26_adjustments_to_income)
        ),
    },
    expected_path="federal.form_1040.line_11_adjusted_gross_income",
)

test_federal_form_1040_line_12_standard_deduction = create_test(
    description="Form 1040 Line 12 (Standard Deduction)",
    func=federal_form_1040_line_12_standard_deduction,
    prepare_args=lambda inputs, policy: {        'policy': policy,
        'line_12_deduction_override': (
            (
                tag_total(inputs, 'form_1040_line_12_deductions')
                + computed(test_federal_form_8960_line_9b_state_local_foreign_income_tax)
            )
            if tag_total(inputs, 'form_1040_line_12_deductions') != Decimal('0')
            else None
        ),
    },
    expected_path="federal.form_1040.line_12_standard_deduction",
)

test_federal_form_1040_line_14_total_deductions = create_test(
    description="Form 1040 Line 14 (Total Deductions)",
    func=federal_form_1040_line_14_total_deductions,
    prepare_args=lambda inputs, policy: {
        'line_12_standard_deduction': computed(test_federal_form_1040_line_12_standard_deduction),
        'line_13_qbi_deduction': (
            tag_or_else(inputs, 'form_1040_line_13_qbi_deduction', lambda: Decimal('0'))
            + round_to_dollars(
                tag_or_else(
                    inputs, 'form_1099_div_box_5_section_199a_dividends', lambda: Decimal('0')
                )
                * Decimal('0.20')
            )
        ),
    },
    expected_path="federal.form_1040.line_14_total_deductions",
)

test_federal_form_1040_line_15_taxable_income = create_test(
    description="Form 1040 Line 15 (Taxable Income)",
    func=federal_form_1040_line_15_taxable_income,
    prepare_args=lambda inputs, policy: {
        'line_11_adjusted_gross_income': computed(test_federal_form_1040_line_11_adjusted_gross_income),
        'line_14_total_deductions': computed(test_federal_form_1040_line_14_total_deductions),
    },
    expected_path="federal.form_1040.line_15_taxable_income",
)

test_federal_form_1040_qualified_dividends_capital_gain_worksheet_line_22_tax_on_line_5 = (
    create_test(
        description="Qualified Dividends and Capital Gain Tax Worksheet Line 22",
        func=federal_form_1040_qualified_dividends_capital_gain_worksheet_line_22_tax_on_line_5,
        prepare_args=lambda inputs, policy: {
            'line_1_taxable_income': computed(test_federal_form_1040_line_15_taxable_income),
            'line_2_qualified_dividends': computed(test_federal_form_1040_line_3a_qualified_dividends),
            'schedule_d_line_15': computed(test_federal_schedule_d_line_15_net_long_term_gain),
            'schedule_d_line_16': computed(test_federal_schedule_d_line_16_net_capital_gain),            'policy': policy,
        },
        expected_path=(
            "federal.form_1040_qualified_dividends_capital_gain_worksheet.line_22_tax_on_line_5"
        ),
    )
)

test_federal_form_1040_qualified_dividends_capital_gain_worksheet_line_24_tax_on_line_1 = (
    create_test(
        description="Qualified Dividends and Capital Gain Tax Worksheet Line 24",
        func=federal_form_1040_qualified_dividends_capital_gain_worksheet_line_24_tax_on_line_1,
        prepare_args=lambda inputs, policy: {
            'line_1_taxable_income': computed(test_federal_form_1040_line_15_taxable_income),            'policy': policy,
        },
        expected_path=(
            "federal.form_1040_qualified_dividends_capital_gain_worksheet.line_24_tax_on_line_1"
        ),
    )
)

test_federal_form_1040_qualified_dividends_capital_gain_worksheet_line_25 = create_test(
    description="Qualified Dividends and Capital Gain Tax Worksheet Line 25",
    func=federal_form_1040_qualified_dividends_capital_gain_worksheet_line_25,
    prepare_args=lambda inputs, policy: {
        'line_1_taxable_income': computed(test_federal_form_1040_line_15_taxable_income),
        'line_2_qualified_dividends': computed(test_federal_form_1040_line_3a_qualified_dividends),
        'schedule_d_line_15': computed(test_federal_schedule_d_line_15_net_long_term_gain),
        'schedule_d_line_16': computed(test_federal_schedule_d_line_16_net_capital_gain),        'policy': policy,
    },
    expected_path="federal.form_1040_qualified_dividends_capital_gain_worksheet.line_25_tax_on_all_income",
)

test_federal_form_1040_line_16_tax = create_test(
    description="Form 1040 Line 16 (Tax)",
    func=federal_form_1040_line_16_tax,
    prepare_args=lambda inputs, policy: {
        'line_16_tax_from_worksheet': tag_or_else(
            inputs,
            'form_1040_line_16_tax',
            lambda: computed(
                test_federal_form_1040_qualified_dividends_capital_gain_worksheet_line_25
            ),
        ),
    },
    expected_path="federal.form_1040.line_16_tax",
)

test_federal_form_1040_line_18_tax_and_amounts = create_test(
    description="Form 1040 Line 18 (Tax and Amounts)",
    func=federal_form_1040_line_18_tax_and_amounts,
    prepare_args=lambda inputs, policy: {
        'line_16_tax': computed(test_federal_form_1040_line_16_tax),
    },
    expected_path="federal.form_1040.line_18_tax_and_amounts",
)

test_federal_form_1040_line_21_total_credits = create_test(
    description="Form 1040 Line 21 (Total Credits)",
    func=federal_form_1040_line_21_total_credits,
    prepare_args=lambda inputs, policy: {
        'line_19_child_tax_credit': tag_or_else(
            inputs,
            'form_1040_line_19_child_tax_credit',
            lambda: Decimal('0'),
        ),
        'line_20_schedule_3_line_8': tag_or_else(
            inputs,
            'form_1116_foreign_taxes_paid',
            lambda: Decimal('0'),
        ),
    },
    expected_path="federal.form_1040.line_21_total_credits",
)

test_federal_form_8960_line_13_modified_adjusted_gross_income = create_test(
    description="Form 8960 Line 13 (Modified AGI)",
    func=federal_form_8960_line_13_modified_adjusted_gross_income,
    prepare_args=lambda inputs, policy: {
        'form_1040_line_11_adjusted_gross_income': tag_or_else(
            inputs,
            'form_1040_line_11_adjusted_gross_income',
            lambda: computed(test_federal_form_1040_line_11_adjusted_gross_income),
        ),
    },
    expected_path="federal.form_8960.line_13_modified_adjusted_gross_income",
)

test_federal_form_8960_line_15_modified_agi_over_threshold = create_test(
    description="Form 8960 Line 15 (Modified AGI Over Threshold)",
    func=federal_form_8960_line_15_modified_agi_over_threshold,
    prepare_args=lambda inputs, policy: {
        'line_13_modified_adjusted_gross_income': tag_or_else(
            inputs,
            'form_8960_line_13_modified_agi',
            lambda: computed(test_federal_form_8960_line_13_modified_adjusted_gross_income),
        ),        'policy': policy,
    },
    expected_path="federal.form_8960.line_15_modified_agi_over_threshold",
)

test_federal_form_8960_line_16_smaller_of_line_12_or_15 = create_test(
    description="Form 8960 Line 16 (Smaller of Line 12 or 15)",
    func=federal_form_8960_line_16_smaller_of_line_12_or_15,
    prepare_args=lambda inputs, policy: {
        'line_12_net_investment_income': tag_or_else(
            inputs,
            'form_8960_line_12_net_investment_income',
            lambda: computed(test_federal_form_8960_line_12_net_investment_income),
        ),
        'line_15_modified_agi_over_threshold': tag_or_else(
            inputs,
            'form_8960_line_15_modified_agi_over_threshold',
            lambda: computed(test_federal_form_8960_line_15_modified_agi_over_threshold),
        ),
    },
    expected_path="federal.form_8960.line_16_smaller_of_line_12_or_15",
)

test_federal_form_8960_line_17_net_investment_income_tax = create_test(
    description="Form 8960 Line 17 (Net Investment Income Tax)",
    func=federal_form_8960_line_17_net_investment_income_tax,
    prepare_args=lambda inputs, policy: {
        'line_16_smaller_of_line_12_or_15': tag_or_else(
            inputs,
            'form_8960_line_16_smaller_of_line_12_or_15',
            lambda: computed(test_federal_form_8960_line_16_smaller_of_line_12_or_15),
        ),
        'policy': policy,
    },
    expected_path="federal.form_8960.line_17_net_investment_income_tax",
)

test_federal_form_1040_line_22_tax_after_credits = create_test(
    description="Form 1040 Line 22 (Tax After Credits)",
    func=federal_form_1040_line_22_tax_after_credits,
    prepare_args=lambda inputs, policy: {
        'line_18_tax_and_amounts': computed(test_federal_form_1040_line_18_tax_and_amounts),
        'line_21_total_credits': computed(test_federal_form_1040_line_21_total_credits),
    },
    expected_path="federal.form_1040.line_22_tax_after_credits",
)

test_federal_schedule_2_line_12_net_investment_income_tax = create_test(
    description="Schedule 2 Line 12 (Net Investment Income Tax)",
    func=federal_schedule_2_line_12_net_investment_income_tax,
    prepare_args=lambda inputs, policy: {
        'form_8960_line_17_net_investment_income_tax': tag_or_else(
            inputs,
            'form_8960_line_17_net_investment_income_tax',
            lambda: computed(test_federal_form_8960_line_17_net_investment_income_tax),
        ),
    },
    expected_path="federal.schedule_2.line_12_net_investment_income_tax",
)

test_federal_schedule_2_line_21_other_taxes = create_test(
    description="Schedule 2 Line 21 (Other Taxes)",
    func=federal_schedule_2_line_21_other_taxes,
    prepare_args=lambda inputs, policy: {
        'line_4_self_employment_tax': tag_or_else(
            inputs,
            'schedule_se_line_12_self_employment_tax',
            lambda: computed(test_federal_schedule_se_line_12_self_employment_tax),
        ),
        'line_11_additional_medicare_tax': tag_or_else(
            inputs,
            'form_8959_line_18_additional_medicare_tax',
            lambda: computed(test_federal_form_8959_line_18_additional_medicare_tax),
        ),
        'line_12_net_investment_income_tax': tag_or_else(
            inputs,
            'schedule_2_line_12_net_investment_income_tax',
            lambda: computed(test_federal_schedule_2_line_12_net_investment_income_tax),
        ),
    },
    expected_path="federal.schedule_2.line_21_other_taxes",
)

test_federal_1040_line_23_other_taxes = create_test(
    description="Form 1040 Line 23 (Other Taxes)",
    func=federal_1040_line_23_other_taxes,
    prepare_args=lambda inputs, policy: {
        'schedule_2_line_21_total_other_taxes': tag_or_else(
            inputs,
            'schedule_2_line_21_other_taxes',
            lambda: computed(test_federal_schedule_2_line_21_other_taxes),
        ),
    },
    expected_path="federal.form_1040.line_23_other_taxes",
)

test_federal_1040_line_24_total_tax = create_test(
    description="Form 1040 Line 24 (Total Tax)",
    func=federal_1040_line_24_total_tax,
    prepare_args=lambda inputs, policy: {
        'line_22_tax_after_credits': computed(test_federal_form_1040_line_22_tax_after_credits),
        'line_23_other_taxes': computed(test_federal_1040_line_23_other_taxes),
    },
    expected_path="federal.form_1040.line_24_total_tax",
)

test_ny_it201_line_62_total_taxes = create_test(
    description="NY IT-201 Line 62 (Total Taxes)",
    func=ny_it201_line_62_total_taxes,
    prepare_args=lambda inputs, policy: {
        'line_61_total_taxes': tag_or_else(
            inputs,
            'ny_it201_line_62_total_taxes',
            lambda: computed(test_ny_it201_line_61_total_taxes),
        ),
    },
    expected_path="ny.it_201.line_62_total_taxes",
)

test_ny_it201_line_61_total_taxes = create_test(
    description="NY IT-201 Line 61 (Total Taxes)",
    func=ny_it201_line_61_total_taxes,
    prepare_args=lambda inputs, policy: {
        'line_46_total_ny_state_taxes': computed(test_ny_it201_line_46_total_ny_state_taxes),
        'line_58_total_nyc_yonkers_mctmt': computed(test_ny_it201_line_58_total_nyc_yonkers_mctmt),
    },
    expected_path="ny.it_201.line_61_total_taxes",
)

test_ny_it201_line_46_total_ny_state_taxes = create_test(
    description="NY IT-201 Line 46 (Total NYS Taxes)",
    func=ny_it201_line_46_total_ny_state_taxes,
    prepare_args=lambda inputs, policy: {
        'line_44_ny_state_tax_after_credits': computed(test_ny_it201_line_44_ny_state_tax_after_credits),
    },
    expected_path="ny.it_201.line_46_total_ny_state_taxes",
)

test_ny_it201_line_44_ny_state_tax_after_credits = create_test(
    description="NY IT-201 Line 44 (NYS Tax After Credits)",
    func=ny_it201_line_44_ny_state_tax_after_credits,
    prepare_args=lambda inputs, policy: {
        'line_39_nys_tax_on_line_38': computed(test_ny_it201_line_39_nys_tax_on_line_38),
        'line_43_nys_credits_total': computed(test_ny_it201_line_43_nys_credits_total),
    },
    expected_path="ny.it_201.line_44_ny_state_tax_after_credits",
)

test_ny_it201_line_43_nys_credits_total = create_test(
    description="NY IT-201 Line 43 (NYS Credits Total)",
    func=ny_it201_line_43_nys_credits_total,
    prepare_args=lambda inputs, policy: {
        'line_41_resident_credit': computed(test_ny_it201_line_41_resident_credit),
    },
    expected_path="ny.it_201.line_43_nys_credits_total",
)

test_ny_it201_line_41_resident_credit = create_test(
    description="NY IT-201 Line 41 (Resident Credit)",
    func=ny_it201_line_41_resident_credit,
    prepare_args=lambda inputs, policy: {
        'it112r_line_34_resident_credit': computed(test_ny_it112r_line_34_resident_credit),
    },
    expected_path="ny.it_201.line_41_resident_credit",
)

test_ny_it112r_line_34_resident_credit = create_test(
    description="IT-112-R Line 34 (Resident Credit)",
    func=ny_it112r_line_34_resident_credit,
    prepare_args=lambda inputs, policy: {
        'line_30_total_credit': computed(test_ny_it112r_line_30_total_credit),
        'line_25_ny_tax_payable': computed(test_ny_it201_line_39_nys_tax_on_line_38),
    },
    expected_path="ny.it_112_r.line_34_resident_credit",
)

test_ny_it112r_line_30_total_credit = create_test(
    description="IT-112-R Line 30 (Total Credit)",
    func=ny_it112r_line_30_total_credit,
    prepare_args=lambda inputs, policy: {
        'line_28_smaller_of_line24_or_27': computed(test_ny_it112r_line_28_smaller_of_line24_or_27),
    },
    expected_path="ny.it_112_r.line_30_total_credit",
)

test_ny_it112r_line_28_smaller_of_line24_or_27 = create_test(
    description="IT-112-R Line 28 (Smaller of Line 24 or 27)",
    func=ny_it112r_line_28_smaller_of_line24_or_27,
    prepare_args=lambda inputs, policy: {
        'line_24_total_other_state_tax': computed(test_ny_it112r_line_24_total_other_state_tax),
        'line_27_ny_tax_times_ratio': computed(test_ny_it112r_line_27_ny_tax_times_ratio),
    },
    expected_path="ny.it_112_r.line_28_smaller_of_line24_or_27",
)

test_ny_it112r_line_27_ny_tax_times_ratio = create_test(
    description="IT-112-R Line 27 (NY Tax Times Ratio)",
    func=ny_it112r_line_27_ny_tax_times_ratio,
    prepare_args=lambda inputs, policy: {
        'line_25_ny_tax_payable': computed(test_ny_it201_line_39_nys_tax_on_line_38),
        'line_26_ratio': computed(test_ny_it112r_line_26_ratio),
    },
    expected_path="ny.it_112_r.line_27_ny_tax_times_ratio",
)

test_ny_it112r_line_26_ratio = create_test(
    description="IT-112-R Line 26 (Ratio)",
    func=ny_it112r_line_26_ratio,
    prepare_args=lambda inputs, policy: {
        'line_22_total_income': computed(test_ny_it112r_line_22_total_income),
        'line_22_other_state_income': computed(test_ny_it112r_line_22_other_state_income),
    },
    expected_path="ny.it_112_r.line_26_ratio",
)

test_ny_it112r_line_24_total_other_state_tax = create_test(
    description="IT-112-R Line 24 (Total Other State Tax)",
    func=ny_it112r_line_24_total_other_state_tax,
    prepare_args=lambda inputs, policy: {
        'line_24_total_other_state_tax_items': [
            {'amount': str(tag_total(inputs, 'ny_it_112_r_line_24_other_state_tax'))}
        ],
    },
    expected_path="ny.it_112_r.line_24_total_other_state_tax",
)

test_ny_it112r_line_22_other_state_income = create_test(
    description="IT-112-R Line 22 (Other-State Income)",
    func=ny_it112r_line_22_other_state_income,
    prepare_args=lambda inputs, policy: {
        'line_22_other_state_income_items': [
            {'amount': str(tag_total(inputs, 'ny_it_112_r_line_22_other_state_income'))}
        ],
    },
    expected_path="ny.it_112_r.line_22_other_state_income",
)

test_ny_it112r_line_22_total_income = create_test(
    description="IT-112-R Line 22 (Total Income)",
    func=ny_it112r_line_22_total_income,
    prepare_args=lambda inputs, policy: {
        'line_33_ny_adjusted_gross_income': computed(test_ny_it201_line_33_ny_adjusted_gross_income),
    },
    expected_path="ny.it_112_r.line_22_total_income",
)

test_ny_it201_line_39_nys_tax_on_line_38 = create_test(
    description="NY IT-201 Line 39 (NYS Tax on Line 38 Amount)",
    func=ny_it201_line_39_nys_tax_on_line_38,
    prepare_args=lambda inputs, policy: {
        'worksheet_line_3_tax_from_rate_schedule': (
            computed(test_ny_it201_statement_2_line_3_tax_from_rate_schedule)
        ),
        'worksheet_line_4_recapture_base_amount': (
            computed(test_ny_it201_statement_2_line_4_recapture_base_amount)
        ),
        'worksheet_line_9_incremental_benefit_addback': (
            computed(test_ny_it201_statement_2_line_9_incremental_benefit_addback)
        ),
    },
    expected_path="ny.it_201.line_39_nys_tax_on_line_38",
)

test_ny_it201_statement_2_line_3_tax_from_rate_schedule = create_test(
    description="Statement 2 Line 3 (NYS Tax Rate Schedule)",
    func=ny_it201_statement_2_line_3_tax_from_rate_schedule,
    prepare_args=lambda inputs, policy: {
        'line_38_ny_taxable_income': computed(test_ny_it201_line_38_ny_taxable_income),        'policy': policy,
    },
    expected_path="ny.it_201.statement_2_tax_computation_worksheet_4.line_3_tax_from_rate_schedule",
)

test_ny_it201_statement_2_line_4_recapture_base_amount = create_test(
    description="Statement 2 Line 4 (Recapture Base Amount)",
    func=ny_it201_statement_2_line_4_recapture_base_amount,
    prepare_args=lambda inputs, policy: {        'policy': policy,
    },
    expected_path=(
        "ny.it_201.statement_2_tax_computation_worksheet_4.line_4_recapture_base_amount"
    ),
)

test_ny_it201_statement_2_line_9_incremental_benefit_addback = create_test(
    description="Statement 2 Line 9 (Incremental Benefit Addback)",
    func=ny_it201_statement_2_line_9_incremental_benefit_addback,
    prepare_args=lambda inputs, policy: {        'policy': policy,
    },
    expected_path=(
        "ny.it_201.statement_2_tax_computation_worksheet_4.line_9_incremental_benefit_addback"
    ),
)

test_ny_it201_line_58_total_nyc_yonkers_mctmt = create_test(
    description="NY IT-201 Line 58 (NYC/Yonkers Taxes + MCTMT)",
    func=ny_it201_line_58_total_nyc_yonkers_mctmt,
    prepare_args=lambda inputs, policy: {
        'line_54_nyc_tax_after_credits': computed(test_ny_it201_line_54_nyc_tax_after_credits),
        'line_54e_mctmt_total': computed(test_ny_it201_line_54e_mctmt_total),
    },
    expected_path="ny.it_201.line_58_total_nyc_yonkers_mctmt",
)

test_ny_it201_line_54e_mctmt_total = create_test(
    description="NY IT-201 Line 54e (MCTMT Total)",
    func=ny_it201_line_54e_mctmt_total,
    prepare_args=lambda inputs, policy: {
        'line_54c_mctmt_zone_1': computed(test_ny_it201_line_54c_mctmt_zone_1),
    },
    expected_path="ny.it_201.line_54e_mctmt_total",
)

test_ny_it201_line_54c_mctmt_zone_1 = create_test(
    description="NY IT-201 Line 54c (MCTMT Zone 1)",
    func=ny_it201_line_54c_mctmt_zone_1,
    prepare_args=lambda inputs, policy: {
        'line_54a_mctmt_net_earnings_zone_1': (
            computed(test_ny_it201_line_54a_mctmt_net_earnings_zone_1)
        ),
        'policy': policy,
    },
    expected_path="ny.it_201.line_54c_mctmt_zone_1",
)

test_ny_it201_line_54a_mctmt_net_earnings_zone_1 = create_test(
    description="NY IT-201 Line 54a (MCTMT Net Earnings Zone 1)",
    func=ny_it201_line_54a_mctmt_net_earnings_zone_1,
    prepare_args=lambda inputs, policy: {
        'it2105_9_worksheet_4a_line_1_net_earnings_zone_1': (
            computed(test_ny_it2105_9_worksheet_4a_line_1_net_earnings_zone_1)
        ),
    },
    expected_path="ny.it_201.line_54a_mctmt_net_earnings_zone_1",
)

test_ny_it2105_9_worksheet_4a_line_1_net_earnings_zone_1 = create_test(
    description="IT-2105.9 Worksheet 4a Line 1 (Net Earnings Zone 1)",
    func=ny_it2105_9_worksheet_4a_line_1_net_earnings_zone_1,
    prepare_args=lambda inputs, policy: {
        'worksheet_4a_line_1_net_earnings_zone_1_items': [
            {
                'ordinary_business_income': tag_total(
                    inputs, 'mctmt_base_ordinary_income', required=True
                ),
                'guaranteed_payments_services': tag_total(
                    inputs, 'mctmt_base_guaranteed_payments', required=True
                ),
            }
        ],
        'policy': policy,
    },
    expected_path="ny.it_2105_9.worksheet_4a_line_1_net_earnings_zone_1",
)

test_ny_it201_line_54_nyc_tax_after_credits = create_test(
    description="NY IT-201 Line 54 (NYC Tax After Credits)",
    func=ny_it201_line_54_nyc_tax_after_credits,
    prepare_args=lambda inputs, policy: {
        'line_52_nyc_tax_before_credits': computed(test_ny_it201_line_52_nyc_tax_before_credits),
        'line_53_nyc_nonrefundable_credits': computed(test_ny_it201_line_53_nyc_nonrefundable_credits),
    },
    expected_path="ny.it_201.line_54_nyc_tax_after_credits",
)

test_ny_it201_line_53_nyc_nonrefundable_credits = create_test(
    description="NY IT-201 Line 53 (NYC Nonrefundable Credits)",
    func=ny_it201_line_53_nyc_nonrefundable_credits,
    prepare_args=lambda inputs, policy: {
        'it201_att_line_10_total_nyc_nonrefundable_credits': (
            computed(test_ny_it201_att_line_10_total_nyc_nonrefundable_credits)
        ),
    },
    expected_path="ny.it_201.line_53_nyc_nonrefundable_credits",
)

test_ny_it201_att_line_10_total_nyc_nonrefundable_credits = create_test(
    description="IT-201-ATT Line 10 (NYC Nonrefundable Credits Total)",
    func=ny_it201_att_line_10_total_nyc_nonrefundable_credits,
    prepare_args=lambda inputs, policy: {
        'line_8_nyc_resident_ubt_credit': computed(test_ny_it201_att_line_8_nyc_resident_ubt_credit),
    },
    expected_path="ny.it_201_att.line_10_total_nyc_nonrefundable_credits",
)

test_ny_it201_att_line_8_nyc_resident_ubt_credit = create_test(
    description="IT-201-ATT Line 8 (NYC Resident UBT Credit)",
    func=ny_it201_att_line_8_nyc_resident_ubt_credit,
    prepare_args=lambda inputs, policy: {
        'it219_line_16_resident_ubt_credit': computed(test_ny_it219_line_16_resident_ubt_credit),
    },
    expected_path="ny.it_201_att.line_8_nyc_resident_ubt_credit",
)

test_ny_it219_line_16_resident_ubt_credit = create_test(
    description="IT-219 Line 16 (Resident UBT Credit)",
    func=ny_it219_line_16_resident_ubt_credit,
    prepare_args=lambda inputs, policy: {
        'line_11_income_based_credit': computed(test_ny_it219_line_11_income_based_credit),
        'line_15_total_tax': computed(test_ny_it219_line_15_total_tax),
    },
    expected_path="ny.it_219.line_16_resident_ubt_credit",
)

test_ny_it219_line_15_total_tax = create_test(
    description="IT-219 Line 15 (Total Tax for Limitation)",
    func=ny_it219_line_15_total_tax,
    prepare_args=lambda inputs, policy: {
        'line_12_nyc_tax_less_household_credit': (
            computed(test_ny_it201_line_49_nyc_tax_after_household_credit)
        ),
    },
    expected_path="ny.it_219.line_15_total_tax",
)

test_ny_it219_line_11_income_based_credit = create_test(
    description="IT-219 Line 11 (Income-Based Credit)",
    func=ny_it219_line_11_income_based_credit,
    prepare_args=lambda inputs, policy: {
        'line_8_total_ubt_credit': computed(test_ny_it219_line_8_total_ubt_credit),
        'line_10_income_factor': computed(test_ny_it219_line_10_income_factor),
    },
    expected_path="ny.it_219.line_11_income_based_credit",
)

test_ny_it219_line_10_income_factor = create_test(
    description="IT-219 Line 10 (Income Factor)",
    func=ny_it219_line_10_income_factor,
    prepare_args=lambda inputs, policy: {
        'line_9_taxable_income': computed(test_ny_it219_line_9_taxable_income),
        'policy': policy,
    },
    expected_path="ny.it_219.line_10_income_factor",
)

test_ny_it219_line_9_taxable_income = create_test(
    description="IT-219 Line 9 (Taxable Income)",
    func=ny_it219_line_9_taxable_income,
    prepare_args=lambda inputs, policy: {
        'line_47_nyc_taxable_income': computed(test_ny_it201_line_47_nyc_taxable_income),
    },
    expected_path="ny.it_219.line_9_taxable_income",
)

test_ny_it219_line_8_total_ubt_credit = create_test(
    description="IT-219 Line 8 (Total UBT Credit)",
    func=ny_it219_line_8_total_ubt_credit,
    prepare_args=lambda inputs, policy: {
        'line_7_beneficiary_ubt_credit': computed(test_ny_it219_line_7_beneficiary_ubt_credit),
    },
    expected_path="ny.it_219.line_8_total_ubt_credit",
)

test_ny_it219_line_7_beneficiary_ubt_credit = create_test(
    description="IT-219 Line 7 (Beneficiary UBT Credit)",
    func=ny_it219_line_7_beneficiary_ubt_credit,
    prepare_args=lambda inputs, policy: {
        'line_7_beneficiary_ubt_credit_items': [
            {'amount': str(tag_total(inputs, 'ny_it_219_line_7_ubt_credit'))}
        ],
    },
    expected_path="ny.it_219.line_7_beneficiary_ubt_credit",
)

test_ny_it201_att_line_18_total_other_refundable_credits = create_test(
    description="IT-201-ATT Line 18 (Total Other Refundable Credits)",
    func=ny_it201_att_line_18_total_other_refundable_credits,
    prepare_args=lambda inputs, policy: {
        'line_14_total_refundable_credits': computed(test_ny_it201_att_line_14_total_refundable_credits),
    },
    expected_path="ny.it_201_att.line_18_total_other_refundable_credits",
)

test_ny_it201_att_line_14_total_refundable_credits = create_test(
    description="IT-201-ATT Line 14 (Total Refundable Credits)",
    func=ny_it201_att_line_14_total_refundable_credits,
    prepare_args=lambda inputs, policy: {
        'line_13_total_refundable_credits': computed(test_ny_it201_att_line_13_total_refundable_credits),
    },
    expected_path="ny.it_201_att.line_14_total_refundable_credits",
)

test_ny_it201_att_line_13_total_refundable_credits = create_test(
    description="IT-201-ATT Line 13 (Total Refundable Credits)",
    func=ny_it201_att_line_13_total_refundable_credits,
    prepare_args=lambda inputs, policy: {
        'line_12_other_refundable_credits': computed(test_ny_it201_att_line_12_other_refundable_credits),
    },
    expected_path="ny.it_201_att.line_13_total_refundable_credits",
)

test_ny_it201_att_line_12_other_refundable_credits = create_test(
    description="IT-201-ATT Line 12 (Other Refundable Credits)",
    func=ny_it201_att_line_12_other_refundable_credits,
    prepare_args=lambda inputs, policy: {
        'line_12_other_refundable_credits_items': [
            {'amount': str(tag_total(inputs, 'ny_it_201_att_line_12_amount'))}
        ],
    },
    expected_path="ny.it_201_att.line_12_other_refundable_credits",
)

test_ny_it201_line_71_other_refundable_credits = create_test(
    description="NY IT-201 Line 71 (Other Refundable Credits)",
    func=ny_it201_line_71_other_refundable_credits,
    prepare_args=lambda inputs, policy: {
        'it201_att_line_18_total_other_refundable_credits': (
            computed(test_ny_it201_att_line_18_total_other_refundable_credits)
        ),
    },
    expected_path="ny.it_201.line_71_other_refundable_credits",
)

test_ny_it201_line_52_nyc_tax_before_credits = create_test(
    description="NY IT-201 Line 52 (NYC Tax Before Credits)",
    func=ny_it201_line_52_nyc_tax_before_credits,
    prepare_args=lambda inputs, policy: {
        'line_49_nyc_tax_after_household_credit': computed(test_ny_it201_line_49_nyc_tax_after_household_credit),
    },
    expected_path="ny.it_201.line_52_nyc_tax_before_credits",
)

test_ny_it201_line_49_nyc_tax_after_household_credit = create_test(
    description="NY IT-201 Line 49 (NYC Tax After Household Credit)",
    func=ny_it201_line_49_nyc_tax_after_household_credit,
    prepare_args=lambda inputs, policy: {
        'line_47a_nyc_resident_tax': computed(test_ny_it201_line_47a_nyc_resident_tax),
    },
    expected_path="ny.it_201.line_49_nyc_tax_after_household_credit",
)

test_ny_it201_line_47a_nyc_resident_tax = create_test(
    description="NY IT-201 Line 47a (NYC Resident Tax)",
    func=ny_it201_line_47a_nyc_resident_tax,
    prepare_args=lambda inputs, policy: {
        'line_47_nyc_taxable_income': computed(test_ny_it201_line_47_nyc_taxable_income),        'policy': policy,
    },
    expected_path="ny.it_201.line_47a_nyc_resident_tax",
)

test_ny_it201_line_47_nyc_taxable_income = create_test(
    description="NY IT-201 Line 47 (NYC Taxable Income)",
    func=ny_it201_line_47_nyc_taxable_income,
    prepare_args=lambda inputs, policy: {
        'line_38_ny_taxable_income': computed(test_ny_it201_line_38_ny_taxable_income),
    },
    expected_path="ny.it_201.line_47_nyc_taxable_income",
)

test_ny_it201_line_38_ny_taxable_income = create_test(
    description="NY IT-201 Line 38 (NY Taxable Income)",
    func=ny_it201_line_38_ny_taxable_income,
    prepare_args=lambda inputs, policy: {
        'line_35_ny_taxable_income_before_exemptions': computed(test_ny_it201_line_35_ny_taxable_income_before_exemptions),
        'line_36_dependent_exemptions': computed(test_ny_it201_line_36_dependent_exemptions),
    },
    expected_path="ny.it_201.line_38_ny_taxable_income",
)

test_ny_it201_line_35_ny_taxable_income_before_exemptions = create_test(
    description="NY IT-201 Line 35 (NY Taxable Income Before Exemptions)",
    func=ny_it201_line_35_ny_taxable_income_before_exemptions,
    prepare_args=lambda inputs, policy: {
        'line_33_ny_adjusted_gross_income': computed(test_ny_it201_line_33_ny_adjusted_gross_income),
        'line_34_standard_deduction': computed(test_ny_it201_line_34_standard_deduction),
    },
    expected_path="ny.it_201.line_35_ny_taxable_income_before_exemptions",
)

test_ny_it201_line_36_dependent_exemptions = create_test(
    description="NY IT-201 Line 36 (Dependent Exemptions)",
    func=ny_it201_line_36_dependent_exemptions,
    prepare_args=lambda inputs, policy: {
        'dependents_count': tag_total(inputs, 'ny_dependents_count', required=True),
        'policy': policy,
    },
    expected_path="ny.it_201.line_36_dependent_exemptions",
)

test_ny_it201_line_34_standard_deduction = create_test(
    description="NY IT-201 Line 34 (Standard Deduction)",
    func=ny_it201_line_34_standard_deduction,
    prepare_args=lambda inputs, policy: {        'policy': policy,
    },
    expected_path="ny.it_201.line_34_standard_deduction",
)

test_ny_it201_line_33_ny_adjusted_gross_income = create_test(
    description="NY IT-201 Line 33 (NY Adjusted Gross Income)",
    func=ny_it201_line_33_ny_adjusted_gross_income,
    prepare_args=lambda inputs, policy: {
        'line_24_ny_total_income': computed(test_ny_it201_line_24_ny_total_income),
        'line_32_ny_total_subtractions': computed(test_ny_it201_line_32_ny_total_subtractions),
    },
    expected_path="ny.it_201.line_33_ny_adjusted_gross_income",
)

test_ny_it201_line_28_us_gov_bond_interest = create_test(
    description="NY IT-201 Line 28 (U.S. Government Bond Interest)",
    func=ny_it201_line_28_us_gov_bond_interest,
    prepare_args=lambda inputs, policy: {
        'line_28_us_gov_bond_interest_items': [
            {
                'fund': fund,
                'amount': tag_total(
                    inputs, f'ny_it_201_line_28_us_gov_bond_interest_items_{fund}'
                ),
            }
            for fund in policy.get('ny_us_gov_bond_interest_percentages', {})
        ],
        'policy': policy,
    },
    expected_path="ny.it_201.line_28_us_gov_bond_interest",
)

test_ny_it201_line_32_ny_total_subtractions = create_test(
    description="NY IT-201 Line 32 (NY Total Subtractions)",
    func=ny_it201_line_32_ny_total_subtractions,
    prepare_args=lambda inputs, policy: {
        'line_28_us_gov_bond_interest': computed(test_ny_it201_line_28_us_gov_bond_interest),
    },
    expected_path="ny.it_201.line_32_ny_total_subtractions",
)

test_ny_it201_line_19_federal_agi = create_test(
    description="NY IT-201 Line 19 (Federal AGI)",
    func=ny_it201_line_19_federal_agi,
    prepare_args=lambda inputs, policy: {
        'line_17_total_federal_income': computed(test_ny_it201_line_17_total_federal_income),
        'line_18_federal_adjustments': computed(test_ny_it201_line_18_federal_adjustments),
    },
    expected_path="ny.it_201.line_19_federal_agi",
)

test_ny_it201_line_24_ny_total_income = create_test(
    description="NY IT-201 Line 24 (NY Total Income)",
    func=ny_it201_line_24_ny_total_income,
    prepare_args=lambda inputs, policy: {
        'line_19_federal_agi': computed(test_ny_it201_line_19_federal_agi),
        'line_21_public_employee_414h': tag_or_else(
            inputs, 'ny_it_201_line_21_public_employee_414h', lambda: Decimal('0')
        ),
        'line_22_ny_529_distributions': tag_or_else(
            inputs, 'ny_it_201_line_22_ny_529_distributions', lambda: Decimal('0')
        ),
        'line_23_other_additions': computed(test_ny_it201_line_23_other_additions),
    },
    expected_path="ny.it_201.line_24_ny_total_income",
)

test_ny_it201_line_23_other_additions = create_test(
    description="NY IT-201 Line 23 (Other Additions)",
    func=ny_it201_line_23_other_additions,
    prepare_args=lambda inputs, policy: {
        'it225_line_9_total_additions': computed(test_ny_it225_line_9_total_additions),
    },
    expected_path="ny.it_201.line_23_other_additions",
)

test_ny_it225_line_9_total_additions = create_test(
    description="NY IT-225 Line 9 (Total Additions)",
    func=ny_it225_line_9_total_additions,
    prepare_args=lambda inputs, policy: {
        'line_4_total_part1_additions': computed(test_ny_it225_line_4_total_part1_additions),
        'line_8_total_part2_additions': computed(test_ny_it225_line_8_total_part2_additions),
    },
    expected_path="ny.it_225.line_9_total_additions",
)

test_ny_it225_line_8_total_part2_additions = create_test(
    description="NY IT-225 Line 8 (Total Part 2 Additions)",
    func=ny_it225_line_8_total_part2_additions,
    prepare_args=lambda inputs, policy: {
        'line_6_total_part2_additions': computed(test_ny_it225_line_6_total_part2_additions),
    },
    expected_path="ny.it_225.line_8_total_part2_additions",
)

test_ny_it225_line_5b_additions = create_test(
    description="NY IT-225 Line 5b (Part 2 Additions)",
    func=ny_it225_line_5b_additions,
    prepare_args=lambda inputs, policy: {
        'line_5b_additions_items': [
            {'amount': str(tag_total(inputs, 'ny_it_225_line_5b_addition'))}
        ],
    },
    expected_path="ny.it_225.line_5b_additions",
)

test_ny_it225_line_5a_additions = create_test(
    description="NY IT-225 Line 5a (Part 2 Additions)",
    func=ny_it225_line_5a_additions,
    prepare_args=lambda inputs, policy: {
        'line_5a_additions_items': [
            {'amount': str(tag_total(inputs, 'ny_it_225_line_5a_addition'))}
        ],
    },
    expected_path="ny.it_225.line_5a_additions",
)

test_ny_it225_line_6_total_part2_additions = create_test(
    description="NY IT-225 Line 6 (Total Part 2 Additions)",
    func=ny_it225_line_6_total_part2_additions,
    prepare_args=lambda inputs, policy: {
        'line_5a_additions': computed(test_ny_it225_line_5a_additions),
        'line_5b_additions': computed(test_ny_it225_line_5b_additions),
    },
    expected_path="ny.it_225.line_6_total_part2_additions",
)

test_ny_it225_line_4_total_part1_additions = create_test(
    description="NY IT-225 Line 4 (Total Part 1 Additions)",
    func=ny_it225_line_4_total_part1_additions,
    prepare_args=lambda inputs, policy: {
        'line_2_total_part1_additions': computed(test_ny_it225_line_2_total_part1_additions),
    },
    expected_path="ny.it_225.line_4_total_part1_additions",
)

test_ny_it225_line_1a_additions = create_test(
    description="NY IT-225 Line 1a (Part 1 Additions)",
    func=ny_it225_line_1a_additions,
    prepare_args=lambda inputs, policy: {
        'line_1a_additions_items': [
            {'amount': str(tag_total(inputs, 'ny_it_201_att_line_12_amount'))}
        ],
    },
    expected_path="ny.it_225.line_1a_additions",
)

test_ny_it225_line_2_total_part1_additions = create_test(
    description="NY IT-225 Line 2 (Total Part 1 Additions)",
    func=ny_it225_line_2_total_part1_additions,
    prepare_args=lambda inputs, policy: {
        'line_1a_additions': computed(test_ny_it225_line_1a_additions),
    },
    expected_path="ny.it_225.line_2_total_part1_additions",
)

test_ny_it201_line_18_federal_adjustments = create_test(
    description="NY IT-201 Line 18 (Federal Adjustments)",
    func=ny_it201_line_18_federal_adjustments,
    prepare_args=lambda inputs, policy: {
        'federal_schedule_1_line_26_adjustments_to_income': (
            computed(test_federal_schedule_1_line_26_adjustments_to_income)
        ),
    },
    expected_path="ny.it_201.line_18_federal_adjustments",
)

test_ny_it201_line_17_total_federal_income = create_test(
    description="NY IT-201 Line 17 (Total Federal Income)",
    func=ny_it201_line_17_total_federal_income,
    prepare_args=lambda inputs, policy: {
        'federal_form_1040_line_9_total_income': computed(test_federal_form_1040_line_9_total_income),
    },
    expected_path="ny.it_201.line_17_total_federal_income",
)

test_compute_federal_total_tax = create_test(
    description="Federal Total Tax (computed from all inputs)",
    func=compute_federal_total_tax,
    prepare_args=lambda inputs, policy: {
        'inputs': inputs,
        'policy': policy,
    },
    expected_path="federal.compute_total_tax",
    use_inputs_index=False,
)

test_compute_ny_total_tax = create_test(
    description="NY Total Tax (computed from all inputs)",
    func=compute_ny_total_tax,
    prepare_args=lambda inputs, policy: {
        'inputs': inputs,
        'policy': policy,
    },
    expected_path="ny.compute_total_tax",
    use_inputs_index=False,
)


if __name__ == '__main__':
    print("Running expected-value tests across years...\n")
    test_expected_values()
    print("\nAll tests passed!")
