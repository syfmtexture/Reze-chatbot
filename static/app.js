/* ═══════════════════════════════════════════
   REZE CONTROL PANEL — Frontend Logic
   ═══════════════════════════════════════════ */

const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

let configCache = {};
let configDirty = false;
let defaultPersona = '';
let statusInterval = null;

// ═══ INIT ═══
document.addEventListener('DOMContentLoaded', async () => {
    const res = await api('/api/auth-check');
    if (res.authenticated) showDashboard();
    setupLoginForm();
    setupNavigation();
    setupLogout();
});

// ═══ API HELPER ═══
async function api(url, opts = {}) {
    try {
        const res = await fetch(url, {
            headers: { 'Content-Type': 'application/json' },
            ...opts,
        });
        return await res.json();
    } catch (e) {
        console.error('API Error:', e);
        return { error: e.message };
    }
}

// ═══ TOAST ═══
function toast(msg, type = 'success') {
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = msg;
    $('#toastContainer').appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300); }, 3000);
}

// ═══ AUTH ═══
function setupLoginForm() {
    $('#loginForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const pw = $('#loginPassword').value;
        if (!pw) return;
        const res = await api('/api/login', { method: 'POST', body: JSON.stringify({ password: pw }) });
        if (res.success) {
            showDashboard();
        } else {
            $('#loginError').textContent = 'wrong password lol';
            $('#loginPassword').value = '';
        }
    });
}

function showDashboard() {
    $('#loginGate').style.display = 'none';
    $('#dashboard').style.display = 'flex';
    loadPage('overview');
    statusInterval = setInterval(loadStatus, 15000);
}

function setupLogout() {
    $('#logoutBtn').addEventListener('click', async () => {
        await api('/api/logout', { method: 'POST' });
        clearInterval(statusInterval);
        $('#dashboard').style.display = 'none';
        $('#loginGate').style.display = 'flex';
        $('#loginPassword').value = '';
        $('#loginError').textContent = '';
    });
}

