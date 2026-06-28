# ============================================================
# Ombre Brain 一键备份脚本
# 从服务器拉取所有记忆桶，保存到本地
#
# 用法：python backup.py
# 需要先设置下面的 SERVER_URL 和 PASSWORD
# ============================================================

import os
import json
import time
import httpx

# --- 配置 ---
SERVER_URL = "https://ye-ombre-brain.zeabur.app"
PASSWORD = ""  # 填你的 Dashboard 密码
BACKUP_DIR = "./ombre-backup"  # 备份保存到这个目录


def login(client: httpx.Client) -> str:
    """Login and get session cookie."""
    resp = client.post(
        f"{SERVER_URL}/auth/login",
        json={"password": PASSWORD},
    )
    if resp.status_code != 200:
        raise Exception(f"登录失败: {resp.text}")
    return resp


def backup_all():
    """Pull all buckets and save locally."""
    os.makedirs(BACKUP_DIR, exist_ok=True)

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        # Login
        login(client)
        print("✅ 登录成功")

        # Get all buckets
        resp = client.get(f"{SERVER_URL}/api/buckets")
        if resp.status_code != 200:
            raise Exception(f"获取桶列表失败: {resp.text}")

        buckets = resp.json().get("buckets", [])
        print(f"📦 共 {len(buckets)} 个记忆桶")

        # Save each bucket as .md file
        saved = 0
        for b in buckets:
            meta = b.get("metadata", {})
            bucket_type = meta.get("type", "dynamic")
            domain = meta.get("domain", ["未分类"])[0] if meta.get("domain") else "未分类"
            name = meta.get("name", b.get("id", "unknown"))
            bucket_id = b.get("id", "unknown")

            # Create directory structure
            type_dir = os.path.join(BACKUP_DIR, bucket_type, domain)
            os.makedirs(type_dir, exist_ok=True)

            # Save as .md file with frontmatter
            filepath = os.path.join(type_dir, f"{name}_{bucket_id}.md")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(b.get("content", ""))

            saved += 1

        # Also backup evolution artifacts
        try:
            resp = client.get(f"{SERVER_URL}/api/evolution/stats")
            if resp.status_code == 200:
                stats = resp.json()
                stats_path = os.path.join(BACKUP_DIR, "evolution_stats.json")
                with open(stats_path, "w", encoding="utf-8") as f:
                    json.dump(stats, f, indent=2, ensure_ascii=False)
                print(f"🧠 进化系统统计已保存")
        except Exception:
            pass

        # Save summary
        summary = {
            "backup_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "server": SERVER_URL,
            "total_buckets": len(buckets),
            "saved": saved,
        }
        summary_path = os.path.join(BACKUP_DIR, "backup_info.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        print(f"\n✅ 备份完成！{saved} 个桶已保存到 {BACKUP_DIR}/")
        print(f"📄 备份信息: {summary_path}")


if __name__ == "__main__":
    if not PASSWORD:
        print("⚠️  请先在脚本里填入 Dashboard 密码（PASSWORD 变量）")
        print(f"   打开 {SERVER_URL}/dashboard 登录时用的那个密码")
        exit(1)
    backup_all()
