"""
LOGI DEMO · Réplica de ejemplo de la herramienta de soporte.

- Web (pantallas tipo LOGI):  http://localhost:5000
- API REST para Make:         http://localhost:5000/api/...   (cabecera X-API-Key)

Arranque:
    pip install -r requirements.txt
    python app.py
"""
import os
import re
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, url_for)

import seed

app = Flask(__name__)
app.json.ensure_ascii = False  # tildes legibles en las respuestas JSON
app.secret_key =os.environ.get("LOGI_SECRET", "logi-demo-secret")
API_KEY = os.environ.get("LOGI_API_KEY", "demo-1234")
DB_PATH = seed.DB_PATH

ESTADOS_PAGO = {"al_dia": "Al día", "deudora": "Deudora"}
ESTADOS_RESENA = {"no_solicitada": "No solicitada", "solicitada": "Solicitada",
                  "realizada": "Realizada", "rechazada": "Rechazada"}
ESTADOS_CLIENTE = {"activo": "Activo", "baja_solicitada": "Baja solicitada", "baja": "Baja"}
CATEGORIAS = ["Alta empresa", "Alta trabajador", "Baja trabajador", "Solicitud de baja",
              "Error de fichaje", "Facturación", "Formación", "Incidencia", "Consulta"]
CANALES = ["Teléfono", "Email", "WhatsApp", "Chat"]
FORMAS_PAGO = ["TRANSFERENCIA", "DOMICILIACION", "TARJETA"]

CAMPOS_EDITABLES = ["nombre", "num_empleados", "encargado", "gerente", "telefono", "email",
                    "direccion", "agente_venta_id", "fecha_alta", "implementacion_gerente",
                    "implementacion_empleados", "seguimiento_mes", "correos_incidencias",
                    "forma_pago", "fondos_europeos", "fecha_fin_contrato", "ultima_factura_fecha",
                    "ultima_factura_importe", "estado_cliente"]


# --------------------------------------------------------------------- BD
def db() -> sqlite3.Connection:
    if "db" not in g:
        seed.asegurar_db()
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def cerrar_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def ahora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalizar_cif(cif: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (cif or "").upper())


def agente_por_nombre(nombre: str):
    return db().execute("SELECT * FROM agentes WHERE nombre = ?", (nombre,)).fetchone()


def agente_automatizacion_id() -> int:
    return agente_por_nombre("Automatización")["id"]


def empresa_por_cif(cif: str):
    return db().execute("SELECT * FROM empresas WHERE cif = ?", (normalizar_cif(cif),)).fetchone()


def cambiar_estado_pago(empresa_id: int, estado: str, agente_id: int, origen="manual", nota=None) -> bool:
    """Cambia el estado de pago y lo registra en el histórico. Devuelve True si hubo cambio."""
    if estado not in ESTADOS_PAGO:
        raise ValueError("estado debe ser 'al_dia' o 'deudora'")
    actual = db().execute("SELECT estado_pago FROM empresas WHERE id = ?", (empresa_id,)).fetchone()
    if actual is None:
        raise LookupError("empresa no encontrada")
    if actual["estado_pago"] == estado:
        return False
    db().execute("UPDATE empresas SET estado_pago = ?, actualizado_en = ? WHERE id = ?",
                 (estado, ahora(), empresa_id))
    db().execute("INSERT INTO historial_pago (empresa_id, fecha, estado, agente_id, origen, nota) "
                 "VALUES (?,?,?,?,?,?)", (empresa_id, ahora(), estado, agente_id, origen, nota))
    db().commit()
    return True


def siguiente_num_caso() -> int:
    return (db().execute("SELECT MAX(id) FROM casos").fetchone()[0] or 16000) + 1


def crear_caso(empresa_id, asunto, categoria, descripcion, canal, agente_id=None,
               escalado=0, sensible=0) -> int:
    num = siguiente_num_caso()
    db().execute(
        "INSERT INTO casos (id, empresa_id, asunto, categoria, descripcion, canal, agente_id, escalado, "
        "sensible, fecha_apertura, fecha_actualizacion) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (num, empresa_id, asunto.upper(), categoria, descripcion, canal, agente_id,
         int(bool(escalado)), int(bool(sensible)), ahora(), ahora()))
    db().commit()
    return num


# --------------------------------------------------------------------- Formato
@app.template_filter("fecha")
def f_fecha(valor, con_hora=False):
    if not valor:
        return "-"
    try:
        if len(valor) > 10:
            d = datetime.strptime(valor[:19], "%Y-%m-%d %H:%M:%S")
            return d.strftime("%d/%m/%Y %H:%M") if con_hora else d.strftime("%d/%m/%Y")
        return date.fromisoformat(valor).strftime("%d/%m/%Y")
    except ValueError:
        return valor