// ═══ NAVIGATION ═══
function setupNavigation() {
    $$('.nav-btn[data-page]').forEach(btn => {
        btn.addEventListener('click', () => {
            const page = btn.dataset.page;
            $$('.nav-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            $$('.page').forEach(p => p.classList.remove('active'));
            const target = $(`#page-${page}`);
            if (target) target.classList.add('active');
            $('#pageTitle').textContent = btn.querySelector('span').textContent;
            loadPage(page);
        });
    });
}

// ═══ PAGE LOADER ═══
async function loadPage(page) {
    switch (page) {
        case 'overview': await loadStatus(); await loadMoods(); await loadGrudges(); break;
        case 'config': await loadConfig(); break;
        case 'personality': await loadPersonality(); break;
        case 'users': await loadUsers(); break;
        case 'memory': await loadChannels(); break;
        case 'tasks': await loadTasks(); break;
    }
}

// ═══ OVERVIEW ═══
async function loadStatus() {
    const s = await api('/api/status');
    if (s.error) return;
    $('#statBotName').textContent = s.bot_name;
    $('#statBotId').textContent = `ID: ${s.bot_id}`;
    $('#statUptime').textContent = s.uptime;
    $('#statGuilds').textContent = s.guild_count;
    $('#statCurrentKey').textContent = s.current_api_key;
    $('#statKeyCount').textContent = s.api_key_count;
    $('#modelBadge').textContent = s.model;
    const dot = $('.live-dot');
    const txt = $('.live-text');
    if (s.is_ready) {
        dot.classList.add('online');
        txt.textContent = 'online';
    } else {
        dot.classList.remove('online');
        txt.textContent = 'offline';
    }
}

async function loadMoods() {
    const moods = await api('/api/moods');
    const grid = $('#moodGrid');
    if (!moods || Object.keys(moods).length === 0) {
        grid.innerHTML = '<div class="mood-empty">no active channels yet</div>';
        return;
    }
    grid.innerHTML = '';
    for (const [ch, data] of Object.entries(moods)) {
        const tag = document.createElement('div');
        tag.className = 'mood-tag';
        const label = ch.startsWith('dm_') ? `DM` : `#${ch.slice(-4)}`;
        tag.innerHTML = `<span class="mood-dot ${data.mood}"></span>${label}: ${data.mood}`;
        grid.appendChild(tag);
    }
}

async function loadGrudges() {
    const grudges = await api('/api/grudges');
    const list = $('#grudgeList');
    if (!grudges || Object.keys(grudges).length === 0) {
        list.innerHTML = `<div class="mood-empty">nobody's pissed her off... yet</div>`;
        return;
    }
    list.innerHTML = '';
    for (const [uid, data] of Object.entries(grudges)) {
        if (data.expired) continue;
        const item = document.createElement('div');
        item.className = 'grudge-item';
        const mins = Math.ceil(data.expires_in / 60);
        item.innerHTML = `<span>User ${uid} — ${mins}m left</span><button class="grudge-clear" data-uid="${uid}">forgive</button>`;
        list.appendChild(item);
    }
    if (!list.children.length) {
        list.innerHTML = `<div class="mood-empty">nobody's pissed her off... yet</div>`;
    }
    list.querySelectorAll('.grudge-clear').forEach(btn => {
        btn.addEventListener('click', async () => {
            await api(`/api/grudges/${btn.dataset.uid}`, { method: 'DELETE' });
            toast('grudge cleared');
            loadGrudges();
        });
    });
}

// ═══ CONFIG ═══
const CONFIG_SCHEMA = {
    'Human Behavior': [
        { key: 'left_on_read_react_chance', label: 'Left on Read (React)', type: 'range', min: 0, max: 1, step: 0.05 },
        { key: 'left_on_read_ignore_chance', label: 'Left on Read (Full Ignore)', type: 'range', min: 0, max: 1, step: 0.05 },
        { key: 'late_reply_chance', label: 'Late Reply Chance', type: 'range', min: 0, max: 1, step: 0.01 },
        { key: 'typing_hesitation_chance', label: 'Typing Hesitation', type: 'range', min: 0, max: 1, step: 0.01 },
        { key: 'typo_chance_normal', label: 'Typo Rate (Normal)', type: 'range', min: 0, max: 0.5, step: 0.01 },
        { key: 'typo_chance_drunk', label: 'Typo Rate (Drunk)', type: 'range', min: 0, max: 0.5, step: 0.01 },
        { key: 'message_edit_chance', label: 'Message Edit Chance', type: 'range', min: 0, max: 0.2, step: 0.005 },
        { key: 'message_delete_chance_normal', label: 'Delete Regret (Normal)', type: 'range', min: 0, max: 0.1, step: 0.005 },
        { key: 'message_delete_chance_drunk', label: 'Delete Regret (Drunk)', type: 'range', min: 0, max: 0.3, step: 0.01 },
        { key: 'screenshot_paranoia_chance', label: 'Screenshot Paranoia', type: 'range', min: 0, max: 0.2, step: 0.005 },
        { key: 'eavesdrop_chance', label: 'Eavesdrop Chance', type: 'range', min: 0, max: 0.3, step: 0.01 },
        { key: 'status_roast_chance', label: 'Status Roast Chance', type: 'range', min: 0, max: 0.5, step: 0.01 },
    ],
    'Rate Limiting': [
        { key: 'rate_limit_count', label: 'Max Messages', type: 'number', min: 1, max: 20 },
        { key: 'rate_limit_window', label: 'Window (seconds)', type: 'number', min: 10, max: 120 },
        { key: 'grudge_trigger_count', label: 'Grudge Trigger (pings)', type: 'number', min: 2, max: 10 },
        { key: 'grudge_duration_min', label: 'Grudge Min (seconds)', type: 'number', min: 60, max: 1800 },
        { key: 'grudge_duration_max', label: 'Grudge Max (seconds)', type: 'number', min: 120, max: 3600 },
    ],
    'Media Pipeline': [
        { key: 'image_cooldown_min', label: 'Image Cooldown Min', type: 'number', min: 0, max: 10 },
        { key: 'image_cooldown_max', label: 'Image Cooldown Max', type: 'number', min: 1, max: 20 },
        { key: 'max_files_per_message', label: 'Max Files/Message', type: 'number', min: 1, max: 10 },
        { key: 'max_file_size_mb', label: 'Max File Size (MB)', type: 'number', min: 1, max: 25 },
    ],
    'AI Engine': [
        { key: 'temperature', label: 'Temperature', type: 'range', min: 0, max: 2, step: 0.05 },
        { key: 'mood_duration_hours', label: 'Mood Duration (hours)', type: 'number', min: 1, max: 24 },
        { key: 'memory_compress_threshold', label: 'Memory Compress At', type: 'number', min: 10, max: 50 },
        { key: 'memory_keep_count', label: 'Messages to Keep', type: 'number', min: 5, max: 30 },
        { key: 'return_detection_days', label: 'Return Detection (days)', type: 'number', min: 1, max: 14 },
    ],
    'Background Timing': [
        { key: 'unprompted_min_interval', label: 'Unprompted Min (sec)', type: 'number', min: 300, max: 7200 },
        { key: 'unprompted_max_interval', label: 'Unprompted Max (sec)', type: 'number', min: 600, max: 14400 },
        { key: 'unprompted_chance', label: 'Unprompted Chance', type: 'range', min: 0, max: 1, step: 0.05 },
        { key: 'wrong_chat_min_interval', label: 'Wrong Chat Min (sec)', type: 'number', min: 1800, max: 36000 },
        { key: 'wrong_chat_chance', label: 'Wrong Chat Chance', type: 'range', min: 0, max: 0.5, step: 0.01 },
        { key: 'story_min_interval', label: 'Story Min (sec)', type: 'number', min: 7200, max: 172800 },
    ],
};

async function loadConfig() {
    configCache = await api('/api/config');
    if (configCache.error) return;
    const container = $('#configSections');
    container.innerHTML = '';

    for (const [group, fields] of Object.entries(CONFIG_SCHEMA)) {
        const section = document.createElement('div');
        section.className = 'config-group';
        section.innerHTML = `<div class="config-group-title">${group}</div>`;

        for (const field of fields) {
            const val = configCache[field.key];
            const row = document.createElement('div');
            row.className = 'config-row';

            if (field.type === 'range') {
                const pct = Math.round((val || 0) * 100);
                row.innerHTML = `
                    <div class="config-label">${field.label}</div>
                    <div class="config-control">
                        <span class="config-val" id="val-${field.key}">${field.step < 0.01 ? val : pct + '%'}</span>
                        <input type="range" min="${field.min}" max="${field.max}" step="${field.step}" value="${val || 0}" data-key="${field.key}">
                    </div>`;
            } else {
                row.innerHTML = `
                    <div class="config-label">${field.label}</div>
                    <div class="config-control">
                        <input type="number" min="${field.min}" max="${field.max}" value="${val || 0}" data-key="${field.key}">
                    </div>`;
            }
            section.appendChild(row);
        }
        container.appendChild(section);
    }

    // Bind events
    container.querySelectorAll('input[type="range"]').forEach(el => {
        el.addEventListener('input', () => {
            const key = el.dataset.key;
            const v = parseFloat(el.value);
            const field = Object.values(CONFIG_SCHEMA).flat().find(f => f.key === key);
            const display = $(`#val-${key}`);
            if (display) display.textContent = (field && field.step >= 0.01 && field.max <= 1) ? Math.round(v * 100) + '%' : v;
            configCache[key] = v;
            showConfigActions();
        });
    });
    container.querySelectorAll('input[type="number"]').forEach(el => {
        el.addEventListener('change', () => {
            configCache[el.dataset.key] = parseFloat(el.value);
            showConfigActions();
        });
    });

    $('#saveConfigBtn').onclick = async () => {
        await api('/api/config', { method: 'POST', body: JSON.stringify(configCache) });
        toast('config saved');
        hideConfigActions();
    };
    $('#resetConfigBtn').onclick = () => { loadConfig(); hideConfigActions(); };
    hideConfigActions();
}

function showConfigActions() { $('.config-actions').classList.add('visible'); }
function hideConfigActions() { $('.config-actions').classList.remove('visible'); }

// ═══ PERSONALITY ═══
async function loadPersonality() {
    const data = await api('/api/personality');
    const editor = $('#personaEditor');
    editor.value = data.prompt || '';
    defaultPersona = data.prompt || '';
    updateLineNumbers();
    updateCharCount();

    editor.addEventListener('input', () => { updateLineNumbers(); updateCharCount(); });
    editor.addEventListener('scroll', () => {
        $('#editorGutter').scrollTop = editor.scrollTop;
    });

    $('#savePersonaBtn').onclick = async () => {
        await api('/api/personality', { method: 'POST', body: JSON.stringify({ prompt: editor.value }) });
        toast('personality saved');
    };
    $('#resetPersonaBtn').onclick = () => {
        if (confirm('revert to the default prompt?')) {
            editor.value = defaultPersona;
            updateLineNumbers();
            updateCharCount();
        }
    };
}

function updateLineNumbers() {
    const lines = $('#personaEditor').value.split('\n').length;
    const gutter = $('#editorGutter');
    gutter.innerHTML = Array.from({ length: lines }, (_, i) => `<div style="padding:0 8px">${i + 1}</div>`).join('');
}

function updateCharCount() {
    const len = $('#personaEditor').value.length;
    $('#charCount').textContent = `${len.toLocaleString()} chars`;
}

// ═══ USERS ═══
async function loadUsers() {
    const users = await api('/api/users');
    const grid = $('#usersGrid');
    if (!users || users.error || !users.length) {
        grid.innerHTML = '<div class="mood-empty">no users tracked yet</div>';
        return;
    }
    renderUsers(users);
    $('#userSearch').addEventListener('input', (e) => {
        const q = e.target.value.toLowerCase();
        const filtered = users.filter(u => (u.display_name || '').toLowerCase().includes(q) || u._id.includes(q));
        renderUsers(filtered);
    });
}

function renderUsers(users) {
    const grid = $('#usersGrid');
    grid.innerHTML = '';
    for (const u of users) {
        const initial = (u.display_name || '?')[0].toUpperCase();
        const closeness = u.closeness || 0;
        const lastSeen = u.last_seen ? new Date(u.last_seen).toLocaleDateString() : 'never';
        const card = document.createElement('div');
        card.className = 'user-card';
        card.innerHTML = `
            <div class="user-card-top">
                <div class="user-avatar">${initial}</div>
                <div>
                    <div class="user-name">${u.display_name || 'Unknown'}</div>
                    <div class="user-id">${u._id}</div>
                </div>
            </div>
            <div class="user-stats">
                <div class="user-stat"><div class="user-stat-val">${u.total_messages || 0}</div><div class="user-stat-label">msgs</div></div>
                <div class="user-stat"><div class="user-stat-val">${u.streak_days || 0}</div><div class="user-stat-label">streak</div></div>
                <div class="user-stat"><div class="user-stat-val">${closeness.toFixed(1)}</div><div class="user-stat-label">close</div></div>
                <div class="user-stat"><div class="user-stat-val">${lastSeen}</div><div class="user-stat-label">seen</div></div>
            </div>
            <div class="closeness-bar"><div class="closeness-fill" style="width:${closeness * 10}%"></div></div>
            <textarea class="user-notes" placeholder="no notes yet..." data-uid="${u._id}">${u.notes || ''}</textarea>
            <button class="user-save-btn" data-uid="${u._id}">save notes</button>`;
        grid.appendChild(card);
    }
    grid.querySelectorAll('.user-save-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const uid = btn.dataset.uid;
            const notes = grid.querySelector(`.user-notes[data-uid="${uid}"]`).value;
            await api(`/api/users/${uid}/notes`, { method: 'POST', body: JSON.stringify({ notes }) });
            toast('notes saved');
        });
    });
}

