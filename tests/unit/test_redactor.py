import docdeid as dd
import pytest

from belgian_deduce.redactor import DeduceRedactor, _shift_date_literal


class TestDateShift:
    def test__shift_date_literal_preserves_numeric_format(self):
        assert _shift_date_literal("10/10/2018", 10) == "20/10/2018"
        assert _shift_date_literal("2018-10-10", 10) == "2018-10-20"
        assert _shift_date_literal("1.2.90", 10) == "11.2.90"

    def test__shift_date_literal_preserves_textual_format(self):
        assert _shift_date_literal("10 oktober 2018", 10) == "20 oktober 2018"
        assert _shift_date_literal("1 février 1990", 10) == "11 février 1990"
        assert _shift_date_literal("1990 février 1", 10) == "1990 février 11"


class TestDeduceRedactor:
    def test_redact_patient(self):
        proc = DeduceRedactor()
        text = "Jan Jansen"

        annotations = dd.AnnotationSet(
            [
                dd.Annotation(text="Jan", start_char=0, end_char=3, tag="patient"),
                dd.Annotation(text="Jansen", start_char=4, end_char=10, tag="patient"),
            ]
        )

        expected_text = "[PATIENT] [PATIENT]"

        assert proc.redact(text, annotations) == expected_text

    def test_redact_mixed(self):
        proc = DeduceRedactor()
        text = "Jan Jansen, wonende in Rotterdam"

        annotations = dd.AnnotationSet(
            [
                dd.Annotation(
                    text="Jan Jansen", start_char=0, end_char=10, tag="patient"
                ),
                dd.Annotation(
                    text="Rotterdam", start_char=23, end_char=32, tag="location"
                ),
            ]
        )

        expected_text = "[PATIENT], wonende in [LOCATION-1]"

        assert proc.redact(text, annotations) == expected_text

    def test_redact_count_multiple(self):
        proc = DeduceRedactor()
        text = "Jan Jansen, wonende in Rotterdam, verhuisd vanuit Groningen"

        annotations = dd.AnnotationSet(
            [
                dd.Annotation(
                    text="Rotterdam", start_char=23, end_char=32, tag="location"
                ),
                dd.Annotation(
                    text="Groningen", start_char=50, end_char=59, tag="location"
                ),
            ]
        )

        expected_text = (
            "Jan Jansen, wonende in [LOCATION-1], verhuisd vanuit [LOCATION-2]"
        )

        assert proc.redact(text, annotations) == expected_text

    def test_redact_count_multiple_fuzzy(self):
        proc = DeduceRedactor()
        text = "Jan Jansen, wonende in Ommen, verhuisd vanuit Emmen"

        annotations = dd.AnnotationSet(
            [
                dd.Annotation(text="Ommen", start_char=23, end_char=28, tag="location"),
                dd.Annotation(text="Emmen", start_char=46, end_char=51, tag="location"),
            ]
        )

        expected_text = (
            "Jan Jansen, wonende in [LOCATION-1], verhuisd vanuit [LOCATION-1]"
        )

        assert proc.redact(text, annotations) == expected_text

    def test_redact_shift_dates_with_explicit_days(self):
        with pytest.warns(RuntimeWarning, match="same date shift"):
            proc = DeduceRedactor(date_strategy="shift", date_shift_days=10)
        text = "Controle op 10 oktober 2018 en 2018-11-01."

        annotations = dd.AnnotationSet(
            [
                dd.Annotation(
                    text="10 oktober 2018",
                    start_char=text.index("10 oktober 2018"),
                    end_char=text.index("10 oktober 2018") + len("10 oktober 2018"),
                    tag="date",
                ),
                dd.Annotation(
                    text="2018-11-01",
                    start_char=text.index("2018-11-01"),
                    end_char=text.index("2018-11-01") + len("2018-11-01"),
                    tag="date",
                ),
            ]
        )

        assert (
            proc.redact(text, annotations)
            == "Controle op 20 oktober 2018 en 2018-11-11."
        )

    def test_redact_shift_dates_falls_back_for_unsupported_date_literals(self):
        with pytest.warns(RuntimeWarning, match="same date shift"):
            proc = DeduceRedactor(date_strategy="shift", date_shift_days=10)
        text = "Controle in 2018:"

        annotations = dd.AnnotationSet(
            [
                dd.Annotation(
                    text="2018",
                    start_char=text.index("2018"),
                    end_char=text.index("2018") + len("2018"),
                    tag="date",
                )
            ]
        )

        assert proc.redact(text, annotations) == "Controle in [DATE-1]:"

    def test_warns_for_short_date_shift(self):
        proc = DeduceRedactor(date_strategy="shift")
        text = "Controle op 10 oktober 2018."
        doc = dd.Document(text, metadata={"date_shift_days": 7})
        doc.annotations = dd.AnnotationSet(
            [
                dd.Annotation(
                    text="10 oktober 2018",
                    start_char=text.index("10 oktober 2018"),
                    end_char=text.index("10 oktober 2018") + len("10 oktober 2018"),
                    tag="date",
                )
            ]
        )

        with pytest.warns(RuntimeWarning, match="7 days or less"):
            proc.process(doc)

        assert doc.deidentified_text == "Controle op 17 oktober 2018."

    def test_process_uses_metadata_date_shift_days(self):
        proc = DeduceRedactor(date_strategy="shift")
        text = "Controle op 10 oktober 2018."
        doc = dd.Document(text, metadata={"date_shift_days": 10})
        doc.annotations = dd.AnnotationSet(
            [
                dd.Annotation(
                    text="10 oktober 2018",
                    start_char=text.index("10 oktober 2018"),
                    end_char=text.index("10 oktober 2018") + len("10 oktober 2018"),
                    tag="date",
                )
            ]
        )

        proc.process(doc)

        assert doc.deidentified_text == "Controle op 20 oktober 2018."

    def test_process_can_seed_deterministic_date_shift_from_metadata(self):
        proc = DeduceRedactor(
            date_strategy="shift",
            date_shift_seed_key="birth_date",
        )
        text = "Controle op 10 oktober 2018."
        first_doc = dd.Document(text, metadata={"birth_date": "1980-03-12"})
        second_doc = dd.Document(text, metadata={"birth_date": "1980-03-12"})

        for doc in (first_doc, second_doc):
            doc.annotations = dd.AnnotationSet(
                [
                    dd.Annotation(
                        text="10 oktober 2018",
                        start_char=text.index("10 oktober 2018"),
                        end_char=text.index("10 oktober 2018") + len("10 oktober 2018"),
                        tag="date",
                    )
                ]
            )
            proc.process(doc)

        assert first_doc.deidentified_text == second_doc.deidentified_text
        assert first_doc.deidentified_text != text
        assert "[DATE-1]" not in first_doc.deidentified_text
