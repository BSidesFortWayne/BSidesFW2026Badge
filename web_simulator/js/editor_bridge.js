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
        // Catch on the Python side and stash the formatted traceback in a
        // global. JS-side `catch (e)` receives a PyProxy of the exception
        // whose `.message` is undefined, so without this we'd lose the
        // actual error text. `sys.print_exception` is also called so the
        // full traceback shows up in the log via stderr.
        const code = `
import _hot_reload, sys
try:
    controller
except NameError:
    controller = None
_hot_reload_err = None
if controller is None:
    print('[editor] Controller not ready yet; skipping reload')
else:
    try:
        await _hot_reload.reload_app(controller, ${JSON.stringify(modulePath)}, ${sourceLit})
    except BaseException as _e:
        sys.print_exception(_e)
        _hot_reload_err = '%s: %s' % (type(_e).__name__, _e)
`;
        try {
            await mp.runPythonAsync(code);
            const err = mp.pyimport('__main__')._hot_reload_err;
            if (err) {
                log(`Reload failed for ${modulePath}: ${err}`, 'ERROR');
                throw new Error(err);
            }
            log(`Reloaded ${modulePath}`, 'INFO');
        } catch (e) {
            const msg = (e && e.message) || (e && typeof e.toString === 'function' && e.toString()) || String(e);
            log(`Reload failed for ${modulePath}: ${msg}`, 'ERROR');
            throw e;
        }
    }

    function fullReload() {
        window.location.reload();
    }

    globalObj.editorBridge = { applyOverlay, fullReload };
}
