from decimal import Decimal
from io import BytesIO
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


class CanvasNumerado(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._estados_paginas = []

    def showPage(self):
        self._estados_paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total_paginas = len(self._estados_paginas)

        for estado in self._estados_paginas:
            self.__dict__.update(estado)
            self._desenhar_numero_pagina(total_paginas)
            super().showPage()

        super().save()

    def _desenhar_numero_pagina(self, total_paginas):
        largura, altura = A4
        self.saveState()
        self.setFont("Helvetica", 7)
        self.drawRightString(
            largura - 10 * mm,
            altura - 6 * mm,
            f"Página: {self._pageNumber} de {total_paginas}",
        )
        self.restoreState()


def gerar_pdf_nota(nota, empresa, logo_bytes=None, logo_mimetype=None):
    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title=f"{nota.documento_nome_exibicao} {nota.numero_formatado}",
        author="Fluxar Emissões",
    )

    estilos = criar_estilos()
    elementos = [
        criar_cabecalho(nota, empresa, estilos, logo_bytes, logo_mimetype),
        criar_bloco_tomador(nota, estilos),
        criar_tabela_itens(nota, estilos),
        criar_totais(nota, estilos),
        criar_observacoes(nota, estilos),
    ]

    documento.build(elementos, canvasmaker=CanvasNumerado)

    buffer.seek(0)
    return buffer


def criar_estilos():
    estilos_base = getSampleStyleSheet()

    return {
        "normal": ParagraphStyle(
            "NormalND",
            parent=estilos_base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=11,
            alignment=TA_LEFT,
        ),
        "empresa": ParagraphStyle(
            "EmpresaND",
            parent=estilos_base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=10.5,
            alignment=TA_LEFT,
        ),
        "centro": ParagraphStyle(
            "CentroND",
            parent=estilos_base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=11,
            alignment=TA_CENTER,
        ),
        "direita": ParagraphStyle(
            "DireitaND",
            parent=estilos_base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=11,
            alignment=TA_RIGHT,
        ),
        "titulo": ParagraphStyle(
            "TituloND",
            parent=estilos_base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            alignment=TA_CENTER,
            spaceAfter=3,
        ),
        "subtitulo": ParagraphStyle(
            "SubtituloND",
            parent=estilos_base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=13,
            alignment=TA_CENTER,
        ),
        "total_destaque_rotulo": ParagraphStyle(
            "TotalDestaqueRotuloND",
            parent=estilos_base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            alignment=TA_RIGHT,
        ),
        "total_destaque_valor": ParagraphStyle(
            "TotalDestaqueValorND",
            parent=estilos_base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=12,
            alignment=TA_RIGHT,
        ),
    }


def criar_cabecalho(nota, empresa, estilos, logo_bytes, logo_mimetype):
    emitente = obter_emitente(nota, empresa)
    dados_empresa = []

    if emitente["razao_social"]:
        dados_empresa.append(f"<b>{escape(emitente['razao_social'])}</b>")
    if emitente["nome_fantasia"] and emitente["nome_fantasia"] != emitente["razao_social"]:
        dados_empresa.append(escape(emitente["nome_fantasia"]))
    if emitente["endereco"]:
        dados_empresa.append(escape(formatar_endereco(emitente["endereco"])))
    if emitente["cnpj"]:
        dados_empresa.append(f"CNPJ: {escape(formatar_documento(emitente['cnpj']))}")
    if emitente["telefone"]:
        dados_empresa.append(f"Tel.: {escape(formatar_telefone(emitente['telefone']))}")
    if emitente["email"]:
        dados_empresa.append(escape(emitente["email"]))

    empresa_html = "<br/>".join(dados_empresa) or "Fluxar Emissões"
    quadro_dados = Paragraph(empresa_html, estilos["empresa"])

    if logo_bytes:
        quadro_logo = criar_logo(logo_bytes, logo_mimetype)
        bloco_emitente = Table(
            [[quadro_logo, quadro_dados]],
            colWidths=[31 * mm, 67 * mm],
        )
        alinhamento_logo = [("ALIGN", (0, 0), (0, 0), "CENTER")]
    else:
        bloco_emitente = Table([[quadro_dados]], colWidths=[98 * mm])
        alinhamento_logo = []

    bloco_emitente.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                *alinhamento_logo,
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    referencia = escape(str(nota.referencia or "-"))
    condicao = escape(str(nota.condicao or "-"))
    vencimento = nota.vencimento.strftime("%d/%m/%Y") if nota.vencimento else ""

    quadro_direito = [
        Paragraph(escape(nota.documento_nome_exibicao), estilos["titulo"]),
        Paragraph(escape(nota.numero_formatado), estilos["subtitulo"]),
        Spacer(1, 3 * mm),
        Paragraph(f"<b>Emissão:</b> {nota.emissao.strftime('%d/%m/%Y')}", estilos["centro"]),
        Paragraph(f"<b>Referência:</b> {referencia}", estilos["centro"]),
    ]

    if nota.vencimento:
        quadro_direito.append(
            Paragraph(f"<b>Vencimento:</b> {vencimento}", estilos["centro"])
        )

    quadro_direito.append(
        Paragraph(f"<b>Condição:</b> {condicao}", estilos["centro"])
    )

    tabela = Table(
        [[bloco_emitente, quadro_direito]],
        colWidths=[102 * mm, 87 * mm],
        rowHeights=[46 * mm],
    )
    tabela.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.8, colors.black),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return tabela


def criar_logo(logo_bytes, logo_mimetype):
    del logo_mimetype

    if not logo_bytes:
        return Spacer(26 * mm, 20 * mm)

    try:
        imagem = Image(BytesIO(logo_bytes))
        imagem._restrictSize(26 * mm, 26 * mm)
        return imagem
    except Exception:
        return Spacer(26 * mm, 20 * mm)


