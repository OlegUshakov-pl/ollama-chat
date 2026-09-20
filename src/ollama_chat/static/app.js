/* Ollama Chat - new frontend (step a: shell + routing skeleton).
 * Plain JS, no framework, no CDN, works offline. Vendor globals:
 * window.marked (marked.umd) and window.DOMPurify (purify.min.js).
 */

const STRINGS = {
    appTitle: 'Ollama Chat',
    navChat: 'Chat',
    navNewChat: 'New chat',
    chatsHeading: 'Chats',
    greeting: 'How can I help you today?',
    composerPlaceholder: 'Send a message',
    errorBannerPrefix: 'Error: ',
    errorLoadConversations: 'Failed to load conversations.',
    errorLoadModels: 'Failed to load models.',
    sidebarToggle: 'Toggle sidebar',
    themeToggle: 'Toggle theme',
    noConversations: 'No conversations yet.',
    loading: 'Loading…',
    classicLink: 'Classic UI',
};

/** Inline SVG icons (contour style, 20px, stroke 1.75, currentColor). */
const ICONS = {
    panel: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"/><line x1="9" y1="4" x2="9" y2="20"/></svg>',
    newChat: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>',
    dots: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/></svg>',
    sun: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>',
    moon: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/></svg>',
};

const root = document.getElementById('app');

const state = {
    route: parseRoute(),
    conversations: [],
    error: null,
};

function parseRoute() {
    const hash = window.location.hash || '#/';
    const match = hash.match(/^#\/c\/([A-Za-z0-9-]+)/);
    if (match) {
        return { name: 'chat', id: match[1] };
    }
    return { name: 'new' };
}

async function apiGet(action, query) {
    const url = query ? `/${action}?${query}` : `/${action}`;
    const response = await fetch(url, { headers: { Accept: 'application/json' } });
    const data = await response.json();
    if (!response.ok || data.error) {
        throw new Error(data.message || data.error || `GET ${action} failed (${response.status})`);
    }
    return data;
}

async function apiPost(action, body) {
    const response = await fetch(`/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(body || {}),
    });
    const data = await response.json();
    if (!response.ok || data.error) {
        throw new Error(data.message || data.error || `POST ${action} failed (${response.status})`);
    }
    return data;
}

/** Escape user text (never innerHTML user text without escaping). */
function escapeHtml(text) {
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

/** Render model markdown safely (marked + DOMPurify). Full polish in step (d). */
function renderMarkdown(markdownText) {
    const raw = window.marked ? window.marked.parse(String(markdownText || '')) : escapeHtml(markdownText);
    return window.DOMPurify ? window.DOMPurify.sanitize(raw) : escapeHtml(raw);
}

function applyTheme(theme) {
    if (theme) {
        document.documentElement.setAttribute('data-theme', theme);
    } else {
        document.documentElement.removeAttribute('data-theme');
    }
}

function currentTheme() {
    return document.documentElement.getAttribute('data-theme')
        || (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
}

function render() {
    document.title = STRINGS.appTitle;
    const theme = currentTheme();
    const chats = state.conversations.map((conv) => {
        const active = state.route.name === 'chat' && state.route.id === conv.id ? ' active' : '';
        return `<a class="nav-item${active}" href="#/c/${escapeHtml(conv.id)}">` +
            `<span>${escapeHtml(conv.title || conv.id)}</span></a>`;
    }).join('');

    root.innerHTML =
        `<div class="layout" id="layout">` +
        `<aside class="sidebar" aria-label="${escapeHtml(STRINGS.chatsHeading)}">` +
        `<div class="sidebar-toolbar">` +
        `<button class="icon-btn" id="btn-sidebar" title="${escapeHtml(STRINGS.sidebarToggle)}" aria-label="${escapeHtml(STRINGS.sidebarToggle)}">${ICONS.panel}</button>` +
        `<button class="icon-btn" id="btn-theme" title="${escapeHtml(STRINGS.themeToggle)}" aria-label="${escapeHtml(STRINGS.themeToggle)}">${theme === 'dark' ? ICONS.sun : ICONS.moon}</button>` +
        `</div>` +
        `<nav class="nav-list">` +
        `<a class="nav-item${state.route.name === 'new' ? ' active' : ''}" href="#/">${ICONS.newChat}<span>${escapeHtml(STRINGS.navChat)}</span></a>` +
        `</nav>` +
        `<p class="chat-list-title">${escapeHtml(STRINGS.chatsHeading)}</p>` +
        `<div class="chat-list" id="chat-list">${chats || `<p class="chat-list-title">${escapeHtml(STRINGS.noConversations)}</p>`}</div>` +
        `<a class="nav-item" href="/classic.html">${escapeHtml(STRINGS.classicLink)}</a>` +
        `</aside>` +
        `<main class="main">` +
        `<div class="messages"><div class="messages-inner" id="messages">` +
        (state.error ? `<div class="error-banner" role="alert">${escapeHtml(STRINGS.errorBannerPrefix)}${escapeHtml(state.error)}</div>` : '') +
        (state.route.name === 'new'
            ? `<p>${escapeHtml(STRINGS.greeting)}</p>`
            : `<p>${escapeHtml(STRINGS.loading)}</p>`) +
        `</div></div>` +
        `<div class="composer-wrap"><div class="composer">` +
        `<textarea rows="1" placeholder="${escapeHtml(STRINGS.composerPlaceholder)}" aria-label="${escapeHtml(STRINGS.composerPlaceholder)}" disabled></textarea>` +
        `</div></div>` +
        `</main>` +
        `</div>`;

    document.getElementById('btn-sidebar').addEventListener('click', () => {
        document.getElementById('layout').classList.toggle('sidebar-open');
    });
    document.getElementById('btn-theme').addEventListener('click', () => {
        const next = currentTheme() === 'dark' ? 'light' : 'dark';
        try {
            window.localStorage.setItem('ollama-chat-theme', next);
        } catch (err) { /* ignore */ }
        applyTheme(next);
        render();
    });
}

async function refreshConversations() {
    try {
        const data = await apiGet('getConversations');
        state.conversations = data.conversations || [];
        state.error = null;
    } catch (err) {
        state.error = `${STRINGS.errorLoadConversations} ${err.message}`;
    }
    render();
}

function onHashChange() {
    state.route = parseRoute();
    document.getElementById('layout')?.classList.remove('sidebar-open');
    render();
}

function init() {
    let saved = null;
    try {
        saved = window.localStorage.getItem('ollama-chat-theme');
    } catch (err) { /* ignore */ }
    if (saved === 'light' || saved === 'dark') {
        applyTheme(saved);
    }
    window.addEventListener('hashchange', onHashChange);
    render();
    refreshConversations();
}

init();

export { STRINGS, parseRoute, renderMarkdown, escapeHtml, apiGet, apiPost };
