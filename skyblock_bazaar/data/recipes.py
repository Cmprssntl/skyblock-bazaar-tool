"""配方加载：NEU JSON → 结构化配方（craft / forge / enchant）。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

_ENCHANTMENT_LEVEL = re.compile(r"^(ENCHANTMENT_.+)_([0-9]+)$")
_CRAFT_TYPES = {"crafting", "craft"}


@dataclass(frozen=True, slots=True)
class Recipe:
    materials: dict[str, float]
    output_count: float = 1.0


@dataclass(frozen=True, slots=True)
class ForgeRecipe:
    materials: dict[str, float]
    duration: float
    count: float = 1.0


@dataclass(frozen=True, slots=True)
class EnchantRecipe:
    base_id: str
    level: int
    alternatives: list[dict[str, float]] = field(default_factory=list)


# ---------------------------------------------------------------- 通用解析
def parse_entry(value) -> tuple[str, float] | None:
    if not isinstance(value, str) or ":" not in value:
        return None
    item_id, amount_text = value.rsplit(":", 1)
    item_id = item_id.strip()
    try:
        amount = float(amount_text)
    except (TypeError, ValueError):
        return None
    if not item_id or amount <= 0:
        return None
    return item_id, amount


def parse_recipe_object(recipe) -> Recipe | None:
    if not isinstance(recipe, dict):
        return None
    materials: dict[str, float] = {}
    for key, value in recipe.items():
        if str(key).lower() in {"type", "count", "output", "output_count", "duration", "inputs", "cost", "result", "coins"}:
            continue
        parsed = parse_entry(value)
        if parsed:
            item_id, amount = parsed
            materials[item_id] = materials.get(item_id, 0) + amount
    if not materials:
        return None
    try:
        output_count = float(recipe.get("count", 1) or 1)
    except (TypeError, ValueError):
        output_count = 1.0
    if output_count <= 0:
        output_count = 1.0
    return Recipe({k: v / output_count for k, v in materials.items()}, output_count)


def get_item_recipe(item_data: dict) -> Recipe | None:
    single = parse_recipe_object(item_data.get("recipe"))
    if single:
        return single
    recipes = item_data.get("recipes")
    if isinstance(recipes, list):
        for recipe in recipes:
            if not isinstance(recipe, dict):
                continue
            if str(recipe.get("type", "crafting")).lower() not in _CRAFT_TYPES:
                continue
            parsed = parse_recipe_object(recipe)
            if parsed:
                return parsed
    return None


def _load_json_files(directory: Path):
    if not directory.is_dir():
        return
    for path in sorted(directory.glob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError, TypeError):
            continue
        if isinstance(data, dict):
            yield path, data


def _book_id(item_data: dict, fallback: str) -> str:
    """NEU 用 CORRUPTION;1，Bazaar 用 ENCHANTMENT_CORRUPTION_1。"""
    item_id = str(item_data.get("internalname") or fallback)
    if item_data.get("itemid") == "minecraft:enchanted_book":
        enchantment, separator, level = item_id.rpartition(";")
        if separator and enchantment and level.isdecimal():
            return f"ENCHANTMENT_{enchantment}_{level}"
    return item_id


# ---------------------------------------------------------------- Craft
def load_craft_recipes(directories: list[Path]) -> dict[str, Recipe]:
    """读取 craft 配方，并把附魔书的 NEU ID（CORRUPTION;1）换成 Bazaar ID。"""
    raw: dict[str, Recipe] = {}
    book_ids: dict[str, str] = {}
    for directory in directories:
        for path, data in _load_json_files(directory):
            item_id = str(data.get("internalname") or path.stem)
            mapped = _book_id(data, path.stem)
            if mapped != item_id:
                book_ids[item_id] = mapped
            recipe = get_item_recipe(data)
            if recipe:
                raw[item_id] = recipe

    if not book_ids:
        return raw
    normalized: dict[str, Recipe] = {}
    for item_id, recipe in raw.items():
        materials: dict[str, float] = {}
        for material_id, amount in recipe.materials.items():
            target = book_ids.get(material_id, material_id)
            materials[target] = materials.get(target, 0) + amount
        normalized[book_ids.get(item_id, item_id)] = Recipe(materials, recipe.output_count)
    return normalized


# ---------------------------------------------------------------- Forge
def load_forge_recipes(directory: Path) -> dict[str, ForgeRecipe]:
    result: dict[str, ForgeRecipe] = {}
    for path, data in _load_json_files(directory):
        output_id = str(data.get("internalname") or path.stem)
        recipes = data.get("recipes")
        if not isinstance(recipes, list):
            continue
        for recipe in recipes:
            if not isinstance(recipe, dict) or str(recipe.get("type", "")).lower() != "forge":
                continue
            materials: dict[str, float] = {}
            for raw in recipe.get("inputs") or []:
                parsed = parse_entry(raw)
                if parsed:
                    materials[parsed[0]] = materials.get(parsed[0], 0) + parsed[1]
            if not materials:
                continue
            try:
                duration = float(recipe.get("duration", 0) or 0)
            except (TypeError, ValueError):
                duration = 0.0
            try:
                count = float(recipe.get("count", 1) or 1)
            except (TypeError, ValueError):
                count = 1.0
            if count <= 0:
                count = 1.0
            result[str(recipe.get("overrideOutputId") or output_id)] = ForgeRecipe(
                {k: v / count for k, v in materials.items()}, duration, count
            )
    return result


# ---------------------------------------------------------------- Enchant
def parse_enchant_output(item_id: str) -> tuple[str, int] | None:
    match = _ENCHANTMENT_LEVEL.fullmatch(str(item_id or ""))
    if not match:
        return None
    return match.group(1), int(match.group(2))


def load_enchant_recipes(directories: list[Path]) -> dict[str, EnchantRecipe]:
    result: dict[str, EnchantRecipe] = {}
    for directory in directories:
        for path, data in _load_json_files(directory):
            output_id = str(data.get("internalname") or path.stem)
            parsed = parse_enchant_output(output_id)
            if not parsed:
                continue
            raw_recipes = data.get("recipes")
            if not isinstance(raw_recipes, list):
                raw_recipes = [data.get("recipe")]
            alternatives: list[dict[str, float]] = []
            for raw in raw_recipes:
                recipe = parse_recipe_object(raw)
                if recipe:
                    alternatives.append(dict(recipe.materials))
            if alternatives:
                result[output_id] = EnchantRecipe(parsed[0], parsed[1], alternatives)
    return result


ROMAN = (
    (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
    (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
    (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
)


def to_roman(value: int) -> str:
    value = int(value)
    parts = []
    for number, numeral in ROMAN:
        count, value = divmod(value, number)
        parts.append(numeral * count)
    return "".join(parts) or "I"
