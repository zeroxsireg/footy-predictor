"""Pick selection and ranking logic for daily analysis."""

from typing import List, Dict, Any
from .daily_models import DailyPick


class PickSelector:
    """Handles pick selection and ranking logic."""
    
    def __init__(self):
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
    
    def _calculate_combo_odds(self, picks: List[DailyPick]) -> float:
        """
        Calcola le quote totali di una combinazione.
        USA LE QUOTE REALI quando disponibili, altrimenti stima dalla probabilità.
        """
        total_odds = 1.0
        
        for pick in picks:
            if pick.real_odds:
                # USA QUOTE REALI dal bookmaker
                total_odds *= pick.real_odds
            else:
                # FALLBACK: Stima dalla probabilità (formula inversa)
                # Odds = 100 / Probabilità
                # Esempio: 75% → 100/75 = 1.33, 50% → 100/50 = 2.0
                if pick.percentage > 0:
                    estimated = 100 / pick.percentage
                    total_odds *= max(1.01, estimated)  # Minimo 1.01
                else:
                    total_odds *= 2.0  # Fallback generico
        
        return round(total_odds, 2)

    def _generate_combinations(self, top_picks: List[DailyPick]) -> List:
        """Generate optimal betting combinations."""
        combinations = []
        
        if len(top_picks) < 3:
            return combinations
        
        # 3-pick combination (diversified)
        if len(top_picks) >= 3:
            combo_3 = top_picks[:3]
            avg_confidence = sum(p.percentage for p in combo_3) / 3
            estimated_odds = self._calculate_combo_odds(combo_3)
            
            combinations.append({
                "picks": combo_3,
                "confidence": avg_confidence,
                "estimated_odds": estimated_odds,
                "description": "3 Picks - Diversificati"
            })
        
        # 4-pick combination
        if len(top_picks) >= 4:
            combo_4 = top_picks[:4]
            avg_confidence = sum(p.percentage for p in combo_4) / 4
            estimated_odds = self._calculate_combo_odds(combo_4)
            
            combinations.append({
                "picks": combo_4,
                "confidence": avg_confidence,
                "estimated_odds": estimated_odds,
                "description": "4 Picks - Bilanciati"
            })
        
        # 5-pick combination (maximum diversification)
        if len(top_picks) >= 5:
            combo_5 = top_picks[:5]
            avg_confidence = sum(p.percentage for p in combo_5) / 5
            estimated_odds = self._calculate_combo_odds(combo_5)
            
            combinations.append({
                "picks": combo_5,
                "confidence": avg_confidence,
                "estimated_odds": estimated_odds,
                "description": "5 Picks - Massima Diversificazione"
            })
        
        # High confidence only combination
        high_conf_picks = [p for p in top_picks if p.confidence == "HIGH"]
        if len(high_conf_picks) >= 3:
            combo_high = high_conf_picks[:3]
            avg_confidence = sum(p.percentage for p in combo_high) / 3
            estimated_odds = self._calculate_combo_odds(combo_high)
            
            combinations.append({
                "picks": combo_high,
                "confidence": avg_confidence,
                "estimated_odds": estimated_odds,
                "description": "3 Picks - Solo High Confidence"
            })
        
        # Mixed combination (2 high + 1 medium)
        if len(high_conf_picks) >= 2:
            medium_conf_picks = [p for p in top_picks if p.confidence == "MEDIUM"]
            if medium_conf_picks:
                combo_mixed = high_conf_picks[:2] + [medium_conf_picks[0]]
                avg_confidence = sum(p.percentage for p in combo_mixed) / 3
                estimated_odds = self._calculate_combo_odds(combo_mixed)
                
                combinations.append({
                    "picks": combo_mixed,
                    "confidence": avg_confidence,
                    "estimated_odds": estimated_odds,
                    "description": "Misto - 2 High + 1 Medium"
                })
        
        return combinations

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
            "best_combination_confidence": combinations[0]["confidence"] if combinations else 0
        }
