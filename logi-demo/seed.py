"""
Genera datos de ejemplo (inventados) para LOGI DEMO.

Uso:
    python seed.py            # crea logi.db si no existe y la rellena
    python seed.py --reset    # borra logi.db y la vuelve a crear
"""
import os
import random
import sqlite3
import sys
from datetime import date, datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("LOGI_DB", os.path.join(BASE, "logi.db"))

rng = random.Random(2026)  # semilla fija: siempre los mismos datos
HOY = date(2026, 11, 11)

AGENTES = [
    ("Andrés Varela", "soporte"),
    ("Lucía Pazos", "soporte"),
    ("Marcos Seoane", "soporte"),
    ("Iria Fandiño", "soporte"),
    ("Brais Lema", "soporte"),
    ("Nerea Castiñeira", "ventas"),
    ("Hugo Otero Blanco", "ventas"),
    ("Sabela Rial", "ventas"),
    ("Automatización", "sistema"),
]

PREFIJOS = ["Talleres", "Clínica Dental", "Asesoría", "Construcciones", "Panadería", "Transportes",
            "Restaurante", "Ferretería", "Distribuciones", "Gestoría", "Óptica", "Farmacia",
            "Carpintería", "Instalaciones", "Academia", "Hotel", "Cafetería", "Limpiezas",
            "Fisioterapia", "Electricidad", "Inmobiliaria", "Peluquería", "Conservas", "Viveros"]
NUCLEOS = ["Atlántico", "Mariñas", "Breogán", "Orzán", "Riazor", "Monelos", "Cantón", "Mera",
           "Sada", "Betanzos", "Arteixo", "Oleiros", "Ferrol", "Santiago", "Lugo", "Miño",
           "Ortegal", "Finisterre", "Corrubedo", "Rías Altas", "Bergantiños", "Ézaro", "Cíes",
           "Ons", "Sálvora", "Faro", "Torre", "Muralla", "Alameda", "Galeras", "Xubia", "Eume"]
FORMAS = ["S.L.", "S.L.U.", "S.A.", "S.L.L."]
CIUDADES = [("A Coruña", "150"), ("Santiago de Compostela", "157"), ("Ferrol", "154"),
            ("Lugo", "270"), ("Vigo", "362"), ("Ourense", "320"), ("Pontevedra", "360"),
            ("Oleiros", "151"), ("Arteixo", "151"), ("Madrid", "280"), ("Oviedo", "330")]
CALLES = ["Rúa Real", "Avenida da Mariña", "Rúa San Andrés", "Ronda de Outeiro", "Avenida de Arteixo",
          "Rúa Juan Flórez", "Praza de Lugo", "Rúa Barcelona", "Avenida Alfonso Molina",
          "Rúa Nova", "Avenida de Madrid", "Rúa do Hórreo", "Rúa Policarpo Sanz"]
NOMBRES = ["Ana", "Xoán", "María", "Pablo", "Laura", "Diego", "Carmen", "Iago", "Paula", "Martín",
           "Uxía", "Antón", "Noa", "Rubén", "Alba", "Manuel", "Elena", "Sergio", "Rocío", "Adrián",
           "Olalla", "Fernando", "Cristina", "Javier", "Sara", "Óscar", "Lara", "Álvaro", "Inés", "Raúl"]
APELLIDOS = ["García", "Fernández", "López", "Rodríguez", "Vázquez", "Pérez", "Martínez", "González",
             "Castro", "Rey", "Sánchez", "Díaz", "Gómez", "Suárez", "Varela", "Iglesias", "Pena",
             "Barreiro", "Seijo", "Couceiro", "Mosquera", "Lago", "Novo", "Souto", "Freire", "Rivas"]
PUESTOS = ["Administración", "Dependiente/a", "Operario/a", "Técnico/a", "Responsable de turno",
           "Recepción", "Cocina", "Sala", "Conductor/a", "Comercial", "Limpieza", "Almacén"]

