#!/usr/bin/env python3
"""Beispiel-Test des chroma_importer mit der AuroraBorealis-XML."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from chroma_importer import parse_chroma_xml, dominant_colors, build_profile, print_analysis

if len(sys.argv) < 2:
    print("Nutzung: test_importer.py <Chroma.xml>")
    sys.exit(1)

data = parse_chroma_xml(sys.argv[1])
if not data:
    sys.exit(1)

dom = dominant_colors(data["raw_colors"], 6)
print_analysis(data, dom)

print("\n\n🔧 Generiertes Profil:")
import json
profile = build_profile(data)
print(json.dumps(profile, indent=2))
