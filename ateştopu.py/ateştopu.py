
import os
import cv2
import mediapipe as mp
import numpy as np
import random
import math
import time
import urllib.request
from collections import deque

# ==========================================
# SELENA ELEMENT GÜÇLERİ
# 1 = ATEŞ | 2 = SU | Q = ÇIKIŞ
# ==========================================

MODEL = "hand_landmarker.task"
MOD = "ATES"

MAX_PARTICLES = 1400
ATES_RENKLERI = [
    (0, 35, 255),
    (0, 100, 255),
    (0, 180, 255),
    (0, 230, 255),
    (60, 245, 255),
]

SU_RENKLERI = [
    (255, 70, 0),
    (255, 150, 0),
    (255, 220, 30),
    (220, 245, 255),
]

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/1/"
    "hand_landmarker.task"
)


# ==========================================
# MODELİ HAZIRLA
# ==========================================

def modeli_hazirla():
    if os.path.exists(MODEL):
        return True

    print("El takip modeli indiriliyor...")

    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL)
        print("Model indirildi.")
        return True
    except Exception as hata:
        print("Model indirilemedi:", hata)
        return False


# ==========================================
# PARÇACIK SİSTEMİ
# ==========================================

class Parca:
    def __init__(self, x, y, dx, dy, mod, guc=1.0):
        self.x = float(x)
        self.y = float(y)
        self.mod = mod

        self.vx = dx * random.uniform(9, 17) * guc
        self.vy = dy * random.uniform(9, 17) * guc

        dagilma = 0.25 if mod == "ATES" else 0.18
        self.vx += random.uniform(-dagilma, dagilma) * 12
        self.vy += random.uniform(-dagilma, dagilma) * 12

        self.omur = random.randint(20, 48)
        self.omur_max = self.omur
        self.r = random.randint(3, 8)

        self.renk = random.choice(
            ATES_RENKLERI if mod == "ATES" else SU_RENKLERI
        )

        self.onceki_x = self.x
        self.onceki_y = self.y

    def guncelle(self):
        self.onceki_x = self.x
        self.onceki_y = self.y

        self.x += self.vx
        self.y += self.vy

        if self.mod == "ATES":
            self.vy -= 0.12
            self.vx *= 0.985
            self.vy *= 0.985
        else:
            self.vy += 0.24
            self.vx *= 0.995

        self.omur -= 1

    def ciz(self, katman):
        if self.omur <= 0:
            return

        oran = self.omur / self.omur_max
        kalinlik = max(1, int(self.r * oran))

        onceki = (int(self.onceki_x), int(self.onceki_y))
        simdiki = (int(self.x), int(self.y))

        cv2.line(
            katman, onceki, simdiki,
            self.renk, kalinlik, cv2.LINE_AA
        )

        cv2.circle(
            katman, simdiki,
            max(1, int(self.r * oran)),
            self.renk, -1, cv2.LINE_AA
        )


# ==========================================
# ATEŞ VE SU PATLAMASI
# ==========================================

def patlama(katman, x, y, mod):
    if mod == "ATES":
        cv2.circle(katman, (x, y), 35, (0, 70, 255), -1, cv2.LINE_AA)
        cv2.circle(katman, (x, y), 22, (0, 180, 255), -1, cv2.LINE_AA)
        cv2.circle(katman, (x, y), 9, (180, 250, 255), -1, cv2.LINE_AA)
    else:
        cv2.circle(katman, (x, y), 30, (255, 100, 0), -1, cv2.LINE_AA)
        cv2.circle(katman, (x, y), 18, (255, 200, 40), -1, cv2.LINE_AA)
        cv2.circle(katman, (x, y), 7, (240, 255, 255), -1, cv2.LINE_AA)


# ==========================================
# PARLAMA
# ==========================================

def efekt_birlestir(kare, katman, mod):
    sigma = 16 if mod == "ATES" else 9
    glow = cv2.GaussianBlur(katman, (0, 0), sigma)
    kare = cv2.addWeighted(kare, 1.0, glow, 0.8, 0)

    glow2 = cv2.GaussianBlur(katman, (0, 0), 5)
    kare = cv2.addWeighted(kare, 1.0, glow2, 0.6, 0)

    return cv2.addWeighted(kare, 1.0, katman, 0.9, 0)


# ==========================================
# ANA PROGRAM
# ==========================================

