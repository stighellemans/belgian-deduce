from __future__ import annotations

import pytest

from belgian_deduce import post_process as POST_PROCESS

REGEX_BY_LABEL = POST_PROCESS.REGEX_BY_LABEL
attach_dr_period_if_present = POST_PROCESS.attach_dr_period_if_present
attach_initial_period_if_present = POST_PROCESS.attach_initial_period_if_present
auto_add_patient_name_spans = POST_PROCESS.auto_add_patient_name_spans
balance_enclosing_brackets = POST_PROCESS.balance_enclosing_brackets
drop_non_alnum_spans = POST_PROCESS.drop_non_alnum_spans
extend_date_with_weekday = POST_PROCESS.extend_date_with_weekday
extend_spans_to_regex = POST_PROCESS.extend_spans_to_regex
merge_adjacent_name_patient = POST_PROCESS.merge_adjacent_name_patient
post_process_spans = POST_PROCESS.post_process_spans
trim = POST_PROCESS.trim


def make_span(label: str, text: str, fragment: str) -> dict:
    begin = text.index(fragment)
    return {
        "label": label,
        "begin": begin,
        "end": begin + len(fragment),
        "text": fragment,
    }


@pytest.mark.parametrize(
    ("text", "fragment", "expected"),
    [
        (
            "Ga naar https://example.com/a/b?x=1.",
            "https://example",
            "https://example.com/a/b?x=1",
        ),
        (
            "Zie www.example.com/path voor details.",
            "www.example",
            "www.example.com/path",
        ),
        (
            "Gebruik sftp://files.example.com/upload.",
            "sftp://files",
            "sftp://files.example.com/upload",
        ),
        (
            "Pad file:///Users/demo/report.pdf.",
            "file:///Users",
            "file:///Users/demo/report.pdf",
        ),
        (
            "Mail mailto:patient@example.com.",
            "mailto:patient",
            "mailto:patient@example.com",
        ),
        (
            "Bel tel:+32470123456.",
            "tel:+324",
            "tel:+32470123456",
        ),
    ],
)
def test_contactdetails_urls_extend_to_complete_match(
    text: str, fragment: str, expected: str
) -> None:
    result = post_process_spans([make_span("Contactdetails", text, fragment)], text)

    assert result[0]["text"] == expected
    assert result[0]["begin"] == text.index(expected)
    assert result[0]["end"] == text.index(expected) + len(expected)


def test_contactdetails_reattaches_leading_plus_after_trim() -> None:
    text = "+32470123456"
    span = make_span("Contactdetails", text, text)

    result = post_process_spans([span], text)

    assert result[0]["text"] == text
    assert result[0]["begin"] == 0
    assert result[0]["end"] == len(text)


def test_trim_strips_non_effective_alnum_from_both_sides() -> None:
    text = "°Jan·"

    assert trim(0, len(text), text) == (1, 4)


def test_trim_leaves_invalid_bounds_unchanged() -> None:
    assert trim(3, 1, "Jan") == (3, 1)


def test_terminal_caregiver_dr_does_not_crash() -> None:
    text = "dokter dr"
    span = make_span("Name:Caregiver", text, "dr")

    result = post_process_spans([span], text)

    assert result == [span]


def test_caregiver_dr_period_is_extended_when_present() -> None:
    text = "dokter dr."
    span = make_span("Name:Caregiver", text, "dr")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "dr."
    assert result[0]["end"] == len(text)


def test_prof_title_prefix_merges_into_caregiver_name() -> None:
    text = "prof. dr. D. De Ridder"
    spans = [
        make_span("Name", text, "prof"),
        make_span("Name:Caregiver", text, "dr. D. De Ridder"),
    ]

    result = post_process_spans(spans, text)

    assert result == [
        {
            "label": "Name:Caregiver",
            "begin": 0,
            "end": len(text),
            "text": text,
        }
    ]


def test_multiple_title_prefixes_merge_into_caregiver_name() -> None:
    text = "prof. dr. D. De Ridder"
    spans = [
        make_span("Name", text, "prof"),
        make_span("Name", text, "dr"),
        make_span("Name:Caregiver", text, "D. De Ridder"),
    ]

    result = post_process_spans(spans, text)

    assert result == [
        {
            "label": "Name:Caregiver",
            "begin": 0,
            "end": len(text),
            "text": text,
        }
    ]


def test_compact_unannotated_title_prefix_merges_into_caregiver_name() -> None:
    text = "Prof.dr.Stevens W."
    spans = [
        make_span("Name", text, "dr."),
        make_span("Name:Caregiver", text, "Stevens W."),
    ]

    result = post_process_spans(spans, text)

    assert result == [
        {
            "label": "Name:Caregiver",
            "begin": 0,
            "end": len(text),
            "text": text,
        }
    ]


def test_unannotated_compact_title_chain_expands_caregiver_name() -> None:
    text = "Prof.dr.Stevens W."
    span = make_span("Name:Caregiver", text, "Stevens W.")

    result = post_process_spans([span], text)

    assert result == [
        {
            "label": "Name:Caregiver",
            "begin": 0,
            "end": len(text),
            "text": text,
        }
    ]


