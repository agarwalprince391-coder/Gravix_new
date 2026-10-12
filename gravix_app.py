"""GRAVIX calisthenics and fitness MVP.

Connects to the Realtime Database URL used by the starter app. Production use
requires Firebase Authentication/database rules, a payment provider, media
storage/streaming, AI inference and mobile health/notification integrations.
"""
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
from kivy.uix.image import AsyncImage
from kivy.uix.progressbar import ProgressBar
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.uix.widget import Widget
from kivy.storage.jsonstore import JsonStore
from kivy.graphics import Color, RoundedRectangle, Line, Ellipse
import datetime
import json
import math
import os
import random
import re
import shutil
import sqlite3
import time
import threading
import webbrowser
import requests

try:
    from plyer import notification as native_notification
except Exception:
    native_notification = None

try:
    from plyer import gps as phone_gps
except Exception:
    phone_gps = None

try:
    from plyer import filechooser as native_filechooser
except Exception:
    native_filechooser = None

try:
    from jnius import autoclass, PythonJavaClass, java_method
except Exception:
    autoclass = PythonJavaClass = java_method = None

if PythonJavaClass:
    class _StepSensorListener(PythonJavaClass):
        __javainterfaces__ = ["android/hardware/SensorEventListener"]

        def __init__(self, callback):
            super().__init__()
            self.callback = callback

        @java_method("(Landroid/hardware/SensorEvent;)V")
        def onSensorChanged(self, event):
            try:
                self.callback(float(event.values[0]))
            except Exception:
                pass

        @java_method("(Landroid/hardware/Sensor;I)V")
        def onAccuracyChanged(self, sensor, accuracy):
            pass
else:
    _StepSensorListener = None


FIREBASE_URL = "https://gravix-7b589-default-rtdb.asia-southeast1.firebasedatabase.app"
try:
    from gravix_config import FIREBASE_API_KEY, FIREBASE_FUNCTIONS_BASE_URL
except Exception:
    FIREBASE_API_KEY = ""
    FIREBASE_FUNCTIONS_BASE_URL = (
        "https://asia-southeast1-gravix-7b589.cloudfunctions.net")

# ---------------- THEME ----------------
BG = "#080A14"
CARD = "#12172A"
CARD2 = "#1A2340"
TEXT = "#F5F4FF"
MUTED = "#A4AEC7"
ACCENT = "#A855F7"
GREEN = "#37D5C5"
GOLD = "#FFC66D"
LOCKED = "#252D47"
WHITE = "#FFFFFF"
Window.clearcolor = get_color_from_hex(BG)


def db_url(endpoint):
    return f"{FIREBASE_URL.rstrip('/')}/{endpoint.strip('/')}.json"


class FirebaseAuthSession:
    """Firebase email/password auth with a locally stored refresh token."""
    STORE_KEY = "firebase_auth"

    def __init__(self, store=None):
        self.store = store
        self.on_invalid_refresh = None
        self.id_token = None
        self.refresh_token = None
        self.uid = None
        self.email = None
        self.expires_at = 0
        self.last_error = ""

    def load_saved_session(self):
        """Load only the refreshable identity; never persist a password."""
        self.last_error = ""
        if self.store is None:
            self.last_error = "storage_unavailable"
            return False
        try:
            if not self.store.exists(self.STORE_KEY):
                return False
            saved = self.store.get(self.STORE_KEY)
            self.uid = saved.get("uid")
            self.email = saved.get("email")
            self.refresh_token = saved.get("refresh_token")
            return bool(self.refresh_token and self.uid)
        except Exception:
            # Leave unreadable data untouched; only an invalid server refresh
            # token or an explicit logout should remove saved credentials.
            self.last_error = "storage_unavailable"
            return False

    def _save_session(self):
        if self.store is None:
            raise ValueError("Could not save your login session on this device.")
        if not self.uid or not self.refresh_token:
            raise ValueError("Firebase did not return a refreshable login session.")
        try:
            self.store.put(
                self.STORE_KEY, uid=self.uid, email=self.email or "",
                refresh_token=self.refresh_token)
        except Exception:
            raise ValueError("Could not save your login session on this device.")

    def _clear_memory(self):
        self.id_token = self.refresh_token = self.uid = self.email = None
        self.expires_at = 0

    def _call(self, operation, payload):
        if not FIREBASE_API_KEY:
            raise ValueError(
                "Firebase Web API key is not configured. Add it to gravix_config.py.")
        try:
            response = requests.post(
                f"https://identitytoolkit.googleapis.com/v1/accounts:{operation}",
                params={"key": FIREBASE_API_KEY}, json=payload, timeout=15)
        except requests.RequestException:
            raise ValueError("Could not reach Firebase Authentication.")
        try:
            data = response.json() if response.content else {}
        except ValueError:
            data = {}
        if not response.ok:
            message = data.get("error", {}).get("message", "Authentication failed.")
            friendly = {
                "EMAIL_EXISTS": "That email already has a GRAVIX account.",
                "INVALID_LOGIN_CREDENTIALS": "Email or password is incorrect.",
                "EMAIL_NOT_FOUND": "Email or password is incorrect.",
                "INVALID_PASSWORD": "Email or password is incorrect.",
                "WEAK_PASSWORD": "Choose a password with at least 8 characters.",
                "OPERATION_NOT_ALLOWED": "Enable email/password sign-in in Firebase.",
                "TOO_MANY_ATTEMPTS_TRY_LATER": "Too many attempts. Try again later.",
            }
            raise ValueError(friendly.get(message, message.replace("_", " ").title()))
        self._accept_tokens(data, persist=True)
        return data

    def _accept_tokens(self, data, persist=False):
        self.id_token = data.get("idToken") or data.get("id_token")
        self.refresh_token = (data.get("refreshToken") or
                              data.get("refresh_token") or self.refresh_token)
        self.uid = (data.get("localId") or data.get("user_id") or self.uid)
        self.email = data.get("email", self.email)
        try:
            lifetime = int(data.get("expiresIn") or data.get("expires_in") or 3600)
        except (TypeError, ValueError):
            lifetime = 3600
        self.expires_at = time.monotonic() + max(0, lifetime - 60)
        self.last_error = ""
        if persist:
            try:
                self._save_session()
            except ValueError:
                self._clear_memory()
                raise

    def sign_in(self, email, password):
        return self._call("signInWithPassword", {
            "email": email, "password": password, "returnSecureToken": True,
        })

    def sign_up(self, email, password):
        return self._call("signUp", {
            "email": email, "password": password, "returnSecureToken": True,
        })

    def get_id_token(self, force_refresh=False):
        if not self.refresh_token:
            return None
        if (not force_refresh and self.id_token and
                time.monotonic() < self.expires_at):
            return self.id_token
        self.last_error = ""
        if not FIREBASE_API_KEY:
            self.last_error = "configuration_error"
            return None
        try:
            response = requests.post(
                "https://securetoken.googleapis.com/v1/token",
                params={"key": FIREBASE_API_KEY},
                data={"grant_type": "refresh_token",
                      "refresh_token": self.refresh_token},
                timeout=15)
            try:
                data = response.json() if response.content else {}
            except ValueError:
                data = {}
            if not response.ok:
                message = str(data.get("error", {}).get("message", "")).upper()
                if message in {"INVALID_REFRESH_TOKEN", "TOKEN_EXPIRED"}:
                    self.last_error = "invalid_refresh_token"
                    self.clear()
                    if self.on_invalid_refresh:
                        Clock.schedule_once(
                            lambda _dt: self.on_invalid_refresh(), 0)
                else:
                    self.last_error = "refresh_failed"
                return None
            if not (data.get("id_token") or data.get("idToken")):
                self.last_error = "refresh_failed"
                return None
            self._accept_tokens(data, persist=True)
            return self.id_token
        except requests.RequestException:
            self.last_error = "network_error"
            return None
        except ValueError:
            # Keep the previously saved token if updating local storage fails.
            self.last_error = "storage_error"
            return None

    def clear(self):
        """Forget the session after logout or a confirmed invalid refresh token."""
        self._clear_memory()
        if self.store is not None:
            try:
                if self.store.exists(self.STORE_KEY):
                    self.store.delete(self.STORE_KEY)
            except Exception:
                pass


def database_request(method, endpoint, payload=None):
    app = App.get_running_app()
    session = getattr(app, "auth", None)
    token = session.get_id_token() if session else None
    if not token:
        return None
    requester = getattr(requests, method)
    for attempt in range(2):
        try:
            kwargs = {"params": {"auth": token}, "timeout": 12}
            if method in ("put", "patch", "post"):
                kwargs["json"] = payload
            response = requester(db_url(endpoint), **kwargs)
            if response.status_code in (401, 403) and attempt == 0:
                token = session.get_id_token(force_refresh=True)
                if token:
                    continue
            return response
        except requests.RequestException:
            return None
    return None


def call_function(name, payload):
    app = App.get_running_app()
    auth = getattr(app, "auth", None)
    token = auth.get_id_token() if auth else None
    if not token:
        return None
    try:
        response = requests.post(
            f"{FIREBASE_FUNCTIONS_BASE_URL.rstrip('/')}/{name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"data": payload}, timeout=20)
        body = response.json() if response.content else {}
        if response.ok:
            return body.get("result", body)
    except requests.RequestException:
        pass
    return None


def today_key():
    return datetime.date.today().isoformat()


def clean_markup(value):
    return str(value).replace("&", "&amp;").replace("[", "&bl;").replace("]", "&br;")


def safe_get(endpoint, default=None):
    try:
        response = database_request("get", endpoint)
        if response is None:
            return default
        if response.ok:
            value = response.json()
            return value if value is not None else default
    except Exception:
        pass
    return default


def safe_patch(endpoint, payload):
    try:
        response = database_request("patch", endpoint, payload)
        return bool(response and response.ok)
    except Exception:
        return False


def safe_put(endpoint, payload):
    try:
        response = database_request("put", endpoint, payload)
        return bool(response and response.ok)
    except Exception:
        return False


def safe_post(endpoint, payload):
    try:
        response = database_request("post", endpoint, payload)
        return bool(response and response.ok)
    except Exception:
        return False


def user_path():
    return f"users/{App.get_running_app().current_user or ''}"


def read_user():
    data = safe_get(user_path(), {}) or {}
    if not isinstance(data, dict):
        return {}
    # Keep user-editable profile/preferences separate from server-owned stats.
    merged = dict(data)
    for key in ("profile", "stats", "preferences"):
        child = data.get(key, {})
        if isinstance(child, dict):
            merged.update(child)
    return merged


def record_activity(kind, details):
    """Ask the authenticated server to validate and record training activity."""
    if not App.get_running_app().current_user:
        return False
    result = call_function("recordActivity", {
        "kind": kind, "details": {**details, "local_date": today_key()},
    })
    return result is not None


def initialize_user_profile(uid, email, display_name):
    profile_path = f"users/{uid}/profile"
    profile = safe_get(profile_path)
    if profile is None:
        profile = {
            "email": email, "display_name": display_name,
            "bodyweight": "", "height": "", "body_type": "Not set",
            "goal": "Build strength", "location": "",
            "latitude": "", "longitude": "",
        }
        if not safe_put(profile_path, profile):
            return False
        safe_put(f"users/{uid}/preferences", {
            "reminder_enabled": True, "reminder_time": "08:00",
        })
    public_profile_path = f"public_profiles/{uid}"
    public_profile = safe_get(public_profile_path)
    if public_profile is None:
        safe_put(public_profile_path, {
            "display_name": display_name or email.split("@")[0],
            "avatar_url": "", "body_type": "Not set",
            "goal": "Build strength",
        })
    return True


def activity_map(records):
    days = {}
    if isinstance(records, dict):
        for value in records.values():
            if isinstance(value, dict) and value.get("date"):
                days[value["date"]] = days.get(value["date"], 0) + 1
    return days


def current_streak(days):
    cursor = datetime.date.today()
    if cursor.isoformat() not in days:
        cursor -= datetime.timedelta(days=1)
    streak = 0
    while cursor.isoformat() in days:
        streak += 1
        cursor -= datetime.timedelta(days=1)
    return streak


def distance_km(lat1, lon1, lat2, lon2):
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp_lat = math.radians(lat2 - lat1)
    dp_lon = math.radians(lon2 - lon1)
    value = (math.sin(dp_lat / 2) ** 2 +
             math.cos(p1) * math.cos(p2) * math.sin(dp_lon / 2) ** 2)
    return 2 * radius * math.asin(min(1.0, math.sqrt(value)))


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
    value = clean_markup(text)
    if bold:
        value = f"[b]{value}[/b]"
    widget = Label(
        text=value, markup=True, font_size=dp(size),
        color=get_color_from_hex(color), halign=halign, valign="middle",
    )
    widget.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0], None)))
    return widget


def pill_button(text, callback=None, color=ACCENT, height=48):
    button = Button(
        text=text, size_hint_y=None, height=dp(height), background_normal="",
        background_color=get_color_from_hex(color),
        color=get_color_from_hex(WHITE), bold=True, font_size=dp(12),
    )
    if callback:
        button.bind(on_release=callback)
    return button


def text_field(hint, text="", height=46):
    return TextInput(
        text=str(text or ""), hint_text=hint, multiline=False,
        size_hint_y=None, height=dp(height), background_normal="",
        background_color=get_color_from_hex(CARD2),
        foreground_color=get_color_from_hex(TEXT),
        hint_text_color=get_color_from_hex(MUTED),
        cursor_color=get_color_from_hex(ACCENT), padding=[dp(12), dp(12)],
    )


def card(**kwargs):
    result = BoxLayout(**kwargs)
    rounded(result, CARD, 18, True)
    result.padding = dp(14)
    return result


