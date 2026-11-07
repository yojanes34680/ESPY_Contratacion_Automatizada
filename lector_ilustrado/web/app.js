"use strict";

const $ = (sel) => document.querySelector(sel);
const COLORES = ["#b5651d", "#2e86ab", "#a23b72", "#3b8b5a", "#c98b2b", "#6c5ce7", "#d35454", "#1b998b", "#8e6c4a"];

const estado = {
  claves: { tiene_claude: false, tiene_openai: false },
  obra: null,
  escena: 0,
  segmento: 0,
  reproduciendo: false,
  turno: 0,          // invalida callbacks viejos al saltar
  sondeo: null,
  colores: {},
};
const audio = new Audio();

// ------------------------------------------------------------------ util
async function api(ruta, opciones = {}) {
  const r = await fetch(ruta, opciones);
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail || msg; } catch (_) { /* sin cuerpo */ }
    throw new Error(msg);
  }
  return r.json();
}
const medio = (ruta) => `/medios/${estado.obra.id}/${ruta}`;

function mostrar(vista) {
  for (const v of document.querySelectorAll(".vista")) v.hidden = v.id !== `vista-${vista}`;
  if (vista !== "lector") detener();
  if (vista !== "progreso" && estado.sondeo) { clearInterval(estado.sondeo); estado.sondeo = null; }
}

function el(tag, props = {}, ...hijos) {
  const n = document.createElement(tag);
  Object.assign(n, props);
  for (const h of hijos) if (h != null) n.append(h);
  return n;
}

// ------------------------------------------------------------------ biblioteca
async function cargarEstado() {
  estado.claves = await api("/api/estado");
  const faltan = [];
  if (!estado.claves.tiene_claude) faltan.push("Anthropic (análisis inteligente)");
  if (!estado.claves.tiene_openai) faltan.push("OpenAI (imágenes y voces con IA)");
  const aviso = $("#aviso-claves");
  aviso.hidden = faltan.length === 0;
  aviso.innerHTML = `Falta configurar: <b>${faltan.join(" y ")}</b>. Puede agregarlas en <b>Configuración</b>, ` +
    `o probar el lector con las opciones gratuitas.`;
}

async function cargarBiblioteca() {
  mostrar("biblioteca");
  await cargarEstado();
  const obras = await api("/api/proyectos");
  const lista = $("#lista-obras");
  lista.replaceChildren();
  $("#sin-obras").hidden = obras.length > 0;
  for (const o of obras) {
    const portada = el("div", { className: "portada" });
    if (o.portada) portada.style.backgroundImage = `url(/medios/${o.id}/${o.portada})`;
    const etiqueta = el("span", {
      className: "etiqueta" + (o.estado === "error" ? " error" : ""),
      textContent: { listo: "Lista", error: "Error" }[o.estado] || "Procesando…",
    });
    const borrar = el("button", { className: "mini secundario", textContent: "Eliminar" });
    borrar.onclick = async (ev) => {
      ev.stopPropagation();
      if (!confirm(`¿Eliminar "${o.titulo}" y todo lo generado?`)) return;
      await api(`/api/proyectos/${o.id}`, { method: "DELETE" });
      cargarBiblioteca();
    };
    const tarjeta = el("div", { className: "obra" }, portada,
      el("div", { className: "info" },
        el("h3", { textContent: o.titulo }),
        el("span", { className: "tenue", textContent: o.autor || "" }),
        el("div", { className: "pie" }, etiqueta,
          el("span", { className: "tenue", textContent: `${o.escenas} escenas` }), borrar)));
    tarjeta.onclick = () => abrirObra(o.id);
    lista.append(tarjeta);
  }
}

async function abrirObra(id) {
  const obra = await api(`/api/proyectos/${id}`);
  estado.obra = obra;
  if (obra.estado === "listo") abrirLector(obra);
  else verProgreso(obra);
}

