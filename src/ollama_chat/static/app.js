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
    deleteTaskTitle: 'Delete task',
    deleteTaskConfirm: 'Delete this scheduled task? This cannot be undone.',
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
    webSearchOn: 'Web search on',
    webSearchOff: 'Web search off',
    emailOn: 'Email tools on',
    emailOff: 'Email tools off',
    toolsLabel: 'Tools',
    toolSearch: 'Search',
    toolOpen: 'Opened page',
    toolCheck: 'Read email',
    toolSend: 'Email to',
    emailConfirmTitle: 'Send this email?',
    emailDraftTo: 'To',
    emailDraftSubject: 'Subject',
    emailSendDraft: 'Send',
    emailDiscard: 'Discard',
    emailSent: 'Email sent',
    menuExportPdf: 'Export PDF',
    pdfExported: 'PDF exported to',
    uploadFile: 'Upload file',
    uploadFilesMax: 'A maximum of 10 files can be attached to a message.',
    uploadFilesType: 'Only txt, md, docx, png, jpg and jpeg files can be attached.',
    removeFile: 'Remove file',
    attachedFiles: 'Attached files',
    openMd: 'Open markdown',
    mdViewerTitle: 'Markdown preview',
    mdClose: 'Close preview',
    navSettings: 'Settings',
    navTasks: 'Tasks',
    settingsHeading: 'Settings',
    settingsWorkspace: 'Workspace',
    workspaceLabel: 'Workspace folder',
    workspaceHint: 'Memory files, tasks, logs, reports and exports live here.',
    workspaceSave: 'Save workspace',
    workspaceSaved: 'Workspace saved',
    workspaceError: 'The folder does not exist and could not be created (or is not writable).',
    settingsGmail: 'Gmail (IMAP / SMTP)',
    imapHostLabel: 'IMAP server',
    imapPortLabel: 'IMAP port',
    smtpHostLabel: 'SMTP server',
    smtpPortLabel: 'SMTP port',
    emailUserLabel: 'Account (login)',
    emailUserHint: 'For Gmail, your e-mail address, e.g. you@gmail.com.',
    emailPasswordLabel: 'App password',
    emailPasswordHint: 'Stored on the server in .env and never sent back to the browser.',
    emailPasswordSave: 'Leave empty to keep the saved password.',
    emailPasswordSavedPlaceholder: '•••••••• (saved)',
    settingsSaveEmail: 'Save',
    emailSaved: 'Email settings saved',
    testConnection: 'Test connection',
    testing: 'Testing…',
    connectionHint: 'This checks the saved settings - save first.',
    connectionOk: 'Connection OK',
    portHint: 'Port',
    tasksHeading: 'Tasks',
    newTask: 'New task',
    noTasks: 'No scheduled tasks yet.',
    taskNewTitle: 'New task',
    taskEditTitle: 'Edit task',
    taskNameLabel: 'Name',
    taskTimeLabel: 'Run time',
    taskDaysLabel: 'Run days',
    dayNames: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    taskPromptLabel: 'Task prompt',
    taskModelLabel: 'Model',
    taskNumCtxLabel: 'Context size (num_ctx)',
    taskNumCtxHint: 'Leave empty for the default context size.',
    taskToolsLabel: 'Allowed tools',
    sendEmailDefaultOff: 'off by default - a task sending email is not confirmed by anyone',
    taskEnabledLabel: 'Enabled',
    taskRunNow: 'Run now',
    taskStarted: 'Task started - see the workspace logs for the result',
    taskLastRun: 'Last run',
    taskSchedule: 'Schedule',
    taskEditing: 'Editing',
    scheduleEveryDay: 'every day',
    taskSaveLabel: 'Save task',
    taskLogTitle: 'Task log',
    noTaskLog: 'No log entries for this task yet.',
    toolsTaskWebSearch: 'Web search',
    toolsTaskFetchPage: 'Open pages',
    toolsTaskCheckEmail: 'Read email',
    toolsTaskSendEmail: 'Send email',
    everyDayShort: 'Every day',
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
    globe: '<svg class="icon icon-small" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><line x1="3" y1="12" x2="21" y2="12"/><ellipse cx="12" cy="12" rx="4" ry="9"/></svg>',
    globeOff: '<svg class="icon icon-small" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><line x1="3" y1="12" x2="21" y2="12"/><ellipse cx="12" cy="12" rx="4" ry="9"/><line x1="4.5" y1="4.5" x2="19.5" y2="19.5"/></svg>',
    mail: '<svg class="icon icon-small" viewBox="0 0 24 24" aria-hidden="true"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-10 6L2 7"/></svg>',
    mailOff: '<svg class="icon icon-small" viewBox="0 0 24 24" aria-hidden="true"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-10 6L2 7"/><line x1="4" y1="5" x2="20" y2="19"/></svg>',
    pdfExport: '<svg class="icon icon-small" viewBox="0 0 24 24" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/><path d="M12 18v-5"/><path d="m9 16 3 3 3-3"/></svg>',
    upload: '<svg class="icon icon-small" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>',
    clip: '<svg class="icon icon-small" viewBox="0 0 24 24" aria-hidden="true"><path d="M21.44 11.05 12.25 20.24a6 6 0 0 1-8.49-8.49l8.57-8.57a4 4 0 1 1 5.66 5.66l-8.58 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>',
    md: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/><path d="M8 13h8"/><path d="M8 17h8"/><path d="M8 9h2"/></svg>',
    gear: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
    checklist: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6h12"/><path d="M9 12h12"/><path d="M9 18h12"/><path d="m3 6 1 1 2-2"/><path d="m3 12 1 1 2-2"/><path d="m3 18 1 1 2-2"/></svg>',
    play: '<svg class="icon icon-small" viewBox="0 0 24 24" aria-hidden="true"><path d="m5 3 14 9-14 9Z"/></svg>',
    folder: '<svg class="icon icon-small" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h5l2 2h9a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z"/></svg>',
    edit: '<svg class="icon icon-small" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>',
};

/** Poll interval (ms) while a response is generating. */
const POLL_MS = 400;

/** Poll interval (ms) for the tasks page list refresh. */
const TASKS_POLL_MS = 4000;

/** The task tools thetasks form offers, in order (send_email is opt-in: unchecked). */
const TASK_FORM_TOOLS = ['web_search', 'fetch_page', 'check_email', 'send_email'];

/** Maximum number of files that can be attached to a single message. */
const MAX_ATTACH_FILES = 10;

/** File extensions accepted as message attachments. */
const ATTACH_FILE_EXTS = ['txt', 'md', 'docx', 'png', 'jpg', 'jpeg'];

/** File extensions read as base64 images rather than text. */
const IMAGE_FILE_EXTS = ['png', 'jpg', 'jpeg'];

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
    toolsOpen: {},
    webSearchEnabled: loadWebSearchEnabled(),
    emailEnabled: loadEmailEnabled(),
    notice: null,
    uploading: false,
    mdViewer: null,
    workspace: null,
    settings: { loading: false, error: null, data: null, saving: false, test: null, notice: null, savingEmail: false },
    tasksPage: { loading: false, error: null, items: null, timer: null },
    taskForm: null,
    taskLog: null,
};

function loadThinkingEnabled() {
    try {
        return window.localStorage.getItem('ollama-chat-thinking') === 'true';
    } catch (err) { return true; }
}

function saveThinkingEnabled(val) {
    try { window.localStorage.setItem('ollama-chat-thinking', String(val)); } catch (err) { /* ignore */ }
}

