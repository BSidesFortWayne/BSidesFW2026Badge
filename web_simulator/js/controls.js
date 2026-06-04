let accelData = [0.0, 0.0, 1.0];
let shakeMagnitude = 2.0;
let adcVoltage = 4.2;
let resistorR1 = 100.0;
let resistorR2 = 47.0;
let chargeState = 'not_charging';
let wifiState = 'disconnected';
let bluetoothState = 'disabled';

let interruptQueue = [];

export function initControls(logCallback) {
    const shakeBtn = document.getElementById('shake-btn');
    const shakeMag = document.getElementById('shake-mag');
    const battVoltage = document.getElementById('batt-voltage');
    const r1Slider = document.getElementById('r1-slider');
    const r2Slider = document.getElementById('r2-slider');
    const chargeSelect = document.getElementById('charge-state');
    const wifiSelect = document.getElementById('wifi-state');
    const btSelect = document.getElementById('bluetooth-state');
    const screenshotBtn = document.getElementById('screenshot-btn');

    shakeBtn.addEventListener('click', () => {
        applyShake();
        logCallback('Shake applied to accelerometer', 'INFO');
    });

    shakeMag.addEventListener('input', () => {
        shakeMagnitude = parseFloat(shakeMag.value);
        document.getElementById('shake-val').textContent = shakeMagnitude.toFixed(1);
    });

    battVoltage.addEventListener('input', () => {
        adcVoltage = parseFloat(battVoltage.value);
        document.getElementById('batt-val').textContent = adcVoltage.toFixed(2);
        updateDividedVoltage();
    });

    r1Slider.addEventListener('input', () => {
        resistorR1 = parseFloat(r1Slider.value);
        document.getElementById('r1-val').textContent = resistorR1.toFixed(1);
        updateDividedVoltage();
    });

    r2Slider.addEventListener('input', () => {
        resistorR2 = parseFloat(r2Slider.value);
        document.getElementById('r2-val').textContent = resistorR2.toFixed(1);
        updateDividedVoltage();
    });

    chargeSelect.addEventListener('change', () => { chargeState = chargeSelect.value; });
    wifiSelect.addEventListener('change', () => { wifiState = wifiSelect.value; });
    btSelect.addEventListener('change', () => { bluetoothState = btSelect.value; });

    screenshotBtn.addEventListener('click', () => {
        takeScreenshot();
        logCallback('Screenshot captured', 'INFO');
    });

    // Start decay loop
    setInterval(decayShake, 50);
    setInterval(updateAccelDisplay, 100);
}

function applyShake() {
    accelData = [
        (Math.random() * 2 - 1) * shakeMagnitude,
        (Math.random() * 2 - 1) * shakeMagnitude,
        (Math.random() * 2 - 1) * shakeMagnitude,
    ];
    interruptQueue.push({ pin: 34, edge: 'rising' });
}

function decayShake() {
    const rate = 0.1;
    accelData[0] *= (1 - rate);
    accelData[1] *= (1 - rate);
    accelData[2] = accelData[2] * (1 - rate) + 1.0 * rate;
}

function updateAccelDisplay() {
    const el = document.getElementById('accel-display');
    if (el) {
        el.textContent = `X: ${accelData[0].toFixed(2)}g Y: ${accelData[1].toFixed(2)}g Z: ${accelData[2].toFixed(2)}g`;
    }
}

function updateDividedVoltage() {
    const mV = (adcVoltage * 1000) * resistorR2 / (resistorR1 + resistorR2);
    const el = document.getElementById('divided-voltage');
    if (el) el.textContent = `ADC sees: ${Math.round(mV)}mV`;
}

function takeScreenshot() {
    const canvas1 = document.getElementById('display1');
    const canvas2 = document.getElementById('display2');
    // Create combined screenshot
    const offscreen = document.createElement('canvas');
    offscreen.width = 480;
    offscreen.height = 240;
    const ctx = offscreen.getContext('2d');
    ctx.drawImage(canvas1, 0, 0);
    ctx.drawImage(canvas2, 240, 0);
    offscreen.toBlob((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `badge_screenshot_${Date.now()}.png`;
        a.click();
        URL.revokeObjectURL(url);
    });
}

export function getAccelData() { return { x: accelData[0], y: accelData[1], z: accelData[2] }; }
export function getAdcVoltage() { return (adcVoltage * 1000) * resistorR2 / (resistorR1 + resistorR2); }
export function getChargeState() { return chargeState; }
export function getWifiState() { return wifiState; }
export function getBluetoothState() { return bluetoothState; }

export function pollInterrupts() {
    const q = interruptQueue.slice();
    interruptQueue = [];
    return q;
}
