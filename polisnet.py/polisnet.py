
# ============================================================
#                         POLİSNET
#              AKILLI OLAY KAYIT VE ANALİZ SİSTEMİ
# ============================================================
#
# PROJEYİ HAZIRLAYAN:
# Emirhan KARAASLAN
#
# PROJENİN ADI:
# POLİSNET - Büyük Veri Destekli Olay Yönetim Sistemi
#
# PROJENİN AMACI:
# Polis ve kamu güvenliği alanlarında olay kayıtlarının
# düzenli biçimde tutulmasını, sınıflandırılmasını,
# aranmasını ve analiz edilmesini desteklemek amacıyla
# geliştirilmiş Python tabanlı bir yazılım prototipidir.
#
# KULLANIM AMACI:
# - Olay kayıtlarının dijital ortamda saklanması
# - Kayıp ve bulunan eşya bildirimlerinin yönetilmesi
# - Trafik, çevre ve kamu düzeni bildirimlerinin
#   kategorilere ayrılması
# - Olayların öncelik ve durum bilgilerinin takip edilmesi
# - Kayıtlar üzerinde arama ve filtreleme yapılması
# - Büyük veri kümelerinin performans testlerinin yapılması
# - CSV formatında rapor ve veri çıktısı oluşturulması
# - Kamu güvenliği alanında veri analizi çalışmalarına
#   yardımcı olunması
#
# TEKNİK ALTYAPI:
# Python, Tkinter ve SQLite teknolojileri kullanılmıştır.
# Veriler yerel SQLite veritabanlarında saklanmaktadır.
#
# VERİ GÜVENLİĞİ VE SORUMLULUK:
# Bu yazılım eğitim, araştırma ve prototip geliştirme
# amacıyla hazırlanmıştır.
#
# DEMO kayıtları tamamen sentetiktir ve gerçek olayları
# temsil etmez. Gerçek kayıtlar yalnızca yetkili kullanıcı
# tarafından girilen bilgilerden oluşmalıdır.
#
# Yazılım, herhangi bir resmî polis veya devlet veri
# tabanına kendiliğinden erişmez.
#
# Gerçek kurum kullanımında gerekli izinler, güvenlik
# önlemleri, erişim kontrolü ve mevzuat uyumluluğu
# ayrıca sağlanmalıdır.
# Projeyi çalıştırmak için Python 3.x ve gerekli kütüphaneler (Tkinter, SQLite) yüklü olmalıdır.
# PROJEYİ GELİŞTİREN:
# Emirhan KARAASLAN
#
# ============================================================


import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import csv
from pathlib import Path
from datetime import datetime, timedelta

# =====================================================
# POLİSNET - 1.000.000 KAYITLIK TEST VERİ SİSTEMİ
# Sentetik kayıtlar DEMO olarak işaretlenir.
# Gerçek kayıtlar ayrı veritabanında tutulur.
# =====================================================

BASE = Path(__file__).resolve().parent

DEMO_DB = BASE / "polisnet_demo.db"
REAL_DB = BASE / "polisnet_gercek.db"

HEDEF_KAYIT = 1_000_000
EKLEME_PAKETI = 25_000
EKRAN_LIMITI = 500


def db_ac(path):
    con = sqlite3.connect(path)
    con.execute("""
        CREATE TABLE IF NOT EXISTS olaylar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            olay_no TEXT UNIQUE,
            tarih TEXT,
            il TEXT,
            ilce TEXT,
            kategori TEXT,
            oncelik TEXT,
            durum TEXT,
            aciklama TEXT
        )
    """)
    con.commit()
    return con


demo_con = db_ac(DEMO_DB)
real_con = db_ac(REAL_DB)

KATEGORILER = [
    "Kayıp eşya",
    "Bulunan eşya",
    "Trafik bildirimi",
    "Kamu düzeni",
    "Yardım talebi",
    "Çevre bildirimi",
    "Gürültü bildirimi",
    "Bilgi talebi",
    "Diğer"
]

