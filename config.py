import os
import sys
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')

    # Connection pooling for production stability
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,  # Recycle connections after 1 hour
        'pool_pre_ping': True,  # Verify connections before use
        'max_overflow': 20,
    }

    # Celery (use lowercase keys for Celery 5.x+)
    broker_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    result_backend = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

    # Genius API
    GENIUS_API_TOKEN = os.environ.get('GENIUS_API_TOKEN')

    # Scraper settings
    MAX_SONGS_PER_ARTIST = int(os.environ.get('MAX_SONGS_PER_ARTIST', 50))
    REQUEST_TIMEOUT = int(os.environ.get('REQUEST_TIMEOUT', 30))
    MAX_RETRIES = int(os.environ.get('MAX_RETRIES', 3))

    # LDA settings
    LDA_NUM_TOPICS = int(os.environ.get('LDA_NUM_TOPICS', 7))
    LDA_PASSES = int(os.environ.get('LDA_PASSES', 10))
    LDA_RANDOM_STATE = 42


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SQLALCHEMY_ECHO = True

    # Development defaults (only for local dev)
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'postgresql://localhost/artist_analyzer'
    )

    # Smaller pool for development
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 5,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'max_overflow': 10,
    }


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SECRET_KEY = 'test-secret-key'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    broker_url = 'memory://'
    result_backend = 'cache+memory://'
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_ENGINE_OPTIONS = {}  # SQLite doesn't use pooling


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False

    # Handle Render's postgres:// vs postgresql://
    _db_uri = os.environ.get('DATABASE_URL', '')
    if _db_uri.startswith('postgres://'):
        _db_uri = _db_uri.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = _db_uri

    # Production session security
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


# Required environment variables for production
REQUIRED_ENV_VARS = {
    'production': ['SECRET_KEY', 'DATABASE_URL', 'GENIUS_API_TOKEN'],
    'development': ['GENIUS_API_TOKEN'],  # Minimum for dev
}


def validate_env_vars(env: str) -> list:
    """
    Validate that required environment variables are set.

    Returns:
        List of missing variable names (empty if all present)
    """
    required = REQUIRED_ENV_VARS.get(env, [])
    missing = [var for var in required if not os.environ.get(var)]
    return missing


def get_config():
    """Get configuration based on FLASK_ENV."""
    env = os.environ.get('FLASK_ENV', 'development')

    # Validate required env vars
    missing = validate_env_vars(env)
    if missing:
        print(f"ERROR: Missing required environment variables for {env}: {', '.join(missing)}",
              file=sys.stderr)
        if env == 'production':
            sys.exit(1)  # Fail hard in production
        else:
            print("WARNING: Continuing in development mode with missing vars", file=sys.stderr)

    return config.get(env, config['default'])
