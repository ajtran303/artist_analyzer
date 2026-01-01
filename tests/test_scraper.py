"""Unit tests for scraper module."""

import pytest
from unittest.mock import patch, MagicMock

from pipeline.scraper import (
    search_artist_albums,
    search_albums_by_title,
    scrape_album,
    _normalize_album_name,
    _extract_year_from_date,
    ScraperError
)
from pipeline.discogs_client import clean_artist_name, search_albums


@pytest.mark.unit
class TestSearchArtistAlbums:
    """Tests for search_artist_albums function."""

    @patch('pipeline.scraper.discogs_search_artist')
    @patch('pipeline.scraper.discogs_get_artist_albums')
    def test_returns_correct_structure(self, mock_albums, mock_search):
        """Returns correct structure with artist and albums."""
        mock_search.return_value = (456, 'Test Artist')

        mock_albums.return_value = {
            'albums': [
                {'id': 1, 'name': 'Album 1', 'year': 2020},
                {'id': 2, 'name': 'Album 2', 'year': 2021}
            ],
            'has_more': False,
            'next_page': 2,
            'page': 1
        }

        result = search_artist_albums('Test Artist')

        assert result['artist_id'] == 456
        assert result['artist_name'] == 'Test Artist'
        assert len(result['albums']) == 2
        assert result['albums'][0]['id'] == 1
        assert result['albums'][0]['name'] == 'Album 1'
        assert result['albums'][0]['year'] == 2020

    @patch('pipeline.scraper.discogs_search_artist')
    def test_returns_none_if_artist_not_found(self, mock_search):
        """Returns None if artist not found."""
        mock_search.return_value = (None, None)

        result = search_artist_albums('Unknown Artist')

        assert result is None


@pytest.mark.unit
class TestScrapeAlbum:
    """Tests for scrape_album function."""

    @patch('pipeline.scraper.discogs_get_release_info')
    @patch('pipeline.scraper.discogs_get_release_tracks')
    @patch('pipeline.scraper._fetch_lyrics_musixmatch')
    @patch('pipeline.scraper._fetch_lyrics_lyricsovh')
    def test_returns_songs_from_album(self, mock_lyricsovh, mock_musixmatch, mock_tracks, mock_info):
        """Returns song data for album tracks."""
        mock_info.return_value = {'artist': 'Test Artist', 'year': 2020}
        mock_tracks.return_value = [
            {'title': 'Track 1', 'position': '1'},
            {'title': 'Track 2', 'position': '2'}
        ]
        mock_musixmatch.side_effect = ['Lyrics 1', 'Lyrics 2']
        mock_lyricsovh.return_value = None  # Not called since musixmatch succeeds

        result = scrape_album(12345, 'Test Album')

        assert result['total_tracks'] == 2
        assert result['tracks_with_lyrics'] == 2
        assert len(result['songs']) == 2
        assert result['songs'][0]['title'] == 'Track 1'
        assert result['songs'][0]['lyrics'] == 'Lyrics 1'
        assert result['songs'][0]['album'] == 'Test Album'
        assert result['songs'][0]['artist'] == 'Test Artist'

    @patch('pipeline.scraper.discogs_get_release_info')
    @patch('pipeline.scraper.discogs_get_release_tracks')
    def test_returns_empty_if_no_tracks(self, mock_tracks, mock_info):
        """Returns empty list if no tracks found."""
        mock_info.return_value = {'artist': 'Test Artist', 'year': 2020}
        mock_tracks.return_value = []
        result = scrape_album(12345, 'Test Album')
        assert result == []

    @patch('pipeline.scraper.discogs_get_release_info')
    @patch('pipeline.scraper.discogs_get_release_tracks')
    @patch('pipeline.scraper._fetch_lyrics_musixmatch')
    @patch('pipeline.scraper._fetch_lyrics_lyricsovh')
    def test_falls_back_to_lyricsovh(self, mock_lyricsovh, mock_musixmatch, mock_tracks, mock_info):
        """Falls back to lyrics.ovh when Musixmatch fails."""
        mock_info.return_value = {'artist': 'Test Artist', 'year': 2020}
        mock_tracks.return_value = [{'title': 'Track 1', 'position': '1'}]
        mock_musixmatch.return_value = ''  # Musixmatch fails
        mock_lyricsovh.return_value = 'Lyrics from lyrics.ovh'

        result = scrape_album(12345, 'Test Album')

        assert result['tracks_with_lyrics'] == 1
        assert result['songs'][0]['lyrics'] == 'Lyrics from lyrics.ovh'
        assert result['songs'][0]['url'] == 'lyrics.ovh'


