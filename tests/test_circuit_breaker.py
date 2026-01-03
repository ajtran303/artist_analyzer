"""Unit tests for circuit breaker functionality."""

import pytest
from unittest.mock import MagicMock, patch

from pipeline.api_metrics import APIMetrics, CIRCUIT_CONFIG


@pytest.fixture
def mock_redis():
    """Create a mock Redis client with in-memory storage."""
    storage = {}

    mock = MagicMock()

    def mock_get(key):
        return storage.get(key)

    def mock_set(key, value, nx=False, ex=None):
        if nx and key in storage:
            return False
        storage[key] = value
        return True

    def mock_setex(key, ttl, value):
        storage[key] = value
        return True

    def mock_incr(key):
        current = int(storage.get(key, 0))
        storage[key] = str(current + 1)
        return current + 1

    def mock_delete(key):
        storage.pop(key, None)
        return 1

    def mock_expire(key, ttl):
        return True

    def mock_ttl(key):
        if key in storage:
            return 30  # Simulate TTL remaining
        return -2  # Key doesn't exist

    def mock_ping():
        return True

    def mock_pipeline():
        pipe = MagicMock()
        commands = []

        def add_command(cmd, *args, **kwargs):
            commands.append((cmd, args, kwargs))
            return pipe

        pipe.incr = lambda k: add_command('incr', k)
        pipe.expire = lambda k, t: add_command('expire', k, t)
        pipe.delete = lambda k: add_command('delete', k)
        pipe.setex = lambda k, t, v: add_command('setex', k, t, v)

        def execute():
            results = []
            for cmd, args, kwargs in commands:
                if cmd == 'incr':
                    results.append(mock_incr(args[0]))
                elif cmd == 'delete':
                    results.append(mock_delete(args[0]))
                elif cmd == 'setex':
                    results.append(mock_setex(args[0], args[1], args[2]))
                elif cmd == 'expire':
                    results.append(True)
            commands.clear()
            return results

        pipe.execute = execute
        return pipe

    mock.get = mock_get
    mock.set = mock_set
    mock.setex = mock_setex
    mock.incr = mock_incr
    mock.delete = mock_delete
    mock.expire = mock_expire
    mock.ttl = mock_ttl
    mock.ping = mock_ping
    mock.pipeline = mock_pipeline

    # Expose storage for test assertions
    mock._storage = storage

    return mock


@pytest.fixture
def metrics(mock_redis):
    """Create APIMetrics instance with mocked Redis."""
    m = APIMetrics()
    m._redis = mock_redis
    return m


@pytest.mark.unit
class TestCircuitBreakerClosed:
    """Tests for circuit breaker in closed (normal) state."""

    def test_circuit_starts_closed(self, metrics):
        """Circuit breaker starts in closed state."""
        assert metrics.is_circuit_open('musixmatch') is False
        assert metrics.is_circuit_open('lyricsovh') is False

    def test_requests_allowed_when_closed(self, metrics):
        """Requests are allowed when circuit is closed."""
        allowed, reason = metrics.should_allow_request('musixmatch')
        assert allowed is True
        assert reason is None

    def test_single_failure_does_not_open_circuit(self, metrics):
        """Single failure does not trip the circuit."""
        metrics.record_failure('musixmatch')

        assert metrics.is_circuit_open('musixmatch') is False

    def test_failures_below_threshold_keep_circuit_closed(self, metrics):
        """Failures below threshold keep circuit closed."""
        threshold = CIRCUIT_CONFIG['musixmatch']['failure_threshold']

        for _ in range(threshold - 1):
            metrics.record_failure('musixmatch')

        assert metrics.is_circuit_open('musixmatch') is False


@pytest.mark.unit
class TestCircuitBreakerOpen:
    """Tests for circuit breaker tripping open."""

    def test_consecutive_failures_open_circuit(self, metrics, mock_redis):
        """Circuit opens after consecutive failures reach threshold."""
        threshold = CIRCUIT_CONFIG['musixmatch']['failure_threshold']

        for _ in range(threshold):
            metrics.record_failure('musixmatch')

        assert metrics.is_circuit_open('musixmatch') is True

    def test_requests_blocked_when_open(self, metrics, mock_redis):
        """Requests are blocked when circuit is open."""
        # Manually open the circuit
        mock_redis._storage['circuit:musixmatch:open'] = '1'

        allowed, reason = metrics.should_allow_request('musixmatch')
        assert allowed is False
        assert reason == 'circuit_open'

    def test_success_resets_failure_count(self, metrics, mock_redis):
        """Success resets consecutive failure counter."""
        threshold = CIRCUIT_CONFIG['musixmatch']['failure_threshold']

        # Record some failures (but not enough to trip)
        for _ in range(threshold - 1):
            metrics.record_failure('musixmatch')

        # Record a success
        metrics.record_success('musixmatch')

        # Now failures should need to start over
        assert mock_redis._storage.get('circuit:musixmatch:failures') is None


