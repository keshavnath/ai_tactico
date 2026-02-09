// AI Tactico Frontend - Q&A Interface

const questionInput = document.getElementById('questionInput');
const submitBtn = document.getElementById('submitBtn');
const messagesDiv = document.getElementById('messages');

// Focus on input when page loads
window.addEventListener('load', () => {
    questionInput.focus();
});

// Submit on button click
submitBtn.addEventListener('click', submitQuestion);

// Submit on Enter key (Shift+Enter for multiline)
questionInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        submitQuestion();
    }
});

async function submitQuestion() {
    const question = questionInput.value.trim();
    
    if (!question) {
        alert('Please enter a question');
        return;
    }
    
    // Disable input while processing
    questionInput.disabled = true;
    submitBtn.disabled = true;
    
    // Show user message
    addMessage('user', question);
    
    // Clear input
    questionInput.value = '';
    
    // Show loading message
    const loadingId = addMessage('loading', 'Analyzing match data...');
    
    try {
        // Call the agent API
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ question })
        });
        
        const data = await response.json();
        
        // Remove loading message
        removeMessage(loadingId);
        
        if (data.success) {
            // Show assistant response
            addMessage('assistant', data.answer);
        } else {
            // Show error
            addMessage('error', data.error || 'An error occurred');
        }
    } catch (error) {
        removeMessage(loadingId);
        addMessage('error', `Error: ${error.message}`);
        console.error('Error:', error);
    } finally {
        // Re-enable input
        questionInput.disabled = false;
        submitBtn.disabled = false;
        questionInput.focus();
    }
}

function addMessage(role, text) {
    const messageId = `msg-${Date.now()}`;
    const messageEl = document.createElement('div');
    messageEl.id = messageId;
    messageEl.className = `message ${role}`;
    
    let label = '';
    if (role === 'user') {
        label = 'You';
    } else if (role === 'assistant') {
        label = 'AI Analyst';
    } else if (role === 'error') {
        label = 'Error';
    } else if (role === 'loading') {
        label = 'Analyzing';
    }
    
    if (label) {
        messageEl.innerHTML = `<div class="label">${label}</div><div class="text">${escapeHtml(text)}</div>`;
    } else {
        messageEl.innerHTML = `<div class="text">${escapeHtml(text)}</div>`;
    }
    
    messagesDiv.appendChild(messageEl);
    
    // Scroll to bottom
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
    
    return messageId;
}

function removeMessage(messageId) {
    const messageEl = document.getElementById(messageId);
    if (messageEl) {
        messageEl.remove();
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
