#!/usr/bin/env python3
"""
Simplified performance utilities for trading bot
"""

import time
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class LatencyMetric:
    """Simple latency tracking"""
    operation: str
    duration_ms: float
    timestamp: float

class SimpleProfiler:
    """Basic profiler for tracking operation performance"""
    
    def __init__(self, max_samples: int = 1000):
        self.metrics: Dict[str, List[LatencyMetric]] = {}
        self.max_samples = max_samples
        
    def start_operation(self, operation: str) -> float:
        """Start timing an operation"""
        return time.perf_counter()
    
    def end_operation(self, operation: str, start_time: float):
        """End timing an operation"""
        end_time = time.perf_counter()
        duration_ms = (end_time - start_time) * 1000
        
        metric = LatencyMetric(
            operation=operation,
            duration_ms=duration_ms,
            timestamp=time.time()
        )
        
        if operation not in self.metrics:
            self.metrics[operation] = []
        
        self.metrics[operation].append(metric)
        
        # Keep only recent samples
        if len(self.metrics[operation]) > self.max_samples:
            self.metrics[operation].pop(0)
    
    def get_stats(self, operation: str) -> Dict:
        """Get statistics for an operation"""
        if operation not in self.metrics or not self.metrics[operation]:
            return {}
        
        durations = [m.duration_ms for m in self.metrics[operation]]
        
        return {
            'count': len(durations),
            'avg_ms': sum(durations) / len(durations),
            'min_ms': min(durations),
            'max_ms': max(durations),
            'total_samples': len(durations)
        }
    
    def get_all_stats(self) -> Dict:
        """Get statistics for all operations"""
        return {op: self.get_stats(op) for op in self.metrics.keys()}

class SimpleCache:
    """Basic TTL cache for performance"""
    
    def __init__(self, default_ttl: float = 300.0):
        self.cache: Dict[str, Dict] = {}
        self.default_ttl = default_ttl
    
    def get(self, key: str) -> Optional[any]:
        """Get cached value if not expired"""
        if key not in self.cache:
            return None
        
        entry = self.cache[key]
        if time.time() - entry['timestamp'] > entry['ttl']:
            del self.cache[key]
            return None
        
        return entry['value']
    
    def set(self, key: str, value: any, ttl: Optional[float] = None):
        """Set cached value with TTL"""
        self.cache[key] = {
            'value': value,
            'timestamp': time.time(),
            'ttl': ttl or self.default_ttl
        }
    
    def clear_expired(self):
        """Clear expired cache entries"""
        current_time = time.time()
        expired_keys = []
        
        for key, entry in self.cache.items():
            if current_time - entry['timestamp'] > entry['ttl']:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]

# Create global instances for easy access
profiler = SimpleProfiler()
cache = SimpleCache()

def profile_async(operation_name: str):
    """Decorator for profiling async functions"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = profiler.start_operation(operation_name)
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                profiler.end_operation(operation_name, start_time)
        return wrapper
    return decorator

def profile_sync(operation_name: str):
    """Decorator for profiling sync functions"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = profiler.start_operation(operation_name)
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                profiler.end_operation(operation_name, start_time)
        return wrapper
    return decorator
