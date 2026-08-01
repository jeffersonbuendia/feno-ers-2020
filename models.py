# -*- coding: utf-8 -*-
"""
Modelos de dominio para la aplicación de FeNO.

Referencias:
  [1] Dweik RA, et al. ATS Clinical Practice Guideline: Interpretation of
      exhaled nitric oxide levels (FeNO) for clinical applications.
      Am J Respir Crit Care Med 2011;184:602-615.
  [2] NICE Guideline NG80. Asthma: diagnosis, monitoring and chronic asthma
      management. 2017.
  [3] NHS South West Respiratory Clinical Network. FeNO Guidance for Primary
      Care. April 2022.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Optional


@dataclass
class PreTestConditions:
    """
    Condiciones previas a la prueba de FeNO.

    Las condiciones que pueden falsear el resultado deben registrarse
    sistemáticamente; afectan la interpretación aunque no invalidan la prueba.
    """
    # Factores que pueden DISMINUIR artificialmente el FeNO [1][3]
    ate_drank_1h: Optional[bool] = None       # Comió o bebió (cafeína, alcohol) 1 h antes
    smoked_1h: Optional[bool] = None          # Fumó 1 h antes
    used_corticosteroids_3d: Optional[bool] = None  # Corticoides inhalados u orales 3 d antes
    used_antibiotics_3d: Optional[bool] = None      # Antibióticos 3 d antes

    # Factores que pueden AUMENTAR artificialmente el FeNO [1][3]
    ate_nitrate_3h: Optional[bool] = None     # Alimentos ricos en nitratos 3 h antes
                                               # (apio, puerro, remolacha, lechuga,
                                               #  espinaca, verduras de hoja verde)

    # Factor que puede tanto aumentar como alterar [3]
    exercised_1h: Optional[bool] = None       # Ejercicio intenso 1 h antes

    # Información clínica adicional
    symptoms: str = ""
    medical_history: str = ""                  # p. ej. "Alergias", "Rinitis alérgica"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FeNOResult:
    """
    Resultado técnico de la medición de FeNO.

    El FeNO50 (fracción exhalada de óxido nítrico a flujo de 50 mL/s)
    es el parámetro estándar para la interpretación clínica [1].
    """
    feno50_ppb: Optional[float] = None          # Valor principal en ppb
    no_flux_pl_s: Optional[float] = None        # Flujo de NO en pl/s
    flow_rate_ml_s: Optional[float] = None      # Tasa de flujo (estándar: 50 mL/s) [1]
    temperature_c: Optional[float] = None       # Temperatura ambiental
    pressure_cmh2o: Optional[float] = None      # Presión
    sampling_method: str = ""                   # "Directo" u otro

    # Para seguimiento: comparar con valor previo estable [3]
    previous_feno_ppb: Optional[float] = None
    previous_feno_date: str = ""

    def change_from_previous_pct(self) -> Optional[float]:
        """Cambio porcentual respecto al valor previo estable."""
        if self.feno50_ppb is None or self.previous_feno_ppb in (None, 0):
            return None
        return (self.feno50_ppb - self.previous_feno_ppb) / self.previous_feno_ppb * 100.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PatientData:
    """Datos demográficos del paciente."""
    name: str = ""
    surname: str = ""
    patient_id: str = ""
    sex: str = ""                    # "Hombre", "Mujer" u otro
    date_of_birth: str = ""          # YYYY-MM-DD
    age_years: Optional[float] = None
    test_date: str = ""              # YYYY-MM-DD HH:MM
    nurse: str = ""
    physician: str = ""
    next_appointment: str = ""
    institution: str = ""

    @property
    def is_paediatric(self) -> bool:
        """
        Edad < 17 años → umbrales pediátricos NICE 2017 [2].
        """
        return self.age_years is not None and self.age_years < 17.0

    @property
    def full_name(self) -> str:
        parts = [self.name, self.surname]
        return " ".join(p for p in parts if p).strip()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FeNOSession:
    """Contenedor completo de una sesión de FeNO."""
    patient: PatientData = field(default_factory=PatientData)
    pre_test: PreTestConditions = field(default_factory=PreTestConditions)
    result: FeNOResult = field(default_factory=FeNOResult)

    def to_dict(self) -> dict:
        return {
            "patient": self.patient.to_dict(),
            "pre_test": self.pre_test.to_dict(),
            "result": self.result.to_dict(),
        }
