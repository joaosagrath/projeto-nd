from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from email.message import EmailMessage
import hashlib
from io import BytesIO
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import smtplib
import ssl
import sys
import threading
import webbrowser
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request as UrlRequest, urlopen

from flask import (
    Flask,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)
from sqlalchemy import func, inspect, or_, text

from models import Empresa, NotaDebito, NotaDebitoItem, Tomador, Usuario, db
from services.pdf_service import gerar_pdf_nota
from werkzeug.security import check_password_hash, generate_password_hash
from dotenv import load_dotenv


RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

INSTANCE_DIR = BASE_DIR / "instance"
UPLOAD_DIR = INSTANCE_DIR / "uploads"
PDF_DIR = INSTANCE_DIR / "pdfs"
EXTENSOES_LOGO = {".png", ".jpg", ".jpeg"}
TAMANHO_MAX_LOGO = 3 * 1024 * 1024

load_dotenv(BASE_DIR / ".env")


def criar_app():
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    app = Flask(
        __name__,
        template_folder=str(RESOURCE_DIR / "templates"),
        static_folder=str(RESOURCE_DIR / "static"),
    )
    app.config["MODO_EXECUTAVEL"] = bool(getattr(sys, "frozen", False))
    app.config["SECRET_KEY"] = obter_secret_key()
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{INSTANCE_DIR / 'fluxar_nd.db'}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=12)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    db.init_app(app)

    registrar_filtros(app)
    registrar_pwa(app)
    registrar_autenticacao(app)
    registrar_rotas(app)

    with app.app_context():
        db.create_all()
        aplicar_migracoes_simples()
        garantir_empresa_padrao()
        garantir_usuario_padrao()
        preencher_snapshots_legados()

    return app


def registrar_filtros(app):
    @app.template_filter("brl")
    def filtro_brl(valor):
        return formatar_brl(valor)

    @app.template_filter("data_br")
    def filtro_data_br(valor):
        if not valor:
            return ""
        return valor.strftime("%d/%m/%Y")

    @app.template_filter("documento_br")
    def filtro_documento_br(valor):
        return formatar_documento(valor)

    @app.template_filter("telefone_br")
    def filtro_telefone_br(valor):
        return formatar_telefone(valor)

    @app.template_filter("cep_br")
    def filtro_cep_br(valor):
        return formatar_cep(valor)


def obter_secret_key():
    chave_ambiente = os.environ.get("FLUXAR_SECRET_KEY", "").strip()
    if chave_ambiente:
        return chave_ambiente

    caminho = INSTANCE_DIR / ".secret_key"
    if caminho.exists():
        chave = caminho.read_text(encoding="utf-8").strip()
        if chave:
            return chave

    chave = secrets.token_hex(32)
    caminho.write_text(chave, encoding="utf-8")
    try:
        os.chmod(caminho, 0o600)
    except OSError:
        pass
    return chave

def registrar_pwa(app):
    @app.route("/service-worker.js")
    def service_worker():
        resposta = send_from_directory(
            app.static_folder,
            "service-worker.js",
            mimetype="application/javascript",
        )
        resposta.headers["Cache-Control"] = "no-cache"
        return resposta

def registrar_autenticacao(app):
    @app.before_request
    def proteger_aplicacao():
        endpoints_publicos = {
            "login",
            "esqueci_senha",
            "redefinir_senha",
            "pdf_publico",
            "service_worker",
            "static",
        }

        if request.endpoint in endpoints_publicos:
            return None

        usuario_id = session.get("usuario_id")

        if not usuario_id:
            destino = request.full_path if request.query_string else request.path
            return redirect(url_for("login", next=destino))

        usuario = db.session.get(Usuario, usuario_id)

        if usuario is None:
            session.clear()
            return redirect(url_for("login"))

        g.usuario = usuario
        return None


def destino_login_seguro(valor):
    destino = str(valor or "").strip()
    if not destino.startswith("/") or destino.startswith("//"):
        return None
    return destino


