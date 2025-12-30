# PROJECT SPEC: Artist Lyrical Analysis Service (TDD-First)

## OVERVIEW

Build a production-ready web application that analyzes any artist's lyrics to discover hidden themes, track sentiment evolution, and reveal lyrical patterns. Uses LDA for theme discovery, sentiment analysis for emotional tracking, and bonus analyses for word frequency and recurring metaphors. All features developed using Test-Driven Development.

## TECH STACK

- Backend: Python (Flask, Celery, SQLAlchemy)
- Database: PostgreSQL
- Message Broker: Redis
- Frontend: HTML/CSS/JavaScript (Vanilla)
- Testing: pytest, pytest-cov, pytest-asyncio, factory-boy, responses
- Deployment: Docker + Render
- API: Genius API for lyrics scraping

## PROJECT STRUCTURE

```
artist-analyzer/
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh
├── .dockerignore
├── .env.example
├── .gitignore
├── requirements.txt
├── render.yaml
├── app.py
├── celery_app.py
├── config.py
├── models.py
├── database.py
├── pipeline/
│   ├── __init__.py
│   ├── tasks.py
│   ├── scraper.py
│   ├── preprocessor.py
│   ├── lda_analyzer.py
│   ├── sentiment_analyzer.py
│   └── bonus_analyzer.py
├── routes/
│   ├── __init__.py
│   └── api.py
├── templates/
│   ├── index.html
│   ├── results.html
│   └── base.html
├── static/
│   ├── style.css
│   ├── script.js
│   └── results.js
├── tests/
│   ├── __init__.py
│   ├── conftest.py (pytest fixtures)
│   ├── factories.py (factory-boy factories)
│   ├── test_models.py
│   ├── test_database.py
│   ├── test_scraper.py
│   ├── test_preprocessor.py
│   ├── test_lda_analyzer.py
│   ├── test_sentiment_analyzer.py
│   ├── test_bonus_analyzer.py
│   ├── test_tasks.py
│   ├── test_api.py
│   ├── test_routes.py
│   └── integration/
│       ├── __init__.py
│       ├── test_full_pipeline.py
│       └── test_api_workflow.py
└── pytest.ini
```

## TESTING STRATEGY

### Phase 0: Setup & Configuration

- Create `pytest.ini` with coverage thresholds (min 80%)
- Create `conftest.py` with shared fixtures
- Create `factories.py` for test data generation
- Mock external APIs (Genius, Redis, PostgreSQL)

### Phase 1: Unit Tests - Models

**FILE:** `tests/test_models.py`

#### Analysis Model Tests

**Test:** `Analysis.create()` initializes with correct defaults

- Status should default to 'queued'
- Created_at should be set to current time
- Job_id should be nullable initially

**Test:** `Analysis.update_status()` updates status and timestamp

- Calling `update_status('completed')` sets status and completed_at
- Only completed status updates completed_at timestamp

**Test:** `Analysis.set_results()` stores JSON results

- Results dict converts to JSON and retrieves correctly
- Complex nested structures preserved

**Test:** `Analysis.from_artist_name()` retrieves or creates

- Returns existing analysis if found
- Creates new if not found

**Test:** `Analysis.mark_failed()` sets error state

- Status becomes 'failed'
- Error message is stored
- No completed_at timestamp set

#### Song Model Tests

**Test:** `Song.create()` with all fields

- All fields persist correctly
- Relationship to Analysis set properly

**Test:** `Song.bulk_create()` inserts multiple

- Batch insert works efficiently
- All songs linked to correct analysis

**Test:** `Song.get_by_analysis()` retrieves related songs

- Returns only songs for that analysis
- Ordered correctly

#### Topic Model Tests

**Test:** `Topic.create()` with keywords JSON

- Keywords dict persists and retrieves
- Weight calculated correctly

**Test:** `Topic.get_top_topics()` returns sorted

- Returns topics sorted by weight descending
- Limits to top N

**COVERAGE TARGET:** 100% of model methods

---

### Phase 2: Unit Tests - Database

**FILE:** `tests/test_database.py`

#### Database Connection Tests

**Test:** `db.session.execute()` works

- Can execute raw SQL

**Test:** Database health check

