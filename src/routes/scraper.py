from flask import Blueprint, jsonify, request
import requests
from bs4 import BeautifulSoup
import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

scraper_bp = Blueprint("scraper", __name__)

@scraper_bp.route("/scan", methods=["GET"])
def scan_marketplaces():
    """Scan marketplaces for electronics under specified price"""
    max_price = request.args.get("max_price", 25, type=int)
    location = request.args.get("location", "Murcia")

    results = []

    # Wallapop search
    try:
        wallapop_results = scan_wallapop(location, max_price)
        results.extend(wallapop_results)
    except Exception as e:
        print(f"Error scanning Wallapop: {e}")

    return jsonify({
        "success": True,
        "results": results,
        "total_found": len(results)
    })

def scan_wallapop(location, max_price):
    """Scan Wallapop for electronics under max_price using Selenium"""
    results = []

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    # Use ChromeDriverManager to automatically download and manage chromedriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # Wallapop search URL for electronics
    # Note: Wallapop's search parameters are complex, direct URL might not work for all filters
    # We will navigate and then try to input search terms if needed, or rely on broad category search
    search_url = f"https://es.wallapop.com/app/search?keywords=electronics&latitude=37.9838&longitude=-1.1297&max_sale_price={max_price}"

    try:
        driver.get(search_url)

        # Wait for the page to load and elements to be present
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".item-card")) # Adjust selector as needed
        )

        # Scroll down to load more content (optional, but good for more results)
        last_height = driver.execute_script("return document.body.scrollHeight")
        for _ in range(3): # Scroll 3 times
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2) # Wait for new content to load
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Find items. This selector is a placeholder and needs to be accurate for Wallapop.
        # You'll need to inspect Wallapop's HTML to find the correct class/element for listings.
        # Example: items = soup.find_all("div", class_="item-card")
        items = soup.find_all("div", class_=lambda x: x and ("item-card" in x or "CardItem-module__item___" in x)) # More robust selector

        for item in items[:20]:  # Limit to first 20 items for testing
            try:
                title_elem = item.find("p", class_=lambda x: x and ("item-title" in x or "CardItem-module__title___" in x)) or item.find("a")
                price_elem = item.find("span", class_=lambda x: x and ("item-price" in x or "CardItem-module__price___" in x)) or item.find("div", class_=lambda x: x and ("item-price" in x or "CardItem-module__price___" in x))
                link_elem = item.find("a", href=True)

                if title_elem and price_elem and link_elem:
                    title = title_elem.get_text(strip=True)
                    price_text = price_elem.get_text(strip=True)
                    link = "https://es.wallapop.com" + link_elem["href"]

                    # Extract price number, handling different formats (e.g., 


10,80 €)
                    price_match = re.search(r'(\d+([.,]\d+)?)', price_text)
                    if price_match:
                        price = float(price_match.group(1).replace(',', '.'))

                        if price <= max_price:
                            estimated_resale = estimate_resale_value(title, price)
                            profit_potential = calculate_profit_potential(price, estimated_resale)

                            results.append({
                                "title": title,
                                "price": price,
                                "platform": "Wallapop",
                                "location": location,
                                "link": link,
                                "estimated_resale": estimated_resale,
                                "profit_potential": profit_potential
                            })
            except Exception as e:
                print(f"Error parsing item: {e}")
                continue

    except Exception as e:
        print(f"Error fetching Wallapop data with Selenium: {e}")
    finally:
        driver.quit()

    return results

def estimate_resale_value(title, current_price):
    """Estimate resale value based on item type and current price"""
    title_lower = title.lower()

    # Simple estimation logic based on item type
    if any(word in title_lower for word in ["iphone", "samsung", "smartphone", "móvil"]):
        return current_price * 1.5  # Phones often have good resale
    elif any(word in title_lower for word in ["laptop", "portátil", "macbook"]):
        return current_price * 1.4
    elif any(word in title_lower for word in ["tablet", "ipad"]):
        return current_price * 1.3
    elif any(word in title_lower for word in ["consola", "playstation", "xbox", "nintendo"]):
        return current_price * 1.6
    elif any(word in title_lower for word in ["auriculares", "headphones", "airpods"]):
        return current_price * 1.4
    elif any(word in title_lower for word in ["cargador", "cable", "adaptador"]):
        return current_price * 1.8  # Accessories often have high markup
    elif any(word in title_lower for word in ["libro", "book"]):
        return current_price * 2.0  # Books can have good margins if rare
    else:
        return current_price * 1.3  # Default 30% markup

def calculate_profit_potential(buy_price, estimated_resale):
    """Calculate profit potential percentage"""
    if buy_price == 0:
        return 0
    return ((estimated_resale - buy_price) / buy_price) * 100

@scraper_bp.route("/analyze", methods=["POST"])
def analyze_item():
    """Analyze a specific item for profit potential"""
    data = request.get_json()

    if not data or "title" not in data or "price" not in data:
        return jsonify({"error": "Missing title or price"}), 400

    title = data["title"]
    price = float(data["price"])

    estimated_resale = estimate_resale_value(title, price)
    profit_potential = calculate_profit_potential(price, estimated_resale)

    return jsonify({
        "title": title,
        "buy_price": price,
        "estimated_resale": estimated_resale,
        "profit_potential": profit_potential,
        "recommendation": "BUY" if profit_potential >= 30 else "SKIP"
    })


