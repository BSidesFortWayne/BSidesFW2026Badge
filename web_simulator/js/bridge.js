import {
    displayFill, displayPixel, displayFillRect, displayLine,
    displayCircle, displayBlitBuffer, displayText, displayJpg,
    flushDisplay, flushAllDisplays
} from './display.js';
import { setLeds } from './leds.js';
import { getInputs, getPinValue } from './buttons.js';
import { getAccelData, getAdcVoltage, pollInterrupts } from './controls.js';
import { pwmSetFreq, pwmSetDuty, pwmDeinit } from './audio.js';

let pendingFlush = new Set();
let flushScheduled = false;

// Re-entrancy guard at the JS level. MicroPython WASM uses ASYNCIFY for
// js.* proxy calls, which can yield to the browser event loop mid-call.
// If another Python task then makes a js.* call before the first returns,
// the runtime aborts. This flag blocks re-entrant bridge calls at the JS
// boundary where it's guaranteed to be checked before any C-level work.
let _bridgeBusy = false;

function guardedCall(fn, fallback) {
    return function(...args) {
        if (_bridgeBusy) return fallback;
        _bridgeBusy = true;
        try {
            return fn.apply(null, args);
        } finally {
            _bridgeBusy = false;
        }
    };
}

function scheduleFlush() {
    if (!flushScheduled) {
        flushScheduled = true;
        requestAnimationFrame(() => {
            for (const id of pendingFlush) flushDisplay(id);
            pendingFlush.clear();
            flushScheduled = false;
        });
    }
}

function markDirty(displayId) {
    pendingFlush.add(displayId);
    scheduleFlush();
}

export function registerBridge(globalObj) {
    globalObj.bridgeDisplayFill = guardedCall(function(displayId, color) {
        displayFill(displayId, color);
        markDirty(displayId);
    }, undefined);

    globalObj.bridgeDisplayPixel = guardedCall(function(displayId, x, y, color) {
        displayPixel(displayId, x, y, color);
        markDirty(displayId);
    }, undefined);

    globalObj.bridgeDisplayFillRect = guardedCall(function(displayId, x, y, w, h, color) {
        displayFillRect(displayId, x, y, w, h, color);
        markDirty(displayId);
    }, undefined);

    globalObj.bridgeDisplayLine = guardedCall(function(displayId, x0, y0, x1, y1, color) {
        displayLine(displayId, x0, y0, x1, y1, color);
        markDirty(displayId);
    }, undefined);

    globalObj.bridgeDisplayCircle = guardedCall(function(displayId, x, y, r, color, filled) {
        displayCircle(displayId, x, y, r, color, !!filled);
        markDirty(displayId);
    }, undefined);

    globalObj.bridgeDisplayBlitBuffer = guardedCall(function(displayId, bufferPtr, x, y, width, height) {
        displayBlitBuffer(displayId, bufferPtr, x, y, width, height);
        markDirty(displayId);
    }, undefined);

    globalObj.bridgeDisplayText = guardedCall(function(displayId, text, x, y, fgColor, bgColor, charWidth, charHeight, fontName) {
        displayText(displayId, text, x, y, fgColor, bgColor, charWidth, charHeight, fontName);
        markDirty(displayId);
    }, undefined);

    globalObj.bridgeDisplayJpg = guardedCall(function(displayId, filename, x, y) {
        displayJpg(displayId, filename, x, y);
    }, undefined);

    globalObj.bridgeGetInputs = guardedCall(function() {
        return getInputs();
    }, 0xFFFF);

    globalObj.bridgeGetPinValue = guardedCall(function(pin) {
        return getPinValue(pin);
    }, 1);

    globalObj.bridgeNeopixelWrite = guardedCall(function(ledsJson) {
        const leds = JSON.parse(ledsJson);
        setLeds(leds);
    }, undefined);

    globalObj.bridgePollInterrupts = guardedCall(function() {
        return JSON.stringify(pollInterrupts());
    }, '[]');

    globalObj.bridgeGetAcceleration = guardedCall(function() {
        return JSON.stringify(getAccelData());
    }, '{"x":0,"y":0,"z":1}');

    globalObj.bridgeGetAdcVoltage = guardedCall(function() {
        return getAdcVoltage();
    }, 1340);

    globalObj.bridgePwmSetFreq = guardedCall(function(freq) { pwmSetFreq(freq); }, undefined);
    globalObj.bridgePwmSetDuty = guardedCall(function(duty) { pwmSetDuty(duty); }, undefined);
    globalObj.bridgePwmDeinit = guardedCall(function() { pwmDeinit(); }, undefined);

    globalObj.bridgeGetTimeMs = function() {
        return Date.now();
    };

    globalObj.bridgeFlushDisplays = guardedCall(function() {
        flushAllDisplays();
    }, undefined);
}
