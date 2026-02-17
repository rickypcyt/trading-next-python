import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from dataclasses import dataclass

@dataclass
class CacheEntry:
    """Entrada de caché con timestamp y datos"""
    data: Dict
    timestamp: datetime
    ttl_seconds: int
    
    def is_expired(self) -> bool:
        """Verificar si la entrada ha expirado"""
        return datetime.now() > self.timestamp + timedelta(seconds=self.ttl_seconds)

class BinanceDataCache:
    """Sistema de caché para datos de Binance"""
    
    def __init__(self, default_ttl: int = 180):  # 3 minutos por defecto
        self.cache: Dict[str, CacheEntry] = {}
        self.default_ttl = default_ttl
        self.cache_hits = 0
        self.cache_misses = 0
    
    def get(self, symbol: str, data_type: str = 'ticker') -> Optional[Dict]:
        """Obtener datos del caché"""
        key = f"{symbol}_{data_type}"
        
        if key in self.cache:
            entry = self.cache[key]
            if not entry.is_expired():
                self.cache_hits += 1
                return entry.data
            else:
                # Eliminar entrada expirada
                del self.cache[key]
        
        self.cache_misses += 1
        return None
    
    def set(self, symbol: str, data: Dict, data_type: str = 'ticker', ttl: Optional[int] = None) -> None:
        """Guardar datos en caché"""
        key = f"{symbol}_{data_type}"
        ttl = ttl or self.default_ttl
        
        entry = CacheEntry(
            data=data,
            timestamp=datetime.now(),
            ttl_seconds=ttl
        )
        
        self.cache[key] = entry
    
    def get_klines(self, symbol: str, interval: str = '1h', limit: int = 24) -> Optional[List]:
        """Obtener velas del caché"""
        key = f"{symbol}_klines_{interval}_{limit}"
        
        if key in self.cache:
            entry = self.cache[key]
            if not entry.is_expired():
                self.cache_hits += 1
                return entry.data
            else:
                del self.cache[key]
        
        self.cache_misses += 1
        return None
    
    def set_klines(self, symbol: str, klines: List, interval: str = '1h', limit: int = 24, ttl: Optional[int] = None) -> None:
        """Guardar velas en caché"""
        key = f"{symbol}_klines_{interval}_{limit}"
        ttl = ttl or self.default_ttl
        
        entry = CacheEntry(
            data=klines,
            timestamp=datetime.now(),
            ttl_seconds=ttl
        )
        
        self.cache[key] = entry
    
    def get_technical_analysis(self, symbol: str) -> Optional[Dict]:
        """Obtener análisis técnico del caché"""
        key = f"{symbol}_technical"
        
        if key in self.cache:
            entry = self.cache[key]
            if not entry.is_expired():
                self.cache_hits += 1
                return entry.data
            else:
                del self.cache[key]
        
        self.cache_misses += 1
        return None
    
    def set_technical_analysis(self, symbol: str, analysis: Dict, ttl: Optional[int] = None) -> None:
        """Guardar análisis técnico en caché"""
        key = f"{symbol}_technical"
        ttl = ttl or 60  # 1 minuto para análisis técnico
        
        entry = CacheEntry(
            data=analysis,
            timestamp=datetime.now(),
            ttl_seconds=ttl
        )
        
        self.cache[key] = entry
    
    def clear_expired(self) -> int:
        """Limpiar entradas expiradas"""
        expired_keys = []
        
        for key, entry in self.cache.items():
            if entry.is_expired():
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]
        
        return len(expired_keys)
    
    def clear_all(self) -> None:
        """Limpiar todo el caché"""
        self.cache.clear()
    
    def get_stats(self) -> Dict:
        """Obtener estadísticas del caché"""
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hit_rate': f"{hit_rate:.2f}%",
            'total_entries': len(self.cache),
            'memory_usage': f"{len(str(self.cache)) / 1024:.2f} KB"
        }
    
    def get_cache_info(self) -> Dict:
        """Obtener información detallada del caché"""
        entries_info = []
        
        for key, entry in self.cache.items():
            age_seconds = (datetime.now() - entry.timestamp).total_seconds()
            remaining_ttl = max(0, entry.ttl_seconds - age_seconds)
            
            entries_info.append({
                'key': key,
                'age_seconds': age_seconds,
                'remaining_ttl': remaining_ttl,
                'is_expired': entry.is_expired(),
                'data_size': len(str(entry.data))
            })
        
        return {
            'entries': entries_info,
            'stats': self.get_stats()
        }

# Instancia global del caché
binance_cache = BinanceDataCache(default_ttl=180)  # 3 minutos por defecto
