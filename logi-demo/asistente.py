"""
Asistente de Soporte LogRoot (chatbot) para la demo de LOGI.

Se engancha a la app con:
    import asistente
    asistente.registrar(app, db)

Rutas que añade:
    /asistente                       Página de demo con el chat (vista de cliente)
    /informes/asistente              Conversaciones y valoraciones (vista interna de Soporte)
    GET  /api/asistente/arbol        Árbol de botones (rol → categoría → pregunta)
    GET  /api/asistente/respuesta/<id>  Respuesta fija de una pregunta del árbol
    POST /api/asistente/chat         Pregunta en texto libre
    POST /api/asistente/valoracion   "¿Te ha servido?" Sí / No

Todo sale de dos archivos que se editan sin tocar código:
    conocimiento/base_conocimiento.md   Preguntas y respuestas
    conocimiento/instrucciones_bot.md   Instrucciones (prompt de sistema) para la IA

IA (opcional). Sin estas variables, el asistente funciona en "modo demo" (buscador por palabras clave):
    ASISTENTE_PROVEEDOR   anthropic | openai | gemini
    ASISTENTE_API_KEY     clave de la API del proveedor (solo como variable de entorno, nunca en el código)
    ASISTENTE_MODELO      modelo a usar (obligatorio para openai y gemini)
"""
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.request
from collections import defaultdict, deque
from datetime import datetime

from flask import jsonify, render_template, request

BASE = os.path.dirname(os.path.abspath(__file__))

CONTACTO = {
    "telefono": "981 111 114",
    "whatsapp": "662 488 889",
    "email": "soporte@logrootrh.com",
}

PROVEEDOR = os.environ.get("ASISTENTE_PROVEEDOR", "").strip().lower()
API_KEY = os.environ.get("ASISTENTE_API_KEY", "").strip()
MODELOS_POR_DEFECTO = {"anthropic": "claude-haiku-5-5"}
MODELO = os.environ.get("ASISTENTE_MODELO", "").strip() or MODELOS_POR_DEFECTO.get(PROVEEDOR, "")

MAX_MENSAJES = 12          # historial que se envía a la IA
MAX_LARGO_MENSAJE = 1000   # caracteres por mensaje
LIMITE_POR_MINUTO = 15     # peticiones de chat por IP y minuto (protege la clave de la API)
TIMEOUT_IA = 30            # segundos

ROLES = {"empleado": "Empleado", "administrador": "Administrador / RR. HH."}


# ===================================================================== Base de conocimiento
def _ruta(nombre):
    for carpeta in (os.path.join(BASE, "conocimiento"), BASE):
        ruta = os.path.join(carpeta, nombre)
        if os.path.exists(ruta):
            return ruta
    raise FileNotFoundError(f"No encuentro {nombre} (ni en conocimiento/ ni junto a app.py)")


def _leer(nombre):
    with open(_ruta(nombre), encoding="utf-8") as f:
        return f.read()


RE_SECCION_ROL = re.compile(r"^##\s+\d+\.\s+(EMPLEADO|ADMINISTRADOR)", re.I)
RE_CATEGORIA = re.compile(r"^###\s+\d+\.\d+\s+(.+)$")
RE_PREGUNTA = re.compile(r"^\*\*([EA]-[A-Z]\d+)\.\s+(.+?)\*\*\s*(.*)$")
RE_MARCA = re.compile(r"\s*\*{0,2}\[(PENDIENTE|REVISAR)[^\]]*\]\*{0,2}")


def limpiar_marcas(texto):
    """Quita las marcas internas [PENDIENTE] / [REVISAR] y las líneas que quedan vacías."""
    lineas = []
    for linea in texto.splitlines():
        nueva = RE_MARCA.sub("", linea).rstrip()
        if linea.strip() and re.fullmatch(r"\s*[-*]\s*", nueva):
            continue  # viñeta que solo contenía la marca
        lineas.append(nueva)
    return "\n".join(lineas).strip()


