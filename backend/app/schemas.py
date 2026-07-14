from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, EmailStr
from app.models import Role, VisitStatus
class Out(BaseModel): model_config=ConfigDict(from_attributes=True)
class Register(BaseModel): name:str; email:EmailStr; password:str; organization_name:str; accept_lgpd:bool
class Login(BaseModel): email:EmailStr; password:str
class Token(BaseModel): access_token:str; token_type:str="bearer"
class UserOut(Out): id:str; name:str; email:EmailStr; role:Role; organization_id:str
class PatientIn(BaseModel): name:str; birth_date:date|None=None; phone:str|None=None; address:str|None=None; notes:str|None=None; family_user_id:str|None=None
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
