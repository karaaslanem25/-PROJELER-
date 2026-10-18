
import os

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["GLOG_minloglevel"] = "3"

import cv2
import mediapipe as mp
import numpy as np
from collections import deque


# ==========================================
# AYARLAR
# ==========================================

KAMERA_NUMARALARI = [0, 1, 2, 3, 4]
IZ_UZUNLUGU = 40

RENKLER = [
    (255, 0, 255),    # Mor
    (255, 100, 0),    # Mavi
    (0, 255, 0),      # Yesil
    (0, 255, 255),    # Sari
    (0, 100, 255),    # Turuncu
]

PARMAK_UCLARI = [4, 8, 12, 16, 20]


# ==========================================
# KAMERAYI BUL
# ==========================================

def kamerayi_ac():
    suruculer = [cv2.CAP_DSHOW, cv2.CAP_MSMF]

    for surucu in suruculer:
        for numara in KAMERA_NUMARALARI:
            kamera = cv2.VideoCapture(numara, surucu)

            if kamera.isOpened():
                kamera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                kamera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

                ok, goruntu = kamera.read()

                if ok and goruntu is not None:
                    print(f"Kamera acildi: {numara}")
                    return kamera

            kamera.release()

    return None


# ==========================================
# ANA PROGRAM
# ==========================================

def main():
    print("Kamera araniyor...")

    kamera = kamerayi_ac()

    if kamera is None:
        print("\nKAMERA ACILAMADI!")
        print("Windows Kamera uygulamasini kontrol et.")
        print("Kamera izinlerini etkinlestir.")
        print("Kamerayi kullanan diger uygulamalari kapat.")
        return

    mp_hands = mp.solutions.hands
    mp_draw = mp.solutions.drawing_utils

    izler = {}

    try:
        with mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            model_complexity=0,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6
        ) as eller:

            print("El takip baslatildi. Cikmak icin Q tusuna bas.")

            while True:
                ok, kare = kamera.read()

                if not ok or kare is None:
                    print("Kameradan goruntu alinamadi.")
                    break

                kare = cv2.flip(kare, 1)
                yukseklik, genislik = kare.shape[:2]

                rgb = cv2.cvtColor(kare, cv2.COLOR_BGR2RGB)
                sonuc = eller.process(rgb)

                # Neon cizgiler icin saydamlik yerine
                # siyah bir goruntu katmani kullanilir.
                isik = np.zeros_like(kare)
                aktif_izler = set()

                if sonuc.multi_hand_landmarks:
                    for el_no, el in enumerate(
                        sonuc.multi_hand_landmarks
                    ):
                        mp_draw.draw_landmarks(
                            kare,
                            el,
                            mp_hands.HAND_CONNECTIONS
                        )

                        for parmak_no, uc_no in enumerate(
                            PARMAK_UCLARI
                        ):
                            nokta = el.landmark[uc_no]

                            x = int(nokta.x * genislik)
                            y = int(nokta.y * yukseklik)

                            x = max(0, min(genislik - 1, x))
                            y = max(0, min(yukseklik - 1, y))

                            anahtar = (el_no, parmak_no)
                            aktif_izler.add(anahtar)

                            if anahtar not in izler:
                                izler[anahtar] = deque(
                                    maxlen=IZ_UZUNLUGU
                                )

                            izler[anahtar].append((x, y))

                            noktalar = list(izler[anahtar])
                            renk = RENKLER[parmak_no]

                            # Parmak ucunun arkasina cizgi cek
                            for i in range(1, len(noktalar)):
                                onceki = noktalar[i - 1]
                                simdiki = noktalar[i]

                                kalinlik = max(
                                    1,
                                    int(2 + 5 * i / len(noktalar))
                                )

                                cv2.line(
                                    isik,
                                    onceki,
                                    simdiki,
                                    renk,
                                    kalinlik,
                                    cv2.LINE_AA
                                )

                            # Neon parmak ucu
                            cv2.circle(
                                isik, (x, y), 12, renk, -1
                            )
                            cv2.circle(
                                kare, (x, y), 5, renk, -1
                            )

                # Kaybolan parmaklarin izlerini sifirla
                for anahtar in list(izler.keys()):
                    if anahtar not in aktif_izler:
                        izler[anahtar].clear()

                # Neon parlama efekti
                bulanik = cv2.GaussianBlur(
                    isik, (0, 0), 12
                )

                kare = cv2.addWeighted(
                    kare, 1.0, bulanik, 0.8, 0
                )

                kare = cv2.addWeighted(
                    kare, 1.0, isik, 0.9, 0
                )

                # Baslik
                cv2.putText(
                    kare,
                    "NEON HAND TRACKING - Q: EXIT",
                    (15, 35),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA
                )

                cv2.imshow("Neon El Takibi", kare)

                tus = cv2.waitKey(1) & 0xFF

                if tus == ord("q"):
                    break

    finally:
        kamera.release()
        cv2.destroyAllWindows()

    print("Program kapatildi.")


if __name__ == "__main__":
    main()
