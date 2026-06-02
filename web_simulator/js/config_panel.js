// Config tab for the simulator's right-hand panel.
//
// Reads the live `Config` objects out of MicroPython (system, controller,
// per-app, per-service), renders a form, applies edits in-place via
// `Config.update()` (which also persists to JSON in Emscripten MEMFS), and
// can flash all config JSON files to a real badge over Web Serial.

import { runFlash, flashSupported } from './flash.js?v=17';

const SCOPE_LOADING_OPT = 'Loading…';

let _state = {
    mp: null,
    addLog: (m) => console.log(m),
    scopes: null,         // { scopeKey: { configKey: value, ... } }
    activeScope: null,    // string, e.g. "system"
    pendingTimer: null,   // debounce for range sliders
};

// ── Tab switching (called early, before MicroPython is ready). ────────────
export function initTabs() {
    const tabs = document.querySelectorAll('.ctrl-tab');
    const panels = document.querySelectorAll('.ctrl-tab-content');
    tabs.forEach((tab) => {
        tab.addEventListener('click', () => {
            const target = tab.dataset.tab;
            tabs.forEach(t => t.classList.toggle('active', t === tab));
            panels.forEach(p => {
                p.classList.toggle('active', p.id === `control-tab-${target}`);
            });
        });
    });
}

// ── Config panel boot (after controller exists). ──────────────────────────
export async function initConfigPanel({ mp, addLog }) {
    _state.mp = mp;
    _state.addLog = addLog || _state.addLog;

    const scopeSel = document.getElementById('config-scope');
    const refreshBtn = document.getElementById('config-refresh');
    const flashBtn = document.getElementById('config-flash');

    scopeSel.addEventListener('change', () => {
        _state.activeScope = scopeSel.value;
        renderScope(_state.activeScope);
    });

    refreshBtn.addEventListener('click', () => { reload(); });

    if (!flashSupported()) {
        flashBtn.disabled = true;
        flashBtn.classList.add('unsupported');
        flashBtn.title = 'Web Serial unavailable — open this page in Chrome or Edge.';
    } else {
        flashBtn.disabled = false;
        flashBtn.addEventListener('click', () => {
            runFlash({
                label: 'configs',
                getFiles: getConfigFiles,
                addLog: _state.addLog,
                buttons: [flashBtn],
            });
        });
    }

    await reload();
}

async function reload() {
    setStatus('');
    try {
        _state.scopes = await loadConfigs();
    } catch (e) {
        setStatus(`Failed to load configs: ${e.message || e}`, 'error');
        return;
    }
    const scopeSel = document.getElementById('config-scope');
    const keys = Object.keys(_state.scopes);
    scopeSel.innerHTML = '';
    if (keys.length === 0) {
        const opt = document.createElement('option');
        opt.textContent = '(no configs)';
        scopeSel.appendChild(opt);
        scopeSel.disabled = true;
        document.getElementById('config-body').innerHTML =
            '<div class="config-placeholder">No configs registered yet.</div>';
        return;
    }
    for (const k of keys) {
        const opt = document.createElement('option');
        opt.value = k;
        opt.textContent = k;
        scopeSel.appendChild(opt);
    }
    scopeSel.disabled = false;
    if (!_state.activeScope || !_state.scopes[_state.activeScope]) {
        _state.activeScope = keys[0];
    }
    scopeSel.value = _state.activeScope;
    renderScope(_state.activeScope);
}

async function loadConfigs() {
    const code = `
import json as _json
def _flatten(v):
    # MicroPython's dict(d) doesn't handle dict subclasses the way CPython
    # does — it falls back to iterating keys, which loses values. Iterate
    # via .items() instead.
    if isinstance(v, dict):
        return {k: vv for k, vv in v.items()}
    return v
def _dump_scope(cfg):
    return {k: _flatten(v) for k, v in cfg.items()}
_scopes = {
    'system': _dump_scope(controller.system_config.config),
    'controller': _dump_scope(controller.config),
}
for _name, _cfg in controller.app_configs.items():
    _scopes['app:' + _name] = _dump_scope(_cfg)
for _name, _cfg in controller.service_configs.items():
    _scopes['service:' + _name] = _dump_scope(_cfg)
_config_dump = _json.dumps(_scopes)
`;
    await _state.mp.runPythonAsync(code);
    const dump = _state.mp.pyimport('__main__')._config_dump;
    return JSON.parse(dump);
}

