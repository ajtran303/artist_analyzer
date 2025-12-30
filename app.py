import os
import logging
from flask import Flask
from config import get_config
from database import db

# Configure logging to not expose sensitive data
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Filter out sensitive data from logs
class SensitiveDataFilter(logging.Filter):
    """Filter to remove sensitive data from logs."""
    SENSITIVE_KEYS = ['password', 'token', 'secret', 'api_key', 'authorization']

    def filter(self, record):
        if hasattr(record, 'msg'):
            msg = str(record.msg).lower()
            for key in self.SENSITIVE_KEYS:
                if key in msg:
                    record.msg = '[REDACTED - Contains sensitive data]'
                    break
        return True

# Apply filter to root logger
logging.getLogger().addFilter(SensitiveDataFilter())


def create_app(config_class=None):
    """Application factory for Flask app."""
    app = Flask(__name__)

    # Load configuration
    if config_class is None:
        config_class = get_config()
    app.config.from_object(config_class)

    # Security configurations
    app.config['WTF_CSRF_ENABLED'] = True
    app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # 1 hour

    # Initialize extensions
    db.init_app(app)

    # Initialize CSRF protection
    from flask_wtf.csrf import CSRFProtect
    csrf = CSRFProtect(app)

    # Exempt API endpoints from CSRF (they use different auth)
    from routes.api import api_bp
    csrf.exempt(api_bp)

    # Initialize rate limiting
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    # Use memory storage for testing, Redis for production
    is_testing = app.config.get('TESTING')
    is_development = os.environ.get('FLASK_ENV') == 'development'

    if is_testing or is_development:
        storage_uri = 'memory://'
        default_limits = []
        limiter_enabled = False
    else:
        storage_uri = os.environ.get('REDIS_URL', 'memory://')
        default_limits = ["1000 per day", "200 per hour"]
        limiter_enabled = True

    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=default_limits,
        storage_uri=storage_uri,
        enabled=limiter_enabled,
        default_limits_exempt_when=lambda: False,
        application_limits_exempt_when=lambda: False,
    )

    # Exempt status polling and health check endpoints from rate limiting
    @limiter.request_filter
    def exempt_endpoints():
        from flask import request
        return request.endpoint in ['api.get_analysis_status', 'api.health_check']

    # Store limiter on app for use in routes
    app.limiter = limiter

    # Initialize CORS
    from flask_cors import CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": os.environ.get('CORS_ORIGINS', '*').split(','),
            "methods": ["GET", "POST"],
            "allow_headers": ["Content-Type"]
        }
    })

    # Initialize security headers (Talisman)
    # Only enable in production to avoid issues with local development
    if not app.config.get('TESTING') and os.environ.get('FLASK_ENV') == 'production':
        from flask_talisman import Talisman
        # Force HTTPS by default in production (set FORCE_HTTPS=false for local Docker testing)
        force_https = os.environ.get('FORCE_HTTPS', 'true').lower() == 'true'
        Talisman(
            app,
            force_https=force_https,
            strict_transport_security=True,
            strict_transport_security_max_age=31536000,
            content_security_policy={
                'default-src': "'self'",
                'script-src': "'self' 'unsafe-inline'",
                'style-src': "'self' 'unsafe-inline'",
                'img-src': "'self' data: https://images.genius.com https://*.genius.com",
                'font-src': "'self'",
            },
            referrer_policy='strict-origin-when-cross-origin',
            x_content_type_options=True,
            x_xss_protection=True,
        )

    # Create tables
    with app.app_context():
        db.create_all()

    # Register blueprints
    app.register_blueprint(api_bp)

    # Register web routes
    from routes.web import web_bp
    app.register_blueprint(web_bp)

    # Register error handlers
    register_error_handlers(app)

    return app


def register_error_handlers(app):
    """Register error handlers that don't expose sensitive info."""
    from flask import jsonify

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({'error': 'Bad request'}), 400

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Resource not found'}), 404

    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        return jsonify({'error': 'Rate limit exceeded. Please try again later.'}), 429

    @app.errorhandler(500)
    def internal_error(error):
        # Log the actual error but don't expose it
        app.logger.error(f'Internal error: {error}')
        return jsonify({'error': 'Internal server error'}), 500


# For gunicorn
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # Never run with debug=True in production
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug)
