"""Discogs API client for fetching artist and album metadata."""

import os
import logging
import re
import time
import requests
import discogs_client

logger = logging.getLogger(__name__)


def clean_artist_name(name):
    """
    Remove Discogs disambiguation numbers from artist names.

    Discogs adds numbers in parentheses to distinguish artists with the same name,
    e.g., "Will Wood (7)" or "The National (2)".

    Args:
        name: Artist name possibly containing disambiguation number

    Returns:
        Cleaned artist name without disambiguation number
    """
    if not name:
        return name
    # Match " (number)" at the end of the string
    cleaned = re.sub(r'\s*\(\d+\)\s*$', '', name)
    return cleaned.strip()

DISCOGS_TOKEN = os.environ.get('DISCOGS_API_TOKEN', '')


class DiscogsError(Exception):
    """Custom exception for Discogs API errors."""
    pass


def _check_rate_limit():
    """
    Check Discogs rate limit before making a request.
    Waits if limit is reached, raises DiscogsError if wait is too long.
    """
    from pipeline.api_metrics import get_metrics
    metrics = get_metrics()

    allowed, wait_time = metrics.check_limit('discogs')
    if not allowed:
        if wait_time and wait_time <= 60:
            logger.info(f"Discogs rate limit reached, waiting {wait_time}s")
            time.sleep(wait_time)
        else:
            raise DiscogsError(f"Discogs rate limit exceeded, reset in {wait_time}s")


def _track_discogs_call(success=True):
    """Track a Discogs API call."""
    from pipeline.api_metrics import get_metrics
    metrics = get_metrics()
    metrics.track_call('discogs', success=success)


def _get_client():
    """Get authenticated Discogs client with timeouts configured."""
    if not DISCOGS_TOKEN:
        raise DiscogsError("DISCOGS_API_TOKEN environment variable not set")
    client = discogs_client.Client(
        'ArtistAnalyzer/1.0',
        user_token=DISCOGS_TOKEN
    )
    # Set timeouts to prevent hanging requests
    client._fetcher.connect_timeout = 10
    client._fetcher.read_timeout = 30
    return client


def search_artist(artist_name):
    """
    Search for an artist on Discogs.

    Args:
        artist_name: Name of the artist to search for

    Returns:
        Tuple of (artist_id, artist_name) or (None, None) if not found
    """
    try:
        _check_rate_limit()
        d = _get_client()
        results = d.search(artist_name, type='artist')
        _track_discogs_call(success=True)

        if results and len(results) > 0:
            artist = results[0]
            # Clean disambiguation number from artist name
            cleaned_name = clean_artist_name(artist.name)
            logger.info(f"Found artist on Discogs: {artist.name} -> {cleaned_name} (ID: {artist.id})")
            return artist.id, cleaned_name

        logger.warning(f"Artist not found on Discogs: {artist_name}")
        return None, None

    except DiscogsError:
        raise
    except Exception as e:
        _track_discogs_call(success=False)
        logger.error(f"Error searching Discogs for artist: {e}")
        return None, None


def get_artist_albums(artist_id, page=1, per_page=20):
    """
    Get albums for an artist from Discogs with server-side pagination.
    Keeps fetching pages until we have enough filtered results or run out.

    Args:
        artist_id: Discogs artist ID
        page: Page number (1-indexed)
        per_page: Number of albums per page

    Returns:
        Dict with albums list, has_more flag, and total count
    """
    headers = {
        'User-Agent': 'ArtistAnalyzer/1.0',
        'Authorization': f'Discogs token={DISCOGS_TOKEN}',
    }

    albums = []
    current_page = page
    total_pages = 1
    max_pages_to_fetch = 5  # Limit to avoid too many requests

    try:
        # Keep fetching until we have enough albums or run out of pages
        pages_fetched = 0
        while len(albums) < per_page and pages_fetched < max_pages_to_fetch:
            _check_rate_limit()
            response = requests.get(
                f'https://api.discogs.com/artists/{artist_id}/releases',
                params={
                    'page': current_page,
                    'per_page': 100,  # Fetch more per page to reduce requests
                    'sort': 'year',
                    'sort_order': 'asc',
                },
                headers=headers,
                timeout=30
            )
            _track_discogs_call(success=response.ok)
            response.raise_for_status()
            data = response.json()

            releases = data.get('releases', [])
            pagination = data.get('pagination', {})
            total_pages = pagination.get('pages', 1)

            # Filter for master releases where artist has main role
            for release in releases:
                release_type = release.get('type', '')
                role = release.get('role', '')

                # Only include masters where artist is primary
                if role and role.lower() != 'main':
                    continue
                if release_type != 'master':
                    continue

                albums.append({
                    'id': release.get('id'),
                    'name': release.get('title', ''),
                    'year': release.get('year'),
                    'type': 'master'
                })

            pages_fetched += 1
            current_page += 1

            # Stop if we've reached the last page
            if current_page > total_pages:
                break

        has_more = current_page <= total_pages

        logger.info(f"Returning {len(albums)} albums (fetched {pages_fetched} pages, next: {current_page}) for artist ID {artist_id}")
        return {
            'albums': albums,
            'has_more': has_more,
            'next_page': current_page,  # Return the next page to fetch
            'page': page
        }

    except DiscogsError:
        raise
    except Exception as e:
        logger.error(f"Error fetching artist albums from Discogs: {e}")
        return {'albums': [], 'has_more': False, 'total': 0, 'page': page}


