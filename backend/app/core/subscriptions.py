from datetime import date, timedelta
from app.models import Subscription, SubscriptionStatus, BillingCycle

def subscription_access(item:Subscription|None,today:date|None=None)->dict:
    today=today or date.today()
    if not item or not item.current_period_end:
        return {"blocked":True,"phase":"blocked","days_remaining":None,"grace_ends_at":None}
    end=item.current_period_end;days=(end-today).days
    if item.status==SubscriptionStatus.CANCELED:
        return {"blocked":True,"phase":"blocked","days_remaining":days,"grace_ends_at":None}
    if item.status==SubscriptionStatus.TRIAL:
        return {"blocked":today>end,"phase":"blocked" if today>end else "trial","days_remaining":days,"grace_ends_at":None}
    if item.cancel_at_period_end:
        return {"blocked":today>end,"phase":"blocked" if today>end else "active","days_remaining":days,"grace_ends_at":None}
    grace_end=end+timedelta(days=5) if item.billing_cycle==BillingCycle.MONTHLY else end
    blocked=today>grace_end
    phase="blocked" if blocked else ("grace" if today>end else "active")
    return {"blocked":blocked,"phase":phase,"days_remaining":days,"grace_ends_at":grace_end if item.billing_cycle==BillingCycle.MONTHLY else None}
