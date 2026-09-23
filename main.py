from urllib.parse import quote

import requests
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp
from kivy.resources import resource_find
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import get_color_from_hex

FIREBASE_URL = "https://gravix-7b589-default-rtdb.asia-southeast1.firebasedatabase.app"
BG, CARD, CARD2 = "#0B0D10", "#15191F", "#1B2027"
TEXT, MUTED, ACCENT = "#F5F7FA", "#9299A5", "#E53935"
GREEN, LOCKED, WHITE = "#31C48D", "#292E36", "#FFFFFF"
Window.clearcolor = get_color_from_hex(BG)


def db_url(endpoint):
    # Firebase REST paths must be URL encoded, especially usernames.
    path = "/".join(quote(part, safe="") for part in endpoint.split("/"))
    return f"{FIREBASE_URL.rstrip('/')}/{path}.json"


def rounded(widget, color=CARD, radius=18, border=False):
    with widget.canvas.before:
        Color(*get_color_from_hex(color))
        widget._bg = RoundedRectangle(pos=widget.pos, size=widget.size,
                                      radius=[dp(radius)])
        if border:
            Color(*get_color_from_hex("#2B313A"))
            widget._line = Line(rounded_rectangle=(widget.x, widget.y,
                widget.width, widget.height, dp(radius)), width=1)
    widget.bind(pos=lambda *_: setattr(widget._bg, "pos", widget.pos))
    widget.bind(size=lambda *_: setattr(widget._bg, "size", widget.size))
    if border:
        widget.bind(pos=lambda *_: setattr(widget._line, "rounded_rectangle",
            (widget.x, widget.y, widget.width, widget.height, dp(radius))))
        widget.bind(size=lambda *_: setattr(widget._line, "rounded_rectangle",
            (widget.x, widget.y, widget.width, widget.height, dp(radius))))
    return widget


def label(text="", size=14, color=TEXT, bold=False, halign="left"):
    return Label(text=f"[b]{text}[/b]" if bold else text, markup=True,
        font_size=dp(size), color=get_color_from_hex(color), halign=halign,
        valign="middle", text_size=(None, None))


def pill_button(text, callback=None, color=ACCENT, height=48):
    button = Button(text=text, size_hint_y=None, height=dp(height),
        background_normal="", background_color=get_color_from_hex(color),
        color=get_color_from_hex(WHITE), bold=True, font_size=dp(13))
    if callback:
        button.bind(on_release=callback)
    return button


