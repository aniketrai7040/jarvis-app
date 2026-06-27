"""
🤖 JARVIS — 100% Android-Ready Version
- Zero external SDK dependencies (sirf stdlib + kivy + pyjnius)
- Voice: Android SpeechRecognizer (native, no pyaudio)
- TTS: Android TextToSpeech (native)
- API calls: urllib only (no anthropic/openai/google packages)
- Storage: Android-safe paths
"""

import os, json, re, threading, time
from datetime import datetime, timedelta

from kivy.app import App
from kivy.uix.boxlayout    import BoxLayout
from kivy.uix.floatlayout  import FloatLayout
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.label        import Label
from kivy.uix.button       import Button
from kivy.uix.textinput    import TextInput
from kivy.uix.scrollview   import ScrollView
from kivy.uix.widget       import Widget
from kivy.uix.popup        import Popup
from kivy.graphics         import Color, Ellipse, Rectangle, RoundedRectangle
from kivy.animation        import Animation
from kivy.clock            import Clock
from kivy.utils            import platform
from kivy.core.window      import Window
from kivy.metrics          import dp

# ═══════════════════════════════════════════════════════════════
# ANDROID SAFE STORAGE PATH
# ═══════════════════════════════════════════════════════════════
def _data_dir():
    """Android pe internal storage path, desktop pe home dir."""
    if platform == 'android':
        try:
            from android import mActivity
            ctx = mActivity.getApplicationContext()
            d = ctx.getFilesDir().getAbsolutePath()
            return d
        except Exception:
            pass
    return os.path.expanduser("~")

DATA_DIR       = _data_dir()
SETTINGS_FILE  = os.path.join(DATA_DIR, "jarvis_settings.json")
REMINDERS_FILE = os.path.join(DATA_DIR, "jarvis_reminders.json")
NOTES_FILE     = os.path.join(DATA_DIR, "jarvis_notes.json")
BRAIN_FILE     = os.path.join(DATA_DIR, "jarvis_brain.json")

# ═══════════════════════════════════════════════════════════════
# COLORS
# ═══════════════════════════════════════════════════════════════
BG       = (0.05, 0.05, 0.12, 1)
GOLD     = (0.96, 0.62, 0.04, 1)
GOLD_DIM = (0.96, 0.62, 0.04, 0.25)
TEXT     = (0.88, 0.91, 0.94, 1)
DIM      = (0.58, 0.64, 0.71, 1)
U_BUB    = (0.15, 0.15, 0.30, 1)
B_BUB    = (0.10, 0.35, 0.25, 1)
HDR      = (0.08, 0.08, 0.18, 1)
CARD     = (0.09, 0.09, 0.20, 1)
GREEN    = (0.06, 0.73, 0.51, 1)
RED      = (0.93, 0.27, 0.27, 1)

# ═══════════════════════════════════════════════════════════════
# SETTINGS
# ═══════════════════════════════════════════════════════════════
DEFAULT_SETTINGS = {
    "claude_key":   "", "gemini_key":   "", "deepseek_key": "",
    "ai4_name":     "", "ai4_key":      "", "ai4_base_url": "",
    "ai5_name":     "", "ai5_key":      "", "ai5_base_url": "",
    "primary_ai":   "claude",
    "username":     "Sir",
    "wake_word":    "jarvis",
    "personality":  "friendly",
    "tts_enabled":  True,
}

def load_settings():
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return {**DEFAULT_SETTINGS, **json.load(f)}
    except Exception:
        pass
    return DEFAULT_SETTINGS.copy()

def save_settings(s):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[JARVIS] save_settings error: {e}")
        return False

S = load_settings()

# ═══════════════════════════════════════════════════════════════
# JSON HELPERS
# ═══════════════════════════════════════════════════════════════
def _load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default() if callable(default) else default

def _save_json(path, data):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[JARVIS] _save_json {path} error: {e}")

def load_reminders():  return _load_json(REMINDERS_FILE, list)
def save_reminders(r): _save_json(REMINDERS_FILE, r)
def load_notes():      return _load_json(NOTES_FILE, list)
def save_notes(n):     _save_json(NOTES_FILE, n)

# ═══════════════════════════════════════════════════════════════
# BRAIN
# ═══════════════════════════════════════════════════════════════
_BRAIN_DEFAULT = {
    "user_facts": [], "preferences": {}, "routine": {},
    "mood_history": [], "conversation_count": 0,
    "learned_responses": {},
    "speaking_style": {"avg_msg_length": 5, "preferred_lang": "hinglish",
                       "common_words": [], "msg_count": 0}
}
BRAIN = _load_json(BRAIN_FILE, lambda: _BRAIN_DEFAULT.copy())
for k, v in _BRAIN_DEFAULT.items():
    BRAIN.setdefault(k, v)

def save_brain(): _save_json(BRAIN_FILE, BRAIN)

# ═══════════════════════════════════════════════════════════════
# ANDROID TTS — Native, no pyttsx3
# ═══════════════════════════════════════════════════════════════
_tts_engine  = None
_tts_ready   = False
_tts_lock    = threading.Lock()

def _init_tts():
    global _tts_engine, _tts_ready
    if platform != 'android':
        return
    try:
        from jnius import autoclass, PythonJavaClass, java_method
        from android import mActivity

        TextToSpeech = autoclass('android.speech.tts.TextToSpeech')
        Locale       = autoclass('java.util.Locale')

        class TTSListener(PythonJavaClass):
            __javainterfaces__ = ['android/speech/tts/TextToSpeech$OnInitListener']
            __javacontext__    = 'app'

            @java_method('(I)V')
            def onInit(self, status):
                global _tts_ready
                if status == 0:  # SUCCESS
                    try:
                        _tts_engine.setLanguage(Locale.forLanguageTag("hi-IN"))
                    except Exception:
                        try:
                            _tts_engine.setLanguage(Locale.ENGLISH)
                        except Exception:
                            pass
                    _tts_ready = True
                    print("[JARVIS TTS] Ready!")
                else:
                    print(f"[JARVIS TTS] Init failed: {status}")

        listener = TTSListener()
        ctx = mActivity.getApplicationContext()
        _tts_engine = TextToSpeech(ctx, listener)
    except Exception as e:
        print(f"[JARVIS TTS] Init error: {e}")