def cargar_conocimiento():
    """
    Lee base_conocimiento.md y devuelve:
      arbol: {rol: [{"categoria": str, "preguntas": [{"id", "pregunta"}]}]}
      preguntas: {id: {"id", "rol", "categoria", "pregunta", "respuesta", "pendiente"}}
    """
    texto = _leer("base_conocimiento.md")
    arbol = {"empleado": [], "administrador": []}
    preguntas = {}
    rol = categoria = actual = None

    def cerrar():
        if actual:
            cuerpo = "\n".join(actual.pop("_lineas")).strip()
            actual["pendiente"] = "[PENDIENTE" in cuerpo
            actual["respuesta"] = limpiar_marcas(cuerpo)

    for linea in texto.splitlines():
        m_rol = RE_SECCION_ROL.match(linea)
        m_cat = RE_CATEGORIA.match(linea)
        m_pre = RE_PREGUNTA.match(linea)
        if m_rol or m_cat or linea.startswith("## ") or linea.strip() == "---":
            cerrar()
            actual = None
            if m_rol:
                rol = "empleado" if m_rol.group(1).upper() == "EMPLEADO" else "administrador"
                categoria = None
            elif m_cat and rol:
                categoria = {"categoria": m_cat.group(1).strip(), "preguntas": []}
                arbol[rol].append(categoria)
            elif linea.startswith("## "):
                rol = categoria = None
            continue
        if m_pre and rol and categoria:
            cerrar()
            pid, titulo, resto = m_pre.groups()
            actual = {"id": pid, "rol": rol, "categoria": categoria["categoria"],
                      "pregunta": limpiar_marcas(titulo), "_lineas": [resto] if resto.strip() else []}
            preguntas[pid] = actual
            categoria["preguntas"].append({"id": pid, "pregunta": actual["pregunta"]})
            continue
        if actual is not None:
            actual["_lineas"].append(linea)
    cerrar()
    return arbol, preguntas, texto


def instrucciones_sistema(texto_base):
    return _leer("instrucciones_bot.md").replace("{{BASE_CONOCIMIENTO}}", texto_base)


# ===================================================================== Modo demo (sin IA)
VACIAS = set("""a al algo como con cual cuales cuando de del donde el ella en es esta este esto hay he la las le lo los
me mi mis no o para pero por que se si sin su sus te tengo tu un una uno y ya yo puedo quiero hago hacer necesito
favor hola buenas buenos dias tardes tambien muy mas eso esa ese ahi asi ver logroot pongo poner pone q min
desde deberia debe dice sale salen cuanto cuesta""".split())

SINONIMOS = {
    "clave": "contrasena", "password": "contrasena", "pass": "contrasena", "pin": "contrasena",
    "olvide": "olvido", "olvidado": "olvido", "olvidar": "olvido", "olvida": "olvido", "olvidao": "olvido",
    "fichaje": "fichar", "fichajes": "fichar", "fiche": "fichar", "ficho": "fichar", "fichado": "fichar",
    "ficha": "fichar", "fichan": "fichar", "fichen": "fichar", "marcar": "fichar", "entrada": "fichar",
    "saco": "sacar", "sacar": "sacar", "aprobaron": "aprobado", "aprobada": "aprobado", "aprobadas": "aprobado",
    "vacacion": "vacaciones", "vacas": "vacaciones", "dias": "vacaciones",
    "trabajador": "empleado", "trabajadores": "empleado", "empleados": "empleado", "plantilla": "empleado",
    "alta": "alta", "crear": "alta", "nuevo": "alta", "añadir": "alta", "anadir": "alta",
    "baja": "baja", "despedir": "baja", "eliminar": "baja", "borrar": "baja",
    "horas": "informe", "excel": "informe", "pdf": "descargar", "exportar": "descargar",
    "factura": "facturas", "recibo": "facturas",
    "cierra": "error", "falla": "error", "bloquea": "error", "abre": "error", "abrirla": "error",
    "funciona": "error", "carga": "error", "errores": "error",
    "movil": "app", "aplicacion": "app", "playstore": "tienda", "store": "tienda",
    "tarde": "retraso", "retrase": "retraso", "llegue": "retraso",
    "antes": "anticipada", "temprano": "anticipada",
    "descanso": "pausa", "parar": "pausa", "comer": "pausa",
    "festivo": "festivos", "fiesta": "festivos",
    "aviso": "notificaciones", "avisos": "notificaciones", "recordatorio": "notificaciones",
    "ordenador": "pc", "escritorio": "pc", "navegador": "pc",
    "turno": "horario", "turnos": "horario", "horarios": "horario",
}


