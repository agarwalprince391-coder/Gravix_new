from kivy.app import App
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.utils import get_color_from_hex
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.progressbar import ProgressBar
from kivy.uix.popup import Popup
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.clock import Clock
import requests

FIREBASE_URL = "https://gravix-7b589-default-rtdb.asia-southeast1.firebasedatabase.app"

# ---------- THEME ----------
BG = "#0B0D10"
CARD = "#15191F"
CARD2 = "#1B2027"
TEXT = "#F5F7FA"
MUTED = "#9299A5"
ACCENT = "#E53935"
ACCENT_DARK = "#9F2523"
GREEN = "#31C48D"
LOCKED = "#292E36"
WHITE = "#FFFFFF"

Window.clearcolor = get_color_from_hex(BG)


def db_url(endpoint):
    return f"{FIREBASE_URL.rstrip('/')}/{endpoint}.json"


def rounded(widget, color=CARD, radius=18, border=False):
    with widget.canvas.before:
        Color(*get_color_from_hex(color))
        widget._bg = RoundedRectangle(pos=widget.pos, size=widget.size,
                                      radius=[dp(radius)])
        if border:
            Color(*get_color_from_hex("#2B313A"))
            widget._line = Line(rounded_rectangle=(
                widget.x, widget.y, widget.width, widget.height, dp(radius)
            ), width=1)
    widget.bind(pos=lambda *_: setattr(widget._bg, "pos", widget.pos))
    widget.bind(size=lambda *_: setattr(widget._bg, "size", widget.size))
    if border:
        widget.bind(pos=lambda *_: setattr(
            widget._line, "rounded_rectangle",
            (widget.x, widget.y, widget.width, widget.height, dp(radius))
        ))
        widget.bind(size=lambda *_: setattr(
            widget._line, "rounded_rectangle",
            (widget.x, widget.y, widget.width, widget.height, dp(radius))
        ))
    return widget


def label(text="", size=14, color=TEXT, bold=False, halign="left"):
    return Label(
        text=f"[b]{text}[/b]" if bold else text,
        markup=True,
        font_size=dp(size),
        color=get_color_from_hex(color),
        halign=halign,
        valign="middle",
        text_size=(None, None),
    )


def pill_button(text, callback=None, color=ACCENT, height=48):
    b = Button(
        text=text,
        size_hint_y=None,
        height=dp(height),
        background_normal="",
        background_color=get_color_from_hex(color),
        color=get_color_from_hex(WHITE),
        bold=True,
        font_size=dp(13),
    )
    if callback:
        b.bind(on_release=callback)
    return b


