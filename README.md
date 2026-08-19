# Fluxar ND

Aplicação local em Python + Flask para cadastro de tomadores, criação, armazenamento e geração de documentos de cobrança em PDF.

O nome do documento e o prefixo da numeração são configuráveis. Por padrão, o sistema inicia com **NOTA DE DÉBITO** e prefixo **ND**.

## Preparação no Windows

1. Execute `setup.bat`.
2. Aguarde a criação da pasta `.venv` e a instalação das dependências.
3. Execute `run.bat`.
4. Acesse `http://127.0.0.1:5000` no navegador.

## Fluxo sugerido

1. Abra **Configurações** e defina o nome do documento, prefixo, dados do emitente e logotipo.
2. No endereço da empresa, informe o CEP para preencher logradouro, bairro, cidade e UF pelo ViaCEP.
3. Abra **Tomadores** e cadastre os clientes que serão reutilizados nos documentos. O cadastro do tomador também possui consulta de CEP pelo ViaCEP.
4. Em **Novo documento**, use a busca em modal para localizar o tomador por nome, CPF ou CNPJ.
5. Informe datas, condição, itens e valores; os campos monetários aplicam a formatação brasileira automaticamente.
6. Gere o documento e baixe o PDF.
7. Se necessário, use **Editar** para corrigir um documento já gravado.

## Nome e prefixo do documento

Em **Configurações > Documento**:

- **Nome do documento** define o título mostrado no PDF, por exemplo `NOTA DE DÉBITO`, `RECIBO` ou `AVISO DE COBRANÇA`.
- **Prefixo da numeração** é concatenado com a sequência de cinco dígitos. `ND` gera `ND00001`. Prefixo vazio gera `00001`.

Documentos já emitidos preservam o nome e o prefixo que possuíam. Se um documento antigo for editado e salvo, ele passa a usar o nome e o prefixo configurados atualmente, mantendo o mesmo número sequencial interno.

## ViaCEP

A consulta é executada quando o CEP possui oito dígitos, ao sair do campo ou ao clicar em **Buscar**. O sistema preenche automaticamente logradouro, bairro, cidade e UF. Número e complemento permanecem para preenchimento manual.

Se a consulta não estiver disponível, o endereço continua editável manualmente.

## Estrutura

- `app.py`: aplicação Flask, rotas, validações e migrações simples do SQLite.
- `models.py`: modelos SQLite/SQLAlchemy.
- `services/pdf_service.py`: geração do PDF.
- `templates/`: telas HTML/Jinja.
- `static/js/viacep.js`: integração com o ViaCEP.
- `static/`: CSS e JavaScript.
- `instance/fluxar_nd.db`: banco SQLite criado automaticamente na primeira execução.
- `instance/uploads/`: logotipo atual do emitente.

## Histórico dos documentos

Ao emitir um novo documento, o sistema grava uma cópia dos dados do tomador, do emitente, do logotipo, do nome do documento e do prefixo utilizados naquele momento. Assim, alterações posteriores nos cadastros não modificam automaticamente os documentos já emitidos.

## Banco existente

Ao iniciar esta versão sobre um banco criado por uma versão anterior, o Fluxar ND adiciona automaticamente os novos campos necessários. Não é preciso apagar o arquivo `instance/fluxar_nd.db`.

## Empacotamento

O projeto mantém as dependências de desenvolvimento em `requirements-dev.txt` para permitir o uso do PyInstaller em uma etapa posterior.
