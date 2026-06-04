// Flash the in-browser editor's filesystem to a real badge over USB.
//
// We use the Web Serial API (not WebUSB) because the badge has a CH340C
// USB-to-serial bridge, which Chrome won't expose through navigator.usb.
// Web Serial gives us the OS-level COM port; on top of that we drive the
// standard MicroPython raw REPL protocol — the same one mpremote / ampy
// use — to write files to the device's filesystem and soft-reboot it.

const SUPPORTED = typeof navigator !== 'undefined' && 'serial' in navigator;
const BAUD = 115200;

export function flashSupported() { return SUPPORTED; }

// MicroPython REPL control bytes.
const CTRL_A = 0x01; // enter raw REPL
const CTRL_B = 0x02; // leave raw REPL
const CTRL_C = 0x03; // interrupt running program
const CTRL_D = 0x04; // raw REPL: execute / friendly REPL: soft reboot

// Hex chars per chunk → bytes-per-chunk * 2. 768 bytes per chunk keeps each
// raw-REPL command well under MicroPython's ~4KB receive buffer.
const CHUNK_BYTES = 768;

let busy = false;

export function initFlash({ getModifiedFiles, getAllFiles, addLog }) {
    const modBtn = document.getElementById('editor-flash-modified');
    const allBtn = document.getElementById('editor-flash-all');
    if (!modBtn || !allBtn) return;

    if (!SUPPORTED) {
        const tip = 'Web Serial unavailable — open this page in Chrome or Edge ' +
            '(https://www.google.com/chrome/ · https://www.microsoft.com/edge).';
        for (const b of [modBtn, allBtn]) {
            b.disabled = true;
            b.title = tip;
            b.classList.add('unsupported');
        }
        addLog('Flash to device: Web Serial not supported in this browser.', 'WARNING');
        return;
    }

    modBtn.addEventListener('click', () => {
        runFlash({ label: 'modified', getFiles: getModifiedFiles, addLog, buttons: [modBtn, allBtn] });
    });
    allBtn.addEventListener('click', () => {
        runFlash({ label: 'all src/', getFiles: getAllFiles, addLog, buttons: [modBtn, allBtn] });
    });
}

export async function runFlash({ label, getFiles, addLog, buttons }) {
    if (busy) return;
    busy = true;
    buttons.forEach(b => { b.disabled = true; });
    expandLogPanel();

    let port = null;
    let reader = null;
    let writer = null;

    try {
        addLog(`Flash (${label}): collecting files...`, 'INFO');
        const files = await getFiles();
        if (!files || files.length === 0) {
            addLog('Nothing to flash.', 'WARNING');
            return;
        }
        addLog(`Flash (${label}): ${files.length} file(s) ready.`, 'INFO');

        addLog('Requesting USB serial port — pick the CH340 device in the popup...', 'INFO');
        try {
            port = await navigator.serial.requestPort();
        } catch (e) {
            addLog('Flash cancelled (no port selected).', 'WARNING');
            return;
        }

        addLog(`Opening port at ${BAUD} baud...`, 'INFO');
        await port.open({
            baudRate: BAUD,
            dataBits: 8,
            stopBits: 1,
            parity: 'none',
            flowControl: 'none',
        });

        // Deassert DTR/RTS so opening the port doesn't pulse the ESP32's
        // reset/boot lines. (HARDWARE.md §RTS/DTR Circuit.)
        try {
            await port.setSignals({ dataTerminalReady: false, requestToSend: false });
        } catch (_) { /* not all backends support this */ }

        writer = port.writable.getWriter();
        reader = port.readable.getReader();
        const repl = new Repl(reader, writer);

        addLog('Entering MicroPython raw REPL (may take a few seconds)...', 'INFO');
        await repl.enterRawRepl(addLog);
        addLog('Raw REPL ready.', 'INFO');

        let i = 0;
        for (const { path, content } of files) {
            i++;
            const bytes = new TextEncoder().encode(content);
            addLog(`[${i}/${files.length}] Writing ${path} (${bytes.length} bytes)...`, 'INFO');
            await repl.writeFile(path, bytes);
        }

        addLog('All files written. Soft-rebooting badge...', 'INFO');
        await repl.exitRawRepl();
        await repl.softReboot();

        addLog(`Flash complete (${files.length} file(s)). Badge will reboot.`, 'INFO');
    } catch (e) {
        const msg = (e && e.message) || String(e);
        addLog(`Flash failed: ${msg}`, 'ERROR');
        console.error('[flash] error:', e);
    } finally {
        // Release locks before closing — port.close() rejects otherwise.
        if (reader) {
            try { await reader.cancel(); } catch (_) {}
            try { reader.releaseLock(); } catch (_) {}
        }
        if (writer) {
            try { await writer.close(); } catch (_) {}
            try { writer.releaseLock(); } catch (_) {}
        }
        if (port) {
            try { await port.close(); } catch (_) {}
        }
        buttons.forEach(b => { b.disabled = false; });
        busy = false;
    }
}