def speak(text):
    if not S.get("tts_enabled", True):
        return
    clean = re.sub(r'[^\w\s\.,!?\-]', ' ', text[:250]).strip()
    if not clean:
        return
    if platform == 'android':
        def _do():
            global _tts_engine, _tts_ready
            try:
                if _tts_engine is None or not _tts_ready:
                    return
                from jnius import autoclass
                TextToSpeech = autoclass('android.speech.tts.TextToSpeech')
                _tts_engine.speak(clean, TextToSpeech.QUEUE_FLUSH, None, None)
            except Exception as e:
                print(f"[JARVIS TTS] speak error: {e}")
        threading.Thread(target=_do, daemon=True).start()
    else:
        # Desktop fallback
        try:
            import subprocess
            subprocess.Popen(['espeak', '-s', '140', clean],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

# ═══════════════════════════════════════════════════════════════
# ANDROID VOICE INPUT — Native SpeechRecognizer (no pyaudio)
# ═══════════════════════════════════════════════════════════════
_voice_callback = None   # set by MainScreen

def _android_voice_listen(on_result, on_error):
    """
    Android native SpeechRecognizer — Intent-based, no mic permission issue.
    on_result(text): called with recognized text
    on_error(msg):   called on failure
    """
    try:
        from jnius import autoclass, PythonJavaClass, java_method
        from android import mActivity

        SpeechRecognizer      = autoclass('android.speech.SpeechRecognizer')
        RecognitionListener   = autoclass('android.speech.RecognitionListener')
        Intent                = autoclass('android.content.Intent')
        RecognizerIntent      = autoclass('android.speech.RecognizerIntent')
        Bundle                = autoclass('android.os.Bundle')

        class MyListener(PythonJavaClass):
            __javainterfaces__ = ['android/speech/RecognitionListener']
            __javacontext__    = 'app'

            @java_method('(Landroid/os/Bundle;)V')
            def onReadyForSpeech(self, params): pass

            @java_method('()V')
            def onBeginningOfSpeech(self): pass

            @java_method('(F)V')
            def onRmsChanged(self, rmsdB): pass

            @java_method('(Landroid/os/Bundle;)V')
            def onBufferReceived(self, buffer): pass

            @java_method('(I)V')
            def onEndOfSpeech(self): pass

            @java_method('(II)V')
            def onError(self, error, suggestedAction):
                msgs = {1:"Network timeout", 2:"Network error", 3:"Audio error",
                        4:"Server error", 5:"Client error", 6:"Speech timeout",
                        7:"Nothing heard", 8:"Recognizer busy", 9:"Insufficient permissions"}
                Clock.schedule_once(lambda dt: on_error(msgs.get(error, f"Error {error}")), 0)

            @java_method('(Landroid/os/Bundle;)V')
            def onResults(self, results):
                try:
                    matches = results.getStringArrayList(RecognizerIntent.EXTRA_RESULTS)
                    if matches and matches.size() > 0:
                        text = matches.get(0)
                        Clock.schedule_once(lambda dt: on_result(text), 0)
                    else:
                        Clock.schedule_once(lambda dt: on_error("Koi awaaz nahi suni"), 0)
                except Exception as e:
                    Clock.schedule_once(lambda dt: on_error(str(e)), 0)

            @java_method('(Landroid/os/Bundle;)V')
            def onPartialResults(self, partialResults): pass

            @java_method('(ILandroid/os/Bundle;)V')
            def onEvent(self, eventType, params): pass

        def _start():
            try:
                ctx        = mActivity.getApplicationContext()
                recognizer = SpeechRecognizer.createSpeechRecognizer(ctx)
                listener   = MyListener()
                recognizer.setRecognitionListener(listener)

                intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "hi-IN")
                intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, "hi-IN")
                intent.putExtra(RecognizerIntent.EXTRA_ONLY_RETURN_LANGUAGE_RESULTS, True)
                intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
                intent.putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 1500)
                intent.putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 1000)

                recognizer.startListening(intent)
            except Exception as e:
                Clock.schedule_once(lambda dt: on_error(str(e)), 0)

        # SpeechRecognizer must run on main thread
        Clock.schedule_once(lambda dt: _start(), 0)

    except Exception as e:
        Clock.schedule_once(lambda dt: on_error(str(e)), 0)

# ═══════════════════════════════════════════════════════════════
# AI CALLS — pure urllib, zero SDK
# ═══════════════════════════════════════════════════════════════
def _http_post(url, headers, body_dict):
    """Simple blocking HTTP POST, returns parsed JSON or raises."""
    import urllib.request, json as _j
    data = _j.dumps(body_dict).encode("utf-8")
    req  = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=25) as resp:
        return _j.loads(resp.read().decode("utf-8"))

def _build_system():
    name  = S["username"]
    facts = BRAIN.get("user_facts", [])
    style = BRAIN.get("speaking_style", {})
    lang  = style.get("preferred_lang", "hinglish")
    ctx   = ""
    if facts:
        ctx += "User ke baare mein: " + "; ".join(facts[-5:]) + "\n"
    moods = BRAIN.get("mood_history", [])
    if moods:
        ctx += f"Recent mood: {moods[-1]['mood']}\n"
    ctx += f"User ki preferred language: {lang}\n"
    return (
        f"You are JARVIS, a friendly AI assistant for {name}. "
        f"Reply in Hinglish (mix Hindi+English naturally). "
        f"Be warm, concise, helpful. Max 80 words. "
        f"Address user as '{name}'.\n{ctx}"
    )

