"""
Celery tasks for downloading and storing property images to MinIO
"""
from workers.celery_app import app
from workers.minio_config import get_minio_client, ensure_bucket_exists, MINIO_BUCKET
import httpx
import io
import asyncio
import asyncpg
import json
from db.config import DB_CONFIG


@app.task(bind=True, max_retries=3, queue='scraper')
def download_property_images(self, property_id: str, image_urls: list):
    """
    Download images from source URLs and upload to MinIO

    Args:
        property_id: The property ID (e.g., "166323035")
        image_urls: List of image URLs to download

    Returns:
        dict with property_id and number of images saved
    """
    try:
        print(f"[IMAGE TASK] Processing {len(image_urls)} images for property {property_id}")

        # Ensure MinIO bucket exists
        ensure_bucket_exists()

        # Get MinIO client
        minio_client = get_minio_client()

        # Download and upload each image
        minio_keys = []

        for idx, url in enumerate(image_urls):
            try:
                # Download image
                with httpx.Client(timeout=30.0) as client:
                    response = client.get(url)
                    response.raise_for_status()
                    image_data = response.content

                # Determine file extension
                if url.endswith('.png'):
                    ext = 'png'
                    content_type = 'image/png'
                elif url.endswith('.jpg') or url.endswith('.jpeg'):
                    ext = 'jpg'
                    content_type = 'image/jpeg'
                else:
                    ext = 'jpg'  # Default to jpg
                    content_type = 'image/jpeg'

                # Create object key
                object_key = f"properties/{property_id}/{idx}.{ext}"

                # Upload to MinIO
                minio_client.put_object(
                    MINIO_BUCKET,
                    object_key,
                    io.BytesIO(image_data),
                    length=len(image_data),
                    content_type=content_type
                )

                minio_keys.append(object_key)
                print(f"[IMAGE TASK] Uploaded: {object_key} ({len(image_data)} bytes)")

            except httpx.HTTPStatusError as e:
                print(f"[IMAGE TASK WARNING] HTTP error downloading {url}: {e}")
                # Continue with other images even if one fails
                continue
            except Exception as e:
                print(f"[IMAGE TASK WARNING] Error processing image {idx}: {e}")
                # Continue with other images
                continue

        # If no images were successfully uploaded, retry the task
        if not minio_keys and image_urls:
            raise Exception(f"Failed to upload any images for property {property_id}")

        # Update database with MinIO keys
        asyncio.run(update_property_images_in_db(property_id, minio_keys))

        print(f"[IMAGE TASK] Successfully processed {len(minio_keys)}/{len(image_urls)} images for property {property_id}")

        return {
            "property_id": property_id,
            "images_saved": len(minio_keys),
            "images_attempted": len(image_urls),
            "minio_keys": minio_keys
        }

    except Exception as e:
        print(f"[IMAGE TASK ERROR] Failed to process images for {property_id}: {e}")
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


async def update_property_images_in_db(property_id: str, minio_keys: list):
    """
    Update the database with MinIO keys for a property

    Args:
        property_id: The property ID
        minio_keys: List of MinIO object keys
    """
    conn = None
    try:
        # Create database connection
        conn = await asyncpg.connect(
            host=DB_CONFIG.get('host', 'localhost'),
            port=DB_CONFIG.get('port', 5432),
            database=DB_CONFIG.get('database', 'rightmove_scraper'),
            user=DB_CONFIG.get('user', 'postgres'),
            password=DB_CONFIG.get('password', '12345')
        )

        # Prepare JSONB data as JSON string
        images_data = {
            "keys": minio_keys,
            "count": len(minio_keys)
        }
        images_json = json.dumps(images_data)

        # Update the most recent record for this property
        # (since we use snapshot-based history, we update the latest snapshot)
        await conn.execute("""
            UPDATE properties
            SET minio_images = $1::jsonb
            WHERE id = (
                SELECT id FROM properties
                WHERE property_id = $2
                ORDER BY created_at DESC
                LIMIT 1
            )
        """, images_json, property_id)

        print(f"[DB UPDATE] Updated property {property_id} with {len(minio_keys)} MinIO keys")

    except Exception as e:
        print(f"[DB ERROR] Failed to update database for property {property_id}: {e}")
        raise
    finally:
        if conn:
            await conn.close()
