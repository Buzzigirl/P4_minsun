# app.py

import os
import datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import json
import time

# --- 분리된 설정 및 유틸리티 모듈 임포트 ---
# 주의: config_utils.py 파일에서 COUNTS_DIR 정의는 삭제되어야 합니다.
from config_utils import (
    client, MODEL_NAME, INTEGRATED_SYSTEM_PROMPT, AUTHORIZED_USERS,
    load_prompt_file, log_conversation_entry, update_scaffolding_count,
    LOGS_DIR # LOGS_DIR은 경로 구성에 필요
)
# ----------------------------------------


app = Flask(__name__, 
            template_folder='homepage/templates', 
            static_folder='homepage/static')

# FLASK_SECRET_KEY를 환경 변수에서 로드
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default-super-secret-key-for-session')


# --- Flask 라우팅 ---

@app.route('/', methods=['GET', 'POST'])
def login():
    """로그인 (학번/이름)"""
    if request.method == 'POST':
        student_id = request.form['student_id'].strip()
        name = request.form['name'].strip()
        expected_name = AUTHORIZED_USERS.get(student_id)

        print("-------------------- 로그인 시도 --------------------")
        print(f"DEBUG: 폼 입력 학번 (ID): '{student_id}'")
        print(f"DEBUG: 폼 입력 성명 (Name): '{name}'")
        print(f"DEBUG: JSON 기대 성명 (Expected): '{expected_name}'")
        print("--------------------------------------------------")
        
        # 인증 확인
        if expected_name is not None and expected_name == name:
            session.clear()
            session['user'] = {'name': name, 'student_id': student_id}
            
            # 사용자별 로그 폴더를 생성하고 세션에 저장
            user_log_dir = os.path.join(LOGS_DIR, name)
            os.makedirs(user_log_dir, exist_ok=True)
            # 🚨 user_log_dir 세션 변수 추가 (카운트 파일 경로 구성에 사용)
            session['user_log_dir'] = user_log_dir 

            now = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')
            
            # 대화 로그 파일 경로 (logs/[이름]/[시간_학번].txt)
            log_filename = os.path.join(name, f"{now}_{student_id}.txt")
            session['log_filename'] = log_filename
            
            # 스캐폴딩 카운트 파일 이름 (logs/[이름]/[학번_이름].json)
            count_filename = f"{student_id}_{name}.json"
            session['count_filename'] = count_filename
            
            session['conversation'] = [] 
            
            return redirect(url_for('consent'))
        else:
            error = "등록되지 않은 사용자입니다. 학번과 이름을 정확히 확인해주세요."
            return render_template('login.html', error=error)
            
    return render_template('login.html')

@app.route('/consent', methods=['GET', 'POST'])
def consent():
    """연구 참여 동의서 페이지"""
    if 'user' not in session:
        return redirect(url_for('login'))
        
    log_filename = session.get('log_filename', 'temp.txt')
    
    if request.method == 'POST':
        consent_status = request.form.get('consent_check')
        
        if consent_status == 'agree':
            # log_conversation_entry는 log_filename을 받습니다.
            log_conversation_entry('System', f"연구 참여 동의: {session['user']['name']} ({session['user']['student_id']}) 동의함", log_filename)
            
            # 🚩 동의 후 summary 페이지로 이동
            return redirect(url_for('summary')) 
        else:
            log_conversation_entry('System', f"연구 참여 동의: {session['user']['name']} ({session['user']['student_id']}) 비동의함. 접속 종료.", log_filename)
            session.clear()
            return render_template('consent.html', error="비동의하셨습니다. 실험에 참여할 수 없습니다. 창을 닫아주세요.")
            
    return render_template('consent.html')


@app.route('/summary')
def summary():
    """학습 개요 및 목표 설명 페이지"""
    if 'user' not in session:
        return redirect(url_for('login'))
        
    situation = load_prompt_file('situation.md')
    rules = load_prompt_file('rules.md')
    task = load_prompt_file('task.md')
    
    learner_model = "**<학습자 중심 모델>**\n\n학습 활동 설계의 이론적 기반입니다. 이 모델을 염두에 두고 활동을 설계해 주세요."
    
    return render_template('summary.html', 
                            user_name=session['user']['name'],
                            situation=situation,
                            rules=rules,
                            task=task,
                            learner_model=learner_model)

