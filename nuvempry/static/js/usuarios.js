(function () {
  var modalEl = document.getElementById("modal-confirmar");
  if (!modalEl) return;

  var modal = new bootstrap.Modal(modalEl);
  var form = document.getElementById("form-confirmar");
  var titulo = document.getElementById("confirmar-titulo");
  var texto = document.getElementById("confirmar-texto");
  var campoMail = document.getElementById("confirmar-mail");
  var campoRol = document.getElementById("confirmar-rol");
  var boton = document.getElementById("confirmar-boton");

  document.querySelectorAll("[data-accion]").forEach(function (el) {
    el.addEventListener("click", function () {
      var d = el.dataset;
      campoMail.value = d.mail;

      if (d.accion === "rol") {
        form.action = modalEl.dataset.urlRol;
        campoRol.value = d.rolId;
        titulo.textContent = "Cambiar rol";
        texto.textContent = "¿Cambiar el rol de " + d.nombre + " a " + d.rolNombre + "?";
        boton.textContent = "Sí, cambiar rol";
        boton.className = "btn btn-nv";
      } else {
        form.action = modalEl.dataset.urlEliminar;
        campoRol.value = "";
        titulo.textContent = "Eliminar usuario";
        texto.textContent = "¿Eliminar a " + d.nombre + "? Esta acción no se puede deshacer.";
        boton.textContent = "Sí, eliminar";
        boton.className = "btn btn-danger";
      }
      modal.show();
    });
  });
})();