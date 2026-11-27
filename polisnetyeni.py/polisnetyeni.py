
# -*- coding: utf-8 -*-
"""
============================================================
POLİSNET - OLAY KAYIT VE ANALİZ PLATFORMU
Hazırlayan: Emirhan KARAASLAN
============================================================

KULLANIM AMACI:
Eğitim ve prototip amacıyla olay kayıtlarının yönetilmesi,
istatistiklerin incelenmesi, raporların oluşturulması,
veri kalitesinin kontrol edilmesi ve veritabanının
yedeklenmesi için geliştirilmiştir.

ÖNEMLİ:
Bu uygulama resmî bir polis sistemi değildir.
Demo kayıtları sentetiktir.
Gerçek kişisel veya operasyonel verileri kullanmayın.
Gerçek kullanım için kurum izni, güvenlik denetimi ve
hukuki değerlendirme gerekir.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import csv
import random
import secrets
import hashlib
import hmac
import threading
import queue
import shutil
from pathlib import Path
from datetime import datetime, timedelta


# ============================================================
# AYARLAR
# ============================================================

KLASOR = Path(__file__).resolve().parent
DB = KLASOR / "polisnet_veritabani.db"

DEMO_HEDEF = 1_000_000
PAKET = 5000

KATEGORILER = [
    "Kayıp Eşya",
    "Kayıp Cüzdan",
    "Kayıp Telefon",
    "Buluntu Eşya",
    "Trafik Olayı",
    "Trafik Kazası Bildirimi",
    "Gürültü Şikâyeti",
    "Çevre Şikâyeti",
    "Dolandırıcılık Bildirimi",
    "Hırsızlık Bildirimi",
    "Mala Zarar Bildirimi",
    "Kimlik/Kart Buluntusu",
    "Hayvan Kaybolması",
    "Genel Başvuru",
    "Diğer"
]

DURUMLAR = [
    "Yeni",
    "İnceleniyor",
    "İşlem Bekliyor",
    "Çözüldü",
    "Tamamlandı",
    "Kapalı"
]

BOLGELER = [
    "İstanbul / Kadıköy",
    "İstanbul / Üsküdar",
    "İstanbul / Ataşehir",
    "İstanbul / Ümraniye",
    "İstanbul / Maltepe",
    "İstanbul / Kartal",
    "Ankara / Çankaya",
    "İzmir / Konak",
    "Bursa / Nilüfer",
    "Antalya / Muratpaşa",
    "Eskişehir / Tepebaşı"
]

DEMO_ACIKLAMALARI = [
    "Eğitim amacıyla oluşturulmuş sentetik test kaydı.",
    "Gerçek kişi bilgisi içermeyen örnek kayıt.",
    "Demo veri seti kapsamında üretilmiş örnek açıklama.",
    "Yazılım testi için oluşturulmuş yapay kayıt."
]

KAPALI_DURUMLAR = (
    "çözüldü",
    "tamamlandı",
    "kapalı"
)


# ============================================================
# VERİTABANI
# ============================================================

def baglan():
    con = sqlite3.connect(DB, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    return con


def veritabani_hazirla():
    with baglan() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_no TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            location TEXT,
            status TEXT NOT NULL,
            source TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            action TEXT NOT NULL,
            reference TEXT,
            event_time TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_date
        ON incidents(created_at);

        CREATE INDEX IF NOT EXISTS idx_category
        ON incidents(category);

        CREATE INDEX IF NOT EXISTS idx_status
        ON incidents(status);

        CREATE INDEX IF NOT EXISTS idx_source
        ON incidents(source);
        """)


def parola_hashla(parola, salt=None):
    salt = salt or secrets.token_bytes(16)

    sonuc = hashlib.pbkdf2_hmac(
        "sha256",
        parola.encode("utf-8"),
        salt,
        240000
    )

    return salt.hex() + "$" + sonuc.hex()


def parola_dogrula(parola, kayit):
    try:
        salt, eski_hash = kayit.split("$", 1)

        yeni_hash = parola_hashla(
            parola,
            bytes.fromhex(salt)
        ).split("$", 1)[1]

        return hmac.compare_digest(yeni_hash, eski_hash)

    except Exception:
        return False


def islem_kaydet(kullanici, islem, referans=""):
    with baglan() as con:
        con.execute("""
            INSERT INTO audit_log
            (username, action, reference, event_time)
            VALUES (?, ?, ?, ?)
        """, (
            kullanici,
            islem,
            str(referans),
            datetime.now().isoformat(timespec="seconds")
        ))


def dosya_no_uret():
    return (
        "PN-"
        + datetime.now().strftime("%Y%m%d-%H%M%S")
        + "-"
        + secrets.token_hex(2).upper()
    )


# ============================================================
# ANA UYGULAMA
# ============================================================

