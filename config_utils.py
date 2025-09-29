# config_utils.py

import os
import json
from openai import OpenAI
import datetime

# --- 환경 변수 로드 및 초기 설정 ---

# 🚨 수정: 로그 경로를 OS의 임시 디렉토리(/tmp)로 변경하여 Railway 쓰기 권한 확보
# 이 경로는 서버 재시작 시 초기화됩니다.
LOGS_DIR = '/tmp/logs' 
# -----------------------------------------------------------------

# BASE_DIR은 프로젝트 최상위 폴더를 가리킵니다.
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 

# DATA 및 PROMPT 경로는 BASE_DIR 기준으로 유지
DATA_DIR = os.path.join(BASE_DIR, 'data')
PROMPT_DIR = os.path.join(DATA_DIR, 'prompts')

# 필요한 폴더 생성 (서버 시작 시 한 번)
# LOGS_DIR이 /tmp/logs로 변경되었으므로, 해당 폴더가 생성됩니다.
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(PROMPT_DIR, exist_ok=True)

# --- OpenAI 클라이언트 초기화 ---
client = None
MODEL_NAME = "gpt-4o-mini" 

try:
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        print("🚨 ERROR: OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
    else:
        client = OpenAI(api_key=openai_api_key)
        print("✅ INFO: OpenAI 클라이언트 초기화 성공.")
except Exception as e:
    print(f"🚨 ERROR: OpenAI 클라이언트 초기화 오류: {e}")

# --- 프롬프트 및 사용자 데이터 로드 함수 ---

def load_prompt_file(filename):
    """지정된 프롬프트 파일을 읽어옵니다."""
    file_path = os.path.join(PROMPT_DIR, filename)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"🚨 오류: '{file_path}' 파일을 찾을 수 없습니다.")
        return f"'{filename}' 파일을 불러오는 데 실패했습니다."
    
# 🚩 RAG 데이터 경로
EDUTECH_TOOLS_PATH = os.path.join(PROMPT_DIR, 'ai_edutech_tools.json')
WEBSITES_PATH = os.path.join(PROMPT_DIR, 'edutech_websites.json')

# 🚩 서버 시작 시 데이터를 메모리에 로드
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
    # 각 내용을 파일에서 로드
    system_base = load_prompt_file('system_prompt.md')
    situation = load_prompt_file('situation.md')
    rules = load_prompt_file('rules.md')
    task = load_prompt_file('task.md')
    learner_model_data = load_prompt_file('learner_model.md') 
    
    # 🚩 RAG 데이터를 MD 파일로 로드 (2번, 3번 질문 유형 자료)
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

# 사용자 데이터 로드
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


# --- 로그 및 카운트 관리 함수 (파일 쓰기 오류 처리 강화) ---

def log_conversation_entry(speaker, text, log_filename, scaffolding_type=None):
    """대화 항목을 TXT 로그 파일에 추가합니다. (파일 쓰기 오류 처리 강화)"""
    # log_filename은 '이름/시간_학번.txt' 형태이므로 LOGS_DIR과 합쳐 전체 경로를 구성
    log_file_path = os.path.join(LOGS_DIR, log_filename)
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if speaker == 'User':
        log_entry = f"[{now_str}] 사용자: {text}\n\n"
    else: # AI
        label = f" ({scaffolding_type})" if scaffolding_type else ""
        log_entry = f"[{now_str}] AI{label}: {text}\n"
        log_entry += f"----------------------------------------\n\n"
        
    log_dir = os.path.dirname(log_file_path)
    
    # 🚩 진단용 코드 추가: 파일 쓰기 시도 경로를 명확히 출력
    print(f"DEBUG: Attempting to write log to: {log_file_path}")
    
    try:
        # Railway 쓰기 권한 확보 및 폴더 생성
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True) 
            
        with open(log_file_path, 'a', encoding='utf-8') as f:
            f.write(log_entry)
            
    except Exception as e:
        # 🚨 오류 발생 시, Railway 로그에서 오류 유형과 경로를 명확히 확인
        print(f"🚨🚨 CRITICAL LOG WRITE FAIL: 로그 파일 저장 실패: {log_file_path} ({e})")


