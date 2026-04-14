import docdeid as dd

from belgian_deduce.annotation_processor import (
    CleanAnnotationTag,
    DeduceMergeAdjacentAnnotations,
    PersonAnnotationConverter,
    RemoveAnnotations,
)


class TestDeduceMergeAdjacent:
    def test_tags_match(self):
        proc = DeduceMergeAdjacentAnnotations()

        assert proc._tags_match("a", "a")
        assert proc._tags_match("house_number", "house_number")
        assert proc._tags_match("patient", "patient")
        assert proc._tags_match("person", "person")
        assert proc._tags_match("patient", "person")
        assert proc._tags_match("person", "patient")

        assert not proc._tags_match("a", "b")
        assert not proc._tags_match("patient", "house_number")
        assert not proc._tags_match("house_number", "patient")
        assert not proc._tags_match("person", "house_number")
        assert not proc._tags_match("house_number", "person")

    def test_annotation_replacement_equal_tags(self):
        proc = DeduceMergeAdjacentAnnotations()
        text = "Jan Jansen"
        left_annotation = dd.Annotation(
            text="Jan", start_char=0, end_char=3, tag="name"
        )
        right_annotation = dd.Annotation(
            text="Jansen", start_char=4, end_char=10, tag="name"
        )
        expected_annotation = dd.Annotation(
            text="Jan Jansen", start_char=0, end_char=10, tag="name"
        )

        assert (
            proc._adjacent_annotations_replacement(
                left_annotation, right_annotation, text
            )
            == expected_annotation
        )

    def test_annotation_replacement_unequal_tags(self):
        proc = DeduceMergeAdjacentAnnotations()
        text = "Jan Jansen"
        left_annotation = dd.Annotation(
            text="Jan", start_char=0, end_char=3, tag="first_name_patient"
        )
        right_annotation = dd.Annotation(
            text="Jansen", start_char=4, end_char=10, tag="last_name_patient"
        )
        expected_annotation = dd.Annotation(
            text="Jan Jansen", start_char=0, end_char=10, tag="patient"
        )

        assert (
            proc._adjacent_annotations_replacement(
                left_annotation, right_annotation, text
            )
            == expected_annotation
        )


class TestPersonAnnotationConverter:
    def test_patient_no_overlap(self):
        proc = PersonAnnotationConverter()
        text = "Jan Jansen"

        annotations = dd.AnnotationSet(
            [
                dd.Annotation(
                    text="Jan", start_char=0, end_char=3, tag="first_name_patient"
                ),
                dd.Annotation(
                    text="Jansen", start_char=4, end_char=10, tag="last_name_patient"
                ),
            ]
        )

        expected_annotations = dd.AnnotationSet(
            [
                dd.Annotation(text="Jan", start_char=0, end_char=3, tag="patient"),
                dd.Annotation(text="Jansen", start_char=4, end_char=10, tag="patient"),
            ]
        )

        assert proc.process_annotations(annotations, text) == expected_annotations

    def test_patient_with_overlap(self):
        proc = PersonAnnotationConverter()
        text = "Jan Jansen"

        annotations = dd.AnnotationSet(
            [
                dd.Annotation(
                    text="Jan", start_char=0, end_char=3, tag="first_name_patient"
                ),
                dd.Annotation(
                    text="Jan Jansen", start_char=0, end_char=10, tag="name_patient"
                ),
            ]
        )

        expected_annotations = dd.AnnotationSet(
            [dd.Annotation(text="Jan Jansen", start_char=0, end_char=10, tag="patient")]
        )

        assert proc.process_annotations(annotations, text) == expected_annotations

    def test_mixed_no_overlap(self):
        proc = PersonAnnotationConverter()
        text = "Jan Jansen"

        annotations = dd.AnnotationSet(
            [
                dd.Annotation(
                    text="Jan", start_char=0, end_char=3, tag="first_name_patient"
                ),
                dd.Annotation(
                    text="Jansen", start_char=4, end_char=10, tag="last_name_unknown"
                ),
            ]
        )

        expected_annotations = dd.AnnotationSet(
            [
                dd.Annotation(text="Jan", start_char=0, end_char=3, tag="patient"),
                dd.Annotation(text="Jansen", start_char=4, end_char=10, tag="person"),
            ]
        )

        assert proc.process_annotations(annotations, text) == expected_annotations

    def test_mixed_with_overlap(self):
        proc = PersonAnnotationConverter()
        text = "Jan Jansen"

        annotations = dd.AnnotationSet(
            [
                dd.Annotation(
                    text="Jan", start_char=0, end_char=3, tag="first_name_patient"
                ),
                dd.Annotation(
                    text="Jan Jansen", start_char=0, end_char=10, tag="name_unknown"
                ),
            ]
        )

        expected_annotations = dd.AnnotationSet(
            [
                dd.Annotation(text="Jan", start_char=0, end_char=3, tag="patient"),
                dd.Annotation(text=" Jansen", start_char=3, end_char=10, tag="person"),
            ]
        )

        assert proc.process_annotations(annotations, text) == expected_annotations

    def test_pseudo(self):
        proc = PersonAnnotationConverter()
        text = "Henoch Schonlein"

        annotations = dd.AnnotationSet(
            [
                dd.Annotation(text="Henoch", start_char=0, end_char=6, tag="first_name"),
                dd.Annotation(
                    text="Henoch Schonlein",
                    start_char=0,
                    end_char=16,
                    tag="pseudo_name",
                ),
            ]
        )

        assert proc.process_annotations(annotations, text) == dd.AnnotationSet()


class TestRemoveAnnotations:
    def test_remove_annotations(self):
        ra = RemoveAnnotations(tags=["first_name_patient", "nonexisting_tag"])

        annotations = dd.AnnotationSet(
            [
                dd.Annotation(
                    text="Jan", start_char=0, end_char=3, tag="first_name_patient"
                ),
                dd.Annotation(
                    text="Jansen", start_char=4, end_char=10, tag="last_name_patient"
                ),
            ]
        )

        processed_annotations = ra.process_annotations(annotations, text="_")

        assert processed_annotations == dd.AnnotationSet(
            [
                dd.Annotation(
                    text="Jansen", start_char=4, end_char=10, tag="last_name_patient"
                )
            ]
        )


class TestCleanAnnotationTag:
    def test_remove_annotations(self):
        cat = CleanAnnotationTag(
            tag_map={"first_name_patient": "first_name", "nonexistent": "test"}
        )

        annotations = dd.AnnotationSet(
            [
                dd.Annotation(
                    text="Jan", start_char=0, end_char=3, tag="first_name_patient"
                ),
                dd.Annotation(
                    text="Jansen", start_char=4, end_char=10, tag="last_name_patient"
                ),
            ]
        )

        processed_annotations = cat.process_annotations(annotations, text="_")

        assert processed_annotations == dd.AnnotationSet(
            [
                dd.Annotation(text="Jan", start_char=0, end_char=3, tag="first_name"),
                dd.Annotation(
                    text="Jansen", start_char=4, end_char=10, tag="last_name_patient"
                ),
            ]
        )
