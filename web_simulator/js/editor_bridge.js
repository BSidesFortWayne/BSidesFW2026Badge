// Editor-specific JS↔MicroPython glue.
// Kept separate from bridge.js so we can extend it without bumping the
// cached URL of the main bridge module.

export function registerEditorBridge(globalObj, mp, addLog) {
    function log(msg, level) {
        if (typeof addLog === 'function') addLog(msg, level || 'INFO');
        else console.log(`[editor] ${msg}`);
    }

    async function applyOverlay(modulePath, source) {
        // Mirror the overlay into MEMFS at /overlays/<path>.py for
        // debuggability — _hot_reload doesn't read from disk, but having
        // the file there means stack traces / open() calls in user code
        // can find it.
        try {
            try { mp.FS.mkdir('/overlays'); } catch (_) {}
            const relPath = modulePath.replace(/\./g, '/') + '.py';
            const parts = relPath.split('/');
            let dir = '/overlays';
            for (let i = 0; i < parts.length - 1; i++) {
                dir += '/' + parts[i];
                try { mp.FS.mkdir(dir); } catch (_) {}
            }
            mp.FS.writeFile('/overlays/' + relPath, source);
        } catch (e) {
            log(`Overlay MEMFS write failed: ${e.message}`, 'WARNING');
        }

        const sourceLit = JSON.stringify(source);
        const code = `
import _hot_reload
try:
    controller
except NameError:
    controller = None
if controller is None:
    print('[editor] Controller not ready yet; skipping reload')
else:
    await _hot_reload.reload_app(controller, ${JSON.stringify(modulePath)}, ${sourceLit})
`;
        try {
            await mp.runPythonAsync(code);
            log(`Reloaded ${modulePath}`, 'INFO');
        } catch (e) {
            log(`Reload failed for ${modulePath}: ${e.message}`, 'ERROR');
            throw e;
        }
    }

    function fullReload() {
        window.location.reload();
    }

    globalObj.editorBridge = { applyOverlay, fullReload };
}
