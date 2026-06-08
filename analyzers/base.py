"""
Base Analyzer - Classe base per tutti gli analyzer di mercato.

Fornisce funzionalità comuni e struttura standard.
"""

import math
from typing import List
from abc import ABC, abstractmethod
from core.models import TeamStats
from core.betting_models import BettingRecommendation


class BaseAnalyzer(ABC):
    """
    Classe base per tutti gli analyzer di mercato.
    
    Ogni analyzer deve:
    1. Dichiarare quali dati statistici necessita
    2. Implementare analyze() per generare raccomandazioni
    3. Usare soglie confidence standard
    """
    
    # Soglie confidence standard
    HIGH_CONFIDENCE = 55.0
    MEDIUM_CONFIDENCE = 40.0
    LOW_CONFIDENCE = 45.0  # Alzato da 25% -> Solo picks di qualità (minimo 45%)
    
    def __init__(self):
        """Inizializza analyzer con soglie confidence."""
        pass
    
    @abstractmethod
    def get_required_stats(self) -> List[str]:
        """
        Ritorna la lista di statistiche necessarie per questo analyzer.
        
        Returns:
            List[str]: Lista di nomi attributi di TeamStats necessari
            
        Esempio:
            return ['goals_per_game', 'goals_conceded_per_game', 'clean_sheets_percentage']
        """
        pass
    
    @abstractmethod
    def analyze(self, home_stats: TeamStats, away_stats: TeamStats, **kwargs) -> List[BettingRecommendation]:
        """
        Analizza e genera raccomandazioni per questo mercato.
        
        Args:
            home_stats: Statistiche squadra casa
            away_stats: Statistiche squadra trasferta
            **kwargs: Parametri opzionali (es. home_position, away_position)
            
        Returns:
            List[BettingRecommendation]: Lista di raccomandazioni per questo mercato
        """
        pass
    
    def _get_confidence_level(self, probability: float) -> str:
        """
        Determina il livello di confidence basato sulla probabilità.
        
        Args:
            probability: Probabilità in percentuale (0-100)
            
        Returns:
            str: "HIGH", "MEDIUM", o "LOW"
        """
        if probability >= self.HIGH_CONFIDENCE:
            return "HIGH"
        elif probability >= self.MEDIUM_CONFIDENCE:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _create_recommendation(self, market: str, selection: str, probability: float, 
                              odds_range: str = None, reasoning: str = "") -> BettingRecommendation:
        """
        Helper per creare una raccomandazione standardizzata.
        
        Args:
            market: Nome mercato (es. "Match Goals")
            selection: Selezione (es. "Over 2.5")
            probability: Probabilità in percentuale
            odds_range: DEPRECATO - Non più usato, quote reali da OddsFetcher
            reasoning: Spiegazione della raccomandazione
            
        Returns:
            BettingRecommendation: Raccomandazione completa
        """
        return BettingRecommendation(
            market=market,
            selection=selection,
            confidence=self._get_confidence_level(probability),
            odds_range=None,  # DEPRECATO: quote reali vengono da OddsFetcher
            reasoning=reasoning,
            percentage=probability
        )
    
    @staticmethod
    def _poisson_over_prob(lambda_val: float, threshold: float) -> float:
        """
        P(X > threshold) con distribuzione di Poisson.

        P(X > 2.5) = P(X >= 3) = 1 - P(X=0) - P(X=1) - P(X=2)

        Args:
            lambda_val: valore atteso (λ) dell'evento (es. gol, corner, cartellini)
            threshold:  soglia non-intera (es. 2.5, 4.5)

        Returns:
            probabilità in [0.0, 1.0]
        """
        if lambda_val <= 0:
            return 0.0
        k_max = int(threshold)  # floor(2.5) = 2
        prob_under = sum(
            lambda_val**k * math.exp(-lambda_val) / math.factorial(k)
            for k in range(k_max + 1)
        )
        return max(0.0, min(1.0, 1.0 - prob_under))

    def _validate_stats(self, home_stats: TeamStats, away_stats: TeamStats) -> bool:
        """
        Valida che le statistiche necessarie siano disponibili.
        
        Args:
            home_stats: Statistiche squadra casa
            away_stats: Statistiche squadra trasferta
            
        Returns:
            bool: True se tutti i dati necessari sono disponibili
        """
        required = self.get_required_stats()
        
        for stat_name in required:
            if not hasattr(home_stats, stat_name) or not hasattr(away_stats, stat_name):
                return False
            
            home_value = getattr(home_stats, stat_name)
            away_value = getattr(away_stats, stat_name)
            
            if home_value is None or away_value is None:
                return False
        
        return True

