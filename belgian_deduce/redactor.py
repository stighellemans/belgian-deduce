from __future__ import annotations

import hashlib
import re
import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

import docdeid as dd
from rapidfuzz.distance import DamerauLevenshtein

from belgian_deduce.date_pseudonyms import pseudonymize_date_text_body

_DATE_TAGS = {"date", "datum"}
_MIN_RECOMMENDED_ABS_DATE_SHIFT_DAYS = 8
_SHORT_DATE_SHIFT_WARNING = (
    "Date shifting by 7 days or less is not recommended. Small shifts can be "
    "easier to reverse engineer from weekday patterns, document creation patterns, "
    "or explicit weekdays in text. Use a shift greater than 7 days."
)
_GLOBAL_DATE_SHIFT_WARNING = (
    "Configuring redactor_date_shift_days on the model applies the same date shift "
    "wherever that model is reused. Prefer a separate date shift per "
    "time-conserving block of text, such as a patient-level or hospitalization-level "
    "block. Reusing one shift for a whole dataset increases the attack surface for "
    "re-identifying original dates."
)

_MONTH_RENDERING = {
    "nl_full": (
        "januari",
        "februari",
        "maart",
        "april",
        "mei",
        "juni",
        "juli",
        "augustus",
        "september",
        "oktober",
        "november",
        "december",
    ),
    "nl_abbr": (
        "jan",
        "feb",
        "mrt",
        "apr",
        "mei",
        "jun",
        "jul",
        "aug",
        "sep",
        "okt",
        "nov",
        "dec",
    ),
    "fr_full": (
        "janvier",
        "fevrier",
        "mars",
        "avril",
        "mai",
        "juin",
        "juillet",
        "aout",
        "septembre",
        "octobre",
        "novembre",
        "decembre",
    ),
    "fr_full_accented": (
        "janvier",
        "février",
        "mars",
        "avril",
        "mai",
        "juin",
        "juillet",
        "août",
        "septembre",
        "octobre",
        "novembre",
        "décembre",
    ),
    "fr_abbr": (
        "janv",
        "fevr",
        "mars",
        "avr",
        "mai",
        "juin",
        "juil",
        "aout",
        "sept",
        "oct",
        "nov",
        "dec",
    ),
    "fr_abbr_accented": (
        "janv",
        "févr",
        "mars",
        "avr",
        "mai",
        "juin",
        "juil",
        "août",
        "sept",
        "oct",
        "nov",
        "déc",
    ),
    "en_full": (
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    ),
    "en_abbr": (
        "jan",
        "feb",
        "mar",
        "apr",
        "may",
        "jun",
        "jul",
        "aug",
        "sep",
        "oct",
        "nov",
        "dec",
    ),
}

_MONTH_STYLE_BY_TOKEN = {
    "januari": ("nl_full", 1),
    "jan": ("nl_abbr", 1),
    "februari": ("nl_full", 2),
    "feb": ("nl_abbr", 2),
    "maart": ("nl_full", 3),
    "mrt": ("nl_abbr", 3),
    "april": ("nl_full", 4),
    "apr": ("nl_abbr", 4),
    "mei": ("nl_full", 5),
    "juni": ("nl_full", 6),
    "jun": ("nl_abbr", 6),
    "juli": ("nl_full", 7),
    "jul": ("nl_abbr", 7),
    "augustus": ("nl_full", 8),
    "aug": ("nl_abbr", 8),
    "september": ("nl_full", 9),
    "sep": ("nl_abbr", 9),
    "oktober": ("nl_full", 10),
    "okt": ("nl_abbr", 10),
    "november": ("nl_full", 11),
    "nov": ("nl_abbr", 11),
    "december": ("nl_full", 12),
    "dec": ("nl_abbr", 12),
    "janvier": ("fr_full", 1),
    "janv": ("fr_abbr", 1),
    "fevrier": ("fr_full", 2),
    "février": ("fr_full_accented", 2),
    "fevr": ("fr_abbr", 2),
    "févr": ("fr_abbr_accented", 2),
    "mars": ("fr_full", 3),
    "avril": ("fr_full", 4),
    "mai": ("fr_full", 5),
    "juin": ("fr_full", 6),
    "juillet": ("fr_full", 7),
    "aout": ("fr_full", 8),
    "août": ("fr_full_accented", 8),
    "septembre": ("fr_full", 9),
    "sept": ("fr_abbr", 9),
    "octobre": ("fr_full", 10),
    "oct": ("fr_abbr", 10),
    "novembre": ("fr_full", 11),
    "decembre": ("fr_full", 12),
    "décembre": ("fr_full_accented", 12),
    "january": ("en_full", 1),
    "february": ("en_full", 2),
    "march": ("en_full", 3),
    "mar": ("en_abbr", 3),
    "may": ("en_full", 5),
    "june": ("en_full", 6),
    "july": ("en_full", 7),
    "august": ("en_full", 8),
    "october": ("en_full", 10),
}

