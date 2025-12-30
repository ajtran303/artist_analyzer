"""Hybrid scraper using Discogs for metadata and Genius for lyrics."""

import os
import re
import time
import logging
import requests
from bs4 import BeautifulSoup
from lyricsgenius import Genius, PublicAPI

logger = logging.getLogger(__name__)

GENIUS_TOKEN = os.environ.get('GENIUS_API_TOKEN', '')
MUSIXMATCH_API_KEY = os.environ.get('MUSIXMATCH_API_KEY', '')

# Import Discogs client functions
from pipeline.discogs_client import (
    search_artist as discogs_search_artist,
    get_artist_albums as discogs_get_artist_albums,
    get_release_tracks as discogs_get_release_tracks,
    get_release_info as discogs_get_release_info,
    DiscogsError
)


class ScraperError(Exception):
    """Custom exception for scraper errors."""
    pass


def _get_genius_client():
    """Get authenticated Genius client."""
    if not GENIUS_TOKEN:
        return None
    genius = Genius(GENIUS_TOKEN, timeout=30, retries=3)
    genius.verbose = False
    genius.remove_section_headers = True
    return genius


def _get_public_api():
    """Get public API client (no auth required)."""
    api = PublicAPI(timeout=30, retries=3)
    return api


def _search_artist_public(artist_name):
    """Search for artist using web scraping (no auth required)."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    try:
        # Use Genius search API with browser headers
        response = requests.get(
            'https://genius.com/api/search/artist',
            params={'q': artist_name},
            headers=headers,
            timeout=30
        )
        response.raise_for_status()

        data = response.json()
        sections = data.get('response', {}).get('sections', [])

        # Look for artist in top_hit or artist section
        for section in sections:
            if section.get('type') in ['top_hit', 'artist']:
                hits = section.get('hits', [])
                for hit in hits:
                    result = hit.get('result', {})
                    if result.get('_type') == 'artist':
                        return result.get('id'), result.get('name')

        # Fall back to song results and get artist from there
        for section in sections:
            if section.get('type') == 'song':
                hits = section.get('hits', [])
                for hit in hits:
                    result = hit.get('result', {})
                    artist = result.get('primary_artist', {})
                    if artist.get('name', '').lower() == artist_name.lower():
                        return artist.get('id'), artist.get('name')

                # Return first artist found
                if hits:
                    artist = hits[0].get('result', {}).get('primary_artist', {})
                    return artist.get('id'), artist.get('name')

        return None, None

    except Exception as e:
        logger.error(f"Error searching artist: {e}")
        return None, None


def scrape_genius(artist_name, max_songs=50, albums_only=True):
    """
    Scrape songs and lyrics for an artist from Genius.

    Args:
        artist_name: Name of the artist to search for
        max_songs: Maximum number of songs to fetch
        albums_only: If True, only fetch songs from official albums

    Returns:
        List of dicts with: title, artist, album, year, lyrics, url
    """
    try:
        # Search for the artist using public API
        artist_id, found_name = _search_artist_public(artist_name)
        if not artist_id:
            logger.warning(f"Artist not found: {artist_name}")
            return []

        # Get songs - either from albums or all songs
        if albums_only:
            songs = _get_songs_from_albums(artist_id, found_name or artist_name, max_songs)
        else:
            songs = _get_artist_songs_public(artist_id, found_name or artist_name, max_songs)

        return songs

    except Exception as e:
        logger.error(f"Error scraping Genius: {e}")
        raise ScraperError(f"Failed to scrape artist: {e}")


def _get_artist_songs_public(artist_id, artist_name, max_songs=50):
    """Get songs for an artist using public API."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
    }
    songs = []
    page = 1

    try:
        while len(songs) < max_songs:
            response = requests.get(
                f'https://genius.com/api/artists/{artist_id}/songs',
                params={'per_page': 20, 'page': page, 'sort': 'popularity'},
                headers=headers,
                timeout=30
            )
            response.raise_for_status()

            data = response.json()
            page_songs = data.get('response', {}).get('songs', [])

            if not page_songs:
                break

            for song_data in page_songs:
                if len(songs) >= max_songs:
                    break

                url = song_data.get('url', '')
                lyrics = _scrape_lyrics_from_url(url)

                if lyrics:
                    songs.append({
                        'title': song_data.get('title', ''),
                        'artist': song_data.get('primary_artist', {}).get('name', artist_name),
                        'album': song_data.get('album', {}).get('name') if song_data.get('album') else None,
                        'year': _extract_year_from_date(song_data.get('release_date_for_display')),
                        'lyrics': lyrics,
                        'url': url
                    })

                time.sleep(0.3)

            page += 1

        return songs

    except Exception as e:
        logger.error(f"Error fetching artist songs: {e}")
        return []


