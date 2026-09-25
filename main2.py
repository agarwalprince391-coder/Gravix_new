from kivy.resources import resource_find
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
from kivy.uix.image import Image
from kivy.uix.progressbar import ProgressBar
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.uix.widget import Widget
import requests
import datetime
import time

FIREBASE_URL = "https://gravix-7b589-default-rtdb.asia-southeast1.firebasedatabase.app"

# ---------------- THEME ----------------
BG = "#0B0D10"
CARD = "#15191F"
CARD2 = "#1B2027"
TEXT = "#F5F7FA"
MUTED = "#9299A5"
ACCENT = "#E53935"
GREEN = "#31C48D"
GOLD = "#F2C94C"
LOCKED = "#292E36"
WHITE = "#FFFFFF"

Window.clearcolor = get_color_from_hex(BG)


def db_url(endpoint):
    return f"{FIREBASE_URL.rstrip('/')}/{endpoint}.json"


def now_key():
    return datetime.datetime.now().strftime("%Y-%m-%d")


def safe_get(endpoint, default=None):
    try:
        r = requests.get(db_url(endpoint), timeout=8)
        if r.ok:
            return r.json() if r.json() is not None else default
    except Exception:
        pass
    return default


def safe_patch(endpoint, payload):
    try:
        return requests.patch(db_url(endpoint), json=payload, timeout=8).ok
    except Exception:
        return False


def safe_put(endpoint, payload):
    try:
        return requests.put(db_url(endpoint), json=payload, timeout=8).ok
    except Exception:
        return False


def safe_post(endpoint, payload):
    try:
        r = requests.post(db_url(endpoint), json=payload, timeout=8)
        return r.ok
    except Exception:
        return False


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
            (widget.x, widget.y, widget.width, widget.height, dp(radius))))
        widget.bind(size=lambda *_: setattr(
            widget._line, "rounded_rectangle",
            (widget.x, widget.y, widget.width, widget.height, dp(radius))))
    return widget


def label(text="", size=14, color=TEXT, bold=False, halign="left"):
    x = Label(
        text=f"[b]{text}[/b]" if bold else text,
        markup=True,
        font_size=dp(size),
        color=get_color_from_hex(color),
        halign=halign,
        valign="middle",
    )
    x.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0], None)))
    return x


def pill_button(text, callback=None, color=ACCENT, height=48):
    b = Button(
        text=text,
        size_hint_y=None,
        height=dp(height),
        background_normal="",
        background_color=get_color_from_hex(color),
        color=get_color_from_hex(WHITE),
        bold=True,
        font_size=dp(12),
    )
    if callback:
        b.bind(on_release=callback)
    return b


class Card(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        rounded(self, CARD, 18, True)
        self.padding = dp(14)


class BaseScreen(Screen):
    def nav(self, active="HOME"):
        nav = BoxLayout(size_hint_y=None, height=dp(68), spacing=dp(7),
                        padding=[0, dp(8), 0, dp(8)])
        for name, screen in [
            ("HOME", "home"), ("SKILLS", "skills"), ("PROFILE", "profile")
        ]:
            nav.add_widget(pill_button(
                name, lambda _, s=screen: setattr(self.manager, "current", s),
                ACCENT if name == active else CARD2, 50))
        return nav

    def popup(self, title, message, action_text="CLOSE", callback=None):
        box = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(12))
        box.add_widget(label(message, 14, TEXT, False, "center"))
        b = pill_button(action_text, callback, ACCENT, 46)
        box.add_widget(b)
        pop = Popup(title=title, content=box, size_hint=(.88, .55),
                    background_color=get_color_from_hex(CARD))
        if callback is None:
            b.bind(on_release=pop.dismiss)
        self._popup = pop
        pop.open()


class LoginScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        try:
            bg_path = resource_find("assets.gravix/Baki_bg.png")
            if bg_path:
                bg = Image(source=bg_path, allow_stretch=True, keep_ratio=False)
                self.add_widget(bg)
        except Exception:
            pass

        root = BoxLayout(orientation="vertical",
                         padding=[dp(28), dp(50), dp(28), dp(28)],
                         spacing=dp(14))
        root.add_widget(BoxLayout(size_hint_y=.22))
        root.add_widget(label("GRAVIX", 38, ACCENT, True, "center"))
        root.add_widget(label("MASTER YOUR BODY.", 13, MUTED, True, "center"))

        self.username = TextInput(hint_text="Username", multiline=False,
            size_hint_y=None, height=dp(52), background_normal="",
            background_color=get_color_from_hex(CARD),
            foreground_color=get_color_from_hex(TEXT),
            hint_text_color=get_color_from_hex(MUTED), padding=[dp(16), dp(15)])
        self.password = TextInput(hint_text="Password", password=True,
            multiline=False, size_hint_y=None, height=dp(52), background_normal="",
            background_color=get_color_from_hex(CARD),
            foreground_color=get_color_from_hex(TEXT),
            hint_text_color=get_color_from_hex(MUTED), padding=[dp(16), dp(15)])
        root.add_widget(self.username)
        root.add_widget(self.password)
        self.status = label("", 12, MUTED, False, "center")
        root.add_widget(self.status)
        root.add_widget(pill_button("ENTER GRAVIX", self.login, ACCENT, 54))
        root.add_widget(pill_button("CREATE ACCOUNT", self.register, CARD2, 50))
        root.add_widget(label("TRAIN • PROGRESS • COMPETE • CONQUER",
                              10, MUTED, True, "center"))
        self.add_widget(root)

    def login(self, *_):
        u, p = self.username.text.strip().lower(), self.password.text.strip()
        if not u or not p:
            self.status.text = "Enter your username and password."
            return
        data = safe_get(f"users/{u}", {})
        if data and data.get("password") == p:
            App.get_running_app().current_user = u
            self.manager.current = "home"
        else:
            self.status.text = "Invalid username or password."

    def register(self, *_):
        u, p = self.username.text.strip().lower(), self.password.text.strip()
        if not u or not p:
            self.status.text = "Username and password cannot be empty."
            return
        if safe_get(f"users/{u}"):
            self.status.text = "Username already exists."
            return
        user = {
            "username": u, "password": p, "level": 0, "xp": 0,
            "streak": 0, "workout_minutes": 0, "skill_minutes": 0,
            "calories": 0, "steps": 0, "completed_workouts": 0,
            "achievements": 0, "bodyweight": "", "height": "",
            "body_type": "Not set", "goal": "Build strength"
        }
        if safe_put(f"users/{u}", user):
            App.get_running_app().current_user = u
            self.manager.current = "home"
        else:
            self.status.text = "Registration failed."


class HomeScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical")
        root.padding = [dp(16), dp(20), dp(16), 0]

        scroll = ScrollView(do_scroll_x=False)
        self.content = BoxLayout(orientation="vertical", spacing=dp(12),
                                 size_hint_y=None)
        self.content.bind(minimum_height=self.content.setter("height"))

        header = BoxLayout(size_hint_y=None, height=dp(54))
        self.greeting = label("WELCOME", 14, MUTED, True)
        header.add_widget(self.greeting)
        header.add_widget(pill_button("LOG OUT", self.logout, CARD2, 38))
        self.content.add_widget(header)

        hero = Card(orientation="vertical", size_hint_y=None, height=dp(145),
                    spacing=dp(6))
        row = BoxLayout(size_hint_y=None, height=dp(34))
        self.level_label = label("LEVEL 0", 22, TEXT, True)
        self.xp_label = label("0 XP", 11, MUTED, True, "right")
        row.add_widget(self.level_label)
        row.add_widget(self.xp_label)
        hero.add_widget(row)
        self.xp_bar = ProgressBar(max=100, value=0, size_hint_y=None, height=dp(8))
        hero.add_widget(self.xp_bar)
        self.hero_text = label("START YOUR GRAVIX JOURNEY.", 11, MUTED, True)
        hero.add_widget(self.hero_text)
        self.content.add_widget(hero)

        mission = Card(orientation="vertical", size_hint_y=None, height=dp(140),
                       spacing=dp(6))
        mission.add_widget(label("TODAY'S MISSION", 11, ACCENT, True))
        self.mission_title = label("BUILD YOUR BASE", 21, TEXT, True)
        mission.add_widget(self.mission_title)
        self.mission_desc = label("Train a skill from your GRAVIX program.", 11, MUTED)
        mission.add_widget(self.mission_desc)
        mission.add_widget(pill_button("OPEN SKILLS", self.go_skills, ACCENT, 40))
        self.content.add_widget(mission)

        self.quick = GridLayout(cols=2, spacing=dp(9), size_hint_y=None,
                                row_default_height=dp(92))
        self.quick.bind(minimum_height=self.quick.setter("height"))
        self.content.add_widget(self.quick)

        self.content.add_widget(label("YOUR TRAINING TODAY", 15, TEXT, True))
        self.today_card = Card(orientation="vertical", size_hint_y=None,
                               height=dp(145), spacing=dp(7))
        self.today_stats = label("0 min • 0 steps • 0 kcal", 13, TEXT, True)
        self.today_card.add_widget(self.today_stats)
        self.today_card.add_widget(
            pill_button("MARK WORKOUT COMPLETE", self.complete_workout, GREEN, 42))
        self.today_card.add_widget(
            pill_button("LOG ACTIVITY", self.log_activity, CARD2, 42))
        self.content.add_widget(self.today_card)

        self.content.add_widget(label("WEEKLY CHALLENGES", 15, TEXT, True))
        challenge = Card(orientation="vertical", size_hint_y=None, height=dp(120),
                         spacing=dp(6))
        challenge.add_widget(label("GLOBAL MISSION • PUSH / PULL / SKILL",
                                   12, GOLD, True))
        challenge.add_widget(label(
            "Train, record your result and build your world ranking.",
            11, MUTED))
        challenge.add_widget(pill_button("VIEW CHALLENGES", self.challenges,
                                         ACCENT, 40))
        self.content.add_widget(challenge)

        self.content.add_widget(label("GRAVIX ECOSYSTEM", 15, TEXT, True))
        eco = GridLayout(cols=2, spacing=dp(9), size_hint_y=None)
        eco.bind(minimum_height=eco.setter("height"))
        for text, cb in [
            ("🥗 NUTRITION", self.nutrition),
            ("🏆 COMPETE", self.challenges),
            ("🧑‍🏫 ATHLETES", self.athletes),
            ("📍 ACADEMIES", self.academies),
            ("🛒 FITNESS STORE", self.store),
            ("✨ GLOW UP", self.glowup),
        ]:
            eco.add_widget(pill_button(text, cb, CARD2, 54))
        self.content.add_widget(eco)

        scroll.add_widget(self.content)
        root.add_widget(scroll)
        root.add_widget(self.nav("HOME"))
        self.add_widget(root)

    def on_enter(self):
        Clock.schedule_once(lambda *_: self.refresh(), .1)

    def refresh(self):
        u = getattr(App.get_running_app(), "current_user", "")
        self.greeting.text = f"HELLO, {u.upper()}"
        d = safe_get(f"users/{u}", {}) or {}
        level, xp = int(d.get("level", 0)), int(d.get("xp", 0))
        need = 100 + level * 50
        self.level_label.text = f"LEVEL {level}"
        self.xp_label.text = f"{xp} / {need} XP"
        self.xp_bar.max, self.xp_bar.value = need, xp
        self.today_stats.text = (
            f"{d.get('workout_minutes', 0)} min • "
            f"{d.get('steps', 0)} steps • {d.get('calories', 0)} kcal"
        )
        self.hero_text.text = (
            f"STREAK {d.get('streak', 0)} DAYS • "
            f"{d.get('completed_workouts', 0)} WORKOUTS COMPLETED"
        )
        self.quick.clear_widgets()
        for title, value in [
            ("SKILLS", len(safe_get("skills", {}) or {})),
            ("ACHIEVEMENTS", d.get("achievements", 0)),
            ("SKILL TIME", f"{d.get('skill_minutes', 0)}m"),
            ("RANK POINTS", d.get("rank_points", 0)),
        ]:
            c = Card(orientation="vertical", size_hint_y=None, height=dp(86),
                     spacing=dp(3))
            c.add_widget(label(title, 9, MUTED, True))
            c.add_widget(label(str(value), 21, TEXT, True))
            self.quick.add_widget(c)

    def complete_workout(self, *_):
        u = App.get_running_app().current_user
        d = safe_get(f"users/{u}", {}) or {}
        d["completed_workouts"] = int(d.get("completed_workouts", 0)) + 1
        d["streak"] = int(d.get("streak", 0)) + 1
        d["workout_minutes"] = int(d.get("workout_minutes", 0)) + 30
        d["rank_points"] = int(d.get("rank_points", 0)) + 25
        self.add_xp(50, d)
        safe_patch(f"users/{u}", d)
        self.refresh()
        self.popup("WORKOUT COMPLETE", "+50 XP • +25 RANK POINTS\nToday's session is recorded.")

    def add_xp(self, amount, d):
        level, xp = int(d.get("level", 0)), int(d.get("xp", 0)) + amount
        while xp >= 100 + level * 50:
            xp -= 100 + level * 50
            level += 1
        d["level"], d["xp"] = level, xp

    def log_activity(self, *_):
        u = App.get_running_app().current_user
        d = safe_get(f"users/{u}", {}) or {}
        d["steps"] = int(d.get("steps", 0)) + 1000
        d["calories"] = int(d.get("calories", 0)) + 100
        d["skill_minutes"] = int(d.get("skill_minutes", 0)) + 10
        safe_patch(f"users/{u}", d)
        self.refresh()
        self.popup("ACTIVITY LOGGED", "+1,000 steps • +100 kcal • +10 skill minutes")

    def challenges(self, *_): self.popup("GLOBAL CHALLENGES",
        "WEEKLY MISSIONS\n\n• PUSH-UP CHALLENGE\n• PULL-UP CHALLENGE\n• SKILL PROGRESSION\n\nFuture backend can record submissions, AI verification and global rankings.")
    def nutrition(self, *_): self.popup("GRAVIX NUTRITION",
        "FREE PLANS\n• Daily calories\n• Protein & carbs\n• Practical meal plans\n\nPRO PLANS\n• Weight-gain plan\n• Weight-loss plan\n• Personalized targets")
    def athletes(self, *_): self.popup("ATHLETE HUB",
        "ATHLETES CAN\n• Publish programs\n• Host live Q&A\n• Sell 1:1 sessions\n• Sell premium 1/3/6-month programs\n• Earn from their content\n\nGRAVIX can take a platform fee from transactions.")
    def academies(self, *_): self.popup("GRAVIX CENTRE",
        "ACADEMY DISCOVERY\n\nUsers can share location and discover nearby calisthenics academies. Academy joining/referral tracking can later connect to a commission system.")
    def store(self, *_): self.popup("FITNESS STORE",
        "Shoes • Compression • Calisthenics equipment • Accessories\n\nAffiliate products and GRAVIX marketplace inventory can be connected to this hub.")
    def glowup(self, *_): self.popup("GLOW UP",
        "STRUCTURED MODULES\n• Skincare basics\n• Grooming\n• Presentation\n• Lifestyle habits\n\nThis section can later become its own guided program.")
    def go_skills(self, *_): self.manager.current = "skills"
    def logout(self, *_):
        App.get_running_app().current_user = None
        self.manager.current = "login"


class SkillsScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical",
                         padding=[dp(16), dp(20), dp(16), 0], spacing=dp(10))
        head = BoxLayout(size_hint_y=None, height=dp(48))
        head.add_widget(label("GRAVIX SKILLS", 24, TEXT, True))
        root.add_widget(head)

        root.add_widget(label(
            "Skills are controlled by the GRAVIX backend. Users train and progress — they do not create the skill tree.",
            10, MUTED))

        scroll = ScrollView(do_scroll_x=False)
        self.grid = GridLayout(cols=1, spacing=dp(10), size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter("height"))
        scroll.add_widget(self.grid)
        root.add_widget(scroll)
        root.add_widget(self.nav("SKILLS"))
        self.add_widget(root)

    def on_enter(self):
        Clock.schedule_once(lambda *_: self.refresh(), .1)

    def refresh(self):
        self.grid.clear_widgets()
        user = App.get_running_app().current_user
        u = safe_get(f"users/{user}", {}) or {}
        level = int(u.get("level", 0))
        data = safe_get("skills", {}) or {}
        if not data:
            self.grid.add_widget(label("No backend skills have been configured yet.", 13,
                                       MUTED, False, "center"))
            return

        for sid, s in data.items():
            name = s.get("skill_name", "Skill")
            diff = s.get("difficulty", "C")
            req = int(s.get("required_level", 0))
            unlocked = level >= req
            progression = s.get("progression", [
                "Foundation", "Technique", "Control", "Consistency", "Mastery"
            ])
            progress = int(s.get("progress", 0))
            row = Card(orientation="vertical", size_hint_y=None, height=dp(155),
                       spacing=dp(6))
            top = BoxLayout(size_hint_y=None, height=dp(35))
            top.add_widget(label(name.upper(), 16, TEXT, True))
            top.add_widget(label(
                f"{diff} • {progress}%", 11,
                GREEN if unlocked else MUTED, True, "right"))
            row.add_widget(top)
            row.add_widget(label(
                f"{'UNLOCKED' if unlocked else 'LOCKED • LEVEL ' + str(req)} • "
                f"{len(progression)} progression steps", 10,
                GREEN if unlocked else MUTED, True))
            pb = ProgressBar(max=100, value=progress, size_hint_y=None, height=dp(7))
            row.add_widget(pb)
            action = pill_button("VIEW PROGRESSION" if unlocked else "LOCKED",
                                 None, ACCENT if unlocked else LOCKED, 38)
            if unlocked:
                action.bind(on_release=lambda _, sid=sid, s=dict(s):
                            self.show_skill(sid, s))
            row.add_widget(action)
            self.grid.add_widget(row)

    def show_skill(self, sid, s):
        name = s.get("skill_name", "Skill")
        steps = s.get("progression", [
            "Foundation", "Technique", "Control", "Consistency", "Mastery"
        ])
        muscles = s.get("target_muscles", "Full-body / skill specific")
        text = f"{name.upper()}\n\nTARGET MUSCLES\n{muscles}\n\nPROGRESSION\n"
        text += "\n".join(
            f"{i+1}. {step} — {round((i+1) * 100 / len(steps))}%"
            for i, step in enumerate(steps)
        )
        text += "\n\nRecord a final-step video in the future for AI form, speed and accuracy analysis."
        self.popup("SKILL PROGRESSION", text, "LOG PRACTICE",
                   lambda *_: self.log_practice(sid, s))

    def log_practice(self, sid, s):
        u = App.get_running_app().current_user
        d = safe_get(f"users/{u}", {}) or {}
        d["skill_minutes"] = int(d.get("skill_minutes", 0)) + 15
        d["rank_points"] = int(d.get("rank_points", 0)) + 10
        safe_patch(f"users/{u}", d)
        self.popup("PRACTICE RECORDED",
                   "+15 skill minutes • +10 rank points\nYour GRAVIX history has been updated.")


class ProfileScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical")
        scroll = ScrollView(do_scroll_x=False)
        self.body = BoxLayout(orientation="vertical", spacing=dp(10),
                              padding=[dp(16), dp(20), dp(16), dp(10)],
                              size_hint_y=None)
        self.body.bind(minimum_height=self.body.setter("height"))

        self.profile_card = Card(orientation="vertical", size_hint_y=None,
                                 height=dp(235), spacing=dp(7))
        self.body.add_widget(self.profile_card)

        self.body.add_widget(label("COMPLETE GRAVIX RECORD", 15, TEXT, True))
        self.record_grid = GridLayout(cols=2, spacing=dp(8), size_hint_y=None)
        self.record_grid.bind(minimum_height=self.record_grid.setter("height"))
        self.body.add_widget(self.record_grid)

        self.body.add_widget(label("ACHIEVEMENTS", 15, TEXT, True))
        self.achievements = Card(orientation="vertical", size_hint_y=None,
                                 height=dp(115), spacing=dp(6))
        self.body.add_widget(self.achievements)

        self.body.add_widget(label("CALENDAR / CONSISTENCY", 15, TEXT, True))
        self.calendar = Card(orientation="vertical", size_hint_y=None,
                             height=dp(115), spacing=dp(5))
        self.body.add_widget(self.calendar)

        self.body.add_widget(label("ATHLETE & CREATOR OPTIONS", 15, TEXT, True))
        creator = GridLayout(cols=2, spacing=dp(8), size_hint_y=None)
        creator.bind(minimum_height=creator.setter("height"))
        for t in ["MY PROGRAMS", "MY SKILL VIDEOS", "1:1 SESSIONS", "EARNINGS"]:
            creator.add_widget(pill_button(t, self.creator_info, CARD2, 48))
        self.body.add_widget(creator)

        edit = pill_button("EDIT BODY / GOAL PROFILE", self.edit_profile, ACCENT, 48)
        self.body.add_widget(edit)

        scroll.add_widget(self.body)
        root.add_widget(scroll)
        root.add_widget(self.nav("PROFILE"))
        self.add_widget(root)

    def on_enter(self):
        Clock.schedule_once(lambda *_: self.refresh(), .1)

    def refresh(self):
        self.profile_card.clear_widgets()
        self.record_grid.clear_widgets()
        self.achievements.clear_widgets()
        self.calendar.clear_widgets()

        u = App.get_running_app().current_user
        d = safe_get(f"users/{u}", {}) or {}

        # Profile identity
        self.profile_card.add_widget(label("GRAVIX ATHLETE", 10, ACCENT, True))
        self.profile_card.add_widget(label(
            f"{u.upper()}  •  LEVEL {d.get('level', 0)}", 24, TEXT, True))
        self.profile_card.add_widget(label(
            f"GOAL: {d.get('goal', 'Not set')}\n"
            f"BODYWEIGHT: {d.get('bodyweight', 'Not set')}   "
            f"HEIGHT: {d.get('height', 'Not set')}\n"
            f"BODY TYPE: {d.get('body_type', 'Not set')}", 11, MUTED))
        self.profile_card.add_widget(label(
            "Avatar/photo slot • personal details • complete training history",
            10, MUTED))

        records = [
            ("LEVEL", d.get("level", 0)), ("XP", d.get("xp", 0)),
            ("WORKOUTS", d.get("completed_workouts", 0)),
            ("STREAK", d.get("streak", 0)),
            ("SKILL TIME", f"{d.get('skill_minutes', 0)} min"),
            ("WORKOUT TIME", f"{d.get('workout_minutes', 0)} min"),
            ("STEPS", d.get("steps", 0)), ("CALORIES", d.get("calories", 0)),
            ("RANK POINTS", d.get("rank_points", 0)),
            ("ACHIEVEMENTS", d.get("achievements", 0)),
        ]
        for a, b in records:
            c = Card(orientation="vertical", size_hint_y=None, height=dp(74))
            c.add_widget(label(a, 9, MUTED, True))
            c.add_widget(label(str(b), 19, TEXT, True))
            self.record_grid.add_widget(c)

        self.achievements.add_widget(label(
            "🏆 PROFILE ACHIEVEMENT SYSTEM", 12, GOLD, True))
        self.achievements.add_widget(label(
            f"Your recorded achievements: {d.get('achievements', 0)}\n"
            "Skill milestones, challenge results, PRs and tournament records can all live here.",
            10, MUTED))

        today = datetime.datetime.now()
        month = today.strftime("%B %Y")
        self.calendar.add_widget(label(f"{month}", 13, TEXT, True))
        self.calendar.add_widget(label(
            "✓ Today • Workout history • streaks • skill practice time\n"
            "A full calendar can be backed by /users/{user}/activity/",
            10, MUTED))

    def edit_profile(self, *_):
        u = App.get_running_app().current_user
        d = safe_get(f"users/{u}", {}) or {}
        box = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(8))
        fields = {}
        for key, hint in [
            ("bodyweight", "Bodyweight (kg)"),
            ("height", "Height (cm)"),
            ("body_type", "Body type / build"),
            ("goal", "Main goal"),
        ]:
            ti = TextInput(text=str(d.get(key, "")), hint_text=hint,
                           multiline=False, size_hint_y=None, height=dp(44),
                           background_normal="",
                           background_color=get_color_from_hex(CARD2),
                           foreground_color=get_color_from_hex(TEXT),
                           hint_text_color=get_color_from_hex(MUTED))
            fields[key] = ti
            box.add_widget(ti)
        save = pill_button("SAVE PROFILE", None, ACCENT, 44)
        box.add_widget(save)
        pop = Popup(title="EDIT PROFILE", content=box, size_hint=(.9, .62))
        def do_save(*_):
            safe_patch(f"users/{u}", {k: v.text.strip() for k, v in fields.items()})
            pop.dismiss()
            self.refresh()
        save.bind(on_release=do_save)
        pop.open()

    def creator_info(self, *_):
        self.popup("CREATOR HUB",
                   "ATHLETE PROGRAMS\nPublish 1/3/6-month programs.\n\n"
                   "SKILL VIDEOS\nPublish educational skill content.\n\n"
                   "1:1 SESSIONS\nOffer paid coaching sessions.\n\n"
                   "EARNINGS\nPlatform transactions can calculate an athlete share and GRAVIX platform fee.")


class GravixApp(App):
    def build(self):
        self.title = "GRAVIX"
        self.current_user = None
        sm = ScreenManager()
        sm.add_widget(LoginScreen(name="login"))
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(SkillsScreen(name="skills"))
        sm.add_widget(ProfileScreen(name="profile"))
        return sm


if __name__ == "__main__":
    GravixApp().run()
