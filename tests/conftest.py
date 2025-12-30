"""Pytest fixtures and configuration."""

import os
import pytest
from unittest.mock import MagicMock, patch

# Set testing environment before importing app
os.environ['FLASK_ENV'] = 'testing'

from app import create_app
from config import TestingConfig
from database import db
from models import Analysis, Song, Topic


@pytest.fixture(scope='session')
def app():
    """Create Flask application for testing."""
    app = create_app(TestingConfig)
    app.config['TESTING'] = True

    yield app


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()


@pytest.fixture
def app_context(app):
    """Create application context."""
    with app.app_context():
        yield


@pytest.fixture
def db_session(app):
    """Create database session for testing."""
    with app.app_context():
        db.create_all()
        yield db.session
        db.session.rollback()
        db.drop_all()


@pytest.fixture
def sample_analysis(db_session):
    """Create a sample analysis."""
    analysis = Analysis(
        artist_name='Test Artist',
        album_id=10001,
        album_name='Test Album',
        job_id='test-job-123',
        status='queued'
    )
    db_session.add(analysis)
    db_session.commit()
    return analysis


@pytest.fixture
def completed_analysis(db_session):
    """Create a completed analysis with results."""
    from datetime import datetime

    analysis = Analysis(
        artist_name='Completed Artist',
        album_id=20002,
        album_name='Completed Album',
        job_id='completed-job-456',
        status='completed',
        results={
            'topics': [{'id': 0, 'name': 'Test Topic', 'keywords': {'word': 0.5}}],
            'sentiment': {'overall': 0.25}
        },
        completed_at=datetime.utcnow()
    )
    db_session.add(analysis)
    db_session.commit()
    return analysis


@pytest.fixture
def sample_songs():
    """Sample songs data for testing."""
    return [
        {
            'title': 'Test Song 1',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'year': 2020,
            'lyrics': 'This is a test song with happy lyrics about love and sunshine.',
            'url': 'https://genius.com/test1'
        },
        {
            'title': 'Test Song 2',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'year': 2021,
            'lyrics': 'Dark night brings pain and sorrow, death awaits tomorrow.',
            'url': 'https://genius.com/test2'
        },
        {
            'title': 'Test Song 3',
            'artist': 'Test Artist',
            'album': None,
            'year': None,
            'lyrics': 'Running through the fields of green, dreaming of what could have been.',
            'url': 'https://genius.com/test3'
        }
    ]


@pytest.fixture
def preprocessed_songs():
    """Sample preprocessed songs with tokens."""
    return [
        {
            'title': 'Song 1',
            'lyrics': 'love sunshine happy day',
            'tokens': ['love', 'sunshin', 'happi', 'day'],
            'text': 'love sunshin happi day'
        },
        {
            'title': 'Song 2',
            'lyrics': 'dark night pain sorrow death',
            'tokens': ['dark', 'night', 'pain', 'sorrow', 'death'],
            'text': 'dark night pain sorrow death'
        },
        {
            'title': 'Song 3',
            'lyrics': 'running field dream',
            'tokens': ['run', 'field', 'dream'],
            'text': 'run field dream'
        }
    ]


@pytest.fixture
def mock_genius_api():
    """Mock Genius API responses."""
    with patch('pipeline.scraper.requests') as mock_requests:
        # Mock search response
        search_response = MagicMock()
        search_response.status_code = 200
        search_response.json.return_value = {
            'response': {
                'hits': [
                    {
                        'result': {
                            'title': 'Test Song',
                            'primary_artist': {
                                'id': 123,
                                'name': 'Test Artist'
                            }
                        }
                    }
                ]
            }
        }

        # Mock artist songs response
        songs_response = MagicMock()
        songs_response.status_code = 200
        songs_response.json.return_value = {
            'response': {
                'songs': [
                    {
                        'title': 'Song 1',
                        'url': 'https://genius.com/song1',
                        'primary_artist': {'name': 'Test Artist'},
                        'album': {'name': 'Test Album'},
                        'release_date_for_display': '2020'
                    }
                ]
            }
        }

        # Mock lyrics page response
        lyrics_response = MagicMock()
        lyrics_response.status_code = 200
        lyrics_response.text = '''
            <html>
            <body>
            <div data-lyrics-container="true">
            Test lyrics content here
            Love and pain mixed together
            </div>
            </body>
            </html>
        '''

        def mock_get(*args, **kwargs):
            url = args[0] if args else kwargs.get('url', '')
            if 'search' in str(url):
                return search_response
            elif 'songs' in str(url):
                return songs_response
            else:
                return lyrics_response

        mock_requests.get.side_effect = mock_get
        yield mock_requests


@pytest.fixture
def mock_celery():
    """Mock Celery task execution."""
    with patch('celery_app.celery') as mock:
        mock_task = MagicMock()
        mock_task.id = 'mock-task-id-123'
        mock.Task.delay.return_value = mock_task
        yield mock


@pytest.fixture
def celery_app(app):
    """Create Celery app for testing."""
    from celery_app import make_celery
    celery = make_celery(app)
    celery.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )
    return celery