def main():
    global MOD

    if not modeli_hazirla():
        print("Model dosyasi olmadan program baslatilamiyor.")
        return

    kamera = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not kamera.isOpened():
        kamera.release()
        kamera = cv2.VideoCapture(0)

    if not kamera.isOpened():
        print("Kamera acilamadi!")
        return

    kamera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    kamera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    BaseOptions = mp.tasks.BaseOptions
    HandLandmarker = mp.tasks.vision.HandLandmarker
    Options = mp.tasks.vision.HandLandmarkerOptions
    RunningMode = mp.tasks.vision.RunningMode

    parcaciklar = []
    izler = {}
    oncekiler = {}
    kare_no = 0

    options = Options(
        base_options=BaseOptions(model_asset_path=MODEL),
        running_mode=RunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.55,
        min_hand_presence_confidence=0.55,
        min_tracking_confidence=0.55
    )

    try:
        with HandLandmarker.create_from_options(options) as takipci:
            print("SELENA ELEMENT GÜÇLERİ AKTİF!")
            print("1: Ates | 2: Su | Q: Cikis")

            while True:
                ok, kare = kamera.read()

                if not ok or kare is None:
                    print("Kameradan goruntu alinamadi.")
                    break

                kare = cv2.flip(kare, 1)
                h, w = kare.shape[:2]
                rgb = cv2.cvtColor(kare, cv2.COLOR_BGR2RGB)
                rgb = np.ascontiguousarray(rgb)

                goruntu = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=rgb
                )

                kare_no += 1
                sonuc = takipci.detect_for_video(
                    goruntu, kare_no * 33
                )

                katman = np.zeros_like(kare)
                aktif = set()

                if sonuc.hand_landmarks:
                    for el_no, el in enumerate(sonuc.hand_landmarks):
                        # Avuç merkezi
                        bilek = el[0]
                        p5 = el[5]
                        p9 = el[9]
                        p13 = el[13]

                        x = int(
                            (bilek.x * 0.15 +
                             p5.x * 0.25 +
                             p9.x * 0.35 +
                             p13.x * 0.25) * w
                        )
                        y = int(
                            (bilek.y * 0.15 +
                             p5.y * 0.25 +
                             p9.y * 0.35 +
                             p13.y * 0.25) * h
                        )

                        x = max(0, min(w - 1, x))
                        y = max(0, min(h - 1, y))

                        # İşaret parmağı yönü
                        kok = el[5]
                        uc = el[8]

                        dx = uc.x - kok.x
                        dy = uc.y - kok.y
                        uzunluk = math.hypot(dx, dy)

                        if uzunluk > 0.001:
                            dx /= uzunluk
                            dy /= uzunluk
                        else:
                            dx, dy = 0.0, -1.0

                        aktif.add(el_no)

                        if el_no not in izler:
                            izler[el_no] = deque(maxlen=12)

                        izler[el_no].append((x, y))

                        eski = oncekiler.get(el_no, (x, y))
                        hiz = math.hypot(
                            x - eski[0], y - eski[1]
                        )
                        oncekiler[el_no] = (x, y)

                        guc = 1.0 + min(hiz / 80.0, 1.8)

                        patlama(katman, x, y, MOD)

                        adet = 12 if MOD == "ATES" else 18
                        adet += min(int(hiz / 8), 12)

                        for _ in range(adet):
                            if len(parcaciklar) >= MAX_PARTICLES:
                                break

                            parcaciklar.append(
                                Parca(x, y, dx, dy, MOD, guc)
                            )

                        # Huzme
                        bitis = (
                            int(x + dx * 90),
                            int(y + dy * 90)
                        )
                        renk = (
                            (0, 140, 255)
                            if MOD == "ATES"
                            else (255, 180, 20)
                        )

                        cv2.line(
                            katman, (x, y), bitis,
                            renk, 5, cv2.LINE_AA
                        )

                        # El iskeleti
                        baglantilar = [
                            (0, 1), (1, 2), (2, 3), (3, 4),
                            (0, 5), (5, 6), (6, 7), (7, 8),
                            (5, 9), (9, 10), (10, 11), (11, 12),
                            (9, 13), (13, 14), (14, 15), (15, 16),
                            (13, 17), (17, 18), (18, 19), (19, 20),
                            (0, 17)
                        ]

                        for a, b in baglantilar:
                            ax = int(el[a].x * w)
                            ay = int(el[a].y * h)
                            bx = int(el[b].x * w)
                            by = int(el[b].y * h)

                            cv2.line(
                                kare, (ax, ay), (bx, by),
                                renk, 2, cv2.LINE_AA
                            )

                # Görünmeyen ellerin izlerini temizle
                for anahtar in list(izler):
                    if anahtar not in aktif:
                        izler[anahtar].clear()
                        oncekiler.pop(anahtar, None)

                # Parçacıkları güncelle
                kalanlar = []

                for p in parcaciklar:
                    p.guncelle()

                    if (
                        p.omur > 0
                        and -50 < p.x < w + 50
                        and -50 < p.y < h + 50
                    ):
                        p.ciz(katman)
                        kalanlar.append(p)

                parcaciklar = kalanlar

                kare = efekt_birlestir(kare, katman, MOD)

                renk_yazi = (
                    (0, 150, 255)
                    if MOD == "ATES"
                    else (255, 200, 30)
                )

                cv2.putText(
                    kare, "SELENA - " + MOD,
                    (20, 42), cv2.FONT_HERSHEY_SIMPLEX,
                    1.0, renk_yazi, 3, cv2.LINE_AA
                )

                cv2.putText(
                    kare, "1: FIRE   2: WATER   Q: EXIT",
                    (20, h - 25), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (255, 255, 255), 2, cv2.LINE_AA
                )

                cv2.imshow("SELENA - ELEMENT GUCUN", kare)

                tus = cv2.waitKey(1) & 0xFF

                if tus == ord("1"):
                    MOD = "ATES"
                    print("ATES GÜCÜ AKTİF!")

                elif tus == ord("2"):
                    MOD = "SU"
                    print("SU GÜCÜ AKTİF!")

                elif tus == ord("q"):
                    break

    except Exception as hata:
        print("Program hatasi:", repr(hata))

    finally:
        kamera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