def registrar_rotas(app):
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if session.get("usuario_id"):
            return redirect(url_for("index"))

        destino = request.args.get("next", "")

        if request.method == "POST":
            login_informado = request.form.get("login", "").strip()
            senha = request.form.get("senha", "")
            destino = request.form.get("next", "")

            usuario = Usuario.query.filter(
                func.lower(Usuario.login) == login_informado.lower()
            ).first()

            if usuario and check_password_hash(usuario.senha_hash, senha):
                session.clear()
                session["usuario_id"] = usuario.id
                session["usuario_login"] = usuario.login
                session.permanent = True

                destino_seguro = destino_login_seguro(destino)
                return redirect(destino_seguro or url_for("index"))

            flash("Login ou senha inválidos.", "danger")

        return render_template("login.html", destino=destino)

    @app.route("/logout")
    def logout():
        session.clear()
        flash("Sessão encerrada.", "success")
        return redirect(url_for("login"))

    @app.route("/encerrar-aplicacao", methods=["POST"])
    def encerrar_aplicacao():
        if not app.config.get("MODO_EXECUTAVEL"):
            abort(404)

        threading.Timer(0.8, lambda: os._exit(0)).start()
        return render_template("encerrando.html")

    @app.route("/esqueci-senha", methods=["GET", "POST"])
    def esqueci_senha():
        if session.get("usuario_id"):
            return redirect(url_for("index"))

        if request.method == "POST":
            identificador = request.form.get("identificador", "").strip()
            if not identificador:
                flash("Informe seu login ou e-mail de recuperação.", "danger")
                return render_template(
                    "esqueci_senha.html",
                    servico_email_ativo=servico_email_configurado(),
                )

            if not servico_email_configurado():
                flash(
                    "A recuperação por e-mail ainda não está configurada neste servidor. "
                    "Use o reset administrativo pelo arquivo reset_senha.py.",
                    "warning",
                )
                return render_template(
                    "esqueci_senha.html",
                    servico_email_ativo=False,
                )

            usuario = localizar_usuario_recuperacao(identificador)
            if usuario and usuario.email_recuperacao:
                token = gerar_token_recuperacao(usuario)
                db.session.commit()
                link = url_for("redefinir_senha", token=token, _external=True)

                try:
                    enviar_email_recuperacao(usuario, link)
                except (OSError, smtplib.SMTPException) as exc:
                    usuario.reset_token_hash = None
                    usuario.reset_token_expira_em = None
                    db.session.commit()
                    app.logger.exception("Falha ao enviar e-mail de recuperação: %s", exc)
                    flash(
                        "Não foi possível enviar o e-mail de recuperação agora. "
                        "Tente novamente mais tarde ou use o reset administrativo.",
                        "danger",
                    )
                    return render_template(
                        "esqueci_senha.html",
                        servico_email_ativo=True,
                    )

            flash(
                "Se a conta informada possuir um e-mail de recuperação cadastrado, "
                "você receberá um link para redefinir a senha.",
                "success",
            )
            return redirect(url_for("login"))

        return render_template(
            "esqueci_senha.html",
            servico_email_ativo=servico_email_configurado(),
        )

    @app.route("/redefinir-senha/<token>", methods=["GET", "POST"])
    def redefinir_senha(token):
        usuario = localizar_usuario_por_token(token)
        if usuario is None:
            flash("Este link de recuperação é inválido ou expirou.", "danger")
            return redirect(url_for("esqueci_senha"))

        if request.method == "POST":
            nova_senha = request.form.get("nova_senha", "")
            confirmar_senha = request.form.get("confirmar_senha", "")

            if len(nova_senha) < 8:
                flash("A nova senha deve ter pelo menos 8 caracteres.", "danger")
            elif nova_senha != confirmar_senha:
                flash("A confirmação da nova senha não confere.", "danger")
            else:
                usuario.senha_hash = generate_password_hash(nova_senha)
                usuario.reset_token_hash = None
                usuario.reset_token_expira_em = None
                db.session.commit()
                session.clear()
                flash("Senha redefinida com sucesso. Entre usando a nova senha.", "success")
                return redirect(url_for("login"))

        return render_template("redefinir_senha.html", token=token)

    @app.route("/")
    def index():
        notas = NotaDebito.query.order_by(NotaDebito.numero_sequencial.desc()).all()
        empresa = Empresa.query.first()
        return render_template("index.html", notas=notas, empresa=empresa)

    @app.route("/configuracoes", methods=["GET", "POST"])
    def configuracoes():
        empresa = Empresa.query.first()
        usuario = g.usuario

        if request.method == "POST":
            acao = request.form.get("acao", "empresa")

            if acao == "credenciais":
                try:
                    atualizar_credenciais_usuario(usuario, request.form)
                    db.session.commit()
                    session["usuario_login"] = usuario.login
                    flash("Dados de acesso atualizados com sucesso.", "success")
                    return redirect(url_for("configuracoes"))
                except ValueError as exc:
                    db.session.rollback()
                    flash(str(exc), "danger")
            else:
                try:
                    empresa.razao_social = request.form.get("razao_social", "").strip() or "Fluxar Emissões"
                    empresa.nome_fantasia = request.form.get("nome_fantasia", "").strip() or None
                    empresa.cnpj = normalizar_documento(request.form.get("cnpj")) or None
                    empresa.logradouro = request.form.get("logradouro", "").strip() or None
                    empresa.numero = request.form.get("numero", "").strip() or None
                    empresa.complemento = request.form.get("complemento", "").strip() or None
                    empresa.bairro = request.form.get("bairro", "").strip() or None
                    empresa.cidade = request.form.get("cidade", "").strip() or None
                    empresa.uf = normalizar_uf(request.form.get("uf")) or None
                    empresa.cep = normalizar_cep(request.form.get("cep")) or None
                    empresa.telefone = normalizar_telefone(request.form.get("telefone")) or None
                    empresa.email = request.form.get("email", "").strip() or None
                    empresa.documento_nome = validar_nome_documento(
                        request.form.get("documento_nome")
                    )
                    empresa.documento_prefixo = validar_prefixo_documento(
                        request.form.get("documento_prefixo")
                    )

                    empresa.endereco = empresa.endereco_formatado or None

                    if request.form.get("remover_logo") == "1":
                        remover_logo_empresa(empresa)

                    arquivo_logo = request.files.get("logo")
                    if arquivo_logo and arquivo_logo.filename:
                        salvar_logo_empresa(empresa, arquivo_logo)

                    db.session.commit()
                    flash("Dados da empresa atualizados.", "success")
                    return redirect(url_for("configuracoes"))
                except ValueError as exc:
                    db.session.rollback()
                    flash(str(exc), "danger")

        return render_template(
            "configuracoes.html",
            empresa=empresa,
            usuario=usuario,
            servico_email_ativo=servico_email_configurado(),
        )

    @app.route("/configuracoes/logo")
    def logo_empresa():
        empresa = Empresa.query.first()
        if not empresa or not empresa.logo_arquivo:
            abort(404)

        caminho = UPLOAD_DIR / empresa.logo_arquivo
        if not caminho.exists():
            abort(404)

        return send_from_directory(UPLOAD_DIR, empresa.logo_arquivo)

    @app.route("/tomadores")
    def listar_tomadores():
        tomadores = Tomador.query.order_by(Tomador.nome.asc()).all()
        return render_template("tomadores.html", tomadores=tomadores)

    @app.route("/tomadores/novo", methods=["GET", "POST"])
    def novo_tomador():
        tomador = Tomador()
        destino = request.args.get("next", "")
        nota_id = request.args.get("nota_id", "")

        if request.method == "POST":
            destino = request.form.get("next", "")
            nota_id = request.form.get("nota_id", "")
            try:
                preencher_tomador(tomador, request.form)
                validar_documento_tomador_unico(tomador)
                db.session.add(tomador)
                db.session.commit()
                flash("Tomador cadastrado com sucesso.", "success")
                if destino == "nova_nota":
                    return redirect(url_for("nova_nota", tomador_id=tomador.id))
                if destino == "editar_nota" and str(nota_id).isdigit():
                    return redirect(
                        url_for(
                            "editar_nota",
                            nota_id=int(nota_id),
                            tomador_id=tomador.id,
                        )
                    )
                return redirect(url_for("listar_tomadores"))
            except ValueError as exc:
                db.session.rollback()
                flash(str(exc), "danger")

        return render_template(
            "tomador_form.html",
            tomador=tomador,
            titulo="Novo tomador",
            destino=destino,
            nota_id=nota_id,
        )

    @app.route("/tomadores/<int:tomador_id>/editar", methods=["GET", "POST"])
    def editar_tomador(tomador_id):
        tomador = Tomador.query.get_or_404(tomador_id)

        if request.method == "POST":
            try:
                preencher_tomador(tomador, request.form)
                validar_documento_tomador_unico(tomador)
                db.session.commit()
                flash("Tomador atualizado com sucesso.", "success")
                return redirect(url_for("listar_tomadores"))
            except ValueError as exc:
                db.session.rollback()
                flash(str(exc), "danger")

        return render_template(
            "tomador_form.html",
            tomador=tomador,
            titulo="Editar tomador",
            destino="",
            nota_id="",
        )

    @app.route("/tomadores/<int:tomador_id>/excluir", methods=["POST"])
    def excluir_tomador(tomador_id):
        tomador = Tomador.query.get_or_404(tomador_id)

        if tomador.notas:
            flash("Este tomador possui documentos e não pode ser excluído.", "warning")
            return redirect(url_for("listar_tomadores"))

        db.session.delete(tomador)
        db.session.commit()
        flash("Tomador excluído.", "success")
        return redirect(url_for("listar_tomadores"))

    @app.route("/api/cep/<cep>")
    def api_buscar_cep(cep):
        digitos = re.sub(r"\D", "", str(cep or ""))
        if len(digitos) != 8:
            return jsonify({"erro": True, "mensagem": "Informe um CEP válido com 8 dígitos."}), 400

        url = f"https://viacep.com.br/ws/{digitos}/json/"
        requisicao = UrlRequest(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "Fluxar-Emissoes/1.0",
            },
        )

        try:
            with urlopen(requisicao, timeout=6) as resposta:
                dados = json.loads(resposta.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            return jsonify(
                {
                    "erro": True,
                    "mensagem": "Não foi possível consultar o ViaCEP. Preencha o endereço manualmente.",
                }
            ), 503

        if dados.get("erro"):
            return jsonify({"erro": True, "mensagem": "CEP não encontrado."}), 404

        return jsonify(
            {
                "erro": False,
                "cep": dados.get("cep", ""),
                "logradouro": dados.get("logradouro", ""),
                "bairro": dados.get("bairro", ""),
                "localidade": dados.get("localidade", ""),
                "uf": dados.get("uf", ""),
            }
        )

    @app.route("/api/tomadores")
    def api_buscar_tomadores():
        termo = request.args.get("q", "").strip()
        consulta = Tomador.query

        if termo:
            filtros = [Tomador.nome.ilike(f"%{termo}%")]
            documento = re.sub(r"\D", "", termo)
            if documento:
                filtros.append(Tomador.documento.ilike(f"%{documento}%"))
            consulta = consulta.filter(or_(*filtros))

        tomadores = consulta.order_by(Tomador.nome.asc()).limit(50).all()
        return jsonify(montar_tomadores_json(tomadores))

    @app.route("/notas/nova", methods=["GET", "POST"])
    def nova_nota():
        if request.method == "POST":
            try:
                nota = salvar_nota(request.form)
                flash(f"{nota.numero_formatado} gerada com sucesso.", "success")
                return redirect(url_for("visualizar_nota", nota_id=nota.id))
            except ValueError as exc:
                db.session.rollback()
                flash(str(exc), "danger")
            except Exception:
                db.session.rollback()
                flash("Não foi possível salvar o documento.", "danger")

        contexto = montar_contexto_form_nota()
        return render_template("nd_form.html", **contexto)

    @app.route("/notas/<int:nota_id>/editar", methods=["GET", "POST"])
    def editar_nota(nota_id):
        nota = NotaDebito.query.get_or_404(nota_id)

        if request.method == "POST":
            try:
                atualizar_nota(nota, request.form)
                flash(f"{nota.numero_formatado} atualizada com sucesso.", "success")
                return redirect(url_for("visualizar_nota", nota_id=nota.id))
            except ValueError as exc:
                db.session.rollback()
                flash(str(exc), "danger")
            except Exception:
                db.session.rollback()
                flash("Não foi possível atualizar o documento.", "danger")

        contexto = montar_contexto_form_nota(nota)
        return render_template("nd_form.html", **contexto)

    @app.route("/notas/<int:nota_id>")
    def visualizar_nota(nota_id):
        nota = NotaDebito.query.get_or_404(nota_id)
        empresa = Empresa.query.first()
        tem_logo = nota_tem_logo(nota, empresa)
        return render_template(
            "nd_visualizar.html",
            nota=nota,
            empresa=empresa,
            tem_logo=tem_logo,
        )

    @app.route("/notas/<int:nota_id>/logo")
    def logo_nota(nota_id):
        nota = NotaDebito.query.get_or_404(nota_id)
        empresa = Empresa.query.first()
        logo_bytes, mimetype = obter_logo_nota(nota, empresa)

        if not logo_bytes:
            abort(404)

        return send_file(
            BytesIO(logo_bytes),
            mimetype=mimetype or "image/png",
            max_age=0,
        )

    @app.route("/notas/<int:nota_id>/pdf")
    def baixar_pdf(nota_id):
        nota = NotaDebito.query.get_or_404(nota_id)
        caminho = obter_ou_gerar_pdf_servidor(nota)
        resposta = send_file(
            caminho,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"{sanitizar_nome_arquivo(nota.numero_formatado)}.pdf",
            max_age=0,
        )
        resposta.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return resposta

    @app.route("/documentos/<token>/pdf")
    def pdf_publico(token):
        nota = NotaDebito.query.filter_by(pdf_token=token).first_or_404()
        caminho = obter_ou_gerar_pdf_servidor(nota)
        resposta = send_file(
            caminho,
            mimetype="application/pdf",
            as_attachment=False,
            download_name=f"{sanitizar_nome_arquivo(nota.numero_formatado)}.pdf",
            max_age=0,
        )
        resposta.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return resposta

    @app.route("/notas/<int:nota_id>/whatsapp")
    def enviar_whatsapp(nota_id):
        nota = NotaDebito.query.get_or_404(nota_id)
        telefone = preparar_telefone_whatsapp(nota.tomador.telefone if nota.tomador else None)
        if not telefone:
            flash("O tomador não possui um telefone válido para WhatsApp.", "warning")
            return redirect(url_for("visualizar_nota", nota_id=nota.id))

        obter_ou_gerar_pdf_servidor(nota)
        link_pdf = url_for("pdf_publico", token=nota.pdf_token, _external=True)
        mensagem = (
            f"Olá, {nota.tomador_nome_exibicao}. "
            f"Segue o link do documento {nota.numero_formatado}: {link_pdf}"
        )
        return redirect(f"https://wa.me/{telefone}?text={quote(mensagem, safe='')}")


def aplicar_migracoes_simples():
    migracoes = {
        "empresa": {
            "logradouro": "VARCHAR(150)",
            "numero": "VARCHAR(30)",
            "complemento": "VARCHAR(100)",
            "bairro": "VARCHAR(100)",
            "cidade": "VARCHAR(100)",
            "uf": "VARCHAR(2)",
            "cep": "VARCHAR(12)",
            "logo_arquivo": "VARCHAR(255)",
            "documento_nome": "VARCHAR(120)",
            "documento_prefixo": "VARCHAR(20)",
        },
        "tomadores": {
            "logradouro": "VARCHAR(150)",
            "numero": "VARCHAR(30)",
            "complemento": "VARCHAR(100)",
            "bairro": "VARCHAR(100)",
            "cidade": "VARCHAR(100)",
            "uf": "VARCHAR(2)",
            "cep": "VARCHAR(12)",
            "telefone": "VARCHAR(30)",
            "email": "VARCHAR(150)",
        },
        "usuarios": {
            "email_recuperacao": "VARCHAR(150)",
            "reset_token_hash": "VARCHAR(64)",
            "reset_token_expira_em": "DATETIME",
        },
        "notas_debito": {
            "tomador_nome": "VARCHAR(180)",
            "tomador_documento": "VARCHAR(30)",
            "tomador_endereco": "VARCHAR(350)",
            "emitente_razao_social": "VARCHAR(150)",
            "emitente_nome_fantasia": "VARCHAR(150)",
            "emitente_cnpj": "VARCHAR(20)",
            "emitente_endereco": "VARCHAR(350)",
            "emitente_telefone": "VARCHAR(30)",
            "emitente_email": "VARCHAR(150)",
            "emitente_logo": "BLOB",
            "emitente_logo_mimetype": "VARCHAR(100)",
            "documento_nome": "VARCHAR(120)",
            "documento_prefixo": "VARCHAR(20)",
            "pdf_token": "VARCHAR(64)",
        },
    }

    inspetor = inspect(db.engine)
    tabelas_existentes = set(inspetor.get_table_names())

    for tabela, colunas in migracoes.items():
        if tabela not in tabelas_existentes:
            continue

        existentes = {coluna["name"] for coluna in inspetor.get_columns(tabela)}
        for nome_coluna, tipo_sql in colunas.items():
            if nome_coluna in existentes:
                continue
            db.session.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {nome_coluna} {tipo_sql}"))

    db.session.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_notas_debito_pdf_token "
            "ON notas_debito (pdf_token)"
        )
    )
    db.session.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_usuarios_reset_token_hash "
            "ON usuarios (reset_token_hash)"
        )
    )
    db.session.commit()


