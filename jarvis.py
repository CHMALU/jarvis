#!/usr/bin/env python3
import asyncio
import datetime
import os
import subprocess
import sys
import tempfile
import threading
import time

import edge_tts
import feedparser
import numpy as np
import pygame
import sounddevice as sd

SAMPLE_RATE = 44100
BLOCK_SIZE = 512
CLAP_DEBOUNCE = 0.15   # ignoruj kolejne spiki przez 150ms po klaśnięciu
CLAP_MIN_GAP = 0.2
CLAP_MAX_GAP = 1.5
AMBIENT_CALIBRATION_SECS = 2
AMBIENT_MULTIPLIER = 8

SPOTIFY_URI = "spotify:track:39shmbIHICJ2Wxnk1fPSdz"
VOICE = "en-GB-RyanNeural"
NEWS_RSS = "http://feeds.bbci.co.uk/news/rss.xml"
NEWS_COUNT = 3

last_clap_time = None
last_spike_time = 0.0   # czas ostatniego spike'a (debounce)
threshold = 0.15
lock = threading.Lock()
triggered = False


def log(msg):
    print(msg, flush=True)


def get_greeting():
    hour = datetime.datetime.now().hour
    if hour < 12:
        return "Good morning, sir."
    elif hour < 18:
        return "Good afternoon, sir."
    return "Good evening, sir."


def get_news():
    try:
        feed = feedparser.parse(NEWS_RSS)
        headlines = [e.title for e in feed.entries[:NEWS_COUNT]]
        if not headlines:
            return ""
        return "Today's headlines: " + ". ".join(headlines) + "."
    except Exception:
        return ""


def speak(text):
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        path = f.name
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(edge_tts.Communicate(text, VOICE).save(path))
        loop.close()
        pygame.mixer.init()
        pygame.mixer.music.load(path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        pygame.mixer.quit()
    except Exception as e:
        log(f"TTS error: {e}")
    finally:
        os.unlink(path)


def trigger_ironman():
    log(">>> IRONMAN SEQUENCE INITIATED <<<")

    subprocess.run(["xset", "dpms", "force", "on"], check=False)
    time.sleep(0.5)

    env = os.environ.copy()
    env.setdefault("DISPLAY", ":0")
    env.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{os.getuid()}/bus")

    greeting = get_greeting()
    news = get_news()
    speech = f"{greeting} {news}" if news else greeting
    log(f"Speaking: {speech}")
    speak(speech)

    subprocess.Popen(["xdg-open", SPOTIFY_URI], env=env)
    time.sleep(0.5)

    subprocess.Popen(
        ["gnome-terminal", "--", "bash", "-c", "claude; exec bash"],
        env=env,
    )
    time.sleep(0.5)

    subprocess.Popen(["code"], env=env)

    log("Sequence done. Shutting down.")
    os._exit(0)


def audio_callback(indata, frames, time_info, status):
    global last_clap_time, last_spike_time, triggered

    if triggered:
        return

    rms = float(np.sqrt(np.mean(indata ** 2)))
    if rms < threshold:
        return

    now = time.monotonic()

    with lock:
        if triggered:
            return

        # debounce: ignoruj spiki które są echem poprzedniego klaśnięcia
        if now - last_spike_time < CLAP_DEBOUNCE:
            return
        last_spike_time = now

        if last_clap_time is None:
            last_clap_time = now
            log(f"Clap 1 (rms={rms:.4f})")
            return

        gap = now - last_clap_time
        last_clap_time = None

        if CLAP_MIN_GAP <= gap <= CLAP_MAX_GAP:
            log(f"Clap 2 (gap={gap:.2f}s) — TRIGGERING")
            triggered = True
            threading.Thread(target=trigger_ironman, daemon=False).start()
        else:
            log(f"Gap {gap:.2f}s — nowe pierwsze klaśnięcie")
            last_clap_time = now


def calibrate():
    global threshold
    log(f"Calibrating ambient noise for {AMBIENT_CALIBRATION_SECS}s...")
    samples = []

    def collect(indata, frames, time_info, status):
        samples.append(float(np.sqrt(np.mean(indata ** 2))))

    with sd.InputStream(samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE,
                        channels=1, dtype="float32", callback=collect):
        time.sleep(AMBIENT_CALIBRATION_SECS)

    ambient = float(np.mean(samples)) if samples else 0.01
    threshold = max(ambient * AMBIENT_MULTIPLIER, 0.05)
    log(f"Ambient RMS: {ambient:.5f} → threshold set to {threshold:.5f}")


def main():
    calibrate()
    log("Jarvis listening... clap twice to activate.")

    with sd.InputStream(samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE,
                        channels=1, dtype="float32", callback=audio_callback):
        while not triggered:
            time.sleep(0.5)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Jarvis stopped.")
        sys.exit(0)
