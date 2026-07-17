from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from app.models import Role, VisitStatus, BillingCycle
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
class Login(BaseModel): email:EmailStr; password:str; captcha_token:str|None=None
class Token(BaseModel): access_token:str; token_type:str="bearer"
class Message(BaseModel): message:str
class SupportTicketIn(BaseModel): category:Literal["error","question","suggestion","request"]; description:str=Field(min_length=10,max_length=5000)
class SupportTicketOut(Out): id:str; ticket_number:str; category:str; description:str; status:str; email_sent_at:datetime|None; admin_response:str|None; responded_at:datetime|None; closed_at:datetime|None; created_at:datetime; requester_name:str|None=None; requester_email:EmailStr|None=None; organization_name:str|None=None
class SupportTicketAdminUpdate(BaseModel): response:str=Field(min_length=2,max_length=5000); close:bool=False
class ProfilePhotoIn(BaseModel): content_base64:str; content_type:Literal["image/jpeg","image/png","image/webp"]
class EmailAction(BaseModel): email:EmailStr
class PasswordReset(BaseModel): token:str; password:str=Field(min_length=8,max_length=128)
class GoogleAuth(BaseModel):
    credential:str; organization_name:str|None=None; phone:str|None=None; cpf:str|None=None; profession:str|None=None; profession_other:str|None=None; council_name:str|None=None; council_code:str|None=None; council_state:str|None=None; postal_code:str|None=None; address:str|None=None; address_number:str|None=None; address_complement:str|None=None; neighborhood:str|None=None; city:str|None=None; state:str|None=None; accept_lgpd:bool=False
class UserOut(Out): id:str; name:str; email:EmailStr; role:Role; organization_id:str; email_verified_at:datetime|None; phone:str|None; profession:str|None; profession_other:str|None; council_name:str|None; council_code:str|None; council_state:str|None; default_session_duration_minutes:int; professional_summary:str|None; specialties:str|None; education:str|None; experience_years:int|None; service_areas:str|None; professional_approach:str|None; signature_name:str|None; signature_council:str|None; signature_profession:str|None
class ProfessionalProfileUpdate(BaseModel): professional_summary:str|None=Field(default=None,max_length=2000); specialties:str|None=Field(default=None,max_length=1000); education:str|None=Field(default=None,max_length=1500); experience_years:int|None=Field(default=None,ge=0,le=80); service_areas:str|None=Field(default=None,max_length=1000); professional_approach:str|None=Field(default=None,max_length=1500)
class ResponsibleCreate(BaseModel): name:str; relationship:str; phone:str|None=None; email:EmailStr|None=None
class PatientIn(BaseModel): name:str; status:str="active"; cpf:str|None=None; birth_date:date|None=None; gender:str|None=None; phone:str|None=None; email:EmailStr|None=None; postal_code:str|None=None; address:str|None=None; address_number:str|None=None; address_complement:str|None=None; neighborhood:str|None=None; city:str|None=None; state:str|None=None; latitude:float|None=None; longitude:float|None=None; conditions:str|None=None; medications:str|None=None; allergies:str|None=None; care_needs:str|None=None; mobility:str|None=None; session_value:Decimal|None=Field(default=None,ge=0); session_count:int|None=Field(default=None,ge=1,le=365); notes:str|None=None; family_user_id:str|None=None; responsible:ResponsibleCreate|None=None
class PatientOut(PatientIn, Out): id:str; organization_id:str; created_at:datetime
class PatientPortalInvite(BaseModel): name:str=Field(min_length=3,max_length=120); email:EmailStr
class ResponsibleIn(BaseModel): patient_id:str; name:str; relationship:str; phone:str|None=None; email:EmailStr|None=None
class ResponsibleOut(ResponsibleIn, Out): id:str; portal_user_id:str|None=None
class VisitIn(BaseModel): patient_id:str; starts_at:datetime; duration_minutes:int=60; notes:str|None=None
class VisitOut(Out): id:str; patient_id:str; professional_id:str; starts_at:datetime; duration_minutes:int; status:VisitStatus; notes:str|None; patient_response:str|None; patient:PatientOut
class RecordIn(BaseModel): patient_id:str; visit_id:str|None=None; occurred_at:datetime|None=None; summary:str; guidance:str|None=None; weight_kg:Decimal|None=Field(default=None,gt=0,le=500); blood_pressure_systolic:int|None=Field(default=None,ge=40,le=300); blood_pressure_diastolic:int|None=Field(default=None,ge=20,le=200); heart_rate_bpm:int|None=Field(default=None,ge=20,le=300); respiratory_rate_bpm:int|None=Field(default=None,ge=4,le=100); temperature_c:Decimal|None=Field(default=None,ge=25,le=45); oxygen_saturation_percent:int|None=Field(default=None,ge=50,le=100); blood_glucose_mg_dl:int|None=Field(default=None,ge=20,le=1000); responsible_name:str|None=None; signature_data:str|None=None
class RecordOut(RecordIn,Out): id:str; professional_id:str; occurred_at:datetime; professional_signature_name:str|None; professional_signature_council:str|None; professional_signature_profession:str|None; patient:PatientOut
class AvailabilityWindow(Out): weekday:int=Field(ge=0,le=6); start_time:time; end_time:time; is_active:bool=True
class AvailabilitySettings(BaseModel): default_session_duration_minutes:int=Field(ge=15,le=480); windows:list[AvailabilityWindow]; signature_name:str|None=Field(default=None,max_length=120); signature_council:str|None=Field(default=None,max_length=100); signature_profession:str|None=Field(default=None,max_length=100)
class AvailabilityOut(AvailabilitySettings): pass
class VisitConfirmationLink(BaseModel): url:str
class PublicVisitOut(BaseModel): patient_name:str; professional_name:str; starts_at:datetime; duration_minutes:int; status:VisitStatus; patient_response:str|None
class VisitResponseIn(BaseModel): action:Literal["confirm","cancel","reschedule"]; new_starts_at:datetime|None=None
class AvailableSlot(BaseModel): starts_at:datetime; ends_at:datetime
class FinanceIn(BaseModel): patient_id:str|None=None; entry_type:str="income"; description:str; amount:Decimal=Field(gt=0); due_date:date; paid:bool=False
class FinanceOut(FinanceIn, Out): id:str; source:str|None=None; patient:PatientOut|None=None
class Dashboard(BaseModel): patients:int; upcoming_visits:int; revenue_last_30_days:Decimal; receivable_next_30_days:Decimal
class DashboardChartItem(BaseModel): label:str; revenue:Decimal; visits:int; records:int
class AdminSettings(BaseModel):
    platform_name:str=Field(default="Impacto Care",min_length=2,max_length=80); support_email:EmailStr="contato@impactocg.com"; registration_enabled:bool=True; maintenance_mode:bool=False; maintenance_message:str=Field(default="Estamos realizando uma manutenção programada.",max_length=500); trial_days:int=Field(default=30,ge=0,le=365); monthly_grace_days:int=Field(default=5,ge=0,le=60); session_timeout_minutes:int=Field(default=480,ge=15,le=10080); email_verification_required:bool=True; family_portal_enabled:bool=True; public_intake_enabled:bool=True; appointment_self_service_enabled:bool=True; routes_enabled:bool=True; finance_enabled:bool=True; google_login_enabled:bool=True; captcha_enabled:bool=True; billing_enabled:bool=True; pix_enabled:bool=True; card_enabled:bool=True; reminder_days:list[int]=[7,3,1]; default_session_minutes:int=Field(default=60,ge=15,le=480); max_profile_photo_mb:int=Field(default=1,ge=1,le=10); privacy_url:str="/privacidade"; terms_url:str="/termos"; footer_text:str="Impacto Care — gestão para atendimento domiciliar"; allow_family_reschedule:bool=True; max_reschedule_days:int=Field(default=30,ge=1,le=180)