function expandLogPanel() {
    const logPanel = document.getElementById('log-panel');
    const logToggle = document.getElementById('log-toggle');
    if (logPanel && logPanel.classList.contains('collapsed')) {
        logPanel.classList.remove('collapsed');
        if (logToggle) logToggle.textContent = 'Collapse';
    }
}

// ── MicroPython raw-REPL client ────────────────────────────────────────────

class Repl {
    constructor(reader, writer) {
        this.reader = reader;
        this.writer = writer;
        this.buffer = new Uint8Array(0);
    }

    async _send(payload) {
        let bytes;
        if (typeof payload === 'string') bytes = new TextEncoder().encode(payload);
        else if (payload instanceof Uint8Array) bytes = payload;
        else if (typeof payload === 'number') bytes = new Uint8Array([payload]);
        else throw new Error('Unsupported send payload');
        await this.writer.write(bytes);
    }

    async _pull(timeoutMs) {
        let timer = null;
        const timeoutPromise = new Promise((_, rej) => {
            timer = setTimeout(() => rej(new Error('Serial read timeout')), timeoutMs);
        });
        try {
            const res = await Promise.race([this.reader.read(), timeoutPromise]);
            if (res.done) throw new Error('Serial port closed unexpectedly');
            if (res.value && res.value.length) {
                const merged = new Uint8Array(this.buffer.length + res.value.length);
                merged.set(this.buffer, 0);
                merged.set(res.value, this.buffer.length);
                this.buffer = merged;
            }
        } finally {
            if (timer) clearTimeout(timer);
        }
    }

    async readUntil(marker, timeoutMs = 5000) {
        const needle = typeof marker === 'string' ? new TextEncoder().encode(marker) : marker;
        const markerStr = typeof marker === 'string' ? marker : '<bytes>';
        const start = Date.now();
        while (true) {
            const idx = indexOf(this.buffer, needle);
            if (idx >= 0) {
                const before = this.buffer.slice(0, idx);
                this.buffer = this.buffer.slice(idx + needle.length);
                return before;
            }
            const remaining = timeoutMs - (Date.now() - start);
            if (remaining <= 0) {
                throw this._timeoutError(markerStr);
            }
            try {
                await this._pull(remaining);
            } catch (e) {
                // _pull timed out or the port closed — surface buffer context.
                throw this._timeoutError(markerStr);
            }
        }
    }

    _timeoutError(markerStr) {
        const got = decodeSafe(this.buffer).slice(-200);
        const tail = got.length ? `last ${this.buffer.length} bytes: ${JSON.stringify(got)}` : 'no bytes received';
        return new Error(`Timeout waiting for ${JSON.stringify(markerStr)} — ${tail}`);
    }

    // Read whatever the device is currently sending and discard it. Returns
    // when no new bytes arrive for `quietMs` (default 200ms) or after
    // `maxMs` total elapsed. Used between handshake steps to clear any
    // boot banner / traceback / friendly-REPL prompt out of the buffer.
    async drain(quietMs = 200, maxMs = 1500) {
        const deadline = Date.now() + maxMs;
        let lastSize = -1;
        while (Date.now() < deadline) {
            const before = this.buffer.length;
            try {
                await this._pull(quietMs);
            } catch (_) {
                // Quiet period elapsed with no new bytes — we're drained.
                if (this.buffer.length === before) {
                    this.buffer = new Uint8Array(0);
                    return;
                }
            }
            if (this.buffer.length === lastSize) break;
            lastSize = this.buffer.length;
        }
        this.buffer = new Uint8Array(0);
    }