@pytest.mark.parametrize(
    "title_prefix",
    [
        "Dokter ",
        "dokter ",
        "Doctor ",
        "dr ",
        "dr. ",
        "Dr.",
        "DR. ",
        "prof ",
        "prof. ",
        "Professor ",
    ],
)
def test_unannotated_professional_title_prefix_expands_caregiver_name(
    title_prefix: str,
) -> None:
    text = f"{title_prefix}Kenis Sandra"
    span = make_span("Name:Caregiver", text, "Kenis Sandra")

    result = post_process_spans([span], text)

    assert result == [
        {
            "label": "Name:Caregiver",
            "begin": 0,
            "end": len(text),
            "text": text,
        }
    ]


def test_unannotated_dokter_prefix_expands_multiple_caregiver_names() -> None:
    text = "Dokter Kenis Sandra Dokter Laridon Annick"
    spans = [
        make_span("Name:Caregiver", text, "Kenis Sandra"),
        make_span("Name:Caregiver", text, "Laridon Annick"),
    ]

    result = post_process_spans(spans, text)

    assert result == [
        {
            "label": "Name:Caregiver",
            "begin": 0,
            "end": len("Dokter Kenis Sandra"),
            "text": "Dokter Kenis Sandra",
        },
        {
            "label": "Name:Caregiver",
            "begin": text.index("Dokter Laridon Annick"),
            "end": len(text),
            "text": "Dokter Laridon Annick",
        },
    ]


def test_mixed_prefix_title_chains_expand_multiple_caregiver_names() -> None:
    text = "Prof. Dr. Kenis Sandra Dr. Prof. Laridon Annick"
    spans = [
        make_span("Name:Caregiver", text, "Kenis Sandra"),
        make_span("Name:Caregiver", text, "Laridon Annick"),
    ]

    result = post_process_spans(spans, text)

    assert result == [
        {
            "label": "Name:Caregiver",
            "begin": 0,
            "end": len("Prof. Dr. Kenis Sandra"),
            "text": "Prof. Dr. Kenis Sandra",
        },
        {
            "label": "Name:Caregiver",
            "begin": text.index("Dr. Prof. Laridon Annick"),
            "end": len(text),
            "text": "Dr. Prof. Laridon Annick",
        },
    ]


def test_comma_separated_prefix_title_chains_expand_multiple_caregiver_names() -> None:
    text = "Prof., Dr. Kenis Sandra Dr., Prof. Laridon Annick"
    spans = [
        make_span("Name:Caregiver", text, "Kenis Sandra"),
        make_span("Name:Caregiver", text, "Laridon Annick"),
    ]

    result = post_process_spans(spans, text)

    assert result == [
        {
            "label": "Name:Caregiver",
            "begin": 0,
            "end": len("Prof., Dr. Kenis Sandra"),
            "text": "Prof., Dr. Kenis Sandra",
        },
        {
            "label": "Name:Caregiver",
            "begin": text.index("Dr., Prof. Laridon Annick"),
            "end": len(text),
            "text": "Dr., Prof. Laridon Annick",
        },
    ]


@pytest.mark.parametrize(
    ("text", "title_fragment"),
    [
        ("Dokter Kenis Sandra", "Dokter"),
        ("doctor Kenis Sandra", "doctor"),
        ("professor Kenis Sandra", "professor"),
        ("DR. Kenis Sandra", "DR"),
    ],
)
def test_professional_title_span_merges_into_caregiver_name(
    text: str, title_fragment: str
) -> None:
    spans = [
        make_span("Name", text, title_fragment),
        make_span("Name:Caregiver", text, "Kenis Sandra"),
    ]

    result = post_process_spans(spans, text)

    assert result == [
        {
            "label": "Name:Caregiver",
            "begin": 0,
            "end": len(text),
            "text": text,
        }
    ]


def test_adjacent_split_ocr_dr_prefix_merges_into_caregiver_name() -> None:
    text = "Dr.Kenis S.,"
    spans = [
        make_span("Name", text, "D"),
        make_span("Name:Caregiver", text, "r.Kenis S"),
    ]

    result = post_process_spans(spans, text)

    assert result == [
        {
            "label": "Name:Caregiver",
            "begin": 0,
            "end": text.index(","),
            "text": "Dr.Kenis S.",
        }
    ]


def test_standalone_d_fragment_does_not_merge_into_caregiver_name() -> None:
    text = "David"
    spans = [
        make_span("Name", text, "D"),
        make_span("Name:Caregiver", text, "avid"),
    ]

    result = post_process_spans(spans, text)

    assert result == spans


def test_caregiver_metadata_recovers_dokter_titled_names() -> None:
    text = "Dokter Kenis Sandra Dokter Laridon Annick"

    result = post_process_spans(
        [],
        text,
        metadata={
            "caregiver_names": [
                {"given_name": "Sandra", "family_name": "Kenis"},
                {"given_name": "Annick", "family_name": "Laridon"},
            ]
        },
    )

    assert [span["text"] for span in result] == [
        "Dokter Kenis Sandra",
        "Dokter Laridon Annick",
    ]
    assert {span["label"] for span in result} == {"Name:Caregiver"}
    assert {span["subtype"] for span in result} == {"Caregiver"}


