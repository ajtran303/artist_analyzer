"""Unit tests for web routes - Phase 10."""

import pytest


@pytest.mark.unit
class TestIndexRoute:
    """Tests for GET / route."""

    def test_returns_200(self, client):
        """Returns 200 OK."""
        response = client.get('/')
        assert response.status_code == 200

    def test_returns_html(self, client):
        """Returns HTML content."""
        response = client.get('/')
        assert b'<!DOCTYPE html>' in response.data or b'<html' in response.data

    def test_has_form(self, client):
        """Has artist input form."""
        response = client.get('/')
        assert b'<form' in response.data
        assert b'artist' in response.data.lower()

    def test_has_submit_button(self, client):
        """Has submit button."""
        response = client.get('/')
        assert b'<button' in response.data or b'type="submit"' in response.data


@pytest.mark.unit
class TestResultsRoute:
    """Tests for GET /results/<job_id> route."""

    def test_returns_200(self, client):
        """Returns 200 OK."""
        response = client.get('/results/test-job-id')
        assert response.status_code == 200

    def test_returns_html(self, client):
        """Returns HTML page."""
        response = client.get('/results/some-job-id')
        assert b'<!DOCTYPE html>' in response.data or b'<html' in response.data

    def test_passes_job_id_to_template(self, client):
        """Job ID is available in the page."""
        response = client.get('/results/my-test-job')
        # Job ID should be in the page (in JS variable)
        assert b'my-test-job' in response.data


@pytest.mark.unit
class TestHealthRoute:
    """Tests for health check via web."""

    def test_api_health_accessible(self, client, app_context):
        """Health endpoint is accessible."""
        from unittest.mock import patch
        with patch('routes.api.check_db_health', return_value=True):
            response = client.get('/api/health')
            assert response.status_code == 200
