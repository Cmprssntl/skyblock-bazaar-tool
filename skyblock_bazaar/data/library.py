"""配方库：启动时加载一次，供各页面复用。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..paths import RECIPE_DIRS
from .recipes import (
    EnchantRecipe,
    ForgeRecipe,
    Recipe,
    load_craft_recipes,
    load_enchant_recipes,
    load_forge_recipes,
)


@dataclass
class RecipeLibrary:
    craft: dict[str, Recipe] = field(default_factory=dict)
    forge: dict[str, ForgeRecipe] = field(default_factory=dict)
    enchant: dict[str, EnchantRecipe] = field(default_factory=dict)
    load_seconds: float = 0.0

    @classmethod
    def load(cls, log=None) -> RecipeLibrary:
        started = time.perf_counter()
        library = cls(
            craft=load_craft_recipes([RECIPE_DIRS["craft"]]),
            forge=load_forge_recipes(RECIPE_DIRS["forge"]),
            enchant=load_enchant_recipes([RECIPE_DIRS["enchant"]]),
        )
        library.load_seconds = time.perf_counter() - started
        if log:
            log.info(
                "配方已加载：craft=%d forge=%d enchant=%d（%.2fs）",
                len(library.craft),
                len(library.forge),
                len(library.enchant),
                library.load_seconds,
            )
        return library
