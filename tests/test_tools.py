from uk_resell_adk.tools import discover_foreign_marketplaces, find_candidate_items


def test_discover_foreign_marketplaces_has_results() -> None:
    marketplaces = discover_foreign_marketplaces()
    assert marketplaces
    assert any(site.country != "United Kingdom" for site in marketplaces)


def test_find_candidate_items_for_known_marketplace() -> None:
    marketplace = discover_foreign_marketplaces()[0]
    items = find_candidate_items(marketplace)
    assert items
    assert all(item.site_name == marketplace.name for item in items)