def garantir_empresa_padrao():
    empresa = Empresa.query.first()
    if empresa is None:
        db.session.add(
            Empresa(
                razao_social="Fluxar Emissões",
                documento_nome="NOTA DE DÉBITO",
                documento_prefixo="ND",
            )
        )
        db.session.commit()
        return

    alterado = False
    if not empresa.documento_nome:
        empresa.documento_nome = "NOTA DE DÉBITO"
        alterado = True
    if empresa.documento_prefixo is None:
        empresa.documento_prefixo = "ND"
        alterado = True

    if alterado:
        db.session.commit()


def garantir_usuario_padrao():
    if Usuario.query.first() is not None:
        return

    usuario = Usuario(
        login="admin",
        senha_hash=generate_password_hash("admin"),
    )
    db.session.add(usuario)
    db.session.commit()


def atualizar_credenciais_usuario(usuario, form):
    login_novo = form.get("usuario_login", "").strip()
    email_recuperacao = validar_email_recuperacao(form.get("email_recuperacao"))
    senha_atual = form.get("senha_atual", "")
    nova_senha = form.get("nova_senha", "")
    confirmar_senha = form.get("confirmar_senha", "")

    if not login_novo:
        raise ValueError("Informe o login de acesso.")
    if len(login_novo) < 3 or len(login_novo) > 80:
        raise ValueError("O login deve ter entre 3 e 80 caracteres.")
    if any(caractere.isspace() for caractere in login_novo):
        raise ValueError("O login não pode conter espaços.")
    if not check_password_hash(usuario.senha_hash, senha_atual):
        raise ValueError("A senha atual está incorreta.")

    usuario_existente = Usuario.query.filter(
        func.lower(Usuario.login) == login_novo.lower(),
        Usuario.id != usuario.id,
    ).first()
    if usuario_existente:
        raise ValueError("Este login já está em uso.")

    if nova_senha:
        if len(nova_senha) < 8:
            raise ValueError("A nova senha deve ter pelo menos 8 caracteres.")
        if nova_senha != confirmar_senha:
            raise ValueError("A confirmação da nova senha não confere.")
        usuario.senha_hash = generate_password_hash(nova_senha)
    elif confirmar_senha:
        raise ValueError("Informe a nova senha antes de confirmá-la.")

    usuario.login = login_novo
    usuario.email_recuperacao = email_recuperacao
    if nova_senha:
        usuario.reset_token_hash = None
        usuario.reset_token_expira_em = None


