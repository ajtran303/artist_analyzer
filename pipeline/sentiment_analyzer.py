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


def find_most_emotional_passage(songs: List[Dict]) -> Dict:
    """
    Find the most emotionally intense passage across all songs.

    Analyzes lyrics by splitting into passages (verses) and finding
    the one with the highest absolute sentiment score.

    Args:
        songs: List of song dicts with 'lyrics' and 'title' keys

    Returns:
        Dict with: song_title, passage, score, sentiment_type ('positive'/'negative')
        Returns None if no valid passages found.
    """
    if not songs:
        return None

    most_emotional = None
    highest_intensity = 0.0

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
            intensity = abs(score)

            if intensity > highest_intensity:
                highest_intensity = intensity
                most_emotional = {
                    'song_title': title,
                    'passage': passage.strip(),
                    'score': score,
                    'sentiment_type': 'positive' if score >= 0 else 'negative'
                }

    return most_emotional


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
