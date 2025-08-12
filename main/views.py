from django.shortcuts import render,redirect,get_object_or_404
import calendar
from decimal import Decimal,DecimalException
from datetime import datetime
from django.db import transaction
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
from .models import *
from accounts.models import *
from consumable.models import *
from loan.models import *
from savings.models import *
# from .models import FinancialSummary
# Create your views here.


import calendar
from datetime import datetime
from decimal import Decimal
from django.db.models import Sum
from django.db.models.functions import ExtractMonth, ExtractYear
from accounts.utils import get_cooperative_withdrawal_stats, get_members_eligible_for_withdrawal

from django.shortcuts import render



def admin_dashboard(request):
    # Get the current year
    current_year = datetime.now().year
    
    # Data retrieval for the current year
    total_members = Member.objects.count()
    total_members_withdrawal = Withdrawal.objects.count()
    total_loans = LoanRequest.objects.filter(date_created__year=current_year).count()
    pending_loans = LoanRequest.objects.filter(status='pending', date_created__year=current_year).count()
    rejected_loans = LoanRequest.objects.filter(status='rejected', date_created__year=current_year).count()
    loan_types = LoanType.objects.all()
    total_consumable = ConsumableRequest.objects.filter(date_created__year=current_year).count()
    pending_consumable = ConsumableRequest.objects.filter(status='Pending', date_created__year=current_year).count()
    rejected_consumable = ConsumableRequest.objects.filter(status='Declined', date_created__year=current_year).count()
    
    def get_monthly_totals(queryset, value_field):
        return (
            queryset
            .annotate(year=ExtractYear("month"), month_num=ExtractMonth("month"))
            .values("year", "month_num")
            .annotate(total=Sum(value_field, default=Decimal('0.00')))
            .order_by("-year", "-month_num")
        )

    def format_months(data):
        return [
            {
                "year": row["year"],
                "month_num": row["month_num"],
                "month": calendar.month_name[row["month_num"]],
                "total": Decimal(row["total"] or '0.00'),
            }
            for row in data
        ]
    
    savings_monthly = format_months(get_monthly_totals(Savings.objects.all(), "month_saving"))
    interest_monthly = format_months(get_monthly_totals(Interest.objects.all(), "amount_deducted"))
    loanable_monthly = format_months(get_monthly_totals(Loanable.objects.all(), "amount"))
    investment_monthly = format_months(get_monthly_totals(Investment.objects.all(), "amount"))

    # Total calculations (no pagination here, just sums)
    total_savings = Decimal(sum(item["total"] for item in savings_monthly))
    total_interest = Decimal(sum(item["total"] for item in interest_monthly))
    total_loanable = Decimal(sum(item["total"] for item in loanable_monthly))
    total_investment = Decimal(sum(item["total"] for item in investment_monthly))

    # Corrected grand total calculation to include all components
    grand_total = total_savings + total_interest
    # + total_loanable + total_investment
    
    investment_loanable = total_loanable + total_investment

    try:
        # Get the latest summary from the DB (assuming FinancialSummary model exists)
        # This part will only work if the FinancialSummary model is defined and imported
        latest_summary = FinancialSummary.objects.order_by('-created_at').first()
        if not latest_summary or latest_summary.grand_total != grand_total:
            # Only save if it's new or changed
            FinancialSummary.objects.create(
                total_savings=total_savings, total_interest=total_interest,
                total_loanable=total_loanable, total_investment=total_investment,
                grand_total=grand_total, user=request.user
            )
            print(f"New FinancialSummary saved. Grand Total: ₦{grand_total}")
        else:
            print(f"No change detected. Grand Total (₦{grand_total}) matches the latest saved summary.")
        print(f"FinancialSummary snapshot saved automatically for user {request.user.username}")
        pass
    except Exception as e:
        # print(f"ERROR: Failed to automatically save FinancialSummary snapshot for user {request.user.username}. Error: {e}")
        pass

    context = {
        'total_members': total_members,
        'total_members_withdrawal':total_members_withdrawal,
        'total_loans': total_loans,
        'pending_loans': pending_loans,
        'rejected_loans': rejected_loans,
        'total_consumable': total_consumable,
        'pending_consumable': pending_consumable,
        'rejected_consumable': rejected_consumable,
        
        "total_savings": total_savings,
        "total_interest": total_interest,
        "total_loanable": total_loanable,
        "total_investment": total_investment,
        "grand_total": grand_total,
        'investment_loanable': investment_loanable,
    }
    return render(request, 'admin/admin_dashboad.html', context)


def list_financial_summaries(request):
    summaries = FinancialSummary.objects.select_related('user').all()
    context = {'summaries': summaries}
    return render(request, 'main/summary_list.html', context)


def delete_financial_summary(request, pk):
    summary = get_object_or_404(FinancialSummary, pk=pk)
    if request.method == 'POST':
        summary.delete()
        messages.success(request, ' summary deleted successfully.')
    return redirect('financial_list')  


def is_admin(user):
    return user.is_staff or user.is_superuser


@login_required
def list_withdrawal_requests(request):
    requests = Withdrawal.objects.select_related('member', 'approved_by').all()
    stats = get_cooperative_withdrawal_stats()
    return render(request, 'main/list_withdrawal_requests.html', {'requests': requests, 'stats': stats, })



@login_required
def approve_withdrawal_request(request, pk):
    withdrawal_request = get_object_or_404(Withdrawal, pk=pk, status='Pending')
    withdrawal_request.approve(request.user)
    messages.success(request, f"Request by {withdrawal_request.member} approved.")
    return redirect('list_withdrawal_requests')


@login_required
def decline_withdrawal_request(request, pk):
    withdrawal_request = get_object_or_404(Withdrawal, pk=pk, status='Pending')

    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        withdrawal_request.status = 'Declined'
        withdrawal_request.date_approved = timezone.now()
        withdrawal_request.approved_by = request.user
        withdrawal_request.save()

        messages.warning(request, f"Request by {withdrawal_request.member} declined.")
        return redirect('list_withdrawal_requests')

    return render(request, 'main/decline_withdrawal_request.html', {'request_obj': withdrawal_request})



@login_required

def eligible_members_view(request):
    eligible_members = get_members_eligible_for_withdrawal()
    return render(request, 'withdrawal/members/eligible_members.html', {
        'eligible_members': eligible_members,
    })


def cooperative_summary(request):
    summary_totals = FinancialSummary.objects.aggregate(
        total_savings=Sum('total_savings'),
        total_interest=Sum('total_interest'),
        total_investment=Sum('total_investment'),
        total_loanable=Sum('total_loanable'),
        grand_total=Sum('grand_total'),
       )
   
    context = {
        "total_savings": summary_totals['total_savings'] or Decimal('0.00'),
        "total_investment": summary_totals['total_investment'] or Decimal('0.00'),
        "total_loanable": summary_totals['total_loanable'] or Decimal('0.00'),
        "grand_total": summary_totals['grand_total'] or Decimal('0.00'),
        
    }
    return render(request, "widower/admin/coop_summary.html", context)

 
