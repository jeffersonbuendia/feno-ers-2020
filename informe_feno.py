# -*- coding: utf-8 -*-
"""
Generador de informe de FeNO en PDF.

Referencias normativas al pie del documento:
  [1] Dweik RA, et al. ATS Clinical Practice Guideline: Interpretation of
      exhaled nitric oxide levels (FeNO) for clinical applications.
      Am J Respir Crit Care Med 2011;184:602-615.
  [2] NICE Guideline NG80. Asthma: diagnosis, monitoring and chronic asthma
      management. 2017.
  [3] NHS South West Respiratory Clinical Network. FeNO Guidance for Primary
      Care. April 2022.
  [4] Stonham C, Baxter N. FeNO Testing for Asthma Diagnosis: A PCRS
      Consensus. Primary Care Respiratory Update 2019;Issue 18.
"""

from __future__ import annotations

import io
from typing import Any, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, KeepTogether,
    PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

from interpretation import InterpretationResult, CRITERIOS_APLICADOS
from models import FeNOSession

# ---------------------------------------------------------------------------
# Paleta de colores
# ---------------------------------------------------------------------------

AZUL   = colors.HexColor("#1F4E79")
AZUL_C = colors.HexColor("#EBF3FB")
GRIS   = colors.HexColor("#F5F5F5")
GRIS_T = colors.HexColor("#555555")
VERDE  = colors.HexColor("#1A6B1A")
VERDE_F= colors.HexColor("#EAF4EA")
AMBAR  = colors.HexColor("#7B4F00")
AMBAR_F= colors.HexColor("#FFF6E0")
ROJO   = colors.HexColor("#8B0000")
ROJO_F = colors.HexColor("#FDEDED")
BORDE  = colors.HexColor("#B0B0B0")

_COLOR_CATEGORIA = {
    "verde": (VERDE, VERDE_F),
    "ambar": (AMBAR, AMBAR_F),
    "rojo":  (ROJO,  ROJO_F),
}


