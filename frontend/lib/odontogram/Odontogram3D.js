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
import { getToothGeometry, toothMetrics, toothScale } from "./toothGeometry";
import { createArchCurve, distributeAlongArch } from "./archCurve";
import { buildGingivaGeometry } from "./gingivaGeometry";
import {
  enamelBumpTexture, enamelRoughnessTexture,
  gingivaBumpTexture, gingivaRoughnessTexture,
} from "./dentalTextures";

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

/* Geometría de las arcadas. Los semiejes se eligen para que la suma de
   los anchos mesio-distales reales quepa sin comprimir las piezas: la
   curva reparte por longitud de arco, no por ángulo. */
const ARCH_SHAPE = {
  permUpper: { rx: 5.50, rz: 4.20, y: 1.12 },
  permLower: { rx: 5.15, rz: 3.95, y: -1.12 },
  tempUpper: { rx: 3.05, rz: 2.35, y: 1.12 },
  tempLower: { rx: 2.85, rz: 2.20, y: -1.12 },
};
const ARCH_FROM = Math.PI * 0.06;
const ARCH_TO = Math.PI * 0.94;

/** Relieve que deja la raíz sobre la tabla vestibular; el canino es el mayor. */
function rootEminence(code) {
  const fam = toothFamily(code);
  if (fam === "canino") return 0.17;
  if (fam === "incisivo") return 0.09;
  if (fam === "premolar") return 0.07;
  return 0.05;
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
      camera.position.set(0, 7, 15);

      const renderer = new THREE.WebGLRenderer({
        antialias: true, alpha: true, preserveDrawingBuffer: true, // permite capturar la imagen
      });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.setSize(width, height);
      // Tono cinematográfico: evita que los blancos del esmalte se quemen
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 0.98;
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

      /* ── Iluminación de estudio clínico ──
         Principal cálida y alta (modela el volumen y proyecta la sombra),
         relleno frío lateral (abre las zonas oscuras sin aplanar),
         contraluz posterior (separa las piezas del fondo) y un rebote
         tenue desde abajo para que las caras inferiores no se cierren en
         negro, que es lo que delata una escena con una sola luz. */
      scene.add(new THREE.HemisphereLight(0xfff6ee, 0xa9b8c6, 0.38));

      const keyLight = new THREE.DirectionalLight(0xfff2e4, 1.5);
      keyLight.position.set(5.5, 13, 9);
      keyLight.castShadow = true;
      keyLight.shadow.mapSize.set(1024, 1024);
      keyLight.shadow.camera.near = 1;
      keyLight.shadow.camera.far = 34;
      // Encuadre ajustado a las arcadas: más texels de sombra sobre lo
      // que de verdad se ve, con el mismo coste de mapa.
      keyLight.shadow.camera.left = -8;
      keyLight.shadow.camera.right = 8;
      keyLight.shadow.camera.top = 8;
      keyLight.shadow.camera.bottom = -8;
      keyLight.shadow.bias = -0.0009;
      keyLight.shadow.normalBias = 0.02;
      keyLight.shadow.radius = 3;
      scene.add(keyLight);

      const fillLight = new THREE.DirectionalLight(0xd6e6f6, 0.5);
      fillLight.position.set(-9, 3.5, 6);
      scene.add(fillLight);

      const rimLight = new THREE.DirectionalLight(0xffffff, 0.85);
      rimLight.position.set(0, 4.5, -12);
      scene.add(rimLight);

      const bounceLight = new THREE.DirectionalLight(0xffd9c0, 0.28);
      bounceLight.position.set(0, -9, 4);
      scene.add(bounceLight);

      // Suelo receptor de sombra: da asiento a las arcadas sin verse
      const floorGeo = new THREE.PlaneGeometry(60, 60);
      const floorMat = new THREE.ShadowMaterial({ opacity: 0.2 });
      const floor = new THREE.Mesh(floorGeo, floorMat);
      floor.rotation.x = -Math.PI / 2;
      floor.position.y = -3.7;
      floor.receiveShadow = true;
      scene.add(floor);

      /* ── Texturas procedurales ──
         Se generan una vez y las comparten todas las piezas: es lo que
         rompe el brillo uniforme del plástico sin coste por objeto. */
      const texRoughEnamel = enamelRoughnessTexture(THREE);
      const texBumpEnamel = enamelBumpTexture(THREE);
      const texRoughGum = gingivaRoughnessTexture(THREE);
      const texBumpGum = gingivaBumpTexture(THREE);
      const textures = [texRoughEnamel, texBumpEnamel, texRoughGum, texBumpGum];

      // ── Arcadas ──
      const teeth = [];
      const group = new THREE.Group();

      /* ── Material de esmalte ──
         MeshPhysicalMaterial con capa de barniz (clearcoat) y algo de
         transmisión: el esmalte real es translúcido y deja pasar luz
         hacia la dentina, que es lo que impide que un diente se vea
         como plástico blanco. Cada pieza recibe su propia instancia
         porque el color y el resaltado se animan por separado.

         El marfil no va en `color` sino en el color de vértice de la
         geometría (esmalte translúcido en el borde, dentina en el cuello,
         cemento en la raíz), de modo que `color` queda libre para llevar
         el estado clínico sin perder ese degradado natural.

         `roughness` es un MULTIPLICADOR del mapa de rugosidad: 1 = tal
         cual lo dibuja la textura (corona pulida, raíz mate). Los
         materiales restauradores lo suben o lo bajan más abajo. */
      function enamelMaterial() {
        return new THREE.MeshPhysicalMaterial({
          color: 0xfdf7ec,
          vertexColors: true,
          roughness: 1,
          roughnessMap: texRoughEnamel,
          bumpMap: texBumpEnamel,
          bumpScale: 0.018,
          metalness: 0.0,
          /* Barniz suave y amplio. Con clearcoat casi 1 y muy liso, el
             reflejo se concentra en un punto blanco durísimo y la pieza
             pasa de esmalte a porcelana de baño. */
          clearcoat: 0.55,
          clearcoatRoughness: 0.22,
          transmission: 0.16,       // translucidez sutil
          thickness: 0.55,
          ior: 1.63,                // índice de refracción del esmalte
          attenuationColor: new THREE.Color(0xffe6c8),
          attenuationDistance: 1.2,
          emissive: new THREE.Color(0x000000),
          transparent: true,
          opacity: 1,
        });
      }

      /* Realce de selección.
         Antes era una copia ampliada de la pieza dibujada por su cara
         interna. Con el esmalte translúcido esa copia se compone en la
         pasada de transmisión y deja de quedar oculta tras el diente: la
         pieza seleccionada se pintaba entera de azul. Ahora el realce es
         una emisión sobre el propio material, que no puede taparlo, no
         añade 52 mallas a la escena y sigue sin falsear el color base
         (la emisión ilumina, no repinta). */
      const SELECT_GLOW = new THREE.Color(0x2e9bdc);

      /* ── Material gingival ──
         Opaco a propósito: la encía anterior era semitransparente y
         dejaba ver las raíces por dentro, que es justo lo que delataba
         el modelo. La sensación de tejido vivo la dan el brillo de
         terciopelo (`sheen`), la película húmeda del margen (`clearcoat`)
         y el punteado de la textura, no la transparencia. */
      function gingivaMaterial() {
        return new THREE.MeshPhysicalMaterial({
          color: 0xc9847d,
          vertexColors: true,
          roughness: 1,
          roughnessMap: texRoughGum,
          bumpMap: texBumpGum,
          bumpScale: 0.022,
          metalness: 0,
          /* Sin capa de barniz: en la encía el brillo húmedo lo da ya el
             mapa de rugosidad (margen brillante, encía adherida mate), y
             el barniz es un coste de sombreado que aquí no se nota. */
          sheen: 0.65,
          sheenColor: new THREE.Color(0xff9d92),
          sheenRoughness: 0.85,
        });
      }

      /* Caché de geometría: las piezas con la misma familia, dentición y
         número de raíces comparten malla (de 52 mallas únicas a unas
         diez). Se libera una sola vez al desmontar. */
      const geoCache = new Map();
      const gums = [];

      function buildArch(codes, shape, { upper, visible }) {
        const curve = createArchCurve(shape.rx, shape.rz, ARCH_FROM, ARCH_TO);
        const metrics = codes.map((c) => toothMetrics(c));
        const spots = distributeAlongArch(curve, metrics.map((m) => m.mdWidth), 0.02);

        codes.forEach((code, i) => {
          const geo = getToothGeometry(THREE, code, geoCache);
          const mesh = new THREE.Mesh(geo, enamelMaterial());
          mesh.castShadow = true;
          mesh.receiveShadow = true;

          const spot = spots[i];
          mesh.position.set(spot.x, shape.y, spot.z);
          /* Orientación explícita: el eje X local es mesio-distal y sigue
             la tangente de la arcada; el eje Z local es vestibular y
             apunta hacia fuera. La versión anterior usaba `lookAt`, que
             alineaba el eje equivocado y dejaba las piezas giradas 90°
             —de ahí que los incisivos se vieran como agujas y las
             coronas se solaparan entre sí. */
          mesh.rotation.set(0, Math.atan2(spot.nx, spot.nz), 0);
          // La arcada superior es la misma malla girada sobre su eje
          // vestíbulo-lingual: corona hacia abajo, vestibular intacto.
          if (upper) mesh.rotateZ(Math.PI);
          // Ligera inclinación vestibular, como en una arcada real
          mesh.rotateX((upper ? 1 : -1) * 0.05);

          // Ajuste de tamaño por pieza concreta (un lateral es más
          // estrecho que un central). Se guarda como escala base porque
          // la animación de selección la multiplica.
          const [sx, sy, sz] = toothScale(code);
          mesh.scale.set(sx, sy, sz);
          mesh.visible = visible;
          mesh.userData = { code, baseY: shape.y, baseScale: [sx, sy, sz] };

          group.add(mesh);
          teeth.push(mesh);
        });

        // ── Encía de esta arcada ──
        const placements = spots.map((spot, i) => ({
          length: spot.length,
          halfDepth: metrics[i].blDepth / 2,
          eminence: rootEminence(codes[i]),
        }));
        const gumGeo = buildGingivaGeometry(THREE, curve, placements, {
          upper,
          /* El margen se sitúa sobre la corona, no sobre el cuello: como
             el collar del perfil va por dentro de la pieza, la encía
             emerge algo más abajo que el plano del margen. Con solo 0.10
             el borde visible caía justo en la unión amelocementaria y
             dejaba ver el resalte cervical como una línea brillante
             cruzando todas las piezas. */
          marginY: shape.y + (upper ? -0.22 : 0.22),
          papilla: 0.26,
        });
        const gum = new THREE.Mesh(gumGeo, gingivaMaterial());
        /* La encía recibe sombra (la de las piezas sobre el tejido es la
           que da profundidad) pero no la proyecta: su silueta apenas
           aporta y así no entra en el paso de sombras, que recorre la
           escena entera en cada fotograma. */
        gum.castShadow = false;
        gum.receiveShadow = true;
        gum.visible = visible;
        group.add(gum);
        gums.push(gum);
      }

      buildArch(ARCHES.permUpper, ARCH_SHAPE.permUpper, { upper: true, visible: true });
      buildArch(ARCHES.permLower, ARCH_SHAPE.permLower, { upper: false, visible: true });
      buildArch(ARCHES.tempUpper, ARCH_SHAPE.tempUpper, { upper: true, visible: false });
      buildArch(ARCHES.tempLower, ARCH_SHAPE.tempLower, { upper: false, visible: false });

      scene.add(group);

      /* ── Órbita, zoom y desplazamiento (implementación propia, para no
         depender de complementos externos al paquete) ── */
      const state = { rotX: 0.38, rotY: 0, dist: 15, panX: 0, panY: 0 };
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
          // El realce multiplica la escala propia de la pieza, que ya
          // distingue un incisivo lateral de un central.
          const sc = t.userData.targetScale ?? 1;
          const [bx, by, bz] = t.userData.baseScale || [1, 1, 1];
          t.scale.lerp(new THREE.Vector3(bx * sc, by * sc, bz * sc), Math.min(1, dt * 9));
          /* Realce luminoso: aparece y desaparece con suavidad sobre la
             emisión que ya lleva la pieza por su estado clínico. */
          const to = (t.userData.targetOutline ?? 0) * (t.userData.targetOpacity ?? 1);
          const cur = t.userData.glow ?? 0;
          const next = cur + (to - cur) * Math.min(1, dt * 10);
          t.userData.glow = next;
          const base = t.userData.baseEmissive;
          if (base) {
            t.material.emissive.setRGB(
              base[0] + SELECT_GLOW.r * next * 0.42,
              base[1] + SELECT_GLOW.g * next * 0.42,
              base[2] + SELECT_GLOW.b * next * 0.42,
            );
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
          t.material.dispose();   // la geometría es compartida: se libera aparte
        });
        geoCache.forEach((g) => g.dispose());
        geoCache.clear();
        gums.forEach((g) => { g.geometry.dispose(); g.material.dispose(); });
        textures.forEach((t) => t.dispose());
        floorGeo.dispose();
        floorMat.dispose();
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

    /* Base casi blanca: el marfil, la dentina cervical y el cemento de
       la raíz los aporta el color de vértice de la geometría, así que
       este color queda libre para llevar el estado clínico. */
    const ENAMEL = new THREE.Color(0xfdf7ec);

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
      // Emisión de partida: el realce de selección se suma a ella
      t.userData.baseEmissive = [m.emissive.r, m.emissive.g, m.emissive.b];

      /* Materiales restauradores: coronas e implantes son metálicos y
         pulidos; las prótesis, cerámicas mates. La diferencia de
         acabado se percibe antes que la de color.

         `roughness` MULTIPLICA al mapa de rugosidad del esmalte (corona
         pulida, raíz mate): 1 deja la textura tal cual, por debajo pule
         y por encima matea. */
      if (/implante/.test(label)) {
        m.metalness = 0.92; m.roughness = 0.55; m.transmission = 0;
        m.clearcoat = 0.4;
      } else if (/corona/.test(label)) {
        m.metalness = 0.45; m.roughness = 0.45; m.transmission = 0.05;
        m.clearcoat = 1.0;
      } else if (/pr[óo]tesis/.test(label)) {
        m.metalness = 0.05; m.roughness = 1.25; m.transmission = 0.06;
        m.clearcoat = 0.5;
      } else {
        m.metalness = 0.0; m.roughness = 1.0; m.transmission = 0.16;
        m.clearcoat = 0.55;
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
    Object.assign(s.state, { rotX: 0.38, rotY: 0, dist: 15, panX: 0, panY: 0 });
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
