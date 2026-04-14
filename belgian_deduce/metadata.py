from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Union


DateLike = Union[date, datetime, str]


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen = set()
    deduped = []

    for item in items:
        item = item.strip()

        if item and item not in seen:
            seen.add(item)
            deduped.append(item)

    return deduped


@dataclass
class MetadataEntity:
    """
    Exact metadata-driven entity that should always be tagged when it occurs in text.

    Args:
        text: The primary value to match.
        tag: The tag that should be emitted, e.g. ``persoon`` or ``locatie``.
        variants: Optional textual variants that should map to the same tag.
    """

    text: str
    tag: str
    variants: Optional[list[str]] = None

    def iter_texts(self) -> list[str]:
        """Return all textual variants, while preserving order."""

        return _dedupe_keep_order([self.text, *(self.variants or [])])


@dataclass
class Address:
    """
    Address metadata that can be converted into location entities.

    Args:
        street: Street name.
        house_number: House number, optionally without suffix.
        unit: Optional suffix or unit, e.g. ``A`` or ``bus 4``.
        postal_code: Postal code.
        city: City or municipality.
        country: Country.
        lines: One or multiple exact address lines.
    """

    street: Optional[str] = None
    house_number: Optional[str] = None
    unit: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    lines: Optional[list[str]] = None

    def as_entities(self) -> list[MetadataEntity]:
        """Convert the address into a set of location entities."""

        texts = list(self.lines or [])

        house_number = self.house_number or ""
        unit = self.unit or ""
        house_part = " ".join(part for part in [house_number, unit] if part).strip()
        street_line = " ".join(
            part for part in [self.street or "", house_part] if part
        ).strip()
        locality = " ".join(
            part for part in [self.postal_code or "", self.city or ""] if part
        ).strip()

        if self.street:
            texts.append(self.street)

        if street_line:
            texts.append(street_line)

        if self.city:
            texts.append(self.city)

        if self.country:
            texts.append(self.country)

        if locality:
            texts.append(locality)

        if street_line and locality:
            texts.extend([f"{street_line} {locality}", f"{street_line}, {locality}"])

        if self.postal_code and not texts:
            texts.append(self.postal_code)

        return [
            MetadataEntity(text=text, tag="locatie")
            for text in _dedupe_keep_order(texts)
        ]


@dataclass
class Person:
    """
    Contains information on a person.

    Usable in a document metadata, where annotators can access it for annotation.
    """

    first_names: Optional[list[str]] = None
    initials: Optional[str] = None
    surname: Optional[str] = None
    birth_date: Optional[DateLike] = None
    aliases: Optional[list[str]] = None
    addresses: Optional[list[Address]] = None

    @classmethod
    def from_keywords(
        cls,
        patient_first_names: str = "",
        patient_initials: str = "",
        patient_surname: str = "",
        patient_given_name: str = "",
    ) -> Person:
        """
        Get a Person from keywords. Mainly used for compatibility with keyword as used
        in deduce<=1.0.8.

        Args:
            patient_first_names: The patient first names, separated by whitespace.
            patient_initials: The patient initials.
            patient_surname: The patient surname.
            patient_given_name: The patient given name.

        Returns:
            A Person object containing the patient information.
        """

        patient_first_names_lst = []

        if patient_first_names:
            patient_first_names_lst = patient_first_names.split(" ")

        if patient_given_name:
            patient_first_names_lst.append(patient_given_name)

        return cls(
            first_names=patient_first_names_lst or None,
            initials=patient_initials or None,
            surname=patient_surname or None,
        )

    @staticmethod
    def _birth_date_variants(value: DateLike) -> list[str]:
        if isinstance(value, datetime):
            value = value.date()

        if isinstance(value, str):
            return _dedupe_keep_order([value])

        month_names = {
            1: ["januari", "janvier", "january"],
            2: ["februari", "fevrier", "february"],
            3: ["maart", "mars", "march"],
            4: ["april"],
            5: ["mei", "mai", "may"],
            6: ["juni", "juin", "june"],
            7: ["juli", "juillet", "july"],
            8: ["augustus", "aout", "august"],
            9: ["september"],
            10: ["oktober", "octobre", "october"],
            11: ["november"],
            12: ["december", "decembre"],
        }

        variants = [
            value.strftime("%Y-%m-%d"),
            f"{value.day:02d}-{value.month:02d}-{value.year}",
            f"{value.day}-{value.month}-{value.year}",
            f"{value.day:02d}/{value.month:02d}/{value.year}",
            f"{value.day}/{value.month}/{value.year}",
            f"{value.day:02d}.{value.month:02d}.{value.year}",
            f"{value.day}.{value.month}.{value.year}",
        ]

        for month_name in month_names[value.month]:
            variants.extend(
                [
                    f"{value.day} {month_name} {value.year}",
                    f"{value.day:02d} {month_name} {value.year}",
                    f"{value.day} {month_name.capitalize()} {value.year}",
                    f"{value.day:02d} {month_name.capitalize()} {value.year}",
                ]
            )

        return _dedupe_keep_order(variants)

    def as_entities(self, tag: str) -> list[MetadataEntity]:
        """Convert person metadata that is not name-structure specific into entities."""

        entities = [
            MetadataEntity(text=alias, tag=tag)
            for alias in _dedupe_keep_order(self.aliases or [])
        ]

        if self.birth_date is not None:
            date_variants = self._birth_date_variants(self.birth_date)
            entities.append(
                MetadataEntity(
                    text=date_variants[0],
                    tag="datum",
                    variants=date_variants[1:],
                )
            )

        for address in self.addresses or []:
            entities.extend(address.as_entities())

        return entities


__all__ = ["Address", "DateLike", "MetadataEntity", "Person"]
