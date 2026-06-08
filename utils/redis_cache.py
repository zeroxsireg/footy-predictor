"""Redis cache manager for football data."""

import json
import redis
import gzip
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import logging

from core.config import get_settings

logger = logging.getLogger(__name__)


class RedisFootballCache:
    """Redis cache manager for football data with compression and TTL management."""
    
    # TTL Configuration (in seconds)
    TTL_CONFIG = {
        'roster': 30 * 24 * 3600,        # 30 giorni - roster cambiano raramente
        'team_stats': -1,                 # MAI SCADONO - statistiche squadre (dati storici)
        'shots_corners': -1,              # MAI SCADONO - shots/corners (dati storici)
        'historical_data': -1,            # Mai scadono - dati storici
        'finished_matches': -1,           # Mai scadono - partite finite
        'league_standings': 24 * 3600,    # 1 giorno - classifiche (cambiano)
        'live_odds': 30 * 60,             # 30 minuti - quote live
        'upcoming_fixtures': 6 * 3600,    # 6 ore - prossime partite
        'league_players_all': 24 * 3600, # 24 ore per tutti i giocatori del campionato
        'team_metadata': -1,              # Mai scadono - metadati squadre
        'data_update': -1                 # Mai scadono - timestamp aggiornamenti
    }
    
    def __init__(self):
        """Initialize Redis connection."""
        self.settings = get_settings()
        self._redis = None
        self._connect()
    
    def _connect(self):
        """Establish Redis connection with SSL support."""
        try:
            import ssl
            # Try multiple connection methods for Redis Cloud compatibility
            connection_configs = [
                # Method 1: SSL with TLS 1.2+
                {
                    'host': self.settings.redis_host,
                    'port': self.settings.redis_port,
                    'password': self.settings.redis_password,
                    'ssl': True,
                    'ssl_cert_reqs': ssl.CERT_NONE,
                    'ssl_check_hostname': False,
                    'ssl_ca_certs': None,
                    'db': self.settings.redis_db,
                    'decode_responses': True,
                    'socket_timeout': 15,
                    'socket_connect_timeout': 15,
                    'retry_on_timeout': True
                },
                # Method 2: SSL with minimal verification
                {
                    'host': self.settings.redis_host,
                    'port': self.settings.redis_port,
                    'password': self.settings.redis_password,
                    'ssl': True,
                    'ssl_cert_reqs': None,
                    'ssl_check_hostname': False,
                    'db': self.settings.redis_db,
                    'decode_responses': True,
                    'socket_timeout': 20,
                    'socket_connect_timeout': 20
                },
                # Method 3: SSL with string cert requirements
                {
                    'host': self.settings.redis_host,
                    'port': self.settings.redis_port,
                    'password': self.settings.redis_password,
                    'ssl': True,
                    'ssl_cert_reqs': 'none',
                    'db': self.settings.redis_db,
                    'decode_responses': True,
                    'socket_timeout': 25
                },
                # Method 4: Basic SSL
                {
                    'host': self.settings.redis_host,
                    'port': self.settings.redis_port,
                    'password': self.settings.redis_password,
                    'ssl': True,
                    'db': self.settings.redis_db,
                    'decode_responses': True,
                    'socket_timeout': 30
                },
                # Method 5: Try without SSL (fallback)
                {
                    'host': self.settings.redis_host,
                    'port': self.settings.redis_port,
                    'password': self.settings.redis_password,
                    'ssl': False,
                    'db': self.settings.redis_db,
                    'decode_responses': True,
                    'socket_timeout': 10
                }
            ]
            
            for i, config in enumerate(connection_configs, 1):
                try:
                    # Don't log every attempt to reduce noise
                    self._redis = redis.Redis(**config)
                    self._redis.ping()
                    logger.info(f"✅ Redis connected successfully")
                    return
                except Exception as e:
                    # Don't log individual connection failures - it's expected
                    continue
            
            # If all methods fail
            raise Exception("All Redis connection methods failed")
            
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            logger.info("📴 Running in offline mode - no caching available")
            self._redis = None
    
    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        if not self._redis:
            return False
        try:
            self._redis.ping()
            return True
        except:
            return False
    
    def _compress_data(self, data: Any) -> str:
        """Compress data using gzip for storage efficiency."""
        try:
            json_str = json.dumps(data, ensure_ascii=False)
            compressed = gzip.compress(json_str.encode('utf-8'))
            # Return base64 encoded string for Redis storage
            import base64
            return base64.b64encode(compressed).decode('ascii')
        except Exception as e:
            logger.warning(f"Compression failed, storing uncompressed: {e}")
            return json.dumps(data, ensure_ascii=False)
    
    def _decompress_data(self, compressed_data: str) -> Any:
        """Decompress data from Redis."""
        try:
            import base64
            compressed = base64.b64decode(compressed_data.encode('ascii'))
            json_str = gzip.decompress(compressed).decode('utf-8')
            return json.loads(json_str)
        except Exception:
            # Fallback to direct JSON parsing (uncompressed data)
            try:
                return json.loads(compressed_data)
            except Exception as e:
                logger.error(f"Failed to decompress data: {e}")
                return None
    
    def _set_with_ttl(self, key: str, data: Any, ttl_type: str, compress: bool = True):
        """Set data in Redis with appropriate TTL."""
        if not self.is_connected():
            logger.warning("Redis not connected, skipping cache set")
            return False
        
        try:
            # Prepare data
            if compress and isinstance(data, (dict, list)):
                value = self._compress_data(data)
                # Mark as compressed
                meta_key = f"{key}:meta"
                self._redis.hset(meta_key, mapping={
                    'compressed': 'true',
                    'timestamp': datetime.now().isoformat(),
                    'ttl_type': ttl_type
                })
                if self.TTL_CONFIG[ttl_type] > 0:
                    self._redis.expire(meta_key, self.TTL_CONFIG[ttl_type])
            else:
                value = json.dumps(data, ensure_ascii=False) if not isinstance(data, str) else data
            
            # Set main data
            self._redis.set(key, value)
            
            # Set TTL if configured
            ttl = self.TTL_CONFIG.get(ttl_type, 3600)  # Default 1 hour
            if ttl > 0:
                self._redis.expire(key, ttl)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to set cache key {key}: {e}")
            return False
    
    def _get_with_decompression(self, key: str) -> Optional[Any]:
        """Get data from Redis with automatic decompression."""
        if not self.is_connected():
            return None
        
        try:
            # Check if data exists
            value = self._redis.get(key)
            if not value:
                return None
            
            # Check if compressed
            meta_key = f"{key}:meta"
            meta = self._redis.hgetall(meta_key)
            
            if meta.get('compressed') == 'true':
                return self._decompress_data(value)
            else:
                # Try JSON parsing
                try:
                    return json.loads(value)
                except:
                    return value
                    
        except Exception as e:
            logger.error(f"Failed to get cache key {key}: {e}")
            return None
    
    # ROSTER MANAGEMENT
    def get_team_roster(self, team_id: int, season: int) -> Optional[List[Dict]]:
        """Get team roster from cache."""
        key = f"team:{team_id}:{season}:roster"
        return self._get_with_decompression(key)
    
    def set_team_roster(self, team_id: int, season: int, roster_data: List[Dict]) -> bool:
        """Cache team roster data."""
        key = f"team:{team_id}:{season}:roster"
        success = self._set_with_ttl(key, roster_data, 'roster', compress=True)
        
        if success:
            # Add to teams index
            self._redis.sadd(f"teams:cached:{season}", str(team_id))
            logger.info(f"✅ Cached roster for team {team_id} season {season}")
        
        return success
    
    # SHOTS/CORNERS MANAGEMENT
    def get_team_shots_corners(self, team_id: int, season: int) -> Optional[Dict]:
        """Get team shots/corners stats from cache."""
        key = f"team:{team_id}:{season}:shots_corners"
        return self._get_with_decompression(key)
    
    def set_team_shots_corners(self, team_id: int, season: int, stats: Dict) -> bool:
        """Cache team shots/corners stats (permanent for historical data)."""
        key = f"team:{team_id}:{season}:shots_corners"
        
        # Mark as historical data (never expires)
        stats_with_metadata = {
            **stats,
            "_metadata": {
                "cached_at": datetime.now().isoformat(),
                "data_type": "historical_shots_corners",
                "season": season,
                "team_id": team_id
            }
        }
        
        return self._set_with_ttl(key, stats_with_metadata, 'shots_corners', compress=False)
    
    # TEAM STATISTICS
    def get_team_stats(self, team_id: int, league_id: int, season: int) -> Optional[Dict]:
        """Get team statistics from cache."""
        key = f"team:{team_id}:{league_id}:{season}:stats"
        return self._get_with_decompression(key)
    
    def set_team_stats(self, team_id: int, league_id: int, season: int, stats: Dict) -> bool:
        """Cache team statistics (permanent for historical data)."""
        key = f"team:{team_id}:{league_id}:{season}:stats"
        
        # Mark as historical data (never expires)
        stats_with_metadata = {
            **stats,
            "_metadata": {
                "cached_at": datetime.now().isoformat(),
                "data_type": "historical_team_stats",
                "season": season,
                "league_id": league_id,
                "team_id": team_id
            }
        }
        
        return self._set_with_ttl(key, stats_with_metadata, 'team_stats', compress=True)
    
    # MATCH STATISTICS
    def get_match_stats(self, match_id: int) -> Optional[Dict]:
        """Get match statistics from cache."""
        key = f"match:{match_id}:stats"
        return self._get_with_decompression(key)
    
    def set_match_stats(self, match_id: int, stats: Dict) -> bool:
        """Cache match statistics (never expire for finished matches)."""
        key = f"match:{match_id}:stats"
        return self._set_with_ttl(key, stats, 'finished_matches', compress=True)
    
    # UTILITY METHODS
    def get_cached_teams(self, season: int) -> List[str]:
        """Get list of teams that have cached data for a season."""
        if not self.is_connected():
            return []
        
        try:
            return list(self._redis.smembers(f"teams:cached:{season}"))
        except:
            return []
    
    def clear_team_cache(self, team_id: int, season: int = None):
        """Clear all cache for a specific team."""
        if not self.is_connected():
            return
        
        try:
            if season:
                # Clear specific season
                patterns = [
                    f"team:{team_id}:{season}:*",
                    f"team:{team_id}:*:{season}:*"
                ]
            else:
                # Clear all seasons
                patterns = [f"team:{team_id}:*"]
            
            for pattern in patterns:
                keys = self._redis.keys(pattern)
                if keys:
                    self._redis.delete(*keys)
                    logger.info(f"🗑️ Cleared cache for team {team_id} pattern {pattern}")
                    
        except Exception as e:
            logger.error(f"Failed to clear cache for team {team_id}: {e}")
    
    def is_historical_data(self, data: Dict) -> bool:
        """Check if data is historical (never expires)."""
        if not data or not isinstance(data, dict):
            return False
        
        metadata = data.get("_metadata", {})
        data_type = metadata.get("data_type", "")
        
        # Historical data types that never expire
        historical_types = [
            "historical_team_stats",
            "historical_shots_corners", 
            "historical_match_data",
            "finished_match_stats"
        ]
        
        return data_type in historical_types
    
    def get_key_info(self, key: str) -> Dict:
        """Get TTL and metadata for a specific Redis key."""
        if not self.is_connected():
            return {}

        try:
            ttl = self._redis.ttl(key)
            data = self._get_with_decompression(key)
            metadata = data.get("_metadata", {}) if data else {}

            return {
                "key": key,
                "ttl": ttl,
                "is_permanent": ttl == -1,
                "metadata": metadata,
                "is_historical": self.is_historical_data(data) if data else False
            }
        except Exception as e:
            logger.error(f"Error getting key info for {key}: {e}")
            return {}
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """Get Redis memory usage statistics."""
        if not self.is_connected():
            return {'error': 'Not connected'}
        
        try:
            info = self._redis.info('memory')
            return {
                'used_memory_mb': round(info['used_memory'] / (1024*1024), 2),
                'used_memory_human': info['used_memory_human'],
                'max_memory_mb': 30,  # Redis Free limit
                'usage_percentage': round((info['used_memory'] / (30*1024*1024)) * 100, 1),
                'keys_count': self._redis.dbsize()
            }
        except Exception as e:
            return {'error': str(e)}
    
    def health_check(self) -> Dict[str, Any]:
        """Perform Redis health check."""
        try:
            if not self.is_connected():
                return {'status': 'disconnected', 'error': 'No connection'}
            
            # Test basic operations
            test_key = 'health_check_test'
            self._redis.set(test_key, 'test', ex=10)
            value = self._redis.get(test_key)
            self._redis.delete(test_key)
            
            if value != 'test':
                return {'status': 'error', 'error': 'Read/write test failed'}
            
            memory_info = self.get_memory_usage()
            
            return {
                'status': 'healthy',
                'memory_usage': memory_info,
                'connection': 'ok'
            }
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    async def clear_all_cache(self):
        """Clear all data from Redis cache."""
        if not self.is_connected():
            raise Exception("Redis non connesso")
        
        try:
            # Flush all databases
            self._redis.flushdb()
            logger.info("✅ Cache Redis completamente svuotata")
        except Exception as e:
            logger.error(f"❌ Errore durante lo svuotamento cache: {e}")
            raise
    
    async def get_cache_info(self) -> Dict[str, Any]:
        """Get cache information and statistics."""
        if not self.is_connected():
            return {'error': 'Redis non connesso'}
        
        try:
            info = self._redis.info()
            return {
                'total_keys': info.get('db0', {}).get('keys', 0),
                'used_memory': info.get('used_memory_human', 'N/A'),
                'uptime': f"{info.get('uptime_in_seconds', 0) // 3600}h {(info.get('uptime_in_seconds', 0) % 3600) // 60}m",
                'connected_clients': info.get('connected_clients', 0),
                'total_commands_processed': info.get('total_commands_processed', 0)
            }
        except Exception as e:
            return {'error': str(e)}
    
    async def get_sample_keys(self, limit: int = 10) -> List[str]:
        """Get a sample of keys from the cache."""
        if not self.is_connected():
            return []
        
        try:
            # Get all keys (this might be slow for large caches)
            keys = self._redis.keys('*')
            return keys[:limit] if keys else []
        except Exception as e:
            logger.error(f"❌ Errore durante il recupero delle chiavi: {e}")
            return []
    
    def delete_data(self, key: str) -> bool:
        """Delete data from Redis cache."""
        if not self.is_connected():
            return False
        
        try:
            result = self._redis.delete(key)
            logger.info(f"🗑️ Deleted key: {key}")
            return result > 0
        except Exception as e:
            logger.error(f"❌ Error deleting key {key}: {e}")
            return False
    
    async def set_data(self, key: str, data: Any, ttl_type: str) -> bool:
        """Set data in Redis cache with specified TTL type."""
        try:
            self._set_with_ttl(key, data, ttl_type)
            return True
        except Exception as e:
            logger.error(f"❌ Error setting data for key {key}: {e}")
            return False
    
    async def get_data(self, key: str, ttl_type: str = None) -> Optional[Any]:
        """Get data from Redis cache."""
        try:
            return self._get_with_decompression(key)
        except Exception as e:
            logger.error(f"❌ Error getting data for key {key}: {e}")
            return None


# Global instance
_redis_cache = None

def get_redis_cache() -> RedisFootballCache:
    """Get global Redis cache instance."""
    global _redis_cache
    if _redis_cache is None:
        _redis_cache = RedisFootballCache()
    return _redis_cache