function loadWebSearchEnabled() {
    try {
        return window.localStorage.getItem('ollama-chat-websearch') === 'true';
    } catch (err) { return false; }
}

function saveWebSearchEnabled(val) {
    try { window.localStorage.setItem('ollama-chat-websearch', String(val)); } catch (err) { /* ignore */ }
}

function loadEmailEnabled() {
    try {
        return window.localStorage.getItem('ollama-chat-email') === 'true';
    } catch (err) { return false; }
}

function saveEmailEnabled(val) {
    try { window.localStorage.setItem('ollama-chat-email', String(val)); } catch (err) { /* ignore */ }
}

function fileExt(name) {
    return String(name).split('.').pop().toLowerCase();
}

function isAttachFile(file) {
    return ATTACH_FILE_EXTS.includes(fileExt(file.name));
}

function uploadFileKey(file) {
    return `${file.name}:${file.size}`;
}

/** The attachment-related error banner messages. */
function uploadError(kind) {
    return `${STRINGS.errorBannerPrefix}${kind}`;
}

function isUploadError() {
    return state.error === uploadError(STRINGS.uploadFilesMax) || state.error === uploadError(STRINGS.uploadFilesType);
}

/** Add the selected files to the attachment list (keeping the 10 file maximum). */
function addUploadFiles(selected) {
    const rejected = selected.filter((file) => !isAttachFile(file));
    const chosen = selected.filter((file) => isAttachFile(file) &&
        !uploadFiles.some((fileCur) => uploadFileKey(fileCur) === uploadFileKey(file)));
    const room = Math.max(MAX_ATTACH_FILES - uploadFiles.length, 0);
    uploadFiles = uploadFiles.concat(chosen.slice(0, room));
    if (rejected.length) {
        state.error = uploadError(STRINGS.uploadFilesType);
    } else if (chosen.length > room) {
        state.error = uploadError(STRINGS.uploadFilesMax);
    } else if (isUploadError()) {
        state.error = null;
    }
    return uploadFiles.length;
}

/** Remove one of the attached files by its index. */
function removeUploadFile(ix) {
    uploadFiles.splice(ix, 1);
    if (state.error === uploadError(STRINGS.uploadFilesMax)) {
        state.error = null;
    }
}