// ------------------------------------------------------------------ progreso
function pintarProgreso(obra) {
  $("#prog-titulo").textContent = obra.ficha?.titulo || obra.nombre_archivo;
  const p = obra.progreso || {};
  $("#prog-paso").textContent = p.paso || "";
  const pct = p.total ? Math.max(5, Math.round((p.hecho / p.total) * 100)) : 5;
  $("#prog-barra").style.width = `${obra.estado === "listo" ? 100 : pct}%`;
  $("#prog-detalle").textContent = p.total ? `${p.hecho} de ${p.total}` : "";
  const err = $("#prog-error");
  err.hidden = obra.estado !== "error";
  err.textContent = obra.error || "";
  const conImagen = obra.escenas.filter((e) => e.imagen).length;
  $("#prog-leer").hidden = conImagen === 0;
}

function verProgreso(obra) {
  mostrar("progreso");
  pintarProgreso(obra);
  estado.sondeo = setInterval(async () => {
    const o = await api(`/api/proyectos/${obra.id}`);
    estado.obra = o;
    pintarProgreso(o);
    if (o.estado === "listo") { clearInterval(estado.sondeo); estado.sondeo = null; abrirLector(o); }
    if (o.estado === "error") { clearInterval(estado.sondeo); estado.sondeo = null; }
  }, 2000);
}

// ------------------------------------------------------------------ lector
function personajesPorId() {
  const mapa = {};
  for (const p of estado.obra.ficha?.personajes || []) mapa[p.id] = p;
  return mapa;
}

function colorDe(hablante) {
  if (hablante === "narrador") return "transparent";
  if (!estado.colores[hablante]) {
    estado.colores[hablante] = COLORES[Object.keys(estado.colores).length % COLORES.length];
  }
  return estado.colores[hablante];
}

function abrirLector(obra) {
  estado.obra = obra;
  estado.colores = {};
  for (const p of obra.ficha?.personajes || []) colorDe(p.id);
  mostrar("lector");
  $("#lec-titulo").textContent = obra.ficha?.titulo || obra.nombre_archivo;
  $("#lec-autor").textContent = obra.ficha?.autor || "";
  const conAudio = obra.escenas.some((e) => e.segmentos.some((s) => s.audio));
  $("#lec-modo-voz").textContent = conAudio ? "Voces con IA" : "Voces del computador";
  irAEscena(0, false);
}

function irAEscena(i, seguirLeyendo) {
  const escenas = estado.obra.escenas;
  if (i < 0 || i >= escenas.length) return;
  detenerSonido();
  estado.escena = i;
  estado.segmento = 0;
  const e = escenas[i];

  const img = $("#lec-imagen");
  img.classList.add("cambiando");
  setTimeout(() => {
    img.src = e.imagen ? medio(e.imagen) : "";
    img.alt = e.descripcion_imagen || "";
    img.onload = () => img.classList.remove("cambiando");
    if (!e.imagen) img.classList.remove("cambiando");
  }, 250);

  $("#lec-escena-num").textContent = `Escena ${i + 1} de ${escenas.length}`;
  $("#lec-escena-titulo").textContent = e.titulo;
  pintarTexto(e);
  pintarReparto(e);
  $("#btn-anterior").disabled = i === 0;
  $("#btn-siguiente").disabled = i === escenas.length - 1;
  $("#btn-regenerar").hidden = estado.obra.opciones?.imagenes !== "openai" && estado.obra.opciones?.imagenes !== "provisional";

  if (seguirLeyendo) { estado.reproduciendo = true; leerSegmento(); }
  else { estado.reproduciendo = false; actualizarBotonPlay(); }
}

