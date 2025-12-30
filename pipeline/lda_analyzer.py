"""LDA (Latent Dirichlet Allocation) topic analysis."""

import re
import logging
from typing import List, Dict, Tuple, Optional

from gensim import corpora
from gensim.models import LdaModel

logger = logging.getLogger(__name__)


def run_lda(songs: List[Dict], num_topics: int = 7, passes: int = 10,
            random_state: int = 42) -> List[Dict]:
    """
    Run LDA topic modeling on preprocessed songs.

    Args:
        songs: List of preprocessed song dicts with 'tokens' and 'stem_to_word' keys
        num_topics: Number of topics to discover
        passes: Number of training passes
        random_state: Random seed for reproducibility

    Returns:
        List of topic dicts with: id, name, keywords, weight
    """
    logger.info(f"=== LDA TOPIC ANALYSIS: {len(songs)} songs, {num_topics} topics ===")

    # Get stem to word mapping from first song (shared across all)
    stem_to_word = songs[0].get('stem_to_word', {}) if songs else {}

    # Extract token lists
    token_lists = [song.get('tokens', []) for song in songs]
    token_lists = [t for t in token_lists if t]  # Remove empty

    if not token_lists:
        logger.warning("No tokens available for LDA")
        return []

    logger.info(f"Building vocabulary from {len(token_lists)} documents...")

    # Adjust num_topics if not enough documents
    if len(token_lists) < num_topics:
        num_topics = max(2, len(token_lists) // 2)
        logger.info(f"Adjusted num_topics to {num_topics} due to small corpus")

    try:
        # Create dictionary
        dictionary = corpora.Dictionary(token_lists)
        logger.info(f"Dictionary size: {len(dictionary)} unique terms")

        # Filter extremes
        dictionary.filter_extremes(no_below=2, no_above=0.5)

        if len(dictionary) < 10:
            logger.warning("Dictionary too small after filtering")
            # Reset without extreme filtering
            dictionary = corpora.Dictionary(token_lists)

        # Create corpus (bag of words)
        corpus = [dictionary.doc2bow(tokens) for tokens in token_lists]
        logger.info(f"Created corpus with {len(corpus)} documents")

        # Train LDA model
        logger.info(f"Training LDA model ({passes} passes)...")
        lda_model = LdaModel(
            corpus=corpus,
            id2word=dictionary,
            num_topics=num_topics,
            passes=passes,
            random_state=random_state,
            alpha='auto',
            eta='auto'
        )

        # Extract topics
        logger.info("Extracting topics...")
        topics = _extract_topics(lda_model, num_topics, stem_to_word)

        for topic in topics:
            top_words = list(topic['keywords'].keys())[:5]
            logger.info(f"  Topic '{topic['name']}': {', '.join(top_words)}")

        logger.info(f"=== LDA COMPLETE: {len(topics)} topics discovered ===")
        return topics

    except Exception as e:
        logger.error(f"LDA analysis failed: {e}")
        return []


def _extract_topics(model: LdaModel, num_topics: int, stem_to_word: Dict = None) -> List[Dict]:
    """
    Extract topics from trained LDA model.

    Args:
        model: Trained LDA model
        num_topics: Number of topics
        stem_to_word: Mapping from stemmed words to original words

    Returns:
        List of topic dicts
    """
    if stem_to_word is None:
        stem_to_word = {}

    topics = []

    for topic_id in range(num_topics):
        # Get top words for this topic
        topic_words = model.show_topic(topic_id, topn=10)

        # Parse into keywords dict, converting stems to original words
        keywords = {}
        for stem, weight in topic_words:
            # Convert stem to original word if available
            original = stem_to_word.get(stem, stem.capitalize())
            keywords[original] = round(float(weight), 4)

        # Calculate topic weight (average probability)
        weight = sum(w for _, w in topic_words) / len(topic_words) if topic_words else 0

        # Generate topic name from top words (now using original words)
        top_words = list(keywords.keys())[:3]
        name = _generate_topic_name(top_words)

        topics.append({
            'id': topic_id,
            'name': name,
            'keywords': keywords,
            'weight': round(float(weight), 4)
        })

    # Sort by weight descending
    topics.sort(key=lambda x: x['weight'], reverse=True)

    # Merge topics with the same name
    topics = _merge_duplicate_topics(topics)

    return topics


def _merge_duplicate_topics(topics: List[Dict]) -> List[Dict]:
    """
    Merge topics that have the same name.

    Args:
        topics: List of topic dicts

    Returns:
        List with duplicate names merged (keywords combined, weights summed)
    """
    merged = {}

    for topic in topics:
        name = topic['name']
        if name in merged:
            # Merge keywords (combine and keep higher weights)
            existing = merged[name]
            for word, weight in topic['keywords'].items():
                if word in existing['keywords']:
                    existing['keywords'][word] = max(existing['keywords'][word], weight)
                else:
                    existing['keywords'][word] = weight
            # Sum the weights
            existing['weight'] = round(existing['weight'] + topic['weight'], 4)
        else:
            merged[name] = {
                'id': topic['id'],
                'name': name,
                'keywords': dict(topic['keywords']),
                'weight': topic['weight']
            }

    # Convert back to list and re-sort
    result = list(merged.values())
    result.sort(key=lambda x: x['weight'], reverse=True)

    # Re-assign IDs
    for i, topic in enumerate(result):
        topic['id'] = i

    return result


# Semantic categories for topic labeling
THEME_CATEGORIES = {
    'Love & Emotion': ['love', 'heart', 'feel', 'feeling', 'emotion', 'passion', 'desire', 'want', 'need', 'miss', 'kiss'],
    'Darkness & Shadow': ['dark', 'darkness', 'night', 'shadow', 'black', 'blind', 'void', 'abyss', 'deep'],
    'Light & Hope': ['light', 'bright', 'sun', 'shine', 'glow', 'hope', 'dream', 'dawn', 'star', 'sky'],
    'Death & Mortality': ['die', 'dying', 'death', 'dead', 'grave', 'blood', 'kill', 'end', 'fade', 'ghost', 'soul'],
    'Pain & Suffering': ['pain', 'hurt', 'suffer', 'wound', 'scar', 'tear', 'cry', 'break', 'broken', 'fall', 'lost'],
    'Anger & Rage': ['rage', 'anger', 'hate', 'fire', 'burn', 'fury', 'wrath', 'fight', 'war', 'destroy'],
    'Freedom & Escape': ['free', 'freedom', 'fly', 'escape', 'run', 'away', 'leave', 'break', 'release', 'rise'],
    'Time & Memory': ['time', 'memory', 'remember', 'forget', 'past', 'future', 'yesterday', 'tomorrow', 'forever', 'never'],
    'Identity & Self': ['self', 'mind', 'soul', 'body', 'face', 'eye', 'hand', 'head', 'inside', 'within'],
    'Nature & Elements': ['rain', 'storm', 'wind', 'sea', 'ocean', 'water', 'earth', 'stone', 'mountain', 'river'],
    'Truth & Lies': ['truth', 'lie', 'real', 'fake', 'believe', 'trust', 'betray', 'hide', 'reveal', 'secret'],
    'Power & Control': ['power', 'control', 'king', 'crown', 'rule', 'throne', 'god', 'master', 'slave', 'chain'],
    'Isolation & Loneliness': ['alone', 'lonely', 'empty', 'hollow', 'silence', 'quiet', 'cold', 'frozen', 'still'],
    'Journey & Path': ['road', 'path', 'walk', 'step', 'journey', 'way', 'follow', 'lead', 'guide', 'home'],
}


def _generate_topic_name(words: List[str]) -> str:
    """
    Generate a human-readable topic name from keywords using semantic matching.

    Args:
        words: Top words for the topic

    Returns:
        Topic name string
    """
    if not words:
        return "Unknown Theme"

    # Normalize words for matching
    words_lower = [w.lower() for w in words]

    # Score each category by how many words match
    category_scores = {}
    for category, keywords in THEME_CATEGORIES.items():
        score = 0
        for word in words_lower:
            # Check if any keyword is contained in the word or vice versa
            for keyword in keywords:
                if keyword in word or word in keyword:
                    score += 1
                    break
        if score > 0:
            category_scores[category] = score

    # Return best matching category, or fall back to top words
    if category_scores:
        best_category = max(category_scores.items(), key=lambda x: x[1])[0]
        return best_category
    else:
        # Fall back to showing top 2 words
        return ' & '.join(words[:2]) if len(words) >= 2 else words[0]


def _parse_topic_words(topic_string: str) -> List[Tuple[str, float]]:
    """
    Parse topic string from Gensim format.

    Args:
        topic_string: String like '0.045*"word1" + 0.032*"word2"'

    Returns:
        List of (word, weight) tuples
    """
    words = []

    # Match pattern: 0.045*"word1"
    pattern = r'(\d+\.\d+)\*"([^"]+)"'
    matches = re.findall(pattern, topic_string)

    for weight_str, word in matches:
        words.append((word, float(weight_str)))

    return words


def assign_topics_to_songs(songs: List[Dict], num_topics: int = 7,
                           random_state: int = 42) -> List[Dict]:
    """
    Assign dominant topic to each song.

    Args:
        songs: List of preprocessed song dicts
        num_topics: Number of topics
        random_state: Random seed

    Returns:
        Songs with 'topic_id' assigned
    """
    token_lists = [song.get('tokens', []) for song in songs]
    non_empty_indices = [i for i, t in enumerate(token_lists) if t]

    if not non_empty_indices:
        return songs

    non_empty_tokens = [token_lists[i] for i in non_empty_indices]

    # Adjust num_topics if needed
    if len(non_empty_tokens) < num_topics:
        num_topics = max(2, len(non_empty_tokens) // 2)

    try:
        dictionary = corpora.Dictionary(non_empty_tokens)
        dictionary.filter_extremes(no_below=2, no_above=0.5)

        if len(dictionary) < 10:
            dictionary = corpora.Dictionary(non_empty_tokens)

        corpus = [dictionary.doc2bow(tokens) for tokens in non_empty_tokens]

        lda_model = LdaModel(
            corpus=corpus,
            id2word=dictionary,
            num_topics=num_topics,
            passes=10,
            random_state=random_state
        )

        # Assign topics
        updated_songs = list(songs)
        for idx, corpus_idx in enumerate(non_empty_indices):
            bow = dictionary.doc2bow(token_lists[corpus_idx])
            topic_distribution = lda_model.get_document_topics(bow)
            if topic_distribution:
                dominant_topic = max(topic_distribution, key=lambda x: x[1])[0]
                updated_songs[corpus_idx] = {
                    **updated_songs[corpus_idx],
                    'topic_id': int(dominant_topic)
                }

        return updated_songs

    except Exception as e:
        logger.error(f"Topic assignment failed: {e}")
        return songs
