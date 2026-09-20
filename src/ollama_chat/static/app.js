/* Ollama Chat - new frontend (step c: chat view + polling).
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
    errorLoadConversation: 'Failed to load the chat.',
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
    thinkingNow: 'Thinking…',
    thoughtDone: 'Thought',
    retry: 'Retry',
    backToChats: 'Back to chats',
};

/** Inline SVG icons (contour style, 20px, stroke 1.75, currentColor). */
const ICONS = {
    panel: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"/><line x1="9" y1="4" x2="9" y2="20"/></svg>',
    newChat: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>',
    dots: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/></svg>',
    sun: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>',
    moon: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/></svg>',
};

/** Poll interval (ms) while a response is generating. */
const POLL_MS = 400;

/** Distance (px) from the bottom that still counts as "at the bottom" for autoscroll. */
const SCROLL_STICK_PX = 80;

const root = document.getElementById('app');

const state = {
    route: parseRoute(),
    conversations: [],
    error: null,
    openMenuId: null,
    modal: null,
    sidebarCollapsed: false,
    current: null,
    pollTimer: null,
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

function messagesBox() {
    return document.querySelector('.messages');
}

function scrollMessagesToBottom() {
    const box = messagesBox();
    if (box) {
        box.scrollTop = box.scrollHeight;
    }
}

function isNearBottom(box) {
    return box.scrollHeight - box.scrollTop - box.clientHeight <= SCROLL_STICK_PX;
}

/** Re-render only the messages region (keeps focus, menu and modal intact during polling). */
function patchMessages() {
    const inner = document.getElementById('messages');
    if (!inner) {
        return;
    }
    const box = messagesBox();
    const stick = box ? isNearBottom(box) : true;
    inner.innerHTML = buildMessagesHtml();
    if (stick) {
        scrollMessagesToBottom();
    }
}

/** Re-render only the sidebar list (skipped while a chat menu is open). */
function patchSidebarList() {
    if (state.openMenuId) {
        return;
    }
    const list = document.getElementById('chat-list');
    if (list) {
        list.innerHTML = buildSidebarListHtml();
    }
}

function renderExchange(exchange, isLast, generating) {
    let html = `<div class="msg msg-user"><div class="bubble">${escapeHtml(exchange.user)}</div></div>`;
    if (exchange.thinking) {
        const open = generating && isLast ? ' open' : '';
        const label = generating && isLast ? STRINGS.thinkingNow : STRINGS.thoughtDone;
        html += `<details class="thinking"${open}><summary>${escapeHtml(label)}</summary>` +
            `<div class="md">${renderMarkdown(exchange.thinking)}</div></details>`;
    }
    if (exchange.model) {
        html += `<div class="msg msg-model"><div class="md">${renderMarkdown(exchange.model)}</div></div>`;
    } else if (generating && isLast) {
        html += `<div class="msg msg-model"><span class="typing" aria-label="${escapeHtml(STRINGS.generating)}">…</span></div>`;
    }
    return html;
}

function buildMessagesHtml() {
    if (state.route.name === 'new') {
        return (state.error ? `<div class="error-banner" role="alert">${escapeHtml(STRINGS.errorBannerPrefix)}${escapeHtml(state.error)}</div>` : '') +
            `<p>${escapeHtml(STRINGS.greeting)}</p>`;
    }
    const cur = state.current;
    let html = '';
    if (state.error) {
        html += `<div class="error-banner" role="alert">${escapeHtml(STRINGS.errorBannerPrefix)}${escapeHtml(state.error)}</div>`;
    }
    if (!cur || cur.loading) {
        return `${html}<p>${escapeHtml(STRINGS.loading)}</p>`;
    }
    if (cur.error && !cur.conversation) {
        return `${html}<div class="error-banner" role="alert">${escapeHtml(STRINGS.errorBannerPrefix)}${escapeHtml(cur.error)}</div>` +
            `<p><a class="back-link" href="#/">${escapeHtml(STRINGS.backToChats)}</a> ` +
            `<button type="button" class="btn" data-action="retry">${escapeHtml(STRINGS.retry)}</button></p>`;
    }
    if (cur.error) {
        html += `<div class="error-banner" role="alert">${escapeHtml(STRINGS.errorBannerPrefix)}${escapeHtml(cur.error)}</div>`;
    }
    const exchanges = cur.conversation.exchanges || [];
    exchanges.forEach((exchange, index) => {
        html += renderExchange(exchange, index === exchanges.length - 1, cur.generating);
    });
    return html;
}

function buildSidebarListHtml() {
    if (!state.conversations.length) {
        return `<p class="chat-list-title">${escapeHtml(STRINGS.noConversations)}</p>`;
    }
    return state.conversations.map(renderChatItem).join('');
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
    if (!state.modal) {
        return '';
    }
    const modal = state.modal;
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

function render() {
    const theme = currentTheme();
    if (state.route.name === 'chat') {
        document.title = `${chatTitle(state.route.id)} - ${STRINGS.appTitle}`;
    } else {
        document.title = STRINGS.appTitle;
    }

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
        `<div class="chat-list" id="chat-list">${buildSidebarListHtml()}</div>` +
        `<a class="nav-item" href="/classic.html">${escapeHtml(STRINGS.classicLink)}</a>` +
        `</aside>` +
        `<main class="main">` +
        `<header class="topbar">` +
        `<button class="icon-btn" id="btn-sidebar-open" title="${escapeHtml(STRINGS.openSidebar)}" aria-label="${escapeHtml(STRINGS.openSidebar)}">${ICONS.panel}</button>` +
        `<span class="topbar-title">${escapeHtml(STRINGS.appTitle)}</span>` +
        `</header>` +
        (state.sidebarCollapsed ? `<button class="icon-btn sidebar-fab" id="btn-sidebar-fab" title="${escapeHtml(STRINGS.openSidebar)}" aria-label="${escapeHtml(STRINGS.openSidebar)}">${ICONS.panel}</button>` : '') +
        `<div class="messages"><div class="messages-inner" id="messages">${buildMessagesHtml()}</div></div>` +
        `<div class="composer-wrap"><div class="composer">` +
        `<textarea rows="1" placeholder="${escapeHtml(STRINGS.composerPlaceholder)}" aria-label="${escapeHtml(STRINGS.composerPlaceholder)}" disabled></textarea>` +
        `</div></div>` +
        `</main>` +
        `</div>` +
        (state.openMenuId ? `<div class="overlay" id="menu-overlay"></div>` : '') +
        renderModal();

    const modalInput = document.getElementById('modal-input');
    if (modalInput) {
        modalInput.focus();
        modalInput.select();
    }
}

function stopPolling() {
    if (state.pollTimer) {
        clearTimeout(state.pollTimer);
        state.pollTimer = null;
    }
}

function schedulePoll() {
    stopPolling();
    state.pollTimer = setTimeout(pollTick, POLL_MS);
}

async function loadConversation(id) {
    stopPolling();
    state.current = { id, loading: true, error: null, conversation: null, generating: false };
    render();
    scrollMessagesToBottom();
    try {
        const data = await apiGet('getConversation', `id=${encodeURIComponent(id)}`);
        if (!state.current || state.current.id !== id) {
            return;
        }
        state.current.loading = false;
        state.current.conversation = data.conversation;
        state.current.generating = Boolean(data.conversation.generating);
        render();
        scrollMessagesToBottom();
        if (state.current.generating) {
            schedulePoll();
        }
    } catch (err) {
        if (!state.current || state.current.id !== id) {
            return;
        }
        state.current.loading = false;
        state.current.error = err.message;
        render();
    }
}

async function pollTick() {
    state.pollTimer = null;
    const cur = state.current;
    if (!cur || state.route.name !== 'chat' || state.route.id !== cur.id) {
        return;
    }
    try {
        const data = await apiGet('getConversation', `id=${encodeURIComponent(cur.id)}`);
        if (!state.current || state.current.id !== cur.id) {
            return;
        }
        const wasGenerating = cur.generating;
        cur.conversation = data.conversation;
        cur.generating = Boolean(data.conversation.generating);
        cur.error = null;
        patchMessages();
        patchSidebarList();
        if (cur.generating) {
            schedulePoll();
        } else if (wasGenerating) {
            await refreshConversations();
        }
    } catch (err) {
        cur.error = err.message;
        patchMessages();
        schedulePoll();
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
    stopPolling();
    state.route = parseRoute();
    state.openMenuId = null;
    state.modal = null;
    state.current = null;
    document.getElementById('layout')?.classList.remove('sidebar-open');
    render();
    if (state.route.name === 'chat') {
        loadConversation(state.route.id);
    }
}

/** Single delegated click handler (survives messages/sidebar patches during polling). */
function onRootClick(event) {
    const actionButton = event.target.closest ? event.target.closest('[data-action]') : null;
    if (actionButton) {
        const { action, id } = actionButton.dataset;
        if (action === 'menu') {
            event.preventDefault();
            event.stopPropagation();
            state.openMenuId = state.openMenuId === id ? null : id;
            render();
        } else if (action === 'rename' || action === 'delete' || action === 'download') {
            handleMenuAction(action, id);
        } else if (action === 'modal-cancel') {
            state.modal = null;
            render();
        } else if (action === 'modal-save') {
            submitRename();
        } else if (action === 'modal-confirm') {
            submitDelete();
        } else if (action === 'retry' && state.route.name === 'chat') {
            loadConversation(state.route.id);
        }
        return;
    }
    if (event.target.id === 'menu-overlay') {
        state.openMenuId = null;
        render();
        return;
    }
    if (event.target.id === 'modal-overlay') {
        state.modal = null;
        render();
        return;
    }
    const button = event.target.closest ? event.target.closest('#btn-sidebar,#btn-sidebar-open,#btn-sidebar-fab,#btn-theme') : null;
    if (button) {
        if (button.id === 'btn-sidebar') {
            state.sidebarCollapsed = true;
            state.openMenuId = null;
            render();
        } else if (button.id === 'btn-sidebar-open') {
            state.sidebarCollapsed = false;
            document.getElementById('layout').classList.add('sidebar-open');
        } else if (button.id === 'btn-sidebar-fab') {
            state.sidebarCollapsed = false;
            render();
        } else if (button.id === 'btn-theme') {
            const next = currentTheme() === 'dark' ? 'light' : 'dark';
            try {
                window.localStorage.setItem('ollama-chat-theme', next);
            } catch (err) { /* ignore */ }
            applyTheme(next);
            render();
        }
    }
}

function onRootKeyDown(event) {
    if (event.key === 'Enter' && event.target && event.target.id === 'modal-input') {
        submitRename();
    }
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
    root.addEventListener('click', onRootClick);
    root.addEventListener('keydown', onRootKeyDown);
    render();
    refreshConversations();
    if (state.route.name === 'chat') {
        loadConversation(state.route.id);
    }
}

init();

export { STRINGS, parseRoute, renderMarkdown, escapeHtml, apiGet, apiPost, buildMarkdownFilename, buildMarkdownExport };
