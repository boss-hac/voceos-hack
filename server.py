"""
VoiceOS MCP Server: Voice-to-Shopping-List Recipe Assistant
Searches recipes on Cookpad, extracts ingredients, and sends a shopping list via email.
"""

import json
import re
import subprocess

import requests
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("recipe-assistant")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en;q=0.9",
}


@mcp.tool()
def get_recipe(recipe_url: str) -> str:
    """Get detailed recipe information from a Cookpad recipe URL.
    Returns the recipe title, ingredients with quantities, and cooking steps.
    Use this after finding a recipe URL via browser search on cookpad.com.
    """
    resp = requests.get(recipe_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    # Try JSON-LD first (most reliable)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
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
    title_el = soup.select_one("h1.break-words")
    title = title_el.get_text(strip=True) if title_el else "タイトル不明"

    ingredients = []
    for li in soup.select("li[id^='ingredient_']"):
        name_el = li.select_one("span")
        qty_el = li.select_one("bdi.font-semibold")
        name = name_el.get_text(strip=True) if name_el else ""
        qty = qty_el.get_text(strip=True) if qty_el else ""
        if name:
            ingredients.append(f"{name} {qty}".strip())

    steps = []
    for li in soup.select("li.step"):
        p = li.select_one("p.overflow-wrap-anywhere")
        if p:
            steps.append(p.get_text(strip=True))

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
    Takes the output of get_recipe and returns just the ingredient names
    suitable for searching on a grocery shopping site.
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
            # Remove quantity (everything after spaces/fullwidth-space + number/unit)
            name = re.split(r'[\s　]+\d|[\s　]+小さじ|[\s　]+大さじ|[\s　]+少々|[\s　]+適量', item)[0].strip()
            if name and name not in pantry:
                items.append(name)

    return "\n".join(items)


@mcp.tool()
def send_shopping_list_email(to_email: str, recipe_name: str, shopping_list: str) -> str:
    """Send a shopping list as an email using macOS Mail.app.
    to_email: recipient email address
    recipe_name: name of the recipe (used as subject)
    shopping_list: newline-separated list of ingredients to buy
    """
    items = [item.strip() for item in shopping_list.strip().split("\n") if item.strip()]
    body_lines = [f"🛒 「{recipe_name}」の買い物リスト", ""]
    for i, item in enumerate(items, 1):
        body_lines.append(f"☐ {item}")
    body_lines.append("")
    body_lines.append("---")
    body_lines.append("VoiceOS Recipe Assistant より自動送信")

    body = "\n".join(body_lines)
    subject = f"買い物リスト: {recipe_name}"

    applescript = f'''
    tell application "Mail"
        set newMessage to make new outgoing message with properties {{subject:"{subject}", content:"{body}", visible:false}}
        tell newMessage
            make new to recipient at end of to recipients with properties {{address:"{to_email}"}}
        end tell
        send newMessage
    end tell
    '''
    subprocess.run(["osascript", "-e", applescript], check=True, timeout=15)
    return f"買い物リストを {to_email} に送信しました（{len(items)}品目）"


if __name__ == "__main__":
    mcp.run(transport="stdio")
