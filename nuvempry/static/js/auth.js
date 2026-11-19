// ---- Mostrar / ocultar contraseña ----
document.querySelectorAll("[data-toggle-password]").forEach(function (boton) {
  boton.addEventListener("click", function () {
    var campo = document.getElementById(boton.dataset.togglePassword);
    campo.type = campo.type === "password" ? "text" : "password";
  });
});

// ---- Registro en dos pasos ----
(function () {
  var form = document.getElementById("form-registro");
  if (!form) return;

  var pasos = form.querySelectorAll(".paso");
  function mostrar(n) {
    pasos.forEach(function (p) {
      p.classList.toggle("activo", p.dataset.paso === String(n));
    });
  }

  document.getElementById("btn-continuar").addEventListener("click", function () {
    // 1) Validación básica del navegador (vacíos, formato de correo)
    var campos = pasos[0].querySelectorAll("input");
    for (var i = 0; i < campos.length; i++) {
      if (!campos[i].reportValidity()) return;
    }
    // 2) Las contraseñas deben coincidir
    var clave2 = document.getElementById("id_password2");
    if (document.getElementById("id_password").value !== clave2.value) {
      clave2.setCustomValidity("Las contraseñas no coinciden.");
      clave2.reportValidity();
      clave2.addEventListener("input", function () { clave2.setCustomValidity(""); }, { once: true });
      return;
    }
    mostrar(2);
  });

  document.getElementById("btn-volver").addEventListener("click", function () { mostrar(1); });

  // Enter en el paso 1 = "Continuar" (y no enviar el formulario a medias)
  pasos[0].addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      e.preventDefault();
      document.getElementById("btn-continuar").click();
    }
  });
})();