"""Genius API scraper for fetching artist lyrics using lyricsgenius."""

import os
import re
import time
import logging
import requests
from bs4 import BeautifulSoup
from lyricsgenius import Genius, PublicAPI

logger = logging.getLogger(__name__)

GENIUS_TOKEN = os.environ.get('GENIUS_API_TOKEN', '')


def _get_browser_headers():
    """Get browser-like headers to avoid blocking."""
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://genius.com/',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }


def _get_api_headers():
    """Get headers for Genius API calls."""
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://genius.com/',
        'Origin': 'https://genius.com',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
    }


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


def _search_artist_authenticated(artist_name):
    """Search for artist using lyricsgenius library (handles API properly)."""
    genius = _get_genius_client()
    if not genius:
        logger.warning("No GENIUS_API_TOKEN set, skipping authenticated search")
        return None, None

    try:
        # Use lyricsgenius to search - it handles the API correctly
        search_results = genius.search_songs(artist_name)
        hits = search_results.get('hits', []) if search_results else []

        # Find artist from search results
        for hit in hits:
            result = hit.get('result', {})
            artist = result.get('primary_artist', {})
            artist_name_found = artist.get('name', '')
            if artist_name_found.lower() == artist_name.lower():
                logger.info(f"Found exact match: {artist_name_found}")
                return artist.get('id'), artist_name_found

        # Return first artist found if no exact match
        if hits:
            artist = hits[0].get('result', {}).get('primary_artist', {})
            logger.info(f"Found artist: {artist.get('name')}")
            return artist.get('id'), artist.get('name')

        return None, None
    except Exception as e:
        logger.warning(f"Authenticated search failed: {e}")
        return None, None