def test_trailing_titles_do_not_merge_across_next_titled_caregiver_name() -> None:
    text = "Kenis Sandra, Dokter Laridon Annick, Dokter"
    spans = [
        make_span("Name:Caregiver", text, "Kenis Sandra"),
        make_span("Name:Caregiver", text, "Laridon Annick"),
    ]

    result = post_process_spans(spans, text)

    assert result == [
        {
            "label": "Name:Caregiver",
            "begin": 0,
            "end": len("Kenis Sandra, Dokter"),
            "text": "Kenis Sandra, Dokter",
        },
        {
            "label": "Name:Caregiver",
            "begin": text.index("Laridon Annick"),
            "end": text.index("Laridon Annick") + len("Laridon Annick"),
            "text": "Laridon Annick",
        },
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Kenis Sandra Dokter Laridon Annick Dokter",
            ["Kenis Sandra Dokter", "Laridon Annick Dokter"],
        ),
        (
            "Kenis Sandra Prof Laridon Annick Dr",
            ["Kenis Sandra Prof", "Laridon Annick Dr"],
        ),
        (
            "Kenis Sandra Prof. Laridon Annick Dr.",
            ["Kenis Sandra Prof.", "Laridon Annick Dr."],
        ),
    ],
)
def test_balanced_undelimited_titles_are_assigned_one_per_caregiver(
    text: str, expected: list[str]
) -> None:
    spans = [
        make_span("Name:Caregiver", text, "Kenis Sandra"),
        make_span("Name:Caregiver", text, "Laridon Annick"),
    ]

    result = post_process_spans(spans, text)

    assert [span["text"] for span in result] == expected


def test_single_middle_undelimited_title_stays_with_following_caregiver() -> None:
    text = "Kenis Sandra Dokter Laridon Annick"
    spans = [
        make_span("Name:Caregiver", text, "Kenis Sandra"),
        make_span("Name:Caregiver", text, "Laridon Annick"),
    ]

    result = post_process_spans(spans, text)

    assert [span["text"] for span in result] == [
        "Kenis Sandra",
        "Dokter Laridon Annick",
    ]


def test_delimited_trailing_titles_expand_per_caregiver_name() -> None:
    text = "Kenis Sandra, Dokter; Laridon Annick, Dokter"
    spans = [
        make_span("Name:Caregiver", text, "Kenis Sandra"),
        make_span("Name:Caregiver", text, "Laridon Annick"),
    ]

    result = post_process_spans(spans, text)

    assert result == [
        {
            "label": "Name:Caregiver",
            "begin": 0,
            "end": len("Kenis Sandra, Dokter"),
            "text": "Kenis Sandra, Dokter",
        },
        {
            "label": "Name:Caregiver",
            "begin": text.index("Laridon Annick"),
            "end": len(text),
            "text": "Laridon Annick, Dokter",
        },
    ]


def test_mixed_suffix_title_chains_expand_per_caregiver_name() -> None:
    text = "Kenis Sandra, Prof. Dr.; Laridon Annick, Dr. Prof."
    spans = [
        make_span("Name:Caregiver", text, "Kenis Sandra"),
        make_span("Name:Caregiver", text, "Laridon Annick"),
    ]

    result = post_process_spans(spans, text)

    assert result == [
        {
            "label": "Name:Caregiver",
            "begin": 0,
            "end": len("Kenis Sandra, Prof. Dr."),
            "text": "Kenis Sandra, Prof. Dr.",
        },
        {
            "label": "Name:Caregiver",
            "begin": text.index("Laridon Annick"),
            "end": len(text),
            "text": "Laridon Annick, Dr. Prof.",
        },
    ]


def test_comma_separated_suffix_title_chains_expand_per_caregiver_name() -> None:
    text = "Kenis Sandra, Prof., Dr.; Laridon Annick, Dr., Prof."
    spans = [
        make_span("Name:Caregiver", text, "Kenis Sandra"),
        make_span("Name:Caregiver", text, "Laridon Annick"),
    ]

    result = post_process_spans(spans, text)

    assert result == [
        {
            "label": "Name:Caregiver",
            "begin": 0,
            "end": len("Kenis Sandra, Prof., Dr."),
            "text": "Kenis Sandra, Prof., Dr.",
        },
        {
            "label": "Name:Caregiver",
            "begin": text.index("Laridon Annick"),
            "end": len(text),
            "text": "Laridon Annick, Dr., Prof.",
        },
    ]


def test_caregiver_metadata_recovers_mixed_suffix_title_chains() -> None:
    text = "Kenis Sandra, Prof. Dr.; Laridon Annick, Dr. Prof."

    result = post_process_spans(
        [],
        text,
        metadata={
            "caregiver_names": [
                {"given_name": "Sandra", "family_name": "Kenis"},
                {"given_name": "Annick", "family_name": "Laridon"},
            ]
        },
    )

    assert [span["text"] for span in result] == [
        "Kenis Sandra, Prof. Dr.",
        "Laridon Annick, Dr. Prof.",
    ]
    assert {span["label"] for span in result} == {"Name:Caregiver"}
    assert {span["subtype"] for span in result} == {"Caregiver"}