def get_release_tracks(release_id, is_master=True):
    """
    Get tracklist for a release from Discogs.

    Args:
        release_id: Discogs release or master ID
        is_master: True if release_id is a master ID

    Returns:
        List of track dicts with position, title, duration
    """
    try:
        _check_rate_limit()
        d = _get_client()

        if is_master:
            # Get the main release for this master
            master = d.master(release_id)
            _track_discogs_call(success=True)
            release = master.main_release
            _track_discogs_call(success=True)  # main_release is another API call
        else:
            release = d.release(release_id)
            _track_discogs_call(success=True)

        tracks = []
        for track in release.tracklist:
            # Skip non-track entries (like headings)
            position = track.position if hasattr(track, 'position') else ''
            if not position:
                continue

            tracks.append({
                'position': position,
                'title': track.title,
                'duration': track.duration if hasattr(track, 'duration') else ''
            })

        logger.info(f"Found {len(tracks)} tracks for release ID {release_id}")
        return tracks

    except DiscogsError:
        raise
    except Exception as e:
        _track_discogs_call(success=False)
        logger.error(f"Error fetching release tracks from Discogs: {e}")
        return []


def get_release_info(release_id, is_master=True):
    """
    Get release metadata from Discogs.

    Args:
        release_id: Discogs release or master ID
        is_master: True if release_id is a master ID

    Returns:
        Dict with title, year, artist, genres, cover_art_url
    """
    try:
        _check_rate_limit()
        d = _get_client()

        if is_master:
            master = d.master(release_id)
            _track_discogs_call(success=True)
            # Get artist from main_release since master might not have artists directly
            artist_name = ''
            if hasattr(master, 'artists') and master.artists:
                artist_name = master.artists[0].name
            elif hasattr(master, 'main_release'):
                main_release = master.main_release
                if hasattr(main_release, 'artists') and main_release.artists:
                    artist_name = main_release.artists[0].name
            return {
                'title': master.title,
                'year': master.year if hasattr(master, 'year') else None,
                'artist': clean_artist_name(artist_name),
                'genres': master.genres if hasattr(master, 'genres') else [],
                'cover_art_url': master.images[0]['uri'] if hasattr(master, 'images') and master.images else ''
            }
        else:
            release = d.release(release_id)
            _track_discogs_call(success=True)
            artist_name = ''
            if hasattr(release, 'artists') and release.artists:
                artist_name = release.artists[0].name
            return {
                'title': release.title,
                'year': release.year if hasattr(release, 'year') else None,
                'artist': clean_artist_name(artist_name),
                'genres': release.genres if hasattr(release, 'genres') else [],
                'cover_art_url': release.images[0]['uri'] if hasattr(release, 'images') and release.images else ''
            }

    except DiscogsError:
        raise
    except Exception as e:
        _track_discogs_call(success=False)
        logger.error(f"Error fetching release info from Discogs: {e}")
        return None


def search_albums(query, page=1, per_page=20):
    """
    Search for albums on Discogs by title using direct API call.

    Args:
        query: Album title to search for
        page: Page number (1-indexed)
        per_page: Number of results per page

    Returns:
        Dict with albums list, has_more flag, page, and next_page
    """
    headers = {
        'User-Agent': 'ArtistAnalyzer/1.0',
        'Authorization': f'Discogs token={DISCOGS_TOKEN}',
    }

    try:
        _check_rate_limit()

        # Use requests directly for proper timeout control
        response = requests.get(
            'https://api.discogs.com/database/search',
            params={
                'q': query,
                'type': 'master',
                'page': page,
                'per_page': per_page,
            },
            headers=headers,
            timeout=15  # 15 second timeout for search
        )
        _track_discogs_call(success=response.ok)
        response.raise_for_status()
        data = response.json()

        results = data.get('results', [])
        pagination = data.get('pagination', {})

        albums = []
        for result in results:
            # Parse "Artist - Album" format from title
            title = result.get('title', '')
            artist_name = ''
            album_title = title

            if ' - ' in title:
                parts = title.split(' - ', 1)
                artist_name = parts[0].strip()
                album_title = parts[1].strip() if len(parts) > 1 else title

            # Clean disambiguation numbers from artist name
            artist_name = clean_artist_name(artist_name) if artist_name else ''

            albums.append({
                'id': result.get('id'),
                'name': album_title,
                'artist': artist_name,
                'year': result.get('year'),
                'type': 'master'
            })

        total_pages = pagination.get('pages', 1)
        current_page = pagination.get('page', page)
        has_more = current_page < total_pages

        logger.info(f"Album search for '{query}': found {len(albums)} results (page {current_page}/{total_pages})")

        return {
            'albums': albums,
            'has_more': has_more,
            'page': current_page,
            'next_page': current_page + 1 if has_more else None
        }

    except DiscogsError:
        raise
    except requests.Timeout:
        _track_discogs_call(success=False)
        logger.error(f"Timeout searching albums on Discogs for: {query}")
        return {
            'albums': [],
            'has_more': False,
            'page': page,
            'next_page': None
        }
    except Exception as e:
        _track_discogs_call(success=False)
        logger.error(f"Error searching albums on Discogs: {e}")
        return {
            'albums': [],
            'has_more': False,
            'page': page,
            'next_page': None
        }


