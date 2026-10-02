"""Bot Telegram: contrataciones <= 8 UIT (SEACE), Bienes, Vigentes,
publicadas hoy (hora de Lima), filtradas por palabras clave de ferretería/EPP."""
import html
import json
import os
import re
import time
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from keywords import KEYWORDS

API = "https://prod6.seace.gob.pe/v1/s8uit-services/buscadorpublico/contrataciones/buscador"
WEB = "https://prod6.seace.gob.pe/buscador-publico/contrataciones"
TZ = ZoneInfo("America/Lima")
PAGE_SIZE = 50
MAX_PAGES = 40
SEEN_FILE = Path(__file__).with_name("seen_ferreteria.json")
TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
NOTIFY_EMPTY = os.getenv("NOTIFY_EMPTY", "0") == "1"
URGENTE_HORAS = float(os.getenv("URGENTE_HORAS", "6"))
# Cada corrida revisa desde la corrida exitosa anterior (menos un margen de seguridad),
# así cubre todo el tramo entre corridas, incluida la noche, aunque GitHub retrase o salte una.
MARGEN_MIN = int(os.getenv("MARGEN_MIN", "60"))
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "1"))  # solo para la primera vez
MAX_DIAS_ATRAS = 3

HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "es-PE,es;q=0.9",
    "Referer": WEB,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36",
}


def norm(t: str) -> str:
    t = unicodedata.normalize("NFD", (t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _patron(k: str) -> re.Pattern:
    palabras = [re.escape(w) + r"(?:s|es)?" for w in norm(k).split()]
    return re.compile(r"\b" + r"\s+".join(palabras) + r"\b")


PATTERNS = [(k, _patron(k)) for k in KEYWORDS]


def coincidencias(texto: str) -> list[str]:
    n = norm(texto)
    return [k for k, p in PATTERNS if p.search(n)]


def parse_fecha(s: str) -> datetime:
    return datetime.strptime(s, "%d/%m/%Y %H:%M:%S").replace(tzinfo=TZ)


def get_json(session, params, intentos=4):
    for i in range(intentos):
        try:
            r = session.get(API, params=params, headers=HEADERS, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if i == intentos - 1:
                raise
            time.sleep(2 ** i)


def traer_publicados(desde: datetime) -> list[dict]:
    """Pagina (orden=2: más recientes primero) hasta pasar la fecha 'desde'."""
    session = requests.Session()
    anio = datetime.now(TZ).year
    items = []
    for page in range(1, MAX_PAGES + 1):
        data = get_json(session, {
            "anio": anio, "lista_codigo_objeto": 1, "palabra_clave": "",
            "orden": 2, "page": page, "page_size": PAGE_SIZE,
        })
        rows = data.get("data") or []
        if not rows:
            break
        hay_recientes = False
        for it in rows:
            try:
                pub = parse_fecha(it["fecPublica"])
            except Exception:
                continue
            if pub >= desde:
                hay_recientes = True
                items.append(it)
        if not hay_recientes:  # toda la página es anterior: se acabó el día
            break
    return items


def enviar(texto: str):
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": texto[:4000], "parse_mode": "HTML",
              "disable_web_page_preview": True},
        timeout=30,
    )
    r.raise_for_status()
    time.sleep(0.6)


def tiempo_restante(it: dict):
    try:
        return (parse_fecha(it["fecFinCotizacion"]) - datetime.now(TZ)).total_seconds() / 3600
    except Exception:
        return None


def formatear(it: dict, palabras: list[str]) -> str:
    e = html.escape
    h = tiempo_restante(it)
    if h is None:
        plazo, marca = "", "🔧"
    elif h <= 0:
        plazo, marca = "\n⏳ Plazo vencido", "🔧"
    else:
        txt = f"{int(h)} h {int((h % 1) * 60)} min"
        plazo = f"\n⏳ Quedan <b>{txt}</b> para cotizar"
        marca = "🚨 URGENTE" if h <= URGENTE_HORAS else "🔧"
    return (
        f"{marca} <b>{e(it['desContratacion'])}</b>\n"
        f"🏛 {e(it['nomEntidad'])}\n"
        f"📦 {e(it['desObjetoContrato'])}\n"
        f"📅 Publicado: {e(it['fecPublica'])}\n"
        f"⏰ Cotizar: {e(it['fecIniCotizacion'])} → {e(it['fecFinCotizacion'])}"
        f"{plazo}\n"
        f"🔎 Coincide: {e(', '.join(palabras))}\n"
        f"🔗 <a href=\"{WEB}\">Abrir buscador SEACE</a> (ID {it['idContrato']})"
    )


def guardar_vistos(seen: dict):
    SEEN_FILE.write_text(json.dumps(seen, ensure_ascii=False, indent=1))


def main():
    ahora = datetime.now(TZ)
    inicio_hoy = ahora.replace(hour=0, minute=0, second=0, microsecond=0)

    seen = json.loads(SEEN_FILE.read_text()) if SEEN_FILE.exists() else {}
    limite = (ahora - timedelta(days=MAX_DIAS_ATRAS + 10)).strftime("%Y-%m-%d")
    seen = {k: v for k, v in seen.items() if k.startswith("_") or v >= limite}

    if seen.get("_last_run"):
        desde = datetime.fromisoformat(seen["_last_run"]) - timedelta(minutes=MARGEN_MIN)
    else:  # primera vez
        desde = inicio_hoy - timedelta(days=LOOKBACK_DAYS)
    desde = max(desde, inicio_hoy - timedelta(days=MAX_DIAS_ATRAS))

    todos = traer_publicados(desde)
    vigentes = [i for i in todos if i.get("nomEstadoContrato") == "Vigente"
                and i.get("nomObjetoContrato") == "Bien"]

    pendientes, enviados = [], 0
    for it in vigentes:
        pid = str(it["idContrato"])
        if pid in seen:
            continue
        palabras = coincidencias(it.get("desObjetoContrato", ""))
        if palabras:
            pendientes.append((it, palabras))
        else:
            seen[pid] = ahora.strftime("%Y-%m-%d")  # revisado, no es de tu rubro

    hora = ahora.strftime("%H:%M")
    if pendientes:
        # lo que vence antes se envía primero
        pendientes.sort(key=lambda x: parse_fecha(x[0]["fecFinCotizacion"]))
        enviar(f"📢 <b>Ferretería/EPP</b> — {len(pendientes)} nueva(s) a las {hora}")
        for it, palabras in pendientes:
            enviar(formatear(it, palabras))
            # se marca como visto SOLO después de enviarlo con éxito
            seen[str(it["idContrato"])] = ahora.strftime("%Y-%m-%d")
            guardar_vistos(seen)
            enviados += 1
    elif NOTIFY_EMPTY:
        enviar(f"Sin novedades de ferretería/EPP a las {hora} "
               f"({len(vigentes)} bienes vigentes revisados).")

    # Aviso diario (una vez, en la primera corrida del día) para saber que el bot sigue vivo
    hoy = ahora.strftime("%Y-%m-%d")
    if ahora.hour >= 8 and seen.get("_heartbeat") != hoy:
        enviar(f"✅ Bot ferretería/EPP activo — {hoy}. Revisa a las 12:00, 17:00 y 21:00.")
        seen["_heartbeat"] = hoy

    seen["_last_run"] = ahora.isoformat()  # solo si todo salió bien
    guardar_vistos(seen)


def run():
    try:
        main()
    except Exception as e:
        try:
            enviar(f"⚠️ El bot de ferretería/EPP falló: {html.escape(str(e))[:300]}")
        except Exception:
            pass
        raise


if __name__ == "__main__":
    run()
