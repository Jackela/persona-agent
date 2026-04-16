(function () {
    function getApiKey() {
        let key = sessionStorage.getItem('pa_api_key');
        if (!key) {
            key = prompt('请输入 API Key:');
            if (key) {
                sessionStorage.setItem('pa_api_key', key);
            }
        }
        return key || '';
    }

    const mobileMenuToggle = document.getElementById('mobileMenuToggle');
    const sidebar = document.getElementById('sidebar');
    const navItems = document.querySelectorAll('.nav-item');
    const pageTitle = document.querySelector('.page-header h1');
    const pageSubtitle = document.querySelector('.header-subtitle');
    const sections = document.querySelectorAll('.page-section');

    const sectionTitles = {
        dashboard: { title: '控制台', subtitle: '管理和切换你的 AI 人格' },
        personas: { title: '人格管理', subtitle: '创建、编辑和配置你的 AI 人格' },
        chat: { title: '对话', subtitle: '与你的 AI 伙伴进行实时交流' },
        memory: { title: '记忆库', subtitle: '查看和管理跨会话记忆' },
    };

    const sectionMap = {
        dashboard: 'dashboard',
        personas: 'persona-editor',
        chat: 'chat',
        memory: 'memory-viz',
    };

    function showSection(sectionId) {
        sections.forEach((sec) => sec.classList.remove('active'));
        const target = document.getElementById(sectionId);
        if (target) target.classList.add('active');
    }

    if (mobileMenuToggle) {
        mobileMenuToggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });
    }

    document.addEventListener('click', (e) => {
        if (window.innerWidth <= 768 && sidebar.classList.contains('open')) {
            if (!sidebar.contains(e.target) && !mobileMenuToggle.contains(e.target)) {
                sidebar.classList.remove('open');
            }
        }
    });

    navItems.forEach((item) => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const section = item.dataset.section;

            navItems.forEach((nav) => nav.classList.remove('active'));
            item.classList.add('active');

            if (sectionTitles[section]) {
                pageTitle.textContent = sectionTitles[section].title;
                pageSubtitle.textContent = sectionTitles[section].subtitle;
            }

            const targetId = sectionMap[section] || section;
            showSection(targetId);

            if (window.innerWidth <= 768) {
                sidebar.classList.remove('open');
            }
        });
    });

    const personaCards = document.querySelectorAll('.persona-card');
    personaCards.forEach((card) => {
        card.addEventListener('click', () => {
            const btn = card.querySelector('.btn-ghost');
            if (btn) {
                btn.textContent = '已选择';
                btn.style.color = 'var(--accent-emerald)';
                setTimeout(() => {
                    btn.textContent = '选择';
                    btn.style.color = '';
                }, 1500);
            }
        });
    });

    const statValues = document.querySelectorAll('.stat-value');
    statValues.forEach((el) => {
        const text = el.textContent.replace(/[^0-9]/g, '');
        const target = parseInt(text, 10);
        if (!isNaN(target)) {
            animateValue(el, 0, target, 800);
        }
    });

    function animateValue(element, start, end, duration) {
        const suffix = element.textContent.replace(/[0-9]/g, '');
        const startTime = performance.now();
        function update(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const ease = 1 - Math.pow(1 - progress, 3);
            const current = Math.floor(start + (end - start) * ease);
            element.textContent = current + suffix;
            if (progress < 1) {
                requestAnimationFrame(update);
            }
        }
        requestAnimationFrame(update);
    }

    function showToast(message) {
        let toast = document.getElementById('appToast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'appToast';
            toast.className = 'toast';
            document.body.appendChild(toast);
        }
        toast.textContent = message;
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), 2500);
    }

    async function loadDashboardStats() {
        try {
            const res = await fetch('/api/stats', {
                headers: { 'X-API-Key': getApiKey() },
            });
            if (!res.ok) throw new Error('Failed to load stats');
            const data = await res.json();

            const personaEl = document.getElementById('stat-personas');
            const sessionsEl = document.getElementById('stat-sessions');
            const memoryEl = document.getElementById('stat-memory');
            const skillsEl = document.getElementById('stat-skills');

            if (personaEl) animateValue(personaEl, 0, data.persona_count || 0, 600);
            if (sessionsEl) animateValue(sessionsEl, 0, data.session_count_today || 0, 600);
            if (memoryEl) animateValue(memoryEl, 0, data.memory_count || 0, 600);
            if (skillsEl) animateValue(skillsEl, 0, data.skills_count || 0, 600);
        } catch (err) {
            console.error('Failed to load dashboard stats:', err);
        }
    }

    loadDashboardStats();
    setInterval(loadDashboardStats, 30000);

    const chatSessionList = document.getElementById('chatSessionList');
    const chatThread = document.getElementById('chatThread');
    const chatInput = document.getElementById('chatInput');
    const chatSend = document.getElementById('chatSend');
    const chatTyping = document.getElementById('chatTyping');
    const chatNewSession = document.getElementById('chatNewSession');
    const streamToggle = document.getElementById('streamToggle');
    let currentSessionId = '1';
    let isWaiting = false;

    function createSessionItem(id, title, time) {
        const div = document.createElement('div');
        div.className = 'chat-session-item';
        div.dataset.sessionId = id;
        div.innerHTML = `<span class="chat-session-title">${escapeHtml(title)}</span><span class="chat-session-time">${escapeHtml(time)}</span>`;
        div.addEventListener('click', () => {
            document.querySelectorAll('.chat-session-item').forEach((i) => i.classList.remove('active'));
            div.classList.add('active');
            currentSessionId = id;
            chatThread.innerHTML = '';
            addAssistantMessage('你好！我是你的 AI 伙伴，有什么可以帮助你的吗？');
        });
        return div;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function sanitizeHtml(html) {
        if (typeof html !== 'string') return '';
        if (typeof window.DOMPurify !== 'undefined') {
            return window.DOMPurify.sanitize(html, {
                ALLOWED_TAGS: [
                    'p', 'br', 'strong', 'b', 'em', 'i', 'u', 's', 'strike',
                    'a', 'img', 'code', 'pre', 'blockquote', 'hr',
                    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                    'ul', 'ol', 'li', 'dl', 'dt', 'dd',
                    'table', 'thead', 'tbody', 'tr', 'th', 'td',
                    'sup', 'sub', 'del', 'ins', 'mark'
                ],
                ALLOWED_ATTR: ['href', 'title', 'src', 'alt', 'class', 'target', 'rel']
            });
        }
        return html
            .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
            .replace(/<iframe\b[^<]*(?:(?!<\/iframe>)<[^<]*)*<\/iframe>/gi, '')
            .replace(/<object\b[^<]*(?:(?!<\/object>)<[^<]*)*<\/object>/gi, '')
            .replace(/<embed\b[^>]*>/gi, '')
            .replace(/on\w+\s*=/gi, 'data-blocked=');
    }

    function renderMarkdown(text) {
        if (typeof marked !== 'undefined') {
            try {
                const raw = marked.parse(text, { async: false });
                return sanitizeHtml(raw);
            } catch (e) {
                return escapeHtml(text);
            }
        }
        return escapeHtml(text);
    }

    function scrollToBottom() {
        chatThread.scrollTop = chatThread.scrollHeight;
    }

    function addUserMessage(text) {
        const msg = document.createElement('div');
        msg.className = 'chat-message chat-message-user';
        msg.innerHTML = `<div class="chat-bubble">${escapeHtml(text)}</div>`;
        chatThread.appendChild(msg);
        scrollToBottom();
    }

    function addAssistantMessage(text) {
        const msg = document.createElement('div');
        msg.className = 'chat-message chat-message-assistant';
        msg.innerHTML = `<div class="chat-avatar mood-joyful">温</div><div class="chat-bubble markdown-body">${renderMarkdown(text)}</div>`;
        chatThread.appendChild(msg);
        scrollToBottom();
        return msg;
    }

    function createStreamingMessage() {
        const msg = document.createElement('div');
        msg.className = 'chat-message chat-message-assistant';
        msg.innerHTML = `<div class="chat-avatar mood-joyful">温</div><div class="chat-bubble markdown-body"></div>`;
        chatThread.appendChild(msg);
        scrollToBottom();
        return msg;
    }

    async function sendMessageNonStream(text) {
        try {
            const res = await fetch(`/api/sessions/${currentSessionId}/messages`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-API-Key': getApiKey() },
                body: JSON.stringify({ message: text }),
            });
            const data = await res.json();
            chatTyping.style.display = 'none';
            if (data && data.content) {
                addAssistantMessage(data.content);
            } else if (data && data.message) {
                addAssistantMessage(data.message);
            } else {
                addAssistantMessage('收到你的消息了，让我想想怎么回复最好。');
            }
        } catch (err) {
            chatTyping.style.display = 'none';
            addAssistantMessage('抱歉，网络似乎有点问题，请稍后再试。');
        } finally {
            isWaiting = false;
        }
    }

    async function sendMessage() {
        const text = chatInput.value.trim();
        if (!text || isWaiting) return;
        chatInput.value = '';
        addUserMessage(text);
        isWaiting = true;
        chatTyping.style.display = 'flex';
        scrollToBottom();

        const useStream = streamToggle && streamToggle.checked;
        if (!useStream) {
            await sendMessageNonStream(text);
            return;
        }

        const encodedMessage = encodeURIComponent(text);
        const evtSource = new EventSource(
            `/api/sessions/${currentSessionId}/messages/stream?message=${encodedMessage}&api_key=${encodeURIComponent(getApiKey())}`
        );

        const msgEl = createStreamingMessage();
        const bubble = msgEl.querySelector('.chat-bubble');
        let rawText = '';
        let hasReceivedData = false;

        evtSource.onmessage = (event) => {
            hasReceivedData = true;
            try {
                const data = JSON.parse(event.data);
                if (data.done) {
                    evtSource.close();
                    chatTyping.style.display = 'none';
                    isWaiting = false;
                    if (bubble) bubble.innerHTML = renderMarkdown(rawText);
                } else if (data.token !== undefined) {
                    rawText += data.token;
                    if (bubble) {
                        bubble.textContent = rawText;
                        scrollToBottom();
                    }
                } else if (data.error) {
                    evtSource.close();
                    chatTyping.style.display = 'none';
                    isWaiting = false;
                    if (bubble) bubble.textContent = data.error;
                }
            } catch (e) {
                console.error('Failed to parse SSE data:', e);
            }
        };

        evtSource.onerror = () => {
            evtSource.close();
            if (!hasReceivedData) {
                msgEl.remove();
                sendMessageNonStream(text);
            } else {
                chatTyping.style.display = 'none';
                isWaiting = false;
                if (bubble) bubble.innerHTML = renderMarkdown(rawText);
            }
        };
    }

    if (chatSend) chatSend.addEventListener('click', sendMessage);
    if (chatInput) {
        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') sendMessage();
        });
    }

    if (chatNewSession) {
        chatNewSession.addEventListener('click', async () => {
            try {
                const res = await fetch('/api/sessions', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-API-Key': getApiKey() } });
                const data = await res.json();
                const id = data.session_id || data.id || String(Date.now());
                currentSessionId = id;
                document.querySelectorAll('.chat-session-item').forEach((i) => i.classList.remove('active'));
                const item = createSessionItem(id, '新会话 ' + new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }), '刚刚');
                item.classList.add('active');
                chatSessionList.insertBefore(item, chatSessionList.firstChild);
                chatThread.innerHTML = '';
                addAssistantMessage('你好！我是你的 AI 伙伴，有什么可以帮助你的吗？');
            } catch (err) {
                showToast('创建会话失败');
            }
        });
    }

    const personaSelect = document.getElementById('personaSelect');
    const personaLoadBtn = document.getElementById('personaLoadBtn');
    const personaSaveBtn = document.getElementById('personaSaveBtn');
    const traitSliders = ['peOpenness', 'peConscientiousness', 'peExtraversion', 'peAgreeableness', 'peNeuroticism'];

    const personalityPresets = {
        warm: { openness: 0.6, conscientiousness: 0.7, extraversion: 0.4, agreeableness: 0.9, neuroticism: 0.3 },
        professional: { openness: 0.6, conscientiousness: 0.9, extraversion: 0.2, agreeableness: 0.6, neuroticism: 0.2 },
        creative: { openness: 0.9, conscientiousness: 0.5, extraversion: 0.6, agreeableness: 0.7, neuroticism: 0.5 },
        humorous: { openness: 0.7, conscientiousness: 0.5, extraversion: 0.8, agreeableness: 0.7, neuroticism: 0.4 },
    };

    const pePersonalityPreset = document.getElementById('pePersonalityPreset');

    function applyPreset(presetKey) {
        const preset = personalityPresets[presetKey];
        if (!preset) return;
        const map = {
            peOpenness: preset.openness,
            peConscientiousness: preset.conscientiousness,
            peExtraversion: preset.extraversion,
            peAgreeableness: preset.agreeableness,
            peNeuroticism: preset.neuroticism,
        };
        Object.entries(map).forEach(([id, value]) => {
            const el = document.getElementById(id);
            const valEl = document.getElementById(id.replace('pe', 'val'));
            if (el) {
                el.value = value;
                if (valEl) valEl.textContent = parseFloat(value).toFixed(1);
            }
        });
    }

    if (pePersonalityPreset) {
        pePersonalityPreset.addEventListener('change', () => {
            const val = pePersonalityPreset.value;
            if (val) {
                applyPreset(val);
            }
        });
    }

    traitSliders.forEach((id) => {
        const el = document.getElementById(id);
        if (!el) return;
        const valId = id.replace('pe', 'val');
        const valEl = document.getElementById(valId);
        el.addEventListener('input', () => {
            if (valEl) valEl.textContent = parseFloat(el.value).toFixed(1);
        });
    });

    async function loadPersona() {
        const name = personaSelect ? personaSelect.value : 'default';
        try {
            const res = await fetch(`/api/characters/${name}`, { headers: { 'X-API-Key': getApiKey() } });
            if (!res.ok) throw new Error('Failed to load');
            const data = await res.json();
            document.getElementById('peName').value = data.name || '';
            document.getElementById('peVersion').value = data.version || '';
            document.getElementById('peRelationship').value = data.relationship || '';
            document.getElementById('peBackstory').value = data.backstory || '';
            document.getElementById('peGoalPrimary').value = (data.goals && data.goals.primary) || '';
            document.getElementById('peGoalSecondary').value = (data.goals && Array.isArray(data.goals.secondary) ? data.goals.secondary.join('\n') : '');

            if (data.traits && data.traits.personality) {
                const t = data.traits.personality;
                const map = {
                    peOpenness: t.openness,
                    peConscientiousness: t.conscientiousness,
                    peExtraversion: t.extraversion,
                    peAgreeableness: t.agreeableness,
                    peNeuroticism: t.neuroticism,
                };
                Object.entries(map).forEach(([id, value]) => {
                    const el = document.getElementById(id);
                    const valEl = document.getElementById(id.replace('pe', 'val'));
                    if (el && value !== undefined) {
                        el.value = value;
                        if (valEl) valEl.textContent = parseFloat(value).toFixed(1);
                    }
                });
                if (pePersonalityPreset) pePersonalityPreset.value = '';
            }

            if (data.traits && data.traits.communication_style) {
                const c = data.traits.communication_style;
                const tone = document.getElementById('peTone');
                const verbosity = document.getElementById('peVerbosity');
                const empathy = document.getElementById('peEmpathy');
                const formality = document.getElementById('peFormality');
                if (tone && c.tone) tone.value = c.tone;
                if (verbosity && c.verbosity) verbosity.value = c.verbosity;
                if (empathy && c.empathy) empathy.value = c.empathy;
                if (formality && c.formality) formality.value = c.formality;
            }
        } catch (err) {
            showToast('加载失败');
        }
    }

    async function savePersona() {
        const name = personaSelect ? personaSelect.value : 'default';
        const payload = {
            name: document.getElementById('peName').value,
            version: document.getElementById('peVersion').value,
            relationship: document.getElementById('peRelationship').value,
            backstory: document.getElementById('peBackstory').value,
            goals: {
                primary: document.getElementById('peGoalPrimary').value,
                secondary: document.getElementById('peGoalSecondary').value.split('\n').filter((s) => s.trim()),
            },
            traits: {
                personality: {
                    openness: parseFloat(document.getElementById('peOpenness').value),
                    conscientiousness: parseFloat(document.getElementById('peConscientiousness').value),
                    extraversion: parseFloat(document.getElementById('peExtraversion').value),
                    agreeableness: parseFloat(document.getElementById('peAgreeableness').value),
                    neuroticism: parseFloat(document.getElementById('peNeuroticism').value),
                },
                communication_style: {
                    tone: document.getElementById('peTone').value,
                    verbosity: document.getElementById('peVerbosity').value,
                    empathy: document.getElementById('peEmpathy').value,
                    formality: document.getElementById('peFormality').value,
                },
            },
        };
        try {
            const res = await fetch(`/api/characters/${name}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'X-API-Key': getApiKey() },
                body: JSON.stringify(payload),
            });
            if (!res.ok) throw new Error('Failed to save');
            showToast('保存成功');
        } catch (err) {
            showToast('保存失败');
        }
    }

    if (personaLoadBtn) personaLoadBtn.addEventListener('click', loadPersona);
    if (personaSaveBtn) personaSaveBtn.addEventListener('click', savePersona);

    const memoryLoadGraph = document.getElementById('memoryLoadGraph');
    const memoryListContent = document.getElementById('memoryListContent');

    async function loadMemoryStats() {
        try {
            const res = await fetch('/api/memory/stats', { headers: { 'X-API-Key': getApiKey() } });
            if (!res.ok) throw new Error('Failed to load memory stats');
            const data = await res.json();

            const working = data.working || {};
            const episodic = data.episodic || {};
            const semantic = data.semantic || {};

            document.getElementById('statWorkingMem').textContent = working.exchanges !== undefined ? working.exchanges : 0;
            document.getElementById('statEpisodic').textContent = episodic.total_episodes !== undefined ? episodic.total_episodes : 0;
            document.getElementById('statSemantic').textContent = semantic.entities !== undefined ? semantic.entities : 0;

            const fusion = semantic.relations && semantic.entities
                ? Math.round((semantic.relations / Math.max(semantic.entities, 1)) * 100) + '%'
                : '0%';
            document.getElementById('statFusion').textContent = fusion;

            if (memoryListContent) {
                memoryListContent.innerHTML =
                    '<li class="memory-list-item"><span class="memory-list-label">工作记忆交换</span><span class="memory-list-value">' +
                    (working.exchanges !== undefined ? working.exchanges : 0) +
                    ' / ' +
                    (working.max_size !== undefined ? working.max_size : '--') +
                    '</span></li>' +
                    '<li class="memory-list-item"><span class="memory-list-label">情景记忆片段</span><span class="memory-list-value">' +
                    (episodic.total_episodes !== undefined ? episodic.total_episodes : 0) +
                    '</span></li>' +
                    '<li class="memory-list-item"><span class="memory-list-label">语义实体</span><span class="memory-list-value">' +
                    (semantic.entities !== undefined ? semantic.entities : 0) +
                    '</span></li>' +
                    '<li class="memory-list-item"><span class="memory-list-label">语义事实</span><span class="memory-list-value">' +
                    (semantic.facts !== undefined ? semantic.facts : 0) +
                    '</span></li>' +
                    '<li class="memory-list-item"><span class="memory-list-label">语义关系</span><span class="memory-list-value">' +
                    (semantic.relations !== undefined ? semantic.relations : 0) +
                    '</span></li>';
            }
        } catch (err) {
            showToast('加载记忆统计失败');
        }
    }

    if (memoryLoadGraph) {
        memoryLoadGraph.addEventListener('click', loadMemoryStats);
    }
})();
