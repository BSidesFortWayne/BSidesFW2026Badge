const ledElements = [];

export function initLeds() {
    const strip = document.getElementById('led-strip');
    if (!strip) return;
    ledElements.length = 0;
    for (const el of strip.querySelectorAll('.led')) {
        ledElements.push(el);
    }
}

export function setLeds(ledsGrb) {
    for (let i = 0; i < 7 && i < ledsGrb.length; i++) {
        const [g, r, b] = ledsGrb[i];
        const el = ledElements[i];
        if (!el) continue;

        if (r === 0 && g === 0 && b === 0) {
            el.classList.remove('active');
            el.style.backgroundColor = 'transparent';
            el.style.boxShadow = 'none';
        } else {
            el.classList.add('active');
            el.style.backgroundColor = `rgb(${r},${g},${b})`;
            el.style.boxShadow =
                `0 0 8px rgba(${r},${g},${b},0.6), ` +
                `0 0 20px rgba(${r},${g},${b},0.3)`;
        }
    }
}
