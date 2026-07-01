"""Bridge Belgian Deduce annotations through the post-process span pipeline."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import docdeid as dd

from belgian_deduce.post_process import post_process_spans

DEDUCE_TAG_TO_POST_LABEL = {
    "patient": "Name:Patient",
    "person": "Name:Caregiver",
    "date": "Date",
    "datum": "Date",
    "age": "Age_Birthdate",
    "url": "Contactdetails",
    "email": "Contactdetails",
    "phone_number": "Contactdetails",
    "location": "Address_Location:Other",
    "hospital": "Organization:Healthcare",
    "healthcare_institution": "Organization:Healthcare",
}

POST_LABEL_TO_DEDUCE_TAG = {
    "Name:Patient": "patient",
    "Name:Caregiver": "person",
    "Name": "person",
    "Date": "date",
    "Age_Birthdate": "age",
    "Contactdetails": "phone_number",
    "Address_Location:Other": "location",
    "Address_Location:Patient": "location",
    "Address_Location:Caregiver": "location",
    "Organization:Healthcare": "hospital",
}


class DeducePostProcessor(dd.process.DocProcessor):
    """Run the span post-processing pipeline on Belgian Deduce annotations."""

    def process(self, doc: dd.Document, **kwargs) -> None:
        del kwargs
        metadata = post_process_metadata(doc.metadata)
        if (
            len(doc.annotations) == 0
            and not metadata.get("patient_name")
            and not metadata.get("caregiver_names")
        ):
            return

        spans = deduce_annotations_to_post_spans(doc.annotations)
        processed_spans = post_process_spans(spans, doc.text, metadata=metadata)
        doc.annotations = dd.AnnotationSet(
            post_span_to_deduce_annotation(span, doc.text) for span in processed_spans
        )


def deduce_annotation_to_post_span(annotation: dd.Annotation) -> dict[str, Any]:
    """Convert one Belgian Deduce annotation to the internal post-process shape."""

    label = DEDUCE_TAG_TO_POST_LABEL.get(annotation.tag, annotation.tag)
    category, subtype = split_post_label(label)
    return {
        "begin": int(annotation.start_char),
        "end": int(annotation.end_char),
        "label": label,
        "text": str(annotation.text),
        "category": category,
        "subtype": subtype,
        "_deduce_tag": str(annotation.tag),
        "priority": int(annotation.priority),
    }


def deduce_annotations_to_post_spans(
    annotations: dd.AnnotationSet | list[dd.Annotation],
) -> list[dict[str, Any]]:
    """Convert multiple Belgian Deduce annotations to post-process spans."""

    return [deduce_annotation_to_post_span(annotation) for annotation in annotations]


def post_span_to_deduce_annotation(span: Mapping[str, Any], text: str) -> dd.Annotation:
    """Convert one processed span back to a Belgian Deduce annotation."""

    begin = int(span["begin"])
    end = int(span["end"])
    tag = str(
        span.get("_deduce_tag")
        or POST_LABEL_TO_DEDUCE_TAG.get(str(span.get("label")), span.get("label"))
    )
    return dd.Annotation(
        text=str(span.get("text", text[begin:end])),
        start_char=begin,
        end_char=end,
        tag=tag,
        priority=int(span.get("priority", 0)),
    )


def split_post_label(label: str) -> tuple[str, str | None]:
    """Return Category/Subtype fields for compatibility with span dictionaries."""

    if ":" not in label:
        return label, None
    category, subtype = label.split(":", maxsplit=1)
    return category, subtype


def post_process_metadata(metadata: dd.MetaData | Mapping[str, Any]) -> dict[str, Any]:
    """Translate Belgian Deduce metadata to the post-process metadata contract."""

    result: dict[str, Any] = {}

    patient_name = metadata_get(metadata, "patient_name")
    if patient_name:
        result["patient_name"] = patient_name
    else:
        patient = metadata_get(metadata, "patient")
        patient_name = patient_metadata_to_post_process_name(patient)
        if patient_name:
            result["patient_name"] = patient_name

    caregiver_names = metadata_get(metadata, "caregiver_names")
    if caregiver_names:
        result["caregiver_names"] = caregiver_names
    else:
        caregiver_names = person_metadata_to_caregiver_names(metadata)
        if caregiver_names:
            result["caregiver_names"] = caregiver_names

    document_creation_date = metadata_get(metadata, "document_creation_date")
    if document_creation_date:
        result["document_creation_date"] = str(document_creation_date)

    return result


def person_metadata_to_caregiver_names(
    metadata: dd.MetaData | Mapping[str, Any],
) -> list[dict[str, str]]:
    """Extract caregiver-name entries from Belgian Deduce person metadata."""

    names: list[dict[str, str]] = []
    for key in ("caregiver", "caregivers", "person", "persons", "people"):
        value = metadata_get(metadata, key)
        for person in normalize_metadata_items(value):
            name = patient_metadata_to_post_process_name(person)
            if name:
                names.append(name)
    return names


def normalize_metadata_items(value: Any) -> list[Any]:
    """Return a metadata value as a list while treating strings as scalars."""

    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def patient_metadata_to_post_process_name(patient: Any) -> dict[str, str] | None:
    """Extract the post-process patient-name contract from a Person-like object."""

    if patient is None:
        return None

    given_parts = []
    first_names = getattr(patient, "first_names", None)
    if first_names:
        given_parts.extend(str(first_name) for first_name in first_names)

    initials = getattr(patient, "initials", None)
    if initials:
        given_parts.append(str(initials))

    family_name = getattr(patient, "surname", None) or ""
    given_name = " ".join(part for part in given_parts if part).strip()

    if not given_name and not family_name:
        return None

    return {
        "given_name": given_name,
        "family_name": str(family_name).strip(),
    }


def metadata_get(metadata: dd.MetaData | Mapping[str, Any], key: str) -> Any:
    """Read a key from either docdeid metadata or a regular mapping."""

    if isinstance(metadata, Mapping):
        return metadata.get(key)
    return metadata[key]
