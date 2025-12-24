"""Risk scoring with combination detection and signal velocity."""

from typing import List, Dict, Any
from datetime import datetime, timedelta

from app.core.constants import (
    PREDICTIVE_WEIGHTS,
    BASE_SEVERITY,
    SIGNAL_COMBINATIONS,
    VELOCITY_THRESHOLDS,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class RiskScorer:
    """
    Calculate risk scores using:
    1. Individual signal predictive weights
    2. Signal combination patterns
    3. Signal velocity (frequency over time)
    """

    def __init__(self):
        self.max_base_score = 100
        self.combination_bonus_cap = 30  # Max additional points from combinations
        self.velocity_bonus_cap = 15     # Max additional points from velocity
        self.bankruptcy_floor = 90       # Min score if BANKRUPTCY_FILING detected

    def detect_combinations(
        self,
        signals: List[Dict[str, Any]],
        lookback_days: int = 180,
    ) -> List[Dict[str, Any]]:
        """
        Detect dangerous signal combinations within a time window.

        Args:
            signals: List of signal dicts with 'type' and 'date' fields
            lookback_days: How far back to look for combinations

        Returns:
            List of detected combination patterns
        """
        if not signals:
            return []

        # Get signal types present
        signal_types = set(s.get("type") for s in signals)

        # Filter to recent signals for velocity/combination detection
        cutoff_date = datetime.now() - timedelta(days=lookback_days)
        recent_signals = []

        for s in signals:
            try:
                signal_date = s.get("date", "")
                if isinstance(signal_date, str) and signal_date:
                    # Parse date string
                    parsed_date = datetime.strptime(signal_date[:10], "%Y-%m-%d")
                    if parsed_date >= cutoff_date:
                        recent_signals.append(s)
                else:
                    # If no date, include the signal
                    recent_signals.append(s)
            except (ValueError, TypeError):
                # If date parsing fails, include the signal
                recent_signals.append(s)

        recent_types = set(s.get("type") for s in recent_signals)

        # Check each combination pattern
        detected_combinations = []

        for combo_name, combo_config in SIGNAL_COMBINATIONS.items():
            required_signals = set(combo_config["signals"])

            # Check if all required signals are present in recent signals
            if required_signals.issubset(recent_types):
                detected_combinations.append({
                    "pattern": combo_name,
                    "signals": list(required_signals),
                    "multiplier": combo_config["multiplier"],
                    "description": combo_config["description"],
                    "risk_level": combo_config["risk_level"],
                })

                logger.info(
                    f"Detected combination: {combo_name} - {combo_config['description']}"
                )

        return detected_combinations

    def calculate_velocity(
        self,
        signals: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Calculate signal velocity (frequency over time).

        Returns velocity info with applicable multiplier.
        """
        if not signals:
            return {"velocity": "LOW", "multiplier": 1.0, "signals_per_90_days": 0}

        # Count signals in last 90 days
        cutoff_90 = datetime.now() - timedelta(days=90)
        recent_count = 0

        for s in signals:
            try:
                signal_date = s.get("date", "")
                if isinstance(signal_date, str) and signal_date:
                    parsed_date = datetime.strptime(signal_date[:10], "%Y-%m-%d")
                    if parsed_date >= cutoff_90:
                        recent_count += 1
            except (ValueError, TypeError):
                pass

        # Determine velocity level
        velocity_info = {
            "velocity": "LOW",
            "multiplier": 1.0,
            "signals_per_90_days": recent_count,
        }

        if recent_count >= VELOCITY_THRESHOLDS["EXTREME_VELOCITY"]["signals_count"]:
            velocity_info = {
                "velocity": "EXTREME",
                "multiplier": VELOCITY_THRESHOLDS["EXTREME_VELOCITY"]["multiplier"],
                "signals_per_90_days": recent_count,
                "description": VELOCITY_THRESHOLDS["EXTREME_VELOCITY"]["description"],
            }
        elif recent_count >= VELOCITY_THRESHOLDS["HIGH_VELOCITY"]["signals_count"]:
            velocity_info = {
                "velocity": "HIGH",
                "multiplier": VELOCITY_THRESHOLDS["HIGH_VELOCITY"]["multiplier"],
                "signals_per_90_days": recent_count,
                "description": VELOCITY_THRESHOLDS["HIGH_VELOCITY"]["description"],
            }

        if velocity_info["velocity"] != "LOW":
            logger.info(
                f"Signal velocity: {velocity_info['velocity']} "
                f"({recent_count} signals in 90 days)"
            )

        return velocity_info

    def calculate_risk_score(
        self,
        signals: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive risk score.

        Components:
        1. Base score from individual signal weights
        2. Combination bonus for dangerous patterns
        3. Velocity bonus for rapid signal accumulation

        Returns:
            Dict with score, components, and breakdown
        """
        if not signals:
            return {
                "score": 0,
                "level": "LOW",
                "base_score": 0,
                "combination_bonus": 0,
                "velocity_bonus": 0,
                "combinations_detected": [],
                "velocity_info": {"velocity": "LOW", "multiplier": 1.0},
                "signal_breakdown": [],
            }

        # Check for bankruptcy filing - apply floor score
        has_bankruptcy = any(s.get("type") == "BANKRUPTCY_FILING" for s in signals)

        # 1. Calculate base score from individual signals
        signal_scores = []
        total_weight = 0

        for s in signals:
            signal_type = s.get("type", "")
            weight = PREDICTIVE_WEIGHTS.get(signal_type, 3)
            severity = s.get("severity", BASE_SEVERITY.get(signal_type, 5))

            # Signal score = weight * (severity / 10)
            signal_score = weight * (severity / 10)
            total_weight += signal_score

            signal_scores.append({
                "type": signal_type,
                "predictive_weight": weight,
                "severity": severity,
                "contribution": round(signal_score, 2),
            })

        # Normalize base score to 0-70 range (leave room for bonuses)
        max_possible = len(signals) * 10  # Max if all weights were 10
        base_score = min(70, (total_weight / max(max_possible, 1)) * 100)

        # 2. Calculate combination bonus
        combinations = self.detect_combinations(signals)
        combination_bonus = 0

        if combinations:
            # Take the highest multiplier from detected combinations
            max_multiplier = max(c["multiplier"] for c in combinations)
            # Bonus = base contribution scaled by multiplier - 1
            combination_bonus = min(
                self.combination_bonus_cap,
                base_score * (max_multiplier - 1)
            )

        # 3. Calculate velocity bonus
        velocity_info = self.calculate_velocity(signals)
        velocity_bonus = 0

        if velocity_info["multiplier"] > 1.0:
            velocity_bonus = min(
                self.velocity_bonus_cap,
                base_score * (velocity_info["multiplier"] - 1)
            )

        # Final score
        final_score = min(100, base_score + combination_bonus + velocity_bonus)

        # Apply bankruptcy floor if detected
        if has_bankruptcy and final_score < self.bankruptcy_floor:
            logger.info(f"Applying bankruptcy floor: {final_score} -> {self.bankruptcy_floor}")
            final_score = self.bankruptcy_floor

        final_score = round(final_score)

        # Determine risk level
        if final_score >= 70:
            level = "CRITICAL"
        elif final_score >= 50:
            level = "HIGH"
        elif final_score >= 30:
            level = "ELEVATED"
        else:
            level = "LOW"

        return {
            "score": final_score,
            "level": level,
            "base_score": round(base_score),
            "combination_bonus": round(combination_bonus),
            "velocity_bonus": round(velocity_bonus),
            "combinations_detected": combinations,
            "velocity_info": velocity_info,
            "signal_breakdown": sorted(
                signal_scores,
                key=lambda x: x["contribution"],
                reverse=True
            ),
        }


# Singleton instance
risk_scorer = RiskScorer()
