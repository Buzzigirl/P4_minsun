import json
import os
import datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from dotenv import load_dotenv
from openai import OpenAI
import time

# --- 환경 변수 로드 및 초기 설정 ---
load_dotenv()
app = Flask(__name__, 
            template_folder='homepage/templates', 
            static_folder='homepage/static') # 템플릿/정적 파일 경로 설정
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default-super-secret-key-for-session')

# BASE_DIR은 프로젝트 최상위 폴더(P4_minsun)를 가리킵니다.
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 

# 로그 및 데이터 폴더 경로 설정
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
COUNTS_DIR = os.path.join(LOGS_DIR, 'scaffolding_counts')
DATA_DIR = os.path.join(BASE_DIR, 'data')
PROMPT_DIR = os.path.join(DATA_DIR, 'prompts')

# 필요한 폴더 생성
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(COUNTS_DIR, exist_ok=True)
os.makedirs(PROMPT_DIR, exist_ok=True)

# OpenAI 클라이언트 초기화
try:
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    MODEL_NAME = "gpt-4o-mini"  # 요청에 따라 gpt-4o-mini 모델 사용
except Exception as e:
    print(f"OpenAI 클라이언트 초기화 오류: {e}")
    client = None
    MODEL_NAME = None

# --- 프롬프트 및 사용자 데이터 로드 함수 ---

def load_prompt_file(filename):
    """지정된 프롬프트 파일을 읽어옵니다."""
    file_path = os.path.join(PROMPT_DIR, filename)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"오류: '{file_path}' 파일을 찾을 수 없습니다. 해당 파일을 꼭 생성해주세요.")
        return f"'{filename}' 파일을 불러오는 데 실패했습니다."

def get_integrated_system_prompt():
    """시스템 프롬프트, 상황, 규칙, 과제를 통합하여 반환합니다."""
    # 각 내용을 파일에서 로드
    system_base = load_prompt_file('system_prompt.md')
    situation = load_prompt_file('situation.md')
    rules = load_prompt_file('rules.md')
    task = load_prompt_file('task.md')
    
    # 통합된 시스템 프롬프트 구성
    return f"""
{system_base}
---
# 📚 현재 문제 상황 및 과제 정보 (Contextual Knowledge)
너는 지금부터 아래에 제시된 문제 상황을 해결하기 위해 사용자와 대화해야 한다. 모든 스캐폴딩과 답변은 반드시 이 배경지식을 기반으로 이루어져야 한다.

## 1. 현재 상황 (Situation)
{situation}

## 2. 관련 규칙 (Rules)
{rules}

## 3. 해결 과제 (Task)
{task}
---
"""

# 통합된 프롬프트는 서버 시작 시 한번만 로드
INTEGRATED_SYSTEM_PROMPT = get_integrated_system_prompt()

# 사용자 데이터 로드
try:
    users_path = os.path.join(DATA_DIR, 'users.json')
    # FIX: 'utf-8-sig' 인코딩을 사용하여 BOM 문제를 해결합니다.
    with open(users_path, 'r', encoding='utf-8-sig') as f:
        AUTHORIZED_USERS = json.load(f)
    print("INFO: users.json 파일 로드 성공.")
except FileNotFoundError:
    print(f"오류: '{users_path}' 파일을 찾을 수 없습니다. users.json을 생성해주세요.")
    AUTHORIZED_USERS = {}
except json.JSONDecodeError as e:
    print(f"오류: users.json 파일 형식이 잘못되었습니다. ({e})")
    AUTHORIZED_USERS = {}


# --- 로그 및 카운트 관리 함수 ---

def log_conversation_entry(log_file_path, speaker, text, scaffolding_type=None):
    """대화 항목을 TXT 로그 파일에 추가합니다."""
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if speaker == 'User':
        log_entry = f"[{now_str}] 사용자: {text}\n\n"
    else: # AI
        # 로그에는 라벨을 포함하되, 채팅창에는 보이지 않음
        label = f" ({scaffolding_type})" if scaffolding_type else ""
        log_entry = f"[{now_str}] AI{label}: {text}\n"
        log_entry += f"----------------------------------------\n\n"
        
    with open(log_file_path, 'a', encoding='utf-8') as f:
        f.write(log_entry)

