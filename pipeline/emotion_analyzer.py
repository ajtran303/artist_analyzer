"""Emotion analysis using NRCLex for granular emotional categories."""

import logging
from typing import List, Dict
from collections import defaultdict

from nrclex import NRCLex

logger = logging.getLogger(__name__)

# The 8 NRC emotions (excluding positive/negative which overlap with sentiment)
EMOTIONS = [
    'fear',
    'anger',
    'anticipation',
    'trust',
    'surprise',
    'sadness',
    'joy',
    'disgust'
]


def analyze_emotions(songs: List[Dict]) -> Dict:
    """
    Analyze emotions across all songs using NRCLex.

    Args:
        songs: List of song dicts with 'lyrics' key

    Returns:
        Dict with:
            - overall: Dict of emotion -> percentage (0-100)
            - by_song: List of {title, emotions} for each song
            - dominant_emotion: The most prevalent emotion
            - emotion_words: Sample words that triggered each emotion
    """
    logger.info(f"=== EMOTION ANALYSIS: {len(songs)} songs ===")

    if not songs:
        return {
            'overall': {emotion: 0 for emotion in EMOTIONS},
            'by_song': [],
            'dominant_emotion': None,
            'emotion_words': {}
        }

    # Aggregate emotion counts across all songs
    total_emotion_counts = defaultdict(int)
    total_word_count = 0
    song_emotions = []
    emotion_word_samples = defaultdict(set)

    for i, song in enumerate(songs, 1):
        title = song.get('title', 'Unknown')
        lyrics = song.get('lyrics', '')

        if not lyrics or not lyrics.strip():
            song_emotions.append({
                'title': title,
                'emotions': {emotion: 0 for emotion in EMOTIONS}
            })
            continue

        # Analyze with NRCLex
        try:
            emotion = NRCLex(lyrics)

            # Get raw emotion counts for this song
            raw_emotions = emotion.raw_emotion_scores

            # Calculate song-level percentages
            song_total = sum(raw_emotions.get(e, 0) for e in EMOTIONS)
            song_percentages = {}

            for e in EMOTIONS:
                count = raw_emotions.get(e, 0)
                total_emotion_counts[e] += count

                # Calculate percentage for this song
                if song_total > 0:
                    song_percentages[e] = round((count / song_total) * 100, 1)
                else:
                    song_percentages[e] = 0

                # Collect sample words for this emotion (limit to 5 per emotion)
                if hasattr(emotion, 'affect_dict') and len(emotion_word_samples[e]) < 5:
                    for word, emotions_list in emotion.affect_dict.items():
                        if e in emotions_list and len(emotion_word_samples[e]) < 5:
                            emotion_word_samples[e].add(word)

            song_emotions.append({
                'title': title,
                'emotions': song_percentages
            })

            total_word_count += song_total

            logger.debug(f"[{i}/{len(songs)}] {title}: dominant = {max(song_percentages, key=song_percentages.get) if song_percentages else 'none'}")

        except Exception as e:
            logger.warning(f"Emotion analysis failed for '{title}': {e}")
            song_emotions.append({
                'title': title,
                'emotions': {emotion: 0 for emotion in EMOTIONS}
            })

    # Calculate overall percentages
    overall_percentages = {}
    for e in EMOTIONS:
        if total_word_count > 0:
            overall_percentages[e] = round((total_emotion_counts[e] / total_word_count) * 100, 1)
        else:
            overall_percentages[e] = 0

    # Find dominant emotion
    dominant = max(overall_percentages, key=overall_percentages.get) if overall_percentages else None

    # Convert word samples to lists
    emotion_words = {e: list(words) for e, words in emotion_word_samples.items()}

    logger.info(f"=== EMOTION ANALYSIS COMPLETE: dominant = {dominant} ===")

    return {
        'overall': overall_percentages,
        'by_song': song_emotions,
        'dominant_emotion': dominant,
        'emotion_words': emotion_words
    }


def get_emotion_summary(emotions_result: Dict) -> str:
    """
    Generate a human-readable summary of the emotion analysis.

    Args:
        emotions_result: Result from analyze_emotions()

    Returns:
        Summary string describing the emotional profile
    """
    overall = emotions_result.get('overall', {})
    dominant = emotions_result.get('dominant_emotion')

    if not dominant:
        return "Unable to determine emotional profile."

    # Get top 3 emotions
    sorted_emotions = sorted(overall.items(), key=lambda x: x[1], reverse=True)[:3]

    if sorted_emotions[0][1] == 0:
        return "No strong emotional content detected."

    top_emotion = sorted_emotions[0][0]
    top_pct = sorted_emotions[0][1]

    # Build summary
    summary_parts = [f"Predominantly {top_emotion} ({top_pct}%)"]

    if len(sorted_emotions) > 1 and sorted_emotions[1][1] > 10:
        summary_parts.append(f"with {sorted_emotions[1][0]} ({sorted_emotions[1][1]}%)")

    if len(sorted_emotions) > 2 and sorted_emotions[2][1] > 10:
        summary_parts.append(f"and {sorted_emotions[2][0]} ({sorted_emotions[2][1]}%)")

    return " ".join(summary_parts)
