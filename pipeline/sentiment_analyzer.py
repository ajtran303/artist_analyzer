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