@pytest.mark.unit
class TestCircuitBreakerHalfOpen:
    """Tests for circuit breaker half-open (probe) state."""

    def test_probe_allowed_after_recovery_timeout(self, metrics, mock_redis):
        """Probe request allowed after recovery timeout expires."""
        # Set circuit to open with expired TTL
        mock_redis._storage['circuit:musixmatch:open'] = '1'
        mock_redis.ttl = lambda k: -1 if k == 'circuit:musixmatch:open' else 30

        allowed, reason = metrics.should_allow_request('musixmatch')
        assert allowed is True  # Probe allowed

    def test_probe_success_closes_circuit(self, metrics, mock_redis):
        """Successful probe closes the circuit."""
        # Set circuit to half-open
        mock_redis._storage['circuit:musixmatch:open'] = '1'
        mock_redis._storage['circuit:musixmatch:half_open'] = '1'

        # Record success
        metrics.record_success('musixmatch')

        # Circuit should be closed
        assert mock_redis._storage.get('circuit:musixmatch:open') is None
        assert mock_redis._storage.get('circuit:musixmatch:half_open') is None

    def test_probe_failure_reopens_circuit(self, metrics, mock_redis):
        """Failed probe reopens the circuit."""
        # Set circuit to half-open
        mock_redis._storage['circuit:musixmatch:half_open'] = '1'

        # Record failure during probe
        metrics.record_failure('musixmatch')

        # Circuit should be open again
        assert mock_redis._storage.get('circuit:musixmatch:open') == '1'


@pytest.mark.unit
class TestCircuitBreakerSlowResponses:
    """Tests for slow response detection."""

    def test_slow_response_recorded(self, metrics, mock_redis):
        """Slow responses are tracked."""
        slow_threshold = CIRCUIT_CONFIG['musixmatch']['slow_threshold_ms']

        # Record a slow but successful response
        metrics.record_success('musixmatch', response_time_ms=slow_threshold + 1000)

        # Should have tracked the slow response
        assert mock_redis._storage.get('circuit:musixmatch:slow') == '1'

    def test_many_slow_responses_open_circuit(self, metrics, mock_redis):
        """Too many slow responses trip the circuit."""
        slow_threshold = CIRCUIT_CONFIG['musixmatch']['slow_threshold_ms']

        # Record 10 slow responses
        for _ in range(10):
            metrics.record_success('musixmatch', response_time_ms=slow_threshold + 1000)

        # Circuit should be open
        assert metrics.is_circuit_open('musixmatch') is True

    def test_fast_response_not_tracked_as_slow(self, metrics, mock_redis):
        """Fast responses are not tracked as slow."""
        slow_threshold = CIRCUIT_CONFIG['musixmatch']['slow_threshold_ms']

        metrics.record_success('musixmatch', response_time_ms=slow_threshold - 1000)

        assert mock_redis._storage.get('circuit:musixmatch:slow') is None


@pytest.mark.unit
class TestCircuitBreakerState:
    """Tests for circuit breaker state reporting."""

    def test_get_closed_state(self, metrics):
        """Reports closed state correctly."""
        state = metrics.get_circuit_state('musixmatch')

        assert state['state'] == 'closed'
        assert state['failures'] == 0
        assert state['threshold'] == CIRCUIT_CONFIG['musixmatch']['failure_threshold']

    def test_get_open_state(self, metrics, mock_redis):
        """Reports open state correctly."""
        mock_redis._storage['circuit:musixmatch:open'] = '1'
        mock_redis.ttl = lambda k: 45  # 45 seconds remaining

        state = metrics.get_circuit_state('musixmatch')

        assert state['state'] == 'open'
        assert state['recovery_in_seconds'] == 45

    def test_get_half_open_state(self, metrics, mock_redis):
        """Reports half-open state correctly."""
        mock_redis._storage['circuit:musixmatch:half_open'] = '1'

        state = metrics.get_circuit_state('musixmatch')

        assert state['state'] == 'half_open'


