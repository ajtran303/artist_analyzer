"""Unit tests for bonus analyzer - Phase 7."""

import pytest

from pipeline.bonus_analyzer import (
    analyze_word_frequency,
    analyze_metaphors,
    get_word_cloud_data,
    analyze_vocabulary_richness
)


@pytest.mark.unit
class TestAnalyzeWordFrequency:
    """Tests for analyze_word_frequency function."""

    def test_returns_top_words(self):
        """Returns list of top words by frequency."""
        songs = [
            {'tokens': ['love', 'love', 'heart', 'soul']},
            {'tokens': ['love', 'dream', 'heart']},
        ]

        result = analyze_word_frequency(songs, top_n=5)

        assert isinstance(result, list)
        assert len(result) <= 5
        assert all('word' in item for item in result)
        assert all('frequency' in item for item in result)

    def test_sorted_by_frequency_descending(self):
        """Results sorted by frequency descending."""
        songs = [
            {'tokens': ['rare', 'common', 'common', 'common', 'frequent', 'frequent']},
        ]

        result = analyze_word_frequency(songs)

        if len(result) > 1:
            for i in range(len(result) - 1):
                assert result[i]['frequency'] >= result[i + 1]['frequency']

    def test_counts_correctly(self):
        """Word frequencies counted correctly."""
        songs = [
            {'tokens': ['love', 'love', 'love', 'love', 'love']},  # 5 times
            {'tokens': ['heart', 'heart', 'heart']},  # 3 times
        ]

        result = analyze_word_frequency(songs)

        # Words are now capitalized
        love_entry = next((item for item in result if item['word'].lower() == 'love'), None)
        assert love_entry is not None
        assert love_entry['frequency'] == 5

    def test_respects_top_n_limit(self):
        """Only returns top N words."""
        songs = [
            {'tokens': ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j']},
        ]

        result = analyze_word_frequency(songs, top_n=3)
        assert len(result) <= 3

    def test_handles_empty_input(self):
        """Handles empty input."""
        result = analyze_word_frequency([])
        assert result == []

    def test_handles_empty_tokens(self):
        """Handles songs with empty tokens."""
        songs = [{'tokens': []}]
        result = analyze_word_frequency(songs)
        assert result == []


@pytest.mark.unit
class TestAnalyzeMetaphors:
    """Tests for analyze_metaphors function."""

    def test_identifies_themes(self):
        """Identifies metaphor themes in lyrics."""
        songs = [
            {'lyrics': 'Death comes for us all, dying slowly in the dark darkness'},
            {'lyrics': 'Love fills my heart with passion and desire'},
        ]

        result = analyze_metaphors(songs)

        metaphors = [item['metaphor'] for item in result]
        assert 'death' in metaphors or 'darkness' in metaphors or 'love' in metaphors

    def test_returns_correct_structure(self):
        """Returns list of metaphor dicts."""
        songs = [{'lyrics': 'Love and pain, death and life'}]

        result = analyze_metaphors(songs)

        assert isinstance(result, list)
        if result:
            assert 'metaphor' in result[0]
            assert 'frequency' in result[0]

    def test_counts_keywords(self):
        """Counts related keywords for each theme."""
        songs = [
            {'lyrics': 'death dying dead die kill grave funeral'}
        ]

        result = analyze_metaphors(songs)

        death_entry = next((item for item in result if item['metaphor'] == 'death'), None)
        assert death_entry is not None
        assert death_entry['frequency'] >= 7  # All death-related words

    def test_case_insensitive(self):
        """Matching is case insensitive."""
        songs = [
            {'lyrics': 'DEATH Death death DYING Dying dying'}
        ]

        result = analyze_metaphors(songs)

        death_entry = next((item for item in result if item['metaphor'] == 'death'), None)
        assert death_entry is not None
        assert death_entry['frequency'] >= 6

    def test_sorted_by_frequency_descending(self):
        """Results sorted by frequency descending."""
        songs = [
            {'lyrics': 'love love love death pain pain'}
        ]

        result = analyze_metaphors(songs)

        if len(result) > 1:
            for i in range(len(result) - 1):
                assert result[i]['frequency'] >= result[i + 1]['frequency']

    def test_handles_empty_input(self):
        """Handles empty input."""
        result = analyze_metaphors([])
        assert result == []

    def test_handles_no_metaphors(self):
        """Handles lyrics with no recognized metaphors."""
        songs = [{'lyrics': 'The table is wooden and brown'}]

        result = analyze_metaphors(songs)
        # Should return empty or list with 0 frequencies
        assert isinstance(result, list)


@pytest.mark.unit
class TestGetWordCloudData:
    """Tests for get_word_cloud_data function."""

    def test_returns_dict_format(self):
        """Returns dict mapping words to frequencies."""
        songs = [
            {'tokens': ['love', 'love', 'heart']},
        ]

        result = get_word_cloud_data(songs)

        assert isinstance(result, dict)
        # Keys are now capitalized
        assert 'Love' in result or 'love' in result
        love_count = result.get('Love', result.get('love', 0))
        assert love_count == 2

    def test_respects_max_words(self):
        """Respects max_words limit."""
        songs = [
            {'tokens': list('abcdefghijklmnop')},
        ]

        result = get_word_cloud_data(songs, max_words=5)
        assert len(result) <= 5


@pytest.mark.unit
class TestAnalyzeVocabularyRichness:
    """Tests for analyze_vocabulary_richness function."""

    def test_returns_metrics(self):
        """Returns vocabulary metrics."""
        songs = [
            {'tokens': ['love', 'heart', 'soul', 'love', 'heart']},
        ]

        result = analyze_vocabulary_richness(songs)

        assert 'total_words' in result
        assert 'unique_words' in result
        assert 'vocabulary_richness' in result
        assert 'average_word_length' in result

    def test_calculates_correctly(self):
        """Metrics calculated correctly."""
        songs = [
            {'tokens': ['love', 'love', 'heart']},  # 3 total, 2 unique
        ]

        result = analyze_vocabulary_richness(songs)

        assert result['total_words'] == 3
        assert result['unique_words'] == 2
        assert result['vocabulary_richness'] == round(2 / 3, 4)

    def test_handles_empty_input(self):
        """Handles empty input."""
        result = analyze_vocabulary_richness([])

        assert result['total_words'] == 0
        assert result['unique_words'] == 0
        assert result['vocabulary_richness'] == 0.0
