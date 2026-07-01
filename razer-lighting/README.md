# Razer Lighting — Chroma-Profil-Manager für OpenRazer

Steuert die Beleuchtung deiner Razer-Geräte über **OpenRazer** unter Linux.
Enthält ein Skript zur direkten Steuerung und einen **Chroma-XML-Importer**.

## Voraussetzungen

```bash
# OpenRazer + Python-Binding
sudo apt install openrazer-meta  # oder aus den Repos
pip install openrazer            # Python-Client

# Berechtigung für die eigene Benutzergruppe
sudo gpasswd -a $USER plugdev
# → neu einloggen!
```

## Verwendung

### `aurora_openrazer.py` — Profile anwenden

```bash
# Interaktive Auswahl
python3 razer-lighting/aurora_openrazer.py

# Alle Profile anzeigen
python3 razer-lighting/aurora_openrazer.py list

# Profil direkt anwenden
python3 razer-lighting/aurora_openrazer.py "Aurora Borealis"

# Beleuchtung ausschalten
python3 razer-lighting/aurora_openrazer.py off
```

### `chroma_importer.py` — Chroma-Profile importieren

Lädt ein Razer-Synapse-Chroma-Profil (XML) und erzeugt daraus ein
JSON-Profil für `aurora_openrazer.py`.

```bash
# Analyse (nur anzeigen)
python3 chroma_importer.py ~/Downloads/Unrealhero.AuroraBorealis/61a54143-*.xml

# Analysieren + als Profil speichern
python3 chroma_importer.py ~/Downloads/Unrealhero.AuroraBorealis/61a54143-*.xml --save

# Ganzes Verzeichnis mit mehreren XMLs verarbeiten
python3 chroma_importer.py ~/Downloads/Unrealhero.AuroraBorealis/ --save
```

Gespeicherte Profile landen in `~/.config/razer-lighting/`
und werden beim nächsten Start von `aurora_openrazer.py` automatisch geladen.

## Autostart (systemd)

Damit das Profil beim Einloggen automatisch gesetzt wird:

```bash
mkdir -p ~/.config/systemd/user/

cat > ~/.config/systemd/user/razer-lighting.service << 'EOF'
[Unit]
Description=Razer Aurora-Beleuchtung
After=graphical-session.target openrazer-daemon.service
PartOf=graphical-session.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /PFAD/ZU/razer-lighting/aurora_openrazer.py "Aurora Borealis"
RemainAfterExit=yes

[Install]
WantedBy=default.target
EOF

systemctl --user enable --now razer-lighting.service
```

Pass den Pfad und den Profilnamen nach Bedarf an.

## Unterstützte Geräte

| Gerät | Status | Steuerung |
|---|---|---|
| Razer BlackWidow Elite | ✅ | `fx.breath_dual()`, `fx.starlight_dual()`, … |
| Razer Mamba Elite | ✅ | `advanced.draw()` + `misc.logo.static()` |
| Andere Tastaturen | ✅ (wenn OpenRazer-kompatibel) | Automatisch erkannt |
| Andere Mäuse | ⚠️ (wenn `advanced`-Matrix) | Möglicherweise anpassbar |

## Eigene Profile

Profile sind JSON-Dateien in `~/.config/razer-lighting/`.
Beispiel:

```json
{
  "name": "Mein Profil",
  "description": "Eigene Farbkombination",
  "colors": {
    "dein_blau": [0, 100, 255],
    "dein_rot": [200, 20, 0]
  },
  "devices": {
    "keyboard": {
      "mode": "breath_dual",
      "color1": "dein_blau",
      "color2": "dein_rot"
    },
    "mouse": {
      "ring_mode": "dein_blau",
      "logo_mode": "dein_rot",
      "scroll_mode": "dein_blau"
    }
  }
}
```

Verfügbare Modi:
- `static`, `breath_single`, `breath_dual`, `breath_triple`
- `starlight_dual`, `reactive`, `ripple`, `wave`, `spectrum`
