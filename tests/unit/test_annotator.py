import re
from datetime import date
from unittest.mock import patch

import docdeid as dd
import pytest

from belgian_deduce.annotator import (
    BsnAnnotator,
    ContextAnnotator,
    MetadataEntityAnnotator,
    NationalRegisterNumberAnnotator,
    PatientNameAnnotator,
    PhoneNumberAnnotator,
    RegexpPseudoAnnotator,
    TokenPatternAnnotator,
    _PatternPositionMatcher,
)
from belgian_deduce.person import Address, MetadataEntity, Person
from belgian_deduce.tokenizer import DeduceTokenizer
from tests.helpers import linked_tokens

BELGIAN_PHONE_REGEXP = (
    r"(?<!\d)"
    r"(?P<prefix>\(?(?:(?:0032|\+32|0))(?P<prefix_code>4\d{2}|800|90[0-9]|78|[1-9]\d|2|3|4|9)\)?)"
    r"(?P<number>(?:[\s./-]?\d){4,8})(?!\d)"
)


@pytest.fixture
def ds():
    ds = dd.ds.DsCollection()

    first_names = ["Andries", "pieter", "Aziz", "Bernard"]
    surnames = ["Meijer", "Smit", "Bakker", "Heerma"]

    ds["first_names"] = dd.ds.LookupSet()
    ds["first_names"].add_items_from_iterable(items=first_names)

    ds["surnames"] = dd.ds.LookupSet()
    ds["surnames"].add_items_from_iterable(items=surnames)

    return ds


@pytest.fixture
def tokenizer():
    return DeduceTokenizer()


@pytest.fixture
def regexp_pseudo_doc(tokenizer):
    return dd.Document(
        text="De patient is Na 12 jaar gestopt met medicijnen.",
        tokenizers={"default": tokenizer},
    )


@pytest.fixture
def pattern_doc(tokenizer):
    return dd.Document(
        text="De man heet Andries Meijer-Heerma, voornaam Andries.",
        tokenizers={"default": tokenizer},
    )


@pytest.fixture
def bsn_doc():
    d = dd.DocDeid()

    return d.deidentify(
        text="Geldige voorbeelden zijn: 111222333 en 123456782. "
        "Patientnummer is 01234, en ander id 01234567890."
    )


@pytest.fixture
def national_register_doc():
    d = dd.DocDeid()

    return d.deidentify(
        text="85.07.30-033.28 00.01.01-001.05 85.07.30-033.29 01234567890"
    )


@pytest.fixture
def phone_number_doc():
    d = dd.DocDeid()

    return d.deidentify(
        text="016 55 55 55 0470 12 34 56 +32470123456 0800 12 345 04701234 "
        "047012345678"
    )


@pytest.fixture
def surname_pattern():
    return linked_tokens(["Van der", "Heide", "-", "Ginkel"])


def token(text: str):
    return dd.Token(text=text, start_char=0, end_char=len(text))


