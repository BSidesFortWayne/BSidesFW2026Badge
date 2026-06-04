// Each badge display is logically 240×240. We render the canvas at SCALE×
// that size internally and let CSS shrink the canvas to its native 240×240
// CSS box. The browser's CSS transform on #board-container (used to fit the
// badge in shorter windows) downscales the already-larger canvas, so glyph
// strokes survive non-integer ratios that would drop pixels at 1:1.
const SCALE = 2;
const LOGICAL = 240;
const W = LOGICAL * SCALE; // 480
const ROW_STRIDE_BYTES = W * 4;

const displays = [];
const imageDataCache = [];

export function initDisplays() {
    for (let i = 1; i <= 2; i++) {
        const canvas = document.getElementById(`display${i}`);
        const ctx = canvas.getContext('2d', { willReadFrequently: true });
        ctx.imageSmoothingEnabled = false;
        const imageData = ctx.createImageData(W, W);
        const data = imageData.data;
        for (let j = 3; j < data.length; j += 4) data[j] = 255;
        ctx.putImageData(imageData, 0, 0);
        displays.push(ctx);
        imageDataCache.push(imageData);
    }
}

// Paint a logical pixel (x, y in 0..LOGICAL) as a SCALE×SCALE block.
function setLogicalPixel(data, x, y, r, g, b) {
    if (x < 0 || x >= LOGICAL || y < 0 || y >= LOGICAL) return;
    const baseY = y * SCALE;
    const baseX = x * SCALE;
    for (let sy = 0; sy < SCALE; sy++) {
        const row = baseY + sy;
        let off = (row * W + baseX) * 4;
        for (let sx = 0; sx < SCALE; sx++) {
            data[off] = r;
            data[off + 1] = g;
            data[off + 2] = b;
            data[off + 3] = 255;
            off += 4;
        }
    }
}

// Fill a logical rect (x, y, w, h in 0..LOGICAL) with one color, expanded by SCALE.
function fillLogicalRect(data, x, y, w, h, r, g, b) {
    const x1 = Math.max(0, x);
    const y1 = Math.max(0, y);
    const x2 = Math.min(LOGICAL, x + w);
    const y2 = Math.min(LOGICAL, y + h);
    if (x1 >= x2 || y1 >= y2) return;
    const phys_x1 = x1 * SCALE;
    const phys_x2 = x2 * SCALE;
    const phys_y1 = y1 * SCALE;
    const phys_y2 = y2 * SCALE;
    for (let py = phys_y1; py < phys_y2; py++) {
        let off = (py * W + phys_x1) * 4;
        for (let px = phys_x1; px < phys_x2; px++) {
            data[off] = r;
            data[off + 1] = g;
            data[off + 2] = b;
            data[off + 3] = 255;
            off += 4;
        }
    }
}

export function displayFill(displayId, color) {
    const ctx = displays[displayId - 1];
    if (!ctx) return;
    const [r, g, b] = rgb565ToRgb(color);
    const imageData = imageDataCache[displayId - 1];
    const data = imageData.data;
    for (let i = 0; i < data.length; i += 4) {
        data[i] = r;
        data[i + 1] = g;
        data[i + 2] = b;
        data[i + 3] = 255;
    }
    ctx.putImageData(imageData, 0, 0);
}

export function displayPixel(displayId, x, y, color) {
    const ctx = displays[displayId - 1];
    if (!ctx) return;
    const [r, g, b] = rgb565ToRgb(color);
    setLogicalPixel(imageDataCache[displayId - 1].data, x, y, r, g, b);
}

export function displayFillRect(displayId, x, y, w, h, color) {
    const ctx = displays[displayId - 1];
    if (!ctx) return;
    const [r, g, b] = rgb565ToRgb(color);
    fillLogicalRect(imageDataCache[displayId - 1].data, x, y, w, h, r, g, b);
}

export function displayLine(displayId, x0, y0, x1, y1, color) {
    const ctx = displays[displayId - 1];
    if (!ctx) return;
    const [r, g, b] = rgb565ToRgb(color);
    const data = imageDataCache[displayId - 1].data;
    // Bresenham over logical pixels — setLogicalPixel handles the SCALE expansion.
    let dx = Math.abs(x1 - x0);
    let dy = Math.abs(y1 - y0);
    let sx = x0 < x1 ? 1 : -1;
    let sy = y0 < y1 ? 1 : -1;
    let err = dx - dy;
    while (true) {
        setLogicalPixel(data, x0, y0, r, g, b);
        if (x0 === x1 && y0 === y1) break;
        let e2 = 2 * err;
        if (e2 > -dy) { err -= dy; x0 += sx; }
        if (e2 < dx) { err += dx; y0 += sy; }
    }
}

