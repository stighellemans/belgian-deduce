# Migrating

## Migrating To `belgian_deduce` 4.0.0

Version `4.0.0` is the first standalone `belgian_deduce` release. The main migration
points are:

* import from `belgian_deduce`, not `deduce`
* config references must point at `belgian_deduce.annotator.*`
* the default Belgian identifier annotator now detects national register numbers
  instead of Dutch BSN values
* the default phone-number annotator now targets Belgian numbering

## Import Path

Old:

```python
from deduce import Deduce
from deduce.person import Person
```

New:

```python
from belgian_deduce import Deduce
from belgian_deduce.person import Person
```

## Config Class Paths

Old:

```json
{
  "annotator_type": "deduce.annotator.TokenPatternAnnotator"
}
```

New:

```json
{
  "annotator_type": "belgian_deduce.annotator.TokenPatternAnnotator"
}
```

## Identifier Behavior

If you relied on the Dutch BSN annotator in upstream `deduce`, move that logic into a
custom config or custom processor. The packaged defaults in `belgian_deduce` now
prioritize Belgian national register numbers.