ILCELER = [
    "Kadıköy", "Üsküdar", "Ataşehir", "Maltepe",
    "Kartal", "Pendik", "Ümraniye", "Beykoz",
    "Çekmeköy", "Sancaktepe", "Sultanbeyli",
    "Tuzla", "Şile", "Şişli", "Beşiktaş",
    "Bakırköy", "Fatih", "Esenler", "Bağcılar",
    "Avcılar", "Büyükçekmece", "Silivri"
]

ONCELIKLER = ["Düşük", "Normal", "Yüksek", "Acil"]

DURUMLAR = [
    "Yeni", "İnceleniyor", "Yönlendirildi", "Sonuçlandı"
]


def toplam_demo():
    return demo_con.execute(
        "SELECT COUNT(*) FROM olaylar"
    ).fetchone()[0]


def demo_uret():
    mevcut = toplam_demo()

    if mevcut >= HEDEF_KAYIT:
        messagebox.showinfo(
            "Bilgi",
            "1.000.000 test kaydı zaten oluşturulmuş."
        )
        return

    cevap = messagebox.askyesno(
        "Test verisi üretimi",
        "1.000.000 sentetik DEMO kaydı oluşturulacak.\n\n"
        "Bu işlem bilgisayarınızda disk alanı kullanır "
        "ve birkaç dakika sürebilir.\n\n"
        "Devam edilsin mi?"
    )

    if not cevap:
        return

    progress = tk.Toplevel(root)
    progress.title("Veri üretimi")
    progress.geometry("430x150")
    progress.transient(root)

    lbl = ttk.Label(
        progress,
        text="Sentetik test verileri hazırlanıyor..."
    )
    lbl.pack(pady=15)

    bar = ttk.Progressbar(
        progress,
        maximum=HEDEF_KAYIT,
        length=370,
        mode="determinate"
    )
    bar.pack(pady=10)

    root.update_idletasks()

    # İndeksler arama performansını artırır.
    demo_con.execute("""
        CREATE INDEX IF NOT EXISTS idx_demo_ilce
        ON olaylar(ilce)
    """)
    demo_con.execute("""
        CREATE INDEX IF NOT EXISTS idx_demo_kategori
        ON olaylar(kategori)
    """)
    demo_con.execute("""
        CREATE INDEX IF NOT EXISTS idx_demo_durum
        ON olaylar(durum)
    """)
    demo_con.commit()

    simdi = datetime.now()
    baslangic = max(0, mevcut)

    for paket_baslangic in range(
        baslangic,
        HEDEF_KAYIT,
        EKLEME_PAKETI
    ):
        paket = []

        paket_son = min(
            paket_baslangic + EKLEME_PAKETI,
            HEDEF_KAYIT
        )

        for i in range(paket_baslangic, paket_son):
            kategori = KATEGORILER[i % len(KATEGORILER)]
            ilce = ILCELER[i % len(ILCELER)]
            oncelik = ONCELIKLER[i % len(ONCELIKLER)]
            durum = DURUMLAR[i % len(DURUMLAR)]

            tarih = (
                simdi - timedelta(days=i % 3650)
            ).strftime("%d.%m.%Y %H:%M:%S")

            olay_no = f"DEMO-{i + 1:07d}"

            aciklama = (
                "SENTETİK TEST KAYDI - GERÇEK OLAY DEĞİLDİR. "
                f"Test kategorisi: {kategori}. "
                f"Test bölgesi: {ilce}. "
                "Bu kayıt yalnızca yazılım performansını "
                "ve raporlama özelliklerini test etmek için "
                "otomatik oluşturulmuştur."
            )

            paket.append((
                olay_no,
                tarih,
                "İstanbul",
                ilce,
                kategori,
                oncelik,
                durum,
                aciklama
            ))

        demo_con.executemany("""
            INSERT OR IGNORE INTO olaylar
            (
                olay_no, tarih, il, ilce,
                kategori, oncelik, durum, aciklama
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, paket)

        demo_con.commit()

        ilerleme = paket_son
        bar["value"] = ilerleme
        lbl.config(
            text=f"{ilerleme:,} / {HEDEF_KAYIT:,} kayıt oluşturuldu"
        )
        progress.update_idletasks()

    progress.destroy()
    listele()

    messagebox.showinfo(
        "Tamamlandı",
        f"Test veritabanında {toplam_demo():,} kayıt bulunuyor."
    )


def listele():
    for item in tablo.get_children():
        tablo.delete(item)

    kelime = arama_var.get().strip()

    if kelime:
        rows = demo_con.execute("""
            SELECT olay_no, tarih, ilce, kategori,
                   oncelik, durum
            FROM olaylar
            WHERE olay_no LIKE ?
               OR ilce LIKE ?
               OR kategori LIKE ?
               OR durum LIKE ?
            ORDER BY id DESC
            LIMIT ?
        """, (
            f"%{kelime}%",
            f"%{kelime}%",
            f"%{kelime}%",
            f"%{kelime}%",
            EKRAN_LIMITI
        )).fetchall()
    else:
        rows = demo_con.execute("""
            SELECT olay_no, tarih, ilce, kategori,
                   oncelik, durum
            FROM olaylar
            ORDER BY id DESC
            LIMIT ?
        """, (EKRAN_LIMITI,)).fetchall()

    for row in rows:
        tablo.insert("", tk.END, values=row)

    toplam_label.config(
        text=f"Toplam DEMO kayıt: {toplam_demo():,}"
    )

    gorunen_label.config(
        text=f"Listelenen: {len(rows):,} / en fazla {EKRAN_LIMITI}"
    )


def gercek_kayit_ekle():
    ilce = ilce_entry.get().strip()
    kategori = kategori_var.get()
    aciklama = aciklama_entry.get().strip()

    if not ilce or not aciklama:
        messagebox.showwarning(
            "Eksik bilgi",
            "İlçe ve açıklama alanlarını doldurun."
        )
        return

    olay_no = "OLAY-" + datetime.now().strftime("%Y%m%d%H%M%S%f")
    tarih = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    real_con.execute("""
        INSERT INTO olaylar
        (
            olay_no, tarih, il, ilce,
            kategori, oncelik, durum, aciklama
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        olay_no,
        tarih,
        "İstanbul",
        ilce,
        kategori,
        "Normal",
        "Yeni",
        aciklama
    ))

    real_con.commit()

    messagebox.showinfo(
        "Kayıt",
        "Kayıt gerçek kayıt veritabanına eklendi.\n"
        f"Olay numarası: {olay_no}"
    )

    ilce_entry.delete(0, tk.END)
    aciklama_entry.delete(0, tk.END)


