# config_utils.py

import os
import json
from openai import OpenAI
import datetime
# from dotenv import load_dotenv # 🚨 Railway 환경을 위해 제거됨

# --- 환경 변수 로드 및 초기 설정 ---
# load_dotenv() # Railway 배포 환경에서는 사용하지 않음

# BASE_DIR은 프로젝트 최상위 폴더를 가리킵니다.
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 

# 로그 및 데이터 폴더 경로 설정
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
DATA_DIR = os.path.join(BASE_DIR, 'data')
PROMPT_DIR = os.path.join(DATA_DIR, 'prompts')

# 필요한 폴더 생성
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(PROMPT_DIR, exist_ok=True)

# --- OpenAI 클라이언트 초기화 ---
client = None
MODEL_NAME = "gpt-4o-mini" # 모델 이름은 여기서 통일

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
    
# 🚩 JSON 파일 경로
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
    # 🚩 학습자 모델 정보 로드 추가
    learner_model_data = load_prompt_file('learner_model.md') 
    
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
학습자 중심 학습 모델에 대한 질문을 받을 경우, 반드시 아래 자료에 기반하여 답변해야 한다.
{learner_model_data}
---
"""
# INTEGRATED_SYSTEM_PROMPT = get_integrated_system_prompt()

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
    print(f"🚨 오류: '{users_path}' 파일을 찾을 수 없습니다. users.json을 생성해주세요.")
    AUTHORIZED_USERS = {}
except json.JSONDecodeError as e:
    print(f"🚨 오류: users.json 파일 형식이 잘못되었습니다. ({e})")
    AUTHORIZED_USERS = {}


# --- 로그 및 카운트 관리 함수 (config_utils에 포함) ---

def log_conversation_entry(speaker, text, log_filename, scaffolding_type=None):
    """대화 항목을 TXT 로그 파일에 추가합니다."""
    log_file_path = os.path.join(LOGS_DIR, log_filename)
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if speaker == 'User':
        log_entry = f"[{now_str}] 사용자: {text}\n\n"
    else: # AI
        label = f" ({scaffolding_type})" if scaffolding_type else ""
        log_entry = f"[{now_str}] AI{label}: {text}\n"
        log_entry += f"----------------------------------------\n\n"
        
    log_dir = os.path.dirname(log_file_path)
    os.makedirs(log_dir, exist_ok=True) 
        
    with open(log_file_path, 'a', encoding='utf-8') as f:
        f.write(log_entry)

def update_scaffolding_count(count_filename, user_log_dir, s_type): 
    """스캐폴딩 유형별 횟수를 카운트하여 사용자 로그 폴더에 저장합니다."""
    
    count_file_path = os.path.join(user_log_dir, count_filename) 
    
    # 분류 실패 또는 유효하지 않은 유형일 경우 "분류실패"로 기록
    valid_types = ["개념적 스캐폴딩", "전략적 스캐폴딩", "메타인지적 스캐폴딩", "동기적 스캐폴딩", "일반"]
    if s_type not in valid_types:
        s_type = "분류실패"
        
    if os.path.exists(count_file_path):
        with open(count_file_path, 'r', encoding='utf-8') as f:
            counts = json.load(f)
    else:
        # 초기화 시 모든 유형을 초기화
        counts = {t: 0 for t in valid_types + ["분류실패"]}

    counts[s_type] = counts.get(s_type, 0) + 1
    
    with open(count_file_path, 'w', encoding='utf-8') as f:
        json.dump(counts, f, ensure_ascii=False, indent=4)

# ----------------------------------------------------
# 🚩 Tool 함수 정의 (RAG 구현을 위한 핵심 로직)
# ----------------------------------------------------

# 🚨 Tool 함수 1: 에듀테크 도구 검색 (2번 질문 유형)
def search_edutech_tool(category: str) -> str:
    """
    주어진 카테고리에 해당하는 인공지능 기반 에듀테크 도구를 검색하여 도구명, 웹사이트, 설명을 JSON 문자열로 반환합니다.
    사용 가능한 카테고리는 '소셜 러닝', '학습 콘텐츠', '수업 계획', '유용한 도구'입니다.
    """
    if not EDUTECH_TOOLS_DATA:
        return json.dumps({"error": "도구 데이터베이스가 준비되지 않았습니다."}, ensure_ascii=False)

    results = [
        item for item in EDUTECH_TOOLS_DATA
        if item.get('카테고리', '').lower() == category.lower()
    ]
    
    if not results:
        return json.dumps({"message": f"'{category}' 카테고리에 해당하는 도구를 찾을 수 없습니다."}, ensure_ascii=False)

    # 응답 토큰 절약을 위해 상위 5개만 반환
    return json.dumps(results[:5], ensure_ascii=False)


# 🚨 Tool 함수 2: 에듀테크 사이트 정보 검색 (3번 질문 유형)
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