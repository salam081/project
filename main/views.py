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
from projectfinance.models import ProjectFinanceRequest
from .models import *
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



# @login_required
# def approve_withdrawal_request(request, pk):
#     withdrawal_request = get_object_or_404(Withdrawal, pk=pk, status='Pending')
#     withdrawal_request.approve(request.user)
#     messages.success(request, f"Request by {withdrawal_request.member} approved.")
#     return redirect('list_withdrawal_requests')

@login_required
def approve_withdrawal_request(request, pk):
    withdrawal_request = get_object_or_404(Withdrawal, pk=pk, status='Pending')
    member = withdrawal_request.member  

    # Get member IPPIS
    ippis = member.ippis  

    # Active Loan Requests
    active_loans = LoanRequest.objects.filter( member=member,status="Approved")

    active_consumables = ConsumableRequest.objects.filter(
    guest_ippis=member.ippis,   # adjust field if it's named differently
    status="Itempicked"
)

    # Active Project Finance Requests
    active_project_finance = ProjectFinanceRequest.objects.filter(
        application__member=member,
        status="Approved"
    )

    if request.method == "POST":
        # only allow approval if no active obligations
        if active_loans.exists() or active_consumables.exists() or active_project_finance.exists():
            messages.error(request, f"Withdrawal cannot be approved. {member} has active obligations.")
            return redirect("list_withdrawal_requests")

        withdrawal_request.approve(request.user)
        messages.success(request, f"Request by {withdrawal_request.member} approved.")
        return redirect("list_withdrawal_requests")

    return render(request, "main/approve_withdrawal_request.html", {
        "withdrawal_request": withdrawal_request,
        "active_loans": active_loans,
        "active_consumables": active_consumables,
        "active_project_finance": active_project_finance, })

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

def guest_request_consumable(request):
    now = timezone.now()

    if request.method == "POST":
        consumable_type_id = request.POST.get("consumable_type")
        loan_term_months = request.POST.get("loan_term_months")
        payslip_file = request.FILES.get("file_payslpt")
        selected_item_ids = request.POST.getlist("selected_items")

        # Validation
        if not loan_term_months or not loan_term_months.isdigit() or int(loan_term_months) <= 0:
            messages.error(request, "A valid loan term (in months) must be provided.")
            return redirect("guest_request_consumable")

        if not selected_item_ids:
            messages.error(request, "You must select at least one item.")
            return redirect("guest_request_consumable")

        # Guest details
        guest_name = request.POST.get("guest_name")
        guest_phone = request.POST.get("guest_phone")
        guest_ippis = request.POST.get("guest_ippis")

        if not guest_name or not guest_phone or not guest_ippis:
            messages.error(request, "Guest details (name, phone, IPPIS) are required.")
            return redirect("guest_request_consumable")

        # Check if guest already has a pending request
        has_pending = ConsumableRequest.objects.filter(
            guest_ippis=guest_ippis, status="Pending"
        ).exists()
        if has_pending:
            messages.error(request, "You already have a pending request. Please wait for it to be processed.")
            return redirect("guest_request_consumable")

        # Collect item quantities
        item_details = {}
        for item_id in selected_item_ids:
            try:
                quantity = int(request.POST.get(f"quantity_{item_id}", 0))
                if quantity <= 0:
                    raise ValueError("Quantity must be positive.")
                item_details[item_id] = {"quantity": quantity}
            except (ValueError, TypeError):
                messages.error(request, f"Invalid quantity for item ID {item_id}.")
                return redirect("guest_request_consumable")

        with transaction.atomic():
            try:
                consumable_type_obj = get_object_or_404(ConsumableType, id=consumable_type_id)
                loan_term_months = int(loan_term_months)

                # Create request
                consumable_request = ConsumableRequest.objects.create(
                    consumable_type=consumable_type_obj,
                    file_payslpt=payslip_file,
                    status="Pending",
                    guest_name=guest_name,
                    guest_phone=guest_phone,
                    guest_ippis=guest_ippis,
                )

                # Process items
                for item_id, details in item_details.items():
                    selling_item = get_object_or_404(
                        SellingPlan.objects.select_related("purchased_item"), id=item_id
                    )
                    quantity = details["quantity"]

                    if quantity > selling_item.quantity:
                        messages.error(
                            request,
                            f"Only {selling_item.quantity} units available for {selling_item.purchased_item.item_name}.",
                        )
                        raise ValueError("Insufficient stock.")

                    ConsumableRequestDetail.objects.create(
                        request=consumable_request,
                        selling_item=selling_item,
                        quantity=quantity,
                        item_price=selling_item.selling_price_per_unit,
                        loan_term_months=loan_term_months,
                    )

                    # reduce stock
                    selling_item.quantity -= quantity
                    selling_item.save(update_fields=["quantity"])

                messages.success(request, "Your consumable request has been submitted successfully!")
                return redirect("guest_request_consumable")

            except Exception as e:
                messages.error(request, f"An unexpected error occurred: {e}")
                return redirect("guest_request_consumable")

    # GET
    selling_plans = SellingPlan.objects.filter(quantity__gt=0)
    consumable_types = ConsumableType.objects.filter(available=True)

    return render(
        request,
        "guest/request_consumable.html",
        {"consumable_types": consumable_types, "selling_plans": selling_plans},
    )


@login_required
def member_active_requests(request):
    ippis = request.GET.get("ippis", "").strip()
    member = None
    active_loans = []
    active_consumables = []
    active_project_finances = []
    pending_withdrawals = []
    can_withdraw = False

    if ippis:
        try:
            member = Member.objects.get(ippis=ippis)

            # Active Loan Requests
            active_loans = LoanRequest.objects.filter(
                member=member,
                status="Approved"
            )

            # Active Consumable Requests
            active_consumables = ConsumableRequest.objects.filter(
                user=member.member,   # 👈 Member → User
                status="Itempicked"
            )
            # Active Project Finance Requests
            active_project_finances = ProjectFinanceRequest.objects.filter(
                application__member=member,
                status="Approved"
            )

            # Pending Withdrawal Requests
            pending_withdrawals = Withdrawal.objects.filter(
                member=member,
                status="Pending"
            )

            # If no active requests → allow new withdrawal approval
            if (
                not active_loans.exists()
                and not active_consumables.exists()
                and not active_project_finances.exists()
            ):
                can_withdraw = True

            # ✅ Only show success if a member is found
            messages.success(request, f"Active requests for {member} displayed below.")

        except Member.DoesNotExist:
            messages.warning(request, "No member found with that IPPIS.")
    else:
        messages.info(request, "Please enter an IPPIS to search.")

    return render(request, "main/member_active_requests.html", {
        "member": member,
        "active_loans": active_loans,
        "active_consumables": active_consumables,
        "active_project_finances": active_project_finances,
        "pending_withdrawals": pending_withdrawals,
        "can_withdraw": can_withdraw,
    })
