/* Little Nest Notes: the only script on the site. No dependencies, no cookies.
   1. A small privacy notice (remembered in localStorage) with an analytics opt-out.
   2. Contact form: validation, honeypot and time-to-submit checks, Netlify Forms submit. */
(function () {
  "use strict";

  var CHOICE_KEY = "lnn-privacy-choice"; // "ok" or "no-analytics"

  function store(key, value) {
    try {
      if (value === null) localStorage.removeItem(key);
      else localStorage.setItem(key, value);
    } catch (e) { /* private mode or storage blocked: the notice just shows again */ }
  }
  function read(key) {
    try { return localStorage.getItem(key); } catch (e) { return null; }
  }

  /* ---------- 1. Privacy notice ---------- */
  function privacyHref() {
    var css = document.querySelector('link[rel="stylesheet"][href*="assets/style.css"]');
    return css ? css.getAttribute("href").replace("assets/style.css", "privacy/") : "/privacy/";
  }

  function showNotice() {
    if (document.getElementById("privacy-notice")) return;
    var hasAnalytics = !!document.querySelector("script[data-domain]");
    var box = document.createElement("section");
    box.id = "privacy-notice";
    box.className = "privacy-notice";
    box.setAttribute("role", "region");
    box.setAttribute("aria-label", "Cookies and privacy");
    box.innerHTML =
      '<p><strong>No tracking cookies here.</strong> This site sets no cookies of its own' +
      (hasAnalytics ? " and counts visits with cookieless, anonymous analytics (Plausible)" : "") +
      ". Shops you reach through affiliate links may set their own cookies on their sites. " +
      '<a href="' + privacyHref() + '">Privacy policy</a></p>' +
      '<div class="privacy-actions">' +
      '<button type="button" class="btn" data-choice="ok">OK</button>' +
      (hasAnalytics ? '<button type="button" class="btn btn-ghost" data-choice="no-analytics">Don’t count my visits</button>' : "") +
      "</div>";
    box.addEventListener("click", function (ev) {
      var choice = ev.target && ev.target.getAttribute("data-choice");
      if (!choice) return;
      store(CHOICE_KEY, choice);
      // Plausible's documented opt-out: it skips every visit while this is "true".
      store("plausible_ignore", choice === "no-analytics" ? "true" : null);
      box.remove();
    });
    document.body.appendChild(box);
  }

  /* ---------- 2. Contact form ---------- */
  var MIN_SECONDS = 3; // humans need longer than this to fill the form
  var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

  function setError(field, message) {
    var err = document.getElementById(field.id + "-error");
    field.setAttribute("aria-invalid", message ? "true" : "false");
    if (err) err.textContent = message || "";
  }

  function validate(form) {
    var ok = true;
    var name = form.elements.name, email = form.elements.email, message = form.elements.message;
    var n = name.value.trim(), e = email.value.trim(), m = message.value.trim();
    if (n.length < 2) { setError(name, "Please enter your name (at least 2 characters)."); ok = false; }
    else if (n.length > 80) { setError(name, "Please keep your name under 80 characters."); ok = false; }
    else setError(name, "");
    if (!e) { setError(email, "Please enter your email so I can reply."); ok = false; }
    else if (!EMAIL_RE.test(e) || e.length > 254) { setError(email, "That email address doesn’t look right (example: name@example.com)."); ok = false; }
    else setError(email, "");
    if (m.length < 10) { setError(message, "Please write a message of at least 10 characters."); ok = false; }
    else if (m.length > 3000) { setError(message, "Please keep your message under 3,000 characters."); ok = false; }
    else setError(message, "");
    if (!ok) {
      var first = form.querySelector('[aria-invalid="true"]');
      if (first) first.focus();
    }
    return ok;
  }

  function setupContactForm(form) {
    var started = Date.now();
    var status = form.querySelector(".form-status");
    var button = form.querySelector('button[type="submit"]');
    form.noValidate = true; // JS takes over; without JS the browser's own checks run

    ["name", "email", "message"].forEach(function (key) {
      form.elements[key].addEventListener("blur", function () {
        if (this.getAttribute("aria-invalid") === "true") validate(form);
      });
    });

    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      status.className = "form-status";
      status.textContent = "";
      if (!validate(form)) return;

      // Honeypot: real people never see or fill this field. Pretend it worked.
      if (form.elements["bot-field"] && form.elements["bot-field"].value) {
        form.reset();
        status.className = "form-status is-ok";
        status.textContent = "Thanks, your message was sent.";
        return;
      }
      if ((Date.now() - started) / 1000 < MIN_SECONDS) {
        status.className = "form-status is-error";
        status.textContent = "That was very fast. Please check your message, then press Send again.";
        started = Date.now() - (MIN_SECONDS - 1) * 1000;
        return;
      }

      button.disabled = true;
      button.textContent = "Sending…";
      var body = new URLSearchParams(new FormData(form)).toString();
      fetch(form.getAttribute("action") || location.pathname, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: body
      }).then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        form.reset();
        status.className = "form-status is-ok";
        status.textContent = "Thanks, your message was sent. I usually reply within a few days.";
      }).catch(function () {
        var mail = form.getAttribute("data-fallback-email");
        status.className = "form-status is-error";
        status.innerHTML = "Sorry, the message could not be sent. Please email me instead" +
          (mail ? ': <a href="mailto:' + mail + '">' + mail + "</a>." : ".");
      }).then(function () {
        button.disabled = false;
        button.textContent = "Send message";
        status.focus();
      });
    });
  }

  function init() {
    if (!read(CHOICE_KEY)) showNotice();
    var reopen = document.querySelectorAll("[data-privacy-choices]");
    for (var i = 0; i < reopen.length; i++) {
      reopen[i].addEventListener("click", function () { store(CHOICE_KEY, null); showNotice(); });
    }
    var form = document.querySelector("form[data-contact]");
    if (form) setupContactForm(form);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
