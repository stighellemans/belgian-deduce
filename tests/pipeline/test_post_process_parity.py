import importlib.util
import json
from pathlib import Path

import docdeid as dd
import pytest

from belgian_deduce.metadata import Person
from belgian_deduce.post_processor import (
    deduce_annotations_to_post_spans,
    post_process_metadata,
    post_span_to_deduce_annotation,
)

POST_PROCESS_REPO = Path(__file__).resolve().parents[3] / "post-process"
POST_PROCESS_MODULE = POST_PROCESS_REPO / "post_process.py"


def load_external_post_process():
    if not POST_PROCESS_MODULE.exists():
        pytest.skip(f"post-process oracle not available at {POST_PROCESS_MODULE}")

    spec = importlib.util.spec_from_file_location(
        "external_post_process_module",
        POST_PROCESS_MODULE,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.post_process_spans


def normalized_annotations(annotations):
    return sorted(
        (
            int(annotation.start_char),
            int(annotation.end_char),
            str(annotation.text),
            str(annotation.tag),
            int(annotation.priority),
        )
        for annotation in annotations
    )


def external_two_step_annotations(model, text, metadata):
    post_process_spans = load_external_post_process()
    base_doc = model.deidentify(
        text,
        metadata=metadata,
        disabled={"post_processor", "redactor"},
    )
    spans = deduce_annotations_to_post_spans(base_doc.annotations)
    processed_spans = post_process_spans(
        spans,
        base_doc.text,
        metadata=post_process_metadata(base_doc.metadata),
    )
    return dd.AnnotationSet(
        post_span_to_deduce_annotation(span, base_doc.text) for span in processed_spans
    )


@pytest.mark.parametrize(
    ("text", "metadata"),
    [
        ("Bel (02) 555 12 12.", None),
        ("Zie www.example.com/path voor details.", None),
        ("Afspraak op ma 08/12/2021.", None),
        ("Laatst gewijzigd door: 09/10 /21 11:24:24", None),
        ("Leeftijd 12 jaar", None),
        (
            "Jan van Dam meldt zich.",
            {"patient": Person(first_names=["Jan", "van"], surname="Dam")},
        ),
        ("Prof.dr.Stevens W. kwam langs.", None),
        ("Postbus ANTWERPEN 1", None),
        ("Patiënt naar OK 3", None),
        ("geboren op °12/01/2000", None),
    ],
)
def test_integrated_post_process_matches_external_two_step_cases(
    model,
    text,
    metadata,
):
    integrated_doc = model.deidentify(text, metadata=metadata, disabled={"redactor"})
    external_annotations = external_two_step_annotations(model, text, metadata)

    assert normalized_annotations(integrated_doc.annotations) == normalized_annotations(
        external_annotations
    )


def test_integrated_post_process_matches_external_two_step_regression_sample(model):
    fixture_paths = sorted(Path("tests/data/regression_cases").glob("*.json"))
    cases = []
    for fixture_path in fixture_paths:
        examples = json.loads(fixture_path.read_text(encoding="utf-8"))["examples"]
        cases.extend(example["text"] for example in examples[:3])

    for text in cases:
        integrated_doc = model.deidentify(text, disabled={"redactor"})
        external_annotations = external_two_step_annotations(model, text, None)

        assert normalized_annotations(
            integrated_doc.annotations
        ) == normalized_annotations(external_annotations)
