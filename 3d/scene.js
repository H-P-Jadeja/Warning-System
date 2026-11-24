/* GLOF-Watch 3D flood simulator (Three.js r128).
 * Sections: 1 terrain maths, 2 scene build, 3 state & data, 4 flood physics, 5 UI/input, 6 game loop.
 */
(() => {
"use strict";

// ---------- 1. Terrain maths (world: lake at z=-37, valley runs toward +z) ----------
const COLORS = { Low: 0x4e9f6b, Watch: 0xc99a2e, Warning: 0xd9772b, Critical: 0xb3261e };
const LAKE_Z = -37, DAM_Z = -30, H0 = (50 - LAKE_Z) * 0.32;   // H0 = lake surface height
const KM_PER_UNIT = 0.25, FRONT_KMH = 30, RAMP_SECONDS = 14;
const cx = (z) => 5 * Math.sin(z / 14);                         // valley centre line

function rawHeight(x, z) {
  const d = x - cx(z);
  return (50 - z) * 0.32 + Math.min(0.035 * d * d, 22)
    + 0.6 * Math.sin(x * 0.3 + z * 0.2) * Math.sin(z * 0.17);
}
function height(x, z) {                                          // carve a bowl for the lake
  const d = x - cx(z);
  const m = Math.exp(-((z - LAKE_Z) ** 2) / 128 - (d * d) / 98);
  return rawHeight(x, z) * (1 - m) + (H0 - 2.2) * m;
}

// ---------- 2. Scene ----------
const canvas = document.getElementById("c");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
const SKY_CALM = new THREE.Color(0xcfe3ec), SKY_ALARM = new THREE.Color(0xe6c3b8);
const scene = new THREE.Scene();
scene.background = SKY_CALM.clone();
scene.fog = new THREE.Fog(0xcfe3ec, 90, 260);
const camera = new THREE.PerspectiveCamera(55, 1, 0.5, 600);
const controls = new THREE.OrbitControls(camera, canvas);
controls.enableDamping = true;
const world = new THREE.Group();            // shaken as a whole during ground vibration
scene.add(world);

scene.add(new THREE.HemisphereLight(0xffffff, 0x6b7a80, 0.8));
const sun = new THREE.DirectionalLight(0xffffff, 0.9);
sun.position.set(40, 80, -20);
scene.add(sun);

(function buildTerrain() {
  const geo = new THREE.PlaneGeometry(70, 100, 140, 200);
  geo.rotateX(-Math.PI / 2);
  const pos = geo.attributes.position, col = new Float32Array(pos.count * 3);
  const snow = new THREE.Color(0xf2f6f8), rock = new THREE.Color(0x7d7a74),
        scree = new THREE.Color(0x8d8a6f), grass = new THREE.Color(0x6e8c5a), c = new THREE.Color();
  for (let i = 0; i < pos.count; i++) {
    const h = height(pos.getX(i), pos.getZ(i));
    pos.setY(i, h);
    if (h > 26) c.copy(snow);
    else if (h > 14) c.copy(rock).lerp(snow, Math.max(0, (h - 22) / 4));
    else if (h > 6) c.copy(scree).lerp(rock, (h - 6) / 8);
    else c.copy(grass).lerp(scree, h / 6);
    col.set([c.r, c.g, c.b], i * 3);
  }
  geo.setAttribute("color", new THREE.BufferAttribute(col, 3));
  geo.computeVertexNormals();
  world.add(new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 1 })));
})();

const glacier = new THREE.Mesh(new THREE.BoxGeometry(24, 3, 14),
  new THREE.MeshStandardMaterial({ color: 0xdff1f7, roughness: 0.3 }));
glacier.position.set(cx(-46), height(cx(-46), -46) + 1, -46);
glacier.rotation.x = -0.15;
world.add(glacier);

const waterMat = new THREE.MeshStandardMaterial({ color: 0x2a8fb0, roughness: 0.15, metalness: 0.1,
  transparent: true, opacity: 0.88 });
const water = new THREE.Mesh(new THREE.CircleGeometry(7.5, 48), waterMat);
water.rotation.x = -Math.PI / 2;
water.scale.set(1, 0.9, 1);                      // circle's y-scale becomes z after rotation
world.add(water);

const damMat = new THREE.MeshStandardMaterial({ color: 0x6f675c, roughness: 1, flatShading: true });
const dam = new THREE.Mesh(new THREE.IcosahedronGeometry(1, 1), damMat);
const DAM_Y = H0 - 1.5;
dam.scale.set(10, 4, 3);
dam.position.set(cx(DAM_Z), DAM_Y, DAM_Z);
world.add(dam);