class Card(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        rounded(self, CARD, 18, True)
        self.padding = dp(16)


class LoginScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        try:
            bg = Image(source=resource_find("assets.gravix/Baki_bg.png"),
                       allow_stretch=True, keep_ratio=False)
            bg.size_hint = (1, 1)
            self.add_widget(bg)
        except Exception:
            pass
        root = BoxLayout(orientation="vertical", padding=[dp(28), dp(50), dp(28), dp(28)], spacing=dp(16))
        root.add_widget(BoxLayout(size_hint_y=.25))
        logo = label("GRAVIX", 38, ACCENT, True, "center")
        logo.size_hint_y = None; logo.height = dp(55); root.add_widget(logo)
        tagline = label("MASTER YOUR BODY.", 13, MUTED, True, "center")
        tagline.size_hint_y = None; tagline.height = dp(28); root.add_widget(tagline)
        self.username = self.field("Username")
        self.password = self.field("Password", password=True)
        root.add_widget(self.username); root.add_widget(self.password)
        self.status = label("", 12, MUTED, False, "center")
        self.status.size_hint_y = None; self.status.height = dp(42); root.add_widget(self.status)
        root.add_widget(pill_button("ENTER GRAVIX", self.login, ACCENT, 54))
        root.add_widget(pill_button("CREATE ACCOUNT", self.register, CARD2, 50))
        bottom = label("Train • Progress • Conquer", 11, MUTED, False, "center")
        bottom.size_hint_y = .4; root.add_widget(bottom); self.add_widget(root)

    def field(self, hint, password=False):
        return TextInput(hint_text=hint, password=password, multiline=False,
            size_hint_y=None, height=dp(52), background_normal="",
            background_active="", background_color=get_color_from_hex(CARD),
            foreground_color=get_color_from_hex(TEXT), hint_text_color=get_color_from_hex(MUTED),
            padding=[dp(16), dp(15)])

    def register(self, *_):
        u, p = self.username.text.strip().lower(), self.password.text.strip()
        if not u or not p:
            self.status.text = "Username and password cannot be empty."; return
        if len(u) < 3:
            self.status.text = "Username must be at least 3 characters."; return
        try:
            user_url = db_url(f"users/{u}")
            existing = requests.get(user_url, timeout=10)
            # Do not treat a permission/server error as an existing username.
            if existing.status_code != 200:
                self.status.text = (f"Firebase read error: {existing.status_code}\n"
                                    f"{existing.text}")
                return
            if existing.json() is not None:
                self.status.text = "Username already exists."; return
            response = requests.put(user_url, json={"username": u, "password": p,
                "level": 0, "xp": 0}, timeout=10)
            if response.status_code not in (200, 201):
                self.status.text = (f"Firebase write error: {response.status_code}\n"
                                    f"{response.text}")
                return
            App.get_running_app().current_user = u
            self.manager.current = "home"
        except requests.exceptions.Timeout:
            self.status.text = "Firebase request timed out."
        except requests.exceptions.ConnectionError:
            self.status.text = "Could not connect to Firebase."
        except ValueError:
            self.status.text = "Firebase returned invalid data."
        except Exception as error:
            self.status.text = f"Registration failed: {error}"

    def login(self, *_):
        u, p = self.username.text.strip().lower(), self.password.text.strip()
        if not u or not p:
            self.status.text = "Enter your username and password."; return
        try:
            response = requests.get(db_url(f"users/{u}"), timeout=10)
            if response.status_code != 200:
                self.status.text = f"Firebase error: {response.status_code}\n{response.text}"; return
            data = response.json()
            if data and data.get("password") == p:
                App.get_running_app().current_user = u; self.manager.current = "home"
            else: self.status.text = "Invalid username or password."
        except requests.exceptions.Timeout: self.status.text = "Firebase request timed out."
        except requests.exceptions.ConnectionError: self.status.text = "Could not connect to Firebase."
        except Exception as error: self.status.text = f"Login failed: {error}"


class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs); self.level = 0; self.xp = 0
        root = BoxLayout(orientation="vertical", padding=[dp(18), dp(25), dp(18), 0])
        scroll = ScrollView(do_scroll_x=False)
        content = BoxLayout(orientation="vertical", spacing=dp(14), size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))
        header = BoxLayout(size_hint_y=None, height=dp(55))
        self.greeting = label("WELCOME", 12, MUTED, True); header.add_widget(self.greeting)
        out = pill_button("LOG OUT", self.logout, CARD2, 38); out.size_hint_x=.3; header.add_widget(out)
        content.add_widget(header)
        hero = Card(orientation="vertical", size_hint_y=None, height=dp(150), spacing=dp(4))
        top = BoxLayout(size_hint_y=None, height=dp(35)); self.level_label=label("LEVEL 0",22,TEXT,True); top.add_widget(self.level_label)
        self.xp_label=label("0 XP",12,MUTED,True,"right"); top.add_widget(self.xp_label); hero.add_widget(top)
        self.xp_bar=ProgressBar(max=100,value=0,size_hint_y=None,height=dp(8)); hero.add_widget(self.xp_bar)
        hero.add_widget(label("KEEP GRINDING. EVERY REP COUNTS.",11,MUTED,True)); content.add_widget(hero)
        mission=Card(orientation="vertical",size_hint_y=None,height=dp(135),spacing=dp(8))
        mission.add_widget(label("TODAY'S MISSION",11,ACCENT,True)); mission.add_widget(label("BUILD YOUR BASE",22,TEXT,True))
        mission.add_widget(label("Complete a skill session and earn XP.",12,MUTED)); mission.add_widget(pill_button("VIEW SKILLS",self.go_skills,ACCENT,42)); content.add_widget(mission)
        content.add_widget(label("YOUR SKILLS",16,TEXT,True)); self.skills_box=GridLayout(cols=2,spacing=dp(10),size_hint_y=None); self.skills_box.bind(minimum_height=self.skills_box.setter("height")); content.add_widget(self.skills_box)
        scroll.add_widget(content); root.add_widget(scroll); root.add_widget(self.nav()); self.add_widget(root)

    def nav(self):
        n=BoxLayout(size_hint_y=None,height=dp(68),spacing=dp(8),padding=[0,dp(8),0,dp(8)])
        n.add_widget(pill_button("HOME",lambda *_:None,ACCENT,50)); n.add_widget(pill_button("SKILLS",self.go_skills,CARD2,50)); n.add_widget(pill_button("PROFILE",self.go_profile,CARD2,50)); return n
    def on_enter(self): Clock.schedule_once(lambda *_: self.refresh(), .1)
    def refresh(self):
        self.username=getattr(App.get_running_app(),"current_user",""); self.greeting.text=f"HELLO, {self.username.upper()}"; self.load_profile(); self.load_skills()
    def load_profile(self):
        try:
            d=requests.get(db_url(f"users/{self.username}"),timeout=10).json() or {}; self.level=int(d.get("level",0)); self.xp=int(d.get("xp",0)); need=100+self.level*50
            self.level_label.text=f"LEVEL {self.level}"; self.xp_label.text=f"{self.xp} / {need} XP"; self.xp_bar.max=need; self.xp_bar.value=self.xp
        except Exception: pass
    def load_skills(self):
        self.skills_box.clear_widgets()
        try:
            data=requests.get(db_url("skills"),timeout=10).json() or {}
            if not data: self.skills_box.add_widget(label("No skills found yet.\nAdd some from the Skills screen.",12,MUTED,False,"center")); return
            for s in list(data.values())[:8]:
                name=s.get("skill_name","Skill"); diff=s.get("difficulty","C"); req=int(s.get("required_level",0)); unlocked=self.level>=req
                b=Button(text=f"[b]{name.upper()}[/b]\n\n{'UNLOCKED • '+str(diff) if unlocked else 'LOCKED • LVL '+str(req)}",markup=True,size_hint_y=None,height=dp(105),background_normal="",background_color=get_color_from_hex(ACCENT if unlocked else LOCKED),color=get_color_from_hex(TEXT),font_size=dp(12))
                b.bind(on_release=lambda _,n=name,r=req,d=diff:self.skill_popup(n,r,d)); self.skills_box.add_widget(b)
        except Exception: self.skills_box.add_widget(label("Could not load skills.",13,MUTED,False,"center"))
    def skill_popup(self,name,req,diff):
        if self.level<req: self.popup_msg("SKILL LOCKED",f"{name}\n\nUnlock this skill at Level {req}."); return
        xp={"S":500,"A":250,"B":100,"C":50}.get(str(diff).upper()[:1],50); self.popup_msg(name.upper(),f"{diff} TIER\n\nTrain this skill to earn XP.\n\nREWARD +{xp} XP")
    def popup_msg(self,title,msg):
        box=BoxLayout(orientation="vertical",padding=dp(18),spacing=dp(10)); box.add_widget(label(msg,15,TEXT,False,"center")); close=pill_button("CLOSE",None,CARD2,46); box.add_widget(close); pop=Popup(title=title,content=box,size_hint=(.84,.42)); close.bind(on_release=pop.dismiss); pop.open()
    def go_skills(self,*_): self.manager.current="skills"
    def go_profile(self,*_): self.manager.current="profile"
    def logout(self,*_): App.get_running_app().current_user=None; self.manager.current="login"


