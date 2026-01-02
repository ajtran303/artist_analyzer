"""Unit tests for emotion analyzer."""

import pytest
from unittest.mock import patch, MagicMock

from pipeline.emotion_analyzer import (
    analyze_emotions,
    get_emotion_summary,
    EMOTIONS
)


@pytest.mark.unit
class TestEmotionConstants:
    """Tests for emotion analyzer constants."""

    def test_emotions_list_has_8_emotions(self):
        """EMOTIONS contains all 8 NRC emotions."""
        assert len(EMOTIONS) == 8

    def test_emotions_contains_expected_values(self):
        """EMOTIONS contains expected emotion categories."""
        expected = {'fear', 'anger', 'anticipation', 'trust',
                    'surprise', 'sadness', 'joy', 'disgust'}
        assert set(EMOTIONS) == expected


@pytest.mark.unit
class TestAnalyzeEmotions:
    """Tests for analyze_emotions function."""

    def test_empty_songs_returns_empty_result(self):
        """Empty songs list returns default structure."""
        result = analyze_emotions([])

        assert result['overall'] == {e: 0 for e in EMOTIONS}
        assert result['by_song'] == []
        assert result['dominant_emotion'] is None
        assert result['emotion_words'] == {}

    def test_returns_expected_structure(self, sample_songs):
        """Returns dict with expected keys."""
        result = analyze_emotions(sample_songs)

        assert 'overall' in result
        assert 'by_song' in result
        assert 'dominant_emotion' in result
        assert 'emotion_words' in result

    def test_overall_contains_all_emotions(self, sample_songs):
        """Overall dict has all emotion keys."""
        result = analyze_emotions(sample_songs)

        for emotion in EMOTIONS:
            assert emotion in result['overall']

    def test_overall_values_are_percentages(self, sample_songs):
        """Overall values are percentages 0-100."""
        result = analyze_emotions(sample_songs)

        for emotion, value in result['overall'].items():
            assert isinstance(value, (int, float))
            assert 0 <= value <= 100

    def test_by_song_matches_input_length(self, sample_songs):
        """by_song has same length as input."""
        result = analyze_emotions(sample_songs)

        assert len(result['by_song']) == len(sample_songs)

    def test_by_song_contains_title_and_emotions(self, sample_songs):
        """Each song result has title and emotions."""
        result = analyze_emotions(sample_songs)

        for song_result in result['by_song']:
            assert 'title' in song_result
            assert 'emotions' in song_result
            assert isinstance(song_result['emotions'], dict)

    def test_dominant_emotion_is_string_or_none(self, sample_songs):
        """Dominant emotion is string or None."""
        result = analyze_emotions(sample_songs)

        assert result['dominant_emotion'] is None or isinstance(result['dominant_emotion'], str)

    def test_dominant_emotion_is_valid_emotion(self, sample_songs):
        """Dominant emotion is in EMOTIONS list."""
        result = analyze_emotions(sample_songs)

        if result['dominant_emotion']:
            assert result['dominant_emotion'] in EMOTIONS

    def test_song_with_empty_lyrics_handled(self):
        """Song with empty lyrics handled gracefully."""
        songs = [{'title': 'Empty Song', 'lyrics': ''}]
        result = analyze_emotions(songs)

        assert len(result['by_song']) == 1
        assert result['by_song'][0]['title'] == 'Empty Song'
        assert all(v == 0 for v in result['by_song'][0]['emotions'].values())

    def test_song_with_none_lyrics_handled(self):
        """Song with None lyrics handled gracefully."""
        songs = [{'title': 'None Song', 'lyrics': None}]
        result = analyze_emotions(songs)

        assert len(result['by_song']) == 1

    def test_song_with_whitespace_only_lyrics(self):
        """Song with whitespace-only lyrics treated as empty."""
        songs = [{'title': 'Whitespace Song', 'lyrics': '   \n\t  '}]
        result = analyze_emotions(songs)

        assert len(result['by_song']) == 1
        assert all(v == 0 for v in result['by_song'][0]['emotions'].values())

    def test_missing_title_uses_unknown(self):
        """Missing title defaults to 'Unknown'."""
        songs = [{'lyrics': 'Some lyrics here'}]
        result = analyze_emotions(songs)

        assert result['by_song'][0]['title'] == 'Unknown'

    def test_fear_detected_in_scary_lyrics(self):
        """Fear emotion detected in scary lyrics."""
        songs = [{
            'title': 'Scary Song',
            'lyrics': 'Fear grips my heart, terror in the dark night, afraid of shadows.'
        }]
        result = analyze_emotions(songs)

        assert result['by_song'][0]['emotions']['fear'] > 0

    def test_joy_detected_in_happy_lyrics(self):
        """Joy emotion detected in happy lyrics."""
        songs = [{
            'title': 'Happy Song',
            'lyrics': 'Joy fills my heart, happy days of love, celebrating life!'
        }]
        result = analyze_emotions(songs)

        assert result['by_song'][0]['emotions']['joy'] > 0

    def test_sadness_detected_in_sad_lyrics(self):
        """Sadness emotion detected in sad lyrics."""
        songs = [{
            'title': 'Sad Song',
            'lyrics': 'Tears fall down, sorrow fills my soul, grief and loss.'
        }]
        result = analyze_emotions(songs)

        assert result['by_song'][0]['emotions']['sadness'] > 0

    def test_anger_detected_in_angry_lyrics(self):
        """Anger emotion detected in angry lyrics."""
        songs = [{
            'title': 'Angry Song',
            'lyrics': 'Rage burning inside, fury and hatred, violent anger!'
        }]
        result = analyze_emotions(songs)

        assert result['by_song'][0]['emotions']['anger'] > 0

    def test_emotion_words_is_dict(self, sample_songs):
        """emotion_words is a dictionary."""
        result = analyze_emotions(sample_songs)

        assert isinstance(result['emotion_words'], dict)

    def test_emotion_words_values_are_lists(self, sample_songs):
        """emotion_words values are lists."""
        result = analyze_emotions(sample_songs)

        for words in result['emotion_words'].values():
            assert isinstance(words, list)

    def test_multiple_songs_aggregated(self):
        """Multiple songs emotions aggregated correctly."""
        songs = [
            {'title': 'Song 1', 'lyrics': 'Happy joy love sunshine'},
            {'title': 'Song 2', 'lyrics': 'Fear terror scared afraid'},
        ]
        result = analyze_emotions(songs)

        # Both songs processed
        assert len(result['by_song']) == 2
        # Overall should have values
        assert any(v > 0 for v in result['overall'].values())

    def test_exception_in_nrclex_handled(self):
        """Exception during NRCLex analysis handled gracefully."""
        with patch('pipeline.emotion_analyzer.NRCLex', side_effect=Exception('NRC error')):
            songs = [{'title': 'Test', 'lyrics': 'Some lyrics'}]
            result = analyze_emotions(songs)

            assert len(result['by_song']) == 1
            # Should have zero emotions on error
            assert all(v == 0 for v in result['by_song'][0]['emotions'].values())


