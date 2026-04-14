import docdeid as dd

from belgian_deduce.annotation_processor import PostalCodeLocalityFilter
from belgian_deduce.postal_code import derive_locality_candidates


class TestPostalCodeHelpers:
    def test_derive_locality_candidates_from_parenthetical_entry(self):
        assert derive_locality_candidates("Brussel (Neder-Over-Heembeek)") == {
            "Brussel",
            "Neder-Over-Heembeek",
        }

    def test_derive_locality_candidates_rejects_special_entries(self):
        assert derive_locality_candidates("Europees Parlement") == set()
        assert derive_locality_candidates("Brussel (Louizalaan)") == {"Brussel"}


class TestPostalCodeLocalityFilter:
    def _build_filter(self) -> PostalCodeLocalityFilter:
        rows = dd.ds.LookupSet()
        rows.add_items_from_iterable(
            [
                "1000\tBrussel (stad)",
                "1120\tBrussel (Neder-Over-Heembeek)",
                "1348\tLouvain-la-Neuve",
                "8500\tKortrijk",
                "1047\tEuropees Parlement",
            ]
        )
        return PostalCodeLocalityFilter(
            postal_code_locality_rows=rows, slack_regexp="[\\. \\-]?[\\. ]?"
        )

    def test_keeps_postcode_before_matching_locality(self):
        proc = self._build_filter()
        text = "1000 Brussel"
        annotations = dd.AnnotationSet(
            [
                dd.Annotation(text="1000", start_char=0, end_char=4, tag="location"),
                dd.Annotation(
                    text="Brussel", start_char=5, end_char=12, tag="location"
                ),
            ]
        )

        assert proc.process_annotations(annotations, text) == annotations

    def test_keeps_postcode_after_matching_locality(self):
        proc = self._build_filter()
        text = "Brussel 1000"
        annotations = dd.AnnotationSet(
            [
                dd.Annotation(text="1000", start_char=8, end_char=12, tag="location"),
                dd.Annotation(
                    text="Brussel", start_char=0, end_char=7, tag="location"
                ),
            ]
        )

        assert proc.process_annotations(annotations, text) == annotations

    def test_removes_isolated_postcode(self):
        proc = self._build_filter()
        text = "1000"
        annotations = dd.AnnotationSet(
            [dd.Annotation(text="1000", start_char=0, end_char=4, tag="location")]
        )

        assert proc.process_annotations(annotations, text) == dd.AnnotationSet()

    def test_removes_mismatched_postcode(self):
        proc = self._build_filter()
        text = "8500 Gent"
        annotations = dd.AnnotationSet(
            [
                dd.Annotation(text="8500", start_char=0, end_char=4, tag="location"),
                dd.Annotation(text="Gent", start_char=5, end_char=9, tag="location"),
            ]
        )

        assert proc.process_annotations(annotations, text) == dd.AnnotationSet(
            [dd.Annotation(text="Gent", start_char=5, end_char=9, tag="location")]
        )

    def test_keeps_prefixed_postcode(self):
        proc = self._build_filter()
        text = "B-1000 Brussel"
        annotations = dd.AnnotationSet(
            [
                dd.Annotation(text="B-1000", start_char=0, end_char=6, tag="location"),
                dd.Annotation(
                    text="Brussel", start_char=7, end_char=14, tag="location"
                ),
            ]
        )

        assert proc.process_annotations(annotations, text) == annotations

    def test_keeps_non_postcode_location(self):
        proc = self._build_filter()
        text = "Heidelberglaan 1111"
        annotations = dd.AnnotationSet(
            [
                dd.Annotation(
                    text="Heidelberglaan 1111",
                    start_char=0,
                    end_char=19,
                    tag="location",
                )
            ]
        )

        assert proc.process_annotations(annotations, text) == annotations
