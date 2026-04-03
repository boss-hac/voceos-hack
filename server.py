"""
VoiceOS MCP Server: Food Assistant
Searches recipes on Cookpad, finds restaurants on Tabelog, and orders delivery on Uber Eats.
"""

import json
import os
import re
from pathlib import Path

from curl_cffi import requests as curl_requests
from scrapling.fetchers import Fetcher
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("food-assistant")

# Uber Eats cookies
COOKIES_PATH = Path(__file__).parent / "cookies.json"
_ue_cookies = {}
if COOKIES_PATH.exists():
    with open(COOKIES_PATH) as f:
        for c in json.load(f):
            _ue_cookies[c["name"]] = c["value"]

UE_HEADERS = {"x-csrf-token": "x", "content-type": "application/json"}


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


AREA_COORDS = {
    "渋谷": (35.6580, 139.7016), "新宿": (35.6938, 139.7034),
    "池袋": (35.7295, 139.7109), "銀座": (35.6717, 139.7651),
    "新橋": (35.6662, 139.7583), "六本木": (35.6627, 139.7311),
    "恵比寿": (35.6467, 139.7100), "品川": (35.6284, 139.7387),
    "上野": (35.7141, 139.7774), "秋葉原": (35.6984, 139.7731),
    "東京駅": (35.6812, 139.7671), "吉祥寺": (35.7030, 139.5796),
    "中目黒": (35.6440, 139.6988), "代官山": (35.6487, 139.7032),
    "表参道": (35.6653, 139.7121), "浅草": (35.7148, 139.7967),
    "目黒": (35.6337, 139.7158), "五反田": (35.6262, 139.7237),
    "横浜": (35.4437, 139.6380), "大宮": (35.9062, 139.6237),
    "千葉": (35.6074, 140.1065), "梅田": (34.7024, 135.4959),
    "難波": (34.6629, 135.5013), "心斎橋": (34.6752, 135.5006),
    "京都": (35.0116, 135.7681), "名古屋": (35.1709, 136.8815),
    "博多": (33.5902, 130.4017), "札幌": (43.0687, 141.3508),
}

TABELOG_AREAS = {
    "渋谷": "tokyo/A1303/A130301", "新宿": "tokyo/A1304/A130401",
    "池袋": "tokyo/A1305/A130501", "銀座": "tokyo/A1301/A130101",
    "新橋": "tokyo/A1301/A130103", "六本木": "tokyo/A1307/A130701",
    "恵比寿": "tokyo/A1303/A130302", "品川": "tokyo/A1314/A131401",
    "上野": "tokyo/A1311/A131101", "秋葉原": "tokyo/A1310/A131001",
    "東京駅": "tokyo/A1302/A130201", "吉祥寺": "tokyo/A1320/A132001",
    "中目黒": "tokyo/A1317/A131701", "代官山": "tokyo/A1303/A130303",
    "表参道": "tokyo/A1306/A130602", "浅草": "tokyo/A1311/A131102",
    "目黒": "tokyo/A1316/A131601", "五反田": "tokyo/A1316/A131602",
    "横浜": "kanagawa/A1401/A140101", "大宮": "saitama/A1101/A110101",
    "千葉": "chiba/A1201/A120101", "梅田": "osaka/A2701/A270101",
    "難波": "osaka/A2701/A270202", "心斎橋": "osaka/A2701/A270201",
    "京都": "kyoto/A2601/A260201", "名古屋": "aichi/A2301/A230101",
    "博多": "fukuoka/A4001/A400101", "札幌": "hokkaido/A0101/A010101",
}


def _get_nearest_area() -> str:
    """Get nearest known area based on IP geolocation."""
    try:
        import math
        resp = Fetcher.get("https://ipinfo.io/json", stealthy_headers=True)
        data = resp.json()
        loc = data.get("loc", "")
        if not loc:
            return ""
        lat, lon = map(float, loc.split(","))
        best_area, best_dist = "", float("inf")
        for area, (a_lat, a_lon) in AREA_COORDS.items():
            dist = math.sqrt((lat - a_lat) ** 2 + (lon - a_lon) ** 2)
            if dist < best_dist:
                best_dist = dist
                best_area = area
        return best_area
    except Exception:
        return ""


