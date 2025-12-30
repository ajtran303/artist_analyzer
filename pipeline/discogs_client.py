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


def _get_client():
    """Get authenticated Discogs client."""
    if not DISCOGS_TOKEN:
        raise DiscogsError("DISCOGS_API_TOKEN environment variable not set")
    return discogs_client.Client(
        'ArtistAnalyzer/1.0',
        user_token=DISCOGS_TOKEN
    )


def search_artist(artist_name):
    """
    Search for an artist on Discogs.

    Args:
        artist_name: Name of the artist to search for

    Returns:
        Tuple of (artist_id, artist_name) or (None, None) if not found
    """
    try:
        d = _get_client()
        results = d.search(artist_name, type='artist')

        if results and len(results) > 0:
            artist = results[0]
            # Clean disambiguation number from artist name
            cleaned_name = clean_artist_name(artist.name)
            logger.info(f"Found artist on Discogs: {artist.name} -> {cleaned_name} (ID: {artist.id})")
            return artist.id, cleaned_name

        logger.warning(f"Artist not found on Discogs: {artist_name}")
        return None, None

    except Exception as e:
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
        d = _get_client()

        if is_master:
            # Get the main release for this master
            master = d.master(release_id)
            release = master.main_release
        else:
            release = d.release(release_id)

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

    except Exception as e:
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
        d = _get_client()

        if is_master:
            master = d.master(release_id)
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

    except Exception as e:
        logger.error(f"Error fetching release info from Discogs: {e}")
        return None


