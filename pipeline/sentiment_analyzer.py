"""Sentiment analysis for lyrics."""

import logging
from typing import List, Dict
from collections import defaultdict

from textblob import TextBlob

logger = logging.getLogger(__name__)


def run_sentiment(songs: List[Dict]) -> Dict:
    """
    Run sentiment analysis on songs.

    Args:
        songs: List of song dicts with 'lyrics' key

    Returns:
        Dict with: by_album, by_year, overall, songs (with scores)
    """
    logger.info(f"=== SENTIMENT ANALYSIS: {len(songs)} songs ===")

    if not songs:
        return {
            'by_album': [],
            'by_year': [],
            'overall': 0.0,
            'songs': []
        }

    # Score each song
    scored_songs = []
    for i, song in enumerate(songs, 1):
        title = song.get('title', 'Unknown')
        score = _analyze_sentiment(song.get('lyrics', ''))
        scored_songs.append({
            **song,
            'sentiment_score': score
        })
        sentiment_label = "positive" if score > 0.1 else "negative" if score < -0.1 else "neutral"
        logger.info(f"[{i}/{len(songs)}] {title}: {score:+.3f} ({sentiment_label})")

    # Aggregate by album
    by_album = _aggregate_by_album(scored_songs)

    # Aggregate by year
    by_year = _aggregate_by_year(scored_songs)

    # Calculate overall
    scores = [s['sentiment_score'] for s in scored_songs]
    overall = sum(scores) / len(scores) if scores else 0.0

    logger.info(f"=== SENTIMENT COMPLETE: overall score {overall:+.3f} ===")

    return {
        'by_album': by_album,
        'by_year': by_year,
        'overall': round(overall, 4),
        'songs': scored_songs
    }


def _analyze_sentiment(text: str) -> float:
    """
    Analyze sentiment of text using TextBlob.

    Args:
        text: Text to analyze

    Returns:
        Sentiment score between -1 (negative) and 1 (positive)
    """
    if not text or not text.strip():
        return 0.0

    try:
        blob = TextBlob(text)
        # TextBlob polarity is already between -1 and 1
        return round(blob.sentiment.polarity, 4)
    except Exception as e:
        logger.warning(f"Sentiment analysis failed: {e}")
        return 0.0


def _aggregate_by_album(songs: List[Dict]) -> List[Dict]:
    """
    Aggregate sentiment scores by album.

    Args:
        songs: List of scored song dicts

    Returns:
        List of album sentiment dicts
    """
    album_scores = defaultdict(list)

    for song in songs:
        album = song.get('album') or 'Unknown'
        album_scores[album].append(song['sentiment_score'])

    results = []
    for album, scores in album_scores.items():
        avg_score = sum(scores) / len(scores) if scores else 0.0
        results.append({
            'album': album,
            'score': round(avg_score, 4),
            'song_count': len(scores)
        })

    # Sort by score ascending (most negative first)
    results.sort(key=lambda x: x['score'])

    return results


def _aggregate_by_year(songs: List[Dict]) -> List[Dict]:
    """
    Aggregate sentiment scores by year.

    Args:
        songs: List of scored song dicts

    Returns:
        List of year sentiment dicts
    """
    year_scores = defaultdict(list)

    for song in songs:
        year = song.get('year')
        if year is not None:
            year_scores[year].append(song['sentiment_score'])

    results = []
    for year, scores in year_scores.items():
        avg_score = sum(scores) / len(scores) if scores else 0.0
        results.append({
            'year': year,
            'score': round(avg_score, 4),
            'song_count': len(scores)
        })

    # Sort by year ascending
    results.sort(key=lambda x: x['year'])

    return results


def get_sentiment_timeline(songs: List[Dict]) -> List[Dict]:
    """
    Get sentiment timeline for visualization.

    Args:
        songs: List of scored song dicts

    Returns:
        List of {year, score} for timeline chart
    """
    by_year = _aggregate_by_year(songs)
    return [{'year': item['year'], 'score': item['score']} for item in by_year]


