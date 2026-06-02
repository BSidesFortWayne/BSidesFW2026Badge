import { initDisplays, flushAllDisplays } from './display.js';
import { initLeds } from './leds.js';
import { initButtons } from './buttons.js';
import { initControls } from './controls.js';
import { registerBridge } from './bridge.js?v=2';
import { registerEditorBridge } from './editor_bridge.js?v=3';
import { initEditor, getModifiedFiles, getAllFiles } from './editor.js?v=16';
import { initFlash } from './flash.js?v=17';
import { initTabs, initConfigPanel, getPersistedConfigs } from './config_panel.js?v=8';

const logContent = document.getElementById('log-content');
const logToggle = document.getElementById('log-toggle');
const logClear = document.getElementById('log-clear');
const logPanel = document.getElementById('log-panel');
const statusText = document.getElementById('status-text');
const fpsDisplay = document.getElementById('fps-display');

function addLog(message, level = 'INFO') {
    const now = new Date();
    const ts = now.toTimeString().slice(0, 8) + '.' + String(now.getMilliseconds()).padStart(3, '0');
    const entry = document.createElement('div');
    entry.className = `log-entry ${level.toLowerCase()}`;
    entry.textContent = `[${ts}] ${level}: ${message}`;
    logContent.appendChild(entry);
    if (logContent.children.length > 500) {
        logContent.removeChild(logContent.firstChild);
    }
    logContent.scrollTop = logContent.scrollHeight;
    console.log(`[${level}] ${message}`);
}

logToggle.addEventListener('click', () => {
    logPanel.classList.toggle('collapsed');
    logToggle.textContent = logPanel.classList.contains('collapsed') ? 'Expand' : 'Collapse';
});

logClear.addEventListener('click', () => {
    logContent.innerHTML = '';
});

// Scale badge to fit viewport. On phones the right panel is hidden via CSS
// and the badge fills the whole screen, so we scale against both axes.
const mobileQuery = window.matchMedia('(max-width: 768px), (max-height: 500px) and (pointer: coarse)');

function scaleBadge() {
    const boardContainer = document.getElementById('board-container');
    const badgeArea = document.getElementById('badge-area');
    const naturalWidth = 560;
    const naturalHeight = 1060;

    if (mobileQuery.matches) {
        const scale = Math.min(window.innerWidth / naturalWidth, window.innerHeight / naturalHeight);
        boardContainer.style.transform = `scale(${scale})`;
        badgeArea.style.width = '100vw';
    } else {
        const availHeight = window.innerHeight - 20;
        const scale = Math.min(1, availHeight / naturalHeight);
        boardContainer.style.transform = `scale(${scale})`;
        badgeArea.style.width = `${Math.ceil(naturalWidth * scale) + 20}px`;
    }
}

scaleBadge();
window.addEventListener('resize', scaleBadge);
mobileQuery.addEventListener('change', scaleBadge);

// Log panel drag-to-resize
const logResizeHandle = document.getElementById('log-resize-handle');
if (logResizeHandle) {
    let resizing = false;
    let startY = 0;
    let startHeight = 0;
    logResizeHandle.addEventListener('mousedown', (e) => {
        resizing = true;
        startY = e.clientY;
        startHeight = logPanel.offsetHeight;
        document.body.style.cursor = 'ns-resize';
        e.preventDefault();
    });
    document.addEventListener('mousemove', (e) => {
        if (!resizing) return;
        const delta = startY - e.clientY;
        const newHeight = Math.max(35, Math.min(window.innerHeight * 0.7, startHeight + delta));
        logPanel.style.flex = `0 0 ${newHeight}px`;
        logPanel.classList.remove('collapsed');
        logToggle.textContent = 'Collapse';
    });
    document.addEventListener('mouseup', () => {
        if (resizing) {
            resizing = false;
            document.body.style.cursor = '';
        }
    });
}

function setStatus(text, type = '') {
    statusText.textContent = text;
    statusText.className = type;
}

