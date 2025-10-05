# config_utils.py

import os
import json
from openai import OpenAI
import datetime

# --- 환경 변수 로드 및 초기 설정 ---
LOGS_DIR = '/tmp/logs' 
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 
DATA_DIR = os.path.join(BASE_DIR, 'data')
PROMPT_DIR = os.path.join(DATA_DIR, 'prompts')

os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(PROMPT_DIR, exist_ok=True)

# --- OpenAI 클라이언트 초기화 ---
STUDENT_KEY_NAMES = [f'OPENAI_KEY_{i}' for i in range(1, 28)] 
API_CLIENTS = {}
LAST_RESORT_CLIENT = None
MODEL_NAME = "gpt-4o" 

try:
    for i, key_name in enumerate(STUDENT_KEY_NAMES):
        api_key = os.getenv(key_name)
        if api_key:
            API_CLIENTS[i + 1] = OpenAI(api_key=api_key) 
        else:
            print(f"🚨 WARNING: {key_name} 환경 변수가 누락되었습니다. {i+1}번 학생에게 키가 할당되지 않습니다.")

    last_key_name = STUDENT_KEY_NAMES[-1] 
    last_api_key = os.getenv(last_key_name)
    
    if last_api_key:
        LAST_RESORT_CLIENT = API_CLIENTS.get(27, OpenAI(api_key=last_api_key)) 
        
    print(f"✅ INFO: 총 {len(API_CLIENTS)}개의 학생 API 클라이언트와 관리자용 클라이언트가 준비되었습니다.")

except Exception as e:
    print(f"🚨 ERROR: OpenAI 클라이언트 초기화 오류: {e}")

# 🚨 학번에 따라 클라이언트를 반환하는 함수 (app.py에서 사용)
def get_client_by_user(student_id):
    """학번의 순서(인덱스)를 기반으로 고유한 API 클라이언트를 반환합니다."""
    
    try:
        user_list = list(AUTHORIZED_USERS.keys())
        user_index = user_list.index(student_id)
    except ValueError:
        print(f"DEBUG: Unknown Student ID {student_id}. Assigning Last Resort Client.")
        return LAST_RESORT_CLIENT
        
    if user_index >= 26: 
        client_key_number = 27
    else:
        client_key_number = user_index + 1
        
    client_to_use = API_CLIENTS.get(client_key_number)

    return client_to_use if client_to_use else LAST_RESORT_CLIENT
# ----------------------------------------------------


# --- 프롬프트 및 사용자 데이터 로드 함수 ---

def load_prompt_file(filename):
    """지정된 프롬프트 파일을 읽어옵니다. 파일이 없을 경우 빈 문자열을 반환합니다."""
    file_path = os.path.join(PROMPT_DIR, filename)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        # 🚩 수정: 파일 로드 실패 시 오류 문자열 대신 빈 문자열 반환 (시스템 프롬프트 안정화)
        print(f"🚨 오류: '{file_path}' 파일을 찾을 수 없습니다.")
        return ""
    
# 🚩 RAG 데이터 경로 (JSON 파일 로드가 성공했다는 전제하에 유지)
EDUTECH_TOOLS_PATH = os.path.join(PROMPT_DIR, 'ai_edutech_tools.json')
WEBSITES_PATH = os.path.join(PROMPT_DIR, 'edutech_websites.json')

# 🚩 서버 시작 시 데이터를 메모리에 로드 (JSON 로드 실패 시에도 빈 리스트로 초기화)
try:
    with open(EDUTECH_TOOLS_PATH, 'r', encoding='utf-8') as f:
        EDUTECH_TOOLS_DATA = json.load(f)
    print("INFO: Edutech tools data loaded successfully.")
except Exception as e:
    print(f"🚨 ERROR: Edutech tools data loading failed: {e}")
    EDUTECH_TOOLS_DATA = []

try:
    with open(WEBSITES_PATH, 'r', encoding='utf-8') as f:
        EDUTECH_WEBSITES_DATA = json.load(f)
    print("INFO: Edutech websites data loaded successfully.")
except Exception as e:
    print(f"🚨 ERROR: Edutech websites data loading failed: {e}")
    EDUTECH_WEBSITES_DATA = []

def get_integrated_system_prompt():
    """시스템 프롬프트, 상황, 규칙, 과제를 통합하여 반환합니다."""
    system_base = load_prompt_file('system_prompt.md')
    situation = load_prompt_file('situation.md')
    rules = load_prompt_file('rules.md')
    task = load_prompt_file('task.md')
    learner_model_data = load_prompt_file('learner_model.md') 
    
    # 🚩 RAG 데이터를 MD 파일로 로드 (시스템 프롬프트에 직접 포함하여 안정화)
    edutech_tools = load_prompt_file('ai_edutech_tools.md')
    edutech_sites = load_prompt_file('edutech_websites.md')
    
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
# 🧠 동료 AI의 핵심 자료 (Knowledge Base for Rule Compliance)

## 학습 모델 자료
학습자 중심 학습 모델에 대한 질문을 받을 경우, 반드시 아래 자료에 기반하여 답변해야 한다.
{learner_model_data}