def validar_email_recuperacao(valor):
    email = str(valor or "").strip().lower()
    if not email:
        return None
    if len(email) > 150:
        raise ValueError("O e-mail de recuperação é muito longo.")
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise ValueError("Informe um e-mail de recuperação válido.")
    return email


def localizar_usuario_recuperacao(identificador):
    valor = str(identificador or "").strip().lower()
    if not valor:
        return None

    return Usuario.query.filter(
        or_(
            func.lower(Usuario.login) == valor,
            func.lower(Usuario.email_recuperacao) == valor,
        )
    ).first()


def gerar_token_recuperacao(usuario):
    token = secrets.token_urlsafe(32)
    usuario.reset_token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    usuario.reset_token_expira_em = datetime.utcnow() + timedelta(minutes=30)
    return token


def localizar_usuario_por_token(token):
    token = str(token or "").strip()
    if not token:
        return None

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    usuario = Usuario.query.filter_by(reset_token_hash=token_hash).first()
    if usuario is None or usuario.reset_token_expira_em is None:
        return None

    if usuario.reset_token_expira_em < datetime.utcnow():
        usuario.reset_token_hash = None
        usuario.reset_token_expira_em = None
        db.session.commit()
        return None

    return usuario


def ler_variavel_booleana(nome, padrao=False):
    valor = os.environ.get(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "yes", "sim", "on"}


