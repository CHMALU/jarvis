#!/usr/bin/env python3
import subprocess
import time
import threading
import sys
import os

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 44100
BLOCK_SIZE = 512
CLAP_MIN_GAP = 0.3
CLAP_MAX_GAP = 1.2
COOLDOWN = 3.0
AMBIENT_CALIBRATION_SECS = 2
AMBIENT_MULTIPLIER = 8

SPOTIFY_URI = "spotify:track:39shmbIHICJ2Wxnk1fPSdz"

last_clap_time = None
last_trigger_time = 0
threshold = 0.15
lock = threading.Lock()


def log(msg):
    print(msg, flush=True)


def trigger_ironman():
    log(">>> IRONMAN SEQUENCE INITIATED <<<")

    subprocess.run(["xset", "dpms", "force", "on"], check=False)
    time.sleep(0.8)

    env = os.environ.copy()
    env.setdefault("DISPLAY", ":0")
    env.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{os.getuid()}/bus")

    subprocess.Popen(["xdg-open", SPOTIFY_URI], env=env)
    time.sleep(0.5)

    subprocess.Popen(
        ["gnome-terminal", "--", "bash", "-c", "claude; exec bash"],
        env=env,
    )
    time.sleep(0.5)

    subprocess.Popen(["code"], env=env)

    log("Sequence done.")


def audio_callback(indata, frames, time_info, status):
    global last_clap_time, last_trigger_time

    rms = float(np.sqrt(np.mean(indata ** 2)))

    if rms < threshold:
        return

    now = time.monotonic()

    with lock:
        if now - last_trigger_time < COOLDOWN:
            return

        if last_clap_time is None:
            last_clap_time = now
            log(f"Clap 1 detected (rms={rms:.4f})")
            return

        gap = now - last_clap_time
        last_clap_time = None

        if CLAP_MIN_GAP <= gap <= CLAP_MAX_GAP:
            log(f"Clap 2 detected (gap={gap:.2f}s) — TRIGGERING")
            last_trigger_time = now
            threading.Thread(target=trigger_ironman, daemon=True).start()
        elif gap < CLAP_MIN_GAP:
            log(f"Too fast ({gap:.2f}s), resetting")
        else:
            log(f"Too slow ({gap:.2f}s), treating as new first clap")
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
        while True:
            time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Jarvis stopped.")
        sys.exit(0)
