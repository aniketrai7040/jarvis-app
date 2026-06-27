[app]
title = JARVIS
package.name = jarvis
package.domain = com.yourname.jarvis

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json

version = 2.0.0

# MINIMAL requirements — no SDK packages, sirf jo zaruri hai
requirements = python3,kivy==2.3.0,android,pyjnius

android.permissions = INTERNET,RECORD_AUDIO,CAMERA,FOREGROUND_SERVICE,VIBRATE,MODIFY_AUDIO_SETTINGS,RECEIVE_BOOT_COMPLETED

android.minapi = 26
android.api    = 33
android.ndk    = 25b
android.sdk    = 33
android.archs  = arm64-v8a, armeabi-v7a

services = jarvis_bg:service.py:foreground

orientation = portrait
fullscreen   = 0

android.features = android.hardware.microphone

android.manifest.attributes = android:foregroundServiceType="microphone"

[buildozer]
log_level    = 2
warn_on_root = 1