def update_scaffolding_count(count_file_path, s_type):
    """스캐폴딩 유형별 횟수를 카운트하여 저장합니다."""
    
    # 분류 실패 또는 유효하지 않은 유형일 경우 "분류실패"로 기록 (로그에만)
    if not s_type in ["개념적 스캐폴딩", "전략적 스캐폴딩", "메타인지적 스캐폴딩", "동기적 스캐폴딩", "일반"]:
        s_type = "분류실패"
        
    if os.path.exists(count_file_path):
        with open(count_file_path, 'r', encoding='utf-8') as f:
            counts = json.load(f)
    else:
        # 초기화 시 '분류실패'도 포함하여 모든 유형을 초기화
        counts = {"개념적 스캐폴딩": 0, "전략적 스캐폴딩": 0, "메타인지적 스캐폴딩": 0, "동기적 스캐폴딩": 0, "일반": 0, "분류실패": 0}

    counts[s_type] = counts.get(s_type, 0) + 1
    
    with open(count_file_path, 'w', encoding='utf-8') as f:
        json.dump(counts, f, ensure_ascii=False, indent=4)


# --- Flask 라우팅 ---

@app.route('/', methods=['GET', 'POST'])
def login():
    """로그인 (학번/이름)"""
    if request.method == 'POST':
        # 사용자가 입력한 학번과 이름을 받아옵니다. (공백 제거)
        student_id = request.form['student_id'].strip()
        name = request.form['name'].strip()
        
        # users.json에서 해당 학번에 기대되는 이름을 조회합니다.
        expected_name = AUTHORIZED_USERS.get(student_id)

        # 디버그 로그 출력 (파이썬 콘솔에서 확인 가능)
        print("-------------------- 로그인 시도 --------------------")
        print(f"DEBUG: 폼 입력 학번 (ID): '{student_id}' (타입: {type(student_id)})")
        print(f"DEBUG: 폼 입력 성명 (Name): '{name}' (타입: {type(name)})")
        print(f"DEBUG: JSON 기대 성명 (Expected): '{expected_name}' (타입: {type(expected_name)})")
        print("--------------------------------------------------")
        
        # 인증 확인
        if expected_name is not None and expected_name == name:
            session.clear() # 기존 세션 초기화
            session['user'] = {'name': name, 'student_id': student_id}
            
            # 사용자별 로그 폴더 및 파일 경로 설정
            user_log_dir = os.path.join(LOGS_DIR, name)
            os.makedirs(user_log_dir, exist_ok=True)

            now = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')
            
            # 대화 로그 파일 경로 (이름 폴더 내에 저장)
            log_filename = os.path.join(name, f"{now}_{student_id}.txt")
            session['log_filename'] = log_filename
            
            # 스캐폴딩 카운트 파일 경로 (scaffolding_counts 폴더에 저장)
            count_filename = f"{student_id}_{name}.json"
            session['count_filename'] = count_filename
            
            # --- 세션 크기 최적화 FIX: 시스템 프롬프트는 제외하고 빈 대화 목록만 저장 ---
            session['conversation'] = [] 
            # --------------------------------------------------------------------------
            
            return redirect(url_for('consent'))
        else:
            # 실패 사유를 디버깅했습니다.
            error = "등록되지 않은 사용자입니다. 학번과 이름을 정확히 확인해주세요."
            return render_template('login.html', error=error)
            
    return render_template('login.html')

@app.route('/consent', methods=['GET', 'POST'])
def consent():
    """연구 참여 동의서 페이지"""
    if 'user' not in session:
        return redirect(url_for('login'))
        
    log_path = os.path.join(LOGS_DIR, session.get('log_filename', 'temp.txt'))
    
    if request.method == 'POST':
        consent_status = request.form.get('consent_check')
        
        if consent_status == 'agree':
            log_conversation_entry(log_path, 'System', f"연구 참여 동의: {session['user']['name']} ({session['user']['student_id']}) 동의함")
            return redirect(url_for('chat'))
        else:
            log_conversation_entry(log_path, 'System', f"연구 참여 동의: {session['user']['name']} ({session['user']['student_id']}) 비동의함. 접속 종료.")
            session.clear()
            return render_template('consent.html', error="비동의하셨습니다. 실험에 참여할 수 없습니다. 창을 닫아주세요.")
            
    return render_template('consent.html')

