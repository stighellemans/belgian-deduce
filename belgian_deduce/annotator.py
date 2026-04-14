"""Contains components for annotating."""

import re
import warnings
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal, Optional

import docdeid as dd
from docdeid import Annotation, Document, Tokenizer
from docdeid.process import RegexpAnnotator

from belgian_deduce.metadata import Address, MetadataEntity, Person
from belgian_deduce.utils import str_match

warnings.simplefilter(action="default")

_DIRECTION_MAP = {
    "left": {
        "attr": "previous",
        "order": reversed,
        "start_token": lambda annotation: annotation.start_token,
    },
    "right": {
        "attr": "next",
        "order": lambda pattern: pattern,
        "start_token": lambda annotation: annotation.end_token,
    },
}

_PERSON_METADATA_KEYS = (
    ("patient", "patient"),
    ("patients", "patient"),
    ("persons", "person"),
    ("people", "person"),
)


def _normalize_metadata_items(value, expected_type: type, key: str) -> list:
    if value is None:
        return []

    if isinstance(value, expected_type):
        return [value]

    if isinstance(value, (list, tuple, set)):
        items = list(value)

        if not all(isinstance(item, expected_type) for item in items):
            raise TypeError(
                f"Metadata key '{key}' must only contain "
                f"{expected_type.__name__} values."
            )

        return items

    raise TypeError(
        f"Metadata key '{key}' must be a {expected_type.__name__} "
        f"or a list of them."
    )


def _iter_people(doc: dd.Document) -> list[tuple[Person, str]]:
    people = []

    for key, tag in _PERSON_METADATA_KEYS:
        people.extend(
            (person, tag)
            for person in _normalize_metadata_items(doc.metadata[key], Person, key)
        )

    return people


def _iter_addresses(doc: dd.Document) -> list[Address]:
    return _normalize_metadata_items(doc.metadata["addresses"], Address, "addresses")


def _iter_metadata_entities(doc: dd.Document) -> list[MetadataEntity]:
    entities = _normalize_metadata_items(
        doc.metadata["entities"], MetadataEntity, "entities"
    )

    for person, tag in _iter_people(doc):
        entities.extend(person.as_entities(tag=tag))

    for address in _iter_addresses(doc):
        entities.extend(address.as_entities())

    return entities


@dataclass(frozen=True)
class _PreparedPerson:
    person: Person
    tag: str
    surname_pattern: Optional[list[dd.Token]] = None


@dataclass(frozen=True)
class _ExactPattern:
    tag: str
    tokens: tuple[str, ...]
    priority: int


class _PatternPositionMatcher:  # pylint: disable=R0903
    """Checks if a token matches against a single pattern."""

    @classmethod
    def match(cls, pattern_position: dict, **kwargs) -> bool:  # pylint: disable=R0911
        """
        Matches a pattern position (a dict with one key). Other information should be
        presented as kwargs.

        Args:
            pattern_position: A dictionary with a single key, e.g. {'is_initial': True}
            kwargs: Any other information, like the token or ds

        Returns:
            True if the pattern position matches, false otherwise.
        """

        if len(pattern_position) > 1:
            raise ValueError(
                f"Cannot parse token pattern ({pattern_position}) with more than 1 key"
            )

        func, value = next(iter(pattern_position.items()))

        if func == "equal":
            return kwargs.get("token").text == value
        if func == "re_match":
            return re.match(value, kwargs.get("token").text) is not None
        if func == "is_initials":
            return (
                len(kwargs.get("token").text) <= 4
                and kwargs.get("token").text.isupper()
            ) == value
        if func == "like_name":
            return (
                len(kwargs.get("token").text) >= 3
                and kwargs.get("token").text.istitle()
                and not any(ch.isdigit() for ch in kwargs.get("token").text)
            ) == value
        if func == "lookup":
            return kwargs.get("token").text in kwargs.get("ds")[value]
        if func == "neg_lookup":
            return kwargs.get("token").text not in kwargs.get("ds")[value]
        if func == "and":
            return all(
                _PatternPositionMatcher.match(pattern_position=x, **kwargs)
                for x in value
            )
        if func == "or":
            return any(
                _PatternPositionMatcher.match(pattern_position=x, **kwargs)
                for x in value
            )

        raise NotImplementedError(f"No known logic for pattern {func}")


