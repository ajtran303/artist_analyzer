"""Unit tests for Discogs API client."""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
import requests

from pipeline.discogs_client import (
    clean_artist_name,
    search_artist,
    get_artist_albums,
    get_release_tracks,
    get_release_info,
    search_albums,
    DiscogsError,
    _get_client,
    _check_rate_limit,
    _track_discogs_call
)


@pytest.mark.unit
class TestCleanArtistName:
    """Tests for clean_artist_name function."""

    def test_removes_disambiguation_number(self):
        """Removes (number) suffix from artist names."""
        assert clean_artist_name('Will Wood (7)') == 'Will Wood'

    def test_handles_single_digit(self):
        """Handles single digit disambiguation."""
        assert clean_artist_name('Artist (1)') == 'Artist'

    def test_handles_multiple_digits(self):
        """Handles multi-digit disambiguation."""
        assert clean_artist_name('The National (23)') == 'The National'

    def test_preserves_name_without_number(self):
        """Preserves names without disambiguation."""
        assert clean_artist_name('Radiohead') == 'Radiohead'

    def test_preserves_parentheses_without_number(self):
        """Preserves parentheses that don't contain only numbers."""
        assert clean_artist_name('Sunn O)))') == 'Sunn O)))'

    def test_handles_none(self):
        """Returns None for None input."""
        assert clean_artist_name(None) is None

    def test_handles_empty_string(self):
        """Returns empty string for empty input."""
        assert clean_artist_name('') == ''

    def test_strips_whitespace(self):
        """Strips extra whitespace."""
        assert clean_artist_name('Artist  (5)  ') == 'Artist'

    def test_preserves_other_parenthetical_info(self):
        """Preserves non-disambiguation parenthetical info."""
        result = clean_artist_name('Artist (UK)')
        assert result == 'Artist (UK)'


@pytest.mark.unit
class TestDiscogsError:
    """Tests for DiscogsError exception."""

    def test_is_exception(self):
        """DiscogsError is an Exception subclass."""
        assert issubclass(DiscogsError, Exception)

    def test_can_be_raised(self):
        """DiscogsError can be raised with message."""
        with pytest.raises(DiscogsError) as exc_info:
            raise DiscogsError('Test error')
        assert 'Test error' in str(exc_info.value)


@pytest.mark.unit
class TestGetClient:
    """Tests for _get_client function."""

    def test_raises_without_token(self):
        """Raises DiscogsError when token not set."""
        with patch('pipeline.discogs_client.DISCOGS_TOKEN', ''):
            with pytest.raises(DiscogsError) as exc_info:
                _get_client()
            assert 'DISCOGS_API_TOKEN' in str(exc_info.value)

    def test_returns_client_with_token(self):
        """Returns client when token is set."""
        with patch('pipeline.discogs_client.DISCOGS_TOKEN', 'test-token'):
            with patch('pipeline.discogs_client.discogs_client.Client') as mock_client:
                mock_instance = MagicMock()
                mock_instance._fetcher = MagicMock()
                mock_client.return_value = mock_instance

                client = _get_client()

                mock_client.assert_called_once()
                assert client == mock_instance


@pytest.mark.unit
class TestCheckRateLimit:
    """Tests for _check_rate_limit function."""

    def test_allows_when_under_limit(self):
        """No action when under rate limit."""
        mock_metrics = MagicMock()
        mock_metrics.check_limit.return_value = (True, 0)

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_metrics):
            # Should not raise
            _check_rate_limit()

    def test_waits_when_short_limit(self):
        """Waits when rate limit reached but reset is soon."""
        mock_metrics = MagicMock()
        mock_metrics.check_limit.return_value = (False, 5)

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_metrics):
            with patch('pipeline.discogs_client.time.sleep') as mock_sleep:
                _check_rate_limit()
                mock_sleep.assert_called_once_with(5)

    def test_raises_when_long_wait(self):
        """Raises DiscogsError when wait time too long."""
        mock_metrics = MagicMock()
        mock_metrics.check_limit.return_value = (False, 120)

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_metrics):
            with pytest.raises(DiscogsError) as exc_info:
                _check_rate_limit()
            assert 'rate limit exceeded' in str(exc_info.value)


@pytest.mark.unit
class TestTrackDiscogsCall:
    """Tests for _track_discogs_call function."""

    def test_tracks_successful_call(self):
        """Tracks successful API call."""
        mock_metrics = MagicMock()

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_metrics):
            _track_discogs_call(success=True)
            mock_metrics.track_call.assert_called_once_with('discogs', success=True)

    def test_tracks_failed_call(self):
        """Tracks failed API call."""
        mock_metrics = MagicMock()

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_metrics):
            _track_discogs_call(success=False)
            mock_metrics.track_call.assert_called_once_with('discogs', success=False)


