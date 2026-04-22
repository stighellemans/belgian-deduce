"""Extract Belgian postcode/locality data from Dutch and French Wikipedia."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

DEFAULT_WIKIPEDIA_URLS = (
    "https://nl.wikipedia.org/wiki/Postnummers_in_België",
    "https://fr.wikipedia.org/wiki/Liste_des_codes_postaux_belges",
)
USER_AGENT = "belgian-deduce/1.0 (local development)"
_POSTCODE_SECTION_HEADING_RE = re.compile(r"^\s*\d{4}\s*[–-]\s*\d{4}")

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


def sort_postal_code_entries(
    entries: Iterable[PostalCodeEntry],
) -> list[PostalCodeEntry]:
    """Return entries in a deterministic postcode/locality order."""

    return sorted(
        set(entries),
        key=lambda entry: (entry.postcode, entry.locality.casefold(), entry.locality),
    )


def fetch_wikipedia_html(url: str) -> str:
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
    if columns is not None:
        for postcode_list in columns.select("div.kolom > section > ul"):
            yield postcode_list
        return

    heading_blocks = main_content.select("div.mw-heading2")
    if len(heading_blocks) == 0:
        heading_blocks = main_content.find_all("h2")

    for heading in heading_blocks:
        heading_text = clean_location_text(heading.get_text(" ", strip=True))
        if _POSTCODE_SECTION_HEADING_RE.match(heading_text) is None:
            continue

        sibling = heading.find_next_sibling()
        while sibling is not None:
            if sibling.name == "ul":
                yield sibling
                break

            if sibling.name == "h2" or (
                sibling.name == "div" and "mw-heading2" in sibling.get("class", [])
            ):
                break

            sibling = sibling.find_next_sibling()


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

    return sort_postal_code_entries(entries)


def fetch_and_parse_postal_code_entries(urls: Iterable[str]) -> list[PostalCodeEntry]:
    """Fetch one or more Wikipedia postcode pages and merge their raw entries."""

    entries = set()
    for url in urls:
        html = fetch_wikipedia_html(url=url)
        entries.update(parse_postal_code_entries(html))
    return sort_postal_code_entries(entries)


def write_lookup_files(
    entries: Iterable[PostalCodeEntry],
    raw_mapping_path: Path = RAW_MAPPING_PATH,
    locality_path: Path = LOCALITY_PATH,
) -> None:
    """Write the raw mapping snapshot and the derived locality list."""

    entries = sort_postal_code_entries(entries)
    localities = sorted(
        {
            locality
            for entry in entries
            for locality in derive_locality_candidates(entry.locality)
        },
        key=lambda locality: (locality.casefold(), locality),
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
    parser.add_argument(
        "--url",
        action="append",
        help=(
            "Wikipedia postcode page URL. Can be provided multiple times. "
            "Defaults to the Dutch and French postcode pages."
        ),
    )
    return parser.parse_args()


def main() -> None:
    """Fetch the page and update the lookup source files."""

    args = parse_args()
    urls = args.url if args.url else list(DEFAULT_WIKIPEDIA_URLS)
    entries = fetch_and_parse_postal_code_entries(urls)
    write_lookup_files(entries)
    print(f"Saved {len(entries)} postcode/locality rows to {RAW_MAPPING_PATH}")
    print(f"Saved {len({l for e in entries for l in derive_locality_candidates(e.locality)})} localities to {LOCALITY_PATH}")


if __name__ == "__main__":
    main()
