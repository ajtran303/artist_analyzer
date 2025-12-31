"""Unit tests for sentiment analyzer - Phase 6."""

import pytest

from pipeline.sentiment_analyzer import (
    run_sentiment,
    _analyze_sentiment,
    _aggregate_by_album,
    _aggregate_by_year,
    get_sentiment_timeline,
    find_most_emotional_passage,
    find_most_emotional_passages,
    _split_into_passages
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


@pytest.mark.unit
class TestSplitIntoPassages:
    """Tests for _split_into_passages function."""

    def test_splits_by_double_newlines(self):
        """Splits lyrics by double newlines (verse breaks)."""
        lyrics = "First verse line one\nFirst verse line two\n\nSecond verse line one\nSecond verse line two"
        passages = _split_into_passages(lyrics)

        assert len(passages) == 2
        assert "First verse" in passages[0]
        assert "Second verse" in passages[1]

    def test_falls_back_to_line_chunks(self):
        """Falls back to 4-line chunks when no double newlines."""
        lyrics = "Line one\nLine two\nLine three\nLine four\nLine five\nLine six\nLine seven\nLine eight"
        passages = _split_into_passages(lyrics)

        assert len(passages) == 2
        assert "Line one" in passages[0]
        assert "Line five" in passages[1]

    def test_returns_whole_lyrics_for_short_text(self):
        """Returns whole lyrics as single passage for short text."""
        lyrics = "Short\nlyrics"
        passages = _split_into_passages(lyrics)

        assert len(passages) == 1
        assert "Short" in passages[0]

    def test_handles_empty_string(self):
        """Handles empty lyrics."""
        passages = _split_into_passages("")
        assert passages == [""]

    def test_strips_whitespace(self):
        """Strips whitespace from passages."""
        lyrics = "  Verse one  \n\n  Verse two  "
        passages = _split_into_passages(lyrics)

        assert passages[0] == "Verse one"
        assert passages[1] == "Verse two"


@pytest.mark.unit
class TestFindMostEmotionalPassages:
    """Tests for find_most_emotional_passages function."""

    def test_finds_both_positive_and_negative(self):
        """Finds both the most positive and most negative passages."""
        songs = [
            {
                'title': 'Mixed Song',
                'lyrics': "I love everything! Joy and happiness forever!\n\nI hate everything! Pain and suffering everywhere!"
            }
        ]

        result = find_most_emotional_passages(songs)

        assert result is not None
        assert 'most_positive' in result
        assert 'most_negative' in result
        assert result['most_positive'] is not None
        assert result['most_negative'] is not None
        assert result['most_positive']['score'] >= 0.05  # Above positive threshold
        assert result['most_negative']['score'] <= -0.05  # Below negative threshold

    def test_finds_passages_across_multiple_songs(self):
        """Finds passages across multiple songs."""
        songs = [
            {
                'title': 'Happy Song',
                'lyrics': "I absolutely love this wonderful amazing beautiful fantastic day!"
            },
            {
                'title': 'Sad Song',
                'lyrics': "I hate everything terrible awful horrible disaster pain!"
            }
        ]

        result = find_most_emotional_passages(songs)

        assert result['most_positive']['song_title'] == 'Happy Song'
        assert result['most_negative']['song_title'] == 'Sad Song'

    def test_returns_none_values_for_empty_songs(self):
        """Returns dict with None values when no songs provided."""
        result = find_most_emotional_passages([])

        assert result == {'most_positive': None, 'most_negative': None}

    def test_returns_none_values_for_songs_without_lyrics(self):
        """Returns dict with None values when songs have no lyrics."""
        songs = [
            {'title': 'No Lyrics', 'lyrics': ''},
            {'title': 'Also No Lyrics', 'lyrics': '   '}
        ]

        result = find_most_emotional_passages(songs)

        assert result['most_positive'] is None
        assert result['most_negative'] is None

    def test_result_structure(self):
        """Result has correct structure for each passage."""
        songs = [
            {
                'title': 'Test Song',
                'lyrics': "I love this beautiful wonderful amazing day with so much joy!"
            }
        ]

        result = find_most_emotional_passages(songs)

        # Check most_positive structure
        pos = result['most_positive']
        assert pos is not None
        assert 'song_title' in pos
        assert 'passage' in pos
        assert 'score' in pos

    def test_neutral_content_returns_none(self):
        """Neutral content (score between -0.05 and 0.05) returns None."""
        songs = [
            {
                'title': 'Neutral Song',
                'lyrics': "The table is in the room. The door is open. The window is closed."
            }
        ]

        result = find_most_emotional_passages(songs)

        # Both should be None since content is neutral
        assert result['most_positive'] is None
        assert result['most_negative'] is None

    def test_same_passage_not_returned_twice(self):
        """When only one emotional passage exists, it's not duplicated."""
        songs = [
            {
                'title': 'Only Song',
                'lyrics': "I love this wonderful amazing beautiful fantastic incredible day!"
            }
        ]

        result = find_most_emotional_passages(songs)

        # Only one should be set (the positive one since the text is positive)
        assert result['most_positive'] is not None
        assert result['most_negative'] is None  # Not duplicated

    def test_only_positive_content(self):
        """Album with only positive content returns only most_positive."""
        songs = [
            {
                'title': 'Happy Song',
                'lyrics': "Joy and love everywhere!\n\nHappiness and wonderful feelings!"
            }
        ]

        result = find_most_emotional_passages(songs)

        assert result['most_positive'] is not None
        assert result['most_negative'] is None  # No negative content

    def test_only_negative_content(self):
        """Album with only negative content returns only most_negative."""
        songs = [
            {
                'title': 'Sad Song',
                'lyrics': "Pain and suffering everywhere!\n\nTerrible awful horrible disaster!"
            }
        ]

        result = find_most_emotional_passages(songs)

        assert result['most_positive'] is None  # No positive content
        assert result['most_negative'] is not None


@pytest.mark.unit
class TestFindMostEmotionalPassageLegacy:
    """Tests for find_most_emotional_passage function (legacy/deprecated)."""

    def test_returns_most_intense_passage(self):
        """Returns the passage with highest absolute sentiment."""
        songs = [
            {
                'title': 'Mixed Song',
                'lyrics': "The table is in the room.\n\nI hate everything terrible awful horrible disaster pain suffering!"
            }
        ]

        result = find_most_emotional_passage(songs)

        assert result is not None
        assert result['sentiment_type'] == 'negative'
        assert result['score'] < 0

    def test_returns_none_for_empty_songs(self):
        """Returns None when no songs provided."""
        result = find_most_emotional_passage([])
        assert result is None

    def test_result_has_sentiment_type(self):
        """Result includes sentiment_type field."""
        songs = [
            {
                'title': 'Test Song',
                'lyrics': "I love this beautiful wonderful amazing day with so much joy!"
            }
        ]

        result = find_most_emotional_passage(songs)

        assert result is not None
        assert 'sentiment_type' in result
        assert result['sentiment_type'] in ['positive', 'negative']
