
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

SOURCE = "https://www.fastighetsbyran.com/sv/sverige/till-salu?kon=382"
BASE = "https://www.fastighetsbyran.com"
OUTPUT = Path("budgivningar.json")

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; Kontorskampen/1.0)"
})


def get_page(url):
    response = session.get(url, timeout=25)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def is_valid_listing(url):
    parsed = urlparse(url)
    return (
        parsed.netloc == "www.fastighetsbyran.com"
        and "/objekt/" in parsed.path
    )


def get_listing_urls(soup):
    urls = set()
    for link in soup.select("a[href]"):
        url = urljoin(BASE, link["href"]).split("#")[0]
        if is_valid_listing(url):
            urls.add(url)
    return sorted(urls)


def has_active_bidding(soup):
    text = soup.get_text(" ", strip=True).lower()

    # Kräver en tydlig uppgift om pågående budgivning.
    active_patterns = [
        r"\bpågående budgivning\b",
        r"\bbudgivning pågår\b",
        r"\baktiv budgivning\b",
    ]

    return any(re.search(pattern, text) for pattern in active_patterns)


def extract_home(soup, url):
    if not has_active_bidding(soup):
        return None

    heading = soup.find("h1")
    address = heading.get_text(" ", strip=True) if heading else "Bostad"

    image = ""
    image_tag = soup.find("meta", property="og:image")
    if image_tag:
        image = image_tag.get("content", "")

    return {
        "adress": address,
        "omrade": "",
        "aktuelltBud": "",
        "bild": urljoin(BASE, image) if image else "",
        "url": url,
    }


def main():
    try:
        soup = get_page(SOURCE)
        urls = get_listing_urls(soup)
        print(f"Hittade {len(urls)} annonslänkar.")

        if not urls:
            raise RuntimeError(
                "Inga annonslänkar hittades. Kontrollera sidans struktur."
            )

        homes = []

        for url in urls:
            try:
                detail = get_page(url)
                home = extract_home(detail, url)

                if home:
                    homes.append(home)
                    print(f"Aktiv budgivning: {home['adress']}")

            except requests.RequestException as error:
                print(f"Kunde inte läsa {url}: {error}")

        result = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "budgivningar": homes,
        }

        OUTPUT.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print(f"Sparade {len(homes)} verifierade budgivningar.")

    except Exception as error:
        print(f"Insamlingen misslyckades: {error}")
        raise


if __name__ == "__main__":
    main()
