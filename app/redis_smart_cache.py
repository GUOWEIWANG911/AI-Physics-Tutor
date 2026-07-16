import os
import json
import redis
import hashlib

# 基于 Redis 的智能缓存管理器
class SmartCache:
    """多级缓存：本地 LRU + Redis 分布式缓存"""
    def __init__(self, redis_host='localhost', redis_port=6379, local_max_size=1000):
        redis_host = os.getenv("REDIS_HOST", redis_host)
        redis_port = int(os.getenv("REDIS_PORT", redis_port))
        
        self.redis_client = redis.Redis(
            host=redis_host, 
            port=redis_port, 
            db=0, 
            protocol=2,
            socket_connect_timeout=10,  # 建立连接的超时时间（秒）
            socket_timeout=60,          # 读写数据的超时时间（秒），防止 Rerank 耗时过长导致卡死
            retry_on_timeout=True       # 遇到超时自动重试一次
        )
        self.local_cache = {} # 本地内存缓存
        self.local_max_size = local_max_size

    def _generate_key(self, query: str) -> str:
        """将问题转化为唯一的哈希键，防止特殊字符导致 Redis 报错"""
        content = f"tutor_agent:{query}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(self, query: str):
        """获取缓存：先查本地，再查 Redis"""
        # 1. 查本地缓存
        if query in self.local_cache:
            print("[Cache] 本地缓存命中！")
            return self.local_cache[query]

        # 2. 查 Redis 缓存
        key = self._generate_key(query)
        cache_value = self.redis_client.get(key)
        if cache_value:
            print("[Cache] Redis 缓存命中！")
            response = json.loads(cache_value.decode('utf-8'))
            # 顺便放入本地缓存
            self.local_cache[query] = response
            return response
        
        return None
    
    def set(self, query: str, response: str, ttl=3600):
        """设置缓存：同时写入本地和 Redis（默认缓存 1 小时）"""
        # 1. 写入本地缓存(简单的 LRU 淘汰机制)
        if len(self.local_cache) >= self.local_max_size:
            self.local_cache.pop(next(iter(self.local_cache)))
        self.local_cache[query] = response

        # 2. 写入 Redis
        key = self._generate_key(query)
        self.redis_client.setex(key, ttl, json.dumps(response))