## 에듀테크 도구 및 사이트 자료
학습자가 에듀테크 도구(질문 유형 2)나 참고 사이트(질문 유형 3)에 대해 물어볼 경우, 반드시 아래 자료를 **참조하여 답변**해야 한다.

### 2. 에듀테크 도구 목록
{edutech_tools}

### 3. 참고 웹사이트 목록
{edutech_sites}
---
"""

INTEGRATED_SYSTEM_PROMPT = get_integrated_system_prompt()

# 사용자 데이터 로드 (유지)
try:
    users_path = os.path.join(DATA_DIR, 'users.json')
    with open(users_path, 'r', encoding='utf-8-sig') as f:
        AUTHORIZED_USERS = json.load(f)
    print("INFO: users.json 파일 로드 성공.")
except FileNotFoundError:
    print(f"🚨 오류: '{users_path}' 파일을 찾을 수 없습니다. users.json을 생성해주세요.")
    AUTHORIZED_USERS = {}
except json.JSONDecodeError as e:
    print(f"🚨 오류: users.json 파일 형식이 잘못되었습니다. ({e})")
    AUTHORIZED_USERS = {}


# config_utils.py 내 log_conversation_entry 함수 확인
def log_conversation_entry(speaker, text, log_filename, scaffolding_type=None):
    """대화 항목을 TXT 로그 파일에 추가합니다. (portalocker 제거)"""
    log_file_path = os.path.join(LOGS_DIR, log_filename)
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if speaker == 'User':
        log_entry = f"[{now_str}] 사용자: {text}\n\n"
    else: # AI
        label = f" ({scaffolding_type})" if scaffolding_type else ""
        log_entry = f"[{now_str}] AI{label}: {text}\n"
        log_entry += f"----------------------------------------\n\n"
        
    log_dir = os.path.dirname(log_file_path)
    
    print(f"DEBUG: Attempting to write log to: {log_file_path}")
    
    try:
        # 🚩 수정: portalocker 없이 표준 os.makedirs와 with open('a') 사용
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True) 
            
        # 'a' (append) 모드로 열어 기존 내용을 덮어쓰지 않고 추가만 합니다.
        with open(log_file_path, 'a', encoding='utf-8') as f:
            f.write(log_entry)
            
    except Exception as e:
        print(f"🚨🚨 CRITICAL LOG WRITE FAIL: 로그 파일 저장 실패: {log_file_path} ({e})")


def update_scaffolding_count(count_filename, user_log_dir, s_type): 
    """스캐폴딩 유형별 횟수를 카운트하여 사용자 로그 폴더에 저장합니다. (portalocker 제거)"""
    
    count_file_path = os.path.join(user_log_dir, count_filename) 
    
    valid_types = ["개념적 스캐폴딩", "전략적 스캐폴딩", "메타인지적 스캐폴딩", "동기적 스캐폴딩", "일반"]
    if s_type not in valid_types:
        s_type = "분류실패"
        
    try:
        if not os.path.exists(user_log_dir):
            os.makedirs(user_log_dir, exist_ok=True)
            
        if os.path.exists(count_file_path):
            # 🚩 수정: portalocker 제거 후 표준 파일 읽기/쓰기 로직 복구
            with open(count_file_path, 'r', encoding='utf-8') as f:
                counts = json.load(f)
        else:
            counts = {t: 0 for t in valid_types + ["분류실패"]}

        counts[s_type] = counts.get(s_type, 0) + 1
        
        # 🚩 수정: 덮어쓰기 모드 'w' 사용
        with open(count_file_path, 'w', encoding='utf-8') as f:
            json.dump(counts, f, ensure_ascii=False, indent=4)
            
    except Exception as e:
        print(f"🚨🚨 CRITICAL COUNT WRITE FAIL: 카운트 파일 저장 실패: {count_file_path} ({e})")

# ----------------------------------------------------
# 🚩 Tool 함수 정의 (Tool-Calling 제거됨)
# ----------------------------------------------------
# (이전 Tool 함수 정의는 삭제되었습니다.)

def format_scaffolding_counts(count_filename, user_log_dir):
    """스캐폴딩 카운트 JSON 파일을 읽어 텍스트 형식으로 포맷합니다."""
    count_file_path = os.path.join(user_log_dir, count_filename) 
    
    try:
        if not os.path.exists(count_file_path):
            return "\n\n--- 스캐폴딩 카운트 정보 --- \n카운트 파일을 찾을 수 없습니다."

        with open(count_file_path, 'r', encoding='utf-8') as f:
            counts = json.load(f)
            
        formatted_text = "\n\n==================================================\n"
        formatted_text += "--- 📊 AI 스캐폴딩 유형별 최종 카운트 결과 ---\n"
        formatted_text += "==================================================\n"
        
        sorted_counts = sorted(counts.items(), key=lambda item: item[1], reverse=True)
        
        for s_type, count in sorted_counts:
            formatted_text += f"- {s_type}: {count}회\n"
            
        formatted_text += "==================================================\n\n"
        return formatted_text
        
    except Exception as e:
        return f"\n\n--- 스캐폴딩 카운트 정보 --- \n카운트 파일 로드 또는 포맷 중 오류 발생: {e}"