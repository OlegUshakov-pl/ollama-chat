/* Ollama Chat - new frontend (step b: sidebar + routing).
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
    openSidebar: 'Open sidebar',
    themeToggle: 'Toggle theme',
    noConversations: 'No conversations yet.',
    loading: 'Loading…',
    classicLink: 'Classic UI',
    chatMenu: 'Chat actions',
    menuRename: 'Rename',
    menuDownload: 'Download .md',
    menuDelete: 'Delete',
    renameTitle: 'Rename chat',
    renameLabel: 'Title',
    save: 'Save',
    cancel: 'Cancel',
    close: 'Close',
    deleteTitle: 'Delete chat',
    deleteConfirm: 'Delete this chat? This cannot be undone.',
    deleteButton: 'Delete',
    generating: 'Generating…',
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
    openMenuId: null,
    modal: null,
    sidebarCollapsed: false,
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

/** File name for the .md export (same rules as the classic UI). */
function buildMarkdownFilename(title) {
    let name = String(title || '').toLowerCase().replace(/['"]/g, '');
    name = name.replace(/[^a-z0-9]+/g, '-').replace(/^-/, '').replace(/-$/, '');
    return `${name || 'chat'}.md`;
}

/** Markdown export body: "# <title>", "**Model:** <model>", then "## User:"/"## Model:" per exchange. */
function buildMarkdownExport(conversation) {
    const parts = [`# ${conversation.title}`, '', `**Model:** ${conversation.model}`];
    for (const exchange of conversation.exchanges || []) {
        parts.push('', '## User:', '', exchange.user, '', '## Model:', '', exchange.model);
    }
    return parts.join('\n');
}

function downloadFile(filename, text) {
    const blob = new Blob([text], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function downloadChat(id) {
    const data = await apiGet('getConversation', `id=${encodeURIComponent(id)}`);
    const conversation = data.conversation;
    downloadFile(buildMarkdownFilename(conversation.title), buildMarkdownExport(conversation));
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

function chatTitle(id) {
    const conv = state.conversations.find((item) => item.id === id);
    return conv ? conv.title : id;
}

function renderChatItem(conv) {
    const active = state.route.name === 'chat' && state.route.id === conv.id ? ' active' : '';
    const menuOpen = state.openMenuId === conv.id ? ' menu-open' : '';
    const menu = state.openMenuId === conv.id
        ? `<div class="chat-menu" role="menu">` +
            `<button type="button" role="menuitem" data-action="rename" data-id="${escapeHtml(conv.id)}">${escapeHtml(STRINGS.menuRename)}</button>` +
            `<button type="button" role="menuitem" data-action="download" data-id="${escapeHtml(conv.id)}">${escapeHtml(STRINGS.menuDownload)}</button>` +
            `<button type="button" role="menuitem" class="danger" data-action="delete" data-id="${escapeHtml(conv.id)}">${escapeHtml(STRINGS.menuDelete)}</button>` +
            `</div>`
        : '';
    return `<div class="chat-item${active}${menuOpen}">` +
        `<a class="chat-link" href="#/c/${escapeHtml(conv.id)}" title="${escapeHtml(conv.title || conv.id)}">${escapeHtml(conv.title || conv.id)}</a>` +
        (conv.generating ? `<span class="gen-dot" title="${escapeHtml(STRINGS.generating)}" aria-label="${escapeHtml(STRINGS.generating)}"></span>` : '') +
        `<button type="button" class="icon-btn chat-menu-btn" data-action="menu" data-id="${escapeHtml(conv.id)}" ` +
        `title="${escapeHtml(STRINGS.chatMenu)}" aria-label="${escapeHtml(STRINGS.chatMenu)}" aria-haspopup="menu" aria-expanded="${state.openMenuId === conv.id}">${ICONS.dots}</button>` +
        menu +
        `</div>`;
}

function renderModal() {
    if (!modalState()) {
        return '';
    }
    const modal = modalState();
    if (modal.type === 'rename') {
        return `<div class="modal-overlay" id="modal-overlay">` +
            `<div class="modal" role="dialog" aria-modal="true" aria-label="${escapeHtml(STRINGS.renameTitle)}">` +
            `<h2>${escapeHtml(STRINGS.renameTitle)}</h2>` +
            (modal.error ? `<p class="modal-error" role="alert">${escapeHtml(modal.error)}</p>` : '') +
            `<label>${escapeHtml(STRINGS.renameLabel)}<input id="modal-input" type="text" value="${escapeHtml(modal.title)}" maxlength="200"></label>` +
            `<div class="modal-actions">` +
            `<button type="button" class="btn" data-action="modal-cancel">${escapeHtml(STRINGS.cancel)}</button>` +
            `<button type="button" class="btn btn-primary" data-action="modal-save">${escapeHtml(STRINGS.save)}</button>` +
            `</div></div></div>`;
    }
    return `<div class="modal-overlay" id="modal-overlay">` +
        `<div class="modal" role="dialog" aria-modal="true" aria-label="${escapeHtml(STRINGS.deleteTitle)}">` +
        `<h2>${escapeHtml(STRINGS.deleteTitle)}</h2>` +
        (modal.error ? `<p class="modal-error" role="alert">${escapeHtml(modal.error)}</p>` : '') +
        `<p>${escapeHtml(STRINGS.deleteConfirm)}</p>` +
        `<p class="modal-target">“${escapeHtml(modal.title)}”</p>` +
        `<div class="modal-actions">` +
        `<button type="button" class="btn" data-action="modal-cancel">${escapeHtml(STRINGS.cancel)}</button>` +
        `<button type="button" class="btn btn-danger" data-action="modal-confirm">${escapeHtml(STRINGS.deleteButton)}</button>` +
        `</div></div></div>`;
}

function modalState() {
    return state.modal;
}

function render() {
    const theme = currentTheme();
    if (state.route.name === 'chat') {
        document.title = `${chatTitle(state.route.id)} - ${STRINGS.appTitle}`;
    } else {
        document.title = STRINGS.appTitle;
    }
    const chats = state.conversations.map(renderChatItem).join('');

    root.innerHTML =
        `<div class="layout${state.sidebarCollapsed ? ' sidebar-collapsed' : ''}" id="layout">` +
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
        `<header class="topbar">` +
        `<button class="icon-btn" id="btn-sidebar-open" title="${escapeHtml(STRINGS.openSidebar)}" aria-label="${escapeHtml(STRINGS.openSidebar)}">${ICONS.panel}</button>` +
        `<span class="topbar-title">${escapeHtml(STRINGS.appTitle)}</span>` +
        `</header>` +
        (state.sidebarCollapsed ? `<button class="icon-btn sidebar-fab" id="btn-sidebar-fab" title="${escapeHtml(STRINGS.openSidebar)}" aria-label="${escapeHtml(STRINGS.openSidebar)}">${ICONS.panel}</button>` : '') +
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
        `</div>` +
        (state.openMenuId ? `<div class="overlay" id="menu-overlay"></div>` : '') +
        renderModal();

    document.getElementById('btn-sidebar').addEventListener('click', () => {
        state.sidebarCollapsed = true;
        state.openMenuId = null;
        render();
    });
    const fab = document.getElementById('btn-sidebar-fab');
    if (fab) {
        fab.addEventListener('click', () => {
            state.sidebarCollapsed = false;
            render();
        });
    }
    document.getElementById('btn-sidebar-open').addEventListener('click', () => {
        state.sidebarCollapsed = false;
        document.getElementById('layout').classList.add('sidebar-open');
    });
    document.getElementById('btn-theme').addEventListener('click', () => {
        const next = currentTheme() === 'dark' ? 'light' : 'dark';
        try {
            window.localStorage.setItem('ollama-chat-theme', next);
        } catch (err) { /* ignore */ }
        applyTheme(next);
        render();
    });
    root.querySelectorAll('[data-action="menu"]').forEach((button) => {
        button.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();
            state.openMenuId = state.openMenuId === button.dataset.id ? null : button.dataset.id;
            render();
        });
    });
    root.querySelectorAll('.chat-menu [data-action]').forEach((button) => {
        button.addEventListener('click', () => {
            handleMenuAction(button.dataset.action, button.dataset.id);
        });
    });
    const menuOverlay = document.getElementById('menu-overlay');
    if (menuOverlay) {
        menuOverlay.addEventListener('click', () => {
            state.openMenuId = null;
            render();
        });
    }
    const modalOverlay = document.getElementById('modal-overlay');
    if (modalOverlay) {
        modalOverlay.addEventListener('click', (event) => {
            if (event.target === modalOverlay) {
                state.modal = null;
                render();
            }
        });
    }
    const modalCancel = root.querySelector('[data-action="modal-cancel"]');
    if (modalCancel) {
        modalCancel.addEventListener('click', () => {
            state.modal = null;
            render();
        });
    }
    const modalSave = root.querySelector('[data-action="modal-save"]');
    if (modalSave) {
        modalSave.addEventListener('click', submitRename);
    }
    const modalConfirm = root.querySelector('[data-action="modal-confirm"]');
    if (modalConfirm) {
        modalConfirm.addEventListener('click', submitDelete);
    }
    const modalInput = document.getElementById('modal-input');
    if (modalInput) {
        modalInput.focus();
        modalInput.select();
        modalInput.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                submitRename();
            }
        });
    }
}