@pytest.mark.unit
class TestSearchArtist:
    """Tests for search_artist function."""

    @pytest.fixture
    def mock_discogs_setup(self):
        """Setup common mocks for Discogs API."""
        mock_metrics = MagicMock()
        mock_metrics.check_limit.return_value = (True, 0)
        return mock_metrics

    def test_returns_artist_id_and_name(self, mock_discogs_setup):
        """Returns tuple of (artist_id, artist_name)."""
        mock_artist = MagicMock()
        mock_artist.id = 12345
        mock_artist.name = 'Test Artist'

        mock_client = MagicMock()
        mock_client.search.return_value = [mock_artist]

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_discogs_setup):
            with patch('pipeline.discogs_client._get_client', return_value=mock_client):
                artist_id, artist_name = search_artist('Test Artist')

        assert artist_id == 12345
        assert artist_name == 'Test Artist'

    def test_cleans_disambiguation_from_name(self, mock_discogs_setup):
        """Cleans disambiguation number from returned name."""
        mock_artist = MagicMock()
        mock_artist.id = 12345
        mock_artist.name = 'Will Wood (7)'

        mock_client = MagicMock()
        mock_client.search.return_value = [mock_artist]

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_discogs_setup):
            with patch('pipeline.discogs_client._get_client', return_value=mock_client):
                artist_id, artist_name = search_artist('Will Wood')

        assert artist_name == 'Will Wood'

    def test_returns_none_when_not_found(self, mock_discogs_setup):
        """Returns (None, None) when artist not found."""
        mock_client = MagicMock()
        mock_client.search.return_value = []

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_discogs_setup):
            with patch('pipeline.discogs_client._get_client', return_value=mock_client):
                artist_id, artist_name = search_artist('Nonexistent Artist')

        assert artist_id is None
        assert artist_name is None

    def test_returns_none_on_exception(self, mock_discogs_setup):
        """Returns (None, None) on API exception."""
        mock_client = MagicMock()
        mock_client.search.side_effect = Exception('API error')

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_discogs_setup):
            with patch('pipeline.discogs_client._get_client', return_value=mock_client):
                artist_id, artist_name = search_artist('Test Artist')

        assert artist_id is None
        assert artist_name is None

    def test_reraises_discogs_error(self, mock_discogs_setup):
        """Re-raises DiscogsError."""
        with patch('pipeline.api_metrics.get_metrics', return_value=mock_discogs_setup):
            with patch('pipeline.discogs_client._get_client', side_effect=DiscogsError('Token missing')):
                with pytest.raises(DiscogsError):
                    search_artist('Test Artist')