@app.template_filter("euros")
def f_euros(valor):
    if valor is None:
        return "-"
    return f"{valor:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


# --------------------------------------------------------------------- Contexto UI
def agente_actual():
    aid = request.cookies.get("agente_id")
    fila = None
    if aid and aid.isdigit():
        fila = db().execute("SELECT * FROM agentes WHERE id = ?", (int(aid),)).fetchone()
    return fila or agente_por_nombre("Andrés Varela")


@app.context_processor
def contexto():
    if request.path.startswith("/api/"):
        return {}
    c = db()
    yo = agente_actual()
    return dict(
        yo=yo,
        agentes=c.execute("SELECT * FROM agentes WHERE rol != 'sistema' ORDER BY nombre").fetchall(),
        cnt_sin_asignar=c.execute("SELECT COUNT(*) FROM casos WHERE estado='abierto' AND agente_id IS NULL").fetchone()[0],
        cnt_escalados=c.execute("SELECT COUNT(*) FROM casos WHERE estado='abierto' AND escalado=1").fetchone()[0],
        cnt_sensibles=c.execute("SELECT COUNT(*) FROM casos WHERE estado='abierto' AND sensible=1").fetchone()[0],
        cnt_mios=c.execute("SELECT COUNT(*) FROM casos WHERE estado='abierto' AND agente_id=?", (yo["id"],)).fetchone()[0],
        ESTADOS_PAGO=ESTADOS_PAGO, ESTADOS_RESENA=ESTADOS_RESENA, ESTADOS_CLIENTE=ESTADOS_CLIENTE,
        CATEGORIAS=CATEGORIAS, CANALES=CANALES, FORMAS_PAGO=FORMAS_PAGO,
    )


# ===================================================================== WEB
@app.route("/")
def escritorio():
    hora = datetime.now().hour
    saludo = "Buenos días" if hora < 14 else ("Buenas tardes" if hora < 21 else "Buenas noches")
    recientes = db().execute(
        "SELECT c.*, e.nombre AS empresa FROM casos c JOIN empresas e ON e.id = c.empresa_id "
        "WHERE c.estado='abierto' AND c.agente_id = ? ORDER BY c.fecha_actualizacion DESC LIMIT 6",
        (agente_actual()["id"],)).fetchall()
    return render_template("escritorio.html", saludo=saludo, recientes=recientes)


@app.route("/agente", methods=["POST"])
def cambiar_agente():
    resp = redirect(request.referrer or url_for("escritorio"))
    resp.set_cookie("agente_id", request.form.get("agente_id", ""), max_age=60 * 60 * 24 * 365)
    return resp


SQL_EMPRESAS = """
SELECT e.*,
       (SELECT COUNT(*) FROM casos c WHERE c.empresa_id = e.id AND c.estado='abierto') AS casos_abiertos,
       (SELECT COUNT(*) FROM casos c WHERE c.empresa_id = e.id AND c.estado='cerrado') AS casos_cerrados,
       a.nombre AS agente_venta
FROM empresas e LEFT JOIN agentes a ON a.id = e.agente_venta_id
"""


@app.route("/empresas")
def buscar_empresas():
    q = request.args.get("q", "").strip()
    filas = db().execute(SQL_EMPRESAS + " WHERE e.nombre LIKE ? OR e.cif LIKE ? ORDER BY e.nombre",
                         (f"%{q}%", f"%{normalizar_cif(q) or q}%")).fetchall()
    if len(filas) == 1 and q:
        return redirect(url_for("ficha_empresa", empresa_id=filas[0]["id"]))
    return render_template("empresas.html", q=q, empresas=filas)


@app.route("/empresas/<int:empresa_id>")
def ficha_empresa(empresa_id):
    c = db()
    e = c.execute(SQL_EMPRESAS + " WHERE e.id = ?", (empresa_id,)).fetchone()
    if e is None:
        abort(404)
    casos = c.execute(
        "SELECT c.*, a.nombre AS agente FROM casos c LEFT JOIN agentes a ON a.id = c.agente_id "
        "WHERE c.empresa_id = ? ORDER BY c.fecha_apertura DESC", (empresa_id,)).fetchall()
    historial = c.execute(
        "SELECT h.*, a.nombre AS agente FROM historial_pago h LEFT JOIN agentes a ON a.id = h.agente_id "
        "WHERE h.empresa_id = ? ORDER BY h.fecha DESC", (empresa_id,)).fetchall()
    trabajadores = c.execute("SELECT * FROM trabajadores WHERE empresa_id = ? ORDER BY activo DESC, nombre",
                             (empresa_id,)).fetchall()
    ventas = c.execute("SELECT * FROM agentes WHERE rol='ventas' ORDER BY nombre").fetchall()
    return render_template("ficha.html", e=e, casos=casos, historial=historial,
                           trabajadores=trabajadores, ventas=ventas)


