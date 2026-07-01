#!/usr/bin/env python3
"""
Razer Aurora Lighting — OpenRazer Profile Manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Steuert Razer-Geräte (BlackWidow Elite, Mamba Elite, …) über OpenRazer.
Profile werden als JSON definiert und können per Kommandozeile geladen werden.

Nutzung:
  python3 aurora_openrazer.py                     # interaktive Auswahl
  python3 aurora_openrazer.py list                # alle Profile anzeigen
  python3 aurora_openrazer.py "Aurora Borealis"    # Profil anwenden
  python3 aurora_openrazer.py off                  # Beleuchtung aus
"""

import json
import os
import sys
import time
from pathlib import Path

# ── Profile-Verzeichnis ──────────────────────────────────────────────────────
PROFILE_DIR = Path.home() / ".config" / "razer-lighting"
PROFILE_DIR.mkdir(parents=True, exist_ok=True)

# ── Integrierte Profile ──────────────────────────────────────────────────────
BUILTIN_PROFILES = {
    "Aurora Borealis": {
        "description": "Grün/Lila/Magenta — Nordlicht-Atmosphäre (aus Chroma-Profil)",
        "colors": {
            "background": (1, 1, 20),
            "dark_purple": (18, 2, 31),
            "purple": (103, 11, 181),
            "aurora_green": (150, 255, 108),
            "magenta": (240, 12, 255),
        },
        "devices": {
            "keyboard": {
                "mode": "breath_dual",
                "color1": "aurora_green",
                "color2": "magenta",
            },
            "mouse": {
                "ring_mode": "aurora_green",
                "logo_mode": "magenta",
                "scroll_mode": "purple",
            },
        },
    },
    "Aurora Night": {
        "description": "Dunkles Blau/Violett — ruhig, dezent",
        "colors": {
            "background": (1, 1, 20),
            "dark_blue": (5, 10, 50),
            "purple": (60, 10, 100),
            "soft_green": (50, 120, 60),
        },
        "devices": {
            "keyboard": {
                "mode": "starlight_dual",
                "color1": "dark_blue",
                "color2": "soft_green",
            },
            "mouse": {
                "ring_mode": "soft_green",
                "logo_mode": "purple",
                "scroll_mode": "dark_blue",
            },
        },
    },
    "Fire": {
        "description": "Rot/Orange/Gelb — feurig und intensiv",
        "colors": {
            "red": (255, 20, 0),
            "orange": (255, 120, 0),
            "yellow": (255, 200, 50),
        },
        "devices": {
            "keyboard": {
                "mode": "breath_triple",
                "color1": "red",
                "color2": "orange",
                "color3": "yellow",
            },
            "mouse": {
                "ring_mode": "orange",
                "logo_mode": "red",
                "scroll_mode": "yellow",
            },
        },
    },
    "Spectrum": {
        "description": "Regenbogen-Welle — Standard-Spektrum",
        "devices": {
            "keyboard": {
                "mode": "wave",
            },
            "mouse": {
                "ring_mode": "wave",
                "logo_mode": None,
                "scroll_mode": None,
            },
        },
    },
    "Static Purple": {
        "description": "Einfarbig Lila — ruhig und clean",
        "colors": {
            "purple": (103, 11, 181),
        },
        "devices": {
            "keyboard": {
                "mode": "static",
                "color1": "purple",
            },
            "mouse": {
                "ring_mode": "purple",
                "logo_mode": "purple",
                "scroll_mode": "purple",
            },
        },
    },
}

# ── Hilfsfunktionen ───────────────────────────────────────────────────────────


def _col(profile, name):
    """Farbe aus Profil-Colors holen. Fallback: (0,0,0)."""
    colors = profile.get("colors", {})
    if name in colors:
        return colors[name]
    return (0, 0, 0)


def _find_device(dm, keyword):
    """Erstes Gerät finden, das 'keyword' im Namen enthält."""
    for d in dm.devices:
        if keyword.lower() in d.name.lower():
            return d
    return None


# ── Geräte-spezifische Setter ─────────────────────────────────────────────────


