from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
import mysql.connector
import uvicorn


from dotenv import load_dotenv
import os

load_dotenv()  # .env 파일에서 환경변수 읽기

DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")



app = FastAPI()

# ✅ CORS 설정
origins = [
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:7860",  # Gradio 기본 포트
    "*"  # 전체 허용 (개발 중에는 OK, 배포 시엔 특정 origin만 허용 권장)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ DB 연결 함수
def get_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )


# ✅ 1. 요약 저장
@app.post("/save-summary")
def save_summary(
    user_id: int = Form(...),
    file_name: str = Form(...),
    summary: str = Form(...),
    tts_audio_url: str = Form(...),
    voice_style: str = Form(...),
    speed: str = Form(...),
    duration: int = Form(...)
):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO study_materials 
        (user_id, file_name, summary, tts_audio_url, voice_style, speed, duration)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (user_id, file_name, summary, tts_audio_url, voice_style, speed, duration)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return {"status": "saved"}

# ✅ 2. 문제 저장
@app.post("/save-question")
def save_question(
    material_id: int = Form(...),
    question_text: str = Form(...),
    choice1: str = Form(...),
    choice2: str = Form(...),
    choice3: str = Form(...),
    choice4: str = Form(...),
    answer: int = Form(...),
    explanation: str = Form(...)
):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO questions 
            (material_id, question_text, choice1, choice2, choice3, choice4, answer, explanation)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (material_id, question_text, choice1, choice2, choice3, choice4, answer, explanation)
        )
        question_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "question saved", "question_id": question_id}
    except Exception as e:
        print("❗문제 저장 오류:", str(e))
        return {"status": "error", "detail": str(e)}

# ✅ 3. 정답 저장
@app.post("/save-answer")
def save_answer(
    user_id: int = Form(...),
    question_id: int = Form(...),
    user_choice: int = Form(...),
    is_correct: bool = Form(...)
):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO user_answers (user_id, question_id, user_choice, is_correct)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, question_id, user_choice, is_correct)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "answer saved"}
    except Exception as e:
        print("❗정답 저장 오류:", str(e))
        return {"status": "error", "detail": str(e)}

# ✅ 4. 오답 저장
@app.post("/save_wrong_answer")
def save_wrong_answer(
    user_id: int = Form(...),
    question_id: int = Form(...),
    user_choice: int = Form(...)
):
    try:
        is_correct = False
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO user_answers (user_id, question_id, user_choice, is_correct)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, question_id, user_choice, is_correct)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "wrong answer saved"}
    except Exception as e:
        print("❗오답 저장 오류:", str(e))
        return {"status": "error", "detail": str(e)}

# ✅ 5. 오답 목록 불러오기
@app.get("/get-wrong-answers")
def get_wrong_answers(user_id: int):
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT q.question_text, q.choice1, q.choice2, q.choice3, q.choice4, 
                   q.answer, q.explanation, ua.user_choice
            FROM user_answers ua
            JOIN questions q ON ua.question_id = q.question_id
            WHERE ua.user_id = %s AND ua.is_correct = FALSE
            """, (user_id,)
        )
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return {"wrong_answers": results}
    except Exception as e:
        print("❗오답 조회 오류:", str(e))
        return {"status": "error", "detail": str(e)}
    




if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)

