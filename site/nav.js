(() => {
  const cache = new Map();
  const pages = [
    { url: './index.html', title: 'STOI — Shit Token On Investment', label: '首页' },
    { url: './docs.html', title: 'STOI 原理 — 文档', label: '分析原理' },
    { url: './cli.html', title: 'STOI CLI 参考', label: 'CLI 参考' },
  ];

  const isLocal = location.protocol === 'file:';

  function normalizeUrl(url) {
    try {
      const u = new URL(url, location.href);
      return u.pathname.split('/').pop() || './index.html';
    } catch {
      return url;
    }
  }

  function getPageName(url) {
    return normalizeUrl(url);
  }

  function findPage(url) {
    const name = getPageName(url);
    return pages.find(p => getPageName(p.url) === name) || pages[0];
  }

  function updateActiveSidebar(url) {
    const name = getPageName(url);
    document.querySelectorAll('.sidebar-link').forEach(el => {
      el.classList.toggle('is-active', getPageName(el.getAttribute('href')) === name);
    });
  }

  async function fetchPage(url) {
    const key = getPageName(url);
    if (cache.has(key)) return cache.get(key);
    const res = await fetch(url, { headers: { 'X-Requested-With': 'PJAX' } });
    const text = await res.text();
    cache.set(key, text);
    return text;
  }

  function extractContent(html) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    const root = doc.getElementById('content-root');
    const title = doc.querySelector('title')?.textContent || '';
    return { html: root ? root.innerHTML : doc.body.innerHTML, title };
  }

  async function navigateTo(url, push = true) {
    const root = document.getElementById('content-root');
    if (!root) return;

    root.classList.add('is-exiting');
    await new Promise(r => setTimeout(r, 180));

    try {
      const html = await fetchPage(url);
      const extracted = extractContent(html);
      root.innerHTML = extracted.html;
      if (extracted.title) document.title = extracted.title;
      if (push && !isLocal) history.pushState({}, '', url);
      updateActiveSidebar(url);
      window.scrollTo({ top: 0, behavior: 'instant' });
    } catch (e) {
      location.assign(url);
      return;
    }

    root.classList.remove('is-exiting');
    root.classList.add('is-entering');
    requestAnimationFrame(() => {
      requestAnimationFrame(() => root.classList.remove('is-entering'));
    });
    initScrollReveal();
    initBurnCounter();
    initHeroParallax();
  }

  function prefetch(url) {
    const key = getPageName(url);
    if (cache.has(key)) return;
    fetch(url).then(r => r.text()).then(t => cache.set(key, t)).catch(() => {});
  }

  function bindPjax() {
    document.addEventListener('click', (e) => {
      const a = e.target.closest('a[data-pjax]');
      if (!a) return;
      const href = a.getAttribute('href');
      if (!href || href.startsWith('http')) return;
      if (isLocal) return; // file:// protocol blocks fetch; let browser handle navigation
      e.preventDefault();
      navigateTo(href);
    });

    document.addEventListener('mouseover', (e) => {
      const a = e.target.closest('a[data-pjax]');
      if (!a) return;
      const href = a.getAttribute('href');
      if (href && !href.startsWith('http') && !isLocal) prefetch(href);
    });

    window.addEventListener('popstate', () => {
      if (isLocal) return;
      navigateTo(location.pathname.split('/').pop() || './index.html', false);
    });
  }

  function bindMobileMenu() {
    const btn = document.getElementById('mobile-menu-btn');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    if (!btn || !sidebar || !overlay) return;

    const open = () => {
      sidebar.classList.add('is-open');
      overlay.classList.add('is-visible');
      btn.setAttribute('aria-expanded', 'true');
    };
    const close = () => {
      sidebar.classList.remove('is-open');
      overlay.classList.remove('is-visible');
      btn.setAttribute('aria-expanded', 'false');
    };

    btn.addEventListener('click', () => {
      sidebar.classList.contains('is-open') ? close() : open();
    });
    overlay.addEventListener('click', close);
    sidebar.querySelectorAll('a').forEach(link => link.addEventListener('click', close));
  }

  function bindSearch() {
    const modal = document.getElementById('search-modal');
    const input = document.getElementById('search-input');
    const results = document.getElementById('search-results');
    const trigger = document.getElementById('search-trigger');
    if (!modal || !input || !results) return;

    const open = () => {
      modal.classList.add('is-open');
      input.focus();
      renderResults(input.value.trim());
    };
    const close = () => {
      modal.classList.remove('is-open');
      input.value = '';
    };

    trigger?.addEventListener('click', open);
    document.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        open();
      }
      if (e.key === 'Escape') close();
    });
    modal.addEventListener('click', (e) => {
      if (e.target === modal) close();
    });

    function renderResults(query) {
      if (!query) {
        results.innerHTML = pages.map(p => `<a class="search-result-item" href="${p.url}" data-pjax>${p.label}</a>`).join('');
        return;
      }
      const q = query.toLowerCase();
      const filtered = pages.filter(p => p.label.toLowerCase().includes(q) || p.title.toLowerCase().includes(q));
      if (!filtered.length) {
        results.innerHTML = '<div class="search-empty">No results found</div>';
        return;
      }
      results.innerHTML = filtered.map(p => `<a class="search-result-item" href="${p.url}" data-pjax>${p.label} <span style="color:var(--text-muted);margin-left:6px;font-size:0.8rem">${p.title}</span></a>`).join('');
    }

    input.addEventListener('input', (e) => renderResults(e.target.value.trim()));
  }

  // ── Theme Toggle ─────────────────────────────────────────────────────────
  function setThemeIcon(theme) {
    document.querySelectorAll('.theme-toggle').forEach(toggle => {
      const moon = toggle.querySelector('.moon');
      const sun = toggle.querySelector('.sun');
      if (moon) moon.style.display = theme === 'dark' ? 'block' : 'none';
      if (sun) sun.style.display = theme === 'dark' ? 'none' : 'block';
    });
  }

  function initThemeToggle() {
    const saved = localStorage.getItem('theme');
    const theme = saved || 'light';
    document.documentElement.setAttribute('data-theme', theme);
    setThemeIcon(theme);

    document.querySelectorAll('.theme-toggle').forEach(toggle => {
      toggle.addEventListener('click', () => {
        const current = document.documentElement.getAttribute('data-theme') || 'light';
        const next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('theme', next);
        setThemeIcon(next);
      });
    });
  }

  // ── Scroll Reveal ────────────────────────────────────────────────────────
  function initScrollReveal() {
    const reveals = document.querySelectorAll('.reveal');
    if (!reveals.length) return;
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -60px 0px' });
    reveals.forEach(el => observer.observe(el));
  }

  // ── Burn Counter Animation ───────────────────────────────────────────────
  function initBurnCounter() {
    const counter = document.querySelector('.burn-number');
    if (!counter) return;
    const target = parseInt(counter.dataset.target || '0', 10);
    let started = false;
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting && !started) {
          started = true;
          animateNumber(counter, target, 1200);
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.4 });
    observer.observe(counter);
  }

  function animateNumber(el, target, duration) {
    const start = performance.now();
    function step(now) {
      const progress = Math.min((now - start) / duration, 1);
      const ease = 1 - Math.pow(1 - progress, 4);
      el.textContent = Math.floor(ease * target);
      if (progress < 1) requestAnimationFrame(step);
      else el.textContent = target;
    }
    requestAnimationFrame(step);
  }

  // ── Hero Poster Parallax on Mouse Move (desktop) ─────────────────────────
  function initHeroParallax() {
    const visual = document.querySelector('.hero-visual');
    if (!visual || window.matchMedia('(pointer: coarse)').matches) return;
    const img = visual.querySelector('img');
    if (!img) return;
    let rafId = null;
    let targetX = 0, targetY = 0;
    let currentX = 0, currentY = 0;

    visual.addEventListener('mousemove', (e) => {
      const rect = visual.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width - 0.5;
      const y = (e.clientY - rect.top) / rect.height - 0.5;
      targetX = x * 8;
      targetY = y * -6;
      if (!rafId) rafId = requestAnimationFrame(tick);
    });

    visual.addEventListener('mouseleave', () => {
      targetX = 0;
      targetY = 0;
      if (!rafId) rafId = requestAnimationFrame(tick);
    });

    function tick() {
      currentX += (targetX - currentX) * 0.1;
      currentY += (targetY - currentY) * 0.1;
      img.style.transform = `rotateY(${currentX}deg) rotateX(${currentY}deg) scale(1.02)`;
      if (Math.abs(targetX - currentX) < 0.05 && Math.abs(targetY - currentY) < 0.05) {
        rafId = null;
        return;
      }
      rafId = requestAnimationFrame(tick);
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    bindPjax();
    bindMobileMenu();
    bindSearch();
    initThemeToggle();
    initScrollReveal();
    initBurnCounter();
    initHeroParallax();
    updateActiveSidebar(location.pathname.split('/').pop() || './index.html');
  });
})();