function pintarTexto(escena) {
  const cont = $("#lec-texto");
  cont.replaceChildren();
  const personajes = personajesPorId();
  let anterior = null;
  escena.segmentos.forEach((s, idx) => {
    const esDialogo = s.hablante !== "narrador";
    const cierraFrase = anterior && /[.!?…»”"]$/.test(anterior.texto.trim());
    const empiezaMayuscula = /^[¿¡«"A-ZÁÉÍÓÚÑ]/.test(s.texto.trim());
    if (anterior && anterior.hablante !== s.hablante && cierraFrase && (esDialogo || empiezaMayuscula)) {
      cont.append(el("span", { className: "salto" }));
    }
    const span = el("span", {
      className: "seg" + (esDialogo ? " dialogo" : ""),
      textContent: s.texto + " ",
      title: esDialogo ? (personajes[s.hablante]?.nombre || s.hablante) : "Narrador",
    });
    span.dataset.i = idx;
    span.style.setProperty("--color", colorDe(s.hablante));
    span.onclick = () => { detenerSonido(); estado.segmento = idx; estado.reproduciendo = true; leerSegmento(); };
    cont.append(span);
    anterior = s;
  });
  cont.scrollTop = 0;
}

function pintarReparto(escena) {
  const personajes = personajesPorId();
  const hablan = [...new Set(escena.segmentos.map((s) => s.hablante))];
  const cont = $("#lec-reparto");
  cont.replaceChildren();
  for (const h of hablan) {
    const punto = el("i");
    punto.style.setProperty("--color", h === "narrador" ? "var(--tenue)" : colorDe(h));
    cont.append(el("span", {}, punto, h === "narrador" ? "Narrador" : (personajes[h]?.nombre || h)));
  }
}

function marcarActivo() {
  for (const s of document.querySelectorAll("#lec-texto .seg")) {
    const activo = Number(s.dataset.i) === estado.segmento && estado.reproduciendo;
    s.classList.toggle("activo", activo);
    if (activo) s.scrollIntoView({ block: "center", behavior: "smooth" });
  }
}

function actualizarBotonPlay() {
  $("#btn-play").textContent = estado.reproduciendo ? "⏸" : "▶";
  marcarActivo();
}

function siguienteSegmento(turno) {
  if (turno !== estado.turno || !estado.reproduciendo) return;
  estado.segmento += 1;
  leerSegmento();
}

function leerSegmento() {
  const escena = estado.obra.escenas[estado.escena];
  const seg = escena.segmentos[estado.segmento];
  const turno = ++estado.turno;
  if (!seg) {
    const hayMas = estado.escena < estado.obra.escenas.length - 1;
    if (hayMas && $("#chk-continuo").checked) irAEscena(estado.escena + 1, true);
    else { estado.reproduciendo = false; estado.segmento = 0; actualizarBotonPlay(); }
    return;
  }
  actualizarBotonPlay();
  const velocidad = Number($("#sel-velocidad").value);
  if (seg.audio) {
    audio.src = medio(seg.audio);
    audio.playbackRate = velocidad;
    audio.onended = () => siguienteSegmento(turno);
    audio.onerror = () => hablarConNavegador(seg, velocidad, turno);
    audio.play().catch(() => hablarConNavegador(seg, velocidad, turno));
  } else {
    hablarConNavegador(seg, velocidad, turno);
  }
}

// --- voces del navegador (gratis) ---
let vocesNavegador = [];
function cargarVocesNavegador() {
  const todas = speechSynthesis.getVoices();
  const es = todas.filter((v) => v.lang.toLowerCase().startsWith("es"));
  vocesNavegador = es.length ? es : todas;
}
if ("speechSynthesis" in window) {
  cargarVocesNavegador();
  speechSynthesis.onvoiceschanged = cargarVocesNavegador;
}

function perfilNavegador(hablante) {
  if (hablante === "narrador") return { voz: vocesNavegador[0], tono: 1 };
  const ids = (estado.obra.ficha?.personajes || []).map((p) => p.id);
  const k = Math.max(0, ids.indexOf(hablante)) + 1;
  const p = personajesPorId()[hablante] || {};
  const texto = `${p.genero || ""} ${p.edad_aproximada || ""}`.toLowerCase();
  let tono = 1;
  if (/femen|mujer|niña|señora|joven/.test(texto)) tono = 1.2;
  if (/mascul|hombre|señor|anciano|viejo/.test(texto)) tono = 0.85;
  if (/niñ|infan/.test(texto)) tono = 1.4;
  tono += ((k % 3) - 1) * 0.08;
  return { voz: vocesNavegador[k % Math.max(1, vocesNavegador.length)], tono };
}

function hablarConNavegador(seg, velocidad, turno) {
  if (!("speechSynthesis" in window)) { siguienteSegmento(turno); return; }
  const u = new SpeechSynthesisUtterance(seg.texto);
  const perfil = perfilNavegador(seg.hablante);
  if (perfil.voz) u.voice = perfil.voz;
  u.lang = perfil.voz?.lang || "es-ES";
  u.pitch = perfil.tono;
  u.rate = velocidad;
  u.onend = () => siguienteSegmento(turno);
  u.onerror = () => siguienteSegmento(turno);
  speechSynthesis.speak(u);
}

function detenerSonido() {
  estado.turno += 1;
  audio.onended = null;
  audio.onerror = null;
  audio.pause();
  if ("speechSynthesis" in window) speechSynthesis.cancel();
}

function detener() {
  detenerSonido();
  estado.reproduciendo = false;
  actualizarBotonPlay();
}

function alternarLectura() {
  if (estado.reproduciendo) {
    estado.reproduciendo = false;
    detenerSonido();
    actualizarBotonPlay();
  } else {
    estado.reproduciendo = true;
    leerSegmento();
  }
}

// ------------------------------------------------------------------ ficha
function abrirFicha() {
  const f = estado.obra.ficha || {};
  $("#ficha-titulo").textContent = f.titulo || estado.obra.nombre_archivo;
  const dl = $("#ficha-datos");
  dl.replaceChildren();
  for (const [k, v] of [["Autor", f.autor], ["Época", f.epoca], ["Lugar", f.lugar],
    ["Contexto", f.contexto_historico], ["Estilo visual", f.estilo_visual], ["Narrador", f.tono_narrador]]) {
    if (v) dl.append(el("dt", { textContent: k }), el("dd", { textContent: v }));
  }
  const cont = $("#ficha-personajes");
  cont.replaceChildren();
  for (const p of f.personajes || []) {
    const d = el("div", { className: "personaje" },
      el("b", { textContent: p.nombre }), el("br"),
      el("span", { className: "tenue", textContent: [p.genero, p.edad_aproximada].filter(Boolean).join(", ") }), el("br"),
      p.descripcion_fisica || "", p.vestuario ? ` Viste: ${p.vestuario}` : "", el("br"),
      el("small", { textContent: `Voz: ${p.personalidad_voz}` }));
    d.style.setProperty("--color", colorDe(p.id));
    cont.append(d);
  }
  const adv = $("#ficha-advertencias");
  adv.replaceChildren(...(estado.obra.advertencias || []).map((a) => el("p", { className: "tenue", textContent: "⚠ " + a })));
  $("#dlg-ficha").showModal();
}

// ------------------------------------------------------------------ eventos
$("#btn-nueva").onclick = () => {
  for (const [nombre, disponible] of [["analisis", estado.claves.tiene_claude],
    ["imagenes", estado.claves.tiene_openai], ["voces", estado.claves.tiene_openai]]) {
    const radios = document.querySelectorAll(`input[name=${nombre}]`);
    radios[0].disabled = !disponible;
    radios[0].parentElement.classList.toggle("no-disponible", !disponible);
    (disponible ? radios[0] : radios[1]).checked = true;
  }
  $("#dlg-nueva").showModal();
};

$("#form-nueva").addEventListener("submit", async (ev) => {
  if (ev.submitter?.value !== "crear") return;
  ev.preventDefault();
  const archivo = $("#in-archivo").files[0];
  if (!archivo) return;
  const valor = (n) => document.querySelector(`input[name=${n}]:checked`).value;
  const numero = (sel) => ($(sel).value ? Number($(sel).value) : null);
  const opciones = {
    desde: numero("#in-desde"), hasta: numero("#in-hasta"), max_escenas: numero("#in-max"),
    analisis: valor("analisis"), imagenes: valor("imagenes"), voces: valor("voces"),
  };
  const datos = new FormData();
  datos.append("archivo", archivo);
  datos.append("opciones", JSON.stringify(opciones));
  $("#btn-crear").disabled = true;
  try {
    const obra = await api("/api/proyectos", { method: "POST", body: datos });
    $("#dlg-nueva").close();
    $("#form-nueva").reset();
    estado.obra = obra;
    verProgreso(obra);
  } catch (e) {
    alert(e.message);
  } finally {
    $("#btn-crear").disabled = false;
  }
});

$("#btn-config").onclick = () => {
  $("#est-anthropic").textContent = estado.claves.tiene_claude ? "✓ Configurada" : "Sin configurar";
  $("#est-openai").textContent = estado.claves.tiene_openai ? "✓ Configurada" : "Sin configurar";
  $("#in-anthropic").value = "";
  $("#in-openai").value = "";
  $("#dlg-config").showModal();
};

$("#form-config").addEventListener("submit", async (ev) => {
  if (ev.submitter?.value !== "guardar") return;
  const cuerpo = {};
  if ($("#in-anthropic").value.trim()) cuerpo.ANTHROPIC_API_KEY = $("#in-anthropic").value.trim();
  if ($("#in-openai").value.trim()) cuerpo.OPENAI_API_KEY = $("#in-openai").value.trim();
  if (Object.keys(cuerpo).length) {
    await api("/api/claves", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo) });
  }
  cargarEstado();
});