@app.route("/empresas/<int:empresa_id>/guardar", methods=["POST"])
def guardar_empresa(empresa_id):
    valores = {}
    for campo in CAMPOS_EDITABLES:
        if campo in request.form:
            v = request.form[campo].strip()
            valores[campo] = v if v != "" else None
    if valores.get("num_empleados") is None:
        valores.pop("num_empleados", None)
    sets = ", ".join(f"{k} = ?" for k in valores)
    db().execute(f"UPDATE empresas SET {sets}, actualizado_en = ? WHERE id = ?",
                 (*valores.values(), ahora(), empresa_id))
    db().commit()
    flash("Datos de empresa guardados.")
    return redirect(url_for("ficha_empresa", empresa_id=empresa_id))


@app.route("/empresas/<int:empresa_id>/estado-pago", methods=["POST"])
def web_estado_pago(empresa_id):
    estado = request.form["estado"]
    cambiar_estado_pago(empresa_id, estado, agente_actual()["id"], "manual")
    flash(f"Empresa marcada como {ESTADOS_PAGO[estado].lower()}.")
    return redirect(url_for("ficha_empresa", empresa_id=empresa_id))


@app.route("/empresas/<int:empresa_id>/resena", methods=["POST"])
def guardar_resena(empresa_id):
    agente = request.form.get("resena_agente_id") or None
    db().execute("UPDATE empresas SET resena_estado = ?, resena_agente_id = ?, actualizado_en = ? WHERE id = ?",
                 (request.form["resena_estado"], agente, ahora(), empresa_id))
    db().commit()
    flash("Reseña guardada.")
    return redirect(url_for("ficha_empresa", empresa_id=empresa_id))


@app.route("/empresas/<int:empresa_id>/casos", methods=["POST"])
def nuevo_caso_web(empresa_id):
    f = request.form
    num = crear_caso(empresa_id, f["asunto"], f["categoria"], f.get("descripcion"), f["canal"],
                     f.get("agente_id") or None, f.get("escalado"), f.get("sensible"))
    flash(f"Caso Nº {num} creado.")
    return redirect(url_for("ver_caso", caso_id=num))


@app.route("/empresas/<int:empresa_id>/trabajadores", methods=["POST"])
def nuevo_trabajador_web(empresa_id):
    f = request.form
    db().execute("INSERT INTO trabajadores (empresa_id, nombre, email, puesto, fecha_alta) VALUES (?,?,?,?,?)",
                 (empresa_id, f["nombre"], f.get("email") or None, f.get("puesto") or None,
                  f.get("fecha_alta") or date.today().isoformat()))
    db().execute("UPDATE empresas SET num_empleados = (SELECT COUNT(*) FROM trabajadores WHERE empresa_id=? AND activo=1) WHERE id=?",
                 (empresa_id, empresa_id))
    db().commit()
    flash("Trabajador dado de alta.")
    return redirect(url_for("ficha_empresa", empresa_id=empresa_id) + "#trabajadores")


@app.route("/trabajadores/<int:tid>/baja", methods=["POST"])
def baja_trabajador_web(tid):
    t = db().execute("SELECT * FROM trabajadores WHERE id = ?", (tid,)).fetchone()
    db().execute("UPDATE trabajadores SET activo = 0, fecha_baja = ? WHERE id = ?", (date.today().isoformat(), tid))
    db().execute("UPDATE empresas SET num_empleados = (SELECT COUNT(*) FROM trabajadores WHERE empresa_id=? AND activo=1) WHERE id=?",
                 (t["empresa_id"], t["empresa_id"]))
    db().commit()
    flash(f"{t['nombre']} dado/a de baja.")
    return redirect(url_for("ficha_empresa", empresa_id=t["empresa_id"]) + "#trabajadores")


