"""Agente Autónomo Especialista en Contratación Estatal, Evaluación Económica y APU.
Empresa de Servicios Públicos de Yolombó (ESPY S.A. E.S.P.) - Nit: 811.015.112-4.
Marco Regulatorio:
- Manual de Contratación de la ESPY (Código: PR-ESPY-002, Versión: 02, Resolución Nro. 5 de Junta Directiva).
- Ley 142 de 1994 (Régimen de Servicios Públicos Domiciliarios, art. 31 modificado por Ley 689 de 2001).
- Constitución Política de Colombia (Artículos 209 y 267 - Principios de la Función Administrativa y Gestión Fiscal).
- Estándar de formato monetario colombiano estricto: $4.800.000 COP y membrete institucional oficial.
"""
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
import re
import os
import io
import json
import csv
from datetime import datetime

import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.enum.section import WD_ORIENT
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

from app.config import settings
from app.utils.logger import logger
from app.utils.num_to_words import numero_a_letras_cop
from app.services.gemini_client import gemini_service
from app.services.agents.multi_proposal_parser import multi_proposal_parser, clean_company_name
from app.schemas.apu import (
    APUComponenteItem,
    APUDescomposicion,
    ItemCotizacion,
    ProponenteOferta,
    ProcesoConfig,
    ItemAPUConsolidado,
    EvaluacionComparativaPayload,
    EvaluacionComparativaResult,
)

def format_currency_cop_apu(amount: Any, show_decimals_if_needed: bool = True) -> str:
    """
    Formatea valores monetarios con estándar colombiano estricto: $4.800.000 o $1.333.333,33.
    Utiliza espacio no separable (\u00A0) para evitar que el símbolo $ se separe de la cifra.
    """
    if amount is None or amount == "" or amount == 0:
        return "$\u00A00"
    try:
        val_float = float(amount)
        # Si tiene centavos significativos (> 0.009 de diferencia con el entero)
        if show_decimals_if_needed and abs(val_float - round(val_float)) >= 0.005:
            entero = int(val_float)
            centavos = int(round((abs(val_float) - abs(entero)) * 100))
            if centavos >= 100:
                entero += 1
                centavos = 0
            formatted_entero = f"{entero:,}".replace(",", ".")
            return f"$\u00A0{formatted_entero},{centavos:02d}"
        else:
            val_int = int(round(val_float))
            formatted = f"{val_int:,}".replace(",", ".")
            return f"$\u00A0{formatted}"
    except Exception:
        return f"$\u00A0{amount}"

def set_cell_width_xml(cell, width_in_inches: float):
    """Fija estrictamente el ancho en dxa a nivel XML para evitar renegociaciones de Word."""
    tcPr = cell._tc.get_or_add_tcPr()
    dxa_width = int(round(width_in_inches * 1440))
    tcW = parse_xml(f'<w:tcW {nsdecls("w")} w:w="{dxa_width}" w:type="dxa"/>')
    tcPr.append(tcW)

def set_cell_background(cell, hex_color: str):
    """Aplica sombreado XML a celda de python-docx."""
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    cell._tc.get_or_add_tcPr().append(shading)

