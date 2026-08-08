"""
SwingEdge Pro — Sentiment Analysis Engine
Uses VADER (always available) with optional FinBERT upgrade.
"""
import re
import logging
from typing import Dict, List, Optional
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from backend.config import settings

logger = logging.getLogger(__name__)


class SentimentEngine:
    """Multi-source sentiment analysis for financial texts."""

    def __init__(self):
        self.vader = SentimentIntensityAnalyzer()
        # Add financial domain-specific words to VADER lexicon
        self._enhance_vader_lexicon()
        self.finbert = None
        self._try_load_finbert()

    def _enhance_vader_lexicon(self):
        """Add finance-specific words to improve VADER accuracy."""
        finance_lexicon = {
            # Strongly bullish
            'beat': 2.5, 'beats': 2.5, 'surpassed': 2.5, 'smashed': 2.8,
            'record': 2.0, 'breakout': 2.3, 'upgrade': 2.5, 'upgraded': 2.5,
            'outperform': 2.0, 'overweight': 1.8, 'buy': 1.5, 'strong buy': 3.0,
            'bullish': 2.5, 'moon': 2.0, 'rocket': 1.8, 'rally': 2.0,
            'squeeze': 2.0, 'surge': 2.2, 'soar': 2.5, 'skyrocket': 2.8,
            'blowout': 2.5, 'blockbuster': 2.3, 'milestone': 1.8,
            'fda approval': 3.0, 'approved': 2.0, 'wins contract': 2.5,
            'strategic partnership': 1.8, 'buyback': 1.8, 'dividend': 1.5,
            'partnership': 1.5, 'expansion': 1.5, 'guidance raised': 2.5,
            # Strongly bearish
            'miss': -2.5, 'missed': -2.5, 'disappoints': -2.5,
            'downgrade': -2.5, 'dowraded': -2.5, 'underperform': -2.0,
            'sell': -1.5, 'strong sell': -3.0, 'bearish': -2.5,
            'crash': -2.8, 'plunge': -2.8, 'tumble': -2.3, 'collapse': -2.8,
            'bankruptcy': -3.0, 'bankrupt': -3.0, 'delisted': -2.8,
            'fraud': -3.0, 'investigation': -2.0, 'lawsuit': -1.8,
            'recall': -2.0, 'fda rejection': -3.0, 'rejected': -1.8,
            'guidance cut': -2.5, 'layoffs': -1.8, 'restructuring': -1.5,
            'halted': -2.0, 'suspended': -1.8, 'short seller': -2.0,
            # Neutral adjustments
            'volatile': -0.5, 'uncertainty': -0.8, 'mixed': 0.0,
        }
        self.vader.lexicon.update(finance_lexicon)

    def _try_load_finbert(self):
        """Attempt to load FinBERT — fails gracefully if torch not installed."""
        try:
            from transformers import pipeline
            self.finbert = pipeline(
                'text-classification',
                model='ProsusAI/finbert',
                truncation=True,
                max_length=512,
            )
            logger.info("FinBERT loaded successfully — using enhanced NLP.")
        except Exception as e:
            logger.info(f"FinBERT not available (using VADER): {e}")
            self.finbert = None

    def analyze_text(self, text: str) -> Dict:
        """Analyze a text string and return sentiment."""
        if not text or len(text.strip()) < 3:
            return {'score': 0.0, 'label': 'neutral', 'confidence': 0.5}

        # Clean text
        text = text.strip()[:512]

        # Try FinBERT first
        if self.finbert:
            try:
                result = self.finbert(text)[0]
                label_map = {'positive': 'bullish', 'negative': 'bearish', 'neutral': 'neutral'}
                label = label_map.get(result['label'].lower(), 'neutral')
                score_map = {'bullish': result['score'], 'bearish': -result['score'], 'neutral': 0.0}
                return {
                    'score': round(score_map[label], 3),
                    'label': label,
                    'confidence': round(result['score'], 3),
                    'method': 'finbert',
                }
            except Exception:
                pass

        # VADER fallback
        scores = self.vader.polarity_scores(text)
        compound = scores['compound']
        if compound >= 0.05:
            label = 'bullish'
        elif compound <= -0.05:
            label = 'bearish'
        else:
            label = 'neutral'

        confidence = abs(compound)  # 0-1 range
        return {
            'score': round(compound, 3),
            'label': label,
            'confidence': round(min(1.0, confidence + 0.3), 3),  # VADER is usually right
            'method': 'vader',
        }

    def analyze_news_batch(self, news_list: List[Dict]) -> List[Dict]:
        """Analyze sentiment for a list of news articles."""
        results = []
        for article in news_list:
            text = article.get('headline', '') + ' ' + article.get('summary', '')
            sentiment = self.analyze_text(text)
            article_copy = dict(article)
            article_copy['sentiment_score'] = sentiment['score']
            article_copy['sentiment_label'] = sentiment['label']
            article_copy['sentiment_confidence'] = sentiment['confidence']
            results.append(article_copy)
        return results

    def aggregate_ticker_sentiment(self, ticker: str, news_list: List[Dict]) -> Dict:
        """Compute overall sentiment score for a stock from its news."""
        if not news_list:
            return {'score': 0.0, 'label': 'neutral', 'article_count': 0, 'bullish': 0, 'bearish': 0, 'neutral': 0}

        scored = self.analyze_news_batch(news_list)
        scores = [a['sentiment_score'] for a in scored]
        labels = [a['sentiment_label'] for a in scored]

        # Weight recent articles higher
        weights = [1.0 + (0.5 * (1 - i / len(scored))) for i in range(len(scored))]
        weighted_score = sum(s * w for s, w in zip(scores, weights)) / sum(weights)

        bullish_count = labels.count('bullish')
        bearish_count = labels.count('bearish')
        neutral_count = labels.count('neutral')

        if weighted_score >= 0.05:
            agg_label = 'bullish'
        elif weighted_score <= -0.05:
            agg_label = 'bearish'
        else:
            agg_label = 'neutral'

        return {
            'score': round(weighted_score, 3),
            'label': agg_label,
            'article_count': len(news_list),
            'bullish': bullish_count,
            'bearish': bearish_count,
            'neutral': neutral_count,
        }

    def detect_sentiment_spike(self, ticker: str, current_score: float, history: List[float]) -> Dict:
        """Detect if current sentiment is significantly higher/lower than recent average."""
        if not history:
            return {'spike': False, 'magnitude': 0.0, 'direction': 'neutral'}
        avg = sum(history) / len(history)
        std = (sum((x - avg) ** 2 for x in history) / len(history)) ** 0.5
        if std == 0:
            return {'spike': False, 'magnitude': 0.0, 'direction': 'neutral'}
        z_score = (current_score - avg) / std
        is_spike = abs(z_score) > 2.0
        direction = 'bullish' if z_score > 0 else 'bearish'
        return {'spike': is_spike, 'magnitude': round(abs(z_score), 2), 'direction': direction}

    def analyze_political_signal(self, text: str, ticker: str = None) -> Dict:
        """Detect political/presidential signals affecting stocks."""
        from backend.data.fetchers import detect_political_signals
        result = detect_political_signals(text)
        if result['is_political']:
            # Also score the sentiment of the political statement itself
            sentiment = self.analyze_text(text)
            result['sentiment'] = sentiment
            if ticker and ticker in result.get('affected_tickers', []):
                result['directly_affects_ticker'] = True
        return result

    def analyze_analyst_action(self, text: str) -> Dict:
        """Detect analyst upgrades, downgrades, price targets."""
        from backend.data.fetchers import detect_analyst_actions
        return detect_analyst_actions(text)

    def score_sentiment_for_stock(self, ticker: str, news_list: List[Dict], wsb_data: Dict = None) -> float:
        """Return a 0-100 sentiment score for use in master scoring."""
        agg = self.aggregate_ticker_sentiment(ticker, news_list)
        base_score = 50.0 + (agg['score'] * 50)  # map -1..1 to 0..100

        # Bonus from WSB/social sentiment
        if wsb_data:
            wsb_score = wsb_data.get('score', 0) * 10
            mentions = min(wsb_data.get('mentions', 0), 100) / 100 * 5  # up to 5 bonus
            base_score += wsb_score + mentions

        return round(max(0.0, min(100.0, base_score)), 1)