def test_caregiver_metadata_recovers_comma_separated_title_chains() -> None:
    text = "Kenis Sandra, Prof., Dr.; Laridon Annick, Dr., Prof."

    result = post_process_spans(
        [],
        text,
        metadata={
            "caregiver_names": [
                {"given_name": "Sandra", "family_name": "Kenis"},
                {"given_name": "Annick", "family_name": "Laridon"},
            ]
        },
    )

    assert [span["text"] for span in result] == [
        "Kenis Sandra, Prof., Dr.",
        "Laridon Annick, Dr., Prof.",
    ]
    assert {span["label"] for span in result} == {"Name:Caregiver"}
    assert {span["subtype"] for span in result} == {"Caregiver"}


@pytest.mark.parametrize("title_label", ["Name", "Name:Caregiver"])
def test_trailing_title_chain_span_merges_into_caregiver_name(title_label: str) -> None:
    text = "Lapperre, Thérèse, Prof. Dr."
    spans = [
        make_span("Name:Caregiver", text, "Lapperre, Thérèse, Prof."),
        make_span(title_label, text, "Dr."),
    ]

    result = post_process_spans(spans, text)

    assert result == [
        {
            "label": "Name:Caregiver",
            "begin": 0,
            "end": len(text),
            "text": text,
        }
    ]


def test_trailing_title_chain_from_name_and_title_fragments_merges_once() -> None:
    text = "Lapperre, Thérèse, Prof. Dr."
    spans = [
        make_span("Name:Caregiver", text, "Lapperre"),
        make_span("Name:Caregiver", text, "Dr."),
    ]

    result = post_process_spans(spans, text)

    assert result == [
        {
            "label": "Name:Caregiver",
            "begin": 0,
            "end": len(text),
            "text": text,
        }
    ]


@pytest.mark.parametrize("fragment", ["ckel", "Berckelaer", "Christophe"])
def test_trailing_title_caregiver_fragment_expands_to_full_name(
    fragment: str,
) -> None:
    text = "Reanimatiestatus Arts : Van Berckelaer, Christophe, Dr."
    expected = "Van Berckelaer, Christophe, Dr."
    span = make_span("Name:Caregiver", text, fragment)

    result = post_process_spans([span], text)

    assert result == [
        {
            "label": "Name:Caregiver",
            "begin": text.index(expected),
            "end": text.index(expected) + len(expected),
            "text": expected,
        }
    ]


def test_caregiver_name_metadata_adds_multiple_titled_full_names() -> None:
    text = (
        "Arts Dr. Alice Vermeulen noteert. "
        "Besproken met Van Berckelaer, Christophe, Dr."
    )

    result = post_process_spans(
        [],
        text,
        metadata={
            "caregiver_names": [
                {"given_name": "Alice", "family_name": "Vermeulen"},
                {"given_name": "Christophe", "family_name": "Van Berckelaer"},
            ]
        },
    )

    expected = ["Dr. Alice Vermeulen", "Van Berckelaer, Christophe, Dr."]
    assert [span["text"] for span in result] == expected
    assert {span["label"] for span in result} == {"Name:Caregiver"}
    assert {span["subtype"] for span in result} == {"Caregiver"}


def test_caregiver_name_metadata_uses_first_last_aliases_and_initial_period() -> None:
    text = "Consult Prof.dr.Stevens W. vandaag."
    expected = "Prof.dr.Stevens W."

    result = post_process_spans(
        [],
        text,
        metadata={"caregiver_names": [{"first_name": "W", "last_name": "Stevens"}]},
    )

    assert result == [
        {
            "label": "Name:Caregiver",
            "begin": text.index(expected),
            "end": text.index(expected) + len(expected),
            "text": expected,
            "category": "Name",
            "subtype": "Caregiver",
        }
    ]


def test_caregiver_name_metadata_skips_isolated_blacklisted_token() -> None:
    text = "van"

    result = post_process_spans(
        [],
        text,
        metadata={"caregiver_names": [{"given_name": "van", "family_name": ""}]},
    )

    assert result == []


def test_caregiver_name_metadata_replaces_contained_generic_name_span() -> None:
    text = "Dr. Alice Vermeulen"
    existing_span = make_span("Name", text, "Alice")

    result = post_process_spans(
        [existing_span],
        text,
        metadata={
            "caregiver_names": [{"given_name": "Alice", "family_name": "Vermeulen"}]
        },
    )

    assert result == [
        {
            "label": "Name:Caregiver",
            "begin": 0,
            "end": len(text),
            "text": text,
            "category": "Name",
            "subtype": "Caregiver",
        }
    ]


@pytest.mark.parametrize("text", ["prof Paelinck", "prof. Paelinck"])
@pytest.mark.parametrize("fragment", ["el", "Paelinck"])
def test_titled_name_fragment_expands_to_title_and_full_name(
    text: str, fragment: str
) -> None:
    span = make_span("Name", text, fragment)

    result = post_process_spans([span], text)

    assert result == [
        {
            "label": "Name",
            "begin": 0,
            "end": len(text),
            "text": text,
        }
    ]


