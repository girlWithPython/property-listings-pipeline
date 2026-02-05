import asyncio
from playwright.async_api import async_playwright
from urllib.parse import parse_qs, urlparse
from scraper.utils import accept_cookies
from scraper.property_parser import extract_property_details
from scraper.search_urls import get_enabled_urls, get_url_count, PAGE_SIZE, MAX_PAGES
from db.database import DatabaseConnector
from db.config import DB_CONFIG

# Browser restart configuration
# Restart browser every N properties to prevent memory exhaustion
BROWSER_RESTART_INTERVAL = 75  # Restart after processing this many properties


def extract_town_from_url(url: str) -> str:
    """
    Extract town name from the third-party property listing portal search URL
    """
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        # Try to get displayLocationIdentifier parameter
        if 'displayLocationIdentifier' in params:
            town = params['displayLocationIdentifier'][0]
            # Remove .html suffix if present
            if town.endswith('.html'):
                town = town[:-5]
            return town

        # Fallback: try to get from locationIdentifier
        if 'locationIdentifier' in params:
            location_id = params['locationIdentifier'][0]
            # Extract town name from identifier if possible
            return location_id.split('^')[-1] if '^' in location_id else location_id

        # Default if can't extract
        return "Unknown"
    except Exception as e:
        print(f"[WARNING] Failed to extract town from URL: {e}")
        return "Unknown"


async def collect_property_links(page, base_url, page_size=24, max_pages=50):
    """
    Collect all property links from search results

    Args:
        page: Playwright page object
        base_url: Base search URL
        page_size: Number of results per page
        max_pages: Maximum number of pages to scrape
    """
    property_links = set()

    # Remove existing index parameter from base URL to avoid duplicates
    if '&index=' in base_url or '?index=' in base_url:
        # Split on index parameter and take everything before it
        base_url = base_url.split('&index=')[0].split('?index=')[0]

    for page_num in range(max_pages):
        offset = page_num * page_size
        page_url = f"{base_url}&index={offset}"

        print(f"  [Page {page_num + 1}] Scraping search results (index={offset})")
        await page.goto(page_url, wait_until="domcontentloaded")

        if page_num == 0:
            await accept_cookies(page)

        # Wait for DOM to settle (increased for headless mode)
        await page.wait_for_timeout(3000)

        # Try to wait for search results to load
        try:
            await page.wait_for_selector('.propertyCard-wrapper, .propertyCard', timeout=5000)
        except:
            print(f"  [Page {page_num + 1}] Warning: propertyCard selector not found, continuing anyway...")

        links = await page.query_selector_all('a[href^="/properties/"]')

        if not links:
            print(f"  [Page {page_num + 1}] No property links found. Ending pagination.")
            break

        before = len(property_links)

        for link in links:
            href = await link.get_attribute("href")
            if not href:
                continue

            if "/properties/" in href:
                clean = href.split("#")[0].split("?")[0]
                property_links.add("https://www.example.com" + clean)

        after = len(property_links)
        print(f"  [Page {page_num + 1}] New properties found: {after - before}")

        # If this page produced nothing new → stop
        if after == before:
            print(f"  [Page {page_num + 1}] No new properties. Pagination complete.")
            break

    return list(property_links)


