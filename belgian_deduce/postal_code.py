"""Helpers for Belgian postcode-locality matching."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Iterable

_POSTAL_CODE_PATTERN = re.compile(r"(?i)^(?:B-)?(\d{4})$")
_PARENTHESIS_PATTERN = re.compile(r"\(([^()]*)\)")
_DISTRICT_PATTERN = re.compile(r"^(?P<base>.+?)\s+\d+\s*-\s*.+$")
_FORBIDDEN_KEYWORDS_PATTERN = re.compile(
    r"\b(?:ADMINISTRAT\w*|ASSEMBLEE|BELGACOM|BPOST|CAMERA|CENTER|CENTRE|"
    r"CHAMBRE|CHEQUE\w*|COMITE|COMMISSION|COMMISSIE|CONSEIL|CONTROL|"
    r"DIENST|EUROPA|EUROPEAN|FOD|FORCE\w*|GEMEENSCHAPSCOMMISSIE|"
    r"GOUVERNEMENT|IMMATRICULAT\w*|KAMER|MINISTER\w*|MOBILIT\w*|NAVO|"
    r"MAATSCHAPPIJ|OPTIRETOUR|ORGANISATION\w*|OTAN|PARLEMENT|POSTCHEQUE|"
    r"PRESS|PROMO|RADIO|REMAILING|RETOUR|RIJKSADMINISTRATIEF|RTBF|"
    r"SCANNING|SECURITY|SENAAT|SENAT|SERVICE|SINTERKLAAS|SOCIAL\w*|"
    r"STRIJDKRACHT\w*|TELEVISI\w*|TRANSPORT\w*|TVI|VLAAMS|VRT)\b"
)
_FORBIDDEN_PHRASES_PATTERN = re.compile(
    r"\b(?:ANCIEN\w*\s+COMMUNE|FUSION\s+ANNUL\w*|HAMEAU\s+DE|"
    r"SOUS\s+LE\s+NOM)\b"
)
_STREET_SUFFIX_PATTERN = re.compile(
    r"(?i)(?:LAAN|STRAAT|STEENWEG|WEG|STEIGER|STEEG|DREEF|KAAI|KADE|PLEIN|"
    r"GRACHT|MARKT|PARK|SINGEL|RUE|CHAUSSEE|AVENUE|BOULEVARD|ALLEE|LEI|"
    r"BAAN|PAD|DRIVE|ROAD)\b"
)
_WHITESPACE_PATTERN = re.compile(r"\s+")
_LIST_SEPARATOR_PATTERN = re.compile(r"\s*,\s*")


def clean_location_text(text: str) -> str:
    """Normalize whitespace and strip wrapper punctuation around a location string."""

    text = (
        text.replace("\xa0", " ")
        .replace("’", "'")
        .replace("`", "'")
        .replace("“", '"')
        .replace("”", '"')
    )
    text = _WHITESPACE_PATTERN.sub(" ", text).strip()
    text = text.strip(' "«»,;:/-–—')
    text = text.replace("( ", "(").replace(" )", ")")
    return text.strip()


def normalize_postal_code(text: str) -> str | None:
    """Return a normalized Belgian postcode, or ``None`` when the text is not one."""

    match = _POSTAL_CODE_PATTERN.fullmatch(text.strip())
    if match is None:
        return None

    return match.group(1)


def normalize_locality_for_match(text: str) -> str:
    """Normalize a locality string for case- and accent-insensitive matching."""

    text = clean_location_text(text)
    text = unicodedata.normalize("NFD", text)
    text = text.encode("ascii", "ignore").decode("utf-8")
    return _WHITESPACE_PATTERN.sub(" ", text).strip().upper()


def is_geographic_locality_candidate(candidate: str) -> bool:
    """Heuristic filter that keeps geographic localities and rejects special entries."""

    candidate = clean_location_text(candidate)

    if len(candidate) == 0 or any(ch.isdigit() for ch in candidate):
        return False

    if not any(ch.isupper() for ch in candidate):
        return False

    normalized = normalize_locality_for_match(candidate)
    stripped_letters = re.sub(r"[^A-Za-z]", "", candidate)

    if len(normalized) == 0:
        return False

    if _FORBIDDEN_KEYWORDS_PATTERN.search(normalized):
        return False

    if _FORBIDDEN_PHRASES_PATTERN.search(normalized):
        return False

    if _STREET_SUFFIX_PATTERN.search(normalized):
        return False

    if "," in candidate:
        return False

    if candidate.count(".") >= 2:
        return False

    if (
        len(stripped_letters) <= 6
        and len(stripped_letters) != 0
        and stripped_letters.isupper()
        and stripped_letters.lower() != stripped_letters
    ):
        return False

    return True


def derive_locality_candidates(raw_text: str) -> set[str]:
    """Derive geographic locality variants from a raw page entry."""

    text = clean_location_text(raw_text)
    if len(text) == 0:
        return set()

    candidates: set[str] = set()
    without_parentheses = clean_location_text(_PARENTHESIS_PATTERN.sub("", text))

    district_match = _DISTRICT_PATTERN.match(without_parentheses)

    if district_match is not None:
        candidates.add(district_match.group("base"))
    elif "(" not in text:
        candidates.add(text)

    if len(without_parentheses) != 0:
        candidates.add(without_parentheses)

    for parenthetical_content in _PARENTHESIS_PATTERN.findall(text):
        candidates.add(parenthetical_content)

    expanded_candidates = set()
    for candidate in candidates:
        expanded_candidates.add(candidate)
        if "," in candidate:
            expanded_candidates.update(_LIST_SEPARATOR_PATTERN.split(candidate))

    return {
        clean_location_text(candidate)
        for candidate in expanded_candidates
        if is_geographic_locality_candidate(candidate)
    }


def build_postcode_locality_map(rows: Iterable[str]) -> dict[str, set[str]]:
    """Build a postcode-to-locality map from raw ``postcode<TAB>locality`` rows."""

    mapping: dict[str, set[str]] = defaultdict(set)

    for row in rows:
        row = row.strip()
        if len(row) == 0:
            continue

        postcode, raw_text = row.split("\t", maxsplit=1)
        normalized_postcode = normalize_postal_code(postcode)

        if normalized_postcode is None:
            continue

        mapping[normalized_postcode].update(
            normalize_locality_for_match(candidate)
            for candidate in derive_locality_candidates(raw_text)
        )

    return dict(mapping)