class TokenPatternAnnotator(dd.process.Annotator):
    """
    Annotates based on token patterns, which should be provided as a list of dicts. Each
    position in the list denotes a token position, e.g.: [{'is_initial': True},
    {'like_name': True}] matches sequences of two tokens, where the first one is an
    initial, and the second one is like a name.

    Arguments:
        pattern: The pattern
        ds: Any datastructures, that can be used for lookup or other logic
        skip: Any string values that should be skipped in matching (e.g. periods)
    """

    def __init__(
        self,
        pattern: list[dict],
        *args,
        ds: Optional[dd.ds.DsCollection] = None,
        skip: Optional[list[str]] = None,
        **kwargs,
    ) -> None:
        self.pattern = pattern
        self.ds = ds
        self.skip = set(skip or [])

        self._start_words = None
        self._matching_pipeline = None

        if len(self.pattern) > 0 and "lookup" in self.pattern[0]:
            if self.ds is None:
                raise RuntimeError(
                    "Created pattern with lookup in TokenPatternAnnotator, but "
                    "no lookup structures provided."
                )

            lookup_list = self.ds[self.pattern[0]["lookup"]]

            if not isinstance(lookup_list, dd.ds.LookupSet):
                raise ValueError(
                    f"Expected a LookupSet, but got a " f"{type(lookup_list)}."
                )

            self._start_words = lookup_list.items()
            self._matching_pipeline = lookup_list.matching_pipeline

        super().__init__(*args, **kwargs)

    @staticmethod
    def _get_chained_token(
        token: dd.Token, attr: str, skip: set[str]
    ) -> Optional[dd.Token]:
        while True:
            token = getattr(token, attr)()

            if token is None or token.text not in skip:
                break

        return token

    def _match_sequence(  # pylint: disable=R0913, R0917
        self,
        text: str,
        pattern: list[dict],
        start_token: dd.tokenizer.Token,
        direction: Literal["left", "right"] = "right",
        skip: Optional[set[str]] = None,
    ) -> Optional[dd.Annotation]:
        """
        Sequentially match a pattern against a specified start_token.

        Args:
            text: The original document text.
            pattern: The pattern to match.
            start_token: The start token to match.
            direction: The direction to match, choice of "left" or "right".
            skip: Any string values that should be skipped in matching.

        Returns:
              An Annotation if matching is possible, None otherwise.
        """

        skip = skip or set()

        attr = _DIRECTION_MAP[direction]["attr"]
        pattern = _DIRECTION_MAP[direction]["order"](pattern)

        current_token = start_token
        end_token = start_token

        for pattern_position in pattern:
            if current_token is None or not _PatternPositionMatcher.match(
                pattern_position=pattern_position, token=current_token, ds=self.ds
            ):
                return None

            end_token = current_token
            current_token = self._get_chained_token(current_token, attr, skip)

        start_token, end_token = _DIRECTION_MAP[direction]["order"](
            (start_token, end_token)
        )

        return dd.Annotation(
            text=text[start_token.start_char : end_token.end_char],
            start_char=start_token.start_char,
            end_char=end_token.end_char,
            tag=self.tag,
            priority=self.priority,
            start_token=start_token,
            end_token=end_token,
        )

    def annotate(self, doc: dd.Document) -> list[dd.Annotation]:
        """
        Annotate the document, by matching the pattern against all tokens.

        Args:
            doc: The document being processed.

        Returns:
            A list of Annotation.
        """

        annotations = []

        tokens = doc.get_tokens()

        if self._start_words is not None:
            tokens = tokens.token_lookup(
                lookup_values=self._start_words,
                matching_pipeline=self._matching_pipeline,
            )

        for token in tokens:
            annotation = self._match_sequence(
                doc.text, self.pattern, token, direction="right", skip=self.skip
            )

            if annotation is not None:
                annotations.append(annotation)

        return annotations