class TestPositionMatcher:
    def test_equal(self):
        assert _PatternPositionMatcher.match({"equal": "test"}, token=token("test"))
        assert not _PatternPositionMatcher.match({"equal": "_"}, token=token("test"))

    def test_re_match(self):
        assert _PatternPositionMatcher.match({"re_match": "[a-z]"}, token=token("abc"))
        assert _PatternPositionMatcher.match(
            {"re_match": "[a-z]"}, token=token("abc123")
        )
        assert not _PatternPositionMatcher.match({"re_match": "[a-z]"}, token=token(""))
        assert not _PatternPositionMatcher.match(
            {"re_match": "[a-z]"}, token=token("123")
        )
        assert not _PatternPositionMatcher.match(
            {"re_match": "[a-z]"}, token=token("123abc")
        )

    def test_is_initials(self):
        assert _PatternPositionMatcher.match({"is_initials": True}, token=token("A"))
        assert _PatternPositionMatcher.match({"is_initials": True}, token=token("AB"))
        assert _PatternPositionMatcher.match({"is_initials": True}, token=token("ABC"))
        assert _PatternPositionMatcher.match({"is_initials": True}, token=token("ABCD"))
        assert not _PatternPositionMatcher.match(
            {"is_initials": True}, token=token("ABCDE")
        )
        assert not _PatternPositionMatcher.match({"is_initials": True}, token=token(""))
        assert not _PatternPositionMatcher.match(
            {"is_initials": True}, token=token("abcd")
        )
        assert not _PatternPositionMatcher.match(
            {"is_initials": True}, token=token("abcde")
        )

    def test_match_like_name(self):
        pattern_position = {"like_name": True}

        assert _PatternPositionMatcher.match(pattern_position, token=token("Diederik"))
        assert not _PatternPositionMatcher.match(pattern_position, token=token("Le"))
        assert not _PatternPositionMatcher.match(
            pattern_position, token=token("diederik")
        )
        assert not _PatternPositionMatcher.match(
            pattern_position, token=token("Diederik3")
        )

    def test_match_lookup(self, ds):
        assert _PatternPositionMatcher.match(
            {"lookup": "first_names"}, token=token("Andries"), ds=ds
        )
        assert not _PatternPositionMatcher.match(
            {"lookup": "first_names"}, token=token("andries"), ds=ds
        )
        assert not _PatternPositionMatcher.match(
            {"lookup": "surnames"}, token=token("Andries"), ds=ds
        )
        assert not _PatternPositionMatcher.match(
            {"lookup": "first_names"}, token=token("Smit"), ds=ds
        )
        assert _PatternPositionMatcher.match(
            {"lookup": "surnames"}, token=token("Smit"), ds=ds
        )
        assert not _PatternPositionMatcher.match(
            {"lookup": "surnames"}, token=token("smit"), ds=ds
        )

    def test_match_neg_lookup(self, ds):
        assert not _PatternPositionMatcher.match(
            {"neg_lookup": "first_names"}, token=token("Andries"), ds=ds
        )
        assert _PatternPositionMatcher.match(
            {"neg_lookup": "first_names"}, token=token("andries"), ds=ds
        )
        assert _PatternPositionMatcher.match(
            {"neg_lookup": "surnames"}, token=token("Andries"), ds=ds
        )
        assert _PatternPositionMatcher.match(
            {"neg_lookup": "first_names"}, token=token("Smit"), ds=ds
        )
        assert not _PatternPositionMatcher.match(
            {"neg_lookup": "surnames"}, token=token("Smit"), ds=ds
        )
        assert _PatternPositionMatcher.match(
            {"neg_lookup": "surnames"}, token=token("smit"), ds=ds
        )

    def test_match_and(self):
        assert _PatternPositionMatcher.match(
            {"and": [{"equal": "Abcd"}, {"like_name": True}]},
            token=token("Abcd"),
            ds=ds,
        )
        assert not _PatternPositionMatcher.match(
            {"and": [{"equal": "dcef"}, {"like_name": True}]},
            token=token("Abcd"),
            ds=ds,
        )
        assert not _PatternPositionMatcher.match(
            {"and": [{"equal": "A"}, {"like_name": True}]}, token=token("A"), ds=ds
        )
        assert not _PatternPositionMatcher.match(
            {"and": [{"equal": "b"}, {"like_name": True}]}, token=token("a"), ds=ds
        )

    def test_match_or(self):
        assert _PatternPositionMatcher.match(
            {"or": [{"equal": "Abcd"}, {"like_name": True}]}, token=token("Abcd"), ds=ds
        )
        assert _PatternPositionMatcher.match(
            {"or": [{"equal": "dcef"}, {"like_name": True}]}, token=token("Abcd"), ds=ds
        )
        assert _PatternPositionMatcher.match(
            {"or": [{"equal": "A"}, {"like_name": True}]}, token=token("A"), ds=ds
        )
        assert not _PatternPositionMatcher.match(
            {"or": [{"equal": "b"}, {"like_name": True}]}, token=token("a"), ds=ds
        )


