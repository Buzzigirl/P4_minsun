// chat_logic.js

// 🚩 Flask 변수는 HTML에서 전역 변수로 설정되어야 함 (아래 최종 chat.html에서 설정함)
const AVATAR_URL = window.AVATAR_URL;
const PLACEHOLDER_AVATAR_URL = window.PLACEHOLDER_AVATAR_URL;

const chatBox = document.getElementById('chat-box');
const userInput = document.getElementById('user-input');

// --- 새로운 기능: 타이머 및 팝업 로직 ---
const TOTAL_TIME_SECONDS = 30 * 60; // 30분
const TIMER_DISPLAY = document.getElementById('timer');
const MODAL = document.getElementById('end-session-modal');
const MODAL_MESSAGE = document.getElementById('modal-message');
const MODAL_BUTTONS = document.getElementById('modal-buttons');

let startTime;

// 1. 타이머 초기화 및 시작
function initializeTimer() {
    if (!localStorage.getItem('chatStartTime')) {
        startTime = Date.now();
        localStorage.setItem('chatStartTime', startTime);
    } else {
        startTime = parseInt(localStorage.getItem('chatStartTime'));
    }
    
    setInterval(updateTimer, 1000);
}

// 2. 타이머 업데이트 로직
function updateTimer() {
    const elapsedTimeMs = Date.now() - startTime;
    const remainingTimeSeconds = TOTAL_TIME_SECONDS - Math.floor(elapsedTimeMs / 1000);
    
    if (remainingTimeSeconds <= 0) {
        TIMER_DISPLAY.textContent = "남은 시간: 00:00 (종료 권장)";
        TIMER_DISPLAY.style.backgroundColor = '#e74c3c';
        return;
    }
    
    const minutes = Math.floor(remainingTimeSeconds / 60);
    const seconds = remainingTimeSeconds % 60;
    
    const formattedTime = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    
    TIMER_DISPLAY.textContent = `남은 시간: ${formattedTime}`;

    if (remainingTimeSeconds < 5 * 60) {
         TIMER_DISPLAY.style.backgroundColor = '#f39c12';
    } else {
         TIMER_DISPLAY.style.backgroundColor = '#4285f4';
    }
}

// 3. 팝업 표시/숨기기
function showModal() {
    MODAL.style.display = 'flex';
}

function closeModal() {
    MODAL.style.display = 'none';
}

// 4. 시간 확인 및 팝업 로직 (버튼 클릭 시 호출됨)
function checkTimeAndShowPopup() {
    const elapsedTimeSeconds = Math.floor((Date.now() - startTime) / 1000);
    const timePassed30Minutes = elapsedTimeSeconds >= TOTAL_TIME_SECONDS;
    
    MODAL_BUTTONS.innerHTML = '';
    
    if (!timePassed30Minutes) {
        // 30분 지나지 않았을 경우
        MODAL_MESSAGE.innerHTML = '아직 과업수행시간이 30분이 지나지 않았습니다. 동료 AI와 학습을 추가적으로 진행해주시기 바랍니다.';
        
        const backButton = document.createElement('button');
        backButton.textContent = '확인 (학습으로 돌아가기)';
        backButton.classList.add('btn-back');
        backButton.onclick = closeModal;
        
        MODAL_BUTTONS.appendChild(backButton);
        
    } else {
        // 30분 지났을 경우
        MODAL_MESSAGE.innerHTML = '사전에 나누어 드린 수업활동지를 구글 드라이브에 업로드 해주셨을까요?';
        
        const yesButton = document.createElement('button');
        yesButton.textContent = '예';
        yesButton.classList.add('btn-yes');
        yesButton.onclick = function() {
            window.open('/submission', '_blank'); 
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

// 기존 메시지 처리 함수들
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
    userInput.disabled = false;
    userInput.focus(); 
}

function sendMessage() {
    const message = userInput.value.trim();
    if (message === '') return;

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

// 윈도우 로드 시 이벤트
window.onload = function() {
    chatBox.scrollTop = chatBox.scrollHeight;
    userInput.focus();
    initializeTimer(); // 타이머 시작
};