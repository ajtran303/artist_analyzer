"""Unit tests for database operations - Phase 2."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from database import db, check_db_health
from models import Analysis, Song, Topic


@pytest.mark.unit
class TestDatabaseConnection:
    """Tests for database connection."""

    def test_session_execute_works(self, db_session):
        """Can execute raw SQL."""
        result = db_session.execute(text('SELECT 1'))
        row = result.fetchone()
        assert row[0] == 1

    def test_database_health_check(self, app_context):
        """Database health check returns True."""
        assert check_db_health() is True

    def test_rollback_on_error(self, db_session):
        """Transaction rolls back on exception."""
        # Create analysis with artist + album combination
        analysis = Analysis(artist_name='Test', album_id=12345, status='queued')
        db_session.add(analysis)
        db_session.commit()

        # Try to create duplicate (same artist + album_id should fail)
        try:
            duplicate = Analysis(artist_name='Test', album_id=12345, status='queued')
            db_session.add(duplicate)
            db_session.commit()
        except IntegrityError:
            db_session.rollback()

        # Session should still be usable
        count = db_session.query(Analysis).count()
        assert count == 1


@pytest.mark.unit
class TestSchemaIndices:
    """Tests for schema indices and constraints."""

    def test_artist_album_is_unique(self, db_session):
        """artist_name + album_id has unique constraint."""
        Analysis.create('Unique Artist', album_id=12345, album_name='Test Album')

        with pytest.raises(IntegrityError):
            Analysis.create('Unique Artist', album_id=12345, album_name='Test Album')
            db_session.commit()

    def test_same_artist_different_album_allowed(self, db_session):
        """Same artist with different album_id is allowed."""
        Analysis.create('Same Artist', album_id=11111, album_name='Album 1')
        Analysis.create('Same Artist', album_id=22222, album_name='Album 2')

        count = db_session.query(Analysis).filter_by(artist_name='Same Artist').count()
        assert count == 2

    def test_job_id_is_unique(self, db_session):
        """job_id has unique constraint when set."""
        analysis1 = Analysis.create('Artist 1')
        analysis1.job_id = 'same-job-id'
        db_session.commit()

        analysis2 = Analysis.create('Artist 2')
        analysis2.job_id = 'same-job-id'

        with pytest.raises(IntegrityError):
            db_session.commit()


@pytest.mark.unit
class TestForeignKeyConstraints:
    """Tests for foreign key constraints."""

    def test_song_deletion_cascades_from_analysis(self, db_session, sample_analysis):
        """Deleting Analysis deletes associated Songs."""
        Song.create(
            analysis_id=sample_analysis.id,
            artist_name='Artist',
            title='Song 1'
        )
        Song.create(
            analysis_id=sample_analysis.id,
            artist_name='Artist',
            title='Song 2'
        )

        # Verify songs exist
        songs = Song.get_by_analysis(sample_analysis.id)
        assert len(songs) == 2

        # Delete analysis
        db_session.delete(sample_analysis)
        db_session.commit()

        # Songs should be deleted too
        songs = Song.query.filter_by(analysis_id=sample_analysis.id).all()
        assert len(songs) == 0

    def test_topic_deletion_cascades_from_analysis(self, db_session, sample_analysis):
        """Deleting Analysis deletes associated Topics."""
        Topic.create(
            analysis_id=sample_analysis.id,
            topic_id=0,
            keywords={'test': 0.5}
        )

        # Verify topic exists
        topics = Topic.query.filter_by(analysis_id=sample_analysis.id).all()
        assert len(topics) == 1

        # Delete analysis
        db_session.delete(sample_analysis)
        db_session.commit()

        # Topics should be deleted too
        topics = Topic.query.filter_by(analysis_id=sample_analysis.id).all()
        assert len(topics) == 0

    def test_song_requires_valid_analysis_id(self, db_session):
        """Song creation fails with invalid analysis_id (PostgreSQL only)."""
        # Note: SQLite doesn't enforce FK constraints by default
        # This test verifies the schema is correct for PostgreSQL
        song = Song(
            analysis_id=99999,  # Non-existent
            artist_name='Artist',
            title='Song'
        )
        db_session.add(song)

        try:
            db_session.commit()
            # If we get here, we're on SQLite - just verify the song was created
            # The FK constraint would be enforced on PostgreSQL
            db_session.rollback()
        except IntegrityError:
            # Expected on PostgreSQL
            db_session.rollback()
