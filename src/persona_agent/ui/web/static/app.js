(function () {
    const mobileMenuToggle = document.getElementById('mobileMenuToggle');
    const sidebar = document.getElementById('sidebar');
    const navItems = document.querySelectorAll('.nav-item');
    const pageTitle = document.querySelector('.page-header h1');
    const pageSubtitle = document.querySelector('.header-subtitle');

    const sectionTitles = {
        dashboard: { title: '控制台', subtitle: '管理和切换你的 AI 人格' },
        personas: { title: '人格管理', subtitle: '创建、编辑和配置你的 AI 人格' },
        chat: { title: '对话', subtitle: '与你的 AI 伙伴进行实时交流' },
        memory: { title: '记忆库', subtitle: '查看和管理跨会话记忆' },
        skills: { title: '技能中心', subtitle: '加载和配置 AI 技能扩展' },
        settings: { title: '设置', subtitle: '调整系统参数和偏好' },
    };

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
        const target = parseInt(el.textContent, 10);
        if (!isNaN(target)) {
            animateValue(el, 0, target, 800);
        }
    });

    function animateValue(element, start, end, duration) {
        const startTime = performance.now();
        function update(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const ease = 1 - Math.pow(1 - progress, 3);
            const current = Math.floor(start + (end - start) * ease);
            element.textContent = current;
            if (progress < 1) {
                requestAnimationFrame(update);
            }
        }
        requestAnimationFrame(update);
    }
})();
