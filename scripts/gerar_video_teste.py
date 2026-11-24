"""Gera um vídeo sintético de teste (formas coloridas em movimento) caso você não tenha um vídeo à mão.

Uso: python scripts/gerar_video_teste.py data/input/teste.mp4 --segundos 10
"""
import argparse

import cv2
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("saida")
ap.add_argument("--segundos", type=int, default=10)
ap.add_argument("--fps", type=int, default=30)
ap.add_argument("--largura", type=int, default=1280)
ap.add_argument("--altura", type=int, default=720)
a = ap.parse_args()

w = cv2.VideoWriter(a.saida, cv2.VideoWriter_fourcc(*"mp4v"), a.fps, (a.largura, a.altura))
for i in range(a.segundos * a.fps):
    t = i / a.fps
    img = np.zeros((a.altura, a.largura, 3), np.uint8)
    img[:] = (40 + 30 * np.sin(t), 60, 90 + 40 * np.cos(t))
    for k in range(6):
        x = int((a.largura / 2) + (a.largura / 3) * np.sin(t * (0.6 + 0.2 * k) + k))
        y = int((a.altura / 2) + (a.altura / 3) * np.cos(t * (0.8 + 0.1 * k) + k))
        cv2.circle(img, (x, y), 40 + 10 * k, ((50 * k) % 255, 200 - 25 * k, 255 - 30 * k), -1)
    cv2.putText(img, f"frame {i}", (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)
    w.write(img)
w.release()
print(f"Vídeo gerado: {a.saida}")
