"""
🤖 JARVIS — Android Background Service
Yeh file tab bhi chalti hai jab main app band ho.
Wake word detect karta hai aur notification deta hai.

Buildozer mein add karo:
  services = jarvis_bg:service.py:foreground
"""

import os, time, re, json
from datetime import datetime

# ── Settings load karo ────────────────────────────
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".jarvis_settings.json")

def load_settings():
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE) as f:
                return json.load(f)
    except:
        pass
    return {"wake_word": "jarvis", "username": "Sir"}

# ── Android classes ───────────────────────────────
try:
    from android import mActivity
    from jnius import autoclass
    IS_ANDROID = True
except ImportError:
    IS_ANDROID = False

def send_notification(title, body):
    """Phone par notification bhejo — app band ho toh bhi."""
    if not IS_ANDROID:
        print(f"[NOTIFY] {title}: {body}")
        return
    try:
        context             = mActivity.getApplicationContext()
        NotificationManager = autoclass('android.app.NotificationManager')
        NotificationChannel = autoclass('android.app.NotificationChannel')
        NotificationCompat  = autoclass('androidx.core.app.NotificationCompat')
        PendingIntent       = autoclass('android.app.PendingIntent')

        CHANNEL_ID = "jarvis_alerts"
        nm = mActivity.getSystemService(context.NOTIFICATION_SERVICE)

        channel = NotificationChannel(
            CHANNEL_ID, "JARVIS Alerts",
            NotificationManager.IMPORTANCE_HIGH
        )
        nm.createNotificationChannel(channel)

        launch_intent = context.getPackageManager().getLaunchIntentForPackage(
            context.getPackageName()
        )
        pi = PendingIntent.getActivity(
            context, 0, launch_intent,
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        )

        builder = NotificationCompat.Builder(context, CHANNEL_ID)
        builder.setSmallIcon(autoclass('android.R$drawable').ic_dialog_info)
        builder.setContentTitle(title)
        builder.setContentText(body)
        builder.setPriority(NotificationCompat.PRIORITY_HIGH)
        builder.setAutoCancel(True)
        builder.setContentIntent(pi)

        nm.notify(int(time.time()) % 10000, builder.build())
    except Exception as e:
        print(f"[JARVIS Service] Notification error: {e}")

def check_reminders():
    """Pending reminders check karo aur fire karo."""
    reminders_file = os.path.join(os.path.expanduser("~"), ".jarvis_reminders.json")
    try:
        if not os.path.exists(reminders_file):
            return
        with open(reminders_file) as f:
            reminders = json.load(f)

        now     = datetime.now()
        changed = False

        for rem in reminders:
            if rem.get("done"):
                continue
            t = datetime.strptime(rem["time"], "%Y-%m-%d %H:%M:%S")
            if now >= t:
                rem["done"] = True
                changed     = True
                send_notification("⏰ JARVIS Reminder!", rem["msg"])

        if changed:
            with open(reminders_file, "w") as f:
                json.dump(reminders, f, indent=2)
    except Exception as e:
        print(f"[JARVIS Service] Reminder error: {e}")

def listen_for_wake_word(S):
    """Background mein wake word suno."""
    try:
        import speech_recognition as sr
        r   = sr.Recognizer()
        r.energy_threshold       = 250
        r.dynamic_energy_threshold = True
        r.pause_threshold        = 0.6
        mic = sr.Microphone()

        print(f"[JARVIS Service] Wake word '{S['wake_word']}' sun raha hoon...")

        while True:
            try:
                with mic as src:
                    r.adjust_for_ambient_noise(src, duration=0.3)
                    audio = r.listen(src, timeout=4, phrase_time_limit=6)

                text = r.recognize_google(
                    audio, language="hi-IN,en-US"
                ).lower().strip()

                ww = S["wake_word"].lower()
                if ww in text:
                    cmd = text.replace(ww, "").strip()
                    print(f"[JARVIS Service] Wake word detected! Command: {cmd}")
                    # Notification bhejo — user app khol ke reply de
                    send_notification(
                        "🤖 JARVIS — Wake Word Detected!",
                        f"Command: '{cmd}' — App khol ke reply lo"
                        if cmd else "App kholo — JARVIS ready hai!"
                    )

            except sr.WaitTimeoutError:
                pass  # Koi awaaz nahi — normal hai
            except sr.UnknownValueError:
                pass  # Samajh nahi aaya — normal hai
            except Exception as e:
                print(f"[JARVIS Service] Listen error: {e}")
                time.sleep(2)

    except ImportError:
        print("[JARVIS Service] speech_recognition not found — reminders only mode")
        # Sirf reminders check karte rahenge
        while True:
            check_reminders()
            time.sleep(30)

# ── MAIN LOOP ─────────────────────────────────────
if __name__ == "__main__":
    import threading
    S = load_settings()

    print(f"[JARVIS Service] Starting — User: {S.get('username','Sir')}")

    # Reminder checker thread (har 30 second)
    def reminder_loop():
        while True:
            check_reminders()
            time.sleep(30)

    threading.Thread(target=reminder_loop, daemon=True).start()

    # Wake word listener (main thread)
    listen_for_wake_word(S)
