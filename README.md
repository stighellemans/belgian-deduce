[![black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

# Belgian Deduce

<!-- start include in docs -->

`belgian_deduce` is a rule-based de-identification package for Belgian clinical text.
It ships as a standalone Python package, uses Belgian lookup data and defaults, and is
built on top of [docdeid](https://github.com/vmenger/docdeid).

* Remove names, places, institutions, dates, ages, identifiers, phone numbers, e-mail
  addresses, and URLs from Belgian medical text
* Tune behavior through config, lookup structures, and custom processors
* Use Belgian defaults for postal codes, phone numbers, and national register numbers

> `belgian_deduce` started from the original
> [deduce](https://github.com/vmenger/deduce) project. This repository now maintains
> its own package identity, configuration, documentation, and Belgian-specific
> defaults.

> De-identification is never perfect. Validate and adapt the package on your own data
> before using it in a critical environment.

## Citing

If you use `belgian_deduce`, cite the original DEDUCE paper for the underlying method
and reference this repository and version in your implementation notes:

[Menger, V.J., Scheepers, F., van Wijk, L.M., Spruit, M. (2017). DEDUCE: A pattern
matching method for automatic de-identification of Dutch medical text, Telematics and
Informatics, 2017, ISSN 0736-5853](http://www.sciencedirect.com/science/article/pii/S0736585316307365)

<!-- end include in docs -->

<!-- start getting started -->

## Installation

Install directly from GitHub:

```bash
pip install "git+https://github.com/stighellemans/belgian-deduce.git"
```

For reproducible environments, pin to a commit:

```bash
pip install "git+https://github.com/stighellemans/belgian-deduce.git@<commit-sha>"
```

## Getting Started

```python
from belgian_deduce import Deduce

model = Deduce()

text = (
    "betreft: Jan Janssens, rijksregisternummer 85.07.30-033.28, patnr 000334433. "
    "De patient J. Janssens is 64 jaar oud en woont in Leuven. Hij werd op "
    "10 oktober 2018 door arts Peter de Smet ontslagen uit UZ Leuven. "
    "Voor nazorg kan hij worden bereikt via j.janssens.123@gmail.com of "
    "0470 12 34 56."
)

doc = model.deidentify(text)
print(doc.deidentified_text)
```

```text
betreft: [PERSOON-1], rijksregisternummer [RIJKSREGISTERNUMMER-1], patnr [ID-1]. De patient [PERSOON-1] is [LEEFTIJD-1] jaar oud en woont in [LOCATIE-1]. Hij werd op [DATUM-1] door arts [PERSOON-2] ontslagen uit [ZIEKENHUIS-1]. Voor nazorg kan hij worden bereikt via [EMAILADRES-1] of [TELEFOONNUMMER-1].
```

If patient metadata is known, pass it explicitly:

```python
from belgian_deduce import Deduce, Person

model = Deduce()
patient = Person(first_names=["Jan"], initials="JJ", surname="Janssens")
doc = model.deidentify(text, metadata={"patient": patient})
```

Metadata can also be used for more than the primary patient. The pipeline supports:

* `persons`: one or more additional `Person` objects treated as regular people
* `addresses`: one or more `Address` objects that should be tagged as `locatie`
* `entities`: arbitrary exact metadata matches via `MetadataEntity`
* `Person.birth_date`, `Person.aliases`, and `Person.addresses`

```python
from datetime import date

from belgian_deduce import Address, Deduce, MetadataEntity, Person

deduce = Deduce()

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
    "persons": [
        Person(
            first_names=["Peter"],
            surname="de Visser",
            aliases=["Dr. Peter de Visser"],
        )
    ],
    "entities": [
        MetadataEntity(text="UZ Gent", tag="ziekenhuis"),
        MetadataEntity(text="ABC-12345", tag="id"),
    ],
}

doc = deduce.deidentify(text, metadata=metadata)
```

<!-- end getting started -->

## Documentation

The project documentation lives in [docs/source/tutorial.md](docs/source/tutorial.md)
and [docs/source/migrating.md](docs/source/migrating.md).

## Contributing

Contribution guidance is available in [CONTRIBUTING.md](CONTRIBUTING.md).

## Versions

* `4.0.0` - First standalone `belgian_deduce` release with Belgian defaults and
  independent docs/tooling
* Earlier entries in [CHANGELOG.md](CHANGELOG.md) predate the standalone release and
  are preserved for provenance

## Authors

* Vincent Menger - original DEDUCE implementation
* Stig Hellemans - Belgian standalone package and maintenance

## License

This project remains licensed under LGPL-3.0-or-later. See [LICENSE.md](LICENSE.md).