def call_ai(prompt, history=None, mood="neutral"):
    if history is None:
        history = []
    ai  = S["primary_ai"]
    sys = _build_system()

    # ── Claude (Anthropic REST) ──────────────────────────────
    if ai == "claude" and S.get("claude_key"):
        try:
            msgs = (history[-10:] + [{"role": "user", "content": prompt}])
            data = _http_post(
                "https://api.anthropic.com/v1/messages",
                {"x-api-key": S["claude_key"],
                 "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
                {"model": "claude-haiku-4-5-20251001",
                 "max_tokens": 300, "system": sys, "messages": msgs}
            )
            return data["content"][0]["text"].strip()
        except Exception as e:
            return f"❌ Claude error: {str(e)[:100]}"

    # ── Gemini (REST) ────────────────────────────────────────
    if ai == "gemini" and S.get("gemini_key"):
        try:
            import urllib.parse
            url = ("https://generativelanguage.googleapis.com/v1beta/models/"
                   f"gemini-1.5-flash:generateContent?key={S['gemini_key']}")
            data = _http_post(url, {"Content-Type": "application/json"}, {
                "contents": [{"role": "user",
                              "parts": [{"text": sys + "\n\nUser: " + prompt}]}]
            })
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            return f"❌ Gemini error: {str(e)[:100]}"

    # ── DeepSeek (OpenAI-compatible REST) ───────────────────
    if ai == "deepseek" and S.get("deepseek_key"):
        try:
            msgs = ([{"role": "system", "content": sys}]
                    + history[-10:]
                    + [{"role": "user", "content": prompt}])
            data = _http_post(
                "https://api.deepseek.com/v1/chat/completions",
                {"Authorization": f"Bearer {S['deepseek_key']}",
                 "Content-Type": "application/json"},
                {"model": "deepseek-chat", "messages": msgs, "max_tokens": 300}
            )
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return f"❌ DeepSeek error: {str(e)[:100]}"

    # ── Custom AI slot 4 & 5 (OpenAI-compatible) ────────────
    for slot in ("ai4", "ai5"):
        slot_name = S.get(f"{slot}_name", "").strip().lower()
        slot_key  = S.get(f"{slot}_key",  "").strip()
        slot_url  = S.get(f"{slot}_base_url", "").strip().rstrip("/")
        if slot_name and ai == slot_name and slot_key:
            try:
                url  = (slot_url or "https://api.openai.com/v1") + "/chat/completions"
                msgs = ([{"role": "system", "content": sys}]
                        + history[-10:]
                        + [{"role": "user", "content": prompt}])
                data = _http_post(
                    url,
                    {"Authorization": f"Bearer {slot_key}",
                     "Content-Type": "application/json"},
                    {"model": slot_name, "messages": msgs, "max_tokens": 300}
                )
                return data["choices"][0]["message"]["content"].strip()
            except Exception as e:
                return f"❌ {slot_name} error: {str(e)[:100]}"

    return "⚠️ Koi AI key set nahi hai. Settings (⚙️) mein jaake key daalo!"

# ═══════════════════════════════════════════════════════════════
# OFFLINE RESPONSES
# ═══════════════════════════════════════════════════════════════
def offline_response(cmd):
    c, name = cmd.lower(), S["username"]
    if any(w in c for w in ["hello","hi","namaskar","hey"]):
        return f"Namaskar, {name}! Kya hukum hai? 🙏"
    if "time" in c or "samay" in c:
        return f"🕐 Abhi {datetime.now().strftime('%I:%M %p')} baj rahe hain"
    if "date" in c or "aaj" in c:
        return f"📅 Aaj {datetime.now().strftime('%A, %d %B %Y')} hai"
    if "kaun" in c or "who are you" in c:
        return "Main JARVIS hoon — aapka personal AI assistant! 🤖"
    if any(w in c for w in ["thanks","shukriya","dhanyavad","thank you"]):
        return f"Humesha aapki seva mein hazir, {name}! 😊"
    return None

# ═══════════════════════════════════════════════════════════════
# MOOD
# ═══════════════════════════════════════════════════════════════
def detect_mood(text):
    t = text.lower()
    if any(w in t for w in ["khush","mast","badhiya","great","happy","excited","zabardast"]):
        return "happy"
    if any(w in t for w in ["dukhi","sad","bura lag","takleef","pareshaan","tension","stressed"]):
        return "sad"
    if any(w in t for w in ["thaka","tired","neend","so jana","rest","aaraam"]):
        return "tired"
    if any(w in t for w in ["gussa","angry","irritate","frustrat","bakwaas"]):
        return "angry"
    if any(w in t for w in ["bored","kuch nahi","kya karu","timepass"]):
        return "bored"
    return "neutral"

def mood_prefix(mood):
    name = S["username"]
    return {
        "happy": f"Bahut acha, {name}! Khushi dekhke mujhe bhi achha laga! 😊 ",
        "sad":   f"Arre {name}, kya hua? Main hoon na. 🤗 ",
        "tired": f"Lagta hai thak gaye, {name}. Thodi rest lo. ☕ ",
        "angry": f"Shant rahein, {name}. Sab theek ho jaayega. 😌 ",
        "bored": f"Bore ho gaye? Chalo kuch karte hain, {name}! 🎯 ",
    }.get(mood, "")

# ═══════════════════════════════════════════════════════════════
# BRAIN / LEARNING
# ═══════════════════════════════════════════════════════════════
def learn_from_conversation(user_text, ai_resp):
    t = user_text.lower()
    BRAIN["conversation_count"] = BRAIN.get("conversation_count", 0) + 1
    facts = BRAIN.get("user_facts", [])
    if "mera naam" in t or "my name is" in t:
        m = re.search(r'(mera naam|my name is)\s+(\w+)', t)
        if m:
            f = f"Naam: {m.group(2)}"
            if f not in facts: facts.append(f)
    if any(w in t for w in ["mujhe pasand","i like","mera favourite"]):
        facts.append(f"Pasand: {user_text[:60]}")
    BRAIN["user_facts"] = facts[-20:]

    mood = detect_mood(user_text)
    if mood != "neutral":
        hist = BRAIN.get("mood_history", [])
        hist.append({"mood": mood, "time": datetime.now().strftime("%d %b %H:%M")})
        BRAIN["mood_history"] = hist[-10:]

    # Style
    words = user_text.split()
    style = BRAIN.get("speaking_style", {})
    cnt   = style.get("msg_count", 0) + 1
    avg   = style.get("avg_msg_length", 5)
    style["avg_msg_length"] = round((avg * (cnt-1) + len(words)) / cnt, 1)
    style["msg_count"]      = cnt
    BRAIN["speaking_style"] = style
    save_brain()

# ═══════════════════════════════════════════════════════════════
# REMINDERS
# ═══════════════════════════════════════════════════════════════
def is_reminder_request(text):
    return any(w in text.lower() for w in
               ["yaad dila","remind","reminder","alarm","bata dena","bhulna nahi"])

def parse_reminder(text):
    t, now = text.lower(), datetime.now()
    target = None
    m = re.search(r'(\d{1,2})(?::(\d{2}))?\s*baj', t)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
        if any(w in t for w in ["shaam","evening","raat","night"]) and hour < 12:
            hour += 12
        elif hour < 7:
            hour += 12
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target < now: target += timedelta(days=1)
    m2 = re.search(r'(\d+)\s*(minute|min|ghante|hour)', t)
    if not target and m2:
        val = int(m2.group(1))
        target = now + (timedelta(hours=val) if "ghante" in m2.group(2) or "hour" in m2.group(2)
                        else timedelta(minutes=val))
    if not target:
        return None
    msg = re.sub(r'\d+.*?baj.*?\s', '', text, flags=re.IGNORECASE)
    msg = re.sub(r'\d+\s*(minute|min|ghante|hour)[^\s]*\s*mein\s*', '', msg, flags=re.IGNORECASE)
    msg = re.sub(r'^(yaad\s*dila[a-z]*|remind\s*me|reminder|set|lagao|do)', '', msg,
                 flags=re.IGNORECASE).strip()
    return {"time": target.strftime("%Y-%m-%d %H:%M:%S"), "msg": msg or "Aapka reminder!", "done": False}

# ═══════════════════════════════════════════════════════════════
# NOTES
# ═══════════════════════════════════════════════════════════════
def is_note_request(text):
    return any(w in text.lower() for w in ["note","likh","save kar","yaad rakh","note karo"])

def is_show_notes(text):
    return any(w in text.lower() for w in ["notes dikhao","meri notes","notes batao","saved notes"])

def handle_note(text, notes):
    m = re.search(r'(\d+)(wa|ra|th|st|nd)?\s*(note|wala)\s*(hata|delete|mita)', text.lower())
    if m:
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(notes):
            removed = notes.pop(idx); save_notes(notes)
            return f"🗑️ Note hata diya: '{removed['text']}'"
        return "❌ Itna note nahi mila!"
    note_text = re.sub(r'(note karo|note kar|likh lo|save kar|yaad rakh|note)\s*[:-]?\s*',
                       '', text, flags=re.IGNORECASE).strip()
    if note_text:
        notes.append({"text": note_text, "time": datetime.now().strftime("%d %b %I:%M %p")})
        save_notes(notes)
        return f"📝 Note save: '{note_text}'"
    return "❌ Kya likhun? Note ke baad text bhi bolo!"

def show_notes(notes):
    if not notes:
        return "📝 Koi notes nahi hain. 'Note karo: ...' bol ke save karo!"
    return "📝 Aapke Notes:\n" + "\n".join(f"{i}. {n['text']}  [{n['time']}]"
                                            for i, n in enumerate(notes, 1))

# ═══════════════════════════════════════════════════════════════
# CALCULATOR
# ═══════════════════════════════════════════════════════════════
def is_calc_request(text):
    return (any(w in text.lower() for w in ["kitna hai","calculate","plus","minus","percent"])
            or bool(re.search(r'\d+\s*[\+\-\*\/x×÷]\s*\d+', text)))

def handle_calc(text):
    t = (text.lower()
         .replace("plus","+").replace("aur","+").replace("minus","-")
         .replace("multiply","*").replace("guna","*").replace("×","*")
         .replace("divide","/").replace("bhaag","/").replace("÷","/")
         .replace("percent","/100*").replace("%","/100*100"))
    t = re.sub(r'[^0-9\+\-\*\/\.\(\)\s]', '', t).strip()
    if not t: return "❌ Calculation samajh nahi aaya!"
    try:
        if all(c in "0123456789+-*/.() " for c in t):
            result = eval(t)
            if isinstance(result, float) and result.is_integer(): result = int(result)
            return f"🧮 {text.strip()} = {result}"
    except Exception:
        pass
    return "❌ Calculation mein galti hai!"

# ═══════════════════════════════════════════════════════════════
# WEATHER
# ═══════════════════════════════════════════════════════════════
def is_weather_request(text):
    return any(w in text.lower() for w in ["weather","mausam","barish","temperature","garmi","sardi"])

def handle_weather(text):
    import urllib.request, urllib.parse
    city = "Delhi"
    try:
        req = urllib.request.Request("http://ip-api.com/json/?fields=city",
                                     headers={"User-Agent": "curl/7"})
        with urllib.request.urlopen(req, timeout=5) as r:
            d = json.loads(r.read().decode())
            if d.get("city"): city = d["city"]
    except Exception:
        pass
    for c in ["mumbai","delhi","bangalore","hyderabad","chennai","kolkata",
              "pune","jaipur","lucknow","ahmedabad","indore","noida","gurgaon"]:
        if c in text.lower():
            city = c.title(); break
    try:
        url = f"https://wttr.in/{urllib.parse.quote(city)}?format=3"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return f"🌤️ {r.read().decode().strip()}"
    except Exception as e:
        return f"❌ Weather nahi mila. Internet check karo! ({str(e)[:50]})"

# ═══════════════════════════════════════════════════════════════
# ANDROID — FLASHLIGHT
# ═══════════════════════════════════════════════════════════════
_flash_on = False

def is_flash_request(text):
    return any(w in text.lower() for w in ["flashlight","torch","torchlight","roshni"])

def handle_flashlight(text):
    global _flash_on
    if platform != 'android':
        return "❌ Flashlight sirf Android pe kaam karta hai!"
    try:
        from jnius import autoclass
        from android import mActivity
        Context       = autoclass('android.content.Context')
        cm = mActivity.getSystemService(Context.CAMERA_SERVICE)
        cam_id  = cm.getCameraIdList()[0]
        turn_on = (any(w in text.lower() for w in ["on","chalu","jala"])
                   or (not any(w in text.lower() for w in ["off","band","bujha"]) and not _flash_on))
        cm.setTorchMode(cam_id, turn_on)
        _flash_on = turn_on
        return "🔦 Torch on!" if turn_on else "🔦 Torch off!"
    except Exception as e:
        return f"❌ Torch error: {str(e)[:60]}"

# ═══════════════════════════════════════════════════════════════
# ANDROID — VOLUME
# ═══════════════════════════════════════════════════════════════
def is_volume_request(text):
    return any(w in text.lower() for w in ["volume","awaaz","awaz","sound","mute","unmute","silent"])

def handle_volume(text):
    if platform != 'android':
        return "❌ Volume sirf Android pe!"
    try:
        from jnius import autoclass
        from android import mActivity
        Context      = autoclass('android.content.Context')
        AudioManager = autoclass('android.media.AudioManager')
        am = mActivity.getSystemService(Context.AUDIO_SERVICE)
        t  = text.lower()
        if any(w in t for w in ["mute","chup","silent"]):
            am.setStreamVolume(AudioManager.STREAM_MUSIC, 0, 0)
            am.setStreamVolume(AudioManager.STREAM_RING,  0, 0)
            return "🔇 Mute kar diya!"
        if any(w in t for w in ["unmute","max","full","poora"]):
            mv = am.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
            am.setStreamVolume(AudioManager.STREAM_MUSIC, mv, 0)
            return "🔊 Full volume!"
        m = re.search(r'(\d+)', t)
        if m:
            pct = min(100, max(0, int(m.group(1))))
            mv  = am.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
            am.setStreamVolume(AudioManager.STREAM_MUSIC, int(mv * pct / 100), 0)
            return f"🔊 Volume {pct}%!"
        cur = am.getStreamVolume(AudioManager.STREAM_MUSIC)
        mv  = am.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
        if any(w in t for w in ["badao","badhao","increase","tez","upar"]):
            step = max(1, mv // 10)
            am.setStreamVolume(AudioManager.STREAM_MUSIC, min(mv, cur + step), 0)
            return f"🔊 Volume badha diya!"
        if any(w in t for w in ["kam karo","decrease","halka","dheema","neeche"]):
            step = max(1, mv // 10)
            am.setStreamVolume(AudioManager.STREAM_MUSIC, max(0, cur - step), 0)
            return f"🔉 Volume kam kar diya!"
        pct = int(cur / mv * 100) if mv else 0
        return f"🔊 Volume {pct}% hai"
    except Exception as e:
        return f"❌ Volume error: {str(e)[:60]}"

# ═══════════════════════════════════════════════════════════════
# ANDROID — CALL / SMS
# ═══════════════════════════════════════════════════════════════
def is_call_request(text):
    return any(w in text.lower() for w in ["call karo","call kar","phone karo","dial karo"])

def handle_call(text):
    if platform != 'android': return "❌ Call sirf Android pe!"
    try:
        from jnius import autoclass
        from android import mActivity
        Intent = autoclass('android.content.Intent')
        Uri    = autoclass('android.net.Uri')
        m = re.search(r'(\d{10,})', text)
        if m:
            intent = Intent(Intent.ACTION_CALL)
            intent.setData(Uri.parse(f"tel:{m.group(1)}"))
        else:
            intent = Intent(Intent.ACTION_DIAL)
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        mActivity.startActivity(intent)
        return f"📞 Call kar raha hoon..."
    except Exception as e:
        return f"❌ Call error: {str(e)[:60]}"

def is_sms_request(text):
    return any(w in text.lower() for w in ["sms karo","message karo","msg bhejo","text karo"])

def handle_sms(text):
    if platform != 'android': return "❌ SMS sirf Android pe!"
    try:
        from jnius import autoclass
        from android import mActivity
        Intent = autoclass('android.content.Intent')
        Uri    = autoclass('android.net.Uri')
        m = re.search(r'(\d{10,})', text)
        number = m.group(1) if m else ""
        mm = re.search(r'(?:likho|message|msg)[:\s]+(.+)', text, re.IGNORECASE)
        intent = Intent(Intent.ACTION_VIEW)
        intent.setData(Uri.parse(f"sms:{number}"))
        if mm: intent.putExtra("sms_body", mm.group(1).strip())
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        mActivity.startActivity(intent)
        return "💬 SMS app khul gaya!"
    except Exception as e:
        return f"❌ SMS error: {str(e)[:60]}"

# ═══════════════════════════════════════════════════════════════
# ANDROID — DO NOT DISTURB
# ═══════════════════════════════════════════════════════════════
def is_dnd_request(text):
    return any(w in text.lower() for w in
               ["do not disturb","dnd","silent mode","notifications band"])

def handle_dnd(text):
    if platform != 'android': return "❌ DND sirf Android pe!"
    try:
        from jnius import autoclass
        from android import mActivity
        Context             = autoclass('android.content.Context')
        NotificationManager = autoclass('android.app.NotificationManager')
        nm = mActivity.getSystemService(Context.NOTIFICATION_SERVICE)
        if not nm.isNotificationPolicyAccessGranted():
            Intent   = autoclass('android.content.Intent')
            Settings = autoclass('android.provider.Settings')
            intent   = Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS)
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            mActivity.startActivity(intent)
            return "⚙️ Permission chahiye — Settings mein JARVIS ko allow karo!"
        t = text.lower()
        on = (any(w in t for w in ["on","chalu","lagao"]) and
              not any(w in t for w in ["off","band","hatao"]))
        nm.setInterruptionFilter(3 if on else 1)
        return "🔕 DND ON!" if on else "🔔 DND OFF!"
    except Exception as e:
        return f"❌ DND error: {str(e)[:60]}"

# ═══════════════════════════════════════════════════════════════
# MORNING BRIEFING
# ═══════════════════════════════════════════════════════════════
def is_briefing_request(text):
    return any(w in text.lower() for w in ["briefing","good morning","subah","aaj ka plan"])

def handle_morning_briefing():
    now  = datetime.now()
    name = S["username"]
    rems = [r for r in load_reminders() if not r["done"] and
            datetime.strptime(r["time"], "%Y-%m-%d %H:%M:%S").date() == now.date()]
    out  = f"🌅 Namaskar, {name}!\n📅 {now.strftime('%A, %d %B %Y')}\n🕐 {now.strftime('%I:%M %p')}\n\n"
    if rems:
        out += "⏰ Aaj ke Reminders:\n"
        for r in rems:
            t = datetime.strptime(r["time"], "%Y-%m-%d %H:%M:%S")
            out += f"  • {t.strftime('%I:%M %p')} — {r['msg']}\n"
    else:
        out += "✅ Aaj koi reminder nahi\n"
    notes_c = len(load_notes())
    if notes_c: out += f"📝 {notes_c} notes saved\n"
    out += "\nAaj kya plan hai? 💪"
    return out

# ═══════════════════════════════════════════════════════════════
# INTERNET SPEED
# ═══════════════════════════════════════════════════════════════
def is_speed_request(text):
    return any(w in text.lower() for w in ["speed","internet speed","net speed","kitni speed"])

def handle_speed():
    import urllib.request, time as _t
    try:
        url = "https://speed.cloudflare.com/__down?bytes=1000000"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7"})
        t0  = _t.time()
        with urllib.request.urlopen(req, timeout=15) as r:
            size = len(r.read())
        elapsed = _t.time() - t0
        mbps = round((size * 8) / (elapsed * 1_000_000), 2)
        return f"📶 Download: {mbps} Mbps"
    except Exception as e:
        return f"❌ Speed test fail: {str(e)[:60]}"

# ═══════════════════════════════════════════════════════════════
# WHATSAPP DRAFT
# ═══════════════════════════════════════════════════════════════
def is_whatsapp_request(text):
    return any(w in text.lower() for w in ["whatsapp","wp message","message draft","message likho"])

def handle_whatsapp_draft(text, history):
    prompt = (f"User ka WhatsApp message draft karo, unki Hinglish style mein. "
              f"Request: {text}\nSirf message text do, koi explanation nahi.")
    return call_ai(prompt, history)

# ═══════════════════════════════════════════════════════════════
# ORB WIDGET
# ═══════════════════════════════════════════════════════════════
class JarvisOrb(Widget):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.listening = False; self.pulse_anim = None
        self.bind(pos=self._draw, size=self._draw)

    def _draw(self, *_):
        self.canvas.clear()
        cx, cy = self.center_x, self.center_y
        r = min(self.width, self.height) * 0.4
        with self.canvas:
            Color(*GOLD_DIM)
            Ellipse(pos=(cx-r*1.5, cy-r*1.5), size=(r*3, r*3))
            Color(1, 0.3, 0.3, 1) if self.listening else Color(*GOLD)
            Ellipse(pos=(cx-r, cy-r), size=(r*2, r*2))
            Color(1, 1, 1, 0.25)
            Ellipse(pos=(cx-r*0.5, cy+r*0.1), size=(r*0.6, r*0.4))

    def set_listening(self, v): self.listening = v; self._draw()

    def pulse(self):
        a = (Animation(size=(dp(130), dp(130)), duration=0.4) +
             Animation(size=(dp(110), dp(110)), duration=0.4))
        a.repeat = True; a.start(self); self.pulse_anim = a

    def stop_pulse(self):
        if self.pulse_anim: self.pulse_anim.stop(self); self.pulse_anim = None

# ═══════════════════════════════════════════════════════════════
# CHAT BUBBLE
# ═══════════════════════════════════════════════════════════════
class ChatBubble(BoxLayout):
    def __init__(self, text, is_user=True, **kw):
        super().__init__(**kw)
        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.padding     = [dp(8), dp(4)]
        lbl = Label(text=text, text_size=(Window.width * 0.65, None),
                    halign='left', valign='top', color=TEXT,
                    font_size=dp(13), markup=True)
        lbl.bind(texture_size=lbl.setter('size'))
        lbl.size_hint = (None, None)
        with lbl.canvas.before:
            Color(*(U_BUB if is_user else B_BUB))
            self._r = RoundedRectangle(radius=[dp(12)])
        def _upd(inst, _):
            self._r.pos  = (inst.x - dp(8),   inst.y - dp(6))
            self._r.size = (inst.width + dp(16), inst.height + dp(12))
            self.height  = inst.height + dp(20)
        lbl.bind(pos=_upd, size=_upd)
        if is_user:
            self.add_widget(Widget())
            self.add_widget(lbl)
        else:
            self.add_widget(Label(text="🤖", font_size=dp(13),
                                  size_hint=(None,None), size=(dp(24), dp(24))))
            self.add_widget(lbl)
            self.add_widget(Widget())

# ═══════════════════════════════════════════════════════════════
# SETTINGS SCREEN
# ═══════════════════════════════════════════════════════════════
class SettingsScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self._build()

    def _build(self):
        root = FloatLayout()
        with root.canvas.before:
            Color(*BG)
            self._bg = Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=lambda *a: setattr(self._bg,'pos',root.pos),
                  size=lambda *a: setattr(self._bg,'size',root.size))

        # Header
        hdr = BoxLayout(orientation='horizontal', size_hint=(1,None),
                        height=dp(52), pos_hint={'top':1}, padding=[dp(14),dp(8)])
        with hdr.canvas.before:
            Color(*HDR)
            self._hbg = Rectangle(pos=hdr.pos, size=hdr.size)
        hdr.bind(pos=lambda *a: setattr(self._hbg,'pos',hdr.pos),
                 size=lambda *a: setattr(self._hbg,'size',hdr.size))
        back = Button(text="← Back", size_hint=(None,1), width=dp(80),
                      background_color=(0,0,0,0), color=GOLD, font_size=dp(13))
        back.bind(on_release=lambda *a: self._go_back())
        hdr.add_widget(back)
        hdr.add_widget(Label(text="⚙️  Settings", color=GOLD, font_size=dp(16), bold=True))
        hdr.add_widget(Widget(size_hint=(None,1), width=dp(80)))
        root.add_widget(hdr)

        # Scroll
        scroll = ScrollView(size_hint=(1, None), pos_hint={'top': 0.88},
                            do_scroll_x=False, bar_width=dp(4))
        def _rsz(*a): scroll.height = root.height - dp(52)
        root.bind(height=_rsz)
        Clock.schedule_once(_rsz, 0)

        content = BoxLayout(orientation='vertical', size_hint_y=None,
                            padding=[dp(14), dp(10)], spacing=dp(12))
        content.bind(minimum_height=content.setter('height'))

        def sec(txt):
            return Label(text=txt, font_size=dp(12), color=DIM,
                         size_hint_y=None, height=dp(28), halign='left',
                         text_size=(Window.width - dp(28), None))

        def inp(val="", hint="", pw=False):
            return TextInput(text=val, hint_text=hint, password=pw,
                             multiline=False, background_color=(0.10,0.10,0.22,1),
                             foreground_color=TEXT, hint_text_color=(*DIM[:3],0.5),
                             cursor_color=GOLD, font_size=dp(13),
                             size_hint_y=None, height=dp(44),
                             padding=[dp(10), dp(12)])

        # Fields
        content.add_widget(sec("👤 Aapka Naam"))
        self.fi_user = inp(S["username"])
        content.add_widget(self.fi_user)

        content.add_widget(sec("🎤 Wake Word"))
        self.fi_wake = inp(S["wake_word"])
        content.add_widget(self.fi_wake)

        content.add_widget(sec("🤖 Primary AI"))
        ai_row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        self.ai_btns = {}
        ai_list = ["claude","gemini","deepseek"]
        for n in [S.get("ai4_name","").strip().lower(), S.get("ai5_name","").strip().lower()]:
            if n and n not in ai_list: ai_list.append(n)
        for ai in ai_list:
            btn = Button(text=ai.title(), font_size=dp(11),
                         background_color=GOLD if S["primary_ai"]==ai else CARD,
                         color=(0,0,0,1) if S["primary_ai"]==ai else DIM)
            btn.bind(on_release=lambda b, a=ai: self._sel_ai(a))
            self.ai_btns[ai] = btn; ai_row.add_widget(btn)
        content.add_widget(ai_row)

        for lbl_txt, key, hint in [
            ("🔑 Claude API Key",   "claude",   "sk-ant-..."),
            ("🔑 Gemini API Key",   "gemini",   "AIza..."),
            ("🔑 DeepSeek API Key", "deepseek", "sk-..."),
        ]:
            content.add_widget(sec(lbl_txt))
            fi = inp(S.get(f"{key}_key",""), hint, pw=True)
            setattr(self, f"fi_{key}", fi)
            content.add_widget(fi)
            st = Label(text="", font_size=dp(10), size_hint_y=None,
                       height=dp(18), color=GREEN, halign='left')
            setattr(self, f"st_{key}", st)
            content.add_widget(st)
            self._upd_key(key)

        for slot in ("ai4","ai5"):
            num = slot[-1]
            content.add_widget(sec(f"🔮 AI Slot #{num} — Naam"))
            fi_n = inp(S.get(f"{slot}_name",""), f"grok, mistral, llama...")
            setattr(self, f"fi_{slot}_name", fi_n); content.add_widget(fi_n)
            content.add_widget(sec(f"🔑 AI #{num} Key"))
            fi_k = inp(S.get(f"{slot}_key",""), "API key...", pw=True)
            setattr(self, f"fi_{slot}_key", fi_k); content.add_widget(fi_k)
            content.add_widget(sec(f"🌐 AI #{num} Base URL (optional)"))
            fi_u = inp(S.get(f"{slot}_base_url",""), "https://api.example.com/v1")
            setattr(self, f"fi_{slot}_url", fi_u); content.add_widget(fi_u)
            st2 = Label(text="", font_size=dp(10), size_hint_y=None,
                        height=dp(18), color=GREEN, halign='left')
            setattr(self, f"st_{slot}", st2); content.add_widget(st2)
            self._upd_slot(slot)

        save_btn = Button(text="💾  Save Karein", font_size=dp(15),
                          size_hint_y=None, height=dp(52),
                          background_color=GOLD, color=(0,0,0,1), bold=True)
        save_btn.bind(on_release=self._save)
        content.add_widget(Widget(size_hint_y=None, height=dp(8)))
        content.add_widget(save_btn)

        del_btn = Button(text="🗑️  Saari Keys Hatao", font_size=dp(13),
                         size_hint_y=None, height=dp(44),
                         background_color=(0.4,0.1,0.1,1), color=TEXT)
        del_btn.bind(on_release=self._confirm_delete)
        content.add_widget(del_btn)
        content.add_widget(Widget(size_hint_y=None, height=dp(30)))

        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    def _upd_key(self, key):
        val = S.get(f"{key}_key", "")
        st  = getattr(self, f"st_{key}", None)
        if not st: return
        if val and len(val) > 8:
            st.text = f"✅ Set ({val[:4]}...{val[-3:]})"; st.color = GREEN
        else:
            st.text = "⚠️  Key nahi hai"; st.color = (*RED[:3], 0.8)

    def _upd_slot(self, slot):
        name = S.get(f"{slot}_name","").strip()
        key  = S.get(f"{slot}_key","").strip()
        st   = getattr(self, f"st_{slot}", None)
        if not st: return
        if name and key and len(key) > 8:
            st.text = f"✅ {name.title()} ready"; st.color = GREEN
        elif name:
            st.text = f"⚠️  '{name}' key nahi"; st.color = (*RED[:3], 0.8)
        else:
            st.text = "— Slot khali"; st.color = (*DIM[:3], 0.5)

    def _sel_ai(self, ai):
        S["primary_ai"] = ai
        for n, b in self.ai_btns.items():
            b.background_color = GOLD if n == ai else CARD
            b.color = (0,0,0,1) if n == ai else DIM

    def _save(self, *_):
        S["username"]    = self.fi_user.text.strip() or "Sir"
        S["wake_word"]   = self.fi_wake.text.strip().lower() or "jarvis"
        for key in ("claude","gemini","deepseek"):
            S[f"{key}_key"] = getattr(self, f"fi_{key}").text.strip()
        for slot in ("ai4","ai5"):
            S[f"{slot}_name"]    = getattr(self, f"fi_{slot}_name").text.strip().lower()
            S[f"{slot}_key"]     = getattr(self, f"fi_{slot}_key").text.strip()
            S[f"{slot}_base_url"]= getattr(self, f"fi_{slot}_url").text.strip()
        if save_settings(S):
            for key in ("claude","gemini","deepseek"): self._upd_key(key)
            for slot in ("ai4","ai5"):                self._upd_slot(slot)
            self._toast("✅ Saved!")
        else:
            self._toast("❌ Save nahi hua!")

    def _confirm_delete(self, *_):
        popup = Popup(title="Confirm", size_hint=(0.8,0.3),
                      background_color=(*CARD[:3],1))
        box = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(10))
        box.add_widget(Label(text="Saari keys delete karein?", color=TEXT, font_size=dp(13)))
        row = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(42))
        yes = Button(text="Haan", background_color=(*RED[:3],1), color=TEXT)
        no  = Button(text="Nahi", background_color=CARD, color=DIM)
        def _del(*_):
            for key in ("claude","gemini","deepseek","ai4","ai5"):
                full = f"{key}_key"
                S[full] = ""
                fi = getattr(self, f"fi_{key}" if key in ("claude","gemini","deepseek")
                             else f"fi_{key}_key", None)
                if fi: fi.text = ""
            save_settings(S)
            for k in ("claude","gemini","deepseek"): self._upd_key(k)
            for s in ("ai4","ai5"):                  self._upd_slot(s)
            popup.dismiss(); self._toast("🗑️ Keys hata di!")
        yes.bind(on_release=_del); no.bind(on_release=popup.dismiss)
        row.add_widget(yes); row.add_widget(no)
        box.add_widget(row); popup.content = box; popup.open()

    def _toast(self, msg):
        p = Popup(title="", size_hint=(0.75,0.12),
                  background_color=(0.1,0.1,0.2,0.95),
                  separator_height=0, title_size=0)
        p.content = Label(text=msg, color=TEXT, font_size=dp(13))
        p.open(); Clock.schedule_once(lambda _: p.dismiss(), 2)

    def _go_back(self):
        self.manager.transition = SlideTransition(direction='right')
        self.manager.current    = 'main'

    def on_enter(self):
        self.fi_user.text    = S["username"]
        self.fi_wake.text    = S["wake_word"]
        for key in ("claude","gemini","deepseek"):
            getattr(self, f"fi_{key}").text = S.get(f"{key}_key","")
        for slot in ("ai4","ai5"):
            getattr(self, f"fi_{slot}_name").text    = S.get(f"{slot}_name","")
            getattr(self, f"fi_{slot}_key").text     = S.get(f"{slot}_key","")
            getattr(self, f"fi_{slot}_url").text     = S.get(f"{slot}_base_url","")
        self._sel_ai(S["primary_ai"])
        for key in ("claude","gemini","deepseek"): self._upd_key(key)
        for slot in ("ai4","ai5"):                self._upd_slot(slot)

