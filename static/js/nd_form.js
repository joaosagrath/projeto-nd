(function () {
  const formulario = document.getElementById("formNotaDebito");
  const tabela = document.querySelector("#tabelaItens tbody");
  const btnAdicionar = document.getElementById("btnAdicionarItem");
  const campoRetencoes = document.getElementById("outras_retencoes");
  const resumoTotal = document.getElementById("resumoValorTotal");
  const resumoPagar = document.getElementById("resumoValorPagar");
  const campoEmissao = document.getElementById("emissao");
  const campoReferencia = document.getElementById("referencia");
  const campoTomadorId = document.getElementById("tomador_id");
  const campoTomadorNome = document.getElementById("tomadorNomeSelecionado");
  const resumoTomador = document.getElementById("tomadorResumo");
  const resumoDocumento = document.getElementById("tomadorResumoDocumento");
  const resumoEndereco = document.getElementById("tomadorResumoEndereco");
  const resumoTelefone = document.getElementById("tomadorResumoTelefone");
  const resumoEmail = document.getElementById("tomadorResumoEmail");
  const btnEditarTomadorSelecionado = document.getElementById("btnEditarTomadorSelecionado");
  const modalTomadorElemento = document.getElementById("modalBuscarTomador");
  const campoBuscaTomador = document.getElementById("buscaTomador");
  const resultadosTomadores = document.getElementById("resultadosTomadores");
  const tomadorSelecionadoElemento = document.getElementById("tomadorSelecionadoData");
  const tiposDocumentoElemento = document.getElementById("tiposDocumentoData");
  const configNotaElemento = document.getElementById("configNotaData");
  const campoTipoDocumento = document.getElementById("tipo_documento_id");
  const tipoDocumentoNome = document.getElementById("tipoDocumentoNome");
  const tipoDocumentoNumero = document.getElementById("tipoDocumentoNumero");
  const campoObservacoes = document.getElementById("observacoes");

  const configNota = configNotaElemento
    ? JSON.parse(configNotaElemento.textContent || "{}")
    : {};
  const tiposDocumento = tiposDocumentoElemento
    ? JSON.parse(tiposDocumentoElemento.textContent || "[]")
    : [];

  let tomadorSelecionado = tomadorSelecionadoElemento
    ? JSON.parse(tomadorSelecionadoElemento.textContent || "null")
    : null;
  let referenciaAutomatica = campoReferencia ? campoReferencia.value : "";
  let temporizadorBuscaTomador = null;
  let requisicaoBuscaTomador = null;

  function atualizarTipoDocumento(atualizarObservacao) {
    if (!campoTipoDocumento) {
      return;
    }

    const tipoId = Number.parseInt(campoTipoDocumento.value || "0", 10);
    const tipo = tiposDocumento.find(function (item) {
      return Number(item.id) === tipoId;
    });

    if (!tipo) {
      if (tipoDocumentoNome) {
        tipoDocumentoNome.textContent = "Nenhum tipo selecionado";
      }
      if (tipoDocumentoNumero) {
        tipoDocumentoNumero.textContent = "—";
      }
      return;
    }

    if (tipoDocumentoNome) {
      tipoDocumentoNome.textContent = tipo.nome || "Documento";
    }
    if (tipoDocumentoNumero) {
      tipoDocumentoNumero.textContent = tipo.numero_formatado || "—";
    }
    if (atualizarObservacao && campoObservacoes) {
      campoObservacoes.value = tipo.observacao_padrao || "";
    }
  }

  function moedaParaNumero(valor) {
    const texto = String(valor || "0")
      .trim()
      .replace(/R\$/g, "")
      .replace(/\s/g, "");

    if (texto.includes(",")) {
      return Number(texto.replace(/\./g, "").replace(",", ".")) || 0;
    }

    return Number(texto.replace(/\./g, "")) || 0;
  }

  function formatarMoeda(valor) {
    return valor.toLocaleString("pt-BR", {
      style: "currency",
      currency: "BRL",
    });
  }

  function normalizarParteInteira(valor) {
    const digitos = String(valor || "").replace(/\D/g, "").replace(/^0+(?=\d)/, "");
    return digitos || "0";
  }

  function formatarPartesMoeda(inteiro, decimais) {
    const inteiroNormalizado = normalizarParteInteira(inteiro);
    const inteiroFormatado = inteiroNormalizado.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    const decimaisNormalizados = String(decimais || "")
      .replace(/\D/g, "")
      .slice(0, 2)
      .padEnd(2, "0");

    return `${inteiroFormatado},${decimaisNormalizados}`;
  }

  function decomporMoeda(valor) {
    const texto = String(valor || "")
      .trim()
      .replace(/R\$/g, "")
      .replace(/\s/g, "");

    if (!texto) {
      return { inteiro: "0", decimais: "00" };
    }

    const posicaoVirgula = texto.lastIndexOf(",");
    if (posicaoVirgula >= 0) {
      return {
        inteiro: normalizarParteInteira(texto.slice(0, posicaoVirgula)),
        decimais: texto.slice(posicaoVirgula + 1).replace(/\D/g, "").slice(0, 2).padEnd(2, "0"),
      };
    }

    return {
      inteiro: normalizarParteInteira(texto),
      decimais: "00",
    };
  }

  function atualizarCampoMoeda(campo, inteiro, decimais, modoDecimal) {
    campo.dataset.inteiro = normalizarParteInteira(inteiro);
    campo.dataset.decimais = String(decimais || "").replace(/\D/g, "").slice(0, 2);
    campo.dataset.modoDecimal = modoDecimal ? "1" : "0";
    campo.value = formatarPartesMoeda(campo.dataset.inteiro, campo.dataset.decimais);
  }

  function inicializarCampoMoeda(campo) {
    if (!campo || campo.dataset.mascaraMoeda === "1") {
      return;
    }

    const partes = decomporMoeda(campo.value);
    campo.dataset.mascaraMoeda = "1";
    atualizarCampoMoeda(campo, partes.inteiro, partes.decimais, false);

    campo.addEventListener("focus", function () {
      if (campo.value === "0,00") {
        window.setTimeout(function () {
          campo.select();
        }, 0);
      }
    });

    campo.addEventListener("keydown", function (event) {
      if (event.ctrlKey || event.metaKey || event.altKey) {
        return;
      }

      if (/^\d$/.test(event.key)) {
        event.preventDefault();

        const tudoSelecionado =
          campo.selectionStart === 0 && campo.selectionEnd === campo.value.length;
        let inteiro = tudoSelecionado ? "0" : campo.dataset.inteiro || "0";
        let decimais = tudoSelecionado ? "" : campo.dataset.decimais || "";
        let modoDecimal = tudoSelecionado ? false : campo.dataset.modoDecimal === "1";

        if (modoDecimal) {
          if (decimais.length < 2) {
            decimais += event.key;
          }
        } else {
          inteiro = inteiro === "0" ? event.key : `${inteiro}${event.key}`;
        }

        atualizarCampoMoeda(campo, inteiro, decimais, modoDecimal);
        atualizarTotais();
        return;
      }

      if (event.key === "," || event.key === ".") {
        event.preventDefault();
        campo.dataset.modoDecimal = "1";
        campo.dataset.decimais = "";
        campo.value = formatarPartesMoeda(campo.dataset.inteiro || "0", "");
        return;
      }

      if (event.key === "Backspace") {
        event.preventDefault();

        const tudoSelecionado =
          campo.selectionStart === 0 && campo.selectionEnd === campo.value.length;
        if (tudoSelecionado) {
          atualizarCampoMoeda(campo, "0", "", false);
        } else if (campo.dataset.modoDecimal === "1") {
          const decimais = campo.dataset.decimais || "";
          if (decimais.length > 0) {
            atualizarCampoMoeda(
              campo,
              campo.dataset.inteiro || "0",
              decimais.slice(0, -1),
              true
            );
          } else {
            atualizarCampoMoeda(campo, campo.dataset.inteiro || "0", "", false);
          }
        } else {
          const inteiro = campo.dataset.inteiro || "0";
          atualizarCampoMoeda(campo, inteiro.length > 1 ? inteiro.slice(0, -1) : "0", "", false);
        }

        atualizarTotais();
        return;
      }

      if (event.key === "Delete") {
        event.preventDefault();
        atualizarCampoMoeda(campo, "0", "", false);
        atualizarTotais();
      }
    });

    campo.addEventListener("paste", function (event) {
      event.preventDefault();
      const texto = (event.clipboardData || window.clipboardData).getData("text");
      const partesColadas = decomporMoeda(texto);
      atualizarCampoMoeda(campo, partesColadas.inteiro, partesColadas.decimais, false);
      atualizarTotais();
    });

    campo.addEventListener("change", function () {
      const partesAlteradas = decomporMoeda(campo.value);
      atualizarCampoMoeda(campo, partesAlteradas.inteiro, partesAlteradas.decimais, false);
      atualizarTotais();
    });
  }

  function inicializarMascarasMoeda(raiz) {
    (raiz || document).querySelectorAll(".campo-moeda").forEach(inicializarCampoMoeda);
  }

  function atualizarTotais() {
    let totalGeral = 0;

    tabela.querySelectorAll(".linha-item").forEach(function (linha) {
      const quantidade = Number.parseInt(linha.querySelector(".item-quantidade").value || "0", 10) || 0;
      const unitario = moedaParaNumero(linha.querySelector(".item-unitario").value);
      const totalItem = quantidade * unitario;

      linha.querySelector(".item-total").textContent = formatarMoeda(totalItem);
      totalGeral += totalItem;
    });

    const retencoes = moedaParaNumero(campoRetencoes.value);
    const valorPagar = Math.max(totalGeral - retencoes, 0);

    resumoTotal.textContent = formatarMoeda(totalGeral);
    resumoPagar.textContent = formatarMoeda(valorPagar);
  }

  function adicionarItem() {
    const linha = document.createElement("tr");
    linha.className = "linha-item";
    linha.innerHTML = `
      <td>
        <input class="form-control" type="text" name="item_descricao[]" required>
      </td>
      <td>
        <input class="form-control item-quantidade" type="number" name="item_quantidade[]" value="1" min="1" step="1" inputmode="numeric" required>
      </td>
      <td>
        <input class="form-control item-unitario campo-moeda" type="text" name="item_valor_unitario[]" value="0,00" inputmode="decimal" autocomplete="off" required>
      </td>
      <td class="text-end fw-semibold item-total">R$ 0,00</td>
      <td class="text-end">
        <button class="btn btn-sm btn-outline-danger btn-remover-item" type="button" aria-label="Remover item">×</button>
      </td>
    `;

    tabela.appendChild(linha);
    inicializarMascarasMoeda(linha);
    linha.querySelector('input[name="item_descricao[]"]').focus();
  }

  function gerarReferencia(dataIso) {
    if (!dataIso || !/^\d{4}-\d{2}-\d{2}$/.test(dataIso)) {
      return "";
    }

    const partes = dataIso.split("-");
    return `${partes[1]}/${partes[0]}`;
  }

  function atualizarReferenciaAutomatica() {
    if (!campoEmissao || !campoReferencia) {
      return;
    }

    const novaReferencia = gerarReferencia(campoEmissao.value);
    const valorAtual = campoReferencia.value.trim();

    if (!valorAtual || valorAtual === referenciaAutomatica) {
      campoReferencia.value = novaReferencia;
      referenciaAutomatica = novaReferencia;
    }
  }

  function montarUrlComTomador(urlBase, tomadorId) {
    if (!urlBase || !tomadorId) {
      return "#";
    }

    return urlBase.replace(/\/0(?=\/|$)/, `/${tomadorId}`);
  }

  function atualizarBotaoEditarTomador() {
    if (!btnEditarTomadorSelecionado) {
      return;
    }

    if (!tomadorSelecionado || !tomadorSelecionado.id) {
      btnEditarTomadorSelecionado.href = "#";
      btnEditarTomadorSelecionado.classList.add("disabled");
      btnEditarTomadorSelecionado.setAttribute("aria-disabled", "true");
      btnEditarTomadorSelecionado.setAttribute("tabindex", "-1");
      return;
    }

    btnEditarTomadorSelecionado.href = montarUrlComTomador(
      configNota.url_editar_tomador_base,
      tomadorSelecionado.id
    );
    btnEditarTomadorSelecionado.classList.remove("disabled");
    btnEditarTomadorSelecionado.removeAttribute("aria-disabled");
    btnEditarTomadorSelecionado.removeAttribute("tabindex");
  }

  function atualizarResumoTomador(tomador) {
    tomadorSelecionado = tomador || null;
    atualizarBotaoEditarTomador();

    if (!tomadorSelecionado) {
      campoTomadorId.value = "";
      campoTomadorNome.value = "";
      resumoTomador.classList.add("d-none");
      return;
    }

    campoTomadorId.value = String(tomadorSelecionado.id);
    campoTomadorNome.value = tomadorSelecionado.nome || "";
    resumoDocumento.textContent = tomadorSelecionado.documento || "-";
    resumoEndereco.textContent = tomadorSelecionado.endereco || "-";
    resumoTelefone.textContent = tomadorSelecionado.telefone || "-";
    resumoEmail.textContent = tomadorSelecionado.email || "-";
    resumoTomador.classList.remove("d-none");
  }

  async function recarregarTomadorSelecionado() {
    if (!tomadorSelecionado || !tomadorSelecionado.id || !configNota.url_tomador_detalhe_base) {
      return;
    }

    const tomadorId = tomadorSelecionado.id;
    const url = montarUrlComTomador(configNota.url_tomador_detalhe_base, tomadorId);

    try {
      const resposta = await fetch(url, {
        headers: { Accept: "application/json" },
        cache: "no-store",
      });

      if (!resposta.ok) {
        return;
      }

      const tomador = await resposta.json();

      if (Number(tomador.id) === Number(tomadorId)) {
        atualizarResumoTomador(tomador);
      }
    } catch (erro) {
      // A atualização automática é apenas uma conveniência.
    }
  }

  function criarCelula(texto, classe) {
    const td = document.createElement("td");
    td.textContent = texto || "-";
    if (classe) {
      td.className = classe;
    }
    return td;
  }

  function renderizarTomadores(tomadores) {
    resultadosTomadores.innerHTML = "";

    if (!tomadores.length) {
      const linha = document.createElement("tr");
      const celula = document.createElement("td");
      celula.colSpan = 4;
      celula.className = "text-center text-body-secondary py-4";
      celula.textContent = "Nenhum tomador encontrado.";
      linha.appendChild(celula);
      resultadosTomadores.appendChild(linha);
      return;
    }

    tomadores.forEach(function (tomador) {
      const linha = document.createElement("tr");
      linha.className = "tomador-resultado";
      linha.appendChild(criarCelula(tomador.nome));
      linha.appendChild(criarCelula(tomador.documento));
      linha.appendChild(criarCelula(tomador.endereco));

      const celulaAcao = document.createElement("td");
      celulaAcao.className = "text-end";
      const botao = document.createElement("button");
      botao.type = "button";
      botao.className = "btn btn-sm btn-primary";
      botao.textContent = "Selecionar";
      botao.addEventListener("click", function () {
        atualizarResumoTomador(tomador);
        bootstrap.Modal.getOrCreateInstance(modalTomadorElemento).hide();
      });
      celulaAcao.appendChild(botao);
      linha.appendChild(celulaAcao);
      resultadosTomadores.appendChild(linha);
    });
  }

  async function buscarTomadores(termo) {
    if (!configNota.url_busca_tomadores) {
      return;
    }

    if (requisicaoBuscaTomador) {
      requisicaoBuscaTomador.abort();
    }

    requisicaoBuscaTomador = new AbortController();
    resultadosTomadores.innerHTML = `
      <tr>
        <td colspan="4" class="text-center text-body-secondary py-4">Pesquisando...</td>
      </tr>
    `;

    try {
      const url = new URL(configNota.url_busca_tomadores, window.location.origin);
      if (termo) {
        url.searchParams.set("q", termo);
      }

      const resposta = await fetch(url, {
        signal: requisicaoBuscaTomador.signal,
        headers: { Accept: "application/json" },
      });

      if (!resposta.ok) {
        throw new Error("Falha ao pesquisar tomadores.");
      }

      const tomadores = await resposta.json();
      renderizarTomadores(tomadores);
    } catch (erro) {
      if (erro.name === "AbortError") {
        return;
      }

      resultadosTomadores.innerHTML = `
        <tr>
          <td colspan="4" class="text-center text-danger py-4">Não foi possível carregar os tomadores.</td>
        </tr>
      `;
    }
  }

  tabela.addEventListener("input", function (event) {
    if (event.target.classList.contains("item-quantidade")) {
      const valor = event.target.value.replace(/\D/g, "");
      event.target.value = valor ? String(Math.max(Number.parseInt(valor, 10), 1)) : "";
      atualizarTotais();
    }
  });

  tabela.addEventListener("click", function (event) {
    const botao = event.target.closest(".btn-remover-item");
    if (!botao) {
      return;
    }

    const linhas = tabela.querySelectorAll(".linha-item");
    if (linhas.length === 1) {
      linhas[0].querySelector('input[name="item_descricao[]"]').value = "";
      linhas[0].querySelector(".item-quantidade").value = "1";
      atualizarCampoMoeda(linhas[0].querySelector(".item-unitario"), "0", "", false);
    } else {
      botao.closest(".linha-item").remove();
    }

    atualizarTotais();
  });

  btnAdicionar.addEventListener("click", adicionarItem);

  if (campoEmissao) {
    campoEmissao.addEventListener("change", atualizarReferenciaAutomatica);
  }

  if (campoReferencia) {
    campoReferencia.addEventListener("input", function () {
      if (campoReferencia.value.trim() !== referenciaAutomatica) {
        referenciaAutomatica = "";
      }
    });
  }

  if (campoTipoDocumento) {
    campoTipoDocumento.addEventListener("change", function () {
      atualizarTipoDocumento(true);
    });
  }

  if (modalTomadorElemento) {
    modalTomadorElemento.addEventListener("shown.bs.modal", function () {
      campoBuscaTomador.focus();
      buscarTomadores(campoBuscaTomador.value.trim());
    });
  }

  if (campoBuscaTomador) {
    campoBuscaTomador.addEventListener("input", function () {
      window.clearTimeout(temporizadorBuscaTomador);
      temporizadorBuscaTomador = window.setTimeout(function () {
        buscarTomadores(campoBuscaTomador.value.trim());
      }, 250);
    });
  }

  window.addEventListener("focus", function () {
    recarregarTomadorSelecionado();
  });

  if (formulario) {
    formulario.addEventListener("submit", function (event) {
      if (campoTipoDocumento && !campoTipoDocumento.value) {
        event.preventDefault();
        campoTipoDocumento.focus();
        return;
      }

      if (!campoTomadorId.value) {
        event.preventDefault();
        bootstrap.Modal.getOrCreateInstance(modalTomadorElemento).show();
      }
    });
  }

  inicializarMascarasMoeda(document);
  atualizarTipoDocumento(false);
  atualizarResumoTomador(tomadorSelecionado);
  atualizarTotais();
})();
