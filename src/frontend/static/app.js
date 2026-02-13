// AI Tactico Frontend - Q&A Interface

const questionInput = document.getElementById('questionInput');
const submitBtn = document.getElementById('submitBtn');
const messagesDiv = document.getElementById('messages');
const agentProcess = document.getElementById('agentProcess');
const agentTraceDiv = agentProcess ? agentProcess.querySelector('.agent-trace') : null;
const agentHeading = agentProcess ? agentProcess.querySelector('h3') : null;
let _agentStartTime = null;

// Focus on input when page loads
window.addEventListener('load', () => {
    questionInput.focus();
    // Clean any leftover loading messages from previous sessions
    removeAllLoadingMessages();
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
    
    // Clean stale loading messages and reset visualizer before processing
    removeAllLoadingMessages();
    resetAgentProcess();

    // Disable input while processing
    questionInput.disabled = true;
    submitBtn.disabled = true;
    
    // Show user message
    addMessage('user', question);
    
    // Clear input
    questionInput.value = '';
    
    // Show loading message and record start time for duration
    const loadingId = addMessage('loading', 'Analyzing match data...');
    _agentStartTime = Date.now();
    
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
        // Render real trace if present, otherwise mark complete
        if (data && Array.isArray(data.trace) && data.trace.length > 0) {
            renderTrace(data.trace);
        } else {
            completeAgentProcess(data.success);
        }

        if (data.success) {
            addMessage('assistant', data.answer);
        } else {
            addMessage('error', data.error || 'An error occurred');
        }
    } catch (error) {
        removeMessage(loadingId);
        failAgentProcess();
        addMessage('error', `Error: ${error.message}`);
        console.error('Error:', error);
    } finally {
        // Re-enable input
        questionInput.disabled = false;
        submitBtn.disabled = false;
        questionInput.focus();
    }
}

function removeAllLoadingMessages() {
    try {
        const nodes = Array.from(document.querySelectorAll('.message.loading'));
        nodes.forEach((n) => n.remove());
    } catch (e) {
        // ignore
    }
}

// Agent trace visualizer control (node/tool style)
let _traceTimer = null;
let _traceIndex = 0;
function resetAgentProcess() {
    if (!agentTraceDiv) return;
    agentTraceDiv.innerHTML = '';
    _traceIndex = 0;
    if (_traceTimer) {
        clearInterval(_traceTimer);
        _traceTimer = null;
    }
}

function _createTraceItem(kind, label, meta) {
    const id = `trace-${Date.now()}-${Math.random().toString(16).slice(2,6)}`;
    const el = document.createElement('div');
    el.id = id;
    el.className = 'trace-item running';

    const badge = document.createElement('div');
    badge.className = `badge ${kind === 'node' ? 'node' : (kind === 'tool' ? 'tool' : 'info')}`;
    badge.textContent = kind === 'node' ? 'Node' : (kind === 'tool' ? 'Tool' : 'Info');

    const content = document.createElement('div');
    const title = document.createElement('div');
    title.className = 'title';
    title.textContent = label;
    const metaEl = document.createElement('div');
    metaEl.className = 'meta';
    metaEl.textContent = meta || '';

    content.appendChild(title);
    content.appendChild(metaEl);
    el.appendChild(badge);
    el.appendChild(content);

    return el;
}

