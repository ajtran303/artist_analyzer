"""Integration tests for API workflow - Phase 11."""

import pytest
import json
from unittest.mock import patch, MagicMock


@pytest.mark.integration
class TestApiWorkflow:
    """API workflow integration tests."""

    def test_submit_check_get_workflow(self, client, db_session):
        """Full workflow: Submit -> Check Status -> Get Results."""
        # Step 1: Submit analysis
        with patch('pipeline.tasks.analyze_album_async') as mock_task:
            mock_task.delay.return_value = MagicMock(id='workflow-test-job')

            response = client.post(
                '/api/analyze',
                data=json.dumps({
                    'artist_name': 'Workflow Artist',
                    'album_id': 12345,
                    'album_name': 'Workflow Album'
                }),
                content_type='application/json'
            )

            assert response.status_code == 202
            data = json.loads(response.data)
            job_id = data['job_id']
            assert job_id == 'workflow-test-job'

        # Step 2: Check status (should be queued/processing)
        response = client.get(f'/api/analyze/{job_id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] in ['queued', 'processing']

        # Step 3: Simulate task completion
        from models import Analysis
        analysis = Analysis.get_by_job_id(job_id)
        analysis.set_results({
            'topics': [{'id': 0, 'name': 'Test Topic', 'keywords': {}, 'weight': 0.5}],
            'sentiment': {'overall': 0.3, 'by_album': [], 'by_year': []},
            'word_frequency': [],
            'metaphors': []
        })

        # Step 4: Check status again (should be completed)
        response = client.get(f'/api/analyze/{job_id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'completed'
        assert 'results' in data

        # Step 5: Get full results
        response = client.get(f'/api/results/{job_id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'artist' in data
        assert 'results' in data
        assert 'completed_at' in data

    def test_caching_workflow(self, client, db_session):
        """Same album requested twice uses cache."""
        # First request
        with patch('pipeline.tasks.analyze_album_async') as mock_task:
            mock_task.delay.return_value = MagicMock(id='cache-job-1')

            response1 = client.post(
                '/api/analyze',
                data=json.dumps({
                    'artist_name': 'Cache Artist',
                    'album_id': 55555,
                    'album_name': 'Cache Album'
                }),
                content_type='application/json'
            )

            assert response1.status_code == 202
            job_id = json.loads(response1.data)['job_id']

        # Complete the analysis
        from models import Analysis
        analysis = Analysis.get_by_job_id(job_id)
        analysis.set_results({'topics': [], 'sentiment': {'overall': 0}})

        # Second request for same artist + album
        response2 = client.post(
            '/api/analyze',
            data=json.dumps({
                'artist_name': 'Cache Artist',
                'album_id': 55555,
                'album_name': 'Cache Album'
            }),
            content_type='application/json'
        )

        assert response2.status_code == 200  # Not 202
        data = json.loads(response2.data)
        assert data['status'] == 'completed'
        assert data.get('cached') is True

    def test_error_workflow(self, client, db_session):
        """Error handling workflow."""
        # Submit analysis
        with patch('pipeline.tasks.analyze_album_async') as mock_task:
            mock_task.delay.return_value = MagicMock(id='error-job')

            response = client.post(
                '/api/analyze',
                data=json.dumps({
                    'artist_name': 'Error Artist',
                    'album_id': 77777,
                    'album_name': 'Error Album'
                }),
                content_type='application/json'
            )

            job_id = json.loads(response.data)['job_id']

        # Simulate task failure
        from models import Analysis
        analysis = Analysis.get_by_job_id(job_id)
        analysis.mark_failed('No songs found for album')

        # Check status shows failure
        response = client.get(f'/api/analyze/{job_id}')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'failed'
        assert 'error' in data

        # Retry should create new analysis (API handles deletion of failed)
        with patch('pipeline.tasks.analyze_album_async') as mock_task:
            mock_task.delay.return_value = MagicMock(id='retry-job')

            response = client.post(
                '/api/analyze',
                data=json.dumps({
                    'artist_name': 'Error Artist',
                    'album_id': 77777,
                    'album_name': 'Error Album'
                }),
                content_type='application/json'
            )

            assert response.status_code == 202


@pytest.mark.integration
class TestConcurrentRequests:
    """Tests for concurrent request handling."""

    def test_same_album_concurrent(self, client, db_session):
        """Concurrent requests for same album handled correctly."""
        with patch('pipeline.tasks.analyze_album_async') as mock_task:
            mock_task.delay.return_value = MagicMock(id='concurrent-job')

            # First request
            response1 = client.post(
                '/api/analyze',
                data=json.dumps({
                    'artist_name': 'Concurrent Artist',
                    'album_id': 66666,
                    'album_name': 'Concurrent Album'
                }),
                content_type='application/json'
            )

            # Second request while first is processing (same album)
            response2 = client.post(
                '/api/analyze',
                data=json.dumps({
                    'artist_name': 'Concurrent Artist',
                    'album_id': 66666,
                    'album_name': 'Concurrent Album'
                }),
                content_type='application/json'
            )

            # Both should get same job
            data1 = json.loads(response1.data)
            data2 = json.loads(response2.data)

            assert data1['job_id'] == data2['job_id']


@pytest.mark.integration
class TestWebIntegration:
    """Tests for web page integration."""

    def test_home_to_results_flow(self, client, db_session):
        """User can navigate from home to results."""
        # Load home page
        response = client.get('/')
        assert response.status_code == 200
        assert b'search-form' in response.data

        # Submit form (via API)
        with patch('pipeline.tasks.analyze_album_async') as mock_task:
            mock_task.delay.return_value = MagicMock(id='nav-test-job')

            response = client.post(
                '/api/analyze',
                data=json.dumps({
                    'artist_name': 'Navigation Artist',
                    'album_id': 88888,
                    'album_name': 'Navigation Album'
                }),
                content_type='application/json'
            )

            job_id = json.loads(response.data)['job_id']

        # Load results page
        response = client.get(f'/results/{job_id}')
        assert response.status_code == 200
        assert job_id.encode() in response.data