PLANTILLAS_CASO = [
    ("Alta empresa", "ALTA DE EMPRESA Y CONFIGURACIÓN INICIAL", "Alta de la empresa en la plataforma, creación de gerente y configuración de horarios."),
    ("Alta trabajador", "ALTA DE TRABAJADOR", "El cliente solicita dar de alta a un nuevo trabajador."),
    ("Alta trabajador", "ALTA DE VARIOS TRABAJADORES", "Envían por email un listado para dar de alta a varios trabajadores."),
    ("Baja trabajador", "BAJA DE TRABAJADOR", "Solicitan dar de baja a un trabajador que finaliza contrato."),
    ("Solicitud de baja", "SOLICITUD DE BAJA DEL SERVICIO", "La empresa comunica que quiere darse de baja del servicio."),
    ("Error de fichaje", "ERROR DE FICHAJE", "Un trabajador no puede fichar desde la app móvil."),
    ("Error de fichaje", "FICHAJE DUPLICADO", "Aparecen fichajes duplicados en el informe mensual."),
    ("Error de fichaje", "GEOLOCALIZACIÓN NO FUNCIONA", "La app no registra la ubicación al fichar."),
    ("Facturación", "CONSULTA SOBRE FACTURA", "El cliente pregunta por el importe de la última factura."),
    ("Facturación", "CAMBIO DE FORMA DE PAGO", "Quieren pasar de transferencia a domiciliación."),
    ("Facturación", "RECLAMACIÓN DE IMPAGO", "Se contacta con el cliente por factura pendiente."),
    ("Formación", "FORMACIÓN AL GERENTE", "Sesión de formación sobre informes y gestión de ausencias."),
    ("Formación", "FORMACIÓN A ENCARGADOS", "Formación para encargados sobre validación de fichajes."),
    ("Incidencia", "NO LLEGAN LOS CORREOS DE INCIDENCIAS", "El gerente no recibe los avisos de olvidos de fichaje."),
    ("Incidencia", "ERROR AL EXPORTAR INFORME", "El informe en Excel sale vacío al exportar."),
    ("Consulta", "CONSULTA SOBRE VACACIONES", "Dudas sobre cómo configurar el calendario de vacaciones."),
    ("Consulta", "CAMBIO DE GERENTE", "Cambia la persona responsable de la cuenta."),
]


def cif_valido(letra: str, numero7: str) -> str:
    """Calcula un CIF con dígito de control correcto."""
    pares = sum(int(numero7[i]) for i in (1, 3, 5))
    impares = 0
    for i in (0, 2, 4, 6):
        d = int(numero7[i]) * 2
        impares += d // 10 + d % 10
    control = (10 - (pares + impares) % 10) % 10
    return f"{letra}{numero7}{control}"


def fecha_aleatoria(desde: date, hasta: date) -> date:
    return desde + timedelta(days=rng.randint(0, (hasta - desde).days))


def dt(d: date, h=None, m=None) -> str:
    h = rng.randint(8, 18) if h is None else h
    m = rng.randint(0, 59) if m is None else m
    return datetime(d.year, d.month, d.day, h, m).strftime("%Y-%m-%d %H:%M:%S")


def slug(texto: str) -> str:
    t = texto.lower()
    for a, b in zip("áéíóúüñ", "aeiouun"):
        t = t.replace(a, b)
    return "".join(c for c in t if c.isalnum())


