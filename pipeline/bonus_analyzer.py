"""Bonus analyses: word frequency and metaphor detection."""

import re
import logging
from typing import List, Dict
from collections import Counter

logger = logging.getLogger(__name__)

# Metaphor categories with associated keywords
METAPHOR_PATTERNS = {
    'death': ['death', 'dying', 'dead', 'die', 'kill', 'grave', 'funeral', 'corpse', 'tomb'],
    'love': ['love', 'heart', 'soul', 'passion', 'desire', 'romance', 'kiss', 'embrace'],
    'darkness': ['dark', 'darkness', 'shadow', 'night', 'black', 'midnight', 'dim', 'gloom'],
    'light': ['light', 'bright', 'sun', 'shine', 'glow', 'radiant', 'dawn', 'illuminate'],
    'pain': ['pain', 'hurt', 'wound', 'suffer', 'ache', 'agony', 'torment', 'sorrow'],
    'loss': ['loss', 'lost', 'lose', 'gone', 'miss', 'empty', 'hollow', 'void'],
    'hope': ['hope', 'dream', 'wish', 'believe', 'faith', 'promise', 'tomorrow'],
    'fear': ['fear', 'afraid', 'scare', 'terror', 'dread', 'horror', 'nightmare'],
    'time': ['time', 'forever', 'eternal', 'moment', 'memory', 'past', 'future', 'yesterday'],
    'freedom': ['free', 'freedom', 'fly', 'escape', 'break', 'release', 'liberate'],
    'nature': ['rain', 'wind', 'storm', 'sea', 'ocean', 'river', 'mountain', 'sky', 'star'],
    'fire': ['fire', 'flame', 'burn', 'blaze', 'ash', 'ember', 'inferno'],
}


def analyze_word_frequency(songs: List[Dict], top_n: int = 50) -> List[Dict]:
    """
    Analyze word frequency across all songs.

    Args:
        songs: List of preprocessed song dicts with 'tokens' and 'stem_to_all_words' keys
        top_n: Number of top words to return

    Returns:
        List of {word, frequency} dicts sorted by frequency
    """
    logger.info(f"=== WORD FREQUENCY ANALYSIS ===")

    all_tokens = []

    for song in songs:
        tokens = song.get('tokens', [])
        all_tokens.extend(tokens)

    if not all_tokens:
        logger.warning("No tokens for word frequency analysis")
        return []

    # Get stem to all words mapping
    stem_to_all_words = songs[0].get('stem_to_all_words', {}) if songs else {}

    # Count frequencies
    counter = Counter(all_tokens)

    # Get top N
    top_words = counter.most_common(top_n)

    logger.info(f"Analyzed {len(all_tokens)} total tokens, {len(counter)} unique words")
    logger.info(f"Top 5 words: {', '.join([f'{w}({c})' for w, c in top_words[:5]])}")

    # Convert stems to readable words, showing all forms if multiple exist
    results = []
    for stem, count in top_words:
        all_forms = stem_to_all_words.get(stem, [stem.capitalize()])
        if len(all_forms) > 1:
            # Show multiple forms: "Body / Bodies"
            word_display = ' / '.join(all_forms[:3])  # Limit to 3 forms
        else:
            word_display = all_forms[0] if all_forms else stem.capitalize()
        results.append({'word': word_display, 'frequency': count})

    return results


def analyze_metaphors(songs: List[Dict]) -> List[Dict]:
    """
    Analyze metaphor/theme frequency in lyrics.

    Args:
        songs: List of song dicts with 'lyrics' key

    Returns:
        List of {metaphor, frequency} dicts sorted by frequency
    """
    logger.info(f"=== METAPHOR/THEME ANALYSIS ===")

    # Combine all lyrics
    all_lyrics = ' '.join(
        song.get('lyrics', '').lower()
        for song in songs
    )

    if not all_lyrics:
        logger.warning("No lyrics for metaphor analysis")
        return []

    results = []

    for metaphor, keywords in METAPHOR_PATTERNS.items():
        count = 0
        for keyword in keywords:
            # Use word boundaries for accurate matching
            pattern = r'\b' + re.escape(keyword) + r'\b'
            matches = re.findall(pattern, all_lyrics, re.IGNORECASE)
            count += len(matches)

        if count > 0:
            results.append({
                'metaphor': metaphor,
                'frequency': count
            })

    # Sort by frequency descending
    results.sort(key=lambda x: x['frequency'], reverse=True)

    if results:
        top_themes = [f"{r['metaphor']}({r['frequency']})" for r in results[:5]]
        logger.info(f"Top themes: {', '.join(top_themes)}")

    logger.info(f"=== BONUS ANALYSES COMPLETE ===")

    return results


def get_word_cloud_data(songs: List[Dict], max_words: int = 100) -> Dict[str, int]:
    """
    Get word frequency data formatted for word cloud visualization.

    Args:
        songs: List of preprocessed song dicts
        max_words: Maximum number of words

    Returns:
        Dict mapping words to frequencies
    """
    freq_list = analyze_word_frequency(songs, top_n=max_words)
    return {item['word']: item['frequency'] for item in freq_list}


def analyze_vocabulary_richness(songs: List[Dict]) -> Dict:
    """
    Analyze vocabulary richness metrics.

    Args:
        songs: List of preprocessed song dicts

    Returns:
        Dict with vocabulary metrics
    """
    all_tokens = []
    for song in songs:
        all_tokens.extend(song.get('tokens', []))

    if not all_tokens:
        return {
            'total_words': 0,
            'unique_words': 0,
            'vocabulary_richness': 0.0,
            'average_word_length': 0.0
        }

    total_words = len(all_tokens)
    unique_words = len(set(all_tokens))
    vocabulary_richness = unique_words / total_words if total_words > 0 else 0

    avg_length = sum(len(t) for t in all_tokens) / total_words if total_words > 0 else 0

    return {
        'total_words': total_words,
        'unique_words': unique_words,
        'vocabulary_richness': round(vocabulary_richness, 4),
        'average_word_length': round(avg_length, 2)
    }
