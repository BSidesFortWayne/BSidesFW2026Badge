import { initDisplays, flushAllDisplays } from './display.js';
import { initLeds } from './leds.js';
import { initButtons } from './buttons.js';
import { initControls } from './controls.js';
import { registerBridge } from './bridge.js';
import { registerEditorBridge } from './editor_bridge.js';
import { initEditor, getModifiedFiles, getAllFiles } from './editor.js?v=16';
import { initFlash } from './flash.js?v=16';

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
        const { loadMicroPython } = await import('../build/micropython.mjs?v=11');
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

        setStatus('Badge running', 'ready');
    } catch (err) {
        addLog(`MicroPython load failed: ${err.message}`, 'ERROR');
        addLog('Running in demo mode (no WASM binary found)', 'WARNING');
        setStatus('Demo mode - WASM not loaded', 'error');
        runDemoMode();
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
