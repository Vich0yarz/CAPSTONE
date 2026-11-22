(function () {
  var modalEl = document.getElementById("modal-producto");
  if (!modalEl) return;

  var contenido = document.getElementById("modal-contenido");
  var modal = new bootstrap.Modal(modalEl);

  function mostrarError(texto) {
    contenido.innerHTML =
      '<div class="modal-body p-4"><div class="alert alert-danger mb-3"></div>' +
      '<div class="text-end"><button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cerrar</button></div></div>';
    contenido.querySelector(".alert").textContent = texto;
    modal.show();
  }

  // Interpreta la respuesta: devuelve {json} o {html}, o null si ya se manejó el problema
  function leer(respuesta) {
    if (respuesta.redirected) { window.location.reload(); return null; }  // sesión vencida: va al login
    var tipo = respuesta.headers.get("content-type") || "";
    if (tipo.indexOf("application/json") !== -1) {
      return respuesta.json().then(function (d) { return { json: d }; });
    }
    if (respuesta.status === 403) { mostrarError("No tienes permiso para realizar esta acción."); return null; }
    if (!respuesta.ok) { mostrarError("No se pudo completar la acción (código " + respuesta.status + ")."); return null; }
    return respuesta.text().then(function (t) { return { html: t }; });
  }

  function procesar(res) {
    if (!res) return;
    if (res.json) {
      if (res.json.ok) {
        // Recarga la misma página conservando orden y búsqueda, y reabre el producto afectado
        var params = new URLSearchParams(window.location.search);
        if (res.json.ver) { params.set("ver", res.json.ver); } else { params.delete("ver"); }
        var qs = params.toString();
        window.location.href = window.location.pathname + (qs ? "?" + qs : "");
      }
      return;
    }
    contenido.innerHTML = res.html;
    modal.show();
  }

  function cargar(url) {
    fetch(url, { credentials: "same-origin" })
      .then(leer).then(procesar)
      .catch(function () { mostrarError("No se pudo conectar con el servidor."); });
  }

  function enviar(form, boton) {
    if (form.dataset.enviando) return;  // evita el doble envío (doble clic)
    form.dataset.enviando = "1";
    var datos = new FormData(form);
    if (boton && boton.name) datos.append(boton.name, boton.value);
    fetch(form.action, { method: "POST", body: datos, credentials: "same-origin" })
      .then(leer).then(procesar)
      .catch(function () { delete form.dataset.enviando; mostrarError("No se pudo conectar con el servidor."); });
  }

  // Cualquier elemento con data-modal-url abre su contenido en la ventana emergente
  document.addEventListener("click", function (e) {
    var el = e.target.closest("[data-modal-url]");
    if (!el) return;
    e.preventDefault();
    cargar(el.dataset.modalUrl);
  });

  // Teclado: Enter o Espacio sobre una tarjeta
  document.addEventListener("keydown", function (e) {
    if ((e.key === "Enter" || e.key === " ") && e.target.matches(".nv-card-abrir")) {
      e.preventDefault();
      cargar(e.target.dataset.modalUrl);
    }
  });

  // Los formularios de la ventana se envían sin salir de la página
  document.addEventListener("submit", function (e) {
    var form = e.target.closest("form[data-modal-form]");
    if (!form) return;
    e.preventDefault();
    enviar(form, e.submitter);
  });

  // Al cerrar la ventana, se quita ?ver= de la dirección para que F5 no la reabra
  modalEl.addEventListener("hidden.bs.modal", function () {
    contenido.innerHTML = "";
    var params = new URLSearchParams(window.location.search);
    if (params.has("ver")) {
      params.delete("ver");
      var qs = params.toString();
      history.replaceState(null, "", window.location.pathname + (qs ? "?" + qs : ""));
    }
  });

  // Si la dirección trae ?ver=ID (tras guardar algo), reabre ese producto
  var ver = new URLSearchParams(window.location.search).get("ver");
  if (ver && /^\d+$/.test(ver)) {
    cargar(modalEl.dataset.urlDetalle.replace("/0/", "/" + ver + "/"));
  }
})();