// FPS counter
let frameCount = 0;
let lastFpsTime = performance.now();
function updateFps() {
    frameCount++;
    const now = performance.now();
    if (now - lastFpsTime >= 1000) {
        const fps = frameCount / ((now - lastFpsTime) / 1000);
        fpsDisplay.textContent = `FPS: ${fps.toFixed(1)}`;
        frameCount = 0;
        lastFpsTime = now;
    }
    requestAnimationFrame(updateFps);
}

async function boot() {
    setStatus('Initializing display...');
    initDisplays();
    initLeds();
    initButtons(addLog);
    initControls(addLog);
    initTabs();

    addLog('Hardware UI initialized', 'INFO');

    // Register bridge functions on globalThis so Python `import js` can see them
    registerBridge(globalThis);
    addLog('JS bridge registered', 'INFO');

    // Kick off Monaco load + editor UI in the background (non-blocking).
    initEditor({ addLog }).catch((err) => {
        addLog(`Editor init failed: ${err.message}`, 'WARNING');
    });

    // Wire up the "Flash to badge" buttons. Safe to call even before the
    // editor has finished initializing — the file-listing helpers read
    // straight from localStorage.
    initFlash({ getModifiedFiles, getAllFiles, addLog });

    requestAnimationFrame(updateFps);

    setStatus('Loading MicroPython WASM...');

    try {
        const { loadMicroPython } = await import('../build/micropython.mjs?v=12');
        addLog('MicroPython module loaded, initializing...', 'INFO');

        const mp = await loadMicroPython({
            heapsize: 4 * 1024 * 1024,
            stdout: (line) => { addLog(line, 'INFO'); },
            stderr: (line) => { addLog(line, 'ERROR'); },
            linebuffer: true,
            // Bust browser cache for the WASM binary so rebuilt-locally
            // changes (e.g. new frozen modules like _hot_reload) take effect
            // on reload without manual cache clearing. loadMicroPython
            // forwards this as the Module.locateFile result.
            url: new URL('../build/micropython.wasm?v=12', import.meta.url).href,
        });

        addLog('MicroPython WASM initialized', 'INFO');
        setStatus('Loading firmware assets...');

        // Load asset files into Emscripten filesystem
        await loadAssets(mp);

        // Mirror the editor's created/edited files (localStorage) into MEMFS so
        // a full page reload boots with them, the same way a real badge
        // filesystem would — otherwise brand-new apps live only in the editor
        // and vanish on reload.
        await applyEditorOverlays(mp);

        // Same idea for config changes made via the config panel: re-apply the
        // persisted config JSON over the bundled defaults before the controller
        // (and its SystemConfig / app configs) loads them.
        applyPersistedConfigs(mp);

        // Register the editor bridge now that `mp` exists. The editor UI was
        // initialised earlier (without an `mp` ref) — applyOverlay() will
        // start working as soon as boot finishes assigning `controller`.
        registerEditorBridge(globalThis, mp, addLog);

        setStatus('Booting badge firmware...');

        // The badge firmware is frozen into the WASM binary.
        // Frozen modules are importable directly. Assets (fonts, images)
        // are loaded into the Emscripten filesystem under /firmware/.
        addLog('Running boot sequence...', 'INFO');
        try {
            await mp.runPythonAsync(`
import sys
print('[BOOT] Starting boot sequence...')
print('[BOOT] sys.path:', sys.path)

# Apply runtime patches to frozen modules (gc9a01 bitmap font rendering, etc.)
try:
    import _sim_patches
except Exception as e:
    print(f'[BOOT] Failed to load _sim_patches: {e}')

import machine
machine.freq(240000000)

from drivers.displays import Displays
displays = Displays()
print(f'[BOOT] Displays ready')
print(f'[BOOT] Display 1 id: {displays.display1.display}, Display 2 id: {displays.display2.display}')
`);
            addLog('Boot sequence complete', 'INFO');
        } catch(e) {
            addLog(`Boot error: ${e.message}`, 'ERROR');
        }

        // Patch the frozen display blit path to be zero-copy. The shipped
        // emulator.send_blit_buffer copies the framebuffer into a JS Uint8Array
        // one byte at a time (115k+ proxy ops for a 240x240 blit); for an app
        // that blits every frame this keeps the js bridge saturated and the
        // runtime aborts ("proxy_c_to_js_call is running asynchronously" /
        // ASYNCIFY). Instead, hand JS the buffer's WASM heap address + length
        // and let it view the bytes directly (see bridgeDisplayBlitBufferPtr).
        try {
            await mp.runPythonAsync(`
try:
    import emulator as _emu
    import uctypes as _uctypes
    import js as _js

    def _fast_send_blit_buffer(display, buffer, x, y, width, height):
        # Honour the existing re-entrancy guard (same module global the other
        # send_* helpers use) so overlapping calls are dropped, not aborted.
        if _emu._in_js_call:
            return 0, None
        _emu._in_js_call = True
        try:
            _js.bridgeDisplayBlitBufferPtr(
                display, _uctypes.addressof(buffer), len(buffer),
                x, y, width, height,
            )
        finally:
            _emu._in_js_call = False
        return 0, None

    _emu.send_blit_buffer = _fast_send_blit_buffer
    print('[BOOT] Installed zero-copy blit_buffer')
except Exception as _e:
    print('[BOOT] Could not install zero-copy blit:', _e)
`);
        } catch(e) {
            addLog(`Blit patch error: ${e.message}`, 'WARNING');
        }

        // Patch the frozen config (de)serialization. The shipped Config.save
        // does json.dumps(self), but MicroPython's json doesn't serialize a
        // dict *subclass* (SmartConfigValue / RangeConfig / ColorConfig) as an
        // object — it emits the object's repr, producing INVALID JSON. The file
        // then fails to parse on the next load ("syntax error in JSON") and the
        // whole config silently reverts to defaults, so no change ever persists.
        // Fix: flatten dict subclasses to plain dicts before dumping, and let
        // ColorConfig accept the extra stored fields when reconstructed on load.
        try {
            await mp.runPythonAsync(`
try:
    import lib.smart_config as _sc
    import json as _cfgjson
    import os as _cfgos

    def _cfg_ser(o):
        if isinstance(o, dict):
            return {k: _cfg_ser(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [_cfg_ser(v) for v in o]
        return o

    def _cfg_save(self):
        _data = _cfgjson.dumps(_cfg_ser(self))
        try:
            with open(self.filename, 'w') as _f:
                _f.write(_data)
        except OSError:
            try:
                _cfgos.mkdir('/'.join(self.filename.split('/')[:-1]))
            except OSError:
                pass
            with open(self.filename, 'w') as _f:
                _f.write(_data)

    _sc.Config.save = _cfg_save

    # ColorConfig stores min/max/step but __init__ only takes (name, current);
    # tolerate the extra fields so it can be rebuilt from its saved JSON.
    def _color_init(self, name, current=None, **kwargs):
        _sc.RangeConfig.__init__(self, name, 0, 0xFFFF, current)
    _sc.ColorConfig.__init__ = _color_init

    print('[BOOT] Installed config JSON serialization fix')
except Exception as _e:
    print('[BOOT] Could not install config fix:', _e)
`);
        } catch(e) {
            addLog(`Config patch error: ${e.message}`, 'WARNING');
        }

        // Make Controller.switch_app tolerant of apps whose setup()/teardown()
        // are plain (non-async) methods. switch_app does \`await view.setup()\`
        // and \`await view.teardown()\`; if those return None (a sync def),
        // \`await None\` raises "TypeError: 'NoneType' object isn't iterable"
        // and the app can't start or be exited (e.g. the LED Test app). This
        // re-defines switch_app to await only actual coroutines.
        try {
            await mp.runPythonAsync(`
try:
    from controller import Controller as _Ctrl
    import apps as _apps
    import apps.app as _appsapp
    try:
        import asyncio as _aio2
    except ImportError:
        import uasyncio as _aio2

    async def _maybe_await(_r):
        if hasattr(_r, 'send'):   # coroutine/generator -> await it
            return await _r
        return _r                 # plain value (e.g. None) -> pass through

    async def _tolerant_switch_app(self, app_name):
        if not app_name:
            print("No view provided")
            return
        app = self.app_directory.get_app_by_name(app_name)
        if not app:
            print("App %s not found" % app_name)
            return
        self.bsp.speaker.stop_song()
        if not app.constructor:
            module_name = app.module_name
            print("Loading %s" % module_name)
            __import__("apps." + module_name)
            module = getattr(_apps, module_name, None)
            if not module:
                print("No module found")
                return
            for _n, _obj in module.__dict__.items():
                if (isinstance(_obj, type)
                        and issubclass(_obj, _appsapp.BaseApp)
                        and _obj != _appsapp.BaseApp
                        and _obj.name == app.friendly_name):
                    app.constructor = _obj
                    break
        if not app.constructor:
            print("App %s not found" % app_name)
            return
        if self.current_view:
            await _maybe_await(self.current_view.teardown())
        async with self.current_app_lock:
            self.current_view = None
            self.current_view = app.constructor(self)
        await _maybe_await(self.current_view.setup())
        await _aio2.sleep(0.01)

    _Ctrl.switch_app = _tolerant_switch_app
    print('[BOOT] Installed tolerant switch_app')
except Exception as _e:
    print('[BOOT] Could not install switch_app patch:', _e)
`);
        } catch(e) {
            addLog(`switch_app patch error: ${e.message}`, 'WARNING');
        }

        addLog('Starting controller...', 'INFO');
        try {
            await mp.runPythonAsync(`
print('[MAIN] Starting controller...')
try:
    from controller import Controller
    try:
        import asyncio
    except ImportError:
        import uasyncio as asyncio

    # Make editor-created apps (mirrored into MEMFS at boot) discoverable by the
    # AppDirectory scan. MicroPython resolves a submodule only via its parent
    # package's __path__, so point apps at the MEMFS dir. Bundled apps still
    # resolve (their fs copies are identical to the frozen ones).
    import apps
    apps.__path__ = '/apps'

    controller = Controller(displays)

    async def main_loop():
        await controller.run()

    asyncio.create_task(main_loop())

    import machine
    machine.start_interrupt_polling()
    print('[MAIN] Interrupt polling started (asyncio)')
except Exception as e:
    print(f'[MAIN] Error: {e}')
    import sys
    sys.print_exception(e)
`);
        } catch(e) {
            addLog(`Controller error: ${e.message}`, 'ERROR');
        }

        // Config panel needs the live `controller` object — defer until after
        // the controller-start block above has run.
        initConfigPanel({ mp, addLog }).catch((err) => {
            addLog(`Config panel init failed: ${err.message}`, 'WARNING');
        });

        setStatus('Badge running', 'ready');
    } catch (err) {
        addLog(`MicroPython load failed: ${err.message}`, 'ERROR');
        addLog('Running in demo mode (no WASM binary found)', 'WARNING');
        setStatus('Demo mode - WASM not loaded', 'error');
        runDemoMode();
    }
}