@pytest.mark.unit
class TestCircuitBreakerNoRedis:
    """Tests for circuit breaker behavior when Redis is unavailable."""

    def test_circuit_closed_without_redis(self):
        """Circuit reports closed when Redis unavailable."""
        metrics = APIMetrics()
        metrics._redis = None

        assert metrics.is_circuit_open('musixmatch') is False

    def test_requests_allowed_without_redis(self):
        """Requests allowed when Redis unavailable (fail open)."""
        metrics = APIMetrics()
        metrics._redis = None

        allowed, reason = metrics.should_allow_request('musixmatch')
        assert allowed is True

    def test_record_failure_graceful_without_redis(self):
        """Recording failure is graceful without Redis."""
        metrics = APIMetrics()
        metrics._redis = None

        # Should not raise
        metrics.record_failure('musixmatch')

    def test_record_success_graceful_without_redis(self):
        """Recording success is graceful without Redis."""
        metrics = APIMetrics()
        metrics._redis = None

        # Should not raise
        metrics.record_success('musixmatch', response_time_ms=100)


@pytest.mark.unit
class TestCircuitBreakerUnconfiguredAPI:
    """Tests for APIs without circuit breaker config."""

    def test_unconfigured_api_always_allowed(self, metrics):
        """APIs without circuit config are always allowed."""
        # 'discogs' has no circuit breaker config
        assert metrics.is_circuit_open('discogs') is False

        allowed, _ = metrics.should_allow_request('discogs')
        assert allowed is True

    def test_unconfigured_api_failures_ignored(self, metrics, mock_redis):
        """Failures for unconfigured APIs don't trip any circuit."""
        for _ in range(100):
            metrics.record_failure('discogs')

        assert metrics.is_circuit_open('discogs') is False


@pytest.mark.unit
class TestScraperCircuitBreakerIntegration:
    """Integration tests for scraper with circuit breaker."""

    @patch('pipeline.scraper.requests.get')
    @patch('pipeline.api_metrics.get_metrics')
    def test_musixmatch_skipped_when_circuit_open(self, mock_get_metrics, mock_requests):
        """Musixmatch is skipped when circuit is open."""
        from pipeline.scraper import _fetch_lyrics_musixmatch

        # Mock metrics to report circuit open
        mock_metrics = MagicMock()
        mock_metrics.should_allow_request.return_value = (False, 'circuit_open')
        mock_get_metrics.return_value = mock_metrics

        with patch('pipeline.scraper.MUSIXMATCH_API_KEY', 'test-key'):
            result = _fetch_lyrics_musixmatch('Artist', 'Song')

        assert result == ''
        mock_requests.assert_not_called()  # No HTTP request made

    @patch('pipeline.scraper.requests.get')
    @patch('pipeline.api_metrics.get_metrics')
    def test_lyricsovh_skipped_when_circuit_open(self, mock_get_metrics, mock_requests):
        """lyrics.ovh is skipped when circuit is open."""
        from pipeline.scraper import _fetch_lyrics_lyricsovh

        mock_metrics = MagicMock()
        mock_metrics.should_allow_request.return_value = (False, 'circuit_open')
        mock_get_metrics.return_value = mock_metrics

        result = _fetch_lyrics_lyricsovh('Artist', 'Song')

        assert result == ''
        mock_requests.assert_not_called()

    @patch('pipeline.scraper.requests.get')
    @patch('pipeline.api_metrics.get_metrics')
    def test_timeout_records_failure(self, mock_get_metrics, mock_requests):
        """Timeout records a failure for circuit breaker."""
        from pipeline.scraper import _fetch_lyrics_musixmatch
        import requests

        mock_metrics = MagicMock()
        mock_metrics.should_allow_request.return_value = (True, None)
        mock_get_metrics.return_value = mock_metrics

        mock_requests.side_effect = requests.exceptions.Timeout()

        with patch('pipeline.scraper.MUSIXMATCH_API_KEY', 'test-key'):
            result = _fetch_lyrics_musixmatch('Artist', 'Song')

        assert result == ''
        mock_metrics.record_failure.assert_called_once_with('musixmatch')

    @patch('pipeline.scraper.requests.get')
    @patch('pipeline.api_metrics.get_metrics')
    def test_success_records_response_time(self, mock_get_metrics, mock_requests):
        """Successful response records response time."""
        from pipeline.scraper import _fetch_lyrics_musixmatch

        mock_metrics = MagicMock()
        mock_metrics.should_allow_request.return_value = (True, None)
        mock_get_metrics.return_value = mock_metrics

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'message': {
                'header': {'status_code': 200},
                'body': {'lyrics': {'lyrics_body': 'Test lyrics'}}
            }
        }
        mock_requests.return_value = mock_response

        with patch('pipeline.scraper.MUSIXMATCH_API_KEY', 'test-key'):
            result = _fetch_lyrics_musixmatch('Artist', 'Song')

        assert result == 'Test lyrics'
        mock_metrics.record_success.assert_called_once()
        # Check that response_time_ms was passed
        call_args = mock_metrics.record_success.call_args
        assert call_args[0][0] == 'musixmatch'
        assert call_args[0][1] is not None  # response_time_ms
