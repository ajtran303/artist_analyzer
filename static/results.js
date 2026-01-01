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
  const compareBtn = document.getElementById("compare-btn");
  const toast = document.getElementById("toast");
  const toastMessage = document.getElementById("toast-message");

  let pollInterval = null;
  let funFactInterval = null;
  let songSentimentData = []; // Store original song order
  let currentSortMode = "track"; // 'track' or 'sentiment'
  let currentAlbumData = null; // Store current album info for comparison

  // Fun facts about lyrics analysis
  const funFacts = [
    "The word 'love' is the most common word in song lyrics across all genres.",
    "Hip-hop lyrics contain the largest vocabulary of any music genre.",
    "The Beatles wrote over 300 songs, making them one of the most analyzed artists in music history.",
    "Song lyrics have become more repetitive over the past 50 years, according to research.",
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
    "LDA (Latent Dirichlet Allocation) was invented in 2003 by David Blei, Andrew Ng, and Michael Jordan.",
    "The average pop song contains about 300-400 words.",
    "Sentiment analysis can detect emotions with up to 85% accuracy on well-written text.",
    "Topic modeling can reveal hidden themes that even the songwriter might not have consciously intended.",
    "The longest song title ever is over 300 characters long!",
    "Natural Language Processing has roots dating back to the 1950s.",
    "The most covered song of all time is 'Yesterday' by The Beatles.",
    "Lyrics analysis can predict song popularity with surprising accuracy.",
    "The human brain processes music in the same areas that process language.",
    "Studies show sad songs are streamed more often during winter months.",
    "Beyoncé's 'Lemonade' album has been analyzed in over 100 academic papers.",
    "The word 'yeah' is one of the most common filler words in English lyrics.",
    "AI can now generate lyrics that are indistinguishable from human-written ones 40% of the time.",
    "Researchers found that lyrics mentioning specific places boost local tourism.",
    "The longest officially released song is over 13 hours long.",
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

      // Store album data for comparison and retry features
      currentAlbumData = {
        job_id: JOB_ID,
        artist: data.artist,
        album: data.album,
        album_id: data.album_id,
      };

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
        updateProgress(
          data.stage || 0,
          data.total_stages || 7,
          data.sub_current,
          data.sub_total
        );
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
      subProgress = subCurrent / subTotal / totalStages;
    }

    const percent = Math.round(Math.max(0, stageProgress + subProgress) * 100);
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

    // Show compare button and set up handler
    compareBtn.classList.remove("hidden");
    setupCompareButton();

    // Show tracks analyzed count in header
    const songsCount = results.songs_count || 0;
    const totalTracks = results.total_tracks || songsCount;
    const tracksAnalyzedEl = document.getElementById("tracks-analyzed");
    if (tracksAnalyzedEl) {
      if (totalTracks > songsCount) {
        tracksAnalyzedEl.innerHTML = `${songsCount}/${totalTracks} tracks analyzed <span class="partial-reason">(some lyrics unavailable)</span> <br/> <button class="retry-link" id="retry-btn">Retry</button> <span class="retry-warning">(results may vary)</span>`;
        tracksAnalyzedEl.classList.add("partial");
        setupRetryButton();
      } else {
        tracksAnalyzedEl.textContent = `${songsCount} tracks analyzed`;
      }
    }

    // Render topics
    renderTopics(results.topics || []);

    // Render sentiment
    renderSentiment(results.sentiment || {});

    // Render most emotional passages (positive and negative)
    renderEmotionalPassages(results.stats?.emotional_passages);

    // Render emotions profile
    renderEmotions(results.emotions);

    // Render word frequency
    renderWordFrequency(results.word_frequency || []);

    // Render metaphors
    renderMetaphors(results.metaphors || []);

    // Update stats display
    if (totalTracks > songsCount) {
      document.getElementById(
        "songs-count"
      ).textContent = `${songsCount} of ${totalTracks}`;
      document.getElementById("songs-label").textContent = "Tracks Analyzed";
    } else {
      document.getElementById("songs-count").textContent = songsCount;
    }

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

    if (!topics || topics.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">~</div>
          <p class="empty-state-message">No topic patterns detected</p>
          <p class="empty-state-hint">This can happen with very short or highly varied lyrics</p>
        </div>`;
      return;
    }

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
                    </div>
                    <div class="topic-keywords">${keywords}</div>
                </div>
            `;
      container.innerHTML += html;
    });
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

  function renderSentiment(sentiment) {
    const overall = sentiment.overall || 0;
    const overallEl = document.getElementById("overall-sentiment");
    overallEl.textContent =
      overall >= 0 ? `+${overall.toFixed(2)}` : overall.toFixed(2);

    // Add sentiment label
    const labelEl = document.getElementById("sentiment-label");
    if (labelEl) {
      labelEl.textContent = getSentimentLabel(overall);
    }

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

  function renderEmotionalPassages(passages) {
    const section = document.getElementById("emotional-passages-section");

    if (!passages) {
      section.classList.add("hidden");
      return;
    }

    const positivePassage = passages.most_positive;
    const negativePassage = passages.most_negative;

    // If neither passage exists, hide the section
    if (!positivePassage && !negativePassage) {
      section.classList.add("hidden");
      return;
    }

    section.classList.remove("hidden");

    // Render positive passage
    renderSinglePassage(
      positivePassage,
      "positive-passage-container",
      "positive-passage-song",
      "positive-passage-score",
      "positive-passage-text",
      true
    );

    // Render negative passage
    renderSinglePassage(
      negativePassage,
      "negative-passage-container",
      "negative-passage-song",
      "negative-passage-score",
      "negative-passage-text",
      false
    );
  }

  function renderSinglePassage(passage, containerId, songId, scoreId, textId, isPositive) {
    const container = document.getElementById(containerId);
    const songEl = document.getElementById(songId);
    const scoreEl = document.getElementById(scoreId);
    const textEl = document.getElementById(textId);

    if (!passage || !passage.passage) {
      container.classList.add("hidden");
      return;
    }

    container.classList.remove("hidden");

    // Set song title
    songEl.textContent = `From "${passage.song_title}"`;

    // Set sentiment score badge
    const score = passage.score || 0;
    scoreEl.textContent = `${score >= 0 ? "+" : ""}${score.toFixed(2)}`;

    // Set passage text with line breaks preserved
    textEl.innerHTML = passage.passage
      .split("\n")
      .map((line) => `<span class="passage-line">${escapeHtml(line)}</span>`)
      .join("<br>");
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function renderEmotions(emotions) {
    const container = document.getElementById("emotions-chart");
    const dominantEl = document.getElementById("dominant-emotion");
    const section = document.getElementById("emotions-section");

    if (!emotions || !emotions.overall) {
      section.classList.add("hidden");
      return;
    }

    section.classList.remove("hidden");

    // Show dominant emotion
    if (emotions.dominant_emotion) {
      const emotionIcons = {
        joy: "^_^",
        trust: "<3",
        fear: ":O",
        surprise: ":!",
        sadness: ":(",
        disgust: ">_<",
        anger: ">:(",
        anticipation: "..."
      };
      const icon = emotionIcons[emotions.dominant_emotion] || "*";
      dominantEl.innerHTML = `
        <span class="dominant-label">Dominant Emotion</span>
        <span class="dominant-value">
          <span class="emotion-icon">${icon}</span>
          ${emotions.dominant_emotion.charAt(0).toUpperCase() + emotions.dominant_emotion.slice(1)}
        </span>
      `;
    }

    // Render emotion bars
    container.innerHTML = "";
    const overall = emotions.overall;
    const maxValue = Math.max(...Object.values(overall), 1);

    // Sort emotions by value descending
    const sortedEmotions = Object.entries(overall)
      .sort((a, b) => b[1] - a[1]);

    sortedEmotions.forEach(([emotion, value]) => {
      const percentage = (value / maxValue) * 100;
      const emotionClass = getEmotionClass(emotion);

      const html = `
        <div class="emotion-bar-item">
          <span class="emotion-label">${emotion}</span>
          <div class="emotion-bar-wrapper">
            <div class="emotion-bar ${emotionClass}" style="width: ${percentage}%"></div>
          </div>
          <span class="emotion-value">${value.toFixed(1)}%</span>
        </div>
      `;
      container.innerHTML += html;
    });
  }

  function getEmotionClass(emotion) {
    const classes = {
      joy: "emotion-positive",
      trust: "emotion-positive",
      anticipation: "emotion-neutral",
      surprise: "emotion-neutral",
      fear: "emotion-negative",
      sadness: "emotion-negative",
      anger: "emotion-negative",
      disgust: "emotion-negative"
    };
    return classes[emotion] || "emotion-neutral";
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
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">♪</div>
          <p class="empty-state-message">No lyrics found for this album</p>
          <p class="empty-state-hint">The tracks may be instrumental or lyrics aren't available</p>
        </div>`;
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

    if (!words || words.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">...</div>
          <p class="empty-state-message">No word data available</p>
          <p class="empty-state-hint">Not enough lyrical content to analyze</p>
        </div>`;
      return;
    }

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

    if (!metaphors || metaphors.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">*</div>
          <p class="empty-state-message">No recurring themes detected</p>
          <p class="empty-state-hint">The lyrics may not contain common thematic keywords</p>
        </div>`;
      return;
    }

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

  function setupRetryButton() {
    const retryBtn = document.getElementById("retry-btn");
    if (!retryBtn || !currentAlbumData) return;

    retryBtn.addEventListener("click", async () => {
      retryBtn.disabled = true;
      retryBtn.textContent = "Retrying...";

      try {
        const response = await fetch("/api/analyze", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            artist_name: currentAlbumData.artist,
            album_id: currentAlbumData.album_id,
            album_name: currentAlbumData.album,
            force: true,
          }),
        });

        const data = await response.json();

        if (response.ok) {
          // Redirect to new job (or same page if job_id is same)
          window.location.href = `/results/${data.job_id}`;
        } else {
          showToast(data.error || "Retry failed");
          retryBtn.disabled = false;
          retryBtn.textContent = "Retry";
        }
      } catch (error) {
        console.error("Retry error:", error);
        showToast("Network error. Please try again.");
        retryBtn.disabled = false;
        retryBtn.textContent = "Retry";
      }
    });
  }

  // Compare feature functions
  function setupCompareButton() {
    const compareBottomBtn = document.getElementById("compare-bottom-btn");

    // Check if we're already in compare mode (have album A stored)
    const storedAlbum = localStorage.getItem("compareAlbumA");

    if (storedAlbum) {
      const albumA = JSON.parse(storedAlbum);

      // Check if this is the same album (user came back to same album)
      if (albumA.job_id === JOB_ID) {
        compareBtn.textContent = "Compare";
      } else {
        // We have album A, this is album B - redirect to compare page
        localStorage.removeItem("compareAlbumA");
        window.location.href = `/compare?a=${albumA.job_id}&b=${JOB_ID}`;
        return;
      }
    }

    compareBtn.addEventListener("click", handleCompareClick);
    if (compareBottomBtn) {
      compareBottomBtn.addEventListener("click", handleCompareClick);
    }
  }

  function handleCompareClick() {
    if (!currentAlbumData) return;

    // Store this album as Album A
    localStorage.setItem("compareAlbumA", JSON.stringify(currentAlbumData));

    // Show toast
    showToast("Album saved! Now search for another album to compare.");

    // Redirect to home page in compare mode
    setTimeout(() => {
      window.location.href = "/?compare=true";
    }, 1500);
  }

  function showToast(message) {
    toastMessage.textContent = message;
    toast.classList.remove("hidden");
    toast.classList.add("show");

    setTimeout(() => {
      toast.classList.remove("show");
      toast.classList.add("hidden");
    }, 3000);
  }
});
