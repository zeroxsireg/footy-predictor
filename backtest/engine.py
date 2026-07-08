"""
Point-in-time replay engine.

The golden rule of a valid backtest: to predict match k, use ONLY information
available before match k. This module enforces that structurally — for every
match it (1) snapshots both teams' accumulated stats + the league averages,
(2) predicts, and only THEN (3) folds the actual result back in. Because the
update always happens after the prediction, future data can never leak into
the past.

Two consumption paths share the same replay:
- iter_scored_matches  -> ScoredMatch    (overall stats; used by the baseline)
- iter_match_contexts  -> MatchContext   (adds home/away splits + league
                                          averages; used by the strength models)
"""

from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Tuple

from core.models import Team, TeamStats
from analyzers.goals_analyzer import GoalsAnalyzer
from analyzers.result_analyzer import ResultAnalyzer


@dataclass
class TeamAccumulator:
    """Running, chronological tally of one team's results so far this season."""
    team_id: int
    name: str = ""
    matches_played: int = 0
    goals_for: int = 0
    goals_against: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    clean_sheets: int = 0
    failed_to_score: int = 0
    form: List[str] = field(default_factory=list)  # chronological "W"/"D"/"L"
    # home/away splits (needed by the strength models)
    home_matches: int = 0
    home_goals_for: int = 0
    home_goals_against: int = 0
    away_matches: int = 0
    away_goals_for: int = 0
    away_goals_against: int = 0

    def to_team_stats(self) -> TeamStats:
        """Snapshot the current tally as a TeamStats (what the model consumes)."""
        return TeamStats(
            team=Team(id=self.team_id, name=self.name),
            matches_played=self.matches_played,
            wins=self.wins,
            draws=self.draws,
            losses=self.losses,
            goals_for=self.goals_for,
            goals_against=self.goals_against,
            shots_total=0,
            shots_on_target=0,
            corners=0,
            yellow_cards=0,
            red_cards=0,
            form="".join(self.form),
            clean_sheets=self.clean_sheets,
            failed_to_score=self.failed_to_score,
        )

    def update(self, scored: int, conceded: int, is_home: bool | None = None) -> None:
        """Fold one played match into the tally (called AFTER predicting it)."""
        self.matches_played += 1
        self.goals_for += scored
        self.goals_against += conceded
        if conceded == 0:
            self.clean_sheets += 1
        if scored == 0:
            self.failed_to_score += 1
        if scored > conceded:
            self.wins += 1
            self.form.append("W")
        elif scored == conceded:
            self.draws += 1
            self.form.append("D")
        else:
            self.losses += 1
            self.form.append("L")

        if is_home is True:
            self.home_matches += 1
            self.home_goals_for += scored
            self.home_goals_against += conceded
        elif is_home is False:
            self.away_matches += 1
            self.away_goals_for += scored
            self.away_goals_against += conceded


@dataclass
class LeagueState:
    """League-wide running totals, used for home/away scoring baselines."""
    matches: int = 0
    home_goals: int = 0
    away_goals: int = 0

    # Sensible priors used before enough matches exist (typical top-league rates).
    DEFAULT_HOME_AVG = 1.5
    DEFAULT_AWAY_AVG = 1.1

    def home_avg(self) -> float:
        return self.home_goals / self.matches if self.matches > 0 else self.DEFAULT_HOME_AVG

    def away_avg(self) -> float:
        return self.away_goals / self.matches if self.matches > 0 else self.DEFAULT_AWAY_AVG

    def update(self, home_goals: int, away_goals: int) -> None:
        self.matches += 1
        self.home_goals += home_goals
        self.away_goals += away_goals


@dataclass
class ScoredMatch:
    """A single match predicted with pre-match stats, plus its real result."""
    date: str
    home_name: str
    away_name: str
    home_stats: TeamStats   # snapshot BEFORE this match
    away_stats: TeamStats   # snapshot BEFORE this match
    home_goals: int
    away_goals: int

    @property
    def total_goals(self) -> int:
        return self.home_goals + self.away_goals

    @property
    def result(self) -> str:
        if self.home_goals > self.away_goals:
            return "1"
        if self.home_goals < self.away_goals:
            return "2"
        return "X"

    def over(self, threshold: float) -> int:
        return 1 if self.total_goals > threshold else 0

    @property
    def btts(self) -> int:
        return 1 if self.home_goals > 0 and self.away_goals > 0 else 0


