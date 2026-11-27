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

  document.addEventListener("DOMContentLoaded", () => {
  const modalAgregar = document.getElementById("modal-agregar");
  const dataEl = document.getElementById("roles-info-data");
  if (!modalAgregar || !dataEl) return;

  const selectRol = modalAgregar.querySelector('select[name="role"]');
  const cajaAyuda = document.getElementById("ayuda-rol");
  const tituloAyuda = document.getElementById("ayuda-rol-titulo");
  const descAyuda = document.getElementById("ayuda-rol-desc");
  if (!selectRol || !cajaAyuda) return;

  const rolesInfo = JSON.parse(dataEl.textContent);
  const opcionPlaceholder = selectRol.querySelector('option[value=""]');

  function describirPermisos(info) {
    if (info.crud_user && info.crud_item && info.update_stock) {
      return "Acceso total: puede gestionar usuarios, revisar auditoría, crear/editar productos y modificar el stock.";
    }
    if (info.crud_user && !info.crud_item && !info.update_stock) {
      return "Puede administrar usuarios y revisar el historial de auditoría, pero no puede crear productos ni alterar el stock.";
    }
    if (!info.crud_user && info.crud_item && info.update_stock) {
      return "Gestión de bodega: puede crear, editar o eliminar productos y actualizar sus unidades de stock.";
    }
    if (!info.crud_user && !info.crud_item && info.update_stock) {
      return "Operación diaria: puede sumar o descontar unidades de stock en productos existentes, sin crear ni borrar artículos.";
    }
    return "Solo lectura: puede consultar el inventario y reportes, sin permisos para editar productos, stock ni usuarios.";
  }

  function actualizarAyudaRol() {
    const val = selectRol.value;
    const info = rolesInfo[val];

    if (!val || !info) {
      cajaAyuda.classList.add("d-none");
      return;
    }

    // Evitar volver a elegir "Selecciona un rol" una vez seleccionado uno válido
    if (opcionPlaceholder) {
      opcionPlaceholder.disabled = true;
      opcionPlaceholder.hidden = true;
    }

    tituloAyuda.textContent = `Permisos de ${info.nombre}`;
    descAyuda.textContent = describirPermisos(info);
    cajaAyuda.classList.remove("d-none");
  }

  selectRol.addEventListener("change", actualizarAyudaRol);

  // Ejecutar al cargar por si el formulario volvió abierto tras un error de validación
  actualizarAyudaRol();
});
})();