async def scrape_search_url(page, db, search_config, search_num, total_searches, browser=None, playwright_instance=None):
    """
    Scrape a single search URL

    Args:
        page: Playwright page object
        db: Database connector
        search_config: Search configuration dict
        search_num: Current search number (1-indexed)
        total_searches: Total number of searches
        browser: Browser instance (for restart capability)
        playwright_instance: Playwright instance (for restart capability)
    """
    url = search_config["url"]
    description = search_config.get("description", "No description")

    print("\n" + "=" * 80)
    print(f"SEARCH {search_num}/{total_searches}: {description}")
    print("=" * 80)

    # Extract town from URL
    town_name = extract_town_from_url(url)
    print(f"[INFO] Location: {town_name}")

    # Collect property links
    print(f"[INFO] Collecting property links...")
    property_links = await collect_property_links(page, url, PAGE_SIZE, MAX_PAGES)

    print(f"\n[INFO] Found {len(property_links)} unique properties for this search")

    # Scrape each property
    results = []
    inserted_count = 0
    skipped_count = 0
    error_count = 0

    for i, prop_url in enumerate(property_links, 1):
        # Browser restart logic - restart every N properties to prevent memory exhaustion
        if browser and playwright_instance and i > 1 and (i - 1) % BROWSER_RESTART_INTERVAL == 0:
            print(f"\n[BROWSER RESTART] Restarting browser after {i-1} properties (memory management)")
            try:
                await page.close()
                await browser.close()
                browser = await playwright_instance.chromium.launch(headless=True)
                page = await browser.new_page()
                print("[BROWSER RESTART] Browser restarted successfully")
            except Exception as e:
                print(f"[WARNING] Browser restart failed: {e}, continuing with existing browser")

        print(f"\n[{i}/{len(property_links)}] Extracting: {prop_url}")
        try:
            data = await extract_property_details(page, prop_url)
            results.append(data)

            # Save to database
            success, status = await db.insert_property(data, town_name)
            if success:
                if status == 'inserted':
                    inserted_count += 1
                    print(f"  [OK] New snapshot saved: {data.get('property_id')}")
                elif status == 'skipped':
                    skipped_count += 1
                    print(f"  [SKIP] No changes: {data.get('property_id')}")

                # Emit task to download and store images if available
                if data.get('images') and data['images'].get('full'):
                    image_urls = data['images']['full']
                    try:
                        from workers.image_tasks import download_property_images
                        task = download_property_images.delay(
                            property_id=data['property_id'],
                            image_urls=image_urls
                        )
                        print(f"  [IMAGES] Queued {len(image_urls)} images for processing (Task: {task.id})")
                    except Exception as e:
                        print(f"  [WARNING] Failed to queue image task: {e}")
            else:
                error_count += 1
                print(f"  [ERROR] Failed to save: {data.get('property_id')}")

        except Exception as e:
            print(f"  [ERROR] Failed to extract property: {e}")
            error_count += 1

    # Summary for this search
    print("\n" + "-" * 80)
    print(f"SEARCH {search_num} COMPLETE: {description}")
    print("-" * 80)
    print(f"  • Properties found: {len(property_links)}")
    print(f"  • New snapshots: {inserted_count}")
    print(f"  • Skipped (no changes): {skipped_count}")
    print(f"  • Errors: {error_count}")
    print("-" * 80)

    return {
        "description": description,
        "town": town_name,
        "found": len(property_links),
        "inserted": inserted_count,
        "skipped": skipped_count,
        "errors": error_count,
        "page": page,  # Return updated page reference
        "browser": browser  # Return updated browser reference
    }


async def main():
    """Main scraper function - processes all enabled search URLs"""

    # Get enabled search URLs
    search_configs = get_enabled_urls()
    total_searches = len(search_configs)

    if total_searches == 0:
        print("[ERROR] No enabled search URLs found!")
        print("Please add search URLs to scraper/search_urls.py")
        return

    print("\n" + "=" * 80)
    print("SCRAPER - MULTI-URL MODE")
    print("=" * 80)
    print(f"Total search URLs to process: {total_searches}")
    for i, config in enumerate(search_configs, 1):
        print(f"  {i}. {config.get('description', 'No description')}")
    print("=" * 80)

    # Initialize database connection
    db = DatabaseConnector()
    try:
        await db.connect(**DB_CONFIG)
        await db.init_schema()
        print("[OK] Database connected")
    except Exception as e:
        print(f"[ERROR] Failed to connect to database: {e}")
        print("  Please ensure PostgreSQL is running and credentials are correct.")
        print("  You can set credentials in db/config.py or via environment variables.")
        return

    # Initialize browser
    async with async_playwright() as p:
        # Use headless mode when running in Docker/worker environment
        # headless=True is required for running in containers without display
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Process each search URL
        results = []
        for i, search_config in enumerate(search_configs, 1):
            result = await scrape_search_url(
                page, db, search_config, i, total_searches,
                browser=browser, playwright_instance=p
            )
            # Update browser and page references (may have been restarted during scraping)
            page = result.get("page", page)
            browser = result.get("browser", browser)
            results.append(result)

        await browser.close()

    # Final summary
    print("\n" + "=" * 80)
    print("SCRAPING COMPLETE - ALL SEARCHES PROCESSED")
    print("=" * 80)

    total_found = sum(r["found"] for r in results)
    total_inserted = sum(r["inserted"] for r in results)
    total_skipped = sum(r["skipped"] for r in results)
    total_errors = sum(r["errors"] for r in results)

    print("\nSummary by Search:")
    for i, result in enumerate(results, 1):
        print(f"\n  {i}. {result['description']} ({result['town']})")
        print(f"     Found: {result['found']} | Inserted: {result['inserted']} | Skipped: {result['skipped']} | Errors: {result['errors']}")

    print("\n" + "-" * 80)
    print("TOTALS:")
    print(f"  • Total properties found: {total_found}")
    print(f"  • New snapshots created: {total_inserted}")
    print(f"  • Skipped (no changes): {total_skipped}")
    print(f"  • Errors: {total_errors}")
    print("-" * 80)

    # Show database stats
    stats = await db.get_stats()
    print(f"\nDatabase Statistics:")
    print(f"  • Total snapshots: {stats['total_snapshots']}")
    print(f"  • Unique properties: {stats['unique_properties']}")
    print(f"  • Average price: {stats['average_price']}")
    print(f"  • Properties with price changes: {stats['properties_with_price_changes']}")
    print("=" * 80)

    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
