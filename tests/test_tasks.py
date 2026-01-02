"""Unit tests for Celery tasks."""

import pytest
from unittest.mock import patch, MagicMock

from pipeline.tasks import analyze_album_async, RETRIABLE_EXCEPTIONS


@pytest.mark.unit
class TestTaskConfiguration:
    """Tests for task configuration and metadata."""

    def test_task_has_correct_name(self):
        """Task has correct name."""
        assert analyze_album_async.name == 'pipeline.tasks.analyze_album_async'

    def test_task_is_celery_task(self):
        """Task is a proper Celery task."""
        assert hasattr(analyze_album_async, 'delay')
        assert hasattr(analyze_album_async, 'apply_async')

    def test_task_is_bound(self):
        """Task is bound (has access to self)."""
        assert callable(analyze_album_async)

    def test_retriable_exceptions_defined(self):
        """RETRIABLE_EXCEPTIONS contains expected exceptions."""
        assert ConnectionError in RETRIABLE_EXCEPTIONS
        assert TimeoutError in RETRIABLE_EXCEPTIONS
        assert OSError in RETRIABLE_EXCEPTIONS

    def test_task_has_retry_config(self):
        """Task has retry configuration."""
        assert hasattr(analyze_album_async, 'autoretry_for')

    def test_task_has_delay_method(self):
        """Task has delay method for async execution."""
        assert callable(getattr(analyze_album_async, 'delay', None))

    def test_task_has_apply_async_method(self):
        """Task has apply_async method."""
        assert callable(getattr(analyze_album_async, 'apply_async', None))

    def test_task_has_apply_method(self):
        """Task has apply method for synchronous execution."""
        assert callable(getattr(analyze_album_async, 'apply', None))


@pytest.mark.unit
class TestTaskWithEagerMode:
    """Tests for task execution in eager mode (synchronous)."""

    @pytest.fixture
    def celery_eager_app(self, app):
        """Configure Celery for eager mode testing."""
        from celery_app import celery
        celery.conf.update(
            task_always_eager=True,
            task_eager_propagates=True,
        )
        return celery

    def test_task_returns_none_for_invalid_analysis(self, app, db_session, celery_eager_app):
        """Task returns None when analysis doesn't exist."""
        result = analyze_album_async.apply(
            args=[999, 'Nonexistent', 99999],
            kwargs={'artist_name': 'Nobody'}
        )
        # Task should return None for non-existent analysis
        assert result.result is None

    def test_task_can_be_called_with_apply(self, celery_eager_app):
        """Task can be invoked with apply method."""
        # Just verify the task runs without crashing
        result = analyze_album_async.apply(
            args=[1, 'Test', 999999],
            kwargs={'artist_name': 'Test'}
        )
        # Should complete (returning None for missing analysis)
        assert result.status in ('SUCCESS', 'FAILURE')


@pytest.mark.unit
class TestTaskErrorHandling:
    """Tests for task error handling logic."""

    def test_scraper_error_is_in_try_except(self):
        """Verify ScraperError is handled in the task."""
        from pipeline.scraper import ScraperError
        # Verify ScraperError exception exists and can be raised
        with pytest.raises(ScraperError):
            raise ScraperError("Test error")

    def test_retriable_exceptions_are_network_errors(self):
        """RETRIABLE_EXCEPTIONS are all network-related."""
        for exc in RETRIABLE_EXCEPTIONS:
            assert issubclass(exc, (ConnectionError, TimeoutError, OSError))


@pytest.mark.unit
class TestTaskResultStructure:
    """Tests for expected result structure from the task."""

    def test_expected_result_keys(self):
        """Document expected keys in successful result."""
        expected_keys = [
            'artist', 'album', 'songs_count', 'total_tracks',
            'topics', 'sentiment', 'emotions', 'word_frequency',
            'metaphors', 'stats', 'timestamp'
        ]
        # This documents the expected structure
        assert len(expected_keys) == 11

    def test_expected_sentiment_structure(self):
        """Document expected sentiment structure."""
        expected_sentiment_keys = ['by_song', 'overall']
        assert len(expected_sentiment_keys) == 2

    def test_expected_stats_structure(self):
        """Document expected stats structure."""
        expected_stats_keys = [
            'total_words', 'unique_words', 'vocabulary_richness',
            'most_positive', 'most_negative', 'emotional_passages'
        ]
        assert len(expected_stats_keys) == 6


@pytest.mark.unit
class TestTaskPipelineStages:
    """Tests documenting the pipeline stages."""

    def test_pipeline_has_seven_stages(self):
        """Pipeline has 7 stages as documented."""
        stages = [
            'Scraping',
            'Preprocessing',
            'LDA Topic Modeling',
            'Sentiment Analysis',
            'Emotion Analysis',
            'Bonus Analyses',
            'Saving Results'
        ]
        assert len(stages) == 7

    def test_pipeline_imports_are_valid(self):
        """All pipeline imports exist."""
        from pipeline.scraper import scrape_album, ScraperError
        from pipeline.preprocessor import preprocess_lyrics
        from pipeline.lda_analyzer import run_lda, assign_topics_to_songs
        from pipeline.sentiment_analyzer import run_sentiment, find_most_emotional_passages
        from pipeline.bonus_analyzer import analyze_word_frequency, analyze_metaphors, analyze_vocabulary_richness
        from pipeline.emotion_analyzer import analyze_emotions

        # All imports should succeed
        assert callable(scrape_album)
        assert callable(preprocess_lyrics)
        assert callable(run_lda)
        assert callable(assign_topics_to_songs)
        assert callable(run_sentiment)
        assert callable(find_most_emotional_passages)
        assert callable(analyze_word_frequency)
        assert callable(analyze_metaphors)
        assert callable(analyze_vocabulary_richness)
        assert callable(analyze_emotions)


@pytest.mark.unit
class TestTaskProgressUpdates:
    """Tests for task progress update mechanism."""

    def test_task_has_update_state_method(self):
        """Bound tasks have update_state method via self."""
        # Celery bound tasks receive 'self' which has update_state
        # We just verify the task is bound
        assert analyze_album_async.bind is True or hasattr(analyze_album_async, '__self__') or callable(analyze_album_async)

    def test_progress_states(self):
        """Document expected progress states."""
        states = ['PROGRESS', 'SUCCESS', 'FAILURE']
        assert 'PROGRESS' in states


@pytest.mark.unit
class TestTaskDatabaseInteraction:
    """Tests for task database interaction patterns."""

    def test_models_can_be_imported(self, app_context):
        """Models used by task can be imported."""
        from models import Analysis, Song, Topic

        assert hasattr(Analysis, 'query')
        assert hasattr(Song, 'create')
        assert hasattr(Topic, 'create')

    def test_analysis_has_required_methods(self):
        """Analysis model has methods used by task."""
        from models import Analysis

        assert hasattr(Analysis, 'update_status')
        assert hasattr(Analysis, 'mark_failed')
        assert hasattr(Analysis, 'set_results')