    async enterRawRepl(addLog) {
        // The badge's MicroPython is normally running an asyncio controller, not
        // sitting at a REPL prompt. Interrupting it requires more than a single
        // Ctrl-C pair: we send several spaced-out interrupts, drain whatever
        // the device emits (boot banner, KeyboardInterrupt traceback, friendly
        // prompt), and then enter raw REPL. Retry on transient flakiness.
        const banner = 'raw REPL; CTRL-B to exit';
        const attempts = 4;
        let lastErr = null;

        for (let attempt = 1; attempt <= attempts; attempt++) {
            try {
                // Give the device a moment in case the port-open pulsed reset.
                await sleep(attempt === 1 ? 400 : 300);

                // CR primes the prompt; Ctrl-B exits any stale raw REPL we
                // may already be in; Ctrl-C×3 interrupts running asyncio code.
                await this._send(new Uint8Array([0x0d, CTRL_B, CTRL_C, CTRL_C, CTRL_C]));
                await this.drain(250, 1500);

                // One more interrupt for good measure, then enter raw REPL.
                await this._send(new Uint8Array([CTRL_C, 0x0d, CTRL_A]));
                await this.readUntil(banner, 4000);
                await this.readUntil('\n>', 2000);
                return;
            } catch (e) {
                lastErr = e;
                if (addLog) addLog(`Raw REPL attempt ${attempt}/${attempts} failed: ${e.message}`, 'WARNING');
                this.buffer = new Uint8Array(0);
            }
        }
        throw new Error(
            `Could not enter MicroPython raw REPL. ${lastErr && lastErr.message}. ` +
            `Try pressing the Reset button (SW5) on the badge, then click Flash again.`
        );
    }

    async exitRawRepl() {
        await this._send(new Uint8Array([CTRL_B]));
        // Don't care about the friendly-REPL banner that follows.
        await sleep(100);
        this.buffer = new Uint8Array(0);
    }

    async softReboot() {
        await this._send(new Uint8Array([CTRL_D]));
        // Give the device a moment to actually consume the byte before we
        // close the port underneath it.
        await sleep(150);
    }

    // Execute a raw-REPL command. After Ctrl-D, the device sends:
    //   OK <stdout> \x04 <stderr> \x04 >
    // We surface stderr as an Error so callers don't silently lose tracebacks.
    async execRaw(code) {
        await this._send(code);
        await this._send(new Uint8Array([CTRL_D]));
        await this.readUntil('OK', 5000);
        await this.readUntil(new Uint8Array([CTRL_D]), 30000); // stdout (discarded)
        const stderr = await this.readUntil(new Uint8Array([CTRL_D]), 5000);
        await this.readUntil('>', 3000);
        if (stderr.length > 0) {
            throw new Error(decodeSafe(stderr).trim());
        }
    }

    async writeFile(path, bytes) {
        const pathLit = pyStringLit(path);

        if (bytes.length === 0) {
            const code =
                'import os\n' +
                `_p=${pathLit}\n` +
                "_ps=_p.split('/')\n" +
                'for _i in range(1,len(_ps)):\n' +
                "    try: os.mkdir('/'.join(_ps[:_i]))\n" +
                '    except OSError: pass\n' +
                "open(_p,'wb').close()\n";
            await this.execRaw(code);
            return;
        }

        let offset = 0;
        let firstChunk = true;
        while (offset < bytes.length) {
            const end = Math.min(bytes.length, offset + CHUNK_BYTES);
            const hex = bytesToHex(bytes.subarray(offset, end));
            let code;
            if (firstChunk) {
                code =
                    'import os, binascii\n' +
                    `_p=${pathLit}\n` +
                    "_ps=_p.split('/')\n" +
                    'for _i in range(1,len(_ps)):\n' +
                    "    try: os.mkdir('/'.join(_ps[:_i]))\n" +
                    '    except OSError: pass\n' +
                    "_f=open(_p,'wb')\n" +
                    `_f.write(binascii.unhexlify('${hex}'))\n` +
                    '_f.close()\n';
                firstChunk = false;
            } else {
                code =
                    'import binascii\n' +
                    `_f=open(${pathLit},'ab')\n` +
                    `_f.write(binascii.unhexlify('${hex}'))\n` +
                    '_f.close()\n';
            }
            await this.execRaw(code);
            offset = end;
        }
    }
}

// ── Helpers ────────────────────────────────────────────────────────────────

function indexOf(haystack, needle) {
    if (needle.length === 0) return 0;
    if (haystack.length < needle.length) return -1;
    outer:
    for (let i = 0; i <= haystack.length - needle.length; i++) {
        for (let j = 0; j < needle.length; j++) {
            if (haystack[i + j] !== needle[j]) continue outer;
        }
        return i;
    }
    return -1;
}

function bytesToHex(bytes) {
    let out = '';
    for (let i = 0; i < bytes.length; i++) {
        const b = bytes[i];
        out += (b < 16 ? '0' : '') + b.toString(16);
    }
    return out;
}

function pyStringLit(s) {
    // Paths are validated upstream (validatePath in editor.js) to a strict
    // charset, but still escape defensively for the raw-REPL transport.
    return "'" + s.replace(/\\/g, '\\\\').replace(/'/g, "\\'") + "'";
}

function decodeSafe(bytes) {
    try { return new TextDecoder('utf-8', { fatal: false }).decode(bytes); }
    catch (_) { return ''; }
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
