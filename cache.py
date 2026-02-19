"""
Firestore-based caching layer with TTL support.

To enable automatic TTL cleanup in Firebase Console:
1. Go to Firestore -> Indexes -> TTL Policies
2. Add TTL policy on 'cache' collection, field: 'expires_at'
"""
import hashlib
from datetime import datetime, timedelta, timezone
from config import db

CACHE_TTL_MINUTES = 30
CACHE_ENABLED = True  # Set to True to enable caching


def _get_cache_key(profile_url: str) -> str:
    """Generate a consistent cache key from profile URL."""
    return hashlib.md5(profile_url.strip().encode()).hexdigest()


async def get_cached_profile(profile_url: str) -> dict | None:
    """
    Retrieve cached profile data if it exists and hasn't expired.
    Returns None if cache miss or expired.
    """
    if not CACHE_ENABLED:
        return None
    cache_key = _get_cache_key(profile_url)
    doc = db.collection("cache").document(cache_key).get()

    if doc.exists:
        data = doc.to_dict()
        expires_at = data.get("expires_at")
        if expires_at and expires_at > datetime.now(timezone.utc):
            return data.get("profile_data")
        # Expired - optionally delete (TTL policy will also handle this)

    return None


async def set_cached_profile(profile_url: str, profile_data: dict) -> None:
    """
    Store profile data in cache with TTL.
    """
    if not CACHE_ENABLED:
        return
    cache_key = _get_cache_key(profile_url)
    db.collection("cache").document(cache_key).set({
        "profile_data": profile_data,
        "profile_url": profile_url.strip(),
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=CACHE_TTL_MINUTES),
        "created_at": datetime.now(timezone.utc)
    })


async def invalidate_cache(profile_url: str) -> None:
    """
    Manually invalidate cache for a profile.
    Useful when profile data is updated.
    """
    cache_key = _get_cache_key(profile_url)
    db.collection("cache").document(cache_key).delete()


def clear_all_cache() -> int:
    """
    Delete all documents from the cache collection.
    Returns the number of documents deleted.
    """
    cache_ref = db.collection("cache")
    docs = cache_ref.stream()
    count = 0
    for doc in docs:
        doc.reference.delete()
        count += 1
    return count


if __name__ == "__main__":
    # Run this file directly to clear all cache
    deleted = clear_all_cache()
    print(f"Cleared {deleted} cached entries.")
