from scripts.extract_be_postcodes_from_wikipedia import PostalCodeEntry, parse_postal_code_entries


def _wrap_html(list_markup: str) -> str:
    return (
        '<div class="mw-parser-output"><div class="kolommen"><div class="kolom">'
        f"<section><ul>{list_markup}</ul></section>"
        "</div></div></div>"
    )


class TestExtractBePostcodesFromWikipedia:
    def test_parse_flat_postcode_entry(self):
        html = _wrap_html("<li>1000 Brussel (stad)</li>")

        assert parse_postal_code_entries(html) == [
            PostalCodeEntry(postcode="1000", locality="Brussel (stad)")
        ]

    def test_parse_nested_postcode_entries_with_inherited_code(self):
        html = _wrap_html(
            """
            <li>1005
              <ul>
                <li>Verenigde Vergadering van de Gemeenschappelijke Gemeenschapscommissie</li>
                <li>Brussels Hoofdstedelijk Parlement</li>
              </ul>
            </li>
            """
        )

        assert parse_postal_code_entries(html) == [
            PostalCodeEntry(
                postcode="1005",
                locality="Brussels Hoofdstedelijk Parlement",
            ),
            PostalCodeEntry(
                postcode="1005",
                locality="Verenigde Vergadering van de Gemeenschappelijke Gemeenschapscommissie",
            ),
        ]

    def test_parse_special_entry_as_raw_mapping_row(self):
        html = _wrap_html("<li>1047 Europees Parlement</li>")

        assert parse_postal_code_entries(html) == [
            PostalCodeEntry(postcode="1047", locality="Europees Parlement")
        ]

    def test_parse_nested_child_with_its_own_postcode(self):
        html = _wrap_html(
            """
            <li>9000 Gent
              <ul>
                <li>9030 Mariakerke</li>
              </ul>
            </li>
            """
        )

        assert parse_postal_code_entries(html) == [
            PostalCodeEntry(postcode="9000", locality="Gent"),
            PostalCodeEntry(postcode="9030", locality="Mariakerke"),
        ]