- SELECT 1 returns successfully
- Connection pool working

**Test:** Rollback on error

- Transaction rolls back on exception
- Session cleaned up properly

#### Migration Tests

**Test:** Alembic migrations apply cleanly

- Latest schema matches models
- Can downgrade and upgrade

**Test:** Schema has correct indices

- artist_name is indexed on Analysis
- job_id is unique on Analysis
- Created_at is indexed for sorting

#### Foreign Key Constraints

**Test:** Song deletion cascades from Analysis

- Deleting Analysis deletes Songs

**Test:** Topic deletion cascades

- Deleting Analysis deletes Topics

**COVERAGE TARGET:** 100% of database operations

---

### Phase 3: Unit Tests - Scraper

**FILE:** `tests/test_scraper.py`

#### Genius API Integration

**Test:** `scrape_genius()` returns correct structure

- Mock Genius API response
- Returns list of dicts with: title, artist, album, year, lyrics, url

**Test:** `scrape_genius()` handles missing data

- Missing album defaults to None
- Missing year defaults to None
- Returns empty list if artist not found

**Test:** `scrape_genius()` respects rate limits

- Makes max 5 requests per artist (configurable)
- Stops when no more songs returned

**Test:** `scrape_genius()` extracts lyrics correctly

- Calls `_scrape_song_lyrics()` for each song
- Lyrics are non-empty strings

**Test:** `_scrape_song_lyrics()` parses HTML

- Mock Genius song page HTML
- Extracts lyrics from correct div containers
- Returns empty string on parse error

**Test:** `_scrape_song_lyrics()` handles 404

- Returns empty string for invalid URL
- Doesn't raise exception

#### Error Handling

**Test:** Network timeout handled

- Retries up to 3 times
- Raises custom exception after retries exhausted

**Test:** Invalid artist name

- Returns empty list (not error)
- Logs warning

**MOCKING:**

- Mock requests library with responses library
- Mock Genius API responses with realistic JSON
- Mock HTML parsing with BeautifulSoup test fixtures

**COVERAGE TARGET:** 95% of scraper (hard to test HTML parsing perfectly)

---

### Phase 4: Unit Tests - Preprocessor

**FILE:** `tests/test_preprocessor.py`

#### Text Cleaning

**Test:** `preprocess_lyrics()` lowercases

- "THE NIGHT" becomes "the night"

**Test:** `preprocess_lyrics()` removes stopwords

- "the", "a", "and", "or" removed
- Content words preserved

**Test:** `preprocess_lyrics()` tokenizes correctly

- "hello world" becomes ["hello", "world"]
- Punctuation separated: "don't" → ["don"]

**Test:** `preprocess_lyrics()` stems words

- "dying" → "die"
- "loved" → "love"
- "running" → "run"

**Test:** `preprocess_lyrics()` removes short words

- Words < 3 chars removed
- Keeps meaningful words

#### Corpus Building

**Test:** `preprocess_lyrics()` returns tokens list

- Each song has 'tokens' key with list
- Each song has 'text' key with rejoined string

**Test:** `preprocess_lyrics()` handles empty lyrics

- Returns empty tokens list
- Doesn't crash

**Test:** `preprocess_lyrics()` handles special characters

- URLs removed or cleaned
- Special symbols handled

#### Edge Cases

**Test:** `preprocess_lyrics()` with non-English

- Handles accented characters
- Doesn't crash on unicode

**Test:** `preprocess_lyrics()` with very short lyrics

- Returns empty tokens (OK)
- Doesn't crash

**FIXTURES:**

- Sample lyrics strings (short, medium, long)
- Pre/post tokenization examples

**COVERAGE TARGET:** 100% of preprocessor

---

### Phase 5: Unit Tests - LDA Analyzer

**FILE:** `tests/test_lda_analyzer.py`

#### Dictionary & Corpus Creation

**Test:** `run_lda()` creates Dictionary

- Dictionary built from tokenized lyrics
- Extremes filtered (no_below=2, no_above=0.5)

**Test:** `run_lda()` creates Corpus

- Bag-of-words representation correct
- Each document is list of (word_id, frequency) tuples

#### LDA Model Training

**Test:** `run_lda()` trains LDA model