class ContextAnnotator(TokenPatternAnnotator):
    """
    Extends existing annotations to the left or right, based on specified patterns.

    Args:
        ds: Any datastructures, that can be used for lookup or other logic
        iterative: Whether the extension process should repeat, or stop after one
        iteration.
    """

    def __init__(
        self,
        *args,
        ds: Optional[dd.ds.DsCollection] = None,
        iterative: bool = True,
        **kwargs,
    ) -> None:
        self.iterative = iterative
        super().__init__(*args, **kwargs, ds=ds, tag="_")

    def _apply_context_pattern(
        self, text: str, annotations: dd.AnnotationSet, context_pattern: dict
    ) -> dd.AnnotationSet:
        direction = context_pattern["direction"]
        skip = set(context_pattern.get("skip", []))

        for annotation in annotations.copy():
            tag = list(_DIRECTION_MAP[direction]["order"](annotation.tag.split("+")))[
                -1
            ]

            if tag not in context_pattern["pre_tag"]:
                continue

            attr = _DIRECTION_MAP[direction]["attr"]
            start_token = self._get_chained_token(
                _DIRECTION_MAP[direction]["start_token"](annotation), attr, skip
            )
            new_annotation = self._match_sequence(
                text,
                context_pattern["pattern"],
                start_token,
                direction=direction,
                skip=skip,
            )

            if new_annotation:
                left_ann, right_ann = _DIRECTION_MAP[direction]["order"](
                    (annotation, new_annotation)
                )

                merged_annotation = dd.Annotation(
                    text=text[left_ann.start_char : right_ann.end_char],
                    start_char=left_ann.start_char,
                    end_char=right_ann.end_char,
                    start_token=left_ann.start_token,
                    end_token=right_ann.end_token,
                    tag=context_pattern["tag"].format(tag=annotation.tag),
                    priority=annotation.priority,
                )

                annotations.remove(annotation)
                annotations.add(merged_annotation)

        return annotations

    def _annotate(self, text: str, annotations: dd.AnnotationSet) -> dd.AnnotationSet:
        """
        Does the annotation, by calling _apply_context_pattern, and then optionally
        recursing. Also keeps track of the (un)changed annotations, so they are not
        repeatedly processed.

        Args:
            text: The input text.
            annotations: The input annotations.

        Returns:
            An extended set of annotations, based on the patterns provided.
        """

        original_annotations = annotations.copy()

        for context_pattern in self.pattern:
            annotations = self._apply_context_pattern(
                text, annotations, context_pattern
            )

        if self.iterative:
            changed = dd.AnnotationSet(annotations.difference(original_annotations))
            annotations = dd.AnnotationSet(
                annotations.intersection(original_annotations)
            )

            if changed:
                annotations.update(self._annotate(text, changed))

        return annotations

    def annotate(self, doc: dd.Document) -> list[dd.Annotation]:
        """
        Wrapper for annotating.

        Args:
            doc: The document to process.

        Returns:
            An empty list, as annotations are modified and not added.
        """

        doc.annotations = self._annotate(doc.text, doc.annotations)
        return []