// Villages (names are replaced with the selected lake's real downstream villages)
const VILLAGE_Z = [-12, 8, 30];
const houses = [];       // {mesh, village, hits}
const villages = VILLAGE_Z.map((z, i) => ({ z, name: `Village ${i + 1}`, hit: false, group: null, label: null }));

function makeLabel(text) {
  const cv = document.createElement("canvas");
  cv.width = 256; cv.height = 64;
  const g = cv.getContext("2d");
  g.fillStyle = "rgba(248,251,252,.9)"; g.fillRect(0, 0, 256, 64);
  g.fillStyle = "#12262e"; g.font = "600 28px Segoe UI, sans-serif"; g.textAlign = "center";
  g.fillText(text, 128, 42);
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(cv) }));
  s.scale.set(10, 2.5, 1);
  return s;
}

function buildVillages() {
  villages.forEach((v) => {
    if (v.group) world.remove(v.group);
    v.group = new THREE.Group();
    [-3.2, 0.4, 3.4].forEach((off, k) => {
      const x = cx(v.z) + off, z = v.z + (k - 1) * 1.6;
      const body = new THREE.Mesh(new THREE.BoxGeometry(1.8, 1.2, 1.8),
        new THREE.MeshStandardMaterial({ color: 0xe9e2d0 }));
      const roof = new THREE.Mesh(new THREE.ConeGeometry(1.5, 0.9, 4),
        new THREE.MeshStandardMaterial({ color: 0x8b4b3a }));
      roof.position.y = 1.05; roof.rotation.y = Math.PI / 4;
      const house = new THREE.Group();
      house.add(body, roof);
      house.position.set(x, height(x, z) + 0.6, z);
      house.userData.village = v;
      body.userData.village = v;
      v.group.add(house);
      houses.push({ body, roof, x, z, village: v, hits: 0 });
    });
    v.label = makeLabel(v.name);
    v.label.position.set(cx(v.z), height(cx(v.z), v.z) + 5, v.z);
    v.group.add(v.label);
    world.add(v.group);
  });
}
function rebuildVillages() { houses.length = 0; buildVillages(); renderVillageList(); }
buildVillages();

// ---------- 3. State and data ----------
// target = what the data says; cur = what is drawn (smoothed). level/tilt/vib come from sensors.
const target = { level: 0, tilt: 0.05, vib: 0.1, score: 0, riskLevel: "Low", lead: null, anomaly: false };
const cur = { level: 0, tilt: 0.05, vib: 0.1, score: 0 };
const flood = { active: false, t: 0, collapsed: false, collapseT: 0, burstSeen: false };
const ramp = { active: false, t: 0 };
let mode = "local", lakes = [], follow = false, ws = null;

const $ = (id) => document.getElementById(id);
function levelFor(score) { return score >= 80 ? "Critical" : score >= 60 ? "Warning" : score >= 35 ? "Watch" : "Low"; }

function setMode(m, text) { mode = m; $("mode").innerHTML = `<small>${text}</small>`; }

function applyLive(d) {
  target.level = d.reading.water_level_m;
  target.tilt = d.reading.dam_tilt_deg;
  target.vib = d.reading.vibration_mms;
  target.score = d.risk.score; target.riskLevel = d.risk.level;
  target.lead = d.risk.lead_time_hours; target.anomaly = d.risk.anomaly;
  if (d.reading.burst && !flood.burstSeen) startFlood();
  if (!d.reading.burst && flood.burstSeen) resetScene();    // backend restarted the lake
}

function stepRamp(dt) {                                        // standalone demo, same shape as simulator.py
  if (!ramp.active) return;
  ramp.t += dt;
  const p = Math.min(ramp.t / RAMP_SECONDS, 1);
  target.level = 1.8 * p * p; target.tilt = 0.05 + 0.5 * p * p; target.vib = 0.1 + 2.5 * p * p;
  target.score = 12 + 88 * Math.pow(p, 1.5);
  target.riskLevel = levelFor(target.score);
  target.lead = target.score >= 60 ? Math.round(12 * (1 - p) * 10) / 10 : null;
  if (p >= 1 && !flood.active) startFlood();
}

function triggerOutburst() {
  if (flood.active) return;
  if (mode === "live") fetch(`/simulate/${$("lake").value}/outburst`, { method: "POST" }).catch(() => {});
  else { ramp.active = true; ramp.t = 0; }
}

