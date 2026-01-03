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

# Circuit breaker configurations
# - failure_threshold: consecutive failures before opening circuit
# - recovery_timeout: seconds to wait before trying again (half-open state)
# - slow_threshold_ms: response time (ms) considered "slow" (counts as half-failure)
CIRCUIT_CONFIG = {
    'musixmatch': {'failure_threshold': 5, 'recovery_timeout': 60, 'slow_threshold_ms': 5000},
    'lyricsovh': {'failure_threshold': 5, 'recovery_timeout': 30, 'slow_threshold_ms': 5000},
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

    # ==================== Circuit Breaker Methods ====================

    def is_circuit_open(self, api_name):
        """
        Check if circuit breaker is open (service considered unhealthy).

        Returns:
            True if circuit is open (should skip this API), False otherwise.
        """
        if self.redis is None:
            return False

        config = CIRCUIT_CONFIG.get(api_name)
        if not config:
            return False

        try:
            open_key = f"circuit:{api_name}:open"
            is_open = self.redis.get(open_key)
            return is_open is not None
        except Exception as e:
            logger.warning(f"Error checking circuit state for {api_name}: {e}")
            return False

    def record_success(self, api_name, response_time_ms=None):
        """
        Record a successful API call. Resets failure count and closes circuit.

        Args:
            api_name: Name of the API
            response_time_ms: Response time in milliseconds (optional, for slow detection)
        """
        if self.redis is None:
            return

        config = CIRCUIT_CONFIG.get(api_name)
        if not config:
            return

        try:
            pipe = self.redis.pipeline()

            # Reset consecutive failure counter
            pipe.delete(f"circuit:{api_name}:failures")

            # Close circuit if it was in half-open state
            pipe.delete(f"circuit:{api_name}:open")
            pipe.delete(f"circuit:{api_name}:half_open")

            pipe.execute()

            # Check if response was slow (but successful)
            if response_time_ms and response_time_ms > config.get('slow_threshold_ms', 5000):
                logger.warning(f"{api_name} slow response: {response_time_ms}ms")
                self._record_slow_response(api_name)

        except Exception as e:
            logger.warning(f"Error recording success for {api_name}: {e}")

    def record_failure(self, api_name):
        """
        Record a failed API call. May trip the circuit breaker.

        Args:
            api_name: Name of the API
        """
        if self.redis is None:
            return

        config = CIRCUIT_CONFIG.get(api_name)
        if not config:
            return

        try:
            # Check if we're in half-open state (testing)
            half_open_key = f"circuit:{api_name}:half_open"
            if self.redis.get(half_open_key):
                # Failed during probe - reopen circuit
                self._open_circuit(api_name, config)
                logger.warning(f"Circuit breaker RE-OPENED for {api_name} (probe failed)")
                return

            # Increment consecutive failure counter
            failures_key = f"circuit:{api_name}:failures"
            failures = self.redis.incr(failures_key)
            # Auto-expire after 2 minutes of no activity
            self.redis.expire(failures_key, 120)

            logger.debug(f"{api_name} failure count: {failures}/{config['failure_threshold']}")

            if failures >= config['failure_threshold']:
                self._open_circuit(api_name, config)
                logger.warning(f"Circuit breaker OPENED for {api_name} after {failures} failures")

        except Exception as e:
            logger.warning(f"Error recording failure for {api_name}: {e}")

    def _record_slow_response(self, api_name):
        """Track slow responses - too many slow responses can trip the circuit."""
        config = CIRCUIT_CONFIG.get(api_name)
        if not config:
            return

        try:
            # Slow responses count as "half" a failure
            slow_key = f"circuit:{api_name}:slow"
            slow_count = self.redis.incr(slow_key)
            self.redis.expire(slow_key, 60)  # Reset after 1 minute

            # 10 slow responses in a minute = trip circuit
            if slow_count >= 10:
                self._open_circuit(api_name, config)
                logger.warning(f"Circuit breaker OPENED for {api_name} (too many slow responses)")

        except Exception as e:
            logger.warning(f"Error recording slow response for {api_name}: {e}")

    def _open_circuit(self, api_name, config):
        """Open the circuit breaker for an API."""
        try:
            pipe = self.redis.pipeline()

            # Set circuit to open state with recovery timeout
            open_key = f"circuit:{api_name}:open"
            pipe.setex(open_key, config['recovery_timeout'], '1')

            # Reset failure counter
            pipe.delete(f"circuit:{api_name}:failures")
            pipe.delete(f"circuit:{api_name}:slow")

            pipe.execute()

        except Exception as e:
            logger.warning(f"Error opening circuit for {api_name}: {e}")

    def should_allow_request(self, api_name):
        """
        Check if a request should be allowed (combines rate limit + circuit breaker).

        This is the main entry point for checking if an API call should proceed.

        Returns:
            Tuple of (allowed: bool, reason: str or None)
            - allowed: True if request can proceed
            - reason: Why request was blocked (if not allowed)
        """
        # Check circuit breaker first (fast failure)
        if self.is_circuit_open(api_name):
            # Check if we should transition to half-open for a probe
            if self._should_probe(api_name):
                return True, None
            return False, 'circuit_open'

        # Check rate limit
        allowed, wait_time = self.check_limit(api_name)
        if not allowed:
            return False, f'rate_limited:{wait_time}s'

        return True, None

    def _should_probe(self, api_name):
        """
        Check if circuit should transition to half-open state for a probe request.

        Returns True if we should allow one test request through.
        """
        if self.redis is None:
            return False

        try:
            open_key = f"circuit:{api_name}:open"
            half_open_key = f"circuit:{api_name}:half_open"

            # Check remaining TTL on open state
            ttl = self.redis.ttl(open_key)

            # If TTL expired or about to expire, allow a probe
            if ttl <= 0:
                # Use SET NX to ensure only one probe at a time
                probe_set = self.redis.set(half_open_key, '1', nx=True, ex=10)
                if probe_set:
                    logger.info(f"Circuit breaker HALF-OPEN for {api_name} (allowing probe)")
                    return True

            return False

        except Exception as e:
            logger.warning(f"Error checking probe state for {api_name}: {e}")
            return False

    def get_circuit_state(self, api_name):
        """
        Get the current circuit breaker state for an API.

        Returns:
            Dict with state ('closed', 'open', 'half_open'), failures, recovery_in_seconds
        """
        config = CIRCUIT_CONFIG.get(api_name, {})
        result = {
            'state': 'closed',
            'failures': 0,
            'threshold': config.get('failure_threshold', 0),
            'recovery_in_seconds': None,
        }

        if self.redis is None or not config:
            return result

        try:
            open_key = f"circuit:{api_name}:open"
            half_open_key = f"circuit:{api_name}:half_open"
            failures_key = f"circuit:{api_name}:failures"

            is_open = self.redis.get(open_key)
            is_half_open = self.redis.get(half_open_key)
            failures = self.redis.get(failures_key)

            if is_half_open:
                result['state'] = 'half_open'
            elif is_open:
                result['state'] = 'open'
                result['recovery_in_seconds'] = self.redis.ttl(open_key)

            result['failures'] = int(failures) if failures else 0

        except Exception as e:
            logger.warning(f"Error getting circuit state for {api_name}: {e}")

        return result


# Global instance
_metrics = None


def get_metrics():
    """Get or create the global APIMetrics instance."""
    global _metrics
    if _metrics is None:
        _metrics = APIMetrics()
    return _metrics
