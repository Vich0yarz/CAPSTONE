(function () {
  var raiz = document.documentElement;

  // Se ejecuta de inmediato (antes de dibujar la página) para que la barra
  // no "parpadee" si la dejaste cerrada.
  try {
    if (localStorage.getItem("nv-sidebar") === "cerrada") {
      raiz.classList.add("sidebar-cerrada");
    }
  } catch (e) {}

  document.addEventListener("DOMContentLoaded", function () {
    var boton = document.getElementById("btn-sidebar");
    if (!boton) return;
    boton.setAttribute("aria-expanded", String(!raiz.classList.contains("sidebar-cerrada")));

    boton.addEventListener("click", function () {
      var cerrada = raiz.classList.toggle("sidebar-cerrada");
      boton.setAttribute("aria-expanded", String(!cerrada));
      try {
        localStorage.setItem("nv-sidebar", cerrada ? "cerrada" : "abierta");
      } catch (e) {}
    });
  });
})();