def crear(conn: sqlite3.Connection):
    with open(os.path.join(BASE, "schema.sql"), encoding="utf-8") as f:
        conn.executescript(f.read())

    cur = conn.cursor()
    cur.executemany("INSERT INTO agentes (nombre, rol) VALUES (?, ?)", AGENTES)
    agentes = {r[1]: r[0] for r in cur.execute("SELECT id, nombre FROM agentes")}
    soporte_ids = [agentes[n] for n, r in AGENTES if r == "soporte"]
    ventas_ids = [agentes[n] for n, r in AGENTES if r == "ventas"]

    usados = set()
    empresas = []
    for i in range(48):
        while True:
            nombre = f"{rng.choice(PREFIJOS)} {rng.choice(NUCLEOS)}"
            if nombre not in usados:
                usados.add(nombre)
                break
        forma = rng.choice(FORMAS)
        letra = "A" if forma == "S.A." else "B"
        cif = cif_valido(letra, f"{rng.randint(1500000, 9999999):07d}")
        ciudad, cp = rng.choice(CIUDADES)
        gerente = f"{rng.choice(NOMBRES)} {rng.choice(APELLIDOS)} {rng.choice(APELLIDOS)}"
        g1, g2 = gerente.split()[0], gerente.split()[1]
        alta = fecha_aleatoria(date(2022, 1, 10), date(2026, 10, 20))
        n_emp = rng.choice([2, 3, 4, 5, 6, 7, 8, 10, 12, 15, 18, 22, 25, 30, 40])
        fin_contrato = None
        if rng.random() < 0.55:
            fin_contrato = (alta + timedelta(days=365 * rng.choice([1, 2, 3]))).isoformat()
        impl_g = (alta + timedelta(days=rng.randint(1, 7))).isoformat() if rng.random() < 0.85 else None
        impl_e = (alta + timedelta(days=rng.randint(5, 20))).isoformat() if impl_g and rng.random() < 0.8 else None
        seguimiento = (alta + timedelta(days=30)).isoformat() if impl_e else None
        fichajes_ant = n_emp * rng.randint(30, 44) if impl_e else 0
        fichajes_act = int(fichajes_ant * 11 / 30 * rng.uniform(0.7, 1.1)) if impl_e else 0
        importe = round(n_emp * rng.choice([2.5, 3.0, 3.5]) * 1.21 + 9.9, 2)
        ult_fact = date(2026, 11, 1) if alta < date(2026, 11, 1) else None
        dominio = slug(nombre.split()[-1]) + ".es"
        empresas.append(dict(
            nombre=f"{nombre}, {forma}", cif=cif, num_empleados=n_emp,
            encargado=1 if n_emp >= 10 and rng.random() < 0.7 else 0,
            gerente=gerente,
            telefono=f"{rng.choice(['981', '981', '881', '6', '7'])}{rng.randint(100000, 999999)}".ljust(9, "0")[:9],
            email=f"{slug(g1)}.{slug(g2)}@{dominio}",
            direccion=f"{rng.choice(CALLES)}, {rng.randint(1, 250)}, {ciudad}, {cp}{rng.randint(0, 99):02d}",
            agente_venta_id=rng.choice(ventas_ids),
            fecha_alta=alta.isoformat(), implementacion_gerente=impl_g,
            implementacion_empleados=impl_e, seguimiento_mes=seguimiento,
            correos_incidencias=f"incidencias@{dominio}" if rng.random() < 0.6 else None,
            fichajes_mes_actual=fichajes_act, fichajes_mes_anterior=fichajes_ant,
            forma_pago=rng.choice(["TRANSFERENCIA", "DOMICILIACION", "DOMICILIACION", "TARJETA"]),
            fondos_europeos=rng.choice(["No tiene"] * 4 + ["Kit Digital"]),
            fecha_fin_contrato=fin_contrato,
            ultima_factura_fecha=ult_fact.isoformat() if ult_fact else None,
            ultima_factura_importe=importe if ult_fact else None,
            resena_estado=rng.choice(["no_solicitada"] * 3 + ["solicitada", "realizada"]),
        ))

    cols = list(empresas[0].keys())
    for e in empresas:
        if e["resena_estado"] != "no_solicitada":
            e["resena_agente_id"] = rng.choice(soporte_ids)
        else:
            e["resena_agente_id"] = None
    cols.append("resena_agente_id")
    cur.executemany(
        f"INSERT INTO empresas ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
        [tuple(e[c] for c in cols) for e in empresas],
    )
    filas = cur.execute("SELECT id, fecha_alta, num_empleados FROM empresas").fetchall()

    # Deudoras: 7 empresas, algunas con historial de idas y vueltas
    deudoras = rng.sample(filas, 7)
    for (eid, alta, _) in deudoras:
        d_alta = date.fromisoformat(alta)
        if rng.random() < 0.4 and d_alta < date(2026, 3, 1):
            f1 = fecha_aleatoria(d_alta + timedelta(days=60), date(2026, 5, 1))
            f2 = f1 + timedelta(days=rng.randint(10, 40))
            cur.execute("INSERT INTO historial_pago (empresa_id, fecha, estado, agente_id) VALUES (?,?,?,?)",
                        (eid, dt(f1), "deudora", rng.choice(soporte_ids)))
            cur.execute("INSERT INTO historial_pago (empresa_id, fecha, estado, agente_id) VALUES (?,?,?,?)",
                        (eid, dt(f2), "al_dia", rng.choice(soporte_ids)))
        f = fecha_aleatoria(max(d_alta, date(2026, 8, 1)), date(2026, 11, 10))
        cur.execute("INSERT INTO historial_pago (empresa_id, fecha, estado, agente_id) VALUES (?,?,?,?)",
                    (eid, dt(f), "deudora", rng.choice(soporte_ids)))
        cur.execute("UPDATE empresas SET estado_pago='deudora' WHERE id=?", (eid,))

    # Algunas empresas con solicitud de baja
    for (eid, _, _) in rng.sample([f for f in filas if f not in deudoras], 3):
        cur.execute("UPDATE empresas SET estado_cliente='baja_solicitada' WHERE id=?", (eid,))

    # Trabajadores
    for (eid, alta, n_emp) in filas:
        d_alta = date.fromisoformat(alta)
        for _ in range(n_emp):
            nom = f"{rng.choice(NOMBRES)} {rng.choice(APELLIDOS)} {rng.choice(APELLIDOS)}"
            cur.execute(
                "INSERT INTO trabajadores (empresa_id, nombre, email, puesto, fecha_alta) VALUES (?,?,?,?,?)",
                (eid, nom, f"{slug(nom.split()[0])}.{slug(nom.split()[1])}{rng.randint(1, 99)}@correo.test",
                 rng.choice(PUESTOS), fecha_aleatoria(d_alta, HOY).isoformat()))
        # alguna baja histórica
        if rng.random() < 0.4:
            nom = f"{rng.choice(NOMBRES)} {rng.choice(APELLIDOS)} {rng.choice(APELLIDOS)}"
            fa = fecha_aleatoria(d_alta, HOY - timedelta(days=30))
            cur.execute(
                "INSERT INTO trabajadores (empresa_id, nombre, email, puesto, fecha_alta, fecha_baja, activo) "
                "VALUES (?,?,?,?,?,?,0)",
                (eid, nom, None, rng.choice(PUESTOS), fa.isoformat(),
                 fecha_aleatoria(fa, HOY).isoformat()))

    # Casos
    num_caso = 16010
    casos = []
    for (eid, alta, _) in filas:
        d_alta = date.fromisoformat(alta)
        casos.append((eid, d_alta, PLANTILLAS_CASO[0]))
        for _ in range(rng.randint(0, 7)):
            casos.append((eid, fecha_aleatoria(d_alta, HOY), rng.choice(PLANTILLAS_CASO[1:])))
    # Actividad reciente (últimas 3 semanas) para que haya casos abiertos
    for _ in range(40):
        eid, alta, _ = rng.choice(filas)
        desde = max(date.fromisoformat(alta), HOY - timedelta(days=20))
        casos.append((eid, fecha_aleatoria(desde, HOY), rng.choice(PLANTILLAS_CASO[1:])))
    casos.sort(key=lambda c: c[1])
    for (eid, f, (cat, asunto, desc)) in casos:
        num_caso += rng.randint(1, 12)
        reciente = (HOY - f).days < 20
        estado = "abierto" if reciente and rng.random() < 0.75 else "cerrado"
        agente = rng.choice(soporte_ids)
        if estado == "abierto" and rng.random() < 0.3:
            agente = None  # sin asignar
        escalado = 1 if cat in ("Error de fichaje", "Incidencia") and rng.random() < 0.35 else 0
        sensible = 1 if cat in ("Solicitud de baja", "Facturación") and rng.random() < 0.3 else 0
        apertura = dt(f)
        actualiz = dt(min(f + timedelta(days=rng.randint(0, 3)), HOY))
        if actualiz < apertura:
            actualiz = apertura
        cierre = actualiz if estado == "cerrado" else None
        cur.execute(
            "INSERT INTO casos (id, empresa_id, asunto, categoria, descripcion, canal, estado, agente_id, "
            "escalado, sensible, fecha_apertura, fecha_actualizacion, fecha_cierre) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (num_caso, eid, asunto, cat, desc, rng.choice(["Teléfono", "Email", "Email", "WhatsApp", "Chat"]),
             estado, agente, escalado, sensible, apertura, actualiz, cierre))
        if agente:
            cur.execute("INSERT INTO notas_caso (caso_id, agente_id, texto, fecha) VALUES (?,?,?,?)",
                        (num_caso, agente, "Contactamos con el cliente y revisamos la incidencia.", actualiz))

    conn.commit()
    n_emp = cur.execute("SELECT COUNT(*) FROM empresas").fetchone()[0]
    n_cas = cur.execute("SELECT COUNT(*) FROM casos").fetchone()[0]
    n_tra = cur.execute("SELECT COUNT(*) FROM trabajadores").fetchone()[0]
    print(f"Base de datos creada en {DB_PATH}: {n_emp} empresas, {n_cas} casos, {n_tra} trabajadores.")


def asegurar_db():
    """Crea y rellena la base de datos si aún no existe (lo usa app.py al arrancar)."""
    if not os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON")
        crear(conn)
        conn.close()


if __name__ == "__main__":
    if "--reset" in sys.argv and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    if os.path.exists(DB_PATH):
        print(f"{DB_PATH} ya existe. Usa --reset para regenerarla.")
    else:
        asegurar_db()