// Write a list of [{ path, content }] into MEMFS, creating missing parent dirs.
function writeFilesToFs(mp, files) {
    for (const { path, content } of files) {
        const full = '/' + path;
        const parts = full.split('/');
        let dir = '';
        for (let i = 1; i < parts.length - 1; i++) {
            dir += '/' + parts[i];
            try { mp.FS.mkdir(dir); } catch (_) {}
        }
        mp.FS.writeFile(full, content);
    }
}

// Write the editor's modified/created files (from localStorage) into MEMFS.
// Runs at boot so a full page reload picks up brand-new apps the same way
// `loadAssets` picks up bundled ones.
async function applyEditorOverlays(mp) {
    try {
        const files = await getModifiedFiles();   // [{ path, content }]
        writeFilesToFs(mp, files);
        if (files.length) {
            addLog(`Applied ${files.length} editor file(s) to filesystem`, 'INFO');
        }
    } catch (e) {
        addLog(`Editor overlay apply failed: ${e.message}`, 'WARNING');
    }
}

// Re-apply config-panel changes (persisted in localStorage) over the bundled
// config defaults, so config edits survive a full page reload.
function applyPersistedConfigs(mp) {
    try {
        const files = getPersistedConfigs();      // [{ path, content }]
        writeFilesToFs(mp, files);
        if (files.length) {
            addLog(`Applied ${files.length} saved config file(s) to filesystem`, 'INFO');
        }
    } catch (e) {
        addLog(`Config persistence apply failed: ${e.message}`, 'WARNING');
    }
}