def _get_songs_from_albums(artist_id, artist_name, max_songs=50):
    """Get songs from official albums only."""
    public_api = _get_public_api()

    albums = _get_unique_albums(public_api, artist_id)
    songs = []

    for album in albums:
        if len(songs) >= max_songs:
            break

        album_id = album.get('id')
        album_name = album.get('name', '')

        tracks = _get_album_tracks(public_api, album_id)
        for track in tracks:
            if len(songs) >= max_songs:
                break

            song_data = track.get('song', {})
            url = song_data.get('url', '')

            # Scrape lyrics from URL
            lyrics = _scrape_lyrics_from_url(url)
            if lyrics:
                songs.append({
                    'title': song_data.get('title', ''),
                    'artist': song_data.get('primary_artist', {}).get('name', artist_name),
                    'album': album_name,
                    'year': _extract_year_from_date(song_data.get('release_date_for_display')),
                    'lyrics': lyrics,
                    'url': url
                })

            time.sleep(0.3)

    return songs


def _get_unique_albums(public_api, artist_id):
    """Get deduplicated albums for an artist."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
    }

    try:
        response = requests.get(
            f'https://genius.com/api/artists/{artist_id}/albums',
            params={'per_page': 50},
            headers=headers,
            timeout=30
        )
        response.raise_for_status()

        data = response.json()
        albums = data.get('response', {}).get('albums', [])

        unique_albums = []
        seen = set()

        for album in albums:
            name = album.get('name', '')
            normalized = _normalize_album_name(name)

            if normalized not in seen:
                seen.add(normalized)
                unique_albums.append(album)

        return unique_albums

    except Exception as e:
        logger.error(f"Error fetching albums: {e}")
        return []


def _get_album_tracks(public_api, album_id):
    """Get tracks from a specific album."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
    }

    try:
        response = requests.get(
            f'https://genius.com/api/albums/{album_id}/tracks',
            params={'per_page': 50},
            headers=headers,
            timeout=30
        )
        response.raise_for_status()

        data = response.json()
        return data.get('response', {}).get('tracks', [])

    except Exception as e:
        logger.error(f"Error fetching album tracks: {e}")
        return []


def _fetch_lyrics_musixmatch(artist_name, song_title):
    """Fetch lyrics from Musixmatch API."""
    if not MUSIXMATCH_API_KEY:
        return ''

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

        return ''
    except Exception as e:
        logger.debug(f"Musixmatch failed for {artist_name} - {song_title}: {e}")
        return ''


def _fetch_lyrics_lyricsovh(artist_name, song_title):
    """Fetch lyrics from lyrics.ovh API (free, no scraping needed)."""
    try:
        # Clean artist and title for URL
        artist = artist_name.strip()
        title = song_title.strip()

        response = requests.get(
            f'https://api.lyrics.ovh/v1/{artist}/{title}',
            timeout=15
        )

        if response.status_code == 200:
            data = response.json()
            lyrics = data.get('lyrics', '')
            if lyrics:
                logger.info(f"Got lyrics from lyrics.ovh for: {artist} - {title}")
                return lyrics.strip()

        return ''
    except Exception as e:
        logger.debug(f"lyrics.ovh failed for {artist_name} - {song_title}: {e}")
        return ''


def _scrape_lyrics_from_url(url, retries=3, artist_name=None, song_title=None):
    """Scrape lyrics from a Genius song URL using web scraping."""
    if not url:
        return ''

    logger.info(f"Scraping lyrics from: {url}")

    # Use browser-like headers to avoid 403 blocks
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }

    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 404:
                return ''
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Try multiple selectors for lyrics
            lyrics_containers = soup.select('[data-lyrics-container="true"]')
            if lyrics_containers:
                lyrics_parts = []
                for container in lyrics_containers:
                    # Remove script tags
                    for script in container.find_all('script'):
                        script.decompose()
                    # Get text with newlines
                    text = container.get_text(separator='\n')
                    lyrics_parts.append(text)
                return '\n'.join(lyrics_parts).strip()

            # Fallback selector
            lyrics_div = soup.find('div', class_=re.compile(r'Lyrics__Container'))
            if lyrics_div:
                for script in lyrics_div.find_all('script'):
                    script.decompose()
                return lyrics_div.get_text(separator='\n').strip()

            return ''

        except requests.exceptions.Timeout:
            if attempt == retries - 1:
                logger.warning(f"Timeout scraping {url}")
                return ''
            time.sleep(2 ** attempt)
        except requests.exceptions.RequestException as e:
            if attempt == retries - 1:
                logger.warning(f"Error scraping {url}: {e}")
                return ''
            time.sleep(2 ** attempt)
        except Exception as e:
            logger.warning(f"Parse error for {url}: {e}")
            return ''

    return ''


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


