"""Celery tasks for async analysis pipeline."""

import logging
from datetime import datetime

from celery_app import celery
from celery.exceptions import SoftTimeLimitExceeded
from database import db

logger = logging.getLogger(__name__)


# Exceptions that should trigger automatic retry
RETRIABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,  # Network errors
)


@celery.task(
    bind=True,
    name='pipeline.tasks.analyze_artist_async',
    autoretry_for=RETRIABLE_EXCEPTIONS,
    retry_kwargs={'max_retries': 3},
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def analyze_artist_async(self, artist_name: str, analysis_id: int):
    """
    Async task to analyze an artist's lyrics.

    Args:
        artist_name: Name of the artist to analyze
        analysis_id: ID of the Analysis record

    Returns:
        Analysis results dict
    """
    from app import create_app
    from models import Analysis, Song, Topic
    from pipeline.scraper import scrape_genius, ScraperError
    from pipeline.preprocessor import preprocess_lyrics
    from pipeline.lda_analyzer import run_lda, assign_topics_to_songs
    from pipeline.sentiment_analyzer import run_sentiment
    from pipeline.bonus_analyzer import analyze_word_frequency, analyze_metaphors, analyze_vocabulary_richness

    app = create_app()

    with app.app_context():
        analysis = Analysis.query.get(analysis_id)
        if not analysis:
            logger.error(f"Analysis {analysis_id} not found")
            return None

        try:
            # Stage 1: Scraping
            self.update_state(state='PROGRESS', meta={'progress': 'Scraping lyrics from Genius...'})
            analysis.update_status('processing', 'Scraping lyrics from Genius...')

            songs_data = scrape_genius(artist_name)

            if not songs_data:
                analysis.mark_failed(f"No songs found for artist: {artist_name}")
                return {'error': 'No songs found'}

            # Stage 2: Preprocessing
            self.update_state(state='PROGRESS', meta={'progress': 'Preprocessing lyrics...'})
            analysis.update_status('processing', 'Preprocessing lyrics...')

            processed_songs = preprocess_lyrics(songs_data)

            # Stage 3: LDA Analysis
            self.update_state(state='PROGRESS', meta={'progress': 'Running LDA topic analysis...'})
            analysis.update_status('processing', 'Running LDA topic analysis...')

            topics = run_lda(processed_songs)

            # Assign topics to songs
            processed_songs = assign_topics_to_songs(processed_songs)

            # Stage 4: Sentiment Analysis
            self.update_state(state='PROGRESS', meta={'progress': 'Analyzing sentiment...'})
            analysis.update_status('processing', 'Analyzing sentiment...')

            sentiment_results = run_sentiment(processed_songs)
            processed_songs = sentiment_results['songs']

            # Stage 5: Bonus Analyses
            self.update_state(state='PROGRESS', meta={'progress': 'Running bonus analyses...'})
            analysis.update_status('processing', 'Running bonus analyses...')

            word_frequency = analyze_word_frequency(processed_songs)
            metaphors = analyze_metaphors(processed_songs)

            # Stage 6: Save to Database
            self.update_state(state='PROGRESS', meta={'progress': 'Saving results...'})
            analysis.update_status('processing', 'Saving results...')

            # Save songs
            for song_data in processed_songs:
                Song.create(
                    analysis_id=analysis_id,
                    artist_name=artist_name,
                    title=song_data.get('title', ''),
                    album=song_data.get('album'),
                    year=song_data.get('year'),
                    lyrics=song_data.get('lyrics'),
                    topic_id=song_data.get('topic_id'),
                    sentiment_score=song_data.get('sentiment_score')
                )

            # Save topics
            for topic_data in topics:
                Topic.create(
                    analysis_id=analysis_id,
                    topic_id=topic_data['id'],
                    name=topic_data.get('name'),
                    keywords=topic_data.get('keywords'),
                    weight=topic_data.get('weight')
                )

            # Compile results
            results = {
                'artist': artist_name,
                'songs_count': len(processed_songs),
                'topics': topics,
                'sentiment': {
                    'by_album': sentiment_results['by_album'],
                    'by_year': sentiment_results['by_year'],
                    'overall': sentiment_results['overall']
                },
                'word_frequency': word_frequency[:15],  # Top 15 for display
                'metaphors': metaphors,
                'timestamp': datetime.utcnow().isoformat()
            }

            # Save results to analysis
            analysis.set_results(results)

            logger.info(f"Analysis completed for {artist_name}")
            return results

        except ScraperError as e:
            logger.error(f"Scraper error for {artist_name}: {e}")
            analysis.mark_failed(f"Failed to scrape lyrics: {str(e)}")
            return {'error': str(e)}

        except Exception as e:
            logger.error(f"Analysis failed for {artist_name}: {e}")
            analysis.mark_failed(f"Analysis failed: {str(e)}")
            return {'error': str(e)}


@celery.task(
    bind=True,
    name='pipeline.tasks.analyze_album_async',
    autoretry_for=RETRIABLE_EXCEPTIONS,
    retry_kwargs={'max_retries': 3},
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def analyze_album_async(self, album_id: int, album_name: str, analysis_id: int, artist_name: str = None):
    """
    Async task to analyze a single album's lyrics.

    Args:
        album_id: Discogs master/release ID
        album_name: Name of the album
        analysis_id: ID of the Analysis record
        artist_name: Name of the artist (for Genius search)

    Returns:
        Analysis results dict
    """
    from app import create_app
    from models import Analysis, Song, Topic
    from pipeline.scraper import scrape_album, ScraperError
    from pipeline.preprocessor import preprocess_lyrics
    from pipeline.lda_analyzer import run_lda, assign_topics_to_songs
    from pipeline.sentiment_analyzer import run_sentiment
    from pipeline.bonus_analyzer import analyze_word_frequency, analyze_metaphors, analyze_vocabulary_richness

    app = create_app()

    with app.app_context():
        analysis = Analysis.query.get(analysis_id)
        if not analysis:
            logger.error(f"Analysis {analysis_id} not found")
            return None

        try:
            # Get artist name from analysis if not provided
            if not artist_name:
                artist_name = analysis.artist_name

            # Stage 1: Scraping
            logger.info(f"========== STAGE 1/6: SCRAPING ==========")
            self.update_state(state='PROGRESS', meta={'progress': 'Fetching lyrics...'})
            analysis.update_status('processing', 'Fetching lyrics...')

            # Progress callback to update status during scraping
            def scraping_progress(current, total, title):
                progress_msg = f'Fetching lyrics ({current}/{total}): {title}'
                self.update_state(state='PROGRESS', meta={'progress': progress_msg})
                analysis.update_status('processing', progress_msg)

            # Use Discogs for tracks, multiple sources for lyrics
            songs_data = scrape_album(album_id, album_name, artist_name, progress_callback=scraping_progress)

            if not songs_data:
                analysis.mark_failed(f"No songs found for album: {album_name}")
                return {'error': 'No songs found'}

            # Stage 2: Preprocessing
            logger.info(f"========== STAGE 2/6: PREPROCESSING ==========")
            self.update_state(state='PROGRESS', meta={'progress': 'Preprocessing lyrics...'})
            analysis.update_status('processing', 'Preprocessing lyrics...')

            processed_songs = preprocess_lyrics(songs_data)

            # Stage 3: LDA Analysis
            logger.info(f"========== STAGE 3/6: LDA TOPIC MODELING ==========")
            self.update_state(state='PROGRESS', meta={'progress': 'Running LDA topic analysis...'})
            analysis.update_status('processing', 'Running LDA topic analysis...')

            topics = run_lda(processed_songs)

            # Assign topics to songs
            processed_songs = assign_topics_to_songs(processed_songs)

            # Stage 4: Sentiment Analysis
            logger.info(f"========== STAGE 4/6: SENTIMENT ANALYSIS ==========")
            self.update_state(state='PROGRESS', meta={'progress': 'Analyzing sentiment...'})
            analysis.update_status('processing', 'Analyzing sentiment...')

            sentiment_results = run_sentiment(processed_songs)
            processed_songs = sentiment_results['songs']

            # Stage 5: Bonus Analyses
            logger.info(f"========== STAGE 5/6: BONUS ANALYSES ==========")
            self.update_state(state='PROGRESS', meta={'progress': 'Running bonus analyses...'})
            analysis.update_status('processing', 'Running bonus analyses...')

            word_frequency = analyze_word_frequency(processed_songs)
            metaphors = analyze_metaphors(processed_songs)
            vocab_stats = analyze_vocabulary_richness(processed_songs)

            # Stage 6: Save to Database
            logger.info(f"========== STAGE 6/6: SAVING RESULTS ==========")
            self.update_state(state='PROGRESS', meta={'progress': 'Saving results...'})
            analysis.update_status('processing', 'Saving results...')

            # Save songs
            logger.info(f"Saving {len(processed_songs)} songs to database...")
            for song_data in processed_songs:
                Song.create(
                    analysis_id=analysis_id,
                    artist_name=artist_name,
                    title=song_data.get('title', ''),
                    album=song_data.get('album'),
                    year=song_data.get('year'),
                    lyrics=song_data.get('lyrics'),
                    topic_id=song_data.get('topic_id'),
                    sentiment_score=song_data.get('sentiment_score')
                )

            # Save topics
            logger.info(f"Saving {len(topics)} topics to database...")
            for topic_data in topics:
                Topic.create(
                    analysis_id=analysis_id,
                    topic_id=topic_data['id'],
                    name=topic_data.get('name'),
                    keywords=topic_data.get('keywords'),
                    weight=topic_data.get('weight')
                )

            # Build song sentiment list (preserve album track order)
            songs_sentiment = [
                {'title': s.get('title', 'Unknown'), 'score': s.get('sentiment_score', 0)}
                for s in processed_songs
            ]

            # Find most positive and most negative songs
            most_positive = max(songs_sentiment, key=lambda x: x['score']) if songs_sentiment else None
            most_negative = min(songs_sentiment, key=lambda x: x['score']) if songs_sentiment else None

            # Compile results
            results = {
                'artist': artist_name,
                'album': album_name,
                'songs_count': len(processed_songs),
                'topics': topics,
                'sentiment': {
                    'by_song': songs_sentiment,
                    'overall': sentiment_results['overall']
                },
                'word_frequency': word_frequency[:15],
                'metaphors': metaphors,
                'stats': {
                    'total_words': vocab_stats['total_words'],
                    'unique_words': vocab_stats['unique_words'],
                    'vocabulary_richness': vocab_stats['vocabulary_richness'],
                    'most_positive': most_positive,
                    'most_negative': most_negative
                },
                'timestamp': datetime.utcnow().isoformat()
            }

            # Save results to analysis
            analysis.set_results(results)

            logger.info(f"========== ANALYSIS COMPLETE ==========")
            logger.info(f"Album: {album_name} | Songs: {len(processed_songs)} | Topics: {len(topics)}")
            return results

        except ScraperError as e:
            logger.error(f"Scraper error for album {album_name}: {e}")
            analysis.mark_failed(f"Failed to scrape lyrics: {str(e)}")
            return {'error': str(e)}

        except Exception as e:
            logger.error(f"Analysis failed for album {album_name}: {e}")
            analysis.mark_failed(f"Analysis failed: {str(e)}")
            return {'error': str(e)}
