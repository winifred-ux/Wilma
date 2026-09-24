/* Wilma 3D hero: SMS tiles travel through two model rings and come out
   with a verdict. Real WebGL, lit and shadowed, rendered at screen resolution. */
(function () {
  "use strict";
  var host = document.getElementById("scene3d");
  if (!host || !window.THREE) return;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var T = window.THREE;
  var root = document.documentElement;
  var DARK = root.dataset.concept === "black" || root.getAttribute("data-theme") === "dark" ||
    (!root.getAttribute("data-theme") && window.matchMedia("(prefers-color-scheme: dark)").matches);

  // ---- renderer ----
  var canvas = document.createElement("canvas");
  canvas.setAttribute("aria-hidden", "true");
  host.insertBefore(canvas, host.firstChild);
  var renderer;
  try {
    renderer = new T.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
  } catch (e) { host.classList.add("no-webgl"); return; }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputEncoding = T.sRGBEncoding;
  renderer.toneMapping = T.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.95;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = T.PCFSoftShadowMap;

  var scene = new T.Scene();
  var camera = new T.PerspectiveCamera(32, 2, 0.1, 100);
  var CAM = new T.Vector3(0, 3.4, 15.5);
  camera.position.copy(CAM);
  camera.lookAt(0, 0.2, 0);

  // ---- lights ----
  scene.add(DARK ? new T.HemisphereLight(0x8fa8ff, 0x050505, 0.35) : new T.HemisphereLight(0xffffff, 0xe8edf5, 0.7));
  var key = new T.DirectionalLight(0xffffff, DARK ? 0.55 : 1.25);
  key.position.set(-2, 12, 6);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  key.shadow.camera.left = -12; key.shadow.camera.right = 12;
  key.shadow.camera.top = 6; key.shadow.camera.bottom = -6;
  key.shadow.radius = 6;
  key.shadow.bias = -0.0005;
  scene.add(key);
  var rim = new T.DirectionalLight(0x9cc3ff, DARK ? 0 : 0.6);
  rim.position.set(6, 3, -6);
  scene.add(rim);

  // ---- floor that only shows shadows ----
  var floor = new T.Mesh(new T.PlaneGeometry(60, 30), DARK
    ? new T.MeshStandardMaterial({ color: 0x000000, roughness: 0.55, metalness: 0.15 })
    : new T.ShadowMaterial({ opacity: 0.07 }));
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -1.55;
  floor.receiveShadow = true;
  scene.add(floor);
  if (DARK) {
    scene.fog = new T.Fog(0x000000, 13, 26);
    var grid = new T.GridHelper(48, 36, 0x1f3560, 0x1f3560);
    grid.position.y = -1.54;
    grid.material.transparent = true; grid.material.opacity = 0.55;
    scene.add(grid);
    // coloured light spilling from each ring onto the floor and the cards
    [[-2.4, 0x3b82f6], [2.4, 0x14b8a6]].forEach(function (d) {
      var pl = new T.PointLight(d[1], 2.2, 7, 2);
      pl.position.set(d[0], 0.4, 0.6);
      scene.add(pl);
    });
  }

  // ---- track line ----


  // ---- helpers ----
  function roundedRect(w, h, r) {
    var s = new T.Shape(), x = -w / 2, y = -h / 2;
    s.moveTo(x + r, y);
    s.lineTo(x + w - r, y); s.quadraticCurveTo(x + w, y, x + w, y + r);
    s.lineTo(x + w, y + h - r); s.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    s.lineTo(x + r, y + h); s.quadraticCurveTo(x, y + h, x, y + h - r);
    s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y);
    return s;
  }
  function roundRectPath(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
  }
  var FONT = '"Inter", -apple-system, "Segoe UI", Roboto, sans-serif';
  var maxAniso = renderer.capabilities.getMaxAnisotropy();

  function wrapLines(ctx, text, maxW) {
    var words = text.split(" "), lines = [], line = "";
    words.forEach(function (w) {
      var t = line ? line + " " + w : w;
      if (ctx.measureText(t).width > maxW && line) { lines.push(line); line = w; } else line = t;
    });
    if (line) lines.push(line);
    return lines;
  }

  // SMS face texture
  function smsTexture(from, text, w, h) {
    var S = 512, c = document.createElement("canvas");
    c.width = Math.round(S * w); c.height = Math.round(S * h);
    var g = c.getContext("2d");
    g.fillStyle = DARK ? "#0c0e13" : "#ffffff"; g.fillRect(0, 0, c.width, c.height);
    var pad = 70;
    g.fillStyle = DARK ? "#2563eb" : "#0a0a09"; g.beginPath(); g.arc(pad + 38, pad + 38, 38, 0, Math.PI * 2); g.fill();
    g.fillStyle = "#fff"; g.font = "700 40px " + FONT; g.textAlign = "center"; g.textBaseline = "middle";
    g.fillText(from.charAt(0), pad + 38, pad + 40);
    g.textAlign = "left"; g.textBaseline = "alphabetic";
    g.fillStyle = DARK ? "#ffffff" : "#0a0a09"; g.font = "700 50px " + FONT; g.fillText(from, pad + 100, pad + 30);
    g.fillStyle = DARK ? "#8b93a7" : "#85857f"; g.font = "500 36px " + FONT; g.fillText("SMS · now", pad + 100, pad + 76);
    g.fillStyle = DARK ? "#e8ecf4" : "#1f1f1d"; g.font = "560 62px " + FONT;
    wrapLines(g, text, c.width - pad * 2).slice(0, 4).forEach(function (l, i) { g.fillText(l, pad, pad + 200 + i * 80); });
    var tex = new T.CanvasTexture(c);
    tex.encoding = T.sRGBEncoding; tex.anisotropy = maxAniso;
    tex.repeat.set(1 / w, 1 / h); tex.offset.set(0.5, 0.5);
    return tex;
  }

  // label texture for floating tags
  function tagTexture(text, fg, bg) {
    var c = document.createElement("canvas"); c.width = 1024; c.height = 256;
    var g = c.getContext("2d");
    var size = 120;
    g.font = "700 " + size + "px " + FONT;
    while (g.measureText(text).width > 880 && size > 40) { size -= 4; g.font = "700 " + size + "px " + FONT; }
    g.fillStyle = bg; roundRectPath(g, 8, 8, 1008, 240, 72); g.fill();
    g.fillStyle = fg; g.textAlign = "center"; g.textBaseline = "middle";
    g.fillText(text, 512, 134);
    var tex = new T.CanvasTexture(c); tex.encoding = T.sRGBEncoding; tex.anisotropy = maxAniso;
    return tex;
  }
  function tagMesh(text, fg, bg, width) {
    var m = new T.Mesh(new T.PlaneGeometry(width, width * 256 / 1024),
      new T.MeshBasicMaterial({ map: tagTexture(text, fg, bg), transparent: true, depthWrite: false, toneMapped: false }));
    return m;
  }

  // ---- the two model rings ----
  var RING_X = [-2.4, 2.4];
  var ringInfo = [
    { color: 0x1e3fae, glow: 0x3b82f6, label: "v1 · long form" },
    { color: 0x0b6b63, glow: 0x14b8a6, label: "v2 · short SMS" }
  ];
  var rings = ringInfo.map(function (info, i) {
    var group = new T.Group();
    var mat = new T.MeshPhysicalMaterial({
      color: info.color, metalness: 0.0, roughness: 0.28, clearcoat: 0.8, clearcoatRoughness: 0.12,
      emissive: info.glow, emissiveIntensity: 0.05
    });
    var torus = new T.Mesh(new T.TorusGeometry(1.75, 0.16, 48, 160), mat);
    torus.rotation.y = Math.PI / 2;
    torus.castShadow = true;
    group.add(torus);
    var inner = new T.Mesh(new T.TorusGeometry(1.45, 0.035, 16, 160),
      new T.MeshStandardMaterial({ color: 0xffffff, emissive: info.glow, emissiveIntensity: 0.4, roughness: 0.4 }));
    inner.rotation.y = Math.PI / 2;
    group.add(inner);
    var stand = new T.Mesh(new T.CylinderGeometry(0.09, 0.09, 1.0, 24), new T.MeshStandardMaterial({ color: 0xcbd5e1, metalness: 0.6, roughness: 0.3 }));
    stand.position.y = -2.1; stand.castShadow = true;
    group.add(stand);
    var label = tagMesh(info.label, "#ffffff", i === 0 ? "#2563eb" : "#0d9488", 2.6);
    label.position.set(0, 2.45, 0);
    group.add(label);
    group.position.x = RING_X[i];
    group.position.y = 0.35;
    scene.add(group);
    return { group: group, torus: torus, inner: inner, mat: mat, flash: 0 };
  });

  // ---- messages ----
  var VERDICT = DARK ? {
    block: { fg: "#ffffff", bg: "#dc2626", side: 0xef4444 },
    review: { fg: "#1a1203", bg: "#fbbf24", side: 0xf59e0b },
    pass: { fg: "#04150a", bg: "#4ade80", side: 0x22c55e }
  } : {
    block: { fg: "#b91c1c", bg: "#fee2e2", side: 0xef4444 },
    review: { fg: "#92400e", bg: "#fef3c7", side: 0xf59e0b },
    pass: { fg: "#166534", bg: "#dcfce7", side: 0x22c55e }
  };
  var MESSAGES = [
    { from: "NIMC-UPDATE", text: "NIN update required. Update in 24hrs or your SIM will be blocked.", v: "review", flags: [false, true] },
    { from: "GTBank", text: "Debit alert: NGN5,000.00 at SHOPRITE LEKKI.", v: "pass", flags: [false, false] },
    { from: "PROMO-NG", text: "You have won N2,000,000! Send your account details to claim.", v: "block", flags: [true, true] },
    { from: "Your bank", text: "Your OTP is 483920. Do not share it with anyone.", v: "pass", flags: [false, false] },
    { from: "QuickLoan", text: "Loan approved! Send your BVN and card details.", v: "block", flags: [true, true] }
  ];
  var TW = 2.5, TH = 1.5;
  var tileGeo = new T.ExtrudeGeometry(roundedRect(TW, TH, 0.22), { depth: 0.14, bevelEnabled: true, bevelThickness: 0.05, bevelSize: 0.05, bevelSegments: 6, curveSegments: 16 });
  tileGeo.translate(0, 0, -0.07);

  var tiles = [];
  var START = -10.5, END = 10.5, SPAN = END - START, SPEED = 1.35;
  function makeTile(msg, idx) {
    var face = new T.MeshBasicMaterial({ map: smsTexture(msg.from, msg.text, TW, TH), toneMapped: false });
    var side = new T.MeshPhysicalMaterial({ color: DARK ? 0x1a1e27 : 0xe2e8f0, roughness: 0.25, clearcoat: 1, clearcoatRoughness: 0.1 });
    var mesh = new T.Mesh(tileGeo, [face, side]);
    mesh.castShadow = true;
    var g = new T.Group();
    g.add(mesh);
    var st = VERDICT[msg.v];
    var tag = tagMesh(msg.v, st.fg, st.bg, 1.5);
    tag.position.set(0, TH / 2 + 0.45, 0.1);
    tag.scale.setScalar(0.001);
    g.add(tag);
    scene.add(g);
    // face the camera a little, like a card held in the hand
    mesh.rotation.y = -0.28;
    return { g: g, mesh: mesh, side: side, tag: tag, msg: msg, x: START + idx * (SPAN / MESSAGES.length), seed: Math.random() * 10, passed: [false, false], done: 0 };
  }
  MESSAGES.forEach(function (m, i) { tiles.push(makeTile(m, i)); });

  var white = new T.Color(DARK ? 0x1a1e27 : 0xe2e8f0);
  function resetTile(t) {
    t.x -= SPAN; t.passed = [false, false]; t.done = 0;
    t.side.color.copy(white); t.side.emissive.setHex(0x000000); t.side.emissiveIntensity = 0;
    t.tag.scale.setScalar(0.001);
  }

  // ---- sizing ----
  function resize() {
    var w = host.clientWidth, h = host.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    // pull the camera back on narrow screens so the whole pipeline fits
    var fit = Math.max(1, 1.9 / camera.aspect);
    CAM.set(0, 3.4 * fit, 15.5 * fit);
    camera.updateProjectionMatrix();
  }
  resize();
  window.addEventListener("resize", resize);

  // ---- interaction ----
  var mx = 0, my = 0, sx = 0, sy = 0;
  if (window.matchMedia("(pointer: fine)").matches) {
    window.addEventListener("mousemove", function (e) {
      mx = e.clientX / window.innerWidth - 0.5; my = e.clientY / window.innerHeight - 0.5;
    });
  }
  var visible = true;
  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (en) { visible = en[0].isIntersecting; if (visible) loop(); }, { threshold: 0 }).observe(host);
  }

  // ---- animation ----
  var clock = new T.Clock(), running = false;
  function step(dt, t) {
    tiles.forEach(function (tile) {
      tile.x += SPEED * dt;
      if (tile.x > END) resetTile(tile);
      var x = tile.x;
      tile.g.position.set(x, 0.35 + Math.sin(t * 1.4 + tile.seed) * 0.06, 0);
      tile.mesh.rotation.x = Math.sin(t * 0.9 + tile.seed) * 0.05;
      // passing through a ring
      RING_X.forEach(function (rx, i) {
        if (!tile.passed[i] && x > rx) {
          tile.passed[i] = true;
          rings[i].flash = tile.msg.flags[i] ? 1 : 0.45;
          rings[i].flashColor = tile.msg.flags[i] ? 0xef4444 : ringInfo[i].glow;
        }
      });
      // verdict appears after the second ring
      if (tile.passed[1]) {
        tile.done = Math.min(1, tile.done + dt * 2.2);
        var st = VERDICT[tile.msg.v];
        tile.side.color.copy(white).lerp(new T.Color(st.side), tile.done);
        if (DARK) { tile.side.emissive.setHex(st.side); tile.side.emissiveIntensity = 0.55 * tile.done; }
        var s = tile.done < 1 ? 0.001 + tile.done * 1.08 : 1 + Math.sin(t * 3) * 0.02;
        tile.tag.scale.setScalar(Math.min(s, 1.08));
      }
      // fade at the ends of the track
      var edge = Math.min(1, Math.min(x - START, END - x) / 1.4);
      tile.g.scale.setScalar(0.6 + 0.4 * Math.max(0, edge));
    });
    rings.forEach(function (r, i) {
      r.flash = Math.max(0, r.flash - dt * 1.6);
      var base = DARK ? 0.35 : 0.22, f = r.flash;
      r.mat.emissive.setHex(f > 0.02 && r.flashColor ? r.flashColor : ringInfo[i].glow);
      r.mat.emissiveIntensity = base + f * (DARK ? 0.8 : 1.4);
      r.inner.material.emissiveIntensity = (DARK ? 1.2 : 0.4) + f * 2.2;
      r.torus.rotation.x = Math.sin(t * 0.6 + i) * 0.04;
      r.group.scale.setScalar(1 + f * 0.05);
    });
    // camera: gentle mouse parallax and a slow drift, plus scroll depth
    sx += (mx - sx) * 0.05; sy += (my - sy) * 0.05;
    var rect = host.getBoundingClientRect();
    var sc = Math.max(-1, Math.min(1, (rect.top + rect.height / 2 - window.innerHeight / 2) / window.innerHeight));
    camera.position.set(CAM.x + sx * 3.2 + Math.sin(t * 0.15) * 0.4, CAM.y - sy * 1.6 + sc * 1.8, CAM.z - sc * 1.2);
    camera.lookAt(0, 0.2, 0);
  }
  function loop() {
    if (running) return;
    running = true;
    clock.getDelta();
    (function frame() {
      if (!visible) { running = false; return; }
      var dt = Math.min(clock.getDelta(), 0.05), t = clock.elapsedTime;
      step(dt, t);
      renderer.render(scene, camera);
      requestAnimationFrame(frame);
    })();
  }

  function start() {
    // redraw text once the page font has loaded so the tiles use Inter
    tiles.forEach(function (tile) {
      tile.mesh.material[0].map = smsTexture(tile.msg.from, tile.msg.text, TW, TH);
      tile.mesh.material[0].needsUpdate = true;
    });
    if (reduce) {
      // one still frame with every tile already judged
      tiles.forEach(function (tile, i) { tile.x = -7 + i * 3.5; tile.passed = [tile.x > RING_X[0], tile.x > RING_X[1]]; });
      step(1, 0); step(1, 0);
      renderer.render(scene, camera);
    } else loop();
    host.classList.add("ready");
  }
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(start); else start();
})();