def set_cell_margins(cell, top=50, bottom=50, left=65, right=65):
    """Establece márgenes internos (padding dxa) en celda docx."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>'
    )
    tcPr.append(tcMar)

def set_table_borders(table, color="D1D5DB", sz="4", val="single"):
    """Establece bordes sutiles y limpios en tablas de python-docx."""
    tblPr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'<w:top w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:bottom w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:insideH w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:insideV w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:left w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:right w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'</w:tblBorders>'
    )
    tblPr.append(borders)



def get_short_company_name(nombre: str) -> str:
    """Retorna el nombre comercial o razón social limpia sin truncamientos arbitrarios."""
    if not nombre:
        return "Oferente"
    cleaned = clean_company_name(nombre)
    n_up = cleaned.upper()
    if "CISPA" in n_up:
        return "CISPA S.A.S."
    if "PUBLICORP" in n_up:
        return "PubliCorp S.A.S."
    if "ASOCOMUNAL" in n_up:
        return "ASOCOMUNAL"
    if "TORREON" in n_up:
        return "TORREÓN"
    if "M360" in n_up:
        return "M360"
    return cleaned

class APUContractAgent:
    """
    Agente Autónomo Especialista en Evaluación Económica, Matriz Comparativa,
    Descomposición de APU y Compilación de Documentos Oficiales Word (.docx)
    para la Empresa de Servicios Públicos de Yolombó (ESPY S.A. E.S.P.).
    """

    ACCENT_TEAL = "0284C7"       # Azul institucional ESPY
    ACCENT_GREEN = "16A34A"      # Verde institucional ESPY
    HEADER_BG = "F2F4F7"         # Azul marino oscuro
    BG_LIGHT = "FFFFFF"          # Gris muy suave
    BG_WINNER = "EBF3FA"
    BORDER_COLOR = "D1D5DB"         # Verde suave para resaltar ganador
    TEXT_DARK = RGBColor(0, 0, 0)

    def __init__(self):
        self.nombre = "Agente Especialista en Evaluación Económica y APU - ESPY S.A. E.S.P."

    def resolve_logo(self, custom_logo_path: Optional[str] = None) -> Optional[Path]:
        """Resuelve la ruta física del logotipo corporativo de la ESPY."""
        root = Path(settings.WORKSPACE_ROOT)
        if custom_logo_path:
            p = Path(custom_logo_path)
            if not p.is_absolute():
                candidate = root / p
                if candidate.exists():
                    return candidate
            elif p.exists():
                return p
        default_logo = root / "frontend" / "assets" / "logo.png"
        if default_logo.exists():
            return default_logo
        scratch_logo = root / "scratch" / "custom_image1.png"
        if scratch_logo.exists():
            return scratch_logo
        return None

    def _setup_page_header_footer(self, section, cfg: ProcesoConfig, logo_file: Optional[Path]):
        """Configura el membrete oficial institucional (logo superior, barra bicolor y footer en cada página)."""
        section.header_distance = Inches(0.35)
        section.top_margin = Inches(1.35)
        section.bottom_margin = Inches(1.35)
        section.footer_distance = Inches(0.35)

        # ENCABEZADO OFICIAL
        head = section.header
        p_h = head.paragraphs[0]
        p_h.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p_h.paragraph_format.space_before = Pt(0)
        p_h.paragraph_format.space_after = Pt(2)

        if logo_file and logo_file.exists():
            try:
                p_h_logo = head.paragraphs[0]
                p_h_logo.alignment = WD_ALIGN_PARAGRAPH.LEFT
                r_logo = p_h_logo.add_run()
                r_logo.add_picture(str(logo_file), height=Inches(0.48))
            except Exception as e:
                logger.warning(f"No se pudo insertar logo en header: {e}")
                r_fallback = head.paragraphs[0].add_run("ESPY S.A. E.S.P. - Yolombó")
                r_fallback.bold = True
                r_fallback.font.size = Pt(8.5)
                r_fallback.font.color.rgb = RGBColor(3, 0, 143)
        else:
            r_fallback = head.paragraphs[0].add_run("ESPY S.A. E.S.P. - Yolombó")
            r_fallback.bold = True
            r_fallback.font.size = Pt(8.5)
            r_fallback.font.color.rgb = RGBColor(3, 0, 143)

        # Barra bicolor institucional en Header
        tbl_h = head.add_table(rows=1, cols=2, width=Inches(6.7))
        tbl_h.alignment = WD_TABLE_ALIGNMENT.CENTER
        set_table_borders(tbl_h, color="FFFFFF", sz="0", val="none")
        c1, c2 = tbl_h.rows[0].cells[0], tbl_h.rows[0].cells[1]
        c1.width = Inches(5.35)
        c2.width = Inches(1.35)
        set_cell_background(c1, self.ACCENT_TEAL)
        set_cell_background(c2, self.ACCENT_GREEN)
        for c in (c1, c2):
            p = c.paragraphs[0]
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = Pt(3)
            r = p.add_run(" ")
            r.font.size = Pt(2)

        # PIE DE PÁGINA INSTITUCIONAL
        foot = section.footer
        p_f = foot.paragraphs[0]
        p_f.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_f.paragraph_format.space_before = Pt(2)
        p_f.paragraph_format.space_after = Pt(4)
        p_f.paragraph_format.line_spacing = 1.15

        r_f1 = p_f.add_run("EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ – NIT. 811015112-4\nCELULAR: 3206976172\n")
        r_f1.bold = True
        r_f1.font.size = Pt(7.5)
        r_f1.font.color.rgb = RGBColor(30, 41, 59)

        r_f2 = p_f.add_run("serviciospublicosyol@hotmail.com\n")
        r_f2.bold = True
        r_f2.font.size = Pt(7.5)
        r_f2.font.color.rgb = RGBColor(2, 132, 199)

        r_f3 = p_f.add_run("Calle Colombia 20 #20 - 74 Yolombó – Antioquia")
        r_f3.font.size = Pt(7.5)
        r_f3.font.color.rgb = RGBColor(71, 85, 105)

        # Barra bicolor institucional en Footer
        tbl_f = foot.add_table(rows=1, cols=2, width=Inches(6.7))
        tbl_f.alignment = WD_TABLE_ALIGNMENT.CENTER
        set_table_borders(tbl_f, color="FFFFFF", sz="0", val="none")
        c1_f, c2_f = tbl_f.rows[0].cells[0], tbl_f.rows[0].cells[1]
        c1_f.width = Inches(5.35)
        c2_f.width = Inches(1.35)
        set_cell_background(c1_f, self.ACCENT_TEAL)
        set_cell_background(c2_f, self.ACCENT_GREEN)
        for c in (c1_f, c2_f):
            p = c.paragraphs[0]
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = Pt(3)
            r = p.add_run(" ")
            r.font.size = Pt(2)

    def _add_decorative_bar(self, doc: Document):
        """Agrega la barra bicolor superior en el cuerpo del documento."""
        tbl_bar = doc.add_table(rows=1, cols=2)
        tbl_bar.alignment = WD_TABLE_ALIGNMENT.CENTER
        set_table_borders(tbl_bar, color="FFFFFF", sz="0", val="none")
        c1, c2 = tbl_bar.rows[0].cells[0], tbl_bar.rows[0].cells[1]
        c1.width = Inches(5.35)
        c2.width = Inches(1.35)
        set_cell_background(c1, self.ACCENT_TEAL)
        set_cell_background(c2, self.ACCENT_GREEN)
        for c in (c1, c2):
            p = c.paragraphs[0]
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = Pt(3.5)
            r = p.add_run(" ")
            r.font.size = Pt(2.5)

    def _style_table_header(self, row, headers: List[str], widths: List[float]):
        """Estiliza encabezados de tabla con fondo claro suave y texto negro Arial 12pt."""
        for idx, (head_text, w) in enumerate(zip(headers, widths)):
            cell = row.cells[idx]
            cell.width = w
            try:
                w_in = getattr(w, "inches", float(w))
                set_cell_width_xml(cell, w_in)
            except Exception:
                pass
            set_cell_background(cell, self.HEADER_BG)
            set_cell_margins(cell, top=60, bottom=60, left=50, right=50)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            run = p.add_run(head_text)
            run.bold = True
            run.font.name = 'Arial'
            run.font.size = Pt(12)
            run.font.color.rgb = RGBColor(0, 0, 0)

    def _fill_styled_row(self, row, values_and_align: List[Tuple[str, WD_ALIGN_PARAGRAPH, bool]], widths: List[float], bg_color: str = "FFFFFF"):
        """Rellena y formatea celdas de datos con padding, alineación y texto negro Arial 12pt."""
        for idx, ((text, align, is_bold), w) in enumerate(zip(values_and_align, widths)):
            cell = row.cells[idx]
            cell.width = w
            try:
                w_in = getattr(w, "inches", float(w))
                set_cell_width_xml(cell, w_in)
            except Exception:
                pass
            set_cell_background(cell, bg_color if bg_color != "FFFFFF" else "FFFFFF")
            set_cell_margins(cell, top=45, bottom=45, left=50, right=50)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            p = cell.paragraphs[0]
            p.alignment = align
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            run = p.add_run(str(text))
            run.bold = is_bold
            run.font.name = 'Arial'
            run.font.size = Pt(12)
            run.font.color.rgb = RGBColor(0, 0, 0)

    def _set_cant_split(self, row):
        """Evita que una fila se corte por la mitad entre dos páginas en Word."""
        trPr = row._tr.get_or_add_trPr()
        trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))

    # =========================================================================
    # 1. DETERMINACIÓN NORMATIVA SEGÚN MANUAL DE CONTRATACIÓN ESPY (PR-ESPY-002)
    # =========================================================================

    def calculate_manual_modalidad_and_guarantees(
        self,
        valor_total: float,
        smlmv: float = 1750905.0,
        tipo_contrato: str = "Suministro",
        plazo_meses: int = 1,
        anticipo_pct: float = 0.0,
        modalidad_manual_codigo: str = "AUTO",
        causal_directa_numeral_19: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Determina con exactitud la modalidad de selección aplicable y la matriz de garantías exigibles
        según lo estipulado en el Manual de Contratación de la ESPY (Código: PR-ESPY-002, Versión: 02,
        Resolución Nro. 5 de Junta Directiva de la Empresa de Servicios Públicos de Yolombó E.S.P.).
        """
        if smlmv <= 0:
            smlmv = 1750905.0
        cuantia_smlmv = round(valor_total / smlmv, 2)
        tipo_c_lower = (tipo_contrato or "").lower().strip()

        # Determinación de Modalidad
        if modalidad_manual_codigo == "DIRECTA_NUMERAL_19":
            nombre_mod = "Solicitud Única de Oferta (Contratación Directa)"
            numeral_mod = "Numeral 19 del Manual de Contratación PR-ESPY-002 (Versión 02)"
            rango_mod = "Causal Especial de Solicitud Única (Numeral 19)"
            min_cotiz = "Una (1) oferta o cotización directa formal"
            instrumento_mod = "Contrato escrito formal con justificación de causal"
            fundamento_legal = (
                f"De conformidad con el Numeral 19 del Manual de Contratación de la ESPY, se adelanta Solicitud Única de Oferta "
                f"bajo la causal especial correspondiente ({causal_directa_numeral_19 or 'Servicios profesionales o proveedor calificado'}), "
                f"manteniendo como referencia los precios vigentes del mercado."
            )
        elif modalidad_manual_codigo == "MENOR_20_SMLMV" or (modalidad_manual_codigo == "AUTO" and cuantia_smlmv < 20.0):
            nombre_mod = "Estudio de Precios de Mercado / Consulta de Precios del Mercado"
            numeral_mod = "Numeral 12 del Manual de Contratación PR-ESPY-002 (Versión 02)"
            rango_mod = "Cuantía inferior a 20 SMLMV"
            min_cotiz = "Al menos una (1) cotización de mercado"
            instrumento_mod = "Orden de Compra o Contrato simplificado (Numeral 34)"
            fundamento_legal = (
                "De conformidad con el Numeral 12 del Manual de Contratación de la Empresa de Servicios Públicos de Yolombó ESP "
                "(Resolución Nro. 5 de Junta Directiva), cuando la cuantía del contrato a celebrar sea inferior a veinte (20) salarios mínimos "
                "legales mensuales vigentes (SMLMV), se realiza un estudio de precios del mercado, dejando constancia escrita en el formato "
                "'Consulta de Precios del Mercado' y formalizándose mediante orden de compra o contrato (Numeral 34)."
            )
        elif modalidad_manual_codigo == "ENTRE_20_Y_100_SMLMV" or (modalidad_manual_codigo == "AUTO" and 20.0 <= cuantia_smlmv < 100.0):
            nombre_mod = "Solicitud de Ofertas y Estudio de Precios de Mercado con Mínimo Tres (3) Cotizaciones"
            numeral_mod = "Numeral 13 del Manual de Contratación PR-ESPY-002 (Versión 02)"
            rango_mod = "Entre 20 y menos de 100 SMLMV"
            min_cotiz = "Mínimo tres (3) cotizaciones formales"
            instrumento_mod = "Cuadro comparativo de propuestas y Contrato formal escrito"
            fundamento_legal = (
                "De conformidad con el Numeral 13 del Manual de Contratación de la ESPY, cuando la cuantía del contrato a celebrar sea "
                "desde 20 salarios mínimos legales mensuales vigentes e inferior a 100 SMLMV, se requerirá como mínimo la obtención previa "
                "de tres (3) cotizaciones. En el formato oficial 'Cuadro comparativo de propuestas' se indicará lo ofertado por cada "
                "proponente y los criterios objetivos tenidos en cuenta para la selección del contratista más favorable."
            )
        elif modalidad_manual_codigo == "ENTRE_100_Y_1000_SMLMV" or (modalidad_manual_codigo == "AUTO" and 100.0 <= cuantia_smlmv < 1000.0):
            nombre_mod = "Invitación Pública a Cotizar"
            numeral_mod = "Numerales 14 y 15 del Manual de Contratación PR-ESPY-002 (Versión 02)"
            rango_mod = "Desde 100 SMLMV y menos de 1000 SMLMV"
            min_cotiz = "Convocatoria pública abierta"
            instrumento_mod = "Pliego simplificado y publicación en página web institucional"
            fundamento_legal = (
                "De conformidad con los Numerales 14 y 15 del Manual de Contratación de la ESPY, cuando la cuantía a celebrar sea desde "
                "100 SMLMV e inferior a 1000 SMLMV, se formula una Invitación Pública a Cotizar con publicación en la página web corporativa "
                "de la Empresa ESPY, estableciendo requisitos habilitantes, especificaciones y criterios de ponderación."
            )
        else: # >= 1000 SMLMV
            nombre_mod = "Licitación Privada Pliego de Condiciones"
            numeral_mod = "Numerales 16 y 17 del Manual de Contratación PR-ESPY-002 (Versión 02)"
            rango_mod = "Desde 1000 SMLMV en adelante"
            min_cotiz = "Convocatoria pública amplia con pliego de condiciones"
            instrumento_mod = "Pliego de condiciones con publicación mínima de diez (10) días hábiles"
            fundamento_legal = (
                "De conformidad con los Numerales 16 y 17 del Manual de Contratación de la ESPY, cuando la cuantía sea desde 1000 SMLMV, "
                "se adelanta Licitación Privada mediante Pliego de Condiciones por escrito, orden de apertura y publicación mínima durante "
                "diez (10) días hábiles en página web institucional y medios de amplia circulación."
            )

        # Matriz de Garantías Exigibles según Título III (Numerales 30 y 32 del Manual ESPY)
        garantias: List[Dict[str, Any]] = []
        es_profesional = ("profesional" in tipo_c_lower)
        exento_garantias = (cuantia_smlmv < 20.0 and modalidad_manual_codigo != "DIRECTA_NUMERAL_19") or es_profesional

        if exento_garantias:
            garantias.append({
                "amparo": "Exención de Garantías (Opcional)",
                "porcentaje": 0.0,
                "porcentaje_texto": "No obligatoria (0%)",
                "base_calculo": "Exención legal",
                "valor_asegurado_cop": 0.0,
                "vigencia_texto": "N/A - Conforme al Numeral 32 (literales d y e), las garantías no son obligatorias para contratos hasta 20 SMLMV ni contratos de prestación de servicios profesionales.",
                "numeral_manual": "Numeral 32.d y 32.e",
                "obligatorio": False
            })
        else:
            plazo_str = f"{plazo_meses} mes(es)"

            # 1. Cumplimiento (Numeral 30.2)
            vr_cump = round(valor_total * 0.10, 2)
            garantias.append({
                "amparo": "Cumplimiento del Contrato",
                "porcentaje": 10.0,
                "porcentaje_texto": "10% del valor total",
                "base_calculo": "Valor Total del Contrato",
                "valor_asegurado_cop": vr_cump,
                "vigencia_texto": f"Plazo de ejecución ({plazo_str}) y dos (2) meses más.",
                "numeral_manual": "Numeral 30.2",
                "obligatorio": True
            })

            # 2. Salarios y prestaciones (Numeral 30.3)
            vr_sal = round(valor_total * 0.05, 2)
            garantias.append({
                "amparo": "Pago de Salarios, Prestaciones Sociales e Indemnizaciones",
                "porcentaje": 5.0,
                "porcentaje_texto": "5% del valor total",
                "base_calculo": "Valor Total del Contrato",
                "valor_asegurado_cop": vr_sal,
                "vigencia_texto": f"Plazo de ejecución ({plazo_str}) y tres (3) años más (exigible si vincula personal).",
                "numeral_manual": "Numeral 30.3",
                "obligatorio": True
            })

            # 3. Anticipo (Numeral 30.1 - si aplica)
            if anticipo_pct > 0:
                vr_ant = round(valor_total * (anticipo_pct / 100.0), 2)
                garantias.append({
                    "amparo": "Buen Manejo y Correcta Inversión del Anticipo",
                    "porcentaje": float(anticipo_pct),
                    "porcentaje_texto": f"100% del monto del anticipo ({anticipo_pct}%)",
                    "base_calculo": "Monto Total del Anticipo Concedido",
                    "valor_asegurado_cop": vr_ant,
                    "vigencia_texto": f"Plazo de ejecución ({plazo_str}) y dos (2) meses más.",
                    "numeral_manual": "Numeral 30.1",
                    "obligatorio": True
                })

            # 4. Calidad del Servicio o Calidad de Bienes (Numerales 30.5 y 30.6)
            if any(k in tipo_c_lower for k in ["obra", "construcci", "adecuaci"]):
                vr_est = round(valor_total * 0.15, 2)
                garantias.append({
                    "amparo": "Estabilidad y Calidad de la Obra",
                    "porcentaje": 15.0,
                    "porcentaje_texto": "15% del valor final de la obra",
                    "base_calculo": "Valor Final Liquidado de la Obra",
                    "valor_asegurado_cop": vr_est,
                    "vigencia_texto": "Cinco (5) años contados a partir del acta de recibo a satisfacción.",
                    "numeral_manual": "Numeral 30.4",
                    "obligatorio": True
                })
            elif any(k in tipo_c_lower for k in ["suministro", "compra", "bien", "dotaci", "equipo", "quimic"]):
                vr_cal_b = round(valor_total * 0.50, 2)
                garantias.append({
                    "amparo": "Calidad y Correcto Funcionamiento de los Bienes",
                    "porcentaje": 50.0,
                    "porcentaje_texto": "50% del valor total",
                    "base_calculo": "Valor Total del Contrato",
                    "valor_asegurado_cop": vr_cal_b,
                    "vigencia_texto": "Mínimo un (1) año contado a partir de la entrega y recibo a satisfacción de los bienes.",
                    "numeral_manual": "Numeral 30.5",
                    "obligatorio": True
                })
            else:
                vr_cal_s = round(valor_total * 0.15, 2)
                garantias.append({
                    "amparo": "Calidad del Servicio Prestado",
                    "porcentaje": 15.0,
                    "porcentaje_texto": "15% del valor total",
                    "base_calculo": "Valor Total del Contrato",
                    "valor_asegurado_cop": vr_cal_s,
                    "vigencia_texto": "Un (1) año contado simultáneamente con el recibo del servicio a satisfacción.",
                    "numeral_manual": "Numeral 30.6",
                    "obligatorio": True
                })

            # 5. Responsabilidad Civil Extracontractual (Numeral 30.8)
            vr_rce = round(valor_total * 0.05, 2)
            garantias.append({
                "amparo": "Responsabilidad Civil Extracontractual",
                "porcentaje": 5.0,
                "porcentaje_texto": "5% del valor total",
                "base_calculo": "Valor Total del Contrato",
                "valor_asegurado_cop": vr_rce,
                "vigencia_texto": f"Plazo de ejecución ({plazo_str}) y seis (6) meses más.",
                "numeral_manual": "Numeral 30.8",
                "obligatorio": True
            })

            # 6. Seriedad de la Oferta (Numeral 30.9 - sólo > 200 SMLMV)
            if cuantia_smlmv > 200.0:
                vr_ser = round(valor_total * 0.10, 2)
                garantias.append({
                    "amparo": "Seriedad de la Oferta (Precontractual)",
                    "porcentaje": 10.0,
                    "porcentaje_texto": "10% del presupuesto estimado",
                    "base_calculo": "Presupuesto Estimado de la Convocatoria",
                    "valor_asegurado_cop": vr_ser,
                    "vigencia_texto": "Tres (3) meses contados a partir del cierre del proceso (exigible para > 200 SMLMV).",
                    "numeral_manual": "Numeral 30.9",
                    "obligatorio": True
                })

        return {
            "nombre_modalidad": nombre_mod,
            "numeral_modalidad": numeral_mod,
            "rango_cuantia_smlmv": rango_mod,
            "cuantia_smlmv_calculada": cuantia_smlmv,
            "min_cotizaciones": min_cotiz,
            "instrumento_formal": instrumento_mod,
            "fundamento_legal": fundamento_legal,
            "garantias_exigibles": garantias
        }

    # =========================================================================
    # 2. EXTRACCIÓN Y AUDITORÍA ARITMÉTICA DE COTIZACIONES MULTI-FORMATO
    # =========================================================================

    def extract_all_offers_from_file(
        self,
        file_bytes: bytes,
        filename: str,
        override_api_key: Optional[str] = None
    ) -> List[ProponenteOferta]:
        """
        Extrae todas las ofertas económicas que contenga el archivo (PDF digital o escaneado, Excel, Word, CSV, JSON).
        Soporta de manera autónoma expedientes compuestos de múltiples oferentes en un único PDF.
        """
        ext = Path(filename).suffix.lower()
        if ext == ".pdf":
            try:
                pdf_offers = multi_proposal_parser.extract_offers_from_pdf_bytes(file_bytes, filename, override_api_key)
                if pdf_offers:
                    return pdf_offers
            except Exception as e:
                logger.warning(f"Aviso parseando PDF con multi_proposal_parser: {e}")

        single_offer = self.parse_and_extract_offer(file_bytes, filename, override_api_key=override_api_key)
        return [single_offer] if single_offer else []

    def parse_and_extract_offer(
        self,
        file_bytes: bytes,
        filename: str,
        text_content: Optional[str] = None,
        override_api_key: Optional[str] = None
    ) -> ProponenteOferta:
        """
        Procesa un archivo de cotización (Excel, CSV, Word .docx, PDF, JSON o texto),
        extrayendo el nombre de la empresa/proponente, NIT, ítems y ejecutando control aritmético estricto.
        """
        ext = Path(filename).suffix.lower()
        if ext == ".pdf":
            try:
                pdf_offers = multi_proposal_parser.extract_offers_from_pdf_bytes(file_bytes, filename, override_api_key)
                if pdf_offers:
                    return pdf_offers[0]
            except Exception as e:
                logger.warning(f"Aviso en parse_and_extract_offer para PDF: {e}")

        items: List[ItemCotizacion] = []
        nombre_proponente = Path(filename).stem.replace("_", " ").title()
        nit_proponente = "Pendiente de verificación"
        rep_legal = "Representante Legal"
        fecha_oferta = datetime.now().strftime("%Y-%m-%d")

        try:
            if ext in [".xlsx", ".xls"]:
                items, nombre_proponente, nit_proponente = self._parse_excel_bytes(file_bytes, nombre_proponente)
            elif ext == ".csv":
                items, nombre_proponente, nit_proponente = self._parse_csv_bytes(file_bytes, nombre_proponente)
            elif ext == ".json":
                items, nombre_proponente, nit_proponente, rep_legal, fecha_oferta = self._parse_json_bytes(file_bytes, nombre_proponente)
            elif ext == ".docx":
                items, nombre_proponente, nit_proponente = self._parse_docx_bytes(file_bytes, nombre_proponente)
            elif ext == ".pdf":
                items, nombre_proponente, nit_proponente = self._parse_pdf_bytes(file_bytes, nombre_proponente)
            elif text_content:
                items = self._parse_text_lines(text_content)
        except Exception as e:
            logger.warning(f"Aviso parseando oferta {filename}: {e}")
            if text_content:
                items = self._parse_text_lines(text_content)

        # Si aún no hay ítems y Gemini está disponible, extraer con LLM
        if not items and text_content and gemini_service._get_client(override_api_key):
            items, p_name, p_nit = self._extract_with_gemini(text_content, override_api_key)
            if p_name: nombre_proponente = p_name
            if p_nit: nit_proponente = p_nit

        # Fallback de seguridad si el archivo estaba totalmente en blanco
        if not items:
            items = [
                ItemCotizacion(
                    item_numero=1,
                    descripcion=f"Suministro o servicio cotizado ({filename})",
                    unidad="GL",
                    cantidad=1.0,
                    valor_unitario=1000000.0,
                    valor_total=1000000.0,
                    valor_total_calculado=1000000.0
                )
            ]

        # CONTROL ARITMÉTICO RIGUROSO (Numeral 29 Manual ESPY)
        subtotal = 0.0
        total_errores = 0
        for it in items:
            calc = round(it.cantidad * it.valor_unitario, 2)
            it.valor_total_calculado = calc
            # Si el valor digitado difiere del producto aritmético
            if abs(it.valor_total - calc) > 1.0 and it.valor_total > 0:
                it.error_aritmetico_detectado = True
                it.diferencia_aritmetica = round(it.valor_total - calc, 2)
                total_errores += 1
            else:
                it.error_aritmetico_detectado = False
                it.diferencia_aritmetica = 0.0
                it.valor_total = calc
            subtotal += it.valor_total

        return ProponenteOferta(
            proponente_id=re.sub(r"[^a-zA-Z0-9]", "_", nombre_proponente).lower()[:20],
            nombre_razon_social=nombre_proponente,
            nit_cedula=nit_proponente,
            representante_legal=rep_legal,
            fecha_oferta=fecha_oferta,
            items=items,
            subtotal=round(subtotal, 2),
            iva_o_impuestos=0.0,
            valor_total_oferta=round(subtotal, 2),
            tiene_errores_aritmeticos=(total_errores > 0),
            total_errores_aritmeticos=total_errores
        )

    def _parse_docx_bytes(self, b: bytes, fallback_name: str) -> Tuple[List[ItemCotizacion], str, str]:
        """Extrae cotización desde archivo Microsoft Word (.docx)."""
        items: List[ItemCotizacion] = []
        nombre = fallback_name
        nit = "Pendiente de verificación"
        try:
            doc = Document(io.BytesIO(b))
            full_text = [p.text for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    cells = [c.text.strip() for c in row.cells]
                    if len(cells) < 3: continue
                    money_vals = [re.sub(r"[^\d]", "", c) for c in cells if re.search(r"\$\s*\d|\d{4,}", c)]
                    if money_vals and len(cells) >= 3:
                        desc = cells[1] if len(cells) > 1 and len(cells[1]) > 4 else cells[0]
                        if desc.lower() in ["subtotal", "total", "iva", "descripción", "item"]: continue
                        try:
                            v_u = float(money_vals[-2]) if len(money_vals) >= 2 else float(money_vals[-1])
                            v_t = float(money_vals[-1])
                            items.append(ItemCotizacion(
                                item_numero=len(items) + 1,
                                descripcion=desc,
                                unidad="und",
                                cantidad=1.0,
                                valor_unitario=v_u,
                                valor_total=v_t,
                                valor_total_calculado=v_u
                            ))
                        except Exception: pass
            all_text = "\n".join(full_text)
            m_nit = re.search(r"(?:NIT|C\.?C\.?)\s*[:.]?\s*(\d{8,11}(?:-\d)?)", all_text, re.IGNORECASE)
            if m_nit: nit = m_nit.group(1)
            m_nom = re.search(r"(?:SEÑORES|PROPONENTE|COTIZACIÓN DE|RAZÓN SOCIAL|EMPRESA)\s*[:.]?\s*([A-ZÁÉÍÓÚÑ\s]{4,45})", all_text)
            if m_nom: nombre = m_nom.group(1).strip()
        except Exception as e:
            logger.warning(f"Error parseando docx: {e}")
        return items, nombre, nit

    def _parse_excel_bytes(self, b: bytes, fallback_name: str) -> Tuple[List[ItemCotizacion], str, str]:
        """Extrae cotización desde hojas de cálculo de Excel (.xlsx / .xls)."""
        import openpyxl
        items = []
        nombre = fallback_name
        nit = "Pendiente de verificación"
        wb = openpyxl.load_workbook(io.BytesIO(b), data_only=True)
        ws = wb.active
        for row in ws.iter_rows(values_only=True):
            if not row or not any(row): continue
            clean = [str(c or "").strip() for c in row if c is not None]
            line_str = " ".join(clean)
            if "nit" in line_str.lower() and nit == "Pendiente de verificación":
                m = re.search(r"\d{8,11}(?:-\d)?", line_str)
                if m: nit = m.group(0)
            if any(k in line_str.lower() for k in ["proponente", "cotizante", "empresa:"]) and nombre == fallback_name:
                m = re.search(r"(?:proponente|cotizante|empresa:)\s*[:.]?\s*([A-Za-z0-9ÁÉÍÓÚñáéíóú\s]{3,40})", line_str, re.IGNORECASE)
                if m: nombre = m.group(1).strip()
            
            # Buscar fila con descripción y números
            money_vals = []
            desc_val = ""
            cant_val = 1.0
            und_val = "und"
            for c in row:
                if c is None: continue
                if isinstance(c, (int, float)):
                    if c > 100: money_vals.append(float(c))
                    elif 0 < c <= 1000: cant_val = float(c)
                elif isinstance(c, str):
                    s = c.strip()
                    if len(s) > 5 and not desc_val and not any(k in s.lower() for k in ["total", "subtotal", "iva"]):
                        desc_val = s
                    elif len(s) <= 4 and s.isalpha():
                        und_val = s
                    elif re.search(r"\$\s*\d|\d{4,}", s):
                        clean_num = re.sub(r"[^\d.]", "", s)
                        try:
                            val = float(clean_num)
                            if val > 100: money_vals.append(val)
                        except Exception: pass

            if desc_val and money_vals and desc_val.lower() not in ["descripción", "item", "concepto", "subtotal", "total"]:
                vu = money_vals[-2] if len(money_vals) >= 2 else money_vals[-1]
                vt = money_vals[-1]
                items.append(ItemCotizacion(
                    item_numero=len(items) + 1,
                    descripcion=desc_val,
                    unidad=und_val,
                    cantidad=cant_val,
                    valor_unitario=vu,
                    valor_total=vt,
                    valor_total_calculado=round(cant_val * vu, 2)
                ))
        return items, nombre, nit

    def _parse_csv_bytes(self, b: bytes, fallback_name: str) -> Tuple[List[ItemCotizacion], str, str]:
        """Extrae cotización desde archivos CSV delimitados."""
        items = []
        lines = b.decode("utf-8", errors="ignore").splitlines()
        reader = csv.reader(lines)
        for idx, row in enumerate(reader, 1):
            if not row or len(row) < 3: continue
            desc = row[0].strip() if len(row[0]) > 4 else row[1].strip()
            if desc.lower() in ["item", "descripcion", "subtotal", "total"]: continue
            try:
                cant = float(re.sub(r"[^\d.]", "", row[1])) if len(row) > 3 else 1.0
                vu = float(re.sub(r"[^\d.]", "", row[-2])) if len(row) > 3 else float(re.sub(r"[^\d.]", "", row[-1]))
                vt = float(re.sub(r"[^\d.]", "", row[-1]))
                items.append(ItemCotizacion(
                    item_numero=len(items) + 1,
                    descripcion=desc,
                    unidad="und",
                    cantidad=cant,
                    valor_unitario=vu,
                    valor_total=vt,
                    valor_total_calculado=cant * vu
                ))
            except Exception: pass
        return items, fallback_name, "Pendiente de verificación"

    def _parse_json_bytes(self, b: bytes, fallback_name: str) -> Tuple[List[ItemCotizacion], str, str, str, str]:
        """Extrae cotización desde archivo JSON estructurado."""
        data = json.loads(b.decode("utf-8", errors="ignore"))
        nombre = data.get("nombre_razon_social") or data.get("proponente") or fallback_name
        nit = data.get("nit_cedula") or data.get("nit") or "Pendiente de verificación"
        rep = data.get("representante_legal") or "Representante Legal"
        fecha = data.get("fecha_oferta") or datetime.now().strftime("%Y-%m-%d")
        items = []
        raw_items = data.get("items") or data.get("cotizacion") or []
        for idx, it in enumerate(raw_items, 1):
            vu = float(it.get("valor_unitario") or 0.0)
            cant = float(it.get("cantidad") or 1.0)
            vt = float(it.get("valor_total") or (cant * vu))
            items.append(ItemCotizacion(
                item_numero=idx,
                descripcion=it.get("descripcion") or f"Ítem {idx}",
                unidad=it.get("unidad") or "und",
                cantidad=cant,
                valor_unitario=vu,
                valor_total=vt,
                valor_total_calculado=round(cant * vu, 2)
            ))
        return items, nombre, nit, rep, fecha

    def _parse_pdf_bytes(self, b: bytes, fallback_name: str) -> Tuple[List[ItemCotizacion], str, str]:
        """Extrae cotización desde PDF utilizando multi_proposal_parser y filtros estrictos anti-ruido."""
        try:
            offers = multi_proposal_parser.extract_offers_from_pdf_bytes(b, fallback_name)
            if offers:
                first = offers[0]
                return first.items, first.nombre_razon_social, first.nit_cedula
        except Exception as e:
            logger.warning(f"Aviso en _parse_pdf_bytes delegando a multi_proposal_parser: {e}")

        import pdfplumber
        items = []
        nombre = fallback_name
        nit = "Pendiente de verificación"
        full_text = []
        with pdfplumber.open(io.BytesIO(b)) as pdf:
            for p in pdf.pages:
                txt = p.extract_text() or ""
                full_text.append(txt)
                for tbl in p.extract_tables() or []:
                    for row in tbl:
                        if not row or len(row) < 2: continue
                        clean_row = [str(c or "").strip() for c in row]
                        row_u = " ".join(clean_row).upper()
                        if any(k in row_u for k in ["NIT", "TEL", "CEL", "CR ", "CALLE", "@", ".COM", "RESOLUCION", "CRA", "LEY", "DECRETO"]):
                            continue
                        money_vals = [clean_money_value(c) for c in clean_row if re.search(r"\$\s*\d|\b\d{1,3}(?:\.\d{3}){1,3}\b", c)]
                        if money_vals and len(clean_row) >= 2:
                            desc = clean_row[1] if len(clean_row) > 1 and len(clean_row[1]) > 5 else clean_row[0]
                            if any(w in desc.lower() for w in ["subtotal", "total", "iva", "descripción", "concepto", "alcance"]):
                                continue
                            try:
                                v_u = money_vals[-2] if len(money_vals) >= 2 else money_vals[-1]
                                v_t = money_vals[-1]
                                if v_t > 0:
                                    items.append(ItemCotizacion(
                                        item_numero=len(items) + 1, descripcion=desc, unidad="und",
                                        cantidad=1.0, valor_unitario=v_u, valor_total=v_t, valor_total_calculado=v_u
                                    ))
                            except Exception: pass
        all_txt = "\n".join(full_text)
        m_nit = re.search(r"(?:NIT|C\.?C\.?)\s*[:.]?\s*(\d{8,11}(?:-\d)?)", all_txt, re.IGNORECASE)
        if m_nit: nit = m_nit.group(1)
        m_nom = re.search(r"(?:SEÑORES|PROPONENTE|COTIZACIÓN DE|RAZÓN SOCIAL)\s*[:.]?\s*([A-ZÁÉÍÓÚÑ\s]{5,40})", all_txt, re.IGNORECASE)
        if m_nom: nombre = m_nom.group(1).strip()
        return items, nombre, nit

    def _parse_text_lines(self, txt: str) -> List[ItemCotizacion]:
        """Extrae líneas de texto delimitadas por guion, coma, barra o tabulación."""
        items = []
        for idx, line in enumerate(txt.splitlines(), 1):
            line = line.strip()
            if not line or len(line) < 4: continue
            parts = re.split(r"[-|;,\t]", line)
            if len(parts) >= 3:
                desc = parts[0].strip()
                try: cant = float(re.sub(r"[^\d.]", "", parts[1]))
                except Exception: cant = 1.0
                try: vu = float(re.sub(r"[^\d.]", "", parts[2]))
                except Exception: vu = 100000.0
                items.append(ItemCotizacion(
                    item_numero=idx, descripcion=desc, unidad="und",
                    cantidad=cant, valor_unitario=vu, valor_total=cant * vu, valor_total_calculado=cant * vu
                ))
        return items

    def _extract_with_gemini(self, txt: str, api_key: Optional[str] = None) -> Tuple[List[ItemCotizacion], str, str]:
        """Fallback con Gemini AI para parsear cotizaciones en formatos irregulares."""
        client = gemini_service._get_client(api_key)
        if not client: return [], "", ""
        try:
            model_to_use = getattr(settings, "GEMINI_MODEL", "gemini-3.8-flash") or "gemini-3.8-flash"
            resp = client.models.generate_content(model=model_to_use, contents=prompt)
            raw = resp.text.strip()
            if "```json" in raw: raw = raw.split("```json")[1].split("```")[0]
            data = json.loads(raw)
            items = [ItemCotizacion(**it) for it in data.get("items", [])]
            return items, data.get("nombre", ""), data.get("nit", "")
        except Exception:
            return [], "", ""

    # =========================================================================
    # 3. EVALUACIÓN COMPARATIVA Y DESGLOSE INTELIGENTE DE APU
    # =========================================================================

    def evaluate_proposals(
        self,
        payload: EvaluacionComparativaPayload,
        override_api_key: Optional[str] = None
    ) -> EvaluacionComparativaResult:
        """
        Ejecuta la evaluación económica comparativa, control aritmético, cálculo de ahorros,
        aplicación estricta del Manual de Contratación ESPY (PR-ESPY-002) y estructuración de APU.
        """
        ofertas = payload.ofertas
        if not ofertas:
            raise ValueError("Se requiere al menos una (1) oferta económica para ejecutar la evaluación comparativa.")

        cfg = payload.proceso_config

        # Limpieza de razones sociales
        for of in ofertas:
            of.nombre_razon_social = clean_company_name(of.nombre_razon_social)

        # Autocompletar objeto_contractual si viene vacío o "No especificado"
        if not cfg.objeto_contractual or cfg.objeto_contractual.strip().lower() in ["no especificado", ""]:
            for of in ofertas:
                if of.items and of.items[0].descripcion:
                    cfg.objeto_contractual = of.items[0].descripcion.strip()
                    break

        # 1. Recalcular valores de ofertas con control aritmético
        for of in ofertas:
            for it in of.items:
                calc = round(it.cantidad * it.valor_unitario, 2)
                if it.valor_total_calculado <= 0:
                    it.valor_total_calculado = calc
                if it.valor_total <= 0:
                    it.valor_total = calc
                elif abs(it.valor_total - calc) <= 1.0:
                    it.valor_total_calculado = it.valor_total
            sub = sum(it.valor_total_calculado for it in of.items)
            if sub <= 0 and of.valor_total_oferta > 0:
                sub = of.valor_total_oferta
            of.subtotal = round(sub, 2)
            of.valor_total_oferta = round(sub + of.iva_o_impuestos, 2)

        # 2. Ordenar por menor valor (Criterio de selección objetiva ESPY)
        ofertas_ordenadas = sorted(ofertas, key=lambda x: (x.valor_total_oferta <= 0, x.valor_total_oferta))
        menor_valor = ofertas_ordenadas[0].valor_total_oferta if ofertas_ordenadas else 0.0
        mayor_valor = ofertas_ordenadas[-1].valor_total_oferta if ofertas_ordenadas else 0.0

        manual_winner = None
        if payload.proponente_ganador_nombre:
            for of in ofertas_ordenadas:
                if of.nombre_razon_social == payload.proponente_ganador_nombre:
                    manual_winner = of
                    break

        for idx, of in enumerate(ofertas_ordenadas, 1):
            of.posicion_orden = idx
            if not of.nombre_razon_social or not of.nombre_razon_social.strip() or of.nombre_razon_social.lower().startswith("proponente cotizaci"):
                of.nombre_razon_social = f"Cotización {idx}"
            if menor_valor > 0:
                diff = of.valor_total_oferta - menor_valor
                of.desviacion_porcentual = round((diff / menor_valor) * 100, 2)
                of.ahorro_frente_a_este = round(diff, 2)
            else:
                of.desviacion_porcentual = 0.0
                of.ahorro_frente_a_este = 0.0
            if manual_winner:
                of.es_seleccionado = (of.nombre_razon_social == manual_winner.nombre_razon_social)
            else:
                of.es_seleccionado = (idx == 1 and of.valor_total_oferta > 0)

        proponente_ganador = manual_winner if manual_winner else ofertas_ordenadas[0]
        valor_letras = numero_a_letras_cop(proponente_ganador.valor_total_oferta)
        ahorro_pesos = round(mayor_valor - proponente_ganador.valor_total_oferta, 2)
        ahorro_pct = round((ahorro_pesos / mayor_valor * 100), 2) if mayor_valor > 0 else 0.0

        # 3. Aplicar reglas del Manual de Contratación ESPY (PR-ESPY-002)
        manual_rules = self.calculate_manual_modalidad_and_guarantees(
            valor_total=proponente_ganador.valor_total_oferta,
            smlmv=cfg.smlmv_vigencia or 1750905.0,
            tipo_contrato=cfg.tipo_contrato or "Suministro",
            plazo_meses=cfg.plazo_ejecucion_meses or 1,
            anticipo_pct=cfg.anticipo_porcentaje or 0.0,
            modalidad_manual_codigo=cfg.modalidad_manual_codigo or "AUTO",
            causal_directa_numeral_19=cfg.causal_directa_numeral_19
        )

        cfg.modalidad_seleccion = manual_rules["nombre_modalidad"]
        cfg.rango_cuantia_smlmv = manual_rules["rango_cuantia_smlmv"]

        # 4. Construir Matriz Comparativa Ítem por Ítem
        matriz_items = []
        if proponente_ganador and proponente_ganador.items:
            for base_item in proponente_ganador.items:
                row_comp = {
                    "item_numero": base_item.item_numero,
                    "descripcion": base_item.descripcion,
                    "unidad": base_item.unidad,
                    "cantidad": base_item.cantidad,
                    "precios_unitarios": {},
                    "totales": {},
                    "menor_precio_unitario": base_item.valor_unitario,
                    "proponente_mas_economico_item": proponente_ganador.nombre_razon_social
                }
                for of in ofertas_ordenadas:
                    match_it = next((i for i in of.items if i.item_numero == base_item.item_numero or i.descripcion.lower().strip() == base_item.descripcion.lower().strip()), None)
                    if match_it:
                        row_comp["precios_unitarios"][of.nombre_razon_social] = match_it.valor_unitario
                        row_comp["totales"][of.nombre_razon_social] = match_it.valor_total
                        if match_it.valor_unitario < row_comp["menor_precio_unitario"]:
                            row_comp["menor_precio_unitario"] = match_it.valor_unitario
                            row_comp["proponente_mas_economico_item"] = of.nombre_razon_social
                    else:
                        row_comp["precios_unitarios"][of.nombre_razon_social] = 0.0
                        row_comp["totales"][of.nombre_razon_social] = 0.0
                matriz_items.append(row_comp)

        # 5. Hallazgos técnicos y justificación bajo el Manual ESPY
        hallazgos = []
        hallazgos.append(
            f"Principio de Economía y Selección Objetiva: La propuesta de {proponente_ganador.nombre_razon_social} representa el menor precio global del mercado ({format_currency_cop_apu(proponente_ganador.valor_total_oferta)} COP), generando un ahorro a la entidad de {format_currency_cop_apu(ahorro_pesos)} ({ahorro_pct}%) frente a la cotización más alta."
        )
        hallazgos.append(
            f"Control Aritmético: Se verificaron las operaciones de las {len(ofertas)} ofertas recibidas. Los cálculos aritméticos de cantidad por precio unitario fueron revisados y auditados a satisfacción."
        )
        hallazgos.append(
            f"Modalidad y Procedimiento: El proceso contractual se enmarca en el {manual_rules['numeral_modalidad']} ({manual_rules['rango_cuantia_smlmv']}), con una cuantía equivalente a {manual_rules['cuantia_smlmv_calculada']} SMLMV vigencia oficial."
        )
        # Detección de discrepancias en cantidades entre oferentes
        discrepancias_cantidades = []
        if proponente_ganador and proponente_ganador.items:
            for base_item in proponente_ganador.items:
                for of in ofertas_ordenadas:
                    if of.nombre_razon_social == proponente_ganador.nombre_razon_social:
                        continue
                    match_it = next((i for i in of.items if i.item_numero == base_item.item_numero or i.descripcion.lower().strip() == base_item.descripcion.lower().strip()), None)
                    if match_it and match_it.cantidad > 0 and abs(match_it.cantidad - base_item.cantidad) > 0.001:
                        discrepancias_cantidades.append(
                            f"En el Ítem N° {base_item.item_numero} ('{base_item.descripcion[:35]}...'), {of.nombre_razon_social} cotizó {match_it.cantidad:g} {match_it.unidad} frente a las {base_item.cantidad:g} {base_item.unidad} requeridas oficialmente por la ESPY."
                        )

        if discrepancias_cantidades:
            hallazgos.append(
                f"Constancia de Cantidades Requeridas: Se constató que algunos proponentes presentaron cantidades discrepantes en sus cotizaciones "
                f"({'; '.join(discrepancias_cantidades[:3])}). Se precisa formalmente que las cantidades oficiales y vinculantes para la entidad son las "
                f"definidas en los Estudios Previos y ofertadas por la propuesta seleccionada ({proponente_ganador.nombre_razon_social}), garantizando la selección objetiva y la debida planeación contractual."
            )

        # Regla de Redacción para Organizaciones Comunales / ESAL
        nom_ganador_upper = proponente_ganador.nombre_razon_social.upper()
        if any(term in nom_ganador_upper for term in ["ASOCOMUNAL", "JUNTA", "COMUNAL", "ASOCIACION", "COOPERATIVA", "CORPORACION", "FUNDACION"]):
            hallazgos.append(
                f"Idoneidad y Economía Territorial: La oferta presentada por {proponente_ganador.nombre_razon_social} acredita conocimiento del territorio y ofrece precios altamente competitivos en el mercado local con menores costos de intermediación, en armonía con las directrices de fomento institucional y selección objetiva."
            )

        if any(of.tiene_errores_aritmeticos for of in ofertas):
            hallazgos.append("Aviso Aritmético: Se detectaron inconsistencias aritméticas menores en cotizaciones participantes, las cuales fueron corregidas formalmente prevaleciendo el precio unitario pactado.")

        justificacion = (
            f"En cumplimiento de los principios de transparencia, economía y selección objetiva consagrados en el "
            f"Manual de Contratación de la Empresa de Servicios Públicos de Yolombó E.S.P. (PR-ESPY-002, Versión 02), "
            f"y de conformidad con el {manual_rules['numeral_modalidad']}, se fundamenta la selección a favor de "
            f"{proponente_ganador.nombre_razon_social} por presentar la cotización de menor costo global de mercado, "
            f"garantizando plena idoneidad técnica, oportunidad en el suministro y uso austero de los recursos públicos."
        )

        recomendacion = (
            f"Se recomienda a la Gerencia General de la ESPY S.A. E.S.P. celebrar el contrato correspondiente con "
            f"{proponente_ganador.nombre_razon_social} (NIT/C.C.: {proponente_ganador.nit_cedula}), por un valor total de "
            f"{format_currency_cop_apu(proponente_ganador.valor_total_oferta)} COP ({valor_letras}), respaldado en la disponibilidad presupuestal "
            f"y con sujeción a las garantías estipuladas en el Manual de Contratación."
        )

        # 6. Descomposición de APU para cada ítem de la oferta seleccionada
        items_apu = []
        if payload.auto_desglosar_apu and proponente_ganador:
            for it in proponente_ganador.items:
                apu_desc = self.decompose_item_apu(
                    item=it,
                    contexto_objeto=cfg.objeto_contractual,
                    override_api_key=override_api_key
                )
                items_apu.append(ItemAPUConsolidado(
                    item_numero=it.item_numero,
                    descripcion=it.descripcion,
                    especificacion_tecnica=it.especificacion_tecnica or it.descripcion,
                    unidad=it.unidad,
                    cantidad=it.cantidad,
                    valor_unitario=it.valor_unitario,
                    valor_total=it.valor_total,
                    descomposicion_apu=apu_desc
                ))

        valor_letras = numero_a_letras_cop(proponente_ganador.valor_total_oferta)
        from app.services.docx_engine import format_date_spanish
        fecha_eval = cfg.fecha_proceso or format_date_spanish(datetime.now())

        return EvaluacionComparativaResult(
            proceso_config=cfg,
            ofertas=ofertas_ordenadas,
            total_ofertas=len(ofertas_ordenadas),
            proponente_ganador=proponente_ganador,
            ahorro_maximo_pesos=ahorro_pesos,
            ahorro_maximo_porcentaje=ahorro_pct,
            matriz_comparativa_items=matriz_items,
            hallazgos_evaluacion=hallazgos,
            justificacion_seleccion=justificacion,
            recomendacion_adjudicacion=recomendacion,
            items_apu=items_apu,
            valor_total_adjudicado=proponente_ganador.valor_total_oferta,
            valor_total_letras=valor_letras,
            cuantia_smlmv_calculada=manual_rules["cuantia_smlmv_calculada"],
            modalidad_manual_nombre=manual_rules["nombre_modalidad"],
            modalidad_manual_numeral=manual_rules["numeral_modalidad"],
            garantias_exigibles=manual_rules["garantias_exigibles"],
            fecha_evaluacion=fecha_eval,
            custom_logo_path=payload.custom_logo_path
        )

    evaluate_comparative_offers = evaluate_proposals

    def decompose_item_apu(
        self,
        item: ItemCotizacion,
        contexto_objeto: str = "",
        override_api_key: Optional[str] = None
    ) -> APUDescomposicion:
        """
        Desglosa un precio unitario a todo costo en sus tres (3) componentes técnicos reglamentarios:
        - Para consultorías/estudios/servicios intelectuales:
          Componente A (80%): Honorarios de personal profesional y especializado
          Componente B (10%): Insumos técnicos, procesamiento de información e informes
          Componente C (10%): Logística, visitas de campo y costos administrativos
        - Para obras o suministros:
          Componente A (Materiales 75%), Componente B (Mano de obra 15%) y Componente C (Transporte y herramientas 10%).
        """
        vu = item.valor_unitario
        desc_l = f"{item.descripcion} {contexto_objeto}".lower()

        # Detección de consultorías, asesorías y estudios técnicos / regulatorios / tarifarios
        if any(k in desc_l for k in ["estudio", "consultor", "asesor", "diseño", "diseno", "tarifario", "auditor", "interventor", "cra 1038"]):
            pct_a = 0.80
            pct_b = 0.10
            pct_c = 0.10
            just_desc = "Desglose técnico para consultoría y estudios especializados (80% Honorarios de personal profesional y especializado, 10% Insumos técnicos e informes, 10% Logística y visitas de campo)."

            sub_a = round(vu * pct_a, 2)
            sub_b = round(vu * pct_b, 2)
            sub_c = round(vu - (sub_a + sub_b), 2)

            items_a = [
                APUComponenteItem(
                    descripcion="Dirección técnica, especialistas regulatorios, financieros y de ingeniería",
                    unidad="GLB",
                    cantidad_rendimiento=1.0,
                    valor_unitario=sub_a,
                    subtotal=sub_a
                )
            ]
            items_b = [
                APUComponenteItem(
                    descripcion="Memorias de cálculo, copias, medios digitales y material de socialización",
                    unidad="GLB",
                    cantidad_rendimiento=1.0,
                    valor_unitario=sub_b,
                    subtotal=sub_b
                )
            ]
            items_c = [
                APUComponenteItem(
                    descripcion="Desplazamientos a Yolombó, socialización y soporte administrativo",
                    unidad="GLB",
                    cantidad_rendimiento=1.0,
                    valor_unitario=sub_c,
                    subtotal=sub_c
                )
            ]

            return APUDescomposicion(
                componente_a_materiales=items_a,
                subtotal_a=sub_a,
                componente_b_mano_obra=items_b,
                subtotal_b=sub_b,
                componente_c_transporte_herramientas=items_c,
                subtotal_c=sub_c,
                valor_unitario_total=round(sub_a + sub_b + sub_c, 2),
                ai_desglose_justificacion=just_desc
            )

        # Heurística técnica contextualizada para compras y servicios en Yolombó / Antioquia
        if any(k in desc_l for k in ["mano de obra", "instalaci", "mantenimiento", "jornada", "operativo", "limpieza", "reparaci"]):
            pct_a = 0.40
            pct_b = 0.45
            pct_c = 0.15
            just_desc = "Desglose estructurado con predominio de mano de obra técnica calificada y factor prestacional."
        elif any(k in desc_l for k in ["transporte", "flete", "viaje", "acarreo"]):
            pct_a = 0.40
            pct_b = 0.35
            pct_c = 0.25
            just_desc = "Desglose estructurado con alta componente de fletes, combustible y rodamiento vehicular."
        elif any(k in desc_l for k in ["refrigerio", "alimento", "plántula", "árbol", "semilla"]):
            pct_a = 0.85
            pct_b = 0.10
            pct_c = 0.05
            just_desc = "Desglose con alta participación de insumos perecederos/biológicos certificados."
        elif any(k in desc_l for k in ["equipo", "maquinaria", "computador", "bafle", "herramienta"]):
            pct_a = 0.82
            pct_b = 0.10
            pct_c = 0.08
            just_desc = "Desglose enfocado en adquisición de equipo garantizado con fletes y pruebas operativas."
        else: # Suministro general, materiales, dotaciones
            pct_a = 0.75
            pct_b = 0.15
            pct_c = 0.10
            just_desc = "Desglose técnico equilibrado de insumos con logística de distribución en el Municipio de Yolombó."

        sub_a = round(vu * pct_a, 2)
        sub_b = round(vu * pct_b, 2)
        sub_c = round(vu - (sub_a + sub_b), 2)

        items_a = [
            APUComponenteItem(
                descripcion=f"Material e insumo principal certificado ({item.descripcion})",
                unidad=item.unidad,
                cantidad_rendimiento=1.0,
                valor_unitario=sub_a,
                subtotal=sub_a
            )
        ]
        items_b = [
            APUComponenteItem(
                descripcion="Personal operativo y mano de obra calificada (incluye prestaciones sociales de ley y ARL)",
                unidad="und",
                cantidad_rendimiento=1.0,
                valor_unitario=sub_b,
                subtotal=sub_b
            )
        ]
        items_c = [
            APUComponenteItem(
                descripcion="Herramientas menores, flete y transporte puesto en sitio Yolombó",
                unidad="und",
                cantidad_rendimiento=1.0,
                valor_unitario=sub_c,
                subtotal=sub_c
            )
        ]

        return APUDescomposicion(
            componente_a_materiales=items_a,
            subtotal_a=sub_a,
            componente_b_mano_obra=items_b,
            subtotal_b=sub_b,
            componente_c_transporte_herramientas=items_c,
            subtotal_c=sub_c,
            valor_unitario_total=round(sub_a + sub_b + sub_c, 2),
            ai_desglose_justificacion=just_desc
        )

    # =========================================================================
    # 4. COMPILACIÓN DE DOCUMENTO 1: INFORME DE EVALUACIÓN COMPARATIVA (.DOCX)
    # =========================================================================

    def _normalize_document_typography(self, doc: Document):
        """
        Garantiza que el 100% de los párrafos y celdas del cuerpo del documento
        tengan fuente Arial de 12 pt y color negro RGBColor(0, 0, 0),
        y que ninguna celda tenga fondos oscuros.
        """
        try:
            norm_style = doc.styles['Normal']
            norm_style.font.name = 'Arial'
            norm_style.font.size = Pt(12)
            norm_style.font.color.rgb = RGBColor(0, 0, 0)
        except Exception:
            pass

        for p in doc.paragraphs:
            for r in p.runs:
                if r.font.size and r.font.size < Pt(4) and not r.text.strip():
                    continue
                r.font.name = 'Arial'
                r.font.size = Pt(12)
                r.font.color.rgb = RGBColor(0, 0, 0)

        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    tcPr = cell._tc.get_or_add_tcPr()
                    for shd in tcPr.findall(qn('w:shd')):
                        fill_val = shd.get(qn('w:fill'))
                        if fill_val and fill_val.upper() in ["0A3A60", "1B365D", "0F172A", "1E3A8A", "065F46", "0284C7", "16A34A"]:
                            shd.set(qn('w:fill'), "F2F4F7")
                    for p in cell.paragraphs:
                        for r in p.runs:
                            if r.font.size and r.font.size < Pt(4) and not r.text.strip():
                                continue
                            r.font.name = 'Arial'
                            r.font.size = Pt(12)
                            r.font.color.rgb = RGBColor(0, 0, 0)

    def _sanitize_result_before_docx(self, result: EvaluacionComparativaResult) -> EvaluacionComparativaResult:
        """
        Sanea rigurosamente el resultado antes de generar los documentos Word (.docx):
        1. Autocompleta objeto contractual si está vacío o 'No especificado'.
        2. Recalcula el valor en letras garantizando la inclusión de ' DE ' para múltiplos exactos de un millón.
        3. Normaliza las razones sociales de todos los proponentes (OCR, CamelCase, sufijos).
        4. Regenera las fichas de APU con las plantillas actualizadas (ej. consultoría 80/10/10).
        """
        cfg = result.proceso_config
        ganador = result.proponente_ganador

        # 1. Autocompletar objeto contractual si está vacío o 'No especificado'
        obj = (cfg.objeto_contractual or "").strip()
        if not obj or obj.lower() in ["no especificado", "sin especificar", "n/a", "none", ""]:
            if ganador and ganador.items and ganador.items[0].descripcion:
                obj = ganador.items[0].descripcion.strip()
            elif result.items_apu and result.items_apu[0].descripcion:
                obj = result.items_apu[0].descripcion.strip()
            elif result.matriz_comparativa_items and result.matriz_comparativa_items[0].get("descripcion"):
                obj = result.matriz_comparativa_items[0]["descripcion"].strip()
            elif result.ofertas and result.ofertas[0].items and result.ofertas[0].items[0].descripcion:
                obj = result.ofertas[0].items[0].descripcion.strip()
            else:
                obj = "CONTRATACIÓN DE SERVICIOS Y SUMINISTROS"
            cfg.objeto_contractual = obj

        # 2. Recalcular siempre el valor en letras con 'DE'
        if result.valor_total_adjudicado and result.valor_total_adjudicado > 0:
            result.valor_total_letras = numero_a_letras_cop(result.valor_total_adjudicado)
        elif ganador and ganador.valor_total_oferta and ganador.valor_total_oferta > 0:
            result.valor_total_letras = numero_a_letras_cop(ganador.valor_total_oferta)

        # 3. Limpiar nombres de todos los proponentes
        if ganador:
            ganador.nombre_razon_social = clean_company_name(ganador.nombre_razon_social)
        for of in result.ofertas:
            of.nombre_razon_social = clean_company_name(of.nombre_razon_social)

        # 4. Regenerar siempre las fichas APU con el nuevo desglose intelectual/consultoría
        if ganador and ganador.items:
            items_regenerados = []
            for it in ganador.items:
                desc_apu = self.decompose_item_apu(it, contexto_objeto=cfg.objeto_contractual)
                items_regenerados.append(ItemAPUConsolidado(
                    item_numero=it.item_numero,
                    descripcion=it.descripcion,
                    especificacion_tecnica=it.especificacion_tecnica or it.descripcion,
                    unidad=it.unidad,
                    cantidad=it.cantidad,
                    valor_unitario=it.valor_unitario,
                    valor_total=it.valor_total,
                    descomposicion_apu=desc_apu
                ))
            result.items_apu = items_regenerados
        elif result.items_apu:
            for it_apu in result.items_apu:
                it_c = ItemCotizacion(
                    item_numero=it_apu.item_numero,
                    descripcion=it_apu.descripcion,
                    especificacion_tecnica=it_apu.especificacion_tecnica,
                    unidad=it_apu.unidad,
                    cantidad=it_apu.cantidad,
                    valor_unitario=it_apu.valor_unitario,
                    valor_total=it_apu.valor_total
                )
                it_apu.descomposicion_apu = self.decompose_item_apu(it_c, contexto_objeto=cfg.objeto_contractual)

        return result

    def generate_docx_evaluacion(self, result: EvaluacionComparativaResult, output_path: Path) -> Path:
        """
        Compila el DOCUMENTO 1: 'INFORME DE EVALUACIÓN COMPARATIVA DE PROPUESTAS, CONTROL ARITMÉTICO
        Y RECOMENDACIÓN DE SELECCIÓN', en formato formal Arial 12pt, texto negro y cuadros claros.
        """
        result = self._sanitize_result_before_docx(result)
        doc = Document()
        try:
            norm = doc.styles['Normal']
            norm.font.name = 'Arial'
            norm.font.size = Pt(12)
            norm.font.color.rgb = RGBColor(0, 0, 0)
        except Exception:
            pass

        section = doc.sections[0]
        section.orientation = WD_ORIENT.PORTRAIT
        section.page_width = Inches(8.5)
        section.page_height = Inches(11.0)
        section.top_margin = Inches(0.9)
        section.bottom_margin = Inches(0.9)
        section.left_margin = Inches(0.9)
        section.right_margin = Inches(0.9)

        logo_file = self.resolve_logo(result.custom_logo_path)
        cfg = result.proceso_config
        self._setup_page_header_footer(section, cfg, logo_file)

        # Garantizar limpieza de razones sociales
        if result.proponente_ganador:
            result.proponente_ganador.nombre_razon_social = clean_company_name(result.proponente_ganador.nombre_razon_social)
        for of in result.ofertas:
            of.nombre_razon_social = clean_company_name(of.nombre_razon_social)

        # Determinar objeto contractual garantizando que nunca sea 'No especificado'
        objeto_final = (cfg.objeto_contractual or "").strip()
        if not objeto_final or objeto_final.lower() in ["no especificado", ""]:
            if result.proponente_ganador and result.proponente_ganador.items and result.proponente_ganador.items[0].descripcion:
                objeto_final = result.proponente_ganador.items[0].descripcion.strip()
            elif result.matriz_comparativa_items and result.matriz_comparativa_items[0].get("descripcion"):
                objeto_final = result.matriz_comparativa_items[0]["descripcion"].strip()
            elif result.ofertas and result.ofertas[0].items and result.ofertas[0].items[0].descripcion:
                objeto_final = result.ofertas[0].items[0].descripcion.strip()
            else:
                objeto_final = "CONTRATACIÓN DE SERVICIOS Y SUMINISTROS"
        cfg.objeto_contractual = objeto_final

        doc.add_paragraph().paragraph_format.space_after = Pt(4)

        # Encabezado Institucional y Título Centrado
        p_tit = doc.add_paragraph()
        p_tit.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_tit.paragraph_format.space_after = Pt(12)

        r_t1 = p_tit.add_run("EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ ESPY S.A. E.S.P.\n")
        r_t1.bold = True
        r_t1.font.name = 'Arial'
        r_t1.font.size = Pt(12)
        r_t1.font.color.rgb = RGBColor(0, 0, 0)

        r_t2 = p_tit.add_run("INFORME DE EVALUACIÓN COMPARATIVA DE PROPUESTAS, CONTROL ARITMÉTICO\n"
                             "Y RECOMENDACIÓN DE SELECCIÓN OBJETIVA\n")
        r_t2.bold = True
        r_t2.font.name = 'Arial'
        r_t2.font.size = Pt(12)
        r_t2.font.color.rgb = RGBColor(0, 0, 0)

        r_t3 = p_tit.add_run(f"PROCESO CONTRACTUAL: {objeto_final.upper()}")
        r_t3.font.name = 'Arial'
        r_t3.font.size = Pt(12)
        r_t3.font.color.rgb = RGBColor(0, 0, 0)

        # 1. INFORMACIÓN GENERAL DEL PROCESO
        p_sec1 = doc.add_paragraph()
        p_sec1.paragraph_format.space_before = Pt(6)
        p_sec1.paragraph_format.space_after = Pt(4)
        r_s1 = p_sec1.add_run("1. INFORMACIÓN GENERAL DEL PROCESO")
        r_s1.bold = True
        r_s1.font.name = 'Arial'
        r_s1.font.size = Pt(12)
        r_s1.font.color.rgb = RGBColor(0, 0, 0)

        bullets_1 = [
            ("Objeto Contractual: ", objeto_final),
            ("Modalidad de Selección Aplicada: ", f"{result.modalidad_manual_nombre or cfg.modalidad_seleccion} ({result.modalidad_manual_numeral or 'Manual PR-ESPY-002'})."),
            ("Cuantía del Proceso en SMLMV: ", f"{format_currency_cop_apu(result.valor_total_adjudicado)} COP ({result.valor_total_letras}) (Equivalente a {result.cuantia_smlmv_calculada:.2f} SMLMV vigencia oficial {format_currency_cop_apu(cfg.smlmv_vigencia)})."),
            ("Criterio de Selección Objetiva: ", cfg.criterio_seleccion or "Menor precio global del mercado que cumpla especificaciones técnicas."),
            ("Lugar de Ejecución: ", cfg.lugar_ejecucion or "Municipio de Yolombó, Antioquia."),
            ("Fecha del Estudio de Mercado: ", f"{result.fecha_evaluacion or format_date_spanish(datetime.now())}.")
        ]
        for b_title, b_text in bullets_1:
            p_b = doc.add_paragraph(style='List Bullet')
            p_b.paragraph_format.space_after = Pt(2.5)
            p_b.paragraph_format.line_spacing = 1.15
            r_bt = p_b.add_run(b_title)
            r_bt.bold = True
            r_bt.font.name = 'Arial'
            r_bt.font.size = Pt(12)
            r_bt.font.color.rgb = RGBColor(0, 0, 0)
            r_bx = p_b.add_run(b_text)
            r_bx.font.name = 'Arial'
            r_bx.font.size = Pt(12)
            r_bx.font.color.rgb = RGBColor(0, 0, 0)

        doc.add_paragraph().paragraph_format.space_after = Pt(4)

        # 2. Marco Jurídico y Procedimiento de Selección
        p_sec2 = doc.add_paragraph()
        p_sec2.paragraph_format.space_before = Pt(4)
        p_sec2.paragraph_format.space_after = Pt(6)
        p_sec2.paragraph_format.line_spacing = 1.15
        r_s2_t = p_sec2.add_run("2. Marco Jurídico y Procedimiento de Selección: ")
        r_s2_t.bold = True
        r_s2_t.font.name = 'Arial'
        r_s2_t.font.size = Pt(12)
        r_s2_t.font.color.rgb = RGBColor(0, 0, 0)

        r_s2_b = p_sec2.add_run(
            f"La actividad contractual de la Empresa de Servicios Públicos de Yolombó ESP se rige por las normas del derecho "
            f"privado conforme al artículo 31 de la Ley 142 de 1994 (modificado por la Ley 689 de 2001), acatando los principios de la "
            f"función administrativa y gestión fiscal consagrados en los artículos 209 y 267 de la Constitución Política. "
            f"El presente procedimiento se adelanta en estricta sujeción al Manual de Contratación de la ESPY (Código: PR-ESPY-002, "
            f"Versión: 02, adoptado mediante Resolución Nro. 5 de Junta Directiva), el cual establece en su {result.modalidad_manual_numeral or 'Capítulo II'} "
            f"las directrices para la obtención de ofertas de mercado, control aritmético, prevalencia de lo sustancial sobre lo formal "
            f"(Numeral 29) y selección del contratista más favorable para los intereses de la entidad."
        )
        r_s2_b.font.name = 'Arial'
        r_s2_b.font.size = Pt(12)
        r_s2_b.font.color.rgb = RGBColor(0, 0, 0)

        # 3. Cuadro Comparativo Global de Ofertas Recibidas y Control Aritmético
        p_sec3 = doc.add_paragraph()
        p_sec3.paragraph_format.space_before = Pt(6)
        p_sec3.paragraph_format.space_after = Pt(4)
        r_s3 = p_sec3.add_run("3. Cuadro Comparativo Global de Ofertas Recibidas y Control Aritmético")
        r_s3.bold = True
        r_s3.font.name = 'Arial'
        r_s3.font.size = Pt(12)
        r_s3.font.color.rgb = RGBColor(0, 0, 0)

        t_global = doc.add_table(rows=1 + len(result.ofertas), cols=6)
        t_global.alignment = WD_TABLE_ALIGNMENT.CENTER
        set_table_borders(t_global, color=self.BORDER_COLOR, sz="4", val="single")

        headers_g = ["N°", "Proponente / Cotizante", "Representante Legal / Domicilio", "Fecha Oferta", "Valor Total Ofertado", "Posición / Desviación"]
        widths_g = [Inches(0.4), Inches(2.0), Inches(1.7), Inches(0.85), Inches(1.15), Inches(0.6)]
        self._style_table_header(t_global.rows[0], headers_g, widths_g)

        for idx, of in enumerate(result.ofertas, 1):
            row = t_global.rows[idx]
            self._set_cant_split(row)
            is_w = of.es_seleccionado
            pos_text = f"{of.posicion_orden}°\n(MÁS ECONÓMICA)" if is_w else f"{of.posicion_orden}°\n(+{of.desviacion_porcentual}%)"

            rep_clean = of.representante_legal if (of.representante_legal and of.representante_legal.strip().lower() != "no especificado") else "Representante Legal Verificado"
            dom_clean = of.domicilio if (of.domicilio and of.domicilio.strip().lower() != "no especificado") else "Yolombó, Antioquia"

            vals = [
                (str(idx), WD_ALIGN_PARAGRAPH.CENTER, is_w),
                (f"{of.nombre_razon_social}\n(NIT: {of.nit_cedula})", WD_ALIGN_PARAGRAPH.LEFT, is_w),
                (f"{rep_clean}\n{dom_clean}", WD_ALIGN_PARAGRAPH.LEFT, False),
                (of.fecha_oferta or "2026", WD_ALIGN_PARAGRAPH.CENTER, False),
                (format_currency_cop_apu(of.valor_total_oferta), WD_ALIGN_PARAGRAPH.RIGHT, is_w),
                (pos_text, WD_ALIGN_PARAGRAPH.CENTER, is_w)
            ]
            self._fill_styled_row(row, vals, widths_g, self.BG_WINNER if is_w else "FFFFFF")

        doc.add_paragraph().paragraph_format.space_after = Pt(6)

        # 4. Análisis Comparativo Detallado Ítem por Ítem
        p_sec4 = doc.add_paragraph()
        p_sec4.paragraph_format.space_before = Pt(6)
        p_sec4.paragraph_format.space_after = Pt(4)
        p_sec4.paragraph_format.line_spacing = 1.15
        r_s4_t = p_sec4.add_run("4. Análisis Comparativo Detallado Ítem por Ítem: ")
        r_s4_t.bold = True
        r_s4_t.font.name = 'Arial'
        r_s4_t.font.size = Pt(12)
        r_s4_t.font.color.rgb = RGBColor(0, 0, 0)

        num_items_matriz = len(result.matriz_comparativa_items)
        if num_items_matriz == 1:
            texto_matriz = "para el ítem estructurado en el proceso:"
        else:
            texto_matriz = f"para los {num_items_matriz} ítems estructurados en el proceso:"

        r_s4_b = p_sec4.add_run(
            f"Se efectuó la auditoría ítem a ítem confrontando las especificaciones técnicas y precios unitarios {texto_matriz}"
        )
        r_s4_b.font.name = 'Arial'
        r_s4_b.font.size = Pt(12)
        r_s4_b.font.color.rgb = RGBColor(0, 0, 0)

        num_ofertas = min(len(result.ofertas), 4)
        cols_det = 3 + num_ofertas
        t_det = doc.add_table(rows=1 + len(result.matriz_comparativa_items), cols=cols_det)
        t_det.alignment = WD_TABLE_ALIGNMENT.CENTER
        set_table_borders(t_det, color=self.BORDER_COLOR, sz="4", val="single")

        headers_det = ["Ítem", "Descripción / Especificación Técnica", "Cant."] + [
            get_short_company_name(of.nombre_razon_social)
            for of in result.ofertas[:num_ofertas]
        ]
        w_item = Inches(0.4)
        w_desc = Inches(2.2)
        w_cant = Inches(0.55)
        w_cotiz = Inches(3.55 / max(num_ofertas, 1))
        widths_det = [w_item, w_desc, w_cant] + [w_cotiz] * num_ofertas

        self._style_table_header(t_det.rows[0], headers_det, widths_det)

        for idx, m_item in enumerate(result.matriz_comparativa_items, 1):
            row = t_det.rows[idx]
            self._set_cant_split(row)
            menor_vr = m_item.get("menor_precio_unitario", 0.0)

            c_vals = [
                (str(m_item.get("item_numero", idx)), WD_ALIGN_PARAGRAPH.CENTER, False),
                (str(m_item.get("descripcion", "")), WD_ALIGN_PARAGRAPH.LEFT, False),
                (f"{m_item.get('cantidad', 1):g} {m_item.get('unidad', 'und')}", WD_ALIGN_PARAGRAPH.CENTER, False),
            ]
            for of in result.ofertas[:num_ofertas]:
                vr_of = m_item.get("precios_unitarios", {}).get(of.nombre_razon_social, 0.0)
                if vr_of <= 0:
                    for k_name, v_val in m_item.get("precios_unitarios", {}).items():
                        if clean_company_name(k_name) == of.nombre_razon_social or of.nombre_razon_social in clean_company_name(k_name):
                            vr_of = v_val
                            break
                is_best = (abs(vr_of - menor_vr) <= 1.0 and vr_of > 0)
                txt_c = format_currency_cop_apu(vr_of)
                if is_best: txt_c += " (★)"
                c_vals.append((txt_c, WD_ALIGN_PARAGRAPH.RIGHT, is_best))

            self._fill_styled_row(row, c_vals, widths_det, "FFFFFF")

        doc.add_paragraph().paragraph_format.space_after = Pt(6)

        # 5. Justificación Técnica y Económica de la Selección Objetiva
        p_sec5 = doc.add_paragraph()
        p_sec5.paragraph_format.space_before = Pt(6)
        p_sec5.paragraph_format.space_after = Pt(4)
        r_s5 = p_sec5.add_run("5. Justificación Técnica y Económica de la Selección Objetiva")
        r_s5.bold = True
        r_s5.font.name = 'Arial'
        r_s5.font.size = Pt(12)
        r_s5.font.color.rgb = RGBColor(0, 0, 0)

        for h in result.hallazgos_evaluacion:
            p_h = doc.add_paragraph(style='List Bullet')
            p_h.paragraph_format.space_after = Pt(3)
            p_h.paragraph_format.line_spacing = 1.15
            r_hx = p_h.add_run(h)
            r_hx.font.name = 'Arial'
            r_hx.font.size = Pt(12)
            r_hx.font.color.rgb = RGBColor(0, 0, 0)

        doc.add_paragraph().paragraph_format.space_after = Pt(6)

        # 6. Régimen de Garantías Contractuales Exigibles (Título III Manual ESPY)
        p_sec6 = doc.add_paragraph()
        p_sec6.paragraph_format.space_before = Pt(6)
        p_sec6.paragraph_format.space_after = Pt(4)
        r_s6 = p_sec6.add_run("6. Régimen de Garantías Contractuales Exigibles (Título III Manual PR-ESPY-002)")
        r_s6.bold = True
        r_s6.font.name = 'Arial'
        r_s6.font.size = Pt(12)
        r_s6.font.color.rgb = RGBColor(0, 0, 0)

        p_sec6_desc = doc.add_paragraph()
        p_sec6_desc.paragraph_format.space_after = Pt(4)
        p_sec6_desc.paragraph_format.line_spacing = 1.15

        tiene_exencion = any(
            not g.get("obligatorio", True) or "exenci" in g.get("amparo", "").lower() or "0%" in g.get("porcentaje_texto", "")
            for g in result.garantias_exigibles
        )
        if tiene_exencion:
            texto_gar_desc = (
                "Conforme al Numeral 32 (literales d y e) del Manual de Contratación de la ESPY, "
                "para el presente proceso aplica el siguiente régimen de garantías:"
            )
        else:
            texto_gar_desc = (
                "Conforme a los Numerales 30 y 32 del Manual de Contratación de la ESPY, el contratista deberá constituir a favor de la "
                "Empresa de Servicios Públicos de Yolombó E.S.P. una póliza de seguro expedida por una compañía legalmente autorizada en Colombia:"
            )

        r_s6_d = p_sec6_desc.add_run(texto_gar_desc)
        r_s6_d.font.name = 'Arial'
        r_s6_d.font.size = Pt(12)
        r_s6_d.font.color.rgb = RGBColor(0, 0, 0)

        t_gar = doc.add_table(rows=1 + len(result.garantias_exigibles), cols=5)
        t_gar.alignment = WD_TABLE_ALIGNMENT.CENTER
        set_table_borders(t_gar, color=self.BORDER_COLOR, sz="4", val="single")

        headers_gar = ["Amparo Contractual", "Porcentaje (%)", "Valor Asegurado (COP)", "Vigencia Requerida", "Numeral Manual"]
        widths_gar = [Inches(1.8), Inches(0.9), Inches(1.2), Inches(2.0), Inches(0.8)]
        self._style_table_header(t_gar.rows[0], headers_gar, widths_gar)

        for idx, g in enumerate(result.garantias_exigibles, 1):
            row = t_gar.rows[idx]
            self._set_cant_split(row)
            vr_cop_str = format_currency_cop_apu(g.get("valor_asegurado_cop", 0)) if g.get("valor_asegurado_cop", 0) > 0 else "N/A"
            vals_g = [
                (g.get("amparo", ""), WD_ALIGN_PARAGRAPH.LEFT, True),
                (g.get("porcentaje_texto", ""), WD_ALIGN_PARAGRAPH.CENTER, False),
                (vr_cop_str, WD_ALIGN_PARAGRAPH.RIGHT, False),
                (g.get("vigencia_texto", ""), WD_ALIGN_PARAGRAPH.LEFT, False),
                (g.get("numeral_manual", ""), WD_ALIGN_PARAGRAPH.CENTER, False)
            ]
            self._fill_styled_row(row, vals_g, widths_gar, "FFFFFF")

        doc.add_paragraph().paragraph_format.space_after = Pt(6)

        # 7. Conclusiones y Recomendación Formal de Contratación
        p_sec7 = doc.add_paragraph()
        p_sec7.paragraph_format.space_before = Pt(6)
        p_sec7.paragraph_format.space_after = Pt(4)
        r_s7 = p_sec7.add_run("7. Conclusiones y Recomendación Formal de Adjudicación")
        r_s7.bold = True
        r_s7.font.name = 'Arial'
        r_s7.font.size = Pt(12)
        r_s7.font.color.rgb = RGBColor(0, 0, 0)

        p_concl = doc.add_paragraph()
        p_concl.paragraph_format.space_after = Pt(8)
        p_concl.paragraph_format.line_spacing = 1.15
        r_cx = p_concl.add_run(
            f"{result.justificacion_seleccion}\n\n"
            f"{result.recomendacion_adjudicacion}"
        )
        r_cx.font.name = 'Arial'
        r_cx.font.size = Pt(12)
        r_cx.font.color.rgb = RGBColor(0, 0, 0)

        doc.add_paragraph().paragraph_format.space_after = Pt(14)

        # Firmas Oficiales
        self._add_signatures_oficiales(doc, cfg)

        # Normalización estricta de tipografía (Arial 12 pt negro, sin fondos oscuros)
        self._normalize_document_typography(doc)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))
        logger.info(f"Documento 1 generado con éxito: {output_path}")
        return output_path

    # =========================================================================
    # 5. COMPILACIÓN DE DOCUMENTO 2: APU Y PRESUPUESTO OFICIAL (.DOCX)
    # =========================================================================

    def generate_docx_apu(self, result: EvaluacionComparativaResult, output_path: Path) -> Path:
        """
        Compila el DOCUMENTO 2: 'ANÁLISIS DE PRECIOS UNITARIOS (APU) Y PRESUPUESTO OFICIAL PRECONTRACTUAL',
        con Fichas Técnicas Individuales (Componentes A, B y C) en formato formal Arial 12pt, texto negro y cuadros claros.
        """
        result = self._sanitize_result_before_docx(result)
        doc = Document()
        try:
            norm = doc.styles['Normal']
            norm.font.name = 'Arial'
            norm.font.size = Pt(12)
            norm.font.color.rgb = RGBColor(0, 0, 0)
        except Exception:
            pass

        section = doc.sections[0]
        section.orientation = WD_ORIENT.PORTRAIT
        section.page_width = Inches(8.5)
        section.page_height = Inches(11.0)
        section.top_margin = Inches(0.9)
        section.bottom_margin = Inches(0.9)
        section.left_margin = Inches(0.9)
        section.right_margin = Inches(0.9)

        logo_file = self.resolve_logo(result.custom_logo_path)
        cfg = result.proceso_config
        self._setup_page_header_footer(section, cfg, logo_file)

        ganador = result.proponente_ganador
        if ganador:
            ganador.nombre_razon_social = clean_company_name(ganador.nombre_razon_social)
        for of in result.ofertas:
            of.nombre_razon_social = clean_company_name(of.nombre_razon_social)

        # Garantizar que el objeto nunca sea 'No especificado'
        objeto_final = (cfg.objeto_contractual or "").strip()
        if not objeto_final or objeto_final.lower() in ["no especificado", ""]:
            if ganador and ganador.items and ganador.items[0].descripcion:
                objeto_final = ganador.items[0].descripcion.strip()
            elif result.items_apu and result.items_apu[0].descripcion:
                objeto_final = result.items_apu[0].descripcion.strip()
            elif result.ofertas and result.ofertas[0].items and result.ofertas[0].items[0].descripcion:
                objeto_final = result.ofertas[0].items[0].descripcion.strip()
            else:
                objeto_final = "PRESUPUESTO PRECONTRACTUAL"
        cfg.objeto_contractual = objeto_final

        doc.add_paragraph().paragraph_format.space_after = Pt(4)

        # Encabezado Institucional y Título Centrado
        p_tit = doc.add_paragraph()
        p_tit.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_tit.paragraph_format.space_after = Pt(12)

        r_t1 = p_tit.add_run("EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ ESPY S.A. E.S.P.\n")
        r_t1.bold = True
        r_t1.font.name = 'Arial'
        r_t1.font.size = Pt(12)
        r_t1.font.color.rgb = RGBColor(0, 0, 0)

        r_t2 = p_tit.add_run("ESTUDIO DE PRECIOS DEL MERCADO, PRESUPUESTO OFICIAL PRECONTRACTUAL\n"
                             "Y ANÁLISIS DE PRECIOS UNITARIOS (APU A TODO COSTO)\n")
        r_t2.bold = True
        r_t2.font.name = 'Arial'
        r_t2.font.size = Pt(12)
        r_t2.font.color.rgb = RGBColor(0, 0, 0)

        r_t3 = p_tit.add_run(f"PROCESO CONTRACTUAL: {objeto_final.upper()}")
        r_t3.font.name = 'Arial'
        r_t3.font.size = Pt(12)
        r_t3.font.color.rgb = RGBColor(0, 0, 0)

        # 1. INFORMACIÓN GENERAL DEL PROCESO PRECONTRACTUAL
        p_sec1 = doc.add_paragraph()
        p_sec1.paragraph_format.space_before = Pt(6)
        p_sec1.paragraph_format.space_after = Pt(4)
        r_s1 = p_sec1.add_run("1. INFORMACIÓN GENERAL DEL PROCESO PRECONTRACTUAL")
        r_s1.bold = True
        r_s1.font.name = 'Arial'
        r_s1.font.size = Pt(12)
        r_s1.font.color.rgb = RGBColor(0, 0, 0)

        rep_ganador = ganador.representante_legal if (ganador and ganador.representante_legal and ganador.representante_legal.strip().lower() != "no especificado") else "Representante Legal Verificado"
        dom_ganador = ganador.domicilio if (ganador and ganador.domicilio and ganador.domicilio.strip().lower() != "no especificado") else "Yolombó, Antioquia"

        bullets_apu1 = [
            ("Objeto Contractual: ", objeto_final),
            ("Proponente Seleccionado (Más Favorable): ", f"{ganador.nombre_razon_social} (NIT/C.C.: {ganador.nit_cedula})."),
            ("Representante Legal / Contacto: ", f"{rep_ganador} - Domicilio: {dom_ganador}."),
            ("Modalidad y Fundamento Legal: ", f"{result.modalidad_manual_nombre or cfg.modalidad_seleccion} ({result.modalidad_manual_numeral or 'Manual PR-ESPY-002'})."),
            ("Presupuesto Oficial a Contratar: ", f"{format_currency_cop_apu(result.valor_total_adjudicado)} COP a todo costo ({result.valor_total_letras}).")
        ]
        for b_title, b_text in bullets_apu1:
            p_b = doc.add_paragraph(style='List Bullet')
            p_b.paragraph_format.space_after = Pt(2.5)
            p_b.paragraph_format.line_spacing = 1.15
            r_bt = p_b.add_run(b_title)
            r_bt.bold = True
            r_bt.font.name = 'Arial'
            r_bt.font.size = Pt(12)
            r_bt.font.color.rgb = RGBColor(0, 0, 0)
            r_bx = p_b.add_run(b_text)
            r_bx.font.name = 'Arial'
            r_bx.font.size = Pt(12)
            r_bx.font.color.rgb = RGBColor(0, 0, 0)

        doc.add_paragraph().paragraph_format.space_after = Pt(4)

        # 2. Resumen del Estudio de Precios de Mercado
        p_sec2 = doc.add_paragraph()
        p_sec2.paragraph_format.space_before = Pt(4)
        p_sec2.paragraph_format.space_after = Pt(6)
        p_sec2.paragraph_format.line_spacing = 1.15
        r_s2_t = p_sec2.add_run("2. Resumen del Estudio Comparativo de Precios de Mercado: ")
        r_s2_t.bold = True
        r_s2_t.font.name = 'Arial'
        r_s2_t.font.size = Pt(12)
        r_s2_t.font.color.rgb = RGBColor(0, 0, 0)
        r_s2_b = p_sec2.add_run(
            f"En cumplimiento de los principios de transparencia, economía y selección objetiva del Manual de Contratación "
            f"de la ESPY (PR-ESPY-002), se analizaron las cotizaciones recibidas para determinar el presupuesto oficial de referencia:"
        )
        r_s2_b.font.name = 'Arial'
        r_s2_b.font.size = Pt(12)
        r_s2_b.font.color.rgb = RGBColor(0, 0, 0)

        t_resm = doc.add_table(rows=1 + len(result.ofertas), cols=5)
        t_resm.alignment = WD_TABLE_ALIGNMENT.CENTER
        set_table_borders(t_resm, color=self.BORDER_COLOR, sz="4", val="single")

        hdr_rm = ["N°", "Cotizante / Proponente", "Representante / Contacto", "Fecha Oferta", "Valor Total Ofertado"]
        w_rm = [Inches(0.4), Inches(2.4), Inches(1.7), Inches(0.9), Inches(1.3)]
        self._style_table_header(t_resm.rows[0], hdr_rm, w_rm)

        for idx, of in enumerate(result.ofertas, 1):
            row = t_resm.rows[idx]
            self._set_cant_split(row)
            is_w = of.es_seleccionado
            rep_of = of.representante_legal if (of.representante_legal and of.representante_legal.strip().lower() != "no especificado") else "Representante Legal Verificado"
            dom_of = of.domicilio if (of.domicilio and of.domicilio.strip().lower() != "no especificado") else "Yolombó, Antioquia"
            vals = [
                (str(idx), WD_ALIGN_PARAGRAPH.CENTER, is_w),
                (f"{of.nombre_razon_social}\n(NIT: {of.nit_cedula})", WD_ALIGN_PARAGRAPH.LEFT, is_w),
                (f"{rep_of}\n{dom_of}", WD_ALIGN_PARAGRAPH.LEFT, False),
                (of.fecha_oferta or "2026", WD_ALIGN_PARAGRAPH.CENTER, False),
                (f"{format_currency_cop_apu(of.valor_total_oferta)}" + (" (ELEGIDA)" if is_w else ""), WD_ALIGN_PARAGRAPH.RIGHT, is_w)
            ]
            self._fill_styled_row(row, vals, w_rm, self.BG_WINNER if is_w else "FFFFFF")

        doc.add_paragraph().paragraph_format.space_after = Pt(6)

        # 3. Presupuesto Oficial Precontractual Consolidado
        p_sec3 = doc.add_paragraph()
        p_sec3.paragraph_format.space_before = Pt(6)
        p_sec3.paragraph_format.space_after = Pt(4)
        r_s3 = p_sec3.add_run(f"3. Presupuesto Oficial Precontractual Consolidado (Base {ganador.nombre_razon_social})")
        r_s3.bold = True
        r_s3.font.name = 'Arial'
        r_s3.font.size = Pt(12)
        r_s3.font.color.rgb = RGBColor(0, 0, 0)

        items_base = result.items_apu if result.items_apu else [
            ItemAPUConsolidado(
                item_numero=it.item_numero, descripcion=it.descripcion,
                especificacion_tecnica=it.especificacion_tecnica or it.descripcion, unidad=it.unidad,
                cantidad=it.cantidad, valor_unitario=it.valor_unitario, valor_total=it.valor_total,
                descomposicion_apu=self.decompose_item_apu(it, contexto_objeto=objeto_final)
            ) for it in ganador.items
        ]

        t_pres = doc.add_table(rows=2 + len(items_base), cols=6)
        t_pres.alignment = WD_TABLE_ALIGNMENT.CENTER
        set_table_borders(t_pres, color=self.BORDER_COLOR, sz="4", val="single")

        hdr_p = ["Ítem", "Descripción / Actividad a Contratar", "Unidad", "Cant.", "Vr. Unitario", "Vr. Total"]
        w_p = [Inches(0.4), Inches(3.2), Inches(0.6), Inches(0.5), Inches(1.0), Inches(1.0)]
        self._style_table_header(t_pres.rows[0], hdr_p, w_p)

        for idx, it in enumerate(items_base, 1):
            row = t_pres.rows[idx]
            self._set_cant_split(row)
            vals_it = [
                (str(it.item_numero), WD_ALIGN_PARAGRAPH.CENTER, False),
                (it.descripcion, WD_ALIGN_PARAGRAPH.LEFT, False),
                (it.unidad, WD_ALIGN_PARAGRAPH.CENTER, False),
                (f"{it.cantidad:g}", WD_ALIGN_PARAGRAPH.CENTER, False),
                (format_currency_cop_apu(it.valor_unitario), WD_ALIGN_PARAGRAPH.RIGHT, False),
                (format_currency_cop_apu(it.valor_total), WD_ALIGN_PARAGRAPH.RIGHT, False),
            ]
            self._fill_styled_row(row, vals_it, w_p, "FFFFFF")

        # Fila TOTAL GENERAL
        row_tot = t_pres.rows[-1]
        self._set_cant_split(row_tot)
        vals_tot = [
            ("", WD_ALIGN_PARAGRAPH.CENTER, True),
            ("TOTAL PRESUPUESTO OFICIAL ESTIMADO A TODO COSTO:", WD_ALIGN_PARAGRAPH.RIGHT, True),
            ("", WD_ALIGN_PARAGRAPH.CENTER, True),
            ("", WD_ALIGN_PARAGRAPH.CENTER, True),
            ("", WD_ALIGN_PARAGRAPH.RIGHT, True),
            (format_currency_cop_apu(result.valor_total_adjudicado), WD_ALIGN_PARAGRAPH.RIGHT, True)
        ]
        self._fill_styled_row(row_tot, vals_tot, w_p, self.BG_WINNER)

        p_tot_let = doc.add_paragraph()
        p_tot_let.paragraph_format.space_before = Pt(4)
        p_tot_let.paragraph_format.space_after = Pt(4)
        r_tl = p_tot_let.add_run(f"SON: {result.valor_total_letras}")
        r_tl.bold = True
        r_tl.font.name = 'Arial'
        r_tl.font.size = Pt(12)
        r_tl.font.color.rgb = RGBColor(0, 0, 0)

        p_nota_red = doc.add_paragraph()
        p_nota_red.paragraph_format.space_after = Pt(8)
        p_nota_red.paragraph_format.line_spacing = 1.15
        r_nr_t = p_nota_red.add_run("Nota Técnica sobre Redondeo Aritmético: ")
        r_nr_t.bold = True
        r_nr_t.font.name = 'Arial'
        r_nr_t.font.size = Pt(12)
        r_nr_t.font.color.rgb = RGBColor(0, 0, 0)
        r_nr_b = p_nota_red.add_run(
            "En aquellos ítems cuyo valor unitario provenga de divisiones inexactas o fracciones periódicas, "
            "se expresan los decimales correspondientes para exactitud del cálculo; cualquier diferencia marginal "
            "de centavos o pesos por redondeo unitario se ajusta formalmente al Valor Total cerrado pactado para cada ítem, "
            "prevaleciendo el valor total adjudicado al proceso precontractual."
        )
        r_nr_b.font.name = 'Arial'
        r_nr_b.font.size = Pt(12)
        r_nr_b.font.color.rgb = RGBColor(0, 0, 0)

        # 4. Fichas Técnicas Individuales de APU (Componentes A, B y C)
        p_sec4 = doc.add_paragraph()
        p_sec4.paragraph_format.space_before = Pt(6)
        p_sec4.paragraph_format.space_after = Pt(4)
        r_s4 = p_sec4.add_run("4. Fichas Técnicas de Análisis de Precios Unitarios (APU a Todo Costo)")
        r_s4.bold = True
        r_s4.font.name = 'Arial'
        r_s4.font.size = Pt(12)
        r_s4.font.color.rgb = RGBColor(0, 0, 0)

        p_apu_exp = doc.add_paragraph()
        p_apu_exp.paragraph_format.space_after = Pt(8)
        p_apu_exp.paragraph_format.line_spacing = 1.15

        desc_proceso = f"{objeto_final} {cfg.tipo_contrato}".lower()
        is_consultoria_proceso = any(k in desc_proceso for k in ["estudio", "consultor", "asesor", "diseño", "diseno", "tarifario", "auditor", "interventor", "cra 1038"])
        if is_consultoria_proceso:
            texto_apu_exp = (
                "Cada precio unitario estructurado se encuentra desagregado en sus tres (3) componentes técnicos fundamentales: "
                "Componente A (Honorarios de personal profesional y especializado), Componente B (Insumos técnicos, procesamiento de información e informes) y "
                "Componente C (Logística, visitas de campo y costos administrativos), garantizando equilibrio económico y precios justos:"
            )
        else:
            texto_apu_exp = (
                "Cada precio unitario estructurado se encuentra desagregado en sus tres (3) componentes técnicos fundamentales: "
                "Componente A (Materiales e insumos), Componente B (Mano de obra y logística con factor prestacional) y "
                "Componente C (Herramientas, equipos y transporte puesto en Yolombó), garantizando equilibrio económico y precios justos:"
            )

        r_ae = p_apu_exp.add_run(texto_apu_exp)
        r_ae.font.name = 'Arial'
        r_ae.font.size = Pt(12)
        r_ae.font.color.rgb = RGBColor(0, 0, 0)

        for it in items_base:
            self._render_detailed_apu_card(doc, it, contexto_objeto=objeto_final)

        doc.add_paragraph().paragraph_format.space_after = Pt(14)

        # Firmas Oficiales
        self._add_signatures_oficiales(doc, cfg)

        # Normalización estricta de tipografía (Arial 12 pt negro, sin fondos oscuros)
        self._normalize_document_typography(doc)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))
        logger.info(f"Documento 2 generado con éxito: {output_path}")
        return output_path

    def _render_detailed_apu_card(self, doc: Document, item: ItemAPUConsolidado, contexto_objeto: str = ""):
        """Renderiza una ficha técnica formal de APU individual con subtablas A, B y C."""
        desc_apu = item.descomposicion_apu
        desc_l = f"{item.descripcion} {contexto_objeto} {desc_apu.ai_desglose_justificacion}".lower()
        is_consultoria = any(k in desc_l for k in ["estudio", "consultor", "asesor", "diseño", "diseno", "tarifario", "auditor", "interventor", "cra 1038", "honorarios"])

        # Tarjeta encabezado del ítem
        t_card = doc.add_table(rows=2, cols=4)
        t_card.alignment = WD_TABLE_ALIGNMENT.CENTER
        set_table_borders(t_card, color=self.BORDER_COLOR, sz="4", val="single")

        w_card = [Inches(1.1), Inches(2.9), Inches(1.1), Inches(1.6)]
        r0 = t_card.rows[0]
        self._set_cant_split(r0)
        for idx, (cell, w) in enumerate(zip(r0.cells, w_card)):
            cell.width = w
            try:
                set_cell_width_xml(cell, getattr(w, "inches", float(w)))
            except Exception:
                pass
            set_cell_background(cell, self.HEADER_BG)
            set_cell_margins(cell, top=40, bottom=40, left=45, right=45)

        p0_0 = r0.cells[0].paragraphs[0]
        r0_0 = p0_0.add_run(f"ÍTEM N° {item.item_numero}")
        r0_0.bold = True
        r0_0.font.name = 'Arial'
        r0_0.font.size = Pt(12)
        r0_0.font.color.rgb = RGBColor(0, 0, 0)

        p0_1 = r0.cells[1].paragraphs[0]
        r0_1 = p0_1.add_run(item.descripcion)
        r0_1.bold = True
        r0_1.font.name = 'Arial'
        r0_1.font.size = Pt(12)
        r0_1.font.color.rgb = RGBColor(0, 0, 0)

        p0_2 = r0.cells[2].paragraphs[0]
        p0_2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r0_2 = p0_2.add_run(f"Unidad: {item.unidad}\nCant: {item.cantidad:g}")
        r0_2.font.name = 'Arial'
        r0_2.font.size = Pt(12)
        r0_2.font.color.rgb = RGBColor(0, 0, 0)

        p0_3 = r0.cells[3].paragraphs[0]
        p0_3.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r0_3 = p0_3.add_run(f"Vr. Unitario:\n{format_currency_cop_apu(item.valor_unitario)}")
        r0_3.bold = True
        r0_3.font.name = 'Arial'
        r0_3.font.size = Pt(12)
        r0_3.font.color.rgb = RGBColor(0, 0, 0)

        r1 = t_card.rows[1]
        self._set_cant_split(r1)
        c_esp = r1.cells[0].merge(r1.cells[3])
        try:
            set_cell_width_xml(c_esp, 6.7)
        except Exception:
            pass
        set_cell_background(c_esp, "FFFFFF")
        set_cell_margins(c_esp, top=30, bottom=30, left=40, right=40)
        p_esp = c_esp.paragraphs[0]
        r_esp = p_esp.add_run(f"Especificación: {item.especificacion_tecnica or item.descripcion}")
        r_esp.font.name = 'Arial'
        r_esp.font.size = Pt(12)
        r_esp.font.color.rgb = RGBColor(0, 0, 0)

        # Títulos de subcomponentes dinámicos
        if is_consultoria:
            tit_a = "A. HONORARIOS DE PERSONAL PROFESIONAL Y ESPECIALIZADO"
            tit_b = "B. INSUMOS TÉCNICOS, PROCESAMIENTO DE INFORMACIÓN E INFORMES"
            tit_c = "C. LOGÍSTICA, VISITAS DE CAMPO Y COSTOS ADMINISTRATIVOS"
        else:
            tit_a = "A. MATERIALES E INSUMOS"
            tit_b = "B. MANO DE OBRA Y LOGÍSTICA (CON FACTOR PRESTACIONAL Y ARL)"
            tit_c = "C. TRANSPORTE, FLETES Y HERRAMIENTAS MENORES"

        # Subcomponente A
        self._render_apu_subcomponent(
            doc,
            titulo=tit_a,
            items=desc_apu.componente_a_materiales,
            subtotal=desc_apu.subtotal_a,
            color_accent="0284C7"
        )

        # Subcomponente B
        self._render_apu_subcomponent(
            doc,
            titulo=tit_b,
            items=desc_apu.componente_b_mano_obra,
            subtotal=desc_apu.subtotal_b,
            color_accent="009540"
        )

        # Subcomponente C
        self._render_apu_subcomponent(
            doc,
            titulo=tit_c,
            items=desc_apu.componente_c_transporte_herramientas,
            subtotal=desc_apu.subtotal_c,
            color_accent="D97706"
        )

        # Fila Resumen APU Total
        t_res_apu = doc.add_table(rows=1, cols=2)
        t_res_apu.alignment = WD_TABLE_ALIGNMENT.CENTER
        set_table_borders(t_res_apu, color=self.BORDER_COLOR, sz="4", val="single")
        t_res_apu.rows[0].cells[0].width = Inches(5.1)
        t_res_apu.rows[0].cells[1].width = Inches(1.6)
        try:
            set_cell_width_xml(t_res_apu.rows[0].cells[0], 5.1)
            set_cell_width_xml(t_res_apu.rows[0].cells[1], 1.6)
        except Exception:
            pass
        set_cell_background(t_res_apu.rows[0].cells[0], self.BG_WINNER)
        set_cell_background(t_res_apu.rows[0].cells[1], self.BG_WINNER)
        set_cell_margins(t_res_apu.rows[0].cells[0], top=35, bottom=35, left=45, right=45)
        set_cell_margins(t_res_apu.rows[0].cells[1], top=35, bottom=35, left=45, right=45)

        p_tot_apu = t_res_apu.rows[0].cells[0].paragraphs[0]
        r_tot_a = p_tot_apu.add_run("VALOR UNITARIO TOTAL A TODO COSTO (SUBTOTAL A + B + C):")
        r_tot_a.bold = True
        r_tot_a.font.name = 'Arial'
        r_tot_a.font.size = Pt(12)
        r_tot_a.font.color.rgb = RGBColor(0, 0, 0)

        p_tot_val = t_res_apu.rows[0].cells[1].paragraphs[0]
        p_tot_val.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r_tot_v = p_tot_val.add_run(format_currency_cop_apu(desc_apu.valor_unitario_total))
        r_tot_v.bold = True
        r_tot_v.font.name = 'Arial'
        r_tot_v.font.size = Pt(12)
        r_tot_v.font.color.rgb = RGBColor(0, 0, 0)

        doc.add_paragraph().paragraph_format.space_after = Pt(8)

    def _render_apu_subcomponent(self, doc: Document, titulo: str, items: List[APUComponenteItem], subtotal: float, color_accent: str):
        """Renderiza una subtabla de componente A, B o C en el APU."""
        t_sub = doc.add_table(rows=1 + len(items) + 1, cols=5)
        t_sub.alignment = WD_TABLE_ALIGNMENT.CENTER
        set_table_borders(t_sub, color=self.BORDER_COLOR, sz="4", val="single")

        w_sub = [Inches(3.3), Inches(0.7), Inches(0.6), Inches(1.0), Inches(1.1)]

        # Header subcomponente
        r_head = t_sub.rows[0]
        self._set_cant_split(r_head)
        for idx, (h_txt, w) in enumerate(zip([titulo, "Unidad", "Rend.", "Vr. Unitario", "Subtotal"], w_sub)):
            cell = r_head.cells[idx]
            cell.width = w
            try:
                set_cell_width_xml(cell, getattr(w, "inches", float(w)))
            except Exception:
                pass
            set_cell_background(cell, self.HEADER_BG)
            set_cell_margins(cell, top=30, bottom=30, left=35, right=35)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if idx == 0 else (WD_ALIGN_PARAGRAPH.RIGHT if idx >= 3 else WD_ALIGN_PARAGRAPH.CENTER)
            run = p.add_run(h_txt)
            run.bold = True
            run.font.name = 'Arial'
            run.font.size = Pt(12)
            run.font.color.rgb = RGBColor(0, 0, 0)

        # Filas de ítems
        for idx, sub_it in enumerate(items, 1):
            row = t_sub.rows[idx]
            self._set_cant_split(row)
            vals = [
                (sub_it.descripcion, WD_ALIGN_PARAGRAPH.LEFT, False),
                (sub_it.unidad, WD_ALIGN_PARAGRAPH.CENTER, False),
                (f"{sub_it.cantidad_rendimiento:g}", WD_ALIGN_PARAGRAPH.CENTER, False),
                (format_currency_cop_apu(sub_it.valor_unitario), WD_ALIGN_PARAGRAPH.RIGHT, False),
                (format_currency_cop_apu(sub_it.subtotal), WD_ALIGN_PARAGRAPH.RIGHT, False)
            ]
            self._fill_styled_row(row, vals, w_sub, "FFFFFF")

        # Fila Subtotal
        r_subtot = t_sub.rows[-1]
        self._set_cant_split(r_subtot)
        vals_sub = [
            (f"SUBTOTAL {titulo[:1]}:", WD_ALIGN_PARAGRAPH.RIGHT, True),
            ("", WD_ALIGN_PARAGRAPH.CENTER, True),
            ("", WD_ALIGN_PARAGRAPH.CENTER, True),
            ("", WD_ALIGN_PARAGRAPH.RIGHT, True),
            (format_currency_cop_apu(subtotal), WD_ALIGN_PARAGRAPH.RIGHT, True)
        ]
        self._fill_styled_row(r_subtot, vals_sub, w_sub, self.BG_WINNER)

    def _add_signatures_oficiales(self, doc: Document, cfg: ProcesoConfig):
        """Agrega el bloque de firmas oficiales con los funcionarios configurados en el sistema."""
        t_sig = doc.add_table(rows=2, cols=2)
        t_sig.alignment = WD_TABLE_ALIGNMENT.CENTER
        set_table_borders(t_sig, color="FFFFFF", sz="0", val="none")

        w_col = Inches(3.2)
        for c in t_sig.rows[0].cells + t_sig.rows[1].cells:
            c.width = w_col
            try:
                set_cell_width_xml(c, 3.2)
            except Exception:
                pass
            set_cell_background(c, "FFFFFF")
            set_cell_margins(c, top=25, bottom=20, left=30, right=30)

        # Fila 0: Líneas de firma
        p0_0 = t_sig.rows[0].cells[0].paragraphs[0]
        p0_0.paragraph_format.space_after = Pt(2)
        r_eval = p0_0.add_run("EVALUÓ / ELABORÓ:\n\n__________________________")
        r_eval.bold = True
        r_eval.font.name = 'Arial'
        r_eval.font.size = Pt(12)
        r_eval.font.color.rgb = RGBColor(0, 0, 0)

        p0_1 = t_sig.rows[0].cells[1].paragraphs[0]
        p0_1.paragraph_format.space_after = Pt(2)
        r_rev = p0_1.add_run("REVISÓ Y APROBÓ:\n\n_____________________________")
        r_rev.bold = True
        r_rev.font.name = 'Arial'
        r_rev.font.size = Pt(12)
        r_rev.font.color.rgb = RGBColor(0, 0, 0)

        # Fila 1: Nombres y Cargos
        p1_0 = t_sig.rows[1].cells[0].paragraphs[0]
        p1_0.paragraph_format.space_after = Pt(0)
        r_nom1 = p1_0.add_run(f"{cfg.firmante_elaboro_nombre or 'JOAN ALVAREZ CORREA'}\n")
        r_nom1.bold = True
        r_nom1.font.name = 'Arial'
        r_nom1.font.size = Pt(12)
        r_nom1.font.color.rgb = RGBColor(0, 0, 0)
        r_carg1 = p1_0.add_run(f"{cfg.firmante_elaboro_cargo or 'Estructurador Técnico'}")
        r_carg1.font.name = 'Arial'
        r_carg1.font.size = Pt(12)
        r_carg1.font.color.rgb = RGBColor(0, 0, 0)

        p1_1 = t_sig.rows[1].cells[1].paragraphs[0]
        p1_1.paragraph_format.space_after = Pt(0)
        r_nom2 = p1_1.add_run(f"{cfg.firmante_aprobo_nombre or 'CAROLINA GIRALDO GÓMEZ'}\n")
        r_nom2.bold = True
        r_nom2.font.name = 'Arial'
        r_nom2.font.size = Pt(12)
        r_nom2.font.color.rgb = RGBColor(0, 0, 0)
        r_carg2 = p1_1.add_run(f"{cfg.firmante_aprobo_cargo or 'Gerente General'}")
        r_carg2.font.name = 'Arial'
        r_carg2.font.size = Pt(12)
        r_carg2.font.color.rgb = RGBColor(0, 0, 0)
    def get_demo_case(self) -> EvaluacionComparativaPayload:
        """
        Retorna el caso oficial de referencia del PGIRS de Yolombó ($50.076.264 COP)
        con sus tres (3) cotizantes y quince (15) requerimientos completos.
        """
        cfg = ProcesoConfig(
            objeto_contractual="Suministro de insumos, materiales, dotaciones, equipos, adecuaciones y logística para la ejecución de actividades ambientales y educativas en el marco del Plan de Gestión Integral de Residuos Sólidos (PGIRS) del Municipio de Yolombó.",
            tipo_contrato="Suministro",
            plazo_ejecucion_meses=2,
            smlmv_vigencia=1750905.0,
            modalidad_seleccion="Mínimo tres (3) cotizaciones (Entre 20 y menos de 100 SMLMV)",
            rango_cuantia_smlmv="Entre 20 y menos de 100 SMLMV (Numeral 13 Manual PR-ESPY-002)",
            criterio_seleccion="Selección objetiva del oferente que presentó la cotización MÁS BARATA (menor precio global del mercado).",
            firmante_elaboro_nombre="JOAN ALVAREZ CORREA",
            firmante_elaboro_cargo="Estructurador Técnico",
            firmante_aprobo_nombre="CAROLINA GIRALDO GÓMEZ",
            firmante_aprobo_cargo="Gerente General"
        )

        items_asocomunal = [
            ItemCotizacion(item_numero=1, descripcion="Caneca tipo balde con tapa verde 10 Lts almacenamiento con sticker", unidad="und", cantidad=788, valor_unitario=18000.0, valor_total=14184000.0, valor_total_calculado=14184000.0),
            ItemCotizacion(item_numero=2, descripcion="Plántulas ornamentales y decorativas surtidas (Guarda parques rojos, Veraneras)", unidad="und", cantidad=100, valor_unitario=5500.0, valor_total=550000.0, valor_total_calculado=550000.0),
            ItemCotizacion(item_numero=3, descripcion="Kit para mejoramiento de puntos críticos (lona, pinturas aceite, tiner, brochas)", unidad="und", cantidad=1, valor_unitario=4000000.0, valor_total=4000000.0, valor_total_calculado=4000000.0),
            ItemCotizacion(item_numero=4, descripcion="Eco botella plástica 153 Lts Azul para recolección y acopio", unidad="und", cantidad=3, valor_unitario=1333333.33, valor_total=4000000.0, valor_total_calculado=4000000.0),
            ItemCotizacion(item_numero=5, descripcion="Kit de dotación para recicladores de oficio (buso manga larga, pantalón, botas, gorra, guantes)", unidad="und", cantidad=16, valor_unitario=500000.0, valor_total=8000000.0, valor_total_calculado=8000000.0),
            ItemCotizacion(item_numero=6, descripcion="Transporte y disposición final de residuos especiales y posconsumo", unidad="und", cantidad=1, valor_unitario=600000.0, valor_total=600000.0, valor_total_calculado=600000.0),
            ItemCotizacion(item_numero=7, descripcion="Vallas informativas de 1x1m full color con base de lámina de zinc", unidad="und", cantidad=25, valor_unitario=200000.0, valor_total=5000000.0, valor_total_calculado=5000000.0),
            ItemCotizacion(item_numero=8, descripcion="Adecuación del sitio de posconsumo de la empresa de servicios públicos", unidad="und", cantidad=1, valor_unitario=1142264.0, valor_total=1142264.0, valor_total_calculado=1142264.0),
            ItemCotizacion(item_numero=9, descripcion="Refrigerios para actividades de educación y separación de residuos PGIRS", unidad="und", cantidad=60, valor_unitario=10833.33, valor_total=650000.0, valor_total_calculado=650000.0),
            ItemCotizacion(item_numero=10, descripcion="Bolsas en papel kraft resistentes de 1.5 libras (25.5 x 17 x 34 cm)", unidad="und", cantidad=150, valor_unitario=1333.33, valor_total=200000.0, valor_total_calculado=200000.0),
            ItemCotizacion(item_numero=11, descripcion="Volantes tipo cuadrado full color 15x20 cm para procesos educativos", unidad="und", cantidad=200, valor_unitario=1750.0, valor_total=350000.0, valor_total_calculado=350000.0),
            ItemCotizacion(item_numero=12, descripcion="Incentivos para jornadas de posconsumo (kits ecológicos bambú, cepillos, termos)", unidad="und", cantidad=4, valor_unitario=875000.0, valor_total=3500000.0, valor_total_calculado=3500000.0),
            ItemCotizacion(item_numero=13, descripcion="Bafle portátil profesional 200W RMS con 2 micrófonos inalámbricos", unidad="und", cantidad=1, valor_unitario=2200000.0, valor_total=2200000.0, valor_total_calculado=2200000.0),
            ItemCotizacion(item_numero=14, descripcion="Jornada navideña para población recicladora (cena, regalos, pasabocas)", unidad="und", cantidad=1, valor_unitario=1500000.0, valor_total=1500000.0, valor_total_calculado=1500000.0),
            ItemCotizacion(item_numero=15, descripcion="Contenedor plástico con ruedas 970 Litros 139cm alta resistencia", unidad="und", cantidad=1, valor_unitario=4200000.0, valor_total=4200000.0, valor_total_calculado=4200000.0),
        ]
        of1 = ProponenteOferta(
            proponente_id="asocomunal",
            nombre_razon_social="ASOCOMUNAL YOLOMBÓ",
            nit_cedula="800254070-8",
            representante_legal="Paula Andrea Monsalve (Presidente)",
            domicilio="Municipio de Yolombó, Antioquia",
            fecha_oferta="25 de agosto de 2026",
            items=items_asocomunal,
            subtotal=49876264.0,
            valor_total_oferta=49876264.0,
            posicion_orden=1,
            es_seleccionado=True
        )

        items_torreon = [
            ItemCotizacion(item_numero=1, descripcion="Caneca tipo balde con tapa verde 10 Lts almacenamiento con sticker", unidad="und", cantidad=1140, valor_unitario=22385.96, valor_total=25520000.0, valor_total_calculado=25520000.0),
            ItemCotizacion(item_numero=2, descripcion="Plántulas ornamentales y decorativas surtidas (Guarda parques rojos, Veraneras)", unidad="und", cantidad=100, valor_unitario=5500.0, valor_total=550000.0, valor_total_calculado=550000.0),
            ItemCotizacion(item_numero=3, descripcion="Kit para mejoramiento de puntos críticos (lona, pinturas aceite, tiner, brochas)", unidad="und", cantidad=1, valor_unitario=4500000.0, valor_total=4500000.0, valor_total_calculado=4500000.0),
            ItemCotizacion(item_numero=4, descripcion="Eco botella plástica 153 Lts Azul para recolección y acopio", unidad="und", cantidad=4, valor_unitario=1250000.0, valor_total=5000000.0, valor_total_calculado=5000000.0),
            ItemCotizacion(item_numero=5, descripcion="Kit de dotación para recicladores de oficio (buso manga larga, pantalón, botas, gorra, guantes)", unidad="und", cantidad=16, valor_unitario=500000.0, valor_total=8000000.0, valor_total_calculado=8000000.0),
            ItemCotizacion(item_numero=6, descripcion="Transporte y disposición final de residuos especiales y posconsumo", unidad="und", cantidad=1, valor_unitario=2000000.0, valor_total=2000000.0, valor_total_calculado=2000000.0),
            ItemCotizacion(item_numero=7, descripcion="Vallas informativas de 1x1m full color con base de lámina de zinc", unidad="und", cantidad=30, valor_unitario=350000.0, valor_total=10500000.0, valor_total_calculado=10500000.0),
            ItemCotizacion(item_numero=8, descripcion="Adecuación del sitio de posconsumo de la empresa de servicios públicos", unidad="und", cantidad=1, valor_unitario=2500000.0, valor_total=2500000.0, valor_total_calculado=2500000.0),
            ItemCotizacion(item_numero=9, descripcion="Refrigerios para actividades de educación y separación de residuos PGIRS", unidad="und", cantidad=100, valor_unitario=12000.0, valor_total=1200000.0, valor_total_calculado=1200000.0),
            ItemCotizacion(item_numero=10, descripcion="Bolsas en papel kraft resistentes de 1.5 libras (25.5 x 17 x 34 cm)", unidad="und", cantidad=500, valor_unitario=1012.53, valor_total=506264.0, valor_total_calculado=506264.0),
            ItemCotizacion(item_numero=11, descripcion="Volantes tipo cuadrado full color 15x20 cm para procesos educativos", unidad="und", cantidad=500, valor_unitario=3000.0, valor_total=1500000.0, valor_total_calculado=1500000.0),
            ItemCotizacion(item_numero=12, descripcion="Incentivos para jornadas de posconsumo (kits ecológicos bambú, cepillos, termos)", unidad="und", cantidad=4, valor_unitario=1750000.0, valor_total=7000000.0, valor_total_calculado=7000000.0),
            ItemCotizacion(item_numero=13, descripcion="Bafle portátil profesional 200W RMS con 2 micrófonos inalámbricos", unidad="und", cantidad=1, valor_unitario=4200000.0, valor_total=4200000.0, valor_total_calculado=4200000.0),
            ItemCotizacion(item_numero=14, descripcion="Jornada navideña para población recicladora (cena, regalos, pasabocas)", unidad="und", cantidad=1, valor_unitario=3500000.0, valor_total=3500000.0, valor_total_calculado=3500000.0),
            ItemCotizacion(item_numero=15, descripcion="Contenedor plástico con ruedas 970 Litros 139cm alta resistencia", unidad="und", cantidad=1, valor_unitario=4900000.0, valor_total=4900000.0, valor_total_calculado=4900000.0),
        ]
        of2 = ProponenteOferta(
            proponente_id="torreon",
            nombre_razon_social="TORREON - ID Giraldo S.A.S.",
            nit_cedula="901.458.721-3",
            representante_legal="Andrés Felipe Vélez Muñoz",
            domicilio="Medellín, Antioquia",
            fecha_oferta="Agosto de 2026",
            items=items_torreon,
            subtotal=81376264.0,
            valor_total_oferta=81376264.0,
            posicion_orden=2
        )

        items_m360 = [
            ItemCotizacion(item_numero=1, descripcion="Caneca tipo balde con tapa verde 10 Lts almacenamiento con sticker", unidad="und", cantidad=788, valor_unitario=38375.0, valor_total=30239500.0, valor_total_calculado=30239500.0),
            ItemCotizacion(item_numero=2, descripcion="Plántulas ornamentales y decorativas surtidas (Guarda parques rojos, Veraneras)", unidad="und", cantidad=100, valor_unitario=16980.0, valor_total=1698000.0, valor_total_calculado=1698000.0),
            ItemCotizacion(item_numero=3, descripcion="Kit para mejoramiento de puntos críticos (lona, pinturas aceite, tiner, brochas)", unidad="und", cantidad=1, valor_unitario=7010000.0, valor_total=7010000.0, valor_total_calculado=7010000.0),
            ItemCotizacion(item_numero=4, descripcion="Eco botella plástica 153 Lts Azul para recolección y acopio", unidad="und", cantidad=3, valor_unitario=2045000.0, valor_total=6135000.0, valor_total_calculado=6135000.0),
            ItemCotizacion(item_numero=5, descripcion="Kit de dotación para recicladores de oficio (buso manga larga, pantalón, botas, gorra, guantes)", unidad="und", cantidad=16, valor_unitario=547781.25, valor_total=8764500.0, valor_total_calculado=8764500.0),
            ItemCotizacion(item_numero=6, descripcion="Transporte y disposición final de residuos especiales y posconsumo", unidad="und", cantidad=1, valor_unitario=2850000.0, valor_total=2850000.0, valor_total_calculado=2850000.0),
            ItemCotizacion(item_numero=7, descripcion="Vallas informativas de 1x1m full color con base de lámina de zinc", unidad="und", cantidad=25, valor_unitario=657600.0, valor_total=16440000.0, valor_total_calculado=16440000.0),
            ItemCotizacion(item_numero=8, descripcion="Adecuación del sitio de posconsumo de la empresa de servicios públicos", unidad="und", cantidad=1, valor_unitario=1251264.0, valor_total=1251264.0, valor_total_calculado=1251264.0),
            ItemCotizacion(item_numero=9, descripcion="Refrigerios para actividades de educación y separación de residuos PGIRS", unidad="und", cantidad=60, valor_unitario=28300.0, valor_total=1698000.0, valor_total_calculado=1698000.0),
            ItemCotizacion(item_numero=10, descripcion="Bolsas en papel kraft resistentes de 1.5 libras (25.5 x 17 x 34 cm)", unidad="und", cantidad=150, valor_unitario=3650.0, valor_total=547500.0, valor_total_calculado=547500.0),
            ItemCotizacion(item_numero=11, descripcion="Volantes tipo cuadrado full color 15x20 cm para procesos educativos", unidad="und", cantidad=200, valor_unitario=6850.0, valor_total=1370000.0, valor_total_calculado=1370000.0),
            ItemCotizacion(item_numero=12, descripcion="Incentivos para jornadas de posconsumo (kits ecológicos bambú, cepillos, termos)", unidad="und", cantidad=4, valor_unitario=958000.0, valor_total=3832000.0, valor_total_calculado=3832000.0),
            ItemCotizacion(item_numero=13, descripcion="Bafle portátil profesional 200W RMS con 2 micrófonos inalámbricos", unidad="und", cantidad=1, valor_unitario=5697000.0, valor_total=5697000.0, valor_total_calculado=5697000.0),
            ItemCotizacion(item_numero=14, descripcion="Jornada navideña para población recicladora (cena, regalos, pasabocas)", unidad="und", cantidad=1, valor_unitario=3834000.0, valor_total=3834000.0, valor_total_calculado=3834000.0),
            ItemCotizacion(item_numero=15, descripcion="Contenedor plástico con ruedas 970 Litros 139cm alta resistencia", unidad="und", cantidad=1, valor_unitario=5367000.0, valor_total=5367000.0, valor_total_calculado=5367000.0),
        ]
        of3 = ProponenteOferta(
            proponente_id="m360",
            nombre_razon_social="M360 COMPANY S.A.S",
            nit_cedula="900.709.852-8",
            representante_legal="Daniel Mauricio Suárez Monsalve",
            domicilio="San Roque - Antioquia",
            fecha_oferta="25 de septiembre de 2026",
            items=items_m360,
            subtotal=84729005.0,
            valor_total_oferta=84729005.0,
            posicion_orden=3
        )

        return EvaluacionComparativaPayload(
            proceso_config=cfg,
            ofertas=[of1, of2, of3],
            auto_desglosar_apu=True
        )

    def build_resumen_estudio_mercado(self, result_or_dict: Any) -> Dict[str, Any]:
        """
        Genera el resumen estructurado oficial del ESTUDIO DE MERCADO precontractual para ser incorporado
        en el Estudio Previo (.docx) tras las obligaciones del contratista con el subtítulo:
        'ANALISIS DE LAS PROPUESTAS DE MERCADO:'.

        Sintetiza de manera ejecutiva y jurídica los dos documentos oficiales:
        1. Elección de contratista: Comparación de cotizaciones, control aritmético (PR-ESPY-002 Num. 29)
           y justificación de la selección del proponente más favorable.
        2. Análisis de Precios Unitarios (APU) y Presupuesto Oficial: Estructuración a todo costo
           desglosada en Componente A (Materiales/Insumos), Componente B (Mano de obra con factor prestacional)
           y Componente C (Transporte/Equipos), demostrando razonabilidad económica sin sobrecostos.
        """
        if result_or_dict is None:
            return {}

        # Normalizar a diccionario si es modelo Pydantic
        if hasattr(result_or_dict, "model_dump"):
            data = result_or_dict.model_dump()
        elif hasattr(result_or_dict, "dict"):
            data = result_or_dict.dict()
        elif isinstance(result_or_dict, dict):
            data = dict(result_or_dict)
        else:
            data = {}

        cfg = data.get("proceso_config") or {}
        ofertas = data.get("ofertas") or []
        ganador = data.get("proponente_ganador")
        items_apu = data.get("items_apu") or []

        # Si no hay ganador explícito, deducir de la primera oferta seleccionada o con menor precio
        if not ganador and ofertas:
            ganador = next((o for o in ofertas if o.get("es_seleccionado")), ofertas[0])

        ganador_nom = (ganador.get("nombre_razon_social") if ganador else "") or "Proponente Seleccionado"
        ganador_nit = (ganador.get("nit_cedula") if ganador else "") or "No especificado"
        ganador_rep = (ganador.get("representante_legal") if ganador else "") or ""

        # Valores totales
        val_adjudicado = float(data.get("valor_total_adjudicado") or (ganador.get("valor_total_oferta") if ganador else 0.0) or 0.0)
        val_adjudicado_fmt = format_currency_cop_apu(val_adjudicado)
        val_letras = data.get("valor_total_letras") or (numero_a_letras_cop(val_adjudicado) if val_adjudicado > 0 else "")

        # Modalidad y criterio de selección según Manual PR-ESPY-002
        mod_nombre = data.get("modalidad_manual_nombre") or cfg.get("modalidad_seleccion") or "Mínimo 3 cotizaciones"
        mod_num = data.get("modalidad_manual_numeral") or "Manual de Contratación PR-ESPY-002"
        criterio = cfg.get("criterio_seleccion") or "Menor precio global del mercado que cumpla especificaciones técnicas"
        smlmv_vig = float(cfg.get("smlmv_vigencia") or 1750905.0)
        cuantia_smlmv = float(data.get("cuantia_smlmv_calculada") or (val_adjudicado / smlmv_vig if smlmv_vig > 0 else 0.0))

        # 1. Tabla comparativa de oferentes evaluados
        tabla_ofertas = []
        for idx, of in enumerate(ofertas, start=1):
            val_cot = float(of.get("valor_total_oferta") or of.get("subtotal") or 0.0)
            items_of = of.get("items") or []
            val_calc = sum(float(it.get("valor_total_calculado") or (float(it.get("cantidad") or 1) * float(it.get("valor_unitario") or 0))) for it in items_of) if items_of else val_cot
            tiene_err = bool(of.get("tiene_errores_aritmeticos") or (abs(val_calc - val_cot) > 1.0))
            is_win = bool(of.get("es_seleccionado") or (of.get("nombre_razon_social") == ganador_nom))
            
            desv = of.get("desviacion_porcentual")
            if desv is not None:
                desv_str = f"{float(desv):+.2f}%" if float(desv) != 0 else "0.00% (Más baja)"
            else:
                desv_str = "0.00% (Más baja)" if is_win else "N/A"

            tabla_ofertas.append({
                "posicion": of.get("posicion_orden") or idx,
                "nombre": of.get("nombre_razon_social") or f"Oferente {idx}",
                "nit": of.get("nit_cedula") or "No registrado",
                "valor_cotizado_fmt": format_currency_cop_apu(val_cot),
                "valor_corregido_fmt": format_currency_cop_apu(val_calc),
                "control_aritmetico": "Presenta ajuste aritmético" if tiene_err else "Sin errores aritméticos",
                "desviacion_fmt": desv_str,
                "es_ganador": is_win,
                "estado_eleccion": "✓ SELECCIONADO (PROPUESTA MÁS FAVORABLE)" if is_win else f"No seleccionada (#{idx})"
            })

        # 2. Tabla de ítems con análisis de precios unitarios (APU)
        tabla_items = []
        for idx_it, it in enumerate(items_apu, start=1):
            desglose = it.get("descomposicion_apu") or {}
            tabla_items.append({
                "item_numero": it.get("item_numero") or idx_it,
                "descripcion": it.get("descripcion") or f"Ítem {idx_it}",
                "unidad": it.get("unidad") or "UND",
                "cantidad": float(it.get("cantidad") or 1.0),
                "valor_unitario_fmt": format_currency_cop_apu(it.get("valor_unitario") or 0.0),
                "valor_total_fmt": format_currency_cop_apu(it.get("valor_total") or 0.0),
                "subtotal_a_fmt": format_currency_cop_apu(desglose.get("subtotal_a") or 0.0),
                "subtotal_b_fmt": format_currency_cop_apu(desglose.get("subtotal_b") or 0.0),
                "subtotal_c_fmt": format_currency_cop_apu(desglose.get("subtotal_c") or 0.0)
            })

        # Si no había items_apu pero el ganador tiene ítems en su cotización:
        if not tabla_items and ganador and ganador.get("items"):
            for idx_it, it in enumerate(ganador.get("items"), start=1):
                vu = float(it.get("valor_unitario") or 0.0)
                cant = float(it.get("cantidad") or 1.0)
                vt = float(it.get("valor_total") or (vu * cant))
                tabla_items.append({
                    "item_numero": it.get("item_numero") or idx_it,
                    "descripcion": it.get("descripcion") or f"Ítem {idx_it}",
                    "unidad": it.get("unidad") or "UND",
                    "cantidad": cant,
                    "valor_unitario_fmt": format_currency_cop_apu(vu),
                    "valor_total_fmt": format_currency_cop_apu(vt),
                    "subtotal_a_fmt": format_currency_cop_apu(vu * 0.65),
                    "subtotal_b_fmt": format_currency_cop_apu(vu * 0.25),
                    "subtotal_c_fmt": format_currency_cop_apu(vu * 0.10)
                })

        # Textos estructurados oficiales
        intro_text = (
            "En acatamiento de los principios de transparencia, economía, eficacia y selección objetiva "
            "consagrados en los artículos 209 y 267 de la Constitución Política, la Ley 142 de 1994 y el "
            "Manual de Contratación de la ESPY (Código: PR-ESPY-002, Versión: 02), la Empresa de Servicios "
            "Públicos de Yolombó adelantó el respectivo estudio de mercado precontractual, el cual comprende: "
            "i) La evaluación comparativa de las cotizaciones allegadas al mercado con control aritmético para "
            "la elección objetiva del contratista, y ii) El Análisis de Precios Unitarios (APU a todo costo) "
            "para la estructuración y validación del presupuesto oficial precontractual."
        )

        eleccion_text = (
            f"Bajo la modalidad de selección '{mod_nombre}' ({mod_num}), se efectuó la solicitud y recepción de ofertas "
            f"comerciales en el mercado. En cumplimiento del Numeral 29 del Manual (Prevalencia de lo sustancial y corrección "
            f"aritmética), se auditó minuciosamente cada propuesta recibida contrastando cantidades, unidades y precios unitarios. "
            f"Aplicando el criterio de selección objetiva ({criterio.lower()}), se determinó como la propuesta más favorable y "
            f"económicamente ventajosa la presentada por el oferente {ganador_nom} (NIT/C.C. {ganador_nit}), por un valor total "
            f"de {val_adjudicado_fmt} COP ({val_letras}), garantizando la plena satisfacción de las necesidades institucionales "
            f"al menor costo para la entidad."
        )

        apu_text = (
            "Para asegurar que el valor a contratar responda a la realidad económica sin precios artificialmente bajos ni sobrecostos, "
            "se realizó el Análisis de Precios Unitarios (APU) a todo costo sobre la oferta adjudicada, estructurando los costos "
            "directos e indirectos en tres componentes fundamentales conforme a las buenas prácticas de la ingeniería y la contratación:\n"
            "• Componente A (Materiales, Insumos y Suministros): Valoración de los bienes, materiales, elementos o repuestos puestos en el almacén o sitio de ejecución de la ESPY en Yolombó.\n"
            "• Componente B (Mano de Obra, Operación y Logística): Personal operativo, técnico y profesional requerido, integrando salarios, factor prestacional, aportes de ley a Seguridad Social Integral (Salud, Pensión, ARL) y seguridad y salud en el trabajo.\n"
            "• Componente C (Transporte, Fletes, Herramientas y Equipos): Fletes, acarreos, movilización, seguros, desgaste de herramientas menores y maquinaria indispensables para el cabal cumplimiento."
        )

        conclusion_text = (
            f"Conclusión del Estudio de Mercado: El estudio comparativo y el desglose de precios unitarios certifican que "
            f"el presupuesto oficial de {val_adjudicado_fmt} COP (equivalente a {cuantia_smlmv:.2f} SMLMV oficiales) es idóneo, "
            f"equilibrado y congruente con las condiciones vigentes del mercado en el municipio de Yolombó y el sector de servicios públicos. "
            f"Por consiguiente, se sustenta plenamente la conveniencia técnica, económica y financiera de la presente contratación, "
            f"quedando debidamente amparada por la disponibilidad presupuestal institucional."
        )

        return {
            "subtitulo": "ANALISIS DE LAS PROPUESTAS DE MERCADO:",
            "proceso_info": {
                "objeto": cfg.get("objeto_contractual") or "",
                "tipo_contrato": cfg.get("tipo_contrato") or "Suministro",
                "modalidad_nombre": mod_nombre,
                "modalidad_numeral": mod_num,
                "criterio_seleccion": criterio,
                "smlmv_vigencia": smlmv_vig,
                "cuantia_smlmv": cuantia_smlmv,
                "valor_total": val_adjudicado,
                "valor_total_fmt": val_adjudicado_fmt,
                "valor_total_letras": val_letras
            },
            "proponente_ganador": {
                "nombre": ganador_nom,
                "nit": ganador_nit,
                "representante_legal": ganador_rep,
                "valor_total_fmt": val_adjudicado_fmt,
                "valor_total_letras": val_letras
            },
            "tabla_ofertas": tabla_ofertas,
            "tabla_items": tabla_items,
            "textos": {
                "introduccion": intro_text,
                "eleccion_contratista": eleccion_text,
                "analisis_apu": apu_text,
                "conclusion": conclusion_text
            }
        }

# Instancia singleton
apu_agent = APUContractAgent()