for (const b of document.querySelectorAll(".volver")) b.onclick = cargarBiblioteca;
$("#prog-leer").onclick = () => abrirLector(estado.obra);
$("#btn-play").onclick = alternarLectura;
$("#btn-anterior").onclick = () => irAEscena(estado.escena - 1, estado.reproduciendo);
$("#btn-siguiente").onclick = () => irAEscena(estado.escena + 1, estado.reproduciendo);
$("#btn-ficha").onclick = abrirFicha;
$("#sel-velocidad").onchange = () => { audio.playbackRate = Number($("#sel-velocidad").value); };

$("#btn-regenerar").onclick = () => {
  $("#in-descripcion").value = estado.obra.escenas[estado.escena].descripcion_imagen;
  $("#dlg-regenerar").showModal();
};
$("#dlg-regenerar").addEventListener("close", async () => {
  if ($("#dlg-regenerar").returnValue !== "ok") return;
  const i = estado.escena;
  const boton = $("#btn-regenerar");
  boton.disabled = true;
  boton.textContent = "Pintando…";
  try {
    const escena = await api(`/api/proyectos/${estado.obra.id}/escenas/${i}/imagen`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ descripcion: $("#in-descripcion").value }),
    });
    estado.obra.escenas[i] = escena;
    if (estado.escena === i) $("#lec-imagen").src = medio(escena.imagen);
  } catch (e) {
    alert(e.message);
  } finally {
    boton.disabled = false;
    boton.textContent = "Otra imagen";
  }
});

document.addEventListener("keydown", (ev) => {
  if ($("#vista-lector").hidden || document.querySelector("dialog[open]")) return;
  if (["INPUT", "SELECT", "TEXTAREA"].includes(ev.target.tagName)) return;
  if (ev.code === "Space") { ev.preventDefault(); alternarLectura(); }
  if (ev.code === "ArrowRight") irAEscena(estado.escena + 1, estado.reproduciendo);
  if (ev.code === "ArrowLeft") irAEscena(estado.escena - 1, estado.reproduciendo);
});

cargarBiblioteca().catch((e) => alert("No se pudo conectar con el programa: " + e.message));
