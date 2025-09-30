# app.py

import os
import datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file 
import json
import time
import shutil

# --- 분리된 설정 및 유틸리티 모듈 임포트 ---
from config_utils import (
    client, MODEL_NAME, INTEGRATED_SYSTEM_PROMPT, AUTHORIZED_USERS,
    load_prompt_file, log_conversation_entry, update_scaffolding_count,
    LOGS_DIR, format_scaffolding_counts # Tool 관련 변수 제거 (필요 없음)
)
# ----------------------------------------


app = Flask(__name__, 
            template_folder='homepage/templates', 
            static_folder='homepage/static')

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
            print(f"DEBUG: 생성 시도 경로: {user_log_dir}")

            os.makedirs(user_log_dir, exist_ok=True)
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
            log_conversation_entry('System', f"연구 참여 동의: {session['user']['name']} ({session['user']['student_id']}) 동의함", log_filename)
            
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

# ----------------------------------------------------
# 🚩 /get_response 라우트 (RAG 안정화 - Tool-Calling 제거)
# ----------------------------------------------------
@app.route('/get_response', methods=['POST'])
def get_response():
    """AI 답변 요청 및 로그 저장 (Tool-Calling 로직 제거)"""
    if 'user' not in session:
        return jsonify({'error': '세션 오류. 다시 로그인해주세요.'}), 401
    if not client:
        return jsonify({'error': 'AI 클라이언트 초기화 실패. API 키 설정 오류일 수 있습니다.'}), 503

    user_message = request.json['message']
    conversation = session.get('conversation', [])
    log_filename = session.get('log_filename', 'temp.txt')
    count_filename = session.get('count_filename', 'temp.json')
    user_log_dir = session.get('user_log_dir', LOGS_DIR) 

    # 1. 사용자 메시지를 대화 이력에 추가 
    conversation.append({"role": "user", "content": user_message})

    # 2. API 호출을 위한 메시지 리스트 구성
    messages_for_api = [
        {"role": "system", "content": INTEGRATED_SYSTEM_PROMPT}
    ] + conversation
    
    try:
        # 🚨 수정: Tool-Calling 구조 제거 및 단일 API 호출로 변경
        response = client.chat.completions.create(
            model=MODEL_NAME, 
            messages=messages_for_api, 
            # tools=TOOLS_SCHEMA, <-- 제거됨
            response_format={"type": "json_object"}
        )
        
        ai_response_json_str = response.choices[0].message.content
        
        # 3. AI 응답 파싱 및 추출
        try:
            ai_response_data = json.loads(ai_response_json_str)
            
            scaffolding_type = ai_response_data.get("scaffolding_type", "분류실패")
            valid_types = ["개념적 스캐폴딩", "전략적 스캐폴딩", "메타인지적 스캐폴딩", "동기적 스캐폴딩", "일반"]
            if not scaffolding_type in valid_types:
                scaffolding_type = "분류실패"
                
            response_text = ai_response_data.get("response_text", "AI 응답 생성에 실패했습니다.")
            
        except json.JSONDecodeError:
            scaffolding_type = "JSON 파싱 실패"
            response_text = "AI 응답 형식에 오류가 발생했어. 잠시 후 다시 시도해 봐."
            
        # 4. AI 응답을 대화 이력에 추가하고 세션에 저장
        conversation.append({"role": "assistant", "content": response_text})
        session['conversation'] = conversation
        
        # 5. 로그 기록 및 카운트 업데이트
        log_conversation_entry('User', user_message, log_filename)
        log_conversation_entry('AI', response_text, log_filename, scaffolding_type)
        update_scaffolding_count(count_filename, user_log_dir, scaffolding_type)
        
        # 6. 최종 응답 반환
        return jsonify({'response': response_text})

    except Exception as e:
        # 오류 발생 시 사용자 메시지를 대화 이력에서 제거
        if conversation and conversation[-1].get('role') == 'user':
            conversation.pop()
            session['conversation'] = conversation 
            
        print(f"🚨 ERROR: OpenAI API 호출 오류: {e}")
        log_conversation_entry('System_Error', f"API 호출 오류 발생: {e}", log_filename)
        return jsonify({'error': 'AI 응답을 가져오는 데 실패했습니다. 다시 시도해 주세요.'}), 500


