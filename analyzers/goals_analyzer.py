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
from core import shrinkage as sh


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

    # ── pure probability methods (single source of truth) ──────────────────────
    # These return raw probabilities in [0.0, 1.0].  The _analyze_* methods below
    # consume them to build (filtered) recommendations; the backtest consumes them
    # directly to score every match.  Keep the maths here and nowhere else.

    @staticmethod
    def _gpg(stats: TeamStats) -> float:
        """Goals scored per game, shrunk toward the league average (few games -> prior)."""
        return sh.shrink(stats.goals_for, stats.matches_played,
                         sh.PRIOR_GOALS_PER_TEAM_GAME, sh.K_GOALS)

    @staticmethod
    def _gpc(stats: TeamStats) -> float:
        """Goals conceded per game, shrunk toward the league average."""
        return sh.shrink(stats.goals_against, stats.matches_played,
                         sh.PRIOR_GOALS_PER_TEAM_GAME, sh.K_GOALS)

    @staticmethod
    def _score_rate(games: int, blanks: int) -> float:
        """P(team scores / concedes in a match) from games minus blank games, shrunk."""
        return sh.shrink(games - blanks, games, sh.PRIOR_SCORE_RATE, sh.K_SCORE_RATE)

    def match_goals_probabilities(self, home_stats: TeamStats, away_stats: TeamStats) -> dict:
        """P(Over N) for total match goals via Poisson, as fractions in [0, 1]."""
        lam = self._gpg(home_stats) + self._gpg(away_stats)
        return {
            f"over_{n}".replace(".", "_"): sh.clamp_probability(self._poisson_over_prob(lam, n))
            for n in (1.5, 2.5, 3.5)
        }

    def btts_yes_probability(self, home_stats: TeamStats, away_stats: TeamStats) -> float:
        """P(Both Teams To Score = Yes) as a fraction in [0, 1] (shrunk + clamped)."""
        home_scores = self._score_rate(home_stats.matches_played, home_stats.failed_to_score)
        away_scores = self._score_rate(away_stats.matches_played, away_stats.failed_to_score)
        home_concedes = self._score_rate(home_stats.matches_played, home_stats.clean_sheets)
        away_concedes = self._score_rate(away_stats.matches_played, away_stats.clean_sheets)
        btts_yes = home_scores * away_scores
        btts_adjusted = (btts_yes + (home_concedes + away_concedes) / 2) / 2
        return sh.clamp_probability(btts_adjusted)

    def _analyze_match_goals(self, home_stats: TeamStats, away_stats: TeamStats) -> List[BettingRecommendation]:
        """Analizza Match Goals (totali partita) con distribuzione di Poisson."""
        recommendations = []

        total_goals_expected = self._gpg(home_stats) + self._gpg(away_stats)

        # Probabilità Poisson per tutte le soglie
        probs = self.match_goals_probabilities(home_stats, away_stats)
        over_1_5_prob = probs["over_1_5"] * 100
        over_2_5_prob = probs["over_2_5"] * 100
        over_3_5_prob = probs["over_3_5"] * 100
        under_2_5_prob = 100 - over_2_5_prob
        under_3_5_prob = 100 - over_3_5_prob

        candidates = [
            ("Over 3.5", over_3_5_prob, 3),
            ("Over 2.5", over_2_5_prob, 2),
            ("Under 2.5", under_2_5_prob, 1),
            ("Under 3.5", under_3_5_prob, 0.5),
            ("Over 1.5", over_1_5_prob, 0),
        ]

        # Scegli max 2 picks: soglia più alta con prob >= 55%,
        # escludi Over 1.5 se esiste qualcosa di meglio
        has_better = any(prob >= 55 for sel, prob, _ in candidates if sel != "Over 1.5")
        valid = [
            (sel, prob, pri) for sel, prob, pri in candidates
            if prob >= 55 and not (sel == "Over 1.5" and has_better)
        ]
        valid.sort(key=lambda x: (x[2], x[1]), reverse=True)

        for sel, prob, _ in valid[:2]:
            recommendations.append(self._create_recommendation(
                market="Match Goals",
                selection=sel,
                probability=prob,
                reasoning=f"Attesi {total_goals_expected:.1f} gol (Poisson): {prob:.1f}% {sel.lower()}"
            ))

        return recommendations
    
    def _analyze_team_goals(self, home_stats: TeamStats, away_stats: TeamStats) -> List[BettingRecommendation]:
        """Analizza Team Goals (gol singola squadra) con distribuzione di Poisson."""
        recommendations = []

        expected_home = (self._gpg(home_stats) + self._gpc(away_stats)) / 2
        expected_away = (self._gpg(away_stats) + self._gpc(home_stats)) / 2

        for team_stats, expected, label in [
            (home_stats, expected_home, "in casa"),
            (away_stats, expected_away, "in trasferta"),
        ]:
            name = team_stats.team.name
            for threshold in [1.5, 2.5]:
                prob = self._poisson_over_prob(expected, threshold) * 100
                if prob >= self.LOW_CONFIDENCE:
                    recommendations.append(self._create_recommendation(
                        market=f"{name} Goals",
                        selection=f"Over {threshold}",
                        probability=prob,
                        reasoning=f"{name} attesi {expected:.1f} gol {label} (Poisson)"
                    ))

        return recommendations
    
    def _analyze_btts(self, home_stats: TeamStats, away_stats: TeamStats) -> List[BettingRecommendation]:
        """Analizza Both Teams To Score."""
        recommendations = []

        btts_adjusted = self.btts_yes_probability(home_stats, away_stats) * 100

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

