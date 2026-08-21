from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.popup import Popup
from kivy.core.window import Window
from kivy.utils import get_color_from_hex
import requests
import json

# --- PASTE YOUR FIREBASE URL HERE ---
FIREBASE_URL = "https://gravix-7b589-default-rtdb.asia-southeast1.firebasedatabase.app" 

Window.clearcolor = get_color_from_hex('#121212') 

def get_db_url(endpoint):
    base = FIREBASE_URL.rstrip('/')
    return f"{base}/{endpoint}.json"

class LoginScreen(Screen):
    """New Login & Registration Screen"""
    def __init__(self, **kwargs):
        super(LoginScreen, self).__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=40, spacing=20)
        
        # Title Header
        title = Label(
            text="[b]GRAVIX LOGIN[/b]", 
            markup=True, 
            size_hint_y=None, height=60, 
            font_size=28,
            color=get_color_from_hex('#E53935')
        )
        self.layout.add_widget(title)
        
        # Input fields
        self.username_input = TextInput(hint_text='Enter Username', multiline=False, size_hint_y=None, height=50)
        self.password_input = TextInput(hint_text='Enter Password', password=True, multiline=False, size_hint_y=None, height=50)
        
        self.layout.add_widget(self.username_input)
        self.layout.add_widget(self.password_input)
        
        # Login Button
        login_btn = Button(
            text='LOGIN', 
            size_hint_y=None, height=55,
            background_normal='', background_color=get_color_from_hex('#E53935'), bold=True
        )
        login_btn.bind(on_release=self.login_user)
        self.layout.add_widget(login_btn)
        
        # Register Button
        register_btn = Button(
            text='CREATE ACCOUNT', 
            size_hint_y=None, height=55,
            background_normal='', background_color=get_color_from_hex('#43A047'), bold=True
        )
        register_btn.bind(on_release=self.register_user)
        self.layout.add_widget(register_btn)
        
        # Status/Feedback Label
        self.status_label = Label(text="", color=get_color_from_hex('#FFD700'), size_hint_y=None, height=40)
        self.layout.add_widget(self.status_label)
        
        self.add_widget(self.layout)

    def login_user(self, instance):
        username = self.username_input.text.strip().lower()
        password = self.password_input.text.strip()
        
        if not username or not password:
            self.status_label.text = "Please enter both username and password."
            return
            
        try:
            res = requests.get(get_db_url(f"users/{username}"))
            user_data = res.json()
            
            if user_data and user_data.get('password') == password:
                # Save active user globally in the App instance
                App.get_running_app().current_user = username
                self.manager.current = 'home'
            else:
                self.status_label.text = "Invalid username or password."
        except Exception as e:
            self.status_label.text = "Cloud connection error."

    def register_user(self, instance):
        username = self.username_input.text.strip().lower()
        password = self.password_input.text.strip()
        
        if not username or not password:
            self.status_label.text = "Username and password cannot be empty."
            return
            
        try:
            # Check if user already exists
            res = requests.get(get_db_url(f"users/{username}"))
            if res.json() is not None:
                self.status_label.text = "Username already taken!"
                return
                
            # Create new user record in Firebase
            new_user = {
                "username": username,
                "password": password,
                "level": 0,
                "xp": 0
            }
            requests.put(get_db_url(f"users/{username}"), json=new_user)
            
            App.get_running_app().current_user = username
            self.manager.current = 'home'
        except Exception as e:
            self.status_label.text = "Registration failed."


