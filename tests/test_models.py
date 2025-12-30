"""Unit tests for models - Phase 1."""

import pytest
from datetime import datetime

from models import Analysis, Song, Topic


@pytest.mark.unit
class TestAnalysis:
    """Tests for Analysis model."""

    def test_create_initializes_with_correct_defaults(self, db_session):
        """Analysis.create() initializes with correct defaults."""
        analysis = Analysis.create('Test Artist')

        assert analysis.artist_name == 'Test Artist'
        assert analysis.status == 'queued'
        assert analysis.job_id is None
        assert analysis.created_at is not None
        assert analysis.completed_at is None

    def test_create_strips_whitespace(self, db_session):
        """Artist name whitespace is trimmed."""
        analysis = Analysis.create('  Test Artist  ')
        assert analysis.artist_name == 'Test Artist'

    def test_update_status_updates_status_and_timestamp(self, db_session):
        """update_status() updates status and timestamp for completed."""
        analysis = Analysis.create('Test Artist')
        analysis.update_status('completed')

        assert analysis.status == 'completed'
        assert analysis.completed_at is not None

    def test_update_status_only_completed_sets_timestamp(self, db_session):
        """Only completed status updates completed_at."""
        analysis = Analysis.create('Test Artist')
        analysis.update_status('processing', 'Working...')

        assert analysis.status == 'processing'
        assert analysis.progress == 'Working...'
        assert analysis.completed_at is None

    def test_set_results_stores_json(self, db_session):
        """set_results() stores JSON results correctly."""
        analysis = Analysis.create('Test Artist')
        results = {
            'topics': [{'id': 0, 'name': 'Love'}],
            'sentiment': {'overall': 0.5},
            'nested': {'deep': {'value': 123}}
        }
        analysis.set_results(results)

        assert analysis.results == results
        assert analysis.status == 'completed'
        assert analysis.completed_at is not None

    def test_get_by_artist_album_returns_existing(self, db_session):
        """get_by_artist_album() returns existing analysis."""
        original = Analysis.create('Existing Artist', album_id=12345, album_name='Test Album')
        original.job_id = 'test-job'
        db_session.commit()

        found = Analysis.get_by_artist_album('Existing Artist', 12345)
        assert found.id == original.id
        assert found.job_id == 'test-job'
        assert found.album_id == 12345

    def test_get_by_artist_album_returns_none(self, db_session):
        """get_by_artist_album() returns None if not found."""
        Analysis.create('Some Artist', album_id=11111, album_name='Some Album')
        db_session.commit()

        # Different album_id should return None
        found = Analysis.get_by_artist_album('Some Artist', 99999)
        assert found is None

        # Different artist should return None
        found = Analysis.get_by_artist_album('Other Artist', 11111)
        assert found is None

    def test_create_with_album_info(self, db_session):
        """create() stores album_id and album_name."""
        analysis = Analysis.create('Test Artist', album_id=54321, album_name='Test Album')
        assert analysis.album_id == 54321
        assert analysis.album_name == 'Test Album'

    def test_mark_failed_sets_error_state(self, db_session):
        """mark_failed() sets error state correctly."""
        analysis = Analysis.create('Test Artist')
        analysis.mark_failed('Something went wrong')

        assert analysis.status == 'failed'
        assert analysis.error_message == 'Something went wrong'
        assert analysis.completed_at is None

    def test_get_by_job_id_returns_analysis(self, db_session):
        """get_by_job_id() returns correct analysis."""
        analysis = Analysis.create('Test Artist')
        analysis.job_id = 'unique-job-id'
        db_session.commit()

        found = Analysis.get_by_job_id('unique-job-id')
        assert found.id == analysis.id

    def test_get_by_job_id_returns_none(self, db_session):
        """get_by_job_id() returns None for non-existent."""
        found = Analysis.get_by_job_id('non-existent')
        assert found is None

    def test_to_dict_converts_correctly(self, db_session):
        """to_dict() converts model to dictionary."""
        analysis = Analysis.create('Test Artist')
        analysis.job_id = 'test-job'
        db_session.commit()

        data = analysis.to_dict()

        assert data['artist_name'] == 'Test Artist'
        assert data['job_id'] == 'test-job'
        assert data['status'] == 'queued'
        assert 'created_at' in data


