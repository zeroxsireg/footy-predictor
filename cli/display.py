"""Display utilities for the CLI using Rich."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from typing import List
from datetime import datetime

from core.models import MatchPrediction, TeamStats


console = Console()


class MatchDisplayer:
    """Handles display of match data and predictions."""
    
    def display_matchday(self, predictions: List[MatchPrediction]) -> None:
        """Display all matches for a matchday."""
        if not predictions:
            console.print("[yellow]No matches found for the next matchday.[/yellow]")
            return
        
        # Display header
        title = Text("⚽ NEXT MATCHDAY ANALYSIS", style="bold blue")
        console.print(Panel(title, expand=False))
        console.print()
        
        for i, prediction in enumerate(predictions, 1):
            self._display_single_match(prediction, i)
            if i < len(predictions):
                console.print()
    
    def _display_single_match(self, prediction: MatchPrediction, match_number: int) -> None:
        """Display analysis for a single match."""
        fixture = prediction.fixture
        
        # Match header
        match_title = f"Match {match_number}: {fixture.home_team.name} vs {fixture.away_team.name}"
        match_date = fixture.date.strftime("%d/%m/%Y %H:%M")
        
        header_text = Text(match_title, style="bold green")
        subtitle_text = Text(f"📅 {match_date}", style="dim")
        if fixture.venue:
            subtitle_text.append(f" | 🏟️ {fixture.venue}", style="dim")
        
        console.print(Panel(header_text, subtitle=subtitle_text, expand=False))
        
        # Team Stats Comparison
        self._display_team_stats_comparison(prediction.home_stats, prediction.away_stats)
        console.print()
        
        # Expected Combined Stats
        self._display_expected_stats(prediction)
    
    def _display_team_stats_comparison(self, home_stats: TeamStats, away_stats: TeamStats) -> None:
        """Display team statistics comparison."""
        table = Table(title="📊 Team Stats Comparison", show_header=True, header_style="bold magenta")
        
        table.add_column("Statistic", style="cyan", width=20)
        table.add_column(f"🏠 {home_stats.team.name}", justify="center", style="green")
        table.add_column(f"✈️ {away_stats.team.name}", justify="center", style="red")
        
        # Add rows with statistics
        table.add_row(
            "Matches Played",
            str(home_stats.matches_played),
            str(away_stats.matches_played)
        )
        
        table.add_row(
            "Goals For/Against",
            f"{home_stats.goals_for}/{home_stats.goals_against}",
            f"{away_stats.goals_for}/{away_stats.goals_against}"
        )
        
        table.add_row(
            "Goals per Game",
            f"{home_stats.goals_per_game:.2f}",
            f"{away_stats.goals_per_game:.2f}"
        )
        
        table.add_row(
            "Goals Conceded/Game",
            f"{home_stats.goals_conceded_per_game:.2f}",
            f"{away_stats.goals_conceded_per_game:.2f}"
        )
        
        table.add_row(
            "Total Shots",
            str(home_stats.shots_total),
            str(away_stats.shots_total)
        )
        
        table.add_row(
            "Shots per Game",
            f"{home_stats.shots_per_game:.2f}",
            f"{away_stats.shots_per_game:.2f}"
        )
        
        table.add_row(
            "Shots on Target",
            str(home_stats.shots_on_target),
            str(away_stats.shots_on_target)
        )
        
        table.add_row(
            "Shots on Target/Game",
            f"{home_stats.shots_on_target_per_game:.2f}",
            f"{away_stats.shots_on_target_per_game:.2f}"
        )
        
        table.add_row(
            "Total Corners",
            str(home_stats.corners),
            str(away_stats.corners)
        )
        
        table.add_row(
            "Corners per Game",
            f"{home_stats.corners_per_game:.2f}",
            f"{away_stats.corners_per_game:.2f}"
        )
        
        table.add_row(
            "Yellow Cards",
            str(home_stats.yellow_cards),
            str(away_stats.yellow_cards)
        )
        
        table.add_row(
            "Yellow Cards/Game",
            f"{home_stats.yellow_cards_per_game:.2f}",
            f"{away_stats.yellow_cards_per_game:.2f}"
        )
        
        table.add_row(
            "Red Cards",
            str(home_stats.red_cards),
            str(away_stats.red_cards)
        )
        
        # Win/Draw/Loss record
        home_record = f"{home_stats.wins}W-{home_stats.draws}D-{home_stats.losses}L"
        away_record = f"{away_stats.wins}W-{away_stats.draws}D-{away_stats.losses}L"
        
        table.add_row(
            "W-D-L Record",
            home_record,
            away_record
        )
        
        console.print(table)
    
    def _display_expected_stats(self, prediction: MatchPrediction) -> None:
        """Display expected combined statistics."""
        table = Table(title="🔮 Expected Combined Stats", show_header=True, header_style="bold yellow")
        
        table.add_column("Metric", style="cyan", width=25)
        table.add_column("Expected Value", justify="center", style="yellow")
        
        table.add_row("Total Goals", f"{prediction.expected_total_goals}")
        table.add_row("Total Corners", f"{prediction.expected_total_corners}")
        table.add_row("Total Yellow Cards", f"{prediction.expected_total_yellow_cards}")
        
        console.print(table)
    
    def display_error(self, message: str) -> None:
        """Display an error message."""
        console.print(f"[red]❌ Error: {message}[/red]")
    
    def display_loading(self, message: str) -> None:
        """Display a loading message."""
        console.print(f"[blue]⏳ {message}...[/blue]")