def test_name_fragment_without_title_does_not_expand_to_full_word() -> None:
    text = "Paelinck"
    span = make_span("Name", text, "el")

    result = post_process_spans([span], text)

    assert result == [span]


def test_attach_dr_period_raises_for_mismatched_span_text() -> None:
    with pytest.raises(ValueError, match="Span text does not match"):
        attach_dr_period_if_present(
            {
                "label": "Name:Caregiver",
                "begin": 7,
                "end": 9,
                "text": "Dr",
            },
            "dokter xx.",
        )


def test_name_initial_period_is_extended() -> None:
    text = "Patient P."
    begin = text.rindex("P")
    span = {
        "label": "Name:Patient",
        "begin": begin,
        "end": begin + 1,
        "text": "P",
    }

    result = post_process_spans([span], text)

    assert result[0]["text"] == "P."
    assert result[0]["end"] == len(text)


def test_name_initial_period_is_not_extended_for_multi_letter_token() -> None:
    text = "Patient AB."
    span = make_span("Name:Patient", text, "AB")

    result = attach_initial_period_if_present(span, text)

    assert result == span


@pytest.mark.parametrize(
    "label",
    [
        "Address_Location:Patient",
        "Address_Location:Other",
        "Address_Location:Caregiver",
    ],
)
def test_real_address_labels_extend_to_post_office_pattern(label: str) -> None:
    assert label in REGEX_BY_LABEL

    text = "Postbus ANTWERPEN 1"
    result = post_process_spans([make_span(label, text, "1")], text)

    assert result[0]["text"] == "ANTWERPEN 1"
    assert result[0]["begin"] == text.index("ANTWERPEN")
    assert result[0]["end"] == len(text)


def test_date_extends_with_weekday() -> None:
    text = "Afspraak op ma 08/12/2021."
    span = make_span("Date", text, "08/12/2021")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "ma 08/12/2021"
    assert result[0]["begin"] == text.index("ma 08/12/2021")


def test_partial_date_extends_to_full_match_with_weekday() -> None:
    text = "Afspraak op ma 08/12/2021."
    span = make_span("Date", text, "2021")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "ma 08/12/2021"
    assert result[0]["begin"] == text.index("ma 08/12/2021")


def test_date_weekday_extension_is_blocked_by_overlapping_span() -> None:
    text = "ma 08/12/2021"
    date_span = make_span("Date", text, "08/12/2021")
    other_span = make_span("Organization:Healthcare", text, "ma")

    result = extend_date_with_weekday(date_span, text, [other_span, date_span])

    assert result == date_span


def test_weekday_extension_is_blocked_even_when_overlap_comes_later_in_input() -> None:
    text = "ma 08/12/2021"
    date_span = make_span("Date", text, "08/12/2021")
    other_span = make_span("Organization:Healthcare", text, "ma")

    result = post_process_spans([date_span, other_span], text)

    assert result == [other_span, date_span]


def test_degree_prefixed_date_is_relabelled_as_birthdate() -> None:
    text = "geboren op °12/01/2000"
    span = make_span("Date", text, "12/01/2000")

    result = post_process_spans([span], text)

    assert result[0]["label"] == "Age_Birthdate"
    assert result[0]["text"] == "12/01/2000"


def test_degree_prefixed_partial_date_is_relabelled_after_extension() -> None:
    text = "geboren op °12/01/2000"
    span = make_span("Date", text, "2000")

    result = post_process_spans([span], text)

    assert result[0]["label"] == "Age_Birthdate"
    assert result[0]["text"] == "12/01/2000"


def test_dot_date_partial_annotation_extends_to_complete_match() -> None:
    text = "Geboortedatum 12.02.2000"
    span = make_span("Date", text, "2000")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "12.02.2000"


def test_month_year_partial_annotation_extends_to_complete_match() -> None:
    text = "Controle 08/2012 voorzien"
    span = make_span("Date", text, "2012")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "08/2012"


def test_ocr_spaced_date_fragments_extend_to_complete_date() -> None:
    text = "Postop ontslag rec 09/10 /21 09: 56 :05"
    spans = [
        make_span("Date", text, "09/10"),
        make_span("Date", text, "/21"),
        make_span("Date", text, "56"),
    ]

    result = post_process_spans(spans, text)

    assert result == [
        {
            "label": "Date",
            "begin": text.index("09/10 /21"),
            "end": text.index("09/10 /21") + len("09/10 /21"),
            "text": "09/10 /21",
        }
    ]


def test_date_spans_inside_times_are_removed() -> None:
    text = "Laatst gewijzigd door: 09/10 /21 11:24:24"
    spans = [
        make_span("Date", text, "09/10"),
        make_span("Date", text, "11"),
        make_span("Date", text, "24"),
    ]

    result = post_process_spans(spans, text)

    assert result == [
        {
            "label": "Date",
            "begin": text.index("09/10 /21"),
            "end": text.index("09/10 /21") + len("09/10 /21"),
            "text": "09/10 /21",
        }
    ]


