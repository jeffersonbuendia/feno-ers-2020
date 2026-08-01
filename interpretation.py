# -*- coding: utf-8 -*-
"""
Motor de interpretación del FeNO.

Aplica los criterios de:
  [1] Dweik RA, et al. ATS Clinical Practice Guideline.
      Am J Respir Crit Care Med 2011;184:602-615.
  [2] NICE NG80. Asthma: diagnosis, monitoring and chronic asthma management. 2017.
  [3] NHS South West Respiratory Clinical Network. FeNO Guidance for Primary Care.
      April 2022.

Categorías clínicas
-------------------
Adultos (≥ 17 años) — NICE 2017 / ATS 2011 [1][2][3]:
  BAJO        < 25 ppb   Inflamación eosinofílica poco probable
  INTERMEDIO  25-39 ppb  Resultado incierto; valorar contexto
  ALTO        ≥ 40 ppb   Inflamación eosinofílica probable → probable beneficio de CEI

Niños (< 17 años) — NICE 2017 [2][3]:
  BAJO        < 20 ppb
  INTERMEDIO  20-34 ppb
  ALTO        ≥ 35 ppb

Seguimiento (asma confirmada) [3]:
  Un aumento ≥ 40 % respecto al valor previo estable es
  clínicamente significativo independientemente del valor absoluto.

Flujo de exhalación estándar: 50 mL/s [1].
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from models import FeNOSession, PatientData, PreTestConditions, FeNOResult

# ---------------------------------------------------------------------------
# Constantes normativas
# ---------------------------------------------------------------------------

# Umbrales adultos (≥ 17 años)  [1][2][3]
ADULTO_BAJO_MAX: float = 25.0
ADULTO_ALTO_MIN: float = 40.0

# Umbrales pediátricos (< 17 años)  [2][3]
PAED_BAJO_MAX: float = 20.0
PAED_ALTO_MIN: float = 35.0

# Umbral de aumento significativo en seguimiento  [3]
SEGUIMIENTO_AUMENTO_PCT: float = 40.0

# Flujo de exhalación estándar ATS 2011  [1]
FLUJO_ESTANDAR_ML_S: float = 50.0
FLUJO_TOLERANCIA_ML_S: float = 5.0   # ± 5 mL/s considerado aceptable

# Temperatura y presión de referencia  [1]
TEMPERATURA_REF_C: float = 37.0     # Temperatura corporal


# ---------------------------------------------------------------------------
# Estructuras de resultado
# ---------------------------------------------------------------------------

@dataclass
class ConfoundingFlag:
    """Advertencia sobre un factor que puede alterar el FeNO."""
    factor: str
    direccion: str   # "↓ Puede disminuir el FeNO" o "↑ Puede aumentar el FeNO"
    consejo: str


@dataclass
class InterpretationResult:
    feno50: Optional[float] = None
    categoria: str = ""           # "BAJO", "INTERMEDIO", "ALTO"
    categoria_color: str = ""     # "verde", "ambar", "rojo"
    descripcion: str = ""
    umbral_bajo_max: float = 0.0
    umbral_alto_min: float = 0.0
    paediatric: bool = False

    # Seguimiento
    tiene_previo: bool = False
    cambio_pct: Optional[float] = None
    aumento_significativo: bool = False

    # Calidad técnica
    flujo_aceptable: bool = True
    flujo_nota: str = ""

    # Confusores
    confounders: List[ConfoundingFlag] = field(default_factory=list)
    hay_confounders_baja: bool = False   # Factores que bajan el FeNO
    hay_confounders_alta: bool = False   # Factores que suben el FeNO

    # Texto final
    conclusion: str = ""
    notas: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Motor de interpretación
# ---------------------------------------------------------------------------

class FeNOInterpreter:

    # ---------------------------------------------------------------- calidad
    @staticmethod
    def evaluar_flujo(result: FeNOResult) -> tuple[bool, str]:
        """
        El FeNO50 se mide a 50 mL/s. Un flujo significativamente diferente
        desplaza el valor medido respecto al estándar [1].
        Tolerancia clínica aceptada: 50 ± 5 mL/s.
        """
        if result.flow_rate_ml_s is None:
            return True, ""
        d = abs(result.flow_rate_ml_s - FLUJO_ESTANDAR_ML_S)
        if d <= FLUJO_TOLERANCIA_ML_S:
            return True, (
                f"Flujo de exhalación {result.flow_rate_ml_s:.0f} mL/s "
                f"(estándar {FLUJO_ESTANDAR_ML_S:.0f} mL/s ± {FLUJO_TOLERANCIA_ML_S:.0f}): "
                "aceptable.")
        return False, (
            f"Flujo de exhalación {result.flow_rate_ml_s:.0f} mL/s fuera del estándar "
            f"de {FLUJO_ESTANDAR_ML_S:.0f} mL/s (ATS 2011). Un flujo mayor infraestima "
            "el FeNO; un flujo menor lo sobreestima. Interpretar con cautela.")

    # --------------------------------------------------------------- confusores
    @staticmethod
    def evaluar_confusores(pre: PreTestConditions) -> List[ConfoundingFlag]:
        flags: List[ConfoundingFlag] = []

        if pre.used_corticosteroids_3d:
            flags.append(ConfoundingFlag(
                factor="Corticoides inhalados u orales en los últimos 3 días",
                direccion="↓ Puede disminuir el FeNO",
                consejo="El resultado puede subestimar la inflamación eosinofílica real. "
                        "Si el resultado es bajo y el paciente sigue sintomático, "
                        "considerar repetir la prueba 4 semanas después de retirar "
                        "los corticoides si clínicamente apropiado."))

        if pre.smoked_1h:
            flags.append(ConfoundingFlag(
                factor="Tabaquismo activo en la hora previa",
                direccion="↓ Puede disminuir el FeNO",
                consejo="El tabaco activo reduce transitoriamente el FeNO. "
                        "Se recomienda abstinencia mínima de 1 hora antes de la prueba."))

        if pre.ate_drank_1h:
            flags.append(ConfoundingFlag(
                factor="Ingesta de alimentos o bebidas (cafeína, alcohol) en la hora previa",
                direccion="↓ Puede disminuir el FeNO",
                consejo="La cafeína y el alcohol reducen transitoriamente el FeNO. "
                        "Se recomienda ayuno de 1 hora antes de la prueba."))

        if pre.ate_nitrate_3h:
            flags.append(ConfoundingFlag(
                factor="Consumo de alimentos ricos en nitratos en las 3 horas previas",
                direccion="↑ Puede aumentar el FeNO",
                consejo="Verduras de hoja verde (lechuga, espinaca, remolacha, "
                        "apio, puerro) pueden elevar transitoriamente el FeNO. "
                        "Se recomienda evitarlos 3 horas antes de la prueba."))

        if pre.exercised_1h:
            flags.append(ConfoundingFlag(
                factor="Ejercicio intenso en la hora previa",
                direccion="↓ Puede disminuir el FeNO transitoriamente",
                consejo="Se recomienda reposo de al menos 1 hora antes de la prueba."))

        return flags

    # ------------------------------------------------------------ categoría
    @staticmethod
    def categorizar(feno: float, paediatric: bool) -> tuple[str, str, str, float, float]:
        """
        Devuelve (categoria, color, descripcion, umbral_bajo_max, umbral_alto_min).
        """
        bajo_max = PAED_BAJO_MAX if paediatric else ADULTO_BAJO_MAX
        alto_min = PAED_ALTO_MIN if paediatric else ADULTO_ALTO_MIN
        poblacion = "niños" if paediatric else "adultos"

        if feno < bajo_max:
            return (
                "BAJO",
                "verde",
                f"FeNO < {bajo_max:.0f} ppb en {poblacion}: inflamación eosinofílica de la vía "
                f"aérea poco probable. En paciente asintomático con asma conocida, "
                f"sugiere inflamación bien controlada. En paciente sintomático, considerar "
                f"diagnósticos alternativos no asociados a inflamación eosinofílica.",
                bajo_max,
                alto_min,
            )
        if feno < alto_min:
            return (
                "INTERMEDIO",
                "ambar",
                f"FeNO {feno:.0f} ppb — rango intermedio ({bajo_max:.0f}-{alto_min-1:.0f} ppb "
                f"en {poblacion}): resultado incierto. La interpretación debe integrarse "
                f"con la historia clínica, la espirometría, la variabilidad del flujo "
                f"espiratorio y otros marcadores de inflamación.",
                bajo_max,
                alto_min,
            )
        return (
            "ALTO",
            "rojo",
            f"FeNO ≥ {alto_min:.0f} ppb en {poblacion}: inflamación eosinofílica de la vía "
            f"aérea probable. En el contexto clínico adecuado, sugiere probable beneficio "
            f"del tratamiento con corticosteroides inhalados (CEI). En asma confirmada con "
            f"FeNO alto y paciente sintomático, considerar exposición alérgena persistente, "
            f"dosis inadecuada de CEI o adherencia subóptima.",
            bajo_max,
            alto_min,
        )

    # ---------------------------------------------------------- seguimiento
    @staticmethod
    def evaluar_seguimiento(result: FeNOResult) -> tuple[Optional[float], bool]:
        """
        Un incremento ≥ 40% respecto al valor previo estable es
        clínicamente significativo, independientemente del valor absoluto [3].
        """
        cambio = result.change_from_previous_pct()
        if cambio is None:
            return None, False
        return cambio, cambio >= SEGUIMIENTO_AUMENTO_PCT

    # ------------------------------------------------------ función principal
    def interpret(self, session: FeNOSession) -> InterpretationResult:
        r = InterpretationResult()
        feno = session.result.feno50_ppb
        paediatric = session.patient.is_paediatric

        r.feno50 = feno
        r.paediatric = paediatric

        if feno is None:
            r.categoria = "No disponible"
            r.descripcion = "No se dispone del valor de FeNO."
            r.conclusion = "Resultado no disponible."
            return r

        # 1. Calidad técnica
        r.flujo_aceptable, r.flujo_nota = self.evaluar_flujo(session.result)

        # 2. Confusores
        r.confounders = self.evaluar_confusores(session.pre_test)
        r.hay_confounders_baja = any(
            "↓" in cf.direccion for cf in r.confounders)
        r.hay_confounders_alta = any(
            "↑" in cf.direccion for cf in r.confounders)

        # 3. Categoría
        r.categoria, r.categoria_color, r.descripcion, r.umbral_bajo_max, r.umbral_alto_min = \
            self.categorizar(feno, paediatric)

        # 4. Seguimiento
        r.tiene_previo = session.result.previous_feno_ppb is not None
        if r.tiene_previo:
            r.cambio_pct, r.aumento_significativo = self.evaluar_seguimiento(
                session.result)

        # 5. Notas adicionales
        if not r.flujo_aceptable:
            r.notas.append(r.flujo_nota)

        if r.hay_confounders_baja and r.categoria == "BAJO":
            r.notas.append(
                "Factores presentes que pueden disminuir artificialmente el FeNO. "
                "Un resultado bajo en estas condiciones debe interpretarse con cautela: "
                "el valor real podría ser más elevado.")

        if r.hay_confounders_alta and r.categoria != "BAJO":
            r.notas.append(
                "Factores presentes que pueden aumentar artificialmente el FeNO. "
                "Corroborar que se cumplieron las instrucciones de preparación.")

        if r.aumento_significativo:
            r.notas.append(
                f"Aumento de {r.cambio_pct:+.0f}% respecto al valor previo estable "
                f"({session.result.previous_feno_ppb:.0f} ppb del "
                f"{session.result.previous_feno_date}): "
                f"cambio clínicamente significativo (umbral ≥ {SEGUIMIENTO_AUMENTO_PCT:.0f}%).")

        # 6. Conclusión
        r.conclusion = self._conclusion(r, session)
        return r

    def _conclusion(self, r: InterpretationResult,
                    session: FeNOSession) -> str:
        partes = []
        cat_lower = r.categoria.lower()
        partes.append(
            f"FeNO50 = {r.feno50:.0f} ppb — resultado {cat_lower} "
            f"(umbral {r.umbral_bajo_max:.0f}/{r.umbral_alto_min:.0f} ppb "
            f"para {'niños' if r.paediatric else 'adultos'}).")

        if r.categoria == "ALTO":
            partes.append(
                "Hallazgo compatible con inflamación eosinofílica de la vía aérea.")
        elif r.categoria == "BAJO":
            partes.append(
                "No se identifica inflamación eosinofílica significativa de la vía aérea "
                "en las condiciones actuales.")
        else:
            partes.append(
                "Valor en rango intermedio; correlacionar con el cuadro clínico.")

        if r.hay_confounders_baja:
            partes.append(
                "Factores que pueden infraestimar el FeNO estaban presentes.")
        if r.hay_confounders_alta:
            partes.append(
                "Factores que pueden sobreestimar el FeNO estaban presentes.")

        if r.aumento_significativo:
            partes.append(
                f"Aumento significativo respecto a medición previa ({r.cambio_pct:+.0f}%).")

        return " ".join(partes)


def interpret(session: FeNOSession) -> InterpretationResult:
    return FeNOInterpreter().interpret(session)


# ---------------------------------------------------------------------------
# Tabla de criterios para el pie del informe
# ---------------------------------------------------------------------------

CRITERIOS_APLICADOS = [
    ("FeNO50 — umbral bajo (adultos ≥ 17 años)",
     "< 25 ppb: inflamación eosinofílica poco probable",
     "ATS 2011 [1]; NICE NG80 2017 [2]; NHS SW 2022 [3]"),
    ("FeNO50 — rango intermedio (adultos)",
     "25-39 ppb: resultado incierto; valorar contexto clínico",
     "ATS 2011 [1]; NICE NG80 2017 [2]"),
    ("FeNO50 — umbral alto (adultos)",
     "≥ 40 ppb: inflamación eosinofílica probable; probable beneficio de CEI",
     "ATS 2011 [1]; NICE NG80 2017 [2]; NHS SW 2022 [3]"),
    ("FeNO50 — umbral bajo (niños < 17 años)",
     "< 20 ppb: inflamación eosinofílica poco probable",
     "NICE NG80 2017 [2]; NHS SW 2022 [3]"),
    ("FeNO50 — rango intermedio (niños)",
     "20-34 ppb: resultado incierto",
     "NICE NG80 2017 [2]"),
    ("FeNO50 — umbral alto (niños)",
     "≥ 35 ppb: inflamación eosinofílica probable",
     "NICE NG80 2017 [2]; NHS SW 2022 [3]"),
    ("Cambio significativo en seguimiento",
     "Aumento ≥ 40% respecto al valor previo estable, independiente del valor absoluto",
     "NHS SW FeNO Guidance 2022 [3]"),
    ("Flujo de exhalación estándar",
     "50 mL/s (tolerancia clínica: ± 5 mL/s)",
     "ATS 2011 [1]"),
    ("Factores que disminuyen el FeNO",
     "Corticoides (inhalados/orales), tabaco activo, cafeína, alcohol, ejercicio intenso",
     "ATS 2011 [1]; NHS SW 2022 [3]"),
    ("Factores que aumentan el FeNO",
     "Rinitis alérgica, alimentos ricos en nitratos (verduras de hoja verde), "
     "infección respiratoria activa",
     "ATS 2011 [1]; NHS SW 2022 [3]"),
    ("Límite de edad para umbrales pediátricos",
     "< 17 años: umbrales pediátricos NICE 2017",
     "NICE NG80 2017 [2]"),
    ("El FeNO no debe usarse como herramienta única",
     "Debe integrarse con historia clínica, espirometría, variabilidad de flujo y "
     "respuesta al tratamiento",
     "ATS 2011 [1]; NICE NG80 2017 [2]; PCRS 2019 [4]"),
]
