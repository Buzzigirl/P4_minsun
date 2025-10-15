// chat_logic.js

// 🚩 Flask 변수는 HTML에서 전역 변수로 설정되어야 함
const AVATAR_URL = window.AVATAR_URL;
const PLACEHOLDER_AVATAR_URL = window.PLACEHOLDER_AVATAR_URL;
const USER_ID = window.USER_ID; // 학번

const chatBox = document.getElementById('chat-box');
const userInput = document.getElementById('user-input');

// --- 30분 학습 타이머 및 팝업 로직 ---
const TOTAL_TIME_SECONDS = 30 * 60; // 30분 제한 복구
const TIMER_DISPLAY = document.getElementById('timer');
const MODAL = document.getElementById('end-session-modal');
const MODAL_MESSAGE = document.getElementById('modal-message');
const MODAL_BUTTONS = document.getElementById('modal-buttons');

const TIMER_STORAGE_KEY = 'chatStartTime_' + USER_ID;

let startTime;

// 🚩 버튼 요소 가져오기
const LOG_DOWNLOAD_BUTTON = document.getElementById('log-download-button');
const LOG_DOWNLOAD_LINK = document.getElementById('log-download-link');
const SUBMIT_END_BUTTON = document.getElementById('submit-and-end-button'); // 종료 버튼도 제어

// 🚩 초기 버튼 상태 설정 (비활성화 상태로 시작)
if (LOG_DOWNLOAD_BUTTON) {
    LOG_DOWNLOAD_BUTTON.disabled = true;
    LOG_DOWNLOAD_BUTTON.style.opacity = '0.5';
    LOG_DOWNLOAD_BUTTON.style.cursor = 'not-allowed';
    // 30분 미만일 경우 다운로드 링크를 임시로 끊어 실수 방지
    if (LOG_DOWNLOAD_LINK) {
        LOG_DOWNLOAD_LINK.href = 'javascript:void(0)';
    }
}
// ------------------------------------

// --- 새로운 기능: 침묵 감지 로직 ---
const INACTIVITY_TIME = 5 * 60 * 1000; // 5분 (밀리초)
let inactivityTimeout;

// 🚩 5분 타이머 초기화 및 재설정 함수
function resetInactivityTimer() {
    clearTimeout(inactivityTimeout);
    inactivityTimeout = setTimeout(promptInactivity, INACTIVITY_TIME);
}

// 🚩 5분 경과 시 호출되는 함수 (AI 재촉 메시지 호출)
function promptInactivity() {
    showLoading(); 
    
    fetch('/get_prompt_response', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({})
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        if (data.response) {
            appendMessage('AI', data.response);
        } else if (data.error) {
            console.error("Inactivity Prompt Error:", data.error);
        }
        resetInactivityTimer();
    })
    .catch(error => {
        hideLoading();
        console.error('Fetch error:', error);
        resetInactivityTimer(); 
    });
}
// --- 침묵 감지 로직 끝 ---

// 1. 30분 타이머 초기화 및 시작
function initializeTimer() {
    if (!localStorage.getItem(TIMER_STORAGE_KEY)) { 
        startTime = Date.now();
        localStorage.setItem(TIMER_STORAGE_KEY, startTime);
    } else {
        startTime = parseInt(localStorage.getItem(TIMER_STORAGE_KEY));
    }
    
    setInterval(updateTimer, 1000);
}

