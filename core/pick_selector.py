"""Pick selection and ranking logic for daily analysis."""

from typing import List, Dict, Any, Optional
from .daily_models import DailyPick
from .value_selection import MIN_EV_THRESHOLD, select_value_picks


class PickSelector:
    """Handles pick selection and ranking logic."""
    
    def __init__(self):
        self.skipped_combinations = 0  # combos dropped for missing real quotes
        # Market diversity weights - Bilanciati per varietà
        self.market_weights = {
            # Match Goals (PRIORITÀ ALTA)
            "Match Goals": 1.3,
            
            # Team-specific Goals
            "Goals": 1.2,
            
            # Match Result (PRIORITÀ ALTA)
            "Match Result": 1.4,
            
            # Both Teams to Score (PRIORITÀ ALTA)
            "Both Teams to Score": 1.3,
            
            # Shots markets
            "Total Shots": 1.0,
            "Total Shots on Goal": 1.0,
            "Shots": 0.9,
            
            # Corners markets  
            "Total Corners": 1.0,
            "Corners": 0.9,
            
            # Cards markets (peso normale ora)
            "Total Cards": 1.0,
            "Cards": 0.9
        }
        
        # Confidence weights
        self.confidence_weights = {
            "HIGH": 3.0,
            "MEDIUM": 2.0,
            "LOW": 1.0
        }

    def _select_best_pick_with_diversity(self, recommendations: List, existing_picks: List[DailyPick]) -> any:
        """Select the best pick considering market diversity and value."""
        if not recommendations:
            return None
        
        # Count existing market usage
        market_usage = {}
        for pick in existing_picks:
            market = pick.market
            market_usage[market] = market_usage.get(market, 0) + 1
        
        best_pick = None
        best_score = -1
        
        for rec in recommendations:
            # Base score from confidence and percentage
            confidence_score = self.confidence_weights.get(rec.confidence, 1.0)
            percentage_score = rec.percentage / 100.0
            
            # Diversity bonus (prefer markets not heavily used)
            market = rec.market
            # Normalize market name for diversity calculation (remove team names)
            normalized_market = self._normalize_market_name(market)
            
            # Count usage of normalized market type
            normalized_usage_count = 0
            for existing_market in market_usage:
                if self._normalize_market_name(existing_market) == normalized_market:
                    normalized_usage_count += market_usage[existing_market]
            
            diversity_bonus = max(0, 5 - normalized_usage_count) / 5.0  # 0-1 scale
            
            # Market preference weight (use normalized market name)
            market_weight = self.market_weights.get(normalized_market, 0.8)
            
            # Realism penalty (ridotto per non penalizzare troppo)
            realism_penalty = 1.0
            if rec.percentage >= 98:
                realism_penalty = 0.9  # Penalità minima per percentuali molto alte
            elif rec.percentage <= 5:
                realism_penalty = 0.8  # Penalize overly pessimistic
            
            # Value score (consider real odds if available)
            value_score = 1.0
            if hasattr(rec, 'real_odds') and rec.real_odds:
                if rec.real_odds < 1.3:
                    value_score = 0.8  # Lower value for very low odds
                elif rec.real_odds >= 3.0:
                    value_score = 1.2  # Higher value for higher odds
            
            # Calculate total score
            total_score = (
                confidence_score * 0.3 +
                percentage_score * 0.3 +
                diversity_bonus * 0.2 +
                market_weight * 0.1 +
                value_score * 0.1
            ) * realism_penalty
            
            if total_score > best_score:
                best_score = total_score
                best_pick = rec
        
        return best_pick
    
    def _normalize_market_name(self, market_name: str) -> str:
        """Normalize market name for diversity calculation by removing team names."""
        # Remove team-specific prefixes
        if " Cards" in market_name:
            return "Cards"
        elif " Shots" in market_name:
            return "Shots"
        elif " Corners" in market_name:
            return "Corners"
        elif " Goals" in market_name:
            return "Goals"
        elif "Match Goals" in market_name:
            return "Match Goals"
        elif "Match Result" in market_name:
            return "Match Result"
        elif "Both Teams to Score" in market_name:
            return "Both Teams to Score"
        elif "Total Cards" in market_name:
            return "Total Cards"
        elif "Total Shots" in market_name:
            return "Total Shots"
        elif "Total Corners" in market_name:
            return "Total Corners"
        else:
            return market_name

    def _rank_picks(self, picks: List[DailyPick]) -> List[DailyPick]:
        """Rank picks by confidence score and return all picks sorted."""
        # Sort by confidence score (descending)
        sorted_picks = sorted(picks, key=lambda p: p.confidence_score, reverse=True)
        
        # Return ALL picks sorted (not just top 10)
        return sorted_picks
    
    def _calculate_combo_odds(self, picks: List[DailyPick]) -> Optional[float]:
        """
        Total odds of a combination, from REAL bookmaker quotes only.

        If any leg lacks a real quote the total is None ("quote incomplete"):
        no odds are ever invented from the model probability.
        """
        total_odds = 1.0
        for pick in picks:
            if not pick.real_odds or pick.real_odds <= 1.0:
                return None
            total_odds *= pick.real_odds
        return round(total_odds, 2)

    def _make_combo(self, picks: List[DailyPick], description: str) -> Optional[Dict]:
        """Build a combination dict, or None when any leg has no real quote."""
        total = self._calculate_combo_odds(picks)
        if total is None:
            self.skipped_combinations += 1
            return None
        return {
            "picks": picks,
            "confidence": sum(p.percentage for p in picks) / len(picks),
            "estimated_odds": total,
            "description": description,
        }

    def _generate_combinations(self, top_picks: List[DailyPick]) -> List:
        """Generate combinations; only those fully priced with real quotes are kept."""
        self.skipped_combinations = 0
        candidates = []
        if len(top_picks) < 3:
            return []
        candidates.append((top_picks[:3], "3 Picks - Diversificati"))
        if len(top_picks) >= 4:
            candidates.append((top_picks[:4], "4 Picks - Bilanciati"))
        if len(top_picks) >= 5:
            candidates.append((top_picks[:5], "5 Picks - Massima Diversificazione"))

        high = [p for p in top_picks if p.confidence == "HIGH"]
        if len(high) >= 3:
            candidates.append((high[:3], "3 Picks - Solo High Confidence"))
        medium = [p for p in top_picks if p.confidence == "MEDIUM"]
        if len(high) >= 2 and medium:
            candidates.append((high[:2] + [medium[0]], "Misto - 2 High + 1 Medium"))

        combos = (self._make_combo(picks, desc) for picks, desc in candidates)
        return [c for c in combos if c]

    def select_value_picks(self, picks: List[DailyPick], tau: float = MIN_EV_THRESHOLD,
                           limit: Optional[int] = None) -> List[DailyPick]:
        """Single-bet value mode: real quote + EV > tau, sorted by EV, Kelly-sized."""
        return select_value_picks(picks, tau, limit)

    def _create_summary(self, all_picks: List[DailyPick], top_picks: List[DailyPick], 
                       combinations: List) -> Dict[str, Any]:
        """Create analysis summary."""
        high_confidence_picks = len([p for p in all_picks if p.confidence == "HIGH"])
        medium_confidence_picks = len([p for p in all_picks if p.confidence == "MEDIUM"])
        low_confidence_picks = len([p for p in all_picks if p.confidence == "LOW"])
        
        average_confidence = sum(p.percentage for p in all_picks) / len(all_picks) if all_picks else 0
        
        return {
            "high_confidence_picks": high_confidence_picks,
            "medium_confidence_picks": medium_confidence_picks,
            "low_confidence_picks": low_confidence_picks,
            "average_confidence": average_confidence,
            "total_combinations": len(combinations),
            "combinations_skipped_no_odds": self.skipped_combinations,
            "best_combination_confidence": combinations[0]["confidence"] if combinations else 0
        }
