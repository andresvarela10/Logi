-- =====================================================================
--  LOGI DEMO · Esquema de base de datos (SQLite)
--  Réplica de ejemplo de la herramienta de soporte. Datos inventados.
-- =====================================================================

PRAGMA foreign_keys = ON;

-- Agentes de soporte / ventas (también "Automatización" para los cambios hechos por Make)
CREATE TABLE IF NOT EXISTS agentes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre        TEXT    NOT NULL UNIQUE,
    rol           TEXT    NOT NULL DEFAULT 'soporte',   -- soporte | ventas | sistema
    activo        INTEGER NOT NULL DEFAULT 1
);

-- Ficha de cliente (empresa)
CREATE TABLE IF NOT EXISTS empresas (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre                    TEXT    NOT NULL,
    cif                       TEXT    NOT NULL UNIQUE,      -- clave para integraciones
    num_empleados             INTEGER NOT NULL DEFAULT 0,
    encargado                 INTEGER NOT NULL DEFAULT 0,   -- 0 = No, 1 = Sí
    gerente                   TEXT,
    telefono                  TEXT,
    email                     TEXT,
    direccion                 TEXT,
    agente_venta_id           INTEGER REFERENCES agentes(id),
    -- Puesta en marcha
    fecha_alta                TEXT    NOT NULL,             -- YYYY-MM-DD
    implementacion_gerente    TEXT,                         -- fecha o NULL
    implementacion_empleados  TEXT,
    seguimiento_mes           TEXT,
    correos_incidencias       TEXT,                         -- separados por coma
    -- Actividad
    fichajes_mes_actual       INTEGER NOT NULL DEFAULT 0,
    fichajes_mes_anterior     INTEGER NOT NULL DEFAULT 0,
    forma_pago                TEXT    NOT NULL DEFAULT 'TRANSFERENCIA', -- TRANSFERENCIA | DOMICILIACION | TARJETA
    fondos_europeos           TEXT    NOT NULL DEFAULT 'No tiene',      -- No tiene | Kit Digital | ...
    fecha_fin_contrato        TEXT,                         -- NULL = "No consta" (nunca 01/01/1970)
    aviso_fin_contrato_enviado TEXT,                        -- cuándo se avisó de que quedan <= 6 meses
    -- Facturación
    ultima_factura_fecha      TEXT,
    ultima_factura_importe    REAL,
    -- Estado de pago
    estado_pago               TEXT    NOT NULL DEFAULT 'al_dia' CHECK (estado_pago IN ('al_dia','deudora')),
    -- Estado comercial
    estado_cliente            TEXT    NOT NULL DEFAULT 'activo' CHECK (estado_cliente IN ('activo','baja_solicitada','baja')),
    -- Reseña App Store
    resena_estado             TEXT    NOT NULL DEFAULT 'no_solicitada' CHECK (resena_estado IN ('no_solicitada','solicitada','realizada','rechazada')),
    resena_agente_id          INTEGER REFERENCES agentes(id),
    creado_en                 TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    actualizado_en            TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_empresas_nombre ON empresas(nombre);
CREATE INDEX IF NOT EXISTS idx_empresas_estado_pago ON empresas(estado_pago);

-- Histórico de estado de pago (lo que muestra el modal "Histórico de estado de pago")
CREATE TABLE IF NOT EXISTS historial_pago (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id   INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    fecha        TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    estado       TEXT    NOT NULL CHECK (estado IN ('al_dia','deudora')),
    agente_id    INTEGER REFERENCES agentes(id),
    origen       TEXT    NOT NULL DEFAULT 'manual' CHECK (origen IN ('manual','automatizacion')),
    nota         TEXT
);

CREATE INDEX IF NOT EXISTS idx_historial_empresa ON historial_pago(empresa_id, fecha);

-- Trabajadores dados de alta en cada empresa
CREATE TABLE IF NOT EXISTS trabajadores (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id   INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    nombre       TEXT    NOT NULL,
    email        TEXT,
    puesto       TEXT,
    fecha_alta   TEXT    NOT NULL,
    fecha_baja   TEXT,
    activo       INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_trabajadores_empresa ON trabajadores(empresa_id);

-- Casos (tickets / interacciones con el cliente)
CREATE TABLE IF NOT EXISTS casos (
    id                INTEGER PRIMARY KEY,                  -- Nº de caso (p. ej. 18595)
    empresa_id        INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    asunto            TEXT    NOT NULL,
    categoria         TEXT    NOT NULL DEFAULT 'Incidencia',
        -- Alta empresa | Alta trabajador | Baja trabajador | Solicitud de baja | Error de fichaje
        -- Facturación | Formación | Incidencia | Consulta
    descripcion       TEXT,
    canal             TEXT    NOT NULL DEFAULT 'Teléfono',  -- Teléfono | Email | WhatsApp | Chat
    estado            TEXT    NOT NULL DEFAULT 'abierto' CHECK (estado IN ('abierto','cerrado')),
    agente_id         INTEGER REFERENCES agentes(id),       -- NULL = sin asignar
    escalado          INTEGER NOT NULL DEFAULT 0,           -- escalado a desarrollo
    sensible          INTEGER NOT NULL DEFAULT 0,
    fecha_apertura    TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    fecha_actualizacion TEXT  NOT NULL DEFAULT (datetime('now','localtime')),
    fecha_cierre      TEXT
);

CREATE INDEX IF NOT EXISTS idx_casos_empresa ON casos(empresa_id);
CREATE INDEX IF NOT EXISTS idx_casos_estado ON casos(estado, agente_id);

-- Notas / respuestas dentro de un caso
CREATE TABLE IF NOT EXISTS notas_caso (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    caso_id    INTEGER NOT NULL REFERENCES casos(id) ON DELETE CASCADE,
    agente_id  INTEGER REFERENCES agentes(id),
    texto      TEXT    NOT NULL,
    fecha      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

-- Registro de llamadas a la API (útil para depurar escenarios de Make)
CREATE TABLE IF NOT EXISTS log_api (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha     TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    metodo    TEXT NOT NULL,
    ruta      TEXT NOT NULL,
    estado    INTEGER,
    resumen   TEXT
);