class TestTokenPatternAnnotator:
    def test_match_sequence(self, pattern_doc, ds):
        pattern = [{"lookup": "first_names"}, {"like_name": True}]

        tpa = TokenPatternAnnotator(pattern=[{}], ds=ds, tag="_")

        assert tpa._match_sequence(
            pattern_doc.text, start_token=pattern_doc.get_tokens()[3], pattern=pattern
        ) == dd.Annotation(text="Andries Meijer", start_char=12, end_char=26, tag="_")
        assert (
            tpa._match_sequence(
                pattern_doc.text,
                start_token=pattern_doc.get_tokens()[7],
                pattern=pattern,
            )
            is None
        )

    def test_match_sequence_left(self, pattern_doc, ds):
        pattern = [{"lookup": "first_names"}, {"like_name": True}]

        tpa = TokenPatternAnnotator(pattern=[{}], ds=ds, tag="_")

        assert tpa._match_sequence(
            pattern_doc.text,
            start_token=pattern_doc.get_tokens()[4],
            pattern=pattern,
            direction="left",
        ) == dd.Annotation(text="Andries Meijer", start_char=12, end_char=26, tag="_")

        assert (
            tpa._match_sequence(
                pattern_doc.text,
                start_token=pattern_doc.get_tokens()[8],
                direction="left",
                pattern=pattern,
            )
            is None
        )

    def test_match_sequence_skip(self, pattern_doc, ds):
        pattern = [{"lookup": "surnames"}, {"like_name": True}]

        tpa = TokenPatternAnnotator(pattern=[{}], ds=ds, tag="_")

        assert tpa._match_sequence(
            pattern_doc.text,
            start_token=pattern_doc.get_tokens()[4],
            pattern=pattern,
            skip={"-"},
        ) == dd.Annotation(text="Meijer-Heerma", start_char=20, end_char=33, tag="_")
        assert (
            tpa._match_sequence(
                pattern_doc.text,
                start_token=pattern_doc.get_tokens()[4],
                pattern=pattern,
                skip=set(),
            )
            is None
        )

    def test_annotate(self, pattern_doc, ds):
        pattern = [{"lookup": "first_names"}, {"like_name": True}]

        tpa = TokenPatternAnnotator(pattern=pattern, ds=ds, tag="_")

        assert tpa.annotate(pattern_doc) == [
            dd.Annotation(text="Andries Meijer", start_char=12, end_char=26, tag="_")
        ]


class TestContextAnnotator:
    def test_apply_context_pattern(self, pattern_doc):
        annotator = ContextAnnotator(pattern=[])

        annotations = dd.AnnotationSet(
            [
                dd.Annotation(
                    text="Andries",
                    start_char=12,
                    end_char=19,
                    tag="voornaam",
                    start_token=pattern_doc.get_tokens()[3],
                    end_token=pattern_doc.get_tokens()[3],
                )
            ]
        )

        assert annotator._apply_context_pattern(
            pattern_doc.text,
            annotations,
            {
                "pattern": [{"like_name": True}],
                "direction": "right",
                "pre_tag": "voornaam",
                "tag": "{tag}+naam",
            },
        ) == dd.AnnotationSet(
            [
                dd.Annotation(
                    text="Andries Meijer",
                    start_char=12,
                    end_char=26,
                    tag="voornaam+naam",
                )
            ]
        )

    def test_apply_context_pattern_left(self, pattern_doc):
        annotator = ContextAnnotator(pattern=[])

        annotations = dd.AnnotationSet(
            [
                dd.Annotation(
                    text="Meijer",
                    start_char=20,
                    end_char=26,
                    tag="achternaam",
                    start_token=pattern_doc.get_tokens()[4],
                    end_token=pattern_doc.get_tokens()[4],
                )
            ]
        )

        assert annotator._apply_context_pattern(
            pattern_doc.text,
            annotations,
            {
                "pattern": [{"like_name": True}],
                "direction": "left",
                "pre_tag": "achternaam",
                "tag": "naam+{tag}",
            },
        ) == dd.AnnotationSet(
            [
                dd.Annotation(
                    text="Andries Meijer",
                    start_char=12,
                    end_char=26,
                    tag="naam+achternaam",
                )
            ]
        )

    def test_apply_context_pattern_skip(self, pattern_doc):
        annotator = ContextAnnotator(pattern=[])

        annotations = dd.AnnotationSet(
            [
                dd.Annotation(
                    text="Meijer",
                    start_char=20,
                    end_char=26,
                    tag="achternaam",
                    start_token=pattern_doc.get_tokens()[4],
                    end_token=pattern_doc.get_tokens()[4],
                )
            ]
        )

        assert annotator._apply_context_pattern(
            pattern_doc.text,
            annotations,
            {
                "pattern": [{"like_name": True}],
                "direction": "right",
                "skip": ["-"],
                "pre_tag": "achternaam",
                "tag": "{tag}+naam",
            },
        ) == dd.AnnotationSet(
            [
                dd.Annotation(
                    text="Meijer-Heerma",
                    start_char=20,
                    end_char=33,
                    tag="achternaam+naam",
                )
            ]
        )

    def test_annotate_multiple(self, pattern_doc):
        pattern = [
            {
                "pattern": [{"like_name": True}],
                "direction": "right",
                "pre_tag": "voornaam",
                "tag": "{tag}+naam",
            },
            {
                "pattern": [{"like_name": True}],
                "direction": "right",
                "skip": ["-"],
                "pre_tag": "achternaam",
                "tag": "{tag}+naam",
            },
        ]

        annotator = ContextAnnotator(pattern=pattern, iterative=False)

        annotations = dd.AnnotationSet(
            [
                dd.Annotation(
                    text="Andries",
                    start_char=12,
                    end_char=19,
                    tag="voornaam",
                    start_token=pattern_doc.get_tokens()[3],
                    end_token=pattern_doc.get_tokens()[3],
                )
            ]
        )

        assert annotator._annotate(pattern_doc.text, annotations) == dd.AnnotationSet(
            {
                dd.Annotation(
                    text="Andries Meijer-Heerma",
                    start_char=12,
                    end_char=33,
                    tag="voornaam+naam+naam",
                )
            }
        )

    def test_annotate_iterative(self, pattern_doc):
        pattern = [
            {
                "pattern": [{"like_name": True}],
                "direction": "right",
                "skip": ["-"],
                "pre_tag": ["naam", "voornaam"],
                "tag": "{tag}+naam",
            }
        ]

        annotator = ContextAnnotator(pattern=pattern, iterative=True)

        annotations = dd.AnnotationSet(
            [
                dd.Annotation(
                    text="Andries",
                    start_char=12,
                    end_char=19,
                    tag="voornaam",
                    start_token=pattern_doc.get_tokens()[3],
                    end_token=pattern_doc.get_tokens()[3],
                )
            ]
        )

        assert annotator._annotate(pattern_doc.text, annotations) == dd.AnnotationSet(
            {
                dd.Annotation(
                    text="Andries Meijer-Heerma",
                    start_char=12,
                    end_char=33,
                    tag="voornaam+naam+naam",
                )
            }
        )


