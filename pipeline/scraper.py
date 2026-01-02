"""Hybrid scraper using Discogs for metadata and Musixmatch/lyrics.ovh for lyrics."""

import os
import re
import time
import logging
import requests

logger = logging.getLogger(__name__)

MUSIXMATCH_API_KEY = os.environ.get('MUSIXMATCH_API_KEY', '')

# Import Discogs client functions
from pipeline.discogs_client import (
    extract_primary_artist,
    search_artist as discogs_search_artist,
    search_albums as discogs_search_albums,
    get_artist_albums as discogs_get_artist_albums,
    get_release_tracks as discogs_get_release_tracks,
    get_release_info as discogs_get_release_info,
    DiscogsError
)


class ScraperError(Exception):
    """Custom exception for scraper errors."""
    pass


def _normalize_album_name(name):
    """Normalize album name for deduplication."""
    name = name.lower()
    # Remove common variant suffixes
    patterns = [
        r'\s*\(deluxe.*?\)',
        r'\s*\(expanded.*?\)',
        r'\s*\(.*?remaster.*?\)',  # Matches "(Remastered)", "(2020 Remaster)", etc.
        r'\s*\(anniversary.*?\)',
        r'\s*\(explicit.*?\)',
        r'\s*\(clean.*?\)',
        r'\s*\[deluxe.*?\]',
        r'\s*\[explicit.*?\]',
        r'\s*-\s*deluxe.*$',
        r'\s*-\s*explicit.*$',
    ]
    for pattern in patterns:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)
    return name.strip()


def _extract_year_from_date(date_str):
    """Extract release year from date string."""
    if not date_str:
        return None
    match = re.search(r'\d{4}', str(date_str))
    if match:
        return int(match.group())
    return None


def _fetch_lyrics_musixmatch(artist_name, song_title, max_retries=2):
    """Fetch lyrics from Musixmatch API with retry logic."""
    from pipeline.api_metrics import get_metrics

    if not MUSIXMATCH_API_KEY:
        return ''

    metrics = get_metrics()

    # Check rate limit before making request
    allowed, wait_time = metrics.check_limit('musixmatch')
    if not allowed:
        logger.warning(f"Musixmatch rate limit reached ({wait_time}s until reset), skipping")
        return ''

    for attempt in range(max_retries):
        try:
            response = requests.get(
                'https://api.musixmatch.com/ws/1.1/matcher.lyrics.get',
                params={
                    'q_track': song_title,
                    'q_artist': artist_name,
                    'apikey': MUSIXMATCH_API_KEY,
                },
                timeout=15
            )

            # Track the API call
            metrics.track_call('musixmatch', success=response.status_code == 200)

            if response.status_code == 200:
                data = response.json()
                message = data.get('message', {})
                if message.get('header', {}).get('status_code') == 200:
                    body = message.get('body', {})
                    lyrics = body.get('lyrics', {}).get('lyrics_body', '')
                    if lyrics:
                        # Musixmatch adds a disclaimer at the end, remove it
                        if '******* This Lyrics is NOT for Commercial use *******' in lyrics:
                            lyrics = lyrics.split('******* This Lyrics is NOT for Commercial use *******')[0].strip()
                        logger.info(f"Got lyrics from Musixmatch for: {artist_name} - {song_title}")
                        return lyrics

            # If we got a response but no lyrics, don't retry (song not found)
            if response.status_code == 200:
                return ''

        except Exception as e:
            metrics.track_call('musixmatch', success=False)
            logger.debug(f"Musixmatch attempt {attempt + 1} failed for {artist_name} - {song_title}: {e}")
            if attempt < max_retries - 1:
                time.sleep(1)  # Wait 1 second before retry

    return ''


def _fetch_lyrics_lyricsovh(artist_name, song_title):
    """Fetch lyrics from lyrics.ovh API (free, no scraping needed)."""
    from pipeline.api_metrics import get_metrics

    metrics = get_metrics()

    try:
        # Clean artist and title for URL
        artist = artist_name.strip()
        title = song_title.strip()

        response = requests.get(
            f'https://api.lyrics.ovh/v1/{artist}/{title}',
            timeout=15
        )

        # Track the API call
        metrics.track_call('lyricsovh', success=response.status_code == 200)

        if response.status_code == 200:
            data = response.json()
            lyrics = data.get('lyrics', '')
            if lyrics:
                logger.info(f"Got lyrics from lyrics.ovh for: {artist} - {title}")
                return lyrics.strip()

        return ''
    except Exception as e:
        metrics.track_call('lyricsovh', success=False)
        logger.debug(f"lyrics.ovh failed for {artist_name} - {song_title}: {e}")
        return ''


def search_artist_albums(artist_name, page=1, per_page=20):
    """
    Search for an artist and return their albums using Discogs with pagination.

    Args:
        artist_name: Name of the artist to search for
        page: Page number (1-indexed)
        per_page: Number of albums per page

    Returns:
        Dict with artist_id, artist_name, albums list, has_more, total
    """
    try:
        # Search for the artist using Discogs
        artist_id, found_name = discogs_search_artist(artist_name)
        if not artist_id:
            logger.warning(f"Artist not found on Discogs: {artist_name}")
            return None

        # Get paginated albums from Discogs
        return get_artist_albums_by_id(artist_id, found_name or artist_name, page, per_page)

    except DiscogsError as e:
        logger.error(f"Discogs API error: {e}")
        return None
    except Exception as e:
        logger.error(f"Error searching artist albums: {e}")
        return None


