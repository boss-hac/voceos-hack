"""
VoiceOS MCP Server: Voice-to-Shopping-List Recipe Assistant
Searches recipes on Cookpad, extracts ingredients, and returns a shopping list.
"""

import json
import re

from scrapling.fetchers import Fetcher
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("recipe-assistant")


@mcp.tool()
def search_recipes(query: str) -> str:
    """Search recipes on Cookpad by keyword (e.g. dish name, ingredient, genre).
    Returns a list of recipe titles and URLs.
    Examples: "カレー", "鶏肉 簡単", "パスタ トマト"
    """
    url = f"https://cookpad.com/jp/search/{query}"
    page = Fetcher.get(url, stealthy_headers=True)

    recipes = []
    for a in page.css("a[href*='/jp/recipes/']"):
        href = a.attrib.get("href", "")
        title = a.text.strip() if a.text else ""
        if "/jp/recipes/" in href and title and len(title) > 2:
            full_url = f"https://cookpad.com{href}" if href.startswith("/") else href
            if full_url not in [r["url"] for r in recipes]:
                recipes.append({"title": title, "url": full_url})
        if len(recipes) >= 5:
            break

    if not recipes:
        return f"「{query}」のレシピが見つかりませんでした。"

    result = f"「{query}」の検索結果:\n\n"
    for i, r in enumerate(recipes, 1):
        result += f"{i}. {r['title']}\n   {r['url']}\n"
    return result


@mcp.tool()
def get_recipe(recipe_url: str) -> str:
    """Get detailed recipe information from a Cookpad recipe URL.
    Returns the recipe title, ingredients with quantities, and cooking steps.
    """
    page = Fetcher.get(recipe_url, stealthy_headers=True)

    # Try JSON-LD first (most reliable)
    for script in page.css("script[type='application/ld+json']"):
        try:
            data = json.loads(script.text)
            if isinstance(data, list):
                data = next((d for d in data if d.get("@type") == "Recipe"), None)
            if data and data.get("@type") == "Recipe":
                title = data.get("name", "")
                servings = data.get("recipeYield", "")
                ingredients = data.get("recipeIngredient", [])
                steps = []
                for step in data.get("recipeInstructions", []):
                    if isinstance(step, dict):
                        steps.append(step.get("text", ""))
                    else:
                        steps.append(str(step))

                result = f"# {title}\n"
                result += f"分量: {servings}\n\n"
                result += "## 材料\n"
                for ing in ingredients:
                    result += f"- {ing}\n"
                result += "\n## 作り方\n"
                for i, step in enumerate(steps, 1):
                    result += f"{i}. {step}\n"
                return result
        except (json.JSONDecodeError, StopIteration):
            continue

    # Fallback: HTML parsing
    title_el = page.css_first("h1.break-words")
    title = title_el.text.strip() if title_el else "タイトル不明"

    ingredients = []
    for li in page.css("li[id^='ingredient_']"):
        name_el = li.css_first("span")
        qty_el = li.css_first("bdi.font-semibold")
        name = name_el.text.strip() if name_el else ""
        qty = qty_el.text.strip() if qty_el else ""
        if name:
            ingredients.append(f"{name} {qty}".strip())

    steps = []
    for li in page.css("li.step"):
        p = li.css_first("p.overflow-wrap-anywhere")
        if p:
            steps.append(p.text.strip())

    result = f"# {title}\n\n## 材料\n"
    for ing in ingredients:
        result += f"- {ing}\n"
    result += "\n## 作り方\n"
    for i, step in enumerate(steps, 1):
        result += f"{i}. {step}\n"
    return result


@mcp.tool()
def extract_shopping_list(recipe_text: str) -> str:
    """Extract a clean shopping list from recipe text.
    Takes the output of get_recipe and returns a formatted shopping list.
    Removes quantities and common pantry items (salt, pepper, water, oil).
    """
    pantry = {"塩", "こしょう", "胡椒", "水", "油", "サラダ油", "酒", "砂糖", "醤油", "しょうゆ", "みりん", "酢", "片栗粉", "小麦粉", "薄力粉"}

    items = []
    in_ingredients = False
    for line in recipe_text.split("\n"):
        if "## 材料" in line:
            in_ingredients = True
            continue
        if line.startswith("## "):
            in_ingredients = False
            continue
        if in_ingredients and line.startswith("- "):
            item = line[2:].strip()
            name = re.split(r'[\s　]+\d|[\s　]+小さじ|[\s　]+大さじ|[\s　]+少々|[\s　]+適量', item)[0].strip()
            if name and name not in pantry:
                items.append(name)

    if not items:
        return "買い物リストに追加する食材はありません。"

    result = "🛒 買い物リスト:\n"
    for item in items:
        result += f"  ☐ {item}\n"
    result += f"\n合計 {len(items)} 品目"
    return result


if __name__ == "__main__":
    mcp.run(transport="stdio")