class PatientNameAnnotator(dd.process.Annotator):
    """
    Annotates names from metadata. ``patient`` / ``patients`` are treated as patient
    names, while ``persons`` / ``people`` are treated as regular person names. This
    class implements logic for detecting first name(s), initials and surnames.

    Args:
        tokenizer: A tokenizer, that is used for breaking up the patient surname
            into multiple tokens.
    """

    def __init__(self, tokenizer: Tokenizer, *args, **kwargs) -> None:
        self.tokenizer = tokenizer
        self.skip = [".", "-", " "]

        super().__init__(*args, **kwargs)

    @staticmethod
    def _match_first_names(
        person: Person, token: dd.Token
    ) -> Optional[tuple[dd.Token, dd.Token]]:
        for first_name in person.first_names or []:
            if str_match(token.text, first_name) or (
                len(token.text) > 3
                and str_match(token.text, first_name, max_edit_distance=1)
            ):
                return token, token

        return None

    @staticmethod
    def _match_initial_from_name(
        person: Person, token: dd.Token
    ) -> Optional[tuple[dd.Token, dd.Token]]:
        for _, first_name in enumerate(person.first_names or []):
            if str_match(token.text, first_name[0]):
                next_token = token.next()

                if (next_token is not None) and str_match(next_token.text, "."):
                    return token, next_token

                return token, token

        return None

    @staticmethod
    def _match_initials(
        person: Person, token: dd.Token
    ) -> Optional[tuple[dd.Token, dd.Token]]:
        if str_match(token.text, person.initials):
            return token, token

        return None

    def next_with_skip(self, token: dd.Token) -> Optional[dd.Token]:
        """Find the next token, while skipping certain punctuation."""

        while True:
            token = token.next()

            if (token is None) or (token not in self.skip):
                break

        return token

    def _match_surname(
        self, surname_pattern: list[dd.Token], token: dd.Token
    ) -> Optional[tuple[dd.Token, dd.Token]]:
        surname_token = surname_pattern[0]
        start_token = token

        while True:
            if not str_match(surname_token.text, token.text, max_edit_distance=1):
                return None

            match_end_token = token

            surname_token = self.next_with_skip(surname_token)
            token = self.next_with_skip(token)

            if surname_token is None:
                return start_token, match_end_token  # end of pattern

            if token is None:
                return None  # end of tokens

    def _prepare_people(self, doc: dd.Document) -> list[_PreparedPerson]:
        prepared_people = []

        for person, tag in _iter_people(doc):
            surname_pattern = None

            if person.surname:
                surname_pattern = self.tokenizer.tokenize(person.surname)

            prepared_people.append(
                _PreparedPerson(person=person, tag=tag, surname_pattern=surname_pattern)
            )

        return prepared_people

    def annotate(self, doc: Document) -> list[Annotation]:
        """
        Annotates the document, based on the person metadata.

        Args:
            doc: The input document.

        Returns: A document with any relevant Annotations added.
        """

        prepared_people = self._prepare_people(doc)

        if not prepared_people:
            return []

        annotations = []
        matchers_by_person = []

        for prepared_person in prepared_people:
            matchers = []

            if prepared_person.person.first_names is not None:
                matchers.extend(
                    [
                        (
                            self._match_first_names,
                            f"first_name_{prepared_person.tag}",
                            False,
                        ),
                        (
                            self._match_initial_from_name,
                            f"initial_{prepared_person.tag}",
                            False,
                        ),
                    ]
                )

            if prepared_person.person.initials is not None:
                matchers.append(
                    (self._match_initials, f"initial_{prepared_person.tag}", False)
                )

            if prepared_person.surname_pattern is not None:
                matchers.append(
                    (self._match_surname, f"last_name_{prepared_person.tag}", True)
                )

            matchers_by_person.append((prepared_person, matchers))

        for token in doc.get_tokens():
            for prepared_person, matchers in matchers_by_person:
                for matcher, tag, uses_surname in matchers:
                    if uses_surname:
                        match = matcher(prepared_person.surname_pattern, token)
                    else:
                        match = matcher(prepared_person.person, token)

                    if match is None:
                        continue

                    start_token, end_token = match

                    annotations.append(
                        dd.Annotation(
                            text=doc.text[start_token.start_char : end_token.end_char],
                            start_char=start_token.start_char,
                            end_char=end_token.end_char,
                            tag=tag,
                            priority=self.priority,
                            start_token=start_token,
                            end_token=end_token,
                        )
                    )

        return annotations


class MetadataEntityAnnotator(dd.process.Annotator):
    """
    Annotates metadata-driven entities such as aliases, birth dates, addresses and
    arbitrary custom values.
    """

    def __init__(self, tokenizer: Tokenizer, *args, **kwargs) -> None:
        self.tokenizer = tokenizer
        super().__init__(*args, **kwargs)

    @staticmethod
    def _tokens_equal(left: str, right: str) -> bool:
        return left.casefold() == right.casefold()

    def _get_patterns(self, doc: dd.Document) -> list[_ExactPattern]:
        patterns = []
        seen = set()

        for entity in _iter_metadata_entities(doc):
            for text in entity.iter_texts():
                tokens = tuple(token.text for token in self.tokenizer.tokenize(text))

                if not tokens:
                    continue

                key = (entity.tag, tokens)

                if key in seen:
                    continue

                seen.add(key)
                patterns.append(
                    _ExactPattern(tag=entity.tag, tokens=tokens, priority=self.priority)
                )

        return patterns

    def _match_pattern(
        self, text: str, start_token: dd.Token, pattern: _ExactPattern
    ) -> Optional[dd.Annotation]:
        current_token = start_token
        end_token = start_token

        for expected in pattern.tokens:
            if current_token is None or not self._tokens_equal(
                current_token.text, expected
            ):
                return None

            end_token = current_token
            current_token = current_token.next()

        return dd.Annotation(
            text=text[start_token.start_char : end_token.end_char],
            start_char=start_token.start_char,
            end_char=end_token.end_char,
            tag=pattern.tag,
            priority=pattern.priority,
            start_token=start_token,
            end_token=end_token,
        )

    def annotate(self, doc: dd.Document) -> list[dd.Annotation]:
        patterns_by_start = defaultdict(list)

        for pattern in self._get_patterns(doc):
            patterns_by_start[pattern.tokens[0].casefold()].append(pattern)

        if not patterns_by_start:
            return []

        annotations = []

        for token in doc.get_tokens():
            for pattern in patterns_by_start.get(token.text.casefold(), []):
                annotation = self._match_pattern(doc.text, token, pattern)

                if annotation is not None:
                    annotations.append(annotation)

        return annotations


