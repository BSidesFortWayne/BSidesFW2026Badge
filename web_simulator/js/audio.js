let audioCtx = null;
let oscillator = null;
let gainNode = null;
let lastFreq = 440;

function ensureAudioCtx() {
    if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        gainNode = audioCtx.createGain();
        gainNode.gain.value = 0;
        gainNode.connect(audioCtx.destination);
    }
}

export function pwmSetFreq(freq) {
    ensureAudioCtx();
    lastFreq = freq;
    if (oscillator) {
        oscillator.frequency.setValueAtTime(freq, audioCtx.currentTime);
    }
}

export function pwmSetDuty(duty) {
    ensureAudioCtx();
    if (duty > 0) {
        if (!oscillator) {
            oscillator = audioCtx.createOscillator();
            oscillator.type = 'square';
            oscillator.frequency.value = lastFreq;
            oscillator.frequency.setValueAtTime(lastFreq, audioCtx.currentTime);
            oscillator.connect(gainNode);
            oscillator.start();
        }
        gainNode.gain.setValueAtTime(Math.min(duty / 1023, 1.0) * 0.3, audioCtx.currentTime);
    } else if (gainNode) {
        // Keep oscillator alive between notes — just mute the gain.
        // Tearing it down would force the next note to recreate with the default 440 Hz.
        gainNode.gain.setValueAtTime(0, audioCtx.currentTime);
    }
}

export function pwmDeinit() {
    if (oscillator) {
        oscillator.stop();
        oscillator.disconnect();
        oscillator = null;
    }
    if (gainNode) {
        gainNode.gain.setValueAtTime(0, audioCtx.currentTime);
    }
}
