(function () {
  var raiz = document.documentElement;

  // Aplicar preferencias de inmediato antes de pintar la página
  try {
    if (localStorage.getItem("nv-sidebar") === "cerrada") {
      raiz.classList.add("sidebar-cerrada");
    }
    if (localStorage.getItem("nv-tema") === "oscuro") {
      raiz.setAttribute("data-bs-theme", "dark");
    }
    if (localStorage.getItem("nv-escala") === "normal") {
      raiz.classList.remove("app-zoom");
    }
  } catch (e) {}

  document.addEventListener("DOMContentLoaded", function () {
    // 1. Menú lateral
    var botonSidebar = document.getElementById("btn-sidebar");
    if (botonSidebar) {
      botonSidebar.setAttribute("aria-expanded", String(!raiz.classList.contains("sidebar-cerrada")));
      botonSidebar.addEventListener("click", function () {
        var cerrada = raiz.classList.toggle("sidebar-cerrada");
        botonSidebar.setAttribute("aria-expanded", String(!cerrada));
        try {
          localStorage.setItem("nv-sidebar", cerrada ? "cerrada" : "abierta");
        } catch (e) {}
      });
    }

    // 2. Modo oscuro / claro
    var btnTema = document.getElementById("btn-tema");
    var txtTema = document.getElementById("txt-tema");
    var icoTema = document.querySelector("#ico-tema use");

    function sincronizarBotonTema() {
      if (!btnTema) return;
      var esOscuro = raiz.getAttribute("data-bs-theme") === "dark";
      btnTema.setAttribute("aria-pressed", String(esOscuro));
      if (txtTema) txtTema.textContent = esOscuro ? "Modo claro" : "Modo oscuro";
      if (icoTema) icoTema.setAttribute("href", esOscuro ? "#i-sun" : "#i-moon");
    }

    sincronizarBotonTema();

    if (btnTema) {
      btnTema.addEventListener("click", function () {
        var esOscuro = raiz.getAttribute("data-bs-theme") === "dark";
        if (esOscuro) {
          raiz.removeAttribute("data-bs-theme");
        } else {
          raiz.setAttribute("data-bs-theme", "dark");
        }
        sincronizarBotonTema();
        try {
          localStorage.setItem("nv-tema", esOscuro ? "claro" : "oscuro");
        } catch (e) {}
        document.dispatchEvent(new CustomEvent("nv:tema-cambiado", { detail: { oscuro: !esOscuro } }));
      });
    }

    // 3. Escala de texto (Grande 125% / Normal 100%)
    var btnEscala = document.getElementById("btn-escala");
    var txtEscala = document.getElementById("txt-escala");

    function sincronizarBotonEscala() {
      if (!btnEscala) return;
      var esGrande = raiz.classList.contains("app-zoom");
      btnEscala.setAttribute("aria-pressed", String(esGrande));
      if (txtEscala) txtEscala.textContent = esGrande ? "Tamaño: Grande" : "Tamaño: Normal";
    }

    sincronizarBotonEscala();

    if (btnEscala) {
      btnEscala.addEventListener("click", function () {
        var esGrande = raiz.classList.toggle("app-zoom");
        sincronizarBotonEscala();
        try {
          localStorage.setItem("nv-escala", esGrande ? "grande" : "normal");
        } catch (e) {}
      });
    }
  });
})();