function resetScene() {
  ramp.active = false; ramp.t = 0;
  flood.active = false; flood.collapsed = false; flood.collapseT = 0; flood.burstSeen = false; flood.t = 0;
  Object.assign(target, { level: 0, tilt: 0.05, vib: 0.1, score: 0, riskLevel: "Low", lead: null });
  particles.forEach((p) => (p.on = false));
  villages.forEach((v) => (v.hit = false));
  houses.forEach((h) => { h.hits = 0; h.body.material.color.setHex(0xe9e2d0); });
  dam.scale.set(10, 4, 3); dam.position.y = DAM_Y;
  renderVillageList();
}

// ---------- 4. Flood physics (particles following the valley, slope-driven speed) ----------
const N = 1800;
const particles = Array.from({ length: N }, () => ({ on: false, z: 0, off: 0, v: 0 }));
const pArr = new Float32Array(N * 3);
const pGeo = new THREE.BufferGeometry();
pGeo.setAttribute("position", new THREE.BufferAttribute(pArr, 3));
const pPoints = new THREE.Points(pGeo, new THREE.PointsMaterial({ color: 0x3aa7c9, size: 1.0,
  transparent: true, opacity: 0.85, depthWrite: false }));
pPoints.frustumCulled = false;
world.add(pPoints);
let speedMul = 1;

function startFlood() {
  flood.active = true; flood.burstSeen = true; flood.collapsed = true; flood.t = 0;
  target.level = -1.4; target.score = 100; target.riskLevel = "Critical"; target.lead = 0;
  renderVillageList();
}

function emit(count) {
  for (const p of particles) {
    if (count <= 0) break;
    if (p.on) continue;
    p.on = true; p.z = DAM_Z + Math.random() * 2; p.off = (Math.random() - 0.5) * 6;
    p.v = 11 + Math.random() * 5; count--;
  }
}

function updateFlood(dt) {
  if (flood.active) {
    flood.t += dt;
    if (flood.t < 7) emit(Math.floor(260 * dt));
  }
  let front = DAM_Z;
  for (let i = 0; i < N; i++) {
    const p = particles[i];
    if (!p.on) { pArr[i * 3 + 1] = -100; continue; }
    p.z += p.v * speedMul * dt;
    if (p.z > 50) { p.on = false; continue; }
    const x = cx(p.z) + p.off;
    pArr[i * 3] = x; pArr[i * 3 + 1] = height(x, p.z) + 0.5; pArr[i * 3 + 2] = p.z;
    front = Math.max(front, p.z);
  }
  pGeo.attributes.position.needsUpdate = true;
  // house impact: a house is "hit" once enough flood particles are within 2.2 units
  houses.forEach((h) => {
    if (h.village.hit && h.hits >= 3) return;
    for (const p of particles) {
      if (!p.on) continue;
      const dx = cx(p.z) + p.off - h.x, dz = p.z - h.z;
      if (dx * dx + dz * dz < 4.84 && ++h.hits >= 3) break;
    }
    if (h.hits >= 3 && !h.village.hit) {
      h.village.hit = true; renderVillageList();
    }
    if (h.hits >= 3) h.body.material.color.setHex(0xb3261e);
  });
  return front;
}

// ---------- 5. UI and input ----------
function eta(v) { return Math.round(((v.z - DAM_Z) * KM_PER_UNIT) / (FRONT_KMH * speedMul) * 60); }
function renderVillageList() {
  $("vlist").innerHTML = villages.map((v) =>
    `<li><span>${v.name}</span><span class="${v.hit ? "hit" : ""}">${v.hit ? "Flooded" : "arrival ~" + eta(v) + " min"}</span></li>`).join("");
}

function setHud() {
  $("score").textContent = Math.round(cur.score);
  const lv = $("level");
  lv.textContent = target.riskLevel;
  lv.style.background = "#" + COLORS[target.riskLevel].toString(16).padStart(6, "0");
  $("lead").textContent = flood.active ? "Outburst in progress"
    : target.lead != null ? `Estimated lead time: ~${target.lead} h`
    : target.anomaly ? "Sensor anomaly detected" : "No precursors detected";
}

const views = {
  1: () => { follow = false; camera.position.set(cx(LAKE_Z) + 24, 40, -62); controls.target.set(cx(LAKE_Z), H0, -34); },
  2: () => { follow = false; camera.position.set(62, 58, 72); controls.target.set(0, 10, 0); },
  3: () => { follow = true; },
};
function setView(k) { views[k](); controls.update(); }

function populateLakes(meta) {
  lakes = meta;
  $("lake").innerHTML = meta.map((l) => `<option value="${l.id}">${l.name}</option>`).join("");
  useLakeVillages();
}
function useLakeVillages() {
  const l = lakes.find((x) => x.id === $("lake").value);
  if (l) l.villages.slice(0, 3).forEach((v, i) => (villages[i].name = v.name));
  resetScene();
  rebuildVillages();
}

