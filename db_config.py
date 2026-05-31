# db_config.py - SQLite 数据库配置（Streamlit Cloud 演示版）
import os
import sqlite3
import logging
from contextlib import contextmanager
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = Path(os.getenv(
    'SQLITE_DB_PATH',
    str(Path(__file__).parent / 'data' / 'car_test_system.db')
))


def adapt_query(query):
    """将 MySQL 风格 %s 占位符转换为 SQLite ? 占位符"""
    if '%s' in query:
        return query.replace('%s', '?')
    return query


class SQLiteCursor:
    """兼容 mysql-connector 的 cursor 接口"""

    def __init__(self, cursor, dictionary=False):
        self._cursor = cursor
        self._dictionary = dictionary

    def execute(self, query, params=None):
        return self._cursor.execute(adapt_query(query), params or ())

    def executemany(self, query, params_list):
        return self._cursor.executemany(adapt_query(query), params_list)

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        if self._dictionary:
            return dict(row)
        return row

    def fetchall(self):
        rows = self._cursor.fetchall()
        if self._dictionary:
            return [dict(r) for r in rows]
        return rows

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def description(self):
        return self._cursor.description

    def close(self):
        self._cursor.close()


class SQLiteConnection:
    """兼容 mysql-connector 的 connection 接口"""

    def __init__(self, conn):
        self._conn = conn

    def cursor(self, dictionary=False):
        if dictionary:
            self._conn.row_factory = sqlite3.Row
        else:
            self._conn.row_factory = None
        return SQLiteCursor(self._conn.cursor(), dictionary=dictionary)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def execute(self, query, params=None):
        return self._conn.execute(adapt_query(query), params or ())