@pytest.mark.unit
class TestGetArtistAlbums:
    """Tests for get_artist_albums function."""

    @pytest.fixture
    def mock_discogs_setup(self):
        """Setup common mocks."""
        mock_metrics = MagicMock()
        mock_metrics.check_limit.return_value = (True, 0)
        return mock_metrics

    def test_returns_albums_list(self, mock_discogs_setup):
        """Returns dict with albums list."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'releases': [
                {'id': 1, 'title': 'Album 1', 'year': 2020, 'type': 'master', 'role': 'Main'},
                {'id': 2, 'title': 'Album 2', 'year': 2021, 'type': 'master', 'role': 'Main'},
            ],
            'pagination': {'pages': 1, 'page': 1}
        }

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_discogs_setup):
            with patch('pipeline.discogs_client.requests.get', return_value=mock_response):
                with patch('pipeline.discogs_client.DISCOGS_TOKEN', 'test-token'):
                    result = get_artist_albums(12345)

        assert 'albums' in result
        assert len(result['albums']) == 2
        assert result['albums'][0]['name'] == 'Album 1'

    def test_filters_non_master_releases(self, mock_discogs_setup):
        """Filters out non-master releases."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'releases': [
                {'id': 1, 'title': 'Master Album', 'year': 2020, 'type': 'master', 'role': 'Main'},
                {'id': 2, 'title': 'Single', 'year': 2020, 'type': 'release', 'role': 'Main'},
            ],
            'pagination': {'pages': 1}
        }

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_discogs_setup):
            with patch('pipeline.discogs_client.requests.get', return_value=mock_response):
                with patch('pipeline.discogs_client.DISCOGS_TOKEN', 'test-token'):
                    result = get_artist_albums(12345)

        assert len(result['albums']) == 1
        assert result['albums'][0]['name'] == 'Master Album'

    def test_filters_non_main_role(self, mock_discogs_setup):
        """Filters out releases where artist is not main."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'releases': [
                {'id': 1, 'title': 'Main Album', 'year': 2020, 'type': 'master', 'role': 'Main'},
                {'id': 2, 'title': 'Featured Album', 'year': 2020, 'type': 'master', 'role': 'Appearance'},
            ],
            'pagination': {'pages': 1}
        }

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_discogs_setup):
            with patch('pipeline.discogs_client.requests.get', return_value=mock_response):
                with patch('pipeline.discogs_client.DISCOGS_TOKEN', 'test-token'):
                    result = get_artist_albums(12345)

        assert len(result['albums']) == 1
        assert result['albums'][0]['name'] == 'Main Album'

    def test_has_more_flag(self, mock_discogs_setup):
        """Returns has_more flag correctly."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'releases': [{'id': 1, 'title': 'Album', 'type': 'master', 'role': 'Main'}] * 20,
            'pagination': {'pages': 3, 'page': 1}
        }

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_discogs_setup):
            with patch('pipeline.discogs_client.requests.get', return_value=mock_response):
                with patch('pipeline.discogs_client.DISCOGS_TOKEN', 'test-token'):
                    result = get_artist_albums(12345, page=1)

        assert result['has_more'] is True

    def test_returns_empty_on_error(self, mock_discogs_setup):
        """Returns empty albums on error."""
        with patch('pipeline.api_metrics.get_metrics', return_value=mock_discogs_setup):
            with patch('pipeline.discogs_client.requests.get', side_effect=Exception('Network error')):
                with patch('pipeline.discogs_client.DISCOGS_TOKEN', 'test-token'):
                    result = get_artist_albums(12345)

        assert result['albums'] == []
        assert result['has_more'] is False


@pytest.mark.unit
class TestGetReleaseTracks:
    """Tests for get_release_tracks function."""

    @pytest.fixture
    def mock_discogs_setup(self):
        """Setup common mocks."""
        mock_metrics = MagicMock()
        mock_metrics.check_limit.return_value = (True, 0)
        return mock_metrics

    def test_returns_tracks_list(self, mock_discogs_setup):
        """Returns list of tracks."""
        mock_track1 = MagicMock()
        mock_track1.position = '1'
        mock_track1.title = 'Track 1'
        mock_track1.duration = '3:45'

        mock_track2 = MagicMock()
        mock_track2.position = '2'
        mock_track2.title = 'Track 2'
        mock_track2.duration = '4:20'

        mock_release = MagicMock()
        mock_release.tracklist = [mock_track1, mock_track2]

        mock_master = MagicMock()
        mock_master.main_release = mock_release

        mock_client = MagicMock()
        mock_client.master.return_value = mock_master

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_discogs_setup):
            with patch('pipeline.discogs_client._get_client', return_value=mock_client):
                tracks = get_release_tracks(12345, is_master=True)

        assert len(tracks) == 2
        assert tracks[0]['title'] == 'Track 1'
        assert tracks[0]['position'] == '1'

    def test_skips_tracks_without_position(self, mock_discogs_setup):
        """Skips tracks without position (like headings)."""
        mock_track1 = MagicMock()
        mock_track1.position = '1'
        mock_track1.title = 'Track 1'
        mock_track1.duration = '3:00'

        mock_heading = MagicMock()
        mock_heading.position = ''
        mock_heading.title = 'Side A'

        mock_release = MagicMock()
        mock_release.tracklist = [mock_heading, mock_track1]

        mock_master = MagicMock()
        mock_master.main_release = mock_release

        mock_client = MagicMock()
        mock_client.master.return_value = mock_master

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_discogs_setup):
            with patch('pipeline.discogs_client._get_client', return_value=mock_client):
                tracks = get_release_tracks(12345, is_master=True)

        assert len(tracks) == 1
        assert tracks[0]['title'] == 'Track 1'

    def test_handles_non_master_release(self, mock_discogs_setup):
        """Handles non-master release directly."""
        mock_track = MagicMock()
        mock_track.position = '1'
        mock_track.title = 'Track'
        mock_track.duration = '3:00'

        mock_release = MagicMock()
        mock_release.tracklist = [mock_track]

        mock_client = MagicMock()
        mock_client.release.return_value = mock_release

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_discogs_setup):
            with patch('pipeline.discogs_client._get_client', return_value=mock_client):
                tracks = get_release_tracks(12345, is_master=False)

        assert len(tracks) == 1
        mock_client.release.assert_called_once_with(12345)

    def test_returns_empty_on_error(self, mock_discogs_setup):
        """Returns empty list on error."""
        mock_client = MagicMock()
        mock_client.master.side_effect = Exception('API error')

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_discogs_setup):
            with patch('pipeline.discogs_client._get_client', return_value=mock_client):
                tracks = get_release_tracks(12345)

        assert tracks == []