- Model has num_topics=7 (or configurable)
- Passes=10 for training iterations
- Returns consistent results (random_state=42)

**Test:** `run_lda()` returns topics list

- Topics sorted by weight descending
- Each topic has: id, name, keywords dict, weight

#### Topic Extraction

**Test:** `run_lda()` extracts keywords from topics

- Keywords extracted from Gensim output
- Weights normalized correctly
- Top keywords represent theme

**Test:** `_parse_topic_words()` parses topic string

- Input: `"(0.045*\"word1\" + 0.032*\"word2\")"`
- Output: `[("word1", 0.045), ("word2", 0.032)]`

#### Edge Cases

**Test:** `run_lda()` with very few documents

- Handles < 10 songs gracefully
- Reduces num_topics if needed

**Test:** `run_lda()` with duplicate songs

- Handles repeated lyrics
- Doesn't crash

**FIXTURES:**

- Sample preprocessed lyrics (3, 10, 50 songs)
- Expected topic structures

**COVERAGE TARGET:** 95% (LDA training is probabilistic)

---

### Phase 6: Unit Tests - Sentiment Analyzer

**FILE:** `tests/test_sentiment_analyzer.py`

#### Sentiment Scoring

**Test:** `run_sentiment()` scores each song

- Happy lyrics score > 0
- Sad lyrics score < 0
- Neutral lyrics score ≈ 0

**Test:** `run_sentiment()` handles edge cases

- Empty lyrics scored as 0
- Single word lyrics handled

**Test:** Sentiment range

- All scores between -1 and 1

#### Album Aggregation

**Test:** `run_sentiment()` aggregates by album

- Returns by_album list of dicts
- Each has: album, score (average), song_count
- Sorted by sentiment score ascending

**Test:** `run_sentiment()` handles missing albums

- Songs with no album listed as "Unknown"
- All songs appear in results

#### Year Aggregation

**Test:** `run_sentiment()` aggregates by year

- Returns by_year list of dicts
- Each has: year, score (average), song_count
- Sorted by year ascending

**Test:** `run_sentiment()` handles missing years

- Songs without year skipped (not in by_year)
- All other years included

#### Overall Sentiment

**Test:** `run_sentiment()` calculates overall

- Returns overall avg of all songs
- Is weighted correctly

**FIXTURES:**

- Sample songs with lyrics (happy, sad, neutral)
- Songs with various albums/years

**COVERAGE TARGET:** 100% of sentiment analyzer

---

### Phase 7: Unit Tests - Bonus Analyzer

**FILE:** `tests/test_bonus_analyzer.py`

#### Word Frequency Analysis

**Test:** `analyze_word_frequency()` returns top words

- Returns list of dicts: {word, frequency}
- Sorted by frequency descending
- Top 50 returned

**Test:** `analyze_word_frequency()` counts correctly

- "love" appears 5 times → frequency: 5
- Order preserved

**Test:** `analyze_word_frequency()` handles duplicates

- Case-insensitive counting
- All instances counted

#### Metaphor Analysis

**Test:** `analyze_metaphors()` identifies themes

- Returns list of dicts: {metaphor, frequency}
- Includes: death, love, darkness, pain, loss, eternity

**Test:** `analyze_metaphors()` counts keywords

- "death" + "dying" + "dead" counted for death theme
- Regex word boundaries respected (`\b`)

**Test:** `analyze_metaphors()` case insensitive

- "DEATH" and "death" both counted

**Test:** `analyze_metaphors()` handles variations

- Stemmed words also match (optional)

**FIXTURES:**

- Sample lyrics with various metaphors
- Expected frequency counts

**COVERAGE TARGET:** 100% of bonus analyzer

---

### Phase 8: Unit Tests - Celery Tasks

**FILE:** `tests/test_tasks.py`

#### Task Creation

**Test:** `analyze_artist_async.delay()` queues task

- Celery accepts task
- Returns task ID

**Test:** Task has correct name

- Task name is 'pipeline.tasks.analyze_artist_async'

#### Task Execution (with mocked pipeline)

**Test:** `analyze_artist_async()` updates progress

- Calls `update_state()` with progress messages
- Progress stages: Scraping, Preprocessing, LDA, Sentiment, Final

