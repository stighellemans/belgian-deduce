from datetime import date

import docdeid as dd

from belgian_deduce.metadata import Address, MetadataEntity, Person

text = (
    "betreft: Jan Janssens, rijksregisternummer 85.07.30-033.28, patnr 000334433. De "
    "patient J. Janssens is 64 jaar oud en woont in Leuven. Hij werd op 10 oktober "
    "2018 door arts Peter de Smet ontslagen uit UZ Leuven. Voor nazorg kan hij "
    "worden bereikt via j.janssens.123@gmail.com of 0470 12 34 56."
)


class TestDeduce:
    def test_annotate(self, model):
        metadata = {"patient": Person(first_names=["Jan"], surname="Janssens")}
        doc = model.deidentify(text, metadata=metadata)

        expected_annotations = dd.AnnotationSet(
            [
                dd.Annotation(
                    text="0470 12 34 56",
                    start_char=text.index("0470 12 34 56"),
                    end_char=text.index("0470 12 34 56") + len("0470 12 34 56"),
                    tag="telefoonnummer",
                ),
                dd.Annotation(
                    text="85.07.30-033.28",
                    start_char=text.index("85.07.30-033.28"),
                    end_char=text.index("85.07.30-033.28") + len("85.07.30-033.28"),
                    tag="rijksregisternummer",
                ),
                dd.Annotation(
                    text="Peter de Smet",
                    start_char=text.index("Peter de Smet"),
                    end_char=text.index("Peter de Smet") + len("Peter de Smet"),
                    tag="persoon",
                ),
                dd.Annotation(
                    text="j.janssens.123@gmail.com",
                    start_char=text.index("j.janssens.123@gmail.com"),
                    end_char=text.index("j.janssens.123@gmail.com")
                    + len("j.janssens.123@gmail.com"),
                    tag="emailadres",
                ),
                dd.Annotation(
                    text="J. Janssens",
                    start_char=text.index("J. Janssens"),
                    end_char=text.index("J. Janssens") + len("J. Janssens"),
                    tag="patient",
                ),
                dd.Annotation(
                    text="Jan Janssens",
                    start_char=text.index("Jan Janssens"),
                    end_char=text.index("Jan Janssens") + len("Jan Janssens"),
                    tag="patient",
                ),
                dd.Annotation(
                    text="10 oktober 2018",
                    start_char=text.index("10 oktober 2018"),
                    end_char=text.index("10 oktober 2018") + len("10 oktober 2018"),
                    tag="datum",
                ),
                dd.Annotation(
                    text="64",
                    start_char=text.index("64"),
                    end_char=text.index("64") + len("64"),
                    tag="leeftijd",
                ),
                dd.Annotation(
                    text="000334433",
                    start_char=text.index("000334433"),
                    end_char=text.index("000334433") + len("000334433"),
                    tag="id",
                ),
                dd.Annotation(
                    text="Leuven",
                    start_char=text.index("Leuven"),
                    end_char=text.index("Leuven") + len("Leuven"),
                    tag="locatie",
                ),
                dd.Annotation(
                    text="UZ Leuven",
                    start_char=text.index("UZ Leuven"),
                    end_char=text.index("UZ Leuven") + len("UZ Leuven"),
                    tag="ziekenhuis",
                ),
            ]
        )

        assert doc.annotations == set(expected_annotations)

    def test_deidentify(self, model):
        metadata = {"patient": Person(first_names=["Jan"], surname="Janssens")}
        doc = model.deidentify(text, metadata=metadata)

        expected_deidentified = (
            "betreft: [PATIENT], rijksregisternummer [RIJKSREGISTERNUMMER-1], patnr "
            "[ID-1]. De patient [PATIENT] is [LEEFTIJD-1] jaar oud en woont in "
            "[LOCATIE-1]. Hij werd op [DATUM-1] door arts [PERSOON-1] ontslagen uit "
            "[ZIEKENHUIS-1]. Voor nazorg kan hij worden bereikt via [EMAILADRES-1] "
            "of [TELEFOONNUMMER-1]."
        )

        assert doc.deidentified_text == expected_deidentified

    def test_annotate_intext(self, model):
        metadata = {"patient": Person(first_names=["Jan"], surname="Janssens")}
        doc = model.deidentify(text, metadata=metadata)

        expected_intext_annotated = (
            "betreft: <PATIENT>Jan Janssens</PATIENT>, rijksregisternummer "
            "<RIJKSREGISTERNUMMER>85.07.30-033.28</RIJKSREGISTERNUMMER>, patnr "
            "<ID>000334433</ID>. De patient <PATIENT>J. Janssens</PATIENT> is "
            "<LEEFTIJD>64</LEEFTIJD> jaar oud en woont in <LOCATIE>Leuven</LOCATIE>. "
            "Hij werd op <DATUM>10 oktober 2018</DATUM> door arts "
            "<PERSOON>Peter de Smet</PERSOON> ontslagen uit "
            "<ZIEKENHUIS>UZ Leuven</ZIEKENHUIS>. Voor nazorg kan hij worden bereikt "
            "via <EMAILADRES>j.janssens.123@gmail.com</EMAILADRES> of "
            "<TELEFOONNUMMER>0470 12 34 56</TELEFOONNUMMER>."
        )

        assert dd.utils.annotate_intext(doc) == expected_intext_annotated

    def test_extended_metadata(self, model):
        text = (
            "Patient Jan Jansen, geboren op 12 maart 1980, woont op Kerkstraat 12A, "
            "9000 Gent. Arts Peter de Visser werkt in UZ Gent."
        )
        metadata = {
            "patient": Person(
                first_names=["Jan"],
                surname="Jansen",
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
            "persons": [Person(first_names=["Peter"], surname="de Visser")],
            "entities": [MetadataEntity(text="UZ Gent", tag="ziekenhuis")],
        }

        doc = model.deidentify(text, metadata=metadata)

        assert dd.Annotation(
            text="Jan Jansen", start_char=8, end_char=18, tag="patient"
        ) in doc.annotations
        assert dd.Annotation(
            text="12 maart 1980", start_char=31, end_char=44, tag="datum"
        ) in doc.annotations
        assert dd.Annotation(
            text="Kerkstraat 12A, 9000 Gent",
            start_char=55,
            end_char=80,
            tag="locatie",
        ) in doc.annotations
        assert dd.Annotation(
            text="Peter de Visser", start_char=87, end_char=102, tag="persoon"
        ) in doc.annotations
        assert dd.Annotation(
            text="UZ Gent", start_char=112, end_char=119, tag="ziekenhuis"
        ) in doc.annotations

        assert doc.deidentified_text == (
            "Patient [PATIENT], geboren op [DATUM-1], woont op [LOCATIE-1]. "
            "Arts [PERSOON-1] werkt in [ZIEKENHUIS-1]."
        )

    def test_belgian_postcode_location_matching(self, model):
        cases = {
            "1000 Brussel": dd.AnnotationSet(
                [dd.Annotation(text="1000 Brussel", start_char=0, end_char=12, tag="locatie")]
            ),
            "Brussel 1000": dd.AnnotationSet(
                [dd.Annotation(text="Brussel 1000", start_char=0, end_char=12, tag="locatie")]
            ),
            "1348 Louvain-la-Neuve": dd.AnnotationSet(
                [
                    dd.Annotation(
                        text="1348 Louvain-la-Neuve",
                        start_char=0,
                        end_char=21,
                        tag="locatie",
                    )
                ]
            ),
            "1120 Neder-Over-Heembeek": dd.AnnotationSet(
                [
                    dd.Annotation(
                        text="1120 Neder-Over-Heembeek",
                        start_char=0,
                        end_char=24,
                        tag="locatie",
                    )
                ]
            ),
            "1047 Europees Parlement": dd.AnnotationSet(),
        }

        for input_text, expected_annotations in cases.items():
            assert model.deidentify(input_text).annotations == expected_annotations

    def test_postcode_like_year_stays_a_date(self, model):
        assert model.deidentify("2016:").annotations == dd.AnnotationSet(
            [dd.Annotation(text="2016", start_char=0, end_char=4, tag="datum")]
        )