@pytest.mark.unit
class TestGetReleaseInfo:
    """Tests for get_release_info function."""

    @pytest.fixture
    def mock_discogs_setup(self):
        """Setup common mocks."""
        mock_metrics = MagicMock()
        mock_metrics.check_limit.return_value = (True, 0)
        return mock_metrics

    def test_returns_release_info(self, mock_discogs_setup):
        """Returns dict with release info."""
        mock_artist = MagicMock()
        mock_artist.name = 'Test Artist'

        mock_master = MagicMock()
        mock_master.title = 'Test Album'
        mock_master.year = 2020
        mock_master.artists = [mock_artist]
        mock_master.genres = ['Rock', 'Alternative']
        mock_master.images = [{'uri': 'http://example.com/cover.jpg'}]

        mock_client = MagicMock()
        mock_client.master.return_value = mock_master

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_discogs_setup):
            with patch('pipeline.discogs_client._get_client', return_value=mock_client):
                info = get_release_info(12345, is_master=True)

        assert info['title'] == 'Test Album'
        assert info['year'] == 2020
        assert info['artist'] == 'Test Artist'
        assert 'Rock' in info['genres']

    def test_cleans_artist_name(self, mock_discogs_setup):
        """Cleans disambiguation from artist name."""
        mock_artist = MagicMock()
        mock_artist.name = 'Artist (5)'

        mock_master = MagicMock()
        mock_master.title = 'Album'
        mock_master.year = 2020
        mock_master.artists = [mock_artist]
        mock_master.genres = []
        mock_master.images = []

        mock_client = MagicMock()
        mock_client.master.return_value = mock_master

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_discogs_setup):
            with patch('pipeline.discogs_client._get_client', return_value=mock_client):
                info = get_release_info(12345)

        assert info['artist'] == 'Artist'

    def test_handles_missing_year(self, mock_discogs_setup):
        """Handles release without year."""
        mock_master = MagicMock(spec=['title', 'artists', 'genres', 'images'])
        mock_master.title = 'Album'
        mock_master.artists = []
        mock_master.genres = []
        mock_master.images = []

        mock_client = MagicMock()
        mock_client.master.return_value = mock_master

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_discogs_setup):
            with patch('pipeline.discogs_client._get_client', return_value=mock_client):
                info = get_release_info(12345)

        assert info['year'] is None

    def test_handles_non_master(self, mock_discogs_setup):
        """Handles non-master release."""
        mock_artist = MagicMock()
        mock_artist.name = 'Artist'

        mock_release = MagicMock()
        mock_release.title = 'Release'
        mock_release.year = 2021
        mock_release.artists = [mock_artist]
        mock_release.genres = []
        mock_release.images = []

        mock_client = MagicMock()
        mock_client.release.return_value = mock_release

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_discogs_setup):
            with patch('pipeline.discogs_client._get_client', return_value=mock_client):
                info = get_release_info(12345, is_master=False)

        assert info['title'] == 'Release'
        mock_client.release.assert_called_once_with(12345)

    def test_returns_none_on_error(self, mock_discogs_setup):
        """Returns None on error."""
        mock_client = MagicMock()
        mock_client.master.side_effect = Exception('API error')

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_discogs_setup):
            with patch('pipeline.discogs_client._get_client', return_value=mock_client):
                info = get_release_info(12345)

        assert info is None


