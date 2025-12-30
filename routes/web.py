"""Web routes for HTML pages."""

from flask import Blueprint, render_template, request

web_bp = Blueprint('web', __name__)


@web_bp.route('/')
def index():
    """Home page with artist input form."""
    return render_template('index.html')


@web_bp.route('/results/<job_id>')
def results(job_id):
    """Results page for displaying analysis."""
    return render_template('results.html', job_id=job_id)


@web_bp.route('/compare')
def compare():
    """Compare two albums side-by-side."""
    job_id_a = request.args.get('a', '')
    job_id_b = request.args.get('b', '')
    return render_template('compare.html', job_id_a=job_id_a, job_id_b=job_id_b)
