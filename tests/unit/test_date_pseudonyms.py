from __future__ import annotations

import pytest

from belgian_deduce.date_pseudonyms import pseudonymize_date_text


def bracketed(value: str) -> str:
    return f"[{value}]"


@pytest.mark.parametrize(
    ("source", "shift_days", "expected"),
    [
        ("05/03/2024", 10, "15/03/2024"),
        ("20-10-15", 17, "06-11-15"),
        ("27-2-16", 17, "15-3-16"),
        ("26-12-00", 17, "12-01-01"),
        ("07/ 09 3", 17, "24/ 09 3"),
        ("2024-03-05", 10, "2024-03-15"),
        ("06/08/20219", 17, "23/08/2021"),
        ("24 /18", 17, "10 /18"),
        ("12 maart 1981", 20, "1 april 1981"),
        ("23 juni", 17, "10 juli"),
        ("ma 05/03/2024", 10, "vr 15/03/2024"),
    ],
)
def test_exact_dates_preserve_source_style_after_shift(
    source: str,
    shift_days: int,
    expected: str,
) -> None:
    assert pseudonymize_date_text(
        source, label="Date", date_shift_days=shift_days
    ) == bracketed(expected)


@pytest.mark.parametrize(
    ("source", "shift_days", "expected"),
    [
        ("september 2024", 10, "september/oktober 2024"),
        ("september", 17, "september/oktober"),
        ("zomer 2021", 10, "zomer/herfst 2021"),
        ("2021", 10, "2021/2022"),
        ("Rond 2007", 17, "Rond 2007/2008"),
        ("29/minuut\t\n2004", 17, "2004/2005"),
        ("08/2024", 10, "08/2024-09/2024"),
    ],
)
def test_approximate_dates_preserve_granularity_with_ranges(
    source: str,
    shift_days: int,
    expected: str,
) -> None:
    assert pseudonymize_date_text(
        source, label="Date", date_shift_days=shift_days
    ) == bracketed(expected)


def test_two_digit_year_can_use_document_creation_date_for_century() -> None:
    assert pseudonymize_date_text(
        "31/12/35",
        label="Age_Birthdate",
        date_shift_days=1,
        document_creation_date="15/01/2040 12:00:00",
    ) == bracketed("4 jaar oud")


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("14/05/2013", "13 jaar oud"),
        ("14/09/2022", "3 jaren, 8 maanden oud"),
        ("14/04/2025", "13 maanden oud"),
        ("28/02/2026", "2 maanden, 2 weken oud"),
        ("16/03/2026", "8 weken, 3 dagen oud"),
        ("07/05/2026", "7 dagen oud"),
    ],
)
def test_birthdates_reduce_to_age_granularity_when_document_date_is_available(
    source: str,
    expected: str,
) -> None:
    assert pseudonymize_date_text(
        source,
        label="Age_Birthdate",
        date_shift_days=0,
        document_creation_date="14/05/2026 12:00:00",
    ) == bracketed(expected)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("17/04/2026", "27 dagen oud"),
        ("16/04/2026", "4 weken oud"),
        ("15/03/2026", "8 weken, 4 dagen oud"),
        ("14/03/2026", "2 maanden oud"),
        ("14/02/2026", "3 maanden oud"),
        ("13/02/2026", "3 maanden oud"),
        ("14/11/2025", "6 maanden oud"),
        ("14/05/2024", "2 jaar oud"),
        ("15/05/2013", "12 jaren, 11 maanden oud"),
        ("14/05/2013", "13 jaar oud"),
    ],
)
def test_birthdate_age_granularity_boundaries(
    source: str,
    expected: str,
) -> None:
    assert pseudonymize_date_text(
        source,
        label="Age_Birthdate",
        date_shift_days=0,
        document_creation_date="14/05/2026 12:00:00",
    ) == bracketed(expected)


def test_birthdate_age_uses_shifted_document_date_to_preserve_age() -> None:
    assert pseudonymize_date_text(
        "14/05/2013",
        label="Age_Birthdate",
        date_shift_days=17,
        document_creation_date="14/05/2026 12:00:00",
    ) == bracketed("13 jaar oud")


@pytest.mark.parametrize(
    ("source", "shift_days", "expected"),
    [
        ("31/12/1980", 1, "1981"),
        ("23-nov-2016", 17, "2016"),
        ("19- \n09-1989", 17, "1989"),
        ("zomer 1980", 200, "1980/1981"),
        ("6-jarig", 10, "6-jarig"),
        ("12 jaar", 10, "12 jaar"),
        ("14 jaar jongere", 17, "14 jaar jongere"),
        ("7 jaar 7 maand", 17, "7 jaar 7 maand"),
        ("7 years 7 months", 17, "7 years 7 months"),
        ("3 jaar, 0 maanden", 17, "3 jaar, 0 maanden"),
        ("35 maanden 23 dagen", 17, "35 maanden 23 dagen"),
        ("61,2 yrs", 17, "61,2 yrs"),
        ("3 maanden", 10, "3 maanden"),
        ("2 weken", 10, "2 weken"),
        ("4 dagen", 10, "4 dagen"),
        ("45j", 10, "45j"),
    ],
)
def test_birthdates_shift_then_reduce_to_year_granularity(
    source: str,
    shift_days: int,
    expected: str,
) -> None:
    assert pseudonymize_date_text(
        source,
        label="Age_Birthdate",
        date_shift_days=shift_days,
    ) == bracketed(expected)


