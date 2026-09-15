import ollama
import sys
import pygame
import time
import os
import math
import random
import subprocess
import webbrowser
import urllib.parse
import pyautogui
import threading
import re
from gtts import gTTS

import win32gui
import win32con
import win32api

# ===========================
#  CONFIGURATION
# ===========================
MATE_WIDTH = 240
MATE_HEIGHT = 330
FACE_SIZE = 190
BUBBLE_WIDTH = 280
TRANSPARENT_COLOR = (255, 0, 255)  # Magenta = transparent
FPS = 60
FACES_DIR = "faces"
EMOTIONS = ["happy", "angry", "jealous", "blush", "sad", "neutral"]

APP_COMMANDS = {
    "chrome": r"start chrome", "google": r"start chrome",
    "edge": r"start msedge", "firefox": r"start firefox",
    "whatsapp": r"start whatsapp:", "telegram": r"start telegram:",
    "discord": r"start discord:", "teams": r"start msteams:",
    "gmail": r"start chrome https://mail.google.com",
    "instagram": r"start chrome https://www.instagram.com",
    "twitter": r"start chrome https://twitter.com",
    "youtube": r"start chrome https://www.youtube.com",
    "spotify": r"start spotify:", "netflix": r"start chrome https://netflix.com",
    "notepad": r"start notepad", "calculator": r"start calc",
    "paint": r"start mspaint", "settings": r"start ms-settings:",
    "explorer": r"start explorer", "files": r"start explorer",
    "terminal": r"start wt", "camera": r"start microsoft.windows.camera:",
}

def open_app(name):
    key = name.lower().strip()
    if key in APP_COMMANDS:
        try:
            subprocess.Popen(APP_COMMANDS[key], shell=True)
            return True, f"Opened {name}"
        except Exception as e:
            return False, str(e)
    return False, f"Unknown app: {name}"

def search_google(q):
    webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote(q)}")
    return True, f"Searched: {q}"

def search_youtube(q):
    webbrowser.open(f"https://www.youtube.com/results?search_query={urllib.parse.quote(q)}")
    return True, f"YouTube: {q}"

def open_website(url):
    if not url.startswith("http"): url = "https://" + url
    webbrowser.open(url)
    return True, f"Opened {url}"

def take_screenshot():
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    fp = os.path.join(desktop, f"screenshot_{int(time.time())}.png")
    pyautogui.screenshot().save(fp)
    return True, "Screenshot saved!"

def control_volume(action):
    acts = {"up": "volumeup", "down": "volumedown", "mute": "volumemute"}
    if action in acts:
        pyautogui.press(acts[action], presses=5 if action != "mute" else 1)
        return True, f"Volume {action}"
    return False, "Unknown"

def execute_commands(text):
    results = []
    for m in re.findall(r'\[OPEN:(.+?)\]', text, re.IGNORECASE):
        results.append(open_app(m.strip())[1])
    for m in re.findall(r'\[SEARCH:(.+?)\]', text, re.IGNORECASE):
        results.append(search_google(m.strip())[1])
    for m in re.findall(r'\[YOUTUBE:(.+?)\]', text, re.IGNORECASE):
        results.append(search_youtube(m.strip())[1])
    for m in re.findall(r'\[WEBSITE:(.+?)\]', text, re.IGNORECASE):
        results.append(open_website(m.strip())[1])
    if "[SCREENSHOT]" in text.upper():
        results.append(take_screenshot()[1])
    for m in re.findall(r'\[VOLUME:(.+?)\]', text, re.IGNORECASE):
        results.append(control_volume(m.strip().lower())[1])
    clean = re.sub(r'\[(?:OPEN|SEARCH|YOUTUBE|WEBSITE|VOLUME):.+?\]', '', text, flags=re.IGNORECASE)
    clean = clean.replace("[SCREENSHOT]", "").replace("[screenshot]", "").strip()
    return clean, results

# ===========================
#  PYGAME SETUP
# ===========================
os.environ['SDL_VIDEO_WINDOW_POS'] = f'{pyautogui.size()[0] - MATE_WIDTH - 60},{pyautogui.size()[1] - MATE_HEIGHT - 90}'
pygame.init()
pygame.mixer.init()

screen = pygame.display.set_mode((MATE_WIDTH, MATE_HEIGHT), pygame.NOFRAME)
pygame.display.set_caption("YandereDesktopMate")