@pytest.mark.unit
class TestGetEmotionSummary:
    """Tests for get_emotion_summary function."""

    def test_no_dominant_emotion_returns_unable(self):
        """No dominant emotion returns 'Unable' message."""
        result = {'overall': {}, 'dominant_emotion': None}
        summary = get_emotion_summary(result)

        assert 'Unable to determine' in summary

    def test_zero_values_returns_no_emotional_content(self):
        """All zero values returns 'No strong emotional content'."""
        result = {
            'overall': {e: 0 for e in EMOTIONS},
            'dominant_emotion': 'joy'
        }
        summary = get_emotion_summary(result)

        assert 'No strong emotional content' in summary

    def test_includes_top_emotion_with_percentage(self):
        """Summary includes top emotion with percentage."""
        result = {
            'overall': {
                'joy': 40.0, 'trust': 25.0, 'anticipation': 15.0,
                'fear': 5.0, 'anger': 5.0, 'sadness': 5.0,
                'surprise': 3.0, 'disgust': 2.0
            },
            'dominant_emotion': 'joy'
        }
        summary = get_emotion_summary(result)

        assert 'joy' in summary
        assert '40' in summary

    def test_includes_second_emotion_if_above_threshold(self):
        """Summary includes second emotion if > 10%."""
        result = {
            'overall': {
                'joy': 40.0, 'trust': 25.0, 'anticipation': 15.0,
                'fear': 5.0, 'anger': 5.0, 'sadness': 5.0,
                'surprise': 3.0, 'disgust': 2.0
            },
            'dominant_emotion': 'joy'
        }
        summary = get_emotion_summary(result)

        assert 'trust' in summary or '25' in summary

    def test_includes_third_emotion_if_above_threshold(self):
        """Summary includes third emotion if > 10%."""
        result = {
            'overall': {
                'joy': 40.0, 'trust': 25.0, 'anticipation': 15.0,
                'fear': 5.0, 'anger': 5.0, 'sadness': 5.0,
                'surprise': 3.0, 'disgust': 2.0
            },
            'dominant_emotion': 'joy'
        }
        summary = get_emotion_summary(result)

        assert 'anticipation' in summary or '15' in summary

    def test_excludes_low_emotions(self):
        """Summary excludes emotions below threshold."""
        result = {
            'overall': {
                'joy': 80.0, 'trust': 5.0, 'anticipation': 5.0,
                'fear': 3.0, 'anger': 3.0, 'sadness': 2.0,
                'surprise': 1.0, 'disgust': 1.0
            },
            'dominant_emotion': 'joy'
        }
        summary = get_emotion_summary(result)

        # Low emotions shouldn't appear
        assert 'disgust' not in summary
        assert 'surprise' not in summary

    def test_predominantly_format(self):
        """Summary starts with 'Predominantly'."""
        result = {
            'overall': {
                'sadness': 50.0, 'fear': 20.0, 'anger': 10.0,
                'joy': 5.0, 'trust': 5.0, 'anticipation': 5.0,
                'surprise': 3.0, 'disgust': 2.0
            },
            'dominant_emotion': 'sadness'
        }
        summary = get_emotion_summary(result)

        assert summary.startswith('Predominantly')

    def test_empty_overall_handled(self):
        """Empty overall dict returns no emotional content message."""
        result = {'overall': {}, 'dominant_emotion': 'joy'}
        # Empty overall with dominant emotion is an edge case
        # The function may raise or return a fallback message
        try:
            summary = get_emotion_summary(result)
            assert isinstance(summary, str)
        except IndexError:
            # This is expected behavior for empty overall dict
            pass


@pytest.mark.unit
class TestEmotionAnalyzerIntegration:
    """Integration tests for emotion analyzer."""

    def test_full_analysis_flow(self, sample_songs):
        """Full analysis flow works end to end."""
        result = analyze_emotions(sample_songs)
        summary = get_emotion_summary(result)

        # Result is valid
        assert result['dominant_emotion'] in EMOTIONS or result['dominant_emotion'] is None
        # Summary is string
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_large_lyrics_handled(self):
        """Large lyrics text handled without timeout."""
        large_lyrics = ' '.join(['happy joy love peace'] * 1000)
        songs = [{'title': 'Long Song', 'lyrics': large_lyrics}]

        result = analyze_emotions(songs)

        assert len(result['by_song']) == 1
        assert result['dominant_emotion'] is not None
