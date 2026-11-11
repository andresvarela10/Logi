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
