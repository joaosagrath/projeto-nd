(function () {
  function somenteDigitos(valor) {
    return String(valor || "").replace(/\D/g, "");
  }

  function formatarDocumento(valor) {
    const digitos = somenteDigitos(valor).slice(0, 14);

    if (digitos.length <= 11) {
      return digitos
        .replace(/^(\d{3})(\d)/, "$1.$2")
        .replace(/^(\d{3})\.(\d{3})(\d)/, "$1.$2.$3")
        .replace(/\.(\d{3})(\d)/, ".$1-$2");
    }

    return digitos
      .replace(/^(\d{2})(\d)/, "$1.$2")
      .replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3")
      .replace(/\.(\d{3})(\d)/, ".$1/$2")
      .replace(/(\/\d{4})(\d)/, "$1-$2");
  }

  function formatarTelefone(valor) {
    const digitos = somenteDigitos(valor).slice(0, 11);

    if (digitos.length <= 10) {
      return digitos
        .replace(/^(\d{2})(\d)/, "($1) $2")
        .replace(/(\d{4})(\d)/, "$1-$2");
    }

    return digitos
      .replace(/^(\d{2})(\d)/, "($1) $2")
      .replace(/(\d{5})(\d)/, "$1-$2");
  }

  function formatarCep(valor) {
    const digitos = somenteDigitos(valor).slice(0, 8);
    return digitos.replace(/^(\d{2})(\d)/, "$1.$2").replace(/(\d{3})(\d)/, "$1-$2");
  }

  function aplicarMascara(campo, formatador) {
    campo.addEventListener("input", function () {
      const inicio = campo.selectionStart;
      const valorAnterior = campo.value;
      campo.value = formatador(campo.value);

      if (inicio !== null && campo.value.length >= valorAnterior.length) {
        campo.setSelectionRange(campo.value.length, campo.value.length);
      }
    });

    if (campo.value) {
      campo.value = formatador(campo.value);
    }
  }

  document.querySelectorAll(".mask-documento").forEach(function (campo) {
    aplicarMascara(campo, formatarDocumento);
  });

  document.querySelectorAll(".mask-telefone").forEach(function (campo) {
    aplicarMascara(campo, formatarTelefone);
  });

  document.querySelectorAll(".mask-cep").forEach(function (campo) {
    aplicarMascara(campo, formatarCep);
  });

  document.querySelectorAll(".mask-uf").forEach(function (campo) {
    campo.addEventListener("input", function () {
      campo.value = campo.value.replace(/[^A-Za-z]/g, "").toUpperCase().slice(0, 2);
    });
  });
})();