def update_scaffolding_count(count_filename, user_log_dir, s_type): 
    """스캐폴딩 유형별 횟수를 카운트하여 사용자 로그 폴더에 저장합니다. (파일 쓰기 오류 처리 강화)"""
    
    # user_log_dir은 app.py에서 LOGS_DIR/이름 형태로 전달됨.
    count_file_path = os.path.join(user_log_dir, count_filename) 
    
    valid_types = ["개념적 스캐폴딩", "전략적 스캐폴딩", "메타인지적 스캐폴딩", "동기적 스캐폴딩", "일반"]
    if s_type not in valid_types:
        s_type = "분류실패"
        
    try:
        # 🚩 Railway 쓰기 권한 확보 및 폴더 생성
        if not os.path.exists(user_log_dir):
            os.makedirs(user_log_dir, exist_ok=True)
            
        if os.path.exists(count_file_path):
            with open(count_file_path, 'r', encoding='utf-8') as f:
                counts = json.load(f)
        else:
            counts = {t: 0 for t in valid_types + ["분류실패"]}

        counts[s_type] = counts.get(s_type, 0) + 1
        
        with open(count_file_path, 'w', encoding='utf-8') as f:
            json.dump(counts, f, ensure_ascii=False, indent=4)
            
    except Exception as e:
        print(f"🚨🚨 CRITICAL COUNT WRITE FAIL: 카운트 파일 저장 실패: {count_file_path} ({e})")

# ----------------------------------------------------
# 🚩 Tool 함수 정의 (RAG 구현을 위한 핵심 로직)
# ----------------------------------------------------

def search_edutech_tool(category: str) -> str:
    """
    주어진 카테고리에 해당하는 인공지능 기반 에듀테크 도구를 검색하여 도구명, 웹사이트, 설명을 JSON 문자열로 반환합니다.
    사용 가능한 카테고리는 '소셜 러닝', '학습 콘텐츠', '수업 계획', '유용한 도구'입니다.
    """
    if not EDUTECH_TOOLS_DATA:
        return json.dumps({"error": "도구 데이터베이스가 준비되지 않았습니다."}, ensure_ascii=False)

    category_lower = category.lower().strip() 
    results = [
        item for item in EDUTECH_TOOLS_DATA
        if item.get('카테고리', '').lower().strip() == category_lower
    ]
    
    if not results:
        return json.dumps({"message": f"'{category}' 카테고리에 해당하는 도구를 찾을 수 없습니다."}, ensure_ascii=False)

    return json.dumps(results[:3], ensure_ascii=False)


def get_edutech_websites() -> str:
    """
    에듀테크 관련 정보 사이트 목록을 검색하여 사이트명, 주소, 특징을 JSON 문자열로 반환합니다.
    """
    if not EDUTECH_WEBSITES_DATA:
        return json.dumps({"error": "웹사이트 데이터베이스가 준비되지 않았습니다."}, ensure_ascii=False)
        
    return json.dumps(EDUTECH_WEBSITES_DATA, ensure_ascii=False)

# 🚨 AI가 사용할 Tool 목록 정의
AI_TOOLS = {
    "search_edutech_tool": search_edutech_tool,
    "get_edutech_websites": get_edutech_websites
}

# config_utils.py 파일 하단에 다음 함수를 추가해 주세요.
# (기존 update_scaffolding_count 함수 뒤에 추가하는 것이 좋습니다.)

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
        
        # 카운트가 많은 순서대로 정렬하여 출력
        sorted_counts = sorted(counts.items(), key=lambda item: item[1], reverse=True)
        
        for s_type, count in sorted_counts:
            formatted_text += f"- {s_type}: {count}회\n"
            
        formatted_text += "==================================================\n\n"
        return formatted_text
        
    except Exception as e:
        # 오류 발생 시에도 최소한의 정보를 남김
        return f"\n\n--- 스캐폴딩 카운트 정보 --- \n카운트 파일 로드 또는 포맷 중 오류 발생: {e}"

# 🚨 Tool Schema 정의 (OpenAI SDK용)
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": search_edutech_tool.__name__,
            "description": search_edutech_tool.__doc__,
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "사용자가 원하는 에듀테크 도구의 카테고리 ('소셜 러닝', '학습 콘텐츠', '수업 계획', '유용한 도구' 중 하나)"
                    }
                },
                "required": ["category"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": get_edutech_websites.__name__,
            "description": get_edutech_websites.__doc__,
            "parameters": {"type": "object", "properties": {}} # 인자 없음
        }
    }
]