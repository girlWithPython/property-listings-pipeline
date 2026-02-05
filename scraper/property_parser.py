from datetime import datetime
from scraper.utils import accept_cookies
import re
import os


def parse_address(address_str: str) -> dict:
    """
    Parse address string into components

    IMPORTANT: Only extracts FULL UK postcodes (e.g., "CM3 1NZ", "SW1A 2AA")
    Partial postcodes (e.g., "KT19", "CM3") are ignored and left as NULL
    These will be filled in later by reverse geocoding from coordinates

    Example input: "Wandle Court, West Ewell, Epsom, KT19"
    Returns: {
        "line1": "Wandle Court",
        "postcode": None  # KT19 is partial, not full
    }

    Example input: "123 High Street, Chelmsford, CM3 1NZ"
    Returns: {
        "line1": "123 High Street",
        "postcode": "CM3 1NZ"  # Full postcode accepted
    }
    """
    if not address_str:
        return {"line1": None, "postcode": None}

    parts = [p.strip() for p in address_str.split(',')]

    # Only accept FULL UK postcodes with inward code (digit + 2 letters at end)
    # Format: AA9A 9AA, A9A 9AA, A9 9AA, A99 9AA, AA9 9AA, AA99 9AA
    # Examples: CM3 1NZ, SW1A 2AA, W1 2AB, EC1A 1BB
    # Rejects partial: CM3, KT19, SW1A
    postcode = None
    full_postcode_pattern = r'^[A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2}$'

    if len(parts) > 0:
        # Check last part for FULL postcode
        last_part = parts[-1].strip()
        if re.match(full_postcode_pattern, last_part, re.IGNORECASE):
            postcode = last_part
            parts = parts[:-1]
        # If partial postcode detected, leave as None for reverse geocoding

    # First part is line1 (street/building)
    line1 = parts[0] if len(parts) > 0 else None

    return {
        "line1": line1,
        "postcode": postcode
    }