class TestPatientNameAnnotator:
    def test_match_first_name_multiple(self, tokenizer):
        person = Person(first_names=["Jan", "Adriaan"])
        tokens = linked_tokens(["Jan", "Adriaan"])
        ann = PatientNameAnnotator(tokenizer=tokenizer, tag="_")

        assert ann._match_first_names(person=person, token=tokens[0]) == (
            tokens[0],
            tokens[0],
        )

        assert ann._match_first_names(person=person, token=tokens[1]) == (
            tokens[1],
            tokens[1],
        )

    def test_match_first_name_fuzzy(self, tokenizer):
        person = Person(first_names=["Adriaan"])
        tokens = linked_tokens(["Adriana"])

        ann = PatientNameAnnotator(tokenizer=tokenizer, tag="_")

        assert ann._match_first_names(person=person, token=tokens[0]) == (
            tokens[0],
            tokens[0],
        )

    def test_match_first_name_fuzzy_short(self, tokenizer):
        person = Person(first_names=["Jan"])
        tokens = linked_tokens(["Dan"])

        ann = PatientNameAnnotator(tokenizer=tokenizer, tag="_")

        assert ann._match_first_names(person=person, token=tokens[0]) is None

    def test_match_initial_from_name(self, tokenizer):
        person = Person(first_names=["Jan", "Adriaan"])
        tokens = linked_tokens(["A", "J"])

        ann = PatientNameAnnotator(tokenizer=tokenizer, tag="_")

        assert ann._match_initial_from_name(person=person, token=tokens[0]) == (
            tokens[0],
            tokens[0],
        )

        assert ann._match_initial_from_name(person=person, token=tokens[1]) == (
            tokens[1],
            tokens[1],
        )

    def test_match_initial_from_name_with_period(self, tokenizer):
        person = Person(first_names=["Jan", "Adriaan"])
        tokens = linked_tokens(["J", ".", "A", "."])

        ann = PatientNameAnnotator(tokenizer=tokenizer, tag="_")

        assert ann._match_initial_from_name(person=person, token=tokens[0]) == (
            tokens[0],
            tokens[1],
        )

        assert ann._match_initial_from_name(person=person, token=tokens[2]) == (
            tokens[2],
            tokens[3],
        )

    def test_match_initial_from_name_no_match(self, tokenizer):
        person = Person(first_names=["Jan", "Adriaan"])
        tokens = linked_tokens(["F", "T"])

        ann = PatientNameAnnotator(tokenizer=tokenizer, tag="_")

        assert ann._match_initial_from_name(person=person, token=tokens[0]) is None
        assert ann._match_initial_from_name(person=person, token=tokens[1]) is None

    def test_match_initials(self, tokenizer):
        person = Person(initials="AFTH")
        tokens = linked_tokens(["AFTH", "THFA"])

        ann = PatientNameAnnotator(tokenizer=tokenizer, tag="_")

        assert ann._match_initials(person=person, token=tokens[0]) == (
            tokens[0],
            tokens[0],
        )
        assert ann._match_initials(person=person, token=tokens[1]) is None

    def test_match_surname_equal(self, tokenizer, surname_pattern):
        tokens = linked_tokens(["Van der", "Heide", "-", "Ginkel", "is", "de", "naam"])

        ann = PatientNameAnnotator(tokenizer=tokenizer, tag="_")

        assert ann._match_surname(surname_pattern=surname_pattern, token=tokens[0]) == (
            tokens[0],
            tokens[3],
        )

    def test_match_surname_longer_than_tokens(self, tokenizer, surname_pattern):
        tokens = linked_tokens(["Van der", "Heide"])

        ann = PatientNameAnnotator(tokenizer=tokenizer, tag="_")

        assert ann._match_surname(surname_pattern=surname_pattern, token=tokens[0]) is None

    def test_match_surname_fuzzy(self, tokenizer, surname_pattern):
        tokens = linked_tokens(["Van der", "Heijde", "-", "Ginkle", "is", "de", "naam"])

        ann = PatientNameAnnotator(tokenizer=tokenizer, tag="_")

        assert ann._match_surname(surname_pattern=surname_pattern, token=tokens[0]) == (
            tokens[0],
            tokens[3],
        )

    def test_match_surname_unequal_first(self, tokenizer, surname_pattern):
        tokens = linked_tokens(["v/der", "Heide", "-", "Ginkel", "is", "de", "naam"])

        ann = PatientNameAnnotator(tokenizer=tokenizer, tag="_")

        assert ann._match_surname(surname_pattern=surname_pattern, token=tokens[0]) is None

    def test_match_surname_unequal_first_fuzzy(self, tokenizer, surname_pattern):
        tokens = linked_tokens(["Van den", "Heide", "-", "Ginkel", "is", "de", "naam"])

        ann = PatientNameAnnotator(tokenizer=tokenizer, tag="_")

        assert ann._match_surname(surname_pattern=surname_pattern, token=tokens[0]) == (
            tokens[0],
            tokens[3],
        )

    def test_annotate_first_name(self, tokenizer):
        metadata = {
            "patient": Person(
                first_names=["Jan", "Johan"], initials="JJ", surname="Jansen"
            )
        }
        text = "De patient heet Jan"
        tokens = tokenizer.tokenize(text)

        ann = PatientNameAnnotator(tokenizer=tokenizer, tag="_")
        doc = dd.Document(text=text, metadata=metadata)

        with patch.object(doc, "get_tokens", return_value=tokens):
            with patch.object(
                tokenizer, "tokenize", return_value=linked_tokens(["Jansen"])
            ):
                annotations = ann.annotate(doc)

        assert annotations == [
            dd.Annotation(
                text="Jan",
                start_char=16,
                end_char=19,
                tag="voornaam_patient",
            )
        ]

    def test_annotate_initials_from_name(self, tokenizer):
        metadata = {
            "patient": Person(
                first_names=["Jan", "Johan"], initials="JJ", surname="Jansen"
            )
        }
        text = "De patient heet JJ"
        tokens = tokenizer.tokenize(text)

        ann = PatientNameAnnotator(tokenizer=tokenizer, tag="_")
        doc = dd.Document(text=text, metadata=metadata)

        with patch.object(doc, "get_tokens", return_value=tokens):
            with patch.object(
                tokenizer, "tokenize", return_value=linked_tokens(["Jansen"])
            ):
                annotations = ann.annotate(doc)

        assert annotations == [
            dd.Annotation(
                text="JJ",
                start_char=16,
                end_char=18,
                tag="initiaal_patient",
            )
        ]

    def test_annotate_initial(self, tokenizer):
        metadata = {
            "patient": Person(
                first_names=["Jan", "Johan"], initials="JJ", surname="Jansen"
            )
        }
        text = "De patient heet J."
        tokens = tokenizer.tokenize(text)

        ann = PatientNameAnnotator(tokenizer=tokenizer, tag="_")
        doc = dd.Document(text=text, metadata=metadata)

        with patch.object(doc, "get_tokens", return_value=tokens):
            with patch.object(
                tokenizer, "tokenize", return_value=linked_tokens(["Jansen"])
            ):
                annotations = ann.annotate(doc)

        assert annotations == [
            dd.Annotation(
                text="J.",
                start_char=16,
                end_char=18,
                tag="initiaal_patient",
            )
        ]

    def test_annotate_surname(self, tokenizer):
        metadata = {
            "patient": Person(
                first_names=["Jan", "Johan"], initials="JJ", surname="Jansen"
            )
        }
        text = "De patient heet Jansen"
        tokens = tokenizer.tokenize(text)

        ann = PatientNameAnnotator(tokenizer=tokenizer, tag="_")
        doc = dd.Document(text=text, metadata=metadata)

        with patch.object(doc, "get_tokens", return_value=tokens):
            with patch.object(
                tokenizer, "tokenize", return_value=linked_tokens(["Jansen"])
            ):
                annotations = ann.annotate(doc)

        assert annotations == [
            dd.Annotation(
                text="Jansen",
                start_char=16,
                end_char=22,
                tag="achternaam_patient",
            )
        ]

    def test_annotate_person_metadata(self, tokenizer):
        metadata = {"persons": [Person(first_names=["Peter"], surname="de Visser")]}
        text = "De arts heet Peter de Visser"
        tokens = tokenizer.tokenize(text)

        ann = PatientNameAnnotator(tokenizer=tokenizer, tag="_")
        doc = dd.Document(text=text, metadata=metadata)

        with patch.object(doc, "get_tokens", return_value=tokens):
            annotations = ann.annotate(doc)

        assert annotations == [
            dd.Annotation(
                text="Peter",
                start_char=13,
                end_char=18,
                tag="voornaam_persoon",
            ),
            dd.Annotation(
                text="de Visser",
                start_char=19,
                end_char=28,
                tag="achternaam_persoon",
            ),
        ]


