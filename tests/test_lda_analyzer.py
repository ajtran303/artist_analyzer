"""Unit tests for LDA analyzer - Phase 5."""

import pytest

from pipeline.lda_analyzer import run_lda, run_combined_lda, _extract_topics, _generate_topic_name, _parse_topic_words, assign_topics_to_songs


@pytest.mark.unit
class TestRunLda:
    """Tests for run_lda function."""

    def test_creates_dictionary_and_corpus(self, preprocessed_songs):
        """run_lda() creates Dictionary and Corpus."""
        # Need more songs for meaningful LDA
        songs = preprocessed_songs * 5  # Duplicate to get 15 songs

        result = run_lda(songs, num_topics=3)

        assert isinstance(result, list)

    def test_trains_lda_model(self):
        """run_lda() trains LDA model with correct params."""
        songs = [
            {'tokens': ['love', 'heart', 'soul', 'passion']},
            {'tokens': ['dark', 'night', 'shadow', 'pain']},
            {'tokens': ['dream', 'hope', 'light', 'future']},
            {'tokens': ['love', 'romance', 'kiss', 'heart']},
            {'tokens': ['darkness', 'death', 'sorrow', 'tears']},
        ] * 4  # 20 songs

        result = run_lda(songs, num_topics=3, random_state=42)

        assert len(result) <= 3

    def test_returns_topics_list(self):
        """run_lda() returns list of topic dicts."""
        songs = [
            {'tokens': ['love', 'heart', 'beautiful', 'romance']},
            {'tokens': ['dark', 'night', 'shadow', 'pain']},
        ] * 10

        result = run_lda(songs, num_topics=2)

        assert isinstance(result, list)
        if result:  # May be empty with small corpus
            assert 'id' in result[0]
            assert 'name' in result[0]
            assert 'keywords' in result[0]
            assert 'weight' in result[0]

    def test_topics_sorted_by_weight(self):
        """Topics are sorted by weight descending."""
        songs = [
            {'tokens': ['love', 'heart', 'soul', 'passion', 'romance']},
            {'tokens': ['dark', 'night', 'shadow', 'pain', 'sorrow']},
            {'tokens': ['dream', 'hope', 'light', 'future', 'believe']},
        ] * 10

        result = run_lda(songs, num_topics=3)

        if len(result) > 1:
            for i in range(len(result) - 1):
                assert result[i]['weight'] >= result[i + 1]['weight']

    def test_handles_few_documents(self):
        """Handles less than num_topics documents gracefully."""
        songs = [
            {'tokens': ['love', 'heart']},
            {'tokens': ['dark', 'night']},
        ]

        result = run_lda(songs, num_topics=5)

        # Should reduce num_topics or return empty
        assert isinstance(result, list)
        assert len(result) <= 2

    def test_handles_duplicate_songs(self):
        """Handles repeated lyrics without crashing."""
        songs = [{'tokens': ['love', 'heart', 'soul']}] * 20

        result = run_lda(songs, num_topics=2)

        assert isinstance(result, list)

    def test_handles_empty_input(self):
        """Handles empty input gracefully."""
        result = run_lda([], num_topics=5)
        assert result == []

    def test_consistent_results_with_random_state(self):
        """Results are consistent with same random_state."""
        songs = [
            {'tokens': ['love', 'heart', 'soul', 'passion']},
            {'tokens': ['dark', 'night', 'shadow', 'pain']},
        ] * 10

        result1 = run_lda(songs, num_topics=2, random_state=42)
        result2 = run_lda(songs, num_topics=2, random_state=42)

        # With same seed, should get similar results
        if result1 and result2:
            assert len(result1) == len(result2)


@pytest.mark.unit
class TestExtractTopics:
    """Tests for _extract_topics function."""

    def test_extracts_keywords_from_topics(self):
        """Keywords extracted from Gensim output."""
        # This would require a trained model
        # Testing the helper functions instead
        pass


@pytest.mark.unit
class TestGenerateTopicName:
    """Tests for _generate_topic_name function."""

    def test_generates_name_from_words(self):
        """Generates readable name from top words using semantic categories."""
        name = _generate_topic_name(['love', 'heart', 'soul'])
        # Should match "Love & Emotion" category
        assert 'Love' in name

    def test_handles_empty_words(self):
        """Handles empty words list."""
        name = _generate_topic_name([])
        assert name == 'Unknown Theme'

    def test_handles_single_word(self):
        """Handles single word."""
        name = _generate_topic_name(['love'])
        assert 'Love' in name

    def test_falls_back_to_words_when_no_category_match(self):
        """Falls back to word names when no category matches."""
        name = _generate_topic_name(['xyz', 'abc'])
        # Should show the words since no category matches
        assert 'xyz' in name.lower() or 'abc' in name.lower()