function readFilesAsData(files) {
    const results = [];
    for (const file of files.slice(0, MAX_ATTACH_FILES)) {
        const ext = fileExt(file.name);
        if (!ATTACH_FILE_EXTS.includes(ext)) continue;
        results.push(new Promise((resolve) => {
            const reader = new FileReader();
            reader.onload = () => {
                let data;
                if (IMAGE_FILE_EXTS.includes(ext)) {
                    const base64 = reader.result.split(',')[1] || reader.result;
                    data = base64;
                } else {
                    data = reader.result;
                }
                resolve({ name: file.name, type: file.type || `application/${ext === 'docx' ? 'vnd.openxmlformats-officedocument.wordprocessingml.document' : ext === 'md' ? 'markdown' : ext === 'txt' ? 'plaintext' : ext === 'png' ? 'png' : 'jpeg'}`, data });
            };
            reader.onerror = () => resolve(null);
            if (IMAGE_FILE_EXTS.includes(ext)) {
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
    if (hash === '#/settings') {
        return { name: 'settings' };
    }
    if (hash === '#/tasks') {
        return { name: 'tasks' };
    }
    const match = hash.match(/^#\/c\/([A-Za-z0-9-]+)/);
    if (match) {
        return { name: 'chat', id: match[1] };
    }
    return { name: 'new' };
}

/** The workspace folder's display name (the workspace path's last segment). */
function workspaceName() {
    const path = state.workspace || '';
    if (!path) {
        return '';
    }
    const parts = String(path).split(/[\\/]/).filter(Boolean);
    return parts.length ? parts[parts.length - 1] : path;
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
        parts.push('', '## User:', '');
        const files = exchange.files || [];
        if (files.length) {
            parts.push(`**Files:** ${files.map((file) => file.name).join(', ')}`, '');
        }
        parts.push(exchange.user, '', '## Model:', '', exchange.model);
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

/** Confirm (send=true) or discard (send=false) a model-drafted email. */
async function sendEmailDraft(ix, send) {
    if (state.route.name !== 'chat') {
        return;
    }
    try {
        await apiPost('sendEmail', { id: state.route.id, send });
        state.notice = send ? STRINGS.emailSent : null;
        await loadConversation(state.route.id);
    } catch (err) {
        state.error = `${STRINGS.errorBannerPrefix}${err.message}`;
        render();
    }
}

/** Export the chat's current conversation as a PDF (server-rendered). */
async function exportCurrentChatPdf() {
    if (state.route.name !== 'chat') {
        return;
    }
    try {
        const data = await apiPost('exportPdf', { id: state.route.id });
        state.notice = `${STRINGS.pdfExported} ${data.file}`;
        render();
        const box = messagesBox();
        if (box) {
            box.scrollTop = 0;
        }
    } catch (err) {
        state.error = `${STRINGS.errorBannerPrefix}${err.message}`;
        render();
    }
}

/* ---------- Settings page ---------- */

async function loadSettings() {
    state.settings = { ...state.settings, loading: true, error: null, test: null, notice: null };
    render();
    try {
        const data = await apiGet('getSettings');
        state.settings.data = data;
        state.settings.loading = false;
        state.workspace = data.workspace;
    } catch (err) {
        state.settings.loading = false;
        state.settings.error = err.message;
    }
    render();
}

/** Save the workspace folder (the server creates it and verifies it is writable). */
async function submitWorkspace() {
    const input = document.getElementById('workspace-input');
    const path = input ? input.value.trim() : '';
    if (!path) {
        return;
    }
    state.settings.saving = true;
    state.settings.error = null;
    state.settings.notice = null;
    render();
    try {
        const data = await apiPost('setWorkspace', { path });
        state.workspace = data.workspace;
        state.settings.data = { ...state.settings.data, workspace: data.workspace };
        state.settings.saving = false;
        state.settings.notice = STRINGS.workspaceSaved;
    } catch (err) {
        state.settings.saving = false;
        state.settings.error = err.message;
    }
    render();
}

/** Save the email settings. The password field is sent only when the user typed one. */
async function submitEmailSettings() {
    const form = state.settings;
    if (!form.data) {
        return;
    }
    const read = (id) => (document.getElementById(id) ? document.getElementById(id).value : '');
    const body = {
        imapHost: read('email-imap-host'),
        imapPort: read('email-imap-port') || undefined,
        smtpHost: read('email-smtp-host'),
        smtpPort: read('email-smtp-port') || undefined,
        user: read('email-user'),
    };
    const password = read('email-password');
    if (password) {
        body.password = password;
    }
    if (!body.imapHost) {
        state.settings.error = `${STRINGS.imapHostLabel}: required`;
    } else if (!body.smtpHost) {
        state.settings.error = `${STRINGS.smtpHostLabel}: required`;
    } else {
        state.settings.savingEmail = true;
        state.settings.error = null;
        state.settings.notice = null;
        render();
        try {
            await apiPost('setEmailSettings', body);
            const data = await apiGet('getSettings');
            state.settings.data = data;
            state.settings.savingEmail = false;
            state.settings.notice = STRINGS.emailSaved;
        } catch (err) {
            state.settings.savingEmail = false;
            state.settings.error = err.message;
        }
    }
    render();
}

/** Check the saved email settings (IMAP + SMTP logins). */
async function testConnection() {
    state.settings.test = { running: true };
    render();
    try {
        const data = await apiPost('testEmailConnection');
        state.settings.test = { running: false, ok: true, message: data.message };
    } catch (err) {
        state.settings.test = { running: false, ok: false, message: err.message };
    }
    render();
}

/* ---------- Tasks page ---------- */

/** The run-days text, e.g. "every day" or "Mon, Thu". */
function taskDaysText(days) {
    const dayList = Array.isArray(days) ? days : [];
    if (dayList.length === 7) {
        return STRINGS.everyDayShort;
    }
    return dayList.map((day) => STRINGS.dayNames[day - 1]).join(', ') || '—';
}

async function loadTasksPage() {
    stopTasksPolling();
    state.tasksPage = { ...state.tasksPage, loading: true, error: null };
    render();
    try {
        const data = await apiGet('getTasks');
        state.tasksPage.items = data.tasks || [];
        state.tasksPage.loading = false;
    } catch (err) {
        state.tasksPage.loading = false;
        state.tasksPage.error = err.message;
    }
    render();
    scheduleTasksPoll();
}

/**
 * While the tasks page is open, refresh the list every few seconds so "Run now" results and
 * the scheduler's lastRun updates appear.
 */
function scheduleTasksPoll() {
    if (state.route.name !== 'tasks') {
        return;
    }
    state.tasksPage.timer = setTimeout(async () => {
        state.tasksPage.timer = null;
        if (state.route.name !== 'tasks' || state.taskForm || state.taskLog) {
            scheduleTasksPoll();
            return;
        }
        try {
            const data = await apiGet('getTasks');
            state.tasksPage.items = data.tasks || [];
            if (state.tasksPage.error) {
                state.tasksPage.error = null;
                render();
            } else {
                patchTasksList();
            }
        } catch (err) {
            state.tasksPage.error = err.message;
            patchTasksList();
        }
        scheduleTasksPoll();
    }, TASKS_POLL_MS);
}

function stopTasksPolling() {
    if (state.tasksPage.timer) {
        clearTimeout(state.tasksPage.timer);
        state.tasksPage.timer = null;
    }
    if (state.taskForm || state.taskLog) {
        return;
    }
    state.tasksPage.items = null;
    state.tasksPage.error = null;
}

/** Re-render only the tasks list (keeps scroll position). */
function patchTasksList() {
    const list = document.getElementById('tasks-list');
    if (list) {
        list.innerHTML = buildTasksListHtml();
    }
}

/** Open the task form - with a task (edit) or without (create). */
function openTaskForm(task) {
    state.taskForm = task
        ? {
            id: task.id,
            name: task.name || '',
            time: task.time || '',
            days: new Set((task.days || []).map(Number)),
            prompt: task.prompt || '',
            model: task.model || '',
            numCtx: task.numCtx != null ? String(task.numCtx) : '',
            tools: new Set(task.tools || []),
            enabled: task.enabled !== false,
            error: null,
            saving: false
        }
        : {
            id: null,
            name: '',
            time: '09:00',
            days: new Set([1, 2, 3, 4, 5, 6, 7]),
            prompt: '',
            model: '',
            numCtx: '',
            tools: new Set(['web_search', 'fetch_page', 'check_email']),
            enabled: true,
            error: null,
            saving: false
        };
    render();
}

async function submitTaskForm() {
    const form = state.taskForm;
    if (!form || form.saving) {
        return;
    }
    const input = (id) => (document.getElementById(id) ? document.getElementById(id).value : '');
    const name = input('task-name').trim();
    const time = input('task-time');
    const prompt = document.getElementById('task-prompt') ? document.getElementById('task-prompt').value : '';
    const numCtx = input('task-numctx');
    if (!name || !form.days.size) {
        form.error = !name ? `${STRINGS.taskNameLabel}: required` : `${STRINGS.taskDaysLabel}: required`;
        render();
        return;
    }
    form.saving = true;
    form.error = null;
    render();
    const body = {
        name,
        time,
        days: [...form.days],
        model: (document.getElementById('task-model') ? document.getElementById('task-model').value : '') || form.model || composerModel() || '',
        prompt,
        tools: [...form.tools],
    };
    if (form.id) {
        body.id = form.id;
    }
    if (numCtx) {
        body.numCtx = Number(numCtx);
    }
    body.enabled = form.enabled;
    try {
        await apiPost('setTask', body);
        state.taskForm = null;
        state.notice = null;
        window.setTimeout(loadTasksPage, 250);
        return null;
    } catch (err) {
        form.saving = false;
        form.error = err.message;
        render();
    }
    return null;
}

function setTaskFormField(field, id, on) {
    const form = state.taskForm;
    if (!form) {
        return;
    }
    if (field === 'day') {
        if (on) {
            form.days.add(id);
        } else {
            form.days.delete(id);
        }
    } else if (field === 'tool') {
        if (on) {
            form.tools.add(id);
        } else {
            form.tools.delete(id);
        }
    } else {
        form[field] = on;
    }
    render();
}

/** Toggle a task's enabled state in the list. */
async function toggleTask(taskId) {
    const item = (state.tasksPage.items || []).find((task) => task.id === taskId);
    if (!item) {
        return;
    }
    const body = {
        id: item.id,
        name: item.name,
        time: item.time,
        days: item.days || [],
        model: item.model,
        prompt: item.prompt || '',
        tools: item.tools || [],
        enabled: !(item.enabled !== false),
    };
    if (item.numCtx != null) {
        body.numCtx = item.numCtx;
    }
    try {
        await apiPost('setTask', body);
        scheduleTasksPoll();
    } catch (err) {
        state.tasksPage.error = err.message;
        patchTasksList();
    }
}

/** Run a task now - the server runs it in the background. */
async function runTaskNow(taskId) {
    try {
        await apiPost('runTask', { id: taskId });
        state.notice = STRINGS.taskStarted;
        render();
    } catch (err) {
        state.tasksPage.error = err.message;
        patchTasksList();
    }
}

/** Delete a task (confirm via the shared modal). */
function openTaskDelete(taskId) {
    const item = (state.tasksPage.items || []).find((task) => task.id === taskId);
    state.modal = { type: 'delete-task', id: taskId, title: item ? item.name : taskId, error: null };
    render();
}

async function submitTaskDelete() {
    const id = state.modal.id;
    try {
        await apiPost('deleteTask', { id });
        state.modal = null;
        if (state.taskForm && state.taskForm.id === id) {
            state.taskForm = null;
        }
        await loadTasksPage();
    } catch (err) {
        state.modal.error = err.message;
        render();
    }
}

/** Show a task's run log. */
async function openTaskLog(taskId) {
    const item = (state.tasksPage.items || []).find((task) => task.id === taskId);
    state.taskLog = { id: taskId, name: item ? item.name : taskId, loading: true, text: null, error: null };
    render();
    try {
        const data = await apiGet('getTaskLog', `id=${encodeURIComponent(taskId)}`);
        state.taskLog = { id: taskId, name: item ? item.name : taskId, loading: false, text: data.log || null, error: null };
    } catch (err) {
        state.taskLog = { id: taskId, name: item ? item.name : taskId, loading: false, text: null, error: err.message };
    }
    render();
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

/** The web tool call's icon and label (e.g. "Search: python news"). */
function toolCallIcon(tool) {
    if (tool.action === 'search') return '🔍';
    if (tool.action === 'open') return '🌐';
    if (tool.action === 'check') return '📧';
    if (tool.action === 'send') return '📤';
    return '🌐';
}

function toolCallLabel(tool) {
    if (tool.action === 'search') return `${STRINGS.toolSearch}: ${tool.value}`;
    if (tool.action === 'open') return `${STRINGS.toolOpen}: ${tool.value}`;
    if (tool.action === 'check') return `${STRINGS.toolCheck}: ${tool.value}`;
    if (tool.action === 'send') return `${STRINGS.toolSend}: ${tool.value}`;
    return `${STRINGS.toolOpen}: ${tool.value}`;
}

function isToolCallsOpen(ix) {
    if (Object.prototype.hasOwnProperty.call(state.toolsOpen, ix)) {
        return state.toolsOpen[ix];
    }
    return false;
}

/** Render an exchange's web/email tool calls as a collapsible block. */
function renderToolCalls(exchange, ix) {
    const tools = exchange.tools || [];
    const open = isToolCallsOpen(ix);
    const first = tools[0] || {};
    const label = tools.length === 1 ? toolCallLabel(first) : `${STRINGS.toolsLabel} (${tools.length})`;
    const rows = tools.map((tool) =>
        `<div class="tool-call">${toolCallIcon(tool)}<span>${escapeHtml(toolCallLabel(tool))}</span></div>`
    ).join('');
    return `<div class="tool-calls">` +
        `<button type="button" class="tool-calls-head" data-action="tools" data-ix="${ix}" aria-expanded="${open}">` +
        `${toolCallIcon(first)}<span>${escapeHtml(label)}</span>${ICONS.chevron}</button>` +
        `<div class="tool-calls-body"${open ? '' : ' hidden'}>${rows}</div>` +
        `</div>`;
}

/** Render an exchange's email draft awaiting the user's send confirmation. */
function renderEmailDraft(email, ix) {
    if (email.sent) {
        return `<div class="email-draft email-draft-sent" role="status">✅ ` +
            `<span>${escapeHtml(`${STRINGS.emailSent}: ${email.to}`)}</span></div>`;
    }
    return `<div class="email-draft" role="group" aria-label="${escapeHtml(STRINGS.emailConfirmTitle)}">` +
        `<div class="email-draft-head">📧<strong>${escapeHtml(STRINGS.emailConfirmTitle)}</strong></div>` +
        `<p class="email-draft-row"><span class="email-draft-label">${escapeHtml(STRINGS.emailDraftTo)}:</span>` +
        `<span class="email-draft-value">${escapeHtml(email.to)}</span></p>` +
        `<p class="email-draft-row"><span class="email-draft-label">${escapeHtml(STRINGS.emailDraftSubject)}:</span>` +
        `<span class="email-draft-value">${escapeHtml(email.subject)}</span></p>` +
        `<pre class="email-draft-body">${escapeHtml(email.body)}</pre>` +
        `<div class="email-draft-actions">` +
        `<button type="button" class="btn btn-primary" data-action="send-email" data-ix="${ix}">${escapeHtml(STRINGS.emailSendDraft)}</button>` +
        `<button type="button" class="btn" data-action="discard-email" data-ix="${ix}">${escapeHtml(STRINGS.emailDiscard)}</button>` +
        `</div></div>`;
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

/** Render an exchange's attached file references as chips. */
function renderExchangeFiles(files) {
    if (!files || !files.length) {
        return '';
    }
    const chips = files.map((file) => {
        const name = file.name || '';
        return `<span class="msg-file" title="${escapeHtml(name)}">${ICONS.clip}<span class="msg-file-name">${escapeHtml(name)}</span></span>`;
    }).join('');
    return `<div class="msg-files" aria-label="${escapeHtml(STRINGS.attachedFiles)}">${chips}</div>`;
}

function renderExchange(exchange, ix, isLast, generating) {
    const filesHtml = renderExchangeFiles(exchange.files);
    let html = `<div class="msg msg-user">${filesHtml}` +
        (exchange.user || !filesHtml ? `<div class="bubble">${escapeHtml(exchange.user)}</div>` : '') + `</div>`;
    if (exchange.thinking) {
        html += renderThinking(exchange, ix, isLast, generating);
    }
    if (exchange.tools && exchange.tools.length) {
        html += renderToolCalls(exchange, ix);
    }
    if (exchange.email) {
        html += renderEmailDraft(exchange.email, ix);
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
        state.toolsOpen = {};
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
        state.toolsOpen = {};
        await loadConversation(state.route.id);
    } catch (err) {
        state.error = `${STRINGS.errorBannerPrefix}${err.message}`;
        render();
    }
}

/* ---------- Settings & tasks page builders ---------- */

/** A page shell: sidebar + scrolling main column (no composer). */
function buildPageHtml(titleText, innerHtml) {
    return `<div class="page-scroll"><div class="page"><h1 class="page-title">${escapeHtml(titleText)}</h1>${innerHtml}</div></div>`;
}

function buildSettingsHtml() {
    const form = state.settings;
    if (form.loading) {
        return buildPageHtml(STRINGS.settingsHeading, `<p class="page-status">${escapeHtml(STRINGS.loading)}</p>`);
    }
    if (form.error && !form.data) {
        return buildPageHtml(STRINGS.settingsHeading,
            `<div class="error-banner" role="alert">${escapeHtml(`${STRINGS.errorBannerPrefix}${form.error}`)}</div>` +
            `<p class="page-status"><button type="button" class="btn" data-action="reloadSettings">${escapeHtml(STRINGS.retry)}</button></p>`);
    }
    const data = form.data;
    const workspaceHtml =
        `<section class="panel">` +
        `<h2>${escapeHtml(STRINGS.settingsWorkspace)}</h2>` +
        `<div class="form-row form-row-wide">` +
        `<label class="form-field" for="workspace-input"><span>${escapeHtml(STRINGS.workspaceLabel)}</span>` +
        `<input id="workspace-input" type="text" value="${escapeHtml(data.workspace)}" spellcheck="false"></label>` +
        `<button type="button" class="btn btn-primary" data-action="saveWorkspace"${form.saving ? ' disabled' : ''}>` +
        `${escapeHtml(STRINGS.workspaceSave)}</button>` +
        `</div>` +
        `<p class="form-hint">${escapeHtml(STRINGS.workspaceHint)}</p>` +
        `</section>`;
    const email = data.email || {};
    const passwordField = email.hasPassword
        ? `<input id="email-password" type="password" placeholder="${escapeHtml(STRINGS.emailPasswordSavedPlaceholder)}" autocomplete="new-password">`
        : `<input id="email-password" type="password" autocomplete="new-password">`;
    const gmailHtml =
        `<section class="panel">` +
        `<h2>${escapeHtml(STRINGS.settingsGmail)}</h2>` +
        `<div class="form-grid">` +
        `<label class="form-field" for="email-imap-host"><span>${escapeHtml(STRINGS.imapHostLabel)}</span>` +
        `<input id="email-imap-host" type="text" value="${escapeHtml(email.imapHost || '')}" spellcheck="false" placeholder="imap.gmail.com"></label>` +
        `<label class="form-field" for="email-imap-port"><span>${escapeHtml(STRINGS.imapPortLabel)}</span>` +
        `<input id="email-imap-port" type="number" min="1" max="65535" value="${email.imapPort || 993}"></label>` +
        `<label class="form-field" for="email-smtp-host"><span>${escapeHtml(STRINGS.smtpHostLabel)}</span>` +
        `<input id="email-smtp-host" type="text" value="${escapeHtml(email.smtpHost || '')}" spellcheck="false" placeholder="smtp.gmail.com"></label>` +
        `<label class="form-field" for="email-smtp-port"><span>${escapeHtml(STRINGS.smtpPortLabel)}</span>` +
        `<input id="email-smtp-port" type="number" min="1" max="65535" value="${email.smtpPort || 465}"></label>` +
        `<label class="form-field" for="email-user"><span>${escapeHtml(STRINGS.emailUserLabel)}</span>` +
        `<input id="email-user" type="text" value="${escapeHtml(email.user || '')}" spellcheck="false"></label>` +
        `<label class="form-field" for="email-password"><span>${escapeHtml(STRINGS.emailPasswordLabel)}</span>` +
        passwordField + `</label>` +
        `</div>` +
        `<p class="form-hint">${escapeHtml(STRINGS.emailPasswordHint)} ${escapeHtml(STRINGS.emailPasswordSave)} ${escapeHtml(STRINGS.connectionHint)}</p>` +
        `<div class="panel-actions">` +
        `<button type="button" class="btn btn-primary" data-action="saveEmail"${form.savingEmail ? ' disabled' : ''}>` +
        `${escapeHtml(STRINGS.settingsSaveEmail)}</button>` +
        `<button type="button" class="btn" data-action="testConnection"${form.test && form.test.running ? ' disabled' : ''}>` +
        `${escapeHtml(form.test && form.test.running ? STRINGS.testing : STRINGS.testConnection)}</button>` +
        `</div>` +
        (form.test && !form.test.running
            ? `<div class="${form.test.ok ? 'status-ok' : 'status-err'}" role="status">${form.test.ok ? '✔' : '✖'} ${escapeHtml(form.test.message)}</div>`
            : '') +
        `</section>`;
    let banners = '';
    if (form.error) {
        banners += `<div class="error-banner" role="alert">${escapeHtml(`${STRINGS.errorBannerPrefix}${form.error}`)}</div>`;
    }
    if (form.notice) {
        banners += `<div class="notice-banner" role="status">${escapeHtml(form.notice)}</div>`;
    }
    return buildPageHtml(STRINGS.settingsHeading, banners + workspaceHtml + gmailHtml);
}

function buildTasksListHtml() {
    const page = state.tasksPage;
    if (page.loading) {
        return `<p class="page-status">${escapeHtml(STRINGS.loading)}</p>`;
    }
    if (page.error) {
        return `<div class="error-banner" role="alert">${escapeHtml(`${STRINGS.errorBannerPrefix}${page.error}`)}</div>` +
            `<p class="page-status"><button type="button" class="btn" data-action="reloadTasks">${escapeHtml(STRINGS.retry)}</button></p>`;
    }
    const items = page.items || [];
    if (!items.length) {
        return `<p class="page-status">${escapeHtml(STRINGS.noTasks)}</p>`;
    }
    return items.map((item) => {
        const enabled = item.enabled !== false;
        return `<div class="task-item${enabled ? '' : ' task-disabled'}">` +
            `<div class="task-main">` +
            `<div class="task-title-row">` +
            `<button type="button" class="task-toggle${enabled ? ' on' : ''}" data-action="task-toggle" data-id="${escapeHtml(item.id)}" ` +
            `role="switch" aria-checked="${enabled}" title="${escapeHtml(STRINGS.taskEnabledLabel)}"></button>` +
            `<strong class="task-name">${escapeHtml(item.name)}</strong>` +
            `<span class="task-schedule">${escapeHtml(item.time || '')} · ${escapeHtml(taskDaysText(item.days))}</span>` +
            `</div>` +
            `<div class="task-meta">` +
            `<span>${escapeHtml(item.model || '')}</span>` +
            (item.lastRun ? `<span>· ${escapeHtml(STRINGS.taskLastRun)}: ${escapeHtml(item.lastRun)}</span>` : '') +
            (item.lastError ? `<span class="status-err">· ✖ ${escapeHtml(item.lastError)}</span>` : '') +
            `</div>` +
            `<div class="task-tools">${(item.tools || []).map((tool) => `<span class="tool-tag">${escapeHtml(tool)}</span>`).join('')}</div>` +
            `</div>` +
            `<div class="task-actions">` +
            `<button type="button" class="btn" data-action="task-run" data-id="${escapeHtml(item.id)}">${ICONS.play}${escapeHtml(STRINGS.taskRunNow)}</button>` +
            `<button type="button" class="btn" data-action="task-log" data-id="${escapeHtml(item.id)}">${escapeHtml(STRINGS.taskLogTitle)}</button>` +
            `<button type="button" class="icon-btn" data-action="task-edit" data-id="${escapeHtml(item.id)}" ` +
            `title="${escapeHtml(STRINGS.taskEditTitle)}" aria-label="${escapeHtml(STRINGS.taskEditTitle)}">${ICONS.edit}</button>` +
            `<button type="button" class="icon-btn" data-action="task-delete" data-id="${escapeHtml(item.id)}" ` +
            `title="${escapeHtml(STRINGS.menuDelete)}" aria-label="${escapeHtml(STRINGS.menuDelete)}">${ICONS.trash}</button>` +
            `</div>` +
            `</div>`;
    }).join('');
}

function buildTaskFormHtml() {
    const form = state.taskForm;
    if (!form) {
        return '';
    }
    const dayButtons = STRINGS.dayNames.map((name, ix) => {
        const day = ix + 1;
        const on = form.days.has(day);
        return `<button type="button" class="day-toggle${on ? ' on' : ''}" data-action="task-day" data-id="${day}" ` +
            `aria-pressed="${on}" title="${escapeHtml(name)}">${escapeHtml(name)}</button>`;
    }).join('');
    const toolLabels = {
        web_search: STRINGS.toolsTaskWebSearch,
        fetch_page: STRINGS.toolsTaskFetchPage,
        check_email: STRINGS.toolsTaskCheckEmail,
        send_email: STRINGS.toolsTaskSendEmail
    };
    const toolChecks = TASK_FORM_TOOLS.map((tool) => {
        const checked = form.tools.has(tool);
        return `<label class="tool-check${checked ? ' on' : ''}">` +
            `<input type="checkbox" data-tool="${escapeHtml(tool)}"${checked ? ' checked' : ''}>` +
            `<span>${escapeHtml(toolLabels[tool] || tool)}</span></label>`;
    }).join('');
    const models = (state.models && state.models.list) || [];
    const modelOptions = models.map((model) => {
        const selected = model.id === form.model ? ' selected' : '';
        return `<option value="${escapeHtml(model.id)}"${selected}>${escapeHtml(model.id)}</option>`;
    }).join('');
    const modelSelect = modelOptions
        ? (form.model && !models.some((model) => model.id === form.model)
            ? `<option value="${escapeHtml(form.model)}" selected>${escapeHtml(form.model)}</option>` + modelOptions
            : modelOptions)
        : (() => {
              const fallback = form.model
                  ? `<option value="${escapeHtml(form.model)}" selected>${escapeHtml(form.model)}</option>`
                  : `<option value="">${escapeHtml(STRINGS.noModels)}</option>`;
              return fallback;
          })();
    return `<div class="modal-overlay" id="modal-overlay">` +
        `<div class="modal modal-wide" role="dialog" aria-modal="true" aria-label="${escapeHtml(form.id ? STRINGS.taskEditTitle : STRINGS.taskNewTitle)}">` +
        `<h2>${escapeHtml(form.id ? STRINGS.taskEditTitle : STRINGS.taskNewTitle)}</h2>` +
        (form.error ? `<p class="modal-error" role="alert">${escapeHtml(form.error)}</p>` : '') +
        `<div class="form-grid">` +
        `<label class="form-field" for="task-name"><span>${escapeHtml(STRINGS.taskNameLabel)}</span>` +
        `<input id="task-name" type="text" value="${escapeHtml(form.name)}" maxlength="200"></label>` +
        `<label class="form-field" for="task-time"><span>${escapeHtml(STRINGS.taskTimeLabel)}</span>` +
        `<input id="task-time" type="time" value="${escapeHtml(form.time)}"></label>` +
        `</div>` +
        `<div class="form-field"><span>${escapeHtml(STRINGS.taskDaysLabel)}</span><div class="day-toggles">${dayButtons}</div></div>` +
        `<label class="form-field form-row-wide" for="task-prompt"><span>${escapeHtml(STRINGS.taskPromptLabel)}</span>` +
        `<textarea id="task-prompt" rows="4">${escapeHtml(form.prompt)}</textarea></label>` +
        `<div class="form-grid">` +
        `<label class="form-field" for="task-model"><span>${escapeHtml(STRINGS.taskModelLabel)}</span>` +
        `<select id="task-model">${modelSelect}</select></label>` +
        `<label class="form-field" for="task-numctx"><span>${escapeHtml(STRINGS.taskNumCtxLabel)}</span>` +
        `<input id="task-numctx" type="number" min="128" step="128" value="${escapeHtml(form.numCtx)}" placeholder="default">` +
        `<span class="form-hint">${escapeHtml(STRINGS.taskNumCtxHint)}</span></label>` +
        `</div>` +
        `<div class="form-field"><span>${escapeHtml(STRINGS.taskToolsLabel)}</span><div class="tools-list">${toolChecks}</div>` +
        `<span class="form-hint">${escapeHtml(STRINGS.toolsTaskSendEmail)} - ${escapeHtml(STRINGS.sendEmailDefaultOff)}</span></div>` +
        `<label class="check-row"><input type="checkbox" id="task-enabled"${form.enabled ? ' checked' : ''}>` +
        `<span>${escapeHtml(STRINGS.taskEnabledLabel)}</span></label>` +
        `<div class="modal-actions">` +
        `<button type="button" class="btn" data-action="task-form-cancel">${escapeHtml(STRINGS.cancel)}</button>` +
        `<button type="button" class="btn btn-primary" data-action="task-form-save"${form.saving ? ' disabled' : ''}>` +
        `${escapeHtml(STRINGS.taskSaveLabel)}</button>` +
        `</div></div></div>`;
}

function buildTaskLogHtml() {
    const log = state.taskLog;
    if (!log) {
        return '';
    }
    return `<div class="modal-overlay" id="modal-overlay">` +
        `<div class="modal modal-wide" role="dialog" aria-modal="true" aria-label="${escapeHtml(STRINGS.taskLogTitle)}">` +
        `<h2>${escapeHtml(log.name)}</h2>` +
        (log.loading
            ? `<p class="page-status">${escapeHtml(STRINGS.loading)}</p>`
            : log.error
                ? `<div class="error-banner" role="alert">${escapeHtml(`${STRINGS.errorBannerPrefix}${log.error}`)}</div>`
                : log.text
                    ? `<pre class="task-log">${escapeHtml(log.text)}</pre>`
                    : `<p class="page-status">${escapeHtml(STRINGS.noTaskLog)}</p>`) +
        `<div class="modal-actions">` +
        `<button type="button" class="btn" data-action="task-log-close">${escapeHtml(STRINGS.close)}</button>` +
        `</div></div></div>`;
}

function buildTasksHtml() {
    const header =
        `<div class="panel-actions tasks-header">` +
        `<button type="button" class="btn btn-primary" data-action="task-new">${escapeHtml(STRINGS.newTask)}</button>` +
        `</div>`;
    const inner = header + `<div id="tasks-list">${buildTasksListHtml()}</div>`;
    return buildPageHtml(STRINGS.tasksHeading, inner);
}

function buildMdViewerHtml() {
    const viewer = state.mdViewer;
    if (!viewer) return '';
    return `<div class="md-viewer">` +
        `<div class="md-viewer-header">` +
        `<strong>${escapeHtml(viewer.name)}</strong>` +
        `<button type="button" class="btn" data-action="closeMd">${escapeHtml(STRINGS.mdClose)}</button>` +
        `</div>` +
        `<div class="md md-viewer-body">${renderMarkdown(viewer.text)}</div>` +
        `</div>`;
}

function buildMessagesHtml() {
    if (state.mdViewer) {
        return buildMdViewerHtml();
    }
    if (state.route.name === 'new') {
        return (state.error ? `<div class="error-banner" role="alert">${escapeHtml(STRINGS.errorBannerPrefix)}${escapeHtml(state.error)}</div>` : '') +
            (state.notice ? `<div class="notice-banner" role="status">${escapeHtml(state.notice)}</div>` : '') +
            `<p>${escapeHtml(STRINGS.greeting)}</p>`;
    }
    const cur = state.current;
    let html = '';
    if (state.error) {
        html += `<div class="error-banner" role="alert">${escapeHtml(STRINGS.errorBannerPrefix)}${escapeHtml(state.error)}</div>`;
    }
    if (state.notice) {
        html += `<div class="notice-banner" role="status">${escapeHtml(state.notice)}</div>`;
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
    const buttons = conversation
        ? `<button type="button" class="action-btn" data-action="download-chat" ` +
            `title="${escapeHtml(STRINGS.menuDownload)}" aria-label="${escapeHtml(STRINGS.menuDownload)}">${ICONS.download}</button>` +
            `<button type="button" class="action-btn" data-action="export-pdf" ` +
            `title="${escapeHtml(STRINGS.menuExportPdf)}" aria-label="${escapeHtml(STRINGS.menuExportPdf)}">${ICONS.pdfExport}</button>`
        : '';
    return `<div class="chat-header"><h1 class="chat-header-title">${escapeHtml(title)}</h1>${buttons}</div>`;
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
    const webSearchIcon = state.webSearchEnabled ? ICONS.globe : ICONS.globeOff;
    const webSearchTitle = state.webSearchEnabled ? STRINGS.webSearchOn : STRINGS.webSearchOff;
    const emailIcon = state.emailEnabled ? ICONS.mail : ICONS.mailOff;
    const emailTitle = state.emailEnabled ? STRINGS.emailOn : STRINGS.emailOff;
    return `<textarea id="composer-input" rows="1" placeholder="${escapeHtml(STRINGS.composerPlaceholder)}" ` +
        `aria-label="${escapeHtml(STRINGS.composerPlaceholder)}">${escapeHtml(draft)}</textarea>` +
        (uploadFiles.length ? buildUploadChipsHtml() : '') +
        `<div class="composer-row">` +
        `<div class="model-picker">` +
        (readOnly
            ? `<span class="model-pill" title="${escapeHtml(model || '')}"><span class="model-name">${escapeHtml(model || STRINGS.noModels)}</span></span>`
            : `<button type="button" class="model-pill" id="model-pill" aria-haspopup="menu" aria-expanded="${state.modelMenuOpen}" ` +
                `title="${escapeHtml(STRINGS.selectModel)}"><span class="model-name">${escapeHtml(model || STRINGS.noModels)}</span>${ICONS.chevron}</button>`) +
        buildModelMenuHtml() +
        `</div>` +
        `<button type="button" class="icon-btn${state.webSearchEnabled ? ' websearch-active' : ''}" id="websearch-btn" data-action="toggleWebSearch" ` +
        `title="${escapeHtml(webSearchTitle)}" aria-label="${escapeHtml(webSearchTitle)}">${webSearchIcon}</button>` +
        `<button type="button" class="icon-btn${state.emailEnabled ? ' email-active' : ''}" id="email-btn" data-action="toggleEmail" ` +
        `title="${escapeHtml(emailTitle)}" aria-label="${escapeHtml(emailTitle)}">${emailIcon}</button>` +
        `<button type="button" class="icon-btn${state.thinkingEnabled ? ' thinking-active' : ''}" id="thinking-btn" data-action="toggleThinking" ` +
        `title="${escapeHtml(thinkingTitle)}" aria-label="${escapeHtml(thinkingTitle)}">${thinkingIcon}</button>` +
        `<button type="button" class="icon-btn${uploadFiles.length ? ' upload-active' : ''}" id="upload-btn" data-action="uploadFile" ` +
        `title="${escapeHtml(uploadFiles.length ? `${uploadFiles.length} / ${MAX_ATTACH_FILES}` : STRINGS.uploadFile)}" aria-label="${escapeHtml(STRINGS.uploadFile)}">${ICONS.upload}</button>` +
        `<input type="file" id="file-input" accept=".txt,.md,.docx,.png,.jpg,.jpeg" multiple style="display:none">` +
        `<button type="button" class="send-btn${canSend ? ' ready' : ''}" id="send-btn" data-action="send" ` +
        `title="${escapeHtml(sendLabel)}" aria-label="${escapeHtml(sendLabel)}"${canSend || generating ? '' : ' disabled'}>${sendIcon}</button>` +
        `</div>`;
}

/** The attached-files chips shown above the composer controls. */
function buildUploadChipsHtml() {
    const chips = uploadFiles.map((file, ix) =>
        `<span class="file-chip" title="${escapeHtml(file.name)}">${ICONS.clip}` +
        `<span class="file-chip-name">${escapeHtml(file.name)}</span>` +
        `<button type="button" class="file-chip-remove" data-action="removeFile" data-ix="${ix}" ` +
        `title="${escapeHtml(STRINGS.removeFile)}" aria-label="${escapeHtml(`${STRINGS.removeFile}: ${file.name}`)}">&times;</button>` +
        `</span>`).join('');
    return `<div class="file-chips" aria-label="${escapeHtml(STRINGS.attachedFiles)}">${chips}` +
        `<span class="file-chip-count">${uploadFiles.length} / ${MAX_ATTACH_FILES}</span></div>`;
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
    const delTitle = modal.type === 'delete-task' ? STRINGS.deleteTaskTitle : STRINGS.deleteTitle;
    const delConfirm = modal.type === 'delete-task' ? STRINGS.deleteTaskConfirm : STRINGS.deleteConfirm;
    return `<div class="modal-overlay" id="modal-overlay">` +
        `<div class="modal" role="dialog" aria-modal="true" aria-label="${escapeHtml(delTitle)}">` +
        `<h2>${escapeHtml(delTitle)}</h2>` +
        (modal.error ? `<p class="modal-error" role="alert">${escapeHtml(modal.error)}</p>` : '') +
        `<p>${escapeHtml(delConfirm)}</p>` +
        `<p class="modal-target">“${escapeHtml(modal.title)}”</p>` +
        `<div class="modal-actions">` +
        `<button type="button" class="btn" data-action="modal-cancel">${escapeHtml(STRINGS.cancel)}</button>` +
        `<button type="button" class="btn btn-danger" data-action="modal-confirm">${escapeHtml(STRINGS.deleteButton)}</button>` +
        `</div></div></div>`;
}

function render() {
    const theme = currentTheme();
    const pageName = state.route.name === 'settings' ? STRINGS.settingsHeading
        : state.route.name === 'tasks' ? STRINGS.tasksHeading
        : state.route.name === 'chat' ? chatTitle(state.route.id)
        : STRINGS.appTitle;
    document.title = state.route.name === 'new' ? STRINGS.appTitle : `${pageName} - ${STRINGS.appTitle}`;

    // The settings/tasks pages show a scrolling page instead of the chat area (no composer)
    const page = state.route.name === 'settings' ? buildSettingsHtml()
        : state.route.name === 'tasks' ? buildTasksHtml()
        : null;
    const main = page !== null
        ? page
        : ((state.sidebarCollapsed ? `<button class="icon-btn sidebar-fab" id="btn-sidebar-fab" title="${escapeHtml(STRINGS.openSidebar)}" aria-label="${escapeHtml(STRINGS.openSidebar)}">${ICONS.panel}</button>` : '') +
            buildChatHeaderHtml() +
            `<div class="messages"><div class="messages-inner" id="messages">${buildMessagesHtml()}</div></div>` +
            `<div class="composer-wrap"><div class="composer">${buildComposerHtml()}</div></div>`);

    root.innerHTML =
        `<div class="layout${state.sidebarCollapsed ? ' sidebar-collapsed' : ''}" id="layout">` +
        buildSidebarHtml(theme) +
        `<main class="main">` +
        `<header class="topbar">` +
        `<button class="icon-btn" id="btn-sidebar-open" title="${escapeHtml(STRINGS.openSidebar)}" aria-label="${escapeHtml(STRINGS.openSidebar)}">${ICONS.panel}</button>` +
        `<span class="topbar-title">${escapeHtml(STRINGS.appTitle)}</span>` +
        `</header>` +
        main +
        `</main>` +
        `</div>` +
        (state.openMenuId || state.modelMenuOpen ? `<div class="overlay" id="menu-overlay"></div>` : '') +
        renderModal() +
        renderModalTask() +
        `<input type="file" id="md-file-input" accept=".md,.markdown,text/markdown" style="display:none">`;

    autoresizeComposer();
    enhanceCodeBlocks(document.getElementById('messages'));
    scrollMessagesToBottom();
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

/** The left sidebar: app nav, workspace name and the Settings/Tasks links. */
function buildSidebarHtml(theme) {
    const work = workspaceName();
    const routeName = state.route.name;
    return `<aside class="sidebar" aria-label="${escapeHtml(STRINGS.chatsHeading)}">` +
        `<div class="sidebar-toolbar">` +
        `<button class="icon-btn" id="btn-sidebar" title="${escapeHtml(STRINGS.sidebarToggle)}" aria-label="${escapeHtml(STRINGS.sidebarToggle)}">${ICONS.panel}</button>` +
        `<button class="icon-btn" id="btn-theme" title="${escapeHtml(STRINGS.themeToggle)}" aria-label="${escapeHtml(STRINGS.themeToggle)}">${theme === 'dark' ? ICONS.sun : ICONS.moon}</button>` +
        `<button class="icon-btn" id="btn-md" title="${escapeHtml(STRINGS.openMd)}" aria-label="${escapeHtml(STRINGS.openMd)}">${ICONS.md}</button>` +
        `</div>` +
        `<nav class="nav-list">` +
        `<a class="nav-item${routeName === 'new' ? ' active' : ''}" href="#/">${ICONS.newChat}<span>${escapeHtml(STRINGS.navChat)}</span></a>` +
        `<a class="nav-item${routeName === 'settings' ? ' active' : ''}" href="#/settings">${ICONS.gear}<span>${escapeHtml(STRINGS.navSettings)}</span></a>` +
        `<a class="nav-item${routeName === 'tasks' ? ' active' : ''}" href="#/tasks">${ICONS.checklist}<span>${escapeHtml(STRINGS.navTasks)}</span></a>` +
        `</nav>` +
        (work ? `<p class="workspace-label" title="${escapeHtml(state.workspace)}">${ICONS.folder}<span>${escapeHtml(work)}</span></p>` : '') +
        `<p class="chat-list-title">${escapeHtml(STRINGS.chatsHeading)}</p>` +
        `<div class="chat-list" id="chat-list">${buildSidebarListHtml()}</div>` +
        `</aside>`;
}

/** The task form and task log modals (rendered next to the shared modal). */
function renderModalTask() {
    if (state.taskLog) {
        return buildTaskLogHtml();
    }
    if (state.taskForm) {
        return buildTaskFormHtml();
    }
    return '';
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
    state.toolsOpen = {};
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
    state.notice = null;
    render();
    try {
        if (state.route.name === 'new') {
            const model = composerModel();
            if (!model) {
                throw new Error(STRINGS.errorNoModel);
            }
            const files = await readFilesAsData(uploadFiles);
            const data = await apiPost('startConversation', { model, user: text, think: state.thinkingEnabled, search: state.webSearchEnabled, email: state.emailEnabled, files });
            setDraft('');
            uploadFiles = [];
            state.sending = false;
            window.location.hash = `#/c/${data.id}`;
            await refreshConversations();
        } else {
            const files = await readFilesAsData(uploadFiles);
            await apiPost('replyConversation', { id: state.route.id, user: text, think: state.thinkingEnabled, search: state.webSearchEnabled, email: state.emailEnabled, files });
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
    const renamedId = state.modal.id;
    try {
        await apiPost('setConversationTitle', { id: renamedId, title });
        state.modal = null;
        await refreshConversations();
        if (state.current && state.current.conversation && state.current.id === renamedId) {
            state.current.conversation.title = title;
        }
        render();
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
        if (data.workspace) {
            state.workspace = data.workspace;
        }
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
    stopTasksPolling();
    state.route = parseRoute();
    state.openMenuId = null;
    state.modal = null;
    state.modelMenuOpen = false;
    state.mdViewer = null;
    state.current = null;
    state.sending = false;
    state.notice = null;
    state.taskForm = null;
    state.taskLog = null;
    state.thinkingOpen = {};
    state.toolsOpen = {};
    document.getElementById('layout')?.classList.remove('sidebar-open');
    render();
    if (state.route.name === 'chat') {
        loadConversation(state.route.id);
    } else if (state.route.name === 'settings') {
        loadSettings();
    } else if (state.route.name === 'tasks') {
        loadTasksPage();
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
            if (state.modal.type === 'delete-task') {
                submitTaskDelete();
            } else {
                submitDelete();
            }
        } else if (action === 'reloadSettings') {
            loadSettings();
        } else if (action === 'saveWorkspace') {
            submitWorkspace();
        } else if (action === 'saveEmail') {
            submitEmailSettings();
        } else if (action === 'testConnection') {
            testConnection();
        } else if (action === 'reloadTasks') {
            loadTasksPage();
        } else if (action === 'task-new') {
            openTaskForm(null);
        } else if (action === 'task-edit') {
            openTaskForm((state.tasksPage.items || []).find((task) => task.id === id) || null);
        } else if (action === 'task-delete') {
            openTaskDelete(id);
        } else if (action === 'task-run') {
            runTaskNow(id);
        } else if (action === 'task-log') {
            openTaskLog(id);
        } else if (action === 'task-toggle') {
            toggleTask(id);
        } else if (action === 'task-day') {
            const day = Number(id);
            setTaskFormField('day', day, !state.taskForm.days.has(day));
        } else if (action === 'task-form-save') {
            submitTaskForm();
        } else if (action === 'task-form-cancel') {
            state.taskForm = null;
            render();
        } else if (action === 'task-log-close') {
            state.taskLog = null;
            render();
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
        } else if (action === 'export-pdf') {
            exportCurrentChatPdf();
        } else if (action === 'send-email') {
            sendEmailDraft(Number(actionButton.dataset.ix), true);
        } else if (action === 'discard-email') {
            sendEmailDraft(Number(actionButton.dataset.ix), false);
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
        } else if (action === 'toggleWebSearch') {
            state.webSearchEnabled = !state.webSearchEnabled;
            saveWebSearchEnabled(state.webSearchEnabled);
            render();
        } else if (action === 'toggleEmail') {
            state.emailEnabled = !state.emailEnabled;
            saveEmailEnabled(state.emailEnabled);
            render();
        } else if (action === 'tools') {
            const toolIx = Number(actionButton.dataset.ix);
            state.toolsOpen[toolIx] = !isToolCallsOpen(toolIx);
            patchMessages();
        } else if (action === 'uploadFile') {
            document.getElementById('file-input')?.click();
        } else if (action === 'removeFile') {
            removeUploadFile(Number(actionButton.dataset.ix));
            state.composerFocus = true;
            render();
        } else if (action === 'closeMd') {
            state.mdViewer = null;
            render();
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
        state.taskForm = null;
        state.taskLog = null;
        render();
        return;
    }
    const button = event.target.closest ? event.target.closest('#btn-sidebar,#btn-sidebar-open,#btn-sidebar-fab,#btn-theme,#btn-md,#model-pill') : null;
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
        } else if (button.id === 'btn-md') {
            document.getElementById('md-file-input')?.click();
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
    } else if (event.key === 'Enter' && event.target && event.target.id === 'workspace-input') {
        event.preventDefault();
        submitWorkspace();
    } else if (event.key === 'Enter' && event.target && (event.target.id === 'task-name' || event.target.id === 'task-time' || event.target.id === 'task-numctx')) {
        // Enter inside a task form field - move the focus to the next field instead of submitting
        const focusables = Array.from(document.querySelectorAll('.modal .form-field input, .modal .form-field textarea'));
        const ix = focusables.indexOf(event.target);
        if (ix >= 0 && ix + 1 < focusables.length) {
            event.preventDefault();
            focusables[ix + 1].focus();
        }
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
        } else if (state.taskForm) {
            state.taskForm = null;
            render();
        } else if (state.taskLog) {
            state.taskLog = null;
            render();
        } else if (state.mdViewer) {
            state.mdViewer = null;
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
            if (files && files.length) {
                addUploadFiles(Array.from(files));
            }
            event.target.value = '';
            render();
        } else if (event.target.id === 'md-file-input') {
            const file = event.target.files && event.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = () => {
                    state.mdViewer = { name: file.name, text: String(reader.result || '') };
                    event.target.value = '';
                    render();
                    enhanceCodeBlocks(document.getElementById('messages'));
                };
                reader.onerror = () => {
                    state.error = `${STRINGS.errorBannerPrefix}Failed to read ${file.name}`;
                    event.target.value = '';
                    render();
                };
                reader.readAsText(file);
            } else {
                event.target.value = '';
            }
        } else if (event.target.matches && event.target.matches('input[data-tool]')) {
            setTaskFormField('tool', event.target.dataset.tool, event.target.checked);
        } else if (event.target.id === 'task-enabled') {
            setTaskFormField('enabled', event.target.checked);
        } else if (event.target.id === 'task-model') {
            if (state.taskForm) {
                state.taskForm.model = event.target.value;
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
    } else if (state.route.name === 'settings') {
        loadSettings();
    } else if (state.route.name === 'tasks') {
        loadTasksPage();
    } else {
        render();
    }
}

init();

export { STRINGS, parseRoute, renderMarkdown, escapeHtml, apiGet, apiPost, buildMarkdownFilename, buildMarkdownExport };
