/* Ollama Chat - new frontend (step d: composer + model picker).
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
    errorNoModel: 'No model selected. Download a model first.',
    errorSend: 'Failed to send the message.',
    sidebarToggle: 'Toggle sidebar',
    openSidebar: 'Open sidebar',
    themeToggle: 'Toggle theme',
    noConversations: 'No conversations yet.',
    loading: 'Loading…',
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
    sendLabel: 'Send',
    stopLabel: 'Stop',
    modelLabel: 'Model',
    selectModel: 'Select model',
    noModels: 'No models',
    copyLabel: 'Copy',
    copiedLabel: 'Copied',
    regenerateLabel: 'Regenerate',
    deleteResponseLabel: 'Delete response',
    codeLabel: 'code',
    thinkingOn: 'Thinking on',
    thinkingOff: 'Thinking off',
    uploadFile: 'Upload file',
};

/** Inline SVG icons (contour style, 20px, stroke 1.75, currentColor). */
const ICONS = {
    panel: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"/><line x1="9" y1="4" x2="9" y2="20"/></svg>',
    newChat: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>',
    dots: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/></svg>',
    sun: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>',
    moon: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/></svg>',
    up: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5"/><path d="m5 12 7-7 7 7"/></svg>',
    stop: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="7" y="7" width="10" height="10" rx="1.5"/></svg>',
    chevron: '<svg class="icon icon-small" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>',
    bulb: '<svg class="icon icon-small" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 18h6"/><path d="M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.4 1 2.3h6c0-.9.4-1.8 1-2.3A7 7 0 0 0 12 2Z"/></svg>',
    copy: '<svg class="icon icon-small" viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>',
    check: '<svg class="icon icon-small" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>',
    refresh: '<svg class="icon icon-small" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12a9 9 0 0 1 15.5-6.2L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15.5 6.2L3 16"/><path d="M3 21v-5h5"/></svg>',
    trash: '<svg class="icon icon-small" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18"/><path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/></svg>',
    download: '<svg class="icon icon-small" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/></svg>',
    paw: '<svg class="icon icon-small" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="10" r="5"/><path d="M8 21v-1a4 4 0 0 1 4-4 4 4 0 0 1 4 4v1"/><path d="M16 7.5V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2.5"/><path d="M4 11.5V9a6 6 0 0 1 6-6h0a6 6 0 0 1 6 6v2.5"/></svg>',
    pawOff: '<svg class="icon icon-small" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="10" r="5"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="4" y1="7" x2="20" y2="23"/><path d="M16 7.5V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2.5"/></svg>',
    upload: '<svg class="icon icon-small" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>',
};

/** Poll interval (ms) while a response is generating. */
const POLL_MS = 400;

/** Distance (px) from the bottom that still counts as "at the bottom" for autoscroll. */
const SCROLL_STICK_PX = 80;

const root = document.getElementById('app');

let uploadFiles = [];

const state = {
    route: parseRoute(),
    conversations: [],
    error: null,
    openMenuId: null,
    modal: null,
    sidebarCollapsed: false,
    current: null,
    pollTimer: null,
    models: null,
    selectedModel: null,
    modelMenuOpen: false,
    drafts: {},
    composerFocus: false,
    sending: false,
    thinkingOpen: {},
    thinkingEnabled: loadThinkingEnabled(),
    uploading: false,
};

function loadThinkingEnabled() {
    try {
        return window.localStorage.getItem('ollama-chat-thinking') === 'true';
    } catch (err) { return true; }
}

function saveThinkingEnabled(val) {
    try { window.localStorage.setItem('ollama-chat-thinking', String(val)); } catch (err) { /* ignore */ }
}

