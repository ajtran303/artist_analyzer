# Deployment Guide

## Deploy to Render

### Prerequisites

1. A [Render](https://render.com) account
2. A [Discogs API token](https://www.discogs.com/settings/developers)
3. (Optional) A [Musixmatch API key](https://developer.musixmatch.com/) for better lyrics coverage
4. This repository pushed to GitHub/GitLab

### Option 1: Blueprint (Recommended)

The easiest way to deploy. Render will automatically create all services.

1. **Fork/Push this repo** to your GitHub or GitLab account

2. **Go to Render Dashboard** → [Blueprints](https://dashboard.render.com/blueprints)

3. **Click "New Blueprint Instance"**

4. **Connect your repository** and select the branch to deploy

5. **Render will detect `render.yaml`** and show the services to be created:
   - `artist-analyzer-web` (Web Service)
   - `artist-analyzer-worker` (Background Worker)
   - `artist-analyzer-redis` (Redis)
   - `artist-analyzer-db` (PostgreSQL)

6. **Set environment variables** when prompted:
   - `DISCOGS_API_TOKEN` - Required, get from [Discogs Developer Settings](https://www.discogs.com/settings/developers)
   - `MUSIXMATCH_API_KEY` - Optional but recommended for better lyrics coverage

7. **Click "Apply"** and wait for deployment (~5-10 minutes)

8. **Access your app** at the URL provided (e.g., `https://artist-analyzer-web.onrender.com`)

### Option 2: Manual Setup

If you prefer to create services individually:

#### 1. Create PostgreSQL Database

- Go to **Dashboard → New → PostgreSQL**
- Name: `artist-analyzer-db`
- Database: `artist_analyzer`
- User: `analyzer_user`
- Plan: Starter (or higher)
- Click **Create Database**
- Copy the **Internal Connection String**

#### 2. Create Redis Instance

- Go to **Dashboard → New → Redis**
- Name: `artist-analyzer-redis`
- Plan: Starter
- Click **Create Redis**
- Copy the **Internal Connection String**

#### 3. Create Web Service

- Go to **Dashboard → New → Web Service**
- Connect your repository
- Settings:
  - Name: `artist-analyzer-web`
  - Runtime: Docker
  - Plan: Starter (or higher)
- Environment Variables:
  ```
  FLASK_ENV=production
  SECRET_KEY=<click Generate>
  DISCOGS_API_TOKEN=<your token>
  MUSIXMATCH_API_KEY=<your key>  # Optional
  DATABASE_URL=<postgres internal connection string>
  REDIS_URL=<redis internal connection string>
  FORCE_HTTPS=false
  ```
- Docker Command:
  ```
  gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --access-logfile - --error-logfile - --log-level info --max-requests 1000
  ```
- Health Check Path: `/api/health`
- Click **Create Web Service**

#### 4. Create Worker Service

- Go to **Dashboard → New → Background Worker**
- Connect the same repository
- Settings:
  - Name: `artist-analyzer-worker`
  - Runtime: Docker
  - Plan: Starter
- Environment Variables: (same as web service)
  ```
  FLASK_ENV=production
  SECRET_KEY=<same as web service>
  DISCOGS_API_TOKEN=<your token>
  MUSIXMATCH_API_KEY=<your key>  # Optional
  DATABASE_URL=<postgres internal connection string>
  REDIS_URL=<redis internal connection string>
  ```
- Docker Command:
  ```
  celery -A celery_app.celery worker --loglevel=info --concurrency=2 --max-tasks-per-child=500
  ```
- Click **Create Background Worker**

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Flask secret key (use Render's "Generate" button) |
| `DISCOGS_API_TOKEN` | Yes | Your Discogs API token for artist/album metadata |
| `MUSIXMATCH_API_KEY` | No | Musixmatch API key for better lyrics coverage |
| `DATABASE_URL` | Yes | PostgreSQL connection string (auto-set by Render) |
| `REDIS_URL` | Yes | Redis connection string (auto-set by Render) |
| `FLASK_ENV` | Yes | Set to `production` |
| `FORCE_HTTPS` | No | Set to `false` (Render handles SSL) |
| `CORS_ORIGINS` | No | Comma-separated allowed origins (default: `*`) |

---

## Post-Deployment

### Verify Deployment

1. **Check Web Service logs** in Render dashboard for startup errors
2. **Visit your app URL** and search for an artist
3. **Check Worker logs** to see analysis tasks running

### Custom Domain (Optional)

1. Go to your Web Service → **Settings → Custom Domains**
2. Add your domain (e.g., `lyrics.yourdomain.com`)
3. Update DNS with the provided CNAME record
4. Render automatically provisions SSL certificate

### Update CORS (If using custom domain)

1. Go to Web Service → **Environment**
2. Update `CORS_ORIGINS` to your domain:
   ```
   CORS_ORIGINS=https://lyrics.yourdomain.com
   ```

---

## Costs (Render Starter Plan)

| Service | Monthly Cost |
|---------|-------------|
| Web Service | $7 |
| Background Worker | $7 |
| PostgreSQL | $7 |
| Redis | $10 |
| **Total** | **~$31/month** |

*Free tier available but services sleep after inactivity*

---

## Troubleshooting

### "No songs found" error
- Check Worker logs - is it running?
- Verify `DISCOGS_API_TOKEN` is set correctly on both web and worker
- If lyrics aren't found, consider adding `MUSIXMATCH_API_KEY` for better coverage

### Analysis stuck at "Starting..."
- Check if Worker service is running
- Check Redis connection in Worker logs

### 502 Bad Gateway
- Check Web Service logs for errors
- Verify `DATABASE_URL` is correct
- Wait for health check to pass (can take 1-2 minutes)

### Database connection errors
- Ensure using **Internal Connection String** (not External)
- Check if database is fully provisioned (can take a few minutes)

---

## Local Development with Docker

```bash
# Copy environment file
cp .env.example .env

# Edit .env with your values
# Required: DISCOGS_API_TOKEN, SECRET_KEY, DB_PASSWORD, REDIS_PASSWORD
# Optional: MUSIXMATCH_API_KEY (recommended for better lyrics coverage)

# Start all services
docker-compose up --build

# Access at http://localhost:5000
```

---

## Architecture

```
┌─────────────────┐     ┌─────────────────┐
│   Web Service   │────▶│    PostgreSQL   │
│  (Flask/Gunicorn)│     │    Database     │
└────────┬────────┘     └─────────────────┘
         │
         │ Submit Task
         ▼
┌─────────────────┐     ┌─────────────────┐
│     Redis       │◀────│  Celery Worker  │
│  (Task Queue)   │     │  (Background)   │
└─────────────────┘     └─────────────────┘
```

1. User submits analysis request → Web service creates task in Redis
2. Celery worker picks up task → Fetches lyrics from Musixmatch/lyrics.ovh, runs NLP pipeline
3. Worker saves results to PostgreSQL
4. Web service polls for completion → Returns results to user
