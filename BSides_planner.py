import time
import json
import os
import framebuf
import gc9a01
from apps.app import BaseApp
from lib.microfont import MicroFont

try:
    import urandom as _rng
except ImportError:
    import random as _rng

BTN_DOWN = 4
BTN_UP   = 5
BTN_SEL  = 6
BTN_BACK = 7

SCREEN_HOME      = 0
SCREEN_SET_TIME  = 1
SCREEN_SET_CUSTOM_HOUR = 2
SCREEN_SET_CUSTOM_MIN  = 3
SCREEN_SCHEDULE  = 4
SCREEN_FAVORITES = 5
SCREEN_DETAIL    = 6
SCREEN_OVERLAPS  = 7
SCREEN_HELP      = 8
SCREEN_WHAT_NEXT = 9
SCREEN_NAME      = 10

STATE_FILE = "config/apps/bsides_planner_state.json"

WHAT_NOW_SUGGESTIONS = [
    "Ask someone: red team or blue team?",
    "Visit a vendor booth and ask what problem they solve.",
    "Find someone with a cool badge mod.",
    "Ask a speaker one follow-up question.",
    "Trade one security tool recommendation.",
    "Ask someone what cert actually helped them.",
    "Find a student or first-timer and say hi.",
    "Compare notes with someone from a different talk.",
    "Ask someone about internships or entry-level roles.",
    "Write one follow-up question for later.",
    "Connect with one person on LinkedIn.",
    "Ask someone what talk they liked most so far.",
    "Go to the badge or CTF area and try one challenge.",
    "Ask a vendor what skills they hire for.",
    "Find someone from a different job role.",
    "Ask someone what lab or project they are building.",
    "Take one hallway lap and start one conversation.",
    "Ask someone what brought them to BSides.",
    "Write down one takeaway from the last talk.",
    "Pick a backup talk for the next time block.",
    "Ask someone what tool they use every week.",
    "Ask a speaker what beginners usually misunderstand.",
    "Find someone attending BSides for the first time.",
    "Ask someone what their home lab looks like.",
    "Ask a vendor what their product replaces.",
    "Ask someone what cybersecurity topic they are learning next.",
    "Trade LinkedIn or Discord with one person.",
    "Ask someone what talk they are going to next.",
    "Find someone who works in a role you want.",
    "Ask someone what advice they would give their younger self.",
    "Look for a sponsor you have never heard of and ask what they do.",
    "Ask someone what their favorite security news source is.",
    "Ask someone what project got them into cybersecurity.",
    "Introduce yourself to someone standing alone.",
    "Ask someone what they think of the badge.",
    "Ask someone if they are doing the CTF.",
    "Ask a vendor what their weirdest customer use case is.",
    "Write down one person you want to follow up with.",
    "Ask someone what skill is underrated in security.",
    "Find someone who went to the other talk in this time block.",
]

TALKS = [
    {"id":  0, "start":  8*3600,            "end":  9*3600,            "title": "Doors Open & Registration",                                               "speaker": "",                               "room": "International Ballroom", "type": "event"},
    {"id":  1, "start":  9*3600,            "end": 10*3600,            "title": "Keynote: From First Packet to Critical Infrastructure",                    "speaker": "Jeff Cody",                      "room": "International Ballroom", "type": "keynote"},
    {"id":  2, "start": 10*3600,            "end": 16*3600,            "title": "CTF",                                                                      "speaker": "",                               "room": "CTF & Badge Hacking",    "type": "ctf"},
    {"id":  3, "start": 10*3600,            "end": 11*3600,            "title": "$200 and a Conversation: AI in Security Infrastructure",                   "speaker": "Jim Haist",                      "room": "International Ballroom", "type": "talk"},
    {"id":  4, "start": 10*3600,            "end": 10*3600 + 30*60,    "title": "Securing AV and UC Environments",                                          "speaker": "Doug Schaefer",                  "room": "Classic Ballroom",       "type": "talk"},
    {"id":  5, "start": 10*3600 + 30*60,    "end": 11*3600,            "title": "Accidental AppSec: Building AppSec Without a Dedicated Team",              "speaker": "Eric Gaby",                      "room": "Classic Ballroom",       "type": "talk"},
    {"id":  6, "start": 11*3600,            "end": 11*3600 + 30*60,    "title": "Don't Feed the Trolls: GenAI Data Leakage & Poisoning",                   "speaker": "Richard Rieben",                 "room": "International Ballroom", "type": "talk"},
    {"id":  7, "start": 11*3600,            "end": 11*3600 + 30*60,    "title": "Influencing Culture. Risk Assessments",                                    "speaker": "TJ Patterson",                   "room": "Classic Ballroom",       "type": "talk"},
    {"id":  8, "start": 11*3600 + 30*60,    "end": 12*3600,            "title": "Break - Lunch Prep",                                                       "speaker": "",                               "room": "International Ballroom", "type": "break"},
    {"id":  9, "start": 11*3600 + 30*60,    "end": 12*3600,            "title": "From Quiet to Mic: Introvert's Guide to CyberSec Speaking",               "speaker": "Anushree Vaidya",                "room": "Classic Ballroom",       "type": "talk"},
    {"id": 10, "start": 12*3600,            "end": 13*3600,            "title": "Lunch",                                                                    "speaker": "Included with Registration",     "room": "International Ballroom", "type": "lunch"},
    {"id": 11, "start": 13*3600,            "end": 14*3600,            "title": "Seeing Is Deceiving: Deepfakes & the New Trust Crisis",                   "speaker": "Kyle Hinterberg",                "room": "International Ballroom", "type": "talk"},
    {"id": 12, "start": 13*3600,            "end": 13*3600 + 30*60,    "title": "A.I., Code, and Security",                                                 "speaker": "Toby Chin",                      "room": "Classic Ballroom",       "type": "talk"},
    {"id": 13, "start": 13*3600 + 30*60,    "end": 14*3600,            "title": "Hardening Security by Pruning JS Dependencies",                            "speaker": "Jim Ender",                      "room": "Classic Ballroom",       "type": "talk"},
    {"id": 14, "start": 14*3600,            "end": 15*3600,            "title": "Definitely Not Secure (DNS)",                                              "speaker": "Matt Scheurer",                  "room": "International Ballroom", "type": "talk"},
    {"id": 15, "start": 14*3600,            "end": 15*3600,            "title": "Securing the Future: Intelligent Network Security",                        "speaker": "David Akinsanya",                "room": "Classic Ballroom",       "type": "talk"},
    {"id": 16, "start": 15*3600,            "end": 15*3600 + 30*60,    "title": "Vishing From a CyberSec Professional POV",                                 "speaker": "Justin Youvan",                  "room": "International Ballroom", "type": "talk"},
    {"id": 17, "start": 15*3600,            "end": 15*3600 + 30*60,    "title": "Why Passing Your SOX Audit Doesn't Mean You're Secure",                   "speaker": "Rachana Sharma",                 "room": "Classic Ballroom",       "type": "talk"},
    {"id": 18, "start": 15*3600 + 30*60,    "end": 16*3600 + 30*60,    "title": "From Pitch to Program: Securing Executive Buy-In for TI",                 "speaker": "Cory Hlavacek",                  "room": "International Ballroom", "type": "talk"},
    {"id": 19, "start": 15*3600 + 30*60,    "end": 16*3600 + 30*60,    "title": "Why Is My Hair on Fire?",                                                  "speaker": "Chuck Knox",                     "room": "Classic Ballroom",       "type": "talk"},
    {"id": 20, "start": 16*3600 + 30*60,    "end": 17*3600,            "title": "Closing Remarks",                                                          "speaker": "BSides Fort Wayne Leadership",   "room": "International Ballroom", "type": "event"},
]

