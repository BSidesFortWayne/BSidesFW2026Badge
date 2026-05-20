import gc9a01
import time
import lib.uQR as uQR


def display_flag(challenge_title, flag, displays):
    """Render `flag` as a QR code on display 1 and `challenge_title` on display 2.

    Also prints the flag to the REPL as a fallback for players who happen to be
    watching the serial port. Caller is responsible for any "press to dismiss"
    UX — this function returns immediately after rendering.
    """
    print()
    print("=" * 60)
    print("FLAG ({}):".format(challenge_title))
    print("  {}".format(flag))
    print("=" * 60)
    print()

    qr = uQR.QRCode(error_correction=uQR.ERROR_CORRECT_M, box_size=1, border=0)
    qr.add_data(flag)
    qr.make()

    modules = qr.modules
    n = qr.modules_count
    # Display is 240×240 but the glass is a circle of radius 120 inscribed in
    # that square — the corners of a centered square get clipped. A centered
    # pattern of width W has its corners at distance W/√2 from center, so we
    # need W ≤ 120·√2 ≈ 169 to stay inside the visible glass. Use 165 for a
    # small safety margin. The white display fill around the pattern acts as
    # the QR quiet zone, so we don't need to reserve modules for a border.
    MAX_PATTERN_PX = 165
    box_size = max(2, MAX_PATTERN_PX // n)
    pattern_size = n * box_size
    offset = (240 - pattern_size) // 2

    d1 = displays.display1
    d1.fill(gc9a01.WHITE)
    for r in range(n):
        for c in range(n):
            if modules[r][c]:
                x = offset + c * box_size
                y = offset + r * box_size
                d1.fill_rect(x, y, box_size, box_size, gc9a01.BLACK)

    displays.display2.fill(gc9a01.BLACK)
    displays.display_center_text(challenge_title, fg=gc9a01.WHITE, display_index=2)
