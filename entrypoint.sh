#!/bin/bash
set -e

# Wait for database to be ready
echo "Waiting for database..."
until python -c "import psycopg2; psycopg2.connect('$DATABASE_URL')" 2>/dev/null; do
    echo "  Retrying..."
    sleep 2
done
echo "Database is ready!"

# Run database migrations (create tables) - only for web service
# Worker will skip this to avoid race conditions
if [[ "$1" == *"gunicorn"* ]]; then
    echo "Setting up database..."
    python -c "
from app import create_app
from database import db

app = create_app()
with app.app_context():
    db.create_all()
    print('Database tables created successfully')
" || echo "Tables may already exist, continuing..."
else
    echo "Skipping DB setup (worker mode)"
    sleep 3  # Give web container time to create tables
fi

# Execute the main command
exec "$@"
