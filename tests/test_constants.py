from constants import CATEGORIES


def test_categories_has_26_items():
    assert len(CATEGORIES) == 26


def test_categories_contains_key_items():
    assert "점심식비" in CATEGORIES
    assert "오사용" in CATEGORIES
    assert "기타비용" in CATEGORIES


def test_categories_are_unique():
    assert len(set(CATEGORIES)) == len(CATEGORIES)