@pytest.mark.unit
class TestParseTopicWords:
    """Tests for _parse_topic_words function."""

    def test_parses_topic_string(self):
        """Parses Gensim topic string format."""
        topic_str = '0.045*"word1" + 0.032*"word2" + 0.028*"word3"'
        result = _parse_topic_words(topic_str)

        assert len(result) == 3
        assert result[0] == ('word1', 0.045)
        assert result[1] == ('word2', 0.032)

    def test_handles_empty_string(self):
        """Handles empty string."""
        result = _parse_topic_words('')
        assert result == []


@pytest.mark.unit
class TestAssignTopicsToSongs:
    """Tests for assign_topics_to_songs function."""

    def test_assigns_topic_ids(self):
        """Assigns topic_id to each song."""
        songs = [
            {'tokens': ['love', 'heart', 'soul', 'passion']},
            {'tokens': ['dark', 'night', 'shadow', 'pain']},
        ] * 10

        result = assign_topics_to_songs(songs, num_topics=2)

        # Some songs should have topic_id assigned
        assigned = [s for s in result if s.get('topic_id') is not None]
        assert len(assigned) > 0

    def test_handles_empty_tokens(self):
        """Songs with empty tokens don't crash."""
        songs = [
            {'tokens': ['love', 'heart']},
            {'tokens': []},
            {'tokens': ['dark', 'night']},
        ] * 5

        result = assign_topics_to_songs(songs, num_topics=2)

        assert len(result) == len(songs)


@pytest.mark.unit
class TestRunCombinedLda:
    """Tests for run_combined_lda function."""

    def test_combines_songs_from_two_albums(self):
        """Combines songs from both albums for analysis."""
        songs_a = [
            {'tokens': ['love', 'heart', 'soul', 'passion'], 'stem_to_word': {'love': 'Love'}},
            {'tokens': ['romance', 'kiss', 'embrace', 'touch'], 'stem_to_word': {}},
        ] * 5

        songs_b = [
            {'tokens': ['dark', 'night', 'shadow', 'pain'], 'stem_to_word': {'dark': 'Dark'}},
            {'tokens': ['sorrow', 'death', 'tears', 'grief'], 'stem_to_word': {}},
        ] * 5

        result = run_combined_lda(songs_a, songs_b, num_topics=2)

        assert isinstance(result, list)

    def test_returns_topics_list(self):
        """Returns list of topic dicts."""
        songs_a = [{'tokens': ['love', 'heart', 'beautiful']}] * 10
        songs_b = [{'tokens': ['dark', 'night', 'shadow']}] * 10

        result = run_combined_lda(songs_a, songs_b, num_topics=2)

        assert isinstance(result, list)
        if result:
            assert 'id' in result[0]
            assert 'name' in result[0]
            assert 'keywords' in result[0]

    def test_handles_empty_album_a(self):
        """Handles empty first album gracefully."""
        songs_a = []
        songs_b = [{'tokens': ['love', 'heart']}] * 10

        result = run_combined_lda(songs_a, songs_b, num_topics=2)

        assert isinstance(result, list)

    def test_handles_empty_album_b(self):
        """Handles empty second album gracefully."""
        songs_a = [{'tokens': ['love', 'heart']}] * 10
        songs_b = []

        result = run_combined_lda(songs_a, songs_b, num_topics=2)

        assert isinstance(result, list)

    def test_handles_both_empty(self):
        """Handles both albums empty gracefully."""
        result = run_combined_lda([], [], num_topics=2)

        assert result == []

    def test_merges_stem_mappings(self):
        """Merges stem_to_word mappings from both albums."""
        songs_a = [
            {'tokens': ['love'], 'stem_to_word': {'lov': 'Love'}},
        ] * 5
        songs_b = [
            {'tokens': ['dark'], 'stem_to_word': {'dark': 'Dark'}},
        ] * 5

        # This test just ensures no crash when merging
        result = run_combined_lda(songs_a, songs_b, num_topics=2)
        assert isinstance(result, list)

    def test_consistent_with_random_state(self):
        """Results are consistent with same random_state."""
        songs_a = [{'tokens': ['love', 'heart', 'soul']}] * 10
        songs_b = [{'tokens': ['dark', 'night', 'pain']}] * 10

        result1 = run_combined_lda(songs_a, songs_b, num_topics=2, random_state=42)
        result2 = run_combined_lda(songs_a, songs_b, num_topics=2, random_state=42)

        if result1 and result2:
            assert len(result1) == len(result2)
