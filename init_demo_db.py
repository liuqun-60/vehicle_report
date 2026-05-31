#!/usr/bin/env python3
"""
SQLite 数据库初始化脚本
用于本地预置演示数据库，或 Streamlit Cloud 首次部署前生成 .db 文件。

用法:
    python init_demo_db.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from db_config import connection_pool, init_database_schema, DB_PATH, clear_vehicle_data, seed_demo_data


def create_default_admin():
    with connection_pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", ('admin',))
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO users (username, password, full_name, is_admin) VALUES (?, ?, ?, ?)",
                ('admin', 'admin123', '系统管理员', 1),
            )
            conn.commit()
            print("[OK] 已创建默认管理员: admin / admin123")


def init_vehicle_stats():
    with connection_pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, model, chassis_number FROM vehicles")
        vehicles = cursor.fetchall()
        for vehicle_id, model, chassis_number in vehicles:
            cursor.execute('''
                SELECT COUNT(*) FROM test_results
                WHERE vehicle_id = ? AND value IS NOT NULL AND value != '' AND TRIM(value) != ''
            ''', (vehicle_id,))
            valid_count = cursor.fetchone()[0]
            total_items = 261
            cursor.execute('SELECT COUNT(*) FROM test_items')
            row = cursor.fetchone()
            if row and row[0]:
                total_items = row[0]
            completion_rate = round(valid_count / total_items * 100, 2) if total_items else 0
            cursor.execute('''
                INSERT INTO vehicle_stats (vehicle_id, model, chassis_number, valid_count, total_items, completion_rate)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(vehicle_id) DO UPDATE SET
                    model = excluded.model,
                    chassis_number = excluded.chassis_number,
                    valid_count = excluded.valid_count,
                    completion_rate = excluded.completion_rate
            ''', (vehicle_id, model, chassis_number, valid_count, total_items, completion_rate))
        conn.commit()
    print(f"✅ 已更新 {len(vehicles)} 辆车的统计数据")


def main():
    print("=" * 50)
    print("X 试验报告系统 - SQLite 演示数据库初始化")
    print("=" * 50)

    connection_pool.initialize()
    init_database_schema()
    with connection_pool.get_connection() as conn:
        clear_vehicle_data(conn)
        seed_demo_data(conn, force=True)
    init_vehicle_stats()
    create_default_admin()

    if DB_PATH.exists():
        size_kb = DB_PATH.stat().st_size / 1024
        print(f"\n✅ 数据库已创建: {DB_PATH}")
        print(f"   文件大小: {size_kb:.1f} KB")
        print("\n默认账号:")
        print("   管理员: admin / admin123")
        print("   工程师: engineer / demo123")
    else:
        print("\n❌ 数据库文件未生成，请检查错误日志")
        sys.exit(1)


if __name__ == "__main__":
    main()
