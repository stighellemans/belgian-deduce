from belgian_deduce._version import __version__
from belgian_deduce.deduce import Deduce
from belgian_deduce.metadata import Address, MetadataEntity, Person

BelgianDeduce = Deduce

__all__ = [
    "Address",
    "BelgianDeduce",
    "Deduce",
    "MetadataEntity",
    "Person",
    "__version__",
]
