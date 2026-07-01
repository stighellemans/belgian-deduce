import docdeid as dd

from belgian_deduce import post_process
from belgian_deduce.post_processor import (
    deduce_annotation_to_post_span,
    post_span_to_deduce_annotation,
)


def test_deduce_post_span_bridge_preserves_original_tag_and_priority():
    annotation = dd.Annotation(
        text="08/12/2021",
        start_char=3,
        end_char=13,
        tag="date",
        priority=7,
    )

    span = deduce_annotation_to_post_span(annotation)
    span["label"] = "Age_Birthdate"
    converted = post_span_to_deduce_annotation(span, "op 08/12/2021")

    assert span["label"] == "Age_Birthdate"
    assert span["_deduce_tag"] == "date"
    assert converted == dd.Annotation(
        text="08/12/2021",
        start_char=3,
        end_char=13,
        tag="date",
        priority=7,
    )
    assert converted.priority == 7


def test_post_process_returns_early_without_spans_or_metadata(monkeypatch):
    def fail_build_regex_match_index(*args, **kwargs):
        raise AssertionError("regex index should not be built")

    monkeypatch.setattr(
        post_process,
        "build_regex_match_index",
        fail_build_regex_match_index,
    )

    assert post_process.post_process_spans([], "Controle op ma 08/12/2021.") == []


def test_post_process_skips_regex_index_when_no_active_labels(monkeypatch):
    def fail_build_regex_match_index(*args, **kwargs):
        raise AssertionError("regex index should not be built")

    monkeypatch.setattr(
        post_process,
        "build_regex_match_index",
        fail_build_regex_match_index,
    )

    spans = [{"label": "id", "begin": 0, "end": 3, "text": "123"}]

    assert post_process.post_process_spans(spans, "123") == spans