def _normalizar(texto):
    texto = unicodedata.normalize("NFD", texto.lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9ñ ]+", " ", texto)


def _tokens(texto):
    salida = []
    for t in _normalizar(texto).split():
        if len(t) < 2 or t in VACIAS:
            continue
        t = SINONIMOS.get(t, t)
        salida.append(t[:6])  # raíz aproximada: "aprobado"/"aprobada" → "aproba"
    return salida


def buscar_respuesta(texto, preguntas, rol=None):
    """
    Elige la pregunta de la base que mejor encaja con el mensaje (modo demo, sin IA).
    Las palabras raras pesan más que las comunes, y las del título de la pregunta, el triple.
    Devuelve (pregunta, puntuación) o (None, puntuación) si no hay una coincidencia clara.
    """
    import math
    consulta = set(_tokens(texto))
    if not consulta:
        return None, 0
    candidatas = [p for p in preguntas.values() if not rol or p["rol"] == rol]
    docs = {p["id"]: (set(_tokens(p["pregunta"])), set(_tokens(p["categoria"] + " " + p["respuesta"])))
            for p in candidatas}
    n = len(docs) or 1
    df = defaultdict(int)
    for titulo, cuerpo in docs.values():
        for t in titulo | cuerpo:
            df[t] += 1
    mejor, mejor_punt = None, 0.0
    for p in candidatas:
        titulo, cuerpo = docs[p["id"]]
        punt = sum(math.log(1 + n / df[t]) * (3 if t in titulo else 1)
                   for t in consulta if t in titulo or t in cuerpo)
        if punt > mejor_punt:
            mejor, mejor_punt = p, punt
    umbral = 3 if len(consulta) <= 2 else 4  # preguntas muy cortas ("¿cómo ficho?") puntúan menos
    return (mejor, mejor_punt) if mejor_punt >= umbral else (None, mejor_punt)


def respuesta_sin_resultado():
    return ("No tengo información sobre eso. El equipo de Soporte te ayuda encantado:\n"
            f"- 📞 {CONTACTO['telefono']}\n- 💬 WhatsApp {CONTACTO['whatsapp']}\n- ✉️ {CONTACTO['email']}\n\n"
            "¿Te ha servido?")


# ===================================================================== IA
class ErrorIA(Exception):
    pass


def ia_configurada():
    return bool(PROVEEDOR in ("anthropic", "openai", "gemini") and API_KEY and MODELO)


def _post_json(url, cuerpo, cabeceras):
    datos = json.dumps(cuerpo).encode("utf-8")
    req = urllib.request.Request(url, data=datos, method="POST",
                                 headers={"Content-Type": "application/json", **cabeceras})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_IA) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detalle = e.read().decode("utf-8", "replace")[:300]
        raise ErrorIA(f"HTTP {e.code}: {detalle}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise ErrorIA(f"Sin conexión con el proveedor de IA: {e}") from e


def llamar_ia(sistema, mensajes):
    """mensajes: [{"rol": "usuario"|"asistente", "texto": str}] → texto de respuesta."""
    if PROVEEDOR == "anthropic":
        r = _post_json("https://api.anthropic.com/v1/messages", {
            "model": MODELO, "max_tokens": 700, "system": sistema,
            "messages": [{"role": "user" if m["rol"] == "usuario" else "assistant", "content": m["texto"]}
                         for m in mensajes],
        }, {"x-api-key": API_KEY, "anthropic-version": "2023-06-01"})
        return "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text").strip()

    if PROVEEDOR == "openai":
        r = _post_json("https://api.openai.com/v1/chat/completions", {
            "model": MODELO, "max_tokens": 700,
            "messages": [{"role": "system", "content": sistema}] +
                        [{"role": "user" if m["rol"] == "usuario" else "assistant", "content": m["texto"]}
                         for m in mensajes],
        }, {"Authorization": f"Bearer {API_KEY}"})
        return (r.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()

    if PROVEEDOR == "gemini":
        r = _post_json(f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:generateContent", {
            "systemInstruction": {"parts": [{"text": sistema}]},
            "contents": [{"role": "user" if m["rol"] == "usuario" else "model", "parts": [{"text": m["texto"]}]}
                         for m in mensajes],
            "generationConfig": {"maxOutputTokens": 700},
        }, {"x-goog-api-key": API_KEY})
        partes = ((r.get("candidates") or [{}])[0].get("content") or {}).get("parts", [])
        return "".join(p.get("text", "") for p in partes).strip()

    raise ErrorIA("Proveedor de IA no configurado")


