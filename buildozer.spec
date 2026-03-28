[app]
title = Arrivals
package.name = arrivals
package.domain = org.arrivals
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0
requirements = python3,kivy==2.2.1,plyer,geopy,certifi,urllib3,idna,charset-normalizer,requests,Pillow
orientation = portrait
fullscreen = 0

android.permissions = ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,ACCESS_BACKGROUND_LOCATION,INTERNET,VIBRATE,FOREGROUND_SERVICE,FOREGROUND_SERVICE_LOCATION,WAKE_LOCK,RECEIVE_BOOT_COMPLETED

android.api = 35
android.minapi = 26
android.archs = arm64-v8a
android.accept_sdk_license = True
android.enable_androidx = True
android.gradle_dependencies = androidx.core:core:1.12.0

[buildozer]
log_level = 2
warn_on_root = 1