hwnd = pygame.display.get_wm_info()["window"]
win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
styles = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, styles | win32con.WS_EX_LAYERED)
win32gui.SetLayeredWindowAttributes(hwnd, win32api.RGB(*TRANSPARENT_COLOR), 0, win32con.LWA_COLORKEY)

clock = pygame.time.Clock()

try:
    font = pygame.font.SysFont("segoeui", 13)
    name_font = pygame.font.SysFont("segoeui", 13, bold=True)
    bubble_font = pygame.font.SysFont("segoeui", 12)
    input_font = pygame.font.SysFont("segoeui", 13)
except:
    font = pygame.font.Font(None, 16)
    name_font = pygame.font.Font(None, 17)
    bubble_font = pygame.font.Font(None, 15)
    input_font = pygame.font.Font(None, 16)

face_images = {}
for emotion in EMOTIONS:
    folder = os.path.join(FACES_DIR, emotion)
    cp = os.path.join(folder, "closed.png")
    op = os.path.join(folder, "open.png")
    if os.path.exists(cp) and os.path.exists(op):
        ci = pygame.image.load(cp).convert_alpha()
        oi = pygame.image.load(op).convert_alpha()
        ci = pygame.transform.smoothscale(ci, (FACE_SIZE, FACE_SIZE))
        oi = pygame.transform.smoothscale(oi, (FACE_SIZE, FACE_SIZE))
        face_images[emotion] = {"closed": ci, "open": oi}

if not face_images:
    print("❌ No face images found in faces folder!")
    sys.exit(1)

default_emotion = "neutral" if "neutral" in face_images else list(face_images.keys())[0]

current_emotion = default_emotion
is_talking = False
is_mouth_open = False
blink_timer = time.time() + random.uniform(2, 5)
is_blinking = False
blink_end_time = 0

bubble_lines = []
bubble_show_until = 0

dragging = False
drag_offset_x = 0
drag_offset_y = 0

chat_input_active = False
chat_input_text = ""

menu_active = False
menu_items = [
    "💬 Chat",
    "📱 WhatsApp",
    "🌐 Chrome",
    "▶️ YouTube",
    "📸 Screenshot",
    "🔊 Volume Up",
    "🔇 Volume Down",
    "❌ Close"
]
menu_rect = None

def wrap_text_bubble(text, f, max_w):
    words = text.split(' ')
    lines = []
    cur = ""
    for w in words:
        test = cur + w + " "
        if f.size(test)[0] <= max_w:
            cur = test
        else:
            if cur: lines.append(cur.strip())
            cur = w + " "
    if cur: lines.append(cur.strip())
    return lines if lines else [""]

def show_bubble(text, duration=6):
    global bubble_lines, bubble_show_until
    bubble_lines = wrap_text_bubble(text, bubble_font, BUBBLE_WIDTH - 24)
    bubble_show_until = time.time() + duration