function renderScope(scopeKey) {
    const body = document.getElementById('config-body');
    body.innerHTML = '';
    const scope = _state.scopes[scopeKey];
    if (!scope) {
        body.innerHTML = '<div class="config-placeholder">Unknown scope.</div>';
        return;
    }
    const keys = Object.keys(scope);
    if (keys.length === 0) {
        body.innerHTML = '<div class="config-placeholder">(empty)</div>';
        return;
    }
    for (const key of keys) {
        const value = scope[key];
        const row = buildRow(scopeKey, key, value);
        body.appendChild(row);
    }
}

function buildRow(scopeKey, key, value) {
    const row = document.createElement('div');
    row.className = 'config-row';

    if (value && typeof value === 'object' && 'type' in value) {
        const t = value.type;
        if (t === 'RangeConfig' || t === 'ColorConfig') {
            return buildRangeRow(row, scopeKey, key, value);
        }
        if (t === 'EnumConfig' || t === 'BoolDropdownConfig') {
            return buildEnumRow(row, scopeKey, key, value);
        }
        // Unknown SmartConfigValue subclass — render read-only JSON.
        const label = document.createElement('label');
        label.textContent = `${key} (${t}, read-only)`;
        const pre = document.createElement('div');
        pre.className = 'val';
        pre.textContent = JSON.stringify(value);
        row.appendChild(label);
        row.appendChild(pre);
        return row;
    }

    // Plain primitive
    if (typeof value === 'boolean') {
        return buildBoolRow(row, scopeKey, key, value);
    }
    return buildTextRow(row, scopeKey, key, value);
}

function buildRangeRow(row, scopeKey, key, cfg) {
    const labelEl = document.createElement('label');
    const nameSpan = document.createElement('span');
    nameSpan.textContent = cfg.name || key;
    const valSpan = document.createElement('span');
    valSpan.className = 'val';
    valSpan.textContent = String(cfg.current);
    labelEl.appendChild(nameSpan);
    labelEl.appendChild(valSpan);

    const input = document.createElement('input');
    input.type = 'range';
    input.min = String(cfg.min);
    input.max = String(cfg.max);
    input.step = String(cfg.step || 1);
    input.value = String(cfg.current);

    input.addEventListener('input', () => {
        valSpan.textContent = input.value;
    });
    input.addEventListener('change', () => {
        scheduleUpdate(scopeKey, key, Number(input.value));
    });
    // Also fire while dragging, but debounced.
    input.addEventListener('input', () => {
        scheduleUpdate(scopeKey, key, Number(input.value), 250);
    });

    row.appendChild(labelEl);
    row.appendChild(input);
    return row;
}

function buildEnumRow(row, scopeKey, key, cfg) {
    const labelEl = document.createElement('label');
    const nameSpan = document.createElement('span');
    nameSpan.textContent = cfg.name || key;
    labelEl.appendChild(nameSpan);

    const select = document.createElement('select');
    for (const opt of (cfg.options || [])) {
        const o = document.createElement('option');
        o.value = opt;
        o.textContent = opt;
        if (opt === cfg.current) o.selected = true;
        select.appendChild(o);
    }
    select.addEventListener('change', () => {
        scheduleUpdate(scopeKey, key, select.value, 0);
    });

    row.appendChild(labelEl);
    row.appendChild(select);
    return row;
}

function buildBoolRow(row, scopeKey, key, value) {
    const labelEl = document.createElement('label');
    const nameSpan = document.createElement('span');
    nameSpan.textContent = key;
    labelEl.appendChild(nameSpan);

    const select = document.createElement('select');
    for (const opt of ['true', 'false']) {
        const o = document.createElement('option');
        o.value = opt;
        o.textContent = opt;
        if ((opt === 'true') === !!value) o.selected = true;
        select.appendChild(o);
    }
    select.addEventListener('change', () => {
        scheduleUpdate(scopeKey, key, select.value, 0);
    });

    row.appendChild(labelEl);
    row.appendChild(select);
    return row;
}