VISTAS_CASOS = {
    "sin_asignar": ("Sin asignar", "c.estado='abierto' AND c.agente_id IS NULL"),
    "asignados": ("Asignados a mí", "c.estado='abierto' AND c.agente_id = :yo"),
    "todos_abiertos": ("Todos los abiertos", "c.estado='abierto'"),
    "escalados": ("Escalados", "c.estado='abierto' AND c.escalado=1"),
    "sensibles": ("Sensibles", "c.estado='abierto' AND c.sensible=1"),
    "cerrados": ("Cerrados", "c.estado='cerrado'"),
}


@app.route("/casos")
def lista_casos():
    vista = request.args.get("vista", "todos_abiertos")
    q = request.args.get("q", "").strip()
    titulo, where = VISTAS_CASOS.get(vista, VISTAS_CASOS["todos_abiertos"])
    params = {"yo": agente_actual()["id"]}
    if q:
        if q.isdigit():
            caso = db().execute("SELECT id FROM casos WHERE id = ?", (int(q),)).fetchone()
            if caso:
                return redirect(url_for("ver_caso", caso_id=caso["id"]))
        where = "c.asunto LIKE :q OR e.nombre LIKE :q OR CAST(c.id AS TEXT) LIKE :q"
        params["q"] = f"%{q}%"
        titulo = f'Resultados de búsqueda por "{q}"'
    casos = db().execute(
        "SELECT c.*, e.nombre AS empresa, a.nombre AS agente FROM casos c "
        "JOIN empresas e ON e.id = c.empresa_id LEFT JOIN agentes a ON a.id = c.agente_id "
        f"WHERE {where} ORDER BY c.fecha_actualizacion DESC LIMIT 300", params).fetchall()
    return render_template("casos.html", casos=casos, titulo=titulo, vista=vista, q=q)


@app.route("/casos/<int:caso_id>")
def ver_caso(caso_id):
    c = db().execute(
        "SELECT c.*, e.nombre AS empresa, e.cif, e.estado_pago, a.nombre AS agente FROM casos c "
        "JOIN empresas e ON e.id = c.empresa_id LEFT JOIN agentes a ON a.id = c.agente_id WHERE c.id = ?",
        (caso_id,)).fetchone()
    if c is None:
        abort(404)
    notas = db().execute("SELECT n.*, a.nombre AS agente FROM notas_caso n LEFT JOIN agentes a ON a.id = n.agente_id "
                         "WHERE caso_id = ? ORDER BY fecha", (caso_id,)).fetchall()
    return render_template("caso.html", c=c, notas=notas)


@app.route("/casos/<int:caso_id>/actualizar", methods=["POST"])
def actualizar_caso_web(caso_id):
    f = request.form
    accion = f.get("accion")
    c = db()
    if accion == "nota" and f.get("texto", "").strip():
        c.execute("INSERT INTO notas_caso (caso_id, agente_id, texto, fecha) VALUES (?,?,?,?)",
                  (caso_id, agente_actual()["id"], f["texto"].strip(), ahora()))
    elif accion == "asignarme":
        c.execute("UPDATE casos SET agente_id = ? WHERE id = ?", (agente_actual()["id"], caso_id))
    elif accion == "guardar":
        c.execute("UPDATE casos SET agente_id = ?, categoria = ?, escalado = ?, sensible = ? WHERE id = ?",
                  (f.get("agente_id") or None, f["categoria"], int("escalado" in f), int("sensible" in f), caso_id))
    elif accion == "cerrar":
        c.execute("UPDATE casos SET estado='cerrado', fecha_cierre = ? WHERE id = ?", (ahora(), caso_id))
    elif accion == "reabrir":
        c.execute("UPDATE casos SET estado='abierto', fecha_cierre = NULL WHERE id = ?", (caso_id,))
    c.execute("UPDATE casos SET fecha_actualizacion = ? WHERE id = ?", (ahora(), caso_id))
    c.commit()
    return redirect(url_for("ver_caso", caso_id=caso_id))


@app.route("/informes/deudoras")
def informe_deudoras():
    mostrar = request.args.get("mostrar", "todas")
    filtro = {"todas": "1=1", "deudoras": "e.estado_pago='deudora'", "al_dia": "e.estado_pago='al_dia'"}.get(mostrar, "1=1")
    filas = db().execute(
        "SELECT e.*, (SELECT MAX(fecha) FROM historial_pago h WHERE h.empresa_id=e.id AND h.estado='deudora') AS ultima_marca "
        f"FROM empresas e WHERE e.id IN (SELECT empresa_id FROM historial_pago) AND {filtro} "
        "ORDER BY e.estado_pago DESC, e.nombre").fetchall()
    historiales = {}
    for f in filas:
        historiales[f["id"]] = db().execute(
            "SELECT h.*, a.nombre AS agente FROM historial_pago h LEFT JOIN agentes a ON a.id=h.agente_id "
            "WHERE empresa_id = ? ORDER BY fecha DESC", (f["id"],)).fetchall()
    return render_template("deudoras.html", filas=filas, mostrar=mostrar, historiales=historiales)


