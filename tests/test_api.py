"""Unit tests for API routes - Phase 9."""

import pytest
from unittest.mock import patch, MagicMock
import json


@pytest.mark.unit
class TestSubmitAnalysis:
    """Tests for POST /api/analyze endpoint."""

    def test_valid_artist_submission(self, client, db_session):
        """Valid artist and album returns 202 with job_id."""
        with patch('pipeline.tasks.analyze_album_async') as mock_task:
            mock_task.delay.return_value = MagicMock(id='test-job-123')

            response = client.post(
                '/api/analyze',
                data=json.dumps({
                    'artist_name': 'The Cure',
                    'album_id': 12345,
                    'album_name': 'Disintegration'
                }),
                content_type='application/json'
            )

            assert response.status_code == 202
            data = json.loads(response.data)
            assert 'job_id' in data
            assert data['status'] == 'queued'
            assert data['artist'] == 'The Cure'
            assert data['album'] == 'Disintegration'

    def test_missing_artist_name(self, client):
        """Missing artist_name returns 400."""
        response = client.post(
            '/api/analyze',
            data=json.dumps({'album_id': 123}),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_missing_album_id(self, client):
        """Missing album_id returns 400."""
        response = client.post(
            '/api/analyze',
            data=json.dumps({'artist_name': 'The Cure'}),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'album_id' in data['error']

    def test_empty_artist_name(self, client):
        """Empty artist_name returns 400."""
        response = client.post(
            '/api/analyze',
            data=json.dumps({'artist_name': '   ', 'album_id': 123}),
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_whitespace_trimmed(self, client, db_session):
        """Artist name whitespace is trimmed."""
        with patch('pipeline.tasks.analyze_album_async') as mock_task:
            mock_task.delay.return_value = MagicMock(id='test-job')

            response = client.post(
                '/api/analyze',
                data=json.dumps({
                    'artist_name': '  The Cure  ',
                    'album_id': 12345,
                    'album_name': 'Disintegration'
                }),
                content_type='application/json'
            )

            data = json.loads(response.data)
            assert data['artist'] == 'The Cure'

    def test_missing_request_body(self, client):
        """Missing request body returns 400."""
        response = client.post('/api/analyze', content_type='application/json')

        assert response.status_code == 400


@pytest.mark.unit
class TestCachingBehavior:
    """Tests for caching behavior."""

    def test_cached_album_returns_immediately(self, client, db_session):
        """Completed analysis returns 200 with cached flag."""
        from datetime import datetime
        from models import Analysis

        # Create a completed analysis with album_id
        analysis = Analysis(
            artist_name='Completed Artist',
            album_id=99999,
            album_name='Completed Album',
            job_id='completed-album-job',
            status='completed',
            results={'topics': [], 'sentiment': {'overall': 0}},
            completed_at=datetime.utcnow()
        )
        db_session.add(analysis)
        db_session.commit()

        response = client.post(
            '/api/analyze',
            data=json.dumps({
                'artist_name': 'Completed Artist',
                'album_id': 99999,
                'album_name': 'Completed Album'
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'completed'
        assert data.get('cached') is True

    def test_processing_album_returns_202(self, client, db_session):
        """Processing analysis returns 202."""
        from models import Analysis

        analysis = Analysis.create('Processing Artist', album_id=88888, album_name='Processing Album')
        analysis.job_id = 'processing-job'
        analysis.status = 'processing'
        db_session.commit()

        response = client.post(
            '/api/analyze',
            data=json.dumps({
                'artist_name': 'Processing Artist',
                'album_id': 88888,
                'album_name': 'Processing Album'
            }),
            content_type='application/json'
        )

        assert response.status_code == 202
        data = json.loads(response.data)
        assert data['status'] == 'processing'


@pytest.mark.unit
class TestGetAnalysisStatus:
    """Tests for GET /api/analyze/<job_id> endpoint."""

    def test_queued_status(self, client, sample_analysis):
        """Returns queued status."""
        response = client.get(f'/api/analyze/{sample_analysis.job_id}')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'queued'
        assert data['artist'] == sample_analysis.artist_name

    def test_completed_status(self, client, completed_analysis):
        """Returns completed status with results."""
        response = client.get(f'/api/analyze/{completed_analysis.job_id}')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'completed'
        assert 'results' in data

    def test_failed_status(self, client, db_session):
        """Returns failed status with error."""
        from models import Analysis

        analysis = Analysis.create('Failed Artist')
        analysis.job_id = 'failed-job'
        analysis.mark_failed('Something went wrong')
        db_session.commit()

        response = client.get('/api/analyze/failed-job')

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'failed'
        assert 'error' in data

    def test_invalid_job_id(self, client, db_session):
        """Returns 404 for invalid job_id."""
        response = client.get('/api/analyze/nonexistent-job')

        assert response.status_code == 404

    def test_includes_progress(self, client, db_session):
        """Includes progress for processing status."""
        from models import Analysis

        analysis = Analysis.create('Progress Artist')
        analysis.job_id = 'progress-job'
        analysis.update_status('processing', 'Running LDA analysis...')
        db_session.commit()

        response = client.get('/api/analyze/progress-job')

        data = json.loads(response.data)
        assert data['progress'] == 'Running LDA analysis...'


@pytest.mark.unit
class TestGetResults:
    """Tests for GET /api/results/<job_id> endpoint."""

    def test_returns_full_results(self, client, completed_analysis):
        """Returns full results when completed."""
        response = client.get(f'/api/results/{completed_analysis.job_id}')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'artist' in data
        assert 'results' in data
        assert 'completed_at' in data

    def test_returns_202_if_not_completed(self, client, sample_analysis):
        """Returns 202 if not completed."""
        response = client.get(f'/api/results/{sample_analysis.job_id}')

        assert response.status_code == 202
        data = json.loads(response.data)
        assert 'message' in data

    def test_returns_404_if_not_found(self, client, db_session):
        """Returns 404 if not found."""
        response = client.get('/api/results/nonexistent')

        assert response.status_code == 404


@pytest.mark.unit
class TestHealthCheck:
    """Tests for GET /health endpoint."""

    def test_returns_ok_status(self, client, app_context):
        """Returns ok status when healthy."""
        with patch('routes.api.check_db_health', return_value=True):
            response = client.get('/api/health')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['status'] == 'ok'
            assert data['database'] == 'connected'

    def test_returns_degraded_when_db_down(self, client, app_context):
        """Returns degraded when database is down."""
        with patch('routes.api.check_db_health', return_value=False):
            response = client.get('/api/health')

            assert response.status_code == 503
            data = json.loads(response.data)
            assert data['status'] == 'degraded'


@pytest.mark.unit
class TestErrorResponses:
    """Tests for error responses."""

    def test_malformed_json(self, client):
        """Returns 400 for malformed JSON."""
        response = client.post(
            '/api/analyze',
            data='not valid json',
            content_type='application/json'
        )

        # Flask returns 400 for malformed JSON
        assert response.status_code in [400, 415]
