"""Pipeline modules for lyrical analysis."""

from .preprocessor import preprocess_lyrics
from .lda_analyzer import run_lda
from .sentiment_analyzer import run_sentiment
from .bonus_analyzer import analyze_word_frequency, analyze_metaphors

__all__ = [
    'preprocess_lyrics',
    'run_lda',
    'run_sentiment',
    'analyze_word_frequency',
    'analyze_metaphors',
]