# ═══════════════════════════════════════════════════════════════
# MAIN CHAT SCREEN
# ═══════════════════════════════════════════════════════════════
class MainScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.history   = []
        self.reminders = load_reminders()
        self.notes     = load_notes()
        self._voice_active = False
        self._build()
        # Start voice after 2 sec (permissions settle karne do)
        Clock.schedule_once(self._request_mic_and_start, 2)
        Clock.schedule_interval(self._check_reminders, 30)

    def _build(self):
        root = FloatLayout()
        with root.canvas.before:
            Color(*BG)
            self._bg = Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=lambda *a: setattr(self._bg,'pos',root.pos),
                  size=lambda *a: setattr(self._bg,'size',root.size))

        # Header
        hdr = BoxLayout(orientation='horizontal', size_hint=(1,None),
                        height=dp(52), pos_hint={'top':1}, padding=[dp(14),dp(8)])
        with hdr.canvas.before:
            Color(*HDR)
            self._hbg = Rectangle(pos=hdr.pos, size=hdr.size)
        hdr.bind(pos=lambda *a: setattr(self._hbg,'pos',hdr.pos),
                 size=lambda *a: setattr(self._hbg,'size',hdr.size))
        hdr.add_widget(Label(text="🤖 [b]JARVIS[/b]", markup=True,
                             color=GOLD, font_size=dp(17), size_hint=(None,1), width=dp(110)))
        self.status_lbl = Label(text="Tayaar hoon...", color=DIM,
                                font_size=dp(10), halign='right')
        hdr.add_widget(self.status_lbl)
        gear = Button(text="⚙️", font_size=dp(18), size_hint=(None,1), width=dp(44),
                      background_color=(0,0,0,0), color=GOLD)
        gear.bind(on_release=self._open_settings)
        hdr.add_widget(gear)
        root.add_widget(hdr)

        # Chat scroll
        self.chat_scroll = ScrollView(size_hint=(1,None),
                                      pos_hint={'top':0.87}, do_scroll_x=False,
                                      bar_width=dp(3))
        self.chat_box = BoxLayout(orientation='vertical', size_hint_y=None,
                                  spacing=dp(4), padding=[dp(10),dp(10)])
        self.chat_box.bind(minimum_height=self.chat_box.setter('height'))
        self.chat_scroll.add_widget(self.chat_box)
        root.add_widget(self.chat_scroll)

        # Orb area
        orb_area = BoxLayout(orientation='vertical', size_hint=(1,None),
                             height=dp(150), pos_hint={'y':0.13}, spacing=dp(6))
        ow = FloatLayout(size_hint=(1,None), height=dp(115))
        self.orb = JarvisOrb(size_hint=(None,None), size=(dp(100),dp(100)))
        self.orb.pos_hint = {'center_x':0.5,'center_y':0.5}
        ow.add_widget(self.orb)
        orb_area.add_widget(ow)
        self.orb_lbl = Label(text=f"🎤 Mic dabao ya neeche likhein",
                             color=DIM, font_size=dp(10), size_hint=(1,None), height=dp(18))
        orb_area.add_widget(self.orb_lbl)
        root.add_widget(orb_area)

        # Input bar
        ibar = BoxLayout(orientation='horizontal', size_hint=(1,None),
                         height=dp(54), pos_hint={'y':0},
                         padding=[dp(8),dp(7)], spacing=dp(6))
        with ibar.canvas.before:
            Color(*HDR)
            self._ibg = Rectangle(pos=ibar.pos, size=ibar.size)
        ibar.bind(pos=lambda *a: setattr(self._ibg,'pos',ibar.pos),
                  size=lambda *a: setattr(self._ibg,'size',ibar.size))

        # Mic button
        self.mic_btn = Button(text="🎤", font_size=dp(18), size_hint=(None,1),
                              width=dp(44), background_color=CARD, color=GOLD)
        self.mic_btn.bind(on_release=self._tap_mic)
        ibar.add_widget(self.mic_btn)

        self.txt = TextInput(hint_text="Kuch poochhein...", multiline=False,
                             background_color=(0.12,0.12,0.25,1), foreground_color=TEXT,
                             hint_text_color=(*DIM[:3],0.5), cursor_color=GOLD,
                             font_size=dp(13), size_hint=(1,1),
                             on_text_validate=self._send)
        ibar.add_widget(self.txt)
        send = Button(text="➤", font_size=dp(17), size_hint=(None,1),
                      width=dp(44), background_color=GOLD, color=(0,0,0,1))
        send.bind(on_release=self._send)
        ibar.add_widget(send)
        root.add_widget(ibar)

        def _rsz(*_):
            self.chat_scroll.height = root.height * 0.74 - dp(52)
        root.bind(height=_rsz)
        Clock.schedule_once(_rsz, 0)

        self._bubble(f"Namaskar, {S['username']}! Main JARVIS hoon 🤖\n"
                     f"🎤 Mic button dabao ya neeche likhein.\n"
                     f"API key set nahi? ⚙️ dabao!", is_user=False)
        self.add_widget(root)

    # ── VOICE ──────────────────────────────────────────────────
    def _request_mic_and_start(self, *_):
        if platform == 'android':
            try:
                from android.permissions import request_permissions, Permission
                request_permissions([Permission.RECORD_AUDIO])
            except Exception as e:
                print(f"[JARVIS] Permission request error: {e}")
        self.status_lbl.text = f"'{S['wake_word']}' bolein ya likhein"
        self.orb_lbl.text    = f"🎤 Mic dabao bolne ke liye"

    def _tap_mic(self, *_):
        """Mic button tap — ek baar listen karo."""
        if self._voice_active:
            return
        self._start_listen()

    def _start_listen(self):
        self._voice_active = True
        self.orb.set_listening(True)
        self.orb.pulse()
        self.orb_lbl.text    = "🔴 Bol dijiye..."
        self.status_lbl.text = "Sun raha hoon... 🔴"
        self.mic_btn.background_color = (*RED[:3], 1)

        if platform == 'android':
            _android_voice_listen(
                on_result=self._on_voice_result,
                on_error=self._on_voice_error
            )
        else:
            # Desktop fallback — type karo
            self._on_voice_error("Desktop pe sirf text input use karein")

    def _on_voice_result(self, text):
        self._voice_active = False
        self.orb.set_listening(False)
        self.orb.stop_pulse()
        self.mic_btn.background_color = CARD
        self.orb_lbl.text    = "🎤 Mic dabao bolne ke liye"
        self.status_lbl.text = "Processing..."
        # Wake word check
        ww = S["wake_word"].lower()
        tl = text.lower()
        if ww in tl:
            cmd = tl.replace(ww, "").strip()
            if not cmd:
                # Sirf wake word tha — dobara suno
                Clock.schedule_once(lambda _: self._start_listen(), 0.3)
                return
        else:
            cmd = text  # wake word nahi tha, poori baat command hai
        self._process(cmd)

    def _on_voice_error(self, msg):
        self._voice_active = False
        self.orb.set_listening(False)
        self.orb.stop_pulse()
        self.mic_btn.background_color = CARD
        self.orb_lbl.text    = "🎤 Mic dabao bolne ke liye"
        self.status_lbl.text = f"Voice error: {msg}"

    # ── TEXT SEND ──────────────────────────────────────────────
    def _send(self, *_):
        t = self.txt.text.strip()
        if not t: return
        self.txt.text = ""
        self._process(t)

    # ── PROCESS COMMAND ────────────────────────────────────────
    def _process(self, cmd):
        self._bubble(cmd, is_user=True)
        self.status_lbl.text = "Soch raha hoon... 🧠"

        # Route
        if is_whatsapp_request(cmd):
            def _wa():
                r = handle_whatsapp_draft(cmd, self.history)
                Clock.schedule_once(lambda _: self._reply(r), 0)
            threading.Thread(target=_wa, daemon=True).start(); return

        if is_briefing_request(cmd):
            self._reply(handle_morning_briefing()); return
        if is_flash_request(cmd):
            self._reply(handle_flashlight(cmd)); return
        if is_volume_request(cmd):
            self._reply(handle_volume(cmd)); return
        if is_dnd_request(cmd):
            self._reply(handle_dnd(cmd)); return
        if is_call_request(cmd):
            self._reply(handle_call(cmd)); return
        if is_sms_request(cmd):
            self._reply(handle_sms(cmd)); return

        if is_reminder_request(cmd):
            rem = parse_reminder(cmd)
            if rem:
                self.reminders.append(rem); save_reminders(self.reminders)
                t = datetime.strptime(rem["time"], "%Y-%m-%d %H:%M:%S")
                self._reply(f"✅ Reminder: {t.strftime('%d %b, %I:%M %p')} — '{rem['msg']}'")
            else:
                self._reply("⏰ Time samajh nahi aaya. Jaise: '30 minute mein chai'")
            return

        if is_show_notes(cmd):
            self._reply(show_notes(self.notes)); return
        if is_note_request(cmd):
            self._reply(handle_note(cmd, self.notes)); return
        if is_calc_request(cmd):
            self._reply(handle_calc(cmd)); return

        if is_speed_request(cmd):
            def _sp():
                r = handle_speed()
                Clock.schedule_once(lambda _: self._reply(r), 0)
            threading.Thread(target=_sp, daemon=True).start(); return

        if is_weather_request(cmd):
            def _wt():
                r = handle_weather(cmd)
                Clock.schedule_once(lambda _: self._reply(r), 0)
            threading.Thread(target=_wt, daemon=True).start(); return

        # Offline check → AI
        mood = detect_mood(cmd)
        def _work():
            r = offline_response(cmd) or call_ai(cmd, self.history, mood)
            if mood != "neutral" and not offline_response(cmd):
                r = mood_prefix(mood) + r
            learn_from_conversation(cmd, r)
            self.history.append({"role":"user","content":cmd})
            self.history.append({"role":"assistant","content":r})
            if len(self.history) > 20:
                self.history = self.history[-20:]
            Clock.schedule_once(lambda _: self._reply(r), 0)
        threading.Thread(target=_work, daemon=True).start()

    def _reply(self, r):
        self._bubble(r, is_user=False)
        self.status_lbl.text = f"'{S['wake_word']}' bolein ya likhein"
        self.orb.set_listening(False)
        self.orb.stop_pulse()
        threading.Thread(target=speak, args=(r,), daemon=True).start()

    def _bubble(self, text, is_user=True):
        self.chat_box.add_widget(ChatBubble(text=text, is_user=is_user))
        Clock.schedule_once(lambda _: setattr(self.chat_scroll,'scroll_y',0), 0.1)

    def _check_reminders(self, _):
        now, changed = datetime.now(), False
        for rem in self.reminders:
            if rem["done"]: continue
            if now >= datetime.strptime(rem["time"], "%Y-%m-%d %H:%M:%S"):
                rem["done"] = True; changed = True
                Clock.schedule_once(lambda _, m=rem["msg"]: self._show_reminder(m), 0)
        if changed: save_reminders(self.reminders)

    def _show_reminder(self, msg):
        popup = Popup(title="⏰ Reminder!", size_hint=(0.88,0.35),
                      background_color=(*HDR[:3],1))
        box = BoxLayout(orientation='vertical', padding=dp(16), spacing=dp(12))
        box.add_widget(Label(text=f"🔔 {msg}", color=GOLD, font_size=dp(15),
                             halign='center', text_size=(Window.width*0.75, None)))
        ok = Button(text="Theek hai!", size_hint_y=None, height=dp(44),
                    background_color=GOLD, color=(0,0,0,1))
        ok.bind(on_release=popup.dismiss)
        box.add_widget(ok); popup.content = box; popup.open()
        self._bubble(f"⏰ Reminder: {msg}", is_user=False)

    def _open_settings(self, *_):
        self.manager.transition = SlideTransition(direction='left')
        self.manager.current    = 'settings'

    def on_enter(self):
        self.orb_lbl.text    = "🎤 Mic dabao bolne ke liye"
        self.status_lbl.text = f"'{S['wake_word']}' bolein ya likhein"

