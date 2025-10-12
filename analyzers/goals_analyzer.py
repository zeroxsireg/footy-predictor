"""
Goals Analyzer - Analisi mercati legati ai gol.

Responsabile di:
- Match Goals (Over/Under totali)
- Team Goals (Over/Under per squadra)
- BTTS (Both Teams To Score)
"""

from typing import List
from .base import BaseAnalyzer
from core.models import TeamStats
from core.betting_models import BettingRecommendation


class GoalsAnalyzer(BaseAnalyzer):
    """Analyzer dedicato ai mercati GOL."""
    
    def get_required_stats(self) -> List[str]:
        """Statistiche necessarie per analisi gol."""
        return [
            'goals_per_game',
            'goals_conceded_per_game',
            'clean_sheets',  # intero, non percentage
            'failed_to_score',  # intero, non percentage
            'matches_played'
        ]
    
    def analyze(self, home_stats: TeamStats, away_stats: TeamStats, **kwargs) -> List[BettingRecommendation]:
        """
        Genera tutte le raccomandazioni legate ai gol.
        
        Returns:
            Lista combinata di Match Goals + Team Goals + BTTS
        """
        if not self._validate_stats(home_stats, away_stats):
            return []
        
        recommendations = []
        
        # 1. Match Goals (totali)
        recommendations.extend(self._analyze_match_goals(home_stats, away_stats))
        
        # 2. Team Goals (per squadra)
        recommendations.extend(self._analyze_team_goals(home_stats, away_stats))
        
        # 3. BTTS
        recommendations.extend(self._analyze_btts(home_stats, away_stats))
        
        return recommendations
    
    def _analyze_match_goals(self, home_stats: TeamStats, away_stats: TeamStats) -> List[BettingRecommendation]:
        """Analizza Match Goals (totali partita)."""
        recommendations = []
        
        # Calcola gol attesi
        home_goals_avg = home_stats.goals_per_game
        away_goals_avg = away_stats.goals_per_game
        total_goals_expected = home_goals_avg + away_goals_avg
        
        # STRATEGIA INTELLIGENTE: Genera SOLO la soglia ottimale in base ai gol attesi
        # - Se >= 3.0 gol: Over 2.5 (quote migliori)
        # - Se 2.0-3.0 gol: Over/Under 2.5 (quello con prob 60-85%)
        # - Se < 2.0 gol: Under 2.5 (difese solide)
        
        # Calcola probabilità per tutte le soglie
        if total_goals_expected >= 1.5:
            over_1_5_prob = min(95, 50 + (total_goals_expected - 1.5) * 25)
        else:
            over_1_5_prob = max(5, (total_goals_expected / 1.5) * 50)
        
        if total_goals_expected >= 2.5:
            over_2_5_prob = min(90, 50 + (total_goals_expected - 2.5) * 20)
        else:
            over_2_5_prob = max(10, (total_goals_expected / 2.5) * 50)
        
        if total_goals_expected >= 3.5:
            over_3_5_prob = min(85, 50 + (total_goals_expected - 3.5) * 15)
        else:
            over_3_5_prob = max(5, (total_goals_expected / 3.5) * 50)
        
        under_2_5_prob = 100 - over_2_5_prob
        under_3_5_prob = 100 - over_3_5_prob
        
        # NUOVA STRATEGIA: Seleziona la soglia PIÙ ALTA con prob >= 60%
        # Se 3.4 gol attesi → Over 2.5 (non Over 1.5!)
        candidates = [
            ("Over 3.5", over_3_5_prob),
            ("Over 2.5", over_2_5_prob),
            ("Under 2.5", under_2_5_prob),
            ("Under 3.5", under_3_5_prob),
            ("Over 1.5", over_1_5_prob)
        ]
        
        # Filtra candidati validi con STRATEGIA AGGRESSIVA
        # Esclude Over 1.5 se esistono soglie più alte con prob >= 55%
        has_higher_threshold = any(
            prob >= 55 for sel, prob in candidates 
            if sel in ["Over 2.5", "Over 3.5", "Under 2.5"]
        )
        
        valid_candidates = []
        for selection, prob in candidates:
            # Escludi Over 1.5 se ci sono soglie migliori
            if "Over 1.5" in selection and has_higher_threshold:
                continue
            
            # Accetta soglie con prob >= 55% (più aggressivo)
            if prob >= 55:
                valid_candidates.append((selection, prob))
        
        # Ordina: preferisci Over più alti o Under più bassi (più value)
        def get_priority(sel_prob):
            selection, prob = sel_prob
            if "Over 3.5" in selection:
                return (3, prob)  # Massima priorità
            elif "Over 2.5" in selection:
                return (2, prob)
            elif "Under 2.5" in selection:
                return (1, prob)
            elif "Under 3.5" in selection:
                return (0.5, prob)
            else:  # Over 1.5
                return (0, prob)  # Minima priorità
        
        valid_candidates.sort(key=get_priority, reverse=True)
        
        # Genera raccomandazioni per i top 2 picks
        for selection, prob in valid_candidates[:2]:  # TOP 2
            recommendations.append(self._create_recommendation(
                market="Match Goals",
                selection=selection,
                probability=prob,
                reasoning=f"Attesi {total_goals_expected:.1f} gol: {prob:.1f}% {selection.lower()}"
            ))
        
        return recommendations
    
    def _analyze_team_goals(self, home_stats: TeamStats, away_stats: TeamStats) -> List[BettingRecommendation]:
        """Analizza Team Goals (gol singola squadra)."""
        recommendations = []
        
        home_goals_avg = home_stats.goals_per_game
        away_goals_avg = away_stats.goals_per_game
        home_conceded_avg = home_stats.goals_conceded_per_game
        away_conceded_avg = away_stats.goals_conceded_per_game
        
        # Expected goals per squadra (considera anche difesa avversaria)
        expected_home_goals = (home_goals_avg + away_conceded_avg) / 2
        expected_away_goals = (away_goals_avg + home_conceded_avg) / 2
        
        # Home Team Over 1.5
        home_over_1_5_prob = min(90, max(10, (expected_home_goals - 1.5) / 1.5 * 100))
        if home_over_1_5_prob >= self.LOW_CONFIDENCE:
            recommendations.append(self._create_recommendation(
                market=f"{home_stats.team.name} Goals",
                selection="Over 1.5",
                probability=home_over_1_5_prob,
                reasoning=f"{home_stats.team.name} attesi {expected_home_goals:.1f} gol"
            ))
        
        # Home Team Over 2.5
        home_over_2_5_prob = min(80, max(5, (expected_home_goals - 2.5) / 2.5 * 100))
        if home_over_2_5_prob >= self.LOW_CONFIDENCE:
            recommendations.append(self._create_recommendation(
                market=f"{home_stats.team.name} Goals",
                selection="Over 2.5",
                probability=home_over_2_5_prob,
                reasoning=f"{home_stats.team.name} alta produzione offensiva: {expected_home_goals:.1f} gol attesi"
            ))
        
        # Away Team Over 1.5
        away_over_1_5_prob = min(90, max(10, (expected_away_goals - 1.5) / 1.5 * 100))
        if away_over_1_5_prob >= self.LOW_CONFIDENCE:
            recommendations.append(self._create_recommendation(
                market=f"{away_stats.team.name} Goals",
                selection="Over 1.5",
                probability=away_over_1_5_prob,
                reasoning=f"{away_stats.team.name} attesi {expected_away_goals:.1f} gol"
            ))
        
        # Away Team Over 2.5
        away_over_2_5_prob = min(80, max(5, (expected_away_goals - 2.5) / 2.5 * 100))
        if away_over_2_5_prob >= self.LOW_CONFIDENCE:
            recommendations.append(self._create_recommendation(
                market=f"{away_stats.team.name} Goals",
                selection="Over 2.5",
                probability=away_over_2_5_prob,
                reasoning=f"{away_stats.team.name} alta produzione in trasferta: {expected_away_goals:.1f} gol attesi"
            ))
        
        return recommendations
    
    def _analyze_btts(self, home_stats: TeamStats, away_stats: TeamStats) -> List[BettingRecommendation]:
        """Analizza Both Teams To Score."""
        recommendations = []
        
        # Calcola percentuali da attributi interi
        home_scores_prob = 100 - ((home_stats.failed_to_score / home_stats.matches_played) * 100 if home_stats.matches_played > 0 else 50)
        away_scores_prob = 100 - ((away_stats.failed_to_score / away_stats.matches_played) * 100 if away_stats.matches_played > 0 else 50)
        
        # BTTS Yes = entrambe segnano
        btts_yes_prob = (home_scores_prob * away_scores_prob) / 100
        
        # Aggiusta per clean sheets (se squadre subiscono spesso)
        home_concedes_prob = 100 - ((home_stats.clean_sheets / home_stats.matches_played) * 100 if home_stats.matches_played > 0 else 50)
        away_concedes_prob = 100 - ((away_stats.clean_sheets / away_stats.matches_played) * 100 if away_stats.matches_played > 0 else 50)
        btts_adjusted = (btts_yes_prob + ((home_concedes_prob + away_concedes_prob) / 2)) / 2
        
        if btts_adjusted >= self.LOW_CONFIDENCE:
            recommendations.append(self._create_recommendation(
                market="Both Teams to Score",
                selection="Yes",
                probability=btts_adjusted,
                reasoning=f"Entrambe con buon attacco e difese permeabili: {btts_adjusted:.1f}% BTTS"
            ))
        
        # BTTS No
        btts_no_prob = 100 - btts_adjusted
        if btts_no_prob >= self.LOW_CONFIDENCE:
            recommendations.append(self._create_recommendation(
                market="Both Teams to Score",
                selection="No",
                probability=btts_no_prob,
                reasoning=f"Almeno una squadra con difficoltà offensive: {btts_no_prob:.1f}% BTTS No"
            ))
        
        return recommendations