@app.route('/chat')
def chat():
    """메인 채팅 페이지"""
    if 'user' not in session:
        return redirect(url_for('login'))
    
    # 채팅창 왼쪽에 표시할 내용 로드
    situation = load_prompt_file('situation.md')
    rules = load_prompt_file('rules.md')
    task = load_prompt_file('task.md')
    
    user_name = session['user']['name']
    
    # --- 첫 접속 시 AI의 초기 인사말 처리 로직 변경 ---
    conversation = session.get('conversation', []) # 세션이 비어있을 경우를 대비
    if not conversation: # 대화 목록이 비어있다면 = 초기 접속
        initial_greeting = f"안녕, {user_name}야! 나는 오늘 너와 함께 과제를 해결할 동료 학습자 AI야. 교내 쓰레기 처리 문제를 해결할 수 있는 학습 활동 설계를 지금부터 함께 시작해 보자! 어떻게 시작하면 좋을까?"
        # 초기 인사말을 세션에 추가
        conversation.append({"role": "assistant", "content": initial_greeting})
        session['conversation'] = conversation
        
        log_path = os.path.join(LOGS_DIR, session.get('log_filename', 'temp.txt'))
        # 초기 인사말은 '일반' 스캐폴딩 유형으로 로그에 기록
        log_conversation_entry(log_path, 'AI', initial_greeting, scaffolding_type="일반")
    # -----------------------------------------------
    
    # 이전 대화 내용을 템플릿에 전달하여 로드
    chat_history = conversation # 이제 시스템 프롬프트가 없으므로 전체를 전달
    
    return render_template('chat.html', 
                           user_name=user_name, 
                           situation=situation, 
                           rules=rules, 
                           task=task,
                           chat_history=chat_history)


@app.route('/get_response', methods=['POST'])
def get_response():
    """AI 답변 요청 및 로그 저장"""
    if 'user' not in session or not client:
        return jsonify({'error': '세션 오류 또는 AI 클라이언트 초기화 실패'}), 401

    user_message = request.json['message']
    conversation = session.get('conversation', [])
    log_path = os.path.join(LOGS_DIR, session.get('log_filename', 'temp.txt'))
    count_path = os.path.join(COUNTS_DIR, session.get('count_filename', 'temp.json'))

    # 1. 사용자 메시지 추가 및 로그 저장
    conversation.append({"role": "user", "content": user_message})
    log_conversation_entry(log_path, 'User', user_message)

    try:
        # --- API 호출 시 시스템 프롬프트를 대화 이력에 추가 ---
        # 실제 API 호출을 위해 시스템 프롬프트와 현재 대화 이력을 합칩니다.
        messages_for_api = [
            {"role": "system", "content": INTEGRATED_SYSTEM_PROMPT}
        ] + conversation
        # ----------------------------------------------------
        
        # GPT-4o-mini 모델 사용 및 JSON 형식 강제
        chat_completion = client.chat.completions.create(
            model=MODEL_NAME, # gpt-4o-mini
            messages=messages_for_api, # 통합된 메시지 사용
            response_format={"type": "json_object"}
        )
        ai_response_json_str = chat_completion.choices[0].message.content
        
        # 2. AI의 JSON 응답 파싱
        try:
            ai_response_data = json.loads(ai_response_json_str)
            
            # 스캐폴딩 유형 추출 및 검증
            scaffolding_type = ai_response_data.get("scaffolding_type", "분류실패")
            valid_types = ["개념적 스캐폴딩", "전략적 스캐폴딩", "메타인지적 스캐폴딩", "동기적 스캐폴딩", "일반"]
            if not scaffolding_type in valid_types:
                 scaffolding_type = "분류실패"
                 
            response_text = ai_response_data.get("response_text", "AI 응답 생성에 실패했습니다.")
            
        except json.JSONDecodeError:
            scaffolding_type = "JSON 파싱 실패"
            response_text = "AI 응답 형식에 오류가 발생했어. 잠시 후 다시 시도해 봐. (원본 응답: " + ai_response_json_str[:50] + "...)"
            
        # 3. AI 응답을 세션에 저장 및 로그에 기록 (라벨 포함)
        conversation.append({"role": "assistant", "content": response_text})
        session['conversation'] = conversation
        
        # 로그 파일에 (스캐폴딩 유형) 라벨 포함하여 저장
        log_conversation_entry(log_path, 'AI', response_text, scaffolding_type)
        
        # 4. 스캐폴딩 횟수 카운트 업데이트
        update_scaffolding_count(count_path, scaffolding_type)
        
        # 5. 채팅창에는 순수 텍스트만 전송
        return jsonify({'response': response_text})

    except Exception as e:
        print(f"OpenAI API 호출 오류: {e}")
        # 오류 발생 시 로그에 기록
        log_conversation_entry(log_path, 'System_Error', f"API 호출 오류 발생: {e}")
        return jsonify({'error': 'AI 응답을 가져오는 데 실패했습니다. API 키 또는 네트워크 상태를 확인하세요.'}), 500

if __name__ == "__main__":
    # 서버 구동 전, 콘솔 출력 내용
    print("======================================================")
    print("✅ 서버 준비 완료.")
    print("------------------------------------------------------")
    print("🚀 서버 시작 (Ctrl+C로 종료)")
    print("   접속 주소 (로컬): http://127.0.0.1:5000")
    print("======================================================")
    
    # Flask 서버 실행
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
