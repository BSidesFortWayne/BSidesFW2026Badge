// Editor-specific JS↔MicroPython glue.
// Kept separate from bridge.js so we can extend it without bumping the
// cached URL of the main bridge module.

export function registerEditorBridge(globalObj, mp, addLog) {
    function log(msg, level) {
        if (typeof addLog === 'function') addLog(msg, level || 'INFO');
        else console.log(`[editor] ${msg}`);
    }

    // Write `source` to `path` in MEMFS, creating any missing parent dirs.
    function writeFsFile(path, source) {
        const parts = path.split('/');           // ['', 'apps', 'foo.py']
        let dir = '';
        for (let i = 1; i < parts.length - 1; i++) {
            dir += '/' + parts[i];
            try { mp.FS.mkdir(dir); } catch (_) {}
        }
        mp.FS.writeFile(path, source);
    }

    async function applyOverlay(modulePath, source) {
        const relPath = modulePath.replace(/\./g, '/') + '.py';
        // Mirror the overlay into MEMFS in two places:
        //   /overlays/<path>.py  — for debuggability (stack traces, open()).
        //   /<path>.py           — the real importable location. This matters
        //     for BRAND-NEW modules: _hot_reload.swap() must `__import__` them,
        //     and MicroPython resolves a submodule only via its parent
        //     package's __path__ (it does NOT scan sys.path), so the file has
        //     to physically exist where the package looks — see the __path__
        //     fix-up in the injected Python below. (Existing/frozen modules are
        //     re-exec'd in place by swap() and don't depend on this.)
        try {
            writeFsFile('/overlays/' + relPath, source);
            writeFsFile('/' + relPath, source);
        } catch (e) {
            log(`Overlay MEMFS write failed: ${e.message}`, 'WARNING');
        }

        const sourceLit = JSON.stringify(source);
        const moduleLit = JSON.stringify(modulePath);
        // Schedule the reload as a task on the ALREADY-RUNNING asyncio loop
        // rather than awaiting a nested runPythonAsync. A nested runPythonAsync
        // forces a second ASYNCIFY unwind on top of the live event loop +
        // interrupt polling, which overflows the (small, shared) asyncify stack
        // and aborts the whole runtime ("RuntimeError: unreachable"). Running it
        // as a loop task uses the same asyncify budget as an ordinary
        // button-driven app switch, which is known-safe. We then poll a couple
        // of plain (non-async) module globals to learn when it finished.
        //
        // The Python side captures its own traceback into `_hot_reload_err`;
        // JS-side `catch` would otherwise receive a bare PyProxy whose
        // `.message` is undefined (renders as "[object Object]").
        const setup = `
import _hot_reload, sys
try:
    import asyncio
except ImportError:
    import uasyncio as asyncio
try:
    controller
except NameError:
    controller = None
_hot_reload_done = False
_hot_reload_err = None
if controller is None:
    _hot_reload_done = True
    print('[editor] Controller not ready yet; skipping reload')
else:
    _mp = ${moduleLit}
    _src = ${sourceLit}
    # Make a brand-new module importable before reload_app runs. For a module
    # that isn't frozen and was never imported, point its parent package's
    # __path__ at the MEMFS dir we just wrote the file to — MicroPython only
    # consults __path__ (not sys.path) for submodules. The fs copies of all
    # apps are identical to the frozen ones, so redirecting __path__ is safe.
    if _mp not in sys.modules and '.' in _mp:
        _parent, _leaf = _mp.rsplit('.', 1)
        try:
            __import__(_parent)
            sys.modules[_parent].__path__ = '/' + _parent.replace('.', '/')
        except Exception as _pe:
            print('[editor] could not prepare parent package %s: %s' % (_parent, _pe))

    async def _do_reload():
        global _hot_reload_done, _hot_reload_err
        try:
            await _hot_reload.reload_app(controller, _mp, _src)
        except BaseException as _e:
            sys.print_exception(_e)
            _hot_reload_err = '%s: %s' % (type(_e).__name__, _e)
        finally:
            _hot_reload_done = True

    asyncio.create_task(_do_reload())
`;
        // Synchronous exec: this only schedules the task — no asyncify unwind.
        mp.runPython(setup);
        const err = await pollHotReload();
        if (err) {
            log(`Reload failed for ${modulePath}: ${err}`, 'ERROR');
            throw new Error(err);
        }
        log(`Reloaded ${modulePath}`, 'INFO');
    }

    // Poll the loop-driven reload task to completion. Reading module globals is
    // a plain synchronous proxy access (no asyncify), and yielding via
    // setTimeout lets the asyncio loop advance the task between ticks.
    function pollHotReload(timeoutMs = 20000) {
        return new Promise((resolve, reject) => {
            const t0 = Date.now();
            const tick = () => {
                let main;
                try { main = mp.pyimport('__main__'); } catch (e) { return reject(e); }
                if (main._hot_reload_done) {
                    resolve(main._hot_reload_err || null);
                    return;
                }
                if (Date.now() - t0 > timeoutMs) {
                    return reject(new Error('Hot reload timed out'));
                }
                setTimeout(tick, 40);
            };
            setTimeout(tick, 40);
        });
    }

    function fullReload() {
        window.location.reload();
    }

    globalObj.editorBridge = { applyOverlay, fullReload };
}
