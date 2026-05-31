# database/initializer.py
"""
数据库初始化和维护功能
"""
import logging
from datetime import datetime

from db_config import connection_pool

logger = logging.getLogger(__name__)


def init_database():
    """初始化SQLite数据库"""
    try:
        if not connection_pool.check_connection():
            raise Exception("数据库连接失败")

        from db_config import init_database_schema
        init_database_schema()

        import time
        time.sleep(1)

        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM test_items')
            total_items = cursor.fetchone()[0]
            logger.info(f"数据库初始化验证：{total_items} 个测试项目")

        logger.info("SQLite 数据库初始化完成")

        # ========== 注意：先等表创建完成，再初始化统计 ==========
        # 等待一下确保表已创建
        time.sleep(0.5)

        # 初始化统计表
        init_vehicle_stats()

        return True

    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise


def initialize_default_data(conn):
    """初始化默认的测试项目数据"""
    cursor = conn.cursor()

    try:
        main_categories = [
            ("基本参数测量", 1),
            ("动力性", 2),
            ("经济性", 3),
            ("制动性能", 4),
            ("滑行性能", 5),
            ("操纵稳定性", 6),
            ("选换挡操作性", 7),
            ("乘降性", 8),
            ("灯具配光测试", 9)
        ]

        for name, order in main_categories:
            cursor.execute(
                "INSERT OR IGNORE INTO main_categories (name, display_order) VALUES (%s, %s)",
                (name, order)
            )

        main_cat_ids = {}
        for name, _ in main_categories:
            cursor.execute("SELECT id FROM main_categories WHERE name = %s", (name,))
            result = cursor.fetchone()
            if result:
                main_cat_ids[name] = result[0]

        test_data = {
            "基本参数测量": {
                "汽车主要尺寸测量": [
                    ("长", "mm"), ("宽", "mm"), ("高（空）", "mm"), ("高（满）", "mm"),
                    ("轴距", "mm"), ("前悬", "mm"), ("后悬", "mm"), ("前轮距", "mm"),
                    ("后轮距", "mm"), ("整车纵向通过角", "°"),
                    ("空载时前轴处车架纵梁上平面离地高度", "mm"),
                    ("空载时后轴处车架纵梁上平面离地高度", "mm"),
                    ("满载时前轴处车架纵梁上平面离地高度", "mm"),
                    ("满载时后轴处车架纵梁上平面离地高度", "mm"),
                    ("空载时侧围边梁前端离地高度（承载式车身）", "mm"),
                    ("空载时侧围边梁后端离地高度（承载式车身）", "mm"),
                    ("满载时侧围边梁前端离地高度（承载式车身）", "mm"),
                    ("满载时侧围边梁后端离地高度（承载式车身）", "mm"),
                    ("空载时侧防护后缘到后轮边缘", "mm"),
                    ("空载时前下防护下平面离地高度", "mm"),
                    ("空载时后防护装置下缘与地面距离", "mm"),
                    ("最小离地间隙（满）", "mm"), ("接近角（满）", "°"), ("离去角（满）", "°"),
                    ("最小转弯直径（左转）", "m"), ("最小转弯直径（右转）", "m"), ("转弯通道最大宽度", "m"),
                ],
                "汽车质量（重量）参数测定": [
                    ("整备质量", "kg"), ("前轴（空）", "kg"), ("后轴（空）", "kg"),
                    ("前轮轮荷（左）（空）", "kg"), ("前轮轮荷（右）（空）", "kg"),
                    ("后轮轮荷（左）（空）", "kg"), ("后轮轮荷（右）（空）", "kg"),
                    ("总质量（满，满油满水满尿素）", "kg"), ("前轴（满）", "kg"), ("后轴（满）", "kg"),
                    ("前轮轮荷（左）（满）", "kg"), ("前轮轮荷（右）（满）", "kg"),
                    ("后轮轮荷（左）（满）", "kg"), ("后轮轮荷（右）（满）", "kg"),
                    ("质心高度（空）", "kg"), ("质心高度（满）", "kg"),
                ],
                "四轮定位参数测量": [
                    ("前束（空）", "mm"), ("前束（满）", "mm"),
                    ("前轮外倾（左）（空）", "°"), ("前轮外倾（右）（空）", "°"),
                    ("前轮外倾（左）（满）", "°"), ("前轮外倾（右）（满）", "°"),
                    ("主销内倾（左）（空）", "°"), ("主销内倾（右）（空）", "°"),
                    ("主销内倾（左）（满）", "°"), ("主销内倾（右）（满）", "°"),
                    ("主销后倾（左）（空）", "°"), ("主销后倾（右）（空）", "°"),
                    ("主销后倾（左）（满）", "°"), ("主销后倾（右）（满）", "°"),
                    ("车轮转角（左）（空）", "°"), ("车轮转角（右）（空）", "°"),
                    ("车轮转角（左）（满）", "°"), ("车轮转角（右）（满）", "°"),
                ]
            },
            "动力性": {
                "车速表里程表校正": [
                    ("10km/h（仪表）", "km/h"), ("20km/h（仪表）", "km/h"), ("40km/h（仪表）", "km/h"),
                    ("60km/h（仪表）", "km/h"), ("80km/h（仪表）", "km/h"), ("90km/h（仪表）", "km/h"),
                    ("100km/h（仪表）", "km/h"), ("120km/h（仪表）", "km/h"), ("10km", "km"),
                    ("直接档", "km/h"), ("最高档", "km/h"),
                ],
                "最低稳定车速": [("最低稳定车速", "km/h")],
                "起步加速时间": [
                    ("0-50km/h", "s"), ("0-80km/h", "s"), ("0-90km/h", "s"), ("0-100km/h", "s"),
                ],
                "二档空车起步连续换档加速时间": [("0→80km/h", "s")],
                "区间加速": [
                    ("30km/h～70km/h", "s"), ("40km/h～70km/h", "s"), ("50km/h～80km/h", "s"),
                    ("60km/h～80km/h", "s"), ("70km/h～90km/h", "s"), ("80km/h～100km/h", "s"),
                ],
                "最高车速最高档": [("最高车速", "km/h")],
            },
            "经济性": {
                "交通部油耗": [
                    ("怠速工况", "L/100km"), ("加速工况", "L/100km"),
                    ("等速工况", "L/100km"), ("综合油耗", "L/100km"),
                ],
                "直接挡等速油耗": [
                    ("40km/h", "L/100km"), ("50km/h", "L/100km"), ("60km/h", "L/100km"),
                    ("70km/h", "L/100km"), ("80km/h", "L/100km"), ("90km/h", "L/100km"), ("100km/h", "L/100km"),
                ],
                "最高档等速油耗": [
                    ("40km/h", "L/100km"), ("50km/h", "L/100km"), ("60km/h", "L/100km"),
                    ("70km/h", "L/100km"), ("80km/h", "L/100km"), ("90km/h", "L/100km"),
                    ("100km/h", "L/100km"), ("110km/h", "L/100km"), ("120km/h", "L/100km"),
                ],
                "续驶里程": [
                    ("城市", "L/100km"), ("高速", "L/100km"), ("城郊", "L/100km"), ("等速100km/h", "L/100km"),
                ]
            },
            "制动性能": {
                "冷态制动": [
                    ("空载，发动机脱开冷态制动 - 制动距离", "m"), ("空载，发动机脱开冷态制动 - 制动踏板力", "N"),
                    ("空载，发动机脱开冷态制动 - MFDD", "m/s²"), ("空载，发动机脱开冷态制动 - 稳定性", "ok"),
                    ("空载，发动机接合冷态制动 - 制动距离", "m"), ("空载，发动机接合冷态制动 - 制动踏板力", "N"),
                    ("空载，发动机接合冷态制动 - MFDD", "m/s²"), ("空载，发动机接合冷态制动 - 稳定性", "ok"),
                    ("满载，发动机脱开冷态制动 - 制动距离", "m"), ("满载，发动机脱开冷态制动 - 制动踏板力", "N"),
                    ("满载，发动机脱开冷态制动 - MFDD", "m/s²"), ("满载，发动机脱开冷态制动 - 稳定性", "ok"),
                    ("满载，发动机接合冷态制动 - 制动距离", "m"), ("满载，发动机接合冷态制动 - 制动踏板力", "N"),
                    ("满载，发动机接合冷态制动 - MFDD", "m/s²"), ("满载，发动机接合冷态制动 - 稳定性", "ok"),
                ],
                "热态制动": [
                    ("满载，发动机脱开热态制动 - 制动距离", "m"), ("满载，发动机脱开热态制动 - 制动踏板力", "N"),
                    ("满载，发动机脱开热态制动 - MFDD", "m/s²"), ("满载，发动机脱开热态制动 - 稳定性", "ok"),
                ],
                "应急制动": [
                    ("前回管路失效满载 - 制动距离", "m"), ("前回管路失效满载 - 制动踏板力", "N"),
                    ("前回管路失效满载 - MFDD", "m/s²"), ("前回管路失效满载 - 稳定性", "ok"),
                    ("后回管路失效满载 - 制动距离", "m"), ("后回管路失效满载 - 制动踏板力", "N"),
                    ("后回管路失效满载 - MFDD", "m/s²"), ("后回管路失效满载 - 稳定性", "ok"),
                    ("真空助力失效满载 - 制动距离", "m"), ("真空助力失效满载 - 制动踏板力", "N"),
                    ("真空助力失效满载 - MFDD", "m/s²"), ("真空助力失效满载 - 稳定性", "ok"),
                ],
                "制动部件能力": [
                    ("抽真空能力耗时", "min"), ("最大真空度", "bar"), ("达到最大真空度时间", "s"),
                    ("真空度0.6bar时间", "s"), ("打气能力压力从0到P1时间", "min"),
                    ("打气能力压力从0到P2时间", "min"),
                    ("气密性空压机停止3min后，管路气压下降值", "kPa"),
                    ("气密性空压机停止，制动踏板踩到底，3min后，管路气压下降值", "kPa"),
                    ("气制动系统车辆响应时间", "s"), ("高速制动性能100km/h→0 - 制动距离", "m"),
                    ("70km/h排气制动性能减速度差值", "m/s²"),
                ]
            },
            "滑行性能": {
                "不同车速滑行时间": [
                    ("90km/h", "s"), ("85km/h", "s"), ("80km/h", "s"), ("75km/h", "s"),
                    ("70km/h", "s"), ("65km/h", "s"), ("60km/h", "s"), ("55km/h", "s"),
                    ("50km/h", "s"), ("45km/h", "s"), ("40km/h", "s"), ("35km/h", "s"),
                    ("30km/h", "s"), ("25km/h", "s"), ("20km/h", "s"), ("15km/h", "s"),
                    ("10km/h", "s"), ("5km/h", "s"), ("0km/h", "s"),
                ],
                "滑行阻力系数计算": [
                    ("阻力二次项系数c", "c"), ("阻力一次项系数b", "b"), ("阻力常数项系数a", "a"),
                ]
            },
            "操纵稳定性": {
                "稳态回转": [
                    ("固定转角加速（左转） - 初始半径", "m"),
                    ("固定转角加速（左转） - 中性转向点侧向加速度an", "m/s²"),
                    ("固定转角加速（右转） - 初始半径", "m"),
                    ("固定转角加速（右转） - 中性转向点侧向加速度an", "m/s²"),
                ],
                "转向轻便性": [
                    ("原地怠速转动转向盘 - 最大操作力", "N"),
                    ("绕'8'字 - 方向盘最大作用力矩", "Nm"),
                    ("绕'8'字 - 方向盘最大作用力", "N"),
                ],
                "转向回正性": [
                    ("左转回正松手3s后残留横摆角速度", "(°)/s"),
                    ("左转回正横摆角速度稳定时间", "s"),
                    ("左转回正横摆角速度超调量", "%"),
                    ("右转回正松手3s后残留横摆角速度", "(°)/s"),
                    ("右转回正横摆角速度稳定时间", "s"),
                    ("右转回正横摆角速度超调量", "%"),
                ]
            },
            "选换挡操作性": {
                "离合操作性": [
                    ("离合踏板总行程", "mm"), ("离合踏板结合行程", "mm"), ("离合踏板最大踏板力", "N"),
                ],
                "挡位自由间隙": [
                    ("档位自由间隙左右 - 1档", "mm*mm"), ("档位自由间隙上下 - 1档", "mm*mm"),
                    ("档位自由间隙左右 - 2档", "mm*mm"), ("档位自由间隙上下 - 2档", "mm*mm"),
                    ("档位自由间隙左右 - 3档", "mm*mm"), ("档位自由间隙上下 - 3档", "mm*mm"),
                    ("档位自由间隙左右 - 4档", "mm*mm"), ("档位自由间隙上下 - 4档", "mm*mm"),
                    ("档位自由间隙左右 - 5档", "mm*mm"), ("档位自由间隙上下 - 5档", "mm*mm"),
                    ("档位自由间隙左右 - 6档", "mm*mm"), ("档位自由间隙上下 - 6档", "mm*mm"),
                    ("档位自由间隙左右 - N档", "mm*mm"), ("档位自由间隙上下 - N档", "mm*mm"),
                ],
                "选档力": [
                    ("选档力 - 1/2档", "N"), ("选档力 - 5/6档", "N"), ("选档力 - R档", "N"),
                ],
                "换挡力": [
                    ("换档力 - N→1档", "N"), ("换档力 - N→2档", "N"), ("换档力 - N→3档", "N"),
                    ("换档力 - N→4档", "N"), ("换档力 - N→5档", "N"), ("换档力 - N→6档", "N"),
                    ("换档力 - N→R档", "N"),
                ],
                "选档行程": [
                    ("选档行程 - 1/2档", "mm"), ("选档行程 - 5/6档", "mm"), ("选档行程 - R档", "mm"),
                ],
                "换挡行程": [
                    ("换档行程 - N→1档", "mm"), ("换档行程 - N→2档", "mm"), ("换档行程 - N→3档", "mm"),
                    ("换档行程 - N→4档", "mm"), ("换档行程 - N→5档", "mm"), ("换档行程 - N→6档", "mm"),
                    ("换档行程 - N→R档", "mm"),
                ],
                "动态换挡力": [
                    ("动态换档力（升档） - 1→2档", "N"), ("动态换档力（升档） - 2→3档", "N"),
                    ("动态换档力（升档） - 3→4档", "N"), ("动态换档力（升档） - 4→5档", "N"),
                    ("动态换档力（升档） - 5→6档", "N"), ("动态换档力（降档） - 6→5档", "N"),
                    ("动态换档力（降档） - 5→4档", "N"), ("动态换档力（降档） - 4→3档", "N"),
                    ("动态换档力（降档） - 3→2档", "N"), ("动态换档力（降档） - 2→1档", "N"),
                ],
                "动态换挡二次冲击力": [
                    ("二次冲击力（升档） - 1→2档", "N"), ("二次冲击力（升档） - 2→3档", "N"),
                    ("二次冲击力（升档） - 3→4档", "N"), ("二次冲击力（升档） - 4→5档", "N"),
                    ("二次冲击力（升档） - 5→6档", "N"), ("二次冲击力（降档） - 6→5档", "N"),
                    ("二次冲击力（降档） - 5→4档", "N"), ("二次冲击力（降档） - 4→3档", "N"),
                    ("二次冲击力（降档） - 3→2档", "N"), ("二次冲击力（降档） - 2→1档", "N"),
                ]
            },
            "乘降性": {
                "车门关闭速度": [
                    ("左前门最小的车门关闭速度", "m/s"), ("右前门最小的车门关闭速度", "m/s"),
                    ("侧滑门最小的车门关闭速度", "m/s"), ("后背门最小的车门关闭速度", "m/s"),
                    ("左后门最小的车门关闭速度", "m/s"), ("右后门最小的车门关闭速度", "m/s"),
                ]
            },
            "灯具配光测试": {
                "前组合灯": [
                    ("前组合灯车前暗区", "m"), ("前组合灯近光75R", "Lux"), ("前组合灯近光75L", "Lux"),
                    ("前组合灯近光50L", "Lux"), ("前组合灯近光50R", "Lux"), ("前组合灯近光50V", "Lux"),
                    ("前组合灯近光25L", "Lux"), ("前组合灯近光25R", "Lux"), ("前组合灯远光强度", "Lux"),
                    ("前组合灯远光范围1,125m,25000，空中", "Lux"),
                    ("前组合灯远光范围: 2,25m,25000，空中", "Lux"),
                ]
            }
        }

        global_order = 1

        for main_cat_name, sub_cats in test_data.items():
            main_cat_id = main_cat_ids[main_cat_name]
            sub_order = 1

            for sub_cat_name, items in sub_cats.items():
                cursor.execute('''
                    INSERT OR IGNORE INTO sub_categories (main_category_id, name, display_order) 
                    VALUES (%s, %s, %s)
                ''', (main_cat_id, sub_cat_name, sub_order))

                cursor.execute("SELECT id FROM sub_categories WHERE main_category_id = %s AND name = %s",
                               (main_cat_id, sub_cat_name))
                result = cursor.fetchone()
                if result:
                    sub_cat_id = result[0]
                else:
                    continue

                for item_name, unit in items:
                    item_id = f"TI{global_order:04d}"
                    cursor.execute('''
                        INSERT OR IGNORE INTO test_items 
                        (id, display_order, name, unit, data_type, sub_category_id) 
                        VALUES (%s, %s, %s, %s, %s, %s)
                    ''', (item_id, global_order, item_name, unit, 'float', sub_cat_id))
                    global_order += 1

                sub_order += 1

        print(f"✅ 数据库初始化完成，共创建 {global_order - 1} 个测试项目")
        return global_order - 1

    except Exception as e:
        print(f"数据库初始化失败: {e}")
        raise


