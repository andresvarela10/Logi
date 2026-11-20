/*
 * Widget del Asistente de Soporte LogRoot.
 * Uso: <div id="lr-chat" data-api="/api/asistente" data-abierto="1"></div><script src="asistente.js"></script>
 *
 * Flujo: rol → categoría → pregunta (botones, respuestas fijas) o texto libre (IA / modo demo).
 * Después de cada respuesta: "¿Te ha servido?" Sí / No → si no, deriva al responsable o a Soporte.
 */
(function () {
  "use strict";

  const raiz = document.getElementById("lr-chat");
  if (!raiz) return;
  const API = (raiz.dataset.api || "/api/asistente").replace(/\/$/, "");

  const estado = {
    arbol: null, roles: {}, contacto: {}, modo: "demo", titulos: {},
    rol: null, historial: [], esperando: false,
    sesion: (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random()).slice(0, 36),
  };

  // ------------------------------------------------------------------ DOM base
  raiz.innerHTML = `
    <button class="lr-burbuja" type="button" aria-label="Abrir el asistente de ayuda">
      <span class="lr-burbuja-ico">💬</span><span class="lr-burbuja-txt">¿Necesitas ayuda?</span>
    </button>
    <section class="lr-panel" role="dialog" aria-label="Asistente de Soporte LogRoot">
      <header class="lr-cab">
        <div class="lr-cab-logo">✱</div>
        <div class="lr-cab-txt"><strong>LogRoot Ayuda</strong><span class="lr-cab-sub">Asistente de Soporte</span></div>
        <button class="lr-cab-btn lr-reiniciar" type="button" title="Empezar de nuevo">↺</button>
        <button class="lr-cab-btn lr-cerrar" type="button" title="Cerrar">✕</button>
      </header>
      <div class="lr-mensajes" aria-live="polite"></div>
      <form class="lr-entrada" autocomplete="off">
        <input type="text" maxlength="1000" placeholder="Escribe tu duda…" aria-label="Escribe tu duda">
        <button type="submit" aria-label="Enviar">➤</button>
      </form>
    </section>`;

  const panel = raiz.querySelector(".lr-panel");
  const zona = raiz.querySelector(".lr-mensajes");
  const form = raiz.querySelector(".lr-entrada");
  const input = form.querySelector("input");

  raiz.querySelector(".lr-burbuja").addEventListener("click", () => abrir(true));
  raiz.querySelector(".lr-cerrar").addEventListener("click", () => abrir(false));
  raiz.querySelector(".lr-reiniciar").addEventListener("click", reiniciar);
  form.addEventListener("submit", (e) => { e.preventDefault(); enviarTexto(input.value); });

  function abrir(si) {
    raiz.classList.toggle("lr-abierto", si);
    if (si) setTimeout(() => input.focus(), 50);
  }

  // ------------------------------------------------------------------ Markdown mínimo y seguro
  function escapar(t) {
    return t.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function enLinea(t) {
    let h = escapar(t);
    h = h.replace(/`([^`]+)`/g, "<code>$1</code>");
    h = h.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    h = h.replace(/(^|[^*\w])\*([^*\n]+)\*(?!\w)/g, "$1<em>$2</em>");
    // Contactos clicables
    const tel = (estado.contacto.telefono || "981 111 114");
    const wa = (estado.contacto.whatsapp || "662 488 889");
    const mail = (estado.contacto.email || "soporte@logrootrh.com");
    h = h.split(escapar(mail)).join(`<a href="mailto:${mail}">${mail}</a>`);
    h = h.replace(new RegExp("(WhatsApp\\s*:?\\s*)?" + wa.replace(/ /g, "\\s?"), "g"),
      (m) => `<a href="https://wa.me/34${wa.replace(/\s/g, "")}" target="_blank" rel="noopener">${m}</a>`);
    h = h.replace(new RegExp(tel.replace(/ /g, "\\s?"), "g"),
      (m) => `<a href="tel:+34${tel.replace(/\s/g, "")}">${m}</a>`);
    // Referencias a otras respuestas: "(ver A-H1)" → botón
    h = h.replace(/\(ver ([EA]-[A-Z]\d+)\)/g, (m, id) => {
      const titulo = estado.titulos[id];
      return titulo ? `<button type="button" class="lr-ref" data-id="${id}">→ ${escapar(titulo)}</button>` : "";
    });
    return h;
  }

  function markdown(texto) {
    const lineas = texto.replace(/\r/g, "").split("\n");
    let html = "";
    const pila = []; // listas abiertas: {tipo, sangria}
    const cerrarHasta = (sangria) => {
      while (pila.length && pila[pila.length - 1].sangria >= sangria) html += `</li></${pila.pop().tipo}>`;
    };
    for (const linea of lineas) {
      const m = linea.match(/^(\s*)(\d+\.|[-*•])\s+(.*)$/);
      if (m) {
        const sangria = m[1].length;
        const tipo = /\d/.test(m[2]) ? "ol" : "ul";
        const tope = pila[pila.length - 1];
        if (tope && tope.sangria === sangria && tope.tipo === tipo) {
          html += "</li><li>";
        } else if (tope && sangria > tope.sangria) {
          html += `<${tipo}><li>`; pila.push({ tipo, sangria });
        } else {
          cerrarHasta(sangria);
          const t2 = pila[pila.length - 1];
          if (t2 && t2.sangria === sangria && t2.tipo === tipo) html += "</li><li>";
          else { html += `<${tipo}><li>`; pila.push({ tipo, sangria }); }
        }
        html += enLinea(m[3]);
      } else if (!linea.trim()) {
        cerrarHasta(0);
      } else if (pila.length && /^\s+/.test(linea)) {
        html += " " + enLinea(linea.trim());
      } else {
        cerrarHasta(0);
        html += `<p>${enLinea(linea.trim())}</p>`;
      }
    }
    cerrarHasta(0);
    return html;
  }

  // ------------------------------------------------------------------ Pintar mensajes
  function bajar() { zona.scrollTop = zona.scrollHeight; }

  function burbuja(quien, contenidoHtml) {
    const div = document.createElement("div");
    div.className = `lr-msg lr-${quien}`;
    div.innerHTML = contenidoHtml;
    zona.appendChild(div);
    div.querySelectorAll(".lr-ref").forEach((b) => b.addEventListener("click", () => elegirPregunta(b.dataset.id)));
    bajar();
    return div;
  }

  function usuario(texto) { burbuja("usuario", `<p>${escapar(texto)}</p>`); }
  function bot(texto) { return burbuja("bot", markdown(texto)); }

  function opciones(lista, clase = "") {
    const div = document.createElement("div");
    div.className = "lr-opciones " + clase;
    for (const op of lista) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "lr-op" + (op.secundaria ? " lr-op-sec" : "");
      b.textContent = op.texto;
      b.addEventListener("click", () => { div.remove(); op.accion(); });
      div.appendChild(b);
    }
    zona.appendChild(div);
    bajar();
    return div;
  }

  function quitarOpciones() { zona.querySelectorAll(".lr-opciones").forEach((o) => o.remove()); }

  function escribiendo() {
    return burbuja("bot lr-escribiendo", "<span></span><span></span><span></span>");
  }

  // ------------------------------------------------------------------ Árbol
  function preguntarRol() {
    bot("¡Hola! 👋 Soy el asistente de **LogRoot**. Puedo ayudarte con fichajes, vacaciones, accesos y la gestión de la plataforma.\n\n¿Eres empleado o administrador de tu empresa?");
    opciones(Object.entries(estado.roles).map(([clave, nombre]) => ({
      texto: clave === "empleado" ? "👤 " + nombre : "🛠️ " + nombre,
      accion: () => { estado.rol = clave; usuario(nombre); mostrarCategorias(); },
    })));
  }

  function mostrarCategorias(texto) {
    const cats = (estado.arbol[estado.rol] || []);
    bot(texto || "¿Sobre qué tienes la duda? También puedes escribirla con tus palabras.");
    opciones(cats.map((c) => ({ texto: c.categoria, accion: () => { usuario(c.categoria); mostrarPreguntas(c); } }))
      .concat([{ texto: "Cambiar de perfil", secundaria: true, accion: () => { estado.rol = null; preguntarRol(); } }]));
  }

  function mostrarPreguntas(cat) {
    bot("Elige tu pregunta:");
    opciones(cat.preguntas.map((p) => ({ texto: p.pregunta, accion: () => elegirPregunta(p.id) }))
      .concat([{ texto: "← Volver", secundaria: true, accion: () => mostrarCategorias() }]), "lr-lista");
  }

  async function elegirPregunta(id) {
    quitarOpciones();
    const ind = escribiendo();
    try {
      const r = await fetch(`${API}/respuesta/${encodeURIComponent(id)}?sesion=${encodeURIComponent(estado.sesion)}`);
      const d = await r.json();
      ind.remove();
      if (!r.ok) throw new Error(d.error || "error");
      usuario(d.pregunta);
      bot(d.respuesta);
      estado.historial.push({ rol: "usuario", texto: d.pregunta }, { rol: "asistente", texto: d.respuesta });
      preguntarSiSirvio(d.log_id);
    } catch (e) {
      ind.remove();
      errorConexion();
    }
  }

  // ------------------------------------------------------------------ Texto libre
  async function enviarTexto(texto) {
    texto = (texto || "").trim();
    if (!texto || estado.esperando) return;
    input.value = "";
    quitarOpciones();
    usuario(texto);
    estado.historial.push({ rol: "usuario", texto });
    estado.esperando = true;
    form.classList.add("lr-ocupado");
    const ind = escribiendo();
    try {
      const r = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mensajes: estado.historial.slice(-12), rol: estado.rol, sesion: estado.sesion }),
      });
      const d = await r.json();
      ind.remove();
      if (!r.ok) {
        bot(d.error || "Ahora mismo no puedo responder.");
        estado.historial.pop();
      } else {
        bot(d.respuesta);
        estado.historial.push({ rol: "asistente", texto: d.respuesta });
        preguntarSiSirvio(d.log_id);
      }
    } catch (e) {
      ind.remove();
      estado.historial.pop();
      errorConexion();
    } finally {
      estado.esperando = false;
      form.classList.remove("lr-ocupado");
      input.focus();
    }
  }

  // ------------------------------------------------------------------ ¿Te ha servido?
  function preguntarSiSirvio(logId) {
    opciones([
      { texto: "👍 Sí, gracias", accion: () => { valorar(logId, true); usuario("Sí, gracias"); siguiente(true); } },
      { texto: "👎 No", accion: () => { valorar(logId, false); usuario("No"); derivar(); } },
    ], "lr-valorar");
  }

  function valorar(logId, util) {
    if (!logId) return;
    fetch(`${API}/valoracion`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ log_id: logId, util }),
    }).catch(() => {});
  }

  function textoSoporte() {
    const c = estado.contacto;
    return `- 📞 ${c.telefono}\n- 💬 WhatsApp ${c.whatsapp}\n- ✉️ ${c.email}`;
  }

  function derivar() {
    if (estado.rol === "empleado") {
      bot("Siento no haberlo resuelto. 🙏\n\n" +
        "- Si es algo de **tu cuenta** (un fichaje, tu contraseña, tu horario o tus vacaciones), habla con **tu responsable** en la empresa.\n" +
        "- Si es un **error técnico** de la app o la web, contacta con Soporte LogRoot:\n\n" + textoSoporte());
    } else {
      bot("Siento no haberlo resuelto. 🙏 El equipo de Soporte LogRoot te ayuda encantado:\n\n" + textoSoporte());
    }
    siguiente(false);
  }

  function siguiente(resuelto) {
    if (!estado.rol) {
      opciones([{ texto: "Tengo otra duda", accion: preguntarRol }]);
      return;
    }
    mostrarCategorias(resuelto ? "¡Genial! 😊 ¿Te ayudo con algo más?" : "¿Quieres consultar otra cosa?");
  }

  function errorConexion() {
    bot("Ahora mismo no puedo conectar. Inténtalo de nuevo en unos segundos o contacta con Soporte LogRoot:\n\n" + textoSoporte());
  }

  // ------------------------------------------------------------------ Arranque
  function reiniciar() {
    zona.innerHTML = "";
    estado.rol = null;
    estado.historial = [];
    preguntarRol();
  }

  fetch(`${API}/arbol`).then((r) => r.json()).then((d) => {
    estado.arbol = d.arbol;
    estado.roles = d.roles;
    estado.contacto = d.contacto;
    estado.modo = d.modo;
    Object.values(d.arbol).flat().forEach((c) => c.preguntas.forEach((p) => { estado.titulos[p.id] = p.pregunta; }));
    raiz.classList.add(d.modo === "ia" ? "lr-modo-ia" : "lr-modo-demo");
    preguntarRol();
    if (raiz.dataset.abierto === "1") abrir(true);
  }).catch(() => {
    estado.contacto = { telefono: "981 111 114", whatsapp: "662 488 889", email: "soporte@logrootrh.com" };
    errorConexion();
  });
})();