def _set_keyboard(dev, mode, profile):
    """Beleuchtung für BlackWidow Elite / Tastatur setzen."""
    colors = profile.get("colors", {})

    try:
        if mode == "off":
            return dev.fx.none()
        if mode == "wave":
            return dev.fx.wave(1)
        if mode == "spectrum":
            return dev.fx.spectrum()
        if mode == "static":
            c = _col(profile, profile["devices"]["keyboard"].get("color1", "aurora_green"))
            return dev.fx.static(*c)
        if mode == "breath_single":
            c = _col(profile, profile["devices"]["keyboard"].get("color1", "aurora_green"))
            return dev.fx.breath_single(*c)
        if mode == "breath_dual":
            c1 = _col(profile, profile["devices"]["keyboard"].get("color1", "aurora_green"))
            c2 = _col(profile, profile["devices"]["keyboard"].get("color2", "purple"))
            return dev.fx.breath_dual(*c1, *c2)
        if mode == "breath_triple":
            c1 = _col(profile, profile["devices"]["keyboard"].get("color1", "red"))
            c2 = _col(profile, profile["devices"]["keyboard"].get("color2", "orange"))
            c3 = _col(profile, profile["devices"]["keyboard"].get("color3", "yellow"))
            return dev.fx.breath_triple(*c1, *c2, *c3)
        if mode == "starlight_dual":
            c1 = _col(profile, profile["devices"]["keyboard"].get("color1", "aurora_green"))
            c2 = _col(profile, profile["devices"]["keyboard"].get("color2", "magenta"))
            return dev.fx.starlight_dual(*c1, *c2, 2)
        if mode == "reactive":
            c = _col(profile, profile["devices"]["keyboard"].get("color1", "aurora_green"))
            return dev.fx.reactive(*c, 2)
        if mode == "ripple":
            c = _col(profile, profile["devices"]["keyboard"].get("color1", "aurora_green"))
            return dev.fx.ripple(*c, 0.05)
    except Exception as e:
        print(f"  ⚠️  Tastatur-Fehler: {e}")
        return False

    print(f"  ⚠️  Unbekannter Tastatur-Modus: {mode}")
    return False


def _set_mouse(dev, profile):
    """Beleuchtung für Mamba Elite setzen (Matrix + Einzel-LEDs)."""
    cfg = profile.get("devices", {}).get("mouse", {})
    colors = profile.get("colors", {})

    ring_mode = cfg.get("ring_mode")
    logo_color_name = cfg.get("logo_mode")
    scroll_color_name = cfg.get("scroll_mode")

    try:
        # Ring über advanced-Matrix
        if ring_mode and ring_mode != "wave":
            if ring_mode in colors:
                rgb = colors[ring_mode]
            else:
                rgb = _col(profile, ring_mode) if ring_mode else (0, 0, 0)

            frame = dev.fx.advanced.matrix
            for c in range(dev.fx.advanced.cols):
                frame.set(0, c, rgb)
            dev.fx.advanced.draw()
        elif ring_mode == "wave":
            dev.fx.wave(1)
        else:
            # Ausschalten (schwarz)
            frame = dev.fx.advanced.matrix
            for c in range(dev.fx.advanced.cols):
                frame.set(0, c, (0, 0, 0))
            dev.fx.advanced.draw()

        # Logo
        if logo_color_name:
            if logo_color_name in colors:
                rgb = colors[logo_color_name]
            else:
                rgb = _col(profile, logo_color_name) if logo_color_name else (0, 0, 0)
            dev.fx.misc.logo.static(*rgb)

        # Scrollrad
        if scroll_color_name:
            if scroll_color_name in colors:
                rgb = colors[scroll_color_name]
            else:
                rgb = _col(profile, scroll_color_name) if scroll_color_name else (0, 0, 0)
            dev.fx.misc.scroll_wheel.static(*rgb)

    except Exception as e:
        print(f"  ⚠️  Maus-Fehler: {e}")
        return False

    return True


# ── Profil anwenden ───────────────────────────────────────────────────────────