function connectWS() {
  ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws.onopen = () => setMode("live", "Live data from GLOF-Watch backend");
  ws.onclose = () => { setMode("local", "Backend not connected: standalone demo"); setTimeout(init, 4000); };
  ws.onmessage = (e) => {
    const d = JSON.parse(e.data).lakes[$("lake").value];
    if (d && mode === "live") applyLive(d);
  };
}

async function init() {
  try {
    const r = await fetch("/lakes");
    if (!r.ok) throw new Error("no backend");
    if (!lakes.length) populateLakes(await r.json());
    connectWS();
  } catch (_) {
    setMode("local", "Backend not connected: standalone demo");
    if (!lakes.length) { $("lake").innerHTML = "<option>Demo lake</option>"; }
  }
}

// raycast click on a house
const ray = new THREE.Raycaster(), mouse = new THREE.Vector2();
let downAt = null;
canvas.addEventListener("pointerdown", (e) => (downAt = [e.clientX, e.clientY]));
canvas.addEventListener("pointerup", (e) => {
  if (!downAt || Math.hypot(e.clientX - downAt[0], e.clientY - downAt[1]) > 5) return;
  mouse.set((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1);
  ray.setFromCamera(mouse, camera);
  const hit = ray.intersectObjects(houses.map((h) => h.body))[0];
  if (hit) {
    const v = hit.object.userData.village;
    alert(`${v.name}: ${v.hit ? "flooded" : "estimated flood arrival ~" + eta(v) + " min after outburst"}`);
  }
});
$("trigger").onclick = triggerOutburst;
$("reset").onclick = () => { resetScene(); };
$("lake").onchange = useLakeVillages;
$("speed").oninput = (e) => { speedMul = +e.target.value; $("speedv").textContent = speedMul.toFixed(1) + "×"; renderVillageList(); };
addEventListener("keydown", (e) => {
  if (e.target.tagName === "SELECT" || e.target.tagName === "INPUT") return;
  if (e.code === "Space") { e.preventDefault(); triggerOutburst(); }
  else if (e.key === "r" || e.key === "R") resetScene();
  else if (views[e.key]) setView(e.key);
});
function resize() {
  renderer.setSize(innerWidth, innerHeight, false);
  camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
}
addEventListener("resize", resize);

// ---------- 6. Game loop ----------
const clock = new THREE.Clock();
const tmpColor = new THREE.Color();
function frame() {
  requestAnimationFrame(frame);
  const dt = Math.min(clock.getDelta(), 0.05);
  if (mode === "local") stepRamp(dt);

  const k = flood.active ? 0.03 : 0.1;                       // water drains slowly, rises responsively
  cur.level += (target.level - cur.level) * k;
  cur.tilt += (target.tilt - cur.tilt) * 0.1;
  cur.vib += (target.vib - cur.vib) * 0.1;
  cur.score += (target.score - cur.score) * 0.1;

  const risk = Math.min(cur.score / 100, 1);
  water.position.set(cx(LAKE_Z), H0 - 0.4 + 0.8 * cur.level, LAKE_Z);
  waterMat.color.setHex(0x2a8fb0).lerp(tmpColor.setHex(COLORS[target.riskLevel]), risk * 0.6);
  scene.background.copy(SKY_CALM).lerp(SKY_ALARM, risk); scene.fog.color.copy(scene.background);
  damMat.emissive.setHex(COLORS[target.riskLevel]); damMat.emissiveIntensity = risk * 0.5;
  dam.rotation.z = THREE.MathUtils.degToRad((cur.tilt - 0.05) * 20);   // exaggerated x20 to be visible

  if (flood.collapsed) {
    flood.collapseT = Math.min(flood.collapseT + dt / 1.5, 1);
    dam.scale.y = 4 * (1 - 0.9 * flood.collapseT);
    dam.position.y = DAM_Y - 1.8 * flood.collapseT;
  }
  const shake = cur.vib > 0.35 ? 0.03 * cur.vib : 0;
  world.position.set((Math.random() - 0.5) * shake, (Math.random() - 0.5) * shake, 0);

  const front = updateFlood(dt);
  if (follow) {
    const fx = cx(front), fy = height(fx, front);
    camera.position.lerp(new THREE.Vector3(fx + 18, fy + 14, front - 24), 0.05);
    controls.target.lerp(new THREE.Vector3(fx, fy, front), 0.1);
  }
  controls.update();
  setHud();
  renderer.render(scene, camera);
}

resize(); setView(1); renderVillageList(); init(); frame();
})();
