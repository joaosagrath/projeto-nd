# Fluxar ND

Aplicação local em Python + Flask para cadastro de tomadores, criação, armazenamento e geração de Notas de Débito em PDF.

## Preparação no Windows

1. Execute `setup.bat`.
2. Aguarde a criação da pasta `.venv` e a instalação das dependências.
3. Execute `run.bat`.
4. Acesse `http://127.0.0.1:5000` no navegador.

## Fluxo sugerido

1. Abra **Configurações** e cadastre os dados do emitente e o logotipo.
2. Abra **Tomadores** e cadastre os clientes que serão reutilizados nas NDs.
3. Em **Nova ND**, use a busca em modal para localizar o tomador por nome, CPF ou CNPJ.
4. Informe datas, condição, itens e valores; os campos monetários aplicam a formatação brasileira automaticamente.
5. Gere a Nota de Débito e baixe o PDF.
6. Se necessário, use **Editar** para corrigir uma ND já gravada sem alterar sua numeração.

## Estrutura

- `app.py`: aplicação Flask, rotas, validações e migrações simples do SQLite.
- `models.py`: modelos SQLite/SQLAlchemy.
- `services/pdf_service.py`: geração do PDF da Nota de Débito.
- `templates/`: telas HTML/Jinja.
- `static/`: CSS e JavaScript.
- `instance/fluxar_nd.db`: banco SQLite criado automaticamente na primeira execução.
- `instance/uploads/`: logotipo atual do emitente.

## Histórico das NDs

Ao emitir uma nova ND, o sistema grava uma cópia dos dados do tomador, do emitente e do logotipo utilizados naquele momento. Assim, alterações posteriores nos cadastros não modificam o conteúdo das NDs já emitidas.

## Banco existente

Ao iniciar esta versão sobre um banco criado pela versão inicial, o Fluxar ND adiciona automaticamente os novos campos necessários. Não é preciso apagar o arquivo `instance/fluxar_nd.db`.

## Empacotamento

O projeto mantém as dependências de desenvolvimento em `requirements-dev.txt` para permitir o uso do PyInstaller em uma etapa posterior.
