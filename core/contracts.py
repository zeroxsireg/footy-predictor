"""
Shared data contracts of the lean pipeline (Serie A singles, paper trading).

Pure dataclasses, no logic: every module of the pipeline imports its inputs and
outputs from here so that parallel work fits together.

Pipeline:  market_data (fixtures, prices, results)  ->  predictor (probabilities)
           ->  value_engine (EV, stake)  ->  ledger (persist)  ->  CLI (report).

Rules (.agents/GEMINI.md): analyzers/predictors estimate probabilities only (rule 6);
odds, de-vigging, EV and staking live in value_engine (rules 6-8); every quote carries
the real bookmaker that offered it (rule 11).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

# Markets of the lean pipeline: the only ones with a validated model and historical odds.
MARKET_1X2 = "1X2"          # selections: "1", "X", "2"
MARKET_OU25 = "OU_2.5"      # selections: "over", "under"

# Paper-trading strategies, each with its own bankroll in the ledger.
STRATEGY_RAW = "raw"            # P used = model probability
STRATEGY_BLEND50 = "blend50"    # P used = 0.5 * model + 0.5 * de-vigged market
STRATEGY_SHARP_GAP = "sharp_gap"  # model-free: Bet365 price vs de-vigged Pinnacle fair price
STRATEGIES = (STRATEGY_RAW, STRATEGY_BLEND50, STRATEGY_SHARP_GAP)


@dataclass(frozen=True)
class FixtureRef:
    """An upcoming (or past) league fixture."""
    fixture_id: int
    kickoff: datetime               # timezone-aware (UTC)
    home: str
    away: str
    home_id: int
    away_id: int
    league_id: int
    season: int
    round: str = ""
    referee: Optional[str] = None
    status: str = "NS"              # API short status: NS, FT, ...


@dataclass(frozen=True)
class MatchProbs:
    """Model probabilities for one fixture (pure estimate, no odds)."""
    fixture_id: int
    p1: float
    px: float
    p2: float
    p_over_2_5: float
    model: str                      # model identifier/version, e.g. "xg_poisson_v1"

    def validate(self) -> None:
        if abs(self.p1 + self.px + self.p2 - 1.0) > 1e-6:
            raise ValueError("1X2 probabilities must sum to 1")
        for p in (self.p1, self.px, self.p2, self.p_over_2_5):
            if not 0.0 <= p <= 1.0:
                raise ValueError("probability out of [0, 1]")


@dataclass(frozen=True)
class PriceQuote:
    """Decimal odds of ONE market from ONE bookmaker (never mixed across bookmakers)."""
    fixture_id: int
    market: str                     # MARKET_1X2 | MARKET_OU25
    bookmaker: str                  # real provider name, e.g. "Bet365"
    bookmaker_id: int
    odds: Dict[str, float]          # {"1":..,"X":..,"2":..} or {"over":..,"under":..}
    captured_at: datetime           # timezone-aware (UTC): when we read the price


@dataclass(frozen=True)
class FixtureResult:
    fixture_id: int
    status: str                     # "FT" when finished
    home_goals: Optional[int]
    away_goals: Optional[int]
    booked_player_ids: List[int] = field(default_factory=list)   # players with a yellow card

    @property
    def finished(self) -> bool:
        return self.status == "FT" and self.home_goals is not None and self.away_goals is not None


@dataclass
class BetCandidate:
    """A single bet the value engine considers/selects (paper or real)."""
    fixture_id: int
    strategy: str
    market: str
    selection: str
    odds: float
    bookmaker: str
    p_model: float                  # raw model probability of the selection
    p_used: float                   # probability used for EV (depends on strategy)
    p_fair: float                   # de-vigged (Shin) probability of the reference market
    ev: float                       # EV = p_used * odds - 1   (fraction, 0.03 = +3%)
    stake_fraction: float = 0.0     # fraction of the strategy bankroll (fractional Kelly, capped)
    stake_amount: float = 0.0       # currency units, rounded
    created_at: Optional[datetime] = None


@dataclass(frozen=True)
class PlayerCandidate:
    """A player at risk of a yellow card (probability only: the API offers no quotes)."""
    fixture_id: int
    player_id: int
    name: str
    team: str
    position: str
    p_booked_given_plays: float     # from the shared player card model
    start_prob: float               # probability of playing (probable XI / official lineup)
    p_booked: float                 # p_booked_given_plays * start_prob (ranking key)
    note: str = ""


# ── "Pronostici probabili" (tips): goal-based markets from ONE joint score matrix ──────────
# Excluded on purpose (user decision): corners, shots, goalscorers. Yellow cards of players
# are handled separately by PlayerCandidate (probability only, no quotes available).

TIP_MIN_EDGE = 0.03            # min_odds = fair_odds * (1 + TIP_MIN_EDGE)  (rule 7, tau = 3%)
MAX_MULTIPLE_LEGS = 3          # multiples: 2-3 legs, always from DIFFERENT fixtures


def _build_tip_catalog() -> Dict[str, tuple]:
    """key -> (italian label, family). Keys are stable identifiers shared by all modules."""
    cat: Dict[str, tuple] = {}
    for s, lab in (("1", "1"), ("X", "X"), ("2", "2")):
        cat[f"R_{s}"] = (f"Esito {lab}", "result")
    for dc in ("1X", "X2", "12"):
        cat[f"DC_{dc}"] = (f"Doppia chance {dc}", "doublechance")
    for line in ("1.5", "2.5", "3.5", "4.5"):
        it = line.replace(".", ",")
        cat[f"OV_{line}"] = (f"Over {it}", "totals")
        cat[f"UN_{line}"] = (f"Under {it}", "totals")
    for side, name in (("HOME", "Casa"), ("AWAY", "Ospite")):
        for line in ("0.5", "1.5", "2.5"):
            it = line.replace(".", ",")
            cat[f"{side}_OV_{line}"] = (f"{name} over {it} gol", "team_totals")
        cat[f"{side}_UN_1.5"] = (f"{name} under 1,5 gol", "team_totals")
    cat["GG"] = ("Gol (entrambe segnano)", "btts")
    cat["NG"] = ("NoGol", "btts")
    for lo, hi in ((1, 2), (2, 3), (1, 3), (1, 4), (2, 4), (2, 5)):
        cat[f"MGT_{lo}_{hi}"] = (f"Multigol {lo}-{hi}", "multigol")
    for side, name in (("H", "casa"), ("A", "ospite")):
        for lo, hi in ((1, 2), (1, 3), (1, 4), (2, 4), (2, 5)):
            cat[f"MG{side}_{lo}_{hi}"] = (f"Multigol {name} {lo}-{hi}", "multigol")
    # Same-match combos: result / double chance  x  total goals (joint probability from the matrix).
    bases = (("R_1", "1"), ("R_2", "2"), ("DC_1X", "1X"), ("DC_X2", "X2"), ("DC_12", "12"))
    for base, base_label in bases:
        for tot in ("OV_1.5", "OV_2.5", "UN_3.5", "UN_4.5"):
            it = ("Over " if tot.startswith("OV") else "Under ") + tot.split("_")[1].replace(".", ",")
            cat[f"{base}+{tot}"] = (f"{base_label} + {it}", "combo")
    return cat


TIP_CATALOG = _build_tip_catalog()      # e.g. "DC_X2+UN_4.5" -> ("X2 + Under 4,5", "combo")


@dataclass(frozen=True)
class Tip:
    """One probable pick for one fixture (probability from the joint score matrix)."""
    fixture_id: int
    key: str                        # a key of TIP_CATALOG
    label: str                      # Italian label
    family: str
    probability: float
    fair_odds: float                # 1 / probability
    min_odds: float                 # fair_odds * (1 + TIP_MIN_EDGE): play only at or above this quote
    reliability: str = "media"      # "alta" | "media" | "bassa", from measured out-of-sample skill


@dataclass(frozen=True)
class TipQuote:
    """A real quote for a tip key (only for markets the API exposes; one bookmaker)."""
    fixture_id: int
    key: str
    bookmaker: str
    bookmaker_id: int
    odds: float
    captured_at: datetime


@dataclass(frozen=True)
class Multiple:
    """2-3 tips from DIFFERENT fixtures. Probability = product (independent matches)."""
    legs: tuple                     # tuple of Tip, len 2..MAX_MULTIPLE_LEGS
    probability: float
    fair_odds: float
    min_odds: float
