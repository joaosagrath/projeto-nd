# Fluxar Emissões

Aplicação em Python + Flask para cadastro de tomadores, criação, armazenamento, edição e emissão de documentos comerciais em PDF. O painel administrativo possui autenticação por login e senha.

O nome do documento e o prefixo da numeração são configuráveis. Por padrão, o sistema inicia com **NOTA DE DÉBITO** e prefixo **ND**.

## Preparação no Windows

1. Execute `setup.bat`.
2. Aguarde a criação da pasta `.venv` e a instalação das dependências.
3. Execute `run.bat`.
4. Acesse `http://127.0.0.1:5000` no navegador.
5. No primeiro acesso, use `admin` como login e `admin` como senha e altere as credenciais em **Configurações > Acesso ao sistema**.

## Fluxo sugerido

1. Abra **Configurações** e defina o nome do documento, prefixo, dados do emitente e logotipo.
2. No endereço da empresa, informe o CEP para preencher logradouro, bairro, cidade e UF pelo ViaCEP.
3. Abra **Tomadores** e cadastre os clientes que serão reutilizados nos documentos.
4. Em **Novo documento**, use a busca em modal para localizar o tomador por nome, CPF ou CNPJ.
5. Informe datas, condição, itens e valores.
6. Ao salvar, o PDF é gerado automaticamente e armazenado no servidor.
7. Se necessário, use **Editar**; ao salvar novamente, o PDF armazenado é regenerado.
8. Use **WhatsApp** para abrir `wa.me` com uma mensagem que contém o link público do PDF.

## Login, senha e recuperação

O painel administrativo é protegido por autenticação. Em uma instalação nova, o usuário inicial é:

- Login: `admin`
- Senha: `admin`

Altere essas credenciais em **Configurações > Acesso ao sistema** antes de publicar a aplicação. Nessa mesma tela é possível cadastrar um **e-mail de recuperação**. Para alterar login, e-mail ou senha, o sistema exige a senha atual. Novas senhas devem ter pelo menos 8 caracteres.

As senhas não são armazenadas em texto puro. O banco grava somente o hash gerado pelo Werkzeug. A sessão expira após 12 horas.

Na tela de login, o link **Esqueci minha senha** permite solicitar um link temporário por e-mail. O token é aleatório, o banco guarda apenas o hash do token, a validade é de 30 minutos e o link deixa de funcionar depois que a senha é redefinida.

A rota pública `/documentos/<token>/pdf` permanece sem login, porque é ela que permite ao tomador abrir o PDF enviado por WhatsApp. As demais telas e APIs administrativas exigem autenticação, com exceção das rotas de login e recuperação de senha.

A chave usada para assinar a sessão Flask é lida da variável de ambiente `FLUXAR_SECRET_KEY`. Se essa variável não estiver definida, o sistema cria automaticamente `instance/.secret_key` e reutiliza o mesmo valor nas próximas inicializações.

### Configuração do envio de e-mail

Por segurança, a senha da conta SMTP não é armazenada no banco nem na tela de Configurações. Configure o servidor usando variáveis de ambiente:

- `FLUXAR_SMTP_HOST`: servidor SMTP, por exemplo `smtp.gmail.com`.
- `FLUXAR_SMTP_PORT`: porta do servidor. O padrão é `587` com STARTTLS ou `465` com SSL.
- `FLUXAR_SMTP_USUARIO`: usuário usado para autenticar no SMTP.
- `FLUXAR_SMTP_SENHA`: senha ou senha de aplicativo do SMTP.
- `FLUXAR_SMTP_REMETENTE`: endereço usado como remetente. Se omitido, usa `FLUXAR_SMTP_USUARIO`.
- `FLUXAR_SMTP_NOME`: nome do remetente. O padrão é `Fluxar Emissões`.
- `FLUXAR_SMTP_TLS`: `true` ou `false`. O padrão é `true` quando SSL não está ativo.
- `FLUXAR_SMTP_SSL`: `true` ou `false`. O padrão é `false`.

Depois de configurar as variáveis e reiniciar a aplicação, **Configurações > Acesso ao sistema** mostrará que o envio de recuperação está ativo.

