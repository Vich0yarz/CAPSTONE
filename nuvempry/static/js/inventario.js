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

  function leer(respuesta) {
    if (respuesta.redirected) { window.location.reload(); return null; }
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
    if (form.dataset.enviando) return;
    form.dataset.enviando = "1";
    var datos = new FormData(form);
    if (boton && boton.name) datos.append(boton.name, boton.value);
    fetch(form.action, { method: "POST", body: datos, credentials: "same-origin" })
      .then(leer).then(procesar)
      .catch(function () { delete form.dataset.enviando; mostrarError("No se pudo conectar con el servidor."); });
  }

  document.addEventListener("submit", function (e) {
    var form = e.target.closest("form[data-modal-form]");
    if (!form) return;
    e.preventDefault();
    enviar(form, e.submitter);
  });

  modalEl.addEventListener("hidden.bs.modal", function () {
    contenido.innerHTML = "";
    var params = new URLSearchParams(window.location.search);
    if (params.has("ver")) {
      params.delete("ver");
      var qs = params.toString();
      history.replaceState(null, "", window.location.pathname + (qs ? "?" + qs : ""));
    }
  });

  var ver = new URLSearchParams(window.location.search).get("ver");
  if (ver && /^\d+$/.test(ver)) {
    cargar(modalEl.dataset.urlDetalle.replace("/0/", "/" + ver + "/"));
  }

  // ---- Ajuste rápido de stock en tarjetas (productos y subproductos) ----
  var holdTimer = null;
  var holdInterval = null;
  var holdResetTimer = null;
  var holdActivo = false;
  var STOCK_MAX = 9999;

  function obtenerCsrf() {
    var input = document.querySelector("[name=csrfmiddlewaretoken]");
    if (input) return input.value;
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function formatearUnidades(cantidad, esPadre) {
    if (esPadre && cantidad > STOCK_MAX) {
      return "+" + STOCK_MAX + " Unidades";
    }
    return cantidad + (cantidad === 1 ? " Unidad" : " Unidades");
  }

  function ajustarTamanoTextoStock(contenedor, etiqueta, etiquetaDelta, original, diferencia) {
    var baseUnidades = original >= 1000 ? 1.2 : (Math.abs(diferencia) >= 1000 ? 1.22 : 1.32);
    var baseDelta = 0.9;

    etiqueta.style.setProperty("font-size", baseUnidades + "rem", "important");
    if (etiquetaDelta) {
      etiquetaDelta.style.setProperty("font-size", baseDelta + "rem", "important");
    }

    var cajaTexto = contenedor.querySelector(".nv-stock-texto");
    if (!cajaTexto) return;

    var escala = 1;
    while (cajaTexto.scrollWidth > cajaTexto.clientWidth && escala > 0.55) {
      escala -= 0.05;
      etiqueta.style.setProperty("font-size", (baseUnidades * escala).toFixed(2) + "rem", "important");
      if (etiquetaDelta) {
        etiquetaDelta.style.setProperty("font-size", (baseDelta * escala).toFixed(2) + "rem", "important");
      }
    }
  }

  function actualizarVistaStock(contenedor, nuevoValor) {
    var original = parseInt(contenedor.dataset.stockOriginal, 10);
    var etiqueta = contenedor.querySelector(".nv-unidades");
    var etiquetaDelta = contenedor.querySelector(".nv-delta");
    var btnCheck = contenedor.querySelector(".nv-check");
    var btnBajar = contenedor.querySelector('.nv-stock-btn[data-delta="-1"]');
    var btnSubir = contenedor.querySelector('.nv-stock-btn[data-delta="1"]');
    var btnCancelar = contenedor.querySelector(".nv-cancelar");

    contenedor.dataset.stockActual = nuevoValor;
    etiqueta.textContent = formatearUnidades(original);

    var diferencia = nuevoValor - original;
    var hayCambios = diferencia !== 0;

    btnCheck.disabled = !hayCambios;
    btnCheck.title = hayCambios ? "Confirmar cambio de stock" : "Sin cambios pendientes";

    if (hayCambios) {
      if (btnCancelar) {
        btnCancelar.disabled = false;
        btnCancelar.classList.remove("d-none");
      }

      if (etiquetaDelta) {
        etiquetaDelta.textContent = (diferencia > 0 ? "+ " : "- ") + Math.abs(diferencia);
      }

      ajustarTamanoTextoStock(contenedor, etiqueta, etiquetaDelta, original, diferencia);

      btnCheck.classList.remove("btn-light", "text-secondary", "border");
      btnCheck.classList.add("btn-success", "text-white");
      btnCheck.style.backgroundColor = "#198754";
      btnCheck.style.borderColor = "#198754";
      btnCheck.style.color = "#ffffff";
    } else {
      etiqueta.style.removeProperty("font-size");
      if (btnCancelar) {
        btnCancelar.classList.add("d-none");
      }

      if (etiquetaDelta) {
        etiquetaDelta.textContent = "";
        etiquetaDelta.style.removeProperty("font-size");
      }

      btnCheck.classList.remove("btn-success", "text-white");
      btnCheck.classList.add("btn-light", "text-secondary", "border");
      btnCheck.style.backgroundColor = "";
      btnCheck.style.borderColor = "";
      btnCheck.style.color = "";
    }

    if (btnBajar) {
      var enCero = nuevoValor <= 0;
      if (holdActivo && enCero) {
        btnBajar.classList.add("disabled", "opacity-50");
        btnBajar.dataset.pendienteDeshabilitar = "1";
      } else {
        btnBajar.disabled = enCero;
        btnBajar.classList.remove("disabled", "opacity-50");
        delete btnBajar.dataset.pendienteDeshabilitar;
      }
    }

    if (btnSubir) {
      var enMax = nuevoValor >= STOCK_MAX;
      if (holdActivo && enMax) {
        btnSubir.classList.add("disabled", "opacity-50");
        btnSubir.dataset.pendienteDeshabilitar = "1";
      } else {
        btnSubir.disabled = enMax;
        btnSubir.classList.remove("disabled", "opacity-50");
        delete btnSubir.dataset.pendienteDeshabilitar;
      }
    }
  }

  // ---- Pulsación corta o mantenida acelerada para subir/bajar stock ----
  function aplicarPasoStock(contenedor, delta, paso) {
    var actual = contenedor.dataset.stockActual !== undefined
      ? parseInt(contenedor.dataset.stockActual, 10)
      : parseInt(contenedor.dataset.stockOriginal, 10);

    var siguiente = Math.min(STOCK_MAX, Math.max(0, actual + delta * paso));
    actualizarVistaStock(contenedor, siguiente);
    return siguiente;
  }

  function detenerHoldStock() {
    clearTimeout(holdTimer);
    clearInterval(holdInterval);
    clearTimeout(holdResetTimer);
    holdTimer = null;
    holdInterval = null;

    document.querySelectorAll('.nv-stock-btn[data-pendiente-deshabilitar="1"]').forEach(function (btn) {
      btn.disabled = true;
      btn.classList.remove("disabled", "opacity-50");
      delete btn.dataset.pendienteDeshabilitar;
    });

    holdResetTimer = setTimeout(function () {
      holdActivo = false;
    }, 200);
  }

  document.addEventListener("pointerdown", function (e) {
    if (e.button !== 0 && e.pointerType === "mouse") return;
    var btn = e.target.closest(".nv-stock-btn");
    if (!btn || btn.disabled) return;

    var contenedor = btn.closest(".nv-card-stock");
    if (!contenedor || contenedor.dataset.guardando === "1") return;

    clearTimeout(holdTimer);
    clearInterval(holdInterval);
    clearTimeout(holdResetTimer);
    holdTimer = null;
    holdInterval = null;
    holdActivo = true;

    if (btn.setPointerCapture) {
      try { btn.setPointerCapture(e.pointerId); } catch (err) {}
    }

    var delta = parseInt(btn.dataset.delta, 10);
    var ticks = 0;

    var inicial = aplicarPasoStock(contenedor, delta, 1);
    if ((delta < 0 && inicial === 0) || (delta > 0 && inicial === STOCK_MAX)) {
      return;
    }

    holdTimer = setTimeout(function () {
      holdInterval = setInterval(function () {
        if (btn.disabled) {
          clearInterval(holdInterval);
          holdInterval = null;
          return;
        }
        ticks++;
        var paso = 1;
        if (ticks > 90) paso = 100;
        else if (ticks > 60) paso = 25;
        else if (ticks > 35) paso = 10;
        else if (ticks > 15) paso = 5;

        var nuevo = aplicarPasoStock(contenedor, delta, paso);
        if ((delta < 0 && nuevo === 0) || (delta > 0 && nuevo === STOCK_MAX)) {
          clearInterval(holdInterval);
          holdInterval = null;
        }
      }, 95);
    }, 400);
  });

  document.addEventListener("pointerup", detenerHoldStock);
  document.addEventListener("pointercancel", detenerHoldStock);

  // ---- Delegación unificada de clics en tarjetas y controles ----
  document.addEventListener("click", function (e) {
    // 1. Cancelar cambio de stock (✕)
    var btnCancelar = e.target.closest(".nv-cancelar");
    if (btnCancelar) {
      var contCancelar = btnCancelar.closest(".nv-card-stock");
      if (!contCancelar || contCancelar.dataset.guardando === "1") return;
      actualizarVistaStock(contCancelar, parseInt(contCancelar.dataset.stockOriginal, 10));
      return;
    }

    // 2. Confirmar cambio de stock (✓)
    var btnCheck = e.target.closest(".nv-check");
    if (btnCheck) {
      if (btnCheck.disabled) return;
      var contenedor = btnCheck.closest(".nv-card-stock");
      if (!contenedor || contenedor.dataset.guardando === "1") return;

      var nuevoValor = contenedor.dataset.stockActual !== undefined
        ? parseInt(contenedor.dataset.stockActual, 10)
        : parseInt(contenedor.dataset.stockOriginal, 10);

      contenedor.dataset.guardando = "1";
      btnCheck.disabled = true;
      var btnCanc = contenedor.querySelector(".nv-cancelar");
      if (btnCanc) btnCanc.disabled = true;

      var datos = new FormData();
      datos.append("stock", nuevoValor);

      fetch(contenedor.dataset.stockUrl, {
        method: "POST",
        headers: { "X-CSRFToken": obtenerCsrf() },
        body: datos,
        credentials: "same-origin"
      })
        .then(function (respuesta) {
          if (respuesta.status === 403) {
            mostrarError("No tienes permiso para actualizar el stock.");
            return null;
          }
          return respuesta.json().then(function (data) {
            if (!respuesta.ok || !data.ok) {
              mostrarError(data.error || "No se pudo actualizar el stock.");
              return null;
            }
            return data;
          });
        })
        .then(function (data) {
          delete contenedor.dataset.guardando;
          if (!data) return;

          contenedor.dataset.stockOriginal = data.stock;
          actualizarVistaStock(contenedor, data.stock);

          if (data.parent_id && data.parent_stock !== null) {
            var cardPadre = document.querySelector('.nv-card[data-item-id="' + data.parent_id + '"] .nv-unidades-padre');
            if (cardPadre) {
              cardPadre.textContent = formatearUnidades(data.parent_stock, true);
            }
            var ddStock = modalEl.querySelector("dl dd:nth-of-type(3)");
            if (ddStock && ddStock.textContent.indexOf("unidad") !== -1) {
              ddStock.textContent = data.parent_stock > STOCK_MAX
                ? "+" + STOCK_MAX + " unidades"
                : data.parent_stock + (data.parent_stock === 1 ? " unidad" : " unidades");
            }
          }
        })
        .catch(function () {
          delete contenedor.dataset.guardando;
          btnCheck.disabled = false;
          if (btnCanc) btnCanc.disabled = false;
          mostrarError("No se pudo conectar con el servidor.");
        });
      return;
    }

    // 3. Abrir modal de detalle al pulsar la tarjeta
    if (holdActivo) return;
    if (e.target.closest(".nv-stock-btn, .nv-check, .nv-cancelar, input, select, textarea")) return;
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
})();