"""Web routes for HTML pages."""

from flask import Blueprint, render_template

web_bp = Blueprint('web', __name__)


@web_bp.route('/')
def index():
    """Home page with artist input form."""
    return render_template('index.html')


@web_bp.route('/results/<job_id>')
def results(job_id):
    """Results page for displaying analysis."""
    return render_template('results.html', job_id=job_id)
