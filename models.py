from datetime import datetime
from database import db


class Analysis(db.Model):
    """Model for artist analysis records."""
    __tablename__ = 'analyses'

    id = db.Column(db.Integer, primary_key=True)
    artist_name = db.Column(db.String(255), nullable=False, index=True)
    album_id = db.Column(db.Integer, nullable=True)
    album_name = db.Column(db.String(255), nullable=True)
    job_id = db.Column(db.String(255), unique=True, nullable=True, index=True)
    status = db.Column(db.String(50), default='queued', nullable=False)
    progress = db.Column(db.Text, nullable=True)
    results = db.Column(db.JSON, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    # Unique constraint on artist + album combination
    __table_args__ = (
        db.UniqueConstraint('artist_name', 'album_id', name='uq_artist_album'),
    )

    # Relationships
    songs = db.relationship('Song', backref='analysis', lazy='dynamic',
                           cascade='all, delete-orphan')
    topics = db.relationship('Topic', backref='analysis', lazy='dynamic',
                            cascade='all, delete-orphan')

    @classmethod
    def create(cls, artist_name, album_id=None, album_name=None, job_id=None):
        """Create a new analysis record."""
        analysis = cls(
            artist_name=artist_name.strip(),
            album_id=album_id,
            album_name=album_name,
            job_id=job_id,
            status='queued',
            created_at=datetime.utcnow()
        )
        db.session.add(analysis)
        db.session.commit()
        return analysis

    @classmethod
    def get_by_artist_album(cls, artist_name, album_id):
        """Get analysis by artist name and album ID."""
        return cls.query.filter_by(
            artist_name=artist_name.strip(),
            album_id=album_id
        ).first()

    @classmethod
    def get_by_job_id(cls, job_id):
        """Get analysis by job ID."""
        return cls.query.filter_by(job_id=job_id).first()

    def update_status(self, status, progress=None):
        """Update the analysis status."""
        self.status = status
        if progress:
            self.progress = progress
        if status == 'completed':
            self.completed_at = datetime.utcnow()
        db.session.commit()

    def set_results(self, results):
        """Store the analysis results."""
        self.results = results
        self.status = 'completed'
        self.completed_at = datetime.utcnow()
        db.session.commit()

    def mark_failed(self, error_message):
        """Mark the analysis as failed."""
        self.status = 'failed'
        self.error_message = error_message
        db.session.commit()

    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'artist_name': self.artist_name,
            'album_id': self.album_id,
            'album_name': self.album_name,
            'job_id': self.job_id,
            'status': self.status,
            'progress': self.progress,
            'results': self.results,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }


class Song(db.Model):
    """Model for individual songs."""
    __tablename__ = 'songs'

    id = db.Column(db.Integer, primary_key=True)
    analysis_id = db.Column(db.Integer, db.ForeignKey('analyses.id', ondelete='CASCADE'),
                           nullable=False)
    artist_name = db.Column(db.String(255), nullable=False, index=True)
    title = db.Column(db.String(500), nullable=False)
    album = db.Column(db.String(500), nullable=True)
    year = db.Column(db.Integer, nullable=True)
    lyrics = db.Column(db.Text, nullable=True)
    topic_id = db.Column(db.Integer, nullable=True)
    sentiment_score = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @classmethod
    def create(cls, analysis_id, artist_name, title, album=None, year=None,
               lyrics=None, topic_id=None, sentiment_score=None):
        """Create a new song record."""
        song = cls(
            analysis_id=analysis_id,
            artist_name=artist_name,
            title=title,
            album=album,
            year=year,
            lyrics=lyrics,
            topic_id=topic_id,
            sentiment_score=sentiment_score
        )
        db.session.add(song)
        db.session.commit()
        return song

    @classmethod
    def bulk_create(cls, songs_data, analysis_id):
        """Bulk insert multiple songs."""
        songs = []
        for data in songs_data:
            song = cls(
                analysis_id=analysis_id,
                artist_name=data.get('artist_name', ''),
                title=data.get('title', ''),
                album=data.get('album'),
                year=data.get('year'),
                lyrics=data.get('lyrics'),
                topic_id=data.get('topic_id'),
                sentiment_score=data.get('sentiment_score')
            )
            songs.append(song)
        db.session.bulk_save_objects(songs)
        db.session.commit()
        return songs

    @classmethod
    def get_by_analysis(cls, analysis_id):
        """Get all songs for an analysis."""
        return cls.query.filter_by(analysis_id=analysis_id).order_by(cls.id).all()

    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'artist_name': self.artist_name,
            'title': self.title,
            'album': self.album,
            'year': self.year,
            'lyrics': self.lyrics[:200] + '...' if self.lyrics and len(self.lyrics) > 200 else self.lyrics,
            'topic_id': self.topic_id,
            'sentiment_score': self.sentiment_score
        }


class Topic(db.Model):
    """Model for LDA-discovered topics."""
    __tablename__ = 'topics'

    id = db.Column(db.Integer, primary_key=True)
    analysis_id = db.Column(db.Integer, db.ForeignKey('analyses.id', ondelete='CASCADE'),
                           nullable=False)
    topic_id = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(255), nullable=True)
    keywords = db.Column(db.JSON, nullable=True)
    weight = db.Column(db.Float, nullable=True)

    @classmethod
    def create(cls, analysis_id, topic_id, keywords, name=None, weight=None):
        """Create a new topic record."""
        topic = cls(
            analysis_id=analysis_id,
            topic_id=topic_id,
            name=name,
            keywords=keywords,
            weight=weight
        )
        db.session.add(topic)
        db.session.commit()
        return topic

    @classmethod
    def get_top_topics(cls, analysis_id, limit=10):
        """Get top topics by weight."""
        return cls.query.filter_by(analysis_id=analysis_id)\
            .order_by(cls.weight.desc())\
            .limit(limit)\
            .all()

    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'topic_id': self.topic_id,
            'name': self.name,
            'keywords': self.keywords,
            'weight': self.weight
        }
