/**
 * Compare page JavaScript
 */

document.addEventListener("DOMContentLoaded", async function () {
  const loadingSection = document.getElementById("loading-section");
  const errorSection = document.getElementById("error-section");
  const errorMessage = document.getElementById("error-message");
  const compareSection = document.getElementById("compare-section");

  // Validate job IDs
  if (!JOB_ID_A || !JOB_ID_B) {
    showError("Missing album IDs for comparison");
    return;
  }

  if (JOB_ID_A === JOB_ID_B) {
    showError("Cannot compare an album with itself");
    return;
  }

  // Set up accordion toggles
  setupAccordions();

  // Fetch comparison data
  try {
    const response = await fetch(`/api/compare?a=${JOB_ID_A}&b=${JOB_ID_B}`);
    const data = await response.json();

    if (!response.ok) {
      showError(data.error || "Failed to load comparison data");
      return;
    }

    loadingSection.classList.add("hidden");
    compareSection.classList.remove("hidden");

    renderComparison(data);
  } catch (error) {
    console.error("Error loading comparison:", error);
    showError("Network error. Please try again.");
  }

  function showError(message) {
    loadingSection.classList.add("hidden");
    errorSection.classList.remove("hidden");
    errorMessage.textContent = message;
  }

  function setupAccordions() {
    const headers = document.querySelectorAll(".accordion-header");
    headers.forEach((header) => {
      header.addEventListener("click", () => {
        const section = header.dataset.section;
        const content = document.getElementById(`${section}-section`);
        const icon = header.querySelector(".accordion-icon");

        content.classList.toggle("collapsed");
        icon.textContent = content.classList.contains("collapsed") ? "+" : "-";
      });
    });
  }

  function renderComparison(data) {
    const albumA = data.album_a;
    const albumB = data.album_b;
    const sharedTopics = data.shared_topics || [];

    // Album headers
    document.getElementById("album-a-name").textContent = albumA.album || "-";
    document.getElementById("album-a-artist").textContent = albumA.artist || "-";
    document.getElementById("album-b-name").textContent = albumB.album || "-";
    document.getElementById("album-b-artist").textContent = albumB.artist || "-";

    // Get results
    const resultsA = albumA.results || {};
    const resultsB = albumB.results || {};

    // Track counts
    document.getElementById("album-a-tracks").textContent = formatTrackCount(resultsA);
    document.getElementById("album-b-tracks").textContent = formatTrackCount(resultsB);

    // Render sentiment comparison
    renderSentiment(resultsA, resultsB);

    // Render vocabulary comparison
    renderVocabulary(resultsA, resultsB);

    // Render theme overlap
    renderThemes(resultsA, resultsB);

    // Render discovered themes in common (LDA)
    renderDiscoveredTopics(sharedTopics);
  }

  function getSentimentLabel(score) {
    if (score >= 0.5) return "Extremely Positive";
    if (score >= 0.3) return "Very Positive";
    if (score >= 0.15) return "Positive";
    if (score >= 0.05) return "Slightly Positive";
    if (score > -0.05) return "Neutral";
    if (score > -0.15) return "Slightly Negative";
    if (score > -0.3) return "Negative";
    if (score > -0.5) return "Very Negative";
    return "Extremely Negative";
  }

  function renderSentiment(resultsA, resultsB) {
    const sentimentA = resultsA.sentiment?.overall || 0;
    const sentimentB = resultsB.sentiment?.overall || 0;

    // Overall scores
    const scoreAEl = document.getElementById("sentiment-a");
    const scoreBEl = document.getElementById("sentiment-b");

    scoreAEl.textContent = formatScore(sentimentA);
    scoreBEl.textContent = formatScore(sentimentB);

    // Add sentiment labels
    const labelAEl = document.getElementById("sentiment-label-a");
    const labelBEl = document.getElementById("sentiment-label-b");
    if (labelAEl) labelAEl.textContent = getSentimentLabel(sentimentA);
    if (labelBEl) labelBEl.textContent = getSentimentLabel(sentimentB);

    // Add color classes based on sentiment
    scoreAEl.classList.add(getSentimentClass(sentimentA));
    scoreBEl.classList.add(getSentimentClass(sentimentB));

    // Delta indicator
    const delta = sentimentA - sentimentB;
    const deltaEl = document.getElementById("sentiment-delta");
    if (Math.abs(delta) > 0.05) {
      const winner = delta > 0 ? "Album A" : "Album B";
      const arrow = delta > 0 ? "↑" : "↓";
      deltaEl.innerHTML = `<span class="${delta > 0 ? 'album-a-color' : 'album-b-color'}">${winner} is more positive ${arrow}</span>`;
    } else {
      deltaEl.textContent = "Similar sentiment";
    }

    // Most positive/negative
    const statsA = resultsA.stats || {};
    const statsB = resultsB.stats || {};

    if (statsA.most_positive) {
      document.getElementById("positive-a").textContent =
        `${statsA.most_positive.title} (${formatScore(statsA.most_positive.score)})`;
    }
    if (statsB.most_positive) {
      document.getElementById("positive-b").textContent =
        `${statsB.most_positive.title} (${formatScore(statsB.most_positive.score)})`;
    }
    if (statsA.most_negative) {
      document.getElementById("negative-a").textContent =
        `${statsA.most_negative.title} (${formatScore(statsA.most_negative.score)})`;
    }
    if (statsB.most_negative) {
      document.getElementById("negative-b").textContent =
        `${statsB.most_negative.title} (${formatScore(statsB.most_negative.score)})`;
    }

    // Track by track bars
    const songsA = resultsA.sentiment?.by_song || [];
    const songsB = resultsB.sentiment?.by_song || [];

    renderTrackBars("tracks-a", songsA, "album-a");
    renderTrackBars("tracks-b", songsB, "album-b");
  }

  function renderTrackBars(containerId, songs, albumClass) {
    const container = document.getElementById(containerId);

    if (!songs || songs.length === 0) {
      container.innerHTML = '<span class="no-tracks">No tracks</span>';
      return;
    }

    // Find max for scaling across both albums
    const maxAbs = Math.max(...songs.map(s => Math.abs(s.score)), 0.1);

    container.innerHTML = songs.map(song => {
      const score = song.score || 0;
      const percentage = (Math.abs(score) / maxAbs) * 100;
      const barClass = score >= 0 ? "positive" : "negative";

      return `
        <div class="track-bar-item">
          <span class="track-title" title="${song.title}">${song.title}</span>
          <div class="track-bar-wrapper">
            <div class="track-bar ${barClass} ${albumClass}" style="width: ${percentage}%"></div>
          </div>
          <span class="track-score ${barClass}">${formatScore(score)}</span>
        </div>
      `;
    }).join("");
  }

  function renderVocabulary(resultsA, resultsB) {
    const statsA = resultsA.stats || {};
    const statsB = resultsB.stats || {};

    // Total words
    document.getElementById("words-a").textContent =
      (statsA.total_words || 0).toLocaleString();
    document.getElementById("words-b").textContent =
      (statsB.total_words || 0).toLocaleString();

    // Unique words
    document.getElementById("unique-a").textContent =
      (statsA.unique_words || 0).toLocaleString();
    document.getElementById("unique-b").textContent =
      (statsB.unique_words || 0).toLocaleString();

    // Richness
    document.getElementById("richness-a").textContent =
      ((statsA.vocabulary_richness || 0) * 100).toFixed(1) + "%";
    document.getElementById("richness-b").textContent =
      ((statsB.vocabulary_richness || 0) * 100).toFixed(1) + "%";

    // Songs analyzed
    document.getElementById("songs-a").textContent = resultsA.songs_count || 0;
    document.getElementById("songs-b").textContent = resultsB.songs_count || 0;
  }

  function renderThemes(resultsA, resultsB) {
    const wordsA = (resultsA.word_frequency || []).slice(0, 20).map(w => w.word);
    const wordsB = (resultsB.word_frequency || []).slice(0, 20).map(w => w.word);

    const setA = new Set(wordsA);
    const setB = new Set(wordsB);

    const shared = wordsA.filter(w => setB.has(w));
    const onlyA = wordsA.filter(w => !setB.has(w));
    const onlyB = wordsB.filter(w => !setA.has(w));

    renderThemeTags("themes-shared", shared, "shared");
    renderThemeTags("themes-only-a", onlyA, "album-a");
    renderThemeTags("themes-only-b", onlyB, "album-b");
  }

  function renderThemeTags(containerId, words, type) {
    const container = document.getElementById(containerId);

    if (words.length === 0) {
      container.innerHTML = '<span class="no-themes">None</span>';
      return;
    }

    container.innerHTML = words
      .map(w => `<span class="theme-tag ${type}">${w}</span>`)
      .join("");
  }

  function formatScore(score) {
    return score >= 0 ? `+${score.toFixed(2)}` : score.toFixed(2);
  }

  function formatTrackCount(results) {
    const analyzed = results.songs_count || 0;
    const total = results.total_tracks || analyzed;
    return `${analyzed}/${total} tracks analyzed`;
  }

  function getSentimentClass(score) {
    if (score > 0.1) return "positive";
    if (score < -0.1) return "negative";
    return "neutral";
  }

  function renderDiscoveredTopics(topics) {
    const container = document.getElementById("discovered-topics");

    if (!topics || topics.length === 0) {
      container.innerHTML = '<p class="no-topics">No shared themes discovered. The albums may have very different lyrical content.</p>';
      return;
    }

    container.innerHTML = topics.map(topic => {
      const keywords = Object.entries(topic.keywords || {})
        .slice(0, 8)
        .map(([word, weight]) => `<span class="keyword-tag">${word}</span>`)
        .join("");

      return `
        <div class="discovered-topic">
          <div class="topic-header">
            <h4 class="topic-name">${topic.name}</h4>
          </div>
          <div class="topic-keywords">${keywords}</div>
        </div>
      `;
    }).join("");
  }
});
