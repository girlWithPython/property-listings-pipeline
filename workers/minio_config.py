"""
MinIO configuration and client setup
"""
import os
from minio import Minio
from minio.error import S3Error

# MinIO connection settings from environment variables
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'localhost:9000')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', 'minioadmin')
MINIO_SECURE = os.getenv('MINIO_SECURE', 'false').lower() == 'true'
MINIO_BUCKET = os.getenv('MINIO_BUCKET', 'property-images')


def get_minio_client():
    """Create and return a MinIO client instance"""
    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE
    )
    return client


def ensure_bucket_exists(bucket_name=None):
    """Ensure the bucket exists, create it if it doesn't"""
    bucket_name = bucket_name or MINIO_BUCKET
    client = get_minio_client()

    try:
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
            print(f"[MinIO] Created bucket: {bucket_name}")
        else:
            print(f"[MinIO] Bucket already exists: {bucket_name}")
    except S3Error as e:
        print(f"[MinIO ERROR] Failed to ensure bucket exists: {e}")
        raise


def get_object_url(bucket_name, object_key):
    """Get the URL to access an object in MinIO"""
    # For local development, return the direct MinIO URL
    protocol = 'https' if MINIO_SECURE else 'http'
    return f"{protocol}://{MINIO_ENDPOINT}/{bucket_name}/{object_key}"
