"""Extract Belgian postcode/locality data from Dutch Wikipedia."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

WIKIPEDIA_URL = "https://nl.wikipedia.org/wiki/Postnummers_in_België"
USER_AGENT = "belgian-deduce/1.0 (local development)"

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from belgian_deduce.postal_code import clean_location_text, derive_locality_candidates

LOOKUP_ROOT = REPO_ROOT / "belgian_deduce" / "data" / "lookup" / "src" / "locations"
RAW_MAPPING_PATH = LOOKUP_ROOT / "lst_postal_code_locality" / "items.txt"
LOCALITY_PATH = LOOKUP_ROOT / "lst_placename" / "lst_postal_locality" / "items.txt"


@dataclass(frozen=True, order=True)
class PostalCodeEntry:
    """A postcode/locality entry extracted from the page."""

    postcode: str
    locality: str


def fetch_wikipedia_html(url: str = WIKIPEDIA_URL) -> str:
    """Fetch the Wikipedia page with a descriptive user agent."""

    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    return response.text


def _direct_text(tag: Tag) -> str:
    parts: list[str] = []

    for child in tag.contents:
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif isinstance(child, Tag) and child.name != "ul":
            parts.append(child.get_text(" ", strip=True))

    return clean_location_text(" ".join(parts))


def _iter_top_level_postcode_lists(main_content: Tag) -> Iterator[Tag]:
    columns = main_content.select_one("div.kolommen")
    if columns is None:
        raise RuntimeError("Could not find the postcode list container on the page.")

    for postcode_list in columns.select("div.kolom > section > ul"):
        yield postcode_list


def _parse_list_item(
    item: Tag, inherited_postcode: Optional[str] = None
) -> Iterator[PostalCodeEntry]:
    direct_text = _direct_text(item)
    if len(direct_text) == 0:
        return

    postcode: Optional[str]
    locality_text: str
    parts = direct_text.split(maxsplit=1)

    if len(parts) > 0 and len(parts[0]) == 4 and parts[0].isdigit():
        postcode = parts[0]
        locality_text = parts[1] if len(parts) > 1 else ""
    else:
        postcode = inherited_postcode
        locality_text = direct_text

    if postcode is None:
        return

    locality_text = clean_location_text(locality_text)
    if len(locality_text) != 0:
        yield PostalCodeEntry(postcode=postcode, locality=locality_text)

    nested_list = item.find("ul", recursive=False)
    if nested_list is None:
        return

    for nested_item in nested_list.find_all("li", recursive=False):
        yield from _parse_list_item(nested_item, inherited_postcode=postcode)


def parse_postal_code_entries(html: str) -> list[PostalCodeEntry]:
    """Parse postcode/locality entries from the live page HTML."""

    soup = BeautifulSoup(html, "html.parser")
    main_content = soup.select_one("div.mw-parser-output")
    if main_content is None:
        raise RuntimeError("Could not find the Wikipedia article content.")

    entries = {
        entry
        for postcode_list in _iter_top_level_postcode_lists(main_content)
        for item in postcode_list.find_all("li", recursive=False)
        for entry in _parse_list_item(item)
    }

    return sorted(entries)


def write_lookup_files(
    entries: Iterable[PostalCodeEntry],
    raw_mapping_path: Path = RAW_MAPPING_PATH,
    locality_path: Path = LOCALITY_PATH,
) -> None:
    """Write the raw mapping snapshot and the derived locality list."""

    entries = sorted(set(entries))
    localities = sorted(
        {
            locality
            for entry in entries
            for locality in derive_locality_candidates(entry.locality)
        }
    )

    raw_mapping_path.parent.mkdir(parents=True, exist_ok=True)
    locality_path.parent.mkdir(parents=True, exist_ok=True)

    raw_mapping_path.write_text(
        "\n".join(f"{entry.postcode}\t{entry.locality}" for entry in entries) + "\n",
        encoding="utf-8",
    )
    locality_path.write_text("\n".join(localities) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=WIKIPEDIA_URL)
    return parser.parse_args()


def main() -> None:
    """Fetch the page and update the lookup source files."""

    args = parse_args()
    html = fetch_wikipedia_html(url=args.url)
    entries = parse_postal_code_entries(html)
    write_lookup_files(entries)
    print(f"Saved {len(entries)} postcode/locality rows to {RAW_MAPPING_PATH}")
    print(f"Saved {len({l for e in entries for l in derive_locality_candidates(e.locality)})} localities to {LOCALITY_PATH}")


if __name__ == "__main__":
    main()
