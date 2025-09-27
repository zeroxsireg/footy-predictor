"""Main CLI application using Typer."""

import typer
import asyncio
from typing import Optional

from core.analyzer import MatchAnalyzer
from core.config import get_settings
from cli.display import MatchDisplayer
from adapters.football_api import FootballAPIError


app = typer.Typer(
    name="footy-predictor",
    help="⚽ Football Match Analysis CLI - Analyze upcoming matches with team statistics"
)

displayer = MatchDisplayer()


@app.command()
def matchday(
    league: Optional[str] = typer.Option(None, "--league", "-l", help="League name (e.g., 'Serie A')"),
    country: Optional[str] = typer.Option(None, "--country", "-c", help="Country name (e.g., 'Italy')"),
    season: Optional[int] = typer.Option(None, "--season", "-s", help="Season year (e.g., 2024)")
):
    """
    📅 Analyze matches for the next matchday.
    
    Shows team statistics comparison and expected combined stats for all upcoming matches
    in the configured league (default: Serie A 2024).
    """
    asyncio.run(_analyze_matchday(league, country, season))


async def _analyze_matchday(league: Optional[str], country: Optional[str], season: Optional[int]):
    """Async function to analyze matchday."""
    try:
        settings = get_settings()
        analyzer = MatchAnalyzer()
        
        # Display loading message
        league_name = league or settings.default_league
        country_name = country or settings.default_country
        season_year = season or settings.default_season
        
        displayer.display_loading(f"Fetching data for {league_name} ({country_name}) - Season {season_year}")
        
        # Get league ID if custom league/country specified
        league_id = None
        if league or country:
            league_id = await analyzer.api_client.get_league_id(country_name, league_name, season_year)
        
        # Analyze next matchday
        predictions = await analyzer.analyze_next_matchday(league_id, season_year)
        
        # Display results
        displayer.display_matchday(predictions)
        
    except FootballAPIError as e:
        displayer.display_error(f"API Error: {e}")
    except Exception as e:
        displayer.display_error(f"Unexpected error: {e}")


@app.command()
def config():
    """
    ⚙️ Show current configuration.
    """
    try:
        settings = get_settings()
        
        from rich.table import Table
        from rich.console import Console
        
        console = Console()
        table = Table(title="🔧 Current Configuration", show_header=True, header_style="bold blue")
        
        table.add_column("Setting", style="cyan", width=20)
        table.add_column("Value", style="green")
        
        table.add_row("API Base URL", settings.api_football_base)
        table.add_row("API Key", f"{'*' * (len(settings.api_football_key) - 4)}{settings.api_football_key[-4:]}")
        table.add_row("Default Country", settings.default_country)
        table.add_row("Default League", settings.default_league)
        table.add_row("Default Season", str(settings.default_season))
        
        console.print(table)
        
    except Exception as e:
        displayer.display_error(f"Configuration error: {e}")


if __name__ == "__main__":
    app()