export function displayCircle(displayId, x, y, radius, color, filled) {
    const ctx = displays[displayId - 1];
    if (!ctx) return;
    const [r, g, b] = rgb565ToRgb(color);
    const data = imageDataCache[displayId - 1].data;

    function hLine(x1, x2, py) {
        for (let px = x1; px <= x2; px++) setLogicalPixel(data, px, py, r, g, b);
    }

    if (filled) {
        let cx = 0, cy = radius, d = 1 - radius;
        while (cx <= cy) {
            hLine(x - cy, x + cy, y + cx);
            hLine(x - cy, x + cy, y - cx);
            hLine(x - cx, x + cx, y + cy);
            hLine(x - cx, x + cx, y - cy);
            cx++;
            if (d < 0) {
                d += 2 * cx + 1;
            } else {
                cy--;
                d += 2 * (cx - cy) + 1;
            }
        }
    } else {
        let cx = 0, cy = radius, d = 1 - radius;
        while (cx <= cy) {
            setLogicalPixel(data, x + cx, y + cy, r, g, b);
            setLogicalPixel(data, x - cx, y + cy, r, g, b);
            setLogicalPixel(data, x + cx, y - cy, r, g, b);
            setLogicalPixel(data, x - cx, y - cy, r, g, b);
            setLogicalPixel(data, x + cy, y + cx, r, g, b);
            setLogicalPixel(data, x - cy, y + cx, r, g, b);
            setLogicalPixel(data, x + cy, y - cx, r, g, b);
            setLogicalPixel(data, x - cy, y - cx, r, g, b);
            cx++;
            if (d < 0) {
                d += 2 * cx + 1;
            } else {
                cy--;
                d += 2 * (cx - cy) + 1;
            }
        }
    }
}

export function displayBlitBuffer(displayId, bufferArray, x, y, width, height) {
    const ctx = displays[displayId - 1];
    if (!ctx) return;
    const data = imageDataCache[displayId - 1].data;

    let srcIdx = 0;
    for (let row = 0; row < height; row++) {
        const destY = y + row;
        if (destY < 0 || destY >= LOGICAL) { srcIdx += width * 2; continue; }
        for (let col = 0; col < width; col++) {
            const destX = x + col;
            if (destX < 0 || destX >= LOGICAL) { srcIdx += 2; continue; }
            // framebuf.RGB565 stores native little-endian uint16. The badge's
            // pre-swap rgb()/rgb_to_565 helpers encode colors so the resulting
            // wire bytes are what the GC9A01 panel reads as big-endian RGB565.
            // Match that: read big-endian here.
            const rgb565 = (bufferArray[srcIdx] << 8) | bufferArray[srcIdx + 1];
            const r = (rgb565 & 0xF800) >> 8;
            const g = (rgb565 & 0x07E0) >> 3;
            const b = (rgb565 & 0x001F) << 3;
            setLogicalPixel(data, destX, destY, r, g, b);
            srcIdx += 2;
        }
    }
}

// VGA bitmap-font atlases (240-space — same as before; we expand at draw time).
const ATLAS_META = {
    'vga1_bold_16x32': { url: 'fonts/vga1_bold_16x32.png', charW: 16, charH: 32 },
    'vga2_bold_16x32': { url: 'fonts/vga2_bold_16x32.png', charW: 16, charH: 32 },
    'vga2_8x16':       { url: 'fonts/vga2_8x16.png',       charW: 8,  charH: 16 },
};
const atlasCache = new Map();

function loadAtlas(fontName) {
    if (atlasCache.has(fontName)) return atlasCache.get(fontName);
    const meta = ATLAS_META[fontName];
    if (!meta) {
        atlasCache.set(fontName, null);
        return null;
    }
    const entry = { ...meta, ready: false, imageData: null, atlasW: 0 };
    atlasCache.set(fontName, entry);
    const img = new Image();
    img.onload = () => {
        const c = document.createElement('canvas');
        c.width = img.width;
        c.height = img.height;
        const cctx = c.getContext('2d');
        cctx.drawImage(img, 0, 0);
        entry.imageData = cctx.getImageData(0, 0, img.width, img.height);
        entry.atlasW = img.width;
        entry.ready = true;
    };
    img.src = meta.url;
    return entry;
}

