/* Wilma chat box.
   1. A floating Wilma button on every page that opens a chat panel.
   2. The panel has two tabs: "Check a message" (asks the real Wilma at /verdict)
      and "Talk to the team" (sends a question to Winifred through /contact).
   3. The same checker powers the full chat page at /chat.html. */
(function () {
  "use strict";

  var COLORS = { block: "#FF5B2E", review: "#FFC53D", pass: "#D4FF3A" };
  var LINES = {
    block: ["Block it. Both my minds agree.", "Don't pay, don't dial, don't click. Delete it."],
    review: ["Check it first. My two minds disagree.", "Don't act on it until you confirm with your bank on a number you trust."],
    pass: ["You're fine. Neither mind flagged it.", "Still, never share your OTP or PIN with anyone."]
  };
  var EXAMPLES = [
    ["N15k screening fee", "Congratulations! You have been shortlisted for a remote role, N450k monthly. Pay N15,000 screening fee today to confirm your slot."],
    ["BVN update", "Dear customer, your BVN has been flagged and your account will be blocked today. Update your BVN now with this link to avoid restriction."],
    ["NIN or SIM block", "NIN update required. Failure to update within 24hrs will lead to SIM blockage. Click to update."],
    ["Bank debit alert", "Acct: ****1234 Amt: NGN5,000.00 DR Desc: POS purchase Bal: NGN42,310.55"]
  ];

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function avatar(v) {
    var c = COLORS[v] || "#F4F1EA", eyes;
    if (v === "block") eyes = '<path d="M62 98H94M106 98H138" stroke="#07080F" stroke-width="12" stroke-linecap="round"/>';
    else eyes = '<circle cx="84" cy="98" r="11" fill="#07080F"/><circle cx="126" cy="98" r="11" fill="#07080F"/>';
    return '<svg class="ww-av" viewBox="0 0 200 200" fill="none" aria-hidden="true"><circle cx="100" cy="100" r="100" fill="' + c + '"/><circle cx="80" cy="96" r="34" stroke="#07080F" stroke-width="10"/><circle cx="120" cy="96" r="34" stroke="#07080F" stroke-width="10"/>' + eyes + '</svg>';
  }
  var FACE = '<svg viewBox="0 0 200 200" fill="none" aria-hidden="true"><circle cx="78" cy="94" r="40" stroke="#F4F1EA" stroke-width="10"/><circle cx="122" cy="94" r="40" stroke="#D4FF3A" stroke-width="10"/><circle cx="84" cy="96" r="12" fill="#F4F1EA"/><circle cx="128" cy="96" r="12" fill="#D4FF3A"/><path d="M84 150Q100 164 116 150" stroke="#F4F1EA" stroke-width="10" stroke-linecap="round"/></svg>';
  var HEAD_AV = '<svg class="ww-av" viewBox="0 0 200 200" fill="none" aria-hidden="true"><circle cx="100" cy="100" r="100" fill="#161826"/><circle cx="80" cy="96" r="34" stroke="#F4F1EA" stroke-width="10"/><circle cx="120" cy="96" r="34" stroke="#D4FF3A" stroke-width="10"/></svg>';

  function readStore(key) {
    if (!key) return [];
    try { return JSON.parse(sessionStorage.getItem(key) || "[]"); } catch (e) { return []; }
  }
  function writeStore(key, list) {
    if (!key) return;
    try { sessionStorage.setItem(key, JSON.stringify(list.slice(-40))); } catch (e) {}
  }

  // ---------- the checker (used by the panel and by /chat.html) ----------
  function mountChecker(o) {
    var log = o.log, input = o.input, send = o.send, status = o.status;
    var history = readStore(o.persistKey);

    function add(html) {
      var d = document.createElement("div"); d.innerHTML = html;
      var el = d.firstChild; log.appendChild(el);
      log.scrollTop = log.scrollHeight;
      return el;
    }
    function her(v, inner) { return add('<div class="ww-her">' + avatar(v) + '<div class="ww-bub">' + inner + '</div></div>'); }
    function me(text) { return add('<div class="ww-me">' + esc(text) + '</div>'); }

    function verdictHtml(d) {
      var v = LINES[d.verdict] ? d.verdict : "review";
      var line = LINES[v];
      if (d.agreement === "single_model") line = [v === "pass" ? "Looks fine to my one working mind." : "Check it first. Only one of my minds is awake.", line[1]];
      var minds = (d.models || []).map(function (m, n) {
        var p = Math.round(m.scam_probability * 100);
        var col = m.is_scam ? COLORS.block : COLORS.pass;
        return '<div class="ww-mind"><span>Mind ' + (n + 1) + '</span><span class="ww-bar"><i style="background:' + col + '" data-w="' + p + '"></i></span><span>' + (m.is_scam ? "scam" : "safe") + '</span></div>';
      }).join("");
      return { v: v, html: '<b class="v-' + v + '">' + esc(line[0]) + '</b> ' + esc(line[1]) + (minds ? '<div class="ww-minds">' + minds + '</div>' : '') };
    }
    function grow(el) {
      requestAnimationFrame(function () { requestAnimationFrame(function () {
        el.querySelectorAll(".ww-bar i").forEach(function (i) { i.style.width = Math.max(4, i.dataset.w) + "%"; });
      }); });
    }
    function setStatus(ok) {
      if (!status) return;
      status.textContent = ok ? "● online" : "● waking up";
      status.classList.toggle("waking", !ok);
    }

    function welcome() {
      her("", "Hi, I'm Wilma. Paste any SMS that feels off and I'll ask both my minds if it's a scam. Or tap an example below.");
    }

    // restore this tab's earlier chat
    if (history.length) {
      history.forEach(function (h) {
        if (h.me) me(h.me);
        else if (h.res) { var out0 = verdictHtml(h.res); grow(her(out0.v, out0.html)); }
      });
    } else if (o.welcome !== false) welcome();

    function ask(text) {
      text = (text || "").trim();
      if (!text) { input.focus(); return; }
      if (text.length > 2000) text = text.slice(0, 2000);
      me(text); history.push({ me: text }); writeStore(o.persistKey, history);
      var thinking = her("", '<span class="ww-dots" aria-label="Wilma is thinking"><i></i><i></i><i></i></span>');
      send.disabled = true;
      fetch("/verdict", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: text }) })
        .then(function (r) {
          if (r.status === 429) throw new Error("You're asking fast! Wait a minute and try again.");
          if (r.status === 503) throw new Error("I'm just waking up. Give me about 30 seconds and try again.");
          if (!r.ok) throw new Error("Something went wrong on my side (" + r.status + "). Try again.");
          return r.json();
        })
        .then(function (d) {
          setStatus(true);
          thinking.remove();
          var out = verdictHtml(d);
          grow(her(out.v, out.html));
          history.push({ res: { verdict: d.verdict, agreement: d.agreement, models: d.models } });
          writeStore(o.persistKey, history);
          if (o.onVerdict) o.onVerdict(out.v);
        })
        .catch(function (e) {
          thinking.remove();
          setStatus(false);
          her("review", esc(e.message || "I couldn't reach my minds just now. Try again in a moment."));
        })
        .then(function () { send.disabled = false; });
    }

    o.form.addEventListener("submit", function (e) { e.preventDefault(); var t = input.value; input.value = ""; autosize(); ask(t); });
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); o.form.requestSubmit ? o.form.requestSubmit() : o.form.dispatchEvent(new Event("submit")); }
    });
    function autosize() { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 140) + "px"; }
    input.addEventListener("input", autosize);

    if (o.chips) {
      EXAMPLES.forEach(function (ex) {
        var b = document.createElement("button");
        b.type = "button"; b.className = "ww-chip"; b.textContent = ex[0];
        b.addEventListener("click", function () { ask(ex[1]); });
        o.chips.appendChild(b);
      });
    }

    return {
      ask: ask,
      clear: function () { history = []; writeStore(o.persistKey, history); log.innerHTML = ""; welcome(); }
    };
  }

  // ---------- the "Talk to the team" form ----------
  function teamPane() {
    return '' +
      '<div class="ww-team">' +
        '<div class="ww-her">' + HEAD_AV + '<div class="ww-bub">Got a question, want Wilma for your bank, or found something broken? Leave a message and Winifred will reply by email.</div></div>' +
        '<form class="ww-tform" novalidate>' +
          '<div class="ww-row">' +
            '<label>Your name<input name="name" id="ww-name" maxlength="80" autocomplete="name" required></label>' +
            '<label>Email<input name="email" id="ww-email" type="email" maxlength="254" autocomplete="email" required></label>' +
          '</div>' +
          '<label>About<select name="topic" id="ww-topic">' +
            '<option value="general">A general question</option>' +
            '<option value="bank">Wilma for my bank or fintech</option>' +
            '<option value="bug">Something isn\'t working</option>' +
            '<option value="press">Press or partnership</option>' +
          '</select></label>' +
          '<label>Message<textarea name="message" id="ww-message" maxlength="2000" required placeholder="Type your message..."></textarea></label>' +
          '<label class="ww-hp" aria-hidden="true">Website<input name="website" tabindex="-1" autocomplete="off"></label>' +
          '<p class="ww-err" role="alert"></p>' +
          '<button class="ww-send" type="submit">Send to Winifred</button>' +
          '<p class="ww-note">We save what you send here so we can reply. We won\'t share it or add you to a mailing list.</p>' +
        '</form>' +
      '</div>';
  }
  function wireTeam(root) {
    var form = root.querySelector(".ww-tform"), err = root.querySelector(".ww-err"), btn = form.querySelector(".ww-send");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var f = form.elements;
      var data = {
        name: f.namedItem("name").value.trim(), email: f.namedItem("email").value.trim(), topic: f.namedItem("topic").value,
        message: f.namedItem("message").value.trim(), website: f.namedItem("website").value, page: location.pathname
      };
      if (!data.name) { err.textContent = "Please add your name."; f.namedItem("name").focus(); return; }
      if (!/^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/.test(data.email)) { err.textContent = "Please add an email address we can reply to."; f.namedItem("email").focus(); return; }
      if (data.message.length < 2) { err.textContent = "Please type your message."; f.namedItem("message").focus(); return; }
      err.textContent = ""; btn.disabled = true; btn.textContent = "Sending...";
      fetch("/contact", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) })
        .then(function (r) {
          if (r.ok) return r.json();
          return r.json().catch(function () { return {}; }).then(function (j) {
            throw new Error(typeof j.detail === "string" ? j.detail : "Your message couldn't be sent. Please try again later.");
          });
        })
        .then(function () {
          var box = document.createElement("div");
          box.className = "ww-her";
          box.innerHTML = avatar("pass") + '<div class="ww-bub"><b class="v-pass">Sent! Thank you, ' + esc(data.name.split(" ")[0]) + '.</b> Winifred will reply to ' + esc(data.email) + '.</div>';
          form.replaceWith(box);
        })
        .catch(function (e2) {
          err.textContent = e2.message;
          btn.disabled = false; btn.textContent = "Send to Winifred";
        });
    });
  }

  // ---------- floating bubble + panel ----------
  var api = { mountChecker: mountChecker, wireTeam: wireTeam, teamPane: teamPane, avatar: avatar, HEAD_AV: HEAD_AV };
  window.WilmaChat = api;

  function build() {
    if (document.body.hasAttribute("data-no-widget")) return;
    var root = document.createElement("div");
    root.className = "ww";
    root.innerHTML =
      '<button class="ww-launch" type="button" aria-label="Chat with Wilma" aria-expanded="false" aria-controls="ww-panel">' +
        '<span class="ww-hi">Ask Wilma</span><span class="ww-btn">' + FACE + '<span class="ww-dot"></span></span>' +
      '</button>' +
      '<section class="ww-panel" id="ww-panel" role="dialog" aria-label="Chat with Wilma" aria-hidden="true">' +
        '<div class="ww-head">' + HEAD_AV + '<div><div class="ww-name">wilma</div><div class="ww-sub" id="ww-status">● online</div></div>' +
          '<button class="ww-x" type="button" aria-label="Close chat"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>' +
        '<div class="ww-tabs" role="tablist"><button type="button" role="tab" aria-selected="true" data-tab="check">Check a message</button><button type="button" role="tab" aria-selected="false" data-tab="team">Talk to the team</button></div>' +
        '<div class="ww-pane" data-pane="check">' +
          '<div class="ww-log" aria-live="polite"></div>' +
          '<div class="ww-chips"></div>' +
          '<form class="ww-form" autocomplete="off"><label for="ww-msg" class="ww-hp">Message for Wilma</label><textarea id="ww-msg" rows="1" maxlength="2000" placeholder="Paste a message..."></textarea><button class="ww-send" type="submit">Check</button></form>' +
          '<div class="ww-foot"><span>Wilma can be wrong. We never store your message.</span><a href="/chat.html">Full chat ↗</a></div>' +
        '</div>' +
        '<div class="ww-pane" data-pane="team" hidden>' + teamPane() + '</div>' +
      '</section>';
    document.body.appendChild(root);

    var launch = root.querySelector(".ww-launch"), panel = root.querySelector(".ww-panel");
    var checkPane = root.querySelector('[data-pane="check"]');
    var checker = null;

    function setOpen(on, tab) {
      root.classList.toggle("ww-open", on);
      launch.setAttribute("aria-expanded", on ? "true" : "false");
      panel.setAttribute("aria-hidden", on ? "false" : "true");
      if (on) {
        if (!checker) checker = mountChecker({
          log: checkPane.querySelector(".ww-log"), form: checkPane.querySelector(".ww-form"),
          input: checkPane.querySelector("textarea"), send: checkPane.querySelector(".ww-send"),
          chips: checkPane.querySelector(".ww-chips"), status: root.querySelector("#ww-status"), persistKey: "wilma-widget"
        });
        if (tab) selectTab(tab);
        setTimeout(function () {
          var f = root.querySelector('.ww-pane:not([hidden]) textarea, .ww-pane:not([hidden]) input');
          if (f && window.matchMedia("(pointer: fine)").matches) f.focus({ preventScroll: true });
        }, 250);
      } else launch.focus({ preventScroll: true });
    }
    function selectTab(name) {
      root.querySelectorAll(".ww-tabs button").forEach(function (b) { b.setAttribute("aria-selected", b.dataset.tab === name ? "true" : "false"); });
      root.querySelectorAll(".ww-pane").forEach(function (p) { p.hidden = p.dataset.pane !== name; });
    }

    launch.addEventListener("click", function () { setOpen(!root.classList.contains("ww-open")); });
    root.querySelector(".ww-x").addEventListener("click", function () { setOpen(false); });
    root.querySelectorAll(".ww-tabs button").forEach(function (b) { b.addEventListener("click", function () { selectTab(b.dataset.tab); }); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && root.classList.contains("ww-open")) setOpen(false); });
    wireTeam(root.querySelector('[data-pane="team"]'));

    // any link or button with data-open-chat="check|team" opens the panel
    document.addEventListener("click", function (e) {
      var t = e.target.closest && e.target.closest("[data-open-chat]");
      if (t) { e.preventDefault(); setOpen(true, t.getAttribute("data-open-chat") || "check"); }
    });
    api.open = function (tab) { setOpen(true, tab); };

    // on the homepage, keep the bubble out of the way while the big hero chat is on screen
    var hero = document.getElementById("ask");
    if (hero && "IntersectionObserver" in window) {
      new IntersectionObserver(function (en) {
        launch.classList.toggle("hide", en[0].isIntersecting && !root.classList.contains("ww-open"));
      }, { threshold: 0.2 }).observe(hero);
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build);
  else build();
})();