def _search_artist(artist_name):
    """Search for artist using authenticated API only."""
    # Only use authenticated API - public web API is blocked on cloud servers
    artist_id, artist_name_found = _search_artist_authenticated(artist_name)
    if artist_id:
        logger.info(f"Found artist: {artist_name_found} (ID: {artist_id})")
        return artist_id, artist_name_found

    logger.error(f"Could not find artist: {artist_name}")
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
        # Search for the artist (tries authenticated first, then public)
        artist_id, found_name = _search_artist(artist_name)
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
    songs = []
    page = 1

    try:
        while len(songs) < max_songs:
            response = requests.get(
                f'https://genius.com/api/artists/{artist_id}/songs',
                params={'per_page': 20, 'page': page, 'sort': 'popularity'},
                headers=_get_api_headers(),
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

    albums = _get_unique_albums(public_api, artist_id, artist_name=artist_name)
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


def _get_unique_albums(public_api, artist_id, artist_name=None):
    """Get deduplicated albums for an artist using official API only."""
    genius = _get_genius_client()
    if not genius:
        logger.error("No Genius client available - GENIUS_API_TOKEN not set?")
        return []

    try:
        # Method 1: Try search_albums if we have artist name
        if artist_name:
            logger.info(f"Searching albums for: {artist_name}")
            albums_data = genius.search_albums(artist_name)

            if albums_data:
                hits = albums_data.get('sections', [{}])[0].get('hits', [])
                logger.info(f"Found {len(hits)} album search results")

                unique_albums = []
                seen = set()

                for hit in hits:
                    album = hit.get('result', {})
                    # Check if album is by the right artist
                    album_artist = album.get('artist', {}).get('name', '')
                    if album_artist.lower() == artist_name.lower():
                        name = album.get('name', '')
                        normalized = _normalize_album_name(name)
                        if normalized and normalized not in seen:
                            seen.add(normalized)
                            # Format album data consistently
                            unique_albums.append({
                                'id': album.get('id'),
                                'name': name,
                                'cover_art_thumbnail_url': album.get('cover_art_thumbnail_url', ''),
                                'cover_art_url': album.get('cover_art_url', ''),
                                'release_date_for_display': album.get('release_date_for_display'),
                                'artist': album.get('artist', {})
                            })

                if unique_albums:
                    logger.info(f"Found {len(unique_albums)} albums for {artist_name}")
                    return unique_albums

        # Method 2: Fall back to getting full artist info
        logger.info(f"Trying to get artist info for ID: {artist_id}")
        artist_info = genius.artist(artist_id)
        if artist_info:
            logger.info(f"Artist info keys: {list(artist_info.get('artist', {}).keys()) if artist_info.get('artist') else 'None'}")

        return []

    except Exception as e:
        logger.error(f"Error fetching albums via lyricsgenius: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []


def _get_album_tracks(public_api, album_id):
    """Get tracks from a specific album using official API only."""
    genius = _get_genius_client()
    if not genius:
        logger.error("No Genius client available - GENIUS_API_TOKEN not set?")
        return []

    try:
        logger.info(f"Fetching tracks for album {album_id}...")
        tracks_data = genius.album_tracks(album_id)
        tracks = tracks_data.get('tracks', []) if tracks_data else []
        logger.info(f"Got {len(tracks)} tracks via lyricsgenius")
        return tracks
    except Exception as e:
        logger.error(f"Error fetching album tracks via lyricsgenius: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []


def _scrape_lyrics_from_url(url, retries=3):
    """Scrape lyrics from a Genius song URL using web scraping."""
    if not url:
        return ''

    logger.info(f"Scraping lyrics from: {url}")

    for attempt in range(retries):
        try:
            response = requests.get(url, headers=_get_browser_headers(), timeout=30)
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


def search_artist_albums(artist_name):
    """
    Search for an artist and return their albums.

    Args:
        artist_name: Name of the artist to search for

    Returns:
        Dict with artist_id, artist_name, and albums list
    """
    public_api = _get_public_api()

    try:
        # Search for the artist (tries authenticated first, then public)
        artist_id, found_name = _search_artist(artist_name)
        if not artist_id:
            return None

        # Get albums using authenticated API
        albums = _get_unique_albums(public_api, artist_id, artist_name=found_name or artist_name)

        # Format albums for frontend
        formatted_albums = []
        for album in albums:
            formatted_albums.append({
                'id': album.get('id'),
                'name': album.get('name', ''),
                'cover_art_url': album.get('cover_art_thumbnail_url', ''),
                'year': _extract_year_from_date(album.get('release_date_for_display')),
                'artist': album.get('artist', {}).get('name', artist_name)
            })

        return {
            'artist_id': artist_id,
            'artist_name': found_name or artist_name,
            'albums': formatted_albums
        }

    except Exception as e:
        logger.error(f"Error searching artist albums: {e}")
        return None


def scrape_album(album_id, album_name=None):
    """
    Scrape lyrics for all songs in a specific album.

    Args:
        album_id: Genius album ID
        album_name: Album name (optional, for metadata)

    Returns:
        List of dicts with: title, artist, album, year, lyrics, url
    """
    logger.info(f"=== SCRAPING ALBUM: {album_name} (ID: {album_id}) ===")
    public_api = _get_public_api()

    try:
        tracks = _get_album_tracks(public_api, album_id)
        logger.info(f"Found {len(tracks)} tracks in album")
        results = []

        for i, track in enumerate(tracks, 1):
            song_data = track.get('song', {})
            url = song_data.get('url', '')
            title = song_data.get('title', 'Unknown')

            logger.info(f"[{i}/{len(tracks)}] Scraping: {title}")

            lyrics = _scrape_lyrics_from_url(url)
            if lyrics:
                results.append({
                    'title': title,
                    'artist': song_data.get('primary_artist', {}).get('name', ''),
                    'album': album_name,
                    'year': _extract_year_from_date(song_data.get('release_date_for_display')),
                    'lyrics': lyrics,
                    'url': url
                })
                logger.info(f"  ✓ Got {len(lyrics)} chars of lyrics")
            else:
                logger.warning(f"  ✗ No lyrics found for: {title}")

            # Rate limiting
            time.sleep(0.3)

        logger.info(f"=== SCRAPING COMPLETE: {len(results)} songs with lyrics ===")
        return results

    except Exception as e:
        logger.error(f"Error scraping album: {e}")
        raise ScraperError(f"Failed to scrape album: {e}")
