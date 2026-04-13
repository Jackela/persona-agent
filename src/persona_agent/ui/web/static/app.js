(function () {
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
        skills: { title: '技能中心', subtitle: '加载和配置 AI 技能扩展' },
        settings: { title: '设置', subtitle: '调整系统参数和偏好' },
    };

    const sectionMap = {
        dashboard: 'dashboard',
        personas: 'persona-editor',
        chat: 'chat',
        memory: 'memory-viz',
        skills: 'skills',
        settings: 'settings',
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

    const chatSessionList = document.getElementById('chatSessionList');
    const chatThread = document.getElementById('chatThread');
    const chatInput = document.getElementById('chatInput');
    const chatSend = document.getElementById('chatSend');
    const chatTyping = document.getElementById('chatTyping');
    const chatNewSession = document.getElementById('chatNewSession');
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
        msg.innerHTML = `<div class="chat-avatar mood-joyful">温</div><div class="chat-bubble">${escapeHtml(text)}</div>`;
        chatThread.appendChild(msg);
        scrollToBottom();
    }

    async function sendMessage() {
        const text = chatInput.value.trim();
        if (!text || isWaiting) return;
        chatInput.value = '';
        addUserMessage(text);
        isWaiting = true;
        chatTyping.style.display = 'flex';
        scrollToBottom();

        try {
            const res = await fetch(`/api/sessions/${currentSessionId}/messages`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: text }),
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

    if (chatSend) chatSend.addEventListener('click', sendMessage);
    if (chatInput) {
        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') sendMessage();
        });
    }

    if (chatNewSession) {
        chatNewSession.addEventListener('click', async () => {
            try {
                const res = await fetch('/api/sessions', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
                const data = await res.json();
                const id = data.id || String(Date.now());
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
            const res = await fetch(`/api/characters/${name}`);
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
                headers: { 'Content-Type': 'application/json' },
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
    let cyInstance = null;

    function initCytoscape() {
        if (cyInstance) return cyInstance;
        const container = document.getElementById('memoryGraph');
        if (!container || typeof cytoscape === 'undefined') return null;
        cyInstance = cytoscape({
            container: container,
            style: [
                {
                    selector: 'node',
                    style: {
                        'background-color': '#525252',
                        'label': 'data(label)',
                        'color': '#fafafa',
                        'font-size': '12px',
                        'text-valign': 'center',
                        'text-halign': 'center',
                        'width': 36,
                        'height': 36,
                        'border-width': 2,
                        'border-color': '#0a0a0a',
                    },
                },
                {
                    selector: 'node[type="working"]',
                    style: { 'background-color': '#e07a5f' },
                },
                {
                    selector: 'node[type="episodic"]',
                    style: { 'background-color': '#f59e0b' },
                },
                {
                    selector: 'node[type="semantic"]',
                    style: { 'background-color': '#10b981' },
                },
                {
                    selector: 'node[type="fact"]',
                    style: { 'background-color': '#525252' },
                },
                {
                    selector: 'edge',
                    style: {
                        'width': 2,
                        'line-color': 'rgba(255,255,255,0.15)',
                        'target-arrow-color': 'rgba(255,255,255,0.15)',
                        'target-arrow-shape': 'triangle',
                        'curve-style': 'bezier',
                    },
                },
            ],
            layout: { name: 'grid', padding: 10 },
            wheelSensitivity: 0.3,
            minZoom: 0.2,
            maxZoom: 3,
        });
        return cyInstance;
    }

    if (memoryLoadGraph) {
        memoryLoadGraph.addEventListener('click', async () => {
            try {
                const res = await fetch('/api/memory/graph');
                const data = await res.json();
                const cy = initCytoscape();
                if (!cy) return;

                const nodes = (data.nodes || []).map((n) => ({
                    data: { id: n.id, label: n.label || n.id, type: n.type || 'fact' },
                }));
                const edges = (data.edges || []).map((e) => ({
                    data: { id: e.id || `${e.source}-${e.target}`, source: e.source, target: e.target },
                }));

                cy.elements().remove();
                cy.add([...nodes, ...edges]);
                cy.layout({ name: 'cose', padding: 20, animate: true, animationDuration: 500 }).run();

                document.getElementById('statWorkingMem').textContent = data.stats && data.stats.working !== undefined ? data.stats.working : nodes.filter((n) => n.data.type === 'working').length;
                document.getElementById('statEpisodic').textContent = data.stats && data.stats.episodic !== undefined ? data.stats.episodic : nodes.filter((n) => n.data.type === 'episodic').length;
                document.getElementById('statSemantic').textContent = data.stats && data.stats.semantic !== undefined ? data.stats.semantic : nodes.filter((n) => n.data.type === 'semantic').length;
                document.getElementById('statFusion').textContent = data.stats && data.stats.fusion !== undefined ? data.stats.fusion + '%' : '0%';
            } catch (err) {
                showToast('加载图谱失败');
            }
        });
    }
})();