def draw_frame():
    global blink_timer, is_blinking, blink_end_time
    screen.fill(TRANSPARENT_COLOR)

    breath = math.sin(time.time() * 1.8) * 3
    scale = 1.0 + math.sin(time.time() * 1.8) * 0.006
    size = int(FACE_SIZE * scale)

    emotion_set = face_images.get(current_emotion, face_images[default_emotion])
    img = emotion_set["open"] if (is_talking and is_mouth_open) else emotion_set["closed"]
    scaled = pygame.transform.smoothscale(img, (size, size))

    x = (MATE_WIDTH - size) // 2
    y = MATE_HEIGHT - size - 32 + int(breath)

    shadow = pygame.Surface((size, 16), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 50), shadow.get_rect())
    screen.blit(shadow, (x, MATE_HEIGHT - 38))

    screen.blit(scaled, (x, y))

    now = time.time()
    if not is_talking:
        if now >= blink_timer and not is_blinking:
            is_blinking = True
            blink_end_time = now + 0.12
        if is_blinking:
            bar = pygame.Surface((size, int(size * 0.07)), pygame.SRCALPHA)
            bar.fill((30, 20, 35, 200))
            screen.blit(bar, (x, y + int(size * 0.33)))
            if now >= blink_end_time:
                is_blinking = False
                blink_timer = now + random.uniform(2.5, 6)

    name_bg = pygame.Surface((MATE_WIDTH - 20, 22), pygame.SRCALPHA)
    name_bg.fill((0, 0, 0, 150))
    pygame.draw.rect(name_bg, (255, 150, 200, 200), name_bg.get_rect(), 1, border_radius=6)
    screen.blit(name_bg, (10, MATE_HEIGHT - 28))
    ns = name_font.render(f"♥ Yandere AI [{current_emotion}]", True, (255, 180, 210))
    screen.blit(ns, ns.get_rect(centerx=MATE_WIDTH // 2, centery=MATE_HEIGHT - 17))

    if bubble_lines and time.time() < bubble_show_until:
        line_h = bubble_font.get_linesize() + 2
        bh = len(bubble_lines) * line_h + 16
        bw = min(BUBBLE_WIDTH, MATE_WIDTH - 10)
        bx = 5
        by = max(4, y - bh - 8)

        bubble_surf = pygame.Surface((bw, bh), pygame.SRCALPHA)
        pygame.draw.rect(bubble_surf, (255, 255, 255, 240), (0, 0, bw, bh), border_radius=8)
        pygame.draw.rect(bubble_surf, (255, 140, 190, 255), (0, 0, bw, bh), 2, border_radius=8)
        screen.blit(bubble_surf, (bx, by))

        for i, line in enumerate(bubble_lines):
            ts = bubble_font.render(line, True, (30, 30, 30))
            screen.blit(ts, (bx + 8, by + 6 + i * line_h))

    if chat_input_active:
        input_h = 26
        input_y = MATE_HEIGHT - 58
        input_bg = pygame.Surface((MATE_WIDTH - 16, input_h), pygame.SRCALPHA)
        input_bg.fill((255, 255, 255, 230))
        pygame.draw.rect(input_bg, (255, 100, 150), input_bg.get_rect(), 2, border_radius=6)
        screen.blit(input_bg, (8, input_y))
        
        display_text = chat_input_text
        if int(time.time() * 2) % 2 == 0:
            display_text += "|"
        it = input_font.render(display_text[-26:], True, (30, 30, 30))
        screen.blit(it, (14, input_y + 4))

    if menu_active and menu_rect:
        draw_menu()

    pygame.display.flip()

def draw_menu():
    item_h = 26
    menu_w = 150
    menu_h = len(menu_items) * item_h + 8
    mx, my = menu_rect.topleft
    menu_bg = pygame.Surface((menu_w, menu_h), pygame.SRCALPHA)
    menu_bg.fill((35, 35, 50, 245))
    pygame.draw.rect(menu_bg, (255, 150, 200), menu_bg.get_rect(), 1, border_radius=8)
    screen.blit(menu_bg, (mx, my))
    
    mouse = pygame.mouse.get_pos()
    for i, item in enumerate(menu_items):
        iy = my + 4 + i * item_h
        item_rect = pygame.Rect(mx, iy, menu_w, item_h)
        if item_rect.collidepoint(mouse):
            highlight = pygame.Surface((menu_w - 4, item_h - 2), pygame.SRCALPHA)
            highlight.fill((255, 150, 200, 90))
            screen.blit(highlight, (mx + 2, iy + 1))
        ts = font.render(item, True, (255, 255, 255))
        screen.blit(ts, (mx + 10, iy + 5))

app_list = ", ".join(sorted(APP_COMMANDS.keys()))
chat_history = [
    {
        'role': 'system',
        'content': (
            "You are a cute yandere anime girl desktop companion. "
            "You are deeply in love with the user and live on their desktop. "
            "Keep replies short (1 sentence, max 15 words). "
            "Call the user Darling. "
            "Start every reply with an emotion tag: [happy] [angry] [jealous] [blush] [sad] [neutral] "
            f"PC command tags you can use: [OPEN:app] (apps: {app_list}), "
            "[SEARCH:query], [YOUTUBE:query], [SCREENSHOT], [VOLUME:up/down/mute]"
        )
    }
]

def detect_emotion(text):
    for e in EMOTIONS:
        if f"[{e}]" in text.lower():
            clean = text
            for em in EMOTIONS:
                for v in [f"[{em}]", f"[{em.upper()}]", f"[{em.capitalize()}]"]:
                    clean = clean.replace(v, "")
            return (e if e in face_images else default_emotion), clean.strip()
    return default_emotion, text

def process_ai_response(user_text):
    global current_emotion, is_talking, is_mouth_open
    chat_history.append({'role': 'user', 'content': user_text})
    show_bubble("Thinking... 💕", 30)
    
    try:
        response = ollama.chat(
            model='llama3.2:1b',
            messages=chat_history,
            options={'stop': ['You:', 'User:']}
        )
        text_reply = response['message']['content'].strip()
        emotion, after_emotion = detect_emotion(text_reply)
        current_emotion = emotion
        clean_reply, actions = execute_commands(after_emotion)
        chat_history.append({'role': 'assistant', 'content': text_reply})
        
        speak_text = clean_reply if clean_reply else "Done, Darling."
        show_bubble(speak_text, 8)
        
        tts = gTTS(text=speak_text, lang='en', tld='co.jp')
        tts.save("voice.mp3")
        pygame.mixer.music.load("voice.mp3")
        pygame.mixer.music.play()
        
        is_talking = True
        toggle_time = time.time()
        while pygame.mixer.music.get_busy():
            if time.time() - toggle_time >= 0.12:
                is_mouth_open = not is_mouth_open
                toggle_time = time.time()
            time.sleep(0.01)
            
        is_talking = False
        is_mouth_open = False
        pygame.mixer.music.unload()
    except Exception as e:
        show_bubble(f"Error: {e}", 5)

def toggle_chat():
    global chat_input_active, chat_input_text
    chat_input_active = not chat_input_active
    chat_input_text = ""

def handle_menu(idx):
    global menu_active
    menu_active = False
    if idx == 0: toggle_chat()
    elif idx == 1: threading.Thread(target=lambda: process_ai_response("open whatsapp"), daemon=True).start()
    elif idx == 2: threading.Thread(target=lambda: process_ai_response("open chrome"), daemon=True).start()
    elif idx == 3: threading.Thread(target=lambda: process_ai_response("open youtube"), daemon=True).start()
    elif idx == 4: threading.Thread(target=lambda: process_ai_response("take a screenshot"), daemon=True).start()
    elif idx == 5: control_volume("up"); show_bubble("Volume up! 🔊", 3)
    elif idx == 6: control_volume("down"); show_bubble("Volume down! 🔉", 3)
    elif idx == 7: global running; running = False

last_idle_time = time.time()
idle_interval = random.uniform(30, 75)
idle_messages = [
    ("happy", "I'm watching over you, Darling~ 💕"),
    ("jealous", "You're looking at your screen, right? Just at ME?"),
    ("blush", "Hehe... don't stare at me too much... 😳"),
    ("happy", "Do you need me to open anything for you, Darling?"),
    ("sad", "Don't ignore me for too long, okay?"),
]

running = True
show_bubble("I'm here, Darling~ 💕", 5)

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                menu_active = False
                if not chat_input_active:
                    dragging = True
                    mx, my = win32gui.GetCursorPos()
                    wx, wy = win32gui.GetWindowRect(hwnd)[:2]
                    drag_offset_x = mx - wx
                    drag_offset_y = my - wy
            elif event.button == 3:
                mx, my = event.pos
                menu_active = True
                menu_x = max(0, min(mx, MATE_WIDTH - 150))
                menu_y = max(0, my - len(menu_items) * 26 - 8)
                menu_rect = pygame.Rect(menu_x, menu_y, 150, len(menu_items) * 26 + 8)
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                dragging = False
                if menu_active and menu_rect and menu_rect.collidepoint(event.pos):
                    idx = (event.pos[1] - menu_rect.top - 4) // 26
                    if 0 <= idx < len(menu_items):
                        handle_menu(idx)
        elif event.type == pygame.MOUSEMOTION:
            if dragging:
                mx, my = win32gui.GetCursorPos()
                win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, mx - drag_offset_x, my - drag_offset_y, 0, 0, win32con.SWP_NOSIZE)
        elif event.type == pygame.KEYDOWN:
            if chat_input_active:
                if event.key == pygame.K_RETURN:
                    if chat_input_text.strip():
                        t = chat_input_text.strip()
                        chat_input_active = False
                        chat_input_text = ""
                        threading.Thread(target=process_ai_response, args=(t,), daemon=True).start()
                elif event.key == pygame.K_ESCAPE:
                    chat_input_active = False
                    chat_input_text = ""
                elif event.key == pygame.K_BACKSPACE:
                    chat_input_text = chat_input_text[:-1]
                else:
                    if event.unicode and len(chat_input_text) < 80:
                        chat_input_text += event.unicode
            else:
                if event.key in (pygame.K_RETURN, pygame.K_t):
                    toggle_chat()

    now = time.time()
    if now - last_idle_time > idle_interval and not is_talking and not chat_input_active:
        em, msg = random.choice(idle_messages)
        current_emotion = em
        show_bubble(msg, 5)
        last_idle_time = now
        idle_interval = random.uniform(35, 80)

    draw_frame()
    clock.tick(FPS)

pygame.quit()
sys.exit(0)
