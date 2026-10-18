import phonenumbers
import json

with open("türkiye_il_plakakodlari.json", "r", encoding="utf-8") as f:
    plakakodlari = json.load(f)

def get_city_from_number(phone_number):
    try:
        number = phonenumbers.parse(phone_number, "TR")
    except phonenumbers.NumberParseException:
        return "Geçersiz numara"

    if not phonenumbers.is_possible_number(number):
        return "Geçersiz numara"

    national_number = str(number.national_number)
    gsm_code = national_number[:3]
    plaka_kodu = gsm_code[:2]

    city = plakakodlari.get(plaka_kodu.zfill(2), "Bilinmeyen Şehir")
    return f"{city} (Tahmini Plaka Kodu: {plaka_kodu}) - GSM Kod: {gsm_code}"