@pytest.mark.unit
class TestSong:
    """Tests for Song model."""

    def test_create_with_all_fields(self, db_session, sample_analysis):
        """Song.create() persists all fields correctly."""
        song = Song.create(
            analysis_id=sample_analysis.id,
            artist_name='Test Artist',
            title='Test Song',
            album='Test Album',
            year=2020,
            lyrics='Test lyrics here',
            topic_id=1,
            sentiment_score=0.5
        )

        assert song.title == 'Test Song'
        assert song.album == 'Test Album'
        assert song.year == 2020
        assert song.lyrics == 'Test lyrics here'
        assert song.topic_id == 1
        assert song.sentiment_score == 0.5

    def test_create_with_minimal_fields(self, db_session, sample_analysis):
        """Song.create() works with minimal required fields."""
        song = Song.create(
            analysis_id=sample_analysis.id,
            artist_name='Artist',
            title='Title'
        )

        assert song.title == 'Title'
        assert song.album is None
        assert song.year is None

    def test_bulk_create_inserts_multiple(self, db_session, sample_analysis):
        """bulk_create() inserts multiple songs."""
        songs_data = [
            {'artist_name': 'Artist', 'title': 'Song 1', 'lyrics': 'Lyrics 1'},
            {'artist_name': 'Artist', 'title': 'Song 2', 'lyrics': 'Lyrics 2'},
            {'artist_name': 'Artist', 'title': 'Song 3', 'lyrics': 'Lyrics 3'},
        ]

        Song.bulk_create(songs_data, sample_analysis.id)

        songs = Song.get_by_analysis(sample_analysis.id)
        assert len(songs) == 3

    def test_get_by_analysis_retrieves_related(self, db_session, sample_analysis):
        """get_by_analysis() returns only related songs."""
        Song.create(
            analysis_id=sample_analysis.id,
            artist_name='Artist',
            title='Song 1'
        )
        Song.create(
            analysis_id=sample_analysis.id,
            artist_name='Artist',
            title='Song 2'
        )

        songs = Song.get_by_analysis(sample_analysis.id)
        assert len(songs) == 2
        assert all(s.analysis_id == sample_analysis.id for s in songs)

    def test_to_dict_truncates_long_lyrics(self, db_session, sample_analysis):
        """to_dict() truncates lyrics over 200 chars."""
        long_lyrics = 'x' * 300
        song = Song.create(
            analysis_id=sample_analysis.id,
            artist_name='Artist',
            title='Song',
            lyrics=long_lyrics
        )

        data = song.to_dict()
        assert len(data['lyrics']) < len(long_lyrics)
        assert data['lyrics'].endswith('...')


@pytest.mark.unit
class TestTopic:
    """Tests for Topic model."""

    def test_create_with_keywords_json(self, db_session, sample_analysis):
        """Topic.create() persists keywords as JSON."""
        keywords = {'love': 0.045, 'heart': 0.032, 'soul': 0.028}
        topic = Topic.create(
            analysis_id=sample_analysis.id,
            topic_id=0,
            keywords=keywords,
            name='Love Theme',
            weight=0.15
        )

        assert topic.keywords == keywords
        assert topic.name == 'Love Theme'
        assert topic.weight == 0.15

    def test_get_top_topics_returns_sorted(self, db_session, sample_analysis):
        """get_top_topics() returns topics sorted by weight."""
        Topic.create(
            analysis_id=sample_analysis.id,
            topic_id=0,
            keywords={'a': 0.1},
            weight=0.2
        )
        Topic.create(
            analysis_id=sample_analysis.id,
            topic_id=1,
            keywords={'b': 0.1},
            weight=0.5
        )
        Topic.create(
            analysis_id=sample_analysis.id,
            topic_id=2,
            keywords={'c': 0.1},
            weight=0.1
        )

        top = Topic.get_top_topics(sample_analysis.id, limit=2)
        assert len(top) == 2
        assert top[0].weight > top[1].weight

    def test_to_dict_converts_correctly(self, db_session, sample_analysis):
        """to_dict() converts topic model correctly."""
        topic = Topic.create(
            analysis_id=sample_analysis.id,
            topic_id=0,
            keywords={'test': 0.5},
            name='Test Topic',
            weight=0.25
        )

        data = topic.to_dict()
        assert data['topic_id'] == 0
        assert data['name'] == 'Test Topic'
        assert data['keywords'] == {'test': 0.5}
        assert data['weight'] == 0.25