def catalog_skills():
    """Broad starter library; coaches can extend it in the authenticated backend."""
    catalog = {
        "push_up": ("Push-up", "Push", "Chest, triceps, front deltoids, core",
                    ["Wall push-up 3×10", "Incline push-up 3×8–12",
                     "Knee or 3-second negative 3×6–10",
                     "Full push-up 4×5–12", "Tempo push-up 4×8 with 2-sec pause"]),
        "glute_bridge": ("Glute bridge", "Lower body", "Glutes, hamstrings, core",
                         ["Glute squeeze 3×10", "Floor bridge 3×12",
                          "Bridge hold 4×20 sec", "Single-leg bridge 3×6/side",
                          "Elevated single-leg bridge 3×8/side"]),
        "split_squat": ("Split squat", "Lower body", "Quads, glutes, balance",
                        ["Supported split stance 3×20 sec/side",
                         "Short-range split squat 3×8/side",
                         "Bodyweight split squat 3×10/side",
                         "Reverse lunge 4×8/side",
                         "Slow-tempo split squat 4×8/side"]),
        "hip_hinge": ("Hip hinge", "Lower body", "Glutes, hamstrings, back",
                      ["Wall-touch hinge 3×10", "Unloaded good morning 3×12",
                       "Single-leg reach 3×8/side", "Backpack hinge 4×10",
                       "Single-leg hinge 4×8/side"]),
        "side_plank": ("Side plank", "Core", "Obliques, shoulders, hips",
                       ["Side-lying brace 3×15 sec/side",
                        "Bent-knee side plank 3×20 sec/side",
                        "Full side plank 3×20 sec/side",
                        "Side plank with reach 3×8/side",
                        "Side plank with top-leg lift 3×6/side"]),
        "dead_bug": ("Dead bug", "Core", "Deep core, hips",
                     ["Abdominal brace 3×5 breaths",
                      "Heel taps 3×8/side", "Opposite arm and leg reach 3×8/side",
                      "Slow dead bug 4×8/side", "Band-resisted dead bug 4×8/side"]),
        "diamond_pushup": ("Diamond push-up", "Push", "Triceps, chest, core",
                           ["Close-grip wall push-up 3×10", "Incline diamond 3×8",
                            "Knee diamond 3×6–10", "Diamond push-up 4×5–10",
                            "Diamond push-up 4×8 with 3-sec lowering"]),
        "archer_pushup": ("Archer push-up", "Push", "Chest, triceps, shoulders, core",
                          ["Wide incline push-up 3×10", "Side-to-side incline 3×6/side",
                           "Knee archer 3×5/side", "Archer negative 4×3/side",
                           "Archer push-up 4×4–8/side"]),
        "pseudo_planche_pushup": ("Pseudo-planche push-up", "Push",
                                  "Chest, front deltoids, triceps, core",
                                  ["Planche lean 4×10 sec", "Knee lean push-up 3×8",
                                   "Short-lean push-up 4×5", "Long-lean push-up 4×5–8",
                                   "Pseudo-planche push-up 4×6–10"]),
        "pike_pushup": ("Pike push-up", "Push", "Shoulders, triceps, upper chest",
                        ["Elevated pike hold 3×20 sec", "Short-range pike push-up 3×8",
                         "Pike push-up 4×6–10", "Feet-elevated pike 4×5–8",
                         "Wall handstand push-up negative 4×3"]),
        "dip": ("Parallel-bar dip", "Push", "Chest, triceps, front deltoids",
                ["Top support 4×15 sec", "Foot-assisted dip 4×6–10",
                 "3-sec eccentric dip 4×4", "Full dip 4×5–10",
                 "Deep controlled dip 4×8"]),
        "straight_bar_dip": ("Straight-bar dip", "Push", "Chest, triceps, shoulders",
                             ["Bar support 4×15 sec", "Low-bar assisted dip 3×8",
                              "Straight-bar negative 4×3", "Full straight-bar dip 4×4–8",
                              "Straight-bar dip 4×8–10"]),
        "ring_dip": ("Ring dip", "Rings", "Chest, triceps, shoulders, stabilizers",
                     ["Ring support with feet assisted 5×10 sec",
                      "Ring push-up 4×8", "Assisted ring dip 4×4",
                      "Ring dip negative 4×3", "Strict ring dip 4×4–8"]),
        "pull_up": ("Pull-up", "Pull", "Lats, biceps, forearms, core",
                    ["Active hang 4×20 sec", "Scapular pull 4×6–10",
                     "Band-assisted pull-up 4×5–8", "3–5 sec negative 4×3",
                     "Strict pull-up 4×3–8"]),
        "chin_up": ("Chin-up", "Pull", "Lats, biceps, forearms",
                    ["Active hang 4×20 sec", "Foot-assisted chin-up 4×6",
                     "Band-assisted chin-up 4×5–8", "Slow negative 4×3",
                     "Strict chin-up 4×4–8"]),
        "chest_to_bar": ("Chest-to-bar pull-up", "Pull", "Lats, upper back, biceps",
                         ["Strict pull-up 4×5", "Fast pull-up 5×3",
                          "Band chest-to-bar 4×4", "High pull to sternum 5×3",
                          "Chest-to-bar pull-up 5×3–6"]),
        "archer_pullup": ("Archer pull-up", "Pull", "Lats, biceps, grip",
                          ["Archer row 4×8/side", "Uneven band pull-up 4×5/side",
                           "Assisted archer pull 4×3/side",
                           "Archer negative 4×2/side", "Archer pull-up 4×2–5/side"]),
        "typewriter_pullup": ("Typewriter pull-up", "Pull", "Lats, biceps, scapular control",
                              ["Wide pull-up 4×5", "Assisted side shift 4×3/side",
                               "Top hold and short shift 4×3",
                               "Typewriter negative 4×2",
                               "Typewriter pull-up 4×2–4"]),
        "one_arm_pullup": ("One-arm pull-up pathway", "Pull",
                           "Lats, biceps, forearms, core",
                           ["Scapular pull + active hang 3×8",
                            "Assisted archer row 4×6/side",
                            "Uneven-grip pull-up 4×4/side",
                            "Band-assisted one-arm negative 3×2/side",
                            "Band-assisted one-arm pull 4×1–3/side"]),
        "muscle_up": ("Bar muscle-up", "Pull / transition",
                      "Lats, chest, triceps, biceps, core",
                      ["Strict pull-up 4×5", "Explosive high pull 5×3",
                       "Low-bar transition drill 4×3", "Straight-bar dip 4×6",
                       "Band-assisted muscle-up 5×1–3"]),
        "l_sit": ("L-sit", "Core / compression", "Abs, hip flexors, quads, triceps",
                  ["Support hold 4×15 sec", "Tuck sit 5×8 sec",
                   "One-leg extension 4×8 sec/side",
                   "Advanced tuck 5×8 sec", "L-sit 6×5–15 sec"]),
        "v_sit": ("V-sit pathway", "Core / compression", "Abs, hip flexors, quads",
                  ["Seated compression lift 4×8", "Tuck L-sit 5×10 sec",
                   "One-leg V raise 4×6/side", "V-sit compression 5×6",
                   "V-sit hold 5×5–10 sec"]),
        "hollow_body": ("Hollow-body hold", "Core", "Abdominals, hip flexors",
                        ["Dead bug 3×8/side", "Tuck hollow hold 4×15 sec",
                         "One-leg hollow 4×15 sec", "Full hollow 5×15 sec",
                         "Hollow rocks 4×10–20"]),
        "hanging_leg_raise": ("Hanging leg raise", "Core", "Abs, hip flexors, grip",
                              ["Hanging knee raise 4×6", "Bent-knee raise to chest 4×8",
                               "Straight-leg raise to 90° 4×5",
                               "Toes-to-bar negative 4×3",
                               "Strict toes-to-bar 4×3–8"]),
        "dragon_flag": ("Dragon flag", "Core", "Abs, lats, glutes",
                        ["Reverse crunch 3×12", "Tuck dragon negative 4×3",
                         "One-leg dragon negative 4×2/side",
                         "Straddle dragon negative 4×2",
                         "Dragon flag 4×1–5 clean reps"]),
        "handstand": ("Handstand", "Balance / inversion", "Shoulders, wrists, core, glutes",
                      ["Wrist prep + box plank 3×20 sec",
                       "Box pike hold 4×20 sec", "Chest-to-wall hold 4×20 sec",
                       "Wall weight shifts 4×5/side",
                       "Freestanding balance drills 8×10 sec with clear space"]),
        "handstand_pushup": ("Handstand push-up", "Balance / push",
                             "Shoulders, triceps, upper chest, core",
                             ["Pike push-up 4×8", "Feet-elevated pike 4×6",
                              "Wall handstand hold 5×20 sec",
                              "Abmat partial negative 5×2",
                              "Wall handstand push-up 5×1–5"]),
        "press_handstand": ("Press handstand pathway", "Balance / compression",
                            "Shoulders, abs, hip flexors, wrists",
                            ["Pike shoulder shift 4×10", "Straddle compression lift 4×8",
                             "Elevated straddle press lean 5×5 sec",
                             "Box press negative 4×2",
                             "Wall-assisted straddle press 5×1"]),
        "one_arm_handstand": ("One-arm handstand pathway", "Balance / inversion",
                              "Shoulders, wrists, obliques, core",
                              ["Chest-to-wall handstand 5×30 sec",
                               "Freestanding balance 10×10 sec",
                               "Wall weight shift 5×5/side",
                               "Finger-assisted one-arm lean 6×5 sec/side",
                               "One-arm handstand drills with spotter 6×1"]),
        "front_lever": ("Front lever", "Static hold", "Lats, core, glutes, grip",
                        ["Active hang + scapular depression 4×20 sec",
                         "Tuck front lever 6×8 sec", "Advanced tuck 6×6 sec",
                         "One-leg / straddle lever 6×5 sec",
                         "Full front lever hold 6×3–8 sec"]),
        "front_lever_raise": ("Front lever raise", "Static strength",
                              "Lats, core, rear shoulders",
                              ["Tuck lever hold 5×8 sec", "Tuck lever raise 4×3",
                               "Advanced tuck raise 4×2", "Straddle raise 5×1–3",
                               "Full front lever raise 4×1–3"]),
        "back_lever": ("Back lever", "Static hold", "Chest, shoulders, biceps, core",
                       ["Skin-the-cat mobility 3×3", "Tuck back lever 5×8 sec",
                        "Advanced tuck 5×6 sec", "One-leg / straddle 5×5 sec",
                        "Full back lever 5×3–8 sec"]),
        "planche_lean": ("Planche lean", "Static push", "Wrists, shoulders, chest, core",
                         ["Wrist prep + plank 3×20 sec", "Knee planche lean 5×10 sec",
                          "Tuck lean 5×10 sec", "Advanced lean 6×8 sec",
                          "Planche lean with protraction 6×10 sec"]),
        "planche": ("Planche", "Static hold", "Shoulders, chest, triceps, core",
                    ["Wrist prep + protracted plank 4×20 sec",
                     "Planche lean with feet grounded 4×10 sec",
                     "Frog stand with spotter or padded setup 5×10 sec",
                     "Tuck planche with bands / coach support 5×5 sec",
                     "Advanced tuck progression with qualified spotting 5×3 sec"]),
        "human_flag": ("Human flag", "Static hold", "Obliques, lats, shoulders, grip",
                       ["Side plank 4×30 sec/side", "Vertical pole hold 5×10 sec",
                        "Tuck flag with feet supported 5×5 sec",
                        "One-leg flag 5×3 sec/side",
                        "Straddle / full flag attempts 6×2–5 sec"]),
        "iron_cross": ("Ring iron-cross pathway", "Rings / advanced",
                       "Chest, biceps, shoulders, connective tissue",
                       ["Ring support 5×20 sec", "Band-assisted cross pull 4×5",
                        "Cross hold with feet support 5×5 sec",
                        "Light-band cross hold 6×3 sec",
                        "Coach-supervised assisted cross only"]),
        "crow_pose": ("Crow pose", "Balance", "Wrists, shoulders, core",
                      ["Wrist prep + squat hold 3×30 sec",
                       "Frog stand with toes down 5×10 sec",
                       "Crow weight shift 5×5",
                       "Crow hold 5×10 sec", "Crow pose 5×20 sec"]),
        "elbow_lever": ("Elbow lever", "Balance / core", "Core, wrists, shoulders",
                        ["Wrist prep + crow lean 4×10 sec",
                         "Elbow placement with feet grounded 5×10 sec",
                         "Tuck lever with spotter 5×5 sec",
                         "Straddle lever 5×5 sec",
                         "Elbow lever hold 5×8–15 sec"]),
        "pistol_squat": ("Pistol squat", "Legs", "Quads, glutes, ankles, core",
                         ["Supported single-leg sit 3×8/side",
                          "Box pistol to high target 4×5/side",
                          "Counterbalanced pistol 4×4/side",
                          "Full pistol negative 4×3/side",
                          "Pistol squat 4×3–8/side"]),
        "shrimp_squat": ("Shrimp squat", "Legs", "Quads, glutes, balance",
                         ["Split squat 3×10/side", "Supported rear-foot squat 4×6",
                          "Assisted shrimp squat 4×5/side",
                          "Shrimp squat negative 4×3/side",
                          "Shrimp squat 4×4–8/side"]),
        "nordic_curl": ("Nordic hamstring curl", "Legs", "Hamstrings, glutes, core",
                        ["Hip hinge 3×12", "Partner-assisted short range 4×5",
                         "Band-assisted negative 4×3",
                         "Slow negative to padded catch 4×3",
                         "Nordic curl 4×3–6"]),
        "sissy_squat": ("Sissy squat", "Legs", "Quads, knees, core",
                        ["Wall-supported knee travel 3×8",
                         "Assisted sissy squat partial 4×6",
                         "Full-range assisted 4×6",
                         "Bodyweight negative 4×4",
                         "Sissy squat 4×5–10"]),
        "box_jump": ("Box jump", "Power / legs", "Quads, glutes, calves",
                     ["Snap-down landing drill 4×3", "Low step jump 5×3",
                      "Low box jump 5×3", "Moderate box jump 6×2",
                      "Repeat crisp jumps; step down between reps"]),
        "skin_the_cat": ("Skin the cat", "Rings / mobility", "Shoulders, lats, core",
                         ["Active hang 4×20 sec", "Tuck inverted hang 4×10 sec",
                          "Feet-assisted rotation 4×3",
                          "Controlled tuck skin-the-cat 4×2",
                          "Skin-the-cat to comfortable German hang 3×2"]),
        "ring_support": ("Ring support", "Rings / stability", "Shoulders, triceps, core",
                         ["Feet-assisted support 5×15 sec", "Ring turnout hold 5×10 sec",
                          "Unassisted support 5×15 sec",
                          "Ring support with small lean 5×10 sec",
                          "Stable turned-out support 5×20 sec"]),
        "bridge": ("Bridge", "Mobility", "Glutes, back, shoulders",
                   ["Thoracic extension + glute bridge 3×10",
                    "Elevated bridge hold 4×15 sec", "Floor bridge hold 4×15 sec",
                    "Bridge rocks 3×8", "Wall walk-down/up with spotter 4×2"]),
        "middle_split": ("Middle split pathway", "Mobility", "Adductors, hips",
                         ["Adductor rock-back 3×10", "Supported wide squat 4×30 sec",
                          "Frog stretch 4×30 sec", "Supported split hold 5×20 sec",
                          "Relaxed middle split hold 5×30 sec"]),
        "front_split": ("Front split pathway", "Mobility", "Hip flexors, hamstrings",
                        ["Half-kneeling hip-flexor stretch 3×30 sec/side",
                         "Hamstring hinge stretch 3×30 sec/side",
                         "Supported lunge split 4×20 sec/side",
                         "Blocks-supported split 5×20 sec",
                         "Front split hold 5×30 sec/side"]),
    }
    phases = ("Foundation", "Regression", "Assisted range", "Full variation",
              "Quality / volume")
    result = {}
    for skill_id, (name, category, muscles, drills) in catalog.items():
        result[skill_id] = {
            "skill_name": name, "category": category,
            "target_muscles": muscles,
            "steps": [
                (f"{phases[index]} • {drills[index]}",
                 f"{drills[index]}. Complete 3–5 sets with clean control; rest 60–180 seconds. "
                 "Stop if you feel sharp pain; use a safe setup and scale the range.",
                 muscles)
                for index in range(5)
            ],
        }
    return result