class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super(HomeScreen, self).__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=20, spacing=15)
        
        # --- PLAYER DASHBOARD ---
        self.profile_layout = BoxLayout(size_hint_y=None, height=80, orientation='vertical')
        self.username_label = Label(text="[b]PLAYER[/b]", markup=True, color=get_color_from_hex('#E53935'), font_size=24)
        self.stats_label = Label(text="Level: 0  |  XP: 0 / 100", color=get_color_from_hex('#FFFFFF'), font_size=16)
        self.profile_layout.add_widget(self.username_label)
        self.profile_layout.add_widget(self.stats_label)
        self.layout.add_widget(self.profile_layout)
        
        # --- SKILLS AREA ---
        self.scroll = ScrollView()
        self.skills_grid = GridLayout(cols=1, spacing=15, size_hint_y=None)
        self.skills_grid.bind(minimum_height=self.skills_grid.setter('height'))
        self.scroll.add_widget(self.skills_grid)
        self.layout.add_widget(self.scroll)
        
        # --- NAVIGATION ---
        add_btn = Button(
            text='ADD SKILL TO CLOUD', 
            size_hint_y=None, height=55,
            background_normal='', background_color=get_color_from_hex('#43A047'), bold=True
        )
        add_btn.bind(on_release=self.go_to_add_skill)
        self.layout.add_widget(add_btn)
        
        self.add_widget(self.layout)

    def on_enter(self):
        # Dynamically fetch data for whoever just logged in!
        app = App.get_running_app()
        self.username = getattr(app, 'current_user', 'player1')
        self.username_label.text = f"[b]{self.username.upper()}[/b]"
        
        self.load_user_profile()
        self.load_skills()

    def load_user_profile(self):
        try:
            res = requests.get(get_db_url(f"users/{self.username}"))
            user = res.json()
            if user:
                self.current_level = user.get('level', 0)
                self.current_xp = user.get('xp', 0)
                self.xp_needed = 100 + (self.current_level * 50)
                self.stats_label.text = f"Level: {self.current_level}  |  XP: {self.current_xp} / {self.xp_needed}"
        except Exception as e:
            print(f"Error loading profile: {e}")

    def load_skills(self):
        self.skills_grid.clear_widgets()
        try:
            res = requests.get(get_db_url("skills"))
            skills_data = res.json()
            
            if skills_data:
                for skill_id, skill in skills_data.items():
                    skill_name = skill.get('skill_name', 'Unknown')
                    difficulty = skill.get('difficulty', 'C Tier')
                    req_level = skill.get('required_level', 0)
                    
                    if self.current_level >= req_level:
                        btn_color = '#E53935' 
                        btn_text = f"[b]{skill_name}[/b]\nUnlocked ({difficulty})"
                    else:
                        btn_color = '#424242' 
                        btn_text = f"[b]{skill_name}[/b]\nUnlocks at Level {req_level}"
                        
                    skill_btn = Button(
                        text=btn_text, markup=True, halign='center',
                        size_hint_y=None, height=80,
                        background_normal='', background_color=get_color_from_hex(btn_color)
                    )
                    skill_btn.bind(on_release=lambda btn, s_name=skill_name, r_lvl=req_level, diff=difficulty: self.skill_clicked(s_name, r_lvl, diff))
                    self.skills_grid.add_widget(skill_btn)
        except Exception as e:
            print(f"Error loading skills: {e}")

    def skill_clicked(self, skill_name, req_level, difficulty):
        popup_content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        if self.current_level >= req_level:
            diff_lower = difficulty.lower()
            if 's' in diff_lower:
                xp_reward = 500
            elif 'a' in diff_lower:
                xp_reward = 250
            elif 'b' in diff_lower:
                xp_reward = 100
            else:
                xp_reward = 50

            msg = f"Workout instructions for {skill_name}.\n\nReward: +{xp_reward} XP"
            title = f"{skill_name} (UNLOCKED)"
            
            popup_content.add_widget(Label(text=msg, halign='center'))
            
            complete_btn = Button(
                text=f"COMPLETE WORKOUT (+{xp_reward} XP)", 
                size_hint_y=None, height=50,
                background_normal='', background_color=get_color_from_hex('#43A047'), bold=True
            )
            popup_content.add_widget(complete_btn)
            
        else:
            msg = f"You must reach Level {req_level} to unlock this skill."
            title = "SKILL LOCKED"
            popup_content.add_widget(Label(text=msg, halign='center'))
            
        close_btn = Button(text="Close", size_hint_y=None, height=40)
        popup_content.add_widget(close_btn)
        
        self.popup = Popup(title=title, content=popup_content, size_hint=(0.8, 0.4))
        close_btn.bind(on_release=self.popup.dismiss)
        
        if self.current_level >= req_level:
            complete_btn.bind(on_release=lambda instance: self.grant_xp(xp_reward))
            
        self.popup.open()

    def grant_xp(self, amount):
        self.current_xp += amount
        initial_level = self.current_level
        
        threshold = 100 + (self.current_level * 50)
        while self.current_xp >= threshold:
            self.current_xp -= threshold
            self.current_level += 1
            threshold = 100 + (self.current_level * 50)
            
        try:
            update_data = {"level": self.current_level, "xp": self.current_xp}
            requests.patch(get_db_url(f"users/{self.username}"), json=update_data)
        except Exception as e:
            print(f"Error updating XP: {e}")
        
        self.popup.dismiss()
        self.load_user_profile()
        self.load_skills()
        
        if self.current_level > initial_level:
            self.show_level_up_popup(self.current_level)

    def show_level_up_popup(self, new_level):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        msg = f"[b]Congratulations on Level Up![/b]\n\nYou are now Level {new_level}!"
        content.add_widget(Label(text=msg, markup=True, halign='center', color=get_color_from_hex('#1976D2')))
        
        close_btn = Button(
            text="CONTINUE", 
            size_hint_y=None, height=50, 
            background_normal='', background_color=get_color_from_hex('#43A047'), bold=True
        )
        content.add_widget(close_btn)
        
        lvl_popup = Popup(title="LEVEL UP!", content=content, size_hint=(0.8, 0.4))
        close_btn.bind(on_release=lvl_popup.dismiss)
        lvl_popup.open()

    def go_to_add_skill(self, instance):
        self.manager.current = 'add_skill'


