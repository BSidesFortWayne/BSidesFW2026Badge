const buttonStates = new Array(8).fill(0);

const ioxButtonMap = [
    1 << 10, // Button 1: SW1
    1 << 9,  // Button 2: SW2
    1 << 8,  // Button 3: SW3
    1 << 0,  // Button 4: SW4
    1 << 1,  // Button 5: SW7
    1 << 2,  // Button 6: SW8
    1 << 3,  // Button 7: SW9
];

const keyToButton = {
    'Digit0': 0, // SW5 (boot)
    'Digit1': 7, // SW1
    'Digit2': 1, // SW2
    'Digit3': 2, // SW3
    'Digit4': 3, // SW4
    'Digit7': 6, // SW7
    'Digit8': 5, // SW8
    'Digit9': 4, // SW9
};

let onLogMessage = null;

export function initButtons(logCallback) {
    onLogMessage = logCallback;

    document.addEventListener('keydown', (e) => {
        const btn = keyToButton[e.code];
        if (btn !== undefined && buttonStates[btn] === 0) {
            buttonStates[btn] = Date.now();
            updateOverlay(btn, true);
            log(`Button ${btn} pressed (keyboard)`);
        }
    });

    document.addEventListener('keyup', (e) => {
        const btn = keyToButton[e.code];
        if (btn !== undefined && buttonStates[btn] > 0) {
            const held = Date.now() - buttonStates[btn];
            buttonStates[btn] = 0;
            updateOverlay(btn, false);
            log(`Button ${btn} released after ${held}ms`);
        }
    });

    for (const el of document.querySelectorAll('.btn-overlay')) {
        const btn = parseInt(el.dataset.btn, 10);
        // Keep HTML labels from index.html (SW names + key hints)

        el.addEventListener('mousedown', (e) => {
            e.preventDefault();
            if (buttonStates[btn] === 0) {
                buttonStates[btn] = Date.now();
                updateOverlay(btn, true);
                log(`Button ${btn} pressed (click)`);
            }
        });

        el.addEventListener('mouseup', () => {
            if (buttonStates[btn] > 0) {
                const held = Date.now() - buttonStates[btn];
                buttonStates[btn] = 0;
                updateOverlay(btn, false);
                log(`Button ${btn} released after ${held}ms`);
            }
        });

        el.addEventListener('mouseleave', () => {
            if (buttonStates[btn] > 0) {
                const held = Date.now() - buttonStates[btn];
                buttonStates[btn] = 0;
                updateOverlay(btn, false);
                log(`Button ${btn} released after ${held}ms (leave)`);
            }
        });

        // Touch support
        el.addEventListener('touchstart', (e) => {
            e.preventDefault();
            if (buttonStates[btn] === 0) {
                buttonStates[btn] = Date.now();
                updateOverlay(btn, true);
            }
        }, { passive: false });

        el.addEventListener('touchend', (e) => {
            e.preventDefault();
            if (buttonStates[btn] > 0) {
                buttonStates[btn] = 0;
                updateOverlay(btn, false);
            }
        }, { passive: false });
    }
}

export function getInputs() {
    let inputNumber = 0xFFFF;
    for (let btnIdx = 1; btnIdx < buttonStates.length; btnIdx++) {
        if (buttonStates[btnIdx] > 0) {
            const ioxIdx = btnIdx - 1;
            if (ioxIdx < ioxButtonMap.length) {
                inputNumber &= ~ioxButtonMap[ioxIdx];
            }
        }
    }
    return inputNumber;
}

export function getPinValue(pin) {
    if (pin === 0) {
        return buttonStates[0] > 0 ? 0 : 1;
    }
    return 1;
}

function updateOverlay(btn, pressed) {
    const el = document.querySelector(`.btn-overlay[data-btn="${btn}"]`);
    if (el) {
        el.classList.toggle('pressed', pressed);
    }
}

function log(msg) {
    if (onLogMessage) onLogMessage(msg, 'INFO');
}