def check_and_fix_serial_numbers():
    """检查和修复序号问题"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM test_items')
            total_items = cursor.fetchone()[0]

            if total_items == 0:
                return True, f"数据库为空，等待初始化数据"

            cursor.execute('''
                SELECT display_order, COUNT(*) as count, GROUP_CONCAT(id)
                FROM test_items
                GROUP BY display_order
                HAVING COUNT(*) > 1
            ''')
            duplicate_orders = cursor.fetchall()
            if duplicate_orders:
                duplicate_info = []
                for order, count, ids in duplicate_orders:
                    duplicate_info.append(f"序号 {order}: {count} 个项目 ({ids})")
                return False, f"发现重复序号：{', '.join(duplicate_info)}"

            cursor.execute('SELECT MIN(display_order), MAX(display_order) FROM test_items')
            min_order, max_order = cursor.fetchone()

            if min_order is None or max_order is None:
                return True, f"数据库无有效数据，等待初始化"

            if max_order != total_items or min_order != 1:
                return False, f"序号不连续：应有{total_items}个项目，序号1-{total_items}，实际序号{min_order}-{max_order}"

            cursor.execute('''
                WITH RECURSIVE numbers(n) AS (
                    SELECT 1
                    UNION ALL
                    SELECT n+1 FROM numbers WHERE n < (SELECT COUNT(*) FROM test_items)
                )
                SELECT n FROM numbers
                WHERE n NOT IN (SELECT display_order FROM test_items)
                ORDER BY n
            ''')
            missing_numbers = cursor.fetchall()
            if missing_numbers:
                missing_str = ', '.join(str(num[0]) for num in missing_numbers)
                return False, f"发现缺失序号：{missing_str}"

            return True, f"序号检查通过：{total_items} 个项目，序号1-{total_items}"

    except Exception as e:
        import traceback
        error_msg = f"序号检查异常（不影响使用）：{str(e)}"
        print(f"⚠️ {error_msg}")
        print(traceback.format_exc())
        return True, error_msg


def get_database_stats():
    """获取数据库统计信息"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            stats = {}

            stats['database_name'] = str(DB_PATH.name)

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = cursor.fetchall()
            stats['table_count'] = len(tables)

            total_records = 0
            table_stats = []
            for table in tables:
                table_name = table[0]
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                total_records += count
                table_stats.append({'table': table_name, 'records': count})

            stats['total_records'] = total_records
            stats['table_stats'] = table_stats

            from db_config import DB_PATH
            db_size = DB_PATH.stat().st_size if DB_PATH.exists() else 0
            stats['database_size_mb'] = db_size / 1024 / 1024

            cursor.execute("SELECT COUNT(*) FROM vehicles")
            stats['vehicle_count'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM test_results")
            stats['test_result_count'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM report_images")
            stats['report_image_count'] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM sample_car_images")
            stats['sample_image_count'] = cursor.fetchone()[0]
            stats['image_count'] = stats['report_image_count'] + stats['sample_image_count']

            from pathlib import Path
            uploads_dir = Path('uploads')
            if uploads_dir.exists():
                image_files = list(uploads_dir.glob('**/*.*'))
                stats['image_files'] = len(
                    [f for f in image_files if f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']])
            else:
                stats['image_files'] = 0

            try:
                cursor.execute("SELECT MAX(created_at) FROM vehicles")
                last_vehicle = cursor.fetchone()[0]
                stats['last_vehicle_added'] = last_vehicle
            except:
                stats['last_vehicle_added'] = None

            return stats
    except Exception as e:
        logger.error(f"获取数据库统计失败: {e}")
        return None


def init_vehicle_stats():
    """
    初始化所有车辆的统计数据
    作用：首次部署时，为现有车辆填充统计表数据
    """
    try:
        from db_config import connection_pool
        from database.core import update_vehicle_stats

        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()

            # 先检查 vehicle_stats 表是否存在
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='vehicle_stats'"
            )
            table_exists = cursor.fetchone()

            if not table_exists:
                print("vehicle_stats 表不存在，跳过初始化")
                return 0

            # 检查统计表是否有数据
            cursor.execute("SELECT COUNT(*) FROM vehicle_stats")
            count = cursor.fetchone()[0]

            if count == 0:
                print("正在初始化车辆统计数据...")

                # 获取所有车辆
                cursor.execute("SELECT id FROM vehicles")
                vehicles = cursor.fetchall()

                for vehicle in vehicles:
                    try:
                        update_vehicle_stats(vehicle[0])
                    except Exception as e:
                        print(f"更新车辆 {vehicle[0]} 统计失败: {e}")

                print(f"✅ 已初始化 {len(vehicles)} 辆车的统计数据")
                return len(vehicles)
            else:
                print(f"统计表已有 {count} 条数据，跳过初始化")
                return count

    except Exception as e:
        print(f"初始化统计表失败: {e}")
        return 0

# database/initializer.py - 文件末尾添加

try:
    import streamlit as st
    _STREAMLIT_AVAILABLE = True
except ImportError:
    st = None
    _STREAMLIT_AVAILABLE = False


def _optional_cache(ttl=300, show_spinner=False):
    if _STREAMLIT_AVAILABLE:
        return st.cache_data(ttl=ttl, show_spinner=show_spinner)
    return lambda fn: fn


@_optional_cache(ttl=300, show_spinner=False)
def get_cached_database_stats():
    """缓存数据库统计信息（5分钟）"""
    return get_database_stats()


@_optional_cache(ttl=300, show_spinner=False)
def get_cached_vehicle_count():
    """缓存车辆数量"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM vehicles")
            return cursor.fetchone()[0]
    except:
        return 0


@_optional_cache(ttl=300, show_spinner=False)
def get_cached_test_result_count():
    """缓存有效测试数据数量"""
    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM test_results 
                WHERE value IS NOT NULL AND value != '' AND TRIM(value) != ''
            """)
            return cursor.fetchone()[0]
    except:
        return 0