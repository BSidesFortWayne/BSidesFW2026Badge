import framebuf

from lib.microfont import MicroFont
from ui.widget import Widget
from ui.theme import FG, FONT_BODY


class TextBox(Widget):
    def __init__(self, text: str = "", width: int = 0, height: int = 0, color=FG, name: str = ''):
        super().__init__(name)
        self.text = text
        self.width = width
        self.height = height
        self.color = color
        self.border = 0
        self.font = MicroFont(FONT_BODY, cache_index=True, cache_chars=True)

    def render(
            self,
            x: int,
            y: int,
            fbuf: framebuf.FrameBuffer,
            fbuf_width: int = 240,
            fbuf_height: int = 240
        ):
        if self.border:
            fbuf.rect(x - 1, y - 1, self.width + 2, self.height + 2, FG)
        width,height = self.font.write(
            self.text,
            fbuf,
            framebuf.RGB565,
            fbuf_width,
            fbuf_height,
            x,
            y,
            self.color,
        )

        return self.width or width, self.height or height


    def set_text(self, text: str):
        self.text = text

    def get_text(self) -> str:
        return self.text
    
