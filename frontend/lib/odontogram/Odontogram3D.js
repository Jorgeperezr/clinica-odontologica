"use client";

/**
 * Odontograma 3D (Sprint 48).
 * ────────────────────────────────────────────────────────────────────
 * Cuarta estrategia de representación. Cumple el mismo contrato que los
 * otros modelos (`contract.js`): recibe los datos y emite intenciones;
 * no tiene base de datos propia ni escribe en la API. Es, literalmente,
 * otra ventana sobre la misma historia clínica.
 *
 * Sobre la geometría: los dientes se generan proceduralmente a partir
 * del número FDI en vez de cargar un modelo descargado. Eso evita
 * depender de recursos de terceros y de sus licencias, mantiene el peso
 * en cero bytes de descarga, permite teñir cada pieza con su estado
 * clínico y —lo más importante— hace que cada diente sea un objeto
 * independiente sobre el que se puede hacer raycasting para
 * seleccionarlo. Un modelo importado en una sola malla no lo permitiría
 * sin trabajo de segmentación.
 *
 * Three.js se importa de forma diferida (`await import`) para que su
 * peso no entre en el paquete inicial de la aplicación: la escena solo
 * se construye cuando el profesional abre esta pestaña.
 *
 * Ampliaciones futuras (periodontograma 3D, ortodoncia, simulaciones)
 * encajan añadiendo capas sobre `buildArches`, sin tocar la lógica
 * clínica ni este contrato.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import {
  PERM_LOWER_L, PERM_LOWER_R, PERM_UPPER_L, PERM_UPPER_R,
  SURFACE_LABELS, TEMP_LOWER_L, TEMP_LOWER_R, TEMP_UPPER_L, TEMP_UPPER_R,
  dominantState, hasRecords,
} from "./contract";
import { toothFamily, isUpper } from "./ToothArt";
import { buildToothGeometry } from "./toothGeometry";

/** Filtros clínicos: resaltan solo las piezas cuyo estado coincide. */
const FILTERS = [
  { key: "all", label: "Todo" },
  { key: "caries", label: "Caries", match: /caries/i },
  { key: "obturado", label: "Obturaciones", match: /obtur/i },
  { key: "corona", label: "Coronas", match: /corona/i },
  { key: "endodoncia", label: "Endodoncias", match: /endodon/i },
  { key: "implante", label: "Implantes", match: /implante/i },
  { key: "protesis", label: "Prótesis", match: /pr[óo]tesis/i },
  { key: "extraccion", label: "Extracciones", match: /extrac|p[ée]rdida|ausente/i },
  { key: "sellante", label: "Sellantes", match: /sellante/i },
  { key: "fractura", label: "Fracturas", match: /fractura/i },
  { key: "registrado", label: "Con registro" },
];

/** Orden de las piezas a lo largo de cada arcada, de derecha a izquierda. */
const ARCHES = {
  permUpper: [...PERM_UPPER_R, ...PERM_UPPER_L],
  tempUpper: [...TEMP_UPPER_R, ...TEMP_UPPER_L],
  tempLower: [...TEMP_LOWER_R, ...TEMP_LOWER_L],
  permLower: [...PERM_LOWER_R, ...PERM_LOWER_L],
};

/** Dimensiones por familia dental (ancho, alto de corona, profundidad). */
function toothDims(code) {
  const fam = toothFamily(code);
  const dec = ["5", "6", "7", "8"].includes(String(code)[0]);
  const s = dec ? 0.78 : 1;
  const base = {
    incisivo: [0.62, 1.15, 0.42],
    canino: [0.66, 1.35, 0.6],
    premolar: [0.76, 1.0, 0.78],
    molar: [1.02, 0.95, 0.95],
  }[fam];
  return base.map((v) => v * s);
}

