#!/usr/bin/env python3
"""
Razer Chroma XML → OpenRazer JSON-Profil Konverter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Liest ein Razer-Synapse-Chroma-Profil (.xml) ein und erzeugt
ein JSON-Profil für aurora_openrazer.py.

Nutzung:
  python3 chroma_importer.py <Profil.xml>
  python3 chroma_importer.py <Profil.xml> --save
  python3 chroma_importer.py <Profil-Verzeichnis>
"""

import json
import os
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


# ── Farbextraktion ────────────────────────────────────────────────────────────


def strip_ns(tag: str) -> str:
    """Namespace aus XML-Tag entfernen."""
    return tag.split("}")[-1]


def parse_chroma_xml(filepath: str) -> dict | None:
    """
    Chroma-XML parsen und relevante Daten extrahieren:
    - Effekte (wave, starlight, ripple, …)
    - Farben (RzColor → RGB)
    - Geräte im Profil
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except Exception as e:
        print(f"❌ Konnte XML nicht parsen: {e}")
        return None

    data = {
        "file": filepath,
        "name": Path(filepath).stem,
        "effects": [],
        "raw_colors": [],
        "devices": [],
        "mode": None,
    }

    # Mode
    mode_el = root.find(".//" + _q("Mode"))
    if mode_el is not None and mode_el.text:
        data["mode"] = mode_el.text.strip()

    # Geräte
    for dev in root.iter():
        tag = strip_ns(dev.tag)
        if tag == "Device":
            name_el = dev.find(_q("Name"))
            pid_el = dev.find(_q("Product_ID"))
            if name_el is not None and name_el.text:
                data["devices"].append({
                    "name": name_el.text.strip(),
                    "product_id": pid_el.text.strip() if pid_el is not None else "?",
                })

    # Effekte
    for elem in root.iter():
        tag = strip_ns(elem.tag)
        if tag == "Effect" and elem.text:
            data["effects"].append(elem.text.strip())

    # Farben (RzColor)
    for rz in root.iter():
        if strip_ns(rz.tag) == "RzColor":
            r = rz.find(_q("Red"))
            g = rz.find(_q("Green"))
            b = rz.find(_q("Blue"))
            blank = rz.find(_q("IsBlank"))
            if blank is not None and blank.text == "true":
                continue
            if r is not None and g is not None and b is not None:
                try:
                    rgb = (int(r.text), int(g.text), int(b.text))
                    data["raw_colors"].append(rgb)
                except ValueError:
                    pass

    return data


def _q(tag: str) -> str:
    """Wildcard-Namespace für ElementTree-Suche."""
    return f".//*[local-name()='{tag}']"


# ── Farbanalyse ───────────────────────────────────────────────────────────────


def dominant_colors(rgb_list: list, n: int = 5) -> list:
    """
    Die häufigsten Farben aus einer Liste von RGB-Tupeln ermitteln.
    Ähnliche Farben werden zusammengefasst.
    """
    if not rgb_list:
        return [(0, 0, 0)]

    # Quantisierung auf 32er-Schritte für Gruppierung
    quantized = []
    for r, g, b in rgb_list:
        qr = (r // 32) * 32
        qg = (g // 32) * 32
        qb = (b // 32) * 32
        quantized.append((qr, qg, qb))

    counter = Counter(quantized)
    most_common = counter.most_common(n)

    # Zurück zu Original-Durchschnittswerten
    result = []
    for (qr, qg, qb), count in most_common:
        # Alle ähnlichen Farben aus Original suchen und mitteln
        similar = [
            (r, g, b) for r, g, b in rgb_list
            if abs(r - qr) < 32 and abs(g - qg) < 32 and abs(b - qb) < 32
        ]
        if similar:
            avg_r = sum(c[0] for c in similar) // len(similar)
            avg_g = sum(c[1] for c in similar) // len(similar)
            avg_b = sum(c[2] for c in similar) // len(similar)
            result.append(((avg_r, avg_g, avg_b), count))
        else:
            result.append(((qr, qg, qb), count))

    return result


def guess_color_name(rgb) -> str:
    """Einen lesbaren Namen für eine RGB-Farbe raten."""
    r, g, b = rgb
    if r < 30 and g < 30 and b < 30:
        return "background"
    if r < 30 and g < 30 and b > 30:
        return "dark_blue"
    if r > 100 and g < 50 and b > 100:
        return "purple"
    if r > 200 and g < 50 and b < 50:
        return "red"
    if r > 150 and g > 200 and b < 150:
        return "aurora_green"
    if r > 200 and g < 100 and b > 200:
        return "magenta"
    if r > 200 and g > 100 and b < 50:
        return "orange"
    if r > 200 and g > 150 and b < 50:
        return "yellow"
    if r > 100 and g > 100 and b > 100:
        if r > g and r > b:
            return "warm"
        if g > r and g > b:
            return "green"
        if b > r and b > g:
            return "blue"
        return "gray"
    if r < 50 and g < 50 and b > 100:
        return "blue"
    if r > 50 and g > 50 and b > 50:
        return "light"
    return f"color_{r}_{g}_{b}"


def effects_to_mode(effects: list) -> str:
    """
    Die häufigsten Effekte aus dem Chroma-Profil auf OpenRazer-Modi mappen.
    """
    if not effects:
        return "static"

    counter = Counter(effects)
    top = counter.most_common(3)

    for effect, _ in top:
        effect = effect.lower()
        if effect == "wave":
            return "starlight_dual"  # näher an Aurora als Standard-Wave
        if effect == "starlight":
            return "starlight_dual"
        if effect in ("breathing", "breath"):
            return "breath_dual"
        if effect == "ripple":
            return "ripple"
        if effect == "reactive":
            return "reactive"
        if effect == "audiometer":
            return "breath_dual"  # nächstbeste Alternative

    return "breath_dual"


# ── Profil erzeugen ───────────────────────────────────────────────────────────


def build_profile(data: dict) -> dict:
    """
    Aus den extrahierten Chroma-Daten ein OpenRazer-Profil bauen.
    """
    dom = dominant_colors(data["raw_colors"], 6)

    # Farben mit Namen versehen
    named_colors = {}
    for (rgb, count), name in zip(dom, [
        "background", "aurora_green", "purple", "magenta",
        "dark_purple", "accent"
    ]):
        # Nur Farben mit >5% Anteil aufnehmen
        total = sum(c[1] for c in dom)
        if count / total > 0.05 or len(named_colors) < 3:
            named_colors[name] = rgb

    if not named_colors:
        named_colors["default"] = (0, 255, 0)

    # Effekt-Modus
    mode = effects_to_mode(data["effects"])

    # Geräte-Informationen für die Beschreibung
    device_names = [d["name"] for d in data["devices"]]
    device_str = ", ".join(device_names[:4])

    # Quelldatei
    source_file = os.path.basename(data["file"])

    colors_keys = list(named_colors.keys())

    profile = {
        "name": data.get("name", "Imported Chroma Profile"),
        "description": f"Aus Chroma-Profil '{source_file}' importiert — "
                       f"für: {device_str}",
        "source_xml": source_file,
        "chroma_mode": data.get("mode", "advanced"),
        "chroma_effects": list(Counter(data["effects"]).most_common(5)),
        "colors": named_colors,
        "devices": {
            "keyboard": {
                "mode": mode,
                "color1": colors_keys[1] if len(colors_keys) > 1 else colors_keys[0],
                "color2": colors_keys[2] if len(colors_keys) > 2 else colors_keys[0],
            },
            "mouse": {
                "ring_mode": colors_keys[1] if len(colors_keys) > 1 else colors_keys[0],
                "logo_mode": colors_keys[2] if len(colors_keys) > 2 else colors_keys[0],
                "scroll_mode": colors_keys[3] if len(colors_keys) > 3 else colors_keys[0],
            },
        },
    }

    # Optional dritte Farbe für breath_triple
    if mode == "breath_triple" and len(colors_keys) > 3:
        profile["devices"]["keyboard"]["color3"] = colors_keys[3]

    return profile


# ── Datei speichern ───────────────────────────────────────────────────────────


def save_profile(profile: dict, output_dir: str = None):
    """Profil als JSON speichern."""
    if output_dir is None:
        output_dir = str(Path.home() / ".config" / "razer-lighting")
    os.makedirs(output_dir, exist_ok=True)

    # Dateiname aus Profilname
    safe_name = profile["name"].replace(" ", "_").replace("/", "_")
    filepath = os.path.join(output_dir, f"{safe_name}.json")

    # Prüfen ob bereits vorhanden
    if os.path.exists(filepath):
        overwrite = input(f"⚠️  {safe_name}.json existiert bereits. Überschreiben? (j/N) ")
        if overwrite.lower() not in ("j", "ja", "y", "yes"):
            print("  Übersprungen.")
            return None

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)

    print(f"  ✅ Gespeichert: {filepath}")
    return filepath


# ── Ausgabe ───────────────────────────────────────────────────────────────────


def print_analysis(data: dict, dom_colors: list):
    """Extraktion analysieren und anzeigen."""
    print(f"\n📁 Datei: {os.path.basename(data['file'])}")
    print(f"📛 Name: {data['name']}")
    print(f"🎯 Modus: {data.get('mode', '?')}")

    print(f"\n📟 Geräte im Profil ({len(data['devices'])}):")
    for d in data["devices"]:
        print(f"  • {d['name']} (PID: {d['product_id']})")

    print(f"\n✨ Effekte ({len(data['effects'])}):")
    for effect, count in Counter(data["effects"]).most_common(10):
        print(f"  • {effect}: {count}x")

    print(f"\n🎨 Dominante Farben ({len(dom_colors)}):")
    for (rgb, count), name in zip(dom_colors, [
            "background", "aurora_green", "purple", "magenta",
            "dark_purple", "accent", "extra1", "extra2"
    ][:len(dom_colors)]):
        pct = count / max(1, len(data["raw_colors"])) * 100
        print(f"  • {name}: rgb{rgb}  ({pct:.0f}%)")


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    target = sys.argv[1]
    do_save = "--save" in sys.argv

    # Verzeichnis oder einzelne Datei?
    if os.path.isdir(target):
        xml_files = list(Path(target).glob("*.xml"))
        if not xml_files:
            print(f"❌ Keine XML-Dateien in '{target}' gefunden.")
            return
        print(f"📂 {len(xml_files)} XML-Dateien gefunden.")
        for xml_file in xml_files:
            data = parse_chroma_xml(str(xml_file))
            if data and data["raw_colors"]:
                dom = dominant_colors(data["raw_colors"], 6)
                print_analysis(data, dom)
                profile = build_profile(data)
                if do_save:
                    save_profile(profile)
            elif data:
                print(f"\n📁 {xml_file.name}: Keine Farbdaten gefunden.")
            print()
    else:
        # Einzeldatei
        if not os.path.exists(target):
            print(f"❌ Datei nicht gefunden: {target}")
            return

        data = parse_chroma_xml(target)
        if not data:
            return

        if not data["raw_colors"]:
            print("⚠️  Keine RzColor-Farben in dieser XML gefunden.")
            if data["effects"]:
                print("   Es wurden aber Effekte gefunden — verwende Standard-Farben.")
                data["raw_colors"] = [(0, 255, 0)]  # Fallback
            else:
                print("❌ Keine verwertbaren Daten.")
                return

        dom = dominant_colors(data["raw_colors"], 6)
        print_analysis(data, dom)

        profile = build_profile(data)

        print(f"\n🔧 Generiertes Profil:")
        print(json.dumps(profile, indent=2, ensure_ascii=False))

        if do_save:
            save_profile(profile)
        else:
            print(f"\n💡 Mit --save speichern, um das Profil dauerhaft zu nutzen.")


if __name__ == "__main__":
    main()