class Card(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        rounded(self, CARD, 18, True)
        self.padding = dp(14)


class MuscleMap(Widget):
    """Simple illustrative focus map; it is not a medical or AI assessment."""
    def __init__(self, muscle_text="", **kwargs):
        super().__init__(**kwargs)
        self.focus = str(muscle_text).lower()
        self.size_hint_y = None
        self.height = dp(180)
        self.bind(pos=self.redraw, size=self.redraw)
        Clock.schedule_once(self.redraw, 0)

    def redraw(self, *_):
        self.canvas.clear()
        width, height = self.width, self.height
        if width <= 0 or height <= 0:
            return
        scale = min(width / dp(170), height / dp(180))
        cx = self.center_x
        base = self.y + (height - dp(180) * scale) / 2
        neutral = get_color_from_hex(CARD2)
        active = get_color_from_hex(ACCENT)

        def rect(color, x, y, w, h, radius=4):
            Color(*color)
            RoundedRectangle(pos=(cx + x * scale, base + y * scale),
                             size=(w * scale, h * scale),
                             radius=[dp(radius) * scale])

        def ellipse(color, x, y, w, h):
            Color(*color)
            Ellipse(pos=(cx + x * scale, base + y * scale),
                    size=(w * scale, h * scale))

        def line(color, points, line_width=10):
            Color(*color)
            Line(points=[(cx + x * scale, base + y * scale)
                         for x, y in points],
                 width=dp(line_width) * scale)

        with self.canvas:
            ellipse(neutral, -13, 148, 26, 27)  # head
            rect(neutral, -7, 138, 14, 10)      # neck
            rect(neutral, -23, 77, 46, 61, 10)  # torso
            line(neutral, [(-20, 130), (-37, 105), (-42, 80)], 11)
            line(neutral, [(20, 130), (37, 105), (42, 80)], 11)
            line(neutral, [(-11, 78), (-14, 44), (-17, 6)], 13)
            line(neutral, [(11, 78), (14, 44), (17, 6)], 13)

            focus = self.focus
            if any(word in focus for word in ("chest", "pectoral")):
                rect(active, -18, 111, 36, 17, 5)
            if any(word in focus for word in ("shoulder", "deltoid")):
                ellipse(active, -29, 125, 18, 16)
                ellipse(active, 11, 125, 18, 16)
            if any(word in focus for word in
                   ("triceps", "biceps", "forearm", "arm")):
                line(active, [(-20, 130), (-37, 105), (-42, 80)], 7)
                line(active, [(20, 130), (37, 105), (42, 80)], 7)
            if any(word in focus for word in ("core", "ab", "hip flexor")):
                rect(active, -15, 83, 30, 25, 5)
            if any(word in focus for word in ("quad", "leg", "glute")):
                line(active, [(-11, 78), (-14, 44), (-17, 6)], 8)
                line(active, [(11, 78), (14, 44), (17, 6)], 8)
            if any(word in focus for word in ("lat", "back", "trapezius")):
                rect(active, -20, 91, 40, 18, 5)


class BaseScreen(Screen):
    def nav(self, active="HOME"):
        nav = BoxLayout(size_hint_y=None, height=dp(66), spacing=dp(5),
                        padding=[0, dp(7), 0, dp(7)])
        options = [
            ("H", "HOME", "home"), ("S", "SKILLS", "skills"),
            ("E", "EXPLORE", "explore"), ("P", "PROFILE", "profile"),
        ]
        for symbol, name, screen in options:
            button = pill_button(
                f"{symbol}  {name}", lambda _, target=screen:
                setattr(self.manager, "current", target),
                ACCENT if name == active else CARD2, 48)
            button.font_size = dp(10)
            nav.add_widget(button)
        return nav

    def popup(self, title, message, action_text="CLOSE", callback=None):
        box = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(12))
        scroll = ScrollView(do_scroll_x=False)
        message_label = label(message, 14, TEXT, False, "left")
        message_label.size_hint_y = None
        message_label.bind(
            texture_size=lambda inst, value: setattr(inst, "height", value[1]))
        scroll.add_widget(message_label)
        box.add_widget(scroll)
        button = pill_button(action_text, callback, ACCENT, 46)
        box.add_widget(button)
        pop = Popup(title=title, content=box, size_hint=(.9, .68),
                    background_color=get_color_from_hex(CARD))
        if callback is None:
            button.bind(on_release=pop.dismiss)
        self._popup = pop
        pop.open()
        return pop

    def form_popup(self, title, fields, action, on_save, size=.72):
        box = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(8))
        controls = {}
        for key, hint, initial in fields:
            control = text_field(hint, initial)
            controls[key] = control
            box.add_widget(control)
        status = label("", 10, MUTED)
        box.add_widget(status)
        button = pill_button(action, None, ACCENT, 46)
        box.add_widget(button)
        pop = Popup(title=title, content=box, size_hint=(.9, size),
                    background_color=get_color_from_hex(CARD))

        def save(*_):
            if on_save({key: control.text.strip() for key, control in controls.items()},
                       status, pop) is not False:
                pop.dismiss()

        button.bind(on_release=save)
        self._popup = pop
        pop.open()
        return pop


class LoginScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical",
                         padding=[dp(28), dp(50), dp(28), dp(28)],
                         spacing=dp(14))
        root.add_widget(BoxLayout(size_hint_y=.22))
        root.add_widget(label("GRAVIX", 38, ACCENT, True, "center"))
        root.add_widget(label("MASTER YOUR BODY.", 13, MUTED, True, "center"))
        self.username = text_field("Email address", height=52)
        self.display_name = text_field("Display name (new accounts)", height=46)
        self.password = text_field("Password", height=52)
        self.password.password = True
        root.add_widget(self.username)
        root.add_widget(self.display_name)
        root.add_widget(self.password)
        self.status = label("", 12, MUTED, False, "center")
        root.add_widget(self.status)
        root.add_widget(pill_button("ENTER GRAVIX", self.login, ACCENT, 54))
        root.add_widget(pill_button("CREATE ACCOUNT", self.register, CARD2, 50))
        root.add_widget(label("TRAIN • PROGRESS • COMPETE • CONQUER",
                              10, MUTED, True, "center"))
        self.add_widget(root)

    def login(self, *_):
        app = App.get_running_app()
        if app.session_restore_pending:
            self.status.text = clean_markup("Checking your saved login. Please wait.")
            return
        email = self.username.text.strip().lower()
        password = self.password.text.strip()
        if not email or not password:
            self.status.text = clean_markup("Enter your email and password.")
            return
        try:
            app.auth.sign_in(email, password)
            app.current_user = app.auth.uid
            app.current_email = app.auth.email or email
            user = safe_get(f"users/{app.current_user}/profile", {}) or {}
            app.current_display_name = user.get(
                "display_name", app.current_email.split("@")[0])
            if not initialize_user_profile(
                    app.current_user, app.current_email, app.current_display_name):
                raise ValueError(
                    "Could not create your profile. Check Firebase Database Rules.")
            self.password.text = ""
            app.start_step_tracking()
            self.manager.current = "home"
        except ValueError as exc:
            self.status.text = clean_markup(str(exc))

    def register(self, *_):
        app = App.get_running_app()
        if app.session_restore_pending:
            self.status.text = clean_markup("Checking your saved login. Please wait.")
            return
        email = self.username.text.strip().lower()
        display_name = self.display_name.text.strip()
        password = self.password.text.strip()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            self.status.text = clean_markup("Enter a valid email address.")
            return
        if len(password) < 8:
            self.status.text = clean_markup("Password must be at least 8 characters.")
            return
        if not display_name:
            display_name = email.split("@")[0]
        display_name = display_name[:50]
        try:
            result = app.auth.sign_up(email, password)
            app.current_user = result["localId"]
            app.current_email = result.get("email", email)
            app.current_display_name = display_name or email.split("@")[0]
            if initialize_user_profile(
                    app.current_user, app.current_email, app.current_display_name):
                safe_patch(f"public_profiles/{app.current_user}", {
                    "display_name": app.current_display_name,
                })
            else:
                raise ValueError(
                    "Account created, but profile setup failed. Check Firebase Database Rules.")
            self.password.text = ""
            app.start_step_tracking()
            self.manager.current = "home"
        except ValueError as exc:
            self.status.text = clean_markup(str(exc))


class HomeScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._load_id = 0
        root = BoxLayout(orientation="vertical")
        root.padding = [dp(14), dp(16), dp(14), 0]
        scroll = ScrollView(do_scroll_x=False)
        self.content = BoxLayout(orientation="vertical", spacing=dp(11),
                                 size_hint_y=None)
        self.content.bind(minimum_height=self.content.setter("height"))
        header = BoxLayout(size_hint_y=None, height=dp(50))
        self.greeting = label("GRAVIX  /  HUNTER", 15, GREEN, True)
        header.add_widget(self.greeting)
        header.add_widget(pill_button("LOG OUT", self.logout, CARD2, 38))
        self.content.add_widget(header)

        hero = Card(orientation="vertical", size_hint_y=None, height=dp(152),
                    spacing=dp(5))
        row = BoxLayout(size_hint_y=None, height=dp(32))
        self.level_label = label("AWAKENING  /  LEVEL 0", 19, TEXT, True)
        self.xp_label = label("0 XP", 12, GOLD, True, "right")
        row.add_widget(self.level_label)
        row.add_widget(self.xp_label)
        hero.add_widget(row)
        self.xp_bar = ProgressBar(max=100, value=0,
                                  size_hint_y=None, height=dp(8))
        hero.add_widget(self.xp_bar)
        self.hero_text = label("YOUR NEXT RANK STARTS WITH ONE QUEST.", 11, GREEN, True)
        hero.add_widget(self.hero_text)
        self.content.add_widget(hero)

        mission = Card(orientation="vertical", size_hint_y=None, height=dp(148),
                       spacing=dp(6))
        mission.add_widget(label("DAILY QUEST  /  WARRIOR ATHLETE", 11, GOLD, True))
        mission.add_widget(label("BUILD YOUR BASE", 21, TEXT, True))
        mission.add_widget(label(
            "Train with control, record your work, and keep your streak alive.",
            11, MUTED))
        mission.add_widget(pill_button("CLEAR TODAY'S QUEST", self.complete_workout,
                                       ACCENT, 44))
        self.content.add_widget(mission)

        self.quick = GridLayout(cols=2, spacing=dp(8), size_hint_y=None,
                                row_default_height=dp(84))
        self.quick.bind(minimum_height=self.quick.setter("height"))
        self.content.add_widget(self.quick)
        tracker = Card(orientation="vertical", size_hint_y=None, height=dp(146),
                       spacing=dp(6))
        tracker.add_widget(label("DAILY TRACKER", 13, TEXT, True))
        self.today_stats = label("0 min • 0 steps • 0 kcal", 12, MUTED, True)
        tracker.add_widget(self.today_stats)
        tracker.add_widget(pill_button("LOG STEPS / CALORIES", self.log_activity,
                                       CARD2, 40))
        tracker.add_widget(pill_button(
            "OPEN STEP QUEST  /  24H", lambda *_: setattr(
                self.manager, "current", "steps"), GREEN, 40))
        self.content.add_widget(tracker)

        challenge = Card(orientation="vertical", size_hint_y=None, height=dp(118),
                         spacing=dp(6))
        challenge.add_widget(label("WORLD GATE  /  WEEKLY CHALLENGE", 12, GOLD, True))
        challenge.add_widget(label("Train skills. Earn rank points. Join the guild.",
                                   10, MUTED))
        challenge.add_widget(pill_button("ENTER WORLD QUESTS", self.challenges,
                                         ACCENT, 40))
        self.content.add_widget(challenge)
        scroll.add_widget(self.content)
        root.add_widget(scroll)
        root.add_widget(self.nav("HOME"))
        self.add_widget(root)

    def on_enter(self):
        self._load_id += 1
        load_id = self._load_id
        username = App.get_running_app().current_user or ""

        def load():
            user = read_user()
            activities = safe_get(f"users/{username}/activity", {}) or {}
            Clock.schedule_once(lambda _dt: self._apply_home(
                load_id, user, activities), 0)

        threading.Thread(target=load, daemon=True).start()

    def refresh(self):
        self.on_enter()

    def _apply_home(self, load_id, user, activities):
        if load_id != self._load_id or self.manager.current != "home":
            return
        user = user if isinstance(user, dict) else {}
        activities = activities if isinstance(activities, dict) else {}
        days = activity_map(activities)
        level, xp = int(user.get("level", 0)), int(user.get("xp", 0))
        needed = 100 + level * 50
        display_name = getattr(App.get_running_app(), "current_display_name", "")
        self.greeting.text = clean_markup(
            f"GRAVIX  /  {(display_name or 'HUNTER').upper()}")
        self.level_label.text = clean_markup(f"AWAKENING  /  LEVEL {level}")
        self.xp_label.text = clean_markup(f"{xp} / {needed} XP")
        self.xp_bar.max, self.xp_bar.value = needed, xp
        today_records = [r for r in activities.values()
                         if isinstance(r, dict) and r.get("date") == today_key()]
        minutes = sum(int(r.get("workout_minutes", 0)) +
                      int(r.get("skill_minutes", 0)) for r in today_records)
        today_steps = sum(int(r.get("steps", 0)) for r in today_records)
        today_calories = sum(int(r.get("calories", 0)) for r in today_records)
        self.today_stats.text = clean_markup(
            f"{minutes} min • {today_steps} steps • {today_calories} kcal")
        streak = current_streak(days)
        self.hero_text.text = clean_markup(
            f"STREAK {streak} DAYS • {user.get('completed_workouts', 0)} WORKOUTS")
        self.quick.clear_widgets()
        for title, value in [
            ("SKILL TIME", f"{user.get('skill_minutes', 0)} min"),
            ("ACHIEVEMENTS", user.get("achievements", 0)),
            ("RANK POINTS", user.get("rank_points", 0)),
            ("ACTIVE DAYS", len(days)),
        ]:
            tile = Card(orientation="vertical", size_hint_y=None,
                        height=dp(78), spacing=dp(3))
            tile.add_widget(label(title, 9, MUTED, True))
            tile.add_widget(label(str(value), 18, TEXT, True))
            self.quick.add_widget(tile)

    def complete_workout(self, *_):
        def save(values, status, popup):
            try:
                minutes = max(0, int(values["minutes"] or 0))
                steps = max(0, int(values["steps"] or 0))
                calories = max(0, int(values["calories"] or 0))
            except ValueError:
                status.text = clean_markup("Enter whole numbers for each field.")
                return False
            if not record_activity("workout", {
                "workout_minutes": minutes, "steps": steps, "calories": calories,
                "completed_workouts": 1, "rank_points": 25,
                "description": "Workout completed",
            }):
                status.text = clean_markup("Could not save. Check your connection.")
                return False
            self.refresh()
            self.popup("SESSION SAVED",
                       f"{minutes} minutes • {steps} steps • {calories} kcal\n"
                       "Server scoring is applied to your GRAVIX record.")
        self.form_popup("LOG TODAY'S WORKOUT", [
            ("minutes", "Workout minutes", "30"),
            ("steps", "Steps completed (optional)", "0"),
            ("calories", "Calories burned (optional)", "0"),
        ], "SAVE WORKOUT", save)

    def log_activity(self, *_):
        def save(values, status, popup):
            try:
                steps = max(0, int(values["steps"] or 0))
                calories = max(0, int(values["calories"] or 0))
                minutes = max(0, int(values["minutes"] or 0))
            except ValueError:
                status.text = clean_markup("Enter whole numbers for each field.")
                return False
            if not record_activity("daily_tracker", {
                "steps": steps, "calories": calories, "skill_minutes": minutes,
                "description": "Manual activity log",
            }):
                status.text = clean_markup("Could not save. Check your connection.")
                return False
            self.refresh()
            self.popup("TRACKER UPDATED", "Your activity was added to your daily record.")
        self.form_popup("LOG DAILY ACTIVITY", [
            ("steps", "Steps since last log", "0"),
            ("calories", "Calories burned since last log", "0"),
            ("minutes", "Skill / exercise minutes", "0"),
        ], "SAVE ACTIVITY", save)

    def challenges(self, *_): self.manager.current = "challenges"
    def nutrition(self, *_): self.manager.current = "nutrition"
    def athletes(self, *_): self.manager.current = "athletes"
    def academies(self, *_): self.manager.current = "academies"
    def store(self, *_): self.manager.current = "store"
    def glowup(self, *_): self.manager.current = "glowup"
    def logout(self, *_):
        app = App.get_running_app()
        app.stop_step_tracking()
        app.auth.clear()
        app.current_user = None
        app.current_email = None
        app.current_display_name = None
        self.manager.current = "login"


class ExploreScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical",
                         padding=[dp(13), dp(10), dp(13), 0], spacing=dp(8))
        title = label("THE HUNTER GATE", 21, TEXT, True)
        title.size_hint_y = None
        title.height = dp(34)
        root.add_widget(title)
        subtitle = label("Choose your next mission.", 11, MUTED)
        subtitle.size_hint_y = None
        subtitle.height = dp(22)
        root.add_widget(subtitle)
        banner = Card(orientation="vertical", size_hint_y=None,
                      height=dp(83), spacing=dp(3))
        banner.add_widget(label("GRAVIX FIELD MAP  /  RANK UP", 13, GOLD, True))
        banner.add_widget(label(
            "Training, community, recovery and daily records — one tap away.",
            10, TEXT))
        root.add_widget(banner)
        scroll = ScrollView(do_scroll_x=False)
        grid = GridLayout(cols=2, spacing=dp(9), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        entries = [
            ("STR", "TRAINING ARC", "Build a weekly program", "program"),
            ("MAP", "DOJO MAP", "Find a nearby academy", "academies"),
            ("PVP", "WORLD QUEST", "Join global challenges", "challenges"),
            ("GUILD", "GUILD HALL", "Meet coaches and athletes", "athletes"),
            ("FUEL", "BATTLE FUEL", "Explore meal plans", "nutrition"),
            ("GEAR", "GEAR VAULT", "Browse training gear", "store"),
            ("REC", "RECOVERY RITUAL", "Build daily habits", "glowup"),
            ("TIME", "DAILY SIGNAL", "Set a workout reminder", "reminders"),
            ("LOG", "HUNTER RECORD", "Review training history", "profile"),
            ("STEP", "STEP QUEST", "Track phone steps", "steps"),
        ]
        for code, name, description, screen in entries:
            button = Button(
                text=f"{code}   /   {name}\n{description}\n\nOPEN MISSION  >",
                size_hint_y=None, height=dp(122),
                background_normal="", background_down="",
                background_color=get_color_from_hex(CARD2),
                color=get_color_from_hex(TEXT), bold=True, font_size=dp(10),
                halign="left", valign="middle", padding=[dp(12), dp(8)])
            button.bind(size=lambda inst, value: setattr(
                inst, "text_size", (value[0] - dp(22), value[1] - dp(14))))
            button.bind(on_release=lambda _, target=screen:
                        setattr(self.manager, "current", target))
            grid.add_widget(button)
        scroll.add_widget(grid)
        root.add_widget(scroll)
        root.add_widget(self.nav("EXPLORE"))
        self.add_widget(root)


class SkillsScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._load_id = 0
        self.skill_progress = {}
        root = BoxLayout(orientation="vertical",
                         padding=[dp(13), dp(10), dp(13), 0], spacing=dp(7))
        title = label("HUNTER'S QUEST BOARD", 21, TEXT, True)
        title.size_hint_y = None
        title.height = dp(34)
        root.add_widget(title)
        subtitle = label("Train a skill. Clear its stages. Rank up.", 11, MUTED)
        subtitle.size_hint_y = None
        subtitle.height = dp(22)
        root.add_widget(subtitle)
        self.quest_banner = Card(orientation="vertical", size_hint_y=None,
                                 height=dp(94), spacing=dp(4))
        self.quest_banner.add_widget(label(
            "WOMEN'S STRENGTH QUEST  /  LOWER BODY + CORE", 12, GOLD, True))
        self.quest_banner.add_widget(label(
            "Glute bridges • split squats • hip hinges • side planks. "
            "Scalable strength missions for every athlete.", 10, TEXT))
        root.add_widget(self.quest_banner)
        scroll = ScrollView(do_scroll_x=False)
        self.grid = GridLayout(cols=1, spacing=dp(9), size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter("height"))
        scroll.add_widget(self.grid)
        root.add_widget(scroll)
        root.add_widget(self.nav("SKILLS"))
        self.add_widget(root)

    def on_enter(self):
        self._load_id += 1
        load_id = self._load_id
        self.skill_progress = {}
        self._render_skills(0, {}, self.skill_progress)
        username = App.get_running_app().current_user

        def load():
            user = read_user()
            remote = safe_get("skills", {}) or {}
            progress = safe_get(
                f"users/{username}/skill_progress", {}) or {}
            Clock.schedule_once(lambda _dt: self._apply_loaded_skills(
                load_id, user, remote, progress), 0)

        threading.Thread(target=load, daemon=True).start()

    def _apply_loaded_skills(self, load_id, user, remote, progress):
        if load_id != self._load_id or self.manager.current != "skills":
            return
        self.skill_progress = progress if isinstance(progress, dict) else {}
        try:
            level = int(user.get("level", 0)) if isinstance(user, dict) else 0
        except (TypeError, ValueError):
            level = 0
        self._render_skills(level, remote, self.skill_progress)

    def _render_skills(self, level, remote, progress_map):
        self.grid.clear_widgets()
        skills = catalog_skills()
        featured = ["one_arm_pullup", "planche", "handstand"]
        strength = ["glute_bridge", "split_squat", "hip_hinge", "side_plank", "dead_bug"]
        for sid, item in (remote.items() if isinstance(remote, dict) else []):
            if isinstance(item, dict):
                sid = re.sub(r"[^a-zA-Z0-9_-]", "_", sid)
                if sid not in featured:
                    skills[sid] = item
        ordered = ([(sid, skills[sid]) for sid in featured if sid in skills] +
                   [(sid, skills[sid]) for sid in strength if sid in skills] +
                   [(sid, skill) for sid, skill in skills.items()
                    if sid not in set(featured + strength)])
        section = label("FEATURED HUNTER MISSIONS", 12, GREEN, True)
        section.size_hint_y = None
        section.height = dp(25)
        self.grid.add_widget(section)
        for index, (sid, skill) in enumerate(ordered):
            if index == len(featured):
                section = label("STRENGTH PATH  /  GLUTES • LEGS • CORE", 12, GOLD, True)
                section.size_hint_y = None
                section.height = dp(27)
                self.grid.add_widget(section)
            if index == len(featured) + len(strength):
                section = label("ALL SKILL MISSIONS", 12, GREEN, True)
                section.size_hint_y = None
                section.height = dp(27)
                self.grid.add_widget(section)
            progress = progress_map.get(sid, {}) if isinstance(progress_map, dict) else {}
            try:
                step = int(progress.get("step", 0)) if isinstance(progress, dict) else 0
            except (TypeError, ValueError):
                step = 0
            pct = 100 if isinstance(progress, dict) and progress.get(
                "review_status") == "approved" else min(max(step, 0) * 20, 80)
            name = skill.get("skill_name", sid.replace("_", " ").title())
            try:
                required_level = int(skill.get("required_level", 0))
            except (TypeError, ValueError):
                required_level = 0
            unlocked = level >= required_level
            stage_label = "CLEARED" if pct == 100 else f"STAGE {min(step + 1, 5)}/5"
            item = Card(orientation="vertical", size_hint_y=None,
                        height=dp(136), spacing=dp(5))
            row = BoxLayout(size_hint_y=None, height=dp(31), spacing=dp(5))
            row.add_widget(label(name.upper(), 16, TEXT, True))
            row.add_widget(label(
                f"{stage_label}  •  {pct}%", 10,
                GREEN if pct == 100 else GOLD, True, "right"))
            item.add_widget(row)
            item.add_widget(label(
                f"TARGET  /  {skill.get('target_muscles', 'Full body')}", 10, MUTED))
            item.add_widget(ProgressBar(max=100, value=pct,
                                        size_hint_y=None, height=dp(7)))
            item.add_widget(pill_button(
                "OPEN MISSION BRIEFING" if unlocked else f"UNLOCK AT LEVEL {required_level}",
                (lambda _, skill_id=sid, data=dict(skill), saved=dict(progress):
                 self.show_skill(skill_id, data, saved)) if unlocked else None,
                ACCENT if unlocked else LOCKED, 40))
            self.grid.add_widget(item)

    def show_skill(self, sid, skill, progress=None):
        progress = progress if isinstance(progress, dict) else {}
        current = int(progress.get("step", 0))
        approved = progress.get("review_status") == "approved"
        steps = skill.get("steps")
        if not steps:
            steps = [(item, "Follow the exercise instructions provided by your coach.",
                      skill.get("target_muscles", "Full body"))
                     for item in skill.get("progression", [
                         "Foundation", "Technique", "Control", "Consistency", "Mastery"
                     ])]
        steps = [
            stage if isinstance(stage, (list, tuple)) and len(stage) >= 3
            else (str(stage), "Follow the exercise instructions provided by your coach.",
                  skill.get("target_muscles", "Full body"))
            for stage in steps
        ]
        steps = list(steps)[:5]
        while len(steps) < 5:
            steps.append(("Practice", "Repeat with controlled technique.",
                          skill.get("target_muscles", "Full body")))
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(7))
        heading = label(f"MISSION  /  {skill.get('skill_name', sid).upper()}",
                         16, TEXT, True)
        heading.size_hint_y = None
        heading.height = dp(30)
        box.add_widget(heading)
        progress_label = label(
            f"TARGET  /  {skill.get('target_muscles', 'Full body')}    •    "
            f"PROGRESS  /  {'100%' if approved else min(current * 20, 80)}%",
            10, GOLD, True)
        progress_label.size_hint_y = None
        progress_label.height = dp(25)
        box.add_widget(progress_label)
        scroll = ScrollView(do_scroll_x=False)
        stages = BoxLayout(orientation="vertical", spacing=dp(7),
                           size_hint_y=None)
        stages.bind(minimum_height=stages.setter("height"))
        for index, stage in enumerate(steps):
            name, instructions, muscles = stage
            completed = index < current or approved
            stage_card = Card(orientation="vertical", size_hint_y=None,
                              height=dp(126), spacing=dp(4))
            stage_card.add_widget(label(
                f"{'CLEARED' if completed else 'STAGE'}  {index + 1}  /  5  "
                f"•  {(index + 1) * 20}%", 10,
                GREEN if completed else GOLD, True))
            stage_card.add_widget(label(str(name), 13, TEXT, True))
            stage_card.add_widget(label(
                f"{instructions}\nFOCUS  /  {muscles}", 10, MUTED))
            stages.add_widget(stage_card)
        scroll.add_widget(stages)
        box.add_widget(scroll)
        box.add_widget(MuscleMap(skill.get("target_muscles", "")))
        box.add_widget(pill_button(
            "LOG 15 MIN PRACTICE",
            lambda *_: self.log_practice(sid), CARD2, 40))
        if current < 4 and not approved:
            box.add_widget(pill_button(
                f"COMPLETE STEP {current + 1} (+20%)",
                lambda *_: self.complete_step(sid, current), ACCENT, 40))
        elif current >= 4 and not approved:
            box.add_widget(pill_button(
                "SUBMIT FINAL-STEP VIDEO LINK",
                lambda *_: self.submit_video(sid), ACCENT, 40))
        pop = Popup(title="HUNTER MISSION BRIEFING", content=box, size_hint=(.94, .88),
                    background_color=get_color_from_hex(CARD))
        self._popup = pop
        pop.open()

    def log_practice(self, sid):
        username = App.get_running_app().current_user
        if not record_activity("skill_practice", {
            "skill_id": sid, "skill_minutes": 15,
            "description": f"Practiced {sid}",
        }):
            self.popup("PRACTICE NOT SAVED", "Could not save the practice to your account. Check the connection and Firebase Functions setup.")
            return
        safe_post(f"users/{username}/skill_logs/{sid}", {
            "date": today_key(), "minutes": 15, "timestamp": datetime.datetime.now().isoformat(),
        })
        if self._popup:
            self._popup.dismiss()
        self.popup("PRACTICE RECORDED", "+15 skill minutes • +10 rank points")

    def complete_step(self, sid, current):
        username = App.get_running_app().current_user
        next_step = min(current + 1, 4)
        safe_patch(f"users/{username}/skill_progress/{sid}", {
            "step": next_step, "review_status": "not_submitted",
            "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        })
        if self._popup:
            self._popup.dismiss()
        self.on_enter()

    def submit_video(self, sid):
        username = App.get_running_app().current_user

        def save(values, status, popup):
            video = values.get("video", "")
            if not video.startswith(("https://", "http://")):
                status.text = clean_markup("Enter a shareable video URL.")
                return False
            safe_patch(f"users/{username}/skill_progress/{sid}", {
                "step": 4, "review_status": "pending",
                "video_url": video, "submitted_at": datetime.datetime.now().isoformat(),
            })
            safe_post(f"users/{username}/video_submissions", {
                "skill_id": sid, "video_url": video,
                "status": "pending", "submitted_at": datetime.datetime.now().isoformat(),
            })
            if self._popup:
                self._popup.dismiss()
            self.on_enter()
            self.popup("VIDEO SUBMITTED",
                       "Your link is saved as pending review. AI form analysis must be connected before it can verify the final step.")
        self.form_popup("FINAL SKILL VIDEO", [
            ("video", "Shareable video link", ""),
        ], "SUBMIT FOR REVIEW", save, .45)


class ProfileScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._load_id = 0
        self.user_data = {}
        self.activities = {}
        self.calendar_month = datetime.date.today().replace(day=1)
        root = BoxLayout(orientation="vertical",
                         padding=[dp(10), dp(8), dp(10), 0], spacing=dp(5))
        title = label("HUNTER PROFILE", 21, TEXT, True)
        title.size_hint_y = None
        title.height = dp(34)
        root.add_widget(title)
        subtitle = label("Your record. Your next rank.", 10, MUTED)
        subtitle.size_hint_y = None
        subtitle.height = dp(20)
        root.add_widget(subtitle)
        scroll = ScrollView(do_scroll_x=False)
        self.body = BoxLayout(orientation="vertical", spacing=dp(8),
                              padding=[dp(4), dp(5), dp(4), dp(8)],
                              size_hint_y=None)
        self.body.bind(minimum_height=self.body.setter("height"))
        self.profile_card = Card(orientation="vertical", size_hint_y=None,
                                 height=dp(286), spacing=dp(5))
        self.body.add_widget(self.profile_card)
        self.body.add_widget(self._section_title("COMPLETE TRAINING RECORD"))
        self.record_grid = GridLayout(cols=2, spacing=dp(7), size_hint_y=None)
        self.record_grid.bind(minimum_height=self.record_grid.setter("height"))
        self.body.add_widget(self.record_grid)
        self.body.add_widget(self._section_title("MONTHLY TRAINING CALENDAR"))
        self.calendar_card = Card(orientation="vertical", size_hint_y=None,
                                  height=dp(370), spacing=dp(5))
        self.body.add_widget(self.calendar_card)
        self.body.add_widget(self._section_title("ACHIEVEMENTS & RECENT RECORDS"))
        self.achievements = Card(orientation="vertical", size_hint_y=None,
                                 height=dp(170), spacing=dp(5))
        self.body.add_widget(self.achievements)
        self.body.add_widget(pill_button("CHOOSE PHOTO OR ANIME CREST",
                                         self.choose_avatar, CARD2, 46))
        creator = pill_button("OPEN GUILD HALL", self.creator_info, CARD2, 44)
        self.body.add_widget(creator)
        self.body.add_widget(pill_button("EDIT PROFILE & AVATAR", self.edit_profile,
                                         ACCENT, 46))
        scroll.add_widget(self.body)
        root.add_widget(scroll)
        root.add_widget(self.nav("PROFILE"))
        self.add_widget(root)

    @staticmethod
    def _section_title(text):
        heading = label(text, 13, GREEN, True)
        heading.size_hint_y = None
        heading.height = dp(26)
        return heading

    def on_enter(self):
        self._load_id += 1
        load_id = self._load_id
        username = App.get_running_app().current_user

        def load():
            user = read_user()
            activities = safe_get(f"users/{username}/activity", {}) or {}
            achievement_data = safe_get(
                f"users/{username}/achievements", {}) or {}
            Clock.schedule_once(lambda _dt: self._apply_profile(
                load_id, user, activities, achievement_data), 0)

        threading.Thread(target=load, daemon=True).start()

    def _apply_profile(self, load_id, user, activities, achievement_data):
        if load_id != self._load_id or self.manager.current != "profile":
            return
        self.user_data = user if isinstance(user, dict) else {}
        self.activities = activities if isinstance(activities, dict) else {}
        self.achievement_data = (achievement_data
                                 if isinstance(achievement_data, dict) else {})
        self._render_profile()

    def _render_profile(self):
        self.profile_card.clear_widgets()
        self.record_grid.clear_widgets()
        self.achievements.clear_widgets()
        username = App.get_running_app().current_user
        user = self.user_data
        activities = self.activities
        days = activity_map(activities)
        avatar_row = BoxLayout(size_hint_y=None, height=dp(94), spacing=dp(12))
        avatar_box = Card(orientation="vertical", size_hint=(None, None),
                          width=dp(78), height=dp(78), padding=dp(3))
        local_avatar, crest = self._local_avatar(username)
        remote_avatar = user.get("avatar_url", "")
        avatar_source = local_avatar or (
            remote_avatar if remote_avatar.startswith(("https://", "http://"))
            else "")
        if avatar_source:
            avatar_box.add_widget(AsyncImage(
                source=avatar_source, allow_stretch=True, keep_ratio=True))
        else:
            crest_marks = {"NOVA": "N", "EMBER": "E", "VOLT": "V", "SHADE": "S"}
            crest_colors = {"NOVA": GREEN, "EMBER": GOLD,
                            "VOLT": "#60A5FA", "SHADE": "#C084FC"}
            mark = label(crest_marks.get(crest, "G"), 30,
                         crest_colors.get(crest, GREEN), True, "center")
            avatar_box.add_widget(mark)
        avatar_row.add_widget(avatar_box)
        display_name = user.get(
            "display_name",
            getattr(App.get_running_app(), "current_display_name", "ATHLETE"))
        identity = BoxLayout(orientation="vertical", spacing=dp(2))
        identity.add_widget(label(f"GRAVIX  /  {crest}", 10, ACCENT, True))
        identity.add_widget(label(
            f"{display_name.upper()}  •  LEVEL {user.get('level', 0)}",
            17, TEXT, True))
        identity.add_widget(label(
            f"RANK  /  {user.get('rank', 'AWAKENING')}", 10, GREEN, True))
        avatar_row.add_widget(identity)
        self.profile_card.add_widget(avatar_row)
        goal_label = label(
            f"MAIN QUEST  /  {user.get('goal', 'Choose your goal')}",
            15, GOLD, True)
        goal_label.size_hint_y = None
        goal_label.height = dp(32)
        self.profile_card.add_widget(goal_label)
        measure_label = label(
            f"BODYWEIGHT  /  {user.get('bodyweight') or '—'} kg     "
            f"HEIGHT  /  {user.get('height') or '—'} cm",
            13, TEXT, True)
        measure_label.size_hint_y = None
        measure_label.height = dp(28)
        self.profile_card.add_widget(measure_label)
        body_label = label(
            f"BODY TYPE  /  {user.get('body_type', 'Not set')}\n"
            f"BASE  /  {user.get('location', 'Not set')}", 11, MUTED)
        body_label.size_hint_y = None
        body_label.height = dp(42)
        self.profile_card.add_widget(body_label)

        records = [
            ("LEVEL", user.get("level", 0)), ("XP", user.get("xp", 0)),
            ("WORKOUTS", user.get("completed_workouts", 0)),
            ("CURRENT STREAK", current_streak(days)),
            ("SKILL TIME", f"{user.get('skill_minutes', 0)} min"),
            ("WORKOUT TIME", f"{user.get('workout_minutes', 0)} min"),
            ("STEPS", user.get("steps", 0)), ("CALORIES", user.get("calories", 0)),
            ("RANK POINTS", user.get("rank_points", 0)),
            ("ACTIVE DAYS", len(days)),
        ]
        for title, value in records:
            tile = Card(orientation="vertical", size_hint_y=None,
                        height=dp(78), spacing=dp(2))
            tile.add_widget(label(title, 9, MUTED, True))
            tile.add_widget(label(str(value), 20, GREEN if title in (
                "CURRENT STREAK", "RANK POINTS") else TEXT, True))
            self.record_grid.add_widget(tile)
        self._render_calendar(days)

        achievement_count = int(user.get("achievements", 0))
        achievement_data = getattr(self, "achievement_data", {})
        achievement_count = max(achievement_count, len(achievement_data))
        self.achievements.add_widget(label(
            f"RANK REWARDS  /  {achievement_count}     "
            f"TRAINING RECORDS  /  {len(activities)}", 11, GOLD, True))
        recent = sorted(
            [r for r in activities.values() if isinstance(r, dict)],
            key=lambda row: row.get("timestamp", ""), reverse=True)[:4]
        if not recent:
            self.achievements.add_widget(label("Your training history will appear here.",
                                               10, MUTED))
        for row in recent:
            self.achievements.add_widget(label(
                f"{row.get('date', '')} • {row.get('type', 'activity')} • "
                f"{row.get('workout_minutes', 0) + row.get('skill_minutes', 0)} min",
                9, TEXT))

    def _local_avatar(self, username):
        app = App.get_running_app()
        try:
            store = JsonStore(f"{app.user_data_dir}/gravix_profile_media.json")
            if store.exists(str(username)):
                saved = store.get(str(username))
                photo = saved.get("photo", "")
                if photo and os.path.isfile(photo):
                    return photo, saved.get("crest", "NOVA")
                return "", saved.get("crest", "NOVA")
        except Exception:
            pass
        return "", "NOVA"

    def _save_local_avatar(self, username, **values):
        app = App.get_running_app()
        store = JsonStore(f"{app.user_data_dir}/gravix_profile_media.json")
        existing = store.get(str(username)) if store.exists(str(username)) else {}
        existing.update(values)
        store.put(str(username), **existing)

    def choose_avatar(self, *_):
        box = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(8))
        box.add_widget(label("PICK YOUR HUNTER CREST", 14, GOLD, True))
        pop = Popup(title="PROFILE CREST", content=box, size_hint=(.88, .58),
                    background_color=get_color_from_hex(CARD))
        for crest in ("NOVA", "EMBER", "VOLT", "SHADE"):
            box.add_widget(pill_button(
                f"{crest} CREST", lambda _, value=crest:
                self._choose_crest(value, pop), CARD2, 42))
        box.add_widget(pill_button(
            "CHOOSE A PHOTO", lambda *_: (pop.dismiss(), self._open_avatar_picker()),
            ACCENT, 44))
        self._popup = pop
        pop.open()

    def _choose_crest(self, crest, popup):
        username = App.get_running_app().current_user
        self._save_local_avatar(username, crest=crest, photo="")
        popup.dismiss()
        self._render_profile()

    def _open_avatar_picker(self):
        if native_filechooser is None:
            self.popup("PHOTO PICKER UNAVAILABLE",
                       "This build does not include a phone photo picker. You can still choose one of the GRAVIX crests.")
            return
        try:
            native_filechooser.open_file(
                on_selection=self._save_avatar_file,
                filters=["*.png", "*.jpg", "*.jpeg", "*.webp"])
        except Exception:
            self.popup("PHOTO PICKER UNAVAILABLE",
                       "The phone could not open the image picker in this build.")

    def _save_avatar_file(self, selection):
        if not selection:
            return
        source = selection[0]
        extension = os.path.splitext(source)[1].lower()
        if extension not in (".png", ".jpg", ".jpeg", ".webp"):
            self.popup("IMAGE NOT SUPPORTED", "Choose a PNG, JPG, JPEG or WEBP image.")
            return
        app = App.get_running_app()
        username = app.current_user
        destination = os.path.join(app.user_data_dir, f"gravix_avatar_{username}{extension}")
        try:
            shutil.copyfile(source, destination)
            self._save_local_avatar(username, photo=destination, crest="NOVA")
            self._render_profile()
        except Exception:
            self.popup("PHOTO COULD NOT BE SAVED",
                       "The selected image could not be copied into GRAVIX storage.")

    def _render_calendar(self, days):
        self.calendar_card.clear_widgets()
        header = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(4))
        header.add_widget(pill_button("<", lambda *_: self.change_month(-1), CARD2, 32))
        month_label = label(self.calendar_month.strftime("%B %Y"), 13, TEXT, True, "center")
        header.add_widget(month_label)
        header.add_widget(pill_button(">", lambda *_: self.change_month(1), CARD2, 32))
        self.calendar_card.add_widget(header)
        calendar = GridLayout(cols=7, spacing=dp(2), size_hint_y=None,
                              row_default_height=dp(40), row_force_default=True)
        calendar.bind(minimum_height=calendar.setter("height"))
        for day_name in ("M", "T", "W", "T", "F", "S", "S"):
            calendar.add_widget(label(day_name, 9, MUTED, True, "center"))
        month = self.calendar_month
        next_month = (datetime.date(month.year + (month.month == 12),
                                    1 if month.month == 12 else month.month + 1, 1))
        days_in_month = (next_month - datetime.timedelta(days=1)).day
        for _ in range(month.weekday()):
            calendar.add_widget(Widget(size_hint_y=None, height=dp(40)))
        for day in range(1, days_in_month + 1):
            date_key = f"{month.year:04d}-{month.month:02d}-{day:02d}"
            marked = date_key in days
            cell = Button(
                text=f"{day}{'*' if marked else ''}",
                background_normal="", background_down="",
                background_color=get_color_from_hex(
                    GREEN if marked else CARD2),
                color=get_color_from_hex(BG if marked else TEXT),
                bold=marked, font_size=dp(11))
            cell.bind(on_release=lambda _, key=date_key:
                      self.show_calendar_day(key))
            calendar.add_widget(cell)
        self.calendar_card.add_widget(calendar)
        self.calendar_card.add_widget(label(
            "Tap any date to view its training entries. * marks activity.",
            9, MUTED))

    def change_month(self, delta):
        month = self.calendar_month
        index = month.year * 12 + month.month - 1 + delta
        year, month_index = divmod(index, 12)
        self.calendar_month = datetime.date(year, month_index + 1, 1)
        self._render_calendar(activity_map(self.activities))

    def show_calendar_day(self, date_key):
        records = [row for row in self.activities.values()
                   if isinstance(row, dict) and row.get("date") == date_key]
        if not records:
            detail = f"No training entries are saved for {date_key}."
        else:
            detail = "\n\n".join(
                f"{row.get('type', 'activity').replace('_', ' ').title()}\n"
                f"Workout {row.get('workout_minutes', 0)} min  •  "
                f"Skill {row.get('skill_minutes', 0)} min\n"
                f"Steps {row.get('steps', 0)}  •  Calories {row.get('calories', 0)}"
                for row in records)
        self.popup(f"TRAINING LOG  /  {date_key}", detail)

    def edit_profile(self, *_):
        username = App.get_running_app().current_user
        user = self.user_data
        fields = [
            ("display_name", "Public display name",
             user.get("display_name",
                      getattr(App.get_running_app(), "current_display_name", ""))),
            ("avatar_url", "Anime avatar or photo URL", user.get("avatar_url", "")),
            ("bodyweight", "Bodyweight in kg", user.get("bodyweight", "")),
            ("height", "Height in cm", user.get("height", "")),
            ("body_type", "Body type: ecto, endo, meso or prefer not to say",
             user.get("body_type", "")),
            ("goal", "Main fitness goal", user.get("goal", "")),
            ("location", "City / area for academy discovery", user.get("location", "")),
            ("latitude", "Latitude (optional, for distance sorting)",
             user.get("latitude", "")),
            ("longitude", "Longitude (optional, for distance sorting)",
             user.get("longitude", "")),
        ]

        def save(values, status, popup):
            if len(values["display_name"].strip()) > 50:
                status.text = clean_markup("Display name must be 50 characters or fewer.")
                return False
            body_type = values["body_type"].lower()
            if body_type and body_type not in (
                    "ecto", "endomorph", "endo", "mesomorph", "meso",
                    "ectomorph", "prefer not to say"):
                status.text = clean_markup("Choose ecto, endo, meso, or prefer not to say.")
                return False
            try:
                if values["bodyweight"]:
                    float(values["bodyweight"])
                if values["height"]:
                    float(values["height"])
                if values["latitude"] or values["longitude"]:
                    latitude = float(values["latitude"])
                    longitude = float(values["longitude"])
                    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                        raise ValueError
            except ValueError:
                status.text = clean_markup("Check body measurements and enter valid coordinates.")
                return False
            avatar = values["avatar_url"]
            if avatar and not avatar.startswith(("https://", "http://")):
                status.text = clean_markup("Avatar/photo must be a shareable URL.")
                return False
            safe_patch(f"users/{username}/profile", values)
            safe_patch(f"public_profiles/{username}", {
                "display_name": values["display_name"],
                "avatar_url": values["avatar_url"],
                "body_type": values["body_type"],
                "goal": values["goal"],
            })
            app = App.get_running_app()
            app.current_display_name = values["display_name"]
            self.user_data.update(values)
            self._render_profile()
        self.form_popup("PROFILE & PERSONAL DETAILS", fields,
                        "SAVE PROFILE", save, .8)

    def creator_info(self, *_):
        self.manager.current = "athletes"


