/* static/js/ai_chat.js - Logique du chatbot IA médical */

document.addEventListener('DOMContentLoaded', () => {
    // 1. CHAT FLOTTANT (BUBBLE)
    const bubble = document.getElementById('ai-chat-bubble');
    const container = document.getElementById('ai-chat-container');
    const closeBtn = document.getElementById('ai-chat-close');
    const sendBtn = document.getElementById('ai-chat-send');
    const inputText = document.getElementById('ai-chat-input-text');
    const messagesContainer = document.getElementById('ai-chat-messages');

    if (bubble && container) {
        bubble.addEventListener('click', () => {
            container.classList.toggle('active');
            if (container.classList.contains('active')) inputText.focus();
        });
        closeBtn.addEventListener('click', () => container.classList.remove('active'));
    }

    if (sendBtn && inputText) {
        sendBtn.addEventListener('click', () => sendMessage(inputText, messagesContainer));
        inputText.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage(inputText, messagesContainer);
        });
    }

    // 2. CHAT INTÉGRÉ AU DASHBOARD (INDEX)
    const dashSendBtn = document.getElementById('dashboard-chat-send');
    const dashInputText = document.getElementById('dashboard-chat-input');
    const dashMessagesContainer = document.getElementById('dashboard-chat-messages');

    if (dashSendBtn && dashInputText) {
        dashSendBtn.addEventListener('click', () => sendMessage(dashInputText, dashMessagesContainer));
        dashInputText.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage(dashInputText, dashMessagesContainer);
        });
    }

    // FONCTION COMMUNE D'ENVOI
    function sendMessage(input, msgContainer) {
        const text = input.value.trim();
        if (!text) return;

        appendMessage('user', text, msgContainer);
        input.value = '';

        const typingId = 'typing-' + Date.now();
        const typingEl = document.createElement('div');
        typingEl.id = typingId;
        typingEl.className = 'ai-typing';
        typingEl.textContent = '...';
        msgContainer.appendChild(typingEl);
        scrollToBottom(msgContainer);

        fetch('/api/ai/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        })
        .then(r => r.json())
        .then(data => {
            const el = document.getElementById(typingId);
            if (el) el.remove();
            if (data.success) {
                appendMessage('ai', data.response, msgContainer);
            } else {
                appendMessage('ai', 'Erreur technique.', msgContainer);
            }
        })
        .catch(() => {
            const el = document.getElementById(typingId);
            if (el) el.remove();
            appendMessage('ai', 'Serveur indisponible.', msgContainer);
        });
    }

    function appendMessage(sender, text, container) {
        if (!container) return;
        const msg = document.createElement('div');
        msg.className = `message message-${sender}`;
        container.appendChild(msg);
        
        if (sender === 'ai' && !text.includes('indisponible') && !text.includes('Erreur')) {
            typeWriter(text, msg, container);
        } else {
            msg.innerHTML = text;
            scrollToBottom(container);
        }
    }

    function typeWriter(text, element, container) {
        let i = 0;
        const speed = 15; // ms entre caractères

        function type() {
            if (i < text.length) {
                // On gère les balises HTML (ex: <b>) pour ne pas les couper
                if (text[i] === '<') {
                    let tagEnd = text.indexOf('>', i);
                    if (tagEnd !== -1) {
                        element.innerHTML += text.substring(i, tagEnd + 1);
                        i = tagEnd + 1;
                    }
                } else {
                    element.innerHTML += text.charAt(i);
                    i++;
                }
                scrollToBottom(container);
                setTimeout(type, speed);
            } else {
                element.classList.add('finished');
            }
        }
        type();
    }

    function scrollToBottom(container) {
        if (container) container.scrollTop = container.scrollHeight;
    }
});
