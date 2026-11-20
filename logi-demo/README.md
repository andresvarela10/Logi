# LOGI DEMO

Réplica de ejemplo de la herramienta de soporte (LOGI) para probar automatizaciones con Make **sin tocar datos reales**. Todos los datos son inventados.

- **Web** con las mismas pantallas: Escritorio, búsqueda de empresas y casos, ficha de empresa, estado de pago con histórico, reseña App Store, casos, trabajadores e informes.
- **Base de datos** SQLite (`logi.db`) con 48 empresas, ~260 casos y ~650 trabajadores. Se crea sola la primera vez que arrancas.
- **API REST** para que Make (u otra herramienta) lea y escriba en la plataforma.

## Estructura

| Archivo | Qué es |
|---|---|
| `app.py` | La aplicación: pantallas + API |
| `schema.sql` | Estructura de la base de datos (tablas y campos) |
| `seed.py` | Genera los datos de ejemplo |
| `templates/`, `static/` | HTML y estilos de las pantallas |
| `deudores_ejemplo.xlsx` | Excel de deudores de prueba para la sincronización |

### Tablas
- `empresas`: la ficha del cliente. El **CIF** es la clave para las integraciones. `fecha_fin_contrato` vacía significa "No consta", nunca 01/01/1970.
- `historial_pago`: cada cambio de deudora / al día, con fecha, agente y origen (`manual` o `automatizacion`).
- `casos` y `notas_caso`: tickets y su seguimiento (sin asignar, escalado, sensible, abierto/cerrado).
- `trabajadores`: altas y bajas de empleados de cada empresa.
- `agentes`: incluye el agente **"Automatización"**, que firma lo que hace Make.
- `log_api`: registro de cada llamada a la API (se ve en *Informes → Registro de la API*).

## Arrancar en tu ordenador

Necesitas Python 3.10 o superior.

```bash
pip install -r requirements.txt
python app.py
```

Abre http://localhost:5000. En el avatar de arriba a la derecha eliges con qué agente trabajas.

Para volver a los datos iniciales: `python seed.py --reset`

## Que Make pueda llegar (publicarlo en internet)

Make está en la nube, así que no ve tu `localhost`. Tienes dos opciones:

**A. Render (gratis, recomendado)**
1. Sube esta carpeta a un repositorio de GitHub.
2. En render.com: *New → Web Service* y elige el repositorio.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Variables de entorno: `LOGI_API_KEY` con una clave tuya.
6. Te dará una URL tipo `https://logi-demo.onrender.com`.

En el plan gratis, la base de datos vuelve a los datos iniciales cada vez que se redespliega. Para una demo no es un problema.

**B. ngrok (rápido, mientras tienes el ordenador encendido)**
`ngrok http 5000` te da una URL pública temporal.

## API

La documentación completa está en la web: **/api-docs**.

- Cabecera: `X-API-Key: demo-1234` (cámbiala con la variable `LOGI_API_KEY`).
- Las empresas se identifican por CIF. Acepta minúsculas, espacios y guiones.

### Sincronizar el Excel de deudores

```
POST /api/deudoras/sincronizar
{ "cifs": ["B12345674", "..."], "respetar_manuales": true, "simular": false }
```

Envía la lista **completa** de CIFs del Excel cada vez:
- Si un CIF está en el Excel y la empresa está al día, pasa a **deudora**.
- Si una empresa es deudora y ya no está en el Excel, pasa a **al día**.
- Con `respetar_manuales: true` (por defecto), las empresas que marcó a mano un agente no se tocan.
- Con `simular: true` te devuelve lo que haría, sin cambiar nada.

**Escenario en Make:** Programar cada X minutos → Excel / Google Sheets *Search rows* → *Array aggregator* (campo CIF) → HTTP *Make a request* a este endpoint.

**Prueba con `deudores_ejemplo.xlsx`:** el Excel tiene una empresa nueva (Restaurante Torre) y le falta Academia Eume.
- Con `respetar_manuales: true`, Restaurante Torre pasa a deudora. Academia Eume se queda como está, porque la marcó un agente a mano y aparece en `conservadas_manuales`.
- Con `false`, Academia Eume también pasa a al día.

## Asistente de Soporte (chatbot)

Prototipo de chatbot para que **empleados** y **administradores** resuelvan sus dudas sobre LogRoot sin llamar a Soporte. Responde solo con la documentación de la plataforma y, si no puede resolver algo, deriva al responsable de la empresa o a Soporte LogRoot.

- **Demo (vista de cliente):** `/asistente`
- **Conversaciones y valoraciones (vista interna):** *Informes → Conversaciones del asistente* (`/informes/asistente`)

### Cómo funciona
1. El usuario elige si es **empleado** o **administrador**.
2. Navega con botones: **categoría → pregunta**, y obtiene una respuesta fija sacada de la base de conocimiento.
3. O escribe su duda con sus palabras: la responde la **IA** (o el buscador por palabras clave en modo demo).
4. Después de cada respuesta: **"¿Te ha servido?"**. Si contesta que no, el empleado recibe la indicación de hablar con su responsable (o con Soporte si es técnico) y el administrador, los datos de contacto de Soporte.

### Archivos
| Archivo | Qué es |
|---|---|
| `asistente.py` | Rutas y lógica del asistente (se engancha a `app.py` con `asistente.registrar(app, db)`) |
| `conocimiento/base_conocimiento.md` | **Preguntas y respuestas.** El árbol de botones se genera solo a partir de sus títulos (`## 1. EMPLEADO`, `### 1.1 Fichajes`, `**E-F1. Pregunta**`) |
| `conocimiento/instrucciones_bot.md` | Instrucciones (prompt de sistema) para la IA |
| `templates/asistente.html` | Página de demo |
| `templates/asistente_log.html` | Informe de conversaciones |
| `static/asistente.js`, `static/asistente.css` | Widget del chat (se puede incrustar en cualquier página) |

Para cambiar una respuesta o añadir una pregunta, **solo hay que editar `base_conocimiento.md`** y volver a desplegar. Las marcas `[PENDIENTE]` y `[REVISAR]` no se muestran al usuario. Si una respuesta tiene `[PENDIENTE]`, el asistente añade los datos de contacto de Soporte.

### Activar la IA
Sin configurar nada, funciona en **modo demo**: los botones van igual y el texto libre se responde con un buscador por palabras clave.

Para activar la IA, añade estas variables de entorno en Render (*Environment*):

| Variable | Valor |
|---|---|
| `ASISTENTE_PROVEEDOR` | `anthropic`, `openai` o `gemini` |
| `ASISTENTE_API_KEY` | La clave de la API del proveedor. **Nunca la pongas en el código ni en GitHub.** |
| `ASISTENTE_MODELO` | El modelo, según la documentación del proveedor (obligatorio en `openai` y `gemini`) |

Si la IA falla (clave incorrecta, sin saldo, caída del proveedor), el asistente sigue respondiendo en modo demo y el fallo queda registrado con origen `error`.

**Protección de la clave:** máximo 15 mensajes por minuto y por IP, con mensajes de 1.000 caracteres como máximo y 12 mensajes de historial.

En el plan gratis de Render, el registro de conversaciones se borra en cada redespliegue (igual que el resto de la base de datos).

### Incrustar el widget en otra página
```html
<link rel="stylesheet" href="https://TU-URL/static/asistente.css">
<div id="lr-chat" data-api="https://TU-URL/api/asistente"></div>
<script src="https://TU-URL/static/asistente.js"></script>
```
