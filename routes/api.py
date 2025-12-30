"""REST API endpoints with security measures."""

import re
import logging
from flask import Blueprint, request, jsonify, current_app
import bleach

from database import check_db_health
from models import Analysis

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__, url_prefix='/api')

# Input validation constants
MAX_ARTIST_NAME_LENGTH = 200

# Stage mapping for progress tracking
TOTAL_STAGES = 6
STAGE_KEYWORDS = [
    ('Fetching', 1),
    ('Scraping', 1),
    ('Preprocessing', 2),
    ('LDA', 3),
    ('sentiment', 4),
    ('bonus', 5),
    ('Saving', 6),
]


def get_stage_from_progress(progress):
    """Extract stage number from progress message."""
    if not progress:
        return 0
    progress_lower = progress.lower()
    for keyword, stage in STAGE_KEYWORDS:
        if keyword.lower() in progress_lower:
            return stage
    return 0


def get_sub_progress(progress):
    """Extract sub-progress from messages like 'Fetching lyrics (5/12): title'."""
    if not progress:
        return None, None
    # Look for pattern like (5/12)
    match = re.search(r'\((\d+)/(\d+)\)', progress)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None, None


ARTIST_NAME_PATTERN = re.compile(r'^[\w\s\-\.\'\&]+$', re.UNICODE)


def sanitize_input(text):
    """Sanitize user input to prevent XSS."""
    if not text:
        return ''
    # Strip HTML tags and limit length
    cleaned = bleach.clean(text, tags=[], strip=True)
    return cleaned.strip()


def validate_artist_name(name):
    """Validate artist name input."""
    if not name:
        return None, 'artist_name is required'

    if len(name) > MAX_ARTIST_NAME_LENGTH:
        return None, f'artist_name must be less than {MAX_ARTIST_NAME_LENGTH} characters'

    # Allow letters, numbers, spaces, hyphens, periods, apostrophes, ampersands
    if not ARTIST_NAME_PATTERN.match(name):
        return None, 'artist_name contains invalid characters'

    return name, None


def get_rate_limiter():
    """Get rate limiter from current app."""
    return getattr(current_app, 'limiter', None)


