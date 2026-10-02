/* Wilma homepage: live chat, 3D face, parallax and reveals. */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // ---------- signed in? swap the nav buttons ----------
  try {
    for (var i = 0; i < localStorage.length; i++) {
      var k = localStorage.key(i);
      if (/^sb-.*-auth-token$/.test(k) && localStorage.getItem(k)) {
        var si = document.querySelector("#nav-cta .signin"); if (si) si.remove();
        var ky = document.querySelector("#nav-cta .key"); if (ky) { ky.href = "/dashboard.html"; ky.textContent = "Dashboard"; }
        break;
      }
    }
  } catch (e) {}

  // ---------- Pidgin: coming soon ----------
  var pg = $("pidgin-btn");
  if (pg) {
    pg.addEventListener("click", function (e) {
      e.stopPropagation();
      pg.classList.add("show");
      clearTimeout(pg._t); pg._t = setTimeout(function () { pg.classList.remove("show"); }, 2600);
    });
    document.addEventListener("click", function () { pg.classList.remove("show"); });
  }

  // ---------- 3D face (three.js) ----------
  var face = null;
  (function build3d() {
    var host = $("face3d");
    if (!host || !window.THREE) return;
    var T = window.THREE, renderer;
    try {
      renderer = new T.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
    } catch (e) { return; }
    if (!renderer.getContext()) return;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputEncoding = T.sRGBEncoding;
    host.appendChild(renderer.domElement);
    document.documentElement.classList.add("has3d");

    var scene = new T.Scene();
    var camera = new T.PerspectiveCamera(32, 1, 0.1, 100);
    camera.position.set(0, 0, 8.6);

    scene.add(new T.AmbientLight(0xffffff, 0.35));
    var key = new T.DirectionalLight(0xffffff, 0.9); key.position.set(-3, 4, 5); scene.add(key);
    var rimP = new T.PointLight(0x7B61FF, 0.6, 20); rimP.position.set(3, -2, -3); scene.add(rimP);
    var rimL = new T.PointLight(0xD4FF3A, 0.6, 20); rimL.position.set(-4, 2, -2); scene.add(rimL);

    function mat(hex) {
      var c = new T.Color(hex);
      return new T.MeshStandardMaterial({ color: c, emissive: c.clone().multiplyScalar(0.5), roughness: 0.42, metalness: 0.05 });
    }
    var CREAM = 0xF4F1EA, LIME = 0xD4FF3A;
    var head = new T.Group(); scene.add(head);

    var ringGeo = new T.TorusGeometry(1, 0.1, 40, 160);
    var mL = mat(CREAM), mR = mat(LIME);
    var ringL = new T.Mesh(ringGeo, mL); ringL.position.x = -0.55; head.add(ringL);
    var ringR = new T.Mesh(ringGeo, mR); ringR.position.x = 0.55; ringR.position.z = 0.04; head.add(ringR);

    var eyeGeo = new T.SphereGeometry(0.25, 48, 48);
    var eyeL = new T.Mesh(eyeGeo, mat(CREAM)); var eyeR = new T.Mesh(eyeGeo, mat(LIME));
    var eyeBase = [new T.Vector3(-0.42, -0.05, 0.28), new T.Vector3(0.68, -0.05, 0.28)];
    eyeL.position.copy(eyeBase[0]); eyeR.position.copy(eyeBase[1]);
    head.add(eyeL); head.add(eyeR);

    var curve = new T.QuadraticBezierCurve3(new T.Vector3(-0.36, -1.45, 0.1), new T.Vector3(0, -1.78, 0.2), new T.Vector3(0.36, -1.45, 0.1));
    var smile = new T.Mesh(new T.TubeGeometry(curve, 48, 0.085, 20, false), mat(CREAM));
    head.add(smile);
    [0, 1].forEach(function (j) {
      var cap = new T.Mesh(new T.SphereGeometry(0.085, 20, 20), smile.material);
      cap.position.copy(j ? curve.v2 : curve.v0); head.add(cap);
    });
    head.position.y = 0.35;

    function size() {
      var w = host.clientWidth, h = host.clientHeight;
      renderer.setSize(w, h, false);
      camera.aspect = w / h; camera.updateProjectionMatrix();
    }
    size(); window.addEventListener("resize", size);

    var mx = 0, my = 0, sx = 0, sy = 0, t0 = performance.now(), visible = true;
    window.addEventListener("pointermove", function (e) {
      mx = e.clientX / window.innerWidth - 0.5; my = e.clientY / window.innerHeight - 0.5;
    }, { passive: true });
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (en) { visible = en[0].isIntersecting; }).observe(host);
    }

    var mood = { target: null, until: 0 };
    var baseL = new T.Color(CREAM), baseR = new T.Color(LIME), tmp = new T.Color();
    face = {
      react: function (hex) { mood.target = new T.Color(hex); mood.until = performance.now() + 2600; }
    };

    function frame(now) {
      requestAnimationFrame(frame);
      if (!visible) return;
      var t = (now - t0) / 1000;
      sx += (mx - sx) * 0.06; sy += (my - sy) * 0.06;
      head.rotation.y = sx * 0.9 + (reduce ? 0 : Math.sin(t * 0.6) * 0.12);
      head.rotation.x = sy * 0.6 + (reduce ? 0 : Math.sin(t * 0.8) * 0.05);
      head.position.y = 0.35 + (reduce ? 0 : Math.sin(t * 1.1) * 0.08);
      // eyes look toward the pointer
      eyeL.position.set(eyeBase[0].x + sx * 0.32, eyeBase[0].y - sy * 0.28, eyeBase[0].z);
      eyeR.position.set(eyeBase[1].x + sx * 0.32, eyeBase[1].y - sy * 0.28, eyeBase[1].z);
      // blink every ~5s
      var b = (t % 5) / 5, s = b > 0.94 ? Math.max(0.12, Math.abs(b - 0.97) / 0.03) : 1;
      eyeL.scale.y = eyeR.scale.y = reduce ? 1 : s;
      // mood tint after a verdict
      var on = mood.target && now < mood.until;
      tmp.copy(on ? mood.target : baseL); mL.color.lerp(tmp, 0.08); mL.emissive.copy(mL.color).multiplyScalar(0.5);
      tmp.copy(on ? mood.target : baseR); mR.color.lerp(tmp, 0.08); mR.emissive.copy(mR.color).multiplyScalar(0.5);
      renderer.render(scene, camera);
    }
    requestAnimationFrame(frame);
  })();

  // ---------- live chat, wired to /verdict ----------
  var COLORS = { block: "#FF5B2E", review: "#FFC53D", pass: "#D4FF3A" };
  var LINES = {
    block: ["Block it. Both my minds agree.", "Don't pay, don't dial, don't click. Delete it."],
    review: ["Check it first. My two minds disagree.", "Don't act on it until you confirm with your bank on a number you trust."],
    pass: ["You're fine. Neither mind flagged it.", "Still, never share your OTP or PIN with anyone."]
  };
  function avatar(v) {
    var c = COLORS[v] || "#F4F1EA", eyes;
    if (v === "block") eyes = '<path d="M62 98H94M106 98H138" stroke="#07080F" stroke-width="12" stroke-linecap="round"/>';
    else eyes = '<circle cx="84" cy="98" r="11" fill="#07080F"/><circle cx="126" cy="98" r="11" fill="#07080F"/>';
    return '<svg class="av" viewBox="0 0 200 200" fill="none" aria-hidden="true"><circle cx="100" cy="100" r="100" fill="' + c + '"/><circle cx="80" cy="96" r="34" stroke="#07080F" stroke-width="10"/><circle cx="120" cy="96" r="34" stroke="#07080F" stroke-width="10"/>' + eyes + '</svg>';
  }
  var log = $("log"), input = $("msg"), go = $("go"), status = $("status");

  function add(html) {
    var d = document.createElement("div"); d.innerHTML = html;
    var el = d.firstChild; log.appendChild(el);
    while (log.children.length > 6) log.removeChild(log.firstChild);
    log.scrollTop = log.scrollHeight;
    return el;
  }
  function her(v, inner) {
    return add('<div class="her">' + avatar(v) + '<div class="bub">' + inner + '</div></div>');
  }

  function ask(text) {
    text = (text || "").trim();
    if (!text) { input.focus(); return; }
    add('<div class="me">' + esc(text) + '</div>');
    var thinking = her("", '<span class="dots" aria-label="Wilma is thinking"><i></i><i></i><i></i></span>');
    go.disabled = true;
    fetch("/verdict", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: text }) })
      .then(function (r) {
        if (r.status === 429) throw new Error("You're asking fast! Wait a minute and try again.");
        if (r.status === 503) throw new Error("I'm just waking up. Give me about 30 seconds and try again.");
        if (!r.ok) throw new Error("Something went wrong on my side (" + r.status + "). Try again.");
        status.textContent = "● online"; status.classList.remove("waking");
        return r.json();
      })
      .then(function (d) {
        var v = LINES[d.verdict] ? d.verdict : "review";
        var line = LINES[v];
        if (d.agreement === "single_model") line = [v === "pass" ? "Looks fine to my one working mind." : "Check it first. Only one of my minds is awake.", line[1]];
        var minds = (d.models || []).map(function (m, n) {
          var p = Math.round(m.scam_probability * 100);
          var col = m.is_scam ? COLORS.block : COLORS.pass;
          return '<div class="mind"><span>Mind ' + (n + 1) + '</span><span class="bar"><i style="background:' + col + '" data-w="' + p + '"></i></span><span>' + (m.is_scam ? "scam" : "safe") + '</span></div>';
        }).join("");
        thinking.remove();
        var el = her(v, '<b class="v-' + v + '">' + esc(line[0]) + '</b> ' + esc(line[1]) + (minds ? '<div class="minds">' + minds + '</div>' : ''));
        requestAnimationFrame(function () { requestAnimationFrame(function () {
          el.querySelectorAll(".bar i").forEach(function (i) { i.style.width = Math.max(4, i.dataset.w) + "%"; });
        }); });
        if (face) face.react(COLORS[v]);
      })
      .catch(function (e) {
        thinking.remove();
        status.textContent = "● waking up"; status.classList.add("waking");
        her("review", esc(e.message || "I couldn't reach my minds just now. Try again in a moment."));
      })
      .then(function () { go.disabled = false; });
  }

  $("form").addEventListener("submit", function (e) { e.preventDefault(); var t = input.value; input.value = ""; ask(t); });
  document.querySelectorAll(".chip[data-msg]").forEach(function (c) {
    c.addEventListener("click", function () { ask(c.dataset.msg); });
  });
  $("ask-now").addEventListener("click", function () { setTimeout(function () { input.focus({ preventScroll: true }); }, 400); });

  // first message, run for real so the demo is honest
  var started = false;
  function firstRun() {
    if (started) return; started = true;
    ask("CONGRATULATIONS! You have won N500,000. Dial *XXX*0# to claim before 6pm today.");
  }
  if ("IntersectionObserver" in window) {
    var io0 = new IntersectionObserver(function (en) { if (en[0].isIntersecting) { firstRun(); io0.disconnect(); } }, { threshold: 0.3 });
    io0.observe($("ask"));
  } else firstRun();

  // ---------- nav background on scroll + parallax layers ----------
  var nav = $("nav"), layers = [].slice.call(document.querySelectorAll("[data-speed]")), ticking = false;
  function onScroll() {
    ticking = false;
    var y = window.scrollY;
    nav.classList.toggle("scrolled", y > 10);
    if (reduce) return;
    var vh = window.innerHeight;
    layers.forEach(function (el) {
      var r = el.getBoundingClientRect();
      if (r.bottom < -200 || r.top > vh + 200) return;
      var mid = r.top + r.height / 2 - vh / 2 - (parseFloat(el.dataset.ty) || 0);
      var ty = -mid * parseFloat(el.dataset.speed);
      el.dataset.ty = ty;
      el.style.translate = "0 " + ty.toFixed(1) + "px";
    });
  }
  window.addEventListener("scroll", function () { if (!ticking) { ticking = true; requestAnimationFrame(onScroll); } }, { passive: true });
  window.addEventListener("resize", onScroll);
  onScroll();

  // ---------- reveal on scroll ----------
  var targets = document.querySelectorAll(".reveal, #trcard");
  if ("IntersectionObserver" in window && !reduce) {
    var io = new IntersectionObserver(function (en) {
      en.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
    }, { threshold: 0.15, rootMargin: "0px 0px -40px 0px" });
    targets.forEach(function (t, n) { t.style.transitionDelay = (n % 3) * 0.08 + "s"; io.observe(t); });
  } else targets.forEach(function (t) { t.classList.add("in"); });

  // ---------- code tabs ----------
  var tabs = document.querySelectorAll(".code-tabs [data-lang]");
  tabs.forEach(function (t) {
    t.addEventListener("click", function () {
      tabs.forEach(function (x) { x.setAttribute("aria-selected", x === t ? "true" : "false"); });
      ["curl", "py", "js"].forEach(function (l) { $("code-" + l).hidden = l !== t.dataset.lang; });
    });
  });
  $("copy").addEventListener("click", function () {
    var lang = document.querySelector('.code-tabs [aria-selected="true"]').dataset.lang;
    var txt = $("code-" + lang).innerText.split("\n\n# response")[0];
    var btn = this;
    if (navigator.clipboard) navigator.clipboard.writeText(txt).then(function () {
      btn.textContent = "Copied"; setTimeout(function () { btn.textContent = "Copy"; }, 1600);
    });
  });
})();
