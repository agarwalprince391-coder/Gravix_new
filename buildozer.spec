[app]

# (str) Title of your application
title = GRAVIX

# (str) Package name
package.name = gravix

# (str) Package domain (needed for android packaging)
package.domain = org.gravix

# (list) Source files to include
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,db

# (list) Application requirements
requirements = python3,kivy,requests

# (str) Supported orientations
orientation = portrait

# (list) Permissions
android.permissions = INTERNET

source.main = main.py
fullscreen = 0
android.api = 35
android.minapi = 23
android.archs = arm64-v8a
android.accept_sdk_license = True
[buildozer]
# (int) Log level (0 = error only, 1 = info, 2 = debug)
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 0
