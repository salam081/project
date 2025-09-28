from django.shortcuts import render,redirect,get_object_or_404
import calendar
from decimal import Decimal,DecimalException
from datetime import datetime
from django.db import transaction
from django.http import HttpResponse
from datetime import timedelta
from django.db.models import Q, Sum, Count
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Sum
from django.db.models.functions import ExtractYear, ExtractMonth
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.conf import settings
from django.contrib import messages
from django.db.models.functions import TruncMonth
from PurchasedItems.models import *


from projectfinance.models import *
from accounts.models import *
from consumable.models import *
from loan.models import *
from savings.models import *
from main.models import Withdrawal
# from .models import FinancialSummary
# Create your views here.


import calendar
from datetime import datetime
from decimal import Decimal
from django.db.models import Sum
from django.db.models.functions import ExtractMonth, ExtractYear
from accounts.utils import get_cooperative_withdrawal_stats, get_members_eligible_for_withdrawal
from datetime import datetime
import datetime
from django.shortcuts import render
# Create your views here.

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.db.models import Sum
from datetime import date
from dateutil.relativedelta import relativedelta

#=========== non member ==============

@login_required
def non_staff_member_dashboard(request):
    try:
        nonstaff = Member.objects.get(member=request.user)
    except Member.DoesNotExist:
        return redirect('login')  # no need to query again

    # --- Pending guarantor finance requests ---
    pending_guarantor_requests = ProjectFinanceRequest.objects.filter(
        guarantor=nonstaff,
        guarantor_status="Pending"
    ).order_by("-created_at").select_related("application__member__member")

    # --- Pending guarantor loans ---
    pending_guarantor_loans = LoanRequest.objects.filter(
        guarantor=nonstaff,
        guarantor_accepted=False,
        status="pending"
    )

    # --- Savings, Loanable, Investment totals ---
    total_savings = Savings.objects.filter(member=nonstaff).aggregate(
        total=Sum("month_saving")
    )["total"] or 0

    loanable_total = Loanable.objects.filter(member=nonstaff).aggregate(
        total=Sum("amount")
    )["total"] or 0

    investment_total = Investment.objects.filter(member=nonstaff).aggregate(
        total=Sum("amount")
    )["total"] or 0

    # --- Current and previous month savings ---
    today = date.today()
    current_month = today.month
    current_year = today.year

    first_day_of_current_month = date(current_year, current_month, 1)
    previous_month_date = first_day_of_current_month - relativedelta(months=4)

    monthly_saving = Savings.objects.filter(
        member=nonstaff,
        month__month=current_month,
        month__year=current_year
    ).first()

    previous_monthly_saving = Savings.objects.filter(
        member=nonstaff,
        month__month=previous_month_date.month,
        month__year=previous_month_date.year
    ).first()

    # --- Active loan ---
    active_loan = LoanRequest.objects.filter(
        member=nonstaff,
        status="approved"
    ).order_by("-approval_date").first()

    if not active_loan:
        active_loan = LoanRequest.objects.filter(
            member=nonstaff,
            status="rejected"
        ).order_by("-approval_date").first()

    loan_paid = loan_balance = monthly_payment = 0
    if active_loan and active_loan.status == "approved":
        repaybacks = LoanRepayback.objects.filter(loan_request=active_loan)
        loan_paid = repaybacks.aggregate(total=Sum("amount_paid"))["total"] or 0
        loan_balance = active_loan.approved_amount - loan_paid
        monthly_payment = active_loan.monthly_payment

    loan_types = LoanType.objects.all()

    # --- Consumable requests ---
    consumable_requests = ConsumableRequest.objects.filter(user=request.user) \
        .prefetch_related("details__item") \
        .order_by("-date_created")[:5]

    approved_consumable = ConsumableRequest.objects.filter(
        user=request.user, status="itempicked"
    ).order_by("-date_created")

    total_remaining = 0
    consumable_data = []

    for consumable in approved_consumable:
        approved_amount = consumable.calculate_total_price()
        total_paid = consumable.total_paid()
        balance = approved_amount - total_paid
        total_remaining += balance

        if consumable.details.exists():
            loan_term_months = consumable.details.first().loan_term_months
        else:
            loan_term_months = 1

        monthly_payment = approved_amount / loan_term_months

        consumable_data.append({
            "consumable": consumable,
            "approved_amount": approved_amount,
            "total_paid": total_paid,
            "balance": balance,
            "monthly_payment": monthly_payment,
        })

    context = {
        "member": nonstaff,  # ✅ request.user is enough
        "total_savings": total_savings,
        "monthly_saving": monthly_saving.month_saving if monthly_saving else 0,
        "previous_monthly_saving": previous_monthly_saving.month_saving if previous_monthly_saving else 0,
        "loan": active_loan,
        "loan_paid": loan_paid,
        "loan_balance": loan_balance,
        "monthly_payment": monthly_payment,
        "loan_types": loan_types,
        "consumable_requests": consumable_requests,
        "approved_consumable": consumable_data,
        "loanable_total": loanable_total,
        "investment_total": investment_total,
        "total_remaining": total_remaining,
        "pending_guarantor_loans": pending_guarantor_loans,
        "pending_guarantor_requests": pending_guarantor_requests,
    }

    return render(request, "guest/non_staff_member_dashboard.html", context)


def non_staff_members_list(request):
    # Fetch all Members whose related User belongs to the "non-member" group
    non_members = Member.objects.filter(member__group__title="non staff member")
    
    context = {
        "non_members": non_members
    }
    return render(request, "guest/non_members_list.html", context)


def non_staff_member_savings(request, id):
    # Get the Member object for this non-member
    member = get_object_or_404(Member, id=id, member__group__title="non staff member")

    # Savings
    savings = Savings.objects.filter(member=member).order_by("-month")
    total_savings = savings.aggregate(total=Sum("month_saving"))["total"] or Decimal("0.00")

    # Loanable
    loanables = Loanable.objects.filter(member=member).order_by("-month")
    total_loanable = loanables.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    # Investment
    investments = Investment.objects.filter(member=member).order_by("-month")
    total_investment = investments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    # Grand total
    grand_total = total_savings + total_loanable + total_investment

    context = {
        "member": member,
        "savings": savings,
        "loanables": loanables,
        "investments": investments,
        "total_savings": total_savings,
        "total_loanable": total_loanable,
        "total_investment": total_investment,
        "grand_total": grand_total,
    }
    return render(request, "guest/non_member_savings.html", context)