class TestMetadataEntityAnnotator:
    def test_annotate_alias_birth_date_and_address(self, tokenizer):
        metadata = {
            "patient": Person(
                aliases=["Jan Jansen-de Smet"],
                birth_date=date(1980, 3, 12),
                addresses=[
                    Address(
                        street="Kerkstraat",
                        house_number="12A",
                        postal_code="9000",
                        city="Gent",
                    )
                ],
            ),
            "entities": [MetadataEntity(text="UZ Gent", tag="ziekenhuis")],
        }
        text = (
            "Jan Jansen-de Smet is geboren op 12 maart 1980 en woont op "
            "Kerkstraat 12A, 9000 Gent. Controle in UZ Gent."
        )
        tokens = tokenizer.tokenize(text)

        ann = MetadataEntityAnnotator(tokenizer=tokenizer, tag="_", priority=2)
        doc = dd.Document(text=text, metadata=metadata)

        with patch.object(doc, "get_tokens", return_value=tokens):
            annotations = ann.annotate(doc)

        assert dd.Annotation(
            text="Jan Jansen-de Smet",
            start_char=0,
            end_char=18,
            tag="patient",
            priority=2,
        ) in annotations
        assert dd.Annotation(
            text="12 maart 1980",
            start_char=33,
            end_char=46,
            tag="datum",
            priority=2,
        ) in annotations
        assert dd.Annotation(
            text="Kerkstraat 12A, 9000 Gent",
            start_char=59,
            end_char=84,
            tag="locatie",
            priority=2,
        ) in annotations
        assert dd.Annotation(
            text="UZ Gent",
            start_char=98,
            end_char=105,
            tag="ziekenhuis",
            priority=2,
        ) in annotations