class AddSkillScreen(Screen):
    def __init__(self, **kwargs):
        super(AddSkillScreen, self).__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=20, spacing=15)
        
        self.layout.add_widget(Label(text="[b]ADD NEW SKILL[/b]", markup=True, size_hint_y=None, height=50, font_size=20))
        
        self.name_input = TextInput(hint_text='Skill Name (e.g., Handstand)', multiline=False, size_hint_y=None, height=45)
        self.diff_input = TextInput(hint_text='Difficulty (S, A, B, or C Tier)', multiline=False, size_hint_y=None, height=45)
        self.level_input = TextInput(hint_text='Required Level to Unlock (e.g., 10)', multiline=False, size_hint_y=None, height=45)
        
        self.layout.add_widget(self.name_input)
        self.layout.add_widget(self.diff_input)
        self.layout.add_widget(self.level_input)
        
        save_btn = Button(text='SAVE SKILL TO CLOUD', size_hint_y=None, height=55, background_normal='', background_color=get_color_from_hex('#43A047'), bold=True)
        save_btn.bind(on_release=self.save_skill)
        self.layout.add_widget(save_btn)
        
        back_btn = Button(text='CANCEL', size_hint_y=None, height=55, background_normal='', background_color=get_color_from_hex('#757575'), bold=True)
        back_btn.bind(on_release=self.go_back)
        self.layout.add_widget(back_btn)
        
        self.add_widget(self.layout)

    def save_skill(self, instance):
        name = self.name_input.text
        diff = self.diff_input.text
        req_level = self.level_input.text
        
        if name and req_level.isdigit():
            skill_data = {
                "skill_name": name,
                "difficulty": diff,
                "required_level": int(req_level)
            }
            try:
                requests.post(get_db_url("skills"), json=skill_data)
            except Exception as e:
                print(f"Error saving skill: {e}")
            
            self.name_input.text = ''
            self.diff_input.text = ''
            self.level_input.text = ''
            self.manager.current = 'home'

    def go_back(self, instance):
        self.manager.current = 'home'


class CalisthenicsApp(App):
    def build(self):
        self.title = 'GRAVIX'
        self.current_user = None
        
        sm = ScreenManager()
        sm.add_widget(LoginScreen(name='login'))
        sm.add_widget(HomeScreen(name='home'))
        sm.add_widget(AddSkillScreen(name='add_skill'))
        return sm

if __name__ == '__main__':
    CalisthenicsApp().run()
