import asyncpg
from typing import Dict, Optional
import uuid


class DatabaseConnector:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "scraper",
        user: str = "postgres",
        password: str = "12345"
    ):
        """Create a connection pool to PostgreSQL"""
        self.pool = await asyncpg.create_pool(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            min_size=1,
            max_size=10,
            ssl=False  # Disable SSL requirement for local connections
        )
        print(f"[OK] Connected to PostgreSQL database: {database}")

    async def disconnect(self):
        """Close the connection pool"""
        if self.pool:
            await self.pool.close()
            print("[OK] Disconnected from database")

    async def init_schema(self):
        """Create the properties, towns, offer_types, and hierarchical places tables if they don't exist"""
        async with self.pool.acquire() as conn:
            # Create towns table first (referenced by properties - kept for backward compatibility)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS towns (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create offer_types table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS offer_types (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create property_types table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS property_types (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create statuses table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS statuses (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(200) UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create tenure_types table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS tenure_types (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(50) UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create counties table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS counties (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create postcodes table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS postcodes (
                    id SERIAL PRIMARY KEY,
                    postcode VARCHAR(20) UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create hierarchical places table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS places (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    place_type TEXT NOT NULL CHECK (
                        place_type IN ('county', 'town', 'locality', 'postcode')
                    ),
                    parent_id INTEGER REFERENCES places(id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(name, place_type, parent_id)
                )
            """)

            # Create addresses table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS addresses (
                    id SERIAL PRIMARY KEY,
                    building TEXT,
                    street TEXT,
                    place_id INTEGER REFERENCES places(id),
                    postcode_id INTEGER REFERENCES postcodes(id),
                    display_address TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(building, place_id, postcode_id)
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS properties (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    property_id VARCHAR(50) NOT NULL,
                    town_id INTEGER REFERENCES towns(id),
                    offer_type_id INTEGER REFERENCES offer_types(id),
                    property_type_id INTEGER REFERENCES property_types(id),
                    status_id INTEGER REFERENCES statuses(id),
                    county_id INTEGER REFERENCES counties(id),
                    address_id INTEGER REFERENCES addresses(id),
                    postcode_id INTEGER REFERENCES postcodes(id),
                    url TEXT NOT NULL,
                    price BIGINT,
                    address_line1 TEXT,
                    locality VARCHAR(100),
                    full_address TEXT,
                    latitude DECIMAL(10, 7),
                    longitude DECIMAL(10, 7),
                    bedrooms VARCHAR(20),
                    bathrooms VARCHAR(20),
                    description TEXT,
                    added_on VARCHAR(20),
                    reduced_on VARCHAR(20),
                    size INTEGER,
                    tenure_id INTEGER REFERENCES tenure_types(id),
                    council_tax_band VARCHAR(10),
                    minio_images JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indices for faster queries
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_properties_property_id
                ON properties(property_id)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_properties_town_id
                ON properties(town_id)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_properties_created_at
                ON properties(created_at)
            """)

            # Create spatial index for coordinates (useful for proximity searches)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_properties_coordinates
                ON properties(latitude, longitude)
            """)

            # Create index for address_id
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_properties_address_id
                ON properties(address_id)
            """)

            # Create index for postcode_id
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_properties_postcode_id
                ON properties(postcode_id)
            """)

            # Create indices for property_type_id, status_id, and county_id
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_properties_property_type_id
                ON properties(property_type_id)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_properties_status_id
                ON properties(status_id)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_properties_county_id
                ON properties(county_id)
            """)

            # Create indices for places table
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_places_parent_id
                ON places(parent_id)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_places_type
                ON places(place_type)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_places_name
                ON places(name)
            """)

            # Create indices for addresses table
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_addresses_place_id
                ON addresses(place_id)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_addresses_postcode_id
                ON addresses(postcode_id)
            """)

            # Create index for postcodes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_postcodes_postcode
                ON postcodes(postcode)
            """)

            # Create indices for property_types table
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_property_types_name
                ON property_types(name)
            """)

            # Create indices for statuses table
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_statuses_name
                ON statuses(name)
            """)

            # Create indices for counties table
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_counties_name
                ON counties(name)
            """)

            print("[OK] Database schema initialized (snapshot mode with hierarchical places including postcodes, normalized towns, offer types, property types, statuses, counties, and coordinates)")

    async def get_or_create_town(self, town_name: str) -> int:
        """Get town ID, creating it if it doesn't exist"""
        async with self.pool.acquire() as conn:
            # Try to get existing town
            town_id = await conn.fetchval(
                "SELECT id FROM towns WHERE name = $1",
                town_name
            )

            if town_id:
                return town_id

            # Create new town
            town_id = await conn.fetchval(
                "INSERT INTO towns (name) VALUES ($1) RETURNING id",
                town_name
            )
            print(f"[NEW TOWN] Created: {town_name} (ID: {town_id})")
            return town_id

    async def get_or_create_offer_type(self, offer_type_name: str) -> Optional[int]:
        """Get offer type ID, creating it if it doesn't exist. Returns None if offer_type_name is None"""
        if not offer_type_name:
            return None

        async with self.pool.acquire() as conn:
            # Try to get existing offer type
            offer_type_id = await conn.fetchval(
                "SELECT id FROM offer_types WHERE name = $1",
                offer_type_name
            )

            if offer_type_id:
                return offer_type_id

            # Create new offer type
            offer_type_id = await conn.fetchval(
                "INSERT INTO offer_types (name) VALUES ($1) RETURNING id",
                offer_type_name
            )
            print(f"[NEW OFFER TYPE] Created: {offer_type_name} (ID: {offer_type_id})")
            return offer_type_id

    async def get_or_create_property_type(self, property_type_name: str) -> Optional[int]:
        """Get property type ID, creating it if it doesn't exist. Returns None if property_type_name is None"""
        if not property_type_name:
            return None

        async with self.pool.acquire() as conn:
            # Try to get existing property type
            property_type_id = await conn.fetchval(
                "SELECT id FROM property_types WHERE name = $1",
                property_type_name
            )

            if property_type_id:
                return property_type_id

            # Create new property type
            property_type_id = await conn.fetchval(
                "INSERT INTO property_types (name) VALUES ($1) RETURNING id",
                property_type_name
            )
            print(f"[NEW PROPERTY TYPE] Created: {property_type_name} (ID: {property_type_id})")
            return property_type_id

    async def get_or_create_status(self, status_name: str) -> Optional[int]:
        """Get status ID, creating it if it doesn't exist. Returns None if status_name is None"""
        if not status_name:
            return None

        async with self.pool.acquire() as conn:
            # Try to get existing status
            status_id = await conn.fetchval(
                "SELECT id FROM statuses WHERE name = $1",
                status_name
            )

            if status_id:
                return status_id

            # Create new status
            status_id = await conn.fetchval(
                "INSERT INTO statuses (name) VALUES ($1) RETURNING id",
                status_name
            )
            print(f"[NEW STATUS] Created: {status_name} (ID: {status_id})")
            return status_id

    async def get_or_create_tenure_type(self, tenure_name: str) -> Optional[int]:
        """Get tenure type ID, creating it if it doesn't exist. Returns None if tenure_name is None"""
        if not tenure_name:
            return None

        async with self.pool.acquire() as conn:
            # Try to get existing tenure type
            tenure_type_id = await conn.fetchval(
                "SELECT id FROM tenure_types WHERE name = $1",
                tenure_name
            )

            if tenure_type_id:
                return tenure_type_id

            # Create new tenure type
            tenure_type_id = await conn.fetchval(
                "INSERT INTO tenure_types (name) VALUES ($1) RETURNING id",
                tenure_name
            )
            print(f"[NEW TENURE TYPE] Created: {tenure_name} (ID: {tenure_type_id})")
            return tenure_type_id

    async def get_or_create_county(self, county_name: str) -> Optional[int]:
        """Get county ID, creating it if it doesn't exist. Returns None if county_name is None"""
        if not county_name:
            return None

        async with self.pool.acquire() as conn:
            # Try to get existing county
            county_id = await conn.fetchval(
                "SELECT id FROM counties WHERE name = $1",
                county_name
            )

            if county_id:
                return county_id

            # Create new county
            county_id = await conn.fetchval(
                "INSERT INTO counties (name) VALUES ($1) RETURNING id",
                county_name
            )
            print(f"[NEW COUNTY] Created: {county_name} (ID: {county_id})")
            return county_id

    async def get_or_create_postcode(self, postcode: str) -> Optional[int]:
        """Get postcode ID, creating it if it doesn't exist. Returns None if postcode is None"""
        if not postcode:
            return None

        # Normalize postcode (uppercase, strip whitespace)
        postcode = postcode.strip().upper()

        async with self.pool.acquire() as conn:
            # Try to get existing postcode
            postcode_id = await conn.fetchval(
                "SELECT id FROM postcodes WHERE postcode = $1",
                postcode
            )

            if postcode_id:
                return postcode_id

            # Create new postcode
            postcode_id = await conn.fetchval(
                "INSERT INTO postcodes (postcode) VALUES ($1) RETURNING id",
                postcode
            )
            print(f"[NEW POSTCODE] Created: {postcode} (ID: {postcode_id})")
            return postcode_id

    async def get_or_create_place(
        self,
        name: str,
        place_type: str,
        parent_id: Optional[int] = None
    ) -> Optional[int]:
        """
        Get or create a place in the hierarchical structure

        Args:
            name: Name of the place (e.g., "Essex", "Chelmsford", "Springfield")
            place_type: Type of place ('county', 'town', 'locality')
            parent_id: ID of parent place (None for counties, town_id for localities, etc.)

        Returns:
            Place ID or None if name is None
        """
        if not name:
            return None

        async with self.pool.acquire() as conn:
            # Try to get existing place
            place_id = await conn.fetchval(
                "SELECT id FROM places WHERE name = $1 AND place_type = $2 AND parent_id IS NOT DISTINCT FROM $3",
                name,
                place_type,
                parent_id
            )

            if place_id:
                return place_id

            # Create new place
            place_id = await conn.fetchval(
                "INSERT INTO places (name, place_type, parent_id) VALUES ($1, $2, $3) RETURNING id",
                name,
                place_type,
                parent_id
            )
            print(f"[NEW PLACE] Created: {name} ({place_type}, parent_id={parent_id}) (ID: {place_id})")
            return place_id

    async def get_or_create_hierarchical_place(
        self,
        county: Optional[str] = None,
        town: Optional[str] = None,
        locality: Optional[str] = None,
        postcode: Optional[str] = None
    ) -> Optional[int]:
        """
        Create hierarchical place structure and return the most specific place_id

        Example hierarchy:
            Essex (county) -> Chelmsford (town) -> Springfield (locality) -> CM3 1NZ (postcode)

        Args:
            county: County name
            town: Town name
            locality: Locality name
            postcode: Postcode value

        Returns:
            ID of the most specific place (postcode > locality > town > county), or None if all are None
        """
        county_id = None
        town_id = None
        locality_id = None
        postcode_id = None

        # Create county if provided
        if county:
            county_id = await self.get_or_create_place(county, 'county', parent_id=None)

        # Create town if provided (parent is county)
        if town:
            town_id = await self.get_or_create_place(town, 'town', parent_id=county_id)

        # Create locality if provided (parent is town)
        if locality:
            locality_id = await self.get_or_create_place(locality, 'locality', parent_id=town_id)

        # Create postcode if provided (parent is locality or town)
        if postcode:
            # Normalize postcode
            postcode = postcode.strip().upper()
            parent_for_postcode = locality_id or town_id
            postcode_id = await self.get_or_create_place(postcode, 'postcode', parent_id=parent_for_postcode)

        # Return most specific place_id (postcode > locality > town > county)
        return postcode_id or locality_id or town_id or county_id

    async def get_or_create_address(
        self,
        building: Optional[str] = None,
        street: Optional[str] = None,
        place_id: Optional[int] = None,
        postcode_id: Optional[int] = None,
        display_address: Optional[str] = None
    ) -> Optional[int]:
        """
        Get or create an address

        Args:
            building: Building/street name (address_line1)
            street: Additional street info
            place_id: Reference to place (usually locality or town)
            postcode_id: Reference to postcode
            display_address: Full formatted address

        Returns:
            Address ID or None if all fields are None
        """
        # If no meaningful address data, return None
        if not any([building, place_id, postcode_id]):
            return None

        async with self.pool.acquire() as conn:
            # Try to get existing address
            address_id = await conn.fetchval(
                """SELECT id FROM addresses
                   WHERE building IS NOT DISTINCT FROM $1
                   AND place_id IS NOT DISTINCT FROM $2
                   AND postcode_id IS NOT DISTINCT FROM $3""",
                building,
                place_id,
                postcode_id
            )

            if address_id:
                return address_id

            # Create new address
            address_id = await conn.fetchval(
                """INSERT INTO addresses (building, street, place_id, postcode_id, display_address)
                   VALUES ($1, $2, $3, $4, $5) RETURNING id""",
                building,
                street,
                place_id,
                postcode_id,
                display_address
            )
            print(f"[NEW ADDRESS] Created: {building or 'N/A'} (place_id={place_id}, postcode_id={postcode_id}) (ID: {address_id})")
            return address_id

    async def get_latest_snapshot(self, property_id: str) -> Optional[Dict]:
        """Get the most recent snapshot for a property"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT property_id, price, status_id, full_address,
                       address_line1, bedrooms,
                       property_type_id, description, town_id,
                       latitude, longitude, offer_type_id, postcode_id, reduced_on, tenure_id
                FROM properties
                WHERE property_id = $1
                ORDER BY created_at DESC
                LIMIT 1
            """, property_id)
            return dict(row) if row else None

    async def has_changes(self, property_id: str, new_data: Dict) -> bool:
        """
        Check if the new data differs from ALL existing snapshots

        Returns True only if the new data is different from all existing snapshots.
        This prevents saving duplicate snapshots that differ only in creation date.

        Tracks changes in critical fields: price, offer_type_id, status_id, reduced_on
        """
        async with self.pool.acquire() as conn:
            # Get ALL existing snapshots for this property (not just latest)
            existing_snapshots = await conn.fetch("""
                SELECT property_id, price, status_id, offer_type_id, reduced_on
                FROM properties
                WHERE property_id = $1
                ORDER BY created_at ASC
            """, property_id)

        if not existing_snapshots:
            # No previous snapshot, this is a new property
            return True

        # Check if any existing snapshot has identical data
        # If we find an identical snapshot, return False (no changes needed)
        for snapshot in existing_snapshots:
            # Compare critical fields
            if (snapshot.get('price') == new_data.get('price') and
                snapshot.get('offer_type_id') == new_data.get('offer_type_id') and
                snapshot.get('status_id') == new_data.get('status_id') and
                snapshot.get('reduced_on') == new_data.get('reduced_on')):

                # Found identical snapshot - no need to insert duplicate
                print(f"[SKIP] {property_id} - identical snapshot already exists (created earlier)")
                return False

        # No identical snapshot found - data has changed
        # Get latest snapshot to show what changed
        latest = existing_snapshots[-1]  # Last one (most recent)

        # Log what changed
        if latest.get('price') != new_data.get('price'):
            print(f"[CHANGE] {property_id} - price: £{latest.get('price')} -> £{new_data.get('price')}")

        if latest.get('offer_type_id') != new_data.get('offer_type_id'):
            print(f"[CHANGE] {property_id} - offer_type_id: {latest.get('offer_type_id')} -> {new_data.get('offer_type_id')}")

        if latest.get('status_id') != new_data.get('status_id'):
            print(f"[CHANGE] {property_id} - status_id: {latest.get('status_id')} -> {new_data.get('status_id')}")

        if latest.get('reduced_on') != new_data.get('reduced_on'):
            print(f"[CHANGE] {property_id} - reduced_on: {latest.get('reduced_on')} -> {new_data.get('reduced_on')}")

        return True

    async def insert_property(self, data: Dict, town_name: str) -> tuple[bool, str]:
        """
        Insert a new property snapshot if data has changed

        Args:
            data: Dictionary containing property data
            town_name: Name of the town for this property

        Returns:
            Tuple of (success: bool, status: str)
            status can be: 'inserted', 'skipped', 'error'
        """
        try:
            property_id = data.get("property_id")

            # Get or create town (backward compatibility)
            town_id = await self.get_or_create_town(town_name)

            # Get or create offer type (if present)
            price_qualifier = data.get("price_qualifier")
            offer_type_id = await self.get_or_create_offer_type(price_qualifier)

            # Get or create property type
            property_type_name = data.get("property_type")
            property_type_id = await self.get_or_create_property_type(property_type_name)

            # Get or create status
            status_name = data.get("status")
            status_id = await self.get_or_create_status(status_name)

            # Get or create tenure type
            tenure_name = data.get("tenure")
            tenure_type_id = await self.get_or_create_tenure_type(tenure_name)

            # Add IDs to data for comparison
            data["offer_type_id"] = offer_type_id
            data["property_type_id"] = property_type_id
            data["status_id"] = status_id
            data["tenure_id"] = tenure_type_id

            # Check if data has changed from latest snapshot
            if not await self.has_changes(property_id, data):
                print(f"[SKIP] No changes for {property_id}")
                return (True, 'skipped')

            # Parse address components
            address_parts = data.get("address_parts", {})

            # Get coordinates
            coordinates = data.get("coordinates", {})

            # NEW: Create hierarchical address structure
            # Extract geographic data (from reverse geocoding)
            county = address_parts.get("county")
            locality = address_parts.get("locality")
            postcode_value = address_parts.get("postcode")
            address_line1 = address_parts.get("line1")
            full_address = data.get("full_address")

            # Get or create county
            county_id = await self.get_or_create_county(county)

            # Create hierarchical places (county -> town -> locality -> postcode)
            # This creates all levels and returns the most specific (postcode if provided)
            most_specific_place_id = await self.get_or_create_hierarchical_place(
                county=county,
                town=town_name,
                locality=locality,
                postcode=postcode_value
            )

            # For address, we want to reference the locality (not postcode)
            # Create hierarchy without postcode to get locality_id
            locality_place_id = await self.get_or_create_hierarchical_place(
                county=county,
                town=town_name,
                locality=locality,
                postcode=None
            )

            # Create postcode in postcodes table (for backward compatibility)
            postcode_id = await self.get_or_create_postcode(postcode_value) if postcode_value else None

            # Create address (references locality, not postcode)
            address_id = await self.get_or_create_address(
                building=address_line1,
                street=None,
                place_id=locality_place_id,
                postcode_id=postcode_id,
                display_address=full_address
            )

            # Insert new snapshot
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO properties (
                        id, property_id, town_id, offer_type_id, property_type_id, status_id, county_id,
                        address_id, postcode_id, url, price,
                        address_line1, locality, full_address,
                        latitude, longitude,
                        bedrooms, bathrooms, description,
                        added_on, reduced_on, size, tenure_id, council_tax_band
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24)
                """,
                    str(uuid.uuid4()),
                    property_id,
                    town_id,
                    offer_type_id,
                    property_type_id,
                    status_id,
                    county_id,
                    address_id,
                    postcode_id,
                    data.get("url"),
                    data.get("price"),
                    address_parts.get("line1"),
                    locality,
                    data.get("full_address"),
                    coordinates.get("latitude"),
                    coordinates.get("longitude"),
                    data.get("bedrooms"),
                    data.get("bathrooms"),
                    data.get("description"),
                    data.get("added_on"),
                    data.get("reduced_on"),
                    data.get("size"),
                    tenure_type_id,
                    data.get("council_tax_band")
                )
                return (True, 'inserted')
        except Exception as e:
            print(f"[ERROR] Error inserting property {data.get('property_id')}: {e}")
            return (False, 'error')

    async def get_property_latest(self, property_id: str) -> Optional[Dict]:
        """Get the latest snapshot for a property by ID"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM properties WHERE property_id = $1 ORDER BY created_at DESC LIMIT 1",
                property_id
            )
            return dict(row) if row else None

    async def get_property_history(self, property_id: str) -> list:
        """Get all snapshots for a property (history)"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM properties WHERE property_id = $1 ORDER BY created_at DESC",
                property_id
            )
            return [dict(row) for row in rows]

    async def get_all_properties_latest(self) -> list:
        """Get the latest snapshot for each unique property"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT DISTINCT ON (property_id) *
                FROM properties
                ORDER BY property_id, created_at DESC
            """)
            return [dict(row) for row in rows]

    async def get_snapshot_count(self, property_id: str) -> int:
        """Get the number of snapshots for a property"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(
                "SELECT COUNT(*) FROM properties WHERE property_id = $1",
                property_id
            )
            return result or 0

    async def get_stats(self) -> Dict:
        """Get database statistics"""
        async with self.pool.acquire() as conn:
            # Total snapshots
            total_snapshots = await conn.fetchval("SELECT COUNT(*) FROM properties")

            # Unique properties
            unique_properties = await conn.fetchval(
                "SELECT COUNT(DISTINCT property_id) FROM properties"
            )

            # Average price from latest snapshots only
            avg_price = await conn.fetchval("""
                WITH latest AS (
                    SELECT DISTINCT ON (property_id) price
                    FROM properties
                    ORDER BY property_id, created_at DESC
                )
                SELECT AVG(price)
                FROM latest
                WHERE price IS NOT NULL
            """)

            # Properties with price changes
            price_changes = await conn.fetchval("""
                SELECT COUNT(DISTINCT property_id)
                FROM (
                    SELECT property_id, COUNT(DISTINCT price) as price_count
                    FROM properties
                    WHERE price IS NOT NULL
                    GROUP BY property_id
                    HAVING COUNT(DISTINCT price) > 1
                ) as changed
            """)

            return {
                "total_snapshots": total_snapshots,
                "unique_properties": unique_properties,
                "average_price": f"£{avg_price:,.2f}" if avg_price else "N/A",
                "properties_with_price_changes": price_changes or 0
            }
