"""
Search URLs configuration for Rightmove scraper

Add your search URLs here. The scraper will process all URLs in one run.
"""

SEARCH_URLS = [
    # Chelmsford - Detached/Semi/Terraced, 3+ beds, max £280k
    {
        "url": "https://www.rightmove.co.uk/property-for-sale/find.html?useLocationIdentifier=true&locationIdentifier=REGION%5E1263&radius=0.0&maxPrice=400000&minBedrooms=3&_includeSSTC=on&includeSSTC=true&tenureTypes=FREEHOLD%2CLEASEHOLD&sortType=6&channel=BUY&transactionType=BUY&displayLocationIdentifier=Stevenage.html&dontShow=retirement%2CsharedOwnership&propertyTypes=detached%2Csemi-detached%2Cterraced%2Cbungalow%2Cpark-home&index=0",
        "enabled": False,
        "description": "Stevenage - Detached/Semi/Terraced, 3+ beds, max £400k"
    },

    {
        "url": "https://www.rightmove.co.uk/property-for-sale/find.html?useLocationIdentifier=true&locationIdentifier=REGION%5E1474&radius=0.0&maxPrice=400000&minBedrooms=3&_includeSSTC=on&includeSSTC=true&tenureTypes=FREEHOLD%2CLEASEHOLD&sortType=6&channel=BUY&transactionType=BUY&displayLocationIdentifier=Woking.html&dontShow=retirement%2CsharedOwnership&propertyTypes=detached%2Csemi-detached%2Cterraced%2Cbungalow%2Cpark-home&index=0",
        "enabled": False,
        "description": "Woking - Detached/Semi/Terraced, 3+ beds, max £400k"
    },

    {
        "url": "https://www.rightmove.co.uk/property-for-sale/find.html?searchLocation=Reading%2C+Berkshire&useLocationIdentifier=true&locationIdentifier=REGION%5E1114&radius=0.0&maxPrice=400000&minBedrooms=3&_includeSSTC=on&includeSSTC=true&tenureTypes=FREEHOLD%2CLEASEHOLD&sortType=6&channel=BUY&transactionType=BUY&displayLocationIdentifier=Reading.html&dontShow=retirement%2CsharedOwnership&propertyTypes=detached%2Csemi-detached%2Cterraced%2Cbungalow%2Cpark-home",
        "enabled": True,
        "description": "Reading - Detached/Semi/Terraced, 3+ beds, max 400"
    },

    {
        "url": "https://www.rightmove.co.uk/property-for-sale/find.html?useLocationIdentifier=true&locationIdentifier=REGION%5E488&radius=0.0&maxPrice=450000&minBedrooms=3&_includeSSTC=on&includeSSTC=true&tenureTypes=FREEHOLD%2CLEASEHOLD&sortType=6&channel=BUY&transactionType=BUY&displayLocationIdentifier=Epsom.html&dontShow=retirement%2CsharedOwnership&propertyTypes=detached%2Csemi-detached%2Cterraced%2Cbungalow%2Cpark-home&index=0",
        "enabled": False,
        "description": "Epsom - Detached/Semi/Terraced, 3+ beds, max £450k"
    },

    {
        "url": "https://www.rightmove.co.uk/property-for-sale/find.html?useLocationIdentifier=true&locationIdentifier=REGION%5E580&radius=0.0&maxPrice=400000&minBedrooms=3&_includeSSTC=on&includeSSTC=true&tenureTypes=FREEHOLD%2CLEASEHOLD&sortType=6&channel=BUY&transactionType=BUY&displayLocationIdentifier=Guildford.html&dontShow=retirement%2CsharedOwnership&propertyTypes=detached%2Csemi-detached%2Cterraced%2Cbungalow%2Cpark-home&index=0",
        "enabled": False,
        "description": "Guilford - Detached/Semi/Terraced, 3+ beds, max £400k"
    },

    {
        "url": "https://www.rightmove.co.uk/property-for-sale/find.html?useLocationIdentifier=true&locationIdentifier=REGION%5E307&radius=0.0&maxPrice=400000&minBedrooms=3&_includeSSTC=on&includeSSTC=true&tenureTypes=FREEHOLD%2CLEASEHOLD&sortType=6&channel=BUY&transactionType=BUY&displayLocationIdentifier=Chelmsford.html&dontShow=retirement%2CsharedOwnership&propertyTypes=detached%2Csemi-detached%2Cterraced%2Cbungalow%2Cpark-home",
        "enabled": False,
        "description": "Chelmsford - Detached/Semi/Terraced, 3+ beds, max £400k"
    }

    # Add more search URLs here
    # Example:
    # {
    #     "url": "https://www.rightmove.co.uk/property-for-sale/find.html?...",
    #     "enabled": True,
    #     "description": "Epsom - 2+ beds, max £400k"
    # },
]

# Configuration
PAGE_SIZE = 24
MAX_PAGES = 50  # Maximum pages to scrape per search URL


def get_enabled_urls():
    """Get all enabled search URLs"""
    return [search for search in SEARCH_URLS if search.get("enabled", True)]


def get_url_count():
    """Get count of enabled search URLs"""
    return len(get_enabled_urls())
