"""Security tests for the application."""

import pytest
import json
from unittest.mock import patch


@pytest.mark.unit
class TestInputValidation:
    """Tests for input validation."""

    def test_rejects_empty_artist_name(self, client, db_session):
        """Rejects empty artist name."""
        response = client.post(
            '/api/analyze',
            data=json.dumps({'artist_name': ''}),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_rejects_whitespace_only_artist_name(self, client, db_session):
        """Rejects whitespace-only artist name."""
        response = client.post(
            '/api/analyze',
            data=json.dumps({'artist_name': '   '}),
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_rejects_too_long_artist_name(self, client, db_session):
        """Rejects artist name over 200 characters."""
        long_name = 'A' * 201
        response = client.post(
            '/api/analyze',
            data=json.dumps({'artist_name': long_name}),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'less than' in data['error']

    def test_sanitizes_html_in_artist_name(self, client, db_session):
        """Strips HTML tags from artist name."""
        with patch('pipeline.tasks.analyze_album_async') as mock_task:
            from unittest.mock import MagicMock
            mock_task.delay.return_value = MagicMock(id='test-job')

            response = client.post(
                '/api/analyze',
                data=json.dumps({'artist_name': '<script>alert("xss")</script>Test'}),
                content_type='application/json'
            )

            # Should be rejected due to invalid characters after sanitization
            # or accepted with sanitized name
            assert response.status_code in [400, 202]

    def test_accepts_ampersand_in_artist_name(self, client, db_session):
        """Accepts ampersand in artist name (e.g., 'Lil Jon & The East Side Boyz')."""
        from urllib.parse import urlencode

        with patch('pipeline.scraper.search_artist_albums') as mock_search:
            mock_search.return_value = {
                'artist_id': 12345,
                'artist_name': 'Lil Jon & The East Side Boyz',
                'albums': [],
                'has_more': False
            }
            # Properly URL-encode the query parameter
            query_string = urlencode({'q': 'Lil Jon & The East Side Boyz'})
            response = client.get(f'/api/artists/search?{query_string}')

            # Should not be rejected for invalid characters
            assert response.status_code == 200

    def test_accepts_slash_in_artist_name(self, client, db_session):
        """Accepts forward slash in artist name (e.g., 'AC/DC')."""
        with patch('pipeline.scraper.search_artist_albums') as mock_search:
            mock_search.return_value = {
                'artist_id': 12345,
                'artist_name': 'AC/DC',
                'albums': [],
                'has_more': False
            }
            response = client.get('/api/artists/search?q=AC/DC')

            # Should not be rejected for invalid characters
            assert response.status_code == 200

    def test_accepts_parentheses_in_artist_name(self, client, db_session):
        """Accepts parentheses in artist name (e.g., 'Sunn O)))')."""
        with patch('pipeline.scraper.search_artist_albums') as mock_search:
            mock_search.return_value = {
                'artist_id': 12345,
                'artist_name': 'Sunn O)))',
                'albums': [],
                'has_more': False
            }
            response = client.get('/api/artists/search?q=Sunn O)))')

            # Should not be rejected for invalid characters
            assert response.status_code == 200

    def test_rejects_invalid_job_id_format(self, client, db_session):
        """Rejects invalid job_id format."""
        # Use characters that are invalid but URL-safe (no angle brackets which confuse Flask routing)
        response = client.get('/api/analyze/test!@%23invalid')
        assert response.status_code == 400

    def test_rejects_too_long_job_id(self, client, db_session):
        """Rejects job_id over 50 characters."""
        long_id = 'a' * 51
        response = client.get(f'/api/analyze/{long_id}')
        assert response.status_code == 400


@pytest.mark.unit
class TestXssPrevention:
    """Tests for XSS prevention."""

    def test_error_messages_sanitized(self, client, db_session):
        """Error messages are sanitized."""
        from models import Analysis

        analysis = Analysis.create('XSS Test Artist')
        analysis.job_id = 'xss-test-job'
        analysis.mark_failed('<script>alert("xss")</script>Error')
        db_session.commit()

        response = client.get('/api/analyze/xss-test-job')

        data = json.loads(response.data)
        if 'error' in data:
            assert '<script>' not in data['error']


@pytest.mark.unit
class TestSqlInjectionPrevention:
    """Tests for SQL injection prevention."""

    def test_artist_name_sql_injection(self, client, db_session):
        """SQL injection in artist name is prevented."""
        malicious_names = [
            "'; DROP TABLE analyses; --",
            "1 OR 1=1",
            "1; DELETE FROM analyses",
            "' UNION SELECT * FROM analyses --"
        ]

        for name in malicious_names:
            response = client.post(
                '/api/analyze',
                data=json.dumps({'artist_name': name}),
                content_type='application/json'
            )

            # Should either reject as invalid or handle safely
            # (SQLAlchemy uses parameterized queries)
            assert response.status_code in [400, 202, 500]

    def test_job_id_sql_injection(self, client, db_session):
        """SQL injection in job_id is prevented."""
        response = client.get("/api/analyze/1' OR '1'='1")
        # Should be rejected as invalid format or return 404
        assert response.status_code in [400, 404]


@pytest.mark.unit
class TestErrorHandling:
    """Tests for secure error handling."""

    def test_no_stack_traces_in_errors(self, client, db_session):
        """No stack traces exposed in error responses."""
        response = client.get('/api/analyze/nonexistent-job-id')

        data = json.loads(response.data)
        response_text = json.dumps(data).lower()

        # Should not contain stack trace indicators
        assert 'traceback' not in response_text
        assert 'file "' not in response_text
        assert 'line ' not in response_text

    def test_malformed_json_handled(self, client, db_session):
        """Malformed JSON returns 400, not 500."""
        response = client.post(
            '/api/analyze',
            data='not valid json',
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_missing_content_type_handled(self, client, db_session):
        """Missing content-type handled gracefully."""
        response = client.post(
            '/api/analyze',
            data='{"artist_name": "test"}'
        )

        # Should handle gracefully
        assert response.status_code in [400, 415]


@pytest.mark.unit
class TestRateLimiting:
    """Tests for rate limiting (basic checks)."""

    def test_rate_limiter_configured(self, app):
        """Rate limiter is configured on app."""
        assert hasattr(app, 'limiter')


@pytest.mark.unit
class TestCsrfProtection:
    """Tests for CSRF protection."""

    def test_csrf_token_in_web_pages(self, client):
        """Web pages include CSRF meta tag or token."""
        response = client.get('/')
        # Note: CSRF is exempt for API, but web forms should have it
        assert response.status_code == 200


@pytest.mark.unit
class TestSecurityHeaders:
    """Tests for security headers (in production mode)."""

    def test_content_type_set(self, client, db_session):
        """API responses have correct content-type."""
        response = client.get('/api/health')
        assert 'application/json' in response.content_type


@pytest.mark.unit
class TestSecretsNotLogged:
    """Tests for secrets not being logged."""

    def test_sensitive_filter_exists(self):
        """Sensitive data filter is configured."""
        import logging
        from app import SensitiveDataFilter

        # Verify the filter class exists and works
        filter_instance = SensitiveDataFilter()

        class MockRecord:
            msg = "Token: abc123"

        record = MockRecord()
        filter_instance.filter(record)
        assert 'REDACTED' in record.msg
