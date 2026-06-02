// Config tab for the simulator's right-hand panel.
//
// Reads the live `Config` objects out of MicroPython (system, controller,
// per-app, per-service), renders a form, applies edits in-place via
// `Config.update()` (which also persists to JSON in Emscripten MEMFS), and
// can flash all config JSON files to a real badge over Web Serial.

import { runFlash, flashSupported } from './flash.js?v=17';

const SCOPE_LOADING_OPT = 'Loading…';

// localStorage key prefix for persisted config JSON files. The stored value is
// the file's exact JSON content; the key suffix is the Config.filename it was
// saved to (e.g. "config/apps/Connect Four.json").
const CONFIG_STORE_PREFIX = 'badge_sim_config:';

// Config files the user has changed via the panel, as [{ path, content }].
// Called at boot to mirror them back into MEMFS before the controller loads,
// so changes survive a full page reload.
export function getPersistedConfigs() {
    const out = [];
    for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (k && k.startsWith(CONFIG_STORE_PREFIX)) {
            out.push({ path: k.slice(CONFIG_STORE_PREFIX.length), content: localStorage.getItem(k) });
        }
    }
    return out;
}

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
        setStatus(`Failed to load configs: ${errToStr(e)}`, 'error');
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
    // NOTE: run this synchronously via runPython (NOT runPythonAsync). The code
    // here is pure synchronous Python — no awaits — and runPythonAsync forces
    // an ASYNCIFY unwind. Doing that re-entrantly while the controller's asyncio
    // loop + interrupt polling are pending overflows the (small, shared) asyncify
    // stack and aborts the whole runtime ("RuntimeError: unreachable").
    // Errors are captured in Python and surfaced as a string; letting them
    // propagate rejects with a bare PyProxy that renders as "[object Object]".
    const code = `
import json as _json
_config_dump = None
_config_err = None
try:
    if 'controller' not in dir():
        raise RuntimeError('controller not initialised — check the boot log for startup errors')

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
except BaseException as _e:
    _config_err = '%s: %s' % (type(_e).__name__, _e)
`;
    _state.mp.runPython(code);
    const main = _state.mp.pyimport('__main__');
    if (main._config_err) {
        throw new Error(main._config_err);
    }
    return JSON.parse(main._config_dump);
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
_upd_file = None
_upd_content = None
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
    # Read back the just-saved JSON (same path Config.save wrote) so JS can
    # persist it to localStorage — MEMFS is rebuilt from bundled assets on a
    # full page reload, so without this the change is lost on reload.
    _upd_file = _cfg.filename
    try:
        with open(_cfg.filename) as _f:
            _upd_content = _f.read()
    except OSError:
        _upd_content = None
    # Apps read their config in __init__/draw and don't poll it, so an in-place
    # value change isn't visible until the app is rebuilt. If the change targets
    # the app that's currently on screen, restart it on the event loop so its
    # __init__ re-reads the (now saved) config and redraws. Scheduling a task
    # avoids a re-entrant ASYNCIFY unwind here (switch_app is async).
    if _scope.startswith('app:') and controller.current_view is not None:
        _aname = _scope[4:]
        if getattr(type(controller.current_view), 'name', None) == _aname:
            try:
                import asyncio as _aio
            except ImportError:
                import uasyncio as _aio
            async def _cfg_restart(_n=_aname):
                try:
                    await controller.switch_app(_n)
                except BaseException as _re:
                    import sys as _sys
                    _sys.print_exception(_re)
            _aio.create_task(_cfg_restart())
except BaseException as _e:
    _upd_err = '%s: %s' % (type(_e).__name__, _e)
`;
    try {
        // Synchronous runPython — see the note in loadConfigs about avoiding
        // re-entrant ASYNCIFY unwinds that crash the runtime.
        _state.mp.runPython(code);
        const main = _state.mp.pyimport('__main__');
        const err = main._upd_err;
        if (err) {
            setStatus(`${key}: ${err}`, 'error');
            return;
        }
        // Persist the saved config file to localStorage so it survives a full
        // page reload (MEMFS is rebuilt from bundled assets on reload). Boot
        // re-applies these via applyConfigOverlays() before the controller loads.
        const file = main._upd_file;
        const content = main._upd_content;
        if (file && content != null) {
            try { localStorage.setItem(CONFIG_STORE_PREFIX + file, content); } catch (_) {}
        }
        // Mirror the new value into our cached scope so subsequent reads
        // (re-render after refresh) see the latest.
        const scope = _state.scopes[scopeKey];
        if (scope && scope[key] && typeof scope[key] === 'object' && 'current' in scope[key]) {
            scope[key].current = value;
        } else if (scope) {
            scope[key] = value;
        }
        setStatus(`Saved ${scopeKey}.${key}.`, 'ok');
    } catch (e) {
        setStatus(`${key}: ${errToStr(e)}`, 'error');
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

// Errors from MicroPython can be PythonError (has .message), a bare PyProxy of
// a Python exception (no .message — would stringify to "[object Object]"), or a
// plain Error. Coax all of them into a readable string.
function errToStr(e) {
    if (e == null) return 'unknown error';
    if (typeof e === 'string') return e;
    if (e.message) return e.message;
    try {
        const s = String(e);
        if (s && s !== '[object Object]') return s;
    } catch (_) { /* fall through */ }
    try { return JSON.stringify(e); } catch (_) { return 'unknown error'; }
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
    // Synchronous runPython — see the note in loadConfigs about avoiding
    // re-entrant ASYNCIFY unwinds that crash the runtime.
    _state.mp.runPython(code);
    const dump = _state.mp.pyimport('__main__')._config_files_dump;
    const map = JSON.parse(dump);
    return Object.entries(map).map(([path, content]) => ({ path, content }));
}