async function loadAssets(mp) {
    try {
        const resp = await fetch('build/manifest.json', { cache: 'no-store' });
        if (!resp.ok) {
            addLog('No asset manifest found', 'WARNING');
            return;
        }
        const manifest = await resp.json();
        addLog(`Loading ${manifest.files.length} asset files...`, 'INFO');

        // Create directory structure in Emscripten FS
        // Assets go to root paths (e.g., /fonts/victor_R_24.mfnt)
        // so the firmware can open them at the expected locations
        const dirs = new Set();
        for (const filePath of manifest.files) {
            const parts = filePath.split('/');
            let dir = '';
            for (let i = 0; i < parts.length - 1; i++) {
                dir += (dir ? '/' : '/') + parts[i];
                dirs.add(dir);
            }
        }
        for (const dir of [...dirs].sort()) {
            try { mp.FS.mkdir(dir); } catch(e) {}
        }

        // Load files (binary for .mfnt, .jpg, .png; text for .json, .py, .csv)
        let loaded = 0;
        const binaryExts = ['.mfnt', '.jpg', '.jpeg', '.png', '.bmp', '.gif', '.bin'];
        for (const filePath of manifest.files) {
            try {
                const isBinary = binaryExts.some(ext => filePath.toLowerCase().endsWith(ext));
                const fileResp = await fetch(`build/fs/${filePath}`, { cache: 'no-store' });
                if (fileResp.ok) {
                    if (isBinary) {
                        const buf = await fileResp.arrayBuffer();
                        mp.FS.writeFile(`/${filePath}`, new Uint8Array(buf));
                    } else {
                        const content = await fileResp.text();
                        mp.FS.writeFile(`/${filePath}`, content);
                    }
                    loaded++;
                }
            } catch(e) {
                addLog(`Failed to load ${filePath}: ${e.message}`, 'WARNING');
            }
        }
        addLog(`Loaded ${loaded}/${manifest.files.length} assets`, 'INFO');
    } catch(e) {
        addLog(`Asset loading error: ${e.message}`, 'WARNING');
    }
}

