"""
App de FeNO — Óxido Nítrico Exhalado Fraccional.

Dos modos de uso:
  ① Entrada manual — el técnico ingresa todos los datos directamente.
  ② PDF del equipo — sube el reporte del dispositivo; la app extrae los datos,
     permite verificarlos y genera el informe.

Criterios: ATS 2011 · NICE NG80 2017 · NHS SW FeNO Guidance 2022.
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from informe_feno import InformeFeNO
from interpretation import interpret, ADULTO_BAJO_MAX, ADULTO_ALTO_MIN, PAED_BAJO_MAX, PAED_ALTO_MIN
from models import FeNOResult, FeNOSession, PatientData, PreTestConditions
from parser import parse_report

st.set_page_config(page_title="FeNO — Óxido Nítrico Exhalado",
                   page_icon="🟡", layout="wide")

# ---------------------------------------------------------------------------
# Sidebar — configuración institucional
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("⚙️ Configuración")
    institution = st.text_input("Institución", "SALUD ES VIVIR IPS")
    laboratory = st.text_input("Laboratorio", "Laboratorio de Función Pulmonar")
    city = st.text_input("Ciudad", "Medellín, Colombia")
    physician = st.text_area("Médico firmante",
                             "Jefferson Antonio Buendía, MD Neumólogo Pediatra",
                             height=80)
    report_number = st.text_input("N.° de informe", "")

    st.divider()
    st.caption(
        "**Umbrales ATS 2011 / NICE 2017**\n\n"
        "**Adultos (≥ 17 años)**\n"
        f"- Bajo: < {ADULTO_BAJO_MAX:.0f} ppb\n"
        f"- Intermedio: {ADULTO_BAJO_MAX:.0f}–{ADULTO_ALTO_MIN-1:.0f} ppb\n"
        f"- Alto: ≥ {ADULTO_ALTO_MIN:.0f} ppb\n\n"
        "**Niños (< 17 años)**\n"
        f"- Bajo: < {PAED_BAJO_MAX:.0f} ppb\n"
        f"- Intermedio: {PAED_BAJO_MAX:.0f}–{PAED_ALTO_MIN-1:.0f} ppb\n"
        f"- Alto: ≥ {PAED_ALTO_MIN:.0f} ppb\n\n"
        "↑ significativo en seguimiento: ≥ 40% respecto al valor previo estable."
    )

# ---------------------------------------------------------------------------
# Título y selección de modo
# ---------------------------------------------------------------------------

st.title("🟡 Informe de FeNO — Óxido Nítrico Exhalado Fraccional")
st.caption(
    "Interpretación conforme a ATS 2011 · NICE NG80 2017 · "
    "NHS SW FeNO Guidance 2022 · PCRS Consensus 2019"
)

modo = st.radio(
    "**Selecciona el modo de entrada de datos:**",
    options=["① Entrada manual (sin PDF)", "② Subir PDF del equipo"],
    horizontal=True,
)

# ---------------------------------------------------------------------------
# Inicializar sesión
# ---------------------------------------------------------------------------

if "session" not in st.session_state:
    st.session_state.session = FeNOSession()
if "raw_text" not in st.session_state:
    st.session_state.raw_text = ""

session: FeNOSession = st.session_state.session

# ---------------------------------------------------------------------------
# MODO ② — subir PDF
# ---------------------------------------------------------------------------

if "②" in modo:
    uploaded = st.file_uploader(
        "Sube el reporte del dispositivo de FeNO (PDF)",
        type=["pdf"], key="feno_upload")

    if uploaded:
        pdf_bytes = uploaded.getvalue()
        try:
            sess_parsed, raw = parse_report(pdf_bytes)
            st.session_state.session = sess_parsed
            st.session_state.raw_text = raw
            st.session_state["original_pdf"] = pdf_bytes
            session = sess_parsed
            st.success("PDF procesado. Verifica los datos extraídos abajo.")
        except Exception as e:
            st.error(f"No fue posible procesar el PDF: {e}")
            st.stop()

        with st.expander("📄 Texto extraído del PDF (depuración)"):
            st.text(raw[:2500])
    else:
        st.info("Sube el PDF del equipo para continuar.")
        st.stop()

# ---------------------------------------------------------------------------
# Formularios compartidos (ambos modos)
# ---------------------------------------------------------------------------

st.divider()
st.subheader("1. Datos del paciente")

p = session.patient
c1, c2, c3 = st.columns(3)

with c1:
    p.name = st.text_input("Nombre(s)", p.name)
    p.surname = st.text_input("Apellido(s)", p.surname)
    p.sex = st.selectbox("Sexo biológico",
                         ["", "Hombre", "Mujer"],
                         index=["", "Hombre", "Mujer"].index(p.sex)
                         if p.sex in ["", "Hombre", "Mujer"] else 0)

with c2:
    p.patient_id = st.text_input("ID / Documento", p.patient_id)
    p.date_of_birth = st.text_input("Fecha de nacimiento (YYYY-MM-DD)",
                                    p.date_of_birth)
    if p.date_of_birth:
        try:
            dob = date.fromisoformat(p.date_of_birth)
            test_d = date.fromisoformat(p.test_date[:10]) if p.test_date else date.today()
            p.age_years = round((test_d - dob).days / 365.25, 1)
        except Exception:
            pass
    age_txt = f"{p.age_years} años" if p.age_years else "—"
    st.metric("Edad calculada", age_txt)

with c3:
    p.test_date = st.text_input("Fecha de la prueba", p.test_date or str(date.today()))
    p.nurse = st.text_input("Enfermera / técnico", p.nurse)
    p.next_appointment = st.text_input("Próxima cita", p.next_appointment)

st.divider()
st.subheader("2. Condiciones pre-prueba")
st.caption(
    "Registra las condiciones antes de la prueba. Afectan la interpretación "
    "aunque no invalidan la medición."
)

pre = session.pre_test

def _tri(label, val, key):
    """Selector Sí / No / No registrado."""
    opts = ["No registrado", "No", "Sí"]
    idx = 2 if val is True else (1 if val is False else 0)
    sel = st.selectbox(label, opts, index=idx, key=key)
    return True if sel == "Sí" else (False if sel == "No" else None)

col_a, col_b = st.columns(2)
with col_a:
    pre.ate_drank_1h = _tri(
        "¿Comió o bebió (cafeína, alcohol) en la hora previa?",
        pre.ate_drank_1h, "ate")
    pre.smoked_1h = _tri(
        "¿Fumó en la hora previa?",
        pre.smoked_1h, "smoked")
    pre.ate_nitrate_3h = _tri(
        "¿Consumió alimentos ricos en nitratos en las 3 h previas?\n"
        "(brócoli, lechuga, espinaca, remolacha, apio, puerro)",
        pre.ate_nitrate_3h, "nitrate")

with col_b:
    pre.exercised_1h = _tri(
        "¿Hizo ejercicio intenso en la hora previa?",
        pre.exercised_1h, "exercise")
    pre.used_corticosteroids_3d = _tri(
        "¿Usó corticoides (inhalados u orales) en los últimos 3 días?",
        pre.used_corticosteroids_3d, "cs")
    pre.used_antibiotics_3d = _tri(
        "¿Usó antibióticos en los últimos 3 días?",
        pre.used_antibiotics_3d, "ab")

col_c, col_d = st.columns(2)
with col_c:
    pre.symptoms = st.text_input("Síntomas", pre.symptoms)
with col_d:
    pre.medical_history = st.text_input("Historial médico", pre.medical_history)

st.divider()
st.subheader("3. Resultado del FeNO")

res = session.result

# ── Valores por defecto para Medellín (solo en modo manual) ──────────────
# Se aplican únicamente si el campo aún no tiene valor (sesión nueva).
# Medellín, 1.495 m s.n.m.: temperatura interior promedio ~22 °C;
# presión de exhalación del dispositivo típica: 14,0 cmH₂O;
# flujo estándar ATS 2011: 50,0 mL/s.
MODO_MANUAL = "①" in modo
if MODO_MANUAL:
    if res.flow_rate_ml_s is None:
        res.flow_rate_ml_s = 50.0
    if res.temperature_c is None:
        res.temperature_c = 22.0
    if res.pressure_cmh2o is None:
        res.pressure_cmh2o = 14.0
    if not res.sampling_method:
        res.sampling_method = "Directo"

if MODO_MANUAL:
    st.info(
        "📍 **Valores estándar para Medellín (1.495 m s.n.m.) precargados:** "
        "temperatura 22,0 °C · presión 14,0 cmH₂O · flujo 50,0 mL/s · "
        "método Directo. Modifícalos si el equipo reporta valores distintos."
    )

col_r1, col_r2, col_r3 = st.columns(3)

with col_r1:
    feno_val = st.number_input(
        "**FeNO50 (ppb)** ← valor principal",
        min_value=0.0, max_value=1000.0,
        value=float(res.feno50_ppb or 0.0), step=0.1,
        help="Fracción exhalada de NO a flujo de 50 mL/s")
    res.feno50_ppb = feno_val if feno_val > 0 else None

    flow = st.number_input(
        "Flujo de exhalación (mL/s) — estándar 50",
        min_value=0.0, max_value=200.0,
        value=float(res.flow_rate_ml_s or 50.0), step=0.1)
    res.flow_rate_ml_s = flow if flow > 0 else None

with col_r2:
    temp = st.number_input(
        "Temperatura (°C)",
        min_value=0.0, max_value=50.0,
        value=float(res.temperature_c or 0.0), step=0.1)
    res.temperature_c = temp if temp > 0 else None

    pres = st.number_input(
        "Presión (cmH₂O)",
        min_value=0.0, max_value=100.0,
        value=float(res.pressure_cmh2o or 0.0), step=0.1)
    res.pressure_cmh2o = pres if pres > 0 else None

with col_r3:
    no_flux = st.number_input(
        "Flujo de NO (pl/s)",
        min_value=0.0,
        value=float(res.no_flux_pl_s or 0.0), step=1.0,
        help="Valor reportado por el equipo. Depende del FeNO medido.")
    res.no_flux_pl_s = no_flux if no_flux > 0 else None

    res.sampling_method = st.text_input(
        "Método de muestreo",
        res.sampling_method or "Directo")

# Valor previo (seguimiento)
with st.expander("📈 Comparación con medición previa (opcional — para seguimiento)"):
    prev_col1, prev_col2 = st.columns(2)
    with prev_col1:
        prev_val = st.number_input("FeNO50 previo (ppb)",
                                   min_value=0.0, max_value=1000.0,
                                   value=float(res.previous_feno_ppb or 0.0),
                                   step=0.1)
        res.previous_feno_ppb = prev_val if prev_val > 0 else None
    with prev_col2:
        res.previous_feno_date = st.text_input(
            "Fecha medición previa (YYYY-MM-DD)",
            res.previous_feno_date)

# ---------------------------------------------------------------------------
# Interpretación en tiempo real
# ---------------------------------------------------------------------------

if res.feno50_ppb:
    st.divider()
    st.subheader("4. Interpretación automática")

    result = interpret(session)

    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        emoji_cat = {"ALTO": "🔴", "INTERMEDIO": "🟡", "BAJO": "🟢"}.get(
            result.categoria, "⚪")
        st.metric("FeNO50", f"{res.feno50_ppb:.0f} ppb")
    with col_m2:
        st.metric("Categoría", f"{emoji_cat} {result.categoria}")
    with col_m3:
        pob = "Pediátrico (< 17 años)" if result.paediatric else "Adulto (≥ 17 años)"
        st.metric("Población", pob)

    if result.categoria == "ALTO":
        st.error(result.descripcion)
    elif result.categoria == "INTERMEDIO":
        st.warning(result.descripcion)
    else:
        st.success(result.descripcion)

    if result.confounders:
        st.subheader("⚠️ Factores de confusión detectados")
        for cf in result.confounders:
            st.warning(f"**{cf.factor}** — {cf.direccion}. {cf.consejo}")

    if result.tiene_previo and result.cambio_pct is not None:
        if result.aumento_significativo:
            st.error(
                f"⬆️ Aumento de {result.cambio_pct:+.0f}% respecto al valor previo "
                f"({res.previous_feno_ppb:.0f} ppb): cambio clínicamente significativo "
                f"(umbral ≥ 40%).")
        else:
            st.info(
                f"Cambio respecto al valor previo: {result.cambio_pct:+.0f}% "
                "(no supera el umbral de significancia del 40%).")

    if not result.flujo_aceptable:
        st.warning(f"⚠️ Calidad técnica: {result.flujo_nota}")

    # Conclusión editable
    st.subheader("5. Conclusión")
    conclusion = st.text_area(
        "Conclusión del informe (editable por el médico)",
        value=result.conclusion, height=110)
    editada = conclusion.strip() != result.conclusion.strip()
    if editada:
        st.caption("Conclusión editada. Aparecerá tal como se escribe.")

    # Generar PDF
    st.divider()
    nombre_firma, _, credenciales = (physician or "").partition(",")
    gen = InformeFeNO(
        institucion=institution,
        laboratorio=laboratory,
        ciudad=city,
        firmante=nombre_firma.strip(),
        credenciales=credenciales.strip(),
    )

    original_pdf = st.session_state.get("original_pdf")
    try:
        pdf_final = gen.generar(
            session=session,
            result=result,
            conclusion=conclusion if editada else "",
            n_reporte=report_number,
            pdf_original=original_pdf,
        )
    except Exception as err:
        st.error(f"Error al generar el informe: {err}")
        st.stop()

    safe_name = "_".join((p.full_name or "paciente").split())
    st.download_button(
        "📥 Descargar informe de FeNO",
        data=pdf_final,
        file_name=f"Informe_FeNO_{safe_name}.pdf",
        mime="application/pdf",
        type="primary",
    )
    if original_pdf:
        st.caption(
            "El PDF incluye el informe completo y, como última página, "
            "la primera hoja del reporte original del equipo.")
else:
    st.info("Introduce el valor de FeNO50 (ppb) para ver la interpretación.")