def obter_configuracao_smtp():
    host = os.environ.get("FLUXAR_SMTP_HOST", "").strip()
    usuario = os.environ.get("FLUXAR_SMTP_USUARIO", "").strip()
    senha = os.environ.get("FLUXAR_SMTP_SENHA", "")
    remetente = os.environ.get("FLUXAR_SMTP_REMETENTE", "").strip() or usuario
    remetente_nome = os.environ.get("FLUXAR_SMTP_NOME", "Fluxar Emissões").strip() or "Fluxar Emissões"
    usar_ssl = ler_variavel_booleana("FLUXAR_SMTP_SSL", False)
    usar_tls = ler_variavel_booleana("FLUXAR_SMTP_TLS", not usar_ssl)

    porta_padrao = 465 if usar_ssl else 587
    try:
        porta = int(os.environ.get("FLUXAR_SMTP_PORT", porta_padrao))
    except (TypeError, ValueError):
        porta = porta_padrao

    return {
        "host": host,
        "porta": porta,
        "usuario": usuario,
        "senha": senha,
        "remetente": remetente,
        "remetente_nome": remetente_nome,
        "usar_ssl": usar_ssl,
        "usar_tls": usar_tls,
    }


def servico_email_configurado():
    config = obter_configuracao_smtp()
    return bool(config["host"] and config["remetente"])


def enviar_email_recuperacao(usuario, link):
    config = obter_configuracao_smtp()
    if not config["host"] or not config["remetente"]:
        raise OSError("Configuração SMTP ausente.")

    mensagem = EmailMessage()
    mensagem["Subject"] = "Redefinição de senha - Fluxar Emissões"
    mensagem["From"] = f'{config["remetente_nome"]} <{config["remetente"]}>'
    mensagem["To"] = usuario.email_recuperacao
    mensagem.set_content(
        "Recebemos uma solicitação para redefinir a senha do Fluxar Emissões.\n\n"
        f"Acesse o link abaixo para definir uma nova senha:\n{link}\n\n"
        "Este link é válido por 30 minutos e poderá ser utilizado apenas uma vez.\n\n"
        "Se você não solicitou a alteração, ignore esta mensagem."
    )

    contexto_ssl = ssl.create_default_context()
    if config["usar_ssl"]:
        with smtplib.SMTP_SSL(
            config["host"],
            config["porta"],
            timeout=20,
            context=contexto_ssl,
        ) as servidor:
            if config["usuario"]:
                servidor.login(config["usuario"], config["senha"])
            servidor.send_message(mensagem)
        return

    with smtplib.SMTP(config["host"], config["porta"], timeout=20) as servidor:
        servidor.ehlo()
        if config["usar_tls"]:
            servidor.starttls(context=contexto_ssl)
            servidor.ehlo()
        if config["usuario"]:
            servidor.login(config["usuario"], config["senha"])
        servidor.send_message(mensagem)


def preencher_snapshots_legados():
    empresa = Empresa.query.first()
    logo_bytes, logo_mimetype = obter_logo_atual(empresa)
    alterado = False

    for nota in NotaDebito.query.all():
        if nota.documento_nome is None:
            nota.documento_nome = empresa.documento_nome_exibicao if empresa else "NOTA DE DÉBITO"
            alterado = True
        if nota.documento_prefixo is None:
            nota.documento_prefixo = empresa.documento_prefixo_exibicao if empresa else "ND"
            alterado = True

        if nota.tomador_nome is None and nota.tomador:
            nota.tomador_nome = nota.tomador.nome
            nota.tomador_documento = nota.tomador.documento
            nota.tomador_endereco = nota.tomador.endereco_formatado or None
            alterado = True

        if nota.emitente_razao_social is None and empresa:
            nota.emitente_razao_social = empresa.razao_social
            nota.emitente_nome_fantasia = empresa.nome_fantasia
            nota.emitente_cnpj = empresa.cnpj
            nota.emitente_endereco = empresa.endereco_formatado or None
            nota.emitente_telefone = empresa.telefone
            nota.emitente_email = empresa.email
            nota.emitente_logo = logo_bytes
            nota.emitente_logo_mimetype = logo_mimetype
            alterado = True

        if not nota.pdf_token:
            nota.pdf_token = gerar_token_pdf()
            alterado = True

    if alterado:
        db.session.commit()


def preencher_tomador(tomador, form):
    nome = form.get("nome", "").strip()
    if not nome:
        raise ValueError("Informe o nome ou a razão social do tomador.")

    tomador.nome = nome
    tomador.documento = normalizar_documento(form.get("documento")) or None
    tomador.logradouro = form.get("logradouro", "").strip() or None
    tomador.numero = form.get("numero", "").strip() or None
    tomador.complemento = form.get("complemento", "").strip() or None
    tomador.bairro = form.get("bairro", "").strip() or None
    tomador.cidade = form.get("cidade", "").strip() or None
    tomador.uf = normalizar_uf(form.get("uf")) or None
    tomador.cep = normalizar_cep(form.get("cep")) or None
    tomador.telefone = normalizar_telefone(form.get("telefone")) or None
    tomador.email = form.get("email", "").strip() or None
    tomador.endereco = tomador.endereco_formatado or None