@pytest.mark.unit
class TestSearchAlbums:
    """Tests for search_albums function."""

    @pytest.fixture
    def mock_discogs_setup(self):
        """Setup common mocks."""
        mock_metrics = MagicMock()
        mock_metrics.check_limit.return_value = (True, 0)
        return mock_metrics

    def test_returns_albums(self, mock_discogs_setup):
        """Returns list of albums."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'results': [
                {'id': 1, 'title': 'Artist - Album 1', 'year': 2020},
                {'id': 2, 'title': 'Artist - Album 2', 'year': 2021},
            ],
            'pagination': {'pages': 1, 'page': 1}
        }

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_discogs_setup):
            with patch('pipeline.discogs_client.requests.get', return_value=mock_response):
                with patch('pipeline.discogs_client.DISCOGS_TOKEN', 'test-token'):
                    result = search_albums('Test Query')

        assert 'albums' in result
        assert len(result['albums']) == 2

    def test_parses_artist_album_format(self, mock_discogs_setup):
        """Parses 'Artist - Album' format correctly."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'results': [
                {'id': 1, 'title': 'Radiohead - OK Computer', 'year': 1997},
            ],
            'pagination': {'pages': 1, 'page': 1}
        }

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_discogs_setup):
            with patch('pipeline.discogs_client.requests.get', return_value=mock_response):
                with patch('pipeline.discogs_client.DISCOGS_TOKEN', 'test-token'):
                    result = search_albums('OK Computer')

        assert result['albums'][0]['artist'] == 'Radiohead'
        assert result['albums'][0]['name'] == 'OK Computer'

    def test_cleans_artist_disambiguation(self, mock_discogs_setup):
        """Cleans disambiguation from artist name."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'results': [
                {'id': 1, 'title': 'Will Wood (7) - The Normal Album', 'year': 2020},
            ],
            'pagination': {'pages': 1, 'page': 1}
        }

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_discogs_setup):
            with patch('pipeline.discogs_client.requests.get', return_value=mock_response):
                with patch('pipeline.discogs_client.DISCOGS_TOKEN', 'test-token'):
                    result = search_albums('The Normal Album')

        assert result['albums'][0]['artist'] == 'Will Wood'

    def test_has_more_flag_when_more_pages(self, mock_discogs_setup):
        """Sets has_more when more pages exist."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'results': [{'id': 1, 'title': 'Album', 'year': 2020}],
            'pagination': {'pages': 5, 'page': 1}
        }

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_discogs_setup):
            with patch('pipeline.discogs_client.requests.get', return_value=mock_response):
                with patch('pipeline.discogs_client.DISCOGS_TOKEN', 'test-token'):
                    result = search_albums('Query')

        assert result['has_more'] is True
        assert result['next_page'] == 2

    def test_no_more_on_last_page(self, mock_discogs_setup):
        """Sets has_more False on last page."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'results': [{'id': 1, 'title': 'Album', 'year': 2020}],
            'pagination': {'pages': 1, 'page': 1}
        }

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_discogs_setup):
            with patch('pipeline.discogs_client.requests.get', return_value=mock_response):
                with patch('pipeline.discogs_client.DISCOGS_TOKEN', 'test-token'):
                    result = search_albums('Query')

        assert result['has_more'] is False
        assert result['next_page'] is None

    def test_handles_timeout(self, mock_discogs_setup):
        """Handles request timeout gracefully."""
        with patch('pipeline.api_metrics.get_metrics', return_value=mock_discogs_setup):
            with patch('pipeline.discogs_client.requests.get', side_effect=requests.Timeout('Timeout')):
                with patch('pipeline.discogs_client.DISCOGS_TOKEN', 'test-token'):
                    result = search_albums('Query')

        assert result['albums'] == []
        assert result['has_more'] is False

    def test_handles_generic_error(self, mock_discogs_setup):
        """Handles generic errors gracefully."""
        with patch('pipeline.api_metrics.get_metrics', return_value=mock_discogs_setup):
            with patch('pipeline.discogs_client.requests.get', side_effect=Exception('Error')):
                with patch('pipeline.discogs_client.DISCOGS_TOKEN', 'test-token'):
                    result = search_albums('Query')

        assert result['albums'] == []


@pytest.mark.unit
class TestDiscogsIntegration:
    """Integration tests for Discogs client functions."""

    def test_search_artist_tracks_call(self):
        """search_artist tracks API call."""
        mock_metrics = MagicMock()
        mock_metrics.check_limit.return_value = (True, 0)

        mock_artist = MagicMock()
        mock_artist.id = 1
        mock_artist.name = 'Artist'

        mock_client = MagicMock()
        mock_client.search.return_value = [mock_artist]

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_metrics):
            with patch('pipeline.discogs_client._get_client', return_value=mock_client):
                search_artist('Artist')

        mock_metrics.track_call.assert_called_with('discogs', success=True)

    def test_failed_search_tracks_failure(self):
        """Failed search tracks call as failure."""
        mock_metrics = MagicMock()
        mock_metrics.check_limit.return_value = (True, 0)

        mock_client = MagicMock()
        mock_client.search.side_effect = Exception('Error')

        with patch('pipeline.api_metrics.get_metrics', return_value=mock_metrics):
            with patch('pipeline.discogs_client._get_client', return_value=mock_client):
                search_artist('Artist')

        mock_metrics.track_call.assert_called_with('discogs', success=False)
