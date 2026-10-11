[app]
title = GRAVIX
package.name = gravix
package.domain = com.gravix
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,json
version = 1.0.0
requirements = python3,kivy==2.3.1,requests,plyer,charset_normalizer==3.3.2
orientation = portrait
fullscreen = 0
android.api = 34
android.minapi = 24
android.ndk_api = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
android.permissions = INTERNET,ACCESS_COARSE_LOCATION,ACCESS_FINE_LOCATION,ACTIVITY_RECOGNITION,POST_NOTIFICATIONS
android.enable_androidx = True
android.private_storage = True
android.allow_backup = False
android.debug_artifact = apk
source.exclude_dirs = .git,.github,functions,node_modules,bin,.buildozer

[buildozer]
log_level = 2
warn_on_root = 1
