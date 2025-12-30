/**
 * Home page JavaScript - Two-step album selection flow
 */

document.addEventListener('DOMContentLoaded', function() {
    // Search form elements
    const searchForm = document.getElementById('search-form');
    const artistInput = document.getElementById('artist-name');
    const searchBtn = document.getElementById('search-btn');
    const searchBtnText = searchBtn.querySelector('.btn-text');
    const searchBtnLoading = searchBtn.querySelector('.btn-loading');
    const errorMessage = document.getElementById('error-message');

    // Album section elements
    const albumSection = document.getElementById('album-section');
    const artistDisplay = document.getElementById('artist-display');
    const albumGrid = document.getElementById('album-grid');

    // State
    let selectedAlbum = null;
    let currentArtist = null;
    let isAnalyzing = false;

    // Search form submission
    searchForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        const artistName = artistInput.value.trim();
        if (!artistName) {
            showError('Please enter an artist name');
            return;
        }

        setSearchLoading(true);
        hideError();
        hideAlbumSection();

        try {
            const response = await fetch(`/api/artists/search?q=${encodeURIComponent(artistName)}`);
            const data = await response.json();

            if (response.ok) {
                currentArtist = data;
                displayAlbums(data);
            } else {
                showError(data.error || 'Artist not found');
            }
        } catch (error) {
            console.error('Error:', error);
            showError('Network error. Please try again.');
        } finally {
            setSearchLoading(false);
        }
    });

    function displayAlbums(data) {
        artistDisplay.textContent = data.artist_name;
        albumGrid.innerHTML = '';
        selectedAlbum = null;

        if (!data.albums || data.albums.length === 0) {
            albumGrid.innerHTML = '<p class="no-albums">No albums found for this artist</p>';
            albumSection.classList.remove('hidden');
            return;
        }

        data.albums.forEach(album => {
            const albumCard = document.createElement('div');
            albumCard.className = 'album-card';
            albumCard.dataset.albumId = album.id;

            const coverUrl = album.cover_art_url || '/static/placeholder-album.png';
            const year = album.year || '';

            albumCard.innerHTML = `
                <div class="album-cover">
                    <img src="${coverUrl}" alt="${album.name}" onerror="this.src='/static/placeholder-album.png'">
                </div>
                <div class="album-info">
                    <h3 class="album-name">${album.name}</h3>
                    <span class="album-year">${year}</span>
                </div>
                <div class="album-action hidden">
                    <button class="analyze-album-btn">
                        <span class="btn-text">Analyze</span>
                        <span class="btn-loading hidden">
                            <span class="spinner"></span>
                        </span>
                    </button>
                </div>
            `;

            albumCard.addEventListener('click', (e) => {
                // Don't toggle selection if clicking the button itself
                if (e.target.closest('.analyze-album-btn')) return;
                selectAlbum(albumCard, album);
            });

            // Add click handler for the analyze button
            const analyzeBtn = albumCard.querySelector('.analyze-album-btn');
            analyzeBtn.addEventListener('click', () => analyzeAlbum(album, analyzeBtn));

            albumGrid.appendChild(albumCard);
        });

        albumSection.classList.remove('hidden');
    }

    function selectAlbum(card, album) {
        if (isAnalyzing) return;

        // Remove selection and hide button from all cards
        document.querySelectorAll('.album-card').forEach(c => {
            c.classList.remove('selected');
            c.querySelector('.album-action').classList.add('hidden');
        });

        // Select this card and show its button
        card.classList.add('selected');
        card.querySelector('.album-action').classList.remove('hidden');
        selectedAlbum = album;
    }

    async function analyzeAlbum(album, button) {
        if (isAnalyzing || !currentArtist) return;

        isAnalyzing = true;
        const btnText = button.querySelector('.btn-text');
        const btnLoading = button.querySelector('.btn-loading');

        button.disabled = true;
        btnText.classList.add('hidden');
        btnLoading.classList.remove('hidden');

        try {
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    artist_name: currentArtist.artist_name,
                    album_id: album.id,
                    album_name: album.name
                }),
            });

            const data = await response.json();

            if (response.ok) {
                window.location.href = `/results/${data.job_id}`;
            } else {
                showError(data.error || 'Failed to start analysis');
                resetAnalyzeButton(button);
            }
        } catch (error) {
            console.error('Error:', error);
            showError('Network error. Please try again.');
            resetAnalyzeButton(button);
        }
    }

    function resetAnalyzeButton(button) {
        isAnalyzing = false;
        button.disabled = false;
        button.querySelector('.btn-text').classList.remove('hidden');
        button.querySelector('.btn-loading').classList.add('hidden');
    }

    function setSearchLoading(loading) {
        searchBtn.disabled = loading;
        artistInput.disabled = loading;

        if (loading) {
            searchBtnText.classList.add('hidden');
            searchBtnLoading.classList.remove('hidden');
        } else {
            searchBtnText.classList.remove('hidden');
            searchBtnLoading.classList.add('hidden');
        }
    }

    function hideAlbumSection() {
        albumSection.classList.add('hidden');
        selectedAlbum = null;
    }

    function showError(message) {
        errorMessage.textContent = message;
        errorMessage.classList.remove('hidden');
    }

    function hideError() {
        errorMessage.classList.add('hidden');
    }
});
