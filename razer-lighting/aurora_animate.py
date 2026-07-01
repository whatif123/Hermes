#!/usr/bin/env python3
"""
Aurora Animated Lighting — Razer OpenRazer Animation Engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Läuft als Loop und setzt jede LED einzeln per advanced-Matrix.
Unterstützt Wellen, Farbverläufe, Pulsieren — auch auf der Maus.

Nutzung:
  python3 aurora_animate.py                    # Aurora-Welle (Standard)
  python3 aurora_animate.py aurora_wave        # explizit
  python3 aurora_animate.py color_wave         # andere Animation
  python3 aurora_animate.py --list             # Animationen auflisten
  python3 aurora_animate.py --fps 30           # FPS anpassen
"""

import json
import sys
import time
from pathlib import Path


# ── Farben ────────────────────────────────────────────────────────────────────

class Color:
    """RGB-Farbe mit Interpolation."""

    def __init__(self, r, g, b):
        self.rgb = (r, g, b)

    @staticmethod
    def lerp(c1, c2, t):
        """Linear interpolieren zwischen zwei Farben (t=0..1)."""
        t = max(0.0, min(1.0, t))
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        return (r, g, b)

    @staticmethod
    def gradient(stops, position):
        """
        Farbverlauf über mehrere Stops.
        stops = [(position, (r,g,b)), ...]  mit position 0.0–1.0
        """
        if not stops:
            return (0, 0, 0)
        if position <= stops[0][0]:
            return stops[0][1]
        if position >= stops[-1][0]:
            return stops[-1][1]

        for i in range(len(stops) - 1):
            p1, c1 = stops[i]
            p2, c2 = stops[i + 1]
            if p1 <= position <= p2:
                t = (position - p1) / (p2 - p1)
                return Color.lerp(c1, c2, t)

        return stops[-1][1]


# ── Profile ───────────────────────────────────────────────────────────────────

AURORA_COLORS = [
    (0.00, (1, 1, 20)),       # dunkelstes Blau
    (0.25, (18, 2, 31)),      # dunkles Violett
    (0.50, (103, 11, 181)),   # Lila
    (0.70, (150, 255, 108)),  # Aurora-Grün
    (0.90, (240, 12, 255)),   # Magenta
    (1.00, (1, 1, 20)),       # zurück zu dunkel
]

FIRE_COLORS = [
    (0.00, (80, 0, 0)),
    (0.30, (255, 20, 0)),
    (0.60, (255, 120, 0)),
    (0.85, (255, 200, 50)),
    (1.00, (255, 255, 100)),
]

OCEAN_COLORS = [
    (0.00, (0, 0, 50)),
    (0.30, (0, 50, 150)),
    (0.60, (0, 150, 200)),
    (0.85, (50, 200, 255)),
    (1.00, (0, 50, 100)),
]

ANIMATIONS = {
    "aurora_wave": {
        "name": "Aurora Borealis",
        "description": "Animierte Aurora-Welle: Dunkelblau → Lila → Grün → Magenta",
        "stops": AURORA_COLORS,
        "speed": 0.001,
    },
    "fire_wave": {
        "name": "Fire",
        "description": "Feurige Welle: Rot → Orange → Gelb",
        "stops": FIRE_COLORS,
        "speed": 0.001,
    },
    "ocean_wave": {
        "name": "Ocean",
        "description": "Ozean-Welle: Tiefblau → Cyan → Hellblau",
        "stops": OCEAN_COLORS,
        "speed": 0.001,
    },
}


# ── Animation Engine ──────────────────────────────────────────────────────────


