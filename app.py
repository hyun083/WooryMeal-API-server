from flask import Flask, jsonify, request, make_response
import sqlite3
import os
import json
from datetime import date

# Flask 애플리케이션 초기화
app = Flask(__name__)

# Flask의 JSON 직렬화 설정
app.config['JSON_AS_ASCII'] = False

# SQLite 데이터베이스 경로 설정
DATABASE_PATH = os.getenv('DATABASE_PATH', '/data/menu.db')
VALID_REGIONS = {"yongin", "pyeongtaek"}
DEFAULT_REGION = os.getenv('DEFAULT_REGION', 'yongin')


MENU_TABLE_SCHEMA = '''
CREATE TABLE menu (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    region TEXT NOT NULL,
    date TEXT NOT NULL,
    meals TEXT NOT NULL,
    order_seq TEXT NOT NULL,
    UNIQUE (region, date)
)
'''

# 데이터베이스 초기화 함수
def init_db():
    if DEFAULT_REGION not in VALID_REGIONS:
        raise ValueError(
            f"DEFAULT_REGION은 {sorted(VALID_REGIONS)} 중 하나여야 합니다."
        )

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'menu'"
        )
        table_exists = cursor.fetchone() is not None

        if not table_exists:
            cursor.execute(MENU_TABLE_SCHEMA)
            conn.commit()
            return

        cursor.execute('PRAGMA table_info(menu)')
        columns = {row[1] for row in cursor.fetchall()}

        cursor.execute('PRAGMA index_list(menu)')
        unique_indexes = [row[1] for row in cursor.fetchall() if row[2]]
        unique_column_sets = []
        for index_name in unique_indexes:
            cursor.execute(f'PRAGMA index_info("{index_name}")')
            unique_column_sets.append([row[2] for row in cursor.fetchall()])

        schema_is_current = (
            'region' in columns
            and ['region', 'date'] in unique_column_sets
            and ['date'] not in unique_column_sets
        )
        if schema_is_current:
            return

        # 기존 date UNIQUE 제약을 (region, date) UNIQUE로 변경하며
        # 기존 데이터는 DEFAULT_REGION에 속한 것으로 이관한다.
        cursor.execute('DROP TABLE IF EXISTS menu_migration')
        cursor.execute(MENU_TABLE_SCHEMA.replace('CREATE TABLE menu', 'CREATE TABLE menu_migration'))

        if 'region' in columns:
            cursor.execute('''
                INSERT INTO menu_migration (id, region, date, meals, order_seq)
                SELECT id,
                       COALESCE(NULLIF(region, ''), ?),
                       date,
                       meals,
                       order_seq
                FROM menu
            ''', (DEFAULT_REGION,))
        else:
            cursor.execute('''
                INSERT INTO menu_migration (id, region, date, meals, order_seq)
                SELECT id, ?, date, meals, order_seq
                FROM menu
            ''', (DEFAULT_REGION,))

        cursor.execute('DROP TABLE menu')
        cursor.execute('ALTER TABLE menu_migration RENAME TO menu')
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def serialize_menu_row(row):
    return {
        "id": row[0],
        "region": row[1],
        "date": row[2],
        "meals": json.loads(row[3]),
        "order": json.loads(row[4])
    }


def validate_date_string(value, field_name):
    try:
        date.fromisoformat(value)
    except (TypeError, ValueError):
        return jsonify({"error": f"'{field_name}'은 YYYY-MM-DD 형식의 유효한 날짜여야 합니다."}), 400

    return None


def validate_region(region):
    if region not in VALID_REGIONS:
        return jsonify({
            "error": f"'{region}'은 지원하지 않는 지역입니다.",
            "valid_regions": sorted(VALID_REGIONS)
        }), 400

    return None

# API 엔드포인트
# 전체 메뉴 조회
@app.route('/<region>/menu', methods=['GET'])
def get_all_menu(region):
    region_error = validate_region(region)
    if region_error:
        return region_error

    from_date = request.args.get('from')
    limit = request.args.get('limit')

    if from_date is not None:
        date_error = validate_date_string(from_date, 'from')
        if date_error:
            return date_error

    if limit is not None:
        try:
            limit = int(limit)
        except ValueError:
            return jsonify({"error": "'limit'은 1 이상의 정수여야 합니다."}), 400

        if limit < 1:
            return jsonify({"error": "'limit'은 1 이상의 정수여야 합니다."}), 400

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    query = 'SELECT id, region, date, meals, order_seq FROM menu WHERE region = ?'
    params = [region]

    if from_date is not None:
        query += ' AND date >= ?'
        params.append(from_date)

    query += ' ORDER BY date ASC'

    if limit is not None:
        query += ' LIMIT ?'
        params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()

    conn.close()

    menus = [serialize_menu_row(row) for row in rows]
    
    # UTF-8 헤더 추가
    response = make_response(jsonify(menus))
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response

# 특정 날짜 메뉴 조회
@app.route('/<region>/menu/<menu_date>', methods=['GET'])
def get_menu_by_date(region, menu_date):
    region_error = validate_region(region)
    if region_error:
        return region_error

    date_error = validate_date_string(menu_date, 'date')
    if date_error:
        return date_error

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT meals, order_seq FROM menu WHERE region = ? AND date = ?',
        (region, menu_date)
    )
    row = cursor.fetchone()
    
    conn.close()

    if not row:
        return jsonify({"error": "No menu found for this date"}), 404

    # meals 데이터를 JSON으로 변환
    meals = json.loads(row[0])
    order = json.loads(row[1])
    
    # UTF-8 Content-Type 명시
    response = make_response(jsonify({
        "region": region,
        "date": menu_date,
        "meals": meals,
        "order": order
    }))
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response