# ═══════════════════════════════════════════════════════════════
# BACKGROUND SERVICE NOTIFICATION
# ═══════════════════════════════════════════════════════════════
def _show_foreground_notification():
    if platform != 'android': return
    try:
        from jnius import autoclass
        from android import mActivity
        NotificationManager = autoclass('android.app.NotificationManager')
        NotificationChannel = autoclass('android.app.NotificationChannel')
        NotificationCompat  = autoclass('androidx.core.app.NotificationCompat')
        PendingIntent       = autoclass('android.app.PendingIntent')
        context = mActivity.getApplicationContext()
        CHANNEL_ID = "jarvis_bg"
        nm = mActivity.getSystemService(context.NOTIFICATION_SERVICE)
        ch = NotificationChannel(CHANNEL_ID, "JARVIS", NotificationManager.IMPORTANCE_LOW)
        ch.setDescription("JARVIS chal raha hai")
        nm.createNotificationChannel(ch)
        pi = PendingIntent.getActivity(
            context, 0,
            context.getPackageManager().getLaunchIntentForPackage(context.getPackageName()),
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        )
        b = NotificationCompat.Builder(context, CHANNEL_ID)
        b.setSmallIcon(autoclass('android.R$drawable').ic_dialog_info)
        b.setContentTitle("JARVIS Active")
        b.setContentText(f"'{S['wake_word']}' bolke activate karein")
        b.setPriority(NotificationCompat.PRIORITY_LOW)
        b.setOngoing(True)
        b.setContentIntent(pi)
        nm.notify(1001, b.build())
    except Exception as e:
        print(f"[JARVIS] Notification error: {e}")

def _cancel_notification():
    if platform != 'android': return
    try:
        from android import mActivity
        from jnius import autoclass
        ctx = mActivity.getApplicationContext()
        nm  = mActivity.getSystemService(ctx.NOTIFICATION_SERVICE)
        nm.cancel(1001)
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════
# APP
# ═══════════════════════════════════════════════════════════════
class JarvisApp(App):
    def build(self):
        Window.clearcolor = BG
        self.title = "JARVIS"
        sm = ScreenManager()
        sm.add_widget(MainScreen(name='main'))
        sm.add_widget(SettingsScreen(name='settings'))
        return sm

    def on_start(self):
        # TTS init karo background mein
        threading.Thread(target=_init_tts, daemon=True).start()
        # Persistent notification
        Clock.schedule_once(lambda _: _show_foreground_notification(), 3)

    def on_pause(self):  return True  # Android service alive rakhega
    def on_resume(self): pass
    def on_stop(self):   _cancel_notification()

if __name__ == "__main__":
    JarvisApp().run()