@app.route("/informes/contratos")
def informe_contratos():
    hoy = date.today().isoformat()
    en90 = (date.today() + timedelta(days=90)).isoformat()
    proximos = db().execute("SELECT * FROM empresas WHERE fecha_fin_contrato BETWEEN ? AND ? ORDER BY fecha_fin_contrato",
                            (hoy, en90)).fetchall()
    vencidos = db().execute("SELECT * FROM empresas WHERE fecha_fin_contrato < ? ORDER BY fecha_fin_contrato DESC",
                            (hoy,)).fetchall()
    sin_fecha = db().execute("SELECT * FROM empresas WHERE fecha_fin_contrato IS NULL ORDER BY nombre").fetchall()
    return render_template("contratos.html", proximos=proximos, vencidos=vencidos, sin_fecha=sin_fecha)


@app.route("/informes/bajas")
def informe_bajas():
    filas = db().execute(SQL_EMPRESAS + " WHERE e.estado_cliente != 'activo' ORDER BY e.nombre").fetchall()
    return render_template("bajas.html", filas=filas)


@app.route("/informes/api")
def informe_api():
    filas = db().execute("SELECT * FROM log_api ORDER BY id DESC LIMIT 200").fetchall()
    return render_template("log_api.html", filas=filas)


@app.route("/cartera")
def cartera():
    agente = request.args.get("agente", "")
    estado = request.args.get("estado", "")
    where, params = ["1=1"], []
    if agente:
        where.append("e.agente_venta_id = ?")
        params.append(agente)
    if estado:
        where.append("e.estado_cliente = ?")
        params.append(estado)
    filas = db().execute(SQL_EMPRESAS + f" WHERE {' AND '.join(where)} ORDER BY e.fecha_alta DESC", params).fetchall()
    ventas = db().execute("SELECT * FROM agentes WHERE rol='ventas' ORDER BY nombre").fetchall()
    return render_template("cartera.html", filas=filas, ventas=ventas, agente=agente, estado=estado)


@app.route("/api-docs")
def api_docs():
    return render_template("api_docs.html", api_key=API_KEY, base=request.host_url.rstrip("/"))


# ===================================================================== API
def api(f):
    @wraps(f)
    def envoltorio(*args, **kwargs):
        clave = request.headers.get("X-API-Key") or request.args.get("api_key")
        if clave != API_KEY:
            resp = jsonify(error="API key incorrecta o ausente (cabecera X-API-Key)")
            resp.status_code = 401
        else:
            try:
                resp = f(*args, **kwargs)
                if not hasattr(resp, "status_code"):
                    resp = jsonify(resp)
            except LookupError as ex:
                resp = jsonify(error=str(ex)); resp.status_code = 404
            except (ValueError, KeyError) as ex:
                resp = jsonify(error=f"Petición no válida: {ex}"); resp.status_code = 400
        try:
            db().execute("INSERT INTO log_api (fecha, metodo, ruta, estado, resumen) VALUES (?,?,?,?,?)",
                         (ahora(), request.method, request.full_path.rstrip("?"), resp.status_code,
                          (request.get_data(as_text=True) or "")[:300]))
            db().commit()
        except sqlite3.Error:
            pass
        return resp
    return envoltorio


def empresa_json(e):
    d = dict(e)
    d["estado_pago_texto"] = ESTADOS_PAGO[d["estado_pago"]]
    return d


def requiere_empresa(cif):
    e = empresa_por_cif(cif)
    if e is None:
        raise LookupError(f"No existe ninguna empresa con CIF {normalizar_cif(cif)}")
    return e


@app.route("/api/salud")
def api_salud():
    return jsonify(ok=True, hora=ahora())


@app.route("/api/empresas", methods=["GET"])
@api
def api_listar_empresas():
    q = request.args.get("q", "")
    estado = request.args.get("estado_pago")
    sql = SQL_EMPRESAS + " WHERE (e.nombre LIKE ? OR e.cif LIKE ?)"
    params = [f"%{q}%", f"%{normalizar_cif(q) or q}%"]
    if estado:
        sql += " AND e.estado_pago = ?"
        params.append(estado)
    filas = db().execute(sql + " ORDER BY e.nombre", params).fetchall()
    return {"total": len(filas), "empresas": [empresa_json(f) for f in filas]}