function buildTextRow(row, scopeKey, key, value) {
    const labelEl = document.createElement('label');
    const nameSpan = document.createElement('span');
    nameSpan.textContent = key;
    labelEl.appendChild(nameSpan);

    const input = document.createElement('input');
    input.type = typeof value === 'number' ? 'number' : 'text';
    input.value = value == null ? '' : String(value);
    input.addEventListener('change', () => {
        const v = input.type === 'number' ? Number(input.value) : input.value;
        scheduleUpdate(scopeKey, key, v, 0);
    });

    row.appendChild(labelEl);
    row.appendChild(input);
    return row;
}

function scheduleUpdate(scopeKey, key, value, debounceMs = 250) {
    if (_state.pendingTimer) {
        clearTimeout(_state.pendingTimer);
        _state.pendingTimer = null;
    }
    const go = () => {
        _state.pendingTimer = null;
        applyUpdate(scopeKey, key, value);
    };
    if (debounceMs > 0) {
        _state.pendingTimer = setTimeout(go, debounceMs);
    } else {
        go();
    }
}

async function applyUpdate(scopeKey, key, value) {
    const code = `
_upd_err = None
try:
    _scope = ${JSON.stringify(scopeKey)}
    _key = ${JSON.stringify(key)}
    _val = ${pyLiteral(value)}
    if _scope == 'system':
        _cfg = controller.system_config.config
    elif _scope == 'controller':
        _cfg = controller.config
    elif _scope.startswith('app:'):
        _cfg = controller.app_configs[_scope[4:]]
    elif _scope.startswith('service:'):
        _cfg = controller.service_configs[_scope[8:]]
    else:
        raise ValueError('Unknown scope: ' + _scope)
    _cfg.update({_key: _val})
except BaseException as _e:
    _upd_err = '%s: %s' % (type(_e).__name__, _e)
`;
    try {
        await _state.mp.runPythonAsync(code);
        const err = _state.mp.pyimport('__main__')._upd_err;
        if (err) {
            setStatus(`${key}: ${err}`, 'error');
            return;
        }
        // Mirror the new value into our cached scope so subsequent reads
        // (re-render after refresh) see the latest.
        const scope = _state.scopes[scopeKey];
        if (scope && scope[key] && typeof scope[key] === 'object' && 'current' in scope[key]) {
            scope[key].current = value;
        } else if (scope) {
            scope[key] = value;
        }
        setStatus(`Saved ${scopeKey}.${key}. Some services may need Full Reload to pick up changes.`, 'ok');
    } catch (e) {
        setStatus(`${key}: ${e.message || e}`, 'error');
    }
}

function pyLiteral(value) {
    if (value === null || value === undefined) return 'None';
    if (typeof value === 'boolean') return value ? 'True' : 'False';
    if (typeof value === 'number') return String(value);
    // Strings: JSON quoting is a valid Python string literal for our purposes
    // (paths/IDs are validated via Config.update; this avoids escape edge cases).
    return JSON.stringify(String(value));
}

function setStatus(msg, kind) {
    const el = document.getElementById('config-status');
    if (!el) return;
    el.textContent = msg || '';
    el.className = kind || '';
}

// ── Flash-files producer (passed to flash.js runFlash). ───────────────────
async function getConfigFiles() {
    if (!_state.mp) {
        throw new Error('MicroPython not initialised yet');
    }
    const code = `
import json as _json
def _cfg_to_json(c):
    # Walk .items() to dodge MicroPython's dict-subclass copy quirk.
    out = {}
    for _k, _v in c.items():
        if isinstance(_v, dict):
            out[_k] = {kk: vv for kk, vv in _v.items()}
        else:
            out[_k] = _v
    return _json.dumps(out)
_files = {}
for _cfg in (controller.system_config.config, controller.config):
    _files[_cfg.filename] = _cfg_to_json(_cfg)
for _cfg in controller.app_configs.values():
    _files[_cfg.filename] = _cfg_to_json(_cfg)
for _cfg in controller.service_configs.values():
    _files[_cfg.filename] = _cfg_to_json(_cfg)
_config_files_dump = _json.dumps(_files)
`;
    await _state.mp.runPythonAsync(code);
    const dump = _state.mp.pyimport('__main__')._config_files_dump;
    const map = JSON.parse(dump);
    return Object.entries(map).map(([path, content]) => ({ path, content }));
}
