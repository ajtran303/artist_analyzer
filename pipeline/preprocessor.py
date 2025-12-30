"""Text preprocessing for lyrics analysis."""

import re
import string
import logging
from typing import List, Dict

import nltk
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from nltk.tokenize import word_tokenize

logger = logging.getLogger(__name__)

# Download required NLTK data
def _ensure_nltk_data():
    """Ensure NLTK data is downloaded."""
    packages = ['punkt', 'punkt_tab', 'stopwords']
    for package in packages:
        try:
            nltk.data.find(f'tokenizers/{package}' if package.startswith('punkt') else f'corpora/{package}')
        except (LookupError, OSError):
            try:
                nltk.download(package, quiet=True)
            except Exception:
                pass  # Ignore download errors, will fall back to split()

_ensure_nltk_data()


# Initialize stemmer and stopwords
stemmer = PorterStemmer()
STOP_WORDS = set(stopwords.words('english'))

# Additional stopwords common in lyrics
LYRICS_STOPWORDS = {
    'oh', 'yeah', 'la', 'na', 'da', 'hey', 'uh', 'ah',
    'ooh', 'whoa', 'hmm', 'mmm', 'ya', 'yo', 'wanna',
    'gonna', 'gotta', 'aint', "i'm", "you're", "it's",
    'verse', 'chorus', 'bridge', 'intro', 'outro',
    # Genius page artifacts
    'contributor', 'contributors', 'lyric', 'lyrics',
    'embed', 'translation', 'translations', 'instrumental',
    # Common genre terms (not meaningful for analysis)
    'metal', 'rock', 'punk', 'pop', 'jazz', 'blues',
    'rap', 'hip', 'hop', 'country', 'folk', 'indie',
}
STOP_WORDS.update(LYRICS_STOPWORDS)

# Stemmed versions of stopwords (checked after stemming)
STEMMED_STOPWORDS = {
    'contributor', 'lyric', 'embed', 'translat', 'instrument',
    'metal', 'rock', 'punk', 'pop', 'jazz', 'blue',
    'rap', 'hip', 'hop', 'countri', 'folk', 'indi',
}


def preprocess_lyrics(songs: List[Dict]) -> List[Dict]:
    """
    Preprocess lyrics for all songs.

    Args:
        songs: List of song dicts with 'lyrics' key

    Returns:
        List of song dicts with added 'tokens', 'text', and 'stem_to_word' keys
    """
    logger.info(f"=== PREPROCESSING: {len(songs)} songs ===")
    processed = []
    global_stem_map = {}  # Track most common original word for each stem

    for i, song in enumerate(songs, 1):
        title = song.get('title', 'Unknown')
        logger.info(f"[{i}/{len(songs)}] Preprocessing: {title}")
        lyrics = song.get('lyrics', '')
        if not lyrics:
            processed.append({
                **song,
                'tokens': [],
                'text': ''
            })
            logger.warning(f"  ✗ No lyrics to process")
            continue

        tokens, stem_map = _tokenize_and_clean(lyrics)

        # Merge stem mappings, keeping most common original
        for stem, originals in stem_map.items():
            if stem not in global_stem_map:
                global_stem_map[stem] = {}
            for orig, count in originals.items():
                global_stem_map[stem][orig] = global_stem_map[stem].get(orig, 0) + count

        processed.append({
            **song,
            'tokens': tokens,
            'text': ' '.join(tokens)
        })
        logger.info(f"  ✓ Generated {len(tokens)} tokens")

    # Build final stem -> best original word mapping
    stem_to_word = {}
    stem_to_all_words = {}  # Also track all word forms
    for stem, originals in global_stem_map.items():
        # Pick the most common original word
        best_word = max(originals.items(), key=lambda x: x[1])[0]
        stem_to_word[stem] = best_word.capitalize()
        # Store all unique forms (capitalized, sorted by frequency)
        sorted_forms = sorted(originals.items(), key=lambda x: -x[1])
        stem_to_all_words[stem] = [w.capitalize() for w, _ in sorted_forms]

    # Add mappings to all processed songs
    for song in processed:
        song['stem_to_word'] = stem_to_word
        song['stem_to_all_words'] = stem_to_all_words

    logger.info(f"=== PREPROCESSING COMPLETE: {len(processed)} songs processed ===")
    return processed


def _tokenize_and_clean(text: str) -> tuple:
    """
    Tokenize and clean text.

    Args:
        text: Raw lyrics text

    Returns:
        Tuple of (list of stemmed tokens, dict mapping stems to original words)
    """
    if not text or not text.strip():
        return [], {}

    # Lowercase
    text = text.lower()

    # Remove URLs
    text = re.sub(r'https?://\S+|www\.\S+', '', text)

    # Remove text in brackets (often annotations)
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\(.*?\)', '', text)

    # Remove special characters but keep apostrophes initially
    text = re.sub(r"[^\w\s']", ' ', text)

    # Handle contractions
    text = re.sub(r"'s\b", '', text)
    text = re.sub(r"'t\b", '', text)
    text = re.sub(r"'re\b", '', text)
    text = re.sub(r"'ve\b", '', text)
    text = re.sub(r"'ll\b", '', text)
    text = re.sub(r"'d\b", '', text)
    text = re.sub(r"'m\b", '', text)

    # Remove remaining apostrophes
    text = text.replace("'", '')

    # Remove numbers
    text = re.sub(r'\d+', '', text)

    # Tokenize
    try:
        tokens = word_tokenize(text)
    except Exception:
        tokens = text.split()

    # Filter and stem
    filtered = []
    stem_map = {}  # Maps stem -> {original_word: count}

    for token in tokens:
        # Skip short words
        if len(token) < 3:
            continue

        # Skip stopwords
        if token in STOP_WORDS:
            continue

        # Skip if contains non-alpha
        if not token.isalpha():
            continue

        # Stem the word
        stemmed = stemmer.stem(token)

        # Skip if stemmed word is too short
        if len(stemmed) < 3:
            continue

        # Skip stemmed stopwords (Genius artifacts, genres, etc.)
        if stemmed in STEMMED_STOPWORDS:
            continue

        # Track original word for this stem
        if stemmed not in stem_map:
            stem_map[stemmed] = {}
        stem_map[stemmed][token] = stem_map[stemmed].get(token, 0) + 1

        filtered.append(stemmed)

    return filtered, stem_map


def get_tokens_for_lda(songs: List[Dict]) -> List[List[str]]:
    """
    Get just the token lists for LDA training.

    Args:
        songs: List of preprocessed song dicts

    Returns:
        List of token lists (one per song)
    """
    return [song.get('tokens', []) for song in songs if song.get('tokens')]