class InformeFeNO:
    """
    Genera el informe de FeNO en PDF.

    Uso:
        gen = InformeFeNO(institucion="SALUD ES VIVIR IPS", ...)
        pdf = gen.generar(session, result, conclusion="...", n_reporte="...")
    """

    def __init__(self, institucion: str = "", laboratorio: str = "",
                 ciudad: str = "", firmante: str = "",
                 credenciales: str = ""):
        self.institucion = institucion
        self.laboratorio = laboratorio
        self.ciudad = ciudad
        self.firmante = firmante
        self.credenciales = credenciales
        self._estilos = self._build_styles()

    # ---------------------------------------------------------------- estilos
    def _build_styles(self) -> dict:
        base = getSampleStyleSheet()
        e = {}
        e["cuerpo"] = ParagraphStyle(
            "cuerpo", parent=base["Normal"], fontName="Helvetica",
            fontSize=8.4, leading=12, alignment=TA_JUSTIFY,
            textColor=colors.HexColor("#1A1A1A"))
        e["seccion"] = ParagraphStyle(
            "seccion", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=11, leading=14, spaceBefore=10, spaceAfter=4, textColor=AZUL)
        e["subseccion"] = ParagraphStyle(
            "subseccion", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=8.8, leading=12, spaceBefore=6, spaceAfter=2, textColor=AZUL)
        e["nota"] = ParagraphStyle(
            "nota", parent=base["Normal"], fontName="Helvetica-Oblique",
            fontSize=7.2, leading=9.4, alignment=TA_JUSTIFY, textColor=GRIS_T)
        e["celda"] = ParagraphStyle(
            "celda", parent=base["Normal"], fontName="Helvetica",
            fontSize=7.4, leading=9.2)
        e["alerta"] = ParagraphStyle(
            "alerta", parent=base["Normal"], fontName="Helvetica",
            fontSize=8.2, leading=11.4, alignment=TA_JUSTIFY)
        e["firma"] = ParagraphStyle(
            "firma", parent=base["Normal"], fontName="Helvetica",
            fontSize=8.2, leading=11, alignment=TA_CENTER)
        e["grande"] = ParagraphStyle(
            "grande", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=28, leading=34, alignment=TA_CENTER)
        e["cat_label"] = ParagraphStyle(
            "cat_label", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=13, leading=16, alignment=TA_CENTER)
        return e

    # ---------------------------------------------------------------- helpers
    def _ancho(self) -> float:
        return LETTER[0] - 30 * mm

    def _tabla(self, filas, anchos, extra=None, cab=True, fill=None) -> Table:
        t = Table(filas, colWidths=anchos, repeatRows=1 if cab else 0)
        cmds = [
            ("GRID", (0, 0), (-1, -1), 0.35, BORDE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.4),
            ("LEFTPADDING", (0, 0), (-1, -1), 3.5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3.5),
            ("TOPPADDING", (0, 0), (-1, -1), 2.4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.4),
        ]
        if cab:
            cmds += [
                ("BACKGROUND", (0, 0), (-1, 0), fill or AZUL),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 7.0),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ]
        if extra:
            cmds += extra
        t.setStyle(TableStyle(cmds))
        return t

    def _panel(self, titulo, cuerpo, col_text, col_fill) -> Table:
        txt = (f'<font color="#{col_text.hexval()[2:]}">'
               f"<b>{titulo}</b></font>  {cuerpo}")
        t = Table([[Paragraph(txt, self._estilos["alerta"])]],
                  colWidths=[self._ancho()])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), col_fill),
            ("BOX", (0, 0), (-1, -1), 0.9, col_text),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return t

    def _titulo(self, texto) -> List[Any]:
        p = Paragraph(texto, self._estilos["seccion"])
        linea = Table([[""]], colWidths=[self._ancho()], rowHeights=[1.0])
        linea.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, -1), 0.9, AZUL),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        return [p, linea, Spacer(1, 4)]

    def _blank(self, s=6): return Spacer(1, s)

    def _cell(self, txt, bold=False, center=False, color=None):
        st = ParagraphStyle(
            "tmp", parent=self._estilos["celda"],
            fontName="Helvetica-Bold" if bold else "Helvetica",
            alignment=TA_CENTER if center else TA_LEFT,
            textColor=color or colors.black)
        return Paragraph(str(txt) if txt is not None else "—", st)

    # ---------------------------------------------------------------- generar
    def generar(self, session: FeNOSession,
                result: InterpretationResult,
                conclusion: str = "",
                n_reporte: str = "",
                pdf_original: Optional[bytes] = None) -> bytes:

        buf = io.BytesIO()
        ancho, alto = LETTER
        mx, mt, mb = 15 * mm, 28 * mm, 18 * mm

        doc = BaseDocTemplate(
            buf, pagesize=LETTER,
            leftMargin=mx, rightMargin=mx, topMargin=mt, bottomMargin=mb,
            title=f"FeNO — {session.patient.full_name}",
            author=self.firmante, subject="Óxido nítrico exhalado (FeNO)")
        marco = Frame(mx, mb, ancho - 2 * mx, alto - mt - mb,
                      id="main", showBoundary=0)
        doc.addPageTemplates([PageTemplate(
            id="std", frames=[marco],
            onPage=lambda c, d: self._decorate(c, d, session, n_reporte))])

        story: List[Any] = []
        self._alertas(story, result)
        self._paciente(story, session)
        self._pretest(story, session)
        self._resultado_visual(story, session, result)
        self._confusores(story, result)
        self._seguimiento(story, session, result)
        self._conclusion_section(story, result, conclusion)
        self._firma(story, session, n_reporte)
        self._normativa(story)

        doc.build(story)
        pdf = buf.getvalue()

        if pdf_original:
            pdf = self._merge(pdf, pdf_original)
        return pdf

    # --------------------------------------------------------------- encabezado
    def _decorate(self, canv, doc, session, n_reporte):
        canv.saveState()
        ancho, alto = LETTER
        mx = 15 * mm

        canv.setFont("Helvetica-Bold", 13)
        canv.setFillColor(AZUL)
        canv.drawString(mx, alto - 16 * mm, self.institucion or "")
        canv.setFont("Helvetica", 7.8)
        canv.setFillColor(GRIS_T)
        canv.drawString(mx, alto - 20.4 * mm, self.laboratorio)
        canv.setFont("Helvetica-Bold", 8.4)
        canv.setFillColor(colors.HexColor("#333333"))
        canv.drawRightString(ancho - mx, alto - 16 * mm,
                             "INFORME DE FeNO")
        canv.setFont("Helvetica", 7.2)
        canv.setFillColor(GRIS_T)
        canv.drawRightString(ancho - mx, alto - 19.6 * mm,
                             "Óxido Nítrico Exhalado Fraccional")
        canv.drawRightString(ancho - mx, alto - 23 * mm,
                             f"Fecha: {session.patient.test_date}")
        if n_reporte:
            canv.drawRightString(ancho - mx, alto - 26.4 * mm, f"N.° {n_reporte}")

        canv.setStrokeColor(AZUL)
        canv.setLineWidth(1.0)
        canv.line(mx, alto - 25 * mm, ancho - mx, alto - 25 * mm)

        canv.setStrokeColor(AZUL)
        canv.setLineWidth(0.5)
        canv.line(mx, 13 * mm, ancho - mx, 13 * mm)
        canv.setFont("Helvetica", 6.4)
        canv.setFillColor(colors.HexColor("#888888"))
        izq = " · ".join(x for x in (self.laboratorio, self.institucion,
                                     self.ciudad) if x)
        canv.drawString(mx, 10 * mm, izq)
        canv.drawRightString(ancho - mx, 10 * mm, f"Página {doc.page}")
        canv.drawString(mx, 7.2 * mm,
                        "Interpretación: ATS 2011 · NICE NG80 2017 · NHS SW FeNO Guidance 2022")
        canv.restoreState()

    # ---------------------------------------------------------------- secciones
    def _alertas(self, story, result):
        if result.hay_confounders_baja and result.categoria == "BAJO":
            story.append(self._panel(
                "ADVERTENCIA — CONFUSORES PRESENTES.",
                "Factores que disminuyen el FeNO estuvieron presentes. "
                "Un resultado bajo en estas condiciones puede subestimar la "
                "inflamación real.",
                AMBAR, AMBAR_F))
            story.append(self._blank(6))

        if result.hay_confounders_alta and result.categoria != "BAJO":
            story.append(self._panel(
                "ADVERTENCIA — CONFUSORES PRESENTES.",
                "Factores que pueden elevar artificialmente el FeNO estuvieron "
                "presentes. Verificar cumplimiento de la preparación pre-prueba.",
                AMBAR, AMBAR_F))
            story.append(self._blank(6))

        if not result.flujo_aceptable:
            story.append(self._panel(
                "CALIDAD TÉCNICA.",
                result.flujo_nota, AMBAR, AMBAR_F))
            story.append(self._blank(6))

    def _paciente(self, story, session):
        p = session.patient
        w = self._ancho()
        filas = [
            [self._cell("Nombre:", bold=True),
             self._cell(f"{p.full_name}"),
             self._cell("ID paciente:", bold=True),
             self._cell(p.patient_id)],
            [self._cell("Sexo:", bold=True),
             self._cell(p.sex),
             self._cell("Fecha de nacimiento:", bold=True),
             self._cell(p.date_of_birth)],
            [self._cell("Edad:", bold=True),
             self._cell(f"{p.age_years} años" if p.age_years else "—"),
             self._cell("Fecha de la prueba:", bold=True),
             self._cell(p.test_date)],
            [self._cell("Enfermera:", bold=True),
             self._cell(p.nurse),
             self._cell("Médico:", bold=True),
             self._cell(p.physician)],
        ]
        estilos = [("BACKGROUND", (0, 0), (0, -1), AZUL_C),
                   ("BACKGROUND", (2, 0), (2, -1), AZUL_C)]
        story.extend(self._titulo("1.  DATOS DEL PACIENTE"))
        story.append(self._tabla(filas, [w*.18, w*.32, w*.20, w*.30],
                                 extra=estilos, cab=False))

    def _pretest(self, story, session):
        pre = session.pre_test
        story.extend(self._titulo("2.  CONDICIONES PRE-PRUEBA"))
        w = self._ancho()

        def _yn(val):
            if val is True:   return self._cell("SÍ", bold=True, center=True, color=ROJO)
            if val is False:  return self._cell("No", center=True, color=VERDE)
            return self._cell("No registrado", center=True, color=GRIS_T)

        filas = [
            ["Condición", "Cumplida / Presente", "Efecto potencial sobre el FeNO"],
            ["Comió o bebió (cafeína, alcohol) en la hora previa",
             _yn(pre.ate_drank_1h), self._cell("↓ Puede disminuir")],
            ["Hizo ejercicio intenso en la hora previa",
             _yn(pre.exercised_1h), self._cell("↓ Puede disminuir")],
            ["Consumió alimentos ricos en nitratos en las 3 horas previas",
             _yn(pre.ate_nitrate_3h), self._cell("↑ Puede aumentar")],
            ["Fumó en la hora previa",
             _yn(pre.smoked_1h), self._cell("↓ Puede disminuir")],
            ["Usó corticoides (inhalados u orales) en los últimos 3 días",
             _yn(pre.used_corticosteroids_3d), self._cell("↓ Puede disminuir")],
            ["Usó antibióticos en los últimos 3 días",
             _yn(pre.used_antibiotics_3d), self._cell("Informativo")],
        ]
        estilos = [("ALIGN", (1, 1), (1, -1), "CENTER"),
                   ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS])]
        story.append(self._tabla(filas, [w*.54, w*.20, w*.26], extra=estilos))
        story.append(self._blank(4))

        # Síntomas e historial
        if pre.symptoms or pre.medical_history:
            filas2 = [["Síntomas", pre.symptoms or "—"],
                      ["Historial médico", pre.medical_history or "—"]]
            estilos2 = [("BACKGROUND", (0, 0), (0, -1), AZUL_C)]
            story.append(self._tabla(filas2, [w*.22, w*.78],
                                     extra=estilos2, cab=False))
        story.append(self._blank(3))
        story.append(Paragraph(
            "Factores de confusión según ATS 2011 [1] y NHS SW FeNO Guidance 2022 [3]. "
            "Las condiciones marcadas con SÍ pueden alterar el resultado y deben "
            "considerarse en la interpretación.",
            self._estilos["nota"]))

    def _resultado_visual(self, story, session, result):
        story.extend(self._titulo("3.  RESULTADO"))
        w = self._ancho()
        feno = result.feno50 or 0
        res = session.result
        paed = result.paediatric
        bajo_max = result.umbral_bajo_max
        alto_min = result.umbral_alto_min

        # --- Panel grande con el valor ---
        col_text, col_fill = _COLOR_CATEGORIA.get(
            result.categoria_color, (AZUL, AZUL_C))

        valor_txt = f"{feno:.0f}" if result.feno50 else "—"
        t_valor = Table(
            [[Paragraph(valor_txt, self._estilos["grande"]),
              Paragraph("ppb", ParagraphStyle(
                  "ppb", parent=self._estilos["cuerpo"],
                  fontName="Helvetica-Bold", fontSize=18, textColor=GRIS_T))]],
            colWidths=[w * .35, w * .15])
        t_valor.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("BACKGROUND", (0, 0), (-1, -1), col_fill),
            ("BOX", (0, 0), (-1, -1), 1.5, col_text),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ]))

        # --- Tabla de umbrales ---
        def _umbral_row(label, rango, activa):
            c, f = (col_text, col_fill) if activa else (colors.black, colors.white)
            return [
                Paragraph(f"<b>{label}</b>" if activa else label,
                          ParagraphStyle("u", parent=self._estilos["celda"],
                                         textColor=c,
                                         fontName="Helvetica-Bold" if activa else "Helvetica")),
                Paragraph(rango, ParagraphStyle("r", parent=self._estilos["celda"],
                                               alignment=TA_CENTER, textColor=c)),
                Paragraph("◀ RESULTADO" if activa else "",
                          ParagraphStyle("m", parent=self._estilos["celda"],
                                         alignment=TA_CENTER, textColor=c,
                                         fontName="Helvetica-Bold")),
            ]

        poblacion = "niños" if paed else "adultos"
        filas_umb = [
            [Paragraph(f"Umbrales {poblacion}", self._estilos["celda"]),
             Paragraph("Rango", self._estilos["celda"]),
             Paragraph("", self._estilos["celda"])],
            _umbral_row("ALTO", f"≥ {alto_min:.0f} ppb", feno >= alto_min),
            _umbral_row("INTERMEDIO",
                        f"{bajo_max:.0f}–{alto_min-1:.0f} ppb",
                        bajo_max <= feno < alto_min),
            _umbral_row("BAJO", f"< {bajo_max:.0f} ppb", feno < bajo_max),
        ]
        rojo_f, ambar_f, verde_f = ROJO_F, AMBAR_F, VERDE_F
        estilos_umb = [
            ("BACKGROUND", (0, 0), (-1, 0), AZUL_C),
            ("BACKGROUND", (0, 1), (-1, 1), rojo_f),
            ("BACKGROUND", (0, 2), (-1, 2), ambar_f),
            ("BACKGROUND", (0, 3), (-1, 3), verde_f),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.35, BORDE),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        t_umbral = Table(filas_umb, colWidths=[w*.22, w*.18, w*.14])
        t_umbral.setStyle(TableStyle(estilos_umb))

        # --- Parámetros técnicos ---
        res = session.result
        def fv(v, u=""): return f"{v:.1f} {u}".strip() if v is not None else "—"
        filas_tec = [
            ["FeNO50", f"{feno:.0f} ppb"],
            ["Flujo (estándar 50 mL/s)", fv(res.flow_rate_ml_s, "mL/s")],
            ["Temperatura", fv(res.temperature_c, "°C")],
            ["Presión", fv(res.pressure_cmh2o, "cmH₂O")],
            ["Flujo de NO", fv(res.no_flux_pl_s, "pl/s")],
            ["Método", res.sampling_method or "—"],
        ]
        estilos_tec = [("BACKGROUND", (0, 0), (0, -1), AZUL_C),
                       ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, GRIS])]
        t_tec = Table(filas_tec, colWidths=[w*.22, w*.22])
        t_tec.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.35, BORDE),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.4),
            ("BACKGROUND", (0, 0), (0, -1), AZUL_C),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, GRIS]),
        ]))

        # Poner los tres elementos en fila
        fila_principal = Table(
            [[t_valor, Spacer(4, 1), t_umbral, Spacer(4, 1), t_tec]],
            colWidths=[w*.51, 4, w*.54, 4, w*.45])
        fila_principal.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(fila_principal)
        story.append(self._blank(6))

        # Descripción de la categoría
        cat_col, cat_fill = _COLOR_CATEGORIA.get(result.categoria_color, (AZUL, AZUL_C))
        story.append(self._panel(
            f"RESULTADO {result.categoria}.", result.descripcion,
            cat_col, cat_fill))
        story.append(self._blank(3))
        story.append(Paragraph(
            f"Umbrales según NICE NG80 2017 [2] y ATS 2011 [1] para "
            f"{'niños (< 17 años)' if paed else 'adultos (≥ 17 años)'}. "
            "El FeNO50 se mide a un flujo de exhalación de 50 mL/s. "
            "Un resultado alto indica probable inflamación eosinofílica de la vía aérea, "
            "pero no es diagnóstico por sí solo: debe integrarse con la historia clínica, "
            "la espirometría y otros marcadores de inflamación.",
            self._estilos["nota"]))

    def _confusores(self, story, result):
        if not result.confounders:
            return
        story.extend(self._titulo("4.  FACTORES DE CONFUSIÓN"))
        w = self._ancho()
        filas = [["Factor", "Efecto potencial", "Recomendación"]]
        for cf in result.confounders:
            filas.append([
                Paragraph(cf.factor, self._estilos["celda"]),
                Paragraph(cf.direccion, self._estilos["celda"]),
                Paragraph(cf.consejo, self._estilos["celda"]),
            ])
        col = AMBAR if result.hay_confounders_baja else ROJO
        estilos = [
            ("BACKGROUND", (0, 0), (-1, 0), col),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 7.0),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
        story.append(self._tabla(filas, [w*.32, w*.20, w*.48],
                                 extra=estilos, cab=False))

    def _seguimiento(self, story, session, result):
        if not result.tiene_previo:
            return
        story.extend(self._titulo("5.  COMPARACIÓN CON MEDICIÓN PREVIA"))
        w = self._ancho()
        prev = session.result.previous_feno_ppb
        curr = result.feno50
        cambio = result.cambio_pct

        filas = [
            ["", "FeNO50 (ppb)", "Fecha"],
            ["Medición previa", f"{prev:.0f}" if prev else "—",
             session.result.previous_feno_date or "—"],
            ["Medición actual", f"{curr:.0f}" if curr else "—",
             session.patient.test_date],
            ["Cambio",
             f"{cambio:+.0f}% {'⚠ SIGNIFICATIVO' if result.aumento_significativo else ''}" if cambio is not None else "—",
             ""],
        ]
        col_cambio = ROJO if result.aumento_significativo else VERDE
        estilos = [
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS]),
            ("TEXTCOLOR", (1, 3), (1, 3), col_cambio),
            ("FONTNAME", (1, 3), (1, 3), "Helvetica-Bold"),
        ]
        story.append(self._tabla(filas, [w*.36, w*.32, w*.32], extra=estilos))
        story.append(self._blank(3))
        story.append(Paragraph(
            f"Un aumento ≥ {40:.0f}% respecto al valor previo estable es "
            "clínicamente significativo, independientemente del valor absoluto "
            "(NHS SW FeNO Guidance 2022 [3]).",
            self._estilos["nota"]))

    def _conclusion_section(self, story, result, conclusion_editada=""):
        n = "6" if result.confounders else "5"
        n = str(int(n) + (1 if result.tiene_previo else 0))
        story.extend(self._titulo(f"{n}.  CONCLUSIÓN"))

        conclusion_final = conclusion_editada.strip() or result.conclusion
        puntos = [s.strip() for s in conclusion_final.split(".")
                  if s.strip()]
        col_text, col_fill = _COLOR_CATEGORIA.get(
            result.categoria_color, (AZUL, AZUL_C))

        celdas = [[Paragraph(f"<b>{i}.</b>  {pt}.",
                             ParagraphStyle("c", parent=self._estilos["cuerpo"],
                                            fontSize=8.6, leading=12.4, spaceAfter=3))]
                  for i, pt in enumerate(puntos, start=1)]
        t = Table(celdas, colWidths=[self._ancho()])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), col_fill),
            ("BOX", (0, 0), (-1, -1), 0.9, col_text),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t)
        story.append(self._blank(3))
        story.append(Paragraph(
            "El resultado del FeNO debe interpretarse en el contexto clínico completo "
            "y nunca de forma aislada. No es diagnóstico por sí solo. El médico debe "
            "integrar este resultado con la historia clínica, la espirometría, "
            "la variabilidad del flujo espiratorio y la respuesta al tratamiento "
            "(ATS 2011 [1]; NICE NG80 2017 [2]; PCRS 2019 [4]).",
            self._estilos["nota"]))

    def _firma(self, story, session, n_reporte):
        w = self._ancho()
        story.append(Spacer(1, 18))
        izq = [
            Paragraph(f"<b>{self.firmante}</b>", self._estilos["firma"]),
            Paragraph(self.credenciales, self._estilos["firma"]),
            Paragraph(self.laboratorio, self._estilos["firma"]),
            Paragraph(self.institucion, self._estilos["firma"]),
        ]
        der = [
            Paragraph(self.ciudad, self._estilos["firma"]),
            Paragraph(f"Fecha: {session.patient.test_date}", self._estilos["firma"]),
        ]
        if n_reporte:
            der.append(Paragraph(f"N.° {n_reporte}", self._estilos["firma"]))
        t = Table([[izq, der]], colWidths=[w*.5, w*.5])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEABOVE", (0, 0), (0, 0), 0.7, colors.HexColor("#333333")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(KeepTogether(t))

    def _normativa(self, story):
        w = self._ancho()
        filas = [["Criterio / parámetro", "Valor aplicado", "Fuente"]]
        for nombre, valor, fuente in CRITERIOS_APLICADOS:
            filas.append([
                Paragraph(f"<b>{nombre}</b>", self._estilos["celda"]),
                Paragraph(valor, self._estilos["celda"]),
                Paragraph(fuente, self._estilos["celda"]),
            ])
        estilos = [("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS]),
                   ("VALIGN", (0, 0), (-1, -1), "TOP")]
        story.append(Spacer(1, 16))
        story.extend(self._titulo("7.  CRITERIOS NORMATIVOS APLICADOS"))
        story.append(self._tabla(filas, [w*.28, w*.42, w*.30], extra=estilos))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            "<b>Referencias.</b>  "
            "[1] Dweik RA, et al. ATS Clinical Practice Guideline: Interpretation "
            "of exhaled nitric oxide levels (FeNO) for clinical applications. "
            "Am J Respir Crit Care Med 2011;184:602-615.  "
            "[2] National Institute for Health and Care Excellence. Asthma: diagnosis, "
            "monitoring and chronic asthma management. NICE guideline NG80. 2017.  "
            "[3] NHS South West Cardiovascular, Respiratory and Diabetes Clinical Network. "
            "Fractional Exhaled Nitric Oxide (FeNO) Guidance for Primary Care. "
            "April 2022.  "
            "[4] Stonham C, Baxter N. FeNO Testing for Asthma Diagnosis: A PCRS "
            "Consensus. Primary Care Respiratory Update 2019;Issue 18.",
            self._estilos["nota"]))

    def _merge(self, informe: bytes, original: bytes) -> bytes:
        import pymupdf
        out = pymupdf.open()
        try:
            d1 = pymupdf.open(stream=informe, filetype="pdf")
            out.insert_pdf(d1); d1.close()
            try:
                d2 = pymupdf.open(stream=original, filetype="pdf")
                if d2.page_count:
                    out.insert_pdf(d2, from_page=0, to_page=0)
                d2.close()
            except Exception:
                pass
            return out.tobytes(garbage=4, deflate=True)
        finally:
            out.close()