class AdminPlanUpdate(BaseModel): name:str=Field(min_length=2,max_length=80); monthly_price:Decimal=Field(ge=0); annual_monthly_price:Decimal=Field(ge=0); active:bool=True
class AdminUserUpdate(BaseModel): is_active:bool|None=None; email_verified:bool|None=None
class SubscriptionOut(Out): id:str; status:str; billing_cycle:str; current_period_end:date|None; gateway:str|None
class VehicleIn(BaseModel): name:str; fuel_type:str="gasoline"; average_km_per_liter:Decimal=Field(gt=0); fuel_price:Decimal=Field(ge=0); additional_cost_per_km:Decimal=Field(ge=0,default=0); is_default:bool=False
class VehicleOut(VehicleIn,Out): id:str; organization_id:str
class RouteCalculate(BaseModel):
    date:date; vehicle_id:str|None=None; average_km_per_liter:Decimal|None=Field(default=None,gt=0); fuel_price:Decimal|None=Field(default=None,ge=0); additional_cost_per_km:Decimal=Field(ge=0,default=0); start_address:str; return_to_start:bool=True; optimize_order:bool=True
    @model_validator(mode="after")
    def route_cost_source(self):
        if not self.vehicle_id and (self.average_km_per_liter is None or self.fuel_price is None): raise ValueError("Informe consumo e preço do combustível")
        return self
class IntakeLinkCreate(BaseModel): expires_in_days:int=Field(default=7,ge=1,le=30); recipient_name:str|None=Field(default=None,min_length=2,max_length=120); recipient_phone:str|None=Field(default=None,min_length=8,max_length=30)
class IntakeSubmit(BaseModel):
    patient_name:str=Field(min_length=3,max_length=120); birth_date:date|None=None; cpf:str|None=None; gender:str|None=None; phone:str|None=None; email:EmailStr|None=None; postal_code:str|None=None; address:str|None=None; address_number:str|None=None; address_complement:str|None=None; neighborhood:str|None=None; city:str|None=None; state:str|None=None; conditions:str|None=None; medications:str|None=None; allergies:str|None=None; needs:str|None=None; mobility:str|None=None; additional_information:str|None=None; responsible_name:str=Field(min_length=3,max_length=120); responsible_relationship:str; responsible_phone:str; responsible_email:EmailStr|None=None; accept_privacy:bool
class CheckoutCreate(BaseModel):
    billing_cycle:BillingCycle
    payment_method:Literal["credit_card","pix"]="credit_card"
    plan_code:Literal["pro","premium"]="pro"
class AIAnalysisCreate(BaseModel): analysis_type:Literal["preparation","evolution"]
class AIAnalysisOut(Out): id:str;visit_id:str;analysis_type:str;content:dict;model:str;created_at:datetime
