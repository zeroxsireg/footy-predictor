#!/usr/bin/env python3
"""Team ID Manager - Automatically fetches and manages correct team IDs for leagues."""

import asyncio
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime

class TeamIDManager:
    """Manages team IDs for different leagues and seasons."""
    
    def __init__(self, api_client):
        self.api_client = api_client
        self._cache = {}  # Cache for team IDs
    
    async def get_league_teams(self, league_id: int, season: int) -> Dict[int, str]:
        """Get all teams for a specific league and season."""
        cache_key = f"{league_id}_{season}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            params = {
                'league': league_id,
                'season': season
            }
            
            data = await self.api_client._make_request('/teams', params)
            
            if data.get('response'):
                teams = {}
                for team_data in data['response']:
                    team_info = team_data.get('team', {})
                    team_id = team_info.get('id')
                    team_name = team_info.get('name')
                    
                    if team_id and team_name:
                        teams[team_id] = team_name
                
                # Cache the results
                self._cache[cache_key] = teams
                return teams
            
            return {}
            
        except Exception as e:
            print(f"❌ Error fetching teams for league {league_id}: {e}")
            return {}
    
    async def get_serie_a_teams(self, season: int = 2025) -> Dict[int, str]:
        """Get Serie A teams for specified season."""
        return await self.get_league_teams(135, season)
    
    async def get_premier_league_teams(self, season: int = 2025) -> Dict[int, str]:
        """Get Premier League teams for specified season."""
        return await self.get_league_teams(39, season)
    
    async def get_la_liga_teams(self, season: int = 2025) -> Dict[int, str]:
        """Get La Liga teams for specified season."""
        return await self.get_league_teams(140, season)
    
    async def get_bundesliga_teams(self, season: int = 2025) -> Dict[int, str]:
        """Get Bundesliga teams for specified season."""
        return await self.get_league_teams(78, season)
    
    async def get_ligue1_teams(self, season: int = 2025) -> Dict[int, str]:
        """Get Ligue 1 teams for specified season."""
        return await self.get_league_teams(61, season)
    
    async def find_team_by_name(self, team_name: str, league_id: int, season: int) -> Optional[int]:
        """Find team ID by name in a specific league."""
        teams = await self.get_league_teams(league_id, season)
        
        # Exact match first
        for team_id, name in teams.items():
            if name.lower() == team_name.lower():
                return team_id
        
        # Partial match
        for team_id, name in teams.items():
            if team_name.lower() in name.lower() or name.lower() in team_name.lower():
                return team_id
        
        return None
    
    def get_league_info(self) -> Dict[str, Dict]:
        """Get information about supported leagues."""
        return {
            "Serie A": {
                "league_id": 135,
                "country": "Italy",
                "method": "get_serie_a_teams"
            },
            "Premier League": {
                "league_id": 39,
                "country": "England", 
                "method": "get_premier_league_teams"
            },
            "La Liga": {
                "league_id": 140,
                "country": "Spain",
                "method": "get_la_liga_teams"
            },
            "Bundesliga": {
                "league_id": 78,
                "country": "Germany",
                "method": "get_bundesliga_teams"
            },
            "Ligue 1": {
                "league_id": 61,
                "country": "France",
                "method": "get_ligue1_teams"
            }
        }
    
    async def validate_and_fix_team_ids(self, current_ids: Dict[int, str], league_id: int, season: int) -> Tuple[Dict[int, str], List[str]]:
        """Validate current team IDs against API and return corrections."""
        correct_teams = await self.get_league_teams(league_id, season)
        corrections = []
        fixed_ids = {}
        
        print(f"🔍 Validating {len(current_ids)} team IDs against API...")
        
        for current_id, expected_name in current_ids.items():
            if current_id in correct_teams:
                api_name = correct_teams[current_id]
                if expected_name.lower() == api_name.lower():
                    fixed_ids[current_id] = api_name
                    print(f"   ✅ {current_id:3d}: {expected_name} = {api_name}")
                else:
                    corrections.append(f"ID {current_id}: Expected '{expected_name}' but API says '{api_name}'")
                    print(f"   ❌ {current_id:3d}: {expected_name} ≠ {api_name}")
                    
                    # Try to find correct ID for expected name
                    correct_id = await self.find_team_by_name(expected_name, league_id, season)
                    if correct_id:
                        fixed_ids[correct_id] = expected_name
                        corrections.append(f"   → Correct ID for '{expected_name}' is {correct_id}")
                        print(f"   🔧 Correct ID for '{expected_name}' is {correct_id}")
                    else:
                        corrections.append(f"   → '{expected_name}' not found in {season} season")
                        print(f"   ❓ '{expected_name}' not found in {season} season")
            else:
                corrections.append(f"ID {current_id} ('{expected_name}') not in league {league_id} season {season}")
                print(f"   ❓ {current_id:3d}: {expected_name} (NOT IN LEAGUE)")
                
                # Try to find correct ID
                correct_id = await self.find_team_by_name(expected_name, league_id, season)
                if correct_id:
                    fixed_ids[correct_id] = expected_name
                    corrections.append(f"   → Found '{expected_name}' with correct ID {correct_id}")
                    print(f"   🔧 Found '{expected_name}' with correct ID {correct_id}")
        
        return fixed_ids, corrections
    
    async def export_correct_ids(self, league_id: int, season: int, filename: str = None):
        """Export correct team IDs to a file."""
        teams = await self.get_league_teams(league_id, season)
        
        if not filename:
            league_name = {135: "serie_a", 39: "premier_league", 140: "la_liga", 78: "bundesliga", 61: "ligue1"}.get(league_id, f"league_{league_id}")
            filename = f"correct_team_ids_{league_name}_{season}.json"
        
        export_data = {
            "league_id": league_id,
            "season": season,
            "updated": datetime.now().isoformat(),
            "teams": teams
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Exported {len(teams)} team IDs to {filename}")
        return filename