// 2. 30분 타이머 업데이트 로직 (🚩 버튼 활성화 로직 포함)
function updateTimer() {
    const elapsedTimeMs = Date.now() - startTime;
    const remainingTimeSeconds = TOTAL_TIME_SECONDS - Math.floor(elapsedTimeMs / 1000);
    
    // 🚩 1. 시간 종료 체크 및 버튼 활성화
    if (remainingTimeSeconds <= 0) {
        TIMER_DISPLAY.textContent = "남은 시간: 00:00 (종료 권장)";
        TIMER_DISPLAY.style.backgroundColor = '#e74c3c'; // 빨간색
        
        // 🚨 다운로드 버튼 활성화 로직
        if (LOG_DOWNLOAD_BUTTON && LOG_DOWNLOAD_BUTTON.disabled) {
            LOG_DOWNLOAD_BUTTON.disabled = false;
            LOG_DOWNLOAD_BUTTON.style.opacity = '1.0';
            LOG_DOWNLOAD_BUTTON.style.cursor = 'pointer';
            // 링크의 다운로드 속성 복구
            if (LOG_DOWNLOAD_LINK) {
                 LOG_DOWNLOAD_LINK.href = "/submit_and_download_log"; 
            }
        }
        // 종료 버튼은 항상 활성화되어 있다고 가정 (팝업에서 시간 체크)
        return; 
    }
    
    // 2. 정상 카운트다운 계산 및 포맷
    const minutes = Math.floor(remainingTimeSeconds / 60);
    const seconds = remainingTimeSeconds % 60;
    
    const formattedTime = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    
    TIMER_DISPLAY.textContent = `남은 시간: ${formattedTime}`;

    // 3. 5분 미만 경고 스타일
    if (remainingTimeSeconds < 5 * 60) {
         TIMER_DISPLAY.style.backgroundColor = '#f39c12'; // 노란색
    } else {
         TIMER_DISPLAY.style.backgroundColor = '#4285f4'; // 파란색
    }
    
    // 🚨 30분 미만일 경우 버튼 비활성화 상태 유지
    if (LOG_DOWNLOAD_BUTTON && !LOG_DOWNLOAD_BUTTON.disabled) {
        LOG_DOWNLOAD_BUTTON.disabled = true;
        LOG_DOWNLOAD_BUTTON.style.opacity = '0.5';
        LOG_DOWNLOAD_BUTTON.style.cursor = 'not-allowed';
        // 30분 미만일 경우 다운로드 링크를 임시로 끊어 실수 방지
        if (LOG_DOWNLOAD_LINK) {
            LOG_DOWNLOAD_LINK.href = 'javascript:void(0)';
        }
    }
}

// 3. 팝업 표시/숨기기
function showModal() {
    MODAL.style.display = 'flex';
}

function closeModal() {
    MODAL.style.display = 'none';
}

// 4. 제출 팝업 로직 (시간 체크 및 버튼 동작)
function checkTimeAndShowPopup() {
    const elapsedTimeSeconds = Math.floor((Date.now() - startTime) / 1000);
    const timePassed30Minutes = elapsedTimeSeconds >= TOTAL_TIME_SECONDS;
    
    const DRIVE_URL = 'https://drive.google.com/drive/folders/1S9kVIZ2Ij_r8XJ6qm7Ck5bc10Ms91fnW?usp=drive_link;
    const DOWNLOAD_URL = '/submit_and_download_log';

    MODAL_BUTTONS.innerHTML = '';
    
    if (!timePassed30Minutes) {
        // 1) 30분 지나지 않았을 경우
        MODAL_MESSAGE.innerHTML = '아직 과업수행시간이 30분이 지나지 않았습니다. 동료 AI와 학습을 추가적으로 진행해주시기 바랍니다.';
        
        const backButton = document.createElement('button');
        backButton.textContent = '확인 (학습으로 돌아가기)';
        backButton.classList.add('btn-back');
        backButton.onclick = closeModal;
        
        MODAL_BUTTONS.appendChild(backButton);
        
    } else {
        // 2) 30분 지났을 경우 (제출 가능)
        MODAL_MESSAGE.innerHTML = '구글 드라이브 링크에 들어가서 본인 이름의 파일에 있는 최종 결과물 양식을 작성해주시기 바랍니다.';
        
        const yesButton = document.createElement('button');
        yesButton.textContent = '예';
        yesButton.classList.add('btn-yes');
        yesButton.onclick = function() {
            // 1. 다운로드 요청 시작 (로그 통합 및 다운로드)
            window.open(DOWNLOAD_URL, '_blank'); 
            
            // 2. 다운로드 시작 후 잠시 지연 후 Google Drive 페이지로 리디렉션
            setTimeout(() => {
                window.location.href = DRIVE_URL;
            }, 1000); 

            closeModal();
        };
        
        const backButton = document.createElement('button');
        backButton.textContent = '학습으로 돌아가기';
        backButton.classList.add('btn-back');
        backButton.onclick = closeModal;
        
        MODAL_BUTTONS.appendChild(yesButton);
        MODAL_BUTTONS.appendChild(backButton);
    }
    
    showModal();
}