export function displayText(displayId, text, x, y, fgColor, bgColor, charWidth, charHeight, fontName) {
    const ctx = displays[displayId - 1];
    if (!ctx) return;
    if (!text || text.length === 0) return;
    const [fr, fg, fb] = rgb565ToRgb(fgColor);
    const [br, bg2, bb] = rgb565ToRgb(bgColor);
    const data = imageDataCache[displayId - 1].data;

    const atlas = fontName ? loadAtlas(fontName) : null;
    if (atlas && atlas.ready) {
        const cw = atlas.charW;
        const ch = atlas.charH;
        const aw = atlas.atlasW;
        const aData = atlas.imageData.data;
        const textWidth = text.length * cw;
        fillLogicalRect(data, x, y, textWidth, ch, br, bg2, bb);

        for (let i = 0; i < text.length; i++) {
            const code = text.charCodeAt(i);
            if (code < 0x20 || code > 0x7F) continue;
            const idx = code - 0x20;
            const ax0 = ((idx % 16) + 1) * cw;
            const ay0 = ((idx >> 4) + 1) * ch;
            const destX0 = x + i * cw;
            for (let dy = 0; dy < ch; dy++) {
                for (let dx = 0; dx < cw; dx++) {
                    const aoff = ((ay0 + dy) * aw + (ax0 + dx)) * 4;
                    if (aData[aoff] > 128) {
                        setLogicalPixel(data, destX0 + dx, y + dy, fr, fg, fb);
                    }
                }
            }
        }
        return;
    }

    // Fallback: canvas-rendered text. Used while the atlas is still loading
    // and for fonts without an atlas. Render to a SCALE-sized temp canvas so
    // glyphs are crisp at the supersampled internal resolution.
    const textWidth = text.length * charWidth;
    fillLogicalRect(data, x, y, textWidth, charHeight, br, bg2, bb);

    const tmpW = textWidth * SCALE;
    const tmpH = charHeight * SCALE;
    const tmpCanvas = document.createElement('canvas');
    tmpCanvas.width = tmpW;
    tmpCanvas.height = tmpH;
    const tmpCtx = tmpCanvas.getContext('2d');
    tmpCtx.fillStyle = `rgb(${br},${bg2},${bb})`;
    tmpCtx.fillRect(0, 0, tmpW, tmpH);
    tmpCtx.fillStyle = `rgb(${fr},${fg},${fb})`;
    const fontPx = Math.max(8, Math.floor(charHeight * SCALE * 0.75));
    tmpCtx.font = `bold ${fontPx}px "Courier New", monospace`;
    tmpCtx.textBaseline = 'top';
    tmpCtx.textAlign = 'center';
    for (let i = 0; i < text.length; i++) {
        tmpCtx.fillText(text[i], (i * charWidth + charWidth / 2) * SCALE, 0);
    }

    const tmpData = tmpCtx.getImageData(0, 0, tmpW, tmpH).data;
    // Copy raw scaled pixels into the same physical position on the canvas.
    const phys_x = x * SCALE;
    const phys_y = y * SCALE;
    for (let row = 0; row < tmpH; row++) {
        const destY = phys_y + row;
        if (destY < 0 || destY >= W) continue;
        for (let col = 0; col < tmpW; col++) {
            const destX = phys_x + col;
            if (destX < 0 || destX >= W) continue;
            const srcOff = (row * tmpW + col) * 4;
            const destOff = (destY * W + destX) * 4;
            data[destOff] = tmpData[srcOff];
            data[destOff + 1] = tmpData[srcOff + 1];
            data[destOff + 2] = tmpData[srcOff + 2];
            data[destOff + 3] = 255;
        }
    }
}

export function displayJpg(displayId, filename, x, y) {
    const ctx = displays[displayId - 1];
    if (!ctx) return;
    const img = new Image();
    img.onload = () => {
        ctx.drawImage(img, x * SCALE, y * SCALE, W, W);
        imageDataCache[displayId - 1] = ctx.getImageData(0, 0, W, W);
    };
    img.src = `build/fs/${filename.replace(/^\//, '')}`;
}

export function flushDisplay(displayId) {
    const ctx = displays[displayId - 1];
    if (!ctx) return;
    ctx.putImageData(imageDataCache[displayId - 1], 0, 0);
}

export function flushAllDisplays() {
    for (let i = 0; i < displays.length; i++) {
        if (displays[i]) {
            displays[i].putImageData(imageDataCache[i], 0, 0);
        }
    }
}

function rgb565ToRgb(color) {
    return [
        (color & 0xF800) >> 8,
        (color & 0x07E0) >> 3,
        (color & 0x001F) << 3
    ];
}