TALK_BY_ID = {}
for _t in TALKS:
    TALK_BY_ID[_t["id"]] = _t

_SEG = [
    [0b11111, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b11111],
    [0b00100, 0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110],
    [0b11111, 0b00001, 0b00001, 0b11111, 0b10000, 0b10000, 0b11111],
    [0b11111, 0b00001, 0b00001, 0b11111, 0b00001, 0b00001, 0b11111],
    [0b10001, 0b10001, 0b10001, 0b11111, 0b00001, 0b00001, 0b00001],
    [0b11111, 0b10000, 0b10000, 0b11111, 0b00001, 0b00001, 0b11111],
    [0b11111, 0b10000, 0b10000, 0b11111, 0b10001, 0b10001, 0b11111],
    [0b11111, 0b00001, 0b00001, 0b00011, 0b00010, 0b00100, 0b00100],
    [0b11111, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b11111],
    [0b11111, 0b10001, 0b10001, 0b11111, 0b00001, 0b00001, 0b11111],
]

_COLON_ROWS = [0, 0, 1, 0, 1, 0, 0]

class App(BaseApp):
    name    = "BSides Planner"
    version = "4.0.0"
    hidden  = False

    def __init__(self, controller):
        super().__init__(controller)
        self.disp1 = self.controller.bsp.displays.display1
        self.disp2 = self.controller.bsp.displays.display2

        self.w = 240
        self.h = 240

        self._buf1_mem = bytearray(self.w * self.h * 2)
        self._buf2_mem = bytearray(self.w * self.h * 2)
        self.buf1 = framebuf.FrameBuffer(self._buf1_mem, self.w, self.h, framebuf.RGB565)
        self.buf2 = framebuf.FrameBuffer(self._buf2_mem, self.w, self.h, framebuf.RGB565)
        self._mv1  = memoryview(self._buf1_mem)
        self._mv2  = memoryview(self._buf2_mem)

        self.buf    = self.buf1
        self._cur_mv = self._mv1

        try:
            self.font = MicroFont("fonts/victor_R_24.mfnt", cache_index=True, cache_chars=True)
        except Exception:
            self.font = None

        self.screen           = SCREEN_SET_TIME
        self.previous_screen  = SCREEN_HOME
        self.selected         = 0
        self.detail_talk      = None
        self.detail_actions   = ["Next Talk", "Toggle Fav", "Other Talks", "Back"]
        self.overlap_source   = None

        self.favorites    = []
        self.base_seconds = None
        self.base_ticks   = None
        self.custom_hour  = 9
        self.custom_min   = 0
        self.needs_redraw = True
        self.last_second  = -1
        self.message      = ""
        self.conflict_msg = ""
        self._detail_entered_ms = -9999
        self._btn_up_held_ms   = -1
        self._btn_down_held_ms = -1
        self._combo_triggered  = False

        self.home_menu = ["Full Schedule", "My Talks", "Current Block",
                          "Set Time", "Demo 10:45", "Demo 1:15",
                          "What Next?", "My Name", "Help"]
        self.time_menu = ["8:00", "9:00", "10:00", "Demo 10:45", "Demo 1:15", "Custom"]

        self.what_next_suggestion = ""
        self.my_name = "Xavier Roberts"

        self._current_block_mode = False

        self.bg_color = gc9a01.BLACK
        self.fg_color = gc9a01.WHITE

    def _load_name(self):
        try:
            with open("/name.json") as f:
                data = json.loads(f.read())
            return data.get("name", "") or data.get("handle", "") or ""
        except Exception:
            return ""

    async def setup(self):
        self.disp1.fill(gc9a01.BLACK)
        self.disp2.fill(gc9a01.BLACK)
        self.load_state()
        self.screen  = SCREEN_HOME if self.base_seconds is not None else SCREEN_SET_TIME
        self.selected = 0
        self.needs_redraw = True

    async def teardown(self):
        self.save_state()
        self.disp1.fill(gc9a01.BLACK)
        self.disp2.fill(gc9a01.BLACK)

    async def update(self):
        self._check_combo()
        now = self.now_seconds()
        if now != self.last_second:
            self.last_second = now
            self.needs_redraw = True
        if self.needs_redraw:
            self.draw()
            self.needs_redraw = False

    def button_press(self, button):
        now = time.ticks_ms()
        if button == BTN_UP:
            self._btn_up_held_ms  = now
            self._combo_triggered = False
            self.move(-1)
        elif button == BTN_DOWN:
            self._btn_down_held_ms = now
            self._combo_triggered  = False
            self.move(1)
        elif button == BTN_SEL:
            self.select()
        elif button == BTN_BACK:
            self.back()

    def button_click(self, button):
        pass

    def button_release(self, button):
        if button == BTN_UP:
            self._btn_up_held_ms  = -1
            self._combo_triggered = False
        elif button == BTN_DOWN:
            self._btn_down_held_ms = -1
            self._combo_triggered  = False

    def button_long_press(self, button):
        if button == BTN_BACK:
            self.back()
        elif button == BTN_UP:
            if self._btn_down_held_ms < 0:
                self.back()

    def _check_combo(self):
        if self._combo_triggered:
            return
        if self._btn_up_held_ms < 0 or self._btn_down_held_ms < 0:
            return
        now     = time.ticks_ms()
        up_dur  = time.ticks_diff(now, self._btn_up_held_ms)
        dn_dur  = time.ticks_diff(now, self._btn_down_held_ms)
        if up_dur >= 3000 and dn_dur >= 3000:
            self._combo_triggered  = True
            self._btn_up_held_ms   = -1
            self._btn_down_held_ms = -1
            self.screen   = SCREEN_HOME
            self.selected = 0
            self._current_block_mode = False
            self.needs_redraw = True

    def load_state(self):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.loads(f.read())
            favs = data.get("favorites", [])
            self.favorites = [fid for fid in favs if fid in TALK_BY_ID]
            bs = data.get("base_seconds", None)
            if bs is not None:
                self.base_seconds = bs
                self.base_ticks   = time.ticks_ms()
        except Exception as e:
            print("BSides Planner load failed:", e)
            self.favorites    = []
            self.base_seconds = None
            self.base_ticks   = None

    def save_state(self):
        data = {"favorites": self.favorites, "base_seconds": self.base_seconds}
        try:
            try: os.mkdir("config")
            except Exception: pass
            try: os.mkdir("config/apps")
            except Exception: pass
            with open(STATE_FILE, "w") as f:
                f.write(json.dumps(data))
        except Exception as e:
            print("BSides Planner save failed:", e)

    def set_time(self, seconds):
        self.base_seconds = int(seconds) % (24 * 3600)
        self.base_ticks   = time.ticks_ms()
        self.save_state()
        self.screen   = SCREEN_HOME
        self.selected = 0
        self.message  = "Time set"
        self.needs_redraw = True

    def now_seconds(self):
        if self.base_seconds is None or self.base_ticks is None:
            return 0
        elapsed_ms = time.ticks_diff(time.ticks_ms(), self.base_ticks)
        corrected_ms = int(elapsed_ms * 0.9963)
        return (self.base_seconds + corrected_ms // 1000) % (24 * 3600)

    def current_list(self):
        if self.screen == SCREEN_HOME:      return self.home_menu
        if self.screen == SCREEN_SET_TIME:  return self.time_menu
        if self.screen == SCREEN_SCHEDULE:  return ["< Home"] + TALKS
        if self.screen == SCREEN_FAVORITES: return ["< Home"] + self.favorite_talks()
        if self.screen == SCREEN_OVERLAPS:  return ["< Back"] + self.get_overlapping_talks(self.overlap_source)
        if self.screen == SCREEN_DETAIL:    return self.detail_actions
        return []

    def move(self, delta):
        if self.screen == SCREEN_SET_CUSTOM_HOUR:
            self.custom_hour = (self.custom_hour + delta) % 24
        elif self.screen == SCREEN_SET_CUSTOM_MIN:
            self.custom_min  = (self.custom_min + delta) % 60
        elif self.screen == SCREEN_WHAT_NEXT:
            self.selected = (self.selected + delta) % 2
        else:
            items = self.current_list()
            if items:
                self.selected = (self.selected + delta) % len(items)
        self.needs_redraw = True

    def select(self):
        if self.screen == SCREEN_HOME:
            item = self.home_menu[self.selected]
            if   item == "Full Schedule":  self.goto_list(SCREEN_SCHEDULE)
            elif item == "My Talks":       self.goto_list(SCREEN_FAVORITES)
            elif item == "Current Block":
                self.screen   = SCREEN_SCHEDULE
                self.selected = 0
                self._current_block_mode = True
            elif item == "Set Time":       self.goto_list(SCREEN_SET_TIME)
            elif item == "Demo 10:45":     self.set_time(10 * 3600 + 45 * 60)
            elif item == "Demo 1:15":      self.set_time(13 * 3600 + 15 * 60)
            elif item == "What Next?":
                self.what_next_suggestion = WHAT_NOW_SUGGESTIONS[
                    _rng.randint(0, len(WHAT_NOW_SUGGESTIONS) - 1)]
                self.screen   = SCREEN_WHAT_NEXT
                self.selected = 0
            elif item == "My Name":
                self.screen   = SCREEN_NAME
                self.selected = 0
            elif item == "Help":
                self.screen   = SCREEN_HELP
                self.selected = 0

        elif self.screen == SCREEN_SET_TIME:
            item = self.time_menu[self.selected]
            if   item == "8:00":        self.set_time(8 * 3600)
            elif item == "9:00":        self.set_time(9 * 3600)
            elif item == "10:00":       self.set_time(10 * 3600)
            elif item == "Demo 10:45":  self.set_time(10 * 3600 + 45 * 60)
            elif item == "Demo 1:15":   self.set_time(13 * 3600 + 15 * 60)
            elif item == "Custom":
                self.screen   = SCREEN_SET_CUSTOM_HOUR
                self.selected = 0

        elif self.screen == SCREEN_SET_CUSTOM_HOUR:
            self.screen = SCREEN_SET_CUSTOM_MIN

        elif self.screen == SCREEN_SET_CUSTOM_MIN:
            self.set_time(self.custom_hour * 3600 + self.custom_min * 60)

        elif self.screen in (SCREEN_SCHEDULE, SCREEN_FAVORITES, SCREEN_OVERLAPS):
            items = self.current_list()
            if not items:
                self.screen = SCREEN_HOME
            else:
                item = items[self.selected]
                if isinstance(item, str):
                    self.back()
                else:
                    self.detail_talk          = item
                    self.previous_screen      = self.screen
                    self.screen               = SCREEN_DETAIL
                    self.selected             = 0
                    self.message              = ""
                    self.conflict_msg         = ""
                    self._detail_entered_ms   = time.ticks_ms()

        elif self.screen == SCREEN_DETAIL:
            if time.ticks_diff(time.ticks_ms(), self._detail_entered_ms) < 400:
                self.needs_redraw = True
                return
            idx = self.selected
            if idx == 0:
                nxt = self._next_talk_from(self.detail_talk)
                if nxt:
                    self.detail_talk        = nxt
                    self.selected           = 0
                    self.message            = ""
                    self.conflict_msg       = ""
                    self._detail_entered_ms = time.ticks_ms()
            elif idx == 1:
                self.toggle_favorite(self.detail_talk)
            elif idx == 2:
                self.overlap_source  = self.detail_talk
                self.previous_screen = SCREEN_DETAIL
                self.goto_list(SCREEN_OVERLAPS)
            elif idx == 3:
                self.back()

        elif self.screen == SCREEN_HELP:
            self.screen   = SCREEN_HOME
            self.selected = 0

        elif self.screen == SCREEN_WHAT_NEXT:
            if self.selected == 0:
                self.what_next_suggestion = WHAT_NOW_SUGGESTIONS[
                    _rng.randint(0, len(WHAT_NOW_SUGGESTIONS) - 1)]
            else:
                self.back()

        self.needs_redraw = True

    def back(self):
        if self.screen == SCREEN_DETAIL:
            prev = self.previous_screen if self.previous_screen is not None else SCREEN_HOME
            self.screen = prev
            self.selected = self._list_index_of(self.detail_talk, prev)
        elif self.screen == SCREEN_OVERLAPS:
            self.screen = SCREEN_DETAIL if self.detail_talk is not None else SCREEN_HOME
            self.selected = 0
        elif self.screen in (SCREEN_SCHEDULE, SCREEN_FAVORITES, SCREEN_SET_TIME,
                             SCREEN_HELP, SCREEN_WHAT_NEXT, SCREEN_NAME):
            self.screen = SCREEN_HOME
            self.selected = 0
            self._current_block_mode = False
        elif self.screen in (SCREEN_SET_CUSTOM_HOUR, SCREEN_SET_CUSTOM_MIN):
            self.screen = SCREEN_SET_TIME
            self.selected = 0
        else:
            self.screen = SCREEN_HOME
            self.selected = 0
        self.needs_redraw = True

    def _list_index_of(self, talk, screen):
        if not talk:
            return 0
        if screen == SCREEN_SCHEDULE:
            items = ["< Home"] + TALKS
        elif screen == SCREEN_FAVORITES:
            items = ["< Home"] + self.favorite_talks()
        elif screen == SCREEN_OVERLAPS:
            items = ["< Back"] + self.get_overlapping_talks(self.overlap_source)
        else:
            return 0
        for i, item in enumerate(items):
            if isinstance(item, dict) and item.get("id") == talk.get("id"):
                return i
        return 0

    def goto_list(self, screen):
        self.screen       = screen
        self.selected     = 0
        self.needs_redraw = True

    def favorite_talks(self):
        return [t for t in TALKS if t["id"] in self.favorites]

    def toggle_favorite(self, talk):
        if not talk:
            return
        tid = talk["id"]
        if tid in self.favorites:
            self.favorites.remove(tid)
            self.message      = "Removed"
            self.conflict_msg = ""
        else:
            c = self.first_conflict(talk)
            if c:
                short = self.shorten(c["title"], 16)
                self.conflict_msg = "Already fav'd:\n" + short + "\nUnselect it first!"
                self.message      = ""
            else:
                self.favorites.append(tid)
                self.message      = "Favorited!"
                self.conflict_msg = ""
        self.save_state()

    def first_conflict(self, talk):
        if not talk:
            return None
        for fid in self.favorites:
            if fid == talk["id"]:
                continue
            other = TALK_BY_ID.get(fid)
            if other and self.overlaps(talk, other):
                return other
        return None

    def overlaps(self, a, b):
        return a["start"] < b["end"] and a["end"] > b["start"]

    def get_overlapping_talks(self, target):
        if not target:
            return []
        SKIP_TYPES = ("ctf", "event", "break", "lunch")
        return [t for t in TALKS
                if t["id"] != target["id"]
                and t.get("type", "") not in SKIP_TYPES
                and self.overlaps(target, t)]

    def _next_talk_from(self, talk):
        if not talk:
            return None
        ids = [t["id"] for t in TALKS]
        try:
            idx = ids.index(talk["id"])
        except ValueError:
            return None
        return TALKS[(idx + 1) % len(TALKS)]

    def next_favorite(self):
        now = self.now_seconds()
        for t in self.favorite_talks():
            if t["start"] <= now < t["end"]:
                return t
        future = [t for t in self.favorite_talks() if t["end"] > now]
        return future[0] if future else None

    def next_overall(self):
        now = self.now_seconds()
        for t in TALKS:
            if t["end"] > now:
                return t
        return None

    def current_block_talks(self):
        now = self.now_seconds()
        return [t for t in TALKS if t["start"] <= now < t["end"]]

    def draw(self):
        self.draw_left_dashboard()

        if   self.screen == SCREEN_HOME:              self.draw_right_home()
        elif self.screen == SCREEN_SET_TIME:          self.draw_set_time()
        elif self.screen == SCREEN_SET_CUSTOM_HOUR:   self.draw_custom_time(hour_screen=True)
        elif self.screen == SCREEN_SET_CUSTOM_MIN:    self.draw_custom_time(hour_screen=False)
        elif self.screen == SCREEN_SCHEDULE:
            if self._current_block_mode:
                block = self.current_block_talks()
                title = "Current Block"
                items = ["< Home"] + (block if block else [])
                self.draw_right_list(title, items, empty="No talks right now")
            else:
                self.draw_right_list("Full Schedule", ["< Home"] + TALKS)
        elif self.screen == SCREEN_FAVORITES:
            favs = self.favorite_talks()
            self.draw_right_list("My Talks", ["< Home"] + favs, empty="No favorites yet")
        elif self.screen == SCREEN_DETAIL:            self.draw_detail()
        elif self.screen == SCREEN_OVERLAPS:
            overlaps = self.get_overlapping_talks(self.overlap_source)
            self.draw_right_list("Same Time", ["< Back"] + overlaps, empty="No other talks")
        elif self.screen == SCREEN_HELP:              self.draw_help()
        elif self.screen == SCREEN_WHAT_NEXT:         self.draw_what_next()
        elif self.screen == SCREEN_NAME:              self.draw_name_screen()

    def draw_left_dashboard(self):
        now   = self.now_seconds()
        favs  = self.favorites

        if not favs:
            self._render_dashboard_no_favs()
            return

        happening = None
        for t in self.favorite_talks():
            if t["start"] <= now < t["end"]:
                happening = t
                break

        if happening:
            secs_left = happening["end"] - now
            others    = self.get_overlapping_talks(happening)
            self._render_dashboard_talk(
                status="Happening Now",
                status_color=gc9a01.GREEN,
                talk=happening,
                secs=secs_left,
                others=others
            )
            return

        future_favs = [t for t in self.favorite_talks() if t["end"] > now]
        if future_favs:
            nxt = future_favs[0]
            secs_until = nxt["start"] - now
            others     = self.get_overlapping_talks(nxt)
            self._render_dashboard_talk(
                status="Next Favorite",
                status_color=gc9a01.YELLOW,
                talk=nxt,
                secs=secs_until,
                others=others
            )
            return

        block = self.current_block_talks()
        if block:
            self._render_dashboard_no_block_fav(block)
            return

        self._render_dashboard_all_done()

    def _render_dashboard_no_favs(self):
        self._use_buf1()
        self.buf.fill(self.bg_color)

        self.center_text("No Favorites", y=34, color=gc9a01.YELLOW, buf=self.buf, mv=self._cur_mv)
        self.center_text("Fav a talk!", y=54, color=self.fg_color, buf=self.buf, mv=self._cur_mv)
        self.draw_big_countdown(0, y_top=88)
        self.buf1.text("Open Schedule", 40, 152, gc9a01.CYAN)
        self.buf1.text("press Select", 44, 164, gc9a01.CYAN)

        self.disp1.blit_buffer(self._cur_mv, 0, 0, self.w, self.h)

    def _render_dashboard_no_block_fav(self, block):
        self._use_buf1()
        self.buf.fill(self.bg_color)

        self.center_text("No Favorite", y=34, color=gc9a01.YELLOW, buf=self.buf, mv=self._cur_mv)
        self.center_text("Current Slot", y=54, color=self.fg_color, buf=self.buf, mv=self._cur_mv)
        self.draw_big_countdown(0, y_top=88)
        t0  = block[0]
        rng = self.fmt_range(t0["start"], t0["end"])
        self.buf1.text(rng, 60, 152, self.fg_color)
        self.buf1.text("Choose a talk", 40, 164, gc9a01.CYAN)
        self.buf1.text("for this block", 38, 174, gc9a01.CYAN)

        self.disp1.blit_buffer(self._cur_mv, 0, 0, self.w, self.h)

    def _render_dashboard_all_done(self):
        self._use_buf1()
        self.buf.fill(self.bg_color)

        self.center_text("All Done!", y=35, color=gc9a01.GREEN, buf=self.buf, mv=self._cur_mv)
        self.center_text("No more favs", y=57, color=self.fg_color, buf=self.buf, mv=self._cur_mv)
        self.draw_big_countdown(0, y_top=80)
        self.buf1.text("Thanks for coming!", 36, 148, gc9a01.CYAN)

        self.disp1.blit_buffer(self._cur_mv, 0, 0, self.w, self.h)

    def _render_dashboard_talk(self, status, status_color, talk, secs, others):
        self._use_buf1()
        self.buf.fill(self.bg_color)

        title_lines = self.wrap_text(talk["title"], max_chars=14, max_lines=2)
        n_title     = len(title_lines)

        spk         = talk.get("speaker", "") or ""
        has_spk     = bool(spk)

        total_m = int(secs) // 60
        cd_h    = 56 if total_m < 100 else 28

        SKIP        = ("ctf", "event", "break", "lunch")
        real_others = [o for o in others if o.get("type", "") not in SKIP]
        n_others    = min(len(real_others), 1)

        total_h  = 8 + 8
        total_h += n_title * 24
        total_h += max(0, n_title - 1) * 4
        total_h += 8
        total_h += cd_h
        total_h += 8
        if has_spk:
            total_h += 8 + 6
        total_h += 8
        if n_others:
            total_h += 8 + 8 + 4
            total_h += 8

        y = max(18, (240 - total_h) // 2)

        sl = str(status)
        sx = max(20, (240 - len(sl) * 8) // 2)
        self.buf1.text(sl, sx, y, status_color)
        y += 8 + 8

        for i, line in enumerate(title_lines):
            self.center_text(line, y=y, color=self.fg_color, buf=self.buf, mv=self._cur_mv)
            y += 24
            if i < n_title - 1:
                y += 4
        y += 8

        self.draw_big_countdown(secs, y_top=y)
        y += cd_h + 8

        if has_spk:
            spk_s = self.shorten(spk, 22)
            spx   = max(20, (240 - len(spk_s) * 8) // 2)
            self.buf1.text(spk_s, spx, y, self.fg_color)
            y += 8 + 6

        room_short = self.shorten(talk["room"], 22)
        rx = max(20, (240 - len(room_short) * 8) // 2)
        self.buf1.text(room_short, rx, y, gc9a01.CYAN)
        y += 8

        if n_others:
            y += 8
            ol = "Other talks:"
            ox = max(20, (240 - len(ol) * 8) // 2)
            self.buf1.text(ol, ox, y, self.fg_color)
            y += 8 + 4
            ot  = self.shorten(real_others[0]["title"], 24)
            otx = max(20, (240 - len(ot) * 8) // 2)
            self.buf1.text(ot, otx, y, self.fg_color)

        self.disp1.blit_buffer(self._cur_mv, 0, 0, self.w, self.h)

    def draw_big_countdown(self, secs, y_top=80):
        if secs < 0:
            secs = 0
        total_secs = int(secs)
        total_m = total_secs // 60
        s       = total_secs % 60

        if total_m < 100:
            m       = total_m
            scale   = 8
            dw      = 5 * scale
            gap     = 3
            col_pad = 6
            col_w   = 1 * scale
            total_w = dw + gap + dw + col_pad + col_w + col_pad + dw + gap + dw
            x       = (self.w - total_w) // 2
            color   = gc9a01.WHITE
            self._draw_digit((m // 10) % 10, x, y_top, scale, color); x += dw + gap
            self._draw_digit(m % 10,          x, y_top, scale, color); x += dw + col_pad
            self._draw_colon(x, y_top, scale, color);                   x += col_w + col_pad
            self._draw_digit((s // 10) % 10, x, y_top, scale, color); x += dw + gap
            self._draw_digit(s % 10,          x, y_top, scale, color)
        else:
            h       = total_m // 60
            m       = total_m % 60
            scale   = 4
            dw      = 5 * scale
            gap     = 2
            col_pad = 3
            col_w   = 1 * scale
            total_w = (dw+gap+dw) + (col_pad+col_w+col_pad) + (dw+gap+dw) + (col_pad+col_w+col_pad) + (dw+gap+dw)
            x       = (self.w - total_w) // 2
            color   = gc9a01.WHITE
            self._draw_digit((h // 10) % 10, x, y_top, scale, color); x += dw + gap
            self._draw_digit(h % 10,          x, y_top, scale, color); x += dw + col_pad
            self._draw_colon(x, y_top, scale, color);                   x += col_w + col_pad
            self._draw_digit((m // 10) % 10, x, y_top, scale, color); x += dw + gap
            self._draw_digit(m % 10,          x, y_top, scale, color); x += dw + col_pad
            self._draw_colon(x, y_top, scale, color);                   x += col_w + col_pad
            self._draw_digit((s // 10) % 10, x, y_top, scale, color); x += dw + gap
            self._draw_digit(s % 10,          x, y_top, scale, color)

    def _draw_digit(self, digit, x, y, scale, color):
        rows = _SEG[digit % 10]
        fr = self.buf.fill_rect
        for row_idx, mask in enumerate(rows):
            for col_idx in range(5):
                if mask & (1 << (4 - col_idx)):
                    fr(x + col_idx * scale, y + row_idx * scale, scale, scale, color)

    def _draw_colon(self, x, y, scale, color):
        fr = self.buf.fill_rect
        for row_idx, dot in enumerate(_COLON_ROWS):
            if dot:
                fr(x, y + row_idx * scale, scale, scale, color)

    def center_text(self, text, y, color=gc9a01.WHITE, buf=None, mv=None):
        if buf is None:
            buf = self.buf
        if mv is None:
            mv = self._cur_mv
        if text is None:
            return
        text = str(text)
        char_w = 13
        text_w = len(text) * char_w
        ideal_x = (self.w - text_w) // 2
        x = max(28, ideal_x)
        if x + text_w > 212:
            x = max(28, 212 - text_w)
        self._write_text(text, x, y, color, mv)

    def _write_text(self, text, x, y, color, mv):
        try:
            self.font.write(str(text), mv, framebuf.RGB565, self.w, self.h, x, y, color)
        except Exception:
            self.buf.text(str(text), x, y, color)

    def right_text(self, text, x, y, color=gc9a01.WHITE):
        self._write_text(text, x, y, color, self._cur_mv)

    def shorten(self, text, max_chars):
        if text is None:
            return ""
        text = str(text)
        if len(text) <= max_chars:
            return text
        return text[:max(0, max_chars - 3)] + "..."

    def wrap_text(self, text, max_chars=20, max_lines=2):
        if not text:
            return [""]
        words  = str(text).split()
        lines  = []
        current = ""
        for word in words:
            candidate = (current + " " + word).strip()
            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current:
                    lines.append(current)
                if len(lines) >= max_lines:
                    last = lines[-1]
                    if len(last) > max_chars - 3:
                        lines[-1] = last[:max_chars - 3] + "..."
                    return lines
                current = word[:max_chars]
        if current and len(lines) < max_lines:
            lines.append(current)
        return lines if lines else [""]

    def two(self, n):
        return ("0" + str(int(n)))[-2:]

    def secs_to_hhmm(self, seconds):
        seconds = int(seconds) % 86400
        h = seconds // 3600
        m = (seconds % 3600) // 60
        ms = str(m) if m >= 10 else "0" + str(m)
        return str(h) + ":" + ms

    def fmt_range(self, start, end):
        return self.secs_to_hhmm(start) + "-" + self.secs_to_hhmm(end)

    def mmss(self, seconds):
        if seconds < 0:
            seconds = 0
        m = int(seconds) // 60
        s = int(seconds) % 60
        return str(m) + ":" + self.two(s)

    def _use_buf1(self):
        self.buf      = self.buf1
        self._cur_mv  = self._mv1

    def _use_buf2(self):
        self.buf      = self.buf2
        self._cur_mv  = self._mv2

    def _blit1(self):
        self.disp1.blit_buffer(self._mv1, 0, 0, self.w, self.h)

    def _blit2(self):
        self.disp2.blit_buffer(self._mv2, 0, 0, self.w, self.h)

    def draw_right_home(self):
        self._use_buf2()
        self.buf.fill(gc9a01.BLACK)
        self.small_center_text("BSides FW 2026", y=22, color=gc9a01.CYAN)
        now_str = self.secs_to_hhmm(self.now_seconds())
        self.small_center_text("Time: " + now_str, y=34, color=gc9a01.WHITE)
        self._draw_right_menu(self.home_menu, self.selected, y_start=50)
        self._blit2()

    def draw_set_time(self):
        self._use_buf2()
        self.buf.fill(gc9a01.BLACK)
        self.small_center_text("Set Time", y=22, color=gc9a01.CYAN)
        self.small_center_text("Eastern / Fort Wayne", y=34, color=gc9a01.WHITE)
        self.small_center_text("Use demo for judging!", y=44, color=gc9a01.YELLOW)
        self._draw_right_menu(self.time_menu, self.selected, y_start=58)
        self._blit2()

    def draw_custom_time(self, hour_screen):
        self._use_buf2()
        self.buf.fill(gc9a01.BLACK)
        self.small_center_text("Custom Time", y=22, color=gc9a01.CYAN)
        self.small_center_text("UP/DN to change", y=34, color=gc9a01.WHITE)
        self.small_center_text("SEL to confirm", y=44, color=gc9a01.WHITE)
        if hour_screen:
            self.small_center_text("Hour:", y=70, color=gc9a01.YELLOW)
            self.small_center_text(str(self.custom_hour), y=90, color=gc9a01.WHITE)
        else:
            self.small_center_text("Minute:", y=70, color=gc9a01.YELLOW)
            self.small_center_text(self.two(self.custom_min), y=90, color=gc9a01.WHITE)
        preview = self.two(self.custom_hour) + ":" + self.two(self.custom_min)
        self.small_center_text(preview, y=120, color=gc9a01.GREEN)
        self._blit2()

    def draw_right_list(self, title, items, empty=""):
        self._use_buf2()
        self.buf.fill(gc9a01.BLACK)
        self.small_center_text(self.shorten(title, 22), y=22, color=gc9a01.CYAN)
        if not items or (len(items) == 1 and isinstance(items[0], str)):
            if empty:
                self.small_center_text(empty, y=110, color=gc9a01.YELLOW)
            self._blit2()
            return
        self._draw_right_menu(items, self.selected, y_start=36, talk_rows=True)
        self._blit2()

    def _draw_right_menu(self, items, selected, y_start=46, talk_rows=False):
        visible  = 8
        start    = max(0, min(selected - 3, max(0, len(items) - visible)))
        y        = y_start
        LINE_H   = 18
        x_left   = 20

        bt = self.buf2.text
        favs = self.favorites
        for idx in range(start, min(start + visible, len(items))):
            item   = items[idx]
            is_sel = idx == selected
            color  = gc9a01.YELLOW if is_sel else gc9a01.WHITE
            cursor = ">" if is_sel else " "
            if isinstance(item, str):
                label = cursor + " " + self.shorten(item, 21)
            else:
                star       = "*" if item["id"] in favs else " "
                time_label = self.secs_to_hhmm(item["start"])
                prefix     = cursor + star + time_label + " "
                label = prefix + self.shorten(item["title"], 24 - len(prefix))
            bt(label[:24], x_left, y, color)
            y += LINE_H

    def draw_detail(self):
        talk = self.detail_talk
        self._use_buf2()
        self.buf.fill(gc9a01.BLACK)

        if not talk:
            self.small_center_text("-- Talk Detail --", y=20, color=gc9a01.CYAN)
            self.small_center_text("No talk selected.", y=110, color=gc9a01.RED)
            self._blit2()
            return

        self.small_center_text("-- Talk Detail --", y=18, color=gc9a01.CYAN)

        star    = "* " if talk["id"] in self.favorites else ""
        t_lines = self.wrap_text(star + talk["title"], max_chars=22, max_lines=3)
        ty = 64
        for line in t_lines:
            self.small_text(line, 20, ty, gc9a01.YELLOW if star else gc9a01.WHITE)
            ty += 10

        ty += 2

        self.small_text(self.fmt_range(talk["start"], talk["end"]), 20, ty, gc9a01.GREEN)
        ty += 10

        spk = self.shorten(talk.get("speaker", ""), 24)
        if spk:
            self.small_text(spk, 20, ty, gc9a01.WHITE)
            ty += 10

        self.small_text(self.shorten(talk["room"], 24), 20, ty, gc9a01.CYAN)
        ty += 10

        if self.conflict_msg:
            box_y = ty + 2
            self.buf2.fill_rect(18, box_y, 204, 34, 0xF800)
            lines = self.conflict_msg.split("\n")
            for li, ln in enumerate(lines[:3]):
                lx = max(20, (240 - len(ln) * 8) // 2)
                self.buf2.text(ln, lx, box_y + 3 + li * 11, gc9a01.WHITE)

        elif self.message:
            self.small_center_text(self.message, y=ty + 2, color=gc9a01.GREEN)

        ACTION_Y = 170
        ACTION_H = 12
        for i, action in enumerate(self.detail_actions):
            ay     = ACTION_Y + i * ACTION_H
            is_sel = (i == self.selected)
            col    = gc9a01.YELLOW if is_sel else gc9a01.WHITE
            prefix = "> " if is_sel else "  "
            self.small_text(prefix + action, 36, ay, col)

        self._blit2()

    def draw_help(self):
        self._use_buf2()
        self.buf.fill(gc9a01.BLACK)
        self.small_center_text("=== Help ===", y=22, color=gc9a01.CYAN)
        lines = [
            ("UP/DN: scroll",       gc9a01.WHITE),
            ("SEL: choose/enter",   gc9a01.WHITE),
            ("BTN7: back",          gc9a01.WHITE),
            ("SEL on detail=Back",  gc9a01.WHITE),
            ("* = Favorited",       gc9a01.YELLOW),
            ("Left = dashboard",    gc9a01.WHITE),
            ("Right = menus",       gc9a01.WHITE),
            ("What Next? = random", gc9a01.GREEN),
            ("task suggestion",     gc9a01.GREEN),
        ]
        y = 36
        for txt, col in lines:
            self.small_text(txt, 28, y, col)
            y += 18
        self._blit2()

    def draw_what_next(self):
        self._use_buf2()
        self.buf.fill(gc9a01.BLACK)

        suggestion = self.what_next_suggestion or "Press SEL for idea!"
        lines = self.wrap_text(suggestion, max_chars=22, max_lines=5)
        n_lines = len(lines)

        content_h = 8 + 6 + n_lines * 14 + 10 + 2 * 14
        y_start   = max(22, (240 - content_h) // 2)

        self.small_center_text("What Next?", y=y_start, color=gc9a01.CYAN)
        y = y_start + 16

        for line in lines:
            self.small_center_text(line, y=y, color=gc9a01.WHITE)
            y += 14

        y += 8
        options = ["New Suggestion", "Back"]
        for i, opt in enumerate(options):
            is_sel = (i == self.selected)
            col    = gc9a01.YELLOW if is_sel else gc9a01.WHITE
            prefix = "> " if is_sel else "  "
            self.small_center_text(prefix + opt, y=y, color=col)
            y += 14

        self._blit2()

    def draw_name_screen(self):
        self._use_buf2()
        self.buf.fill(gc9a01.BLACK)
        self.small_center_text("-- My Badge --", y=22, color=gc9a01.CYAN)
        name = "Xavier Roberts"
        lines = self.wrap_text(name, max_chars=14, max_lines=3)
        total_h = len(lines) * 28
        y = max(60, (240 - total_h) // 2)
        for line in lines:
            self.center_text(line, y=y, color=gc9a01.WHITE)
            y += 28
        self.small_center_text("Hold BTN7 to exit", y=210, color=gc9a01.WHITE)
        self._blit2()

    def small_text(self, text, x, y, color=gc9a01.WHITE):
        if text is None:
            return
        self.buf2.text(str(text), x, y, color)

    def small_center_text(self, text, y, color=gc9a01.WHITE):
        if text is None:
            return
        text   = str(text)
        text_w = len(text) * 8
        x      = max(28, (self.w - text_w) // 2)
        if x + text_w > 212:
            x = max(28, 212 - text_w)
        self.buf2.text(text, x, y, color)

if __name__ == "__main__":
    from single_app_runner import run_app
    run_app(App)