@pytest.mark.parametrize(
    "time_text",
    [
        "09:56",
        "09: 56",
        "09:56:05",
        "09: 56 :05",
        "11:24:24",
    ],
)
def test_standalone_time_date_spans_are_removed(time_text: str) -> None:
    span = make_span("Date", time_text, time_text)

    result = post_process_spans([span], time_text)

    assert result == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("09/10 /21 11:24:24", "09/10 /21"),
        ("09/10/21 11:24", "09/10/21"),
        ("09/10 /21 09: 56 :05", "09/10 /21"),
    ],
)
def test_date_span_with_trailing_time_is_reduced_to_date(
    text: str, expected: str
) -> None:
    span = make_span("Date", text, text)

    result = post_process_spans([span], text)

    assert result == [
        {
            "label": "Date",
            "begin": 0,
            "end": len(expected),
            "text": expected,
        }
    ]


def test_season_year_partial_annotation_extends_to_complete_match() -> None:
    text = "Controle zomer 2021 voorzien"
    span = make_span("Date", text, "2021")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "zomer 2021"


def test_textual_month_year_partial_annotation_extends_to_complete_match() -> None:
    text = "Controle september 2024 voorzien"
    span = make_span("Date", text, "2024")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "september 2024"


def test_textual_date_range_partial_annotation_extends_to_complete_match() -> None:
    text = "Controle 5-10 juni 2023 voorzien"
    span = make_span("Date", text, "juni")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "5-10 juni 2023"


def test_textual_day_month_does_not_absorb_sentence_period_after_full_month() -> None:
    text = "Controle op 23 juni. Nieuwe afspraak op 1 juli."
    spans = [
        make_span("Date", text, "23 juni"),
        make_span("Date", text, "1 juli"),
    ]

    result = post_process_spans(spans, text)

    assert [span["text"] for span in result] == ["23 juni", "1 juli"]


def test_textual_day_month_keeps_period_for_abbreviated_month() -> None:
    text = "Controle op 23 jun. gepland"
    span = make_span("Date", text, "jun")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "23 jun."


def test_textual_dmy_range_with_shared_trailing_year_extends_to_complete_match() -> (
    None
):
    text = "Controle 4 september - 6 september 2020 voorzien"
    span = make_span("Date", text, "4 september")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "4 september - 6 september 2020"


def test_textual_dmy_range_with_shared_trailing_year_extends_from_year_side() -> None:
    text = "Controle 4 september - 6 september 2020 voorzien"
    span = make_span("Date", text, "6 september 2020")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "4 september - 6 september 2020"


def test_textual_dmy_range_with_shared_trailing_year_extends_across_newline() -> None:
    text = "Controle 4\nseptember\n-\n6\nseptember 2020 voorzien"
    span = make_span("Date", text, "4\nseptember")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "4\nseptember\n-\n6\nseptember 2020"


def test_textual_dmy_range_with_shared_leading_year_extends_to_complete_match() -> None:
    text = "Controle 4 september 2020 - 6 september voorzien"
    span = make_span("Date", text, "6 september")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "4 september 2020 - 6 september"


def test_textual_dmy_range_with_two_full_dates_does_not_extend() -> None:
    text = "Controle 4 september 2020 - 6 september 2020 voorzien"
    span = make_span("Date", text, "4 september 2020")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "4 september 2020"


def test_numeric_date_range_without_year_does_not_extend_from_first_date() -> None:
    text = "Controle 25/2 - 04/03 voorzien"
    span = make_span("Date", text, "25/2")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "25/2"


def test_numeric_date_range_without_year_does_not_extend_from_second_date() -> None:
    text = "Controle 25/2 - 04/03 voorzien"
    span = make_span("Date", text, "04/03")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "04/03"


def test_compact_numeric_date_range_without_year_does_not_extend() -> None:
    text = "Controle 12/02-14/06 voorzien"
    span = make_span("Date", text, "14/06")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "14/06"


def test_numeric_date_range_with_shared_trailing_year_extends_to_complete_match() -> (
    None
):
    text = "Controle 04/09 - 06/09/2020 voorzien"
    span = make_span("Date", text, "04/09")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "04/09 - 06/09/2020"


def test_numeric_date_range_with_shared_trailing_year_extends_across_newline() -> None:
    text = "Controle 04/09\n-\n06/09/2020 voorzien"
    span = make_span("Date", text, "04/09")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "04/09\n-\n06/09/2020"


def test_numeric_date_range_with_shared_leading_year_extends_to_complete_match() -> (
    None
):
    text = "Controle 04/09/2020 - 06/09 voorzien"
    span = make_span("Date", text, "06/09")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "04/09/2020 - 06/09"


def test_numeric_date_range_with_dots_extends_to_complete_match() -> None:
    text = "Controle 04.09 - 06.09.2020 voorzien"
    span = make_span("Date", text, "04.09")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "04.09 - 06.09.2020"


def test_numeric_date_range_with_internal_hyphens_extends_when_range_separator_is_explicit() -> (
    None
):
    text = "Controle 04-09 - 06-09-2020 voorzien"
    span = make_span("Date", text, "04-09")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "04-09 - 06-09-2020"


def test_numeric_date_range_with_internal_hyphens_extends_across_newline() -> None:
    text = "Controle 04-09\n-\n06-09-2020 voorzien"
    span = make_span("Date", text, "04-09")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "04-09\n-\n06-09-2020"