@mcp.tool()
def search_restaurants(query: str, location: str = "") -> str:
    """Search nearby restaurants for eating out using Tabelog.
    query: food genre or dish name (e.g. "カレー", "ラーメン", "イタリアン")
    location: area name (e.g. "渋谷", "新宿", "池袋"). If empty, auto-detects nearest area from IP.
    Returns top-rated restaurants with ratings and links.
    """
    from urllib.parse import quote
    if not location:
        location = _get_nearest_area()
    area_path = TABELOG_AREAS.get(location, "")
    if area_path:
        url = f"https://tabelog.com/{area_path}/rstLst/?Srt=D&SrtT=rt&sk={quote(query)}"
    else:
        search_query = f"{location} {query}".strip() if location else query
        url = f"https://tabelog.com/rstLst/?Srt=D&SrtT=rt&sk={quote(search_query)}"
    page = Fetcher.get(url, stealthy_headers=True)

    restaurants = []
    for item in page.css("div.list-rst"):
        names = item.css("a.list-rst__rst-name-target")
        if not names or not names[0].text:
            continue
        name = names[0].text.strip()
        link = names[0].attrib.get("href", "")

        ratings = item.css("span.c-rating__val")
        rating = ratings[0].text.strip() if ratings and ratings[0].text else ""

        if name:
            restaurants.append({"name": name, "url": link, "rating": rating})
        if len(restaurants) >= 5:
            break

    if not restaurants:
        tabelog_url = f"https://tabelog.com/rstLst/?sk={quote(query + ' ' + location)}"
        return f"レストラン情報を取得できませんでした。\n食べログで検索: {tabelog_url}"

    area_label = f" ({location})" if location else ""
    result = f"🍽️ 「{query}」のおすすめレストラン{area_label}:\n\n"
    for i, r in enumerate(restaurants, 1):
        result += f"{i}. {r['name']}"
        if r["rating"]:
            result += f"  ⭐{r['rating']}"
        result += "\n"
        if r["url"]:
            result += f"   {r['url']}\n"
        result += "\n"
    return result


@mcp.tool()
def search_ubereats(query: str) -> str:
    """Search for food on Uber Eats for delivery.
    query: food type or dish name (e.g. "カレー", "ピザ", "寿司")
    Returns nearby restaurants with delivery available.
    """
    resp = curl_requests.post(
        "https://www.ubereats.com/api/getSearchSuggestionsV1",
        json={"userQuery": query, "date": "", "startTime": 0, "endTime": 0},
        cookies=_ue_cookies,
        headers=UE_HEADERS,
        impersonate="chrome",
        timeout=15,
    )
    data = resp.json()
    if data.get("status") != "success":
        return f"Uber Eatsで「{query}」の検索に失敗しました。"

    stores = []
    for item in data.get("data", []):
        if item.get("type") != "store":
            continue
        store = item.get("store", {})
        if not store.get("isOrderable"):
            continue
        stores.append({
            "uuid": store["uuid"],
            "name": store.get("title", ""),
            "slug": store.get("slug", ""),
        })
        if len(stores) >= 5:
            break

    if not stores:
        return f"「{query}」で注文可能な店舗が見つかりませんでした。"

    result = f"🛵 Uber Eats「{query}」の検索結果:\n\n"
    for i, s in enumerate(stores, 1):
        url = f"https://www.ubereats.com/jp/store/{s['slug']}/{s['uuid']}"
        result += f"{i}. {s['name']}\n   {url}\n\n"
    return result


@mcp.tool()
def get_ubereats_menu(store_uuid: str) -> str:
    """Get the menu of an Uber Eats store.
    store_uuid: the UUID of the store (from search_ubereats results).
    Returns menu items with names, prices, and order links.
    """
    resp = curl_requests.post(
        "https://www.ubereats.com/api/getStoreV1",
        json={"storeUuid": store_uuid},
        cookies=_ue_cookies,
        headers=UE_HEADERS,
        impersonate="chrome",
        timeout=15,
    )
    data = resp.json()
    if data.get("status") != "success":
        return "メニューの取得に失敗しました。"

    store_data = data["data"]
    store_name = store_data.get("title", "")
    slug = store_data.get("slug", "")
    catalog = store_data.get("catalogSectionsMap", {})

    seen = set()
    menu_items = []
    for sec_items in catalog.values():
        for item in sec_items:
            sip = item.get("payload", {}).get("standardItemsPayload", {})
            section_title = sip.get("title", {}).get("text", "") if isinstance(sip.get("title"), dict) else str(sip.get("title", ""))
            for ci in sip.get("catalogItems", []):
                uid = ci.get("uuid", "")
                if uid in seen:
                    continue
                seen.add(uid)
                price = ci.get("price", 0)
                price_str = f"¥{price // 100:,}" if price else ""
                menu_items.append({
                    "title": ci.get("title", ""),
                    "price": price_str,
                    "uuid": uid,
                    "section": section_title,
                })
            if len(menu_items) >= 15:
                break
        if len(menu_items) >= 15:
            break

    if not menu_items:
        return f"{store_name}のメニューが見つかりませんでした。"

    result = f"📋 {store_name} のメニュー:\n\n"
    current_section = ""
    for item in menu_items:
        if item["section"] and item["section"] != current_section:
            current_section = item["section"]
            result += f"--- {current_section} ---\n"
        result += f"  • {item['title']}"
        if item["price"]:
            result += f"  {item['price']}"
        order_url = f"https://www.ubereats.com/jp/store/{slug}/{store_uuid}?mod={item['uuid']}"
        result += f"\n    注文: {order_url}\n"
    return result


if __name__ == "__main__":
    mcp.run(transport="stdio")