### Reset administrativo de emergência

Se o usuário não tiver acesso ao e-mail ou o SMTP estiver indisponível, execute no servidor:

```bash
cd ~/projeto-nd
source .venv/bin/activate
python reset_senha.py
```

No Windows, com a `.venv` ativa, execute:

```bat
python reset_senha.py
```

O script permite manter ou alterar o login e definir uma nova senha sem conhecer a senha atual. Ele também invalida qualquer link de recuperação pendente.

## PDFs armazenados no servidor

Os PDFs são gravados em:

`instance/pdfs/`

O nome físico usa um token aleatório e não o número sequencial do documento. Isso permite manter o mesmo link público mesmo quando um documento é editado e seu nome/prefixo muda.

O acesso externo é feito pela rota:

`/documentos/<token>/pdf`

A pasta `instance/pdfs/` não precisa ser exposta diretamente pelo servidor web. O Flask entrega o arquivo pela rota pública. O token é longo e aleatório, evitando URLs sequenciais previsíveis.

Ao editar um documento, o arquivo do mesmo token é substituído. Assim, links de WhatsApp enviados anteriormente continuam apontando para o documento atualizado.

## WhatsApp

O botão **WhatsApp** usa o telefone cadastrado no tomador e abre:

`https://wa.me/<telefone>?text=<mensagem>`

Para telefones brasileiros salvos com DDD e número, o sistema acrescenta o código do país `55`.

O link do PDF só pode ser acessado por outra pessoa quando o Fluxar Emissões estiver publicado em um endereço público, por exemplo no PythonAnywhere. Em execução local (`127.0.0.1` ou `localhost`), o link existe, mas não é acessível fora do computador.

## Nome e prefixo do documento

Em **Configurações > Documento**:

- **Nome do documento** define o título mostrado no PDF, por exemplo `NOTA DE DÉBITO`, `RECIBO` ou `AVISO DE COBRANÇA`.
- **Prefixo da numeração** é concatenado com a sequência de cinco dígitos. `ND` gera `ND00001`. Prefixo vazio gera `00001`.

Documentos já emitidos preservam o nome e o prefixo que possuíam. Se um documento antigo for editado e salvo, ele passa a usar o nome e o prefixo configurados atualmente, mantendo o mesmo número sequencial interno.

## ViaCEP

A consulta é executada quando o CEP possui oito dígitos, ao sair do campo ou ao clicar em **Buscar**. O sistema preenche automaticamente logradouro, bairro, cidade e UF. Número e complemento permanecem para preenchimento manual.

## Estrutura

- `app.py`: aplicação Flask, rotas, validações, armazenamento de PDFs e migrações simples do SQLite.
- `models.py`: modelos SQLite/SQLAlchemy.
- `services/pdf_service.py`: geração do PDF.
- `templates/`: telas HTML/Jinja.
- `static/js/viacep.js`: integração com o ViaCEP.
- `instance/fluxar_nd.db`: banco SQLite criado automaticamente na primeira execução.
- `instance/uploads/`: logotipo atual do emitente.
- `instance/pdfs/`: PDFs persistidos no servidor.
- `instance/.secret_key`: chave local usada para proteger as sessões quando `FLUXAR_SECRET_KEY` não estiver configurada.
- `reset_senha.py`: redefinição administrativa de emergência do login e senha.

## Banco existente

Ao iniciar esta versão sobre um banco criado por uma versão anterior, o Fluxar Emissões mantém os dados existentes, cria a tabela de usuários automaticamente e adiciona qualquer estrutura ainda necessária. Não é preciso apagar o arquivo `instance/fluxar_nd.db`.

## PythonAnywhere

A pasta `instance/` fica dentro do diretório do projeto e permanece no servidor. Não apague nem sobrescreva `instance/fluxar_nd.db`, `instance/uploads/`, `instance/pdfs/` ou `instance/.secret_key` durante atualizações da aplicação.

## Empacotamento

O projeto mantém as dependências de desenvolvimento em `requirements-dev.txt` para permitir o uso do PyInstaller em uma etapa posterior.