_NUMERIC_DATE_PATTERN = re.compile(
    r"^(?P<first>\d{1,4})(?P<sep1>[-/. ])(?P<second>\d{1,2})"
    r"(?P<sep2>[-/. ])(?P<third>(?:19|20|'|`)?\d{2})$",
    re.IGNORECASE,
)
_TEXTUAL_DMY_PATTERN = re.compile(
    r"^(?P<day>\d{1,2})(?P<sep1>[-/. ]{1,2})"
    r"(?P<month>[A-Za-zÀ-ÿ]+)(?P<dot>\.?)"
    r"(?P<sep2>[-/. ]+)(?P<year>(?:19|20|'|`)?\d{2})$",
    re.IGNORECASE,
)
_TEXTUAL_YMD_PATTERN = re.compile(
    r"^(?P<year>(?:19|20|'|`)?\d{2})(?P<sep1>[-/. ]{1,2})"
    r"(?P<month>[A-Za-zÀ-ÿ]+)(?P<dot>\.?)"
    r"(?P<sep2>[-/. ]+)(?P<day>\d{1,2})$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _DateRenderStyle:
    order: str
    day_width: int
    month_width: int
    year_width: int
    first_separator: str
    second_separator: str
    month_style: str = "numeric"
    month_has_trailing_dot: bool = False
    year_prefix: str = ""


def _normalize_month_token(token: str) -> str:
    return token.strip().casefold()


def _month_style_and_value(token: str) -> tuple[str, int]:
    return _MONTH_STYLE_BY_TOKEN[_normalize_month_token(token)]


def _expand_year_token(token: str) -> tuple[int, int, str]:
    year_prefix = ""
    digits = token

    if token and token[0] in {"'", "`"}:
        year_prefix = token[0]
        digits = token[1:]

    if len(digits) == 4:
        return int(digits), 4, year_prefix

    year_suffix = int(digits)
    year_value = 2000 + year_suffix if year_suffix <= 30 else 1900 + year_suffix
    return year_value, 2, year_prefix


def _render_year(year: int, width: int, prefix: str) -> str:
    if width == 4:
        return f"{year:04d}"

    return f"{prefix}{year % 100:02d}"


def _match_case_style(replacement: str, original_text: str) -> str:
    stripped_original = original_text.strip()

    if not stripped_original:
        return replacement
    if stripped_original.isupper():
        return replacement.upper()
    if stripped_original.islower():
        return replacement.lower()
    if stripped_original.istitle():
        return replacement.title()

    return replacement


def _extract_month_token(value: str) -> str:
    for token in value.split():
        normalized = token.rstrip(".")

        if _normalize_month_token(normalized) in _MONTH_STYLE_BY_TOKEN:
            return normalized

    return value


def _render_month(month_number: int, month_style: str, original_text: str) -> str:
    month_text = _MONTH_RENDERING[month_style][month_number - 1]
    return _match_case_style(month_text, _extract_month_token(original_text))


def _wrap_with_original_whitespace(rendered: str, original_text: str) -> str:
    match = re.match(r"^(\s*)(.*?)(\s*)$", original_text, flags=re.DOTALL)

    if match is None:
        return rendered

    return f"{match.group(1)}{rendered}{match.group(3)}"


def _parse_date_literal(value: str) -> tuple[date, _DateRenderStyle]:
    stripped = value.strip()
    numeric_match = _NUMERIC_DATE_PATTERN.fullmatch(stripped)

    if numeric_match:
        first = numeric_match.group("first")
        second = numeric_match.group("second")
        third = numeric_match.group("third")
        order = "ymd" if len(first) == 4 else "dmy"
        year_value, year_width, year_prefix = _expand_year_token(
            third if order == "dmy" else first
        )

        if order == "dmy":
            parsed_date = date(year_value, int(second), int(first))
            style = _DateRenderStyle(
                order="dmy",
                day_width=len(first),
                month_width=len(second),
                year_width=year_width,
                first_separator=numeric_match.group("sep1"),
                second_separator=numeric_match.group("sep2"),
                year_prefix=year_prefix,
            )
        else:
            parsed_date = date(year_value, int(second), int(third))
            style = _DateRenderStyle(
                order="ymd",
                day_width=len(third),
                month_width=len(second),
                year_width=year_width,
                first_separator=numeric_match.group("sep1"),
                second_separator=numeric_match.group("sep2"),
                year_prefix=year_prefix,
            )

        return parsed_date, style

    dmy_match = _TEXTUAL_DMY_PATTERN.fullmatch(stripped)

    if dmy_match:
        month_style, month_value = _month_style_and_value(dmy_match.group("month"))
        year_value, year_width, year_prefix = _expand_year_token(
            dmy_match.group("year")
        )

        return (
            date(year_value, month_value, int(dmy_match.group("day"))),
            _DateRenderStyle(
                order="dmy",
                day_width=len(dmy_match.group("day")),
                month_width=0,
                year_width=year_width,
                first_separator=dmy_match.group("sep1"),
                second_separator=dmy_match.group("sep2"),
                month_style=month_style,
                month_has_trailing_dot=bool(dmy_match.group("dot")),
                year_prefix=year_prefix,
            ),
        )

    ymd_match = _TEXTUAL_YMD_PATTERN.fullmatch(stripped)

    if ymd_match:
        month_style, month_value = _month_style_and_value(ymd_match.group("month"))
        year_value, year_width, year_prefix = _expand_year_token(
            ymd_match.group("year")
        )

        return (
            date(year_value, month_value, int(ymd_match.group("day"))),
            _DateRenderStyle(
                order="ymd",
                day_width=len(ymd_match.group("day")),
                month_width=0,
                year_width=year_width,
                first_separator=ymd_match.group("sep1"),
                second_separator=ymd_match.group("sep2"),
                month_style=month_style,
                month_has_trailing_dot=bool(ymd_match.group("dot")),
                year_prefix=year_prefix,
            ),
        )

    raise ValueError(f"Unsupported date literal: {value}")


def _render_date_literal(
    shifted_date: date,
    style: _DateRenderStyle,
    original_text: str,
) -> str:
    day_part = (
        f"{shifted_date.day:0{style.day_width}d}"
        if style.day_width > 1
        else str(shifted_date.day)
    )
    year_part = _render_year(shifted_date.year, style.year_width, style.year_prefix)

    if style.month_style == "numeric":
        month_part = (
            f"{shifted_date.month:0{style.month_width}d}"
            if style.month_width > 1
            else str(shifted_date.month)
        )
    else:
        month_part = _render_month(shifted_date.month, style.month_style, original_text)

        if style.month_has_trailing_dot:
            month_part = f"{month_part}."

    if style.order == "ymd":
        rendered = (
            f"{year_part}{style.first_separator}{month_part}"
            f"{style.second_separator}{day_part}"
        )
    else:
        rendered = (
            f"{day_part}{style.first_separator}{month_part}"
            f"{style.second_separator}{year_part}"
        )

    return _wrap_with_original_whitespace(rendered, original_text)


def _shift_date_literal(value: str, days: int) -> str:
    """Shift a date literal by a number of days while preserving its format."""

    parsed_date, render_style = _parse_date_literal(value)
    shifted_date = parsed_date + timedelta(days=days)
    return _render_date_literal(shifted_date, render_style, value)


def _coerce_date_shift_days(value) -> Optional[int]:
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, str):
        stripped = value.strip()

        if stripped:
            return int(stripped)

    return None


