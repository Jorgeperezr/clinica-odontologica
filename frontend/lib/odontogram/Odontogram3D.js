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
import { toothFamily, isUpper, isDeciduous } from "./ToothArt";
import { toothJitter, toothPose } from "./toothGeometry";
import { createMeshProvider } from "./meshProvider";
import { createArchCurve, distributeAlongArch } from "./archCurve";
import {
  PERFIL_HUESO, TONO_HUESO, buildGingivaGeometry, medirEnvolvente,
} from "./gingivaGeometry";
import {
  enamelNormalTexture, enamelRoughnessTexture,
  gingivaNormalTexture, gingivaRoughnessTexture,
} from "./dentalTextures";

/* ── Color natural de cada pieza ──────────────────────────────────────
   Todas las piezas compartían un único marfil, rgb(253,247,236). Ese
   valor es MÁS CLARO que el B1 de la guía VITA Classical —rgb(208,194,168),
   el matiz más blanco de toda la guía—, así que la arcada se leía como
   una masa continua: sin diferencia de matiz, el ojo no separa una pieza
   de la siguiente.

   En una boca real el color no es uniforme y la variación no es aleatoria:

     · los CANINOS son las piezas más cromáticas, típicamente uno o dos
       matices por debajo de los incisivos;
     · los incisivos son los más claros;
     · premolares y molares quedan en medio, algo más saturados;
     · la dentición TEMPORAL es más blanca y más azulada que la
       permanente, que es justo por lo que un diente de leche al lado de
       uno definitivo se nota a simple vista.

   Los valores salen de convertir a sRGB los L*a*b* publicados de la guía
   VITA y quedarse con las PROPORCIONES entre matices, no con los valores
   crudos: el color del material se multiplica por el de vértice y luego
   lo ilumina la escena, así que poner el sRGB de VITA tal cual daría una
   arcada apagada. Las relaciones, en cambio, trasladan bien, y son las
   que dan la distinción.

   (Los L*a*b* de VITA varían algo entre estudios y geometrías de medida.
   Se usan como referencia de las relaciones, no como calibración.) */
const MARFIL_BASE = [253 / 255, 247 / 255, 236 / 255];   // el de antes ≈ A1

const MATIZ_VITA = {
  //            r       g       b     (proporción respecto a A1)
  B1:   [1.015, 1.032, 1.057],
  A1:   [1.000, 1.000, 1.000],
  A2:   [0.995, 0.968, 0.918],
  A3:   [0.985, 0.936, 0.843],
  "A3.5": [0.961, 0.888, 0.761],
};

const MATIZ_POR_FAMILIA = {
  incisivo: "A1",
  canino: "A3.5",
  premolar: "A2",
  molar: "A3",
};

function matizNatural(THREE, code) {
  const temporal = isDeciduous(code);
  const clave = temporal ? "B1" : (MATIZ_POR_FAMILIA[toothFamily(code)] || "A2");
  const k = MATIZ_VITA[clave];
  return new THREE.Color(
    Math.min(1, MARFIL_BASE[0] * k[0]),
    Math.min(1, MARFIL_BASE[1] * k[1]),
    Math.min(1, MARFIL_BASE[2] * k[2]),
  );
}

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

/* Capas por omisión: la boca como se ve en el sillón. El hueso arranca
   al 60 % para que, al bajar la encía, se vea dónde está la cresta sin
   tapar las raíces. */
const CAPAS_INICIALES = { encia: 1, hueso: 0.6, arcadas: "ambas", apertura: 0, denticion: "permanente" };
const CLAVE_CAPAS = "odontograma3dCapas";

/** Preferencia de esta persona en este navegador; nunca viaja al servidor. */
function leerCapas() {
  try {
    const v = JSON.parse(localStorage.getItem(CLAVE_CAPAS) || "null");
    return v && typeof v === "object" ? { ...CAPAS_INICIALES, ...v } : CAPAS_INICIALES;
  } catch {
    return CAPAS_INICIALES;       // modo privado o almacenamiento bloqueado
  }
}
function guardarCapas(c) {
  try { localStorage.setItem(CLAVE_CAPAS, JSON.stringify(c)); } catch { /* modo privado */ }
}

const VISTAS_RAPIDAS = [
  { clave: "frente", label: "Frente" },
  { clave: "oclusalSup", label: "Oclusal superior", arcadas: "sup" },
  { clave: "oclusalInf", label: "Oclusal inferior", arcadas: "inf" },
  { clave: "derecha", label: "Lado derecho" },
  { clave: "izquierda", label: "Lado izquierdo" },
];

/** Relieve que deja la raíz sobre la tabla vestibular; el canino es el mayor. */
function rootEminence(code) {
  const fam = toothFamily(code);
  if (fam === "canino") return 0.17;
  if (fam === "incisivo") return 0.09;
  if (fam === "premolar") return 0.07;
  return 0.05;
}