def test_numeric_date_range_with_two_full_dates_does_not_extend() -> None:
    text = "Controle 04/09/2020 - 06/09/2020 voorzien"
    span = make_span("Date", text, "04/09/2020")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "04/09/2020"


def test_numeric_month_year_range_extends_to_complete_match() -> None:
    text = "Controle 08/2024-09/2024 voorzien"
    span = make_span("Date", text, "09/2024")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "08/2024-09/2024"


def test_textual_month_year_range_extends_to_complete_match() -> None:
    text = "Controle augustus 2024-september 2024 voorzien"
    span = make_span("Date", text, "september")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "augustus 2024-september 2024"


def test_month_phase_extends_to_following_month() -> None:
    text = "Controle eind november voorzien"
    span = make_span("Date", text, "eind")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "eind november"


def test_month_phase_extends_from_month_side() -> None:
    text = "Controle eind november voorzien"
    span = make_span("Date", text, "november")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "eind november"


def test_compound_month_phase_extends_to_following_month() -> None:
    text = "Controle midden/eind november voorzien"
    span = make_span("Date", text, "midden/eind")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "midden/eind november"


@pytest.mark.parametrize("fragment", ["begin", "midden/eind", "volgend jaar", "13-21"])
def test_false_positive_date_spans_are_dropped(fragment: str) -> None:
    text = f"Controle {fragment} voorzien"
    span = make_span("Date", text, fragment)

    result = post_process_spans([span], text)

    assert result == []


def test_standalone_numeric_date_without_component_context_is_kept() -> None:
    text = "Controle 10 voorzien"
    span = make_span("Date", text, "10")

    result = post_process_spans([span], text)

    assert result == [span]


@pytest.mark.parametrize(
    "text",
    [
        "birth_day ::: 10",
        "birth day ::: 10",
        "birth-day ::: 10",
        "birth.day ::: 10",
        "birthDay ::: 10",
        "birty day ::: 10",
        "sample_month ::: 10",
        "sample month ::: 10",
        "sample.month ::: 10",
        "Geboorte dag: 10",
    ],
)
def test_standalone_numeric_date_with_component_context_is_kept(text: str) -> None:
    span = make_span("Date", text, "10")

    result = post_process_spans([span], text)

    assert result == [span]


def test_regex_extension_prefers_smallest_containing_match() -> None:
    text = "ma 08/12/2021"
    span = make_span("Date", text, "2021")

    result = extend_spans_to_regex([span], text, REGEX_BY_LABEL)

    assert result[0]["text"] == "08/12/2021"


def test_duplicate_spans_collapsed_after_extension() -> None:
    text = "Geboortedatum 12.02.2000"
    spans = [
        make_span("Date", text, "12"),
        make_span("Date", text, "2000"),
    ]

    result = post_process_spans(spans, text)

    assert result == [
        {
            "label": "Date",
            "begin": text.index("12.02.2000"),
            "end": text.index("12.02.2000") + len("12.02.2000"),
            "text": "12.02.2000",
        }
    ]


def test_age_birthdate_label_extends_to_age_expression() -> None:
    text = "Leeftijd 12 jaar"
    span = make_span("Age_Birthdate", text, "12")

    result = extend_spans_to_regex([span], text, REGEX_BY_LABEL)

    assert result[0]["text"] == "12 jaar"


@pytest.mark.parametrize("expected", ["62-jarige", "62 -jarige", "62 - jarige"])
def test_age_birthdate_label_extends_to_hyphenated_age_expression(
    expected: str,
) -> None:
    text = f"De {expected} dame werd gezien"
    span = make_span("Age_Birthdate", text, "62")

    result = post_process_spans([span], text)

    assert result[0]["text"] == expected


def test_age_birthdate_partial_month_unit_extends_to_age_expression() -> None:
    text = "Leeftijd 2 Maanden"
    span = make_span("Age_Birthdate", text, "aanden")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "2 Maanden"


def test_healthcare_organization_label_extends_to_room_pattern() -> None:
    text = "Patiënt naar OK 3"
    span = make_span("Organization:Healthcare", text, "3")

    result = extend_spans_to_regex([span], text, REGEX_BY_LABEL)

    assert result[0]["text"] == "OK 3"


def test_patient_name_metadata_adds_blacklisted_connectors_and_merges_tokens() -> None:
    text = "Jan van Dam meldt zich."

    result = post_process_spans(
        [],
        text,
        metadata={"patient_name": {"given_name": "Jan van", "family_name": "Dam"}},
    )

    assert result == [
        {
            "label": "Name:Patient",
            "begin": 0,
            "end": len("Jan van Dam"),
            "text": "Jan van Dam",
            "category": "Name",
            "subtype": "Patient",
        }
    ]


def test_patient_name_metadata_accepts_first_last_aliases() -> None:
    text = "Jan Dam meldt zich."

    result = post_process_spans(
        [],
        text,
        metadata={"patient_name": {"first_name": "Jan", "last_name": "Dam"}},
    )

    assert result == [
        {
            "label": "Name:Patient",
            "begin": 0,
            "end": len("Jan Dam"),
            "text": "Jan Dam",
            "category": "Name",
            "subtype": "Patient",
        }
    ]