# ===================================================================== Límite de uso
_llamadas = defaultdict(deque)


def demasiadas_peticiones(ip):
    ahora = time.time()
    cola = _llamadas[ip]
    while cola and ahora - cola[0] > 60:
        cola.popleft()
    if len(cola) >= LIMITE_POR_MINUTO:
        return True
    cola.append(ahora)
    return False


# ===================================================================== Registro en Flask
def registrar(app, db):
    """Añade las rutas del asistente a la app de Flask. `db` es la función que devuelve la conexión SQLite."""

    def conexion():
        c = db()
        c.execute("""CREATE TABLE IF NOT EXISTS asistente_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            sesion TEXT,
            rol TEXT,
            origen TEXT NOT NULL,          -- boton | ia | demo | error
            pregunta_id TEXT,
            pregunta TEXT NOT NULL,
            respuesta TEXT NOT NULL,
            util INTEGER                   -- 1 sí, 0 no, NULL sin valorar
        )""")
        return c

    def guardar(sesion, rol, origen, pregunta_id, pregunta, respuesta):
        c = conexion()
        cur = c.execute(
            "INSERT INTO asistente_log (fecha, sesion, rol, origen, pregunta_id, pregunta, respuesta) "
            "VALUES (?,?,?,?,?,?,?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), sesion, rol, origen, pregunta_id,
             pregunta[:MAX_LARGO_MENSAJE], respuesta))
        c.commit()
        return cur.lastrowid

    def rol_valido(valor):
        return valor if valor in ROLES else None

    @app.after_request
    def cors_asistente(resp):
        # Permite incrustar el widget en otra web (p. ej. la web de LogRoot) que llame a esta API
        if request.path.startswith("/api/asistente/"):
            resp.headers["Access-Control-Allow-Origin"] = "*"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return resp

    # ----------------------------------------------------------------- Páginas
    @app.route("/asistente")
    def asistente_demo():
        return render_template("asistente.html", contacto=CONTACTO, modo_ia=ia_configurada(),
                               proveedor=PROVEEDOR if ia_configurada() else None)

    @app.route("/informes/asistente")
    def informe_asistente():
        c = conexion()
        filas = c.execute("SELECT * FROM asistente_log ORDER BY id DESC LIMIT 300").fetchall()
        tot = c.execute("SELECT COUNT(*) AS total, SUM(util = 1) AS si, SUM(util = 0) AS no, "
                        "SUM(origen = 'ia') AS ia, SUM(origen = 'boton') AS boton, SUM(origen = 'demo') AS demo "
                        "FROM asistente_log").fetchone()
        return render_template("asistente_log.html", filas=filas, tot=tot, modo_ia=ia_configurada())

    # ----------------------------------------------------------------- API pública del widget
    @app.route("/api/asistente/arbol")
    def api_asistente_arbol():
        arbol, _, _ = cargar_conocimiento()
        return jsonify(roles=ROLES, arbol=arbol, contacto=CONTACTO,
                       modo="ia" if ia_configurada() else "demo")

    @app.route("/api/asistente/respuesta/<pid>")
    def api_asistente_respuesta(pid):
        _, preguntas, _ = cargar_conocimiento()
        p = preguntas.get(pid.upper())
        if not p:
            return jsonify(error="pregunta no encontrada"), 404
        texto = p["respuesta"]
        if p["pendiente"]:
            texto += (f"\n\nPara el resto, contacta con Soporte LogRoot: 📞 {CONTACTO['telefono']} · "
                      f"💬 {CONTACTO['whatsapp']} · ✉️ {CONTACTO['email']}")
        texto += "\n\n¿Te ha servido?"
        log_id = guardar(request.args.get("sesion"), p["rol"], "boton", p["id"], p["pregunta"], texto)
        return jsonify(id=p["id"], pregunta=p["pregunta"], respuesta=texto, log_id=log_id)

    @app.route("/api/asistente/chat", methods=["POST"])
    def api_asistente_chat():
        if demasiadas_peticiones(request.headers.get("X-Forwarded-For", request.remote_addr or "?").split(",")[0]):
            return jsonify(error="Has enviado muchos mensajes seguidos. Espera un minuto, por favor."), 429
        d = request.get_json(silent=True) or {}
        rol = rol_valido(d.get("rol"))
        sesion = str(d.get("sesion") or "")[:40]
        mensajes = []
        for m in (d.get("mensajes") or [])[-MAX_MENSAJES:]:
            if not isinstance(m, dict) or m.get("rol") not in ("usuario", "asistente"):
                continue
            texto = str(m.get("texto") or "").strip()[:MAX_LARGO_MENSAJE]
            if texto:
                mensajes.append({"rol": m["rol"], "texto": texto})
        # La conversación tiene que empezar y terminar con el usuario
        while mensajes and mensajes[0]["rol"] != "usuario":
            mensajes.pop(0)
        if not mensajes or mensajes[-1]["rol"] != "usuario":
            return jsonify(error="Falta el mensaje del usuario"), 400
        pregunta = mensajes[-1]["texto"]

        _, preguntas, texto_base = cargar_conocimiento()

        if ia_configurada():
            sistema = instrucciones_sistema(texto_base)
            contexto = f"ROL: {rol}" if rol else "ROL: desconocido"
            mensajes_ia = [dict(m) for m in mensajes]
            mensajes_ia[-1]["texto"] = f"[{contexto}]\n{mensajes_ia[-1]['texto']}"
            try:
                respuesta = llamar_ia(sistema, mensajes_ia) or respuesta_sin_resultado()
                origen = "ia"
            except ErrorIA as e:
                app.logger.warning("Asistente: fallo de la IA (%s). Se usa el modo demo.", e)
                p, _ = buscar_respuesta(pregunta, preguntas, rol)
                respuesta = (p["respuesta"] + "\n\n¿Te ha servido?") if p else respuesta_sin_resultado()
                origen = "error"
            log_id = guardar(sesion, rol, origen, None, pregunta, respuesta)
            return jsonify(respuesta=respuesta, origen=origen, log_id=log_id)

        # Modo demo: buscador por palabras clave sobre la base de conocimiento
        p, _ = buscar_respuesta(pregunta, preguntas, rol)
        if p:
            respuesta = p["respuesta"]
            if p["pendiente"]:
                respuesta += (f"\n\nPara el resto, contacta con Soporte LogRoot: 📞 {CONTACTO['telefono']} · "
                              f"💬 {CONTACTO['whatsapp']} · ✉️ {CONTACTO['email']}")
            respuesta += "\n\n¿Te ha servido?"
        else:
            respuesta = respuesta_sin_resultado()
        log_id = guardar(sesion, rol, "demo", p["id"] if p else None, pregunta, respuesta)
        return jsonify(respuesta=respuesta, origen="demo", log_id=log_id,
                       pregunta_id=p["id"] if p else None, pregunta_titulo=p["pregunta"] if p else None)

    @app.route("/api/asistente/valoracion", methods=["POST"])
    def api_asistente_valoracion():
        d = request.get_json(silent=True) or {}
        try:
            log_id, util = int(d.get("log_id")), 1 if d.get("util") else 0
        except (TypeError, ValueError):
            return jsonify(error="log_id no válido"), 400
        c = conexion()
        c.execute("UPDATE asistente_log SET util = ? WHERE id = ?", (util, log_id))
        c.commit()
        return jsonify(ok=True)