@pytest.mark.unit
class TestNormalizeAlbumName:
    """Tests for album name normalization."""

    def test_removes_deluxe_suffix(self):
        """Removes deluxe edition suffix."""
        assert _normalize_album_name('Album (Deluxe Edition)') == 'album'
        assert _normalize_album_name('Album [Deluxe]') == 'album'
        assert _normalize_album_name('Album - Deluxe') == 'album'

    def test_removes_remaster_suffix(self):
        """Removes remaster suffix."""
        assert _normalize_album_name('Album (Remastered)') == 'album'
        assert _normalize_album_name('Album (2020 Remaster)') == 'album'

    def test_removes_explicit_suffix(self):
        """Removes explicit tag."""
        assert _normalize_album_name('Album (Explicit)') == 'album'
        assert _normalize_album_name('Album [Explicit]') == 'album'

    def test_handles_complex_names(self):
        """Handles album names with multiple suffixes."""
        name = 'The Album (Deluxe Edition) (Explicit)'
        # Should remove at least deluxe
        result = _normalize_album_name(name)
        assert 'deluxe' not in result.lower()

    def test_preserves_core_name(self):
        """Preserves the core album name."""
        assert _normalize_album_name('Greatest Hits') == 'greatest hits'
        assert _normalize_album_name("The Dark Side of the Moon") == "the dark side of the moon"


@pytest.mark.unit
class TestExtractYearFromDate:
    """Tests for year extraction."""

    def test_extracts_year_from_full_date(self):
        """Extracts year from full date string."""
        assert _extract_year_from_date('January 1, 2020') == 2020
        assert _extract_year_from_date('December 31, 1999') == 1999

    def test_extracts_year_only(self):
        """Handles year-only string."""
        assert _extract_year_from_date('2021') == 2021

    def test_handles_none(self):
        """Returns None for None input."""
        assert _extract_year_from_date(None) is None

    def test_handles_empty_string(self):
        """Returns None for empty string."""
        assert _extract_year_from_date('') is None

    def test_handles_invalid_format(self):
        """Returns None for invalid format."""
        assert _extract_year_from_date('No Date') is None


@pytest.mark.unit
class TestErrorHandling:
    """Tests for error handling in scraper."""

    @patch('pipeline.scraper.discogs_search_artist')
    def test_returns_none_on_discogs_error(self, mock_search):
        """Returns None when Discogs search fails."""
        mock_search.side_effect = Exception("API Error")

        result = search_artist_albums('Test Artist')
        assert result is None


@pytest.mark.unit
class TestCleanArtistName:
    """Tests for clean_artist_name function."""

    def test_removes_disambiguation_number(self):
        """Removes Discogs disambiguation numbers."""
        assert clean_artist_name('Will Wood (7)') == 'Will Wood'
        assert clean_artist_name('The National (2)') == 'The National'
        assert clean_artist_name('James (3)') == 'James'

    def test_handles_large_numbers(self):
        """Handles large disambiguation numbers."""
        assert clean_artist_name('John Smith (123)') == 'John Smith'
        assert clean_artist_name('Artist (9999)') == 'Artist'

    def test_preserves_non_disambiguation_parentheses(self):
        """Preserves parentheses that are not disambiguation numbers."""
        assert clean_artist_name('Panic! At The Disco') == 'Panic! At The Disco'
        assert clean_artist_name('(Sandy) Alex G') == '(Sandy) Alex G'
        assert clean_artist_name('fun.') == 'fun.'

    def test_handles_no_parentheses(self):
        """Handles names without parentheses."""
        assert clean_artist_name('The Beatles') == 'The Beatles'
        assert clean_artist_name('Taylor Swift') == 'Taylor Swift'

    def test_handles_empty_and_none(self):
        """Handles empty string and None."""
        assert clean_artist_name('') == ''
        assert clean_artist_name(None) is None

    def test_handles_parentheses_with_text(self):
        """Does not remove parentheses containing text."""
        assert clean_artist_name('Artist (UK)') == 'Artist (UK)'
        assert clean_artist_name('Band (featuring Guest)') == 'Band (featuring Guest)'