/**
 * Perfil gingival propio de cada zona de la arcada.
 *
 *   papillaH  altura de la papila: alta y afilada entre incisivos, baja
 *             y ancha entre molares, donde el espacio interdental es un
 *             nicho aplanado y no un pico.
 *   thickness grosor del tejido: la encía posterior es sensiblemente más
 *             gruesa que la del frente.
 *   margin    cuánto cubre el margen de la corona. En los posteriores se
 *             sitúa más apical, así que descubre algo menos de diente.
 *             Eran 0,18–0,24 (2–3 mm) y nadie lo notaba porque la encía se
 *             dibujaba del revés; al verse por fuera cubría una cuarta parte
 *             de cada corona. Medido con rayos horizontales sobre el 21:
 *             ahora queda en torno a 1 mm sobre el cuello, como en una
 *             encía sana.
 */
function gingivaProfile(code) {
  const fam = toothFamily(code);
  if (fam === "incisivo") return { papillaH: 0.30, thickness: 0.92, margin: 0.12 };
  if (fam === "canino") return { papillaH: 0.26, thickness: 1.00, margin: 0.13 };
  if (fam === "premolar") return { papillaH: 0.20, thickness: 1.08, margin: 0.11 };
  return { papillaH: 0.15, thickness: 1.16, margin: 0.10 };
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
  const [acabadoReducido, setAcabadoReducido] = useState(false);
  /* Se arranca con los valores por omisión y la preferencia guardada se
     lee ya en el navegador: leerla en el primer render daría un HTML
     distinto en el servidor y en el cliente. */
  const [capas, setCapas] = useState(CAPAS_INICIALES);
  const [capasCargadas, setCapasCargadas] = useState(false);
  useEffect(() => { setCapas(leerCapas()); setCapasCargadas(true); }, []);
  useEffect(() => { if (capasCargadas) guardarCapas(capas); }, [capas, capasCargadas]);
  const cambiarCapas = useCallback((c) => setCapas((prev) => ({ ...prev, ...c })), []);

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

      /* ── Tamaño del lienzo ──
         El alto era 460 fijo. En una pantalla ancha eso deja una franja
         apaisada con las arcadas pequeñas en el centro, y en una tableta
         vertical o un teléfono el arco no cabe a lo ancho y se sale.
         Se deriva del ancho para conservar una proporción legible, con
         topes para que ni se aplaste ni se coma la pantalla entera. */
      function medidas() {
        const w = Math.max(260, mount.clientWidth || 800);
        const h = Math.round(Math.min(560, Math.max(320, w * 0.42)));
        return { w, h };
      }
      let { w: width, h: height } = medidas();

      /* Cuánto hay que alejarse para que el arco quepa a lo ancho. Con
         un lienzo estrecho, la distancia pensada para escritorio deja las
         piezas de los extremos fuera del encuadre: el profesional ve el
         centro de la boca y tiene que arrastrar para llegar a los
         molares. Se corrige por la relación de aspecto, no por el ancho
         en píxeles, que es lo que de verdad determina el recorte. */
      const ASPECTO_COMODO = 2.2;
      function distanciaMinima(aspect) {
        return aspect >= ASPECTO_COMODO ? 11 : 11 * (ASPECTO_COMODO / Math.max(0.6, aspect));
      }

      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(38, width / height, 0.1, 200);
      camera.position.set(0, 5.4, 13.5);

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

      /* ── Adaptación al tema claro / oscuro ──
         El lienzo es transparente y se ve sobre el fondo de la
         aplicación. Con la misma exposición en ambos modos, en oscuro las
         piezas quedan como un recorte deslumbrante sobre el fondo y en
         claro se lavan. Se mide la luminancia real del fondo —no el
         nombre del tema— para que funcione también con los colores de
         marca de cada clínica. */
      const themeLights = [];
      function applyTheme() {
        let lum = 1;
        try {
          const bg = getComputedStyle(mount).backgroundColor || "";
          const m = bg.match(/(\d+)[,\s]+(\d+)[,\s]+(\d+)/);
          if (m) {
            lum = (0.2126 * +m[1] + 0.7152 * +m[2] + 0.0722 * +m[3]) / 255;
          }
        } catch { /* se queda en claro */ }
        const dark = lum < 0.45;
        renderer.toneMappingExposure = dark ? 0.86 : 1.0;
        themeLights.forEach(({ light, base }) => {
          light.intensity = base * (dark ? 0.86 : 1);
        });
        if (scene.environment) scene.environmentIntensity = dark ? 0.65 : 1;
      }
      const themeObserver = new MutationObserver(applyTheme);
      themeObserver.observe(document.documentElement,
                            { attributes: true, attributeFilter: ["data-theme", "class"] });

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
         negro, que es lo que delata una escena con una sola luz.

         El reparto está deliberadamente CONTRASTADO: repartir la luz a
         partes iguales entre los cuatro focos ilumina cada cara por igual
         y aplana el volumen, que es lo que hacía que las arcadas se
         leyeran como una masa clara continua. */
      scene.add(new THREE.HemisphereLight(0xfff6ee, 0xa9b8c6, 0.26));

      const keyLight = new THREE.DirectionalLight(0xfff2e4, 1.95);
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
      themeLights.push({ light: keyLight, base: keyLight.intensity });

      const fillLight = new THREE.DirectionalLight(0xd6e6f6, 0.32);
      fillLight.position.set(-9, 3.5, 6);
      scene.add(fillLight);
      themeLights.push({ light: fillLight, base: fillLight.intensity });

      const rimLight = new THREE.DirectionalLight(0xffffff, 0.55);
      rimLight.position.set(0, 4.5, -12);
      scene.add(rimLight);
      themeLights.push({ light: rimLight, base: rimLight.intensity });

      const bounceLight = new THREE.DirectionalLight(0xffd9c0, 0.18);
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
      const texNormEnamel = enamelNormalTexture(THREE);
      const texRoughGum = gingivaRoughnessTexture(THREE);
      const texNormGum = gingivaNormalTexture(THREE);
      const textures = [texRoughEnamel, texNormEnamel, texRoughGum, texNormGum];

      /* ── Oclusión ambiental en espacio de pantalla (GTAO) ──
         El salto de acabado que separa un render clínico de uno plano no
         está en la malla sino en la luz de contacto: los rincones donde
         dos superficies se acercan —tronera interdental, surco gingival,
         fondo de fisura, encuentro entre corona y encía— reciben menos
         luz del entorno. Ninguna luz direccional reproduce eso; hay que
         calcularlo a partir de la profundidad y las normales de la
         escena, que es justo lo que hace GTAO.

         Se monta con repliegue: si el paso no está disponible o falla al
         compilar, se dibuja directo como hasta ahora. La escena nunca
         depende de que el post-proceso exista. */
      let composer = null;
      let gtao = null;
      try {
        const [{ EffectComposer }, { RenderPass }, { GTAOPass }, { OutputPass }] =
          await Promise.all([
            import("three/examples/jsm/postprocessing/EffectComposer.js"),
            import("three/examples/jsm/postprocessing/RenderPass.js"),
            import("three/examples/jsm/postprocessing/GTAOPass.js"),
            import("three/examples/jsm/postprocessing/OutputPass.js"),
          ]);
        composer = new EffectComposer(renderer);
        composer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        composer.setSize(width, height);
        composer.addPass(new RenderPass(scene, camera));
        gtao = new GTAOPass(scene, camera, width, height);
        // Radio en unidades de escena: las arcadas miden ~11, así que un
        // radio corto mantiene la sombra pegada a los contactos en vez de
        // ensuciar toda la pieza.
        gtao.updateGtaoMaterial({
          radius: 0.32, distanceExponent: 1.4, thickness: 0.5,
          scale: 1.0, samples: 12, distanceFallOff: 1.0, screenSpaceRadius: false,
        });
        gtao.blendIntensity = 0.9;
        composer.addPass(gtao);
        composer.addPass(new OutputPass());
      } catch {
        composer = null;   // se dibuja sin post-proceso
      }

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
          normalMap: texNormEnamel,
          normalScale: new THREE.Vector2(0.16, 0.16),
          metalness: 0.0,
          /* Barniz suave y amplio. Con clearcoat casi 1 y muy liso, el
             reflejo se concentra en un punto blanco durísimo y la pieza
             pasa de esmalte a porcelana de baño. */
          /* Barniz suave y amplio. Con clearcoat casi 1 y muy liso, el
             reflejo se concentra en un punto blanco durísimo y la pieza
             pasa de esmalte a porcelana de baño.

             Se probó a bajarlos (0.42 / 0.10) suponiendo que el reflejo
             del entorno tapaba el matiz propio de cada pieza. Se midió
             el resultado y NO era así: el canino y el incisivo central
             seguían dando el mismo amarilleo, 20 contra 20 sobre 255, y
             lo único que cambió fue que toda la arcada se oscureció ocho
             unidades. Se dejan donde estaban: bajarlos no compraba nada
             y costaba realismo en el esmalte. */
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
          normalMap: texNormGum,
          /* Era 0,45 y se ajustó mirando la cara INTERIOR de la encía (se
             dibujaba del revés). Vista por fuera, esa intensidad arrugaba
             el tejido como papel: el punteado de la encía adherida es una
             piel de naranja fina que solo se aprecia de cerca. */
          normalScale: new THREE.Vector2(0.11, 0.11),
          metalness: 0,
          /* Sin capa de barniz: en la encía el brillo húmedo lo da ya el
             mapa de rugosidad (margen brillante, encía adherida mate), y
             el barniz es un coste de sombreado que aquí no se nota. */
          sheen: 0.65,
          sheenColor: new THREE.Color(0xff9d92),
          sheenRoughness: 0.85,
        });
      }

      /* Proveedor de mallas. El motor no sabe si el diente lo fabrica el
         generador procedural o viene de un .glb dejado en
         `public/models/teeth/`: pide la pieza por su número FDI y recibe
         geometría, escala y medidas en el marco local canónico. Las
         piezas equivalentes comparten malla, así que de 52 mallas únicas
         se pasa a una docena. */
      /* ── Material del hueso alveolar ──
         Solo se ve cuando la encía se vuelve translúcida: con la encía
         opaca queda oculto y ni se dibuja. Cortical mate, marfil apagado. */
      function huesoMaterial() {
        return new THREE.MeshStandardMaterial({
          color: 0xe4d6bb,
          vertexColors: true,
          roughness: 0.88,
          metalness: 0,
        });
      }

      const meshProvider = await createMeshProvider(THREE);
      const gums = [];
      const huesos = [];
      /* Una rama por arcada: la apertura de la boca y el mostrar solo una
         arcada se hacen moviendo u ocultando la rama entera. */
      const arcadas = { sup: new THREE.Group(), inf: new THREE.Group() };
      group.add(arcadas.sup, arcadas.inf);

      function buildArch(codes, shape, { upper, visible, denticion }) {
        const rama = upper ? arcadas.sup : arcadas.inf;
        const arcada = upper ? "sup" : "inf";
        const piezas = [];
        const curve = createArchCurve(shape.rx, shape.rz, ARCH_FROM, ARCH_TO);
        const parts = codes.map((c) => meshProvider.getTooth(c));
        const metrics = parts.map((p) => p.metrics);
        /* Sin holgura entre piezas: las secciones llevan convexidad
           proximal, así que a separación cero las coronas se tocan en su
           punto de contacto, como en una arcada real. Con holgura se
           veían rendijas de luz entre diente y diente. */
        const spots = distributeAlongArch(curve, metrics.map((m) => m.mdWidth), 0.012);
        const poses = codes.map((c) => toothPose(c));

        codes.forEach((code, i) => {
          const part = parts[i];
          const mesh = new THREE.Mesh(part.geometry, enamelMaterial());
          mesh.castShadow = true;
          mesh.receiveShadow = true;

          const spot = spots[i];
          const pose = poses[i];
          /* Curva de Spee: los sectores posteriores se acercan al plano
             oclusal. Sin ella las muelas —de corona más baja— dejan un
             hueco creciente hacia atrás. */
          const jit = toothJitter(code);
          const cervixY = shape.y
            + (upper ? -(pose.rise + jit.rise) : pose.rise + jit.rise);
          mesh.position.set(spot.x, cervixY, spot.z);
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
          /* Torque e inclinación por pieza. Girar la arcada entera un
             ángulo fijo deja todas las coronas paralelas, que es el rasgo
             que delata un montaje a mano; cada familia tiene el suyo. */
          const side = i < codes.length / 2 ? -1 : 1;
          mesh.rotateZ(side * (pose.tip + jit.tip) * (upper ? -1 : 1));
          mesh.rotateX(upper ? -(pose.torque + jit.torque) : pose.torque + jit.torque);
          // Pequeña rotación propia: ninguna pieza queda perfectamente alineada
          mesh.rotateY(jit.rotY);

          // Ajuste de tamaño por pieza concreta (un lateral es más
          // estrecho que un central). Se guarda como escala base porque
          // la animación de selección la multiplica.
          const sx = part.scale[0] * jit.scale[0];
          const sy = part.scale[1] * jit.scale[1];
          const sz = part.scale[2] * jit.scale[2];
          mesh.scale.set(sx, sy, sz);
          mesh.visible = visible;
          mesh.userData = { code, baseY: cervixY, baseScale: [sx, sy, sz], arcada, denticion };
          // Primero los dientes y después, encima, los tejidos
          // translúcidos: ver `aplicarCapas`.
          mesh.renderOrder = 0;

          rama.add(mesh);
          teeth.push(mesh);
          piezas.push({ mesh, spot });
        });

        /* Hasta dónde llegan de verdad las raíces de esta arcada, ya con
           su inclinación y su escala. La encía y el hueso se construyen
           para envolverlo (ver `gingivaGeometry.js`). */
        const envolvente = medirEnvolvente(THREE, piezas, { upper });

        // ── Encía de esta arcada ──
        const placements = spots.map((spot, i) => {
          const jr = toothJitter(codes[i]).rise;
          const cy = shape.y
            + (upper ? -(poses[i].rise + jr) : poses[i].rise + jr);
          const gp = gingivaProfile(codes[i]);
          // Cada margen tiene su propia altura: un festón regular delata
          // el trazado automático tanto como una arcada de piezas iguales
          const jm = (toothJitter(codes[i]).scale[1] - 1) * 0.5;
          return {
            length: spot.length,
            cervixY: cy,
            halfDepth: metrics[i].blDepth / 2,
            eminence: rootEminence(codes[i]),
            papillaH: gp.papillaH,
            thickness: gp.thickness,
            /* El margen se sitúa sobre la corona, no sobre el cuello: como
               el collar del perfil va por dentro de la pieza, la encía
               emerge algo más abajo que el plano del margen. Y va ligado
               al cuello REAL de cada pieza, que la curva de Spee desplaza:
               con un margen a altura constante, el tejido se despegaba del
               cuello en unas piezas y montaba sobre la corona en otras. */
            marginY: cy + (upper ? -(gp.margin + jm) : gp.margin + jm),
          };
        });
        const gumGeo = buildGingivaGeometry(THREE, curve, placements,
                                            { upper, envolvente, holgura: 0.11 });
        const gum = new THREE.Mesh(gumGeo, gingivaMaterial());
        /* La encía proyecta sombra. Antes no, para ahorrar el paso de
           sombras, y la sombra del suelo la hacían las raíces, que están
           dentro de ella: salía un peine de púas debajo de cada arcada.
           Con la encía translúcida se apaga (ver `aplicarCapas`) y
           vuelven a verse las raíces, que es lo coherente. */
        gum.castShadow = true;
        gum.receiveShadow = true;
        gum.visible = visible;
        gum.renderOrder = 2;
        gum.userData = { arcada, denticion };
        rama.add(gum);
        gums.push(gum);

        /* ── Hueso alveolar ──
           Misma curva y misma envolvente, con la cresta 0,17 por debajo
           del cuello (1,5–2 mm, lo de una boca sana) y una holgura menor
           que la de la encía, para que quede siempre por dentro de ella. */
        const crestas = placements.map((p) => ({
          ...p,
          marginY: p.cervixY + (upper ? 0.17 : -0.17),
          eminence: p.eminence * 0.8,
        }));
        const hueso = new THREE.Mesh(
          buildGingivaGeometry(THREE, curve, crestas, {
            upper, envolvente, holgura: 0.035,
            perfil: PERFIL_HUESO, tonos: TONO_HUESO, papila: 0.55,
          }),
          huesoMaterial(),
        );
        hueso.castShadow = false;
        hueso.receiveShadow = true;
        hueso.visible = false;          // lo enciende `aplicarCapas`
        hueso.renderOrder = 1;
        hueso.userData = { arcada, denticion };
        rama.add(hueso);
        huesos.push(hueso);
      }

      buildArch(ARCHES.permUpper, ARCH_SHAPE.permUpper, { upper: true, visible: true, denticion: "permanente" });
      buildArch(ARCHES.permLower, ARCH_SHAPE.permLower, { upper: false, visible: true, denticion: "permanente" });
      buildArch(ARCHES.tempUpper, ARCH_SHAPE.tempUpper, { upper: true, visible: false, denticion: "temporal" });
      buildArch(ARCHES.tempLower, ARCH_SHAPE.tempLower, { upper: false, visible: false, denticion: "temporal" });

      scene.add(group);

      /* ── Capas: encía, hueso, arcadas, apertura y dentición ──
         La encía a 100 % es la de siempre: opaca, entra en la pasada de
         transmisión del esmalte y en la oclusión ambiental. Por debajo se
         vuelve translúcida SIN escribir profundidad y se dibuja después de
         los dientes (`renderOrder`), así las raíces se ven a través de
         ella en vez de quedar recortadas. Lo mismo el hueso, que va entre
         medias. El orden explícito hace falta porque three ordena los
         objetos translúcidos por la distancia a su origen, y el de una
         encía que rodea toda la boca no dice nada útil. */
      const capas = { encia: 1, hueso: 0.6, arcadas: "ambas", apertura: 0, denticion: "permanente" };
      function visibleSegun(ud) {
        return ud.denticion === capas.denticion
          && (capas.arcadas === "ambas" || capas.arcadas === ud.arcada);
      }
      function translucir(m, opacidad) {
        const t = opacidad < 1;
        if (m.transparent !== t) {
          m.transparent = t;
          m.depthWrite = !t;
          m.needsUpdate = true;      // cambia el programa del sombreador
        }
        m.opacity = opacidad;
      }
      function aplicarCapas(nuevas) {
        Object.assign(capas, nuevas);
        for (const t of teeth) t.visible = visibleSegun(t.userData);
        for (const g of gums) {
          g.visible = visibleSegun(g.userData) && capas.encia > 0;
          g.castShadow = capas.encia >= 1;
          translucir(g.material, capas.encia);
        }
        for (const h of huesos) {
          // Con la encía opaca el hueso queda tapado: no se dibuja.
          h.visible = visibleSegun(h.userData) && capas.encia < 1 && capas.hueso > 0;
          translucir(h.material, capas.hueso);
        }
      }
      aplicarCapas({});

      /* ── Órbita, zoom y desplazamiento (implementación propia, para no
         depender de complementos externos al paquete) ── */
      const state = {
        rotX: 0.30, rotY: 0,
        dist: Math.max(13.5, distanciaMinima(width / height)),
        panX: 0, panY: 0, panZ: 0,
      };
      let dragging = null, lastX = 0, lastY = 0;
      /* Cuánto se movió el puntero desde que se pulsó. El navegador
         dispara `click` al soltar aunque haya habido arrastre, así que
         girar el modelo seleccionaba la pieza que quedara bajo el cursor. */
      let iniX = 0, iniY = 0, recorrido = 0;

      const el = renderer.domElement;
      el.style.touchAction = "none";
      el.style.cursor = "grab";

      const onDown = (e) => {
        dragging = e.shiftKey || e.button === 2 ? "pan" : "rotate";
        lastX = e.clientX; lastY = e.clientY;
        iniX = e.clientX; iniY = e.clientY; recorrido = 0;
        el.setPointerCapture?.(e.pointerId);
        el.style.cursor = "grabbing";
      };
      const onMove = (e) => {
        if (!dragging) { pickHover(e); return; }
        const dx = e.clientX - lastX, dy = e.clientY - lastY;
        lastX = e.clientX; lastY = e.clientY;
        recorrido = Math.max(recorrido, Math.hypot(e.clientX - iniX, e.clientY - iniY));
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

      /* Vistas rápidas. Derecha e izquierda son las del PACIENTE: su
         derecha (cuadrantes 1 y 4) está en −x, a la izquierda de quien
         mira de frente. */
      /* Las oclusales miran al CENTRO de la arcada, que está adelantado
         (z ≈ 1,9) y a la altura de su plano oclusal: apuntando al origen,
         como las demás, la arcada quedaba cortada en el borde. */
      const VISTAS = {
        frente: { rotX: 0.30, rotY: 0 },
        oclusalSup: { rotX: -1.25, rotY: 0, panY: 0.5, panZ: 1.9 },
        oclusalInf: { rotX: 1.32, rotY: 0, panY: -0.5, panZ: 1.9 },
        derecha: { rotX: 0.18, rotY: -1.35 },
        izquierda: { rotX: 0.18, rotY: 1.35 },
      };
      function vista(clave) {
        if (VISTAS[clave]) Object.assign(state, { panX: 0, panY: 0, panZ: 0 }, VISTAS[clave]);
      }

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
        if (recorrido > 5) return;      // fue un giro, no un clic
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
      /* Salvaguarda de rendimiento. El post-proceso de oclusión ambiental
         mejora mucho el acabado pero cuesta una pasada extra por
         fotograma, y el abanico de tabletas es demasiado amplio para
         decidirlo a priori. Se mide el coste real durante el primer
         medio segundo y, si el equipo no lo sostiene con holgura, se
         desactiva solo: antes fluidez que oclusión. */
      let probeFrames = 0, probeTime = 0;
      function loop() {
        raf = requestAnimationFrame(loop);
        const dt = Math.min(clock.getDelta(), 0.05);
        if (composer && probeFrames < 40) {
          probeFrames++;
          probeTime += dt;
          if (probeFrames === 40 && probeTime / 40 > 0.028) {   // < 35 fps
            composer = null;
            /* Se apagaba en silencio, y eso deja al profesional mirando
               una imagen más plana sin saber por qué: la oclusión es lo
               que hunde las troneras y separa una pieza de la siguiente.
               Ahora se dice, para que quien vea el modelo «raro» sepa que
               es el equipo y no su paciente, y para que sea una pista si
               alguien pregunta por la calidad de la imagen. */
            setAcabadoReducido(true);
          }
        }

        // Cámara orbital interpolada
        const cx = Math.sin(state.rotY) * Math.cos(state.rotX) * state.dist;
        const cy = Math.sin(state.rotX) * state.dist;
        const cz = Math.cos(state.rotY) * Math.cos(state.rotX) * state.dist;
        camera.position.lerp(new THREE.Vector3(cx + state.panX, cy + state.panY, cz + state.panZ), 0.18);
        camera.lookAt(state.panX, state.panY, state.panZ);

        /* Apertura de la boca: cada arcada se aleja del plano oclusal.
           El suelo que recibe la sombra acompaña a la inferior. */
        const ab = capas.apertura * 1.4;
        const kA = Math.min(1, dt * 8);
        arcadas.sup.position.y += (ab - arcadas.sup.position.y) * kA;
        arcadas.inf.position.y += (-ab - arcadas.inf.position.y) * kA;
        floor.position.y = -3.7 + arcadas.inf.position.y;

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
        if (composer) composer.render();
        else renderer.render(scene, camera);
      }
      loop();

      /* Antes esto solo escuchaba a `window.resize` y solo cambiaba el
         ancho. Dos problemas, los dos comprobados con el navegador
         emulando una tableta:

         · `window.resize` no se dispara cuando lo que cambia es el
           CONTENEDOR y no la ventana: plegar la barra lateral, abrir el
           panel lateral de la pieza o cambiar de pestaña dejaban el
           lienzo con el tamaño anterior. `ResizeObserver` observa lo que
           de verdad importa.
         · Había un bloqueo mutuo. three.js le pone al `<canvas>` un
           tamaño en píxeles, y como la columna de la rejilla era `1fr`
           —cuyo mínimo es el contenido— el contenedor no podía encoger
           por debajo del lienzo; el manejador leía siempre el mismo
           ancho y no ajustaba nada. Medido: 1146×460 en escritorio, en
           tableta apaisada, en tableta vertical y en un teléfono, con el
           panel desbordándose a 1420 px de scroll. La columna pasa a
           `minmax(0,1fr)` y con eso el contenedor ya puede encoger. */
      let ultimoAncho = 0, ultimoAlto = 0;
      const onResize = () => {
        const { w, h } = medidas();
        if (w === ultimoAncho && h === ultimoAlto) return;
        ultimoAncho = w; ultimoAlto = h;
        mount.style.height = `${h}px`;
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        renderer.setSize(w, h);
        composer?.setSize(w, h);
        gtao?.setSize(w, h);
        // Que no se queden los molares fuera al estrecharse el lienzo.
        state.dist = Math.max(state.dist, distanciaMinima(w / h));
      };
      onResize();
      const observador = new ResizeObserver(onResize);
      observador.observe(mount);
      window.addEventListener("resize", onResize);

      applyTheme();
      sceneRef.current = { THREE, scene, camera, renderer, teeth, state, composer, aplicarCapas, vista };
      if (!cancelled) setReady(true);

      cleanup = () => {
        cancelAnimationFrame(raf);
        themeObserver.disconnect();
        observador.disconnect();
        window.removeEventListener("resize", onResize);
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
        el.removeEventListener("pointerdown", onDown);
        el.removeEventListener("wheel", onWheel);
        el.removeEventListener("click", onClick);
        teeth.forEach((t) => {
          t.material.dispose();   // la geometría es compartida: se libera aparte
        });
        meshProvider.dispose();
        [...gums, ...huesos].forEach((g) => { g.geometry.dispose(); g.material.dispose(); });
        textures.forEach((t) => t.dispose());
        floorGeo.dispose();
        floorMat.dispose();
        gtao?.dispose?.();
        composer?.dispose?.();
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

    for (const t of teeth) {
      const code = t.userData.code;
      /* El matiz de ESTA pieza, no uno común a toda la boca. El marfil
         cervical y el cemento de la raíz los sigue aportando el color de
         vértice de la geometría; este color queda libre para llevar
         encima el estado clínico. */
      const ENAMEL = matizNatural(THREE, code);
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

  /* Capas → escena. */
  useEffect(() => { sceneRef.current?.aplicarCapas(capas); }, [capas, ready]);

  /* Si se selecciona una pieza temporal desde otra vista (o al revés),
     se muestra la dentición que la contiene: si no, la pieza elegida
     estaría oculta y el panel hablaría de algo que no se ve. */
  useEffect(() => {
    if (!selectedTooth) return;
    const d = isDeciduous(selectedTooth) ? "temporal" : "permanente";
    setCapas((prev) => (prev.denticion === d ? prev : { ...prev, denticion: d }));
  }, [selectedTooth]);

  const irAVista = useCallback((v) => {
    sceneRef.current?.vista(v.clave);
    // Desde oclusal la otra arcada tapa la que se quiere ver.
    cambiarCapas({ arcadas: v.arcadas || "ambas" });
  }, [cambiarCapas]);

  /* ── Captura de imagen para informes ── */
  const capture = useCallback(() => {
    const s = sceneRef.current;
    if (!s) return;
    // Se redibuja por la MISMA cadena que la pantalla: si se llamara a
    // renderer.render directamente, la imagen del informe saldría sin la
    // oclusión ambiental y no coincidiría con lo que ve el profesional.
    if (s.composer) s.composer.render();
    else s.renderer.render(s.scene, s.camera);
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
    Object.assign(s.state, { rotX: 0.30, rotY: 0, dist: 13.5, panX: 0, panY: 0, panZ: 0 });
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

      <CapasControles capas={capas} onCambio={cambiarCapas} onVista={irAVista} />

      <div style={{ display: "grid", gap: 14,
                    /* `minmax(0,1fr)` también sin selección: con `1fr` a
                       secas el mínimo de la columna es su contenido, y el
                       lienzo con tamaño en píxeles impedía encoger al
                       contenedor. Ahí estaba el desbordamiento en tableta. */
                    gridTemplateColumns: selectedTooth ? "minmax(0,1fr) minmax(0,300px)" : "minmax(0,1fr)" }}>
        {/* Lienzo 3D */}
        <div>
          <div ref={mountRef}
               /* El alto lo ajusta el motor con el ancho real (ver
                  `medidas`); este es solo el valor de partida mientras
                  carga. */
               style={{ width: "100%", height: 460, minWidth: 0, borderRadius: "var(--radius)",
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
          {acabadoReducido && (
            <p style={{ fontSize: 12, color: "var(--ink-faint)", marginTop: 2 }}>
              Este equipo no sostiene la oclusión ambiental con holgura, así que
              se ha desactivado para mantener el giro fluido. El modelo se ve más
              plano —menos sombra entre las piezas—, pero los datos clínicos y la
              selección funcionan igual.
            </p>
          )}
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

const ETIQUETA = {
  fontSize: 11, fontWeight: 700, letterSpacing: ".05em",
  textTransform: "uppercase", color: "var(--ink-faint)",
};

/** Deslizador de 0 a 100 % con su valor a la vista. */
function Deslizador({ etiqueta, valor, onCambio, ayuda, atenuado = false }) {
  const pct = Math.round(valor * 100);
  return (
    <label style={{ display: "grid", gap: 3, minWidth: 160, opacity: atenuado ? 0.55 : 1 }}
           title={ayuda}>
      <span style={{ ...ETIQUETA, display: "flex", justifyContent: "space-between", gap: 10 }}>
        {etiqueta}
        <span className="tabular" style={{ color: "var(--ink-soft)" }}>{pct} %</span>
      </span>
      <input type="range" min="0" max="100" step="5" value={pct}
             aria-label={etiqueta}
             onChange={(e) => onCambio(Number(e.target.value) / 100)} />
    </label>
  );
}

/** Grupo de botones excluyentes. */
function Segmentado({ etiqueta, opciones, valor, onCambio }) {
  return (
    <div style={{ display: "grid", gap: 3 }}>
      <span style={ETIQUETA}>{etiqueta}</span>
      <div role="group" aria-label={etiqueta} style={{ display: "flex", gap: 3 }}>
        {opciones.map(([v, t]) => (
          <button key={v} type="button" onClick={() => onCambio(v)}
                  aria-pressed={valor === v}
                  className={`btn ${valor === v ? "btn-primary" : "btn-ghost"}`}
                  style={{ fontSize: 12, padding: "3px 9px" }}>
            {t}
          </button>
        ))}
      </div>
    </div>
  );
}

/**
 * Capas y vista. Solo cambian lo que se VE: ninguna toca los datos
 * clínicos ni la selección.
 */
function CapasControles({ capas, onCambio, onVista }) {
  const verRaices = capas.encia < 1;
  return (
    <div className="card" style={{ padding: "10px 14px", marginBottom: 10,
                                   display: "flex", flexWrap: "wrap", gap: "12px 22px",
                                   alignItems: "end" }}>
      <Deslizador etiqueta="Encía" valor={capas.encia}
                  ayuda="Bájala para ver las raíces y el hueso"
                  onCambio={(v) => onCambio({ encia: v })} />
      {/* Con la encía opaca el hueso queda tapado: se atenúa el control
          para que no parezca que no responde. */}
      <Deslizador etiqueta="Hueso alveolar" valor={capas.hueso} atenuado={!verRaices}
                  ayuda={verRaices ? "Opacidad del hueso que rodea las raíces"
                                   : "Se ve al bajar la opacidad de la encía"}
                  onCambio={(v) => onCambio({ hueso: v })} />
      <Deslizador etiqueta="Apertura" valor={capas.apertura}
                  ayuda="Separa las arcadas para ver las caras oclusales"
                  onCambio={(v) => onCambio({ apertura: v })} />
      <Segmentado etiqueta="Arcadas" valor={capas.arcadas}
                  opciones={[["ambas", "Ambas"], ["sup", "Superior"], ["inf", "Inferior"]]}
                  onCambio={(v) => onCambio({ arcadas: v })} />
      <Segmentado etiqueta="Dentición" valor={capas.denticion}
                  opciones={[["permanente", "Permanente"], ["temporal", "Temporal"]]}
                  onCambio={(v) => onCambio({ denticion: v })} />
      <div style={{ display: "grid", gap: 3 }}>
        <span style={ETIQUETA}>Vista</span>
        <div style={{ display: "flex", gap: 3, flexWrap: "wrap" }}>
          {VISTAS_RAPIDAS.map((v) => (
            <button key={v.clave} type="button" className="btn btn-ghost"
                    style={{ fontSize: 12, padding: "3px 9px" }} onClick={() => onVista(v)}>
              {v.label}
            </button>
          ))}
        </div>
      </div>
      <div style={{ display: "flex", gap: 6, marginLeft: "auto" }}>
        <button type="button" className="btn btn-ghost" style={{ fontSize: 12, padding: "3px 9px" }}
                onClick={() => onCambio(verRaices ? { encia: 1 } : { encia: 0.25, hueso: 0 })}>
          {verRaices ? "Encía opaca" : "Ver raíces"}
        </button>
        <button type="button" className="btn btn-ghost" style={{ fontSize: 12, padding: "3px 9px" }}
                onClick={() => onCambio(CAPAS_INICIALES)}>
          Restablecer capas
        </button>
      </div>
    </div>
  );
}
