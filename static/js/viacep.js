(function () {
  function somenteDigitos(valor) {
    return String(valor || "").replace(/\D/g, "");
  }

  function definirStatus(elemento, mensagem, tipo) {
    if (!elemento) {
      return;
    }

    elemento.textContent = mensagem;
    elemento.classList.remove("text-body-secondary", "text-success", "text-danger");
    elemento.classList.add(tipo || "text-body-secondary");
  }

  function preencherEndereco(container, dados) {
    container.querySelectorAll("[data-viacep-field]").forEach(function (campo) {
      const chave = campo.dataset.viacepField;
      if (Object.prototype.hasOwnProperty.call(dados, chave) && dados[chave]) {
        campo.value = dados[chave];
        campo.dispatchEvent(new Event("input", { bubbles: true }));
      }
    });
  }

  document.querySelectorAll(".viacep-endereco").forEach(function (container) {
    const campoCep = container.querySelector(".viacep-cep");
    const botaoBuscar = container.querySelector(".viacep-buscar");
    const status = container.querySelector(".viacep-status");
    const campoNumero = container.querySelector(".viacep-numero");
    const urlModelo = container.dataset.viacepUrl || "/api/cep/__CEP__";

    if (!campoCep) {
      return;
    }

    let ultimoCepConsultado = "";
    let temporizador = null;
    let controlador = null;

    async function consultarCep(forcar, focarNumero) {
      const cep = somenteDigitos(campoCep.value).slice(0, 8);

      if (!cep) {
        ultimoCepConsultado = "";
        definirStatus(status, "Informe o CEP para preencher o endereço automaticamente.", "text-body-secondary");
        return;
      }

      if (cep.length !== 8) {
        if (forcar) {
          definirStatus(status, "Informe os 8 dígitos do CEP.", "text-danger");
        }
        return;
      }

      if (!forcar && cep === ultimoCepConsultado) {
        return;
      }

      if (controlador) {
        controlador.abort();
      }
      controlador = new AbortController();

      definirStatus(status, "Consultando CEP...", "text-body-secondary");
      if (botaoBuscar) {
        botaoBuscar.disabled = true;
      }

      try {
        const url = urlModelo.replace("__CEP__", encodeURIComponent(cep));
        const resposta = await fetch(url, {
          signal: controlador.signal,
          headers: { Accept: "application/json" },
        });
        const dados = await resposta.json();

        if (!resposta.ok || dados.erro) {
          ultimoCepConsultado = "";
          definirStatus(status, dados.mensagem || "CEP não encontrado.", "text-danger");
          return;
        }

        preencherEndereco(container, dados);
        ultimoCepConsultado = cep;
        definirStatus(status, "Endereço preenchido pelo ViaCEP.", "text-success");

        if (focarNumero && campoNumero) {
          campoNumero.focus();
        }
      } catch (erro) {
        if (erro.name === "AbortError") {
          return;
        }

        ultimoCepConsultado = "";
        definirStatus(
          status,
          "Não foi possível consultar o ViaCEP. Você pode preencher o endereço manualmente.",
          "text-danger"
        );
      } finally {
        if (botaoBuscar) {
          botaoBuscar.disabled = false;
        }
      }
    }

    campoCep.addEventListener("input", function () {
      window.clearTimeout(temporizador);
      const cep = somenteDigitos(campoCep.value);

      if (cep.length < 8) {
        ultimoCepConsultado = "";
        definirStatus(status, "Informe o CEP para preencher o endereço automaticamente.", "text-body-secondary");
        return;
      }

      temporizador = window.setTimeout(function () {
        consultarCep(false, false);
      }, 350);
    });

    campoCep.addEventListener("blur", function () {
      consultarCep(false, false);
    });

    if (botaoBuscar) {
      botaoBuscar.addEventListener("click", function () {
        consultarCep(true, true);
      });
    }
  });
})();