class ProgramScreen(BaseScreen):
    WEEK = [
        ("MON • PUSH STRENGTH", "Push-ups 4×6–12 • Pike push-ups 3×6–10 • "
         "Bench dips 3×8–12"),
        ("TUE • PULL STRENGTH", "Rows 4×8–12 • Assisted pull-ups 4×5–8 • "
         "Active hangs 3×20 sec"),
        ("WED • LEGS & CORE", "Squats 4×12 • Reverse lunges 3×8/side • "
         "Hollow hold 4×20 sec"),
        ("THU • SKILL PRACTICE", "Choose one skill progression • 15–25 min "
         "focused technique • stop if form breaks"),
        ("FRI • CONDITIONING", "Push-up / squat / plank circuit • 3–5 rounds "
         "at a pace you can control"),
        ("SAT • MOBILITY & SKILL", "Shoulder and wrist mobility • repeat your "
         "current skill step • easy recovery"),
        ("SUN • REST", "Rest, walk comfortably, hydrate and review your week."),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical",
                         padding=[dp(14), dp(15), dp(14), 0], spacing=dp(7))
        root.add_widget(label("STRUCTURED CALISTHENICS", 20, TEXT, True))
        root.add_widget(label(
            "Starter week • scale reps to your level • rest 60–120 seconds between sets.",
            9, MUTED))
        self.status = label("", 9, GREEN)
        root.add_widget(self.status)
        scroll = ScrollView(do_scroll_x=False)
        content = BoxLayout(orientation="vertical", spacing=dp(6),
                            size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))
        for title, exercises in self.WEEK:
            session = Card(orientation="vertical", size_hint_y=None,
                           height=dp(83), spacing=dp(3))
            session.add_widget(label(title, 11, ACCENT, True))
            session.add_widget(label(exercises, 9, TEXT))
            content.add_widget(session)
        content.add_widget(label("PAID COACH PROGRAMS", 13, GOLD, True))
        content.add_widget(label(
            "Request a coach-built 1, 3 or 6 month plan. Listed prices start at 99; "
            "the currency and checkout are configured by GRAVIX/payment services.",
            9, MUTED))
        for months in (1, 3, 6):
            content.add_widget(pill_button(
                f"REQUEST {months}-MONTH PRO PLAN • STARTS AT 99",
                lambda _, duration=months: self.request_program(duration),
                CARD2, 40))
        scroll.add_widget(content)
        root.add_widget(scroll)
        root.add_widget(pill_button("LOG TODAY'S PROGRAM SESSION",
                                    self.log_session, GREEN, 42))
        root.add_widget(self.nav("EXPLORE"))
        self.add_widget(root)

    def request_program(self, months):
        username = App.get_running_app().current_user
        safe_post(f"marketplace/requests/{username}", {
            "buyer_uid": username, "category": "programs",
            "program": "Structured calisthenics",
            "duration_months": months, "starting_price": 99,
            "created_at": datetime.datetime.now().isoformat(),
            "status": "request",
        })
        self.popup("PROGRAM REQUESTED",
                   f"Your {months}-month program request is saved. Payment will be available when a checkout provider is connected.")

    def log_session(self, *_):
        day_name = datetime.date.today().strftime("%A").upper()
        session = next((item for item in self.WEEK if item[0].startswith(day_name[:3])),
                       self.WEEK[-1])

        def save(values, status, popup):
            try:
                minutes = max(0, int(values["minutes"] or 0))
                steps = max(0, int(values["steps"] or 0))
                calories = max(0, int(values["calories"] or 0))
            except ValueError:
                status.text = clean_markup("Enter whole numbers.")
                return False
            if not record_activity("program_session", {
                "workout_minutes": minutes, "steps": steps,
                "calories": calories, "completed_workouts": 1,
                "rank_points": 20, "program_day": session[0],
                "description": session[0],
            }):
                status.text = clean_markup("Could not save. Check your connection.")
                return False
            username = App.get_running_app().current_user
            safe_put(f"users/{username}/program_sessions/{today_key()}", {
                "day": session[0], "minutes": minutes,
                "completed_at": datetime.datetime.now().isoformat(),
            })
            self.status.text = clean_markup(f"Saved: {session[0]}")
        self.form_popup(f"LOG {session[0]}", [
            ("minutes", "Actual training minutes", "30"),
            ("steps", "Steps completed (optional)", "0"),
            ("calories", "Calories burned (optional)", "0"),
        ], "SAVE SESSION", save, .62)


class AcademyScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.items = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        self.items.bind(minimum_height=self.items.setter("height"))
        root = BoxLayout(orientation="vertical",
                         padding=[dp(14), dp(16), dp(14), 0], spacing=dp(8))
        root.add_widget(label("NEARBY CALISTHENICS ACADEMIES", 19, TEXT, True))
        root.add_widget(pill_button(
            "USE THIS PHONE'S LOCATION", self.use_phone_location, CARD2, 40))
        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(7))
        self.location = text_field("Enter your city or area")
        row.add_widget(self.location)
        row.add_widget(pill_button("SEARCH", self.search, ACCENT, 44))
        root.add_widget(row)
        coords = GridLayout(cols=2, spacing=dp(6), size_hint_y=None,
                            row_default_height=dp(42))
        self.latitude = text_field("Latitude (optional)", height=42)
        self.longitude = text_field("Longitude (optional)", height=42)
        coords.add_widget(self.latitude)
        coords.add_widget(self.longitude)
        root.add_widget(coords)
        self.status = label("", 10, MUTED)
        root.add_widget(self.status)
        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(self.items)
        root.add_widget(scroll)
        root.add_widget(self.nav("EXPLORE"))
        self.add_widget(root)

    def on_enter(self):
        user = read_user()
        self.location.text = user.get("location", "")
        self.latitude.text = str(user.get("latitude", ""))
        self.longitude.text = str(user.get("longitude", ""))
        Clock.schedule_once(lambda *_: self.search(), .1)

    def use_phone_location(self, *_):
        if phone_gps is None:
            self.status.text = clean_markup(
                "Phone GPS is available in the Android build. Enter coordinates manually here.")
            return

        def start_gps(*_args):
            try:
                phone_gps.configure(on_location=self._on_gps_location,
                                    on_status=self._on_gps_status)
                phone_gps.start(minTime=1000, minDistance=0)
                self.status.text = clean_markup("Waiting for a GPS fix…")
            except Exception:
                self.status.text = clean_markup(
                    "Could not start GPS. Check location permission and device settings.")

        try:
            from android.permissions import request_permissions
            request_permissions([
                "android.permission.ACCESS_FINE_LOCATION",
                "android.permission.ACCESS_COARSE_LOCATION",
            ], lambda _permissions, grants: Clock.schedule_once(
                lambda _dt: start_gps() if any(grants) else setattr(
                    self.status, "text", clean_markup("Location permission was not granted.")), 0))
        except Exception:
            start_gps()

    def _on_gps_status(self, provider, status):
        Clock.schedule_once(lambda _dt: setattr(
            self.status, "text", clean_markup(f"Location: {status}")), 0)

    def _on_gps_location(self, **location):
        try:
            latitude = float(location["lat"])
            longitude = float(location["lon"])
        except (KeyError, TypeError, ValueError):
            return
        def apply_location(_dt):
            self.latitude.text = f"{latitude:.6f}"
            self.longitude.text = f"{longitude:.6f}"
            self.status.text = clean_markup("GPS location loaded. Nearby academy records are sorted by distance.")
            safe_patch(f"users/{App.get_running_app().current_user}/profile", {
                "latitude": latitude, "longitude": longitude,
            })
            try:
                phone_gps.stop()
            except Exception:
                pass
            self.search()
        Clock.schedule_once(apply_location, 0)

    def search(self, *_):
        query = self.location.text.strip().lower()
        self.items.clear_widgets()
        catalog = safe_get("academy_directory", {}) or {}
        matches = []
        try:
            user_lat, user_lon = float(self.latitude.text), float(self.longitude.text)
        except (TypeError, ValueError):
            user_lat = user_lon = None
        for academy_id, academy in (catalog.items() if isinstance(catalog, dict) else []):
            if not isinstance(academy, dict):
                continue
            location = str(academy.get("city", academy.get("location", "")))
            distance = None
            try:
                if user_lat is not None and user_lon is not None:
                    distance = distance_km(
                        user_lat, user_lon,
                        float(academy["latitude"]), float(academy["longitude"]))
            except (KeyError, TypeError, ValueError):
                pass
            if distance is not None or not query or query in location.lower():
                matches.append((academy_id, academy, distance))
        if not matches:
            self.status.text = clean_markup(
                "No matching academy records. Add public academy listings to /academy_directory in Firebase.")
            return
        if user_lat is not None and user_lon is not None:
            matches.sort(key=lambda row: row[2] if row[2] is not None else float("inf"))
        self.status.text = clean_markup(
            f"{len(matches)} academies • "
            f"{'sorted by distance' if user_lat is not None and user_lon is not None else 'matched by city/area'}.")
        for academy_id, academy, distance in matches:
            distance_text = f" • {distance:.1f} km away" if distance is not None else ""
            item = Card(orientation="vertical", size_hint_y=None,
                        height=dp(142), spacing=dp(5))
            item.add_widget(label(academy.get("name", "Calisthenics academy"),
                                  14, TEXT, True))
            item.add_widget(label(
                f"{academy.get('city', academy.get('location', 'Location not set'))}"
                f"{distance_text}\n"
                f"{academy.get('address', '')}\n"
                f"{academy.get('classes', 'Calisthenics classes')} • "
                f"Fee: {academy.get('fee', 'Contact academy')}", 9, MUTED))
            item.add_widget(pill_button(
                "REQUEST TO JOIN", lambda _, aid=academy_id, a=dict(academy):
                self.request_join(aid, a), ACCENT, 38))
            self.items.add_widget(item)

    def request_join(self, academy_id, academy):
        username = App.get_running_app().current_user
        request_path = f"users/{username}/academy_requests/{academy_id}"
        if safe_get(request_path):
            self.popup("ALREADY RECORDED",
                       "Your one-time academy referral request is already on record.")
            return
        event = {
            "user": username, "academy_id": academy_id,
            "academy_name": academy.get("name", ""),
            "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "status": "pending_settlement",
            "commission_type": "one_time",
            "commission_amount": academy.get(
                "commission_amount", academy.get("referral_commission", 0)),
            "commission_currency": academy.get("commission_currency", ""),
        }
        if not safe_put(request_path, event):
            self.popup("REQUEST NOT SAVED",
                       "Could not record the academy request. Check your connection and try again.")
            return
        self.popup("REQUEST RECORDED",
            "Your academy interest is saved. A one-time academy commission must be settled through a verified academy/payment integration.")


class ChallengeScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical",
                         padding=[dp(14), dp(16), dp(14), 0], spacing=dp(8))
        root.add_widget(label("GLOBAL CHALLENGES", 22, TEXT, True))
        self.status = label("", 10, MUTED)
        root.add_widget(self.status)
        root.add_widget(pill_button("RECORD A PUSH-UP 1v1", self.start_match,
                                    ACCENT, 44))
        root.add_widget(label("THIS WEEK'S MISSIONS", 13, GOLD, True))
        mission = Card(orientation="vertical", size_hint_y=None, height=dp(142),
                       spacing=dp(5))
        mission.add_widget(label("• Log three skill practices\n"
                                 "• Complete a push-up challenge\n"
                                 "• Earn rank points through workouts",
                                 10, TEXT))
        mission.add_widget(pill_button("CLAIM WEEKLY MISSION", self.claim_mission,
                                       CARD2, 40))
        root.add_widget(mission)
        root.add_widget(label("WORLD RANKINGS", 13, TEXT, True))
        scroll = ScrollView(do_scroll_x=False)
        self.rankings = BoxLayout(orientation="vertical", spacing=dp(6),
                                  size_hint_y=None)
        self.rankings.bind(minimum_height=self.rankings.setter("height"))
        scroll.add_widget(self.rankings)
        root.add_widget(scroll)
        root.add_widget(label(
            "Opponent suggestions use similar goal, body type and level. "
            "Scores are self-reported until video counting and AI verification are connected.",
            9, MUTED))
        root.add_widget(self.nav("EXPLORE"))
        self.add_widget(root)

    def on_enter(self):
        Clock.schedule_once(lambda *_: self.refresh(), .1)

    def refresh(self):
        users = safe_get("leaderboard", {}) or {}
        rows = sorted(
            [(name, data) for name, data in users.items()
             if isinstance(data, dict)],
            key=lambda pair: int(pair[1].get("rank_points", 0)), reverse=True)
        self.rankings.clear_widgets()
        if not rows:
            self.rankings.add_widget(label("Rankings will appear as athletes train.",
                                           10, MUTED))
        for position, (name, data) in enumerate(rows[:20], start=1):
            tile = Card(size_hint_y=None, height=dp(46), spacing=dp(4))
            tile.add_widget(label(
                f"#{position}  {data.get('display_name', name)}  •  {data.get('rank_points', 0)} pts",
                11, TEXT, position <= 3))
            self.rankings.add_widget(tile)

    def claim_mission(self, *_):
        username = App.get_running_app().current_user
        week = datetime.date.today().isocalendar()
        key = f"{week.year}-W{week.week:02d}"
        safe_put(f"users/{username}/missions/{key}", {
            "claimed_at": datetime.datetime.now().isoformat(),
            "status": "in_progress",
            "tasks": {"skill_practice": 0, "pushup_match": 0},
        })
        self.popup("MISSION STARTED",
                   "Your weekly GRAVIX mission is saved. Complete the listed activities to build your record.")

    def start_match(self, *_):
        users = safe_get("public_profiles", {}) or {}
        levels = safe_get("leaderboard", {}) or {}
        username = App.get_running_app().current_user
        own_profile = users.get(username, {}) if isinstance(users, dict) else {}
        opponents = [
            (name, data) for name, data in users.items()
            if name != username and isinstance(data, dict)
        ] if isinstance(users, dict) else []
        if not opponents:
            self.popup("MATCHMAKING", "A 1v1 opponent will appear when another athlete joins GRAVIX.")
            return
        own_level = int(read_user().get("level", 0))

        def compatibility(candidate):
            _, profile = candidate
            score = 0
            own_type = str(own_profile.get("body_type", "")).lower()
            other_type = str(profile.get("body_type", "")).lower()
            if own_type and own_type != "not set" and own_type == other_type:
                score += 3
            own_goal = str(own_profile.get("goal", "")).lower()
            other_goal = str(profile.get("goal", "")).lower()
            if own_goal and own_goal == other_goal:
                score += 2
            other_level = int((levels.get(candidate[0], {}) or {}).get("level", 0))
            if abs(own_level - other_level) <= 2:
                score += 1
            return score

        best_score = max(compatibility(item) for item in opponents)
        closest = [item for item in opponents if compatibility(item) == best_score]
        opponent, opponent_profile = random.choice(closest)

        def save(values, status, popup):
            try:
                own = max(0, int(values["reps"] or 0))
                other = max(0, int(values["opponent_reps"] or 0))
            except ValueError:
                status.text = clean_markup("Enter whole-number rep counts.")
                return False
            winner = username if own > other else (opponent if other > own else "tie")
            result = {
                "player_1": username, "player_1_reps": own,
                "player_2": opponent, "player_2_reps": other,
                "winner": winner, "verified": False,
                "created_at": datetime.datetime.now().isoformat(),
            }
            safe_post(f"match_submissions/{username}", result)
            record_activity("pushup_match", {
                "description": f"Push-up match vs {opponent}", "reps": own,
            })
            self.refresh()
            self.popup("MATCH RECORDED",
                       f"{username}: {own} reps • {opponent}: {other} reps\n"
                       f"Result: {winner}\nScores are not AI verified.")
        self.form_popup(f"1v1 MATCH VS {opponent.upper()}", [
            ("reps", "Your push-ups", "0"),
            ("opponent_reps", f"{opponent}'s push-ups (reported)", "0"),
        ], "SAVE MATCH RESULT", save, .55)


