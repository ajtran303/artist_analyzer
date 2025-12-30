from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

db = SQLAlchemy()


def init_db(app):
    """Initialize the database with the Flask app."""
    db.init_app(app)
    with app.app_context():
        db.create_all()


def get_db_session():
    """Get the current database session."""
    return db.session


def check_db_health():
    """Check if the database connection is healthy."""
    try:
        db.session.execute(text('SELECT 1'))
        return True
    except Exception:
        return False