def criar_bloco_tomador(nota, estilos):
    documento = formatar_documento(nota.tomador_documento_exibicao) or "-"
    endereco = formatar_endereco(nota.tomador_endereco_exibicao) or "-"
    nome = nota.tomador_nome_exibicao or "-"

    conteudo = [
        Paragraph("<b>Tomador</b>", estilos["normal"]),
        Spacer(1, 2 * mm),
        Paragraph(escape(nome), estilos["normal"]),
        Spacer(1, 1.5 * mm),
        Paragraph(escape(endereco), estilos["normal"]),
        Spacer(1, 1.5 * mm),
        Paragraph(f"CNPJ/CPF&nbsp;&nbsp;{escape(documento)}", estilos["normal"]),
    ]

    tabela = Table([[conteudo]], colWidths=[189 * mm], rowHeights=[32 * mm])
    tabela.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return tabela


def criar_tabela_itens(nota, estilos):
    dados = [
        [
            Paragraph("<b>Item</b>", estilos["centro"]),
            Paragraph("<b>Descrição</b>", estilos["centro"]),
            Paragraph("<b>Quant.</b>", estilos["centro"]),
            Paragraph("<b>Unit.</b>", estilos["centro"]),
            Paragraph("<b>Total</b>", estilos["centro"]),
        ]
    ]

    for indice, item in enumerate(nota.itens, start=1):
        descricao = escape(str(item.descricao or "")).replace("\n", "<br/>")
        dados.append(
            [
                Paragraph(str(indice), estilos["centro"]),
                Paragraph(descricao, estilos["normal"]),
                Paragraph(formatar_quantidade(item.quantidade), estilos["direita"]),
                Paragraph(formatar_numero(item.valor_unitario), estilos["direita"]),
                Paragraph(formatar_numero(item.valor_total), estilos["direita"]),
            ]
        )

    tabela = Table(
        dados,
        colWidths=[13 * mm, 101 * mm, 20 * mm, 27 * mm, 28 * mm],
        repeatRows=1,
    )
    tabela.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.8, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return tabela


def criar_totais(nota, estilos):
    dados = [
        [
            Paragraph("<b>Valor total:</b>", estilos["direita"]),
            Paragraph(f"<b>{formatar_brl(nota.valor_total)}</b>", estilos["direita"]),
        ],
        [
            Paragraph("<b>Outras retenções/descontos:</b>", estilos["direita"]),
            Paragraph(f"<b>{formatar_brl(nota.outras_retencoes)}</b>", estilos["direita"]),
        ],
        [
            Paragraph("Valor a pagar:", estilos["total_destaque_rotulo"]),
            Paragraph(formatar_brl(nota.valor_pagar), estilos["total_destaque_valor"]),
        ],
    ]

    tabela = Table(dados, colWidths=[151 * mm, 38 * mm])
    tabela.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
                ("LINEABOVE", (0, 2), (-1, 2), 1.0, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, 1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, 1), 2),
                ("TOPPADDING", (0, 2), (-1, 2), 3),
                ("BOTTOMPADDING", (0, 2), (-1, 2), 3),
            ]
        )
    )
    return KeepTogether([tabela])


def criar_observacoes(nota, estilos):
    texto = escape(str(nota.observacoes or "")).replace("\n", "<br/>")
    conteudo = [
        Paragraph("Observações:", estilos["normal"]),
        Spacer(1, 2 * mm),
        Paragraph(texto, estilos["normal"]),
    ]

    altura = estimar_altura_observacoes(nota)
    tabela = Table([[conteudo]], colWidths=[189 * mm], rowHeights=[altura])
    tabela.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return tabela


def estimar_altura_observacoes(nota):
    quantidade_itens = max(len(nota.itens), 1)
    linhas_extras_itens = sum(max((len(str(item.descricao or "")) - 1) // 85, 0) for item in nota.itens)
    reducao = max(quantidade_itens - 1, 0) * 7 * mm + linhas_extras_itens * 5 * mm
    altura = max(95 * mm - reducao, 35 * mm)

    texto = str(nota.observacoes or "")
    linhas_observacao = max(len(texto.splitlines()), (len(texto) // 110) + 1 if texto else 1)
    altura_texto = (18 + linhas_observacao * 5) * mm

    return max(altura, min(altura_texto, 95 * mm))


def obter_emitente(nota, empresa):
    if nota.emitente_razao_social is not None:
        return {
            "razao_social": nota.emitente_razao_social or "",
            "nome_fantasia": nota.emitente_nome_fantasia or "",
            "cnpj": nota.emitente_cnpj or "",
            "endereco": nota.emitente_endereco or "",
            "telefone": nota.emitente_telefone or "",
            "email": nota.emitente_email or "",
        }

    return {
        "razao_social": empresa.razao_social if empresa else "Fluxar Emissões",
        "nome_fantasia": empresa.nome_fantasia if empresa else "",
        "cnpj": empresa.cnpj if empresa else "",
        "endereco": empresa.endereco_formatado if empresa else "",
        "telefone": empresa.telefone if empresa else "",
        "email": empresa.email if empresa else "",
    }


def formatar_quantidade(valor):
    return str(int(Decimal(valor or 0)))


def formatar_numero(valor):
    valor = Decimal(valor or 0)
    texto = f"{valor:,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_brl(valor):
    return f"R$ {formatar_numero(valor)}"


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


def formatar_endereco(valor):
    texto = str(valor or "")
    return re.sub(r"CEP\s+(\d{8})(?!\d)", lambda m: f"CEP {formatar_cep(m.group(1))}", texto)
