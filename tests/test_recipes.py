"""配方加载：数量、附魔书 ID 归一化、罗马数字。"""

from __future__ import annotations

from skyblock_bazaar.data.library import RecipeLibrary
from skyblock_bazaar.data.recipes import parse_enchant_output, parse_entry, to_roman

LIBRARY = RecipeLibrary.load()


def test_recipe_counts_match_v35():
    assert len(LIBRARY.craft) == 2504
    assert len(LIBRARY.forge) == 124
    assert len(LIBRARY.enchant) == 540


def test_enchant_book_ids_are_bazaar_ids():
    assert "CORRUPTION;1" not in LIBRARY.craft
    assert "ENCHANTMENT_CORRUPTION_1" in LIBRARY.craft


def test_enchant_recipe_alternatives():
    recipe = LIBRARY.enchant["ENCHANTMENT_AIMING_2"]
    assert recipe.base_id == "ENCHANTMENT_AIMING"
    assert recipe.level == 2
    assert recipe.alternatives[0]["ENCHANTMENT_AIMING_1"] == 2


def test_forge_recipe_duration():
    recipe = LIBRARY.forge["AMBER_MATERIAL"]
    assert recipe.duration == 21600
    assert recipe.materials["FINE_AMBER_GEM"] == 12


def test_parse_helpers():
    assert parse_entry("ITEM:2.5") == ("ITEM", 2.5)
    assert parse_entry("ITEM") is None
    assert parse_enchant_output("ENCHANTMENT_WISE_5") == ("ENCHANTMENT_WISE", 5)
    assert parse_enchant_output("ENCHANTMENT_WISE") is None
    assert to_roman(1) == "I"
    assert to_roman(4) == "IV"
    assert to_roman(9) == "IX"
    assert to_roman(14) == "XIV"
