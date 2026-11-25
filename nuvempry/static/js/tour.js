document.addEventListener("DOMContentLoaded", () => {
  const dataEl = document.getElementById("nv-tour-data");
  const configEl = document.getElementById("nv-tour-config");
  if (!dataEl || !configEl) return;

  const STORAGE_KEY = "nv_onboarding_step";
  const pasos = JSON.parse(dataEl.textContent);
  const iniciar = configEl.dataset.iniciar === "1";
  const urlDesactivar = configEl.dataset.urlDesactivar;
  const csrfToken = configEl.dataset.csrf;

  // Permitir reiniciar el tutorial desde cualquier botón con data-iniciar-tour
  document.addEventListener("click", (e) => {
    const btnIniciar = e.target.closest("[data-iniciar-tour]");
    if (!btnIniciar) return;
    e.preventDefault();
    sessionStorage.setItem(STORAGE_KEY, "0");
    window.location.href = pasos[0].ruta;
  });

  if (iniciar) {
    sessionStorage.setItem(STORAGE_KEY, "0");
    fetch(urlDesactivar, {
      method: "POST",
      headers: { "X-CSRFToken": csrfToken },
      credentials: "same-origin",
    }).catch(() => {});
  }

  const rawStep = sessionStorage.getItem(STORAGE_KEY);
  if (rawStep === null) return;

  const pasoActual = parseInt(rawStep, 10);
  if (isNaN(pasoActual) || pasoActual < 0 || pasoActual >= pasos.length) {
    sessionStorage.removeItem(STORAGE_KEY);
    return;
  }

  const paso = pasos[pasoActual];
  const esUltimo = pasoActual === pasos.length - 1;
  const backdrop = document.getElementById("nvTourBackdrop");
  const card = document.getElementById("nvTourCard");
  const btnNext = document.getElementById("nvTourNext");
  const btnSkip = document.getElementById("nvTourSkip");

  let targetActual = null;
  let modalAbierto = false;
  let envioFormularioEnModal = false;

  function limpiarDestacado() {
    document.querySelectorAll(".nv-tour-highlight").forEach((el) => {
      el.classList.remove("nv-tour-highlight");
    });
  }

  function finalizarTour() {
    sessionStorage.removeItem(STORAGE_KEY);
    targetActual = null;
    limpiarDestacado();
    backdrop.classList.add("d-none");
    card.classList.add("d-none");
  }

  function avanzarPaso() {
    if (esUltimo) {
      finalizarTour();
      return;
    }
    const siguiente = pasoActual + 1;
    sessionStorage.setItem(STORAGE_KEY, String(siguiente));
    if (pasos[siguiente].ruta !== window.location.pathname) {
      window.location.href = pasos[siguiente].ruta;
    } else {
      window.location.reload();
    }
  }

  function posicionarTarjeta(target) {
    if (card.classList.contains("d-none")) return;

    const vw = document.documentElement.clientWidth;
    const vh = document.documentElement.clientHeight;
    const margen = 16;

    if (!target) {
      card.style.top = "50%";
      card.style.left = "50%";
      card.style.transform = "translate(-50%, -50%)";
      return;
    }

    card.style.transform = "none";
    const rect = target.getBoundingClientRect();
    const cardWidth = card.offsetWidth;
    const cardHeight = card.offsetHeight;

    const estaALaDerecha = rect.left + rect.width / 2 > vw / 2;
    let left = estaALaDerecha ? rect.right - cardWidth : rect.left;
    left = Math.max(margen, Math.min(left, vw - cardWidth - margen));

    // Preferir debajo del elemento; si no cabe abajo, colocar encima
    let top = rect.bottom + 14;
    if (top + cardHeight > vh - margen) {
      top = rect.top - cardHeight - 14;
    }
    // Mantener siempre dentro de los límites verticales visibles de la pantalla
    top = Math.max(margen, Math.min(top, vh - cardHeight - margen));

    card.style.left = `${left}px`;
    card.style.top = `${top}px`;
  }

  function asegurarSidebarAbierta() {
    const htmlEl = document.documentElement;
    if (!htmlEl.classList.contains("sidebar-cerrada")) return;

    const btnSidebar = document.getElementById("btn-sidebar");
    if (btnSidebar) {
      btnSidebar.click();
    } else {
      htmlEl.classList.remove("sidebar-cerrada");
    }
  }

  function mostrarPaso() {
    if (window.location.pathname !== paso.ruta) {
      window.location.href = paso.ruta;
      return;
    }

    if (paso.selector.includes(".nav-nv")) {
      asegurarSidebarAbierta();
    }

    targetActual = document.querySelector(paso.selector);
    backdrop.classList.remove("d-none");
    card.classList.remove("d-none");

    document.getElementById("nvTourBadge").textContent = `Paso ${pasoActual + 1} de ${pasos.length}`;
    document.getElementById("nvTourTitle").textContent = paso.titulo;
    document.getElementById("nvTourText").innerHTML = formatearTextoTour(paso.texto);

    const hintEl = document.getElementById("nvTourHint");
    if (esPasoObligatorio()) {
      btnNext.classList.add("d-none");
      const nombreElemento = targetActual
        ? targetActual.textContent.trim().replace(/\s+/g, " ")
        : "";
      hintEl.textContent = nombreElemento
        ? `Haz clic en «${nombreElemento}» para continuar`
        : "Completa esta acción para continuar";
    } else {
      btnNext.classList.remove("d-none");

      const textoBoton = esUltimo ? "Finalizar" : "Siguiente";
      btnNext.textContent = textoBoton;

      if (esUltimo || paso.avanzar_al_click) {
        hintEl.textContent = ""
      } else {
        hintEl.textContent = `Pulsa ${textoBoton.toLocaleLowerCase()} para saltar`;
      }
    }

    if (targetActual) {
      targetActual.classList.add("nv-tour-highlight");
      targetActual.scrollIntoView({ behavior: "smooth", block: "center" });

      if (paso.avanzarAlClick) {
        targetActual.addEventListener("click", () => {
          sessionStorage.setItem(STORAGE_KEY, String(pasoActual + 1));
        }, { once: true });
      }
    }

    posicionarTarjeta(targetActual);
  }

  function esPasoObligatorio() {
    if (paso.obligatorio) return true;
    if (paso.obligatorioSiNoExiste) {
      return document.querySelector(paso.obligatorioSiNoExiste) === null;
    }
    return false;
  }

  // Actualizar posición continuamente mientras se hace scroll o cambia el tamaño de ventana
  let rafScroll = null;
  function actualizarPosicionEnPantalla() {
    if (!targetActual || card.classList.contains("d-none")) return;
    if (rafScroll) return;
    rafScroll = requestAnimationFrame(() => {
      posicionarTarjeta(targetActual);
      rafScroll = null;
    });
  }

  function formatearTextoTour(texto) {
    return String(texto || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/\n/g, "<br>");
  }

  window.addEventListener("scroll", actualizarPosicionEnPantalla, { passive: true });
  window.addEventListener("resize", actualizarPosicionEnPantalla, { passive: true });

  document.addEventListener("show.bs.modal", () => {
    modalAbierto = true;
    envioFormularioEnModal = false;
    backdrop.classList.add("d-none");
    card.classList.add("d-none");
    limpiarDestacado();
  });

  document.addEventListener("submit", (e) => {
    if (!modalAbierto || !paso.pausaEnModal) return;
    if (!e.target.closest(".modal")) return;

    envioFormularioEnModal = true;
    if (esUltimo) {
      sessionStorage.removeItem(STORAGE_KEY);
    } else {
      sessionStorage.setItem(STORAGE_KEY, String(pasoActual + 1));
    }
  }, true);

  document.addEventListener("hidden.bs.modal", () => {
    modalAbierto = false;
    if (sessionStorage.getItem(STORAGE_KEY) === null) return;

    if (paso.pausaEnModal) {
      if (envioFormularioEnModal) {
        const pasoGuardado = parseInt(sessionStorage.getItem(STORAGE_KEY), 10);
        if (pasos[pasoGuardado]?.ruta !== window.location.pathname) {
          window.location.href = pasos[pasoGuardado].ruta;
        } else {
          window.location.reload();
        }
      } else if (esPasoObligatorio()) {
        mostrarPaso();
      } else {
        avanzarPaso();
      }
    } else {
      mostrarPaso();
    }
  });

  // Bloquear clics en otros enlaces de la barra lateral mientras el tour está activo
  document.addEventListener("click", (e) => {
    if (backdrop.classList.contains("d-none")) return;
    if (!e.target.closest(".sidebar")) return;
    if (targetActual && targetActual.contains(e.target)) return;

    e.preventDefault();
    e.stopImmediatePropagation();
  }, true);

  btnSkip.addEventListener("click", finalizarTour);
  btnNext.addEventListener("click", () => {
    if (!esPasoObligatorio()) avanzarPaso();
  });

  setTimeout(mostrarPaso, 200);
});