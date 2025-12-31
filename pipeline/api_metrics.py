"""API metrics tracking and rate limiting using Redis."""

import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Rate limit configurations
API_LIMITS = {
    'discogs': {'limit': 60, 'window': 'minute', 'ttl': 60},
    'musixmatch': {'limit': 500, 'window': 'day', 'ttl': 86400},
    'lyricsovh': {'limit': None, 'window': 'minute', 'ttl': 60},  # No limit, just track
}


class APIMetrics:
    """Track API usage and enforce rate limits using Redis."""

    def __init__(self, redis_url=None):
        self._redis = None
        self._redis_url = redis_url or os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

    @property
    def redis(self):
        """Lazy-load Redis connection."""
        if self._redis is None:
            try:
                import redis
                self._redis = redis.from_url(
                    self._redis_url,
                    decode_responses=True,
                    socket_timeout=2,  # 2 second timeout for operations
                    socket_connect_timeout=2  # 2 second timeout for connection
                )
                # Test connection
                self._redis.ping()
            except Exception as e:
                logger.warning(f"Redis connection failed, metrics disabled: {e}")
                self._redis = None
        return self._redis

    def _get_key(self, api_name, key_type='requests'):
        """Generate Redis key for the current time window."""
        config = API_LIMITS.get(api_name, {'window': 'minute'})
        window = config['window']

        now = datetime.now(timezone.utc)
        if window == 'minute':
            # Key per minute: api:discogs:requests:2024-01-15T10:30
            time_key = now.strftime('%Y-%m-%dT%H:%M')
        elif window == 'day':
            # Key per day: api:musixmatch:requests:2024-01-15
            time_key = now.strftime('%Y-%m-%d')
        else:
            time_key = now.strftime('%Y-%m-%dT%H:%M')

        return f"api:{api_name}:{key_type}:{time_key}"

    def _get_ttl(self, api_name):
        """Get TTL for the API's rate limit window."""
        config = API_LIMITS.get(api_name, {'ttl': 60})
        # Add buffer to TTL to ensure key exists for full window
        return config['ttl'] + 10

    def check_limit(self, api_name):
        """
        Check if we can make a request to this API.

        Args:
            api_name: Name of the API ('discogs', 'musixmatch', 'lyricsovh')

        Returns:
            Tuple of (allowed: bool, wait_seconds: int or None)
            - allowed: True if request can proceed
            - wait_seconds: Seconds until limit resets (if not allowed)
        """
        if self.redis is None:
            # Redis unavailable, fail open
            return True, None

        config = API_LIMITS.get(api_name)
        if not config or config['limit'] is None:
            # No limit configured
            return True, None

        try:
            key = self._get_key(api_name)
            current = self.redis.get(key)
            count = int(current) if current else 0

            if count >= config['limit']:
                # Rate limited - calculate wait time
                ttl = self.redis.ttl(key)
                wait_seconds = max(ttl, 1) if ttl > 0 else config['ttl']
                return False, wait_seconds

            return True, None

        except Exception as e:
            logger.warning(f"Error checking rate limit for {api_name}: {e}")
            # Fail open on errors
            return True, None

    def track_call(self, api_name, success=True):
        """
        Record an API call.

        Args:
            api_name: Name of the API
            success: Whether the call succeeded
        """
        if self.redis is None:
            return

        try:
            # Increment request counter
            key = self._get_key(api_name, 'requests')
            ttl = self._get_ttl(api_name)

            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, ttl)

            if not success:
                # Also track errors
                error_key = self._get_key(api_name, 'errors')
                pipe.incr(error_key)
                pipe.expire(error_key, ttl)

            pipe.execute()

        except Exception as e:
            logger.warning(f"Error tracking API call for {api_name}: {e}")

    def get_usage(self, api_name):
        """
        Get current usage stats for an API.

        Returns:
            Dict with count, limit, remaining, window, reset_in_seconds
        """
        config = API_LIMITS.get(api_name, {'limit': None, 'window': 'minute', 'ttl': 60})

        result = {
            'count': 0,
            'limit': config['limit'],
            'remaining': config['limit'],
            'window': config['window'],
            'reset_in_seconds': config['ttl'],
            'errors': 0,
        }

        if self.redis is None:
            result['status'] = 'redis_unavailable'
            return result

        try:
            key = self._get_key(api_name, 'requests')
            error_key = self._get_key(api_name, 'errors')

            count = self.redis.get(key)
            errors = self.redis.get(error_key)
            ttl = self.redis.ttl(key)

            result['count'] = int(count) if count else 0
            result['errors'] = int(errors) if errors else 0

            if config['limit']:
                result['remaining'] = max(0, config['limit'] - result['count'])

            if ttl > 0:
                result['reset_in_seconds'] = ttl

            result['status'] = 'ok'

        except Exception as e:
            logger.warning(f"Error getting usage for {api_name}: {e}")
            result['status'] = 'error'

        return result

    def get_all_usage(self):
        """Get usage stats for all tracked APIs."""
        return {
            api_name: self.get_usage(api_name)
            for api_name in API_LIMITS.keys()
        }


# Global instance
_metrics = None


def get_metrics():
    """Get or create the global APIMetrics instance."""
    global _metrics
    if _metrics is None:
        _metrics = APIMetrics()
    return _metrics
