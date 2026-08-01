"""Tests del motor de interpretación FeNO — ATS 2011 + NICE 2017."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from models import FeNOResult, FeNOSession, PatientData, PreTestConditions
from interpretation import (
    FeNOInterpreter, interpret,
    ADULTO_BAJO_MAX, ADULTO_ALTO_MIN, PAED_BAJO_MAX, PAED_ALTO_MIN,
    SEGUIMIENTO_AUMENTO_PCT,
)


def _sess(feno, age=35.0, sex="Hombre", **kwargs):
    s = FeNOSession()
    s.patient = PatientData(age_years=age, sex=sex)
    s.result = FeNOResult(feno50_ppb=feno, flow_rate_ml_s=50.0, **kwargs)
    return s


# -------------------------------------------------------- umbrales adulto
@pytest.mark.parametrize("ppb,esperado", [
    (10.0,  "BAJO"),
    (24.9,  "BAJO"),
    (25.0,  "INTERMEDIO"),
    (39.9,  "INTERMEDIO"),
    (40.0,  "ALTO"),
    (111.0, "ALTO"),
    (200.0, "ALTO"),
])
def test_categorias_adulto(ppb, esperado):
    r = interpret(_sess(ppb))
    assert r.categoria == esperado
    assert r.paediatric is False


# -------------------------------------------------------- umbrales pediátrico
@pytest.mark.parametrize("ppb,esperado", [
    (10.0, "BAJO"),
    (19.9, "BAJO"),
    (20.0, "INTERMEDIO"),
    (34.9, "INTERMEDIO"),
    (35.0, "ALTO"),
    (60.0, "ALTO"),
])
def test_categorias_pediatrico(ppb, esperado):
    r = interpret(_sess(ppb, age=10.0))
    assert r.categoria == esperado
    assert r.paediatric is True


# -------------------------------------------------------- límites de edad
def test_limite_edad_adulto_17():
    """17 años = adulto según NICE 2017."""
    r = interpret(_sess(40.0, age=17.0))
    assert r.paediatric is False
    assert r.categoria == "ALTO"


def test_limite_edad_pediatrico_16():
    r = interpret(_sess(35.0, age=16.9))
    assert r.paediatric is True
    assert r.categoria == "ALTO"


# -------------------------------------------------------- confusores
def test_confusor_corticoides_detectado():
    s = _sess(20.0)
    s.pre_test.used_corticosteroids_3d = True
    r = interpret(s)
    assert r.hay_confounders_baja is True
    nombres = [cf.factor for cf in r.confounders]
    assert any("corticoid" in n.lower() for n in nombres)


def test_confusor_nitratos_detectado():
    s = _sess(50.0)
    s.pre_test.ate_nitrate_3h = True
    r = interpret(s)
    assert r.hay_confounders_alta is True


def test_sin_confusores():
    s = _sess(40.0)
    s.pre_test.used_corticosteroids_3d = False
    s.pre_test.smoked_1h = False
    s.pre_test.ate_nitrate_3h = False
    r = interpret(s)
    assert not r.confounders


# -------------------------------------------------------- flujo
def test_flujo_aceptable():
    s = _sess(40.0)
    s.result.flow_rate_ml_s = 52.0
    r = interpret(s)
    assert r.flujo_aceptable is True


def test_flujo_fuera_de_estandar():
    s = _sess(40.0)
    s.result.flow_rate_ml_s = 80.0
    r = interpret(s)
    assert r.flujo_aceptable is False
    assert "fuera del estándar" in r.flujo_nota


def test_sin_dato_flujo():
    s = _sess(40.0)
    s.result.flow_rate_ml_s = None
    r = interpret(s)
    assert r.flujo_aceptable is True  # No penaliza si no hay dato


# -------------------------------------------------------- seguimiento
def test_cambio_significativo():
    s = _sess(55.0)
    s.result.previous_feno_ppb = 30.0
    r = interpret(s)
    assert r.cambio_pct == pytest.approx(83.3, abs=0.1)
    assert r.aumento_significativo is True


def test_cambio_no_significativo():
    s = _sess(35.0)
    s.result.previous_feno_ppb = 30.0
    r = interpret(s)
    assert r.cambio_pct == pytest.approx(16.7, abs=0.1)
    assert r.aumento_significativo is False


def test_umbral_exacto_seguimiento():
    s = _sess(42.0)
    s.result.previous_feno_ppb = 30.0  # cambio = 40% exacto
    r = interpret(s)
    assert r.aumento_significativo is True


def test_sin_valor_previo():
    r = interpret(_sess(40.0))
    assert r.cambio_pct is None
    assert r.aumento_significativo is False


# -------------------------------------------------------- resultado None
def test_feno_none():
    s = FeNOSession()
    s.patient = PatientData(age_years=35.0)
    s.result = FeNOResult(feno50_ppb=None)
    r = interpret(s)
    assert r.categoria == "No disponible"


# -------------------------------------------------------- caso real Diana
def test_caso_real_diana():
    """Diana Trespalacio — FeNO50 = 111 ppb, adulta, sin confusores."""
    s = FeNOSession()
    s.patient = PatientData(age_years=29.0, sex="Mujer")
    s.result = FeNOResult(feno50_ppb=111.0, flow_rate_ml_s=52.0)
    s.pre_test.used_corticosteroids_3d = False
    s.pre_test.smoked_1h = False
    s.pre_test.ate_nitrate_3h = False
    r = interpret(s)
    assert r.categoria == "ALTO"
    assert r.flujo_aceptable is True
    assert not r.confounders
    assert "111" in r.conclusion


# -------------------------------------------------------- constantes
@pytest.mark.parametrize("val,esperado", [
    (ADULTO_BAJO_MAX, 25.0),
    (ADULTO_ALTO_MIN, 40.0),
    (PAED_BAJO_MAX, 20.0),
    (PAED_ALTO_MIN, 35.0),
    (SEGUIMIENTO_AUMENTO_PCT, 40.0),
])
def test_constantes_normativas(val, esperado):
    assert val == pytest.approx(esperado)


# -------------------------------------------------------- PDF generado
def test_genera_pdf():
    from informe_feno import InformeFeNO
    s = FeNOSession()
    s.patient = PatientData(age_years=29.0, sex="Mujer",
                            name="Diana", surname="Trespalacio",
                            test_date="2026-05-04")
    s.result = FeNOResult(feno50_ppb=111.0, flow_rate_ml_s=52.0)
    r = interpret(s)
    gen = InformeFeNO(institucion="SALUD ES VIVIR IPS",
                      firmante="Jefferson Antonio Buendía",
                      credenciales="MD · Neumólogo Pediatra")
    pdf = gen.generar(s, r, n_reporte="TEST-001")
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 5000
