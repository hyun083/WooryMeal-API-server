# WooryMeal-API-server

우리밀 식단 조회 서비스용 API 서버입니다.  
Flask와 SQLite를 사용하며, 날짜 기준으로 식단 데이터를 등록, 조회, 수정, 삭제할 수 있습니다.

## 기술 스택

- Python 3.10
- Flask
- Gunicorn
- SQLite
- Docker

## 주요 기능

- 전체 식단 조회
- 특정 날짜 식단 조회
- 식단 등록
- 특정 날짜 식단 수정
- 특정 날짜 식단 삭제

## 데이터 구조

식단 데이터는 `menu` 테이블에 저장됩니다.

- `id`: 자동 증가 기본키
- `date`: 날짜 문자열, 고유값
- `meals`: 점심/저녁 식단 JSON 문자열
- `order_seq`: 조 순서 JSON 문자열

`meals`는 다음 구조를 가집니다.

- `lunch`
- `dinner`

각 식사(`lunch`, `dinner`)에는 아래 필드가 필요합니다.

- `rice`
- `soup`
- `dishes`
- `kimchi`
- `plus_corner`

타입 가이드는 다음과 같습니다.

- `rice`: 배열
- `dishes`: 배열
- `plus_corner`: 배열

`order`는 `1조`, `2조`, `3조`를 모두 포함한 배열이어야 하며 순서만 변경 가능합니다.

## 로컬 실행 방법

1. 의존성 설치

```bash
pip install -r requirements.txt
```

2. 서버 실행

```bash
python app.py
```

기본 실행 주소는 `http://localhost:8080` 입니다.

## API 명세

### 1) 전체 메뉴 조회

- Method: `GET`
- URL: `/menu`

```bash
curl -X GET "http://localhost:8080/menu"
```

### 2) 특정 날짜 메뉴 조회

- Method: `GET`
- URL: `/menu/<date>`

```bash
curl -X GET "http://localhost:8080/menu/2025-05-20"
```

### 3) 메뉴 추가

- Method: `POST`
- URL: `/menu`
- Body: `date`, `meals`, `order`

```bash
curl -X POST "http://localhost:8080/menu" \
	-H "Content-Type: application/json" \
	-d '{
		"date": "2025-05-20",
		"meals": {
			"lunch": {
				"rice": ["보리밥", "잡곡밥"],
				"soup": "김국",
				"dishes": ["불고기", "계란찜"],
				"kimchi": "백김치",
				"plus_corner": ["버터"]
			},
			"dinner": {
				"rice": ["쌀밥", "현미밥"],
				"soup": "된장찌개",
				"dishes": ["생선까스", "우동"],
				"kimchi": "깍두기",
				"plus_corner": ["수수팥빙수"]
			}
		},
		"order": ["1조", "3조", "2조"]
	}'
```

### 4) 특정 날짜 메뉴 수정

- Method: `PUT`
- URL: `/menu/<date>`
- Body: `meals`, `order`

```bash
curl -X PUT "http://localhost:8080/menu/2025-05-20" \
	-H "Content-Type: application/json" \
	-d '{
		"meals": {
			"lunch": {
				"rice": ["보리밥", "잡곡밥"],
				"soup": "김국",
				"dishes": ["불고기", "계란찜"],
				"kimchi": "백김치",
				"plus_corner": ["버터"]
			},
			"dinner": {
				"rice": ["쌀밥", "현미밥"],
				"soup": "된장찌개",
				"dishes": ["생선까스", "우동"],
				"kimchi": "깍두기",
				"plus_corner": ["수수팥빙수"]
			}
		},
		"order": ["1조", "3조", "2조"]
	}'
```

### 5) 특정 날짜 메뉴 삭제

- Method: `DELETE`
- URL: `/menu/<date>`

```bash
curl -X DELETE "http://localhost:8080/menu/2025-05-20"
```

## 응답 코드 요약

- `200`: 조회/수정/삭제 성공
- `201`: 등록 성공
- `400`: 요청 형식 오류
- `404`: 대상 날짜 데이터 없음
- `409`: 이미 존재하는 날짜 등록 시도
- `500`: 서버 내부 오류

## 환경 변수

- `DATABASE_PATH`: SQLite 파일 경로
	- 기본값: `/data/menu.db`