**Test:** `analyze_artist_async()` calls all pipeline steps

- Calls `scrape_genius()`
- Calls `preprocess_lyrics()`
- Calls `run_lda()`
- Calls `run_sentiment()`
- Calls `analyze_word_frequency()`
- Calls `analyze_metaphors()`

**Test:** `analyze_artist_async()` saves to database

- Creates Analysis record
- Sets status='completed'
- Stores results JSON
- Sets completed_at timestamp

#### Error Handling

**Test:** `analyze_artist_async()` on scraper failure

- Catches exception
- Sets status='failed'
- Stores error message
- Doesn't raise

**Test:** `analyze_artist_async()` on LDA failure

- Similar error handling
- Preserves which step failed

**Test:** Task retries (optional)

- Retries up to 3 times on failure
- Exponential backoff

**MOCKING:**

- Mock all pipeline functions
- Mock database operations
- Mock Celery update_state()

**COVERAGE TARGET:** 95% (hard to test distributed task fully)

---

### Phase 9: Unit Tests - API Routes

**FILE:** `tests/test_api.py`

#### POST /api/analyze Endpoint

**Test:** Valid artist submission

- Input: `{artist_name: "The Cure"}`
- Returns: `{job_id, status: "queued", artist: "The Cure"}`
- HTTP 202 Accepted

**Test:** Missing artist name

- Returns 400 Bad Request
- Error message provided

**Test:** Whitespace trimmed

- Input: `"  The Cure  "`
- Treated as "The Cure"

**Test:** Artist not found handling

- If scraper returns no songs
- Task marked failed with appropriate message

#### Caching Behavior

**Test:** Cached artist returns immediately

- First request: 202 (queued)
- Second request (same artist): 200 (completed)
- Returns cached results

#### GET /api/analyze/<job_id> Endpoint

**Test:** Queued status

- Returns: `{job_id, status: "queued", artist}`
- HTTP 200

**Test:** Processing status

- Returns: `{job_id, status: "processing", progress: "...", artist}`
- HTTP 200

**Test:** Completed status

- Returns: `{job_id, status: "completed", artist, results: {...}}`
- HTTP 200

**Test:** Failed status

- Returns: `{job_id, status: "failed", error: "...", artist}`
- HTTP 400

**Test:** Invalid job_id

- Returns 404 Not Found

#### GET /api/results/<job_id> Endpoint

**Test:** Returns full results when completed

- Returns: `{artist, results, completed_at}`
- HTTP 200

**Test:** Returns 202 if not completed

- Returns error message

**Test:** Returns 404 if not found

#### Error Responses

**Test:** Malformed JSON

- Returns 400 Bad Request

**Test:** Server errors caught

- Returns 500 with error message
- Exception logged

**MOCKING:**

- Mock AsyncResult from Celery
- Mock database queries
- Mock task submission

**FIXTURES:**

- Sample Analysis objects (various states)
- Sample AsyncResult objects

**COVERAGE TARGET:** 100% of API routes

---

### Phase 10: Frontend Tests (Minimal, Optional)

**FILE:** `tests/test_routes.py`

#### GET / Route

**Test:** Returns 200 OK

**Test:** Returns HTML with form

**Test:** Form has artist input field

**Test:** Form has submit button

#### GET /results/<job_id> Route

**Test:** Returns 200 OK

**Test:** Returns HTML page

**Test:** Passes job_id to template

#### GET /health Route

**Test:** Returns `{status: ok}`

**Test:** Returns 200

**COVERAGE TARGET:** 100% of routes

---

### Phase 11: Integration Tests

**FILE:** `tests/integration/test_full_pipeline.py`

#### End-to-End Pipeline (with real models, mocked API)

**Test:** `analyze_artist_async()` full execution

- Mock only Genius API
- Use real: preprocess, LDA, sentiment, bonus
- Verify results structure correct
- Verify database records created

**Test:** Results quality

- LDA topics are coherent
- Sentiment scores reasonable
- Word frequency sorted correctly
- Metaphors counted correctly

**FILE:** `tests/integration/test_api_workflow.py`

#### API Workflow (Real Flask app, mocked Celery)

