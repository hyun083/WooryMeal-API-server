from flask import Flask, jsonify, request, make_response
import sqlite3
import os
import json

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
        date TEXT NOT NULL,
        meals TEXT NOT NULL  -- JSON 형태로 lunch와 dinner를 함께 저장
    )
    ''')
    conn.commit()
    conn.close()

# API 엔드포인트
# 전체 메뉴 조회
@app.route('/menu', methods=['GET'])
def get_all_menu():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM menu')
    rows = cursor.fetchall()

    # 데이터 변환
    menus = [
        {
            "id": row[0],
            "date": row[1],
            "meals": json.loads(row[2])  # meals에 lunch와 dinner 모두 포함
        }
        for row in rows
    ]
    conn.close()
    
    # UTF-8 헤더 추가
    response = make_response(jsonify(menus))
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response

# 특정 날짜 메뉴 조회
@app.route('/menu/<date>', methods=['GET'])
def get_menu_by_date(date):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT meals FROM menu WHERE date = ?', (date,))
    row = cursor.fetchone()

    if not row:
        return jsonify({"error": "No menu found for this date"}), 404

    # meals 데이터를 JSON으로 변환
    meals = json.loads(row[0])
    conn.close()

    # UTF-8 Content-Type 명시
    response = make_response(jsonify({"date": date, "meals": meals}))
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response

# 메뉴 데이터 추가
@app.route('/menu', methods=['POST'])
def add_menu():
    try:
        data = request.get_json()

        # 필수 필드 확인
        if 'date' not in data or 'meals' not in data:
            return jsonify({"error": "'date'와 'meals' 필드는 필수입니다."}), 400

        meals = data['meals']

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
        INSERT INTO menu (date, meals)
        VALUES (?, ?)
        ''', (data['date'], json.dumps(data['meals'], ensure_ascii=False)))
        conn.commit()
        conn.close()

        return make_response(jsonify({"message": "Menu added successfully"}), 201)

    except Exception as e:
        return make_response(jsonify({"error": str(e)}), 500)
    
# 데이터베이스 초기화
init_db()

# 서버 시작
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)