def _safe_deterministic_shift_days(value) -> Optional[int]:
    if value is None:
        return None

    if isinstance(value, datetime):
        value = value.date()

    if isinstance(value, date):
        seed = value.isoformat()
    else:
        seed = str(value).strip()

    if not seed:
        return None

    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    weeks = 6 + (int.from_bytes(digest[:2], "big") % 99)
    direction = -1 if digest[2] % 2 else 1
    return direction * weeks * 7


def _metadata_get(metadata: Optional[dd.MetaData | Mapping], key: str):
    if metadata is None:
        return None
    if isinstance(metadata, Mapping):
        return metadata.get(key)
    return metadata[key]


def _document_creation_date_from_metadata(
    metadata: Optional[dd.MetaData | Mapping],
) -> Optional[str]:
    value = _metadata_get(metadata, "document_creation_date")
    return str(value) if value else None


def _context_before(text: str, annotation: dd.Annotation) -> str:
    return text[max(0, annotation.start_char - 80) : annotation.start_char]


def _context_after(text: str, annotation: dd.Annotation) -> str:
    return text[annotation.end_char : min(len(text), annotation.end_char + 80)]


def _is_degree_prefixed_date(text: str, annotation: dd.Annotation) -> bool:
    return annotation.start_char > 0 and text[annotation.start_char - 1] in {"°", "º"}