@app.route("/api/empresas", methods=["POST"])
@api
def api_crear_empresa():
    d = request.get_json(force=True)
    cif = normalizar_cif(d["cif"])
    if empresa_por_cif(cif):
        raise ValueError(f"ya existe una empresa con CIF {cif}")
    campos = {k: d[k] for k in CAMPOS_EDITABLES if k in d}
    campos.setdefault("fecha_alta", date.today().isoformat())
    campos["cif"] = cif
    db().execute(f"INSERT INTO empresas ({', '.join(campos)}) VALUES ({', '.join('?' * len(campos))})",
                 tuple(campos.values()))
    db().commit()
    e = empresa_por_cif(cif)
    num = crear_caso(e["id"], "ALTA DE EMPRESA Y CONFIGURACIÓN INICIAL", "Alta empresa",
                     "Caso creado automáticamente al dar de alta la empresa por API.", "Email",
                     agente_automatizacion_id())
    resp = jsonify(empresa=empresa_json(e), caso_alta=num)
    resp.status_code = 201
    return resp


@app.route("/api/empresas/<cif>", methods=["GET"])
@api
def api_empresa(cif):
    return empresa_json(requiere_empresa(cif))


@app.route("/api/empresas/<cif>", methods=["PATCH"])
@api
def api_editar_empresa(cif):
    e = requiere_empresa(cif)
    d = request.get_json(force=True)
    campos = {k: d[k] for k in CAMPOS_EDITABLES if k in d}
    if not campos:
        raise ValueError(f"ningún campo editable. Permitidos: {', '.join(CAMPOS_EDITABLES)}")
    db().execute(f"UPDATE empresas SET {', '.join(f'{k} = ?' for k in campos)}, actualizado_en = ? WHERE id = ?",
                 (*campos.values(), ahora(), e["id"]))
    db().commit()
    return empresa_json(empresa_por_cif(cif))


@app.route("/api/empresas/<cif>/estado-pago", methods=["POST"])
@api
def api_estado_pago(cif):
    e = requiere_empresa(cif)
    d = request.get_json(force=True)
    agente = agente_por_nombre(d.get("agente") or "Automatización")
    if agente is None:
        raise ValueError(f"agente '{d.get('agente')}' no existe")
    cambiado = cambiar_estado_pago(e["id"], d["estado"], agente["id"],
                                   "automatizacion" if agente["rol"] == "sistema" else "manual", d.get("nota"))
    return {"cif": e["cif"], "estado_pago": d["estado"], "cambiado": cambiado}


@app.route("/api/empresas/<cif>/historial-pago")
@api
def api_historial(cif):
    e = requiere_empresa(cif)
    filas = db().execute("SELECT h.fecha, h.estado, a.nombre AS agente, h.origen, h.nota FROM historial_pago h "
                         "LEFT JOIN agentes a ON a.id = h.agente_id WHERE empresa_id = ? ORDER BY fecha DESC",
                         (e["id"],)).fetchall()
    return {"cif": e["cif"], "historial": [dict(f) for f in filas]}


@app.route("/api/deudoras")
@api
def api_deudoras():
    filas = db().execute("SELECT nombre, cif, ultima_factura_fecha, ultima_factura_importe FROM empresas "
                         "WHERE estado_pago='deudora' ORDER BY nombre").fetchall()
    return {"total": len(filas), "deudoras": [dict(f) for f in filas]}