function startAgentProcess() {
    resetAgentProcess();
    if (!agentTraceDiv) return;

    // Simulated realistic agent nodes and tool calls (visual only)
    const sequence = [
        { kind: 'node', label: 'Planner', meta: 'building plan' },
        { kind: 'node', label: 'Selector', meta: 'choosing tools' },
        { kind: 'tool', label: 'find_goals()', meta: 'querying events' },
        { kind: 'node', label: 'Reflector', meta: 'evaluating results' },
        { kind: 'tool', label: 'get_event_summary()', meta: 'summarizing buildup' },
        { kind: 'node', label: 'Responder', meta: 'composing answer' }
    ];

    // Append all items but set them not visible; reveal one-by-one
    const items = sequence.map((s) => {
        const el = _createTraceItem(s.kind, s.label, s.meta);
        el.classList.remove('running');
        agentTraceDiv.appendChild(el);
        return el;
    });

    _traceIndex = 0;
    const revealNext = () => {
        if (_traceIndex >= items.length) {
            clearInterval(_traceTimer);
            _traceTimer = null;
            return;
        }
        const cur = items[_traceIndex];
        cur.classList.add('running');
        // mark previous as success
        if (_traceIndex > 0) items[_traceIndex - 1].classList.add('success');
        _traceIndex += 1;
    };

    // Reveal first immediately
    revealNext();
    _traceTimer = setInterval(revealNext, 700);
}

// Render a real trace array from the backend and animate it
function renderTrace(trace) {
    resetAgentProcess();
    if (!agentTraceDiv) return;

    const items = trace.map((t) => {
        if (t.stage === 'action') {
            const params = t.parameters ? JSON.stringify(t.parameters) : '';
            const meta = t.error ? `error: ${t.error}` : params;
            const el = _createTraceItem('tool', t.tool || 'tool', meta);
            el.dataset.success = t.success ? '1' : '0';
            agentTraceDiv.appendChild(el);
            return { el, info: t };
        } else if (t.stage === 'thought') {
            const short = (t.text || '').replace(/\s+/g, ' ').slice(0, 140);
            const el = _createTraceItem('node', 'Thought', short + (t.text && t.text.length > 140 ? '…' : ''));
            el.dataset.kind = 'thought';
            agentTraceDiv.appendChild(el);
            return { el, info: t };
        } else {
            const el = _createTraceItem('info', t.label || 'info', t.meta || '');
            agentTraceDiv.appendChild(el);
            return { el, info: t };
        }
    });

    // set running heading
    if (agentHeading) agentHeading.textContent = 'Agent Process — Running...';
    let idx = 0;
    const step = () => {
        if (idx > 0) {
            const prev = items[idx - 1];
            const ok = prev.el.dataset.success !== '0';
            prev.el.classList.remove('running');
            if (ok) prev.el.classList.add('success');
            else prev.el.classList.add('fail');
        }
        if (idx >= items.length) {
            clearInterval(_traceTimer);
            _traceTimer = null;
            // when finished, show completed heading with duration
            if (agentHeading) {
                const dur = _agentStartTime ? ((Date.now() - _agentStartTime) / 1000).toFixed(2) : '0.00';
                agentHeading.textContent = `Agent Process — Completed (${dur}s)`;
            }
            _agentStartTime = null;
            return;
        }
        const cur = items[idx];
        cur.el.classList.add('running');
        idx += 1;
    };

    step();
    _traceTimer = setInterval(step, 600);
}

function completeAgentProcess(success = true) {
    if (!agentTraceDiv) return;
    if (_traceTimer) {
        clearInterval(_traceTimer);
        _traceTimer = null;
    }
    const items = Array.from(agentTraceDiv.children);
    items.forEach((it) => {
        it.classList.remove('running');
        it.classList.add('success');
    });
    if (agentHeading) {
        const dur = _agentStartTime ? ((Date.now() - _agentStartTime) / 1000).toFixed(2) : '0.00';
        agentHeading.textContent = `Agent Process — Completed (${dur}s)`;
    }
    _agentStartTime = null;
}

function failAgentProcess() {
    if (!agentTraceDiv) return;
    if (_traceTimer) {
        clearInterval(_traceTimer);
        _traceTimer = null;
    }
    const running = agentTraceDiv.querySelector('.trace-item.running');
    if (running) {
        running.classList.remove('running');
        running.classList.add('fail');
    }
    if (agentHeading) {
        const dur = _agentStartTime ? ((Date.now() - _agentStartTime) / 1000).toFixed(2) : '0.00';
        agentHeading.textContent = `Agent Process — Failed (${dur}s)`;
    }
    _agentStartTime = null;
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
