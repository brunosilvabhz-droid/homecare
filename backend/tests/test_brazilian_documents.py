import pytest
from pydantic import ValidationError

from app.schemas import PatientIn, PatientOut, Register


def registration(**changes):
    values = {
        "name": "Ana Souza",
        "email": "ana@example.com",
        "password": "segura123",
        "organization_name": "Ana Cuidados",
        "phone": "(31) 99999-9999",
        "cpf": "529.982.247-25",
        "profession": "nurse",
        "city": "Belo Horizonte",
        "state": "MG",
        "accept_lgpd": True,
    }
    return Register(**(values | changes))


def test_normalizes_valid_cpf_and_mobile():
    result = registration()
    assert result.cpf == "52998224725"
    assert result.phone == "31999999999"


@pytest.mark.parametrize("cpf", ["111.111.111-11", "529.982.247-24", "123"])
def test_rejects_invalid_cpf(cpf):
    with pytest.raises(ValidationError):
        registration(cpf=cpf)


@pytest.mark.parametrize("phone", ["319999999", "(31) 8888-7777", "00999999999"])
def test_rejects_invalid_professional_mobile(phone):
    with pytest.raises(ValidationError):
        registration(phone=phone)


def test_patient_accepts_landline_but_rejects_invalid_phone():
    assert PatientIn(name="Maria", phone="(31) 3333-4444").phone == "3133334444"
    with pytest.raises(ValidationError):
        PatientIn(name="Maria", phone="3333-4444")


def test_legacy_patient_remains_readable_but_cannot_be_written_again():
    legacy={"id":"legacy-1","organization_id":"org-1","created_at":"2026-01-01T00:00:00Z","name":"Paciente demo","cpf":"00000000101","phone":"319999999"}
    assert PatientOut.model_validate(legacy).cpf=="00000000101"
    with pytest.raises(ValidationError):
        PatientIn(name="Paciente demo",cpf="00000000101",phone="319999999")