**Test:** Submit → Check Status → Get Results

- POST /api/analyze returns job_id
- GET /api/analyze/<job_id> returns processing
- (Mock task completion)
- GET /api/analyze/<job_id> returns completed
- GET /api/results/<job_id> returns full results

**Test:** Caching workflow

- Submit same artist twice
- Second request returns immediately

**Test:** Error workflow

- Submit artist with no songs
- Task fails
- Status endpoint shows failed
- Error message provided

**COVERAGE TARGET:** 90% of integration

---

## TESTING INFRASTRUCTURE

### pytest.ini

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = --cov=. --cov-report=html --cov-report=term-missing --cov-fail-under=80
markers =
    unit: unit tests
    integration: integration tests
    slow: slow running tests
```

### conftest.py Fixtures

- `app` (Flask app with test config)
- `client` (Flask test client)
- `db_session` (database session)
- `celery_app` (Celery test app)
- `sample_songs` (fixture data)
- `sample_analysis` (fixture data)

### factories.py

- `AnalysisFactory` (creates test Analysis objects)
- `SongFactory` (creates test Song objects)
- `TopicFactory` (creates test Topic objects)

### requirements-test.txt

```
pytest==7.4.0
pytest-cov==4.1.0
pytest-mock==3.11.0
pytest-asyncio==0.21.0
factory-boy==3.3.0
responses==0.23.0
faker==19.0.0
```

---

## TEST EXECUTION

### Run all tests:

```bash
pytest
```

### Run with coverage:

```bash
pytest --cov=. --cov-report=html
```

### Run specific test file:

```bash
pytest tests/test_models.py
```

### Run specific test:

```bash
pytest tests/test_models.py::TestAnalysis::test_create
```

### Run by marker:

```bash
pytest -m unit
pytest -m integration
```

### Watch mode (optional):

```bash
pytest-watch
```

---

## CORE ARCHITECTURE

### TECH STACK

- Backend: Python (Flask, Celery, SQLAlchemy)
- Database: PostgreSQL
- Message Broker: Redis
- Frontend: HTML/CSS/JavaScript (Vanilla)
- Testing: pytest, pytest-cov, factory-boy, responses
- Deployment: Docker + Render
- API: Genius API for lyrics scraping

### DATABASE SCHEMA

**analyses:**

- id (PK)
- artist_name (unique, indexed)
- job_id (unique, indexed)
- status (queued, processing, completed, failed)
- progress (text)
- results (JSON)
- error_message (text)
- created_at (datetime)
- completed_at (datetime, nullable)

**songs:**

- id (PK)
- analysis_id (FK)
- artist_name (indexed)
- title
- album (nullable)
- year (nullable)
- lyrics (text)
- topic_id (nullable)
- sentiment_score (float, nullable)
- created_at (datetime)

**topics:**

- id (PK)
- analysis_id (FK)
- topic_id (int)
- name (nullable)
- keywords (JSON)
- weight (float)

---

## API ENDPOINTS

### POST /api/analyze

**Input:**

```json
{
  "artist_name": "The Cure"
}
```

**Returns:**

```json
{
  "job_id": "abc-123-def",
  "status": "queued",
  "artist": "The Cure"
}
```

**Status Code:** 202 Accepted

---

### GET /api/analyze/<job_id>

**Returns:**

```json
{
  "job_id": "abc-123-def",
  "status": "processing",
  "progress": "Running LDA analysis...",
  "artist": "The Cure"
}
```

**Status Code:** 200 OK

---

### GET /api/results/<job_id>

**Returns:**

```json
{
  "artist": "The Cure",
  "results": {
    "topics": [...],
    "sentiment": {...},
    "word_frequency": [...],
    "metaphors": [...]
  },
  "completed_at": "2025-01-15T10:30:00"
}
```

**Status Code:** 200 OK

---

### GET /health

**Returns:**

```json
{
  "status": "ok",
  "database": "connected"
}
```

**Status Code:** 200 OK

---

## PIPELINE STAGES

1. **Scraping:** Pull all songs + lyrics from Genius API
2. **Preprocessing:** Tokenize, remove stopwords, stem words
3. **LDA:** Discover 5-8 hidden themes using Gensim
4. **Sentiment:** Analyze emotion by album/year using TextBlob
5. **Bonus 1 - Word Frequency:** Top 50 most common words
6. **Bonus 2 - Metaphors:** Track recurring themes

---

## RESULTS FORMAT

```json
{
  "artist": "The Cure",
  "songs_count": 150,
  "topics": [
    {
      "id": 0,
      "name": "Theme 1",
      "keywords": {
        "word1": 0.045,
        "word2": 0.032
      },
      "weight": 0.15
    }
  ],
  "sentiment": {
    "by_album": [
      {
        "album": "Disintegration",
        "score": -0.3,
        "song_count": 12
      }
    ],
    "by_year": [
      {
        "year": 1989,
        "score": -0.25,
        "song_count": 12
      }
    ],
    "overall": -0.18
  },
  "word_frequency": [
    {
      "word": "love",
      "frequency": 142
    },
    {
      "word": "night",
      "frequency": 98
    }
  ],
  "metaphors": [
    {
      "metaphor": "death",
      "frequency": 45
    },
    {
      "metaphor": "love",
      "frequency": 156
    }
  ],
  "timestamp": "2025-01-15T10:30:00"
}
```

---

## FRONTEND UX

### Home Page

- Large title + subtitle
- Artist name input field
- Submit button
- Loading spinner during analysis

### Results Page

- Artist name heading
- Status + progress text (polling every 2 seconds)
- Once complete, show tabs/cards:
  - Topics: Bar chart of discovered themes
  - Sentiment: Line chart of emotion over time
  - Word Frequency: Bar chart of top 15 words
  - Metaphors: List of recurring themes with counts
- Back button to analyze another artist

---

## ENVIRONMENT VARIABLES

```
FLASK_ENV=production
DATABASE_URL=postgresql://user:password@host:port/dbname
REDIS_URL=redis://host:port/0
SECRET_KEY=secure_random_key
PORT=5000
```

---

## DOCKER DEPLOYMENT

- **Dockerfile:** Multi-stage build, optimized layers
- **docker-compose.yml:** Web, Celery worker, PostgreSQL, Redis
- **entrypoint.sh:** Handle migrations before starting
- Deploy to Render with `render.yaml`

---

## RENDER SERVICES

### 1. Web Service (Python 3.11, Docker)

- Start command: `gunicorn app:create_app() --bind 0.0.0.0:5000 --workers 4`
- Health check: `/health`

### 2. Background Worker (Python 3.11, Docker)

- Start command: `celery -A celery_app worker --loglevel=info`

### 3. PostgreSQL Database

- Version 15
- Standard plan

### 4. Redis Instance

- Standard plan

---

## ADDITIONAL FEATURES

- Result caching (no re-analysis of same artist)
- Error handling with user-friendly messages
- Database health checks
- Logging throughout pipeline
- Rate limiting for Genius API
- Optional: Celery Beat for scheduled tasks
- Optional: Sentry integration for error tracking

---

## TESTING WORKFLOW (TDD)

1. Write test for feature
2. Run test (should fail - RED)
3. Write minimal code to pass test (GREEN)
4. Refactor code (REFACTOR)
5. Repeat for next test
6. Run full test suite: `pytest --cov`
7. Ensure coverage >= 80%
8. Commit with test results

---

## SUCCESS CRITERIA

- ✅ All unit tests pass (80%+ coverage)
- ✅ All integration tests pass
- ✅ No failing tests on CI/CD
- ✅ Scrape 100+ songs for any artist
- ✅ Discover 5-8 coherent themes via LDA
- ✅ Calculate sentiment timeline
- ✅ Track word frequencies and metaphors
- ✅ Web interface with real-time polling
- ✅ Async task processing (no blocking)
- ✅ Result caching for speed
- ✅ Docker containerization working
- ✅ Deployed and accessible on Render
- ✅ All error states handled gracefully

---

## FUTURE ENHANCEMENTS

- E2E tests with Selenium/Playwright
- Load testing with locust
- Performance profiling
- API benchmarking
- Mutation testing (mutmut)
- Batch artist analysis
- Export results to PDF
- Artist comparison
- User accounts and history
- Mobile app
- Social sharing