class RegexpPseudoAnnotator(RegexpAnnotator):
    """
    Regexp annotator that filters out matches preceded or followed by certain terms.
    Currently matches on sequential alpha characters preceding or following the match.
    This annotator does not depend on any tokenizer.

    Args:
        pre_pseudo: A list of strings that invalidate a match when preceding it
        post_pseudo: A list of strings that invalidate a match when following it
        lowercase: Whether to match lowercase
    """

    def __init__(
        self,
        *args,
        pre_pseudo: Optional[list[str]] = None,
        post_pseudo: Optional[list[str]] = None,
        lowercase: bool = True,
        **kwargs,
    ) -> None:
        self.pre_pseudo = set(pre_pseudo or [])
        self.post_pseudo = set(post_pseudo or [])
        self.lowercase = lowercase

        super().__init__(*args, **kwargs)

    @staticmethod
    def _is_word_char(char: str) -> bool:
        """
        Determines whether a character can be part of a word.

        Args:
            char: The character

        Returns: True when the character can be part of a word, false otherwise.
        """

        return char.isalpha()

    def _get_previous_word(self, char_index: int, text: str) -> str:
        """
        Get the previous word starting at some character index.

        Args:
            char_index: The character index to start searching.
            text: The text.

        Returns: The previous word, or an empty string if at beginning of text.
        """

        text = text[:char_index].strip()
        result = ""

        for ch in text[::-1]:
            if not self._is_word_char(ch):
                break

            result = ch + result

        return result.strip()

    def _get_next_word(self, char_index: int, text: str) -> str:
        """
        Get the next word starting at some character index.

        Args:
            char_index: The character index to start searching.
            text: The text.

        Returns: The next word, or an empty string if at end of text.
        """

        text = text[char_index:].strip()
        result = ""

        for ch in text:
            if not self._is_word_char(ch):
                break

            result = result + ch

        return result

    def _validate_match(self, match: re.Match, doc: Document) -> bool:
        """
        Validate match, by checking the preceding or following words against the defined
        pseudo sets.

        Args:
            match: The regexp match.
            doc: The doc object.

        Returns: True when the match is valid, False when invalid.
        """

        start_char, end_char = match.span(0)

        previous_word = self._get_previous_word(start_char, doc.text)
        next_word = self._get_next_word(end_char, doc.text)

        if self.lowercase:
            previous_word = previous_word.lower()
            next_word = next_word.lower()

        return (previous_word not in self.pre_pseudo) and (
            next_word not in self.post_pseudo
        )


class BsnAnnotator(dd.process.Annotator):
    """
    Annotates Burgerservicenummer (BSN), according to the elfproef logic.
    See also: https://nl.wikipedia.org/wiki/Burgerservicenummer

    Args:
        bsn_regexp: A regexp to match potential BSN nummers. The simplest form could be
            9-digit numbers, but matches with periods or other punctutation can also be
            accepted. Any non-digit characters are removed from the match before
            the elfproef is applied.
        capture_group: The regexp capture group to consider.
    """

    def __init__(
        self, bsn_regexp: str, *args, capture_group: int = 0, **kwargs
    ) -> None:
        self.bsn_regexp = re.compile(bsn_regexp)
        self.capture_group = capture_group
        super().__init__(*args, **kwargs)

    @staticmethod
    def _elfproef(bsn: str) -> bool:
        if len(bsn) != 9 or (any(not char.isdigit() for char in bsn)):
            raise ValueError(
                "Elfproef for testing BSN can only be applied to strings with 9 digits."
            )

        total = 0

        for char, factor in zip(bsn, [9, 8, 7, 6, 5, 4, 3, 2, -1]):
            total += int(char) * factor

        return total % 11 == 0

    def annotate(self, doc: Document) -> list[Annotation]:
        annotations = []

        for match in self.bsn_regexp.finditer(doc.text):
            text = match.group(self.capture_group)
            digits = re.sub(r"\D", "", text)

            start, end = match.span(self.capture_group)

            if self._elfproef(digits):
                annotations.append(
                    Annotation(
                        text=text,
                        start_char=start,
                        end_char=end,
                        tag=self.tag,
                        priority=self.priority,
                    )
                )

        return annotations