class TestRegexpPseudoAnnotator:
    def test_is_word_char(self):
        assert RegexpPseudoAnnotator._is_word_char("a")
        assert RegexpPseudoAnnotator._is_word_char("abc")
        assert not RegexpPseudoAnnotator._is_word_char("123")
        assert not RegexpPseudoAnnotator._is_word_char(" ")
        assert not RegexpPseudoAnnotator._is_word_char("\n")
        assert not RegexpPseudoAnnotator._is_word_char(".")

    def test_get_previous_word(self):
        r = RegexpPseudoAnnotator(regexp_pattern="_", tag="_")

        assert r._get_previous_word(0, "12 jaar") == ""
        assert r._get_previous_word(1, "<12 jaar") == ""
        assert r._get_previous_word(8, "patient 12 jaar") == "patient"
        assert r._get_previous_word(7, "(sinds 12 jaar)") == "sinds"
        assert r._get_previous_word(11, "patient is 12 jaar)") == "is"

    def test_get_next(self):
        r = RegexpPseudoAnnotator(regexp_pattern="_", tag="_")

        assert r._get_next_word(7, "12 jaar") == ""
        assert r._get_next_word(7, "12 jaar, geleden") == ""
        assert r._get_next_word(7, "12 jaar geleden") == "geleden"
        assert r._get_next_word(7, "12 jaar geleden geopereerd") == "geleden"

    def test_validate_match(self, regexp_pseudo_doc):
        r = RegexpPseudoAnnotator(regexp_pattern="_", tag="_")
        pattern = re.compile(r"\d+ jaar")

        match = list(pattern.finditer(regexp_pseudo_doc.text))[0]

        assert r._validate_match(match, regexp_pseudo_doc)

    def test_validate_match_pre(self, regexp_pseudo_doc):
        r = RegexpPseudoAnnotator(
            regexp_pattern="_", tag="_", pre_pseudo=["sinds", "al", "vanaf"]
        )
        pattern = re.compile(r"\d+ jaar")

        match = list(pattern.finditer(regexp_pseudo_doc.text))[0]

        assert r._validate_match(match, regexp_pseudo_doc)

    def test_validate_match_post(self, regexp_pseudo_doc):
        r = RegexpPseudoAnnotator(
            regexp_pattern="_", tag="_", post_pseudo=["geleden", "getrouwd", "gestopt"]
        )
        pattern = re.compile(r"\d+ jaar")

        match = list(pattern.finditer(regexp_pseudo_doc.text))[0]

        assert not r._validate_match(match, regexp_pseudo_doc)

    def test_validate_match_lower(self, regexp_pseudo_doc):
        r = RegexpPseudoAnnotator(
            regexp_pattern="_", tag="_", pre_pseudo=["na"], lowercase=True
        )
        pattern = re.compile(r"\d+ jaar")

        match = list(pattern.finditer(regexp_pseudo_doc.text))[0]

        assert not r._validate_match(match, regexp_pseudo_doc)


