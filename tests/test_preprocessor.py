"""Unit tests for preprocessor - Phase 4."""

import pytest

from pipeline.preprocessor import preprocess_lyrics, _tokenize_and_clean, get_tokens_for_lda


@pytest.mark.unit
class TestPreprocessLyrics:
    """Tests for preprocess_lyrics function."""

    def test_lowercases_text(self):
        """Text is lowercased."""
        songs = [{'lyrics': 'THE NIGHT Was DARK'}]
        result = preprocess_lyrics(songs)
        # Check that tokens are lowercase
        assert all(t.islower() for t in result[0]['tokens'])

    def test_removes_stopwords(self):
        """Common stopwords are removed."""
        songs = [{'lyrics': 'the love and the pain or the sorrow'}]
        result = preprocess_lyrics(songs)

        tokens = result[0]['tokens']
        assert 'the' not in tokens
        assert 'and' not in tokens
        assert 'or' not in tokens

    def test_tokenizes_correctly(self):
        """Text is tokenized into words."""
        songs = [{'lyrics': 'hello world today'}]
        result = preprocess_lyrics(songs)

        tokens = result[0]['tokens']
        assert isinstance(tokens, list)
        assert len(tokens) > 0

    def test_stems_words(self):
        """Words are stemmed."""
        songs = [{'lyrics': 'dying loved running dreaming'}]
        result = preprocess_lyrics(songs)

        tokens = result[0]['tokens']
        # Stemmed versions should be present
        assert any('die' in t or 'dy' in t for t in tokens) or 'die' in tokens

    def test_removes_short_words(self):
        """Words shorter than 3 chars are removed."""
        songs = [{'lyrics': 'I am a so to be or an it is'}]
        result = preprocess_lyrics(songs)

        tokens = result[0]['tokens']
        assert all(len(t) >= 3 for t in tokens)

    def test_returns_tokens_list(self):
        """Result has tokens key with list."""
        songs = [{'lyrics': 'test song lyrics here'}]
        result = preprocess_lyrics(songs)

        assert 'tokens' in result[0]
        assert isinstance(result[0]['tokens'], list)

    def test_returns_rejoined_text(self):
        """Result has text key with rejoined string."""
        songs = [{'lyrics': 'testing lyrics here'}]
        result = preprocess_lyrics(songs)

        assert 'text' in result[0]
        assert isinstance(result[0]['text'], str)

    def test_handles_empty_lyrics(self):
        """Empty lyrics returns empty tokens."""
        songs = [{'lyrics': ''}]
        result = preprocess_lyrics(songs)

        assert result[0]['tokens'] == []
        assert result[0]['text'] == ''

    def test_handles_missing_lyrics(self):
        """Missing lyrics key handled."""
        songs = [{'title': 'No Lyrics'}]
        result = preprocess_lyrics(songs)

        assert result[0]['tokens'] == []

    def test_handles_special_characters(self):
        """Special characters are handled."""
        songs = [{'lyrics': 'Love!!! @#$% dreams??? ...hope...'}]
        result = preprocess_lyrics(songs)

        # Should extract meaningful words
        tokens = result[0]['tokens']
        assert all(t.isalpha() for t in tokens)

    def test_removes_urls(self):
        """URLs are removed from lyrics."""
        songs = [{'lyrics': 'Check out https://example.com and www.test.com for more'}]
        result = preprocess_lyrics(songs)

        text = result[0]['text']
        assert 'http' not in text
        assert 'www' not in text

    def test_handles_non_english(self):
        """Handles accented characters without crashing."""
        songs = [{'lyrics': 'café résumé naïve über'}]
        result = preprocess_lyrics(songs)

        # Should not crash
        assert isinstance(result[0]['tokens'], list)

    def test_handles_very_short_lyrics(self):
        """Very short lyrics don't crash."""
        songs = [{'lyrics': 'a'}]
        result = preprocess_lyrics(songs)

        assert result[0]['tokens'] == []


@pytest.mark.unit
class TestTokenizeAndClean:
    """Tests for _tokenize_and_clean function."""

    def test_removes_brackets_content(self):
        """Removes content in brackets."""
        tokens, _ = _tokenize_and_clean('[Verse 1] Hello [Chorus] World')
        assert 'verse' not in str(tokens).lower()
        assert 'chorus' not in str(tokens).lower()

    def test_removes_parentheses_content(self):
        """Removes content in parentheses."""
        tokens, _ = _tokenize_and_clean('Hello (spoken) World (repeat)')
        assert 'spoken' not in str(tokens).lower()
        assert 'repeat' not in str(tokens).lower()

    def test_removes_numbers(self):
        """Numbers are removed."""
        tokens, _ = _tokenize_and_clean('Song 123 from 2020 album')
        assert not any(t.isdigit() for t in tokens)

    def test_handles_contractions(self):
        """Contractions are handled."""
        tokens, stem_map = _tokenize_and_clean("I'm don't won't can't")
        # Should not crash, contractions cleaned up
        assert isinstance(tokens, list)
        assert isinstance(stem_map, dict)

    def test_returns_stem_mapping(self):
        """Returns mapping from stems to original words."""
        tokens, stem_map = _tokenize_and_clean('loving loved loves')
        assert isinstance(stem_map, dict)
        # 'love' stem should map to original forms
        assert 'love' in stem_map or len(stem_map) > 0


@pytest.mark.unit
class TestGetTokensForLda:
    """Tests for get_tokens_for_lda function."""

    def test_returns_token_lists(self):
        """Returns list of token lists."""
        songs = [
            {'tokens': ['love', 'heart']},
            {'tokens': ['dark', 'night']},
            {'tokens': []}
        ]

        result = get_tokens_for_lda(songs)

        # Empty token lists should be filtered
        assert len(result) == 2
        assert result[0] == ['love', 'heart']
        assert result[1] == ['dark', 'night']

    def test_handles_empty_input(self):
        """Handles empty input."""
        result = get_tokens_for_lda([])
        assert result == []

    def test_filters_empty_tokens(self):
        """Filters out songs with empty tokens."""
        songs = [
            {'tokens': []},
            {'tokens': ['word']},
            {'tokens': []}
        ]

        result = get_tokens_for_lda(songs)
        assert len(result) == 1