@app.route('/chat')
def chat():
    """메인 채팅 페이지"""
    if 'user' not in session:
        return redirect(url_for('login'))
    
    # 아바타 경로는 peer_avatar.webp로 가정
    avatar_url = url_for('static', filename='images/peer_avatar.webp')
    
    situation = load_prompt_file('situation.md')
    rules = load_prompt_file('rules.md')
    task = load_prompt_file('task.md')
    
    user_name = session['user']['name']
    log_filename = session.get('log_filename', 'temp.txt')
    
    # --- 첫 접속 시 AI의 초기 인사말 처리 로직 ---
    conversation = session.get('conversation', [])
    if not conversation: 
        initial_greeting = f"안녕, {user_name}야! 나는 오늘 너와 함께 과제를 해결할 동료 학습자 AI야. 교내 쓰레기 처리 문제를 해결할 수 있는 학습 활동 설계를 지금부터 함께 시작해 보자! 어떻게 시작하면 좋을까?"
        conversation.append({"role": "assistant", "content": initial_greeting})
        session['conversation'] = conversation
        
        log_conversation_entry('AI', initial_greeting, log_filename, scaffolding_type="일반")
    # -----------------------------------------------
    
    chat_history = conversation
    
    return render_template('chat.html', 
                            user_name=user_name, 
                            situation=situation, 
                            rules=rules, 
                            task=task,
                            chat_history=chat_history,
                            AVATAR_URL=avatar_url)


@app.route('/get_response', methods=['POST'])
def get_response():
    """AI 답변 요청 및 로그 저장"""
    if 'user' not in session:
        return jsonify({'error': '세션 오류. 다시 로그인해주세요.'}), 401
    if not client:
        return jsonify({'error': 'AI 클라이언트 초기화 실패. API 키 설정 오류일 수 있습니다.'}), 503

    user_message = request.json['message']
    conversation = session.get('conversation', [])
    log_filename = session.get('log_filename', 'temp.txt')
    count_filename = session.get('count_filename', 'temp.json')
    # 🚨 user_log_dir 변수 가져오기 (config_utils의 update_scaffolding_count 함수에 전달)
    user_log_dir = session.get('user_log_dir', LOGS_DIR) 


    # 1. 사용자 메시지 추가 및 로그 저장
    conversation.append({"role": "user", "content": user_message})
    log_conversation_entry('User', user_message, log_filename)

    try:
        # --- API 호출 시 시스템 프롬프트를 대화 이력에 추가 ---
        messages_for_api = [
            {"role": "system", "content": INTEGRATED_SYSTEM_PROMPT}
        ] + conversation
        # ----------------------------------------------------
        
        chat_completion = client.chat.completions.create(
            model=MODEL_NAME, 
            messages=messages_for_api, 
            response_format={"type": "json_object"}
        )
        ai_response_json_str = chat_completion.choices[0].message.content
        
        # 2. AI의 JSON 응답 파싱
        try:
            ai_response_data = json.loads(ai_response_json_str)
            
            scaffolding_type = ai_response_data.get("scaffolding_type", "분류실패")
            valid_types = ["개념적 스캐폴딩", "전략적 스캐폴딩", "메타인지적 스캐폴딩", "동기적 스캐폴딩", "일반"]
            if not scaffolding_type in valid_types:
                scaffolding_type = "분류실패"
                
            response_text = ai_response_data.get("response_text", "AI 응답 생성에 실패했습니다.")
            
        except json.JSONDecodeError:
            scaffolding_type = "JSON 파싱 실패"
            response_text = "AI 응답 형식에 오류가 발생했어. 잠시 후 다시 시도해 봐. (원본 응답: " + ai_response_json_str[:50] + "...)"
            
        # 3. AI 응답을 세션에 저장 및 로그에 기록
        conversation.append({"role": "assistant", "content": response_text})
        session['conversation'] = conversation
        
        log_conversation_entry('AI', response_text, log_filename, scaffolding_type)
        
        # 4. 스캐폴딩 횟수 카운트 업데이트 (🚨 user_log_dir 인자 추가)
        update_scaffolding_count(count_filename, user_log_dir, scaffolding_type)
        
        # 5. 채팅창에는 순수 텍스트만 전송
        return jsonify({'response': response_text})

    except Exception as e:
        print(f"🚨 ERROR: OpenAI API 호출 오류: {e}")
        log_conversation_entry('System_Error', f"API 호출 오류 발생: {e}", log_filename)
        return jsonify({'error': 'AI 응답을 가져오는 데 실패했습니다. API 키 또는 네트워크 상태를 확인하세요.'}), 500

if __name__ == "__main__":
    print("======================================================")
    print("✅ 서버 준비 완료.")
    print("------------------------------------------------------")
    print("🚀 서버 시작 (Ctrl+C로 종료)")
    
    # 🚨 Railway 환경 변수 PORT를 사용하여 동적 포트 바인딩
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)