class SQLiteDatabase:
    """SQLite 数据库管理器（无连接池）"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def initialize(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"SQLite 数据库路径: {DB_PATH}")

    @contextmanager
    def get_connection(self):
        connection = None
        try:
            raw = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=30)
            raw.execute("PRAGMA foreign_keys = ON")
            connection = SQLiteConnection(raw)
            yield connection
        except Exception as err:
            logger.error(f"数据库连接错误: {err}")
            if connection:
                try:
                    connection.rollback()
                except Exception:
                    pass
            raise
        finally:
            if connection:
                try:
                    connection.close()
                except Exception:
                    pass

    @contextmanager
    def get_cursor(self, connection=None, dictionary=False):
        conn = connection
        own_connection = False
        try:
            if conn is None:
                own_connection = True
                with self.get_connection() as managed:
                    conn = managed
                    cursor = conn.cursor(dictionary=dictionary)
                    yield cursor
                    return
            cursor = conn.cursor(dictionary=dictionary)
            yield cursor
        finally:
            try:
                if 'cursor' in locals() and cursor:
                    cursor.close()
            except Exception:
                pass

    def execute_query(self, query, params=None, fetchone=False, fetchall=False):
        with self.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute(query, params or ())
                conn.commit()
                if fetchone:
                    return cursor.fetchone()
                if fetchall:
                    return cursor.fetchall()
                return cursor.lastrowid or cursor.rowcount
            except Exception as err:
                conn.rollback()
                logger.error(f"查询执行失败: {err}")
                raise

    def execute_many(self, query, params_list):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.executemany(query, params_list)
                conn.commit()
                return cursor.rowcount
            except Exception as err:
                conn.rollback()
                logger.error(f"批量执行失败: {err}")
                raise

    def check_connection(self):
        try:
            with self.get_connection() as conn:
                conn.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"数据库连接检查失败: {e}")
            return False


connection_pool = SQLiteDatabase()


def get_db_connection():
    return connection_pool.get_connection()


def execute_sql(sql, params=None):
    return connection_pool.execute_query(sql, params)


def _column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def _table_exists(cursor, table):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    )
    return cursor.fetchone() is not None


def create_tables(cursor):
    """创建所有表（SQLite 语法）"""

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS main_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            display_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_mc_display_order ON main_categories(display_order)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sub_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            main_category_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            display_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (main_category_id) REFERENCES main_categories(id) ON DELETE CASCADE,
            UNIQUE(main_category_id, name)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sc_display_order ON sub_categories(display_order)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS test_items (
            id TEXT PRIMARY KEY,
            display_order INTEGER NOT NULL UNIQUE,
            name TEXT NOT NULL,
            unit TEXT,
            data_type TEXT DEFAULT 'float',
            sub_category_id INTEGER NOT NULL,
            description TEXT,
            tags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sub_category_id) REFERENCES sub_categories(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ti_sub_category ON test_items(sub_category_id)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehicles (
            id TEXT PRIMARY KEY,
            model TEXT NOT NULL,
            chassis_number TEXT NOT NULL,
            production_date TEXT,
            curb_weight TEXT,
            notes TEXT,
            status TEXT DEFAULT 'active',
            energy_type TEXT DEFAULT '',
            vehicle_platform TEXT DEFAULT '',
            created_by TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_v_chassis ON vehicles(chassis_number)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_v_model ON vehicles(model)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS test_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id TEXT NOT NULL,
            test_item_id TEXT NOT NULL,
            value TEXT,
            test_date TEXT,
            operator TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE,
            FOREIGN KEY (test_item_id) REFERENCES test_items(id) ON DELETE CASCADE,
            UNIQUE(vehicle_id, test_item_id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tr_vehicle ON test_results(vehicle_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tr_test_item ON test_results(test_item_id)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS test_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id TEXT NOT NULL,
            main_category_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            description TEXT,
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE,
            FOREIGN KEY (main_category_id) REFERENCES main_categories(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ti_vehicle_category ON test_images(vehicle_id, main_category_id)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS report_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id TEXT NOT NULL,
            config_type TEXT NOT NULL,
            config_key TEXT NOT NULL,
            config_value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE,
            UNIQUE(vehicle_id, config_type, config_key)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_rc_vehicle ON report_configs(vehicle_id)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS report_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id TEXT NOT NULL,
            main_category_id TEXT NOT NULL,
            image_name TEXT NOT NULL,
            image_path TEXT NOT NULL,
            display_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ri_vehicle_category ON report_images(vehicle_id, main_category_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ri_display_order ON report_images(display_order)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS test_info_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id TEXT NOT NULL,
            main_category_id TEXT NOT NULL,
            info_key TEXT NOT NULL,
            info_value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE,
            UNIQUE(vehicle_id, main_category_id, info_key)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tic_vehicle_category ON test_info_configs(vehicle_id, main_category_id)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sample_car_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id TEXT NOT NULL,
            image_name TEXT NOT NULL,
            image_path TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sci_vehicle ON sample_car_images(vehicle_id)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS test_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id TEXT NOT NULL,
            project_number INTEGER NOT NULL,
            project_name TEXT NOT NULL,
            execution_standard TEXT,
            display_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE,
            UNIQUE(vehicle_id, project_number)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tp_display_order ON test_projects(display_order)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS test_equipment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id TEXT NOT NULL,
            equipment_name TEXT NOT NULL,
            equipment_accuracy TEXT,
            display_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_te_display_order ON test_equipment(display_order)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS report_signatures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id TEXT NOT NULL,
            signature_type TEXT NOT NULL,
            signature_name TEXT,
            signature_path TEXT,
            signature_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE,
            UNIQUE(vehicle_id, signature_type)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_rs_vehicle ON report_signatures(vehicle_id)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehicle_stats (
            vehicle_id TEXT PRIMARY KEY,
            model TEXT,
            chassis_number TEXT,
            valid_count INTEGER DEFAULT 0,
            total_items INTEGER DEFAULT 555,
            completion_rate REAL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_vs_completion ON vehicle_stats(completion_rate)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT,
            is_active INTEGER DEFAULT 1,
            is_admin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')

    for col_name, col_def in [
        ('status', "TEXT DEFAULT 'active'"),
        ('energy_type', "TEXT DEFAULT ''"),
        ('vehicle_platform', "TEXT DEFAULT ''"),
        ('created_by', "TEXT DEFAULT ''"),
    ]:
        if not _column_exists(cursor, 'vehicles', col_name):
            cursor.execute(f"ALTER TABLE vehicles ADD COLUMN {col_name} {col_def}")
            print(f"✅ 已为 vehicles 表添加 {col_name} 列")


def clear_vehicle_data(conn):
    """清空车辆及关联业务数据（保留测试项目目录与用户）"""
    cursor = conn.cursor()
    cursor.execute('PRAGMA foreign_keys = OFF')
    for table in (
        'test_results', 'report_configs', 'test_info_configs', 'test_projects',
        'test_equipment', 'report_signatures', 'report_images', 'sample_car_images',
        'test_images', 'vehicle_stats', 'vehicles',
    ):
        cursor.execute(f'DELETE FROM {table}')
    cursor.execute('PRAGMA foreign_keys = ON')
    conn.commit()


def seed_demo_data(conn, force=False):
    """预置 5 辆演示车及完整示例数据"""
    cursor = conn.cursor()
    if not force:
        cursor.execute('SELECT COUNT(*) FROM vehicles')
        if cursor.fetchone()[0] > 0:
            return 0

    demo_vehicles = [
        ('V10001', '1001', '20010001', '1850', '', 'active', '1', '1', 'admin'),
        ('V10002', '1002', '20010002', '1920', '', 'active', '2', '2', 'admin'),
        ('V10003', '1003', '20010003', '2100', '', 'active', '3', '3', 'admin'),
        ('V10004', '1004', '20010004', '1750', '', 'active', '1', '2', 'admin'),
        ('V10005', '1005', '20010005', '1680', '', 'active', '2', '1', 'admin'),
    ]
    for v in demo_vehicles:
        cursor.execute('''
            INSERT INTO vehicles (id, model, chassis_number, curb_weight, notes, status,
                                  energy_type, vehicle_platform, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', v)

    cursor.execute("SELECT id, name, display_order FROM test_items ORDER BY display_order")
    all_items = cursor.fetchall()
    if not all_items:
        conn.commit()
        return len(demo_vehicles)

    cursor.execute('SELECT COUNT(*) FROM test_items')
    total_item_count = cursor.fetchone()[0]

    cursor.execute('''
        SELECT ti.id, mc.name FROM test_items ti
        JOIN sub_categories sc ON ti.sub_category_id = sc.id
        JOIN main_categories mc ON sc.main_category_id = mc.id
        ORDER BY ti.display_order
    ''')
    category_first_item = {}
    for item_id, cat_name in cursor.fetchall():
        category_first_item.setdefault(cat_name, item_id)

    default_projects = [
        (1, '参数测量', 'GB/T 12674 汽车质量（重量）参数测定方法'),
        (2, '动力性试验', 'GB/T12543 汽车加速性能试验方法'),
        (3, '油耗试验', 'JT719-2008 营运货车燃料消耗量限值及测量方法'),
        (4, '制动试验', 'GB/T12676 商用车辆和挂车制动系统技术要求及试验方法'),
        (5, '滑行试验', 'GB/T27840 商用车燃料消耗量测量方法'),
        (6, '操纵稳定性试验', 'GB/T6323 汽车操纵稳定性试验方法'),
        (7, '灯光试验', 'X001 LED远近光灯测试与评价方法'),
        (8, '选换挡试验', 'X002 选换挡操纵性试验规范'),
    ]
    default_equipment = [
        ('转鼓试验台', '±0.1km/h', 1),
        ('五轴运动分析仪', '±0.01g', 2),
        ('油耗仪', '±1%', 3),
    ]

    test_date = '20260115'
    result_count = 0

    for idx, (vehicle_id, model, chassis, weight, *_rest) in enumerate(demo_vehicles):
        base = 100 + idx * 10
        # 每辆车抽取约 20 个测试项目写入结果
        step = max(1, len(all_items) // 20)
        for j in range(0, len(all_items), step):
            item_id, item_name, order = all_items[j]
            value = str(base + (order % 50) + j // step)
            cursor.execute('''
                INSERT INTO test_results (vehicle_id, test_item_id, value, test_date)
                VALUES (?, ?, ?, ?)
            ''', (vehicle_id, item_id, value, test_date))
            result_count += 1

        report_no = f'SY-X-2026-{int(model):03d}'
        header_cfg = {
            '编号': report_no,
            '名称': f'{model}性能试验报告',
            '编制日期': test_date,
        }
        overview_cfg = {
            '任务来源': str(idx + 1),
            '项目费用': str(100000 + int(model)),
            '试验结论': f'共完成 {len(range(0, len(all_items), step))} 个测试项目',
        }
        for key, val in header_cfg.items():
            cursor.execute('''
                INSERT INTO report_configs (vehicle_id, config_type, config_key, config_value)
                VALUES (?, 'header', ?, ?)
            ''', (vehicle_id, key, val))
        for key, val in overview_cfg.items():
            cursor.execute('''
                INSERT INTO report_configs (vehicle_id, config_type, config_key, config_value)
                VALUES (?, 'overview', ?, ?)
            ''', (vehicle_id, key, val))

        for cat_name, rep_item_id in category_first_item.items():
            info_rows = {
                '试验日期': test_date,
                '总质量（kg）': weight,
                '试验地点': str(100 + idx),
                '天气': '1',
                '里程（km）': str(1000 + int(model)),
                '备注': str(idx + 1),
            }
            for info_key, info_val in info_rows.items():
                cursor.execute('''
                    INSERT INTO test_info_configs (vehicle_id, main_category_id, info_key, info_value)
                    VALUES (?, ?, ?, ?)
                ''', (vehicle_id, rep_item_id, info_key, info_val))

        for pnum, pname, pstd in default_projects:
            cursor.execute('''
                INSERT INTO test_projects (vehicle_id, project_number, project_name, execution_standard, display_order)
                VALUES (?, ?, ?, ?, ?)
            ''', (vehicle_id, pnum, pname, pstd, pnum))

        for ename, eacc, eorder in default_equipment:
            cursor.execute('''
                INSERT INTO test_equipment (vehicle_id, equipment_name, equipment_accuracy, display_order)
                VALUES (?, ?, ?, ?)
            ''', (vehicle_id, ename, eacc, eorder))

        valid_count = len(range(0, len(all_items), step))
        completion_rate = round(valid_count / total_item_count * 100, 2) if total_item_count else 0
        cursor.execute('''
            INSERT INTO vehicle_stats (vehicle_id, model, chassis_number, valid_count, total_items, completion_rate)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (vehicle_id, model, chassis, valid_count, total_item_count, completion_rate))

    cursor.execute('''
        INSERT OR IGNORE INTO users (username, password, full_name, is_admin)
        VALUES (?, ?, ?, ?)
    ''', ('engineer', 'demo123', '演示工程师', 0))
    cursor.execute('''
        INSERT OR IGNORE INTO users (username, password, full_name, is_admin)
        VALUES (?, ?, ?, ?)
    ''', ('admin', 'admin123', '系统管理员', 1))

    conn.commit()
    print(f"✅ 演示数据已加载：{len(demo_vehicles)} 辆车，{result_count} 条测试结果")
    return len(demo_vehicles)


def init_database_schema():
    """初始化数据库表结构（首次运行时调用）"""
    from database.initializer import initialize_default_data

    with connection_pool.get_connection() as conn:
        cursor = conn.cursor()
        try:
            main_categories_exists = _table_exists(cursor, 'main_categories')
            print("检查并创建缺失的数据库表...")
            create_tables(cursor)
            conn.commit()

            if not main_categories_exists:
                print("首次运行：初始化默认数据...")
                item_count = initialize_default_data(conn)
                print(f"✅ 数据库初始化完成，共创建 {item_count} 个测试项目，序号1-{item_count}")
                logger.info(f"数据库表结构初始化完成，创建 {item_count} 个项目")
            else:
                cursor.execute('SELECT COUNT(*) FROM test_items')
                item_count = cursor.fetchone()[0]
                print(f"✅ 数据库已存在，共有 {item_count} 个测试项目")
                logger.info(f"数据库已存在，共有 {item_count} 个项目")
                if item_count == 0:
                    print("检测到空表，重新初始化数据...")
                    item_count = initialize_default_data(conn)
                    print(f"✅ 数据重新初始化完成，创建 {item_count} 个项目")

            seed_demo_data(conn)
            return True

        except Exception as e:
            conn.rollback()
            logger.error(f"数据库初始化失败: {e}")
            raise
