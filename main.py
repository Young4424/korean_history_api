from fastapi import FastAPI, Form, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import mysql.connector
import uvicorn
import os
import shutil
from datetime import datetime
from typing import Optional


from dotenv import load_dotenv
import os

load_dotenv()  # .env 파일에서 환경변수 읽지 않게 하기

DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

# 이미지 저장 경로 설정
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
IMAGE_DIR = os.path.join(UPLOAD_DIR, "images")
AUDIO_SAVE_DIR = "./static/audio"


# 디렉토리가 없으면 생성
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(AUDIO_SAVE_DIR, exist_ok=True)

app = FastAPI()

# ✅ CORS 설정
origins = [
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:7860",  # Gradio 기본 포트
    "*"  # 전체 허용 (개발 중에는 OK, 배포 시엔 특정 origin만 허용 권장)

]


# ✅ 정적 파일 서빙 (오디오)
app.mount("/static/audio", StaticFiles(directory=AUDIO_SAVE_DIR), name="audio")

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
    
@app.get("/get-next-wrong-question")
def get_next_wrong_question(user_id: int):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT q.question_id, q.question_text, q.choice1, q.choice2, q.choice3, q.choice4, q.answer
        FROM user_answers ua
        JOIN questions q ON ua.question_id = q.question_id
        WHERE ua.user_id = %s AND ua.is_correct = FALSE
        ORDER BY ua.answer_id DESC
        LIMIT 1
    """, (user_id,))
    question = cursor.fetchone()
    cursor.close()
    conn.close()

    if question:
        return {"question": question}
    else:
        return {"message": "더 이상 오답이 없습니다."}
    
# ✅ study_materials 테이블 확장용 API (추가)
@app.post("/alter-study-materials-table")
def alter_study_materials_table():
    """study_materials 테이블에 필기노트 분석에 필요한 필드를 추가합니다."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # 컬럼 존재 여부 확인 후 추가
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'study_materials' AND COLUMN_NAME = 'analysis_type'
        """)
        exists = cursor.fetchone()[0]
        
        if not exists:
            cursor.execute("""
                ALTER TABLE study_materials
                ADD COLUMN analysis_type VARCHAR(50) DEFAULT 'summary' COMMENT '분석 유형 (summary, note_analysis)',
                ADD COLUMN ocr_text TEXT DEFAULT NULL COMMENT 'OCR을 통해 추출된 원본 텍스트',
                ADD COLUMN length_option VARCHAR(50) DEFAULT NULL COMMENT '요약 길이 옵션'
            """)
            cursor.execute("""
                CREATE INDEX idx_study_materials_analysis_type ON study_materials(analysis_type)
            """)
            
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "success", "message": "테이블이 확장되었습니다."}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

# ✅ 필기노트 분석 결과 저장 API
@app.post("/save-note-analysis")
def save_note_analysis(
    user_id: int = Form(...),
    file_name: str = Form(...),
    ocr_text: str = Form(...),
    summary: str = Form(...),
    tts_audio_url: str = Form(...),
    voice_style: str = Form(...),
    speed: str = Form(...),
    duration: int = Form(...),
    length_option: str = Form(...)
):
    """필기노트 분석 결과를 study_materials 테이블에 저장합니다."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO study_materials 
            (user_id, file_name, summary, tts_audio_url, voice_style, speed, duration, 
             analysis_type, ocr_text, length_option)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, file_name, summary, tts_audio_url, voice_style, speed, duration, 
             'note_analysis', ocr_text, length_option)
        )
        material_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "success", "material_id": material_id}
    except Exception as e:
        print("❗필기노트 분석 저장 오류:", str(e))
        return {"status": "error", "detail": str(e)}

# ✅ 필기노트 분석 결과 불러오기 API
@app.get("/get-note-analysis")
def get_note_analysis(user_id: int, limit: int = 5):
    """특정 사용자의 필기노트 분석 결과 목록을 가져옵니다."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT material_id, file_name, summary, tts_audio_url, voice_style, 
                   speed, duration, ocr_text, uploaded_at
            FROM study_materials
            WHERE user_id = %s AND analysis_type = 'note_analysis'
            ORDER BY uploaded_at DESC
            LIMIT %s
            """,
            (user_id, limit)
        )
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return {"analysis_results": results}
    except Exception as e:
        print("❗필기노트 분석 결과 조회 오류:", str(e))
        return {"status": "error", "detail": str(e)}

