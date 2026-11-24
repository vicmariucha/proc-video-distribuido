"""Filtros de imagem aplicados pelos workers. Todos recebem e devolvem uma imagem BGR do mesmo tamanho."""
import cv2
import numpy as np

def cinza(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)

def bordas(img: np.ndarray) -> np.ndarray:
    g = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    return cv2.cvtColor(cv2.Canny(g, 60, 150), cv2.COLOR_GRAY2BGR)

def desfoque(img: np.ndarray) -> np.ndarray:
    return cv2.GaussianBlur(img, (21, 21), 0)

def cartoon(img: np.ndarray) -> np.ndarray:
    g = cv2.medianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 7)
    mascara = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 9, 9)
    cor = img
    for _ in range(3):
        cor = cv2.bilateralFilter(cor, 9, 75, 75)
    return cv2.bitwise_and(cor, cor, mask=mascara)

def estilizar(img: np.ndarray) -> np.ndarray:
    return cv2.stylization(img, sigma_s=60, sigma_r=0.45)

_CLASSIFICADOR_ROSTOS = None

def rostos(img: np.ndarray) -> np.ndarray:
    global _CLASSIFICADOR_ROSTOS
    if _CLASSIFICADOR_ROSTOS is None:
        _CLASSIFICADOR_ROSTOS = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
    saida = img.copy()
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    for (x, y, w, h) in _CLASSIFICADOR_ROSTOS.detectMultiScale(g, scaleFactor=1.1, minNeighbors=5):
        saida[y:y + h, x:x + w] = cv2.GaussianBlur(saida[y:y + h, x:x + w], (51, 51), 0)  # anonimiza
        cv2.rectangle(saida, (x, y), (x + w, y + h), (0, 255, 0), 2)
    return saida

FILTROS = {
    "cinza": cinza,
    "bordas": bordas,
    "desfoque": desfoque,
    "cartoon": cartoon,
    "estilizar": estilizar,
    "rostos": rostos,
}

def aplicar(nome: str, img: np.ndarray) -> np.ndarray:
    if nome not in FILTROS:
        raise ValueError(f"Filtro desconhecido: {nome}")
    return FILTROS[nome](img)