class Card(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        rounded(self, CARD, 18, True)
        self.padding = dp(16)


class LoginScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = BoxLayout(orientation="vertical", padding=[dp(28), dp(50), dp(28), dp(28)])
        root.spacing = dp(16)

        spacer = BoxLayout(size_hint_y=0.55)
        root.add_widget(spacer)

        logo = label("GRAVIX", 38, ACCENT, True, "center")
        logo.size_hint_y = None
        logo.height = dp(55)
        root.add_widget(logo)

        tagline = label("MASTER YOUR BODY.", 13, MUTED, True, "center")
        tagline.size_hint_y = None
        tagline.height = dp(28)
        root.add_widget(tagline)

        self.username = TextInput(
            hint_text="Username",
            multiline=False,
            size_hint_y=None,
            height=dp(52),
            background_normal="",
            background_active="",
            background_color=get_color_from_hex(CARD),
            foreground_color=get_color_from_hex(TEXT),
            hint_text_color=get_color_from_hex(MUTED),
            padding=[dp(16), dp(15)],
        )
        self.password = TextInput(
            hint_text="Password",
            password=True,
            multiline=False,
            size_hint_y=None,
            height=dp(52),
            background_normal="",
            background_active="",
            background_color=get_color_from_hex(CARD),
            foreground_color=get_color_from_hex(TEXT),
            hint_text_color=get_color_from_hex(MUTED),
            padding=[dp(16), dp(15)],
        )
        root.add_widget(self.username)
        root.add_widget(self.password)

        self.status = label("", 12, MUTED, False, "center")
        self.status.size_hint_y = None
        self.status.height = dp(28)
        root.add_widget(self.status)

        root.add_widget(pill_button("ENTER GRAVIX", self.login, ACCENT, 54))
        root.add_widget(pill_button("CREATE ACCOUNT", self.register, CARD2, 50))

        bottom = label("Train • Progress • Conquer", 11, MUTED, False, "center")
        bottom.size_hint_y = 0.4
        root.add_widget(bottom)

        self.add_widget(root)

    def login(self, *_):
        u, p = self.username.text.strip().lower(), self.password.text.strip()
        if not u or not p:
            self.status.text = "Enter your username and password."
            return
        try:
            data = requests.get(db_url(f"users/{u}"), timeout=10).json()
            if data and data.get("password") == p:
                App.get_running_app().current_user = u
                self.manager.current = "home"
            else:
                self.status.text = "Invalid username or password."
        except Exception:
            self.status.text = "Cloud connection failed."

    def register(self, *_):
        u, p = self.username.text.strip().lower(), self.password.text.strip()
        if not u or not p:
            self.status.text = "Username and password cannot be empty."
            return
        try:
            if requests.get(db_url(f"users/{u}"), timeout=10).json() is not None:
                self.status.text = "Username already exists."
                return
            user = {"username": u, "password": p, "level": 0, "xp": 0}
            requests.put(db_url(f"users/{u}"), json=user, timeout=10)
            App.get_running_app().current_user = u
            self.manager.current = "home"
        except Exception:
            self.status.text = "Registration failed."


class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.level = 0
        self.xp = 0
        self.skills = []

        root = BoxLayout(orientation="vertical")
        root.padding = [dp(18), dp(25), dp(18), dp(0)]

        scroll = ScrollView(do_scroll_x=False)
        content = BoxLayout(orientation="vertical", spacing=dp(14), size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))

        header = BoxLayout(size_hint_y=None, height=dp(55))
        self.greeting = label("WELCOME", 12, MUTED, True)
        self.greeting.size_hint_x = 0.72
        header.add_widget(self.greeting)
        logout = pill_button("LOG OUT", self.logout, CARD2, 38)
        logout.size_hint_x = 0.28
        header.add_widget(logout)
        content.add_widget(header)

        hero = Card(orientation="vertical", size_hint_y=None, height=dp(150), spacing=dp(4))
        top = BoxLayout(size_hint_y=None, height=dp(35))
        self.level_label = label("LEVEL 0", 22, TEXT, True)
        top.add_widget(self.level_label)
        self.xp_label = label("0 XP", 12, MUTED, True, "right")
        top.add_widget(self.xp_label)
        hero.add_widget(top)

        self.xp_bar = ProgressBar(max=100, value=0, size_hint_y=None, height=dp(8))
        hero.add_widget(self.xp_bar)

        hero.add_widget(label("KEEP GRINDING. EVERY REP COUNTS.", 11, MUTED, True))
        content.add_widget(hero)

        mission = Card(orientation="vertical", size_hint_y=None, height=dp(135), spacing=dp(8))
        mission.add_widget(label("TODAY'S MISSION", 11, ACCENT, True))
        mission.add_widget(label("BUILD YOUR BASE", 22, TEXT, True))
        mission.add_widget(label("Complete a skill session and earn XP.", 12, MUTED))
        mission.add_widget(pill_button("VIEW SKILLS", self.go_skills, ACCENT, 42))
        content.add_widget(mission)

        content.add_widget(label("YOUR SKILLS", 16, TEXT, True))

        self.skills_box = GridLayout(cols=2, spacing=dp(10), size_hint_y=None)
        self.skills_box.bind(minimum_height=self.skills_box.setter("height"))
        content.add_widget(self.skills_box)

        root.add_widget(scroll)
        root.add_widget(self.bottom_nav())
        self.add_widget(root)

    def bottom_nav(self):
        nav = BoxLayout(size_hint_y=None, height=dp(68), spacing=dp(8), padding=[0, dp(8), 0, dp(8)])
        nav.add_widget(pill_button("HOME", lambda *_: None, ACCENT, 50))
        nav.add_widget(pill_button("SKILLS", self.go_skills, CARD2, 50))
        nav.add_widget(pill_button("PROFILE", self.go_profile, CARD2, 50))
        return nav

    def on_enter(self):
        Clock.schedule_once(lambda *_: self.refresh(), 0.1)

    def refresh(self):
        app = App.get_running_app()
        self.username = getattr(app, "current_user", "")
        self.greeting.text = f"HELLO, {self.username.upper()}"
        self.load_profile()
        self.load_skills()

    def load_profile(self):
        try:
            user = requests.get(db_url(f"users/{self.username}"), timeout=10).json() or {}
            self.level = int(user.get("level", 0))
            self.xp = int(user.get("xp", 0))
            need = 100 + self.level * 50
            self.level_label.text = f"LEVEL {self.level}"
            self.xp_label.text = f"{self.xp} / {need} XP"
            self.xp_bar.max = need
            self.xp_bar.value = self.xp
        except Exception:
            pass

    def load_skills(self):
        self.skills_box.clear_widgets()
        try:
            data = requests.get(db_url("skills"), timeout=10).json() or {}
            self.skills = list(data.values())
            if not self.skills:
                self.add_empty_skills()
                return
            for s in self.skills[:8]:
                name = s.get("skill_name", "Skill")
                diff = s.get("difficulty", "C")
                req = int(s.get("required_level", 0))
                unlocked = self.level >= req
                card = Button(
                    text=f"[b]{name.upper()}[/b]\n\n{'UNLOCKED • ' + str(diff) if unlocked else 'LOCKED • LVL ' + str(req)}",
                    markup=True,
                    size_hint_y=None,
                    height=dp(105),
                    background_normal="",
                    background_color=get_color_from_hex(ACCENT if unlocked else LOCKED),
                    color=get_color_from_hex(TEXT),
                    font_size=dp(12),
                    halign="center",
                )
                card.bind(on_release=lambda _, n=name, r=req, d=diff: self.skill_popup(n, r, d))
                self.skills_box.add_widget(card)
        except Exception:
            self.add_empty_skills()

    def add_empty_skills(self):
        self.skills_box.add_widget(label("No skills found yet.\nAdd some from the Skills screen.", 12, MUTED, False, "center"))

    def skill_popup(self, name, req, difficulty):
        if self.level < req:
            msg = f"{name}\n\nUnlock this skill at Level {req}."
            self.show_popup("SKILL LOCKED", msg, [("CLOSE", None)])
            return
        xp = {"S": 500, "A": 250, "B": 100, "C": 50}.get(str(difficulty).upper()[:1], 50)
        self.show_popup(
            name.upper(),
            f"{difficulty} TIER\n\nTrain this skill to earn XP.\n\nREWARD   +{xp} XP",
            [("COMPLETE +XP", lambda *_: self.grant_xp(xp)), ("CLOSE", None)]
        )

    def grant_xp(self, amount):
        old = self.level
        self.xp += amount
        while self.xp >= 100 + self.level * 50:
            self.xp -= 100 + self.level * 50
            self.level += 1
        try:
            requests.patch(db_url(f"users/{self.username}"),
                            json={"level": self.level, "xp": self.xp}, timeout=10)
        except Exception:
            pass
        if hasattr(self, "popup") and self.popup:
            self.popup.dismiss()
        self.refresh()
        if self.level > old:
            self.show_popup("LEVEL UP", f"YOU REACHED LEVEL {self.level}!", [("CONTINUE", None)])

    def show_popup(self, title, message, buttons):
        box = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(10))
        box.add_widget(label(message, 15, TEXT, False, "center"))
        for text, callback in buttons:
            b = pill_button(text, callback, ACCENT if callback else CARD2, 46)
            box.add_widget(b)
        self.popup = Popup(title=title, content=box, size_hint=(0.84, 0.48),
                           background_color=get_color_from_hex(CARD))
        for child in box.children:
            if isinstance(child, Button) and child.text == "CLOSE":
                child.bind(on_release=self.popup.dismiss)
        self.popup.open()

    def go_skills(self, *_):
        self.manager.current = "skills"

    def go_profile(self, *_):
        self.manager.current = "profile"

    def logout(self, *_):
        App.get_running_app().current_user = None
        self.manager.current = "login"


class SkillsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical", padding=[dp(18), dp(25), dp(18), 0], spacing=dp(12))

        head = BoxLayout(size_hint_y=None, height=dp(50))
        head.add_widget(label("SKILL TREE", 25, TEXT, True))
        back = pill_button("HOME", lambda *_: setattr(self.manager, "current", "home"), CARD2, 40)
        head.add_widget(back)
        root.add_widget(head)

        scroll = ScrollView(do_scroll_x=False)
        self.grid = GridLayout(cols=1, spacing=dp(10), size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter("height"))
        scroll.add_widget(self.grid)
        root.add_widget(scroll)

        add = pill_button("+ ADD SKILL", self.add_skill, ACCENT, 50)
        root.add_widget(add)
        self.add_widget(root)

    def on_enter(self):
        Clock.schedule_once(lambda *_: self.refresh(), 0.1)

    def refresh(self):
        self.grid.clear_widgets()
        user = getattr(App.get_running_app(), "current_user", "")
        try:
            level = int((requests.get(db_url(f"users/{user}"), timeout=10).json() or {}).get("level", 0))
            data = requests.get(db_url("skills"), timeout=10).json() or {}
            for s in data.values():
                name = s.get("skill_name", "Skill")
                diff = s.get("difficulty", "C")
                req = int(s.get("required_level", 0))
                unlocked = level >= req
                row = Card(size_hint_y=None, height=dp(86), orientation="horizontal", spacing=dp(12))
                info = BoxLayout(orientation="vertical")
                info.add_widget(label(name.upper(), 16, TEXT, True))
                info.add_widget(label(
                    f"{diff} TIER  •  " + ("READY TO TRAIN" if unlocked else f"UNLOCKS AT LEVEL {req}"),
                    11, GREEN if unlocked else MUTED, True
                ))
                row.add_widget(info)
                action = pill_button("TRAIN" if unlocked else "LOCKED", None, ACCENT if unlocked else LOCKED, 42)
                if unlocked:
                    action.bind(on_release=lambda _, n=name, d=diff: self.train(n, d))
                row.add_widget(action)
                self.grid.add_widget(row)
        except Exception:
            self.grid.add_widget(label("Could not load skills.", 13, MUTED, False, "center"))

    def train(self, name, diff):
        xp = {"S": 500, "A": 250, "B": 100, "C": 50}.get(str(diff).upper()[:1], 50)
        box = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(12))
        box.add_widget(label(f"{name.upper()}\n\nSESSION READY\n\nReward: +{xp} XP", 16, TEXT, True, "center"))
        complete = pill_button("COMPLETE SESSION", None, ACCENT, 50)
        close = pill_button("CANCEL", None, CARD2, 45)
        box.add_widget(complete)
        box.add_widget(close)
        pop = Popup(title="TRAIN", content=box, size_hint=(0.84, 0.48))
        close.bind(on_release=pop.dismiss)

        def done(*_):
            username = App.get_running_app().current_user
            try:
                user = requests.get(db_url(f"users/{username}"), timeout=10).json() or {}
                level, cur = int(user.get("level", 0)), int(user.get("xp", 0))
                cur += xp
                while cur >= 100 + level * 50:
                    cur -= 100 + level * 50
                    level += 1
                requests.patch(db_url(f"users/{username}"), json={"level": level, "xp": cur}, timeout=10)
            except Exception:
                pass
            pop.dismiss()
            self.manager.current = "home"

        complete.bind(on_release=done)
        pop.open()

    def add_skill(self, *_):
        self.manager.current = "add_skill"


class AddSkillScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical", padding=[dp(25), dp(30), dp(25), dp(20)], spacing=dp(12))
        root.add_widget(label("ADD SKILL", 26, TEXT, True))
        root.add_widget(label("Expand the GRAVIX skill tree.", 12, MUTED))

        self.name = TextInput(hint_text="Skill name", multiline=False, size_hint_y=None, height=dp(52),
                              background_normal="", background_color=get_color_from_hex(CARD),
                              foreground_color=get_color_from_hex(TEXT), hint_text_color=get_color_from_hex(MUTED))
        self.diff = TextInput(hint_text="Difficulty: S / A / B / C", multiline=False, size_hint_y=None, height=dp(52),
                              background_normal="", background_color=get_color_from_hex(CARD),
                              foreground_color=get_color_from_hex(TEXT), hint_text_color=get_color_from_hex(MUTED))
        self.req = TextInput(hint_text="Required level", multiline=False, input_filter="int",
                             size_hint_y=None, height=dp(52),
                             background_normal="", background_color=get_color_from_hex(CARD),
                             foreground_color=get_color_from_hex(TEXT), hint_text_color=get_color_from_hex(MUTED))
        root.add_widget(self.name)
        root.add_widget(self.diff)
        root.add_widget(self.req)

        self.status = label("", 12, MUTED)
        root.add_widget(self.status)
        root.add_widget(pill_button("SAVE TO CLOUD", self.save, ACCENT, 52))
        root.add_widget(pill_button("BACK", lambda *_: setattr(self.manager, "current", "skills"), CARD2, 48))
        root.add_widget(BoxLayout())
        self.add_widget(root)

    def save(self, *_):
        if not self.name.text.strip() or not self.req.text.strip():
            self.status.text = "Name and required level are required."
            return
        try:
            payload = {
                "skill_name": self.name.text.strip(),
                "difficulty": self.diff.text.strip().upper() or "C",
                "required_level": int(self.req.text),
            }
            requests.post(db_url("skills"), json=payload, timeout=10)
            self.name.text = self.diff.text = self.req.text = ""
            self.manager.current = "skills"
        except Exception:
            self.status.text = "Could not save skill."


class ProfileScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical", padding=[dp(18), dp(25), dp(18), dp(15)], spacing=dp(14))
        head = BoxLayout(size_hint_y=None, height=dp(50))
        head.add_widget(label("PROFILE", 25, TEXT, True))
        head.add_widget(pill_button("HOME", lambda *_: setattr(self.manager, "current", "home"), CARD2, 40))
        root.add_widget(head)

        self.card = Card(orientation="vertical", size_hint_y=None, height=dp(210), spacing=dp(8))
        self.card.add_widget(label("PLAYER", 11, MUTED, True))
        self.user_label = label("PLAYER", 28, TEXT, True)
        self.card.add_widget(self.user_label)
        self.stats = label("LEVEL 0\n0 XP", 15, MUTED)
        self.card.add_widget(self.stats)
        root.add_widget(self.card)
        root.add_widget(label("GRAVIX", 34, ACCENT, True, "center"))
        root.add_widget(label("TRAIN HARD. MOVE BETTER. BECOME MORE.", 11, MUTED, True, "center"))
        root.add_widget(BoxLayout())
        self.add_widget(root)

    def on_enter(self):
        user = getattr(App.get_running_app(), "current_user", "")
        self.user_label.text = user.upper()
        try:
            d = requests.get(db_url(f"users/{user}"), timeout=10).json() or {}
            self.stats.text = f"LEVEL {d.get('level', 0)}\n{d.get('xp', 0)} XP"
        except Exception:
            pass


class GravixApp(App):
    def build(self):
        self.title = "GRAVIX"
        self.current_user = None
        sm = ScreenManager()
        sm.add_widget(LoginScreen(name="login"))
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(SkillsScreen(name="skills"))
        sm.add_widget(AddSkillScreen(name="add_skill"))
        sm.add_widget(ProfileScreen(name="profile"))
        return sm


if __name__ == "__main__":
    GravixApp().run()
