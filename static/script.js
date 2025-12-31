/**
 * Home page JavaScript - Two-step album selection flow with infinite scroll
 */

document.addEventListener("DOMContentLoaded", function () {
  // Tab elements
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabPanels = document.querySelectorAll(".tab-panel");

  // Artist search form elements
  const searchForm = document.getElementById("search-form");
  const artistInput = document.getElementById("artist-name");
  const searchBtn = document.getElementById("search-btn");
  const searchBtnText = searchBtn.querySelector(".btn-text");
  const searchBtnLoading = searchBtn.querySelector(".btn-loading");
  const errorMessage = document.getElementById("error-message");

  // Album search form elements
  const albumSearchForm = document.getElementById("album-search-form");
  const albumQueryInput = document.getElementById("album-query");
  const albumSearchBtn = document.getElementById("album-search-btn");
  const albumSearchBtnText = albumSearchBtn.querySelector(".btn-text");
  const albumSearchBtnLoading = albumSearchBtn.querySelector(".btn-loading");

  // Album search results elements
  const albumSearchResultsSection = document.getElementById("album-search-results");
  const albumSearchQueryDisplay = document.getElementById("album-search-query");
  const albumSearchGrid = document.getElementById("album-search-grid");

  // Loading section elements
  const loadingSection = document.getElementById("loading-section");
  const loadingStatus = document.getElementById("loading-status");
  const loadingFunFact = document.getElementById("loading-fun-fact");

  // Album section elements
  const albumSection = document.getElementById("album-section");
  const artistDisplay = document.getElementById("artist-display");
  const albumGrid = document.getElementById("album-grid");

  // Compare mode elements
  const compareBanner = document.getElementById("compare-banner");
  const compareAlbumName = document.getElementById("compare-album-name");
  const cancelCompareBtn = document.getElementById("cancel-compare");

  // Analysis progress elements (for compare mode)
  const analysisSection = document.getElementById("analysis-section");
  const analysisStatusText = document.getElementById("analysis-status-text");
  const analysisProgressFill = document.getElementById("analysis-progress-fill");
  const analysisProgressPercent = document.getElementById("analysis-progress-percent");
  const analysisFunFact = document.getElementById("analysis-fun-fact");

  // State
  let selectedAlbum = null;
  let currentArtist = null;
  let currentArtistId = null;
  let currentArtistName = null;
  let isAnalyzing = false;
  let isCompareMode = false;
  let compareAlbumA = null;

  // Pagination state (artist search)
  let currentPage = 1;
  let hasMore = false;
  let isLoadingMore = false;
  let totalAlbums = 0;
  let albumIndex = 0; // For playlist numbering

  // Album search state
  let currentSearchMode = 'artist';
  let albumSearchQuery = '';
  let albumSearchPage = 1;
  let albumSearchHasMore = false;
  let albumSearchIsLoading = false;
  let albumSearchIndex = 0;

  // Fun facts interval
  let funFactInterval = null;
  let analysisPollInterval = null;
  let analysisFunFactInterval = null;

  // Check for compare mode on load
  initCompareMode();

  // Tab switching
  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetTab = btn.dataset.tab;
      switchTab(targetTab);
    });
  });

  function switchTab(tab) {
    currentSearchMode = tab;

    // Update tab buttons
    tabBtns.forEach(btn => {
      btn.classList.toggle("active", btn.dataset.tab === tab);
    });

    // Update tab panels
    tabPanels.forEach(panel => {
      panel.classList.toggle("active", panel.id === `${tab}-tab`);
    });

    // Hide results sections when switching tabs
    hideError();
    albumSection.classList.add("hidden");
    albumSearchResultsSection.classList.add("hidden");
    loadingSection.classList.add("hidden");
  }

  // Album search form submission
  albumSearchForm.addEventListener("submit", async function (e) {
    e.preventDefault();

    const query = albumQueryInput.value.trim();
    if (!query) {
      showError("Please enter an album title");
      return;
    }

    // Reset album search state
    albumSearchQuery = query;
    albumSearchPage = 1;
    albumSearchHasMore = false;
    albumSearchIndex = 0;

    setAlbumSearchLoading(true);
    hideError();
    hideAlbumSection();
    albumSearchResultsSection.classList.add("hidden");
    showLoadingSection(query);

    try {
      const response = await fetch(
        `/api/albums/search?q=${encodeURIComponent(query)}&page=1`
      );
      const data = await response.json();

      hideLoadingSection();

      if (response.ok) {
        albumSearchHasMore = data.has_more;
        albumSearchPage = data.next_page || 2;
        displayAlbumSearchResults(data, query, false);
      } else {
        showError(data.error || "No albums found");
      }
    } catch (error) {
      console.error("Error:", error);
      hideLoadingSection();
      showError("Network error. Please try again.");
    } finally {
      setAlbumSearchLoading(false);
    }
  });

  // Infinite scroll for album search results
  albumSearchGrid.addEventListener("scroll", async function () {
    if (!albumSearchHasMore || albumSearchIsLoading) return;

    const scrollTop = albumSearchGrid.scrollTop;
    const scrollHeight = albumSearchGrid.scrollHeight;
    const clientHeight = albumSearchGrid.clientHeight;

    if (scrollTop + clientHeight >= scrollHeight - 100) {
      await loadMoreAlbumSearchResults();
    }
  });

  async function loadMoreAlbumSearchResults() {
    if (albumSearchIsLoading || !albumSearchHasMore) return;

    albumSearchIsLoading = true;
    showAlbumSearchLoadingIndicator();

    try {
      const response = await fetch(
        `/api/albums/search?q=${encodeURIComponent(albumSearchQuery)}&page=${albumSearchPage}`
      );
      const data = await response.json();

      if (response.ok) {
        albumSearchHasMore = data.has_more;
        albumSearchPage = data.next_page || albumSearchPage + 1;
        appendAlbumSearchResults(data.albums);
        updateAlbumSearchCount();
      }
    } catch (error) {
      console.error("Error loading more albums:", error);
    } finally {
      albumSearchIsLoading = false;
      hideAlbumSearchLoadingIndicator();
    }
  }

  function displayAlbumSearchResults(data, query, append = false) {
    albumSearchQueryDisplay.textContent = query;

    if (!append) {
      albumSearchGrid.innerHTML = "";
      albumSearchIndex = 0;
    }

    if (!data.albums || data.albums.length === 0) {
      if (!append) {
        albumSearchGrid.innerHTML =
          '<p class="no-albums">No albums found matching this title</p>';
      }
      albumSearchResultsSection.classList.remove("hidden");
      return;
    }

    appendAlbumSearchResults(data.albums);
    updateAlbumSearchCount();
    albumSearchResultsSection.classList.remove("hidden");
  }

  function appendAlbumSearchResults(albums) {
    albums.forEach((album) => {
      albumSearchIndex++;
      const albumItem = document.createElement("div");
      albumItem.className = "album-item";
      albumItem.dataset.albumId = album.id;
      albumItem.dataset.artistName = album.artist;

      const year = album.year || "";
      const yearDisplay = year ? `(${year})` : "";

      albumItem.innerHTML = `
        <span class="album-index">${albumSearchIndex}.</span>
        <div class="album-info">
          <span class="album-name">${album.name}</span>
          <span class="album-artist">${album.artist}</span>
          <span class="album-year">${yearDisplay}</span>
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

      albumItem.addEventListener("click", (e) => {
        if (e.target.closest(".analyze-album-btn")) return;
        selectAlbumFromSearch(albumItem, album);
      });

      const analyzeBtn = albumItem.querySelector(".analyze-album-btn");
      analyzeBtn.addEventListener("click", () =>
        analyzeAlbumFromSearch(album, analyzeBtn)
      );

      albumSearchGrid.appendChild(albumItem);
    });
  }

  function selectAlbumFromSearch(item, album) {
    if (isAnalyzing) return;

    document.querySelectorAll("#album-search-grid .album-item").forEach((el) => {
      el.classList.remove("selected");
      el.querySelector(".album-action").classList.add("hidden");
    });

    item.classList.add("selected");
    item.querySelector(".album-action").classList.remove("hidden");
  }

  async function analyzeAlbumFromSearch(album, button) {
    if (isAnalyzing) return;

    isAnalyzing = true;
    const btnText = button.querySelector(".btn-text");
    const btnLoading = button.querySelector(".btn-loading");

    button.disabled = true;
    btnText.classList.add("hidden");
    btnLoading.classList.remove("hidden");

    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          artist_name: album.artist,
          album_id: album.id,
          album_name: album.name,
        }),
      });

      const data = await response.json();

      if (response.ok) {
        if (isCompareMode && compareAlbumA) {
          showAnalysisProgress(data.job_id);
        } else {
          window.location.href = `/results/${data.job_id}`;
        }
      } else {
        showError(data.error || "Failed to start analysis");
        resetAnalyzeButton(button);
      }
    } catch (error) {
      console.error("Error:", error);
      showError("Network error. Please try again.");
      resetAnalyzeButton(button);
    }
  }

  function updateAlbumSearchCount() {
    let notice = albumSearchResultsSection.querySelector(".album-limit-notice");
    if (!notice) {
      notice = document.createElement("p");
      notice.className = "album-limit-notice";
      albumSearchResultsSection.appendChild(notice);
    }

    const loadedCount = albumSearchGrid.querySelectorAll(".album-item").length;
    if (albumSearchHasMore) {
      notice.textContent = `${loadedCount} albums loaded (scroll for more)`;
    } else {
      notice.textContent = `${loadedCount} albums`;
    }
  }

  function showAlbumSearchLoadingIndicator() {
    let loader = document.getElementById("album-search-load-more-indicator");
    if (!loader) {
      loader = document.createElement("div");
      loader.id = "album-search-load-more-indicator";
      loader.className = "load-more-indicator";
      loader.innerHTML = '<span class="spinner"></span> Loading more albums...';
      albumSearchResultsSection.appendChild(loader);
    }
    loader.classList.remove("hidden");
  }

  function hideAlbumSearchLoadingIndicator() {
    const loader = document.getElementById("album-search-load-more-indicator");
    if (loader) {
      loader.classList.add("hidden");
    }
  }

  function setAlbumSearchLoading(loading) {
    albumSearchBtn.disabled = loading;
    albumQueryInput.disabled = loading;

    if (loading) {
      albumSearchBtnText.classList.add("hidden");
      albumSearchBtnLoading.classList.remove("hidden");
    } else {
      albumSearchBtnText.classList.remove("hidden");
      albumSearchBtnLoading.classList.add("hidden");
    }
  }

  // Fun facts about lyrics and music
  const funFacts = [
    "The word 'love' is the most common word in song lyrics across all genres.",
    "Hip-hop lyrics contain the largest vocabulary of any music genre.",
    "The Beatles wrote over 300 songs, making them one of the most analyzed artists in music history.",
    "Song lyrics have become more repetitive over the past 50 years, according to research.",
    "Eminem holds the record for most words in a hit single with 'Rap God' at 1,560 words.",
    "Country music lyrics mention trucks, beer, and rain more than any other genre.",
    "Taylor Swift's lyrics have been studied by linguists for their narrative complexity.",
    "The word 'baby' appears in over 25% of all Billboard Hot 100 songs.",
    "Bob Dylan won the Nobel Prize in Literature partly for his lyrical compositions.",
    "The average hit song has a reading level of about 3rd grade.",
    "K-pop lyrics often mix Korean, English, and Japanese in a single song.",
    "Spotify uses NLP to analyze lyrics for mood-based playlist recommendations.",
    "Queen's 'Bohemian Rhapsody' contains over 900 individual vocal overdubs.",
    "The Beatles used the word 'love' 613 times across their discography.",
    "Daft Punk's 'Around the World' repeats the title phrase exactly 144 times.",
    "Prince wrote over 500 songs that were never released during his lifetime.",
    "The most common rhyme scheme in pop music is ABAB.",
    "Songs in minor keys are perceived as sadder regardless of lyrical content.",
    "Finnish has produced more metal bands per capita than any other country.",
    "Radiohead's lyrics are considered some of the most linguistically complex in rock music.",
  ];

  // Search form submission
  searchForm.addEventListener("submit", async function (e) {
    e.preventDefault();

    const artistName = artistInput.value.trim();
    if (!artistName) {
      showError("Please enter an artist name");
      return;
    }

    // Reset pagination state
    currentPage = 1;
    hasMore = false;
    currentArtistId = null;
    currentArtistName = null;

    setSearchLoading(true);
    hideError();
    hideAlbumSection();
    showLoadingSection(artistName);

    try {
      const response = await fetch(
        `/api/artists/search?q=${encodeURIComponent(artistName)}&page=1`
      );
      const data = await response.json();

      hideLoadingSection();

      if (response.ok) {
        currentArtist = data;
        currentArtistId = data.artist_id;
        currentArtistName = data.artist_name;
        hasMore = data.has_more;
        currentPage = data.next_page || 2;
        displayAlbums(data, false);
      } else {
        showError(data.error || "Artist not found");
      }
    } catch (error) {
      console.error("Error:", error);
      hideLoadingSection();
      showError("Network error. Please try again.");
    } finally {
      setSearchLoading(false);
    }
  });

  // Infinite scroll handler - on the album list container
  albumGrid.addEventListener("scroll", async function () {
    if (!hasMore || isLoadingMore || !currentArtistId) return;

    // Check if near bottom of scrollable container
    const scrollTop = albumGrid.scrollTop;
    const scrollHeight = albumGrid.scrollHeight;
    const clientHeight = albumGrid.clientHeight;

    if (scrollTop + clientHeight >= scrollHeight - 100) {
      await loadMoreAlbums();
    }
  });

  async function loadMoreAlbums() {
    if (isLoadingMore || !hasMore || !currentArtistId) return;

    isLoadingMore = true;

    // Show loading indicator
    showLoadingIndicator();

    try {
      // Use artist ID endpoint for faster pagination (no re-search)
      const url = `/api/artists/${currentArtistId}/albums?page=${currentPage}&artist_name=${encodeURIComponent(
        currentArtistName
      )}`;
      const response = await fetch(url);
      const data = await response.json();

      if (response.ok) {
        hasMore = data.has_more;
        currentPage = data.next_page || currentPage + 1;
        appendAlbums(data.albums);
        updateAlbumCount();
      }
    } catch (error) {
      console.error("Error loading more albums:", error);
    } finally {
      isLoadingMore = false;
      hideLoadingIndicator();
    }
  }

  function displayAlbums(data, append = false) {
    artistDisplay.textContent = data.artist_name;

    if (!append) {
      albumGrid.innerHTML = "";
      selectedAlbum = null;
      albumIndex = 0;
    }

    if (!data.albums || data.albums.length === 0) {
      if (!append) {
        albumGrid.innerHTML =
          '<p class="no-albums">No albums found for this artist</p>';
      }
      albumSection.classList.remove("hidden");
      return;
    }

    appendAlbums(data.albums);
    updateAlbumCount();
    albumSection.classList.remove("hidden");
  }

  function appendAlbums(albums) {
    albums.forEach((album) => {
      albumIndex++;
      const albumItem = document.createElement("div");
      albumItem.className = "album-item";
      albumItem.dataset.albumId = album.id;

      const year = album.year || "";
      const yearDisplay = year ? `(${year})` : "";

      albumItem.innerHTML = `
        <span class="album-index">${albumIndex}.</span>
        <div class="album-info">
          <span class="album-name">${album.name}</span>
          <span class="album-year">${yearDisplay}</span>
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

      albumItem.addEventListener("click", (e) => {
        // Don't toggle selection if clicking the button itself
        if (e.target.closest(".analyze-album-btn")) return;
        selectAlbum(albumItem, album);
      });

      // Add click handler for the analyze button
      const analyzeBtn = albumItem.querySelector(".analyze-album-btn");
      analyzeBtn.addEventListener("click", () =>
        analyzeAlbum(album, analyzeBtn)
      );

      albumGrid.appendChild(albumItem);
    });
  }

  function updateAlbumCount() {
    // Create or get the notice element
    let notice = document.querySelector(".album-limit-notice");
    if (!notice) {
      notice = document.createElement("p");
      notice.className = "album-limit-notice";
      albumSection.appendChild(notice);
    }

    const loadedCount = albumGrid.querySelectorAll(".album-item").length;
    if (hasMore) {
      notice.textContent = `${loadedCount} releases loaded (scroll for more)`;
    } else {
      notice.textContent = `${loadedCount} releases`;
    }
  }

  function showLoadingIndicator() {
    let loader = document.getElementById("load-more-indicator");
    if (!loader) {
      loader = document.createElement("div");
      loader.id = "load-more-indicator";
      loader.className = "load-more-indicator";
      loader.innerHTML = '<span class="spinner"></span> Loading more albums...';
      albumSection.appendChild(loader);
    }
    loader.classList.remove("hidden");
  }

  function hideLoadingIndicator() {
    const loader = document.getElementById("load-more-indicator");
    if (loader) {
      loader.classList.add("hidden");
    }
  }

  function selectAlbum(item, album) {
    if (isAnalyzing) return;

    // Remove selection and hide button from all items
    document.querySelectorAll(".album-item").forEach((el) => {
      el.classList.remove("selected");
      el.querySelector(".album-action").classList.add("hidden");
    });

    // Select this item and show its button
    item.classList.add("selected");
    item.querySelector(".album-action").classList.remove("hidden");
    selectedAlbum = album;
  }

  async function analyzeAlbum(album, button) {
    if (isAnalyzing || !currentArtist) return;

    isAnalyzing = true;
    const btnText = button.querySelector(".btn-text");
    const btnLoading = button.querySelector(".btn-loading");

    button.disabled = true;
    btnText.classList.add("hidden");
    btnLoading.classList.remove("hidden");

    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          artist_name: currentArtist.artist_name,
          album_id: album.id,
          album_name: album.name,
        }),
      });

      const data = await response.json();

      if (response.ok) {
        if (isCompareMode && compareAlbumA) {
          // Show progress UI on this page for compare mode
          showAnalysisProgress(data.job_id);
        } else {
          // Normal mode - redirect to results page
          window.location.href = `/results/${data.job_id}`;
        }
      } else {
        showError(data.error || "Failed to start analysis");
        resetAnalyzeButton(button);
      }
    } catch (error) {
      console.error("Error:", error);
      showError("Network error. Please try again.");
      resetAnalyzeButton(button);
    }
  }

  // Analysis progress for compare mode
  function showAnalysisProgress(jobId) {
    // Hide other sections
    albumSection.classList.add("hidden");
    albumSearchResultsSection.classList.add("hidden");
    compareBanner.classList.add("hidden");

    // Show analysis section
    analysisSection.classList.remove("hidden");

    // Start fun facts rotation
    showAnalysisFunFact();
    analysisFunFactInterval = setInterval(showAnalysisFunFact, 10000);

    // Start polling for status
    pollAnalysisStatus(jobId);
    analysisPollInterval = setInterval(() => pollAnalysisStatus(jobId), 2000);
  }

  async function pollAnalysisStatus(jobId) {
    try {
      const response = await fetch(`/api/analyze/${jobId}`);
      const data = await response.json();

      if (data.status === "completed") {
        clearInterval(analysisPollInterval);
        clearInterval(analysisFunFactInterval);
        updateAnalysisProgress(data.total_stages, data.total_stages);
        updateAnalysisSteps(data.total_stages);

        // Redirect to compare page
        setTimeout(() => {
          localStorage.removeItem("compareAlbumA");
          window.location.href = `/compare?a=${compareAlbumA.job_id}&b=${jobId}`;
        }, 500);
      } else if (data.status === "failed") {
        clearInterval(analysisPollInterval);
        clearInterval(analysisFunFactInterval);
        analysisSection.classList.add("hidden");
        showError(data.error || "Analysis failed");
      } else {
        // Still processing
        analysisStatusText.textContent = data.progress || "Processing...";
        updateAnalysisProgress(data.stage || 0, data.total_stages || 6, data.sub_current, data.sub_total);
        updateAnalysisSteps(data.stage || 0);
      }
    } catch (error) {
      console.error("Error polling status:", error);
    }
  }

  function updateAnalysisProgress(stage, totalStages, subCurrent, subTotal) {
    const stageProgress = (stage - 1) / totalStages;
    let subProgress = 0;
    if (subCurrent && subTotal && subTotal > 0) {
      subProgress = (subCurrent / subTotal) / totalStages;
    }
    const percent = Math.round(Math.max(0, (stageProgress + subProgress)) * 100);
    analysisProgressFill.style.width = `${percent}%`;
    analysisProgressPercent.textContent = `${percent}%`;
  }

  function updateAnalysisSteps(currentStage) {
    const steps = analysisSection.querySelectorAll(".step");
    steps.forEach((step) => {
      const stepNum = parseInt(step.dataset.step);
      const iconEl = step.querySelector(".step-icon");

      step.classList.remove("completed", "active", "pending");

      if (stepNum < currentStage) {
        step.classList.add("completed");
        iconEl.textContent = "✓";
      } else if (stepNum === currentStage) {
        step.classList.add("active");
        iconEl.textContent = "●";
      } else {
        step.classList.add("pending");
        iconEl.textContent = "○";
      }
    });

    const connectors = analysisSection.querySelectorAll(".step-connector");
    connectors.forEach((connector, index) => {
      connector.classList.remove("completed");
      if (index + 1 < currentStage) {
        connector.classList.add("completed");
      }
    });
  }

  function showAnalysisFunFact() {
    analysisFunFact.classList.remove("fade-in");
    void analysisFunFact.offsetWidth;
    const randomIndex = Math.floor(Math.random() * funFacts.length);
    analysisFunFact.textContent = funFacts[randomIndex];
    analysisFunFact.classList.add("fade-in");
  }

  function resetAnalyzeButton(button) {
    isAnalyzing = false;
    button.disabled = false;
    button.querySelector(".btn-text").classList.remove("hidden");
    button.querySelector(".btn-loading").classList.add("hidden");
  }

  function setSearchLoading(loading) {
    searchBtn.disabled = loading;
    artistInput.disabled = loading;

    if (loading) {
      searchBtnText.classList.add("hidden");
      searchBtnLoading.classList.remove("hidden");
    } else {
      searchBtnText.classList.remove("hidden");
      searchBtnLoading.classList.add("hidden");
    }
  }

  function hideAlbumSection() {
    albumSection.classList.add("hidden");
    selectedAlbum = null;
  }

  function showError(message) {
    errorMessage.textContent = message;
    errorMessage.classList.remove("hidden");
  }

  function hideError() {
    errorMessage.classList.add("hidden");
  }

  function showLoadingSection(artistName) {
    loadingSection.classList.remove("hidden");
    loadingStatus.textContent = `Searching for "${artistName}"...`;

    // Show initial fun fact
    showFunFact();

    // Rotate fun facts every 4 seconds
    funFactInterval = setInterval(showFunFact, 4000);
  }

  function hideLoadingSection() {
    loadingSection.classList.add("hidden");

    // Clear fun fact rotation
    if (funFactInterval) {
      clearInterval(funFactInterval);
      funFactInterval = null;
    }
  }

  function showFunFact() {
    loadingFunFact.classList.remove("fade-in");
    void loadingFunFact.offsetWidth; // Trigger reflow for animation restart
    const randomIndex = Math.floor(Math.random() * funFacts.length);
    loadingFunFact.textContent = funFacts[randomIndex];
    loadingFunFact.classList.add("fade-in");
  }

  // Compare mode functions
  function initCompareMode() {
    const urlParams = new URLSearchParams(window.location.search);
    const compareParam = urlParams.get("compare");

    // Check if we have a stored album for comparison
    const storedAlbum = localStorage.getItem("compareAlbumA");

    if (compareParam === "true" && storedAlbum) {
      try {
        compareAlbumA = JSON.parse(storedAlbum);
        isCompareMode = true;
        showCompareBanner();
      } catch (e) {
        // Invalid stored data, clear it
        localStorage.removeItem("compareAlbumA");
      }
    }

    // Set up cancel button
    if (cancelCompareBtn) {
      cancelCompareBtn.addEventListener("click", cancelCompareMode);
    }
  }

  function showCompareBanner() {
    if (!compareBanner || !compareAlbumA) return;

    const displayName = `${compareAlbumA.album} - ${compareAlbumA.artist}`;
    compareAlbumName.textContent = displayName;
    compareBanner.classList.remove("hidden");
  }

  function cancelCompareMode() {
    isCompareMode = false;
    compareAlbumA = null;
    localStorage.removeItem("compareAlbumA");
    compareBanner.classList.add("hidden");

    // Remove compare param from URL
    const url = new URL(window.location);
    url.searchParams.delete("compare");
    window.history.replaceState({}, "", url);
  }
});