class AthleteHubScreen(BaseScreen):
    CATEGORIES = [
        ("PROGRAMS", "programs"), ("1:1 SESSIONS", "sessions"),
        ("LIVE & Q&A", "live"), ("SKILL VIDEOS", "videos"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.category = "programs"
        root = BoxLayout(orientation="vertical",
                         padding=[dp(12), dp(14), dp(12), 0], spacing=dp(7))
        root.add_widget(label("ATHLETE HUB", 22, TEXT, True))
        root.add_widget(label(
            "Explore coaching, athlete content and paid programs.", 10, MUTED))
        root.add_widget(pill_button("MY SALES & EARNINGS", self.earnings,
                                    CARD2, 38))
        tabs = GridLayout(cols=2, spacing=dp(6), size_hint_y=None,
                          row_default_height=dp(40))
        for title, category in self.CATEGORIES:
            tabs.add_widget(pill_button(
                title, lambda _, value=category: self.select(value), CARD2, 38))
        root.add_widget(tabs)
        self.items = BoxLayout(orientation="vertical", spacing=dp(7),
                               size_hint_y=None)
        self.items.bind(minimum_height=self.items.setter("height"))
        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(self.items)
        root.add_widget(scroll)
        root.add_widget(pill_button("PUBLISH OFFER / LIVE / VIDEO",
                                    self.publish, ACCENT, 42))
        root.add_widget(self.nav("EXPLORE"))
        self.add_widget(root)

    def on_enter(self):
        Clock.schedule_once(lambda *_: self.refresh(), .1)

    def select(self, category):
        self.category = category
        self.refresh()

    def refresh(self):
        self.items.clear_widgets()
        data = safe_get(f"marketplace/{self.category}", {}) or {}
        if not data:
            self.items.add_widget(label(
                f"No {self.category} published yet. Athletes can add listings with the button below.",
                10, MUTED))
            return
        entries = list(data.items()) if isinstance(data, dict) else []
        for item_id, item in entries[-30:][::-1]:
            if not isinstance(item, dict):
                continue
            tile = Card(orientation="vertical", size_hint_y=None,
                        height=dp(142), spacing=dp(5))
            tile.add_widget(label(item.get("title", self.category.title()),
                                  13, TEXT, True))
            tile.add_widget(label(
                f"{item.get('creator', 'GRAVIX athlete')} • "
                f"{item.get('duration', '')} • Price: {item.get('price', 'Free')}\n"
                f"{item.get('description', '')}", 9, MUTED))
            row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(6))
            row.add_widget(pill_button(
                "REQUEST / ENQUIRE",
                lambda _, iid=item_id, listing=dict(item): self.request(iid, listing),
                ACCENT, 34))
            if item.get("url"):
                row.add_widget(pill_button(
                    "OPEN LINK",
                    lambda _, url=item["url"]: self.open_link(url), CARD2, 34))
            tile.add_widget(row)
            if self.category == "live":
                comments = safe_get(f"live_comments/{item_id}", {}) or {}
                for comment in list(comments.values())[-3:]:
                    if isinstance(comment, dict):
                        tile.add_widget(label(
                            f"{comment.get('display_name', 'Athlete')}: "
                            f"{comment.get('comment', '')}", 9, MUTED))
                tile.add_widget(pill_button(
                    "ASK A QUESTION",
                    lambda _, iid=item_id: self.comment(iid), CARD2, 34))
            self.items.add_widget(tile)

    def request(self, item_id, listing):
        username = App.get_running_app().current_user
        safe_post(f"marketplace/requests/{username}", {
            "buyer_uid": username, "listing_id": item_id,
            "category": self.category, "listing": listing,
            "created_at": datetime.datetime.now().isoformat(),
            "status": "request",
        })
        self.popup("REQUEST SENT",
                   "Your request is recorded. Payment and booking confirmation need a connected checkout/provider.")

    def publish(self, *_):
        username = App.get_running_app().current_user
        category_choices = ", ".join(value for _, value in self.CATEGORIES)

        def save(values, status, popup):
            category = values["category"].lower()
            if category not in [value for _, value in self.CATEGORIES]:
                status.text = clean_markup(f"Category must be one of: {category_choices}")
                return False
            price = values["price"] or "Free"
            listing = {
                "title": values["title"] or "GRAVIX athlete listing",
                "description": values["description"],
                "duration": values["duration"],
                "price": price,
                "url": values["url"],
                "creator": getattr(App.get_running_app(),
                                    "current_display_name", username),
                "creator_uid": username,
                "created_at": datetime.datetime.now().isoformat(),
            }
            if not safe_post(f"marketplace/{category}", listing):
                status.text = clean_markup("Could not publish. Check your connection.")
                return False
            self.category = category
            self.refresh()
        self.form_popup("PUBLISH TO ATHLETE HUB", [
            ("category", "Category: programs, sessions, live or videos", self.category),
            ("title", "Title", ""),
            ("description", "Description", ""),
            ("duration", "Duration: 1, 3 or 6 months / session length", ""),
            ("price", "Price (currency set by your payment provider)", ""),
            ("url", "Video, booking or live-room URL (optional)", ""),
        ], "PUBLISH", save, .88)

    def comment(self, item_id):
        username = App.get_running_app().current_user

        def save(values, status, popup):
            if not values["comment"]:
                status.text = clean_markup("Write a question or comment first.")
                return False
            safe_post(f"live_comments/{item_id}", {
                "uid": username,
                "display_name": getattr(App.get_running_app(),
                                         "current_display_name", "Athlete"),
                "comment": values["comment"],
                "created_at": datetime.datetime.now().isoformat(),
            })
        self.form_popup("LIVE Q&A COMMENT", [
            ("comment", "Ask the athlete a question", ""),
        ], "POST COMMENT", save, .45)

    def open_link(self, url):
        try:
            webbrowser.open(url)
        except Exception:
            self.popup("LINK", url)

    def earnings(self, *_):
        username = App.get_running_app().current_user
        transactions = safe_get(
            f"marketplace/transactions/{username}", {}) or {}
        mine = [
            item for item in transactions.values()
            if isinstance(item, dict) and item.get("creator_uid") == username
        ] if isinstance(transactions, dict) else []
        paid = [item for item in mine if item.get("status") == "paid"]
        requests = safe_get(
            f"marketplace/requests/{username}", {}) or {}
        enquiries = list(requests.values()) if isinstance(requests, dict) else []
        total = 0.0
        for item in paid:
            try:
                total += float(item.get("net_amount", item.get("amount", 0)))
            except (TypeError, ValueError):
                pass
        currency = next((item.get("currency", "") for item in paid
                         if item.get("currency")), "")
        self.popup(
            "MY SALES & EARNINGS",
            f"Paid transactions: {len(paid)}\n"
            f"Reported net earnings: {currency} {total:.2f}\n"
            f"Requests you created: {len(enquiries)}\n\n"
            "A payment provider/webhook must write completed transactions to "
            f"/marketplace/transactions/{username} before earnings appear.")


class NutritionScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical",
                         padding=[dp(14), dp(16), dp(14), 0], spacing=dp(8))
        root.add_widget(label("NUTRITION & MEAL PLANS", 20, TEXT, True))
        self.summary = Card(orientation="vertical", size_hint_y=None,
                            height=dp(102), spacing=dp(5))
        root.add_widget(self.summary)
        scroll = ScrollView(do_scroll_x=False)
        content = BoxLayout(orientation="vertical", spacing=dp(8),
                            size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))
        for title, detail in [
            ("FREE • EVERYDAY BALANCED PLATE",
             "Rice or whole grains • dal/beans/eggs/tofu • vegetables • fruit. "
             "Adjust portions to appetite and activity."),
            ("FREE • HIGH-PROTEIN TEMPLATE",
             "Include a protein source at each meal: lentils, beans, dairy, eggs, "
             "tofu, fish or lean meat. Add grains and vegetables."),
            ("FREE • SAMPLE DAY (ESTIMATES)",
             "Breakfast: oats, milk and banana — 400 kcal, 18 g protein, 65 g carbs.\n"
             "Lunch: rice, dal, vegetables and curd — 650 kcal, 24 g protein, 105 g carbs.\n"
             "Snack: yogurt, fruit and peanuts — 300 kcal, 14 g protein, 38 g carbs.\n"
             "Dinner: chapati, paneer/tofu and vegetables — 600 kcal, 30 g protein, "
             "70 g carbs.\n"
             "Approx. total: 1,950 kcal • 86 g protein • 278 g carbs. Portions and brands vary."),
            ("PAID • PERSONALIZED PLAN",
             "Request a weight-gain or weight-loss plan from the buttons below. "
             "Checkout is not connected in this build."),
        ]:
            item = Card(orientation="vertical", size_hint_y=None,
                        height=dp(142 if "SAMPLE DAY" in title else 105), spacing=dp(5))
            item.add_widget(label(title, 11, GREEN if "FREE" in title else GOLD, True))
            item.add_widget(label(detail, 9, MUTED))
            content.add_widget(item)
        scroll.add_widget(content)
        root.add_widget(scroll)
        root.add_widget(pill_button(
            "REQUEST WEIGHT-GAIN MEAL PLAN",
            lambda *_: self.request_paid_plan("weight_gain"), CARD2, 40))
        root.add_widget(pill_button(
            "REQUEST WEIGHT-LOSS MEAL PLAN",
            lambda *_: self.request_paid_plan("weight_loss"), CARD2, 40))
        root.add_widget(label(
            "Macro estimates are general starting points, not medical advice.",
            9, MUTED))
        root.add_widget(self.nav("EXPLORE"))
        self.add_widget(root)

    def on_enter(self):
        user = read_user()
        self.summary.clear_widgets()
        try:
            weight = float(user.get("bodyweight", 0))
            calories = int(weight * 30)
            protein = int(weight * 1.6)
            carbs = int(weight * 4)
            text = (f"At {weight:g} kg: roughly {calories} kcal maintenance estimate • "
                    f"{protein} g protein • {carbs} g carbs/day")
        except (TypeError, ValueError):
            text = "Add your bodyweight in Profile to see a rough macro starting point."
        self.summary.add_widget(label("DAILY STARTING ESTIMATE", 10, ACCENT, True))
        self.summary.add_widget(label(text, 10, TEXT))
        self.summary.add_widget(label(
            "Actual needs vary by age, health, activity and goals.", 8, MUTED))

    def request_paid_plan(self, goal):
        username = App.get_running_app().current_user
        safe_post(f"marketplace/requests/{username}", {
            "buyer_uid": username, "category": "nutrition",
            "plan_type": goal, "created_at": datetime.datetime.now().isoformat(),
            "status": "request",
        })
        self.popup("MEAL PLAN REQUESTED",
                   "Your request is recorded. A qualified coach and payment provider must be connected to fulfill it.")


class StoreScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical",
                         padding=[dp(14), dp(16), dp(14), 0], spacing=dp(8))
        root.add_widget(label("GRAVIX FITNESS STORE", 20, TEXT, True))
        root.add_widget(label(
            "Equipment, shoes, compression and training accessories.", 10, MUTED))
        self.items = BoxLayout(orientation="vertical", spacing=dp(8),
                               size_hint_y=None)
        self.items.bind(minimum_height=self.items.setter("height"))
        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(self.items)
        root.add_widget(scroll)
        root.add_widget(pill_button("PUBLISH AN ITEM / AFFILIATE LINK",
                                    self.publish, ACCENT, 42))
        root.add_widget(label("Purchases happen on the seller's site in this MVP.",
                              9, MUTED))
        root.add_widget(self.nav("EXPLORE"))
        self.add_widget(root)

    def on_enter(self):
        Clock.schedule_once(lambda *_: self.refresh(), .1)

    def refresh(self):
        self.items.clear_widgets()
        data = safe_get("store/items", {}) or {}
        entries = list(data.items()) if isinstance(data, dict) else []
        if not entries:
            self.items.add_widget(label(
                "Store items will show here when configured in /store/items.",
                10, MUTED))
        for item_id, item in entries[-50:][::-1]:
            if not isinstance(item, dict):
                continue
            tile = Card(orientation="vertical", size_hint_y=None,
                        height=dp(118), spacing=dp(5))
            tile.add_widget(label(item.get("name", "Fitness item"), 13, TEXT, True))
            tile.add_widget(label(
                f"{item.get('description', '')}\nPrice: {item.get('price', 'See seller')}",
                9, MUTED))
            if item.get("url"):
                tile.add_widget(pill_button(
                    "VIEW PRODUCT", lambda _, iid=item_id, url=item["url"]:
                    self.open_item(iid, url), CARD2, 36))
            self.items.add_widget(tile)

    def open_item(self, item_id, url):
        username = App.get_running_app().current_user
        safe_post(f"users/{username}/store_clicks", {
            "item_id": item_id,
            "clicked_at": datetime.datetime.now().isoformat(),
        })
        try:
            webbrowser.open(url)
        except Exception:
            self.popup("PRODUCT LINK", url)

    def publish(self, *_):
        username = App.get_running_app().current_user

        def save(values, status, popup):
            if not values["url"].startswith(("https://", "http://")):
                status.text = clean_markup("Enter a valid product/affiliate URL.")
                return False
            safe_post("store/items", {
                "name": values["name"], "description": values["description"],
                "price": values["price"], "url": values["url"],
                "seller_uid": username,
                "seller": getattr(App.get_running_app(),
                                   "current_display_name", username),
            })
            self.refresh()
        self.form_popup("ADD STORE / AFFILIATE ITEM", [
            ("name", "Product name", ""),
            ("description", "Description", ""),
            ("price", "Price", ""),
            ("url", "Product or affiliate URL", ""),
        ], "PUBLISH LINK", save, .66)


class GlowUpScreen(BaseScreen):
    HABITS = [
        "Cleanse gently and moisturize",
        "Apply sunscreen in the daytime",
        "Drink water with meals",
        "Sleep on a consistent schedule",
        "Keep grooming tools and pillowcases clean",
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical",
                         padding=[dp(14), dp(16), dp(14), 0], spacing=dp(8))
        root.add_widget(label("GLOW-UP ROUTINE", 21, TEXT, True))
        root.add_widget(label("Simple skincare, grooming and recovery habits.",
                              10, MUTED))
        root.add_widget(label(
            "Choose a habit to record today's completion.", 10, GREEN))
        for index, habit in enumerate(self.HABITS):
            root.add_widget(pill_button(
                habit, lambda _, i=index: self.log_habit(i), CARD2, 48))
        root.add_widget(Widget())
        root.add_widget(self.nav("EXPLORE"))
        self.add_widget(root)

    def log_habit(self, index):
        username = App.get_running_app().current_user
        safe_put(f"users/{username}/glowup/{today_key()}/{index}", {
            "habit": self.HABITS[index],
            "completed_at": datetime.datetime.now().isoformat(),
        })
        self.popup("HABIT SAVED", f"Added to today's routine:\n{self.HABITS[index]}")


class StepCounterScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.store = None  # Kept for one-time migration from the old tracker.
        self.store_key = None
        self.db_path = None
        self.sensor_manager = None
        self.sensor = None
        self.listener = None
        self.sensor_total = None
        self.daily_steps = 0
        self.synced_steps = 0
        self.session_started_at = 0
        self.session_expires_at = 0
        self.tracking_enabled = False
        self._service_active = False
        self._service_poll = None
        root = BoxLayout(orientation="vertical",
                         padding=[dp(14), dp(12), dp(14), 0], spacing=dp(8))
        title = label("STEP QUEST", 21, TEXT, True)
        title.size_hint_y = None
        title.height = dp(34)
        root.add_widget(title)
        subtitle = label("SYNC ONCE  /  TRACK FOR 24 HOURS", 11, GOLD, True)
        subtitle.size_hint_y = None
        subtitle.height = dp(24)
        root.add_widget(subtitle)
        self.count = label("0", 46, GREEN, True, "center")
        self.count.size_hint_y = None
        self.count.height = dp(100)
        root.add_widget(self.count)
        self.status = label("Waiting for sensor permission.", 10, MUTED, False, "center")
        self.status.size_hint_y = None
        self.status.height = dp(48)
        root.add_widget(self.status)
        root.add_widget(pill_button("START 24H STEP QUEST",
                                    self.start_sensor, ACCENT, 52))
        root.add_widget(pill_button("SAVE CURRENT STEP TOTAL",
                                    self.sync_steps, GREEN, 48))
        root.add_widget(label(
            "Start once and GRAVIX keeps counting for 24 hours, even when closed. "
            "Android activity permission and the packaged step service are required.",
            10, MUTED))
        root.add_widget(Widget())
        root.add_widget(self.nav("HOME"))
        self.add_widget(root)
        self.status.text = clean_markup("Sync your phone to start a 24-hour tracking quest.")

    def on_enter(self):
        self._load_tracker_state()
        if self._session_is_active():
            if self.tracking_enabled:
                self.status.text = clean_markup(
                    "24-hour tracking active. You can close GRAVIX.")
                self._register_sensor()
            else:
                self.status.text = clean_markup(
                    "Your 24-hour quest is paused. Start it again to resume counting.")
        elif self.session_expires_at:
            self.status.text = clean_markup("24-hour quest complete. Sync again to start a new window.")

    def _load_tracker_state(self, user_id=None):
        app = App.get_running_app()
        try:
            self.db_path = os.path.join(app.user_data_dir, "gravix_steps.sqlite3")
            user_id = user_id or app.current_user
            if not user_id:
                self.store_key = None
                return
            self.store_key = f"steps_{user_id}"
            with sqlite3.connect(self.db_path, timeout=10) as db:
                db.execute("PRAGMA journal_mode=WAL")
                db.execute("PRAGMA busy_timeout=10000")
                db.execute("""CREATE TABLE IF NOT EXISTS step_sessions (
                    user_id TEXT PRIMARY KEY,
                    started_at REAL NOT NULL DEFAULT 0,
                    expires_at REAL NOT NULL DEFAULT 0,
                    steps INTEGER NOT NULL DEFAULT 0,
                    synced_steps INTEGER NOT NULL DEFAULT 0,
                    latest REAL,
                    tracking_enabled INTEGER NOT NULL DEFAULT 0
                )""")
            saved = self._read_tracker_state()
            if saved is None:
                # Migrate a session created by the earlier JsonStore tracker.
                legacy = JsonStore(os.path.join(app.user_data_dir,
                                                "gravix_steps.json"))
                if legacy.exists(self.store_key):
                    old = legacy.get(self.store_key)
                    self._create_tracker_state(
                        started_at=float(old.get("started_at", 0)),
                        expires_at=float(old.get("expires_at", 0)),
                        steps=max(0, int(old.get("steps", 0))),
                        synced_steps=max(0, int(old.get("synced_steps", 0))),
                        latest=old.get("latest"), tracking_enabled=1)
                    saved = self._read_tracker_state()
            if saved:
                self.session_started_at = float(saved.get("started_at", 0))
                self.session_expires_at = float(saved.get("expires_at", 0))
                self.daily_steps = max(0, int(saved.get("steps", 0)))
                self.synced_steps = max(0, int(saved.get("synced_steps", 0)))
                self.sensor_total = saved.get("latest")
                self.tracking_enabled = bool(saved.get("tracking_enabled", 0))
                self.count.text = f"{self.daily_steps:,}"
        except Exception:
            self.store = None
            self.db_path = None

    def _read_tracker_state(self):
        if not self.db_path or not self.store_key:
            return None
        try:
            with sqlite3.connect(self.db_path, timeout=10) as db:
                db.row_factory = sqlite3.Row
                db.execute("PRAGMA busy_timeout=10000")
                row = db.execute(
                    "SELECT * FROM step_sessions WHERE user_id=?",
                    (self.store_key,)).fetchone()
                return dict(row) if row else None
        except (sqlite3.Error, OSError):
            return None

    def _create_tracker_state(self, started_at, expires_at, steps,
                              synced_steps, latest, tracking_enabled):
        if not self.db_path or not self.store_key:
            return
        try:
            with sqlite3.connect(self.db_path, timeout=10) as db:
                db.execute("PRAGMA busy_timeout=10000")
                db.execute("""INSERT OR REPLACE INTO step_sessions
                    (user_id, started_at, expires_at, steps, synced_steps,
                     latest, tracking_enabled) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (self.store_key, started_at, expires_at, steps, synced_steps,
                     latest, tracking_enabled))
        except (sqlite3.Error, OSError):
            pass

    def _update_tracker_fields(self, **fields):
        if not self.db_path or not self.store_key or not fields:
            return
        allowed = {"started_at", "expires_at", "steps", "synced_steps",
                   "latest", "tracking_enabled"}
        if not set(fields).issubset(allowed):
            return
        assignments = ", ".join(f"{name}=?" for name in fields)
        values = list(fields.values()) + [self.store_key]
        try:
            with sqlite3.connect(self.db_path, timeout=10) as db:
                db.execute("PRAGMA busy_timeout=10000")
                db.execute(f"UPDATE step_sessions SET {assignments} WHERE user_id=?",
                           values)
        except (sqlite3.Error, OSError):
            pass

    def _session_is_active(self):
        return bool(self.session_expires_at and time.time() < self.session_expires_at)

    def resume_tracking(self):
        self._load_tracker_state()
        if self._session_is_active():
            self.tracking_enabled = True
            self._update_tracker_fields(tracking_enabled=1)
            self._register_sensor()

    def start_sensor(self, *_):
        if _StepSensorListener is None:
            self.status.text = clean_markup(
                "Phone step sensor is supported in the Android package, not this desktop session.")
            return
        self._load_tracker_state()
        if not self._session_is_active():
            self.session_started_at = time.time()
            self.session_expires_at = self.session_started_at + 24 * 60 * 60
            self.daily_steps = 0
            self.synced_steps = 0
            self.sensor_total = None
            self.tracking_enabled = True
            self._create_tracker_state(
                started_at=self.session_started_at,
                expires_at=self.session_expires_at,
                steps=0, synced_steps=0, latest=None, tracking_enabled=1)
        else:
            self.tracking_enabled = True
            self._update_tracker_fields(tracking_enabled=1)
        self._register_sensor()

    def _register_sensor(self):
        if _StepSensorListener is None or not self._session_is_active():
            return
        if self._service_active and self._service_poll is not None:
            return
        if self.sensor_manager is not None and self.listener is not None:
            return

        def begin(*_args):
            try:
                if self._start_background_service():
                    self._service_active = True
                    self.status.text = clean_markup(
                        "24-hour tracking active. Close GRAVIX whenever you like.")
                    if self._service_poll is None:
                        self._service_poll = Clock.schedule_interval(
                            self._refresh_from_service, 1)
                    return
                self._register_local_sensor()
            except Exception:
                self._register_local_sensor()

        def permission_result(_permissions, grants):
            if grants and grants[0]:
                Clock.schedule_once(lambda _dt: begin(), 0)
            else:
                self.status.text = clean_markup(
                    "Activity-recognition permission is needed to count steps.")

        try:
            sdk = autoclass("android.os.Build$VERSION").SDK_INT
            if sdk >= 29:
                from android.permissions import request_permissions
                permissions = ["android.permission.ACTIVITY_RECOGNITION"]
                if sdk >= 33:
                    permissions.append("android.permission.POST_NOTIFICATIONS")
                request_permissions(permissions, permission_result)
            else:
                begin()
        except Exception:
            begin()

    def _start_background_service(self):
        """Start the packaged python-for-android health foreground service."""
        if not self.db_path or not self.store_key or not self._session_is_active():
            return False
        try:
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            package_name = str(activity.getPackageName())
            service = autoclass(f"{package_name}.ServiceSteptracker")
            argument = json.dumps({"db_path": self.db_path,
                                   "user_id": self.store_key})
            service.start(activity, "", "GRAVIX STEP QUEST",
                          "Counting steps for your active 24-hour quest", argument)
            return True
        except Exception:
            self.status.text = clean_markup(
                "Background step service is not in this Android build; steps count while GRAVIX is open.")
            return False

    def _register_local_sensor(self):
        if _StepSensorListener is None:
            self.status.text = clean_markup(
                "Phone step sensor is available in the Android app only.")
            return
        if self.sensor_manager is not None and self.listener is not None:
            return
        try:
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            context = autoclass("android.content.Context")
            sensor_api = autoclass("android.hardware.Sensor")
            manager_api = autoclass("android.hardware.SensorManager")
            self.sensor_manager = activity.getSystemService(context.SENSOR_SERVICE)
            self.sensor = self.sensor_manager.getDefaultSensor(sensor_api.TYPE_STEP_COUNTER)
            if self.sensor is None:
                self.status.text = clean_markup("This phone does not expose a step-counter sensor.")
                return
            self.listener = _StepSensorListener(self._sensor_value)
            ok = self.sensor_manager.registerListener(
                self.listener, self.sensor, manager_api.SENSOR_DELAY_NORMAL)
            self.status.text = clean_markup(
                "Counting while GRAVIX is open. Rebuild with the step service for 24-hour background tracking.") if ok else clean_markup(
                "The phone could not start its step sensor.")
        except Exception:
            self.status.text = clean_markup(
                "Could not access the phone sensor. Check Android activity-recognition permission.")

    def _refresh_from_service(self, _dt):
        saved = self._read_tracker_state()
        if saved:
            self.daily_steps = max(0, int(saved.get("steps", 0)))
            self.synced_steps = max(0, int(saved.get("synced_steps", 0)))
            self.sensor_total = saved.get("latest")
            self.count.text = f"{self.daily_steps:,}"
        if not self._session_is_active():
            self.status.text = clean_markup(
                "24-hour quest complete. Sync again to start a new window.")
            if self._service_poll is not None:
                self._service_poll.cancel()
                self._service_poll = None
            return False
        return True

    def _sensor_value(self, total):
        def apply(_dt):
            if not self._session_is_active():
                self.status.text = clean_markup(
                    "24-hour quest complete. Sync again to start a new window.")
                return
            if not self._apply_sensor_total(total):
                return
            self.count.text = f"{self.daily_steps:,}"
        Clock.schedule_once(apply, 0)

    def _apply_sensor_total(self, total):
        if not self.db_path or not self.store_key:
            return False
        try:
            total = float(total)
            with sqlite3.connect(self.db_path, timeout=10) as db:
                db.execute("PRAGMA busy_timeout=10000")
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("""SELECT started_at, expires_at, steps,
                    latest, tracking_enabled FROM step_sessions WHERE user_id=?""",
                    (self.store_key,)).fetchone()
                if not row:
                    db.rollback()
                    return False
                _started_at, expires_at, steps, previous_total, enabled = row
                if not enabled or time.time() >= float(expires_at):
                    db.rollback()
                    return False
                steps = int(steps)
                if previous_total is not None and total >= float(previous_total):
                    steps += int(total - float(previous_total))
                # A lower hardware counter means the phone rebooted. Preserve
                # the accumulated total and use this reading as the new base.
                db.execute("UPDATE step_sessions SET steps=?, latest=? WHERE user_id=?",
                           (steps, total, self.store_key))
                db.commit()
            self.daily_steps = steps
            self.sensor_total = total
            return True
        except (sqlite3.Error, OSError, TypeError, ValueError):
            return False

    def sync_steps(self, *_):
        self._load_tracker_state()
        if not self._session_is_active():
            self.popup("NO ACTIVE QUEST", "Sync the phone to start a new 24-hour step-tracking window.")
            return
        unsynced_steps = max(0, self.daily_steps - self.synced_steps)
        if unsynced_steps == 0:
            self.popup("NO NEW STEPS", "Your current phone step total has already been saved.")
            return
        if not record_activity("daily_tracker", {
                "steps": unsynced_steps, "calories": 0,
                "skill_minutes": 0, "description": "24-hour phone step quest"}):
            self.popup("SYNC FAILED", "Could not save the step total. Check your connection and Firebase setup.")
            return
        submitted_total = self.daily_steps
        saved = self._read_tracker_state() or {}
        current_total = max(submitted_total, int(saved.get("steps", 0)))
        self.synced_steps = min(current_total, max(
            self.synced_steps, submitted_total))
        self.daily_steps = current_total
        self._update_tracker_fields(synced_steps=self.synced_steps)
        self.count.text = f"{self.daily_steps:,}"
        self.popup("STEP QUEST SAVED", f"{self.daily_steps:,} phone steps sent to your GRAVIX record.")

    def stop_tracking(self):
        if self.sensor_manager is not None and self.listener is not None:
            try:
                self.sensor_manager.unregisterListener(self.listener)
            except Exception:
                pass
        self.sensor_manager = self.sensor = self.listener = None
        if self._service_poll is not None:
            self._service_poll.cancel()
            self._service_poll = None
        saved = self._read_tracker_state()
        if saved and self._session_is_active():
            self.tracking_enabled = False
            self._update_tracker_fields(tracking_enabled=0)
        self._service_active = False


class ReminderScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical",
                         padding=[dp(16), dp(20), dp(16), 0], spacing=dp(10))
        root.add_widget(label("DAILY WORKOUT REMINDER", 21, TEXT, True))
        root.add_widget(label(
            "Set a local reminder time. The app must be running for this build to check it.",
            10, MUTED))
        self.time_field = text_field("24-hour time, e.g. 07:30")
        root.add_widget(self.time_field)
        root.add_widget(pill_button("SAVE REMINDER", self.save, ACCENT, 48))
        root.add_widget(label(
            "Native push reminders while the app is closed need a mobile notification service.",
            9, MUTED))
        root.add_widget(Widget())
        root.add_widget(self.nav("EXPLORE"))
        self.add_widget(root)

    def on_enter(self):
        user = read_user()
        self.time_field.text = user.get("reminder_time", "08:00")

    def save(self, *_):
        value = self.time_field.text.strip()
        try:
            datetime.datetime.strptime(value, "%H:%M")
        except ValueError:
            self.popup("INVALID TIME", "Enter a 24-hour time, such as 07:30.")
            return
        username = App.get_running_app().current_user
        safe_patch(f"users/{username}/preferences", {
            "reminder_enabled": True, "reminder_time": value,
        })
        self.popup("REMINDER SAVED", f"Daily workout reminder set for {value}.")


class GravixApp(App):
    def build(self):
        self.title = "GRAVIX"
        icon_path = os.path.join(os.path.dirname(__file__),
                                 "gravix_launcher_icon.png")
        if os.path.isfile(icon_path):
            self.icon = icon_path
        self.current_user = None
        self.current_email = None
        self.current_display_name = None
        self.session_restore_pending = False
        try:
            session_store = JsonStore(f"{self.user_data_dir}/gravix_auth.json")
        except Exception:
            session_store = None
        self.auth = FirebaseAuthSession(session_store)
        self.reminder_last_sent = None
        Clock.schedule_interval(self.check_reminder, 30)
        manager = ScreenManager()
        screens = [
            LoginScreen(name="login"), HomeScreen(name="home"),
            SkillsScreen(name="skills"), ProfileScreen(name="profile"),
            ExploreScreen(name="explore"), ProgramScreen(name="program"),
            AcademyScreen(name="academies"),
            ChallengeScreen(name="challenges"), AthleteHubScreen(name="athletes"),
            NutritionScreen(name="nutrition"), StoreScreen(name="store"),
            GlowUpScreen(name="glowup"), ReminderScreen(name="reminders"),
            StepCounterScreen(name="steps"),
        ]
        for screen in screens:
            manager.add_widget(screen)
        self.screen_manager = manager
        self.auth.on_invalid_refresh = self._handle_invalid_refresh
        return manager

    def _handle_invalid_refresh(self):
        self.stop_step_tracking()
        self.current_user = None
        self.current_email = None
        self.current_display_name = None
        self.session_restore_pending = False
        if hasattr(self, "screen_manager"):
            self.screen_manager.current = "login"
            self.screen_manager.get_screen("login").status.text = clean_markup(
                "Your saved login expired. Please sign in again.")

    def start_step_tracking(self):
        if not self.current_user or not hasattr(self, "screen_manager"):
            return
        step_screen = self.screen_manager.get_screen("steps")
        Clock.schedule_once(lambda _dt: step_screen.resume_tracking(), .2)

    def stop_step_tracking(self):
        if hasattr(self, "screen_manager"):
            step_screen = self.screen_manager.get_screen("steps")
            saved_uid = self.current_user or getattr(self.auth, "uid", None)
            if saved_uid:
                step_screen._load_tracker_state(saved_uid)
            step_screen.stop_tracking()

    def on_start(self):
        if not self.auth.load_saved_session():
            if self.auth.last_error:
                self.screen_manager.get_screen("login").status.text = clean_markup(
                    "Could not read the saved login. Please sign in again.")
            return
        self.session_restore_pending = True
        login = self.screen_manager.get_screen("login")
        login.status.text = clean_markup("Restoring your saved login...")
        threading.Thread(target=self._refresh_saved_session, daemon=True).start()

    def _refresh_saved_session(self):
        try:
            token = self.auth.get_id_token(force_refresh=True)
            error = self.auth.last_error
        except Exception:
            token, error = None, "refresh_failed"
        Clock.schedule_once(
            lambda _dt: self._finish_session_restore(token, error), 0)

    def _finish_session_restore(self, token, error):
        self.session_restore_pending = False
        login = self.screen_manager.get_screen("login")
        if not token:
            if error == "invalid_refresh_token":
                message = "Your saved login expired. Please sign in again."
            elif error in {"network_error", "refresh_failed", "configuration_error"}:
                message = "Could not verify your saved login. Check your connection and sign in again."
            else:
                message = "Could not restore your saved login. Please sign in again."
            login.status.text = clean_markup(message)
            return

        self.current_user = self.auth.uid
        self.current_email = self.auth.email or ""
        self.current_display_name = self.current_email.split("@")[0]
        profile = safe_get(f"users/{self.current_user}/profile", {}) or {}
        if not isinstance(profile, dict):
            profile = {}
        self.current_display_name = profile.get(
            "display_name", self.current_display_name)
        login.status.text = ""
        self.screen_manager.current = "home"
        self.start_step_tracking()

    def check_reminder(self, _dt):
        if not self.current_user:
            return
        user = read_user()
        now = datetime.datetime.now()
        if (not user.get("reminder_enabled", True) or
                user.get("reminder_time", "08:00") != now.strftime("%H:%M") or
                self.reminder_last_sent == today_key()):
            return
        self.reminder_last_sent = today_key()
        text = "Your GRAVIX workout is waiting. Log today's training when you're done."
        if native_notification:
            try:
                native_notification.notify(
                    title="GRAVIX daily workout", message=text, timeout=10)
                return
            except Exception:
                pass
        box = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(12))
        box.add_widget(label(text, 13, TEXT))
        popup = Popup(title="GRAVIX DAILY WORKOUT", content=box,
                      size_hint=(.86, .38),
                      background_color=get_color_from_hex(CARD))
        box.add_widget(pill_button("GOT IT", lambda *_: popup.dismiss(), ACCENT, 42))
        popup.open()


if __name__ == "__main__":
    GravixApp().run()