def find_most_emotional_passages(songs: List[Dict]) -> Dict:
    """
    Find the most positive and most negative passages across all songs.

    Analyzes lyrics by splitting into passages (verses) and finding
    the passages with the highest and lowest sentiment scores.

    Only includes passages that are clearly positive (>= 0.05) or
    negative (<= -0.05), excluding neutral content. Will not return
    the same passage for both if there's only one emotional passage.

    Args:
        songs: List of song dicts with 'lyrics' and 'title' keys

    Returns:
        Dict with 'most_positive' and 'most_negative', each containing:
            song_title, passage, score
        Returns None values if no valid passages found.
    """
    # Thresholds matching the UI's neutral range (-0.05 to 0.05)
    POSITIVE_THRESHOLD = 0.05
    NEGATIVE_THRESHOLD = -0.05

    if not songs:
        return {'most_positive': None, 'most_negative': None}

    most_positive = None
    most_negative = None
    highest_score = POSITIVE_THRESHOLD  # Must exceed this to count as positive
    lowest_score = NEGATIVE_THRESHOLD   # Must be below this to count as negative

    for song in songs:
        lyrics = song.get('lyrics', '')
        title = song.get('title', 'Unknown')

        if not lyrics or not lyrics.strip():
            continue

        # Split lyrics into passages (by double newlines for verses)
        passages = _split_into_passages(lyrics)

        for passage in passages:
            if len(passage.strip()) < 20:  # Skip very short passages
                continue

            score = _analyze_sentiment(passage)

            # Track most positive (must be above positive threshold)
            if score >= POSITIVE_THRESHOLD and score > highest_score:
                highest_score = score
                most_positive = {
                    'song_title': title,
                    'passage': passage.strip(),
                    'score': score
                }

            # Track most negative (must be below negative threshold)
            if score <= NEGATIVE_THRESHOLD and score < lowest_score:
                lowest_score = score
                most_negative = {
                    'song_title': title,
                    'passage': passage.strip(),
                    'score': score
                }

    # Don't return the same passage for both (can happen with single passage)
    if (most_positive and most_negative and
            most_positive['passage'] == most_negative['passage']):
        # Keep whichever has higher absolute score
        if abs(most_positive['score']) >= abs(most_negative['score']):
            most_negative = None
        else:
            most_positive = None

    return {
        'most_positive': most_positive,
        'most_negative': most_negative
    }


def find_most_emotional_passage(songs: List[Dict]) -> Dict:
    """
    Find the most emotionally intense passage across all songs.

    DEPRECATED: Use find_most_emotional_passages() instead.

    Args:
        songs: List of song dicts with 'lyrics' and 'title' keys

    Returns:
        Dict with: song_title, passage, score, sentiment_type ('positive'/'negative')
        Returns None if no valid passages found.
    """
    result = find_most_emotional_passages(songs)

    # Return whichever has higher absolute score
    pos = result.get('most_positive')
    neg = result.get('most_negative')

    if not pos and not neg:
        return None
    if not pos:
        return {**neg, 'sentiment_type': 'negative'}
    if not neg:
        return {**pos, 'sentiment_type': 'positive'}

    if abs(pos['score']) >= abs(neg['score']):
        return {**pos, 'sentiment_type': 'positive'}
    else:
        return {**neg, 'sentiment_type': 'negative'}


def _split_into_passages(lyrics: str) -> List[str]:
    """
    Split lyrics into passages/verses.

    First tries to split by double newlines (verse breaks).
    If that yields too few passages, falls back to grouping lines.

    Args:
        lyrics: Raw lyrics text

    Returns:
        List of passage strings
    """
    # Try splitting by double newlines (verse separators)
    passages = [p.strip() for p in lyrics.split('\n\n') if p.strip()]

    # If we got reasonable passages, return them
    if len(passages) >= 2:
        return passages

    # Fallback: split by single newlines and group into chunks of 4 lines
    lines = [line.strip() for line in lyrics.split('\n') if line.strip()]

    if len(lines) < 4:
        return [lyrics]  # Return whole lyrics as single passage

    passages = []
    for i in range(0, len(lines), 4):
        chunk = '\n'.join(lines[i:i+4])
        if chunk.strip():
            passages.append(chunk)

    return passages if passages else [lyrics]
