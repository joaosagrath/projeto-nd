from getpass import getpass

from sqlalchemy import func
from werkzeug.security import generate_password_hash

from app import app
from models import Usuario, db


def ler_login_atual():
    usuarios = Usuario.query.order_by(Usuario.id.asc()).all()
    if not usuarios:
        raise RuntimeError("Nenhum usuário foi encontrado no banco de dados.")

    if len(usuarios) == 1:
        return usuarios[0]

    print("Usuários disponíveis:")
    for usuario in usuarios:
        print(f"  - {usuario.login}")

    while True:
        login = input("Login que deseja redefinir: ").strip()
        usuario = Usuario.query.filter(func.lower(Usuario.login) == login.lower()).first()
        if usuario:
            return usuario
        print("Usuário não encontrado. Tente novamente.")


def ler_novo_login(usuario):
    while True:
        novo_login = input(f"Novo login [{usuario.login}]: ").strip() or usuario.login
        if len(novo_login) < 3 or len(novo_login) > 80:
            print("O login deve ter entre 3 e 80 caracteres.")
            continue
        if any(caractere.isspace() for caractere in novo_login):
            print("O login não pode conter espaços.")
            continue

        existente = Usuario.query.filter(
            func.lower(Usuario.login) == novo_login.lower(),
            Usuario.id != usuario.id,
        ).first()
        if existente:
            print("Este login já está em uso.")
            continue
        return novo_login


def ler_nova_senha():
    while True:
        nova_senha = getpass("Nova senha: ")
        confirmar_senha = getpass("Confirmar nova senha: ")

        if len(nova_senha) < 8:
            print("A senha deve ter pelo menos 8 caracteres.")
            continue
        if nova_senha != confirmar_senha:
            print("A confirmação da senha não confere.")
            continue
        return nova_senha


def redefinir_acesso():
    with app.app_context():
        usuario = ler_login_atual()
        novo_login = ler_novo_login(usuario)
        nova_senha = ler_nova_senha()

        usuario.login = novo_login
        usuario.senha_hash = generate_password_hash(nova_senha)
        usuario.reset_token_hash = None
        usuario.reset_token_expira_em = None
        db.session.commit()

        print()
        print("Acesso redefinido com sucesso.")
        print(f"Login atual: {usuario.login}")


if __name__ == "__main__":
    try:
        redefinir_acesso()
    except (KeyboardInterrupt, EOFError):
        print("\nOperação cancelada.")
    except RuntimeError as exc:
        print(f"Erro: {exc}")