# (matches, goals_for, goals_against) for a home or away split, taken pre-match.
Split = Tuple[int, int, int]


@dataclass
class MatchContext:
    """Everything a model needs to predict one match, all pre-match (no leakage)."""
    scored: ScoredMatch          # overall snapshots + actual result
    lg_home_avg: float           # league avg goals a HOME side scores, so far
    lg_away_avg: float           # league avg goals an AWAY side scores, so far
    home_home: Split             # home team's record when playing at home
    away_away: Split             # away team's record when playing away


def _replay(fixtures: List[Dict], min_matches: int) -> Iterator[MatchContext]:
    """
    Core chronological replay. Yields a MatchContext per finished match where
    both teams already have >= min_matches played. Accumulators and league
    state are updated only AFTER each yield.
    """
    accumulators: Dict[int, TeamAccumulator] = {}
    league = LeagueState()

    def acc(team_id: int, name: str) -> TeamAccumulator:
        a = accumulators.get(team_id)
        if a is None:
            a = accumulators[team_id] = TeamAccumulator(team_id=team_id, name=name)
        elif not a.name:
            a.name = name
        return a

    ordered = sorted(fixtures, key=lambda r: (r["date"], r["fixture_id"]))
    for rec in ordered:
        if rec.get("status") != "FT":
            continue
        hg, ag = rec.get("home_goals"), rec.get("away_goals")
        if hg is None or ag is None:
            continue

        home = acc(rec["home_id"], rec["home_name"])
        away = acc(rec["away_id"], rec["away_name"])

        if home.matches_played >= min_matches and away.matches_played >= min_matches:
            scored = ScoredMatch(
                date=rec["date"],
                home_name=home.name,
                away_name=away.name,
                home_stats=home.to_team_stats(),
                away_stats=away.to_team_stats(),
                home_goals=hg,
                away_goals=ag,
            )
            yield MatchContext(
                scored=scored,
                lg_home_avg=league.home_avg(),
                lg_away_avg=league.away_avg(),
                home_home=(home.home_matches, home.home_goals_for, home.home_goals_against),
                away_away=(away.away_matches, away.away_goals_for, away.away_goals_against),
            )

        # Only now does the actual result enter the accumulators + league state.
        home.update(hg, ag, is_home=True)
        away.update(ag, hg, is_home=False)
        league.update(hg, ag)


def iter_match_contexts(fixtures: List[Dict], min_matches: int = 4) -> Iterator[MatchContext]:
    """Replay a season, yielding a rich MatchContext per scored match."""
    yield from _replay(fixtures, min_matches)


def iter_scored_matches(fixtures: List[Dict], min_matches: int = 4) -> Iterator[ScoredMatch]:
    """Replay a season, yielding just the ScoredMatch (overall stats + result)."""
    for ctx in _replay(fixtures, min_matches):
        yield ctx.scored


# ── baseline prediction layer (the CURRENT model, via the analyzers) ──────────

_goals = GoalsAnalyzer()
_result = ResultAnalyzer()


def predict_match(match: ScoredMatch) -> Dict[str, float]:
    """
    Baseline model probabilities (fractions in [0, 1]) using the live app's
    analyzer maths. This is the model we already backtested.
    """
    goals_probs = _goals.match_goals_probabilities(match.home_stats, match.away_stats)
    btts_yes = _goals.btts_yes_probability(match.home_stats, match.away_stats)
    result_probs = _result.result_probabilities(match.home_stats, match.away_stats)
    return {
        "over_1_5": goals_probs["over_1_5"],
        "over_2_5": goals_probs["over_2_5"],
        "over_3_5": goals_probs["over_3_5"],
        "btts_yes": btts_yes,
        "result_1": result_probs["1"],
        "result_X": result_probs["X"],
        "result_2": result_probs["2"],
    }
