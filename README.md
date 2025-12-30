# Artist Lyrical Analyzer

A web application that analyzes song lyrics to discover hidden themes, track sentiment evolution, and reveal lyrical patterns using NLP techniques.

## Features

- **Topic Discovery**: Uses LDA (Latent Dirichlet Allocation) to uncover 5-8 hidden themes in album lyrics
- **Sentiment Analysis**: Tracks emotional tone across songs using TextBlob
- **Word Frequency**: Identifies most common words and vocabulary richness
- **Metaphor Detection**: Finds recurring metaphorical themes (love, darkness, nature, etc.)
- **Winamp-inspired UI**: Retro aesthetic with modern responsive design

## Tech Stack

### Backend
- **Flask** - Web framework
- **Celery + Redis** - Async task processing for long-running analyses
- **PostgreSQL** - Database for storing analysis results
- **Gensim** - LDA topic modeling
- **TextBlob/NLTK** - Sentiment analysis and text preprocessing

### Data Sources
- **Discogs API** - Artist and album metadata, tracklists
- **Musixmatch API** - Primary lyrics source (optional, best coverage)
- **lyrics.ovh** - Free lyrics API fallback
- **Genius** - Song search and lyrics scraping fallback

### Infrastructure
- **Docker Compose** - Container orchestration
- **Gunicorn** - Production WSGI server
- **Redis** - Task queue and caching

## Prerequisites

- Docker and Docker Compose
- Discogs API token ([get one here](https://www.discogs.com/settings/developers))
- Musixmatch API key (optional, [get one here](https://developer.musixmatch.com/))
- Genius API token ([get one here](https://genius.com/api-clients))

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd artist-analyzer
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   ```

3. **Configure environment variables**
   ```env
   # API Keys (Musixmatch optional but recommended)
   DISCOGS_API_TOKEN=your_discogs_token
   MUSIXMATCH_API_KEY=your_musixmatch_key
   GENIUS_API_TOKEN=your_genius_token

   # Security
   SECRET_KEY=your_secret_key_here
   DB_PASSWORD=your_db_password
   REDIS_PASSWORD=your_redis_password

   # Optional
   CORS_ORIGINS=*
   ```

4. **Start the application**
   ```bash
   docker compose up --build
   ```

5. **Access the app**
   Open http://localhost:5000 in your browser

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Browser   │────▶│  Flask Web  │────▶│  PostgreSQL │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐     ┌─────────────┐
                    │   Celery    │────▶│    Redis    │
                    │   Worker    │     │             │
                    └─────────────┘     └─────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
   ┌──────────┐     ┌────────────┐     ┌──────────┐
   │ Discogs  │     │  Lyrics    │     │   NLP    │
   │   API    │     │   APIs     │     │ Pipeline │
   └──────────┘     └────────────┘     └──────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         Musixmatch   lyrics.ovh    Genius
```

## Analysis Pipeline

1. **Search**: User searches for an artist via Discogs API
2. **Select**: User selects an album from the discography
3. **Fetch Lyrics**: Celery worker fetches lyrics using multiple sources:
   - Musixmatch API (best coverage, if configured)
   - lyrics.ovh API (free fallback)
   - Genius scraping (last resort)
4. **Preprocess**: Lyrics are tokenized, stemmed, and cleaned
5. **Analyze**:
   - LDA discovers latent topics
   - TextBlob calculates sentiment scores
   - Word frequency and metaphors are extracted
6. **Display**: Results shown with interactive visualizations

## Project Structure

```
artist-analyzer/
├── app.py                 # Flask application factory
├── celery_app.py          # Celery configuration
├── config.py              # Environment configuration
├── database.py            # SQLAlchemy setup
├── models.py              # Database models
├── pipeline/
│   ├── scraper.py         # Multi-source lyrics fetching
│   ├── discogs_client.py  # Discogs API wrapper
│   ├── preprocessor.py    # Text preprocessing
│   ├── lda_analyzer.py    # Topic modeling
│   ├── sentiment_analyzer.py
│   ├── bonus_analyzer.py  # Word freq & metaphors
│   └── tasks.py           # Celery tasks
├── routes/
│   ├── api.py             # REST API endpoints
│   └── web.py             # HTML page routes
├── templates/             # Jinja2 templates
├── static/
│   ├── style.css          # Winamp-inspired styles
│   ├── script.js          # Home page JavaScript
│   └── results.js         # Results page JavaScript
├── tests/                 # Test suite
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/artists/search?q=<name>` | Search for an artist |
| GET | `/api/artists/<id>/albums` | Get albums with pagination |
| POST | `/api/analyze` | Submit album for analysis |
| GET | `/api/analyze/<job_id>` | Check analysis status |
| GET | `/api/results/<job_id>` | Get analysis results |
| GET | `/api/health` | Health check |

## Development

### Local Development (without Docker)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download NLTK data
python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords'); nltk.download('wordnet')"

# Set environment variables
export FLASK_ENV=development
export DISCOGS_API_TOKEN=your_token
export MUSIXMATCH_API_KEY=your_key
export GENIUS_API_TOKEN=your_token

# Run Flask
flask run

# In another terminal, run Celery worker
celery -A celery_app.celery worker --loglevel=info
```

### Running Tests

```bash
pytest tests/ -v
```

## Security Features

- CSRF protection on web forms
- Rate limiting on API endpoints
- Input sanitization with Bleach
- Security headers via Flask-Talisman (production)
- Sensitive data filtering in logs

## Deployment

The application is designed for deployment on platforms like Render, Railway, or any Docker-compatible host.

### Environment Variables for Production

```env
FLASK_ENV=production
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
DISCOGS_API_TOKEN=...
MUSIXMATCH_API_KEY=...
GENIUS_API_TOKEN=...
SECRET_KEY=...
CORS_ORIGINS=https://yourdomain.com
FORCE_HTTPS=true
```

## Limitations

- English lyrics only (sentiment analysis optimized for English)
- Lyrics availability depends on coverage across Musixmatch, lyrics.ovh, and Genius
- Rate limits apply to external APIs
- Some cloud providers may be blocked by Genius scraping

## License

MIT License
