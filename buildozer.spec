[app]

# (str) Title of your application
title = GRAVIX

# (str) Package name
package.name = gravix

# (str) Package domain
package.domain = org.gravix

# (str) Source directory
source.dir = .

# (str) Application version
version = 1.0

# (list) Source files to include
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,db

# (list) Application requirements
requirements = python3,kivy,requests

# (str) Supported orientations
orientation = portrait

# (list) Permissions
android.permissions = INTERNET

# (bool) Fullscreen
fullscreen = 0

# (int) Android API
android.api = 35

# (int) Minimum Android API
android.minapi = 26

# (list) Android architectures
android.archs = arm64-v8a

# (bool) Accept Android SDK license
android.accept_sdk_license = True


[buildozer]

# (int) Log level
log_level = 2

# (int) Display warning if buildozer is run as root
warn_on_root = 0