async function handleMenuAction(action, id) {
    if (action === 'rename') {
        state.openMenuId = null;
        state.modal = { type: 'rename', id, title: chatTitle(id), error: null };
        render();
    } else if (action === 'delete') {
        state.openMenuId = null;
        state.modal = { type: 'delete', id, title: chatTitle(id), error: null };
        render();
    } else if (action === 'download') {
        state.openMenuId = null;
        render();
        try {
            await downloadChat(id);
        } catch (err) {
            state.error = `${STRINGS.errorBannerPrefix}${err.message}`;
            render();
        }
    }
}

async function submitRename() {
    const input = document.getElementById('modal-input');
    const title = input ? input.value.trim() : '';
    if (!title) {
        return;
    }
    try {
        await apiPost('setConversationTitle', { id: state.modal.id, title });
        state.modal = null;
        await refreshConversations();
    } catch (err) {
        state.modal.error = err.message;
        render();
    }
}

async function submitDelete() {
    const id = state.modal.id;
    try {
        await apiPost('deleteConversation', { id });
        state.modal = null;
        if (state.route.name === 'chat' && state.route.id === id) {
            window.location.hash = '#/';
        }
        await refreshConversations();
    } catch (err) {
        state.modal.error = err.message;
        render();
    }
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
    state.openMenuId = null;
    state.modal = null;
    document.getElementById('layout')?.classList.remove('sidebar-open');
    render();
}

function onKeyDown(event) {
    if (event.key === 'Escape') {
        if (state.modal) {
            state.modal = null;
            render();
        } else if (state.openMenuId) {
            state.openMenuId = null;
            render();
        }
    }
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
    window.addEventListener('keydown', onKeyDown);
    render();
    refreshConversations();
}

init();

export { STRINGS, parseRoute, renderMarkdown, escapeHtml, apiGet, apiPost, buildMarkdownFilename, buildMarkdownExport };
