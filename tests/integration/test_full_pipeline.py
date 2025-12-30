"""Integration tests for full pipeline - Phase 11."""

import pytest
from unittest.mock import patch, MagicMock

from pipeline.preprocessor import preprocess_lyrics
from pipeline.lda_analyzer import run_lda
from pipeline.sentiment_analyzer import run_sentiment
from pipeline.bonus_analyzer import analyze_word_frequency, analyze_metaphors


@pytest.mark.integration
class TestFullPipeline:
    """End-to-end pipeline tests with mocked API."""

    def test_full_pipeline_execution(self):
        """Full pipeline executes with mocked lyrics data."""
        # Simulated scraped songs
        songs = [
            {
                'title': 'Love Song',
                'artist': 'Test Artist',
                'album': 'Album 1',
                'year': 2020,
                'lyrics': 'I love you with all my heart and soul. '
                          'Together forever in the sunshine of love. '
                          'Dreams come true when I am with you.',
                'url': 'http://example.com/1'
            },
            {
                'title': 'Dark Night',
                'artist': 'Test Artist',
                'album': 'Album 1',
                'year': 2020,
                'lyrics': 'In the darkness I wander alone. '
                          'Pain and sorrow fill my soul. '
                          'Death awaits at the end of this lonely road.',
                'url': 'http://example.com/2'
            },
            {
                'title': 'Hope Rising',
                'artist': 'Test Artist',
                'album': 'Album 2',
                'year': 2021,
                'lyrics': 'Tomorrow brings hope and light. '
                          'Dreams can fly on wings of freedom. '
                          'The sun will shine again.',
                'url': 'http://example.com/3'
            },
        ] * 5  # Duplicate to have enough for LDA

        # Step 1: Preprocess
        processed = preprocess_lyrics(songs)
        assert len(processed) == 15
        assert all('tokens' in song for song in processed)
        assert all('text' in song for song in processed)

        # Step 2: LDA Analysis
        topics = run_lda(processed, num_topics=3)
        assert isinstance(topics, list)
        # May have fewer topics than requested with small corpus

        # Step 3: Sentiment Analysis
        sentiment_results = run_sentiment(processed)
        assert 'by_album' in sentiment_results
        assert 'by_year' in sentiment_results
        assert 'overall' in sentiment_results
        assert 'songs' in sentiment_results

        # Step 4: Word Frequency
        word_freq = analyze_word_frequency(processed)
        assert isinstance(word_freq, list)
        if word_freq:
            assert 'word' in word_freq[0]
            assert 'frequency' in word_freq[0]

        # Step 5: Metaphors
        metaphors = analyze_metaphors(songs)  # Use original with lyrics
        assert isinstance(metaphors, list)

    def test_results_quality(self):
        """Results are coherent and reasonable."""
        # Create songs with distinct themes
        happy_songs = [
            {'title': f'Happy {i}', 'lyrics': 'joy happiness love sunshine wonderful amazing'
                                               ' beautiful perfect great excellent'}
            for i in range(5)
        ]
        sad_songs = [
            {'title': f'Sad {i}', 'lyrics': 'sadness pain sorrow tears crying heartbreak'
                                            ' misery suffering agony despair'}
            for i in range(5)
        ]

        all_songs = happy_songs + sad_songs
        processed = preprocess_lyrics(all_songs)

        # Sentiment should show difference
        sentiment = run_sentiment(all_songs)

        # Happy songs should have positive sentiment
        happy_scores = [s['sentiment_score'] for s in sentiment['songs'][:5]]
        sad_scores = [s['sentiment_score'] for s in sentiment['songs'][5:]]

        avg_happy = sum(happy_scores) / len(happy_scores)
        avg_sad = sum(sad_scores) / len(sad_scores)

        # Happy should be more positive than sad
        assert avg_happy > avg_sad

    def test_handles_edge_cases(self):
        """Pipeline handles edge cases gracefully."""
        edge_cases = [
            {'title': 'Empty', 'lyrics': ''},
            {'title': 'Short', 'lyrics': 'hi'},
            {'title': 'Special', 'lyrics': '!@#$%^&*()'},
            {'title': 'Unicode', 'lyrics': 'café résumé naïve'},
            {'title': 'Numbers', 'lyrics': '123 456 789'},
        ]

        # Should not crash
        processed = preprocess_lyrics(edge_cases)
        assert len(processed) == 5

        sentiment = run_sentiment(edge_cases)
        assert 'overall' in sentiment

    def test_database_records_created(self, db_session, sample_analysis):
        """Database records are created correctly."""
        from models import Song, Topic

        # Create songs
        Song.create(
            analysis_id=sample_analysis.id,
            artist_name='Test Artist',
            title='Test Song',
            lyrics='Test lyrics'
        )

        # Create topic
        Topic.create(
            analysis_id=sample_analysis.id,
            topic_id=0,
            keywords={'test': 0.5},
            weight=0.3
        )

        # Verify records
        songs = Song.get_by_analysis(sample_analysis.id)
        topics = Topic.get_top_topics(sample_analysis.id)

        assert len(songs) == 1
        assert len(topics) == 1


@pytest.mark.integration
class TestPipelineWithDatabase:
    """Pipeline tests that interact with database."""

    def test_analysis_lifecycle(self, db_session):
        """Full analysis lifecycle in database."""
        from models import Analysis

        # Create
        analysis = Analysis.create('Lifecycle Artist')
        assert analysis.status == 'queued'

        # Update to processing
        analysis.update_status('processing', 'Working...')
        assert analysis.status == 'processing'
        assert analysis.progress == 'Working...'

        # Complete with results
        results = {
            'topics': [{'id': 0, 'name': 'Test'}],
            'sentiment': {'overall': 0.5}
        }
        analysis.set_results(results)

        assert analysis.status == 'completed'
        assert analysis.results == results
        assert analysis.completed_at is not None

    def test_failed_analysis_can_retry(self, db_session):
        """Failed analysis can be retried."""
        from models import Analysis

        # Create and fail
        analysis = Analysis.create('Retry Artist')
        analysis.mark_failed('Initial failure')
        assert analysis.status == 'failed'

        # In real app, would delete and create new
        db_session.delete(analysis)
        db_session.commit()

        # Create new
        new_analysis = Analysis.create('Retry Artist')
        assert new_analysis.status == 'queued'