@api_bp.route('/artists/search', methods=['GET'])
def search_artists():
    """
    Search for an artist and return their albums with pagination.

    Query params:
        q: Artist name to search
        page: Page number (default: 1)

    Returns:
        {artist_id, artist_name, albums: [...], has_more, total, page}
    """
    query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    if not query:
        return jsonify({'error': 'Search query required'}), 400

    if page < 1:
        page = 1

    # Sanitize and validate
    query = sanitize_input(query)
    query, error = validate_artist_name(query)

    if error:
        return jsonify({'error': error}), 400

    try:
        from pipeline.scraper import search_artist_albums

        result = search_artist_albums(query, page=page, per_page=20)

        if not result:
            return jsonify({'error': 'Artist not found'}), 404

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error searching artists: {type(e).__name__}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/artists/<int:artist_id>/albums', methods=['GET'])
def get_artist_albums(artist_id):
    """
    Get albums for an artist by ID (for pagination).

    Query params:
        page: Page number (default: 1)
        artist_name: Artist name for response

    Returns:
        {artist_id, artist_name, albums: [...], has_more, total, page}
    """
    page = request.args.get('page', 1, type=int)
    artist_name = request.args.get('artist_name', '')

    if page < 1:
        page = 1

    try:
        from pipeline.scraper import get_artist_albums_by_id

        result = get_artist_albums_by_id(artist_id, artist_name, page=page, per_page=20)

        if not result:
            return jsonify({'error': 'Failed to fetch albums'}), 500

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error getting artist albums: {type(e).__name__}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/analyze', methods=['POST'])
def submit_analysis():
    """
    Submit an album for analysis.

    Request body:
        {artist_name: "Artist Name", album_id: 123, album_name: "Album Name"}

    Returns:
        {job_id, status, artist, album}
    """
    # Apply rate limit: 10 submissions per minute (skip if limiter disabled)
    limiter = get_rate_limiter()
    if limiter and limiter.enabled:
        limiter.limit("10 per minute")(lambda: None)()

    try:
        data = request.get_json(silent=True)

        if not data:
            return jsonify({'error': 'Request body required'}), 400

        # Sanitize and validate input
        raw_artist_name = data.get('artist_name', '')
        artist_name = sanitize_input(raw_artist_name)
        artist_name, error = validate_artist_name(artist_name)

        if error:
            return jsonify({'error': error}), 400

        # Get album info
        album_id = data.get('album_id')
        album_name = sanitize_input(data.get('album_name', ''))

        if not album_id:
            return jsonify({'error': 'album_id is required'}), 400

        # Check for existing analysis for this artist + album
        existing = Analysis.get_by_artist_album(artist_name, album_id)

        if existing:
            if existing.status == 'completed':
                return jsonify({
                    'job_id': existing.job_id,
                    'status': 'completed',
                    'artist': artist_name,
                    'album': album_name,
                    'cached': True
                }), 200

            # Check if stuck (queued/processing for more than 10 minutes)
            from datetime import datetime, timedelta
            is_stuck = False
            if existing.status in ('queued', 'processing'):
                if existing.created_at:
                    age = datetime.utcnow() - existing.created_at
                    is_stuck = age > timedelta(minutes=10)

            if existing.status in ('queued', 'processing') and not is_stuck:
                return jsonify({
                    'job_id': existing.job_id,
                    'status': existing.status,
                    'artist': artist_name,
                    'album': album_name
                }), 202

            # If failed or stuck, allow retry by deleting old record
            if existing.status == 'failed' or is_stuck:
                from database import db
                logger.info(f"Deleting {'stuck' if is_stuck else 'failed'} analysis {existing.id}")
                db.session.delete(existing)
                db.session.commit()

        # Create new analysis
        analysis = Analysis.create(artist_name, album_id=album_id, album_name=album_name)

        # Queue Celery task (pass artist_name for Genius search)
        from pipeline.tasks import analyze_album_async
        logger.info(f"Sending task to Celery for analysis_id={analysis.id}")
        try:
            task = analyze_album_async.delay(album_id, album_name, analysis.id, artist_name)
            logger.info(f"Task sent successfully, task.id={task.id}")
        except Exception as celery_error:
            logger.error(f"Failed to send Celery task: {celery_error}")
            raise

        # Update analysis with job ID
        analysis.job_id = task.id
        from database import db
        db.session.commit()

        # Log without sensitive data
        logger.info(f"Queued analysis for album with job_id {task.id}")

        return jsonify({
            'job_id': task.id,
            'status': 'queued',
            'artist': artist_name,
            'album': album_name
        }), 202

    except Exception as e:
        logger.error(f"Error submitting analysis: {type(e).__name__}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/analyze/<job_id>', methods=['GET'])
def get_analysis_status(job_id):
    """
    Get the status of an analysis.

    Note: This endpoint is exempt from rate limiting since it's polled frequently.

    Returns:
        {job_id, status, progress, artist}
    """
    # Skip rate limiting for status checks (handled by exemption in app.py)
    # Validate job_id format (UUID-like)
    if not job_id or len(job_id) > 50 or not re.match(r'^[\w\-]+$', job_id):
        return jsonify({'error': 'Invalid job_id format'}), 400

    try:
        analysis = Analysis.get_by_job_id(job_id)

        if not analysis:
            return jsonify({'error': 'Analysis not found'}), 404

        response = {
            'job_id': job_id,
            'status': analysis.status,
            'artist': analysis.artist_name,
            'album': analysis.album_name,
            'total_stages': TOTAL_STAGES
        }

        if analysis.progress:
            response['progress'] = analysis.progress
            response['stage'] = get_stage_from_progress(analysis.progress)
            # Include sub-progress for granular updates during fetching
            sub_current, sub_total = get_sub_progress(analysis.progress)
            if sub_current is not None:
                response['sub_current'] = sub_current
                response['sub_total'] = sub_total
        else:
            response['stage'] = 0

        if analysis.status == 'completed':
            response['stage'] = TOTAL_STAGES
            if analysis.results:
                response['results'] = analysis.results

        if analysis.status == 'failed' and analysis.error_message:
            # Sanitize error message before returning
            response['error'] = sanitize_input(analysis.error_message)[:200]
            return jsonify(response), 400

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error getting analysis status: {type(e).__name__}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/results/<job_id>', methods=['GET'])
def get_results(job_id):
    """
    Get full analysis results.

    Returns:
        {artist, results, completed_at}
    """
    # Validate job_id format
    if not job_id or len(job_id) > 50 or not re.match(r'^[\w\-]+$', job_id):
        return jsonify({'error': 'Invalid job_id format'}), 400

    try:
        analysis = Analysis.get_by_job_id(job_id)

        if not analysis:
            return jsonify({'error': 'Analysis not found'}), 404

        if analysis.status != 'completed':
            return jsonify({
                'job_id': job_id,
                'status': analysis.status,
                'message': 'Analysis not yet completed'
            }), 202

        return jsonify({
            'artist': analysis.artist_name,
            'results': analysis.results,
            'completed_at': analysis.completed_at.isoformat() if analysis.completed_at else None
        }), 200

    except Exception as e:
        logger.error(f"Error getting results: {type(e).__name__}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint.

    Returns:
        {status, database}
    """
    db_healthy = check_db_health()

    return jsonify({
        'status': 'ok' if db_healthy else 'degraded',
        'database': 'connected' if db_healthy else 'disconnected'
    }), 200 if db_healthy else 503