class SkillsScreen(Screen):
    def __init__(self,**kwargs):
        super().__init__(**kwargs); root=BoxLayout(orientation="vertical",padding=[dp(18),dp(25),dp(18),0],spacing=dp(12)); head=BoxLayout(size_hint_y=None,height=dp(50)); head.add_widget(label("SKILL TREE",25,TEXT,True)); head.add_widget(pill_button("HOME",lambda *_:setattr(self.manager,"current","home"),CARD2,40)); root.add_widget(head); scroll=ScrollView(do_scroll_x=False); self.grid=GridLayout(cols=1,spacing=dp(10),size_hint_y=None); self.grid.bind(minimum_height=self.grid.setter("height")); scroll.add_widget(self.grid); root.add_widget(scroll); root.add_widget(pill_button("+ ADD SKILL",lambda *_:setattr(self.manager,"current","add_skill"),ACCENT,50)); self.add_widget(root)
    def on_enter(self): Clock.schedule_once(lambda *_: self.refresh(),.1)
    def refresh(self):
        self.grid.clear_widgets()
        try:
            data=requests.get(db_url("skills"),timeout=10).json() or {}
            for s in data.values():
                self.grid.add_widget(label(f"{s.get('skill_name','Skill').upper()}  •  {s.get('difficulty','C')} TIER",16,TEXT,True))
        except Exception: self.grid.add_widget(label("Could not load skills.",13,MUTED))


