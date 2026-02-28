// Init lucide icons
lucide.createIcons();

// DOM Elements
const views = {
    login: document.getElementById('login-view'),
    dashboard: document.getElementById('dashboard-view')
};

const sections = {
    devices: document.getElementById('devices-section'),
    settings: document.getElementById('settings-section'),
    logs: document.getElementById('logs-section')
};

// State
let isAuthenticated = false;
let ws = null;

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    await checkAuthStatus();
    setupEventListeners();
    setupWebSocket();
});

function setupWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/ws`;

    ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.type === 'device_change') {
                loadDevices();
                loadLogs(); // Re-fetch logs smoothly
            } else if (data.type === 'log_change') {
                appendLog(data.log);
            }
        } catch (e) { }
    };

    ws.onclose = () => {
        setTimeout(setupWebSocket, 3000);
    };
}

// Auth Flow
async function checkAuthStatus() {
    try {
        const res = await fetch('/api/auth/status');

        if (!res.ok) {
            isAuthenticated = false;
            showView('login');
            return;
        }

        const data = await res.json();

        if (!data.auth_enabled) {
            isAuthenticated = true;
            showView('dashboard');
            loadDevices();
            loadConfig();
            return;
        }

        if (data.authenticated) {
            isAuthenticated = true;
            showView('dashboard');
            loadDevices();
            loadConfig();
        } else {
            isAuthenticated = false;
            showView('login');
        }
    } catch (e) {
        isAuthenticated = false;
        showView('login');
    }
}

// Event Listeners
function setupEventListeners() {
    // Login
    document.getElementById('login-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const user = document.getElementById('username').value;
        const pass = document.getElementById('password').value;
        const errorEl = document.getElementById('login-error');

        try {
            const res = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: user, password: pass })
            });

            if (res.ok) {
                isAuthenticated = true;
                errorEl.classList.add('hidden');
                showView('dashboard');
                loadDevices();
                loadConfig();
            } else {
                errorEl.textContent = 'Invalid username or password';
                errorEl.classList.remove('hidden');
            }
        } catch (err) {
            errorEl.textContent = 'Connection error';
            errorEl.classList.remove('hidden');
        }
    });

    // Logout
    document.getElementById('logout-btn').addEventListener('click', async () => {
        await fetch('/api/auth/logout', { method: 'POST' });
        isAuthenticated = false;
        showView('login');
        document.getElementById('password').value = '';
    });

    // Tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            e.currentTarget.classList.add('active');

            const targetId = e.currentTarget.getAttribute('data-target');
            Object.values(sections).forEach(s => s.classList.add('hidden'));
            document.getElementById(targetId).classList.remove('hidden');

            if (targetId === 'devices-section') loadDevices();
            if (targetId === 'logs-section') loadLogs();
        });
    });

    // Refresh Devices
    document.getElementById('refresh-devices-btn').addEventListener('click', () => {
        const icon = document.querySelector('#refresh-devices-btn i');
        icon.classList.add('spin');
        loadDevices().finally(() => {
            setTimeout(() => icon.classList.remove('spin'), 500);
        });
    });

    // Refresh Logs
    document.getElementById('refresh-logs-btn').addEventListener('click', () => {
        const icon = document.querySelector('#refresh-logs-btn i');
        icon.classList.add('spin');
        loadLogs().finally(() => {
            setTimeout(() => icon.classList.remove('spin'), 500);
        });
    });

    // Save Settings
    document.getElementById('config-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const msgEl = document.getElementById('config-msg');

        const payload = {
            auth_enabled: document.getElementById('auth_enabled').checked,
            auth_username: document.getElementById('config_username').value,
            auth_password: document.getElementById('config_password').value,
            log_level: document.getElementById('log_level').value,
            app_port: parseInt(document.getElementById('app_port').value, 10) || 8000
        };

        try {
            const res = await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                document.getElementById('config_password').value = ''; // Clear password field
                msgEl.classList.remove('hidden');
                showToast("Settings saved successfully");
                setTimeout(() => msgEl.classList.add('hidden'), 3000);
            }
        } catch (err) {
            showToast("Failed to save settings", true);
        }
    });
}

// Data Fetching
async function loadLogs() {
    const el = document.getElementById('log-output');
    try {
        const res = await fetch('/api/logs');
        if (!res.ok) throw new Error("Could not load logs");
        const data = await res.json();

        if (data.logs && data.logs.length > 0) {
            el.textContent = data.logs.join('\n');
            el.scrollTop = el.scrollHeight; // Auto-scroll to bottom
        } else {
            el.textContent = "No logs available.";
        }
    } catch (err) {
        el.textContent = "Error loading logs.";
    }
}

function appendLog(logLine) {
    const el = document.getElementById('log-output');
    if (!el) return;

    // Provide an initial line break if already populated
    if (el.textContent && el.textContent !== "No logs available.") {
        el.textContent += '\\n';
    } else {
        el.textContent = ''; // clear placeholder
    }
    el.textContent += logLine;
    el.scrollTop = el.scrollHeight;
}
async function loadDevices() {
    const container = document.getElementById('device-list');

    try {
        const res = await fetch('/api/devices');
        if (!res.ok) {
            if (res.status === 401) checkAuthStatus();
            throw new Error("Failed to load");
        }

        const data = await res.json();

        if (data.devices.length === 0) {
            container.innerHTML = `<div class="loading-state"><i data-lucide="usb" style="width:48px;height:48px;opacity:0.5;margin-bottom:1rem"></i>No USB devices found</div>`;
        } else {
            container.innerHTML = data.devices.map(dev => {
                const actionBtn = dev.bound
                    ? `<button class="btn btn-danger" onclick="unbindDevice('${dev.busid}')"><i data-lucide="link-2-off"></i> Unbind</button>`
                    : `<button class="btn btn-success" onclick="bindDevice('${dev.busid}')"><i data-lucide="link-2"></i> Bind</button>`;

                let snippetHtml = '';
                if (dev.bound) {
                    const hostname = window.location.hostname;
                    const command = `usbip attach --remote ${hostname} --busid ${dev.busid}`;
                    snippetHtml = `
                        <div style="margin-top: 1rem; padding: 0.75rem; background: rgba(0,0,0,0.1); border-radius: 6px; font-family: monospace; font-size: 0.85em; display: flex; justify-content: space-between; align-items: center;">
                            <span>${command}</span>
                            <button class="btn btn-secondary" style="padding: 4px 8px; min-width: auto" title="Copy Client Command" onclick="navigator.clipboard.writeText('${command}'); showToast('Command copied to clipboard!');">
                                <i data-lucide="copy"></i>
                            </button>
                        </div>
                    `;
                }

                return `
                <div class="device-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; gap: 1rem;">
                        <div class="device-info" style="flex: 1; min-width: 0;">
                            <h3 style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${dev.name}">${dev.name}</h3>
                            <div class="device-meta" style="display: flex; align-items: center; gap: 10px;">
                                <span><i data-lucide="hash"></i> ID: ${dev.busid}</span>
                                ${dev.attached ? '<span style="color: var(--success); background: rgba(16, 185, 129, 0.1); padding: 2px 8px; border-radius: 4px; font-weight: 500; display: inline-flex; align-items: center; gap: 4px; font-size: 0.85em;"><i data-lucide="plug-zap" style="width:14px;height:14px;"></i> Active Connection</span>' : ''}
                            </div>
                        </div>
                        <div style="flex-shrink: 0;">
                            ${actionBtn}
                        </div>
                    </div>
                    ${snippetHtml}
                </div>
                `;
            }).join('');
        }
        lucide.createIcons();
    } catch (err) {
        container.innerHTML = `<div class="error-msg">Failed to load devices. Is usbip installed?</div>`;
    }
}

async function loadConfig() {
    try {
        const res = await fetch('/api/config');
        if (!res.ok) return;

        const config = await res.json();
        document.getElementById('auth_enabled').checked = config.auth_enabled;
        document.getElementById('config_username').value = config.auth_username;
        document.getElementById('log_level').value = config.log_level;
        document.getElementById('app_port').value = config.app_port || 8000;
    } catch (e) {
        console.error("Failed to load config", e);
    }
}

// Device Actions
window.bindDevice = async (busid) => {
    try {
        const res = await fetch('/api/devices/bind', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ busid })
        });
        if (res.ok) {
            showToast(`Successfully bound device ${busid}`);
            loadDevices();
        } else {
            showToast(`Failed to bind device ${busid}`, true);
        }
    } catch (e) {
        showToast("Connection error", true);
    }
};

window.unbindDevice = async (busid) => {
    try {
        const res = await fetch('/api/devices/unbind', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ busid })
        });
        if (res.ok) {
            showToast(`Successfully unbound device ${busid}`);
            loadDevices();
        } else {
            showToast(`Failed to unbind device ${busid}`, true);
        }
    } catch (e) {
        showToast("Connection error", true);
    }
};

// Utilities
function showView(viewName) {
    Object.values(views).forEach(v => v.classList.add('hidden'));
    views[viewName].classList.remove('hidden');
}

function showToast(message, isError = false) {
    const toast = document.getElementById('toast');
    const msg = document.getElementById('toast-msg');
    const icon = toast.querySelector('i');

    msg.textContent = message;

    if (isError) {
        toast.style.borderColor = 'var(--danger)';
        icon.setAttribute('data-lucide', 'alert-circle');
        icon.style.color = 'var(--danger)';
    } else {
        toast.style.borderColor = 'var(--success)';
        icon.setAttribute('data-lucide', 'check-circle');
        icon.style.color = 'var(--success)';
    }

    lucide.createIcons();

    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}