def test_patient_name_metadata_skips_isolated_blacklisted_token() -> None:
    text = "van"

    result = auto_add_patient_name_spans(
        [],
        text,
        {"given_name": "van", "family_name": ""},
    )

    assert result == []


def test_patient_name_metadata_does_not_duplicate_existing_exact_span() -> None:
    text = "Jan meldt zich."
    existing_span = make_span("Name:Patient", text, "Jan")

    result = post_process_spans(
        [existing_span],
        text,
        metadata={"patient_name": {"given_name": "Jan", "family_name": ""}},
    )

    assert result == [existing_span]


def test_patient_name_metadata_replaces_existing_patient_subspan() -> None:
    text = "Jan Dam meldt zich."
    existing_span = make_span("Name:Patient", text, "Ja")

    result = post_process_spans(
        [existing_span],
        text,
        metadata={"patient_name": {"given_name": "Jan", "family_name": "Dam"}},
    )

    assert result == [
        {
            "label": "Name:Patient",
            "begin": 0,
            "end": len("Jan Dam"),
            "text": "Jan Dam",
            "category": "Name",
            "subtype": "Patient",
        }
    ]


def test_patient_name_metadata_skips_subspan_inside_existing_annotation() -> None:
    text = "Jan X meldt zich."
    existing_span = {
        "label": "Organization:Healthcare",
        "begin": 0,
        "end": len("Jan X"),
        "text": "Jan X",
    }

    result = auto_add_patient_name_spans(
        [existing_span],
        text,
        {"given_name": "Jan", "family_name": ""},
    )

    assert result == [existing_span]


def test_patient_name_metadata_still_adds_name_parts_when_other_label_contains_token() -> (
    None
):
    text = "(Jan) Dam meldt zich."
    existing_span = {
        "label": "Date",
        "begin": 0,
        "end": len("(Jan)"),
        "text": "(Jan)",
    }

    result = auto_add_patient_name_spans(
        [existing_span],
        text,
        {"given_name": "Jan", "family_name": "Dam"},
    )

    assert result == [
        existing_span,
        {
            "label": "Name:Patient",
            "begin": text.index("Dam"),
            "end": text.index("Dam") + len("Dam"),
            "text": "Dam",
            "category": "Name",
            "subtype": "Patient",
        },
    ]


def test_patient_name_metadata_skips_token_overlap_with_other_label_but_adds_later_parts() -> (
    None
):
    text = "Jan Dam meldt zich."
    existing_span = {
        "label": "Date",
        "begin": 0,
        "end": len("Ja"),
        "text": "Ja",
    }

    result = auto_add_patient_name_spans(
        [existing_span],
        text,
        {"given_name": "Jan", "family_name": "Dam"},
    )

    assert result == [
        existing_span,
        {
            "label": "Name:Patient",
            "begin": text.index("Dam"),
            "end": text.index("Dam") + len("Dam"),
            "text": "Dam",
            "category": "Name",
            "subtype": "Patient",
        },
    ]


def test_merge_adjacent_patient_names_across_newline() -> None:
    text = "Jan\nDam"
    spans = [
        make_span("Name:Patient", text, "Dam"),
        make_span("Name:Patient", text, "Jan"),
    ]

    result = merge_adjacent_name_patient(spans, text)

    assert result == [
        {
            "label": "Name:Patient",
            "begin": 0,
            "end": len(text),
            "text": text,
        }
    ]


def test_merge_adjacent_patient_names_does_not_cross_punctuation() -> None:
    text = "Jan, Dam"
    spans = [
        make_span("Name:Patient", text, "Jan"),
        make_span("Name:Patient", text, "Dam"),
    ]

    result = merge_adjacent_name_patient(spans, text)

    assert result == sorted(spans, key=lambda span: span["begin"])


def test_balance_enclosing_brackets_can_attach_missing_left_bracket() -> None:
    text = "(Jan)"
    span = {
        "label": "Name:Patient",
        "begin": 1,
        "end": len(text),
        "text": "Jan)",
    }

    result = balance_enclosing_brackets(span, text)

    assert result["text"] == "(Jan)"
    assert result["begin"] == 0
    assert result["end"] == len(text)


def test_balances_missing_right_bracket_when_span_contains_unmatched_opener() -> None:
    text = "A(B)"
    span = make_span("Name:Patient", text, "A(B")

    result = post_process_spans([span], text)

    assert result[0]["text"] == "A(B)"
    assert result[0]["begin"] == 0
    assert result[0]["end"] == len(text)


def test_drop_non_alnum_spans_treats_degree_symbol_as_non_effective() -> None:
    spans = [
        {"label": "Date", "begin": 0, "end": 1, "text": "°"},
        {"label": "Name:Patient", "begin": 1, "end": 4, "text": "Jan"},
    ]

    assert drop_non_alnum_spans(spans) == [spans[1]]


def test_non_alnum_only_spans_are_dropped() -> None:
    text = "()"
    span = make_span("Name:Patient", text, text)

    result = post_process_spans([span], text)

    assert result == []