def validar_documento_tomador_unico(tomador):
    if not tomador.documento:
        return

    consulta = Tomador.query.filter(Tomador.documento == tomador.documento)
    if tomador.id:
        consulta = consulta.filter(Tomador.id != tomador.id)

    if consulta.first():
        raise ValueError("Já existe um tomador cadastrado com este CPF/CNPJ.")


def salvar_nota(form):
    nota = NotaDebito(
        numero_sequencial=obter_proximo_numero(),
        pdf_token=gerar_token_pdf(),
    )
    preencher_nota_com_formulario(
        nota,
        form,
        atualizar_emitente=True,
        atualizar_documento=True,
    )
    db.session.add(nota)
    db.session.flush()
    salvar_pdf_no_servidor(nota)
    db.session.commit()
    return nota


def atualizar_nota(nota, form):
    preencher_nota_com_formulario(
        nota,
        form,
        atualizar_emitente=False,
        atualizar_documento=True,
    )
    if not nota.pdf_token:
        nota.pdf_token = gerar_token_pdf()
    db.session.flush()
    salvar_pdf_no_servidor(nota)
    db.session.commit()
    return nota


def preencher_nota_com_formulario(
    nota,
    form,
    atualizar_emitente=False,
    atualizar_documento=False,
):
    tomador_id = form.get("tomador_id", "").strip()
    if not tomador_id.isdigit():
        raise ValueError("Selecione um tomador cadastrado.")

    tomador = db.session.get(Tomador, int(tomador_id))
    if tomador is None:
        raise ValueError("O tomador selecionado não foi encontrado.")

    emissao = converter_data(form.get("emissao"), "emissão")
    vencimento = converter_data(form.get("vencimento"), "vencimento")

    descricoes = form.getlist("item_descricao[]")
    quantidades = form.getlist("item_quantidade[]")
    valores_unitarios = form.getlist("item_valor_unitario[]")

    itens_validos = []
    valor_total = Decimal("0.00")

    for indice, descricao in enumerate(descricoes):
        descricao = descricao.strip()
        if not descricao:
            continue

        quantidade = converter_quantidade(
            quantidades[indice] if indice < len(quantidades) else "1"
        )
        valor_unitario = converter_decimal(
            valores_unitarios[indice] if indice < len(valores_unitarios) else "0",
            "valor unitário",
        )

        if valor_unitario < 0:
            raise ValueError("O valor unitário não pode ser negativo.")

        total_item = arredondar_moeda(Decimal(quantidade) * valor_unitario)
        valor_total += total_item
        itens_validos.append((descricao, quantidade, valor_unitario, total_item))

    if not itens_validos:
        raise ValueError("Adicione pelo menos um item ao documento.")

    outras_retencoes = converter_decimal(
        form.get("outras_retencoes", "0"),
        "outras retenções/descontos",
    )

    if outras_retencoes < 0:
        raise ValueError("Outras retenções/descontos não pode ser negativo.")

    valor_total = arredondar_moeda(valor_total)
    valor_pagar = arredondar_moeda(valor_total - outras_retencoes)

    if valor_pagar < 0:
        raise ValueError("As retenções/descontos não podem superar o valor total.")

    parcelas = converter_parcelas(form.get("parcelas"))
    forma_pagamento = form.get("forma_pagamento", "").strip().upper()
    if not forma_pagamento:
        raise ValueError("Informe a forma de pagamento.")

    referencia = form.get("referencia", "").strip() or emissao.strftime("%m/%Y")

    nota.emissao = emissao
    nota.referencia = referencia
    nota.vencimento = vencimento
    nota.condicao = f"{parcelas}x {forma_pagamento}"
    nota.observacoes = form.get("observacoes", "").strip() or None
    nota.outras_retencoes = outras_retencoes
    nota.valor_total = valor_total
    nota.valor_pagar = valor_pagar
    nota.tomador = tomador
    nota.tomador_nome = tomador.nome
    nota.tomador_documento = tomador.documento
    nota.tomador_endereco = tomador.endereco_formatado or None

    empresa = Empresa.query.first()
    if empresa is None:
        garantir_empresa_padrao()
        empresa = Empresa.query.first()

    if atualizar_documento or nota.documento_nome is None:
        nota.documento_nome = empresa.documento_nome_exibicao
        nota.documento_prefixo = empresa.documento_prefixo_exibicao

    if atualizar_emitente or nota.emitente_razao_social is None:
        logo_bytes, logo_mimetype = obter_logo_atual(empresa)
        nota.emitente_razao_social = empresa.razao_social
        nota.emitente_nome_fantasia = empresa.nome_fantasia
        nota.emitente_cnpj = empresa.cnpj
        nota.emitente_endereco = empresa.endereco_formatado or None
        nota.emitente_telefone = empresa.telefone
        nota.emitente_email = empresa.email
        nota.emitente_logo = logo_bytes
        nota.emitente_logo_mimetype = logo_mimetype

    nota.itens.clear()
    for ordem, item in enumerate(itens_validos, start=1):
        descricao, quantidade, valor_unitario, total_item = item
        nota.itens.append(
            NotaDebitoItem(
                ordem=ordem,
                descricao=descricao,
                quantidade=quantidade,
                valor_unitario=valor_unitario,
                valor_total=total_item,
            )
        )