// 5. 메시지 처리 함수들 (appendMessage, showLoading, hideLoading 유지)
function appendMessage(speaker, message) {
    const row = document.createElement('div');
    row.classList.add('message-row', speaker === 'AI' ? 'ai-message-row' : 'user-message-row');

    if (speaker === 'AI') {
        const avatar = document.createElement('img');
        avatar.src = AVATAR_URL; 
        avatar.alt = "AI 아바타";
        avatar.classList.add('avatar');
        avatar.onerror = function() { this.onerror=null; this.src=PLACEHOLDER_AVATAR_URL; };
        row.appendChild(avatar);
    }

    const content = document.createElement('div');
    content.classList.add('message-content');
    content.innerHTML = message.replace(/\n/g, '<br>'); 
    row.appendChild(content);

    chatBox.appendChild(row);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function showLoading() {
    const loadingRow = document.createElement('div');
    loadingRow.id = 'loading-row';
    loadingRow.classList.add('message-row', 'ai-message-row');

    const avatar = document.createElement('img');
    avatar.src = AVATAR_URL; 
    avatar.alt = "AI 아바타";
    avatar.classList.add('avatar');
    avatar.onerror = function() { this.onerror=null; this.src=PLACEHOLDER_AVATAR_URL; };
    loadingRow.appendChild(avatar);
    
    const content = document.createElement('div');
    content.classList.add('message-content');
    content.innerHTML = 'AI가 생각 중입니다... <span class="loading-dot"></span><span class="loading-dot"></span><span class="loading-dot"></span>';
    loadingRow.appendChild(content);

    chatBox.appendChild(loadingRow);
    chatBox.scrollTop = chatBox.scrollHeight;
    
    userInput.disabled = true;
}

function hideLoading() {
    const loadingRow = document.getElementById('loading-row');
    if (loadingRow) {
        loadingRow.remove();
    }
    // 🚩 2초 쿨다운 로직은 sendMessage에 isSending 플래그를 사용하지 않으므로, 
    //    여기서는 단순 입력 활성화만 유지합니다. (sendMessage 함수에서 처리됨)
    userInput.disabled = false;
    document.querySelector('.input-form button').disabled = false; 
    userInput.focus(); 
}

// 6. 메시지 전송 로직 (🚩 침묵 감지 타이머 재설정 추가)
function sendMessage() {
    const message = userInput.value.trim();
    if (message === '') return;

    // 🚩 메시지 보낼 때 침묵 타이머 재설정
    resetInactivityTimer(); 

    // 🚩 2초 쿨다운 로직을 위해 버튼 비활성화 (sendMessage 내부에서 처리)
    document.querySelector('.input-form button').disabled = true;
    
    appendMessage('User', message);
    userInput.value = '';

    showLoading();
    
    fetch('/get_response', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ message: message })
    })
    .then(response => {
        hideLoading();
        // ... (나머지 then/catch 로직 유지) ...
        if (!response.ok) {
            return response.json().then(data => { 
                console.error('API Error:', data.error || 'Unknown error during API call.');
                throw new Error(data.error || 'AI 응답을 가져오는 데 실패했습니다.'); 
            });
        }
        return response.json();
    })
    .then(data => {
        if (data.error) {
            appendMessage('System', `오류: ${data.error}`);
        } else {
            appendMessage('AI', data.response);
        }
    })
    .catch(error => {
        hideLoading();
        console.error('Fetch error:', error);
        appendMessage('System', `통신 오류: ${error.message}`);
    });
}

// 7. 윈도우 로드 시 이벤트 (🚩 침묵 감지 타이머 시작 추가)
window.onload = function() {
    chatBox.scrollTop = chatBox.scrollHeight;
    userInput.focus();
    initializeTimer(); // 30분 타이머 시작
    
    // 🚩 페이지 로드 시 침묵 감지 타이머 시작
    resetInactivityTimer(); 
};

// 8. 🚩 사용자 활동 감지 이벤트 리스너 추가 (침묵 감지 초기화)
document.addEventListener('mousemove', resetInactivityTimer);
document.addEventListener('keypress', resetInactivityTimer);
userInput.addEventListener('focus', resetInactivityTimer);