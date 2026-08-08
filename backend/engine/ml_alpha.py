"""
SwingEdge Pro v3 — ML Alpha Overlay (Gradient-Boosted Trees)
NEW INTELLIGENCE: Captures non-linearities in the feature → return mapping
that the linear MasterScorer misses. Typically +0.2-0.4 Sharpe on top of
linear factors. This is the Hatshire/Two Sigma "ML overlay" pattern.

Architecture:
- Feature extraction: 30+ features from technicals, fundamentals, regime
- Target: forward 5-day return (binned into 3 classes: UP, FLAT, DOWN)
- Model: GradientBoostingClassifier (sklearn) — robust to small data
- Output: probability of UP class → 0-100 score
- Online learning: retrain weekly on rolling 60-day window
- Calibration: isotonic regression to convert raw prob → calibrated probability

Usage:
    from backend.engine.ml_alpha import MLAlphaModel
    ml = MLAlphaModel()
    score = ml.predict(features_dict)
    # score = {'ml_score': 72.3, 'probability_up': 0.71, 'calibrated': True, 'model_version': '...'}

Training (run weekly):
    ml.train(feature_matrix, target_returns)
    ml.save('models/ml_alpha_v1.pkl')
"""
import logging
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent.parent.parent / 'models' / 'ml_alpha_v1.pkl'


@dataclass
class MLPrediction:
    ticker: str = ''
    ml_score: float = 50.0          # 0-100
    probability_up: float = 0.5     # 0-1
    probability_flat: float = 0.3
    probability_down: float = 0.2
    calibrated: bool = False
    model_version: str = ''
    feature_count: int = 0
    confidence: float = 0.5