def montar_contexto_form_nota(nota=None):
    hoje = date.today()
    modo_edicao = nota is not None
    empresa = Empresa.query.first()
    if empresa is None:
        garantir_empresa_padrao()
        empresa = Empresa.query.first()

    documento_nome_atual = empresa.documento_nome_exibicao
    documento_prefixo_atual = empresa.documento_prefixo_exibicao

    if request.method == "POST":
        form_data = {
            "emissao": request.form.get("emissao", hoje.isoformat()),
            "referencia": request.form.get("referencia", hoje.strftime("%m/%Y")),
            "vencimento": request.form.get("vencimento", hoje.isoformat()),
            "parcelas": request.form.get("parcelas", "1"),
            "forma_pagamento": request.form.get("forma_pagamento", "DINHEIRO"),
            "observacoes": request.form.get("observacoes", ""),
            "outras_retencoes": request.form.get("outras_retencoes", "0,00"),
        }
        itens_form = obter_itens_formulario(request.form)
        tomador_id = request.form.get("tomador_id", "")
    elif modo_edicao:
        parcelas, forma_pagamento = separar_condicao(nota.condicao)
        form_data = {
            "emissao": nota.emissao.isoformat(),
            "referencia": nota.referencia or nota.emissao.strftime("%m/%Y"),
            "vencimento": nota.vencimento.isoformat(),
            "parcelas": str(parcelas),
            "forma_pagamento": forma_pagamento,
            "observacoes": nota.observacoes or "",
            "outras_retencoes": formatar_decimal_form(nota.outras_retencoes),
        }
        itens_form = [
            {
                "descricao": item.descricao,
                "quantidade": str(int(Decimal(item.quantidade or 0))),
                "valor_unitario": formatar_decimal_form(item.valor_unitario),
            }
            for item in nota.itens
        ]
        tomador_id = request.args.get("tomador_id", "") or str(nota.tomador_id)
    else:
        form_data = {
            "emissao": hoje.isoformat(),
            "referencia": hoje.strftime("%m/%Y"),
            "vencimento": hoje.isoformat(),
            "parcelas": "1",
            "forma_pagamento": "DINHEIRO",
            "observacoes": "",
            "outras_retencoes": "0,00",
        }
        itens_form = obter_itens_formulario(request.form)
        tomador_id = request.args.get("tomador_id", "")

    tomador_selecionado = None
    if str(tomador_id).isdigit():
        tomador_selecionado = db.session.get(Tomador, int(tomador_id))

    if modo_edicao:
        titulo_pagina = f"Editar {nota.numero_formatado}"
        numero_exibicao = nota.numero_formatado
        form_action = url_for("editar_nota", nota_id=nota.id)
        url_cadastrar_tomador = url_for(
            "novo_tomador",
            next="editar_nota",
            nota_id=nota.id,
        )
        texto_submit = "Salvar alterações"
    else:
        titulo_pagina = "Novo documento"
        numero_exibicao = formatar_numero_documento(
            obter_proximo_numero(),
            documento_prefixo_atual,
        )
        form_action = url_for("nova_nota")
        url_cadastrar_tomador = url_for("novo_tomador", next="nova_nota")
        texto_submit = "Gerar documento"

    numero_apos_salvar = (
        formatar_numero_documento(nota.numero_sequencial, documento_prefixo_atual)
        if modo_edicao
        else numero_exibicao
    )

    return {
        "nota": nota,
        "modo_edicao": modo_edicao,
        "titulo_pagina": titulo_pagina,
        "numero_exibicao": numero_exibicao,
        "form_action": form_action,
        "form_data": form_data,
        "itens_form": itens_form,
        "tem_tomadores": Tomador.query.count() > 0,
        "tomador_selecionado_json": montar_tomador_json(tomador_selecionado),
        "url_cadastrar_tomador": url_cadastrar_tomador,
        "texto_submit": texto_submit,
        "documento_nome_atual": documento_nome_atual,
        "documento_prefixo_atual": documento_prefixo_atual,
        "numero_apos_salvar": numero_apos_salvar,
    }


def obter_proximo_numero():
    ultimo = db.session.query(func.max(NotaDebito.numero_sequencial)).scalar()
    return (ultimo or 0) + 1


def obter_itens_formulario(form):
    descricoes = form.getlist("item_descricao[]")
    quantidades = form.getlist("item_quantidade[]")
    unitarios = form.getlist("item_valor_unitario[]")

    if not descricoes:
        return [
            {
                "descricao": "Arrendamento de Veículo conforme contrato(s):",
                "quantidade": "1",
                "valor_unitario": "0,00",
            }
        ]

    itens = []
    for indice, descricao in enumerate(descricoes):
        itens.append(
            {
                "descricao": descricao,
                "quantidade": quantidades[indice] if indice < len(quantidades) else "1",
                "valor_unitario": unitarios[indice] if indice < len(unitarios) else "0,00",
            }
        )
    return itens


def montar_tomadores_json(tomadores):
    return [montar_tomador_json(tomador) for tomador in tomadores]


def montar_tomador_json(tomador):
    if tomador is None:
        return None

    return {
        "id": tomador.id,
        "nome": tomador.nome,
        "documento": formatar_documento(tomador.documento),
        "endereco": formatar_endereco_para_exibicao(tomador.endereco_formatado),
        "telefone": formatar_telefone(tomador.telefone),
        "email": tomador.email or "",
    }


def separar_condicao(condicao):
    texto_condicao = str(condicao or "").strip()
    correspondencia = re.match(r"^(\d+)x\s+(.+)$", texto_condicao, flags=re.IGNORECASE)
    if correspondencia:
        return int(correspondencia.group(1)), correspondencia.group(2).strip().upper()
    return 1, texto_condicao.upper() or "DINHEIRO"


def formatar_decimal_form(valor):
    valor_decimal = Decimal(valor or 0)
    texto = f"{valor_decimal:,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def validar_nome_documento(valor):
    nome = str(valor or "").strip()
    if not nome:
        raise ValueError("Informe o nome do documento.")
    if len(nome) > 120:
        raise ValueError("O nome do documento deve ter no máximo 120 caracteres.")
    return nome


def validar_prefixo_documento(valor):
    prefixo = str(valor or "").strip()
    if len(prefixo) > 20:
        raise ValueError("O prefixo do documento deve ter no máximo 20 caracteres.")
    return prefixo


def formatar_numero_documento(numero_sequencial, prefixo):
    prefixo_texto = "" if prefixo is None else str(prefixo).strip()
    return f"{prefixo_texto}{int(numero_sequencial):05d}"


def sanitizar_nome_arquivo(valor):
    nome = re.sub(r'[<>:"/\\|?*]+', "_", str(valor or "documento").strip())
    nome = nome.rstrip(". ")
    return nome or "documento"


def salvar_logo_empresa(empresa, arquivo):
    extensao = Path(arquivo.filename).suffix.lower()
    if extensao not in EXTENSOES_LOGO:
        raise ValueError("O logotipo deve estar em PNG, JPG ou JPEG.")

    arquivo.stream.seek(0, 2)
    tamanho = arquivo.stream.tell()
    arquivo.stream.seek(0)

    if tamanho > TAMANHO_MAX_LOGO:
        raise ValueError("O logotipo deve ter no máximo 3 MB.")

    remover_logo_empresa(empresa)

    nome_arquivo = f"empresa_logo{extensao}"
    caminho = UPLOAD_DIR / nome_arquivo
    arquivo.save(caminho)
    empresa.logo_arquivo = nome_arquivo


