#!/usr/bin/env python3
"""Redis 通知限流监控脚本"""
import redis
import time
from datetime import datetime

# 连接 Redis（根据你的 docker-compose.yml 调整 host）
r = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

def monitor():
    print("=" * 70)
    print(f"  通知限流监控 | 扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 扫描所有 notify_limit:* 键
    keys = r.keys("notify_limit:*")

    if not keys:
        print("  📭 当前无活跃限流记录")
        return

    print(f"  📊 活跃限流键数量: {len(keys)}\n")
    print(f"  {'IP地址':<20} {'剩余秒数':<10} {'状态'}")
    print("  " + "-" * 45)

    for key in sorted(keys):
        ip = key.replace("notify_limit:", "")
        ttl = r.ttl(key)  # 返回剩余秒数，-1=永不过期，-2=不存在

        if ttl == -2:
            status = "❌ 已过期（待清理）"
        elif ttl == -1:
            status = "⚠️  永不过期（异常）"
        else:
            status = "✅ 正常"

        print(f"  {ip:<20} {ttl:<10} {status}")

    print("\n" + "=" * 70)
    print("  💡 提示: 按 Ctrl+C 退出 | 每 5 秒自动刷新")
    print("=" * 70)

if __name__ == "__main__":
    try:
        while True:
            monitor()
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n👋 监控已停止")