class TestBsnAnnotator:
    def test_elfproef(self):
        an = BsnAnnotator(bsn_regexp="(\\D|^)(\\d{9})(\\D|$)", capture_group=2, tag="_")

        assert an._elfproef("111222333")
        assert not an._elfproef("111222334")
        assert an._elfproef("123456782")
        assert not an._elfproef("123456783")

    def test_elfproef_wrong_length(self):
        an = BsnAnnotator(bsn_regexp="(\\D|^)(\\d{9})(\\D|$)", capture_group=2, tag="_")

        with pytest.raises(ValueError):
            an._elfproef("12345678")

    def test_elfproef_non_numeric(self):
        an = BsnAnnotator(bsn_regexp="(\\D|^)(\\d{9})(\\D|$)", capture_group=2, tag="_")

        with pytest.raises(ValueError):
            an._elfproef("test")

    def test_annotate(self, bsn_doc):
        an = BsnAnnotator(bsn_regexp="(\\D|^)(\\d{9})(\\D|$)", capture_group=2, tag="_")
        annotations = an.annotate(bsn_doc)

        expected_annotations = [
            dd.Annotation(text="111222333", start_char=26, end_char=35, tag="_"),
            dd.Annotation(text="123456782", start_char=39, end_char=48, tag="_"),
        ]

        assert annotations == expected_annotations

    def test_annotate_with_nondigits(self, bsn_doc):
        an = BsnAnnotator(bsn_regexp=r"\d{4}\.\d{2}\.\d{3}", tag="_")
        doc = dd.Document("1234.56.782")
        annotations = an.annotate(doc)

        expected_annotations = [
            dd.Annotation(text="1234.56.782", start_char=0, end_char=11, tag="_"),
        ]

        assert annotations == expected_annotations