def remover_logo_empresa(empresa):
    if not empresa.logo_arquivo:
        return

    caminho = UPLOAD_DIR / empresa.logo_arquivo
    if caminho.exists():
        caminho.unlink()
    empresa.logo_arquivo = None


def obter_logo_atual(empresa):
    if not empresa or not empresa.logo_arquivo:
        return None, None

    caminho = UPLOAD_DIR / empresa.logo_arquivo
    if not caminho.exists():
        return None, None

    mimetype = mimetypes.guess_type(caminho.name)[0] or "image/png"
    return caminho.read_bytes(), mimetype


def obter_logo_nota(nota, empresa):
    if nota.emitente_razao_social is not None:
        logo = bytes(nota.emitente_logo) if nota.emitente_logo else None
        return logo, nota.emitente_logo_mimetype

    return obter_logo_atual(empresa)


def nota_tem_logo(nota, empresa):
    logo_bytes, _ = obter_logo_nota(nota, empresa)
    return bool(logo_bytes)


def gerar_token_pdf():
    return secrets.token_urlsafe(32)


def caminho_pdf_servidor(nota):
    if not nota.pdf_token:
        nota.pdf_token = gerar_token_pdf()
        db.session.flush()
    return PDF_DIR / f"{nota.pdf_token}.pdf"


def salvar_pdf_no_servidor(nota):
    empresa = Empresa.query.first()
    logo_bytes, logo_mimetype = obter_logo_nota(nota, empresa)
    pdf = gerar_pdf_nota(
        nota,
        empresa,
        logo_bytes=logo_bytes,
        logo_mimetype=logo_mimetype,
    )

    caminho = caminho_pdf_servidor(nota)
    caminho_temporario = caminho.with_suffix(".tmp")
    caminho_temporario.write_bytes(pdf.getvalue())
    caminho_temporario.replace(caminho)
    return caminho


def obter_ou_gerar_pdf_servidor(nota):
    caminho = caminho_pdf_servidor(nota)
    if not caminho.exists():
        caminho = salvar_pdf_no_servidor(nota)
        db.session.commit()
    return caminho


def preparar_telefone_whatsapp(valor):
    digitos = normalizar_telefone(valor)
    if len(digitos) in (10, 11):
        digitos = f"55{digitos}"
    if len(digitos) not in (12, 13):
        return ""
    return digitos


def converter_data(valor, campo):
    try:
        return datetime.strptime(valor or "", "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"Informe uma data válida para {campo}.") from exc


def converter_quantidade(valor):
    texto = str(valor or "").strip().replace(" ", "")
    if not texto:
        raise ValueError("Informe uma quantidade válida.")

    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")

    try:
        quantidade = Decimal(texto)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Informe uma quantidade inteira válida.") from exc

    if quantidade != quantidade.to_integral_value():
        raise ValueError("A quantidade dos itens deve ser um número inteiro.")

    quantidade_inteira = int(quantidade)
    if quantidade_inteira <= 0:
        raise ValueError("A quantidade dos itens deve ser maior que zero.")

    return quantidade_inteira


def converter_decimal(valor, campo):
    texto = str(valor or "0").strip().replace("R$", "").replace(" ", "")

    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")

    try:
        return arredondar_moeda(Decimal(texto))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Informe um valor válido para {campo}.") from exc


def converter_parcelas(valor):
    try:
        parcelas = int(valor or 1)
    except (TypeError, ValueError) as exc:
        raise ValueError("Informe uma quantidade válida de parcelas.") from exc

    if parcelas < 1 or parcelas > 99:
        raise ValueError("A quantidade de parcelas deve estar entre 1 e 99.")
    return parcelas


def arredondar_moeda(valor):
    return Decimal(valor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def normalizar_documento(valor):
    texto = str(valor or "").strip()
    digitos = re.sub(r"\D", "", texto)
    if len(digitos) in (11, 14):
        return digitos
    return texto


def normalizar_telefone(valor):
    return re.sub(r"\D", "", str(valor or ""))


def normalizar_cep(valor):
    return re.sub(r"\D", "", str(valor or ""))[:8]


def normalizar_uf(valor):
    return re.sub(r"[^A-Za-z]", "", str(valor or "")).upper()[:2]


def formatar_documento(valor):
    texto = str(valor or "").strip()
    digitos = re.sub(r"\D", "", texto)

    if len(digitos) == 11:
        return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"
    if len(digitos) == 14:
        return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}"
    return texto


def formatar_telefone(valor):
    digitos = re.sub(r"\D", "", str(valor or ""))

    if len(digitos) == 11:
        return f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}"
    if len(digitos) == 10:
        return f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"
    return str(valor or "")


def formatar_cep(valor):
    digitos = re.sub(r"\D", "", str(valor or ""))
    if len(digitos) == 8:
        return f"{digitos[:2]}.{digitos[2:5]}-{digitos[5:]}"
    return str(valor or "")


def formatar_endereco_para_exibicao(valor):
    texto = str(valor or "")
    return re.sub(r"CEP\s+(\d{8})(?!\d)", lambda m: f"CEP {formatar_cep(m.group(1))}", texto)


def formatar_brl(valor):
    valor = Decimal(valor or 0)
    texto = f"{valor:,.2f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


app = criar_app()


def fechar_splash_pyinstaller():
    if not getattr(sys, "frozen", False):
        return

    try:
        import pyi_splash
    except ImportError:
        return

    try:
        pyi_splash.close()
    except Exception:
        pass


def executar_aplicacao_local():
    host = "127.0.0.1"
    port = 5000
    modo_executavel = bool(getattr(sys, "frozen", False))

    if modo_executavel:
        fechar_splash_pyinstaller()
        url = f"http://{host}:{port}"
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    app.run(
        host=host,
        port=port,
        debug=not modo_executavel,
        use_reloader=False,
    )


if __name__ == "__main__":
    executar_aplicacao_local()
