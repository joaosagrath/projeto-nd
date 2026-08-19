from datetime import datetime
from decimal import Decimal

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Numeric


db = SQLAlchemy()


def _juntar_endereco(logradouro, numero, complemento, bairro, cidade, uf, cep, endereco_legado=None):
    if not any([logradouro, numero, complemento, bairro, cidade, uf, cep]):
        return endereco_legado or ""

    partes = []

    linha_logradouro = (logradouro or "").strip()
    if numero:
        linha_logradouro = f"{linha_logradouro}, {numero}" if linha_logradouro else str(numero)
    if complemento:
        linha_logradouro = f"{linha_logradouro}, {complemento}" if linha_logradouro else str(complemento)
    if linha_logradouro:
        partes.append(linha_logradouro)

    if bairro:
        partes.append(str(bairro).strip())

    localidade = (cidade or "").strip()
    if uf:
        localidade = f"{localidade} - {uf}" if localidade else str(uf).strip()
    if localidade:
        partes.append(localidade)

    if cep:
        partes.append(f"CEP {cep}")

    return " - ".join(parte for parte in partes if parte)


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(80), nullable=False, unique=True, index=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    email_recuperacao = db.Column(db.String(150), nullable=True)
    reset_token_hash = db.Column(db.String(64), nullable=True, index=True)
    reset_token_expira_em = db.Column(db.DateTime, nullable=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    atualizado_em = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class Empresa(db.Model):
    __tablename__ = "empresa"

    id = db.Column(db.Integer, primary_key=True)
    razao_social = db.Column(db.String(150), nullable=False, default="Fluxar Emissões")
    nome_fantasia = db.Column(db.String(150), nullable=True)
    cnpj = db.Column(db.String(20), nullable=True)
    endereco = db.Column(db.String(255), nullable=True)
    logradouro = db.Column(db.String(150), nullable=True)
    numero = db.Column(db.String(30), nullable=True)
    complemento = db.Column(db.String(100), nullable=True)
    bairro = db.Column(db.String(100), nullable=True)
    cidade = db.Column(db.String(100), nullable=True)
    uf = db.Column(db.String(2), nullable=True)
    cep = db.Column(db.String(12), nullable=True)
    telefone = db.Column(db.String(30), nullable=True)
    email = db.Column(db.String(150), nullable=True)
    logo_arquivo = db.Column(db.String(255), nullable=True)
    documento_nome = db.Column(db.String(120), nullable=False, default="NOTA DE DÉBITO")
    documento_prefixo = db.Column(db.String(20), nullable=False, default="ND")
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    atualizado_em = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    @property
    def endereco_formatado(self):
        return _juntar_endereco(
            self.logradouro,
            self.numero,
            self.complemento,
            self.bairro,
            self.cidade,
            self.uf,
            self.cep,
            self.endereco,
        )

    @property
    def documento_nome_exibicao(self):
        return (self.documento_nome or "NOTA DE DÉBITO").strip()

    @property
    def documento_prefixo_exibicao(self):
        if self.documento_prefixo is None:
            return "ND"
        return self.documento_prefixo.strip()


class Tomador(db.Model):
    __tablename__ = "tomadores"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(180), nullable=False)
    documento = db.Column(db.String(30), nullable=True, index=True)
    endereco = db.Column(db.String(255), nullable=True)
    logradouro = db.Column(db.String(150), nullable=True)
    numero = db.Column(db.String(30), nullable=True)
    complemento = db.Column(db.String(100), nullable=True)
    bairro = db.Column(db.String(100), nullable=True)
    cidade = db.Column(db.String(100), nullable=True)
    uf = db.Column(db.String(2), nullable=True)
    cep = db.Column(db.String(12), nullable=True)
    telefone = db.Column(db.String(30), nullable=True)
    email = db.Column(db.String(150), nullable=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    atualizado_em = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    notas = db.relationship("NotaDebito", back_populates="tomador")

    @property
    def endereco_formatado(self):
        return _juntar_endereco(
            self.logradouro,
            self.numero,
            self.complemento,
            self.bairro,
            self.cidade,
            self.uf,
            self.cep,
            self.endereco,
        )


class NotaDebito(db.Model):
    __tablename__ = "notas_debito"

    id = db.Column(db.Integer, primary_key=True)
    numero_sequencial = db.Column(db.Integer, nullable=False, unique=True, index=True)
    emissao = db.Column(db.Date, nullable=False)
    referencia = db.Column(db.String(30), nullable=True)
    vencimento = db.Column(db.Date, nullable=False)
    condicao = db.Column(db.String(100), nullable=True)
    observacoes = db.Column(db.Text, nullable=True)
    outras_retencoes = db.Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    valor_total = db.Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    valor_pagar = db.Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    tomador_id = db.Column(db.Integer, db.ForeignKey("tomadores.id"), nullable=False)

    documento_nome = db.Column(db.String(120), nullable=True)
    documento_prefixo = db.Column(db.String(20), nullable=True)
    pdf_token = db.Column(db.String(64), nullable=True, unique=True, index=True)

    tomador_nome = db.Column(db.String(180), nullable=True)
    tomador_documento = db.Column(db.String(30), nullable=True)
    tomador_endereco = db.Column(db.String(350), nullable=True)

    emitente_razao_social = db.Column(db.String(150), nullable=True)
    emitente_nome_fantasia = db.Column(db.String(150), nullable=True)
    emitente_cnpj = db.Column(db.String(20), nullable=True)
    emitente_endereco = db.Column(db.String(350), nullable=True)
    emitente_telefone = db.Column(db.String(30), nullable=True)
    emitente_email = db.Column(db.String(150), nullable=True)
    emitente_logo = db.Column(db.LargeBinary, nullable=True)
    emitente_logo_mimetype = db.Column(db.String(100), nullable=True)

    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    atualizado_em = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    tomador = db.relationship("Tomador", back_populates="notas")
    itens = db.relationship(
        "NotaDebitoItem",
        back_populates="nota",
        cascade="all, delete-orphan",
        order_by="NotaDebitoItem.ordem",
    )

    @property
    def documento_nome_exibicao(self):
        return (self.documento_nome or "NOTA DE DÉBITO").strip()

    @property
    def documento_prefixo_exibicao(self):
        if self.documento_prefixo is None:
            return "ND"
        return self.documento_prefixo.strip()

    @property
    def numero_formatado(self):
        return f"{self.documento_prefixo_exibicao}{self.numero_sequencial:05d}"

    @property
    def tomador_nome_exibicao(self):
        return self.tomador_nome or (self.tomador.nome if self.tomador else "")

    @property
    def tomador_documento_exibicao(self):
        return self.tomador_documento or (self.tomador.documento if self.tomador else "")

    @property
    def tomador_endereco_exibicao(self):
        if self.tomador_endereco:
            return self.tomador_endereco
        return self.tomador.endereco_formatado if self.tomador else ""


class NotaDebitoItem(db.Model):
    __tablename__ = "notas_debito_itens"

    id = db.Column(db.Integer, primary_key=True)
    nota_id = db.Column(db.Integer, db.ForeignKey("notas_debito.id"), nullable=False)
    ordem = db.Column(db.Integer, nullable=False, default=1)
    descricao = db.Column(db.String(500), nullable=False)
    quantidade = db.Column(Numeric(12, 2), nullable=False, default=Decimal("1.00"))
    valor_unitario = db.Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    valor_total = db.Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))

    nota = db.relationship("NotaDebito", back_populates="itens")