def csv_aktar():
    dosya = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV dosyası", "*.csv")]
    )

    if not dosya:
        return

    kelime = arama_var.get().strip()

    if kelime:
        rows = demo_con.execute("""
            SELECT olay_no, tarih, il, ilce,
                   kategori, oncelik, durum, aciklama
            FROM olaylar
            WHERE olay_no LIKE ?
               OR ilce LIKE ?
               OR kategori LIKE ?
               OR durum LIKE ?
        """, (
            f"%{kelime}%",
            f"%{kelime}%",
            f"%{kelime}%",
            f"%{kelime}%"
        ))
    else:
        rows = demo_con.execute("""
            SELECT olay_no, tarih, il, ilce,
                   kategori, oncelik, durum, aciklama
            FROM olaylar
        """)

    with open(
        dosya, "w", newline="", encoding="utf-8-sig"
    ) as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([
            "Olay No", "Tarih", "İl", "İlçe",
            "Kategori", "Öncelik", "Durum", "Açıklama"
        ])

        writer.writerows(rows)

    messagebox.showinfo(
        "CSV",
        "Dışa aktarma tamamlandı."
    )


# =====================================================
# ARAYÜZ
# =====================================================

root = tk.Tk()
root.title("POLİSNET | Büyük Veri Olay Yönetimi")
root.geometry("1250x780")
root.configure(bg="#101827")

style = ttk.Style()
style.theme_use("clam")
style.configure("Treeview", rowheight=27)
style.configure(
    "Treeview.Heading",
    font=("Segoe UI", 10, "bold")
)

header = tk.Frame(root, bg="#101827")
header.pack(fill="x", padx=15, pady=12)

