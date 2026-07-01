"""belgian-deduce production-label vocabulary (owned by belgian-deduce).

A belgian-deduce-specific label set derived from ProductionLabels, but which
**permits bare categories** (``Name``, ``ID``, ``Address_Location``) for
detections whose subtype is genuinely unknown. A subtype is only assigned when
there is a real signal:

* a **medical title** in front of a person  -> ``Name:Caregiver``
* the **national register number** (RRN)    -> ``ID:Patient`` (it is the patient's)
* per-document **metadata** (patient/caregiver names, injected ``known_values``)

Everything else that a rule engine cannot know (a bare person, a generic ``id``,
a loose address) stays a bare category rather than guessing a subtype.

``to_canonical`` maps this relaxed set down to the strict 15-label taxonomy for
evaluation / interop: bare ``Name`` -> ``Name:Other``, bare ``Address_Location``
-> ``Address_Location:Other``. Bare ``ID`` has no ``ID:Other`` in the taxonomy,
so it stays ``ID`` and is meant to be scored at the *category* level.
"""

from __future__ import annotations

# Medical / doctoral titles — the medically-related subset of the belgian-deduce
# ``lst_prefix`` lookup (the rest of that list is generic honorifics such as
# "de heer", "mevrouw", "mr" which do NOT imply a caregiver). Tune here.
MEDICAL_TITLES = frozenset(
    {
        "dr",
        "dr.",
        "dra",
        "dra.",
        "drs",
        "drs.",
        "prof",
        "prof.",
        "dr.h.c",
        "dr.h.c.",
        "collega",
    }
)

#: belgian-deduce native docdeid tag -> belgian production label.
#: Bare category where the subtype is unknown to the recognizer.
TAG_TO_LABEL: dict[str, str] = {
    "patient": "Name:Patient",
    "person": "Name",  # bare unless a medical title or metadata says otherwise
    "pseudo_name": "Name",
    "date": "Date",
    "age": "Age_Birthdate",
    "email": "Contactdetails",
    "phone_number": "Contactdetails",
    "url": "Contactdetails",
    "location": "Address_Location",  # bare
    "street": "Address_Location",  # bare
    "hospital": "Organization:Healthcare",
    "healthcare_institution": "Organization:Healthcare",
    "national_register_number": "ID:Patient",  # the RRN is the patient's
    "id": "ID",  # bare — role unknown
}

#: bare belgian label -> strict 15-label canonical, for eval / interop.
TO_CANONICAL: dict[str, str] = {
    "Name": "Name:Other",
    "Address_Location": "Address_Location:Other",
    # "ID" stays bare: no ID:Other in the taxonomy -> score at category level.
}


def has_medical_title(text: str) -> bool:
    """True if ``text`` begins with a medical title (dr / prof / ...)."""
    if not text:
        return False
    tokens = text.strip().split()
    if not tokens:
        return False
    return tokens[0].lower().rstrip(",") in MEDICAL_TITLES


def tag_to_label(tag: str, span_text: str = "") -> str:
    """Map a belgian-deduce native tag to a belgian production label.

    Applies the title-aware rule: a generic ``person`` becomes ``Name:Caregiver``
    only when its span text starts with a medical title; otherwise it stays a
    bare ``Name``. Unknown tags pass through unchanged.
    """
    label = TAG_TO_LABEL.get(tag, tag)
    if label == "Name" and has_medical_title(span_text):
        return "Name:Caregiver"
    return label


def to_canonical(label: str) -> str:
    """Map a belgian production label down to the strict 15-label taxonomy.

    Bare ``ID`` is returned unchanged (score it at the category level).
    """
    return TO_CANONICAL.get(label, label)
