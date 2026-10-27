/* Embeddable widget. One <script> tag is the whole install:
 *   <script src="https://your-api/widget.js?id=WIDGET_ID"></script>
 * It loads the widget's config, renders a form, and posts submissions back. */
(function () {
  var script = document.currentScript;
  if (!script) return;
  var src = new URL(script.src);
  var widgetId = script.getAttribute("data-widget-id") || src.searchParams.get("id");
  if (!widgetId) { console.error("[widget] missing widget id"); return; }
  var API = src.origin;

  function uuid() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return "k" + Date.now().toString(36) + Math.random().toString(36).slice(2, 12);
  }
  function el(tag, props, text) {
    var node = document.createElement(tag);
    for (var k in (props || {})) node.setAttribute(k, props[k]);
    if (text) node.textContent = text;          // textContent, never innerHTML: config text is untrusted
    return node;
  }

  fetch(API + "/widgets/" + encodeURIComponent(widgetId) + "/config")
    .then(function (r) { if (!r.ok) throw new Error("config request failed: " + r.status); return r.json(); })
    .then(render)
    .catch(function (e) { console.error("[widget]", e); });

  function render(cfg) {
    var idemKey = uuid();                        // one key per rendered form: a retried submit is stored once
    var box = el("div", { style: "font-family:sans-serif;max-width:360px;border:1px solid #ddd;border-radius:8px;padding:16px;margin:16px 0" });
    var form = el("form", { novalidate: "novalidate" });
    var status = el("p", { style: "min-height:1.2em;font-size:14px" });

    box.appendChild(el("h3", { style: "margin:0 0 6px" }, cfg.title));
    if (cfg.description) box.appendChild(el("p", { style: "margin:0 0 12px;color:#555" }, cfg.description));

    var inputs = {};
    cfg.fields.forEach(function (f) {
      var wrap = el("div", { style: "margin-bottom:10px" });
      wrap.appendChild(el("label", { style: "display:block;font-size:13px;margin-bottom:3px" }, f.label + (f.required ? " *" : "")));
      var input = f.type === "textarea" ? el("textarea", { rows: "3" }) : el("input", { type: f.type === "email" ? "email" : "text" });
      input.setAttribute("name", f.name);
      input.setAttribute("maxlength", String(f.max_length));
      input.style.cssText = "width:100%;box-sizing:border-box;padding:6px";
      inputs[f.name] = input;
      wrap.appendChild(input);
      form.appendChild(wrap);
    });

    // Honeypot: invisible to people, tempting to bots. Anything typed in here means "bot".
    var hp = el("input", { type: "text", name: cfg.honeypot_field, tabindex: "-1", autocomplete: "off", "aria-hidden": "true" });
    hp.style.cssText = "position:absolute;left:-9999px;opacity:0;height:0;width:0";
    form.appendChild(hp);

    var button = el("button", { type: "submit" }, cfg.button_text);
    button.style.cssText = "padding:8px 14px;cursor:pointer";
    form.appendChild(button);
    form.appendChild(status);
    box.appendChild(form);

    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var data = {};
      Object.keys(inputs).forEach(function (name) { data[name] = inputs[name].value; });
      button.disabled = true;
      status.textContent = "Sending...";
      fetch(API + "/submissions", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Idempotency-Key": idemKey },
        body: JSON.stringify({ widget_id: cfg.id, data: data, website: hp.value })
      }).then(function (r) {
        if (r.ok) { form.style.display = "none"; box.appendChild(el("p", {}, cfg.success_message)); return; }
        return r.json().catch(function () { return {}; }).then(function (body) {
          var msg = r.status === 429 ? "Too many attempts. Please wait a moment and try again."
                  : (body.fields && body.fields[0]) ? body.fields[0].field + ": " + body.fields[0].message
                  : "Something went wrong. Please try again.";
          status.textContent = msg;
          button.disabled = false;
        });
      }).catch(function () { status.textContent = "Network error. Please try again."; button.disabled = false; });
    });

    if (cfg.type === "cta_popover") {              // a floating button that opens the form
      var launcher = el("button", { type: "button" }, cfg.title);
      launcher.style.cssText = "position:fixed;right:20px;bottom:20px;padding:10px 16px;cursor:pointer;z-index:9999";
      box.style.cssText += ";position:fixed;right:20px;bottom:70px;background:#fff;display:none;z-index:9999";
      launcher.addEventListener("click", function () { box.style.display = box.style.display === "none" ? "block" : "none"; });
      document.body.appendChild(box);
      document.body.appendChild(launcher);
    } else if (script.parentNode) {
      script.parentNode.insertBefore(box, script.nextSibling);
    } else {
      document.body.appendChild(box);
    }
  }
})();