class TestNationalRegisterNumberAnnotator:
    def test_is_valid(self):
        assert NationalRegisterNumberAnnotator._is_valid("85073003328")
        assert NationalRegisterNumberAnnotator._is_valid("00010100105")
        assert not NationalRegisterNumberAnnotator._is_valid("85073003329")
        assert not NationalRegisterNumberAnnotator._is_valid("00130100105")

    def test_annotate(self, national_register_doc):
        an = NationalRegisterNumberAnnotator(
            national_number_regexp=r"(?<!\d)((?:\d{2}[\s./-]?){3}\d{3}[\s./-]?\d{2})(?!\d)",
            capture_group=1,
            tag="_",
        )
        annotations = an.annotate(national_register_doc)

        expected_annotations = [
            dd.Annotation(text="85.07.30-033.28", start_char=0, end_char=15, tag="_"),
            dd.Annotation(text="00.01.01-001.05", start_char=16, end_char=31, tag="_"),
        ]

        assert annotations == expected_annotations

    def test_annotate_without_separators(self):
        an = NationalRegisterNumberAnnotator(
            national_number_regexp=r"(?<!\d)(\d{11})(?!\d)",
            capture_group=1,
            tag="_",
        )
        doc = dd.Document("85073003328 85073003329")
        annotations = an.annotate(doc)

        expected_annotations = [
            dd.Annotation(text="85073003328", start_char=0, end_char=11, tag="_"),
        ]

        assert annotations == expected_annotations


class TestPhoneNumberAnnotator:
    def test_annotate_defaults(self, phone_number_doc):
        an = PhoneNumberAnnotator(phone_regexp=BELGIAN_PHONE_REGEXP, tag="_")
        annotations = an.annotate(phone_number_doc)
        text = phone_number_doc.text

        expected_annotations = [
            dd.Annotation(
                text="016 55 55 55",
                start_char=text.index("016 55 55 55"),
                end_char=text.index("016 55 55 55") + len("016 55 55 55"),
                tag="_",
            ),
            dd.Annotation(
                text="0470 12 34 56",
                start_char=text.index("0470 12 34 56"),
                end_char=text.index("0470 12 34 56") + len("0470 12 34 56"),
                tag="_",
            ),
            dd.Annotation(
                text="+32470123456",
                start_char=text.index("+32470123456"),
                end_char=text.index("+32470123456") + len("+32470123456"),
                tag="_",
            ),
            dd.Annotation(
                text="0800 12 345",
                start_char=text.index("0800 12 345"),
                end_char=text.index("0800 12 345") + len("0800 12 345"),
                tag="_",
            ),
        ]

        assert annotations == expected_annotations

    def test_annotate_short(self, phone_number_doc):
        an = PhoneNumberAnnotator(
            phone_regexp=BELGIAN_PHONE_REGEXP,
            min_digits=8,
            max_digits=8,
            tag="_",
        )
        annotations = an.annotate(phone_number_doc)
        text = phone_number_doc.text

        expected_annotations = [
            dd.Annotation(
                text="04701234",
                start_char=text.index("04701234"),
                end_char=text.index("04701234") + len("04701234"),
                tag="_",
            )
        ]

        assert annotations == expected_annotations

    def test_annotate_long(self, phone_number_doc):
        an = PhoneNumberAnnotator(
            phone_regexp=BELGIAN_PHONE_REGEXP,
            min_digits=11,
            max_digits=12,
            tag="_",
        )
        annotations = an.annotate(phone_number_doc)
        text = phone_number_doc.text

        expected_annotations = [
            dd.Annotation(
                text="047012345678",
                start_char=text.index("047012345678"),
                end_char=text.index("047012345678") + len("047012345678"),
                tag="_",
            )
        ]

        assert annotations == expected_annotations
