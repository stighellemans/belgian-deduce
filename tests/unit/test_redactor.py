import docdeid as dd

from belgian_deduce.redactor import DeduceRedactor


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
                dd.Annotation(
                    text="Ommen", start_char=23, end_char=28, tag="location"
                ),
                dd.Annotation(
                    text="Emmen", start_char=46, end_char=51, tag="location"
                ),
            ]
        )

        expected_text = (
            "Jan Jansen, wonende in [LOCATION-1], verhuisd vanuit [LOCATION-1]"
        )

        assert proc.redact(text, annotations) == expected_text