def apply_profile(profile_name: str, profile: dict) -> bool:
    """Ein Profil auf alle angeschlossenen Razer-Geräte anwenden."""
    try:
        from openrazer.client import DeviceManager
    except ImportError:
        print("❌ OpenRazer nicht installiert. (pip install openrazer)")
        return False

    dm = DeviceManager()
    if not dm.devices:
        print("❌ Keine Razer-Geräte gefunden.")
        return False

    keyboard = _find_device(dm, "blackwidow")
    mouse = _find_device(dm, "mamba")

    print(f"\n  Profil: {profile_name}")
    print(f"  Info:   {profile.get('description', '')}")
    print()

    # Tastatur
    kb_cfg = profile.get("devices", {}).get("keyboard", {})
    if keyboard and kb_cfg:
        mode = kb_cfg.get("mode", "breath_dual")
        print(f"  ⌨️  Tastatur ({keyboard.name}): {mode}")
        result = _set_keyboard(keyboard, mode, profile)
        print(f"      → {'✅' if result else '❌'}")
    elif keyboard:
        print(f"  ⌨️  Tastatur: kein Profil definiert — übersprungen")

    # Maus
    mouse_cfg = profile.get("devices", {}).get("mouse", {})
    if mouse and mouse_cfg:
        print(f"  🖱️  Maus ({mouse.name}): Ring={mouse_cfg.get('ring_mode','?')} "
              f"Logo={mouse_cfg.get('logo_mode','?')} Scroll={mouse_cfg.get('scroll_mode','?')}")
        result = _set_mouse(mouse, profile)
        print(f"      → {'✅' if result else '❌'}")
    elif mouse:
        print(f"  🖱️  Maus: kein Profil definiert — übersprungen")

    if not keyboard and not mouse:
        print("  ⚠️  Weder Tastatur noch Maus gefunden.")
        return False

    return True


# ── Profile laden (built-in + extern) ────────────────────────────────────────


def load_profiles() -> dict:
    """Alle verfügbaren Profile laden (built-in + aus ~/.config/razer-lighting/)."""
    profiles = dict(BUILTIN_PROFILES)

    # Externe Profile aus dem Config-Ordner laden
    for f in sorted(PROFILE_DIR.glob("*.json")):
        try:
            with open(f, "r") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and "devices" in data:
                name = data.get("name", f.stem)
                profiles[name] = data
        except Exception:
            pass

    return profiles


def list_profiles(profiles: dict):
    """Alle Profile übersichtlich anzeigen."""
    print("\nVerfügbare Profile:")
    print("=" * 60)
    for i, (name, data) in enumerate(profiles.items(), 1):
        desc = data.get("description", "")
        kb = data.get("devices", {}).get("keyboard", {}).get("mode", "?")
        mouse = data.get("devices", {}).get("mouse", {}).get("ring_mode", "?")
        col = _describe_colors(data)
        print(f"  {i:2d}. {name}")
        print(f"      {desc}")
        print(f"      Tastatur: {kb}  |  Maus: Ring={mouse}")
        if col:
            print(f"      Farben: {col}")
        print()


def _describe_colors(profile: dict) -> str:
    """Farben als lesbaren String darstellen."""
    colors = profile.get("colors")
    if not colors:
        return ""
    parts = []
    for name, rgb in colors.items():
        if isinstance(rgb, tuple) and len(rgb) == 3:
            parts.append(f"{name}=({rgb[0]},{rgb[1]},{rgb[2]})")
    return ", ".join(parts[:5])  # max 5


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    profiles = load_profiles()

    # Kein Argument → interaktiv
    if len(sys.argv) < 2:
        list_profiles(profiles)
        names = list(profiles.keys())
        try:
            choice = input(f"Profil-Nummer (1–{len(names)}) oder Name: ").strip()
            if not choice:
                return
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(names):
                    apply_profile(names[idx], profiles[names[idx]])
                else:
                    print(f"❌ Ungültige Nummer: {choice}")
            elif choice in profiles:
                apply_profile(choice, profiles[choice])
            else:
                print(f"❌ Unbekanntes Profil: {choice}")
        except (EOFError, KeyboardInterrupt):
            print()
        return

    cmd = sys.argv[1]

    if cmd == "list":
        list_profiles(profiles)
        return

    if cmd == "off":
        try:
            from openrazer.client import DeviceManager
            dm = DeviceManager()
            for d in dm.devices:
                d.fx.none()
                print(f"  {d.name}: aus")
        except ImportError:
            print("❌ OpenRazer nicht installiert.")
        return

    if cmd in profiles:
        apply_profile(cmd, profiles[cmd])
        return

    # Namen mit Teilübereinstimmung suchen
    matches = [n for n in profiles if cmd.lower() in n.lower()]
    if len(matches) == 1:
        apply_profile(matches[0], profiles[matches[0]])
    elif len(matches) > 1:
        print(f"Mehrere Treffer für '{cmd}':")
        for m in matches:
            print(f"  • {m}")
    else:
        print(f"❌ Profil '{cmd}' nicht gefunden.")
        print("Verfügbar: python3 aurora_openrazer.py list")
        sys.exit(1)


if __name__ == "__main__":
    main()
