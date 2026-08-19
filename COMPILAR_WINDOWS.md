# Fluxar Emissões — Compilar para Windows

O Fluxar Emissões pode ser gerado como um executável portátil de arquivo único usando PyInstaller.

## Arquivos necessários na raiz

Antes da compilação, confirme que existem:

```text
projeto-nd/
├── app.ico
├── Splash.png
├── build_windows.bat
├── build_windows.ps1
├── app.py
├── templates/
└── static/
```

- `app.ico` será usado como ícone do `.exe`.
- `Splash.png` será exibida durante a inicialização do executável.

## Compilar

Com a `.venv` do projeto criada, dê duplo clique em:

```text
build_windows.bat
```

Ou execute pelo PowerShell:

```powershell
.\build_windows.ps1 -Clean
```

O script instala o PyInstaller na `.venv` automaticamente se ele ainda não estiver instalado.

## Resultado

Os executáveis serão criados em:

```text
dist/
├── Fluxar Emissoes.exe
└── Fluxar Emissoes Console.exe
```

A versão **Console** é destinada a diagnóstico. Se a versão principal não abrir corretamente, execute a versão Console para visualizar a mensagem de erro.

## Dados persistentes

Na primeira execução, o sistema cria automaticamente ao lado do executável:

```text
instance/
├── fluxar_nd.db
├── .secret_key
├── uploads/
└── pdfs/
```

A pasta `instance` nunca é colocada dentro do executável. Para fazer backup ou migrar a instalação para outro computador, preserve essa pasta.

Se existir um `.env` ao lado do executável, ele também será carregado automaticamente.

## Encerrar a aplicação

Na versão sem console, use o botão **Encerrar aplicativo** exibido no menu superior. Fechar apenas a aba do navegador não encerra o servidor Flask em execução.