class AuroraEngine:
    """Steuert Tastatur + Maus gleichzeitig mit eigener Animation."""

    def __init__(self, animation="aurora_wave", custom_speed=None):
        self.anim = ANIMATIONS.get(animation)
        if not self.anim:
            raise ValueError(f"Unbekannte Animation: {animation}")

        self._custom_speed = custom_speed
        self._import_openrazer()
        self._init_devices()
        self._phase = 0.0
        self._running = False

    def _import_openrazer(self):
        """OpenRazer importieren (hier, damit Import-Fehler nicht das ganze Skript blockieren)."""
        try:
            from openrazer.client import DeviceManager as DM
            self.DeviceManager = DM
        except ImportError:
            print("❌ OpenRazer nicht installiert. (pip install openrazer)")
            sys.exit(1)

    def _init_devices(self):
        """Geräte initialisieren und Matrix-Größen ermitteln."""
        dm = self.DeviceManager()
        self.keyboard = None
        self.mouse = None
        self.kb_rows = 1
        self.kb_cols = 1
        self.mouse_cols = 1

        for d in dm.devices:
            name = d.name.lower()
            if "blackwidow" in name:
                self.keyboard = d
                adv = d.fx.advanced
                self.kb_rows = adv.rows
                self.kb_cols = adv.cols
                print(f"  ⌨️  {d.name}: {self.kb_rows}×{self.kb_cols} Matrix")
            elif "mamba" in name:
                self.mouse = d
                adv = d.fx.advanced
                self.mouse_cols = adv.cols
                print(f"  🖱️  {d.name}: 1×{self.mouse_cols} Ring")

        if not self.keyboard and not self.mouse:
            print("❌ Keine Razer-Geräte gefunden.")
            sys.exit(1)

    def _render_keyboard(self, phase):
        """Keyboard-Matrix mit Farbverlauf rendern."""
        if not self.keyboard:
            return
        frame = self.keyboard.fx.advanced.matrix
        cols = self.kb_cols
        rows = self.kb_rows

        for row in range(rows):
            for col in range(cols):
                pos = ((col / cols) + phase) % 1.0
                row_offset = row * 0.03
                pos = (pos + row_offset) % 1.0
                rgb = Color.gradient(self.anim["stops"], pos)
                frame.set(row, col, rgb)

        # Reset + draw_with_fb_or = sauberer Frame ohne Flackern
        self.keyboard.fx.advanced.draw()

    def _render_mouse(self, phase):
        """Maus-Ring mit Farbverlauf rendern. Logo/Scroll nur selten aktualisieren."""
        if not self.mouse:
            return
        frame = self.mouse.fx.advanced.matrix
        cols = self.mouse_cols

        for col in range(cols):
            pos = ((col / cols) + phase) % 1.0
            rgb = Color.gradient(self.anim["stops"], pos)
            frame.set(0, col, rgb)

        # Reset + draw = sauberer Frame
        self.mouse.fx.advanced.draw()

    def _update_mouse_statics(self, phase):
        """Logo & Scrollrad setzen (nur alle ~2s, um Flackern zu vermeiden)."""
        if not self.mouse:
            return
        dom_pos = (phase + 0.3) % 1.0
        dom_rgb = Color.gradient(self.anim["stops"], dom_pos)
        try:
            self.mouse.fx.misc.logo.static(*dom_rgb)
            self.mouse.fx.misc.scroll_wheel.static(*dom_rgb)
        except Exception:
            pass

    def run(self, fps=24, duration=None):
        """
        Hauptloop.
        fps: Bilder pro Sekunde
        duration: Sekunden (None = endlos bis Ctrl+C)
        """
        self._running = True
        speed = self._custom_speed if self._custom_speed is not None else self.anim["speed"]
        interval = 1.0 / fps
        start = time.time()
        frames = 0

        print(f"\n  ✨ {self.anim['name']}")
        print(f"  {self.anim['description']}")
        print(f"  FPS: {fps}  |  Drücke Ctrl+C zum Beenden\n")

        try:
            mouse_static_timer = 0.0
            while self._running:
                loop_start = time.time()
                frames += 1

                self._render_keyboard(self._phase)
                self._render_mouse(self._phase)

                # Logo/Scroll nur alle 2s aktualisieren (gegen Flackern)
                mouse_static_timer += interval
                if mouse_static_timer >= 2.0:
                    self._update_mouse_statics(self._phase)
                    mouse_static_timer = 0.0

                self._phase = (self._phase + speed) % 1.0

                elapsed = time.time() - loop_start
                sleep_time = interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

                # Zeitlimit prüfen
                if duration and (time.time() - start) >= duration:
                    print(f"  Fertig ({duration}s).")
                    break

        except KeyboardInterrupt:
            print("  Abbruch...")
        finally:
            self.cleanup()

    def stop(self):
        """Animation sanft beenden."""
        self._running = False

    def cleanup(self):
        """Aufräumen: Standard-Wave setzen."""
        print("  Setze Standard-Beleuchtung...")
        try:
            if self.keyboard:
                self.keyboard.fx.wave(1)
            if self.mouse:
                self.mouse.fx.wave(1)
        except Exception:
            pass
        print("  ✅ Fertig.")


# ── Main ──────────────────────────────────────────────────────────────────────


def list_animations():
    print("\nVerfügbare Animationen:")
    print("=" * 60)
    for key, anim in ANIMATIONS.items():
        print(f"  {key}")
        print(f"      {anim['description']}")
    print()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Aurora Animated Lighting für Razer (OpenRazer)"
    )
    parser.add_argument(
        "animation", nargs="?",
        default="aurora_wave",
        help="Animation (default: aurora_wave)"
    )
    parser.add_argument("--list", action="store_true", help="Animationen auflisten")
    parser.add_argument("--fps", type=int, default=12, help="FPS (default: 12)")
    parser.add_argument("--duration", type=float, default=None, help="Laufzeit in Sek.")
    parser.add_argument("--speed", type=float, default=None,
                        help="Geschwindigkeit überschreiben (0.001=langsam, 0.01=schnell)")

    args = parser.parse_args()

    if args.list:
        list_animations()
        return

    if args.animation == "list":
        list_animations()
        return

    if args.animation not in ANIMATIONS:
        print(f"❌ Unbekannte Animation: {args.animation}")
        list_animations()
        sys.exit(1)

    engine = AuroraEngine(args.animation, custom_speed=args.speed)
    engine.run(fps=args.fps, duration=args.duration)


if __name__ == "__main__":
    main()