// ═══ MEMORY ═══
let activeChannel = null;

async function loadChannels() {
    const channels = await api('/api/memory');
    const list = $('#channelList');
    if (!channels || channels.error || !channels.length) {
        list.innerHTML = '<div class="mood-empty">no channels with memory</div>';
        return;
    }
    list.innerHTML = '';
    for (const ch of channels) {
        const item = document.createElement('div');
        item.className = 'channel-item';
        const label = ch.channel_id.startsWith('dm_') ? `DM ${ch.channel_id.slice(3, 7)}...` : `#${ch.channel_id.slice(-6)}`;
        item.innerHTML = `${label} <span class="ch-count">${ch.message_count}</span>`;
        item.addEventListener('click', () => {
            list.querySelectorAll('.channel-item').forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            loadMemory(ch.channel_id);
        });
        list.appendChild(item);
    }
}

async function loadMemory(channelId) {
    activeChannel = channelId;
    const data = await api(`/api/memory/${channelId}`);
    const label = channelId.startsWith('dm_') ? `DM ${channelId.slice(3)}` : `Channel ${channelId}`;
    $('#memoryTitle').textContent = label;
    $('#memoryActions').style.display = 'flex';

    if (data.summary) {
        $('#memorySummary').style.display = 'block';
        $('#summaryText').textContent = data.summary;
    } else {
        $('#memorySummary').style.display = 'none';
    }

    const log = $('#chatLog');
    if (!data.messages || !data.messages.length) {
        log.innerHTML = '<div class="chat-empty">no messages in memory</div>';
        return;
    }
    log.innerHTML = '';
    for (const msg of data.messages) {
        const el = document.createElement('div');
        el.className = `chat-msg ${msg.role}`;
        el.textContent = msg.content;
        log.appendChild(el);
    }
    log.scrollTop = log.scrollHeight;

    $('#wipeMemoryBtn').onclick = async () => {
        if (!confirm(`wipe all memory for ${label}?`)) return;
        await api(`/api/memory/${channelId}`, { method: 'DELETE' });
        toast('memory wiped');
        loadChannels();
        $('#chatLog').innerHTML = '<div class="chat-empty">memory wiped</div>';
        $('#memorySummary').style.display = 'none';
        $('#memoryActions').style.display = 'none';
    };

    $('#editSummaryBtn').onclick = () => {
        const current = data.summary || '';
        const newSummary = prompt('Edit long-term summary:', current);
        if (newSummary !== null) {
            api(`/api/memory/${channelId}/summary`, { method: 'POST', body: JSON.stringify({ summary: newSummary }) });
            $('#summaryText').textContent = newSummary;
            toast('summary updated');
        }
    };
}

// ═══ TASKS ═══
async function loadTasks() {
    const tasks = await api('/api/tasks');
    if (tasks.error) return;
    for (const [key, val] of Object.entries(tasks)) {
        const el = $(`#task-${key}`);
        if (el) el.checked = val;
    }
    $$('.toggle input').forEach(el => {
        el.onchange = async () => {
            const task = el.dataset.task;
            await api('/api/tasks', { method: 'POST', body: JSON.stringify({ [task]: el.checked }) });
            toast(`${task} ${el.checked ? 'enabled' : 'disabled'}`);
        };
    });
}