export default function Odontogram3D({
  surfacesByTooth = {},
  selectedTooth,
  onSurfaceClick,
  history = [],
  historyLoading = false,
}) {
  const mountRef = useRef(null);
  const sceneRef = useRef(null);        // { THREE, scene, camera, renderer, teeth, dispose }
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  const [hovered, setHovered] = useState(null);

  // Los callbacks cambian en cada render del contenedor; se guardan en una
  // referencia para no reconstruir la escena en cada actualización.
  const clickRef = useRef(onSurfaceClick);
  useEffect(() => { clickRef.current = onSurfaceClick; }, [onSurfaceClick]);

  /* ── Construcción de la escena (una sola vez) ── */
  useEffect(() => {
    let cancelled = false;
    let cleanup = () => {};

    (async () => {
      let THREE;
      try {
        THREE = await import("three");
      } catch {
        if (!cancelled) setError("No se pudo cargar el motor 3D.");
        return;
      }
      if (cancelled || !mountRef.current) return;

      const mount = mountRef.current;
      const width = mount.clientWidth || 800;
      const height = 460;

      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(38, width / height, 0.1, 200);
      camera.position.set(0, 6.5, 13);

      const renderer = new THREE.WebGLRenderer({
        antialias: true, alpha: true, preserveDrawingBuffer: true, // permite capturar la imagen
      });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.setSize(width, height);
      // Tono cinematográfico: evita que los blancos del esmalte se quemen
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.05;
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.shadowMap.enabled = true;
      renderer.shadowMap.type = THREE.PCFSoftShadowMap;
      mount.appendChild(renderer.domElement);

      /* ── Entorno para reflejos ──
         Sin un mapa de entorno, un material físico no tiene nada que
         reflejar y el esmalte se ve mate. Se genera proceduralmente con
         RoomEnvironment (viene en el paquete de three, no se descarga
         nada) y se preconvoluciona con PMREM para reflejos correctos. */
      let envRT = null;
      try {
        const { RoomEnvironment } = await import("three/examples/jsm/environments/RoomEnvironment.js");
        const pmrem = new THREE.PMREMGenerator(renderer);
        envRT = pmrem.fromScene(new RoomEnvironment(), 0.04);
        scene.environment = envRT.texture;
        pmrem.dispose();
      } catch {
        // Sin entorno la escena sigue siendo válida, solo menos reflectante
      }

      /* ── Iluminación de tres puntos ──
         Principal cenital (modela el volumen y proyecta la sombra),
         relleno frío lateral (abre las zonas oscuras sin aplanar) y
         contraluz posterior (separa las piezas del fondo). */
      scene.add(new THREE.HemisphereLight(0xffffff, 0xb9c6d2, 0.42));

      const keyLight = new THREE.DirectionalLight(0xfff4e8, 1.5);
      keyLight.position.set(5, 14, 9);
      keyLight.castShadow = true;
      keyLight.shadow.mapSize.set(1024, 1024);
      keyLight.shadow.camera.near = 1;
      keyLight.shadow.camera.far = 40;
      keyLight.shadow.camera.left = -12;
      keyLight.shadow.camera.right = 12;
      keyLight.shadow.camera.top = 12;
      keyLight.shadow.camera.bottom = -12;
      keyLight.shadow.bias = -0.0012;
      keyLight.shadow.radius = 4;
      scene.add(keyLight);

      const fillLight = new THREE.DirectionalLight(0xd8e8f6, 0.55);
      fillLight.position.set(-8, 3, 6);
      scene.add(fillLight);

      const rimLight = new THREE.DirectionalLight(0xffffff, 0.7);
      rimLight.position.set(0, 4, -12);
      scene.add(rimLight);

      // Suelo receptor de sombra: da asiento a las arcadas sin verse
      const floor = new THREE.Mesh(
        new THREE.PlaneGeometry(60, 60),
        new THREE.ShadowMaterial({ opacity: 0.16 }),
      );
      floor.rotation.x = -Math.PI / 2;
      floor.position.y = -4.6;
      floor.receiveShadow = true;
      scene.add(floor);

      // ── Arcadas ──
      const teeth = [];
      const group = new THREE.Group();

      /* ── Material de esmalte ──
         MeshPhysicalMaterial con capa de barniz (clearcoat) y algo de
         transmisión: el esmalte real es translúcido y deja pasar luz
         hacia la dentina, que es lo que impide que un diente se vea
         como plástico blanco. Cada pieza recibe su propia instancia
         porque el color y el resaltado se animan por separado. */
      function enamelMaterial() {
        return new THREE.MeshPhysicalMaterial({
          color: 0xf6f4ef,
          roughness: 0.28,
          metalness: 0.0,
          clearcoat: 0.85,
          clearcoatRoughness: 0.16,
          transmission: 0.18,       // translucidez sutil
          thickness: 0.6,
          ior: 1.63,                // índice de refracción del esmalte
          attenuationColor: new THREE.Color(0xffe9cf),
          attenuationDistance: 1.4,
          emissive: new THREE.Color(0x000000),
          transparent: true,
          opacity: 1,
        });
      }

      // Contorno luminoso: copia ampliada dibujada por su cara interna.
      // Resalta la pieza sin alterar su color, que es lo que pedía el
      // criterio clínico de no falsear el aspecto del diente.
      const outlineMat = new THREE.MeshBasicMaterial({
        color: 0x2e9bdc, side: THREE.BackSide,
        transparent: true, opacity: 0, depthWrite: false,
      });

      function buildArch(codes, { radiusX, radiusZ, y, upper, visible }) {
        const n = codes.length;
        codes.forEach((code, i) => {
          // Distribución sobre una elipse: forma real de la arcada
          const t = n === 1 ? 0.5 : i / (n - 1);
          const ang = Math.PI * (0.06 + 0.88 * t);
          const x = -Math.cos(ang) * radiusX;
          const z = Math.sin(ang) * radiusZ;

          const geo = buildToothGeometry(THREE, code);
          const mesh = new THREE.Mesh(geo, enamelMaterial());
          mesh.castShadow = true;
          mesh.receiveShadow = true;
          mesh.position.set(x, y, z);
          mesh.lookAt(0, y, 0);
          mesh.rotateY(Math.PI);
          // Ligera inclinación vestibular, como en una arcada real
          mesh.rotateX((upper ? 1 : -1) * 0.06);
          mesh.visible = visible;
          mesh.userData = { code, baseY: y };

          // Contorno como hijo: hereda transformaciones sin duplicar lógica
          const outline = new THREE.Mesh(geo, outlineMat.clone());
          outline.scale.setScalar(1.055);
          outline.renderOrder = -1;
          mesh.add(outline);
          mesh.userData.outline = outline;

          group.add(mesh);
          teeth.push(mesh);
        });
      }

      buildArch(ARCHES.permUpper, { radiusX: 4.6, radiusZ: 3.5, y: 1.1, upper: true, visible: true });
      buildArch(ARCHES.permLower, { radiusX: 4.2, radiusZ: 3.2, y: -1.1, upper: false, visible: true });
      buildArch(ARCHES.tempUpper, { radiusX: 3.0, radiusZ: 2.3, y: 1.1, upper: true, visible: false });
      buildArch(ARCHES.tempLower, { radiusX: 2.8, radiusZ: 2.1, y: -1.1, upper: false, visible: false });

      // Encías: dos toros achatados que enmarcan las arcadas
      [1.85, -1.85].forEach((gy) => {
        const g = new THREE.Mesh(
          new THREE.TorusGeometry(4.3, 0.55, 12, 48, Math.PI * 1.05),
          new THREE.MeshPhysicalMaterial({
            color: 0xd99a95, roughness: 0.72, clearcoat: 0.25,
            transmission: 0.12, thickness: 0.4,
            transparent: true, opacity: 0.55,
          }),
        );
        g.rotation.x = Math.PI / 2;
        g.rotation.z = -Math.PI * 0.02;
        g.position.y = gy;
        g.scale.set(1, 0.82, 1);
        group.add(g);
      });

      scene.add(group);

      /* ── Órbita, zoom y desplazamiento (implementación propia, para no
         depender de complementos externos al paquete) ── */
      const state = { rotX: 0.38, rotY: 0, dist: 13, panX: 0, panY: 0 };
      let dragging = null, lastX = 0, lastY = 0;

      const el = renderer.domElement;
      el.style.touchAction = "none";
      el.style.cursor = "grab";

      const onDown = (e) => {
        dragging = e.shiftKey || e.button === 2 ? "pan" : "rotate";
        lastX = e.clientX; lastY = e.clientY;
        el.setPointerCapture?.(e.pointerId);
        el.style.cursor = "grabbing";
      };
      const onMove = (e) => {
        if (!dragging) { pickHover(e); return; }
        const dx = e.clientX - lastX, dy = e.clientY - lastY;
        lastX = e.clientX; lastY = e.clientY;
        if (dragging === "rotate") {
          state.rotY += dx * 0.008;
          state.rotX = Math.max(-1.3, Math.min(1.4, state.rotX + dy * 0.006));  // giro vertical amplio
        } else {
          state.panX -= dx * 0.02;
          state.panY += dy * 0.02;
        }
      };
      const onUp = (e) => {
        dragging = null;
        el.style.cursor = "grab";
        el.releasePointerCapture?.(e.pointerId);
      };
      const onWheel = (e) => {
        e.preventDefault();
        state.dist = Math.max(4.5, Math.min(30, state.dist + e.deltaY * 0.01));
      };

      // ── Selección por raycasting ──
      const ray = new THREE.Raycaster();
      const ndc = new THREE.Vector2();
      function toNdc(e) {
        const r = el.getBoundingClientRect();
        ndc.x = ((e.clientX - r.left) / r.width) * 2 - 1;
        ndc.y = -((e.clientY - r.top) / r.height) * 2 + 1;
      }
      function pick(e) {
        toNdc(e);
        ray.setFromCamera(ndc, camera);
        const hit = ray.intersectObjects(teeth.filter((t) => t.visible), false)[0];
        return hit?.object?.userData?.code || null;
      }
      let hoverCode = null;
      function pickHover(e) {
        const code = pick(e);
        if (code !== hoverCode) {
          hoverCode = code;
          setHovered(code);
          el.style.cursor = code ? "pointer" : "grab";
        }
      }
      const onClick = (e) => {
        const code = pick(e);
        if (code) clickRef.current?.(code, "whole");
      };

      el.addEventListener("pointerdown", onDown);
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
      el.addEventListener("wheel", onWheel, { passive: false });
      el.addEventListener("click", onClick);
      el.addEventListener("contextmenu", (e) => e.preventDefault());

      // ── Bucle de render con transiciones suaves ──
      let raf;
      const clock = new THREE.Clock();
      function loop() {
        raf = requestAnimationFrame(loop);
        const dt = Math.min(clock.getDelta(), 0.05);

        // Cámara orbital interpolada
        const cx = Math.sin(state.rotY) * Math.cos(state.rotX) * state.dist;
        const cy = Math.sin(state.rotX) * state.dist;
        const cz = Math.cos(state.rotY) * Math.cos(state.rotX) * state.dist;
        camera.position.lerp(new THREE.Vector3(cx + state.panX, cy + state.panY, cz), 0.18);
        camera.lookAt(state.panX, state.panY, 0);

        // Animación de las piezas: la seleccionada se separa y late suave
        for (const t of teeth) {
          const target = t.userData.targetY ?? t.userData.baseY;
          t.position.y += (target - t.position.y) * Math.min(1, dt * 9);
          const so = t.userData.targetOpacity ?? 1;
          t.material.opacity += (so - t.material.opacity) * Math.min(1, dt * 9);
          const sc = t.userData.targetScale ?? 1;
          t.scale.lerp(new THREE.Vector3(sc, sc, sc), Math.min(1, dt * 9));
          // Contorno luminoso: aparece y desaparece con suavidad
          const ol = t.userData.outline;
          if (ol) {
            const to = (t.userData.targetOutline ?? 0) * (t.userData.targetOpacity ?? 1);
            ol.material.opacity += (to - ol.material.opacity) * Math.min(1, dt * 10);
            ol.visible = ol.material.opacity > 0.01;
          }
        }
        renderer.render(scene, camera);
      }
      loop();

      const onResize = () => {
        const w = mount.clientWidth || 800;
        camera.aspect = w / height;
        camera.updateProjectionMatrix();
        renderer.setSize(w, height);
      };
      window.addEventListener("resize", onResize);

      sceneRef.current = { THREE, scene, camera, renderer, teeth, state };
      if (!cancelled) setReady(true);

      cleanup = () => {
        cancelAnimationFrame(raf);
        window.removeEventListener("resize", onResize);
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
        el.removeEventListener("pointerdown", onDown);
        el.removeEventListener("wheel", onWheel);
        el.removeEventListener("click", onClick);
        teeth.forEach((t) => {
          t.userData.outline?.material.dispose();
          t.geometry.dispose();
          t.material.dispose();
        });
        envRT?.dispose();
        renderer.dispose();
        if (el.parentNode) el.parentNode.removeChild(el);
        sceneRef.current = null;
      };
    })();

    return () => { cancelled = true; cleanup(); };
  }, []);

  /* ── Sincronización: color, filtro y selección ──
     Este efecto es el puente entre los datos clínicos y la escena. Se
     ejecuta ante CUALQUIER cambio en los datos, de modo que un registro
     hecho en el odontograma clásico se ve aquí de inmediato. */
  useEffect(() => {
    const s = sceneRef.current;
    if (!s) return;
    const { THREE, teeth } = s;
    const f = FILTERS.find((x) => x.key === filter);

    const ENAMEL = new THREE.Color(0xf6f4ef);

    for (const t of teeth) {
      const code = t.userData.code;
      const surfaces = surfacesByTooth[code];
      const st = dominantState(surfaces);
      const registrado = hasRecords(surfaces);
      const label = (st?.label || "").toLowerCase();
      const m = t.material;

      /* Patología como TINTE sobre el esmalte, no como repintado.
         Se mezcla el color clínico con el marfil natural, así el diente
         sigue leyéndose como diente —conserva translucidez y reflejos—
         mientras el hallazgo queda inequívoco. */
      if (st?.color) {
        const tint = new THREE.Color(st.color);
        m.color.copy(ENAMEL).lerp(tint, 0.62);
        // Un halo tenue del propio color mejora la lectura a distancia
        m.emissive.copy(tint).multiplyScalar(0.10);
      } else {
        m.color.copy(ENAMEL);
        m.emissive.setHex(0x000000);
      }

      /* Materiales restauradores: coronas e implantes son metálicos y
         pulidos; las prótesis, cerámicas mates. La diferencia de
         acabado se percibe antes que la de color. */
      if (/implante/.test(label)) {
        m.metalness = 0.92; m.roughness = 0.24; m.transmission = 0;
        m.clearcoat = 0.4;
      } else if (/corona/.test(label)) {
        m.metalness = 0.45; m.roughness = 0.18; m.transmission = 0.05;
        m.clearcoat = 1.0;
      } else if (/pr[óo]tesis/.test(label)) {
        m.metalness = 0.05; m.roughness = 0.5; m.transmission = 0.06;
        m.clearcoat = 0.5;
      } else {
        m.metalness = 0.0; m.roughness = 0.28; m.transmission = 0.18;
        m.clearcoat = 0.85;
      }

      // Filtro: lo no coincidente se atenúa, nunca se oculta, para no
      // perder la referencia anatómica de la boca completa.
      let coincide = true;
      if (f?.key === "registrado") coincide = registrado;
      else if (f?.match) coincide = f.match.test(label);
      t.userData.targetOpacity = coincide ? 1 : 0.14;

      // Selección: contorno luminoso + ligera separación de la arcada
      const sel = selectedTooth === code;
      const hov = hovered === code;
      const dir = isUpper(code) ? 1 : -1;
      t.userData.targetY = t.userData.baseY + (sel ? dir * 0.42 : 0);
      t.userData.targetScale = sel ? 1.05 : 1;
      t.userData.targetOutline = sel ? 0.9 : (hov ? 0.35 : 0);
    }
  }, [surfacesByTooth, selectedTooth, filter, hovered, ready]);

  /* ── Captura de imagen para informes ── */
  const capture = useCallback(() => {
    const s = sceneRef.current;
    if (!s) return;
    s.renderer.render(s.scene, s.camera);
    s.renderer.domElement.toBlob((blob) => {
      if (!blob) return;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `odontograma3d_${selectedTooth || "vista"}_${Date.now()}.png`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    }, "image/png");
  }, [selectedTooth]);

  const resetView = useCallback(() => {
    const s = sceneRef.current;
    if (!s) return;
    Object.assign(s.state, { rotX: 0.38, rotY: 0, dist: 13, panX: 0, panY: 0 });
  }, []);

  const selSurfaces = selectedTooth ? surfacesByTooth[selectedTooth] : null;

  return (
    <div>
      {/* Barra de herramientas: filtros y acciones */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center",
                    marginBottom: 10 }}>
        <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: ".05em",
                       textTransform: "uppercase", color: "var(--ink-faint)" }}>
          Resaltar
        </span>
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
          {FILTERS.map((f) => (
            <button key={f.key} type="button" onClick={() => setFilter(f.key)}
                    className={`btn ${filter === f.key ? "btn-primary" : "btn-ghost"}`}
                    style={{ fontSize: 12, padding: "4px 10px" }}>
              {f.label}
            </button>
          ))}
        </div>
        <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
          <button className="btn btn-ghost" style={{ fontSize: 12.5 }} onClick={resetView}>
            Centrar
          </button>
          <button className="btn btn-ghost" style={{ fontSize: 12.5 }} onClick={capture}
                  title="Descargar la vista actual como imagen para el informe">
            Capturar imagen
          </button>
        </div>
      </div>

      <div style={{ display: "grid", gap: 14,
                    gridTemplateColumns: selectedTooth ? "minmax(0,1fr) 300px" : "1fr" }}>
        {/* Lienzo 3D */}
        <div>
          <div ref={mountRef}
               style={{ width: "100%", height: 460, borderRadius: "var(--radius)",
                        overflow: "hidden", background: "var(--paper)",
                        border: "1px solid var(--line)", position: "relative" }}>
            {!ready && !error && (
              <div className="empty" style={{ paddingTop: 200 }}>Cargando modelo 3D…</div>
            )}
            {error && <div className="error-box" style={{ margin: 16 }}>{error}</div>}
          </div>
          <p style={{ fontSize: 12, color: "var(--ink-faint)", marginTop: 6 }}>
            Arrastra para rotar · rueda para acercar · Mayús + arrastrar para desplazar ·
            clic en una pieza para ver su historial
            {hovered && <strong style={{ color: "var(--petrol)" }}> · pieza {hovered}</strong>}
          </p>
        </div>

        {/* Panel lateral: historial de la pieza seleccionada */}
        {selectedTooth && (
          <aside className="card animate-rise" style={{ alignSelf: "start" }}>
            <h3 style={{ marginBottom: 4 }}>Pieza {selectedTooth}</h3>
            <p style={{ fontSize: 12.5, color: "var(--ink-soft)", marginBottom: 12 }}>
              {toothFamily(selectedTooth)} · {isUpper(selectedTooth) ? "superior" : "inferior"}
            </p>

            {/* Estado actual por superficie */}
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".05em",
                            textTransform: "uppercase", color: "var(--ink-faint)",
                            marginBottom: 6 }}>Estado actual</div>
              {selSurfaces && Object.keys(selSurfaces).length > 0 ? (
                <div style={{ display: "grid", gap: 5 }}>
                  {Object.entries(selSurfaces).map(([surf, st]) => (
                    <div key={surf} style={{ display: "flex", alignItems: "center", gap: 8,
                                             fontSize: 12.5 }}>
                      <span style={{ width: 10, height: 10, borderRadius: 3, flexShrink: 0,
                                     background: st.color, border: "1px solid var(--line)" }} />
                      <span style={{ color: "var(--ink-soft)" }}>
                        {SURFACE_LABELS[surf] || surf}
                      </span>
                      <span style={{ marginLeft: "auto", fontWeight: 600 }}>{st.label}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p style={{ fontSize: 12.5, color: "var(--ink-faint)" }}>Sin registros.</p>
              )}
            </div>

            {/* Historial clínico */}
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".05em",
                          textTransform: "uppercase", color: "var(--ink-faint)",
                          marginBottom: 6 }}>Historial</div>
            {historyLoading ? (
              <div className="skeleton" style={{ height: 48 }} />
            ) : history.length === 0 ? (
              <p style={{ fontSize: 12.5, color: "var(--ink-faint)" }}>
                Sin historial para esta pieza.
              </p>
            ) : (
              <div style={{ display: "grid", gap: 8, maxHeight: 260, overflowY: "auto" }}>
                {history.map((h) => (
                  <div key={h.id} style={{ fontSize: 12.5, paddingBottom: 8,
                                           borderBottom: "1px solid var(--line)" }}>
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <span style={{ width: 9, height: 9, borderRadius: "50%", flexShrink: 0,
                                     background: h.state_color || "var(--line)" }} />
                      <strong>{h.state_label || h.state}</strong>
                      <span className="tabular" style={{ marginLeft: "auto",
                                                         color: "var(--ink-faint)", fontSize: 11.5 }}>
                        {(h.date || "").slice(0, 10)}
                      </span>
                    </div>
                    <div style={{ color: "var(--ink-soft)", marginTop: 2 }}>
                      {SURFACE_LABELS[h.surface] || h.surface}
                      {h.notes ? ` · ${h.notes}` : ""}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </aside>
        )}
      </div>
    </div>
  );
}
