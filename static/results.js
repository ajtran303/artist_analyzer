/**
 * Results page JavaScript
 */

document.addEventListener("DOMContentLoaded", function () {
  const artistNameEl = document.getElementById("artist-name");
  const albumNameEl = document.getElementById("album-name");
  const statusSection = document.getElementById("status-section");
  const statusText = document.getElementById("status-text");
  const resultsSection = document.getElementById("results-section");
  const errorSection = document.getElementById("error-section");
  const errorMessageEl = document.getElementById("error-message");
  const progressFill = document.getElementById("progress-fill");
  const progressPercent = document.getElementById("progress-percent");
  const funFactEl = document.getElementById("fun-fact");

  let pollInterval = null;
  let funFactInterval = null;
  let songSentimentData = []; // Store original song order
  let currentSortMode = "track"; // 'track' or 'sentiment'

  // Fun facts about lyrics analysis
  const funFacts = [
    "LDA (Latent Dirichlet Allocation) was invented in 2003 by David Blei, Andrew Ng, and Michael Jordan.",
    "The average pop song contains about 300-400 words.",
    "Sentiment analysis can detect emotions with up to 85% accuracy on well-written text.",
    "The word 'love' is the most common word in song lyrics across all genres.",
    "Topic modeling can reveal hidden themes that even the songwriter might not have consciously intended.",
    "The Beatles wrote over 300 songs, making them one of the most analyzed artists in music history.",
    "Song lyrics have become more repetitive over the past 50 years, according to research.",
    "Hip-hop lyrics contain the largest vocabulary of any music genre.",
    "The longest song title ever is over 300 characters long!",
    "Natural Language Processing has roots dating back to the 1950s.",
    "The most covered song of all time is 'Yesterday' by The Beatles.",
    "Lyrics analysis can predict song popularity with surprising accuracy.",
    "The human brain processes music in the same areas that process language.",
    "Country music lyrics mention trucks, beer, and rain more than any other genre.",
    "Taylor Swift's lyrics have been studied by linguists for their narrative complexity.",
    "The word 'baby' appears in over 25% of all Billboard Hot 100 songs.",
    "Radiohead's lyrics are considered some of the most linguistically complex in rock music.",
    "Studies show sad songs are streamed more often during winter months.",
    "Bob Dylan won the Nobel Prize in Literature partly for his lyrical compositions.",
    "The average hit song has a reading level of about 3rd grade.",
    "K-pop lyrics often mix Korean, English, and Japanese in a single song.",
    "Beyoncé's 'Lemonade' album has been analyzed in over 100 academic papers.",
    "Spotify uses NLP to analyze lyrics for mood-based playlist recommendations.",
    "The word 'yeah' is one of the most common filler words in English lyrics.",
    "Finnish has produced more metal bands per capita than any other country.",
    "Queen's 'Bohemian Rhapsody' contains over 900 individual vocal overdubs.",
    "AI can now generate lyrics that are indistinguishable from human-written ones 40% of the time.",
    "The Beatles used the word 'love' 613 times across their discography.",
    "Daft Punk's 'Around the World' repeats the title phrase exactly 144 times.",
    "Researchers found that lyrics mentioning specific places boost local tourism.",
    "The longest officially released song is over 13 hours long.",
    "Prince wrote over 500 songs that were never released during his lifetime.",
    "The most common rhyme scheme in pop music is ABAB.",
    "Songs in minor keys are perceived as sadder regardless of lyrical content.",
  ];

  // Start polling for status
  checkStatus();
  pollInterval = setInterval(checkStatus, 2000);

  // Start fun facts rotation
  showFunFact();
  funFactInterval = setInterval(showFunFact, 10000);

  function showFunFact() {
    funFactEl.classList.remove("fade-in");
    void funFactEl.offsetWidth; // Trigger reflow
    const randomIndex = Math.floor(Math.random() * funFacts.length);
    funFactEl.textContent = funFacts[randomIndex];
    funFactEl.classList.add("fade-in");
  }

  async function checkStatus() {
    try {
      const response = await fetch(`/api/analyze/${JOB_ID}`);
      const data = await response.json();

      artistNameEl.textContent = data.artist || "Unknown Artist";
      if (data.album) {
        albumNameEl.textContent = data.album;
      }

      if (data.status === "completed") {
        clearInterval(pollInterval);
        clearInterval(funFactInterval);
        updateProgress(data.total_stages, data.total_stages);
        // Short delay to show 100% before showing results
        setTimeout(() => showResults(data.results), 500);
      } else if (data.status === "failed") {
        clearInterval(pollInterval);
        clearInterval(funFactInterval);
        showError(data.error || "Analysis failed");
      } else {
        // Still processing
        statusText.textContent = data.progress || getStatusMessage(data.status);
        updateProgress(data.stage || 0, data.total_stages || 6, data.sub_current, data.sub_total);
        updateSteps(data.stage || 0);
      }
    } catch (error) {
      console.error("Error checking status:", error);
      statusText.textContent = "Error checking status...";
    }
  }

  function updateProgress(stage, totalStages, subCurrent, subTotal) {
    // Calculate base progress from completed stages
    const stageProgress = (stage - 1) / totalStages;

    // Add sub-progress within current stage if available
    let subProgress = 0;
    if (subCurrent && subTotal && subTotal > 0) {
      subProgress = (subCurrent / subTotal) / totalStages;
    }

    const percent = Math.round(Math.max(0, (stageProgress + subProgress)) * 100);
    progressFill.style.width = `${percent}%`;
    progressPercent.textContent = `${percent}%`;
  }

  function updateSteps(currentStage) {
    const steps = document.querySelectorAll(".step");
    steps.forEach((step) => {
      const stepNum = parseInt(step.dataset.step);
      const iconEl = step.querySelector(".step-icon");

      step.classList.remove("completed", "active", "pending");

      if (stepNum < currentStage) {
        // Completed
        step.classList.add("completed");
        iconEl.textContent = "✓";
      } else if (stepNum === currentStage) {
        // Active/In Progress
        step.classList.add("active");
        iconEl.textContent = "●";
      } else {
        // Pending
        step.classList.add("pending");
        iconEl.textContent = "○";
      }
    });

    // Update connectors
    const connectors = document.querySelectorAll(".step-connector");
    connectors.forEach((connector, index) => {
      connector.classList.remove("completed");
      if (index + 1 < currentStage) {
        connector.classList.add("completed");
      }
    });
  }

  function getStatusMessage(status) {
    switch (status) {
      case "queued":
        return "Waiting in queue...";
      case "processing":
        return "Processing analysis...";
      default:
        return "Working...";
    }
  }

  function showResults(results) {
    statusSection.classList.add("hidden");
    resultsSection.classList.remove("hidden");

    // Render topics
    renderTopics(results.topics || []);

    // Render sentiment
    renderSentiment(results.sentiment || {});

    // Render word frequency
    renderWordFrequency(results.word_frequency || []);

    // Render metaphors
    renderMetaphors(results.metaphors || []);

    // Update stats
    document.getElementById("songs-count").textContent =
      results.songs_count || 0;

    const stats = results.stats || {};
    document.getElementById("total-words").textContent = (
      stats.total_words || 0
    ).toLocaleString();
    document.getElementById("unique-words").textContent = (
      stats.unique_words || 0
    ).toLocaleString();
    document.getElementById("vocab-richness").textContent =
      ((stats.vocabulary_richness || 0) * 100).toFixed(1) + "%";

    // Most positive/negative songs
    if (stats.most_positive) {
      const pos = stats.most_positive;
      document.getElementById("most-positive-song").textContent = `${
        pos.title
      } (${pos.score >= 0 ? "+" : ""}${pos.score.toFixed(2)})`;
    }
    if (stats.most_negative) {
      const neg = stats.most_negative;
      document.getElementById("most-negative-song").textContent = `${
        neg.title
      } (${neg.score >= 0 ? "+" : ""}${neg.score.toFixed(2)})`;
    }
  }

  function renderTopics(topics) {
    const container = document.getElementById("topics-container");
    container.innerHTML = "";

    topics.forEach((topic, index) => {
      const keywords = Object.entries(topic.keywords || {})
        .slice(0, 6)
        .map(([word, weight]) => `<span class="keyword-tag">${word}</span>`)
        .join("");

      const html = `
                <div class="topic-item">
                    <div class="topic-header">
                        <span class="topic-name">${
                          topic.name || `Topic ${index + 1}`
                        }</span>
                        <span class="topic-weight">${(
                          (topic.weight || 0) * 100
                        ).toFixed(1)}%</span>
                    </div>
                    <div class="topic-keywords">${keywords}</div>
                </div>
            `;
      container.innerHTML += html;
    });
  }

  function renderSentiment(sentiment) {
    const overall = sentiment.overall || 0;
    const overallEl = document.getElementById("overall-sentiment");
    overallEl.textContent =
      overall >= 0 ? `+${overall.toFixed(2)}` : overall.toFixed(2);

    if (overall > 0.1) {
      overallEl.className = "score positive";
    } else if (overall < -0.1) {
      overallEl.className = "score negative";
    } else {
      overallEl.className = "score neutral";
    }

    // Store original song order data
    songSentimentData = sentiment.by_song || [];

    // Render song chart in track order
    renderBarChart("song-chart", songSentimentData, "title");

    // Set up sort toggle buttons
    setupSortToggle();
  }

  function setupSortToggle() {
    const sortTrackBtn = document.getElementById("sort-track");
    const sortSentimentBtn = document.getElementById("sort-sentiment");
    const chartTitle = document.getElementById("chart-title");

    sortTrackBtn.addEventListener("click", () => {
      if (currentSortMode === "track") return;
      currentSortMode = "track";
      sortTrackBtn.classList.add("active");
      sortSentimentBtn.classList.remove("active");
      chartTitle.textContent = "Track Order";
      renderBarChart("song-chart", songSentimentData, "title");
    });

    sortSentimentBtn.addEventListener("click", () => {
      if (currentSortMode === "sentiment") return;
      currentSortMode = "sentiment";
      sortSentimentBtn.classList.add("active");
      sortTrackBtn.classList.remove("active");
      chartTitle.textContent = "By Sentiment";
      // Sort from most negative to most positive
      const sorted = [...songSentimentData].sort((a, b) => a.score - b.score);
      renderBarChart("song-chart", sorted, "title");
    });
  }

  function renderBarChart(containerId, data, labelKey) {
    const container = document.getElementById(containerId);
    container.innerHTML = "";

    if (data.length === 0) {
      container.innerHTML = '<p class="text-muted">No data available</p>';
      return;
    }

    // Show all songs (no limit for song view)
    const items = data;

    // Find max absolute value for scaling
    const maxAbs = Math.max(...items.map((d) => Math.abs(d.score)), 0.1);

    items.forEach((item) => {
      const score = item.score || 0;
      const percentage = (Math.abs(score) / maxAbs) * 100;
      const isPositive = score >= 0;
      const barClass = isPositive ? "positive" : "negative";

      const html = `
                <div class="bar-item">
                    <span class="bar-label" title="${item[labelKey]}">${
        item[labelKey]
      }</span>
                    <div class="bar-wrapper">
                        <div class="bar ${barClass}" style="width: ${percentage}%"></div>
                    </div>
                    <span class="bar-value">${
                      score >= 0 ? "+" : ""
                    }${score.toFixed(2)}</span>
                </div>
            `;
      container.innerHTML += html;
    });
  }

  function renderWordFrequency(words) {
    const container = document.getElementById("word-frequency");
    container.innerHTML = "";

    words.slice(0, 15).forEach((item) => {
      const html = `
                <div class="word-item">
                    <span class="word-text">${item.word}</span>
                    <span class="word-count">${item.frequency}</span>
                </div>
            `;
      container.innerHTML += html;
    });
  }

  function renderMetaphors(metaphors) {
    const container = document.getElementById("metaphors");
    container.innerHTML = "";

    metaphors.forEach((item) => {
      const html = `
                <div class="metaphor-item">
                    <span class="metaphor-name">${item.metaphor}</span>
                    <span class="metaphor-count">${item.frequency}</span>
                </div>
            `;
      container.innerHTML += html;
    });
  }

  function showError(message) {
    statusSection.classList.add("hidden");
    errorSection.classList.remove("hidden");
    errorMessageEl.textContent = message;
  }
});