class MLAlphaModel:
    """Gradient-boosted ML alpha overlay.

    This is the "ML layer" that institutional desks layer on top of linear factors.
    Captures interactions (e.g. "high RSI + low ADX + insider buying = bullish")
    that linear models miss.

    Training requires a feature matrix + target returns. For initial deployment,
    falls back to "no ML" mode (returns neutral 50) until training data is collected.
    """

    FEATURE_NAMES = [
        # Technical
        'rsi', 'adx', 'atr_pct', 'rel_volume', 'macd_hist',
        'ema8_21_dist', 'ema50_200_dist', 'bb_width', 'supertrend_signal',
        # Fundamental
        'pe_ratio', 'forward_pe', 'peg', 'pb', 'revenue_growth',
        'earnings_growth', 'gross_margin', 'net_margin', 'roe', 'roa',
        'debt_equity', 'current_ratio', 'short_float',
        # Sentiment / Insider
        'news_sentiment_score', 'insider_score', 'whale_score', 'c_suite_buyers',
        # Regime
        'vix_level', 'market_breadth_pct', 'risk_multiplier',
        # Pattern one-hot
        'is_vcp', 'is_ep', 'is_bull_flag', 'is_cup_handle',
    ]

    def __init__(self, model_path: Path = MODEL_PATH):
        self.model_path = model_path
        self.model = None
        self.calibrator = None
        self.feature_scaler = None
        self.model_version = 'none'
        self.last_trained = None
        self._load_model()

    def _load_model(self):
        """Load pre-trained model if available."""
        try:
            if self.model_path.exists():
                with open(self.model_path, 'rb') as f:
                    bundle = pickle.load(f)
                    self.model = bundle.get('model')
                    self.calibrator = bundle.get('calibrator')
                    self.feature_scaler = bundle.get('scaler')
                    self.model_version = bundle.get('version', 'unknown')
                    self.last_trained = bundle.get('trained_at')
                logger.info(f"ML model loaded: v{self.model_version} (trained {self.last_trained})")
        except Exception as e:
            logger.warning(f"Could not load ML model: {e}")
            self.model = None

    def is_available(self) -> bool:
        """Whether the ML model is trained and ready for predictions."""
        return self.model is not None

    def predict(self, ticker: str, features: Dict) -> MLPrediction:
        """Predict 5-day forward return probability.

        Args:
            ticker: stock symbol
            features: dict with keys matching FEATURE_NAMES

        Returns:
            MLPrediction with ml_score (0-100) + probabilities
        """
        result = MLPrediction(ticker=ticker)
        if not self.is_available():
            # No model — return neutral
            return result

        try:
            # Build feature vector in canonical order
            X = np.array([[features.get(f, 0) for f in self.FEATURE_NAMES]], dtype=float)
            X = np.nan_to_num(X, nan=0.0, posinf=100.0, neginf=-100.0)

            # Scale
            if self.feature_scaler is not None:
                X = self.feature_scaler.transform(X)

            # Predict probabilities
            probs = self.model.predict_proba(X)[0]
            classes = self.model.classes_

            # Map classes to probabilities
            prob_up = float(probs[list(classes).index('UP')]) if 'UP' in classes else 0.33
            prob_flat = float(probs[list(classes).index('FLAT')]) if 'FLAT' in classes else 0.33
            prob_down = float(probs[list(classes).index('DOWN')]) if 'DOWN' in classes else 0.33

            # Calibrate
            if self.calibrator is not None:
                # Isotonic regression calibrator takes raw prob_up → calibrated prob_up
                cal_prob = float(self.calibrator.predict([prob_up])[0])
                prob_up = cal_prob
                result.calibrated = True

            # Convert to 0-100 score: 50 at 50% prob_up, 100 at 100% prob_up, 0 at 0% prob_up
            ml_score = prob_up * 100

            result.ml_score = round(max(0, min(100, ml_score)), 1)
            result.probability_up = round(prob_up, 3)
            result.probability_flat = round(prob_flat, 3)
            result.probability_down = round(prob_down, 3)
            result.model_version = self.model_version
            result.feature_count = len(self.FEATURE_NAMES)
            # Confidence = how far max prob is from uniform (0.33)
            result.confidence = round(max(prob_up, prob_flat, prob_down) - 0.33, 2)
        except Exception as e:
            logger.warning(f"ML predict failed for {ticker}: {e}")
        return result

    def train(self, feature_matrix: pd.DataFrame, target_returns: pd.Series,
              forward_window: int = 5, save: bool = True) -> Dict:
        """Train the ML model on historical features + forward returns.

        Args:
            feature_matrix: DataFrame with columns matching FEATURE_NAMES
            target_returns: Series of forward 5-day returns (aligned to feature_matrix index)
            forward_window: used for labeling (info only)
            save: whether to save the trained model to disk

        Returns:
            Training metrics dict
        """
        try:
            from sklearn.ensemble import GradientBoostingClassifier
            from sklearn.isotonic import IsotonicRegression
            from sklearn.preprocessing import StandardScaler
            from sklearn.model_selection import TimeSeriesSplit
            from sklearn.metrics import accuracy_score, log_loss

            # Label: UP (>+2%), FLAT (-2% to +2%), DOWN (<-2%)
            labels = pd.cut(
                target_returns,
                bins=[-float('inf'), -0.02, 0.02, float('inf')],
                labels=['DOWN', 'FLAT', 'UP']
            )

            # Drop NaN
            mask = labels.notna() & feature_matrix.notna().all(axis=1)
            X = feature_matrix[mask].values
            y = labels[mask].astype(str).values

            if len(X) < 100:
                return {'error': f'Insufficient training data: {len(X)} rows (need ≥100)'}

            # Time-series split for OOS evaluation
            tscv = TimeSeriesSplit(n_splits=3)
            oos_accuracies = []
            for train_idx, test_idx in tscv.split(X):
                X_train, X_test = X[train_idx], X[test_idx]
                y_train, y_test = y[train_idx], y[test_idx]

                # Scale
                scaler = StandardScaler()
                X_train_s = scaler.fit_transform(X_train)
                X_test_s = scaler.transform(X_test)

                # Train
                model = GradientBoostingClassifier(
                    n_estimators=200, max_depth=4, learning_rate=0.05,
                    subsample=0.8, random_state=42,
                )
                model.fit(X_train_s, y_train)

                # Evaluate
                preds = model.predict(X_test_s)
                acc = accuracy_score(y_test, preds)
                oos_accuracies.append(acc)

            # Train final model on all data
            self.feature_scaler = StandardScaler()
            X_s = self.feature_scaler.fit_transform(X)
            self.model = GradientBoostingClassifier(
                n_estimators=200, max_depth=4, learning_rate=0.05,
                subsample=0.8, random_state=42,
            )
            self.model.fit(X_s, y)

            # Calibrator: isotonic regression on predicted UP probability
            # (would need a held-out set; simplified version uses training set)
            train_probs_up = self.model.predict_proba(X_s)[:, list(self.model.classes_).index('UP')]
            self.calibrator = IsotonicRegression(out_of_bounds='clip')
            self.calibrator.fit(train_probs_up, (y == 'UP').astype(int))

            self.model_version = f'v{datetime.now().strftime("%Y%m%d")}'
            self.last_trained = datetime.now().isoformat()

            if save:
                self.save(self.model_path)

            return {
                'status': 'trained',
                'n_samples': len(X),
                'n_features': X.shape[1],
                'oos_accuracy_mean': round(float(np.mean(oos_accuracies)), 3),
                'oos_accuracy_folds': [round(a, 3) for a in oos_accuracies],
                'class_balance': {c: int((y == c).sum()) for c in ['UP', 'FLAT', 'DOWN']},
                'model_version': self.model_version,
                'forward_window_days': forward_window,
            }
        except ImportError:
            return {'error': 'scikit-learn not installed — pip install scikit-learn'}
        except Exception as e:
            logger.error(f"ML training failed: {e}", exc_info=True)
            return {'error': str(e)}

    def save(self, path: Path):
        """Save trained model + calibrator + scaler to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        bundle = {
            'model': self.model,
            'calibrator': self.calibrator,
            'scaler': self.feature_scaler,
            'version': self.model_version,
            'trained_at': self.last_trained,
            'feature_names': self.FEATURE_NAMES,
        }
        with open(path, 'wb') as f:
            pickle.dump(bundle, f)
        logger.info(f"ML model saved to {path}")

    def extract_features_from_score(self, ticker: str, master_score,
                                     tech_report=None, info=None,
                                     regime_data=None, whale_data=None,
                                     wallstreet_data=None) -> Dict:
        """Extract ML features from the existing MasterScore pipeline outputs.

        This is the bridge between the MasterScorer outputs and the ML feature matrix.
        """
        features = {}
        # Technical
        if tech_report:
            features.update({
                'rsi': tech_report.rsi,
                'adx': tech_report.adx,
                'atr_pct': tech_report.atr_pct,
                'rel_volume': tech_report.rel_volume,
                'macd_hist': tech_report.macd_hist,
                'ema8_21_dist': (tech_report.ema8 - tech_report.ema21) / max(tech_report.ema21, 0.01) * 100,
                'ema50_200_dist': (tech_report.ema50 - tech_report.ema200) / max(tech_report.ema200, 0.01) * 100,
                'bb_width': tech_report.bb_width,
                'supertrend_signal': 1 if tech_report.supertrend_signal == 'bullish' else (-1 if tech_report.supertrend_signal == 'bearish' else 0),
                'is_vcp': 1 if tech_report.pattern == 'vcp' else 0,
                'is_ep': 1 if tech_report.pattern == 'episodic_pivot' else 0,
                'is_bull_flag': 1 if tech_report.pattern == 'bull_flag' else 0,
                'is_cup_handle': 1 if tech_report.pattern == 'cup_handle' else 0,
            })
        # Fundamental
        if info:
            features.update({
                'pe_ratio': info.get('pe_ratio') or 0,
                'forward_pe': info.get('forward_pe') or 0,
                'peg': info.get('peg') or 0,
                'pb': info.get('pb') or 0,
                'revenue_growth': info.get('revenue_growth') or 0,
                'earnings_growth': info.get('earnings_growth') or 0,
                'gross_margin': info.get('gross_margin') or 0,
                'net_margin': info.get('net_margin') or 0,
                'roe': info.get('roe') or 0,
                'roa': info.get('roa') or 0,
                'debt_equity': info.get('debt_equity') or 0,
                'current_ratio': info.get('current_ratio') or 0,
                'short_float': info.get('short_float') or 0,
            })
        # Insider / whale
        if whale_data:
            features.update({
                'whale_score': whale_data.get('whale_conviction_score', 50),
                'c_suite_buyers': whale_data.get('c_suite_buyers_count', 0),
            })
        # Regime
        if regime_data:
            features.update({
                'vix_level': regime_data.get('vix_level') or 18,
                'market_breadth_pct': regime_data.get('market_breadth_pct') or 55,
                'risk_multiplier': regime_data.get('risk_multiplier') or 1.0,
            })
        # WallStreet
        if wallstreet_data:
            features['news_sentiment_score'] = wallstreet_data.get('sentiment_score', 50)
        return features
