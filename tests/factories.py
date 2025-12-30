"""Factory-boy factories for test data generation."""

import factory
from factory.alchemy import SQLAlchemyModelFactory
from faker import Faker
from datetime import datetime

from database import db
from models import Analysis, Song, Topic

fake = Faker()


class BaseFactory(SQLAlchemyModelFactory):
    """Base factory with SQLAlchemy session."""

    class Meta:
        abstract = True
        sqlalchemy_session = None
        sqlalchemy_session_persistence = 'commit'

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Create instance and add to session."""
        from app import create_app
        from config import TestingConfig

        app = create_app(TestingConfig)
        with app.app_context():
            instance = model_class(*args, **kwargs)
            db.session.add(instance)
            db.session.commit()
            return instance


class AnalysisFactory(factory.Factory):
    """Factory for Analysis model."""

    class Meta:
        model = Analysis

    artist_name = factory.LazyFunction(lambda: fake.name())
    job_id = factory.LazyFunction(lambda: fake.uuid4())
    status = 'queued'
    progress = None
    results = None
    error_message = None
    created_at = factory.LazyFunction(datetime.utcnow)
    completed_at = None

    @classmethod
    def create_queued(cls, **kwargs):
        """Create a queued analysis."""
        return cls(status='queued', **kwargs)

    @classmethod
    def create_processing(cls, progress='Running analysis...', **kwargs):
        """Create a processing analysis."""
        return cls(status='processing', progress=progress, **kwargs)

    @classmethod
    def create_completed(cls, **kwargs):
        """Create a completed analysis with results."""
        return cls(
            status='completed',
            results={
                'topics': [],
                'sentiment': {'overall': 0.0},
                'word_frequency': [],
                'metaphors': []
            },
            completed_at=datetime.utcnow(),
            **kwargs
        )

    @classmethod
    def create_failed(cls, error='Analysis failed', **kwargs):
        """Create a failed analysis."""
        return cls(status='failed', error_message=error, **kwargs)


class SongFactory(factory.Factory):
    """Factory for Song model."""

    class Meta:
        model = Song

    analysis_id = factory.LazyAttribute(lambda o: 1)
    artist_name = factory.LazyFunction(lambda: fake.name())
    title = factory.LazyFunction(lambda: fake.sentence(nb_words=4))
    album = factory.LazyFunction(lambda: fake.sentence(nb_words=2))
    year = factory.LazyFunction(lambda: fake.year())
    lyrics = factory.LazyFunction(lambda: fake.paragraph(nb_sentences=10))
    topic_id = None
    sentiment_score = factory.LazyFunction(lambda: round(fake.pyfloat(min_value=-1, max_value=1), 4))
    created_at = factory.LazyFunction(datetime.utcnow)

    @classmethod
    def create_with_lyrics(cls, lyrics, **kwargs):
        """Create a song with specific lyrics."""
        return cls(lyrics=lyrics, **kwargs)

    @classmethod
    def create_happy(cls, **kwargs):
        """Create a song with positive sentiment."""
        return cls(
            lyrics='I love you sunshine happiness joy wonderful amazing beautiful',
            sentiment_score=0.7,
            **kwargs
        )

    @classmethod
    def create_sad(cls, **kwargs):
        """Create a song with negative sentiment."""
        return cls(
            lyrics='Sadness darkness pain sorrow tears death lonely broken',
            sentiment_score=-0.6,
            **kwargs
        )


class TopicFactory(factory.Factory):
    """Factory for Topic model."""

    class Meta:
        model = Topic

    analysis_id = factory.LazyAttribute(lambda o: 1)
    topic_id = factory.Sequence(lambda n: n)
    name = factory.LazyFunction(lambda: f"{fake.word().title()} / {fake.word().title()}")
    keywords = factory.LazyFunction(
        lambda: {fake.word(): round(fake.pyfloat(min_value=0.01, max_value=0.1), 4) for _ in range(5)}
    )
    weight = factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.05, max_value=0.3), 4))


def create_sample_lyrics(theme='general'):
    """Generate sample lyrics based on theme."""
    themes = {
        'love': 'Love is all around, my heart beats for you. '
                'Together forever, our dreams come true. '
                'Kiss me under the stars tonight.',
        'dark': 'In the darkness I wander alone. '
                'Shadows creep and the cold wind blows. '
                'Death awaits at the end of this road.',
        'nature': 'The sun rises over the mountain high. '
                  'Rivers flow to the endless sea. '
                  'Birds sing their songs in the morning light.',
        'pain': 'Pain cuts deep into my soul. '
                'Tears fall like rain in the night. '
                'Suffering is all I have ever known.',
        'hope': 'Tomorrow brings a brighter day. '
                'Dreams can come true if we believe. '
                'Hope is the light that guides the way.',
        'general': 'Walking down the street today. '
                   'Thinking about yesterday. '
                   'Time goes by so fast.'
    }
    return themes.get(theme, themes['general'])


def create_song_batch(count=10, analysis_id=1, artist_name='Test Artist'):
    """Create a batch of songs for testing."""
    songs = []
    themes = ['love', 'dark', 'nature', 'pain', 'hope', 'general']

    for i in range(count):
        theme = themes[i % len(themes)]
        songs.append({
            'title': f'Song {i + 1}',
            'artist': artist_name,
            'album': f'Album {(i // 3) + 1}',
            'year': 2018 + (i % 5),
            'lyrics': create_sample_lyrics(theme),
            'url': f'https://genius.com/song{i + 1}'
        })

    return songs
