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

# 데이터베이스 초기화 함수
def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # 테이블 생성 (meals에 lunch와 dinner 정보 통합)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS menu (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL UNIQUE,
        meals TEXT NOT NULL,  -- JSON 형태로 lunch와 dinner를 함께 저장
        order_seq TEXT NOT NULL  -- 조 순서 저장
    )
    ''')
    conn.commit()
    conn.close()


def serialize_menu_row(row):
    return {
        "id": row[0],
        "date": row[1],
        "meals": json.loads(row[2]),
        "order": json.loads(row[3])
    }


def validate_date_string(value, field_name):
    try:
        date.fromisoformat(value)
    except ValueError:
        return jsonify({"error": f"'{field_name}'은 YYYY-MM-DD 형식의 유효한 날짜여야 합니다."}), 400

    return None

# API 엔드포인트
# 전체 메뉴 조회
@app.route('/menu', methods=['GET'])
def get_all_menu():
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

    query = 'SELECT * FROM menu'
    params = []

    if from_date is not None:
        query += ' WHERE date >= ?'
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
@app.route('/menu/<date>', methods=['GET'])
def get_menu_by_date(date):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT meals, order_seq FROM menu WHERE date = ?', (date,))
    row = cursor.fetchone()
    
    conn.close()

    if not row:
        return jsonify({"error": "No menu found for this date"}), 404

    # meals 데이터를 JSON으로 변환
    meals = json.loads(row[0])
    order = json.loads(row[1])
    
    # UTF-8 Content-Type 명시
    response = make_response(jsonify({
        "date": date,
        "meals": meals,
        "order": order
    }))
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response

# 특정 날짜 메뉴 삭제
@app.route('/menu/<date>', methods=['DELETE'])
def delete_menu_by_date(date):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute('DELETE FROM menu WHERE date = ?', (date,))
    conn.commit()
    deleted_count = cursor.rowcount
    conn.close()

    if deleted_count == 0:
        return jsonify({"error": "No menu found for this date"}), 404

    return make_response(jsonify({"message": "Menu deleted successfully"}), 200)

# 특정 날짜 메뉴 수정
@app.route('/menu/<date>', methods=['PUT'])
def update_menu_by_date(date):
    try:
        data = request.get_json()

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
        cursor.execute('SELECT id FROM menu WHERE date = ?', (date,))
        if cursor.fetchone() is None:
            conn.close()
            return jsonify({"error": "No menu found for this date"}), 404
        
        # 데이터 업데이트
        cursor.execute('''
        UPDATE menu SET meals = ?, order_seq = ? WHERE date = ?
        ''', (
            json.dumps(meals, ensure_ascii=False),
            json.dumps(order, ensure_ascii=False),
            date
        ))
        conn.commit()
        conn.close()

        return make_response(jsonify({"message": "Menu updated successfully"}), 200)

    except Exception as e:
        return make_response(jsonify({"error": str(e)}), 500)

# 메뉴 데이터 추가
@app.route('/menu', methods=['POST'])
def add_menu():
    try:
        data = request.get_json()

        # 필수 필드 확인
        if 'date' not in data or 'meals' not in data or 'order' not in data:
            return jsonify({"error": "'date', 'meals', 'order' 필드는 필수입니다."}), 400

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
        INSERT INTO menu (date, meals, order_seq)
        VALUES (?, ?, ?)
        ''', (
            data['date'],
            json.dumps(data['meals'], ensure_ascii=False),
            json.dumps(order, ensure_ascii=False)
        ))
        conn.commit()
        conn.close()

        return make_response(jsonify({"message": "Menu added successfully"}), 201)

    except sqlite3.IntegrityError:
        return jsonify({"error": "이미 존재하는 날짜입니다."}), 409

    except Exception as e:
        return make_response(jsonify({"error": str(e)}), 500)

# 데이터베이스 초기화 및 서버 시작
init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