@pytest.mark.parametrize(
    ("source", "shift_days", "expected"),
    [
        ("5-10 juni 2023", 10, "15-20 juni 2023"),
        ("25-30 juni 2023", 10, "5-10 juli 2023"),
        ("25/7", 17, "11/8"),
        ("20-10", 17, "6-11"),
        ("10-31/08", 17, "27/08-17/09"),
        ("12/02-14/06", 10, "22/02-24/06"),
        ("12/7/25-23/8/25", 10, "22/7/25-2/9/25"),
    ],
)
def test_date_ranges_shift_both_bounds_and_preserve_visible_precision(
    source: str,
    shift_days: int,
    expected: str,
) -> None:
    assert pseudonymize_date_text(
        source, label="Date", date_shift_days=shift_days
    ) == bracketed(expected)


@pytest.mark.parametrize(
    ("source", "shift_days", "expected"),
    [
        ("08/2024-09/2024", 10, "08/2024-10/2024"),
        ("8/2024 - 9/2024", 10, "8/2024 - 10/2024"),
        ("08-2024 - 09-2024", 10, "08-2024 - 10-2024"),
        ("augustus 2024-september 2024", 10, "augustus 2024-oktober 2024"),
        ("aug. 2024 - sep. 2024", 10, "aug. 2024 - okt. 2024"),
        ("december 2024 - januari 2025", 10, "december 2024 - februari 2025"),
    ],
)
def test_month_year_ranges_shift_as_month_granularity_periods(
    source: str,
    shift_days: int,
    expected: str,
) -> None:
    assert pseudonymize_date_text(
        source, label="Date", date_shift_days=shift_days
    ) == bracketed(expected)


@pytest.mark.parametrize(
    "context_before",
    ["Leeftijd: ", "Jaren: ", "Maanden: ", "Dagen: "],
)
def test_standalone_numeric_age_uses_age_context_without_rewriting_value(
    context_before: str,
) -> None:
    assert pseudonymize_date_text(
        "15",
        label="Age_Birthdate",
        date_shift_days=17,
        context_before=context_before,
    ) == bracketed("15")


def test_month_phase_with_month_substitutes_month_interval() -> None:
    assert pseudonymize_date_text(
        "eind november", label="Date", date_shift_days=17
    ) == bracketed("begin/midden december")


def test_half_month_substitutes_as_middle_phase_range() -> None:
    assert pseudonymize_date_text(
        "half juli", label="Date", date_shift_days=17
    ) == bracketed("eind juli/begin augustus")


def test_compound_month_phase_with_month_substitutes_range() -> None:
    assert pseudonymize_date_text(
        "midden/eind november", label="Date", date_shift_days=17
    ) == bracketed("eind november/midden december")


def test_birthdate_shift_reduces_to_shifted_year() -> None:
    assert pseudonymize_date_text(
        "23-nov-2016", label="Age_Birthdate", date_shift_days=17
    ) == bracketed("2016")
    assert pseudonymize_date_text(
        "23-dec-2016", label="Age_Birthdate", date_shift_days=17
    ) == bracketed("2017")


@pytest.mark.parametrize(
    ("context_before", "source", "expected"),
    [
        ("sample_day ::: ", "1", "18"),
        ("sample day ::: ", "1", "18"),
        ("sample-day ::: ", "1", "18"),
        ("sample_month ::: ", "10", "10/11"),
        ("sample.month ::: ", "10", "10/11"),
        ("sample_year ::: ", "2012", "2012/2013"),
        ("sampleYear ::: ", "2012", "2012/2013"),
    ],
)
def test_standalone_numeric_date_uses_english_component_context(
    context_before: str,
    source: str,
    expected: str,
) -> None:
    assert pseudonymize_date_text(
        source,
        label="Date",
        date_shift_days=17,
        context_before=context_before,
    ) == bracketed(expected)


def test_standalone_numeric_date_without_component_context_keeps_value() -> None:
    assert pseudonymize_date_text("10", label="Date", date_shift_days=17) == bracketed(
        "10"
    )


def test_standalone_numeric_date_uses_dutch_component_context() -> None:
    assert pseudonymize_date_text(
        "10",
        label="Date",
        date_shift_days=17,
        context_before="Geboorte dag: ",
    ) == bracketed("27")


@pytest.mark.parametrize(
    ("context_before", "source", "shift_days", "expected"),
    [
        ("Jaar: ", "69", 17, "1969/1970"),
        ("Maand: ", "9", 17, "9/10"),
        ("dag: ", "20", 17, "6"),
        ("birth_day ::: ", "10", 17, "27"),
        ("birth day ::: ", "10", 17, "27"),
        ("birth-day ::: ", "10", 17, "27"),
        ("birth.day ::: ", "10", 17, "27"),
        ("birth_month ::: ", "2", 17, "2/3"),
        ("birthMonth ::: ", "2", 17, "2/3"),
        ("birth_year ::: ", "1933", 17, "1933/1934"),
        ("birty year ::: ", "1933", 17, "1933/1934"),
        ("geboorte maand ::: ", "2", 17, "2/3"),
    ],
)
def test_standalone_numeric_birthdate_uses_date_component_context(
    context_before: str,
    source: str,
    shift_days: int,
    expected: str,
) -> None:
    assert pseudonymize_date_text(
        source,
        label="Age_Birthdate",
        date_shift_days=shift_days,
        context_before=context_before,
    ) == bracketed(expected)


def test_standalone_numeric_birthdate_without_context_keeps_value() -> None:
    assert pseudonymize_date_text(
        "15", label="Age_Birthdate", date_shift_days=17
    ) == bracketed("15")


@pytest.mark.parametrize(
    ("source", "label", "shift_days"),
    [
        ("niet te parseren", "Date", 10),
        ("05/03/2024", "Date", None),
    ],
)
def test_unsupported_or_unshifted_dates_return_none_for_placeholder_fallback(
    source: str,
    label: str,
    shift_days: int | None,
) -> None:
    assert (
        pseudonymize_date_text(source, label=label, date_shift_days=shift_days) is None
    )