# ✅ 특정 분석 결과 상세 조회 API
@app.get("/get-note-analysis-detail/{material_id}")
def get_note_analysis_detail(material_id: int):
    """특정 필기노트 분석 결과의 상세 정보를 가져옵니다."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT * FROM study_materials
            WHERE material_id = %s AND analysis_type = 'note_analysis'
            """,
            (material_id,)
        )
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            return {"analysis_detail": result}
        else:
            return {"status": "error", "detail": "분석 결과를 찾을 수 없습니다."}
    except Exception as e:
        print(f"❗분석 결과 상세 조회 오류 (ID: {material_id}):", str(e))
        return {"status": "error", "detail": str(e)}

# ✅ 필기노트 분석 결과 삭제 API
@app.delete("/delete-note-analysis/{material_id}")
def delete_note_analysis(material_id: int):
    """특정 필기노트 분석 결과를 삭제합니다."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            DELETE FROM study_materials
            WHERE material_id = %s AND analysis_type = 'note_analysis'
            """,
            (material_id,)
        )
        deleted = cursor.rowcount > 0
        conn.commit()
        cursor.close()
        conn.close()
        
        if deleted:
            return {"status": "success", "message": "분석 결과가 삭제되었습니다."}
        else:
            return {"status": "error", "detail": "삭제할 분석 결과를 찾을 수 없습니다."}
    except Exception as e:
        print(f"❗분석 결과 삭제 오류 (ID: {material_id}):", str(e))
        return {"status": "error", "detail": str(e)}

# 새로 추가: 필기 이미지 업로드 API
@app.post("/upload-note-image")
async def upload_note_image(file: UploadFile = File(...), user_id: int = Form(...)):
    """
    필기 이미지를 서버에 저장하고 파일 경로를 반환합니다.
    """
    try:
        # 고유한 파일명 생성 (중복 방지)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{user_id}_{timestamp}{file_extension}"
        file_path = os.path.join(IMAGE_DIR, unique_filename)
        
        # 파일 저장
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 상대 경로 (DB에 저장할 경로)
        relative_path = os.path.join("images", unique_filename)
        
        return {
            "status": "success",
            "file_name": file.filename,
            "saved_path": relative_path,
            "full_path": file_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"이미지 업로드 실패: {str(e)}")

# 새로 추가: 필기노트 OCR 결과 저장 API
@app.post("/save-note-ocr")
async def save_note_ocr(
    user_id: int = Form(...),
    file_name: str = Form(...),
    image_path: str = Form(...),
    ocr_text: str = Form(...)
):
    """
    필기노트 OCR 결과만 임시로 저장합니다.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO study_materials 
            (user_id, file_name, ocr_text, analysis_type)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, file_name, ocr_text, "ocr_only")
        )
        material_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "success", "material_id": material_id, "ocr_text": ocr_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR 결과 저장 실패: {str(e)}")

# 새로 추가: OCR과 요약 결과를 함께 저장하는 API
# ✅ 최종 분석 결과 저장 API
@app.post("/save-note-analysis-complete")
async def save_note_analysis_complete(
    user_id: int = Form(...),
    file_name: str = Form(...),
    image_path: str = Form(...),
    ocr_text: str = Form(...),
    summary: str = Form(...),
    tts_audio_url: str = Form(None),
    voice_style: str = Form(...),
    speed: str = Form(...),
    duration: int = Form(...),
    length_option: str = Form(...)
):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        audio_url = tts_audio_url if tts_audio_url else ""

        cursor.execute(
            """
            INSERT INTO study_materials 
            (user_id, file_name, summary, tts_audio_url, voice_style, speed, duration, 
             analysis_type, ocr_text, length_option)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, file_name, summary, audio_url, voice_style, speed, duration,
             'note_analysis', ocr_text, length_option)
        )
        material_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()
        return {
            "status": "success",
            "material_id": material_id,
            "message": "분석 결과가 저장되었습니다."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"분석 결과 저장 실패: {str(e)}")

# ✅ TTS 음성 업로드 API
@app.post("/upload-tts-audio")
async def upload_tts_audio(file: UploadFile = File(...)):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{file.filename}"
        save_path = os.path.join(AUDIO_SAVE_DIR, filename)

        with open(save_path, "wb") as f:
            content = await file.read()
            f.write(content)

        base_url = "https://korean-history-api-g7auebfdhhd6fpb5.koreacentral-01.azurewebsites.net"
        audio_url = f"{base_url}/static/audio/{filename}"

        return {"status": "success", "audio_url": audio_url, "filename": filename}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})





# if __name__ == "__main__":
#     uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)