@app.route("/api/deudoras/sincronizar", methods=["POST"])
@api
def api_sincronizar_deudoras():
    """
    Recibe la lista COMPLETA de CIFs del Excel de deudores y deja LOGI igual:
      - CIF en la lista y empresa al día        -> se marca deudora
      - Empresa deudora cuyo CIF no está en la lista -> se marca al día
        (si respetar_manuales=true, las marcadas a mano por un agente se conservan)
    Con simular=true solo devuelve lo que haría, sin cambiar nada.
    """
    d = request.get_json(force=True)
    cifs = {normalizar_cif(c) for c in d.get("cifs", []) if normalizar_cif(c)}
    respetar = bool(d.get("respetar_manuales", True))
    simular = bool(d.get("simular", False))
    auto = agente_automatizacion_id()
    res = {"marcadas_deudoras": [], "marcadas_al_dia": [], "ya_deudoras": [],
           "conservadas_manuales": [], "cif_no_encontrados": []}

    for cif in sorted(cifs):
        e = empresa_por_cif(cif)
        if e is None:
            res["cif_no_encontrados"].append(cif)
        elif e["estado_pago"] == "deudora":
            res["ya_deudoras"].append(cif)
        else:
            res["marcadas_deudoras"].append({"cif": cif, "nombre": e["nombre"]})
            if not simular:
                cambiar_estado_pago(e["id"], "deudora", auto, "automatizacion", "Sincronización con Excel de deudores")

    for e in db().execute("SELECT * FROM empresas WHERE estado_pago='deudora'").fetchall():
        if e["cif"] in cifs:
            continue
        ultima = db().execute("SELECT origen FROM historial_pago WHERE empresa_id=? AND estado='deudora' "
                              "ORDER BY fecha DESC LIMIT 1", (e["id"],)).fetchone()
        if respetar and (ultima is None or ultima["origen"] == "manual"):
            res["conservadas_manuales"].append({"cif": e["cif"], "nombre": e["nombre"]})
            continue
        res["marcadas_al_dia"].append({"cif": e["cif"], "nombre": e["nombre"]})
        if not simular:
            cambiar_estado_pago(e["id"], "al_dia", auto, "automatizacion", "Ya no figura en el Excel de deudores")

    res["simulacion"] = simular
    res["resumen"] = (f"{len(res['marcadas_deudoras'])} marcadas deudoras, {len(res['marcadas_al_dia'])} pasadas a al día, "
                      f"{len(res['conservadas_manuales'])} manuales conservadas, {len(res['cif_no_encontrados'])} CIF no encontrados")
    return res


@app.route("/api/empresas/<cif>/trabajadores", methods=["GET"])
@api
def api_trabajadores(cif):
    e = requiere_empresa(cif)
    filas = db().execute("SELECT * FROM trabajadores WHERE empresa_id = ? ORDER BY activo DESC, nombre", (e["id"],)).fetchall()
    return {"cif": e["cif"], "total_activos": sum(f["activo"] for f in filas), "trabajadores": [dict(f) for f in filas]}


@app.route("/api/empresas/<cif>/trabajadores", methods=["POST"])
@api
def api_alta_trabajador(cif):
    e = requiere_empresa(cif)
    d = request.get_json(force=True)
    cur = db().execute("INSERT INTO trabajadores (empresa_id, nombre, email, puesto, fecha_alta) VALUES (?,?,?,?,?)",
                       (e["id"], d["nombre"], d.get("email"), d.get("puesto"), d.get("fecha_alta") or date.today().isoformat()))
    db().execute("UPDATE empresas SET num_empleados = (SELECT COUNT(*) FROM trabajadores WHERE empresa_id=? AND activo=1) WHERE id=?",
                 (e["id"], e["id"]))
    db().commit()
    resp = jsonify(id=cur.lastrowid, empresa=e["nombre"], nombre=d["nombre"])
    resp.status_code = 201
    return resp


@app.route("/api/trabajadores/<int:tid>/baja", methods=["POST"])
@api
def api_baja_trabajador(tid):
    t = db().execute("SELECT * FROM trabajadores WHERE id = ?", (tid,)).fetchone()
    if t is None:
        raise LookupError("trabajador no encontrado")
    d = request.get_json(silent=True) or {}
    db().execute("UPDATE trabajadores SET activo = 0, fecha_baja = ? WHERE id = ?",
                 (d.get("fecha_baja") or date.today().isoformat(), tid))
    db().execute("UPDATE empresas SET num_empleados = (SELECT COUNT(*) FROM trabajadores WHERE empresa_id=? AND activo=1) WHERE id=?",
                 (t["empresa_id"], t["empresa_id"]))
    db().commit()
    return {"id": tid, "baja": True}


SQL_CASOS = ("SELECT c.*, e.nombre AS empresa, e.cif, a.nombre AS agente FROM casos c "
             "JOIN empresas e ON e.id = c.empresa_id LEFT JOIN agentes a ON a.id = c.agente_id")


@app.route("/api/casos", methods=["GET"])
@api
def api_listar_casos():
    where, params = ["1=1"], []
    a = request.args
    if a.get("estado"):
        where.append("c.estado = ?"); params.append(a["estado"])
    if a.get("cif"):
        where.append("e.cif = ?"); params.append(normalizar_cif(a["cif"]))
    if a.get("sin_asignar") == "true":
        where.append("c.agente_id IS NULL")
    if a.get("escalado") == "true":
        where.append("c.escalado = 1")
    if a.get("sensible") == "true":
        where.append("c.sensible = 1")
    if a.get("categoria"):
        where.append("c.categoria = ?"); params.append(a["categoria"])
    if a.get("actualizado_desde"):
        where.append("c.fecha_actualizacion >= ?"); params.append(a["actualizado_desde"])
    limite = min(int(a.get("limite", 100)), 500)
    filas = db().execute(SQL_CASOS + f" WHERE {' AND '.join(where)} ORDER BY c.fecha_actualizacion DESC LIMIT {limite}",
                         params).fetchall()
    return {"total": len(filas), "casos": [dict(f) for f in filas]}