function runDemoMode() {
    addLog('Demo: Drawing test pattern on displays', 'INFO');

    if (window.bridgeDisplayFill) {
        window.bridgeDisplayFill(1, 0x0000);
        window.bridgeDisplayFill(2, 0x0000);

        window.bridgeDisplayFillRect(1, 20, 20, 200, 40, 0xF800);
        window.bridgeDisplayFillRect(1, 20, 70, 200, 40, 0x07E0);
        window.bridgeDisplayFillRect(1, 20, 120, 200, 40, 0x001F);
        window.bridgeDisplayFillRect(1, 20, 170, 200, 40, 0xFFFF);

        window.bridgeDisplayCircle(2, 120, 120, 100, 0x04FF, false);
        window.bridgeDisplayCircle(2, 120, 120, 70, 0xF800, true);
        window.bridgeDisplayCircle(2, 120, 120, 40, 0xFFFF, true);

        window.bridgeFlushDisplays();
    }

    let ledFrame = 0;
    setInterval(() => {
        const leds = [];
        for (let i = 0; i < 7; i++) {
            const hue = ((ledFrame + i * 51) % 360) / 360;
            const [r, g, b] = hslToRgb(hue, 1, 0.5);
            leds.push([g, r, b]);
        }
        window.bridgeNeopixelWrite(JSON.stringify(leds));
        ledFrame += 3;
    }, 50);
}

function hslToRgb(h, s, l) {
    let r, g, b;
    if (s === 0) {
        r = g = b = l;
    } else {
        const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
        const p = 2 * l - q;
        r = hue2rgb(p, q, h + 1/3);
        g = hue2rgb(p, q, h);
        b = hue2rgb(p, q, h - 1/3);
    }
    return [Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)];
}

function hue2rgb(p, q, t) {
    if (t < 0) t += 1;
    if (t > 1) t -= 1;
    if (t < 1/6) return p + (q - p) * 6 * t;
    if (t < 1/2) return q;
    if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
    return p;
}

boot();
