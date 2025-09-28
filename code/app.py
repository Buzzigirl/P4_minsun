import json
import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from openai import OpenAI
from datetime import datetime
from waitress import serve

load_dotenv()
app = Flask(__name__)
app.secret_key = 'super-secret-key'
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LOGS_DIR = os.path.join(BASE_DIR, '..', 'logs')
#COUNTS_DIR = os.path.join(BASE_DIR, '..', 'scaffolding_counts') # 기존 코드
COUNTS_DIR = os.path.join(LOGS_DIR, 'scaffolding_counts') # 이렇게 변경
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(COUNTS_DIR, exist_ok=True)
# ------------------------------------

# (load_prompt_file, 프롬프트 로드, 사용자 로드 로직은 이전과 동일)
def load_prompt_file(filename):
    file_path = os.path.join(BASE_DIR, '..', 'data', 'prompts', filename)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"오류: '{file_path}' 파일을 찾을 수 없습니다.")
        return f"{filename} 파일을 불러오는 데 실패했습니다."

SYSTEM_PROMPT_BASE = load_prompt_file('system_prompt.md')
SITUATION_TEXT = load_prompt_file('situation.md')
RULES_TEXT = load_prompt_file('rules.md')
TASK_TEXT = load_prompt_file('task.md')

INTEGRATED_SYSTEM_PROMPT = f"""
{SYSTEM_PROMPT_BASE}
---
# [과제 배경지식]
너는 지금부터 아래에 제시된 문제 상황을 해결하기 위해 사용자와 대화해야 한다. 모든 스캐폴딩과 답변은 반드시 이 배경지식을 기반으로 이루어져야 한다.
## 1. 현재 상황
{SITUATION_TEXT}
## 2. 관련 규칙
{RULES_TEXT}
## 3. 해결 과제
{TASK_TEXT}
---
"""
try:
    users_path = os.path.join(BASE_DIR, '..', 'data', 'users.json')
    with open(users_path, 'r', encoding='utf-8') as f:
        AUTHORIZED_USERS = json.load(f)
except FileNotFoundError:
    print(f"오류: '{users_path}' 파일을 찾을 수 없습니다.")
    AUTHORIZED_USERS = {}

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        student_id = request.form['student_id']
        name = request.form['name']
        if AUTHORIZED_USERS.get(student_id) == name:
            session.clear() 
            session['user'] = {'name': name, 'student_id': student_id}
            
            # --- [2] 이 부분이 바뀌었습니다! ---
            # 사용자별 로그 폴더 생성
            user_log_dir = os.path.join(LOGS_DIR, name)
            os.makedirs(user_log_dir, exist_ok=True)

            now = datetime.now().strftime('%Y-%m-%d_%H%M%S')
            # 로그 파일 경로를 '이름/파일명' 형태로 저장
            log_filename = os.path.join(name, f"{now}_{student_id}.txt")
            session['log_filename'] = log_filename

            # 스캐폴딩 카운트 파일명 저장 (이름과 학번으로)
            count_filename = f"{student_id}_{name}.json"
            session['count_filename'] = count_filename
            # ------------------------------------
            
            return redirect(url_for('consent'))
        else:
            error = "등록되지 않은 사용자입니다. 학번과 이름을 확인해주세요."
            return render_template('login.html', error=error)
    return render_template('login.html')

# (@app.route('/consent')와 @app.route('/chat')은 이전과 동일)
@app.route('/consent', methods=['GET', 'POST'])
def consent():
    if 'user' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        if 'agree' in request.form:
            return redirect(url_for('chat'))
    return render_template('consent.html')

@app.route('/chat')
def chat():
    if 'user' not in session:
        return redirect(url_for('login'))
    user_name = session['user']['name']
    return render_template('chat.html', user_name=user_name, situation=SITUATION_TEXT, rules=RULES_TEXT, task=TASK_TEXT)


# --- [3] 이 부분이 바뀌었습니다! (get_response 함수 대폭 수정) ---
@app.route('/get_response', methods=['POST'])
def get_response():
    conversation = session.get('conversation', [
        {"role": "system", "content": INTEGRATED_SYSTEM_PROMPT}
    ])
    
    user_message = request.json['message']
    conversation.append({"role": "user", "content": user_message})

    try:
        chat_completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=conversation,
            response_format={"type": "json_object"} # JSON 형식으로 응답하도록 강제
        )
        ai_response_json_str = chat_completion.choices[0].message.content
        
        # AI의 JSON 응답 파싱
        try:
            ai_response_data = json.loads(ai_response_json_str)
            scaffolding_type = ai_response_data.get("scaffolding_type", "분류실패")
            response_text = ai_response_data.get("response_text", "AI 응답 생성에 실패했습니다.")
        except json.JSONDecodeError:
            # AI가 유효한 JSON을 생성하지 못한 경우의 예외 처리
            scaffolding_type = "JSON 파싱 실패"
            response_text = ai_response_json_str # AI가 보낸 텍스트를 그대로 보여줌

        conversation.append({"role": "assistant", "content": response_text})
        session['conversation'] = conversation
        
        # --- 1. 대화 로그 저장 (라벨 포함) ---
        if 'log_filename' in session:
            log_file_path = os.path.join(LOGS_DIR, session['log_filename'])
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open(log_file_path, 'a', encoding='utf-8') as f:
                log_entry = (
                    f"[{now_str}] 사용자: {user_message}\n\n"
                    f"[{now_str}] AI ({scaffolding_type}): {response_text}\n" # 라벨 추가
                    f"----------------------------------------\n\n"
                )
                f.write(log_entry)

        # --- 2. 스캐폴딩 횟수 카운트 ---
        if 'count_filename' in session and scaffolding_type in ["개념적", "전략적", "메타인지적", "동기적", "일반"]:
            count_file_path = os.path.join(COUNTS_DIR, session['count_filename'])
            
            # 기존 카운트 파일 읽기 (없으면 초기화)
            if os.path.exists(count_file_path):
                with open(count_file_path, 'r', encoding='utf-8') as f:
                    counts = json.load(f)
            else:
                counts = {"개념적": 0, "전략적": 0, "메타인지적": 0, "동기적": 0, "일반": 0}

            # 현재 스캐폴딩 유형 횟수 1 증가
            counts[scaffolding_type] = counts.get(scaffolding_type, 0) + 1
            
            # 파일에 다시 저장
            with open(count_file_path, 'w', encoding='utf-8') as f:
                json.dump(counts, f, ensure_ascii=False, indent=4)
        
        # 채팅창에는 순수 텍스트만 전송
        return jsonify({'response': response_text})

    except Exception as e:
        print(f"OpenAI API 호출 오류: {e}")
        return jsonify({'error': 'AI 응답을 가져오는 데 실패했습니다.'}), 500
# ... (모든 라우트, 함수, 설정 코드) ...
# --------------------------------------------------------------------

if __name__ == "__main__":
    # Railway 환경변수 PORT를 사용하고, 로컬 실행 시에는 5000 포트를 사용
    port = int(os.environ.get("PORT", 5000))
    # Flask 기본 서버를 0.0.0.0 호스트로 실행
    app.run(host="0.0.0.0", port=port)