@app.route("/api/casos/<int:caso_id>", methods=["GET"])
@api
def api_caso(caso_id):
    c = db().execute(SQL_CASOS + " WHERE c.id = ?", (caso_id,)).fetchone()
    if c is None:
        raise LookupError("caso no encontrado")
    notas = db().execute("SELECT n.fecha, n.texto, a.nombre AS agente FROM notas_caso n LEFT JOIN agentes a "
                         "ON a.id = n.agente_id WHERE caso_id = ? ORDER BY fecha", (caso_id,)).fetchall()
    return {**dict(c), "notas": [dict(n) for n in notas]}


@app.route("/api/casos", methods=["POST"])
@api
def api_crear_caso():
    d = request.get_json(force=True)
    e = requiere_empresa(d["cif"])
    categoria = d.get("categoria", "Incidencia")
    if categoria not in CATEGORIAS:
        raise ValueError(f"categoria no válida. Opciones: {', '.join(CATEGORIAS)}")
    agente = agente_por_nombre(d["agente"]) if d.get("agente") else None
    num = crear_caso(e["id"], d["asunto"], categoria, d.get("descripcion"), d.get("canal", "Email"),
                     agente["id"] if agente else None, d.get("escalado"), d.get("sensible"))
    resp = jsonify(numero=num, empresa=e["nombre"], url=url_for("ver_caso", caso_id=num, _external=True))
    resp.status_code = 201
    return resp


@app.route("/api/casos/<int:caso_id>", methods=["PATCH"])
@api
def api_editar_caso(caso_id):
    d = request.get_json(force=True)
    sets, params = [], []
    if "estado" in d:
        if d["estado"] not in ("abierto", "cerrado"):
            raise ValueError("estado debe ser 'abierto' o 'cerrado'")
        sets += ["estado = ?", "fecha_cierre = ?"]
        params += [d["estado"], ahora() if d["estado"] == "cerrado" else None]
    if "agente" in d:
        ag = agente_por_nombre(d["agente"]) if d["agente"] else None
        if d["agente"] and ag is None:
            raise ValueError(f"agente '{d['agente']}' no existe")
        sets.append("agente_id = ?"); params.append(ag["id"] if ag else None)
    for campo in ("escalado", "sensible"):
        if campo in d:
            sets.append(f"{campo} = ?"); params.append(int(bool(d[campo])))
    if "categoria" in d:
        sets.append("categoria = ?"); params.append(d["categoria"])
    if not sets:
        raise ValueError("nada que actualizar (estado, agente, escalado, sensible, categoria)")
    sets.append("fecha_actualizacion = ?"); params.append(ahora())
    cur = db().execute(f"UPDATE casos SET {', '.join(sets)} WHERE id = ?", (*params, caso_id))
    if cur.rowcount == 0:
        raise LookupError("caso no encontrado")
    db().commit()
    return api_caso.__wrapped__(caso_id)


@app.route("/api/casos/<int:caso_id>/notas", methods=["POST"])
@api
def api_nota_caso(caso_id):
    d = request.get_json(force=True)
    agente = agente_por_nombre(d.get("agente") or "Automatización")
    if db().execute("SELECT 1 FROM casos WHERE id = ?", (caso_id,)).fetchone() is None:
        raise LookupError("caso no encontrado")
    db().execute("INSERT INTO notas_caso (caso_id, agente_id, texto, fecha) VALUES (?,?,?,?)",
                 (caso_id, agente["id"] if agente else None, d["texto"], ahora()))
    db().execute("UPDATE casos SET fecha_actualizacion = ? WHERE id = ?", (ahora(), caso_id))
    db().commit()
    resp = jsonify(ok=True, caso=caso_id)
    resp.status_code = 201
    return resp


@app.errorhandler(404)
def no_encontrado(_e):
    if request.path.startswith("/api/"):
        return jsonify(error="ruta no encontrada"), 404
    return render_template("404.html"), 404


if __name__ == "__main__":
    seed.asegurar_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