def search_song_genius(artist_name, song_title):
    """
    Search Genius for a song using the official API.

    Args:
        artist_name: Name of the artist
        song_title: Title of the song

    Returns:
        URL of the song on Genius, or None if not found
    """
    if not GENIUS_TOKEN:
        logger.warning("No Genius API token configured")
        return None

    headers = {
        'Authorization': f'Bearer {GENIUS_TOKEN}',
        'User-Agent': 'ArtistAnalyzer/1.0',
    }

    try:
        # Search using official Genius API
        response = requests.get(
            'https://api.genius.com/search',
            params={'q': f'{artist_name} {song_title}'},
            headers=headers,
            timeout=30
        )
        response.raise_for_status()

        data = response.json()
        hits = data.get('response', {}).get('hits', [])

        if not hits:
            logger.debug(f"No Genius results for: {artist_name} - {song_title}")
            return None

        # Find best match - prefer exact artist match
        artist_lower = artist_name.lower()
        song_lower = song_title.lower()

        for hit in hits:
            result = hit.get('result', {})
            result_artist = result.get('primary_artist', {}).get('name', '').lower()
            result_title = result.get('title', '').lower()

            # Check if artist matches (fuzzy)
            if artist_lower in result_artist or result_artist in artist_lower:
                # Check if song title is similar
                if _titles_match(song_lower, result_title):
                    url = result.get('url')
                    logger.debug(f"Found Genius match: {url}")
                    return url

        # Fall back to first result if no exact match
        first_result = hits[0].get('result', {})
        url = first_result.get('url')
        logger.debug(f"Using first Genius result: {url}")
        return url

    except requests.exceptions.RequestException as e:
        logger.error(f"Error searching Genius API: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error searching Genius: {e}")
        return None


def _titles_match(title1, title2):
    """Check if two song titles match (fuzzy comparison)."""
    # Normalize titles
    def normalize(t):
        # Remove common suffixes, punctuation
        t = re.sub(r'\s*\(.*?\)', '', t)  # Remove parenthetical
        t = re.sub(r'\s*\[.*?\]', '', t)  # Remove bracketed
        t = re.sub(r'[^\w\s]', '', t)  # Remove punctuation
        return t.lower().strip()

    n1 = normalize(title1)
    n2 = normalize(title2)

    # Exact match after normalization
    if n1 == n2:
        return True

    # One contains the other
    if n1 in n2 or n2 in n1:
        return True

    return False


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


def scrape_album(album_id, album_name=None, artist_name=None, progress_callback=None):
    """
    Scrape lyrics for all songs in an album using Discogs + Genius hybrid approach.

    Args:
        album_id: Discogs master/release ID
        album_name: Album name (optional, for metadata)
        artist_name: Artist name (required for Genius search)
        progress_callback: Optional callback(current, total, title) for progress updates

    Returns:
        List of dicts with: title, artist, album, year, lyrics, url
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
            logger.info(f"[{i}/{total_tracks}] Fetching lyrics for: {artist_name} - {title}")

            # Report progress if callback provided
            if progress_callback:
                progress_callback(i, total_tracks, title)

            lyrics = None
            source_url = None

            # Try Musixmatch first (paid, best coverage)
            if MUSIXMATCH_API_KEY:
                lyrics = _fetch_lyrics_musixmatch(artist_name, title)
                if lyrics:
                    source_url = 'musixmatch'

            # Try lyrics.ovh second (free API)
            if not lyrics:
                lyrics = _fetch_lyrics_lyricsovh(artist_name, title)
                if lyrics:
                    source_url = 'lyrics.ovh'

            # Fall back to Genius search + scraping (often blocked from cloud)
            if not lyrics:
                genius_url = search_song_genius(artist_name, title)
                if genius_url:
                    lyrics = _scrape_lyrics_from_url(genius_url, artist_name=artist_name, song_title=title)
                    source_url = genius_url

            if lyrics:
                results.append({
                    'title': title,
                    'artist': artist_name,
                    'album': album_name,
                    'year': album_year,
                    'lyrics': lyrics,
                    'url': source_url
                })
                logger.info(f"  ✓ Got {len(lyrics)} chars of lyrics")
            else:
                logger.warning(f"  ✗ Could not find lyrics for: {title}")

            # Rate limiting
            time.sleep(0.3)

        logger.info(f"=== SCRAPING COMPLETE: {len(results)}/{len(tracks)} songs with lyrics ===")
        return results

    except DiscogsError as e:
        logger.error(f"Discogs API error: {e}")
        raise ScraperError(f"Failed to get album from Discogs: {e}")
    except Exception as e:
        logger.error(f"Error scraping album: {e}")
        raise ScraperError(f"Failed to scrape album: {e}")
