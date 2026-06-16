import collections
import logging
from typing import Any, Dict, Tuple, Optional

logger = logging.getLogger(__name__)

class LRUCache:
    """
    A simple Least Recently Used (LRU) cache implementation.
    """
    def __init__(self, capacity: int = 5):
        self.capacity = capacity
        self.cache = collections.OrderedDict() # Stores (key, value) pairs, maintains insertion order
        logger.info(f"Initialized LRU cache with capacity: {capacity}")

    def get(self, key: Tuple[Any, ...]) -> Optional[Dict[str, Any]]:
        if key not in self.cache:
            return None
        # Move the accessed key to the end to mark it as recently used
        value = self.cache.pop(key)
        self.cache[key] = value
        logger.debug(f"Cache hit for key: {key}")
        return value

    def put(self, key: Tuple[Any, ...], value: Dict[str, Any]):
        if key in self.cache:
            self.cache.pop(key) # Remove existing entry to update its recency
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            # Remove the least recently used item (first item)
            lru_key = next(iter(self.cache))
            self.cache.pop(lru_key)
            logger.debug(f"Cache full, evicted LRU item: {lru_key}")
        logger.debug(f"Cache put for key: {key}")

    def clear(self):
        self.cache.clear()
        logger.info("LRU cache cleared manually.")

# Global instance of the cache, with a default capacity of 5
forecast_model_cache = LRUCache(capacity=5)