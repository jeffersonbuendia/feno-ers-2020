# -*- coding: utf-8 -*-
"""
Parser para el formato de informe del equipo de FeNO del
Centro de Excelencia en Neumología y Somnología.

Detecta y extrae automáticamente:
  - Datos demográficos del paciente
  - Condiciones pre-test (checkboxes ■Si / ■No)
  - Valor de FeNO50 en ppb
  - Parámetros técnicos (flujo, temperatura, presión, flujo NO)
  - Síntomas e historial
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

import pymupdf

from models import FeNOResult, FeNOSession, PatientData, PreTestConditions


def _num(s: Optional[str]) -> Optional[float]:
    if not s:
        return None
    s = str(s).strip().replace(",", ".")
    m = re.search(r"[-+]?\d+\.?\d*", s)
    return float(m.group()) if m else None


def _extract_text(pdf_bytes: bytes) -> str:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    pages = [page.get_text() for page in doc]
    doc.close()
    return "\n".join(pages)


def _checkbox_si(text: str, label: str) -> Optional[bool]:
    """
    Detecta el estado de un checkbox en el PDF.

    El formato real del equipo usa:
      ƶSi ƵNo  → ambos presentes, se determina cuál está marcado por el contexto
    En este equipo, todos los checkboxes muestran ambas opciones y el símbolo
    ƶ aparece tanto para Si marcado como No marcado.
    La convención observada en el PDF de ejemplo es que ƶSi ƵNo = No marcado
    y ƵSi ƶNo = Sí marcado (diferencia en el carácter Unicode del checkbox).

    Dado que en el ejemplo todos estaban en No (ƶSi ƵNo), se usa la heurística:
    si la línea siguiente al label contiene ƵNo = No,
    si contiene ƵSi o ƶSi antes de un Sí explícito = Sí.

    Como fallback conservador: None (no determinado).
    """
    pattern = re.escape(label)
    m = re.search(pattern + r".{0,300}", text, re.DOTALL)
    if not m:
        return None
    zona = m.group()

    # Carácter ƵNo (U+01B5 + "No") = No marcado en el ejemplo
    # Carácter ƶSi (U+01B6 + "Si") aparece en ambos casos
    # En el PDF de ejemplo, todos son ƶSi ƵNo (= No).
    # Cuando es Sí, el equipo usa ■Si □No en otros modelos.
    # Sin muestra de "Sí marcado" en este formato, devolvemos None si ambiguo.

    # Soporte para otros formatos que usan ■/□
    if "■Si" in zona or "\u25a0Si" in zona:
        return True
    if "■No" in zona or "\u25a0No" in zona:
        return False
    if "\u01b5No" in zona:   # ƵNo = No en el formato del ejemplo
        return False
    if "\u01b6Si" in zona:   # ƶSi en contexto donde no hay ƵNo = puede ser Sí
        return True
    return None


def parse_report(pdf_bytes: bytes) -> Tuple[FeNOSession, str]:
    """
    Parsea el PDF del equipo y devuelve (FeNOSession, texto_crudo).
    """
    text = _extract_text(pdf_bytes)
    session = FeNOSession()

    # ---------------------------------------------------------------- Paciente
    p = session.patient

    m = re.search(r"ID del Paciente:\s*(\S+)", text)
    if m:
        p.patient_id = m.group(1).strip()

    m = re.search(r"Nombre:\s*([^\n]+)", text)
    if m:
        p.name = m.group(1).strip()

    m = re.search(r"Apellido:\s*([^\n]+)", text)
    if m:
        p.surname = m.group(1).strip()

    m = re.search(r"Sexo:\s*([^\n]+)", text)
    if m:
        p.sex = m.group(1).strip()

    m = re.search(r"Fecha de nacimiento:\s*(\d{4}-\d{2}-\d{2})", text)
    if m:
        p.date_of_birth = m.group(1)
        # Calcular edad
        try:
            from datetime import date
            dob = date.fromisoformat(p.date_of_birth)
            test_date = _extract_test_date(text)
            ref = date.fromisoformat(test_date[:10]) if test_date else date.today()
            delta = ref - dob
            p.age_years = round(delta.days / 365.25, 1)
        except Exception:
            pass

    test_date = _extract_test_date(text)
    if test_date:
        p.test_date = test_date

    m = re.search(r"Enfermera:\s*([^\n]+?)(?=\s{2,}|Doctor:|$)", text)
    if m:
        p.nurse = m.group(1).strip()

    m = re.search(r"Doctor:\s*([^\n]+?)(?=\s{2,}|Próxima|$)", text)
    if m:
        p.physician = m.group(1).strip()

    m = re.search(r"Próxima hora médica:\s*([^\n]*)", text)
    if m:
        p.next_appointment = m.group(1).strip()

    # ---------------------------------------------------------------- Pre-test
    pre = session.pre_test

    pre.ate_drank_1h = _checkbox_si(text, "Comió o bebió durante la hora")
    pre.exercised_1h = _checkbox_si(text, "Hizo ejercicio durante la hora")
    pre.ate_nitrate_3h = _checkbox_si(
        text, "Comió Brocoli")  # etiqueta del PDF
    pre.smoked_1h = _checkbox_si(text, "Fumó durante la hora")
    pre.used_corticosteroids_3d = _checkbox_si(text, "Usó corticoides")
    pre.used_antibiotics_3d = _checkbox_si(text, "Usó antibióticos")

    m = re.search(r"Síntomas:\s*([^\n]+)", text)
    if m:
        pre.symptoms = m.group(1).strip()

    m = re.search(r"Historial Médico:\s*([^\n]+)", text)
    if m:
        pre.medical_history = m.group(1).replace("□", "").replace("■", "").strip()

    # ---------------------------------------------------------------- Resultado
    res = session.result

    # FeNO50 ppb — varios formatos posibles
    for pattern in [
        r"Valor de FeNO[_5]?50:\s*([\d,.]+)\s*ppb",
        r"FeNO[_5]?50\s*=?\s*([\d,.]+)\s*ppb",
        r"FeNO:\s*([\d,.]+)\s*ppb",
        r"([\d,.]+)\s*ppb",  # genérico: último recurso
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            res.feno50_ppb = _num(m.group(1))
            break

    m = re.search(r"Flujo de NO:\s*([\d,.]+)\s*pl", text, re.IGNORECASE)
    if m:
        res.no_flux_pl_s = _num(m.group(1))

    m = re.search(r"Tasa de Flujo:\s*([\d,.]+)\s*ml", text, re.IGNORECASE)
    if m:
        res.flow_rate_ml_s = _num(m.group(1))

    m = re.search(r"Temperatura:\s*([\d,.]+)", text, re.IGNORECASE)
    if m:
        res.temperature_c = _num(m.group(1))

    m = re.search(r"Presión:\s*([\d,.]+)\s*cmH", text, re.IGNORECASE)
    if m:
        res.pressure_cmh2o = _num(m.group(1))

    m = re.search(r"Método de Muestreo:\s*([^\n]+)", text, re.IGNORECASE)
    if m:
        res.sampling_method = m.group(1).strip()

    return session, text


def _extract_test_date(text: str) -> str:
    m = re.search(r"Fecha de Prueba:\s*(\d{4}-\d{2}-\d{2})", text)
    if m:
        return m.group(1)
    m = re.search(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", text)
    if m:
        return m.group(1)
    return ""