class AddSkillScreen(Screen):
    def __init__(self,**kwargs):
        super().__init__(**kwargs); root=BoxLayout(orientation="vertical",padding=[dp(25),dp(30),dp(25),dp(20)],spacing=dp(12)); root.add_widget(label("ADD SKILL",26,TEXT,True)); root.add_widget(label("Expand the GRAVIX skill tree.",12,MUTED)); self.name=TextInput(hint_text="Skill name",multiline=False,size_hint_y=None,height=dp(52)); self.diff=TextInput(hint_text="Difficulty: S / A / B / C",multiline=False,size_hint_y=None,height=dp(52)); self.req=TextInput(hint_text="Required level",multiline=False,input_filter="int",size_hint_y=None,height=dp(52)); root.add_widget(self.name); root.add_widget(self.diff); root.add_widget(self.req); self.status=label("",12,MUTED); root.add_widget(self.status); root.add_widget(pill_button("SAVE TO CLOUD",self.save,ACCENT,52)); root.add_widget(pill_button("BACK",lambda *_:setattr(self.manager,"current","skills"),CARD2,48)); root.add_widget(BoxLayout()); self.add_widget(root)
    def save(self,*_):
        if not self.name.text.strip() or not self.req.text.strip(): self.status.text="Name and required level are required."; return
        try:
            r=requests.post(db_url("skills"),json={"skill_name":self.name.text.strip(),"difficulty":self.diff.text.strip().upper() or "C","required_level":int(self.req.text)},timeout=10)
            if r.status_code not in (200,201): self.status.text=f"Firebase error: {r.status_code}\\n{r.text}"; return
            self.name.text=self.diff.text=self.req.text=""; self.manager.current="skills"
        except Exception as e: self.status.text=f"Could not save skill: {e}"


class ProfileScreen(Screen):
    def __init__(self,**kwargs):
        super().__init__(**kwargs); root=BoxLayout(orientation="vertical",padding=[dp(18),dp(25),dp(18),dp(15)],spacing=dp(14)); head=BoxLayout(size_hint_y=None,height=dp(50)); head.add_widget(label("PROFILE",25,TEXT,True)); head.add_widget(pill_button("HOME",lambda *_:setattr(self.manager,"current","home"),CARD2,40)); root.add_widget(head); self.user=label("PLAYER",28,TEXT,True); self.stats=label("LEVEL 0\\n0 XP",15,MUTED); card=Card(orientation="vertical",size_hint_y=None,height=dp(150),spacing=dp(8)); card.add_widget(label("PLAYER",11,MUTED,True)); card.add_widget(self.user); card.add_widget(self.stats); root.add_widget(card); root.add_widget(BoxLayout()); self.add_widget(root)
    def on_enter(self):
        u=getattr(App.get_running_app(),"current_user",""); self.user.text=u.upper()
        try: d=requests.get(db_url(f"users/{u}"),timeout=10).json() or {}; self.stats.text=f"LEVEL {d.get('level',0)}\\n{d.get('xp',0)} XP"
        except Exception: pass


class GravixApp(App):
    def build(self):
        self.title="GRAVIX"; self.current_user=None; sm=ScreenManager()
        for screen in (LoginScreen(name="login"),HomeScreen(name="home"),SkillsScreen(name="skills"),AddSkillScreen(name="add_skill"),ProfileScreen(name="profile")): sm.add_widget(screen)
        return sm


if __name__ == "__main__":
    GravixApp().run()
