import json
from pathlib import Path

import docdeid as dd

from belgian_deduce.lookup_structs import (
    cache_lookup_structs,
    load_lookup_structs_from_cache,
    load_raw_itemset,
    load_raw_itemsets,
    validate_lookup_struct_cache,
)

DATA_PATH = Path(".").cwd() / "tests" / "data" / "lookup"


class TestLookupStruct:
    def test_load_raw_itemset(self):
        raw_itemset = load_raw_itemset(DATA_PATH / "src" / "lst_test")

        assert len(raw_itemset) == 5
        assert "de Vries" in raw_itemset
        assert "De Vries" in raw_itemset
        assert "Sijbrand" in raw_itemset
        assert "Sybrand" in raw_itemset
        assert "Pieters" in raw_itemset
        assert "Wolter" not in raw_itemset

    def test_load_raw_itemset_nested(self):
        raw_itemset = load_raw_itemset(DATA_PATH / "src" / "lst_test_nested")

        assert raw_itemset == {"a", "b", "c", "d"}

    def test_load_raw_itemsets(self):
        raw_itemsets = load_raw_itemsets(
            base_path=DATA_PATH, subdirs=["lst_test", "lst_test_nested"]
        )

        assert "test" in raw_itemsets
        assert len(raw_itemsets["test"]) == 5
        assert "test_nested" in raw_itemsets
        assert len(raw_itemsets["test_nested"]) == 4

    def test_validate_lookup_struct_cache_valid(self, tmp_path):
        (tmp_path / "src" / "lst_test").mkdir(parents=True)
        (tmp_path / "src" / "lst_test" / "items.txt").write_text("a\n", encoding="utf-8")

        cache_lookup_structs(
            lookup_structs=dd.ds.DsCollection(),
            cache_path=tmp_path,
            package_version="2.5.0",
        )

        with open(
            tmp_path / "cache" / "lookup_structs.meta.json", "r", encoding="utf-8"
        ) as file:
            cache_metadata = json.load(file)

        assert validate_lookup_struct_cache(
            cache=cache_metadata, base_path=tmp_path, package_version="2.5.0"
        )

    def test_validate_lookup_struct_cache_file_changes(self, tmp_path):
        list_dir = tmp_path / "src" / "lst_test"
        list_dir.mkdir(parents=True)
        items_file = list_dir / "items.txt"
        items_file.write_text("a\n", encoding="utf-8")

        cache_lookup_structs(
            lookup_structs=dd.ds.DsCollection(),
            cache_path=tmp_path,
            package_version="2.5.0",
        )

        items_file.write_text("a\nb\n", encoding="utf-8")

        with open(
            tmp_path / "cache" / "lookup_structs.meta.json", "r", encoding="utf-8"
        ) as file:
            cache_metadata = json.load(file)

        assert not validate_lookup_struct_cache(
            cache=cache_metadata, base_path=tmp_path, package_version="2.5.0"
        )

    def test_load_lookup_structs_from_cache(self, tmp_path):
        (tmp_path / "src" / "lst_test").mkdir(parents=True)
        (tmp_path / "src" / "lst_test" / "items.txt").write_text("a\n", encoding="utf-8")

        ds_collection = dd.ds.DsCollection()
        ds_collection["test"] = dd.ds.LookupSet()
        ds_collection["test"].add_items_from_iterable(["a", "b"])
        ds_collection["test_nested"] = dd.ds.LookupSet()
        ds_collection["test_nested"].add_items_from_iterable(["c", "d"])

        cache_lookup_structs(
            lookup_structs=ds_collection,
            cache_path=tmp_path,
            package_version="_",
        )

        loaded = load_lookup_structs_from_cache(cache_path=tmp_path, package_version="_")

        assert len(loaded) == 2
        assert "test" in loaded
        assert "test_nested" in loaded

    def test_load_lookup_structs_from_cache_nofile(self):
        ds_collection = load_lookup_structs_from_cache(
            cache_path=DATA_PATH / "non_existing_dir", package_version="_"
        )

        assert ds_collection is None

    def test_load_lookup_structs_from_cache_invalid(self, tmp_path):
        list_dir = tmp_path / "src" / "lst_test"
        list_dir.mkdir(parents=True)
        items_file = list_dir / "items.txt"
        items_file.write_text("a\n", encoding="utf-8")

        ds_collection = dd.ds.DsCollection()
        ds_collection["test"] = dd.ds.LookupSet()
        ds_collection["test"].add_items_from_iterable(["a"])

        cache_lookup_structs(
            lookup_structs=ds_collection,
            cache_path=tmp_path,
            package_version="_",
        )
        items_file.write_text("a\nb\n", encoding="utf-8")

        ds_collection = load_lookup_structs_from_cache(
            cache_path=tmp_path, package_version="_"
        )

        assert ds_collection is None

    def test_cache_lookup_structs(self, tmp_path):
        (tmp_path / "src" / "lst_test").mkdir(parents=True)
        (tmp_path / "src" / "lst_test" / "items.txt").write_text("a\n", encoding="utf-8")

        cache_lookup_structs(
            lookup_structs=dd.ds.DsCollection(),
            cache_path=tmp_path,
            package_version="2.5.0",
        )

        assert (tmp_path / "cache" / "lookup_structs.pickle").exists()
        assert (tmp_path / "cache" / "lookup_structs.meta.json").exists()