# 특정 날짜 메뉴 삭제
@app.route('/<region>/menu/<menu_date>', methods=['DELETE'])
def delete_menu_by_date(region, menu_date):
    region_error = validate_region(region)
    if region_error:
        return region_error

    date_error = validate_date_string(menu_date, 'date')
    if date_error:
        return date_error

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute(
        'DELETE FROM menu WHERE region = ? AND date = ?',
        (region, menu_date)
    )
    conn.commit()
    deleted_count = cursor.rowcount
    conn.close()

    if deleted_count == 0:
        return jsonify({"error": "No menu found for this date"}), 404

    return make_response(jsonify({
        "message": "Menu deleted successfully",
        "region": region
    }), 200)

# 특정 날짜 메뉴 수정
@app.route('/<region>/menu/<menu_date>', methods=['PUT'])
def update_menu_by_date(region, menu_date):
    conn = None

    try:
        region_error = validate_region(region)
        if region_error:
            return region_error

        date_error = validate_date_string(menu_date, 'date')
        if date_error:
            return date_error

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "JSON 객체 본문이 필요합니다."}), 400

        # 필수 필드 확인
        if 'meals' not in data or 'order' not in data:
            return jsonify({"error": "'meals', 'order' 필드는 필수입니다."}), 400

        meals = data['meals']
        order = data['order']

        # order 유효성 검사
        valid_orders = {"1조", "2조", "3조"}
        
        if not isinstance(order, list) or set(order) != valid_orders:
            return jsonify({
                "error": "'order'는 '1조', '2조', '3조'를 포함한 리스트여야 하며, 순서만 바뀔 수 있습니다."
            }), 400

        # meals 내부의 lunch와 dinner 필드 검증
        required_meal_fields = ['rice', 'soup', 'dishes', 'kimchi', 'plus_corner']
        
        for meal_type in ['lunch', 'dinner']:
            if meal_type not in meals:
                return jsonify({"error": f"meals에는 '{meal_type}'가 포함되어야 합니다."}), 400
            
            for field in required_meal_fields:
                if field not in meals[meal_type]:
                    return jsonify({
                        "error": f"'{meal_type}'에 '{field}' 필드가 없습니다."
                    }), 400

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # 해당 날짜 데이터 존재 여부 확인
        cursor.execute(
            'SELECT id FROM menu WHERE region = ? AND date = ?',
            (region, menu_date)
        )
        if cursor.fetchone() is None:
            return jsonify({"error": "No menu found for this date"}), 404
        
        # 데이터 업데이트
        cursor.execute('''
        UPDATE menu SET meals = ?, order_seq = ? WHERE region = ? AND date = ?
        ''', (
            json.dumps(meals, ensure_ascii=False),
            json.dumps(order, ensure_ascii=False),
            region,
            menu_date
        ))
        conn.commit()

        return make_response(jsonify({
            "message": "Menu updated successfully",
            "region": region
        }), 200)

    except Exception as e:
        if conn is not None:
            conn.rollback()
        return make_response(jsonify({"error": str(e)}), 500)

    finally:
        if conn is not None:
            conn.close()

# 메뉴 데이터 추가
@app.route('/<region>/menu', methods=['POST'])
def add_menu(region):
    conn = None

    try:
        region_error = validate_region(region)
        if region_error:
            return region_error

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "JSON 객체 본문이 필요합니다."}), 400

        # 필수 필드 확인
        if 'date' not in data or 'meals' not in data or 'order' not in data:
            return jsonify({"error": "'date', 'meals', 'order' 필드는 필수입니다."}), 400

        date_error = validate_date_string(data['date'], 'date')
        if date_error:
            return date_error

        meals = data['meals']
        order = data['order']

        # order 유효성 검사
        valid_orders = {"1조", "2조", "3조"}
        
        if not isinstance(order, list) or set(order) != valid_orders:
            return jsonify({
                "error": "'order'는 '1조', '2조', '3조'를 포함한 리스트여야 하며, 순서만 바뀔 수 있습니다."
            }), 400

        # meals 내부의 lunch와 dinner 필드 검증
        required_meal_fields = ['rice', 'soup', 'dishes', 'kimchi', 'plus_corner']
        
        for meal_type in ['lunch', 'dinner']:
            if meal_type not in meals:
                return jsonify({"error": f"meals에는 '{meal_type}'가 포함되어야 합니다."}), 400
            
            for field in required_meal_fields:
                if field not in meals[meal_type]:
                    return jsonify({
                        "error": f"'{meal_type}'에 '{field}' 필드가 없습니다."
                    }), 400

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # 데이터 삽입 (JSON 형태로 저장)
        cursor.execute('''
        INSERT INTO menu (region, date, meals, order_seq)
        VALUES (?, ?, ?, ?)
        ''', (
            region,
            data['date'],
            json.dumps(data['meals'], ensure_ascii=False),
            json.dumps(order, ensure_ascii=False)
        ))
        conn.commit()

        return make_response(jsonify({
            "message": "Menu added successfully",
            "region": region
        }), 201)

    except sqlite3.IntegrityError:
        if conn is not None:
            conn.rollback()
        return jsonify({"error": "해당 지역에 이미 존재하는 날짜입니다."}), 409

    except Exception as e:
        if conn is not None:
            conn.rollback()
        return make_response(jsonify({"error": str(e)}), 500)

    finally:
        if conn is not None:
            conn.close()

# 데이터베이스 초기화 및 서버 시작
init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
