"""Génère assets/icon.png et assets/icon.ico (nécessite Pillow).
Appelé automatiquement par build_windows.bat / build_macos.sh si les icônes sont absentes.
    python assets/make_icon.py
"""
import os
from PIL import Image, ImageDraw

OUT = os.path.dirname(os.path.abspath(__file__))
S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle([40, 40, S - 40, S - 40], radius=220, fill=(67, 56, 202))
# Clap de cinéma stylisé
d.rounded_rectangle([200, 420, 824, 800], radius=40, fill=(255, 255, 255))
d.polygon([(200, 300), (800, 200), (824, 330), (224, 430)], fill=(255, 255, 255))
for i in range(4):
    x = 260 + i * 150
    d.polygon([(x, 290 - i * 25), (x + 70, 278 - i * 25), (x + 130, 400 - i * 25),
               (x + 60, 412 - i * 25)], fill=(67, 56, 202))
d.ellipse([440, 540, 584, 684], fill=(245, 158, 11))
img.save(os.path.join(OUT, "icon.png"))
img.resize((256, 256), Image.LANCZOS).save(
    os.path.join(OUT, "icon.ico"),
    sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("Icônes générées dans", OUT)
