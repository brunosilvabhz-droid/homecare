from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from app.models import Role, VisitStatus
class Out(BaseModel): model_config=ConfigDict(from_attributes=True)
PROFESSIONS={"nurse","nursing_technician","caregiver","physiotherapist","occupational_therapist","speech_therapist","nutritionist","psychologist","social_worker","physician","dentist","other"}
class Register(BaseModel):
    name:str=Field(min_length=3,max_length=120); email:EmailStr; password:str=Field(min_length=8,max_length=128); organization_name:str=Field(min_length=2,max_length=120); phone:str=Field(min_length=10,max_length=30); cpf:str=Field(min_length=11,max_length=14); profession:str; profession_other:str|None=None; council_name:str|None=None; council_code:str|None=None; council_state:str|None=None; postal_code:str|None=None; address:str|None=None; address_number:str|None=None; address_complement:str|None=None; neighborhood:str|None=None; city:str=Field(min_length=2,max_length=100); state:str=Field(min_length=2,max_length=2); accept_lgpd:bool
    @field_validator("profession")
    @classmethod
    def valid_profession(cls,value):
        if value not in PROFESSIONS: raise ValueError("Profissão inválida")
        return value
    @field_validator("cpf")
    @classmethod
    def valid_cpf(cls,value):
        digits="".join(filter(str.isdigit,value))
        if len(digits)!=11 or len(set(digits))==1: raise ValueError("CPF inválido")
        def digit(base):
            total=sum(int(n)*w for n,w in zip(base,range(len(base)+1,1,-1)))
            result=11-total%11
            return "0" if result>=10 else str(result)
        if digits[-2:] != digit(digits[:9])+digit(digits[:10]): raise ValueError("CPF inválido")
        return digits
    @model_validator(mode="after")
    def other_required(self):
        if self.profession=="other" and not self.profession_other: raise ValueError("Informe a profissão")
        return self
class Login(BaseModel): email:EmailStr; password:str
class Token(BaseModel): access_token:str; token_type:str="bearer"
class Message(BaseModel): message:str
class EmailAction(BaseModel): email:EmailStr
class UserOut(Out): id:str; name:str; email:EmailStr; role:Role; organization_id:str; email_verified_at:datetime|None; phone:str|None; profession:str|None; profession_other:str|None; council_name:str|None; council_code:str|None; council_state:str|None
class ResponsibleCreate(BaseModel): name:str; relationship:str; phone:str|None=None; email:EmailStr|None=None
class PatientIn(BaseModel): name:str; status:str="active"; cpf:str|None=None; birth_date:date|None=None; gender:str|None=None; phone:str|None=None; email:EmailStr|None=None; postal_code:str|None=None; address:str|None=None; address_number:str|None=None; address_complement:str|None=None; neighborhood:str|None=None; city:str|None=None; state:str|None=None; latitude:float|None=None; longitude:float|None=None; notes:str|None=None; family_user_id:str|None=None; responsible:ResponsibleCreate|None=None
class PatientOut(PatientIn, Out): id:str; organization_id:str; created_at:datetime
class ResponsibleIn(BaseModel): patient_id:str; name:str; relationship:str; phone:str|None=None; email:EmailStr|None=None
class ResponsibleOut(ResponsibleIn, Out): id:str; portal_user_id:str|None=None
class VisitIn(BaseModel): patient_id:str; starts_at:datetime; duration_minutes:int=60; notes:str|None=None
class VisitOut(Out): id:str; patient_id:str; professional_id:str; starts_at:datetime; duration_minutes:int; status:VisitStatus; notes:str|None; patient:PatientOut
class RecordIn(BaseModel): patient_id:str; visit_id:str|None=None; occurred_at:datetime|None=None; summary:str; guidance:str|None=None; responsible_name:str|None=None; signature_data:str|None=None
class RecordOut(Out): id:str; patient_id:str; visit_id:str|None; professional_id:str; occurred_at:datetime; summary:str; guidance:str|None; responsible_name:str|None; signature_data:str|None; patient:PatientOut
class FinanceIn(BaseModel): patient_id:str|None=None; description:str; amount:Decimal; due_date:date; paid:bool=False
class FinanceOut(FinanceIn, Out): id:str; patient:PatientOut|None=None
class Dashboard(BaseModel): patients:int; upcoming_visits:int; monthly_revenue:Decimal; pending_amount:Decimal
class SubscriptionOut(Out): id:str; status:str; billing_cycle:str; current_period_end:date|None; gateway:str|None
class VehicleIn(BaseModel): name:str; fuel_type:str="gasoline"; average_km_per_liter:Decimal=Field(gt=0); fuel_price:Decimal=Field(ge=0); additional_cost_per_km:Decimal=Field(ge=0,default=0); is_default:bool=False
class VehicleOut(VehicleIn,Out): id:str; organization_id:str
class RouteCalculate(BaseModel): date:date; vehicle_id:str; start_address:str; return_to_start:bool=True; optimize_order:bool=True
class IntakeLinkCreate(BaseModel): expires_in_days:int=Field(default=7,ge=1,le=30)
class IntakeSubmit(BaseModel):
    patient_name:str=Field(min_length=3,max_length=120); birth_date:date|None=None; cpf:str|None=None; gender:str|None=None; phone:str|None=None; email:EmailStr|None=None; postal_code:str|None=None; address:str|None=None; address_number:str|None=None; address_complement:str|None=None; neighborhood:str|None=None; city:str|None=None; state:str|None=None; conditions:str|None=None; medications:str|None=None; allergies:str|None=None; needs:str|None=None; mobility:str|None=None; additional_information:str|None=None; responsible_name:str=Field(min_length=3,max_length=120); responsible_relationship:str; responsible_phone:str; responsible_email:EmailStr|None=None; accept_privacy:bool