def get_artist_albums_by_id(artist_id, artist_name, page=1, per_page=20):
    """
    Get albums for an artist by ID (for pagination without re-searching).

    Args:
        artist_id: Discogs artist ID
        artist_name: Artist name for response
        page: Page number (1-indexed)
        per_page: Number of albums per page

    Returns:
        Dict with artist_id, artist_name, albums list, has_more, total
    """
    try:
        # Get paginated albums from Discogs
        result = discogs_get_artist_albums(artist_id, page=page, per_page=per_page)

        # Format albums for frontend
        formatted_albums = []
        for album in result.get('albums', []):
            formatted_albums.append({
                'id': album.get('id'),
                'name': album.get('name', ''),
                'year': album.get('year'),
                'artist': artist_name
            })

        logger.info(f"Found {len(formatted_albums)} albums (page {page}) for {artist_name} via Discogs")
        return {
            'artist_id': artist_id,
            'artist_name': artist_name,
            'albums': formatted_albums,
            'has_more': result.get('has_more', False),
            'next_page': result.get('next_page', page + 1),
            'page': page
        }

    except DiscogsError as e:
        logger.error(f"Discogs API error: {e}")
        return None
    except Exception as e:
        logger.error(f"Error getting artist albums: {e}")
        return None


def search_albums_by_title(query, page=1, per_page=20):
    """
    Search for albums by title using Discogs.

    Args:
        query: Album title to search for
        page: Page number (1-indexed)
        per_page: Number of albums per page

    Returns:
        Dict with albums list, has_more flag, page, and next_page, or None on error
    """
    if not query or not query.strip():
        return None

    try:
        result = discogs_search_albums(query.strip(), page=page, per_page=per_page)
        logger.info(f"Album search for '{query}': found {len(result.get('albums', []))} results")
        return result

    except Exception as e:
        logger.error(f"Error searching albums by title: {e}")
        return None


def scrape_album(album_id, album_name=None, artist_name=None, progress_callback=None):
    """
    Scrape lyrics for all songs in an album using Discogs + Musixmatch/lyrics.ovh.

    Args:
        album_id: Discogs master/release ID
        album_name: Album name (optional, for metadata)
        artist_name: Artist name (required for lyrics search)
        progress_callback: Optional callback(current, total, title) for progress updates

    Returns:
        Dict with: songs (list), total_tracks, tracks_with_lyrics
    """
    logger.info(f"=== SCRAPING ALBUM: {album_name} (ID: {album_id}) ===")

    try:
        # Get release info from Discogs
        release_info = discogs_get_release_info(album_id, is_master=True)
        if release_info:
            if not artist_name:
                artist_name = release_info.get('artist', '')
            album_year = release_info.get('year')
        else:
            album_year = None

        # Clean artist name for lyrics search
        # Removes "Featuring X", split release markers, Discogs disambiguation, etc.
        search_artist_name = extract_primary_artist(artist_name) if artist_name else ''
        if search_artist_name != artist_name:
            logger.info(f"Normalized artist name for search: '{artist_name}' -> '{search_artist_name}'")

        # Get tracks from Discogs
        tracks = discogs_get_release_tracks(album_id, is_master=True)
        logger.info(f"Found {len(tracks)} tracks from Discogs")

        if not tracks:
            logger.warning(f"No tracks found for album ID {album_id}")
            return []

        results = []
        total_tracks = len(tracks)
        for i, track in enumerate(tracks, 1):
            title = track.get('title', 'Unknown')
            logger.info(f"[{i}/{total_tracks}] Fetching lyrics for: {search_artist_name} - {title}")

            # Report progress if callback provided
            if progress_callback:
                progress_callback(i, total_tracks, title)

            lyrics = None
            source_url = None

            # Try Musixmatch first (paid, best coverage)
            if MUSIXMATCH_API_KEY:
                lyrics = _fetch_lyrics_musixmatch(search_artist_name, title)
                if lyrics:
                    source_url = 'musixmatch'

            # Try lyrics.ovh second (free API)
            if not lyrics:
                lyrics = _fetch_lyrics_lyricsovh(search_artist_name, title)
                if lyrics:
                    source_url = 'lyrics.ovh'

            if lyrics:
                results.append({
                    'title': title,
                    'artist': artist_name,
                    'album': album_name,
                    'year': album_year,
                    'lyrics': lyrics,
                    'url': source_url
                })
                logger.info(f"  Got {len(lyrics)} chars of lyrics")
            else:
                logger.warning(f"  Could not find lyrics for: {title}")

            # Rate limiting
            time.sleep(0.3)

        logger.info(f"=== SCRAPING COMPLETE: {len(results)}/{total_tracks} songs with lyrics ===")
        return {
            'songs': results,
            'total_tracks': total_tracks,
            'tracks_with_lyrics': len(results)
        }

    except DiscogsError as e:
        logger.error(f"Discogs API error: {e}")
        raise ScraperError(f"Failed to get album from Discogs: {e}")
    except Exception as e:
        logger.error(f"Error scraping album: {e}")
        raise ScraperError(f"Failed to scrape album: {e}")
