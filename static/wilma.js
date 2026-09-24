/* Wilma shared script: theme, nav, reveal, Supabase and app shell helpers. */
(function () {
  "use strict";

  // ---- Theme (runs immediately, before paint) ----
  var THEME_KEY = "wilma-theme";
  function storedTheme() {
    try { return localStorage.getItem(THEME_KEY) || "light"; } catch (e) { return "light"; }
  }
  function applyTheme(t) {
    if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t);
    else document.documentElement.removeAttribute("data-theme");
  }
  if (!document.documentElement.dataset.concept) applyTheme(storedTheme());
  document.documentElement.classList.add("js");

  function currentlyDark() {
    var t = document.documentElement.getAttribute("data-theme");
    if (t) return t === "dark";
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  var W = window.Wilma = {};
  W.setTheme = function (t) {
    try { localStorage.setItem(THEME_KEY, t); } catch (e) {}
    applyTheme(t);
  };
  W.storedTheme = storedTheme;

  // ---- Supabase ----
  W.SUPABASE_URL = "https://upapunmvqqwdkqdfckjr.supabase.co";
  W.SUPABASE_KEY = "sb_publishable_sohMwjK8tRBxren6rtbfaQ_1ijB4dcd"; // publishable key, safe in the browser
  var _sb = null;
  W.sb = function () {
    if (!_sb && window.supabase) _sb = window.supabase.createClient(W.SUPABASE_URL, W.SUPABASE_KEY);
    return _sb;
  };

  // ---- Small helpers ----
  W.$ = function (id) { return document.getElementById(id); };
  W.esc = function (s) {
    return String(s == null ? "" : s).replace(/[<>&"']/g, function (c) {
      return { "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };
  W.showMsg = function (el, text, kind) { el.className = "msg show " + (kind || ""); el.textContent = text; };
  W.clearMsg = function (el) { el.className = "msg"; el.textContent = ""; };
  W.humanize = function (err) {
    if (!err) return "Something went wrong. Please try again.";
    var m = (err.message || "").toLowerCase();
    if (m.indexOf("invalid login credentials") > -1) return "Wrong email or password. Try again, or reset your password.";
    if (m.indexOf("email not confirmed") > -1) return "Please confirm your email first. Check your inbox for the link.";
    if (m.indexOf("already registered") > -1) return "An account with this email already exists. Try signing in.";
    if (m.indexOf("password should be at least") > -1) return err.message;
    if (m.indexOf("rate limit") > -1) return "Too many attempts. Wait a minute and try again.";
    if (m.indexOf("invalid") > -1 && m.indexOf("email") > -1) return "That does not look like a valid email address.";
    return err.message || "Something went wrong.";
  };
  W.fmtDate = function (iso, long) {
    if (!iso) return "never";
    return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: long ? "long" : "short", year: "numeric" });
  };
  W.busy = function (btn, on, text) {
    if (on) { btn.dataset.label = btn.textContent; btn.disabled = true; btn.textContent = text || "Working…"; }
    else { btn.disabled = false; btn.textContent = btn.dataset.label || btn.textContent; }
  };

  var EYE = '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/>';
  var EYE_OFF = '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><path d="M1 1l22 22"/>';
  W.eyeToggles = function () {
    document.querySelectorAll(".eye").forEach(function (btn) {
      var input = btn.parentNode.querySelector("input");
      var svg = btn.querySelector("svg");
      btn.addEventListener("click", function () {
        var showing = input.type === "text";
        input.type = showing ? "password" : "text";
        btn.setAttribute("aria-label", showing ? "Show password" : "Hide password");
        svg.innerHTML = showing ? EYE : EYE_OFF;
        input.focus();
      });
    });
  };

  W.strength = function (input, bars, label) {
    input.addEventListener("input", function () {
      var v = input.value, s = 0;
      if (v.length >= 8) s++;
      if (v.length >= 12) s++;
      if (/[A-Z]/.test(v) && /[a-z]/.test(v)) s++;
      if (/\d/.test(v) && /[^A-Za-z0-9]/.test(v)) s++;
      var colours = ["var(--block)", "var(--review)", "var(--accent)", "var(--pass)"];
      var words = ["Too weak", "Okay", "Good", "Strong"];
      bars.querySelectorAll("i").forEach(function (b, i) { b.style.background = v && i < Math.max(s, 1) ? colours[Math.max(s, 1) - 1] : ""; });
      label.textContent = v ? words[Math.max(s, 1) - 1] : "";
    });
  };

  // ---- App shell (dashboard, keys, settings) ----
  var ICONS = {
    home: '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
    key: '<circle cx="7.5" cy="15.5" r="4.5"/><path d="m10.7 12.3 9.3-9.3M17 6l3 3M14.5 8.5l2 2"/>',
    gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    book: '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5z"/><path d="M4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
    out: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
    menu: '<path d="M4 6h16M4 12h16M4 18h16"/>'
  };
  W.icon = function (name) {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (ICONS[name] || "") + "</svg>";
  };
  W.LOGO = '<svg class="brand-mark" viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M5 9l5 15 6-13 6 13 5-15" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  W.shell = async function (page) {
    var side = W.$("side");
    var links = [
      ["dashboard", "/dashboard.html", "home", "Overview"],
      ["keys", "/api-keys.html", "key", "API keys"],
      ["settings", "/settings.html", "gear", "Settings"]
    ];
    side.innerHTML =
      '<a class="brand" href="/">' + W.LOGO + "Wilma</a>" +
      '<nav class="side-nav" aria-label="App">' +
      links.map(function (l) {
        return '<a href="' + l[1] + '"' + (l[0] === page ? ' aria-current="page"' : "") + ">" + W.icon(l[2]) + l[3] + "</a>";
      }).join("") +
      '<div class="side-label">Resources</div>' +
      '<a href="/docs" target="_blank" rel="noopener">' + W.icon("book") + "API reference</a>" +
      '<a href="/">' + W.icon("globe") + "Home page</a>" +
      "</nav>" +
      '<div class="side-foot"><div class="who"><span class="avatar" id="av">·</span><div><div class="nm" id="who-name">&nbsp;</div><div class="em" id="who-email">&nbsp;</div></div></div>' +
      '<div class="side-nav"><button type="button" id="signout">' + W.icon("out") + "Sign out</button></div></div>";

    var top = W.$("app-top");
    if (top) {
      top.innerHTML = '<a class="brand" href="/">' + W.LOGO + 'Wilma</a><button class="icon-btn" id="side-toggle" aria-label="Open menu">' + W.icon("menu") + "</button>";
      W.$("side-toggle").addEventListener("click", function () { side.classList.toggle("open"); });
    }

    var sb = W.sb();
    var res = await sb.auth.getSession();
    if (!res.data.session) { window.location.replace("/signin.html"); return null; }
    var u = res.data.session.user;
    var meta = u.user_metadata || {};
    var name = meta.display_name || u.email.split("@")[0];
    W.$("who-name").textContent = name;
    W.$("who-email").textContent = u.email;
    W.$("av").textContent = name.charAt(0).toUpperCase();
    W.$("signout").addEventListener("click", async function () {
      await sb.auth.signOut();
      window.location.href = "/signin.html";
    });
    return u;
  };

  // ---- DOM ready wiring for marketing pages ----
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-theme-toggle]").forEach(function (b) {
      b.addEventListener("click", function () { W.setTheme(currentlyDark() ? "light" : "dark"); });
    });

    var nav = document.querySelector(".nav");
    if (nav) {
      var onScroll = function () { nav.classList.toggle("scrolled", window.scrollY > 8); };
      onScroll();
      window.addEventListener("scroll", onScroll, { passive: true });
    }
    var menu = W.$("menu-btn");
    if (menu) {
      menu.addEventListener("click", function () {
        var links = document.querySelector(".nav-links");
        var open = links.classList.toggle("open");
        menu.setAttribute("aria-expanded", open ? "true" : "false");
      });
      document.querySelectorAll(".nav-links a").forEach(function (a) {
        a.addEventListener("click", function () { document.querySelector(".nav-links").classList.remove("open"); });
      });
    }

    var items = document.querySelectorAll(".reveal");
    var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce || !("IntersectionObserver" in window)) {
      items.forEach(function (el) { el.classList.add("in"); });
    } else {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); }
        });
      }, { rootMargin: "0px 0px -10% 0px" });
      items.forEach(function (el) { io.observe(el); });
    }


    // ---- Layered motion: parallax, mouse depth, 3D tilt, count up ----
    if (!reduce) {
      var par = Array.prototype.slice.call(document.querySelectorAll("[data-speed]"));
      var tilts = Array.prototype.slice.call(document.querySelectorAll("[data-tilt]"));
      var fades = Array.prototype.slice.call(document.querySelectorAll("[data-fade]"));
      var mx = 0, my = 0, tx = 0, ty = 0, ticking = false;
      var fine = window.matchMedia("(pointer: fine)").matches;
      function frame() {
        ticking = false;
        tx += (mx - tx) * 0.08; ty += (my - ty) * 0.08;
        var sy = window.scrollY, vh = window.innerHeight;
        par.forEach(function (el) {
          var s = parseFloat(el.dataset.speed) || 0, m = parseFloat(el.dataset.mouse || 0), y;
          if (el.dataset.mode === "center") {
            var r = el.parentNode.getBoundingClientRect();
            y = (r.top + r.height / 2 - vh / 2) * -s;
          } else { y = sy * s; }
          var rot = el.dataset.rot ? " rotate(" + (sy * parseFloat(el.dataset.rot)) + "deg)" : "";
          el.style.transform = "translate3d(" + (tx * m) + "px," + (y + ty * m) + "px,0)" + rot;
        });
        fades.forEach(function (el) {
          var f = Math.max(0, 1 - sy / (vh * 0.7));
          el.style.opacity = f.toFixed(3);
        });
        tilts.forEach(function (el) {
          var r = el.getBoundingClientRect();
          var p = Math.min(1, Math.max(0, (vh - r.top) / (vh * 0.75)));
          var e = 1 - Math.pow(1 - p, 3);
          el.style.transform = "perspective(1400px) rotateX(" + ((1 - e) * 18).toFixed(2) + "deg) scale(" + (0.92 + 0.08 * e).toFixed(4) + ") translateY(" + ((1 - e) * 30).toFixed(1) + "px)";
        });
        if (Math.abs(mx - tx) > 0.001 || Math.abs(my - ty) > 0.001) request();
      }
      function request() { if (!ticking) { ticking = true; requestAnimationFrame(frame); } }
      window.addEventListener("scroll", request, { passive: true });
      window.addEventListener("resize", request);
      if (fine) window.addEventListener("mousemove", function (e) {
        mx = e.clientX / window.innerWidth - 0.5; my = e.clientY / window.innerHeight - 0.5; request();
      });
      request();
    }

    var counts = document.querySelectorAll("[data-count]");
    function runCount(el) {
      var end = parseFloat(el.dataset.count), dec = el.dataset.dec ? parseInt(el.dataset.dec, 10) : 0;
      if (reduce) { el.textContent = end.toFixed(dec); return; }
      var t0 = null, dur = 1400;
      function step(t) {
        if (!t0) t0 = t;
        var p = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - p, 4);
        el.textContent = (end * e).toFixed(dec);
        if (p < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    }
    if ("IntersectionObserver" in window) {
      var co = new IntersectionObserver(function (en) {
        en.forEach(function (x) { if (x.isIntersecting) { runCount(x.target); co.unobserve(x.target); } });
      }, { threshold: 0.6 });
      counts.forEach(function (el) { co.observe(el); });
    } else counts.forEach(runCount);


    // hover tilt for cards (desktop only)
    if (!reduce && window.matchMedia("(pointer: fine)").matches) {
      document.querySelectorAll(".tilt-card").forEach(function (card) {
        card.addEventListener("mousemove", function (e) {
          var r = card.getBoundingClientRect();
          var x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5;
          card.style.transform = "perspective(900px) rotateX(" + (-y * 8).toFixed(2) + "deg) rotateY(" + (x * 10).toFixed(2) + "deg) translateY(-4px)";
        });
        card.addEventListener("mouseleave", function () { card.style.transform = ""; });
      });
    }

    W.eyeToggles();
  });
})();
