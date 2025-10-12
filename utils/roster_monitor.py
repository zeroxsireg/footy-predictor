#!/usr/bin/env python3
"""Roster Monitor - Automatically updates rosters when players become active/inactive."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Set, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class RosterMonitor:
    """Monitors and automatically updates team rosters when player activity changes."""
    
    def __init__(self, api_client, redis_cache):
        self.api_client = api_client
        self.redis_cache = redis_cache
        self.last_check = {}  # Track last check time per team
    
    async def check_roster_updates_needed(self, team_id: int, season: int) -> Tuple[bool, Dict]:
        """Check if a team's roster needs updating due to player activity changes."""
        try:
            # Get current cached roster
            cached_roster = self.redis_cache.get_team_roster(team_id, season)
            if not cached_roster:
                return True, {"reason": "no_cached_roster"}
            
            # Get fresh data from API (current squad)
            current_squad = await self.api_client._get_current_squad(team_id)
            if not current_squad:
                return False, {"reason": "api_unavailable"}
            
            # Check for new active players (players not in cache but with game time)
            cached_player_ids = {p.get('id') for p in cached_roster if p.get('id')}
            new_active_players = []
            
            for player in current_squad:
                player_id = player.get('id')
                if player_id and player_id not in cached_player_ids:
                    # Check if this new player has game time
                    player_stats = await self.api_client._get_player_season_stats(player_id, team_id, season)
                    appearances = player_stats.get('appearances', 0) or 0
                    minutes = player_stats.get('minutes', 0) or 0
                    
                    if appearances > 0 or minutes > 0:
                        new_active_players.append({
                            'id': player_id,
                            'name': player.get('name'),
                            'appearances': appearances,
                            'minutes': minutes
                        })
            
            # Check for previously inactive players who became active
            reactivated_players = []
            for cached_player in cached_roster:
                player_id = cached_player.get('id')
                if player_id:
                    # Get fresh stats for this player
                    fresh_stats = await self.api_client._get_player_season_stats(player_id, team_id, season)
                    fresh_apps = fresh_stats.get('appearances', 0) or 0
                    fresh_mins = fresh_stats.get('minutes', 0) or 0
                    
                    cached_apps = cached_player.get('appearances', 0) or 0
                    cached_mins = cached_player.get('minutes', 0) or 0
                    
                    # Check if player became more active
                    if (fresh_apps > cached_apps) or (fresh_mins > cached_mins):
                        reactivated_players.append({
                            'id': player_id,
                            'name': cached_player.get('name'),
                            'old_apps': cached_apps,
                            'new_apps': fresh_apps,
                            'old_mins': cached_mins,
                            'new_mins': fresh_mins
                        })
            
            # Determine if update is needed
            needs_update = len(new_active_players) > 0 or len(reactivated_players) > 0
            
            update_info = {
                "new_active_players": new_active_players,
                "reactivated_players": reactivated_players,
                "cached_roster_size": len(cached_roster),
                "current_squad_size": len(current_squad)
            }
            
            return needs_update, update_info
            
        except Exception as e:
            logger.error(f"Error checking roster updates for team {team_id}: {e}")
            return False, {"reason": "error", "error": str(e)}
    
    async def update_roster_if_needed(self, team_id: int, season: int, force: bool = False) -> Dict:
        """Update roster if changes are detected or if forced."""
        try:
            if not force:
                needs_update, update_info = await self.check_roster_updates_needed(team_id, season)
                if not needs_update:
                    return {
                        "updated": False,
                        "reason": "no_changes_needed",
                        "info": update_info
                    }
            else:
                update_info = {"reason": "forced_update"}
            
            # Clear cache and fetch fresh roster
            self.redis_cache.clear_team_cache(team_id, season)
            
            # Fetch fresh roster with current filtering logic
            fresh_roster = await self.api_client.get_team_squad(team_id, season)
            
            if fresh_roster:
                now = datetime.now()
                self.last_check[team_id] = now
                
                # Mark data as updated (usando timestamp)
                # Il nuovo sistema usa DataService per il tracking
                
                return {
                    "updated": True,
                    "roster_size": len(fresh_roster),
                    "info": update_info,
                    "timestamp": now.isoformat()
                }
            else:
                return {
                    "updated": False,
                    "reason": "failed_to_fetch",
                    "info": update_info
                }
                
        except Exception as e:
            logger.error(f"Error updating roster for team {team_id}: {e}")
            return {
                "updated": False,
                "reason": "error",
                "error": str(e)
            }
    
    async def monitor_league_rosters(self, league_teams: Dict[int, str], season: int, check_interval_hours: int = 24) -> Dict:
        """Monitor all teams in a league for roster changes."""
        results = {}
        
        print(f"🔍 Monitoring {len(league_teams)} teams for roster changes...")
        
        for team_id, team_name in league_teams.items():
            try:
                # Check if we need to update this team
                last_check = self.last_check.get(team_id)
                
                # Skip if checked recently (unless forced)
                if last_check and (datetime.now() - last_check).total_seconds() < check_interval_hours * 3600:
                    results[team_id] = {
                        "team_name": team_name,
                        "checked": False,
                        "reason": "recently_checked",
                        "last_check": last_check.isoformat()
                    }
                    continue
                
                print(f"🔄 Checking {team_name}...")
                
                # Check and update if needed
                update_result = await self.update_roster_if_needed(team_id, season)
                update_result["team_name"] = team_name
                update_result["checked"] = True
                
                results[team_id] = update_result
                
                if update_result.get("updated"):
                    info = update_result.get("info", {})
                    new_players = len(info.get("new_active_players", []))
                    reactivated = len(info.get("reactivated_players", []))
                    
                    print(f"   ✅ Updated: {update_result.get('roster_size')} players")
                    if new_players > 0:
                        print(f"      🆕 {new_players} new active players")
                    if reactivated > 0:
                        print(f"      🔄 {reactivated} reactivated players")
                else:
                    print(f"   ⏭️  No update needed")
                
                # Small delay to avoid API rate limits
                await asyncio.sleep(0.5)
                
            except Exception as e:
                results[team_id] = {
                    "team_name": team_name,
                    "checked": True,
                    "updated": False,
                    "reason": "error",
                    "error": str(e)
                }
                print(f"   ❌ Error checking {team_name}: {e}")
        
        return results
    
    def get_monitoring_summary(self, results: Dict) -> Dict:
        """Generate a summary of monitoring results."""
        total_teams = len(results)
        checked_teams = len([r for r in results.values() if r.get("checked", False)])
        updated_teams = len([r for r in results.values() if r.get("updated", False)])
        error_teams = len([r for r in results.values() if r.get("reason") == "error"])
        
        return {
            "total_teams": total_teams,
            "checked_teams": checked_teams,
            "updated_teams": updated_teams,
            "error_teams": error_teams,
            "success_rate": f"{((checked_teams - error_teams) / checked_teams * 100):.1f}%" if checked_teams > 0 else "0%",
            "update_rate": f"{(updated_teams / checked_teams * 100):.1f}%" if checked_teams > 0 else "0%"
        }
    
    async def smart_roster_refresh(self, team_id: int, season: int, max_age_hours: int = 24) -> bool:
        """Smart refresh: update roster only after matches have been played."""
        try:
            # Check roster age
            roster = self.redis_cache.get_team_roster(team_id, season)
            if not roster:
                # No roster cached, definitely need refresh
                await self.update_roster_if_needed(team_id, season, force=True)
                return True
            
            # Simplified logic: just check and update
            result = await self.update_roster_if_needed(team_id, season)
            
            return result.get("updated", False)
            
        except Exception as e:
            logger.error(f"Error in smart refresh for team {team_id}: {e}")
            return False
    
    async def _should_update_roster_after_matches(self, team_id: int, season: int) -> bool:
        """Check if roster should be updated based on matches played since last update."""
        try:
            from datetime import datetime, timedelta
            import pytz
            
            # Get last roster update timestamp
            cache_key = f"roster_last_update:{team_id}:{season}"
            last_update_str = await self.redis_cache.get_data(cache_key)
            
            if not last_update_str:
                # No previous update recorded, assume we need to check
                return True
            
            # Parse last update time
            try:
                last_update = datetime.fromisoformat(last_update_str)
                if last_update.tzinfo is None:
                    local_tz = pytz.timezone('Europe/Rome')
                    last_update = local_tz.localize(last_update)
            except:
                # If we can't parse, assume we need to check
                return True
            
            # Get all matches for this team (both played and upcoming)
            all_fixtures = await self.api_client.get_team_fixtures(team_id, season)
            
            if not all_fixtures:
                return False
            
            # Get current time
            local_tz = pytz.timezone('Europe/Rome')
            now = datetime.now(local_tz)
            
            # Check if any match has been played since last roster update
            for fixture in all_fixtures:
                if fixture.date and fixture.status in ['FT', 'AET', 'PEN']:  # Finished matches
                    fixture_date = fixture.date
                    if fixture_date.tzinfo is None:
                        fixture_date = local_tz.localize(fixture_date)
                    
                    # If match was played after last roster update, we should check for changes
                    if fixture_date > last_update:
                        print(f"📅 Match played on {fixture_date.strftime('%Y-%m-%d %H:%M')} after last roster update ({last_update.strftime('%Y-%m-%d %H:%M')})")
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking if roster should update after matches for team {team_id}: {e}")
            # If we can't check, assume we need to check
            return True

    async def _has_upcoming_matches(self, team_id: int, season: int, days_ahead: int = 7) -> bool:
        """Check if team has upcoming matches in the next N days."""
        try:
            from datetime import datetime, timedelta
            import pytz
            
            # Get team's upcoming fixtures
            fixtures = await self.api_client.get_team_fixtures(team_id, season, status="NS")  # Not Started
            
            if not fixtures:
                return False
            
            # Get current time in local timezone
            local_tz = pytz.timezone('Europe/Rome')
            now = datetime.now(local_tz)
            future_date = now + timedelta(days=days_ahead)
            
            for fixture in fixtures:
                if fixture.date:
                    # Ensure fixture date is timezone-aware for comparison
                    fixture_date = fixture.date
                    if fixture_date.tzinfo is None:
                        fixture_date = local_tz.localize(fixture_date)
                    
                    if now <= fixture_date <= future_date:
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking upcoming matches for team {team_id}: {e}")
            # If we can't check, assume there might be matches and allow refresh
            return True
    