tk.Label(
    header,
    text="POLİSNET",
    font=("Segoe UI", 27, "bold"),
    fg="white",
    bg="#101827"
).pack(anchor="w")

tk.Label(
    header,
    text="BÜYÜK VERİ • OLAY KAYIT • ANALİZ",
    font=("Segoe UI", 11),
    fg="#60a5fa",
    bg="#101827"
).pack(anchor="w")

tk.Label(
    root,
    text="UYARI: DEMO verileri sentetiktir, gerçek olay değildir.",
    bg="#7f1d1d",
    fg="white",
    font=("Segoe UI", 10, "bold"),
    pady=7
).pack(fill="x", padx=15)

top = tk.Frame(root, bg="#101827")
top.pack(fill="x", padx=15, pady=10)

tk.Button(
    top,
    text="1.000.000 DEMO KAYDI ÜRET",
    command=demo_uret,
    bg="#2563eb",
    fg="white",
    font=("Segoe UI", 10, "bold"),
    padx=12,
    pady=8
).pack(side="left", padx=5)

tk.Button(
    top,
    text="YENİLE",
    command=listele,
    padx=12,
    pady=8
).pack(side="left", padx=5)

tk.Button(
    top,
    text="CSV DIŞA AKTAR",
    command=csv_aktar,
    padx=12,
    pady=8
).pack(side="left", padx=5)

arama_var = tk.StringVar()

tk.Label(
    top,
    text="Ara:",
    bg="#101827",
    fg="white"
).pack(side="right")

tk.Entry(
    top,
    textvariable=arama_var,
    width=28
).pack(side="right", padx=5)

arama_var.trace_add(
    "write",
    lambda *_: listele()
)

sayac = tk.Frame(root, bg="#101827")
sayac.pack(fill="x", padx=15)

toplam_label = tk.Label(
    sayac,
    text="Toplam DEMO kayıt: 0",
    bg="#101827",
    fg="white",
    font=("Segoe UI", 11, "bold")
)
toplam_label.pack(side="left")

gorunen_label = tk.Label(
    sayac,
    text="Listelenen: 0",
    bg="#101827",
    fg="#93c5fd"
)
gorunen_label.pack(side="right")

table_frame = tk.Frame(root)
table_frame.pack(fill="both", expand=True, padx=15, pady=10)

columns = (
    "Olay No", "Tarih", "İlçe",
    "Kategori", "Öncelik", "Durum"
)

tablo = ttk.Treeview(
    table_frame,
    columns=columns,
    show="headings"
)

for col in columns:
    tablo.heading(col, text=col)
    tablo.column(col, width=175, anchor="center")

scrollbar = ttk.Scrollbar(
    table_frame,
    orient="vertical",
    command=tablo.yview
)
tablo.configure(yscrollcommand=scrollbar.set)

tablo.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

# Gerçek kayıt girişi ayrı panel
real_frame = ttk.LabelFrame(
    root,
    text="Gerçek kayıt girişi - ayrı veritabanı",
    padding=10
)
real_frame.pack(fill="x", padx=15, pady=10)

tk.Label(real_frame, text="İlçe").grid(row=0, column=0)
ilce_entry = tk.Entry(real_frame, width=20)
ilce_entry.grid(row=1, column=0, padx=5)

tk.Label(real_frame, text="Kategori").grid(row=0, column=1)
kategori_var = tk.StringVar(value=KATEGORILER[0])

ttk.Combobox(
    real_frame,
    textvariable=kategori_var,
    values=KATEGORILER,
    state="readonly",
    width=22
).grid(row=1, column=1, padx=5)

tk.Label(real_frame, text="Açıklama").grid(row=0, column=2)
aciklama_entry = tk.Entry(real_frame, width=55)
aciklama_entry.grid(row=1, column=2, padx=5)

tk.Button(
    real_frame,
    text="GERÇEK KAYDI KAYDET",
    command=gercek_kayit_ekle,
    bg="#059669",
    fg="white"
).grid(row=1, column=3, padx=10)

listele()

def kapat():
    demo_con.close()
    real_con.close()
    root.destroy()

root.protocol("WM_DELETE_WINDOW", kapat)
root.mainloop()