async def extract_property_details(page, url):
    """
    Given a property URL, extract key info and full-size images
    """
    await page.goto(url, wait_until="domcontentloaded")
    await accept_cookies(page)

    # Wait for page to fully load
    await page.wait_for_timeout(2000)

    data = {
        "url": url,
        "property_id": url.split("/properties/")[1].split("/")[0],
        "timestamp": datetime.utcnow(),  # Keep as datetime object, not string
    }

    async def get_text(selectors_list):
        """Try multiple selectors and return the first match"""
        if isinstance(selectors_list, str):
            selectors_list = [selectors_list]

        for selector in selectors_list:
            try:
                el = await page.query_selector(selector)
                if el:
                    text = await el.inner_text()
                    if text and text.strip():
                        return text.strip()
            except Exception as e:
                print(f"Error with selector '{selector}': {e}")
                continue

        print(f"No match found for selectors: {selectors_list}")
        return None

    # 1. Price - try multiple possible selectors
    price_text = await get_text([
        'div[data-testid="primaryPrice"] span',
        'div[data-testid="price"]',
        'span._1gfnqJ3Vtd1z40MlC0MzXu span',
        'div._1gfnqJ3Vtd1z40MlC0MzXu span'
    ])

    # Parse price to integer (remove £ and commas)
    def parse_price(price_str):
        """Convert price string like '£300,000' to integer 300000"""
        if not price_str:
            return None
        try:
            # Remove £ sign, commas, and any whitespace
            clean_price = price_str.replace('£', '').replace(',', '').strip()
            # Convert to integer
            return int(clean_price)
        except (ValueError, AttributeError):
            print(f"[WARNING] Could not parse price: {price_str}")
            return None

    data["price"] = parse_price(price_text)
    data["price_text"] = price_text  # Keep original text for reference

    # 1b. Price qualifier (offer type) from PAGE_MODEL
    async def get_price_qualifier():
        """Extract price qualifier (e.g., 'Offers in Region of', 'Guide Price', etc.)"""
        try:
            qualifier_script = """
            () => {
                if (window.PAGE_MODEL && window.PAGE_MODEL.propertyData && window.PAGE_MODEL.propertyData.prices) {
                    return window.PAGE_MODEL.propertyData.prices.displayPriceQualifier || null;
                }
                return null;
            }
            """
            qualifier = await page.evaluate(qualifier_script)
            if qualifier and qualifier.strip():
                print(f"[DEBUG] Price qualifier found: {qualifier}")
                return qualifier.strip()
            return None
        except Exception as e:
            print(f"[WARNING] Failed to extract price qualifier: {e}")
            return None

    data["price_qualifier"] = await get_price_qualifier()

    # 2. Address - try multiple possible selectors
    full_address = await get_text([
        'h1[itemprop="streetAddress"]',
        'h1._2uQQ3SV0eMHL1P6t5ZDo2q',
        'h1[data-testid="address"]',
        'div[itemprop="address"] h1'
    ])

    data["full_address"] = full_address
    data["address_parts"] = parse_address(full_address)

    # 7. Coordinates from PAGE_MODEL JSON
    async def get_coordinates():
        """Extract latitude and longitude from window.PAGE_MODEL JavaScript object"""
        try:
            # Extract coordinates from the PAGE_MODEL JavaScript object
            coords_script = """
            () => {
                if (window.PAGE_MODEL && window.PAGE_MODEL.propertyData && window.PAGE_MODEL.propertyData.location) {
                    return {
                        latitude: window.PAGE_MODEL.propertyData.location.latitude,
                        longitude: window.PAGE_MODEL.propertyData.location.longitude
                    };
                }
                return null;
            }
            """

            coords = await page.evaluate(coords_script)

            if coords and coords.get('latitude') and coords.get('longitude'):
                latitude = float(coords['latitude'])
                longitude = float(coords['longitude'])
                print(f"[DEBUG] Coordinates found: {latitude}, {longitude}")
                return {
                    "latitude": latitude,
                    "longitude": longitude
                }
            else:
                print("[DEBUG] Coordinates not found in PAGE_MODEL.propertyData.location")
                return {"latitude": None, "longitude": None}

        except Exception as e:
            print(f"[WARNING] Failed to extract coordinates: {e}")
            import traceback
            traceback.print_exc()
            return {"latitude": None, "longitude": None}

    data["coordinates"] = await get_coordinates()

    # 3. Bedrooms - try multiple possible selectors
    data["bedrooms"] = await get_text([
        'span[data-testid="info-reel-BEDROOMS-text"] p',
        'span[data-testid="info-reel-BEDROOMS-text"]',
        'dd:has(svg[data-testid="svg-bed"]) span p',
        'span[data-testid="beds"]'
    ])

    # 4. Property type - try multiple possible selectors
    data["property_type"] = await get_text([
        'span[data-testid="info-reel-PROPERTY_TYPE-text"] p',
        'span[data-testid="info-reel-PROPERTY_TYPE-text"]',
        'li[data-testid="property-type"]'
    ])

    # 5. Description - try multiple possible selectors
    data["description"] = await get_text([
        'div.STw8udCxUaBUMfOOZu0iL',
        'div._3nPVwR0HZYQah5tkVJHFh5',
        'div[data-testid="description"]',
        'div.OD0O7FWw1TjbTD4sdRi1_ div.STw8udCxUaBUMfOOZu0iL'
    ])

    # 6. Property status (SOLD STC, UNDER OFFER, etc.)
    async def get_status():
        """Check multiple patterns for property status"""
        # Try common selectors for small elements first
        selectors = [
            'span[data-test="soldLabel"]',
            'div[data-test="soldLabel"]',
            'span.soldLabel',
            'div.soldLabel',
            'span[class*="sold"]',
            'div[class*="sold"]',
            'span[class*="STC"]',
            'div[class*="STC"]',
            '*[class*="propertyStatus"]',
            '*[data-testid*="status"]',
        ]

        for selector in selectors:
            try:
                elements = await page.query_selector_all(selector)
                for el in elements:
                    text = await el.inner_text()
                    if text and text.strip():
                        text = text.strip()
                        # Only accept short text (< 100 chars) to avoid capturing large sections
                        if len(text) < 100 and any(keyword in text.upper() for keyword in ['SOLD', 'STC', 'UNDER OFFER', 'LET AGREED', 'RESERVED']):
                            print(f"[DEBUG] Found status '{text}' with selector: {selector}")
                            return text
            except Exception:
                continue

        # If not found, search all small text elements
        try:
            all_elements = await page.query_selector_all('span, div, p, h1, h2, h3')
            for el in all_elements:
                try:
                    text = await el.inner_text()
                    if text:
                        text = text.strip()
                        # Look for exact matches of status keywords in short text
                        if len(text) <= 50:  # Only check small elements
                            if text.upper() in ['SOLD STC', 'SOLD', 'UNDER OFFER', 'LET AGREED', 'RESERVED', 'SSTC']:
                                print(f"[DEBUG] Found exact status match: {text}")
                                return text
                except Exception:
                    continue
        except Exception:
            pass

        return None

    data["status"] = await get_status()

    # 7. Bathrooms
    data["bathrooms"] = await get_text([
        'span[data-testid="info-reel-BATHROOMS-text"] p',
        'span[data-testid="info-reel-BATHROOMS-text"]',
        'dd:has(svg[data-testid="svg-bathroom"]) span p',
    ])

    # 8. Added on date
    async def get_added_on():
        """Extract 'Added on' date"""
        try:
            # Search all elements for "Added on" text
            elements = await page.query_selector_all('div, p, span')
            for el in elements:
                try:
                    text = await el.inner_text()
                    if text and 'added on' in text.lower():
                        # Extract date from "Added on 22/01/2026"
                        date_match = re.search(r'added on (\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
                        if date_match:
                            date_str = date_match.group(1)
                            print(f"[DEBUG] Added on date found: {date_str}")
                            return date_str
                except Exception:
                    continue
        except Exception as e:
            print(f"[DEBUG] Could not extract 'Added on' date: {e}")
        return None

    data["added_on"] = await get_added_on()

    # 9. Reduced on date
    async def get_reduced_on():
        """Extract 'Reduced on' date"""
        try:
            # Search all elements for "Reduced on" text
            elements = await page.query_selector_all('div, p, span')
            for el in elements:
                try:
                    text = await el.inner_text()
                    if text and 'reduced on' in text.lower():
                        # Extract date from "Reduced on 22/01/2026"
                        date_match = re.search(r'reduced on (\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
                        if date_match:
                            date_str = date_match.group(1)
                            print(f"[DEBUG] Reduced on date found: {date_str}")
                            return date_str
                except Exception:
                    continue
        except Exception as e:
            print(f"[DEBUG] Could not extract 'Reduced on' date: {e}")
        return None

    data["reduced_on"] = await get_reduced_on()

    # 10. Property size (sq ft or sq m)
    async def get_size():
        """Extract property size as integer (numeric value only)"""
        try:
            # Search all elements for size information
            elements = await page.query_selector_all('dt, dd, p, span, div')
            for el in elements:
                try:
                    text = await el.inner_text()
                    if not text:
                        continue

                    text = text.strip()

                    # Look for patterns like "1,200 sq ft", "120 m²", "100 sq m"
                    if len(text) < 100:  # Avoid large text blocks
                        # Match patterns with numbers and size units
                        size_match = re.search(r'(\d+[,\s]*\d*)\s*(sq\s*ft|sq\s*m|m²|sqft|sqm)', text, re.IGNORECASE)
                        if size_match:
                            # Extract numeric part and remove commas/spaces
                            size_str = size_match.group(1).replace(',', '').replace(' ', '')
                            size_int = int(size_str)
                            print(f"[DEBUG] Property size found: {size_int} (from '{text.strip()}')")
                            return size_int
                except Exception:
                    continue
        except Exception as e:
            print(f"[DEBUG] Could not extract size: {e}")
        return None

    data["size"] = await get_size()

    # 11. Tenure (Freehold/Leasehold)
    async def get_tenure():
        """Extract tenure information"""
        try:
            # Search all elements for tenure information
            elements = await page.query_selector_all('dt, dd, p, span, div')
            for el in elements:
                try:
                    text = await el.inner_text()
                    if not text:
                        continue

                    text = text.strip()

                    # Look for TENURE label or direct mentions
                    if 'tenure' in text.lower() or len(text) < 30:
                        # Check for Freehold or Leasehold
                        if 'freehold' in text.lower():
                            print(f"[DEBUG] Tenure: Freehold")
                            return 'Freehold'
                        elif 'leasehold' in text.lower():
                            print(f"[DEBUG] Tenure: Leasehold")
                            return 'Leasehold'
                except Exception:
                    continue
        except Exception as e:
            print(f"[DEBUG] Could not extract tenure: {e}")
        return None

    data["tenure"] = await get_tenure()

    # 12. Council tax band
    async def get_council_tax_band():
        """Extract council tax band (A-H)"""
        try:
            # Strategy 1: Look for specific dt/dd pairs with COUNCIL TAX
            council_elements = await page.query_selector_all('dt, dd, p, span, div')

            for el in council_elements:
                try:
                    text = await el.inner_text()
                    if not text:
                        continue

                    text = text.strip()

                    # Look for council tax band patterns
                    # Matches: "Band A", "Band: D", "Tax Band B", "Council Tax Band C", etc.
                    if 'council' in text.lower() and 'tax' in text.lower() and 'band' in text.lower():
                        # Extract band letter (with optional colon)
                        band_match = re.search(r'band\s*:?\s*([A-H])', text, re.IGNORECASE)
                        if band_match:
                            band = band_match.group(1).upper()
                            print(f"[DEBUG] Council tax band found: {band}")
                            return band

                    # Also check for standalone "Band X" or "Band: X" near council tax labels
                    elif 'band' in text.lower() and len(text) < 20:
                        # Short text like "Band A", "Band: D" or just "A"
                        band_match = re.search(r'band\s*:?\s*([A-H])|^([A-H])$', text, re.IGNORECASE)
                        if band_match:
                            band = (band_match.group(1) or band_match.group(2)).upper()
                            # Verify this is near council tax by checking nearby elements
                            parent = await el.evaluate_handle('el => el.parentElement')
                            if parent:
                                parent_text = await parent.inner_text()
                                if 'council' in parent_text.lower():
                                    print(f"[DEBUG] Council tax band found (parent check): {band}")
                                    return band

                except Exception:
                    continue

            # Strategy 2: Use JavaScript to search PAGE_MODEL
            try:
                council_script = """
                () => {
                    // Check if council tax band is in the page model
                    if (window.PAGE_MODEL && window.PAGE_MODEL.propertyData) {
                        const data = window.PAGE_MODEL.propertyData;

                        // Check various possible locations
                        if (data.councilTaxBand) return data.councilTaxBand;
                        if (data.keyFeatures) {
                            for (const feature of data.keyFeatures) {
                                const match = feature.match(/council.*tax.*band\s*([A-H])/i);
                                if (match) return match[1];
                            }
                        }
                    }

                    // Search all text content for council tax band
                    const allText = document.body.innerText;
                    const match = allText.match(/council.*tax.*band\s*([A-H])/i);
                    if (match) return match[1];

                    return null;
                }
                """
                band = await page.evaluate(council_script)
                if band:
                    band = band.upper()
                    print(f"[DEBUG] Council tax band found via JavaScript: {band}")
                    return band
            except Exception as e:
                print(f"[DEBUG] JavaScript council tax extraction failed: {e}")

        except Exception as e:
            print(f"[DEBUG] Could not extract council tax band: {e}")

        return None

    data["council_tax_band"] = await get_council_tax_band()

    # 13. Images (full size only)
    full_images = []

    # Extract images from meta tags with itemprop="contentUrl"
    # These contain all property images regardless of lazy loading
    meta_elements = await page.query_selector_all('meta[itemprop="contentUrl"]')
    print(f"[DEBUG] Found {len(meta_elements)} meta tags with itemprop='contentUrl'")

    for meta in meta_elements:
        url = await meta.get_attribute("content")
        if not url:
            continue

        print(f"[DEBUG] Meta image URL: {url[:80]}...")

        # Accept all images from media.example.co.uk
        # This includes both patterns:
        # - https://media.example.com/id/...
        # - https://media.example.com/id/...
        if "media.example.com" in url and url.endswith(('.jpeg', '.jpg', '.png')):
            full_images.append(url)

    print(f"[DEBUG] Captured {len(full_images)} full images")

    # Deduplicate while preserving order
    unique_full_images = list(dict.fromkeys(full_images))

    data["images"] = {
        "count": len(unique_full_images),
        "full": unique_full_images,
    }

    return data