@app.route('/get_prompt_response', methods=['POST'])
def get_prompt_response():
    """JavaScript 타이머에 의해 호출되어 AI의 재촉 메시지를 받습니다."""
    if 'user' not in session:
        return jsonify({'error': '세션 오류 또는 AI 클라이언트 초기화 실패'}), 401

    conversation = session.get('conversation', [])
    log_filename = session.get('log_filename', 'temp.txt')
    count_filename = session.get('count_filename', 'temp.json')
    user_log_dir = session.get('user_log_dir', LOGS_DIR) 

    prompt_message = "5분 동안 사용자로부터 응답이 없습니다. 프롬프트 규칙 1번(침묵 감지 및 재촉)에 따라, '지금 어디까지 생각해봤거나 어디까지 진행되었어? 하면서 어떤 부분이 어렵니?'와 같은 내용으로 사용자의 대화를 재촉하는 메시지를 생성하세요."

    messages_for_api = [
        {"role": "system", "content": INTEGRATED_SYSTEM_PROMPT},
        {"role": "user", "content": prompt_message} 
    ] + conversation 

    try:
        # 🚨 Tool 호출 인자 제거
        chat_completion = client.chat.completions.create(
            model=MODEL_NAME, 
            messages=messages_for_api, 
            response_format={"type": "json_object"}
        )
        ai_response_json_str = chat_completion.choices[0].message.content
        
        ai_response_data = json.loads(ai_response_json_str)
        response_text = ai_response_data.get("response_text", "다시 시도해 주세요.")
        scaffolding_type = ai_response_data.get("scaffolding_type", "동기적 스캐폴딩") 

        conversation.append({"role": "assistant", "content": response_text})
        session['conversation'] = conversation
        log_conversation_entry('AI', response_text, log_filename, scaffolding_type)
        
        update_scaffolding_count(count_filename, user_log_dir, scaffolding_type)
        
        return jsonify({'response': response_text})

    except Exception as e:
        print(f"🚨 ERROR: 침묵 감지 API 호출 오류: {e}")
        log_conversation_entry('System_Error', f"침묵 감지 오류 발생: {e}", log_filename)
        return jsonify({'error': 'AI 재촉 메시지를 가져오는 데 실패했습니다.'}), 500

# ----------------------------------------------------
# 🚩 /submit_and_download_log 라우트 (로그 다운로드 기능)
# ----------------------------------------------------
@app.route('/submit_and_download_log')
def submit_and_download_log():
    """최종 로그 파일과 카운트 횟수를 통합하여 다운로드 제공합니다. (세션 유지)"""
    if 'user' not in session or 'user_log_dir' not in session:
        return redirect(url_for('login'))
        
    user_info = session['user']
    user_log_dir = session['user_log_dir']
    
    # 세션에서 파일명 로드
    log_filename_relative = session.get('log_filename') 
    count_filename = session.get('count_filename')
    
    # 🚨 핵심: 파일 경로 구성 및 존재 확인
    main_log_path = os.path.join(LOGS_DIR, log_filename_relative)
    
    print(f"DEBUG: 로그 다운로드 시도 (LOG): {main_log_path}")
    
    # 1. 메인 대화 로그 읽기
    try:
        from config_utils import format_scaffolding_counts # 함수 임포트
        
        if not os.path.exists(main_log_path):
            print(f"🚨 CRITICAL ERROR: Main log file not found at {main_log_path}")
            return f"오류: 대화 로그 파일이 서버에 존재하지 않습니다. 경로를 확인하세요: {main_log_path}", 404
        
        with open(main_log_path, 'r', encoding='utf-8') as f:
            conversation_log = f.read()
            
    except Exception as e:
        print(f"🚨 ERROR: 메인 로그 파일 읽기 오류: {e}")
        return "로그 파일을 읽는 중 서버 오류가 발생했습니다.", 500

    # 2. 스캐폴딩 카운트 포맷하여 가져오기
    count_summary = format_scaffolding_counts(count_filename, user_log_dir)
    
    # 3. 최종 통합 내용 생성 (다운로드를 위한 임시 파일)
    final_download_filename = f"{user_info['name']}_{user_info['student_id']}_AI_Log.txt"
    final_download_path = os.path.join('/tmp', final_download_filename)
    final_content = conversation_log + count_summary

    try:
        with open(final_download_path, 'w', encoding='utf-8') as f:
            f.write(final_content)
            
        # 4. 파일 전송 (다운로드 시작)
        response = send_file(
            final_download_path, 
            mimetype='text/plain',
            as_attachment=True,
            download_name=final_download_filename
        )
        
        # 5. 응답 반환
        return response

    except Exception as e:
        print(f"🚨 ERROR: 최종 로그 파일 생성/다운로드 중 오류 발생: {e}")
        return "최종 로그 파일 다운로드 중 서버 오류가 발생했습니다.", 500


if __name__ == "__main__":
    print("======================================================")
    print("✅ 서버 준비 완료.")
    print("------------------------------------------------------")
    print("🚀 서버 시작 (Ctrl+C로 종료)")
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)