def _warn_if_short_date_shift(date_shift_days: Optional[int]) -> None:
    if date_shift_days is None:
        return

    if abs(date_shift_days) < _MIN_RECOMMENDED_ABS_DATE_SHIFT_DAYS:
        warnings.warn(_SHORT_DATE_SHIFT_WARNING, RuntimeWarning, stacklevel=3)


def _warn_if_global_date_shift(date_shift_days: Optional[int]) -> None:
    if date_shift_days is None:
        return

    warnings.warn(_GLOBAL_DATE_SHIFT_WARNING, RuntimeWarning, stacklevel=3)


class DeduceRedactor(dd.process.SimpleRedactor):
    """
    Implements the redacting logic of Deduce:

    - All annotations with "patient" tag are replaced with <PATIENT>
    - All other annotations are replaced with <TAG-n>, with n identifying a group
        of annotations with a similar text (edit_distance <= 1).
    """

    def __init__(
        self,
        open_char: str = "[",
        close_char: str = "]",
        check_overlap: bool = True,
        date_strategy: str = "replace",
        date_shift_days: Optional[int] = None,
        date_shift_days_key: str = "date_shift_days",
        date_shift_seed_key: Optional[str] = None,
    ) -> None:
        super().__init__(
            open_char=open_char,
            close_char=close_char,
            check_overlap=check_overlap,
        )
        self.date_strategy = date_strategy
        self.date_shift_days = date_shift_days
        self.date_shift_days_key = date_shift_days_key
        self.date_shift_seed_key = date_shift_seed_key

        if self.date_strategy == "shift":
            configured_shift = _coerce_date_shift_days(self.date_shift_days)
            _warn_if_global_date_shift(configured_shift)
            _warn_if_short_date_shift(configured_shift)

    def process(self, doc: dd.Document, **kwargs) -> None:
        del kwargs
        doc.set_deidentified_text(
            self.redact(
                doc.text,
                doc.annotations,
                date_shift_days=self._date_shift_days_from_metadata(doc.metadata),
                metadata=doc.metadata,
            )
        )

    def _date_shift_days_from_metadata(self, metadata: dd.MetaData) -> Optional[int]:
        date_shift_days = _coerce_date_shift_days(self.date_shift_days)

        if date_shift_days is not None:
            _warn_if_short_date_shift(date_shift_days)
            return date_shift_days

        date_shift_days = _coerce_date_shift_days(metadata[self.date_shift_days_key])

        if date_shift_days is not None:
            _warn_if_short_date_shift(date_shift_days)
            return date_shift_days

        if self.date_shift_seed_key is not None:
            date_shift_days = _safe_deterministic_shift_days(
                metadata[self.date_shift_seed_key]
            )
            _warn_if_short_date_shift(date_shift_days)
            return date_shift_days

        return None

    def _date_replacement(
        self,
        annotation: dd.Annotation,
        text: str,
        date_shift_days: Optional[int],
        metadata: Optional[dd.MetaData | Mapping] = None,
    ) -> Optional[str]:
        if self.date_strategy != "shift" or annotation.tag not in _DATE_TAGS:
            return None

        if date_shift_days is None:
            return None

        label = (
            "Age_Birthdate" if _is_degree_prefixed_date(text, annotation) else "Date"
        )
        substitute = pseudonymize_date_text_body(
            annotation.text,
            label=label,
            date_shift_days=date_shift_days,
            context_before=_context_before(text, annotation),
            context_after=_context_after(text, annotation),
            document_creation_date=_document_creation_date_from_metadata(metadata),
        )
        if substitute is not None:
            return substitute

        if label != "Date":
            return None

        try:
            return _shift_date_literal(annotation.text, date_shift_days)
        except (KeyError, ValueError):
            return None

    def redact(
        self,
        text: str,
        annotations: dd.AnnotationSet,
        date_shift_days: Optional[int] = None,
        metadata: Optional[dd.MetaData | Mapping] = None,
    ) -> str:
        if date_shift_days is None:
            date_shift_days = _coerce_date_shift_days(self.date_shift_days)

        if self.date_strategy == "shift":
            _warn_if_short_date_shift(date_shift_days)

        annotations_to_intext_replacement = {}

        for tag, annotation_group in self._group_annotations_by_tag(
            annotations
        ).items():
            annotations_to_replacement_group: dict[dd.Annotation, str] = {}
            counter = 1

            for annotation in sorted(
                annotation_group, key=lambda a: a.get_sort_key(by=("end_char",))
            ):
                date_replacement = self._date_replacement(
                    annotation, text, date_shift_days, metadata
                )

                if date_replacement is not None:
                    annotations_to_intext_replacement[annotation] = date_replacement
                    continue

                if tag == "patient":
                    annotations_to_intext_replacement[annotation] = (
                        f"{self.open_char}" f"PATIENT" f"{self.close_char}"
                    )

                else:
                    match = False

                    # Check match with any
                    for (
                        annotation_match,
                        replacement,
                    ) in annotations_to_replacement_group.items():
                        if (
                            DamerauLevenshtein.distance(
                                annotation.text, annotation_match.text, score_cutoff=1
                            )
                            <= 1
                        ):
                            annotations_to_replacement_group[annotation] = replacement
                            match = True
                            break

                    if not match:
                        annotations_to_replacement_group[annotation] = (
                            f"{self.open_char}"
                            f"{annotation.tag.upper()}"
                            f"-"
                            f"{counter}"
                            f"{self.close_char}"
                        )

                        counter += 1

                annotations_to_intext_replacement |= annotations_to_replacement_group

        return self._replace_annotations_in_text(
            text, annotations, annotations_to_intext_replacement
        )
