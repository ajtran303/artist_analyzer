"""Unit tests for scraper module."""

import pytest
from unittest.mock import patch, MagicMock

from pipeline.scraper import (
    search_artist_albums,
    scrape_album,
    _normalize_album_name,
    _extract_year_from_date,
    ScraperError
)


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