class NationalRegisterNumberAnnotator(dd.process.Annotator):
    """
    Annotates Belgian national register numbers (RRN/NISS).

    Args:
        national_number_regexp: A regexp to match potential national register
            numbers. Optional separators such as spaces, dots, and hyphens may be
            included in the match; they are removed before validation.
        capture_group: The regexp capture group to consider.
    """

    def __init__(
        self,
        national_number_regexp: str,
        *args,
        capture_group: int = 0,
        **kwargs,
    ) -> None:
        self.national_number_regexp = re.compile(national_number_regexp)
        self.capture_group = capture_group
        super().__init__(*args, **kwargs)

    @staticmethod
    def _checksum(base_number: int) -> int:
        checksum = 97 - (base_number % 97)
        return 97 if checksum == 0 else checksum

    @staticmethod
    def _has_valid_date_section(digits: str) -> bool:
        month = int(digits[2:4])
        day = int(digits[4:6])

        if 21 <= month <= 32:
            month -= 20
        elif 41 <= month <= 52:
            month -= 40

        return 1 <= month <= 12 and 1 <= day <= 31

    @classmethod
    def _is_valid(cls, digits: str) -> bool:
        if len(digits) != 11 or any(not char.isdigit() for char in digits):
            return False

        if not cls._has_valid_date_section(digits):
            return False

        base_number = int(digits[:9])
        checksum = int(digits[9:])

        return checksum in {
            cls._checksum(base_number),
            cls._checksum(2_000_000_000 + base_number),
        }

    def annotate(self, doc: Document) -> list[Annotation]:
        annotations = []

        for match in self.national_number_regexp.finditer(doc.text):
            text = match.group(self.capture_group)
            digits = re.sub(r"\D", "", text)

            if not self._is_valid(digits):
                continue

            start, end = match.span(self.capture_group)
            annotations.append(
                Annotation(
                    text=text,
                    start_char=start,
                    end_char=end,
                    tag=self.tag,
                    priority=self.priority,
                )
            )

        return annotations


class PhoneNumberAnnotator(dd.process.Annotator):
    """
    Annotates phone numbers, based on a regexp and min and max number of digits.
    Additionally employs some logic like detecting parentheses and hyphens.

    Args:
        phone_regexp: The regexp to detect phone numbers.
        min_digits: The minimum number of digits that need to be present.
        max_digits: The maximum number of digits that need to be present.
    """

    def __init__(
        self,
        phone_regexp: str,
        *args,
        min_digits: int = 9,
        max_digits: int = 11,
        **kwargs,
    ) -> None:
        self.phone_regexp = re.compile(phone_regexp)
        self.min_digits = min_digits
        self.max_digits = max_digits

        super().__init__(*args, **kwargs)

    def annotate(self, doc: Document) -> list[Annotation]:
        annotations = []

        for match in self.phone_regexp.finditer(doc.text):
            left_index_shift = 0
            match_groups = match.groupdict()

            prefix_with_parens = match_groups.get("prefix")
            if prefix_with_parens is None:
                prefix_with_parens = match.group(1)

            prefix_code = match_groups.get("prefix_code")
            if prefix_code is None:
                prefix_code = match.group(3)

            number_text = match_groups.get("number")
            if number_text is None:
                number_text = match.group(4)

            prefix_digits = "0" + re.sub(r"\D", "", prefix_code)
            number_digits = re.sub(r"\D", "", number_text)

            # Trim parenthesis
            if prefix_with_parens.startswith("(") and not prefix_with_parens.endswith(
                ")"
            ):
                left_index_shift = 1

            total_digits = len(prefix_digits) + len(number_digits)

            if self.min_digits <= total_digits <= self.max_digits:
                text = match.group(0)[left_index_shift:]
                start_char, end_char = match.span(0)
                start_char += left_index_shift

                annotations.append(
                    Annotation(
                        text=text,
                        start_char=start_char,
                        end_char=end_char,
                        tag=self.tag,
                        priority=self.priority,
                    )
                )

        return annotations