function readFilesAsData(files) {
    const results = [];
    for (const file of files) {
        const ext = file.name.split('.').pop().toLowerCase();
        const allowed = ['txt', 'md', 'docx', 'png', 'jpg', 'jpeg'];
        if (!allowed.includes(ext)) continue;
        results.push(new Promise((resolve) => {
            const reader = new FileReader();
            reader.onload = () => {
                let data;
                if (['png', 'jpg', 'jpeg'].includes(ext)) {
                    const base64 = reader.result.split(',')[1] || reader.result;
                    data = base64;
                } else {
                    data = reader.result;
                }
                resolve({ name: file.name, type: file.type || `application/${ext === 'docx' ? 'vnd.openxmlformats-officedocument.wordprocessingml.document' : ext === 'md' ? 'markdown' : ext === 'txt' ? 'plaintext' : ext === 'png' ? 'png' : 'jpeg'}`, data });
            };
            reader.onerror = () => resolve(null);
            if (['png', 'jpg', 'jpeg'].includes(ext)) {
                reader.readAsDataURL(file);
            } else {
                reader.readAsText(file);
            }
        }));
    }
    return Promise.all(results).then((items) => items.filter(Boolean));
}

function parseRoute() {
    const hash = window.location.hash || '#/';
    const match = hash.match(/^#\/c\/([A-Za-z0-9-]+)/);
    if (match) {
        return { name: 'chat', id: match[1] };
    }
    return { name: 'new' };
}

function draftKey() {
    return state.route.name === 'chat' ? `c:${state.route.id}` : 'new';
}

function getDraft() {
    return state.drafts[draftKey()] || '';
}

function setDraft(text) {
    state.drafts[draftKey()] = text;
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

/** File name for the .md export (letters, digits and dashes, like before). */
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

async function downloadCurrentChat() {
    if (state.route.name !== 'chat') {
        return;
    }
    try {
        await downloadChat(state.route.id);
    } catch (err) {
        state.error = `${STRINGS.errorBannerPrefix}${err.message}`;
        render();
    }
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

/** Model shown in the composer: the open chat's model (read-only) or the selected model. */
function composerModel() {
    if (state.route.name === 'chat' && state.current && state.current.conversation) {
        return state.current.conversation.model;
    }
    return state.selectedModel;
}

function isGenerating() {
    return Boolean(state.current && state.current.generating && state.route.name === 'chat');
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
    enhanceCodeBlocks(inner);
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

function isThinkingOpen(ix, isLast, generating) {
    if (Object.prototype.hasOwnProperty.call(state.thinkingOpen, ix)) {
        return state.thinkingOpen[ix];
    }
    return isLast && generating;
}

function renderThinking(exchange, ix, isLast, generating) {
    const open = isThinkingOpen(ix, isLast, generating);
    const label = generating && isLast ? STRINGS.thinkingNow : STRINGS.thoughtDone;
    return `<div class="thinking">` +
        `<button type="button" class="thinking-head" data-action="thinking" data-ix="${ix}" aria-expanded="${open}">` +
        `${ICONS.bulb}<span>${escapeHtml(label)}</span>${ICONS.chevron}</button>` +
        `<div class="thinking-body md"${open ? '' : ' hidden'}>${renderMarkdown(exchange.thinking)}</div>` +
        `</div>`;
}

function renderActions(ix, isLast, generating) {
    let html = `<div class="msg-actions">` +
        `<button type="button" class="action-btn" data-action="copy" data-ix="${ix}" ` +
        `title="${escapeHtml(STRINGS.copyLabel)}" aria-label="${escapeHtml(STRINGS.copyLabel)}">${ICONS.copy}</button>`;
    if (isLast && !generating) {
        html += `<button type="button" class="action-btn" data-action="regenerate" ` +
            `title="${escapeHtml(STRINGS.regenerateLabel)}" aria-label="${escapeHtml(STRINGS.regenerateLabel)}">${ICONS.refresh}</button>` +
            `<button type="button" class="action-btn" data-action="delete-exchange" ` +
            `title="${escapeHtml(STRINGS.deleteResponseLabel)}" aria-label="${escapeHtml(STRINGS.deleteResponseLabel)}">${ICONS.trash}</button>`;
    }
    return `${html}</div>`;
}

function renderExchange(exchange, ix, isLast, generating) {
    let html = `<div class="msg msg-user"><div class="bubble">${escapeHtml(exchange.user)}</div></div>`;
    if (exchange.thinking) {
        html += renderThinking(exchange, ix, isLast, generating);
    }
    if (exchange.model) {
        html += `<div class="msg msg-model"><div class="md">${renderMarkdown(exchange.model)}</div>` +
            renderActions(ix, isLast, generating) + `</div>`;
    } else if (generating && isLast) {
        html += `<div class="msg msg-model"><span class="typing" aria-label="${escapeHtml(STRINGS.generating)}">…</span></div>`;
    }
    return html;
}

/** Wrap rendered <pre> blocks with a language label + copy button (DOM APIs only, no innerHTML). */
function enhanceCodeBlocks(container) {
    if (!container || !container.querySelectorAll || !document.createElement) {
        return;
    }
    const pres = container.querySelectorAll('pre');
    pres.forEach((pre) => {
        if (pre.parentNode && pre.parentNode.classList && pre.parentNode.classList.contains('codeblock')) {
            return;
        }
        const code = pre.querySelector ? pre.querySelector('code') : null;
        let lang = '';
        if (code && code.className) {
            const match = code.className.match(/language-([\w+-]+)/);
            if (match) {
                lang = match[1];
            }
        }
        const wrap = document.createElement('div');
        wrap.className = 'codeblock';
        const head = document.createElement('div');
        head.className = 'codeblock-head';
        const label = document.createElement('span');
        label.className = 'codeblock-lang';
        label.textContent = lang || STRINGS.codeLabel;
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'codeblock-copy';
        button.textContent = STRINGS.copyLabel;
        button.setAttribute('aria-label', STRINGS.copyLabel);
        button.addEventListener('click', () => copyCode(button, code || pre));
        head.appendChild(label);
        head.appendChild(button);
        pre.parentNode.insertBefore(wrap, pre);
        wrap.appendChild(head);
        wrap.appendChild(pre);
    });
}

async function copyText(text) {
    if (typeof navigator !== 'undefined' && navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
        return;
    }
    const area = document.createElement('textarea');
    area.value = text;
    document.body.appendChild(area);
    area.select();
    document.execCommand('copy');
    area.remove();
}

function flashCopied(button, done) {
    try {
        button.classList.add('copied');
        if (done) {
            const previous = button.innerHTML;
            button.innerHTML = ICONS.check;
            setTimeout(() => {
                if (button.isConnected) {
                    button.innerHTML = previous;
                    button.classList.remove('copied');
                }
            }, 1200);
        } else {
            const previous = button.textContent;
            button.textContent = STRINGS.copiedLabel;
            setTimeout(() => {
                if (button.isConnected) {
                    button.textContent = previous;
                    button.classList.remove('copied');
                }
            }, 1200);
        }
    } catch (err) { /* ignore */ }
}

async function copyCode(button, node) {
    try {
        await copyText(node.textContent);
        flashCopied(button, false);
    } catch (err) {
        state.error = `${STRINGS.errorBannerPrefix}${err.message}`;
        render();
    }
}

async function copyExchange(button, ix) {
    const conv = state.current && state.current.conversation;
    const exchange = conv && (conv.exchanges || [])[ix];
    if (!exchange) {
        return;
    }
    try {
        await copyText(exchange.model);
        flashCopied(button, true);
    } catch (err) {
        state.error = `${STRINGS.errorBannerPrefix}${err.message}`;
        render();
    }
}

async function regenerateLastExchange() {
    if (state.route.name !== 'chat') {
        return;
    }
    try {
        await apiPost('regenerateConversationExchange', { id: state.route.id });
        state.thinkingOpen = {};
        await loadConversation(state.route.id);
    } catch (err) {
        state.error = `${STRINGS.errorBannerPrefix}${err.message}`;
        render();
    }
}

async function deleteLastExchange() {
    if (state.route.name !== 'chat') {
        return;
    }
    try {
        await apiPost('deleteConversationExchange', { id: state.route.id });
        state.thinkingOpen = {};
        await loadConversation(state.route.id);
    } catch (err) {
        state.error = `${STRINGS.errorBannerPrefix}${err.message}`;
        render();
    }
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
        html += renderExchange(exchange, index, index === exchanges.length - 1, cur.generating);
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

function buildChatHeaderHtml() {
    if (state.route.name !== 'chat') {
        return '';
    }
    const cur = state.current;
    const conversation = cur && cur.conversation;
    const title = conversation ? conversation.title : chatTitle(state.route.id);
    const button = conversation
        ? `<button type="button" class="action-btn" data-action="download-chat" ` +
            `title="${escapeHtml(STRINGS.menuDownload)}" aria-label="${escapeHtml(STRINGS.menuDownload)}">${ICONS.download}</button>`
        : '';
    return `<div class="chat-header"><h1 class="chat-header-title">${escapeHtml(title)}</h1>${button}</div>`;
}

function buildModelMenuHtml() {
    if (!state.modelMenuOpen || !state.models) {
        return '';
    }
    const options = state.models.list.map((model) => {
        const selected = model.id === composerModel() ? ' aria-current="true"' : '';
        return `<button type="button" role="menuitemradio"${selected} data-action="model" data-id="${escapeHtml(model.id)}" ` +
            `title="${escapeHtml(model.id)}">${escapeHtml(model.id)}</button>`;
    }).join('');
    return `<div class="model-menu" role="menu">${options || `<p class="chat-list-title">${escapeHtml(STRINGS.noModels)}</p>`}</div>`;
}

function buildComposerHtml() {
    const draft = getDraft();
    const generating = isGenerating();
    const model = composerModel();
    const readOnly = state.route.name === 'chat';
    const canSend = (draft.trim() !== '' || uploadFiles.length > 0) && !state.sending && !generating;
    const sendLabel = generating ? STRINGS.stopLabel : STRINGS.sendLabel;
    const sendIcon = generating ? ICONS.stop : ICONS.up;
    const thinkingIcon = state.thinkingEnabled ? ICONS.paw : ICONS.pawOff;
    const thinkingTitle = state.thinkingEnabled ? STRINGS.thinkingOn : STRINGS.thinkingOff;
    return `<textarea id="composer-input" rows="1" placeholder="${escapeHtml(STRINGS.composerPlaceholder)}" ` +
        `aria-label="${escapeHtml(STRINGS.composerPlaceholder)}">${escapeHtml(draft)}</textarea>` +
        `<div class="composer-row">` +
        `<div class="model-picker">` +
        (readOnly
            ? `<span class="model-pill" title="${escapeHtml(model || '')}"><span class="model-name">${escapeHtml(model || STRINGS.noModels)}</span></span>`
            : `<button type="button" class="model-pill" id="model-pill" aria-haspopup="menu" aria-expanded="${state.modelMenuOpen}" ` +
                `title="${escapeHtml(STRINGS.selectModel)}"><span class="model-name">${escapeHtml(model || STRINGS.noModels)}</span>${ICONS.chevron}</button>`) +
        buildModelMenuHtml() +
        `</div>` +
        `<button type="button" class="icon-btn${state.thinkingEnabled ? ' thinking-active' : ''}" id="thinking-btn" data-action="toggleThinking" ` +
        `title="${escapeHtml(thinkingTitle)}" aria-label="${escapeHtml(thinkingTitle)}">${thinkingIcon}</button>` +
        `<button type="button" class="icon-btn${uploadFiles.length ? ' upload-active' : ''}" id="upload-btn" data-action="uploadFile" ` +
        `title="${escapeHtml(uploadFiles.length ? uploadFiles.length + ' file(s) selected' : STRINGS.uploadFile)}" aria-label="${escapeHtml(STRINGS.uploadFile)}">${ICONS.upload}</button>` +
        (uploadFiles.length ? `<span class="file-pill">${escapeHtml(uploadFiles.map(f => f.name).join(', '))}</span>` : '') +
        `<input type="file" id="file-input" accept=".txt,.md,.docx,.png,.jpg,.jpeg" multiple style="display:none">` +
        `<button type="button" class="send-btn${canSend ? ' ready' : ''}" id="send-btn" data-action="send" ` +
        `title="${escapeHtml(sendLabel)}" aria-label="${escapeHtml(sendLabel)}"${canSend || generating ? '' : ' disabled'}>${sendIcon}</button>` +
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
        `</aside>` +
        `<main class="main">` +
        `<header class="topbar">` +
        `<button class="icon-btn" id="btn-sidebar-open" title="${escapeHtml(STRINGS.openSidebar)}" aria-label="${escapeHtml(STRINGS.openSidebar)}">${ICONS.panel}</button>` +
        `<span class="topbar-title">${escapeHtml(STRINGS.appTitle)}</span>` +
        `</header>` +
        (state.sidebarCollapsed ? `<button class="icon-btn sidebar-fab" id="btn-sidebar-fab" title="${escapeHtml(STRINGS.openSidebar)}" aria-label="${escapeHtml(STRINGS.openSidebar)}">${ICONS.panel}</button>` : '') +
        buildChatHeaderHtml() +
        `<div class="messages"><div class="messages-inner" id="messages">${buildMessagesHtml()}</div></div>` +
        `<div class="composer-wrap"><div class="composer">${buildComposerHtml()}</div></div>` +
        `</main>` +
        `</div>` +
        (state.openMenuId || state.modelMenuOpen ? `<div class="overlay" id="menu-overlay"></div>` : '') +
        renderModal();

    autoresizeComposer();
    enhanceCodeBlocks(document.getElementById('messages'));
    const modalInput = document.getElementById('modal-input');
    if (modalInput) {
        modalInput.focus();
        modalInput.select();
    } else if (state.composerFocus) {
        const composer = document.getElementById('composer-input');
        if (composer) {
            composer.focus();
            composer.setSelectionRange(composer.value.length, composer.value.length);
        }
    }
}

function autoresizeComposer() {
    const composer = document.getElementById('composer-input');
    if (composer) {
        composer.style.height = 'auto';
        composer.style.height = `${composer.scrollHeight}px`;
    }
}

/** Update the send button in place while typing (no re-render, keeps focus). */
function updateSendButton() {
    const button = document.getElementById('send-btn');
    if (!button || isGenerating()) {
        return;
    }
    const ready = (getDraft().trim() !== '' || uploadFiles.length > 0) && !state.sending;
    button.classList.toggle('ready', ready);
    if (ready) {
        button.removeAttribute('disabled');
    } else {
        button.setAttribute('disabled', '');
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
    state.thinkingOpen = {};
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

async function loadModels() {
    const data = await apiGet('getModels');
    state.models = { current: data.model || null, list: data.models || [] };
    if (!state.selectedModel) {
        state.selectedModel = state.models.current || (state.models.list.length ? state.models.list[0].id : null);
    }
}

async function submitComposer() {
    if (state.sending) {
        return;
    }
    if (isGenerating() && state.route.name === 'chat') {
        await stopCurrentChat();
        return;
    }
    const text = getDraft().trim();
    if (!text && !uploadFiles.length) {
        return;
    }
    state.sending = true;
    state.error = null;
    render();
    try {
        if (state.route.name === 'new') {
            const model = composerModel();
            if (!model) {
                throw new Error(STRINGS.errorNoModel);
            }
            const files = await readFilesAsData(uploadFiles);
            const data = await apiPost('startConversation', { model, user: text, think: state.thinkingEnabled, files });
            setDraft('');
            uploadFiles = [];
            state.sending = false;
            window.location.hash = `#/c/${data.id}`;
            await refreshConversations();
        } else {
            const files = await readFilesAsData(uploadFiles);
            await apiPost('replyConversation', { id: state.route.id, user: text, think: state.thinkingEnabled, files });
            setDraft('');
            uploadFiles = [];
            state.sending = false;
            state.composerFocus = true;
            await loadConversation(state.route.id);
        }
    } catch (err) {
        state.sending = false;
        state.error = `${STRINGS.errorSend} ${err.message}`;
        state.composerFocus = state.route.name !== 'new';
        render();
    }
}

async function stopCurrentChat() {
    if (state.route.name !== 'chat') {
        return;
    }
    try {
        await apiPost('stopConversation', { id: state.route.id });
        await loadConversation(state.route.id);
    } catch (err) {
        state.error = `${STRINGS.errorBannerPrefix}${err.message}`;
        render();
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
    } else if (action === 'model') {
        state.selectedModel = id;
        state.modelMenuOpen = false;
        render();
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
        if (!state.selectedModel && data.model) {
            state.selectedModel = data.model;
        }
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
    state.modelMenuOpen = false;
    state.current = null;
    state.sending = false;
    state.thinkingOpen = {};
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
        } else if (action === 'rename' || action === 'delete' || action === 'download' || action === 'model') {
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
        } else if (action === 'send') {
            submitComposer();
        } else if (action === 'copy') {
            copyExchange(actionButton, Number(actionButton.dataset.ix));
        } else if (action === 'regenerate') {
            regenerateLastExchange();
        } else if (action === 'delete-exchange') {
            deleteLastExchange();
        } else if (action === 'download-chat') {
            downloadCurrentChat();
        } else if (action === 'thinking') {
            const ix = Number(actionButton.dataset.ix);
            const cur = state.current;
            const lastIx = cur && cur.conversation ? (cur.conversation.exchanges || []).length - 1 : -1;
            const shown = isThinkingOpen(ix, ix === lastIx, Boolean(cur && cur.generating));
            state.thinkingOpen[ix] = !shown;
            patchMessages();
        } else if (action === 'toggleThinking') {
            state.thinkingEnabled = !state.thinkingEnabled;
            saveThinkingEnabled(state.thinkingEnabled);
            render();
        } else if (action === 'uploadFile') {
            document.getElementById('file-input')?.click();
        }
        return;
    }
    if (event.target.id === 'menu-overlay') {
        state.openMenuId = null;
        state.modelMenuOpen = false;
        render();
        return;
    }
    if (event.target.id === 'modal-overlay') {
        state.modal = null;
        render();
        return;
    }
    const button = event.target.closest ? event.target.closest('#btn-sidebar,#btn-sidebar-open,#btn-sidebar-fab,#btn-theme,#model-pill') : null;
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
        } else if (button.id === 'model-pill') {
            toggleModelMenu();
        }
    }
}

async function toggleModelMenu() {
    if (state.modelMenuOpen) {
        state.modelMenuOpen = false;
        render();
        return;
    }
    try {
        await loadModels();
        state.modelMenuOpen = true;
        render();
    } catch (err) {
        state.error = `${STRINGS.errorLoadModels} ${err.message}`;
        render();
    }
}

function onRootKeyDown(event) {
    if (event.key === 'Enter' && event.target && event.target.id === 'modal-input') {
        submitRename();
    } else if (event.key === 'Enter' && event.target && event.target.id === 'composer-input' && !event.shiftKey) {
        event.preventDefault();
        submitComposer();
    }
}

function onRootInput(event) {
    if (event.target && event.target.id === 'composer-input') {
        setDraft(event.target.value);
        autoresizeComposer();
        updateSendButton();
    }
}

function onRootFocus(event) {
    if (event.target && event.target.id === 'composer-input') {
        state.composerFocus = true;
    }
}

function onRootBlur(event) {
    if (event.target && event.target.id === 'composer-input') {
        state.composerFocus = false;
    }
}

function onKeyDown(event) {
    if (event.key === 'Escape') {
        if (state.modal) {
            state.modal = null;
            render();
        } else if (state.openMenuId || state.modelMenuOpen) {
            state.openMenuId = null;
            state.modelMenuOpen = false;
            render();
        }
    }
}

async function init() {
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
    root.addEventListener('input', onRootInput);
    root.addEventListener('focusin', onRootFocus);
    root.addEventListener('focusout', onRootBlur);
    root.addEventListener('change', (event) => {
        if (event.target.id === 'file-input') {
            const files = event.target.files;
            if (files) {
                uploadFiles = Array.from(files).filter((f) => {
                    const ext = f.name.split('.').pop().toLowerCase();
                    return ['txt', 'md', 'docx', 'png', 'jpg', 'jpeg'].includes(ext);
                });
                render();
            }
        }
    });
    render();
    try {
        await loadModels();
    } catch (err) {
        state.error = `${STRINGS.errorLoadModels} ${err.message}`;
    }
    await refreshConversations();
    if (state.route.name === 'chat') {
        loadConversation(state.route.id);
    } else {
        render();
    }
}

init();

export { STRINGS, parseRoute, renderMarkdown, escapeHtml, apiGet, apiPost, buildMarkdownFilename, buildMarkdownExport };
