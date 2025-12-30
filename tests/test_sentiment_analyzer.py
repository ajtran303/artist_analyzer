"""Unit tests for sentiment analyzer - Phase 6."""

import pytest

from pipeline.sentiment_analyzer import (
    run_sentiment,
    _analyze_sentiment,
    _aggregate_by_album,
    _aggregate_by_year,
    get_sentiment_timeline
)


@pytest.mark.unit
class TestAnalyzeSentiment:
    """Tests for _analyze_sentiment function."""

    def test_happy_lyrics_score_positive(self):
        """Happy lyrics score > 0."""
        lyrics = "I love you, you make me so happy! Joy and sunshine everywhere!"
        score = _analyze_sentiment(lyrics)
        assert score > 0

    def test_sad_lyrics_score_negative(self):
        """Sad lyrics score < 0."""
        lyrics = "Sadness fills my heart, pain and sorrow everywhere. I hate this."
        score = _analyze_sentiment(lyrics)
        assert score < 0

    def test_neutral_lyrics_score_near_zero(self):
        """Neutral lyrics score approximately 0."""
        lyrics = "The table is in the room. The door is open."
        score = _analyze_sentiment(lyrics)
        assert -0.3 <= score <= 0.3

    def test_empty_lyrics_scored_zero(self):
        """Empty lyrics scored as 0."""
        score = _analyze_sentiment('')
        assert score == 0.0

    def test_single_word_handled(self):
        """Single word lyrics handled."""
        score = _analyze_sentiment('love')
        assert isinstance(score, float)

    def test_sentiment_range(self):
        """All scores between -1 and 1."""
        lyrics_samples = [
            "I absolutely love this wonderful amazing beautiful day!",
            "I hate everything, terrible awful horrible disaster!",
            "The sky is blue.",
        ]

        for lyrics in lyrics_samples:
            score = _analyze_sentiment(lyrics)
            assert -1 <= score <= 1


@pytest.mark.unit
class TestRunSentiment:
    """Tests for run_sentiment function."""

    def test_scores_each_song(self, sample_songs):
        """Scores each song individually."""
        result = run_sentiment(sample_songs)

        assert 'songs' in result
        assert len(result['songs']) == len(sample_songs)

        for song in result['songs']:
            assert 'sentiment_score' in song
            assert isinstance(song['sentiment_score'], float)

    def test_calculates_overall_sentiment(self, sample_songs):
        """Calculates overall average sentiment."""
        result = run_sentiment(sample_songs)

        assert 'overall' in result
        assert isinstance(result['overall'], float)
        assert -1 <= result['overall'] <= 1

    def test_handles_empty_input(self):
        """Handles empty songs list."""
        result = run_sentiment([])

        assert result['by_album'] == []
        assert result['by_year'] == []
        assert result['overall'] == 0.0
        assert result['songs'] == []


@pytest.mark.unit
class TestAggregateByAlbum:
    """Tests for _aggregate_by_album function."""

    def test_aggregates_by_album(self):
        """Returns by_album list of dicts."""
        songs = [
            {'album': 'Album 1', 'sentiment_score': 0.5},
            {'album': 'Album 1', 'sentiment_score': 0.3},
            {'album': 'Album 2', 'sentiment_score': -0.2},
        ]

        result = _aggregate_by_album(songs)

        assert len(result) == 2
        assert all('album' in item for item in result)
        assert all('score' in item for item in result)
        assert all('song_count' in item for item in result)

    def test_album_has_correct_structure(self):
        """Each album entry has album, score, song_count."""
        songs = [
            {'album': 'Test Album', 'sentiment_score': 0.5},
            {'album': 'Test Album', 'sentiment_score': 0.7},
        ]

        result = _aggregate_by_album(songs)

        assert result[0]['album'] == 'Test Album'
        assert result[0]['score'] == 0.6  # Average of 0.5 and 0.7
        assert result[0]['song_count'] == 2

    def test_sorted_by_sentiment_ascending(self):
        """Results sorted by sentiment score ascending."""
        songs = [
            {'album': 'Happy Album', 'sentiment_score': 0.8},
            {'album': 'Sad Album', 'sentiment_score': -0.5},
            {'album': 'Neutral Album', 'sentiment_score': 0.0},
        ]

        result = _aggregate_by_album(songs)

        assert result[0]['score'] <= result[1]['score'] <= result[2]['score']

    def test_handles_missing_albums(self):
        """Songs with no album listed as Unknown."""
        songs = [
            {'album': None, 'sentiment_score': 0.5},
            {'album': 'Known Album', 'sentiment_score': 0.3},
        ]

        result = _aggregate_by_album(songs)

        albums = [item['album'] for item in result]
        assert 'Unknown' in albums


@pytest.mark.unit
class TestAggregateByYear:
    """Tests for _aggregate_by_year function."""

    def test_aggregates_by_year(self):
        """Returns by_year list of dicts."""
        songs = [
            {'year': 2020, 'sentiment_score': 0.5},
            {'year': 2020, 'sentiment_score': 0.3},
            {'year': 2021, 'sentiment_score': -0.2},
        ]

        result = _aggregate_by_year(songs)

        assert len(result) == 2
        assert all('year' in item for item in result)
        assert all('score' in item for item in result)
        assert all('song_count' in item for item in result)

    def test_year_has_correct_structure(self):
        """Each year entry has year, score, song_count."""
        songs = [
            {'year': 2020, 'sentiment_score': 0.4},
            {'year': 2020, 'sentiment_score': 0.6},
        ]

        result = _aggregate_by_year(songs)

        assert result[0]['year'] == 2020
        assert result[0]['score'] == 0.5
        assert result[0]['song_count'] == 2

    def test_sorted_by_year_ascending(self):
        """Results sorted by year ascending."""
        songs = [
            {'year': 2022, 'sentiment_score': 0.3},
            {'year': 2020, 'sentiment_score': 0.5},
            {'year': 2021, 'sentiment_score': 0.4},
        ]

        result = _aggregate_by_year(songs)

        years = [item['year'] for item in result]
        assert years == sorted(years)

    def test_handles_missing_years(self):
        """Songs without year skipped."""
        songs = [
            {'year': None, 'sentiment_score': 0.5},
            {'year': 2020, 'sentiment_score': 0.3},
        ]

        result = _aggregate_by_year(songs)

        years = [item['year'] for item in result]
        assert None not in years
        assert len(result) == 1


@pytest.mark.unit
class TestGetSentimentTimeline:
    """Tests for get_sentiment_timeline function."""

    def test_returns_timeline_data(self):
        """Returns timeline data for chart."""
        songs = [
            {'year': 2020, 'sentiment_score': 0.5},
            {'year': 2021, 'sentiment_score': 0.3},
        ]

        result = get_sentiment_timeline(songs)

        assert len(result) == 2
        assert all('year' in item for item in result)
        assert all('score' in item for item in result)