class PolisNet:

    def __init__(self, root):

        self.root = root
        self.root.title(
            "POLİSNET | Olay Kayıt ve Analiz Platformu"
        )

        self.root.geometry("1300x850")
        self.root.minsize(1050, 700)
        self.root.configure(bg="#101827")

        self.kullanici = None
        self.rol = None
        self.secili_id = None

        self.kuyruk = queue.Queue()
        self.demo_calisiyor = False

        self.arama = tk.StringVar()
        self.kaynak = tk.StringVar(value="Tümü")
        self.filtre_durum = tk.StringVar(value="Tümü")

        self.kategori = tk.StringVar(value=KATEGORILER[0])
        self.durum = tk.StringVar(value=DURUMLAR[0])
        self.baslik = tk.StringVar()
        self.konum = tk.StringVar()
        self.aciklama = tk.StringVar()

        self.stil_ayarla()
        veritabani_hazirla()

        self.root.after(100, self.ilk_kontrol)

    # --------------------------------------------------------
    # ARAYÜZ STİLİ
    # --------------------------------------------------------

    def stil_ayarla(self):

        style = ttk.Style()

        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "TFrame",
            background="#101827"
        )

        style.configure(
            "Panel.TFrame",
            background="#1b293b"
        )

        style.configure(
            "TLabel",
            background="#101827",
            foreground="#e8eef7",
            font=("Segoe UI", 10)
        )

        style.configure(
            "Panel.TLabel",
            background="#1b293b",
            foreground="#ffffff"
        )

        style.configure(
            "Title.TLabel",
            background="#101827",
            foreground="#ffffff",
            font=("Segoe UI", 22, "bold")
        )

        style.configure(
            "TButton",
            font=("Segoe UI", 9, "bold"),
            padding=7
        )

        style.configure(
            "Treeview",
            rowheight=27,
            background="#f4f7fb",
            foreground="#182334",
            fieldbackground="#f4f7fb"
        )

        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 9, "bold")
        )

    # --------------------------------------------------------
    # İLK KURULUM
    # --------------------------------------------------------

    def ilk_kontrol(self):

        with baglan() as con:
            sayi = con.execute(
                "SELECT COUNT(*) FROM users"
            ).fetchone()[0]

        if sayi == 0:
            self.yonetici_olustur()
        else:
            self.giris_ekrani()

    def yonetici_olustur(self):

        win = tk.Toplevel(self.root)
        win.title("POLİSNET İlk Kurulum")
        win.geometry("420x340")
        win.configure(bg="#1b293b")
        win.grab_set()

        ttk.Label(
            win,
            text="İLK KURULUM",
            style="Title.TLabel"
        ).pack(pady=20)

        frame = ttk.Frame(
            win,
            style="Panel.TFrame",
            padding=20
        )
        frame.pack(fill="both", expand=True, padx=20)

        ttk.Label(
            frame,
            text="Yönetici kullanıcı adı",
            style="Panel.TLabel"
        ).pack(anchor="w")

        kullanici = ttk.Entry(frame)
        kullanici.pack(fill="x", pady=5)

        ttk.Label(
            frame,
            text="Parola (en az 8 karakter)",
            style="Panel.TLabel"
        ).pack(anchor="w")

        parola = ttk.Entry(frame, show="*")
        parola.pack(fill="x", pady=5)

        ttk.Label(
            frame,
            text="Parola tekrar",
            style="Panel.TLabel"
        ).pack(anchor="w")

        tekrar = ttk.Entry(frame, show="*")
        tekrar.pack(fill="x", pady=5)

        def kaydet():

            u = kullanici.get().strip()
            p = parola.get()

            if not u or len(p) < 8 or p != tekrar.get():
                messagebox.showerror(
                    "Hata",
                    "Kullanıcı adı girin. Parolalar aynı ve en az 8 karakter olmalı.",
                    parent=win
                )
                return

            try:
                with baglan() as con:
                    con.execute("""
                        INSERT INTO users
                        (username, password_hash, role, created_at)
                        VALUES (?, ?, ?, ?)
                    """, (
                        u,
                        parola_hashla(p),
                        "Yönetici",
                        datetime.now().isoformat(timespec="seconds")
                    ))

                win.destroy()
                self.giris_ekrani()

            except sqlite3.IntegrityError:
                messagebox.showerror(
                    "Hata",
                    "Bu kullanıcı adı zaten mevcut.",
                    parent=win
                )

        ttk.Button(
            frame,
            text="Yönetici hesabı oluştur",
            command=kaydet
        ).pack(fill="x", pady=12)

        self.root.wait_window(win)

    # --------------------------------------------------------
    # GİRİŞ
    # --------------------------------------------------------

    def giris_ekrani(self):

        win = tk.Toplevel(self.root)
        win.title("POLİSNET Giriş")
        win.geometry("390x280")
        win.configure(bg="#1b293b")
        win.grab_set()

        ttk.Label(
            win,
            text="POLİSNET",
            style="Title.TLabel"
        ).pack(pady=20)

        frame = ttk.Frame(
            win,
            style="Panel.TFrame",
            padding=20
        )
        frame.pack(fill="both", expand=True, padx=20)

        ttk.Label(
            frame,
            text="Kullanıcı adı",
            style="Panel.TLabel"
        ).pack(anchor="w")

        u = ttk.Entry(frame)
        u.pack(fill="x", pady=5)

        ttk.Label(
            frame,
            text="Parola",
            style="Panel.TLabel"
        ).pack(anchor="w")

        p = ttk.Entry(frame, show="*")
        p.pack(fill="x", pady=5)

        def giris():

            with baglan() as con:
                row = con.execute(
                    "SELECT * FROM users WHERE username=?",
                    (u.get().strip(),)
                ).fetchone()

            if row and parola_dogrula(
                p.get(),
                row["password_hash"]
            ):

                self.kullanici = row["username"]
                self.rol = row["role"]

                win.destroy()

                islem_kaydet(
                    self.kullanici,
                    "Oturum açtı"
                )

                self.arayuz_olustur()

            else:
                messagebox.showerror(
                    "Giriş başarısız",
                    "Kullanıcı adı veya parola hatalı.",
                    parent=win
                )

        ttk.Button(
            frame,
            text="Giriş yap",
            command=giris
        ).pack(fill="x", pady=10)

        p.bind("<Return>", lambda e: giris())

        self.root.wait_window(win)

    # --------------------------------------------------------
    # ANA ARAYÜZ
    # --------------------------------------------------------

    def arayuz_olustur(self):

        header = ttk.Frame(self.root, padding=18)
        header.pack(fill="x")

        ttk.Label(
            header,
            text="POLİSNET",
            style="Title.TLabel"
        ).pack(anchor="w")

        ttk.Label(
            header,
            text="OLAY KAYIT • ANALİZ • RAPORLAMA • VERİ YÖNETİMİ"
        ).pack(anchor="w")

        ttk.Label(
            header,
            text=f"Kullanıcı: {self.kullanici} | Rol: {self.rol}"
        ).pack(anchor="e")

        tk.Label(
            self.root,
            text="EĞİTİM / PROTOTİP UYGULAMASI — Resmî sistem değildir.",
            bg="#49351c",
            fg="#ffe0a3",
            font=("Segoe UI", 9, "bold"),
            pady=7
        ).pack(fill="x", padx=18)

        self.kartlar = ttk.Frame(
            self.root,
            padding=12
        )
        self.kartlar.pack(fill="x")

        self.kart_degerleri = {}

        for anahtar, baslik in [
            ("toplam", "TOPLAM KAYIT"),
            ("cozulen", "ÇÖZÜLEN"),
            ("acik", "AÇIK / BEKLEYEN"),
            ("oran", "ÇÖZÜM ORANI")
        ]:

            panel = ttk.Frame(
                self.kartlar,
                style="Panel.TFrame",
                padding=12
            )

            panel.pack(
                side="left",
                fill="x",
                expand=True,
                padx=5
            )

            ttk.Label(
                panel,
                text=baslik,
                style="Panel.TLabel"
            ).pack(anchor="w")

            deger = tk.Label(
                panel,
                text="0",
                bg="#1b293b",
                fg="white",
                font=("Segoe UI", 21, "bold")
            )

            deger.pack(anchor="w", pady=5)

            self.kart_degerleri[anahtar] = deger

        self.sekmeler = ttk.Notebook(self.root)
        self.sekmeler.pack(
            fill="both",
            expand=True,
            padx=18,
            pady=12
        )

        self.kayit_sekmesi = ttk.Frame(self.sekmeler)
        self.analiz_sekmesi = ttk.Frame(self.sekmeler)
        self.sistem_sekmesi = ttk.Frame(self.sekmeler)

        self.sekmeler.add(
            self.kayit_sekmesi,
            text="Kayıt Yönetimi"
        )

        self.sekmeler.add(
            self.analiz_sekmesi,
            text="Analiz Paneli"
        )

        self.sekmeler.add(
            self.sistem_sekmesi,
            text="Sistem Yönetimi"
        )

        self.kayit_sekmesi_olustur()
        self.analiz_sekmesi_olustur()
        self.sistem_sekmesi_olustur()

        self.yenile()

    # --------------------------------------------------------
    # KAYIT EKRANI
    # --------------------------------------------------------

    def kayit_sekmesi_olustur(self):

        ana = ttk.Frame(
            self.kayit_sekmesi,
            padding=10
        )
        ana.pack(fill="both", expand=True)

        form = ttk.LabelFrame(
            ana,
            text="Olay Kaydı",
            padding=10
        )
        form.pack(fill="x")

        satir = ttk.Frame(form)
        satir.pack(fill="x", pady=4)

        ttk.Label(satir, text="Kategori").pack(side="left")

        ttk.Combobox(
            satir,
            textvariable=self.kategori,
            values=KATEGORILER,
            state="readonly",
            width=25
        ).pack(side="left", padx=6)

        ttk.Label(satir, text="Durum").pack(
            side="left",
            padx=(15, 0)
        )

        ttk.Combobox(
            satir,
            textvariable=self.durum,
            values=DURUMLAR,
            state="readonly",
            width=20
        ).pack(side="left", padx=6)

        satir2 = ttk.Frame(form)
        satir2.pack(fill="x", pady=4)

        ttk.Label(satir2, text="Başlık").pack(side="left")

        ttk.Entry(
            satir2,
            textvariable=self.baslik
        ).pack(side="left", fill="x", expand=True, padx=6)

        ttk.Label(
            satir2,
            text="Konum etiketi"
        ).pack(side="left", padx=(12, 0))

        ttk.Entry(
            satir2,
            textvariable=self.konum,
            width=25
        ).pack(side="left", padx=6)

        satir3 = ttk.Frame(form)
        satir3.pack(fill="x", pady=4)

        ttk.Label(satir3, text="Açıklama").pack(side="left")

        ttk.Entry(
            satir3,
            textvariable=self.aciklama
        ).pack(side="left", fill="x", expand=True, padx=6)

        butonlar = ttk.Frame(form)
        butonlar.pack(fill="x", pady=8)

        ttk.Button(
            butonlar,
            text="Yeni kayıt oluştur",
            command=self.kayit_ekle
        ).pack(side="left", padx=3)

        ttk.Button(
            butonlar,
            text="Seçileni güncelle",
            command=self.kayit_guncelle
        ).pack(side="left", padx=3)

        ttk.Button(
            butonlar,
            text="Seçileni sil",
            command=self.kayit_sil
        ).pack(side="left", padx=3)

        ttk.Button(
            butonlar,
            text="Formu temizle",
            command=self.form_temizle
        ).pack(side="left", padx=3)

        filtre = ttk.Frame(ana)
        filtre.pack(fill="x", pady=8)

        ttk.Label(filtre, text="Arama").pack(side="left")

        arama = ttk.Entry(
            filtre,
            textvariable=self.arama,
            width=25
        )
        arama.pack(side="left", padx=5)
        arama.bind(
            "<KeyRelease>",
            lambda e: self.tablo_yenile()
        )

        ttk.Label(filtre, text="Kaynak").pack(
            side="left",
            padx=(10, 0)
        )

        kaynak = ttk.Combobox(
            filtre,
            textvariable=self.kaynak,
            values=["Tümü", "USER", "DEMO"],
            state="readonly",
            width=10
        )
        kaynak.pack(side="left", padx=5)
        kaynak.bind(
            "<<ComboboxSelected>>",
            lambda e: self.tablo_yenile()
        )

        ttk.Label(filtre, text="Durum").pack(
            side="left",
            padx=(10, 0)
        )

        durum = ttk.Combobox(
            filtre,
            textvariable=self.filtre_durum,
            values=["Tümü"] + DURUMLAR,
            state="readonly",
            width=16
        )
        durum.pack(side="left", padx=5)
        durum.bind(
            "<<ComboboxSelected>>",
            lambda e: self.tablo_yenile()
        )

        ttk.Button(
            filtre,
            text="CSV dışa aktar",
            command=self.csv_aktar
        ).pack(side="right")

        sutunlar = (
            "no",
            "tarih",
            "kategori",
            "baslik",
            "konum",
            "durum",
            "kaynak"
        )

        self.tablo = ttk.Treeview(
            ana,
            columns=sutunlar,
            show="headings",
            height=13
        )

        basliklar = {
            "no": "Dosya No",
            "tarih": "Tarih",
            "kategori": "Kategori",
            "baslik": "Başlık",
            "konum": "Konum",
            "durum": "Durum",
            "kaynak": "Kaynak"
        }

        for sutun in sutunlar:
            self.tablo.heading(
                sutun,
                text=basliklar[sutun]
            )

            self.tablo.column(
                sutun,
                width=150
            )

        scroll = ttk.Scrollbar(
            ana,
            orient="vertical",
            command=self.tablo.yview
        )

        self.tablo.configure(
            yscrollcommand=scroll.set
        )

        self.tablo.pack(
            side="left",
            fill="both",
            expand=True
        )

        scroll.pack(side="right", fill="y")

        self.tablo.bind(
            "<<TreeviewSelect>>",
            self.secim_degisti
        )

    # --------------------------------------------------------
    # KAYIT İŞLEMLERİ
    # --------------------------------------------------------

    def kayit_ekle(self):

        if not self.baslik.get().strip():
            messagebox.showwarning(
                "Eksik bilgi",
                "Başlık alanını doldurun."
            )
            return

        simdi = datetime.now().isoformat(
            timespec="seconds"
        )

        no = dosya_no_uret()

        with baglan() as con:
            con.execute("""
                INSERT INTO incidents
                (case_no, created_at, category, title,
                 description, location, status, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                no,
                simdi,
                self.kategori.get(),
                self.baslik.get().strip(),
                self.aciklama.get().strip(),
                self.konum.get().strip(),
                self.durum.get(),
                "USER",
                simdi
            ))

        islem_kaydet(
            self.kullanici,
            "Kayıt oluşturdu",
            no
        )

        self.form_temizle()
        self.yenile()

        messagebox.showinfo(
            "Tamamlandı",
            f"Kayıt oluşturuldu.\nDosya numarası: {no}"
        )

    def secim_degisti(self, event=None):

        secim = self.tablo.selection()

        if not secim:
            return

        no = self.tablo.item(
            secim[0],
            "values"
        )[0]

        with baglan() as con:
            row = con.execute(
                "SELECT * FROM incidents WHERE case_no=?",
                (no,)
            ).fetchone()

        if not row:
            return

        self.secili_id = row["id"]

        self.kategori.set(row["category"])
        self.durum.set(row["status"])
        self.baslik.set(row["title"])
        self.konum.set(row["location"] or "")
        self.aciklama.set(row["description"] or "")

    def kayit_guncelle(self):

        if not self.secili_id:
            messagebox.showwarning(
                "Seçim",
                "Önce bir kayıt seçin."
            )
            return

        if not self.baslik.get().strip():
            messagebox.showwarning(
                "Eksik bilgi",
                "Başlık boş bırakılamaz."
            )
            return

        with baglan() as con:
            row = con.execute(
                "SELECT * FROM incidents WHERE id=?",
                (self.secili_id,)
            ).fetchone()

            if not row:
                return

            if row["source"] == "DEMO":
                messagebox.showwarning(
                    "İşlem engellendi",
                    "Sentetik demo kayıtları bu ekrandan güncellenemez."
                )
                return

            con.execute("""
                UPDATE incidents
                SET category=?, title=?, description=?,
                    location=?, status=?, updated_at=?
                WHERE id=?
            """, (
                self.kategori.get(),
                self.baslik.get().strip(),
                self.aciklama.get().strip(),
                self.konum.get().strip(),
                self.durum.get(),
                datetime.now().isoformat(timespec="seconds"),
                self.secili_id
            ))

        islem_kaydet(
            self.kullanici,
            "Kayıt güncelledi",
            row["case_no"]
        )

        self.form_temizle()
        self.yenile()

    def kayit_sil(self):

        if not self.secili_id:
            messagebox.showwarning(
                "Seçim",
                "Önce bir kayıt seçin."
            )
            return

        with baglan() as con:
            row = con.execute(
                "SELECT * FROM incidents WHERE id=?",
                (self.secili_id,)
            ).fetchone()

        if not row:
            return

        if row["source"] == "DEMO" and self.rol != "Yönetici":
            messagebox.showwarning(
                "Yetki",
                "Demo kayıtlarını yalnızca yönetici silebilir."
            )
            return

        if not messagebox.askyesno(
            "Silme onayı",
            f"{row['case_no']} kaydı silinsin mi?"
        ):
            return

        with baglan() as con:
            con.execute(
                "DELETE FROM incidents WHERE id=?",
                (self.secili_id,)
            )

        islem_kaydet(
            self.kullanici,
            "Kayıt sildi",
            row["case_no"]
        )

        self.form_temizle()
        self.yenile()

    def form_temizle(self):

        self.secili_id = None

        self.kategori.set(KATEGORILER[0])
        self.durum.set(DURUMLAR[0])

        self.baslik.set("")
        self.konum.set("")
        self.aciklama.set("")

        if hasattr(self, "tablo"):
            for item in self.tablo.selection():
                self.tablo.selection_remove(item)

    # --------------------------------------------------------
    # TABLO VE FİLTRELEME
    # --------------------------------------------------------

    def tablo_yenile(self):

        if not hasattr(self, "tablo"):
            return

        for item in self.tablo.get_children():
            self.tablo.delete(item)

        sql = """
            SELECT case_no, created_at, category, title,
                   location, status, source
            FROM incidents
            WHERE 1=1
        """

        parametreler = []

        if self.kaynak.get() != "Tümü":
            sql += " AND source=?"
            parametreler.append(self.kaynak.get())

        if self.filtre_durum.get() != "Tümü":
            sql += " AND status=?"
            parametreler.append(self.filtre_durum.get())

        aranan = self.arama.get().strip()

        if aranan:
            like = "%" + aranan + "%"
            sql += """
                AND (
                    case_no LIKE ?
                    OR category LIKE ?
                    OR title LIKE ?
                    OR location LIKE ?
                    OR description LIKE ?
                )
            """
            parametreler.extend([like] * 5)

        sql += " ORDER BY id DESC LIMIT 1000"

        with baglan() as con:
            rows = con.execute(
                sql,
                parametreler
            ).fetchall()

        for row in rows:
            self.tablo.insert(
                "",
                "end",
                values=(
                    row["case_no"],
                    row["created_at"],
                    row["category"],
                    row["title"],
                    row["location"],
                    row["status"],
                    row["source"]
                )
            )

    # --------------------------------------------------------
    # İSTATİSTİKLER
    # --------------------------------------------------------

    def kartlari_yenile(self):

        with baglan() as con:

            toplam = con.execute(
                "SELECT COUNT(*) FROM incidents"
            ).fetchone()[0]

            cozulen = con.execute("""
                SELECT COUNT(*) FROM incidents
                WHERE lower(status) IN (?, ?, ?)
            """, KAPALI_DURUMLAR).fetchone()[0]

        acik = toplam - cozulen

        oran = (
            cozulen / toplam * 100
            if toplam else 0
        )

        self.kart_degerleri["toplam"].config(
            text=f"{toplam:,}"
        )

        self.kart_degerleri["cozulen"].config(
            text=f"{cozulen:,}"
        )

        self.kart_degerleri["acik"].config(
            text=f"{acik:,}"
        )

        self.kart_degerleri["oran"].config(
            text=f"%{oran:.1f}"
        )

    # --------------------------------------------------------
    # ANALİZ PANELİ
    # --------------------------------------------------------

    def analiz_sekmesi_olustur(self):

        frame = ttk.Frame(
            self.analiz_sekmesi,
            padding=12
        )

        frame.pack(fill="both", expand=True)

        butonlar = ttk.Frame(frame)
        butonlar.pack(fill="x")

        ttk.Button(
            butonlar,
            text="Analizi yenile",
            command=self.analiz_yenile
        ).pack(side="left", padx=4)

        ttk.Button(
            butonlar,
            text="PDF raporu",
            command=self.pdf_aktar
        ).pack(side="left", padx=4)

        ttk.Button(
            butonlar,
            text="Excel raporu",
            command=self.excel_aktar
        ).pack(side="left", padx=4)

        ttk.Button(
            butonlar,
            text="Harita HTML oluştur",
            command=self.harita_olustur
        ).pack(side="left", padx=4)

        self.analiz_bilgi = ttk.Label(
            frame,
            text="Analiz bekleniyor..."
        )

        self.analiz_bilgi.pack(
            anchor="w",
            pady=10
        )

        self.grafik = tk.Canvas(
            frame,
            bg="#1b293b",
            highlightthickness=0
        )

        self.grafik.pack(
            fill="both",
            expand=True
        )

        self.grafik.bind(
            "<Configure>",
            lambda e: self.analiz_yenile()
        )

    def analiz_yenile(self):

        if not hasattr(self, "grafik"):
            return

        with baglan() as con:

            toplam = con.execute(
                "SELECT COUNT(*) FROM incidents"
            ).fetchone()[0]

            kategoriler = con.execute("""
                SELECT category, COUNT(*) AS adet
                FROM incidents
                GROUP BY category
                ORDER BY adet DESC
                LIMIT 12
            """).fetchall()

            durumlar = con.execute("""
                SELECT status, COUNT(*) AS adet
                FROM incidents
                GROUP BY status
                ORDER BY adet DESC
            """).fetchall()

            bolgeler = con.execute("""
                SELECT
                    COALESCE(NULLIF(location,''),'Belirtilmemiş') AS bolge,
                    COUNT(*) AS adet
                FROM incidents
                GROUP BY bolge
                ORDER BY adet DESC
                LIMIT 8
            """).fetchall()

            gunluk = con.execute("""
                SELECT substr(created_at,1,10) AS gun,
                       COUNT(*) AS adet
                FROM incidents
                WHERE created_at >= ?
                GROUP BY gun
                ORDER BY gun
            """, (
                (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d"),
            )).fetchall()

            aylik = con.execute("""
                SELECT substr(created_at,1,7) AS ay,
                       COUNT(*) AS adet
                FROM incidents
                GROUP BY ay
                ORDER BY ay DESC
                LIMIT 6
            """).fetchall()

            demo = con.execute(
                "SELECT COUNT(*) FROM incidents WHERE source='DEMO'"
            ).fetchone()[0]

            kullanici = con.execute(
                "SELECT COUNT(*) FROM incidents WHERE source='USER'"
            ).fetchone()[0]

        self.analiz_bilgi.config(
            text=(
                f"Toplam: {toplam:,} | "
                f"Kullanıcı kayıtları: {kullanici:,} | "
                f"Sentetik demo kayıtları: {demo:,}"
            )
        )

        self.grafik.delete("all")

        w = max(self.grafik.winfo_width(), 750)

        self.grafik.create_text(
            20, 20,
            text="KATEGORİ DAĞILIMI",
            anchor="w",
            fill="white",
            font=("Segoe UI", 12, "bold")
        )

        en_yuksek = max(
            [r["adet"] for r in kategoriler],
            default=1
        )

        y = 55

        for row in kategoriler:

            self.grafik.create_text(
                20, y + 8,
                text=row["category"][:24],
                anchor="w",
                fill="#dce7f5"
            )

            x0 = 210

            x1 = x0 + int(
                (w * 0.42) * row["adet"] / en_yuksek
            )

            self.grafik.create_rectangle(
                x0, y, x1, y + 17,
                fill="#3d8bfd",
                outline=""
            )

            self.grafik.create_text(
                x1 + 8, y + 8,
                text=f"{row['adet']:,}",
                anchor="w",
                fill="white"
            )

            y += 28

        sag = int(w * 0.63)

        self.grafik.create_text(
            sag, 20,
            text="DURUM DAĞILIMI",
            anchor="w",
            fill="white",
            font=("Segoe UI", 12, "bold")
        )

        yy = 55

        for row in durumlar:

            self.grafik.create_text(
                sag, yy,
                text=row["status"],
                anchor="w",
                fill="#dce7f5"
            )

            self.grafik.create_text(
                w - 25, yy,
                text=f"{row['adet']:,}",
                anchor="e",
                fill="white"
            )

            yy += 28

        yy = max(y + 15, 360)

        self.grafik.create_text(
            20, yy,
            text="BÖLGE DAĞILIMI",
            anchor="w",
            fill="white",
            font=("Segoe UI", 11, "bold")
        )

        yy += 25

        for row in bolgeler:

            self.grafik.create_text(
                20, yy,
                text=f"{row['bolge']} - {row['adet']:,} kayıt",
                anchor="w",
                fill="#c7d5e8"
            )

            yy += 22

        yy += 10

        self.grafik.create_text(
            20, yy,
            text="SON 7 GÜN",
            anchor="w",
            fill="white",
            font=("Segoe UI", 11, "bold")
        )

        yy += 23

        for row in gunluk:
            self.grafik.create_text(
                20, yy,
                text=f"{row['gun']} : {row['adet']:,}",
                anchor="w",
                fill="#c7d5e8"
            )
            yy += 20

        yy += 8

        self.grafik.create_text(
            330, y + 15,
            text="SON 6 AY",
            anchor="w",
            fill="white",
            font=("Segoe UI", 11, "bold")
        )

        yy = y + 40

        for row in aylik:
            self.grafik.create_text(
                330, yy,
                text=f"{row['ay']} : {row['adet']:,}",
                anchor="w",
                fill="#c7d5e8"
            )
            yy += 20

    # --------------------------------------------------------
    # HARİTA HTML
    # --------------------------------------------------------

    def harita_olustur(self):

        try:
            import folium
        except ImportError:
            messagebox.showwarning(
                "Eksik paket",
                "Harita özelliği için:\n"
                "python -m pip install folium"
            )
            return

        # Yaklaşık ilçe merkezleri; yalnızca örnek harita gösterimi.
        koordinatlar = {
            "Kadıköy": (40.990, 29.030),
            "Üsküdar": (41.025, 29.015),
            "Ataşehir": (40.992, 29.125),
            "Ümraniye": (41.025, 29.100),
            "Maltepe": (40.935, 29.155),
            "Kartal": (40.890, 29.190),
            "Çankaya": (39.900, 32.860),
            "Konak": (38.420, 27.130),
            "Nilüfer": (40.215, 28.980),
            "Muratpaşa": (36.885, 30.705),
            "Tepebaşı": (39.780, 30.510)
        }

        harita = folium.Map(
            location=[39.0, 休],
            zoom_start=6
        )

        with baglan() as con:
            rows = con.execute("""
                SELECT location, COUNT(*) AS adet
                FROM incidents
                WHERE source='DEMO'
                GROUP BY location
            """).fetchall()

        for row in rows:

            konum = row["location"]

            for ilce, koordinat in koordinatlar.items():

                if ilce.lower() in konum.lower():

                    folium.CircleMarker(
                        location=koordinat,
                        radius=min(8 + row["adet"] ** 0.5, 22),
                        popup=f"{konum}: {row['adet']} demo kayıt",
                        color="#2878d0",
                        fill=True
                    ).add_to(harita)

                    break

        path = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML", "*.html")],
            initialfile="polisnet_harita.html"
        )

        if not path:
            return

        harita.save(path)

        messagebox.showinfo(
            "Tamamlandı",
            "Sentetik demo kayıtları için harita oluşturuldu."
        )

    # --------------------------------------------------------
    # CSV
    # --------------------------------------------------------

    def csv_aktar(self):

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="polisnet_kayitlari.csv"
        )

        if not path:
            return

        with baglan() as con:
            cur = con.execute("""
                SELECT case_no, created_at, category, title,
                       description, location, status, source
                FROM incidents
                ORDER BY id
            """)

            with open(
                path,
                "w",
                newline="",
                encoding="utf-8-sig"
            ) as file:

                writer = csv.writer(
                    file,
                    delimiter=";"
                )

                writer.writerow([
                    "Dosya No",
                    "Tarih",
                    "Kategori",
                    "Başlık",
                    "Açıklama",
                    "Konum",
                    "Durum",
                    "Kaynak"
                ])

                while True:

                    rows = cur.fetchmany(5000)

                    if not rows:
                        break

                    writer.writerows([
                        tuple(row)
                        for row in rows
                    ])

        islem_kaydet(
            self.kullanici,
            "CSV dışa aktardı",
            path
        )

        messagebox.showinfo(
            "Tamamlandı",
            "CSV dosyası oluşturuldu."
        )

    # --------------------------------------------------------
    # EXCEL
    # --------------------------------------------------------

    def excel_aktar(self):

        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill
        except ImportError:
            messagebox.showwarning(
                "Eksik paket",
                "Excel için:\npython -m pip install openpyxl"
            )
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile="polisnet_rapor.xlsx"
        )

        if not path:
            return

        wb = Workbook()
        ws = wb.active
        ws.title = "Olay Kayıtları"

        ws.append([
            "Dosya No",
            "Tarih",
            "Kategori",
            "Başlık",
            "Açıklama",
            "Konum",
            "Durum",
            "Kaynak"
        ])

        for cell in ws[1]:
            cell.font = Font(
                bold=True,
                color="FFFFFF"
            )

            cell.fill = PatternFill(
                "solid",
                fgColor="20344F"
            )

        with baglan() as con:

            cur = con.execute("""
                SELECT case_no, created_at, category, title,
                       description, location, status, source
                FROM incidents
                ORDER BY id
            """)

            while True:

                rows = cur.fetchmany(5000)

                if not rows:
                    break

                for row in rows:
                    ws.append(list(row))

        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

        for column in ws.columns:

            letter = column[0].column_letter

            width = max(
                len(str(cell.value or ""))
                for cell in column
            )

            ws.column_dimensions[letter].width = min(
                max(width + 2, 12),
                40
            )

        wb.save(path)

        islem_kaydet(
            self.kullanici,
            "Excel raporu oluşturdu",
            path
        )

        messagebox.showinfo(
            "Tamamlandı",
            "Excel raporu oluşturuldu."
        )

    # --------------------------------------------------------
    # PDF
    # --------------------------------------------------------

    def pdf_aktar(self):

        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
        except ImportError:
            messagebox.showwarning(
                "Eksik paket",
                "PDF için:\npython -m pip install reportlab"
            )
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile="polisnet_rapor.pdf"
        )

        if not path:
            return

        with baglan() as con:

            toplam = con.execute(
                "SELECT COUNT(*) FROM incidents"
            ).fetchone()[0]

            kategoriler = con.execute("""
                SELECT category, COUNT(*) AS adet
                FROM incidents
                GROUP BY category
                ORDER BY adet DESC
            """).fetchall()

            durumlar = con.execute("""
                SELECT status, COUNT(*) AS adet
                FROM incidents
                GROUP BY status
                ORDER BY adet DESC
            """).fetchall()

        c = canvas.Canvas(
            path,
            pagesize=A4
        )

        width, height = A4
        y = height - 55

        c.setFont("Helvetica-Bold", 18)
        c.drawString(
            45,
            y,
            "POLISNET - Olay Analiz Raporu"
        )

        y -= 30

        c.setFont("Helvetica", 10)
        c.drawString(
            45,
            y,
            "Egitim ve prototip raporudur. Resmi belge degildir."
        )

        y -= 25

        c.drawString(
            45,
            y,
            f"Rapor tarihi: {datetime.now():%d.%m.%Y %H:%M}"
        )

        y -= 22

        c.drawString(
            45,
            y,
            f"Toplam kayıt: {toplam:,}"
        )

        y -= 35

        c.setFont("Helvetica-Bold", 12)
        c.drawString(
            45,
            y,
            "Kategori dağılımı"
        )

        y -= 22
        c.setFont("Helvetica", 10)

        for row in kategoriler:

            if y < 60:
                c.showPage()
                y = height - 55
                c.setFont("Helvetica", 10)

            c.drawString(
                55,
                y,
                f"{row['category']}: {row['adet']:,}"
            )

            y -= 17

        y -= 15

        c.setFont("Helvetica-Bold", 12)
        c.drawString(
            45,
            y,
            "Durum dağılımı"
        )

        y -= 22
        c.setFont("Helvetica", 10)

        for row in durumlar:

            if y < 60:
                c.showPage()
                y = height - 55
                c.setFont("Helvetica", 10)

            c.drawString(
                55,
                y,
                f"{row['status']}: {row['adet']:,}"
            )

            y -= 17

        c.save()

        islem_kaydet(
            self.kullanici,
            "PDF raporu oluşturdu",
            path
        )

        messagebox.showinfo(
            "Tamamlandı",
            "PDF raporu oluşturuldu."
        )

    # --------------------------------------------------------
    # DEMO VERİ ÜRETİMİ
    # --------------------------------------------------------

    def demo_baslat(self):

        if self.rol != "Yönetici":
            messagebox.showwarning(
                "Yetki",
                "Demo veri üretimi yöneticiye açıktır."
            )
            return

        if self.demo_calisiyor:
            return

        with baglan() as con:
            mevcut = con.execute("""
                SELECT COUNT(*) FROM incidents
                WHERE source='DEMO'
            """).fetchone()[0]

        kalan = max(
            0,
            DEMO_HEDEF - mevcut
        )

        if kalan == 0:
            messagebox.showinfo(
                "Bilgi",
                "Zaten 1 milyon demo kayıt bulunuyor."
            )
            return

        if not messagebox.askyesno(
            "Demo veri üretimi",
            f"{kalan:,} sentetik kayıt üretilecek.\n"
            "Bu işlem bilgisayarınıza yük bindirebilir.\n"
            "Devam edilsin mi?"
        ):
            return

        self.demo_calisiyor = True

        pencere = tk.Toplevel(self.root)
        pencere.title("Demo veri üretimi")
        pencere.geometry("430x160")
        pencere.transient(self.root)

        ttk.Label(
            pencere,
            text="Sentetik kayıtlar oluşturuluyor..."
        ).pack(pady=15)

        bar = ttk.Progressbar(
            pencere,
            maximum=kalan,
            length=380
        )

        bar.pack(pady=5)

        bilgi = ttk.Label(
            pencere,
            text="Başlatılıyor..."
        )

        bilgi.pack(pady=5)

        def isci():

            eklenen = 0

            try:

                with baglan() as con:

                    paket = []

                    for i in range(kalan):

                        tarih = (
                            datetime.now()
                            - timedelta(
                                days=random.randint(0, 730),
                                minutes=random.randint(0, 1440)
                            )
                        )

                        paket.append((
                            "DM-" + secrets.token_hex(7).upper(),
                            tarih.isoformat(timespec="seconds"),
                            random.choice(KATEGORILER),
                            random.choice([
                                "Kayıp eşya bildirimi",
                                "Buluntu eşya kaydı",
                                "Genel başvuru",
                                "Trafik olayı bildirimi",
                                "Çevre bildirimi"
                            ]),
                            random.choice(DEMO_ACIKLAMALARI),
                            random.choice(BOLGELER),
                            random.choice(DURUMLAR),
                            "DEMO",
                            datetime.now().isoformat(timespec="seconds")
                        ))

                        if len(paket) >= PAKET:

                            con.executemany("""
                                INSERT INTO incidents
                                (case_no, created_at, category, title,
                                 description, location, status, source, updated_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, paket)

                            con.commit()

                            eklenen += len(paket)
                            paket.clear()

                            self.kuyruk.put(
                                ("ilerleme", eklenen)
                            )

                    if paket:

                        con.executemany("""
                            INSERT INTO incidents
                            (case_no, created_at, category, title,
                             description, location, status, source, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, paket)

                        con.commit()
                        eklenen += len(paket)

                self.kuyruk.put(
                    ("bitti", eklenen)
                )

            except Exception as hata:

                self.kuyruk.put(
                    ("hata", str(hata))
                )

        threading.Thread(
            target=isci,
            daemon=True
        ).start()

        def kontrol():

            try:

                while True:

                    mesaj = self.kuyruk.get_nowait()

                    if mesaj[0] == "ilerleme":

                        bar["value"] = mesaj[1]

                        bilgi.config(
                            text=f"{mesaj[1]:,} / {kalan:,}"
                        )

                    elif mesaj[0] == "bitti":

                        self.demo_calisiyor = False
                        pencere.destroy()

                        islem_kaydet(
                            self.kullanici,
                            "Sentetik demo veri üretti",
                            mesaj[1]
                        )

                        self.yenile()

                        messagebox.showinfo(
                            "Tamamlandı",
                            f"{mesaj[1]:,} sentetik kayıt eklendi."
                        )

                        return

                    elif mesaj[0] == "hata":

                        self.demo_calisiyor = False
                        pencere.destroy()

                        messagebox.showerror(
                            "Hata",
                            mesaj[1]
                        )

                        return

            except queue.Empty:
                pass

            if self.demo_calisiyor:
                self.root.after(150, kontrol)

        self.root.after(150, kontrol)

    # --------------------------------------------------------
    # YEDEKLEME
    # --------------------------------------------------------

    def yedek_al(self):

        path = filedialog.asksaveasfilename(
            defaultextension=".db",
            filetypes=[("SQLite", "*.db")],
            initialfile="polisnet_yedek.db"
        )

        if not path:
            return

        try:

            with baglan() as kaynak:
                with sqlite3.connect(path) as hedef:
                    kaynak.backup(hedef)

            islem_kaydet(
                self.kullanici,
                "Veritabanı yedekledi",
                path
            )

            messagebox.showinfo(
                "Tamamlandı",
                "Veritabanı yedeklendi."
            )

        except Exception as hata:

            messagebox.showerror(
                "Yedekleme hatası",
                str(hata)
            )

    def yedek_yukle(self):

        if self.rol != "Yönetici":
            messagebox.showwarning(
                "Yetki",
                "Yalnızca yönetici yedek yükleyebilir."
            )
            return

        path = filedialog.askopenfilename(
            filetypes=[("SQLite", "*.db")]
        )

        if not path:
            return

        if not messagebox.askyesno(
            "Dikkat",
            "Mevcut veritabanı seçilen dosyayla değiştirilecek. "
            "Önce mevcut verilerin yedeğini aldığınızdan emin olun. Devam?"
        ):
            return

        try:

            with sqlite3.connect(path) as test:
                sonuc = test.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='incidents'
                """).fetchone()

            if not sonuc:
                raise ValueError(
                    "Bu dosyada POLİSNET kayıt tablosu bulunamadı."
                )

            shutil.copy2(path, DB)

            messagebox.showinfo(
                "Tamamlandı",
                "Yedek yüklendi. Programı yeniden başlatın."
            )

        except Exception as hata:

            messagebox.showerror(
                "Hata",
                str(hata)
            )

    # --------------------------------------------------------
    # İŞLEM GEÇMİŞİ
    # --------------------------------------------------------

    def islem_gecmisi(self):

        pencere = tk.Toplevel(self.root)
        pencere.title("İşlem Geçmişi")
        pencere.geometry("850x450")

        sutunlar = (
            "tarih",
            "kullanici",
            "islem",
            "referans"
        )

        tablo = ttk.Treeview(
            pencere,
            columns=sutunlar,
            show="headings"
        )

        for sutun, baslik, genislik in [
            ("tarih", "Tarih", 170),
            ("kullanici", "Kullanıcı", 130),
            ("islem", "İşlem", 220),
            ("referans", "Referans", 300)
        ]:

            tablo.heading(
                sutun,
                text=baslik
            )

            tablo.column(
                sutun,
                width=genislik
            )

        tablo.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=10
        )

        with baglan() as con:

            rows = con.execute("""
                SELECT event_time, username, action, reference
                FROM audit_log
                ORDER BY id DESC
                LIMIT 2000
            """).fetchall()

        for row in rows:
            tablo.insert(
                "",
                "end",
                values=tuple(row)
            )

    # --------------------------------------------------------
    # KULLANICI YÖNETİMİ
    # --------------------------------------------------------

    def kullanici_olustur(self):

        if self.rol != "Yönetici":
            messagebox.showwarning(
                "Yetki",
                "Kullanıcı oluşturma yalnızca yöneticiye açıktır."
            )
            return

        pencere = tk.Toplevel(self.root)
        pencere.title("Yeni Kullanıcı")
        pencere.geometry("360x280")

        frame = ttk.Frame(
            pencere,
            padding=18
        )

        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text="Kullanıcı adı"
        ).pack(anchor="w")

        u = ttk.Entry(frame)
        u.pack(fill="x", pady=5)

        ttk.Label(
            frame,
            text="Parola (en az 8 karakter)"
        ).pack(anchor="w")

        p = ttk.Entry(
            frame,
            show="*"
        )

        p.pack(fill="x", pady=5)

        ttk.Label(
            frame,
            text="Rol"
        ).pack(anchor="w")

        rol = ttk.Combobox(
            frame,
            values=[
                "Kayıt Personeli",
                "Rapor Görüntüleyici"
            ],
            state="readonly"
        )

        rol.current(0)
        rol.pack(fill="x", pady=5)

        def kaydet():

            if not u.get().strip() or len(p.get()) < 8:
                messagebox.showerror(
                    "Hata",
                    "Kullanıcı adı girin ve en az 8 karakterli parola kullanın.",
                    parent=pencere
                )
                return

            try:

                with baglan() as con:
                    con.execute("""
                        INSERT INTO users
                        (username, password_hash, role, created_at)
                        VALUES (?, ?, ?, ?)
                    """, (
                        u.get().strip(),
                        parola_hashla(p.get()),
                        rol.get(),
                        datetime.now().isoformat(timespec="seconds")
                    ))

                islem_kaydet(
                    self.kullanici,
                    "Kullanıcı oluşturdu",
                    u.get().strip()
                )

                pencere.destroy()

                messagebox.showinfo(
                    "Tamamlandı",
                    "Kullanıcı oluşturuldu."
                )

            except sqlite3.IntegrityError:

                messagebox.showerror(
                    "Hata",
                    "Bu kullanıcı adı zaten kullanılıyor.",
                    parent=pencere
                )

        ttk.Button(
            frame,
            text="Kullanıcı oluştur",
            command=kaydet
        ).pack(fill="x", pady=10)

    # --------------------------------------------------------
    # SİSTEM SEKMESİ
    # --------------------------------------------------------

    def sistem_sekmesi_olustur(self):

        frame = ttk.Frame(
            self.sistem_sekmesi,
            padding=20
        )

        frame.pack(
            fill="both",
            expand=True
        )

        ttk.Label(
            frame,
            text="SİSTEM YÖNETİMİ",
            style="Title.TLabel"
        ).pack(anchor="w", pady=(0, 12))

        ttk.Label(
            frame,
            text=(
                "Demo kayıtları sentetiktir ve kullanıcı kayıtlarından "
                "ayrı kaynak etiketiyle tutulur."
            )
        ).pack(anchor="w", pady=5)

        ttk.Button(
            frame,
            text="1.000.000 sentetik demo kaydına tamamla",
            command=self.demo_baslat
        ).pack(anchor="w", pady=7)

        ttk.Button(
            frame,
            text="Veritabanını yedekle",
            command=self.yedek_al
        ).pack(anchor="w", pady=7)

        ttk.Button(
            frame,
            text="Yedekten geri yükle",
            command=self.yedek_yukle
        ).pack(anchor="w", pady=7)

        ttk.Button(
            frame,
            text="İşlem geçmişini görüntüle",
            command=self.islem_gecmisi
        ).pack(anchor="w", pady=7)

        ttk.Button(
            frame,
            text="Yeni kullanıcı oluştur",
            command=self.kullanici_olustur
        ).pack(anchor="w", pady=7)

        ttk.Label(
            frame,
            text=(
                "Not: Bu prototip canlı kişi sorgulaması, "
                "kişisel profil çıkarma veya resmî kurum bağlantısı içermez."
            )
        ).pack(anchor="w", pady=15)

    # --------------------------------------------------------
    # GENEL YENİLEME
    # --------------------------------------------------------

    def yenile(self):

        self.kartlari_yenile()
        self.tablo_yenile()

        if hasattr(self, "grafik"):
            self.analiz_yenile()


# ============================================================
# PROGRAMI BAŞLAT
# ============================================================

if __name__ == "__main__":

    root = tk.Tk()
    root.withdraw()

    uygulama = PolisNet(root)

    root.deiconify()
    root.mainloop()
