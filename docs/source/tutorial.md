# Tutorial

`belgian_deduce` is a standalone de-identification package for Belgian clinical text.
It uses [docdeid](https://docdeid.readthedocs.io/en/latest/) as its processing
framework and ships with Belgian defaults for lookup data, postal codes, phone
numbers, and national register numbers.

If you get stuck, open an issue in the
[belgian-deduce repository](https://github.com/stighellemans/belgian-deduce/issues).

```{include} ../../README.md
:start-after: <!-- start getting started -->
:end-before: <!-- end getting started -->
```

## Included Components

A `docdeid` de-identifier is assembled from annotators, processors, and a redactor.
`belgian_deduce` ships with these default groups:

| Group | Purpose |
|-------|---------|
| `names` | Personal names, initials, prefixes, interfixes, and patient metadata |
| `locations` | Place names, streets, house numbers, Belgian postal codes, and postbus references |
| `institutions` | Hospitals and healthcare institutions |
| `dates` | Numeric and written Dutch date formats |
| `ages` | Age patterns such as `64 jaar` |
| `identifiers` | Belgian national register numbers and generic numeric identifiers |
| `phone_numbers` | Belgian phone numbers |
| `email_addresses` | E-mail addresses |
| `urls` | URLs |

The custom annotators are loaded from `belgian_deduce.annotator.*`. The base
configuration lives in
[belgian_deduce/base_config.json](../../belgian_deduce/base_config.json).

## Custom Configuration

You can extend or override the packaged configuration:

```python
from belgian_deduce import Deduce

model = Deduce(config="my_config.json")
model = Deduce(config={"redactor_open_char": "<", "redactor_close_char": ">"})
```

To replace the packaged defaults entirely:

```python
from belgian_deduce import Deduce

model = Deduce(load_base_config=False, config="my_config.json")
```

## Enable Or Disable Components

Disable whole groups:

```python
from belgian_deduce import Deduce

model = Deduce()
doc = model.deidentify(text, disabled={"identifiers", "phone_numbers"})
```

Or only enable a narrow path through the pipeline:

```python
from belgian_deduce import Deduce

model = Deduce()
doc = model.deidentify(
    text,
    enabled={
        "email_addresses",
        "email",
        "post_processing",
        "overlap_resolver",
        "merge_adjacent_annotations",
        "redactor",
    },
)
```

## Custom Processors

Because `belgian_deduce` extends `docdeid`, you can inject your own annotators,
processors, redactors, or tokenizers:

```python
from belgian_deduce import Deduce

model = Deduce()

del model.processors["dates"]
model.processors.add_processor("custom", MyCustomAnnotator(), position=0)
```

## Tailoring Lookup Data

Lookup structures are available through `Deduce.lookup_structs`:

```python
from belgian_deduce import Deduce

model = Deduce()

model.lookup_structs["first_name"].add_items_from_iterable(["Jef", "Lotte"])
model.lookup_structs["whitelist"].add_items_from_iterable(["campus", "klinisch"])
```

If you want to maintain your own lookup source tree, point the model to a copied
lookup directory:

```python
from belgian_deduce import Deduce

model = Deduce(lookup_data_path="/my/custom/lookup")
```

That fully detaches runtime data from package updates, but it also means you own the
merge process for future list changes.
