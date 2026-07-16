from datetime import date, timedelta
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models import Subscription, SubscriptionReminder, User, Role, BillingCycle
from app.core.email import send_plan_expiration_email
from app.core.subscriptions import subscription_access

def run(today:date|None=None)->int:
    today=today or date.today();sent=0
    with SessionLocal() as db:
        subscriptions=db.scalars(select(Subscription).where(Subscription.current_period_end.is_not(None))).all()
        for item in subscriptions:
            days=(item.current_period_end-today).days;access=subscription_access(item,today);kind=None
            if days==7: kind="7_days"
            elif days==1: kind="1_day"
            elif days==0: kind="expired"
            elif access["blocked"] and today==((item.current_period_end+timedelta(days=6)) if item.billing_cycle==BillingCycle.MONTHLY else item.current_period_end+timedelta(days=1)): kind="blocked"
            if not kind: continue
            key=f"{item.id}:{item.current_period_end.isoformat()}:{kind}"
            if db.scalar(select(SubscriptionReminder).where(SubscriptionReminder.reminder_key==key)): continue
            users=db.scalars(select(User).where(User.organization_id==item.organization_id,User.role.in_([Role.PROFESSIONAL,Role.ADMIN]),User.is_active.is_(True))).all()
            delivered=False
            for user in users:
                delivered=send_plan_expiration_email(user.email,user.name,item.current_period_end.strftime("%d/%m/%Y"),kind,item.billing_cycle==BillingCycle.MONTHLY) or delivered
            if delivered:
                db.add(SubscriptionReminder(subscription_id=item.id,reminder_key=key,reminder_type=kind));db.commit();sent+=1
    return sent

if __name__=="__main__": print(f"Lembretes enviados: {run()}")