@pytest.mark.unit
class TestSearchAlbums:
    """Tests for search_albums function in discogs_client."""

    @patch('pipeline.discogs_client.requests.get')
    def test_returns_correct_structure(self, mock_get):
        """Returns correct structure with albums list and pagination."""
        # Mock the API response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'results': [
                {
                    'id': 12345,
                    'title': 'The Cure - Disintegration',
                    'year': 1989,
                },
                {
                    'id': 67890,
                    'title': 'Monolord - Disintegration',
                    'year': 2014,
                }
            ],
            'pagination': {
                'pages': 1,
                'page': 1
            }
        }
        mock_get.return_value = mock_response

        result = search_albums('Disintegration')

        assert 'albums' in result
        assert 'has_more' in result
        assert 'page' in result
        assert len(result['albums']) == 2
        assert result['albums'][0]['id'] == 12345
        assert result['albums'][0]['name'] == 'Disintegration'
        assert result['albums'][0]['artist'] == 'The Cure'
        assert result['albums'][0]['year'] == 1989

    @patch('pipeline.discogs_client.requests.get')
    def test_returns_empty_if_no_results(self, mock_get):
        """Returns empty albums list if no results found."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'results': [],
            'pagination': {
                'pages': 0,
                'page': 1
            }
        }
        mock_get.return_value = mock_response

        result = search_albums('Nonexistent Album Title XYZ')

        assert result['albums'] == []
        assert result['has_more'] is False

    @patch('pipeline.discogs_client.requests.get')
    def test_cleans_artist_name_in_results(self, mock_get):
        """Artist names are cleaned of disambiguation numbers."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'results': [
                {
                    'id': 11111,
                    'title': 'Will Wood (7) - Test Album',
                    'year': 2020,
                }
            ],
            'pagination': {
                'pages': 1,
                'page': 1
            }
        }
        mock_get.return_value = mock_response

        result = search_albums('Test Album')

        assert result['albums'][0]['artist'] == 'Will Wood'

    @patch('pipeline.discogs_client.requests.get')
    def test_handles_pagination(self, mock_get):
        """Handles pagination with has_more and next_page."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'results': [
                {
                    'id': 12345,
                    'title': 'Artist - Album',
                    'year': 2020,
                }
            ],
            'pagination': {
                'pages': 3,
                'page': 1
            }
        }
        mock_get.return_value = mock_response

        result = search_albums('Album', page=1)

        assert result['has_more'] is True
        assert result['next_page'] == 2
        assert result['page'] == 1

    @patch('pipeline.discogs_client.requests.get')
    def test_returns_empty_on_exception(self, mock_get):
        """Returns empty result on API exception."""
        mock_get.side_effect = Exception("API Error")

        result = search_albums('Test Album')

        assert result['albums'] == []
        assert result['has_more'] is False

    @patch('pipeline.discogs_client.requests.get')
    def test_handles_missing_artist(self, mock_get):
        """Handles albums without artist information."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'results': [
                {
                    'id': 12345,
                    'title': 'Various Artists Compilation',  # No " - " separator
                    'year': 2020,
                }
            ],
            'pagination': {
                'pages': 1,
                'page': 1
            }
        }
        mock_get.return_value = mock_response

        result = search_albums('Various Artists Compilation')

        assert result['albums'][0]['artist'] == ''

    @patch('pipeline.discogs_client.requests.get')
    def test_extracts_artist_from_title(self, mock_get):
        """Extracts artist from 'Artist - Album' title format."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'results': [
                {
                    'id': 12345,
                    'title': 'Abnormity (2) - Irreversible Disintegration',
                    'year': 2010,
                }
            ],
            'pagination': {
                'pages': 1,
                'page': 1
            }
        }
        mock_get.return_value = mock_response

        result = search_albums('Irreversible Disintegration')

        # Should extract and clean artist name from title
        assert result['albums'][0]['artist'] == 'Abnormity'
        assert result['albums'][0]['name'] == 'Irreversible Disintegration'


@pytest.mark.unit
class TestSearchAlbumsByTitle:
    """Tests for search_albums_by_title function in scraper."""

    @patch('pipeline.scraper.discogs_search_albums')
    def test_returns_correct_structure(self, mock_search):
        """Returns correct structure with albums list and pagination."""
        mock_search.return_value = {
            'albums': [
                {'id': 12345, 'name': 'Disintegration', 'artist': 'The Cure', 'year': 1989, 'type': 'master'},
                {'id': 67890, 'name': 'Disintegration', 'artist': 'Monolord', 'year': 2014, 'type': 'master'}
            ],
            'has_more': False,
            'page': 1,
            'next_page': None
        }

        result = search_albums_by_title('Disintegration')

        assert 'albums' in result
        assert len(result['albums']) == 2
        assert result['albums'][0]['name'] == 'Disintegration'
        assert result['albums'][0]['artist'] == 'The Cure'

    @patch('pipeline.scraper.discogs_search_albums')
    def test_returns_empty_if_no_results(self, mock_search):
        """Returns empty albums list if no results found."""
        mock_search.return_value = {
            'albums': [],
            'has_more': False,
            'page': 1,
            'next_page': None
        }

        result = search_albums_by_title('Nonexistent Album')

        assert result['albums'] == []

    @patch('pipeline.scraper.discogs_search_albums')
    def test_handles_pagination(self, mock_search):
        """Handles pagination parameters."""
        mock_search.return_value = {
            'albums': [{'id': 1, 'name': 'Test', 'artist': 'Artist', 'year': 2020, 'type': 'master'}],
            'has_more': True,
            'page': 2,
            'next_page': 3
        }

        result = search_albums_by_title('Test', page=2)

        mock_search.assert_called_once_with('Test', page=2, per_page=20)
        assert result['has_more'] is True
        assert result['next_page'] == 3

    @patch('pipeline.scraper.discogs_search_albums')
    def test_returns_none_on_exception(self, mock_search):
        """Returns None on API exception."""
        mock_search.side_effect = Exception("API Error")

        result = search_albums_by_title('Test Album')

        assert result is None

    @patch('pipeline.scraper.discogs_search_albums')
    def test_empty_query_returns_none(self, mock_search):
        """Returns None for empty query."""
        result = search_albums_by_title('')

        assert result is None
        mock_search.assert_not_called()

    @patch('pipeline.scraper.discogs_search_albums')
    def test_whitespace_query_returns_none(self, mock_search):
        """Returns None for whitespace-only query."""
        result = search_albums_by_title('   ')

        assert result is None
        mock_search.assert_not_called()
