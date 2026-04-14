from belgian_deduce.metadata import Address, MetadataEntity, Person
from belgian_deduce.person import (
    Address as LegacyAddress,
    MetadataEntity as LegacyMetadataEntity,
    Person as LegacyPerson,
)


class TestMetadataModule:
    def test_person_module_remains_alias_for_metadata(self):
        assert Address is LegacyAddress
        assert MetadataEntity is LegacyMetadataEntity
        assert Person is LegacyPerson
