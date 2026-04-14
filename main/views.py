from django.shortcuts import render,redirect,get_object_or_404
import calendar
from decimal import Decimal,DecimalException
from datetime import datetime
from django.db import transaction
from django.http import HttpResponse
from datetime import timedelta
from django.db.models import Sum, F, DecimalField, OuterRef, Subquery
from django.db.models.functions import Coalesce

from django.db.models import Q, Sum, Count, Max, F, Min, OuterRef, Subquery, DecimalField ,Value
from django.db.models import F, ExpressionWrapper, DecimalField  
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Sum
from django.db.models.functions import ExtractYear, ExtractMonth
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import datetime
import datetime
from django.conf import settings
from django.contrib import messages
from django.db.models.functions import TruncMonth
from decimal import Decimal
from decimal import Decimal, InvalidOperation
from django.db import transaction
from decimal import Decimal
import openpyxl
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from accounts.decorators import group_required
from PurchasedItems.models import *
from django import forms
from projectfinance.models import *
from .models import *
from accounts.models import *
from consumable.models import *
from loan.models import *
from savings.models import *
from main.models import Withdrawal,UserActivity
from django.db.models.functions import ExtractMonth, ExtractYear
from accounts.utils import get_cooperative_withdrawal_stats, get_members_eligible_for_withdrawal
from accounts.views import *
from .forms import *




@login_required
@group_required(['admin'])
def admin_dashboard(request):
    # Get the current year
    # current_year = datetime.now().year
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    current_year = datetime.datetime.now().year
    
    daily_logins = UserActivity.objects.filter(
        action__icontains="logged in",
        timestamp__date=today
    ).values('user').distinct().count()

    # Count distinct users who logged in in the past 7 days
    weekly_logins = UserActivity.objects.filter(
        action__icontains="logged in",
        timestamp__date__gte=week_ago
    ).values('user').distinct().count()
   
    total_members = User.objects.filter(is_active=True).exclude(is_superuser=True).count()
    print('total_members', total_members)
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
    print('total_savings',total_savings)
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
        
        'daily_logins': daily_logins,
        'weekly_logins': weekly_logins,
        
       
    }
    return render(request, 'main/admin_dashboad.html', context)


@login_required
@group_required(['staff','loan committee'])
def staff_dashboard(request):
        # Get the current year
    # current_year = datetime.now().year
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    current_year = datetime.datetime.now().year
    
    daily_logins = UserActivity.objects.filter(
        action__icontains="logged in",
        timestamp__date=today
    ).values('user').distinct().count()

    # Count distinct users who logged in in the past 7 days
    weekly_logins = UserActivity.objects.filter(
        action__icontains="logged in",
        timestamp__date__gte=week_ago
    ).values('user').distinct().count()
    
    # Data retrieval for the current year
    # total_members = Member.objects.count()
    total_members = User.objects.filter(is_active=True).exclude(is_superuser=True).count()
    print('total_members', total_members)
    total_members_withdrawal = Withdrawal.objects.count()
    total_loans = LoanRequest.objects.filter(date_created__year=current_year).count()
    pending_loans = LoanRequest.objects.filter(status='pending', date_created__year=current_year).count()
    rejected_loans = LoanRequest.objects.filter(status='rejected', date_created__year=current_year).count()
    loan_types = LoanType.objects.all()
    total_consumable = ConsumableRequest.objects.filter(date_created__year=current_year).count()
    pending_consumable = ConsumableRequest.objects.filter(status='Pending', date_created__year=current_year).count()
    rejected_consumable = ConsumableRequest.objects.filter(status='Declined', date_created__year=current_year).count()
    
    
    context = {
        'total_members': total_members,
        'total_members_withdrawal':total_members_withdrawal,
        'total_loans': total_loans,
        'pending_loans': pending_loans,
        'rejected_loans': rejected_loans,
        'total_consumable': total_consumable,
        'pending_consumable': pending_consumable,
        'rejected_consumable': rejected_consumable,
        
        
        'daily_logins': daily_logins,
        'weekly_logins': weekly_logins,
    }
    return render(request, 'main/staff_dashboard.html', context)



@login_required
@group_required(['admin'])
def list_financial_summaries(request):
    summaries = FinancialSummary.objects.select_related('user').all()
    context = {'summaries': summaries}
    return render(request, 'main/summary_list.html', context)

@login_required(login_url='login')
def delete_financial_summary(request, pk):
    summary = get_object_or_404(FinancialSummary, pk=pk)
    if request.method == 'POST':
        summary.delete()
        messages.success(request, ' summary deleted successfully.')
    return redirect('financial_list')  


def is_admin(user):
    return user.is_staff or user.is_superuser


@login_required
@group_required(['admin'])
def list_withdrawal_requests(request):
    requests = Withdrawal.objects.select_related('member', 'approved_by').all()
    stats = get_cooperative_withdrawal_stats()
    return render(request, 'main/list_withdrawal_requests.html', {'requests': requests, 'stats': stats, })



@login_required
@group_required(['admin'])
def approve_withdrawal_request(request, pk):
    withdrawal_request = get_object_or_404(Withdrawal, pk=pk, status='Pending')
    member = withdrawal_request.member  

    # Get member IPPIS
    ippis = member.ippis  

    # Active Loan Requests
    active_loans = LoanRequest.objects.filter(member=member, status="Approved")

    # Active Consumable Requests
    active_consumables = ConsumableRequest.objects.filter(
        guest_ippis=member.ippis,  # adjust field name if different
        status="Itempicked"
    )

    # Active Project Finance Requests
    active_project_finance = ProjectFinanceRequest.objects.filter(
        application__member=member,
        status="Approved"
    )

    if request.method == "POST":
        # Only allow approval if no active obligations
        if active_loans.exists() or active_consumables.exists() or active_project_finance.exists():
            messages.error(request, f"Withdrawal cannot be approved. {member} has active obligations.")
            return redirect("list_withdrawal_requests")

        # Approve withdrawal
        withdrawal_request.approve(request.user)

        # Deactivate member after approval
        member.member.is_active = False  # deactivate the linked User account
        member.member.save() 
        messages.success(request, f"Request by {withdrawal_request.member} approved and member deactivated.")
        return redirect("list_withdrawal_requests")

    return render(request, "main/approve_withdrawal_request.html", {
        "withdrawal_request": withdrawal_request,
        "active_loans": active_loans,
        "active_consumables": active_consumables,
        "active_project_finance": active_project_finance,
    })



@login_required
@group_required(['admin'])
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
def partial_withdrawals_list(request):
    """List all partial withdrawal requests with filtering"""
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    
    # Base queryset
    withdrawals = PartialWithdrawal.objects.select_related('member', 'approved_by').all()
    
    # Apply status filter
    if status_filter:
        withdrawals = withdrawals.filter(status=status_filter)
    
    # Apply search filter (member name or registration number)
    if search:
        withdrawals = withdrawals.filter(
            Q(member__member__first_name__icontains=search) |
            Q(member__member__last_name__icontains=search) |
            Q(member__ippis__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(withdrawals, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get counts for status badges
    status_counts = {
        'pending': PartialWithdrawal.objects.filter(status='Pending').count(),
        'approved': PartialWithdrawal.objects.filter(status='Approved').count(),
        'declined': PartialWithdrawal.objects.filter(status='Declined').count(),
    }
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'search': search,
        'status_counts': status_counts,
    }
    
    return render(request, 'main/partial_withdrawal_list.html', context)


@login_required
def partial_withdrawal_detail(request, pk):
    """View details of a specific withdrawal request"""
    withdrawal = get_object_or_404(PartialWithdrawal.objects.select_related('member', 'approved_by'),pk=pk)
    
    total_savings = Savings.objects.filter(member=withdrawal.member).aggregate(
        total=Sum('month_saving'))['total'] or Decimal('0.00')
    
    total_loanable = Loanable.objects.filter(member=withdrawal.member).aggregate(
        total=Sum('amount'))['total'] or Decimal('0.00')
    
    total_investment = Investment.objects.filter(member=withdrawal.member).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    context = {
        'withdrawal': withdrawal,
        'total_savings': total_savings,
        'total_loanable': total_loanable,
        'total_investment': total_investment,
    }
    
    return render(request, 'main/partial_withdrawal_detail.html', context)


# @login_required
# def partial_withdrawal_approve(request, pk):
#     """Approve a withdrawal request"""
#     withdrawal = get_object_or_404(PartialWithdrawal, pk=pk)
    
#     # Check if already processed
#     if withdrawal.status != 'Pending':
#         messages.warning(request, f'This withdrawal has already been {withdrawal.status.lower()}.')
#         return redirect('partial_withdrawal_detail', pk=pk)
    
#     if request.method == 'POST':
#         try:
#             withdrawal.approve(request.user)
#             messages.success(request,f'Withdrawal of ₦{withdrawal.amount_requested:,.2f} for {withdrawal.member} approved successfully.')
#             return redirect('partial_withdrawals_list')
#         except ValueError as e:
#             messages.error(request, f'Approval failed: {str(e)}')
#             return redirect('partial_withdrawal_detail', pk=pk)
#         except Exception as e:
#             messages.error(request, f'An error occurred: {str(e)}')
#             return redirect('partial_withdrawal_detail', pk=pk)
#     from decimal import Decimal
# from django.db.models import Sum

@login_required
def partial_withdrawal_approve(request, pk):
    withdrawal = get_object_or_404(PartialWithdrawal, pk=pk)

    if withdrawal.status != 'Pending':
        messages.warning(request, f'This withdrawal has already been {withdrawal.status.lower()}.')
        return redirect('partial_withdrawal_detail', pk=pk)

    if request.method == 'POST':
        try:
            # 🔥 Recalculate total savings BEFORE approval
            total_savings = Savings.objects.filter(member=withdrawal.member).aggregate(
                total=Sum('month_saving')
            )['total'] or Decimal('0.00')

            # 🚫 BLOCK if amount >= total savings
            if withdrawal.amount_requested >= total_savings:
                messages.error(
                    request,
                    f'Approval failed: Withdrawal amount must be LESS than total savings (₦{total_savings:,.2f}).'
                )
                return redirect('partial_withdrawal_detail', pk=pk)

            # ✅ Continue approval if valid
            withdrawal.approve(request.user)

            messages.success(
                request,
                f'Withdrawal of ₦{withdrawal.amount_requested:,.2f} for {withdrawal.member} approved successfully.'
            )
            return redirect('partial_withdrawals_list')

        except ValueError as e:
            messages.error(request, f'Approval failed: {str(e)}')
            return redirect('partial_withdrawal_detail', pk=pk)

        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
            return redirect('partial_withdrawal_detail', pk=pk)    
    # GET request - show approval confirmation
    
    total_savings = Savings.objects.filter(member=withdrawal.member).aggregate(
        total=Sum('month_saving')
    )['total'] or Decimal('0.00')
    
    total_loanable = Loanable.objects.filter(member=withdrawal.member).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    total_investment = Investment.objects.filter(member=withdrawal.member).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    # Calculate what will be withdrawn
    from_loanable = withdrawal.amount_requested / Decimal('2.00')
    from_investment = withdrawal.amount_requested / Decimal('2.00')
    
    # Check if sufficient funds
    has_sufficient_funds = (
        withdrawal.amount_requested <= total_savings and
        from_loanable <= total_loanable and
        from_investment <= total_investment
    )
    
    context = {
        'withdrawal': withdrawal,
        'total_savings': total_savings,
        'total_loanable': total_loanable,
        'total_investment': total_investment,
        'from_loanable': from_loanable,
        'from_investment': from_investment,
        'has_sufficient_funds': has_sufficient_funds,
        'balance_after': total_savings - withdrawal.amount_requested if has_sufficient_funds else None,
    }
    
    return render(request, 'main/approve_partial_withdrawal.html', context)


@login_required
def partial_withdrawal_decline(request, pk):
    """Decline a withdrawal request"""
    withdrawal = get_object_or_404(PartialWithdrawal, pk=pk)
    
    # Check if already processed
    if withdrawal.status != 'Pending':
        messages.warning(request, f'This withdrawal has already been {withdrawal.status.lower()}.')
        return redirect('partial_withdrawal_detail', pk=pk)
    
    if request.method == 'POST':
        reason = request.POST.get('decline_reason', '').strip()
        
        if not reason:
            messages.error(request, 'Please provide a reason for declining.')
            return redirect('partial_withdrawal_decline', pk=pk)
        
        try:
            withdrawal.decline(request.user, reason)
            messages.success(
                request,
                f'Withdrawal request for {withdrawal.member} has been declined.'
            )
            return redirect('partial_withdrawals_list')
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
            return redirect('partial_withdrawal_detail', pk=pk)
    
    # GET request - show decline form
    context = {'withdrawal': withdrawal,}
    return render(request, 'main/partial_withdrawal_decline_form.html', context)


@login_required
def partial_withdrawal_bulk_action(request):
    """Handle bulk actions on withdrawal requests"""
    if request.method != 'POST':
        return redirect('partial_withdrawals_list')
    
    action = request.POST.get('action')
    withdrawal_ids = request.POST.getlist('withdrawal_ids')
    
    if not withdrawal_ids:
        messages.warning(request, 'No withdrawals selected.')
        return redirect('partial_withdrawals_list')
    
    withdrawals = PartialWithdrawal.objects.filter(
        pk__in=withdrawal_ids,
        status='Pending'
    )
    
    if action == 'approve_selected':
        success_count = 0
        error_count = 0
        
        for withdrawal in withdrawals:
            try:
                withdrawal.approve(request.user)
                success_count += 1
            except Exception as e:
                error_count += 1
        
        if success_count:
            messages.success(request, f'Successfully approved {success_count} withdrawal(s).')
        if error_count:
            messages.warning(request, f'Failed to approve {error_count} withdrawal(s).')
    
    elif action == 'decline_selected':
        reason = request.POST.get('bulk_decline_reason', '').strip()
        
        if not reason:
            messages.error(request, 'Please provide a reason for declining.')
            return redirect('partial_withdrawals_list')
        
        decline_count = 0
        for withdrawal in withdrawals:
            try:
                withdrawal.decline(request.user, reason)
                decline_count += 1
            except Exception:
                pass
        
        messages.success(request, f'Declined {decline_count} withdrawal(s).')
    
    return redirect('partial_withdrawals_list')


@login_required
def eligible_members_view(request):
    eligible_members = get_members_eligible_for_withdrawal()
    return render(request, 'withdrawal/members/eligible_members.html', {'eligible_members': eligible_members,})


def guest_request_consumable(request):
    now = timezone.now()

    if request.method == "POST":
        consumable_type_id = request.POST.get("consumable_type")
        loan_term_months = request.POST.get("loan_term_months")
        payslip_file = request.FILES.get("file_payslpt")
        passport = request.FILES.get("passport")
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

        # ✅ Check if guest already has a pending request
        has_pending = ConsumableRequest.objects.filter(
            guest_ippis=guest_ippis, status="Pending"
        ).exists()
        if has_pending:
            messages.error(request, "You already have a pending request. Please wait for it to be processed.")
            return redirect("guest_request_consumable")

        # ✅ Check if guest has paid form fee
        consumable_type_obj = get_object_or_404(ConsumableType, id=consumable_type_id)
        has_paid_fee = ConsumableFormFee.objects.filter(
            guest_name=guest_name.strip(),
            guest_ippis=guest_ippis.strip(),
            consumable_type=consumable_type_obj,
            status="paid"
        ).exists()

        if not has_paid_fee:
            messages.error(
                request,
                f"{guest_name} (IPPIS {guest_ippis}) You must pay the consumable form fee at the Cooperative before making a request."
            )
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

        # ✅ Create request + details inside transaction
        with transaction.atomic():
            try:
                loan_term_months = int(loan_term_months)

                # Create request
                consumable_request = ConsumableRequest.objects.create(
                    consumable_type=consumable_type_obj,
                    file_payslpt=payslip_file,
                    passport=passport,
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

                    # Reduce stock
                    selling_item.quantity -= quantity
                    selling_item.save(update_fields=["quantity"])

                # ✅ Move this outside the loop
                ConsumableFormFee.objects.filter(
                    guest_name=guest_name.strip(),
                    guest_ippis=guest_ippis.strip(),
                    consumable_type=consumable_type_obj,
                    status="paid"
                ).update(status="used")

                messages.success(request, "Your consumable request has been submitted successfully!")
                return redirect("guest_request_consumable")

            except Exception as e:
                messages.error(request, f"An unexpected error occurred: {e}")
                return redirect("guest_request_consumable")

    # GET
    selling_plans = SellingPlan.objects.filter(quantity__gt=0)
    consumable_types = ConsumableType.objects.filter(available=True)

    return render(request,"guest/request_consumable.html",{"consumable_types": consumable_types, "selling_plans": selling_plans},)




@login_required
@group_required(['admin','staff'])
def member_active_requests(request):
    ippis = request.GET.get("ippis", "").strip()
    member = None

    # defaults
    active_loans = LoanRequest.objects.none()
    active_consumables = ConsumableRequest.objects.none()
    active_project_finances = ProjectFinanceRequest.objects.none()
    withdrawals = Withdrawal.objects.none()

    loan_total = loan_paid = loan_balance = 0
    consumable_total = consumable_paid = consumable_balance = 0
    project_total = project_paid = project_balance = 0
    withdrawal_total = 0
    grand_total = grand_paid = grand_balance = 0
    has_active = False

    if ippis:
        try:
            member = Member.objects.get(ippis=ippis)

            # ── Loans ──────────────────────────────────────────────
            active_loans = (
                LoanRequest.objects
                .filter(member=member, status="approved")
                .annotate(
                    total_paid=Coalesce(
                        Sum('repaybacks__amount_paid'),
                        Value(0, output_field=DecimalField(max_digits=14, decimal_places=2))
                    ),
                    repayment_count=Count('repaybacks'),
                    last_payment_date=Max('repaybacks__repayment_date'),
                )
            )

            loan_total = active_loans.aggregate(t=Sum("amount"))["t"] or 0
            loan_paid  = active_loans.aggregate(p=Sum("total_paid"))["p"] or 0
            loan_balance = loan_total - loan_paid

            # ── Consumables ────────────────────────────────────────
            details_total_sq = (
                ConsumableRequestDetail.objects
                .filter(request=OuterRef("pk"))
                .values("request")
                .annotate(
                    total=Sum(
                        ExpressionWrapper(
                            F("quantity") * F("item_price"),
                            output_field=DecimalField(max_digits=14, decimal_places=2)
                        )
                    )
                )
                .values("total")
            )

            repayment_total_sq = (
                PaybackConsumable.objects
                .filter(consumable_request=OuterRef("pk"))
                .values("consumable_request")
                .annotate(
                    total=Sum(
                        "amount_paid",
                        output_field=DecimalField(max_digits=14, decimal_places=2)
                    )
                )
                .values("total")
            )

            active_consumables = (
                ConsumableRequest.objects
                .filter(user=member.member, status="Itempicked")
                .annotate(
                    total_amount_agg=Coalesce(
                        Subquery(details_total_sq),
                        Value(0, output_field=DecimalField(max_digits=14, decimal_places=2))
                    ),
                    total_paid_agg=Coalesce(
                        Subquery(repayment_total_sq),
                        Value(0, output_field=DecimalField(max_digits=14, decimal_places=2))
                    ),
                )
                .annotate(
                    balance_agg=ExpressionWrapper(
                        F("total_amount_agg") - F("total_paid_agg"),
                        output_field=DecimalField(max_digits=14, decimal_places=2)
                    )
                )
            )

            consumable_total   = active_consumables.aggregate(t=Sum("total_amount_agg"))["t"] or 0
            consumable_paid    = active_consumables.aggregate(p=Sum("total_paid_agg"))["p"] or 0
            consumable_balance = active_consumables.aggregate(b=Sum("balance_agg"))["b"] or 0

            # ── Project Finance ────────────────────────────────────
            active_project_finances = (
                ProjectFinanceRequest.objects
                .filter(application__member=member, status="Approved")
                .annotate(
                    balance=ExpressionWrapper(
                        F("requested_amount") - F("total_repayment_amount"),
                        output_field=DecimalField(max_digits=12, decimal_places=2)
                    )
                )
            )

            project_total   = active_project_finances.aggregate(t=Sum("requested_amount"))["t"] or 0
            project_paid    = active_project_finances.aggregate(p=Sum("total_repayment_amount"))["p"] or 0
            project_balance = project_total - project_paid

            # ── Withdrawals ────────────────────────────────────────
            withdrawals      = Withdrawal.objects.filter(member=member, status__in=["Pending", "Approved"])
            withdrawal_total = withdrawals.aggregate(t=Sum("total_withdrawn"))["t"] or 0

            # ── Totals ─────────────────────────────────────────────
            grand_total   = loan_total + consumable_total + project_total
            grand_paid    = loan_paid  + consumable_paid  + project_paid
            grand_balance = grand_total - grand_paid

            has_active = (
                active_loans.exists()
                or active_consumables.exists()
                or active_project_finances.exists()
                or withdrawals.exists()
            )

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
        "withdrawals": withdrawals,

        "loan_total": loan_total,
        "loan_paid": loan_paid,
        "loan_balance": loan_balance,

        "consumable_total": consumable_total,
        "consumable_paid": consumable_paid,
        "consumable_balance": consumable_balance,

        "project_total": project_total,
        "project_paid": project_paid,
        "project_balance": project_balance,

        "withdrawal_total": withdrawal_total,

        "grand_total": grand_total,
        "grand_paid": grand_paid,
        "grand_balance": grand_balance,

        "has_active": has_active,
    })


@transaction.atomic
@login_required
@group_required(['admin'])
def upload_opening_balances(request):
    if request.method == "POST" and request.FILES.get("file"):
        file = request.FILES["file"]

        try:
            wb = openpyxl.load_workbook(file)
            ws = wb.active
        except Exception:
            messages.error(request, "Invalid Excel file. Please upload a valid .xlsx file.")
            return redirect("upload_opening_balances")

        created, updated, skipped = 0, 0, 0
        opening_date = "2025-11-25"   # fixed opening balance date
        
        for row in ws.iter_rows(min_row=2, values_only=True):
            ippis, savings_total, loanable_total, investment_total = row

            if not ippis:
                skipped += 1
                continue

            try:
                member = Member.objects.get(ippis=str(ippis).strip())
            except Member.DoesNotExist:
                skipped += 1
                messages.warning(request, f"⚠️ Member with IPPIS {ippis} not found, skipped")
                continue

            # ----------------------------
            # Update Member Total Savings
            # ----------------------------
            member.total_savings = Decimal(savings_total or 0)
            member.save(update_fields=["total_savings"])

            # ----------------------------
            # Savings Record
            # ----------------------------
            if savings_total:
                _, created_flag = Savings.objects.update_or_create(
                    member=member,
                    month=opening_date,
                    defaults={
                        "month_saving": Decimal(savings_total or 0),
                        "original_amount": Decimal(savings_total or 0),
                    },
                )
                created += 1 if created_flag else 1

            # ----------------------------
            # Loanable Record
            # ----------------------------
            _, created_flag = Loanable.objects.update_or_create(
                member=member,
                month=opening_date,
                defaults={
                    "amount": Decimal(loanable_total or 0),
                    "total_amount": Decimal(loanable_total or 0),
                },
            )
            created += 1 if created_flag else 1

            # ----------------------------
            # Investment Record
            # ----------------------------
            _, created_flag = Investment.objects.update_or_create(
                member=member,
                month=opening_date,
                defaults={
                    "amount": Decimal(investment_total or 0),
                    "total_amount": Decimal(investment_total or 0),
                },
            )
            created += 1 if created_flag else 1

        # Summary Message
        messages.success(
            request,
            f"Opening balances processed! {created} created, {updated} updated, {skipped} skipped."
        )

        return redirect("upload_opening_balances")

    return render(request, "main/upload_opening_balances.html")



@login_required(login_url='login')
def loan_totals(request):
    # Aggregate by month
    savings_by_month = (
        Savings.objects.annotate(period=TruncMonth("date_created"))
        .values("period")
        .annotate(total_savings=Sum("original_amount"))
    )
    loanable_by_month = (
        Loanable.objects.annotate(period=TruncMonth("date_created"))
        .values("period")
        .annotate(total_loanable=Sum("amount"))
    )
    investment_by_month = (
        Investment.objects.annotate(period=TruncMonth("date_created"))
        .values("period")
        .annotate(total_investment=Sum("amount"))
    )
    interest_by_month = (
        Interest.objects.annotate(period=TruncMonth("date_deducted"))
        .values("period")
        .annotate(total_interest=Sum("amount_deducted"))
    )

    loans_by_month = (
        LoanRequest.objects.annotate(period=TruncMonth("application_date"))
        .values("period", "loan_type__name")
        .annotate(
            total_requested=Sum("amount"),
            total_approved=Sum("approved_amount"),
        )
    )

    # --- Normalize months to datetime.date and collect unique months ---
    all_months_set = set()
    for qs in [savings_by_month, loanable_by_month, investment_by_month, interest_by_month]:
        for item in qs:
            period = item["period"]
            if isinstance(period, datetime.datetime):
                period = period.date()
            all_months_set.add(period)

    all_months = sorted(all_months_set, reverse=True)  # now safe

    context = {
        "all_months": all_months,
        "savings_by_month": savings_by_month,
        "loanable_by_month": loanable_by_month,
        "investment_by_month": investment_by_month,
        "interest_by_month": interest_by_month,
        "loans_by_month": loans_by_month,
    }
    return render(request, "main/loan_totals.html", context)


from datetime import date
from decimal import Decimal

@login_required
@group_required(['admin'])
def dividend_report(request):
    start_date = None
    end_date = None
    show_profit_section = False
    profit = None
    unit_profit = None
    members = []
    total_savings = Decimal("0.00")
    total_shares = Decimal("0.00")
    errors = {}

    last_dividend = Dividend.objects.order_by('-created_at').first()
    if last_dividend:
        unit_profit = last_dividend.unit_profit

    def get_members_queryset(start, end):
        """Reusable savings filter — change 'month' to your actual field name"""
        savings_sum = (
            Savings.objects.filter(
                member=OuterRef("pk"),
                month__gte=start,   # ✅ use ONE consistent field everywhere
                month__lte=end,
            )
            .values("member")
            .annotate(total=Sum("month_saving", output_field=DecimalField()))
            .values("total")
        )
        return (
            Member.objects.annotate(
                period_savings=Subquery(savings_sum, output_field=DecimalField())
            ).filter(period_savings__gt=0)
        )

    # ✅ FILTER POST
    if request.method == "POST" and "filter" in request.POST:
        start_str = request.POST.get("start_date")
        end_str = request.POST.get("end_date")
        try:
            start_date = date.fromisoformat(start_str)
            end_date = date.fromisoformat(end_str)
            return redirect(
                f"{request.path}?start_date={start_date}&end_date={end_date}&filtered=1"
            )
        except (ValueError, TypeError):
            errors["date"] = "Invalid date range provided."

    # ✅ DISTRIBUTE POST
    elif request.method == "POST" and "distribute" in request.POST:
        start_str = request.POST.get("start_date")
        end_str = request.POST.get("end_date")
        profit_str = request.POST.get("profit")
        distribution_date_str = request.POST.get("distribution_date")

        try:
            start_date = date.fromisoformat(start_str)
            end_date = date.fromisoformat(end_str)
        except (ValueError, TypeError):
            errors["date"] = "Invalid date range."

        try:
            profit = Decimal(profit_str) if profit_str else None
        except Exception:
            errors["profit"] = "Invalid profit value."

        try:
            distribution_date = date.fromisoformat(distribution_date_str) if distribution_date_str else None
        except (ValueError, TypeError):
            errors["distribution_date"] = "Invalid distribution date."
            distribution_date = None

        if not errors and start_date and end_date:
            members = get_members_queryset(start_date, end_date)
            total_savings = sum([m.period_savings or Decimal("0.00") for m in members])
            total_shares = total_savings / Decimal("1000") if total_savings > 0 else Decimal("0.00")

            if profit and distribution_date and total_shares > 0:
                new_unit_profit = profit / total_shares
                unit_profit = (unit_profit + new_unit_profit) if unit_profit else new_unit_profit

                with transaction.atomic():
                    dividends_to_create = []
                    members_to_update = []

                    for member in members:
                        member_savings = member.period_savings or Decimal("0.00")
                        member_shares = member_savings / Decimal("1000")
                        dividend_amount = member_shares * new_unit_profit

                        dividends_to_create.append(
                            Dividend(
                                member=member,
                                profit=profit,
                                unit_profit=new_unit_profit,
                                dividend_amount=dividend_amount,
                                distribution_date=distribution_date,
                                created_by=request.user,
                            )
                        )
                        member.total_profit = (member.total_profit or Decimal("0.00")) + dividend_amount
                        members_to_update.append(member)

                    Dividend.objects.bulk_create(dividends_to_create)
                    Member.objects.bulk_update(members_to_update, ["total_profit"])

                return redirect("distribute_dividends")

        show_profit_section = True

    # ✅ GET with filter params
    elif request.method == "GET":
        start_str = request.GET.get("start_date")
        end_str = request.GET.get("end_date")

        if start_str and end_str:
            try:
                start_date = date.fromisoformat(start_str)
                end_date = date.fromisoformat(end_str)
                show_profit_section = bool(request.GET.get("filtered"))
                members = get_members_queryset(start_date, end_date)
                total_savings = sum([m.period_savings or Decimal("0.00") for m in members])
                total_shares = total_savings / Decimal("1000") if total_savings > 0 else Decimal("0.00")
            except (ValueError, TypeError):
                errors["date"] = "Invalid date parameters in URL."

    # ✅ Default: all members, no filter
    if not members and not start_date:
        savings_sum = (
            Savings.objects.filter(member=OuterRef("pk"))
            .values("member")
            .annotate(total=Sum("month_saving", output_field=DecimalField()))
            .values("total")
        )
        members = Member.objects.annotate(
            period_savings=Subquery(savings_sum, output_field=DecimalField())
        )
        total_savings = sum([m.period_savings or Decimal("0.00") for m in members])
        total_shares = total_savings / Decimal("1000") if total_savings > 0 else Decimal("0.00")

    # ✅ Enrich members
    enriched_members = []
    for idx, m in enumerate(members, start=1):
        savings = m.period_savings or Decimal("0.00")
        share = savings / Decimal("1000")
        current_dividend = share * (unit_profit or Decimal("0.00"))
        enriched_members.append({
            "sn": idx,
            "name": str(m),
            "ippis": getattr(m, "ippis", ""),
            "savings": savings,
            "share": share,
            "unit_profit": unit_profit or Decimal("0.00"),
            "dividend_amount": current_dividend,
            "total_profit": m.total_profit or Decimal("0.00"),
        })

    paginator = Paginator(enriched_members, 80)
    page_number = request.GET.get("page", 1)
    shares = paginator.get_page(page_number)

    context = {
        "shares": shares,
        "total_savings": total_savings,
        "total_shares": total_shares,
        "unit_profit": unit_profit,
        "profit": profit,
        "show_profit_section": show_profit_section,
        "start_date": start_date,
        "end_date": end_date,
        "errors": errors,
    }

    return render(request, "main/dividends_report.html", context)


# # ===inline  Dividend Distribution Form === #
# class ProfitForm(forms.Form):
#     start_date = forms.DateField(
#         label="Savings Start Date",
#         widget=forms.DateInput(attrs={'type': 'date'}),
#         required=True
#     )
#     end_date = forms.DateField(
#         label="Savings End Date",
#         widget=forms.DateInput(attrs={'type': 'date'}),
#         required=True
#     )
#     profit = forms.DecimalField(
#         label="Enter Profit",
#         decimal_places=2,
#         max_digits=15,
#         required=False
#     )
#     distribution_date = forms.DateField(
#         label="Distribution Date",
#         widget=forms.DateInput(attrs={'type': 'date'}),
#         required=False
#     )
# #=== Dividend Distribution Form End === #


# @login_required
# @group_required(['admin'])
# def dividend_report(request):
#     # ✅ FIX 1: Read filter params from GET so pagination preserves them
#     start_date = None
#     end_date = None
#     show_profit_section = False
#     profit = None
#     unit_profit = None
#     members = []
#     total_savings = Decimal("0.00")
#     total_shares = Decimal("0.00")

#     # ✅ Get last recorded unit profit (if any)
#     last_dividend = Dividend.objects.order_by('-created_at').first()
#     if last_dividend:
#         unit_profit = last_dividend.unit_profit

#     # ✅ FIX 2: Persist filter via GET params after POST redirect
#     if request.method == "POST" and "filter" in request.POST:
#         form = ProfitForm(request.POST)
#         if form.is_valid():
#             start_date = form.cleaned_data["start_date"]
#             end_date = form.cleaned_data["end_date"]
#             # Redirect to GET so pagination works
#             return redirect(
#                 f"{request.path}?start_date={start_date}&end_date={end_date}&filtered=1"
#             )

#     elif request.method == "POST" and "distribute" in request.POST:
#         form = ProfitForm(request.POST)
#         if form.is_valid():
#             start_date = form.cleaned_data["start_date"]
#             end_date = form.cleaned_data["end_date"]
#             profit = form.cleaned_data["profit"]
#             distribution_date = form.cleaned_data["distribution_date"]

#             # ✅ FIX 3: Use __date lookup to include full end_date day
#             savings_sum = (
#                 Savings.objects.filter(
#                     member=OuterRef("pk"),
#                     date_created__date__gte=start_date,
#                     date_created__date__lte=end_date,  # ← FIX: includes full end day
#                 )
#                 .values("member")
#                 .annotate(total=Sum("month_saving", output_field=DecimalField()))
#                 .values("total")
#             )

#             members = (
#                 Member.objects.annotate(
#                     period_savings=Subquery(savings_sum, output_field=DecimalField())
#                 )
#                 .filter(period_savings__gt=0)
#             )

#             total_savings = sum([m.period_savings or Decimal("0.00") for m in members])
#             total_shares = total_savings / Decimal("1000") if total_savings > 0 else Decimal("0.00")

#             if profit and distribution_date and total_shares > 0:
#                 new_unit_profit = profit / total_shares

#                 if unit_profit:
#                     unit_profit += new_unit_profit
#                 else:
#                     unit_profit = new_unit_profit

#                 with transaction.atomic():
#                     dividends_to_create = []
#                     members_to_update = []

#                     for member in members:
#                         member_savings = member.period_savings or Decimal("0.00")
#                         member_shares = member_savings / Decimal("1000")
#                         dividend_amount = member_shares * new_unit_profit

#                         dividends_to_create.append(
#                             Dividend(
#                                 member=member,
#                                 profit=profit,
#                                 unit_profit=new_unit_profit,
#                                 dividend_amount=dividend_amount,
#                                 distribution_date=distribution_date,
#                                 created_by=request.user,
#                             )
#                         )

#                         if member.total_profit is None:
#                             member.total_profit = Decimal("0.00")
#                         member.total_profit += dividend_amount
#                         members_to_update.append(member)

#                     Dividend.objects.bulk_create(dividends_to_create)
#                     Member.objects.bulk_update(members_to_update, ["total_profit"])

#                 return redirect("distribute_dividends")

#             show_profit_section = True

#     else:
#         form = ProfitForm()

#     # ✅ FIX 4: On GET, read filter params from query string (supports pagination)
#     if request.method == "GET":
#         start_date_str = request.GET.get("start_date")
#         end_date_str = request.GET.get("end_date")
#         filtered = request.GET.get("filtered")

#         if start_date_str and end_date_str:
#             try:
#                 from datetime import date
#                 start_date = date.fromisoformat(start_date_str)
#                 end_date = date.fromisoformat(end_date_str)
#                 show_profit_section = bool(filtered)

#                 savings_sum = (
#                     Savings.objects.filter(
#                         member=OuterRef("pk"),
#                         date_created__date__gte=start_date,
#                         date_created__date__lte=end_date,
#                     )
#                     .values("member")
#                     .annotate(total=Sum("month_saving", output_field=DecimalField()))
#                     .values("total")
#                 )

#                 members = (
#                     Member.objects.annotate(
#                         period_savings=Subquery(savings_sum, output_field=DecimalField())
#                     )
#                     .filter(period_savings__gt=0)
#                 )

#                 total_savings = sum([m.period_savings or Decimal("0.00") for m in members])
#                 total_shares = total_savings / Decimal("1000") if total_savings > 0 else Decimal("0.00")

#                 # Pre-fill form with GET params
#                 form = ProfitForm(initial={"start_date": start_date, "end_date": end_date})

#             except ValueError:
#                 pass

#     # ✅ Default: show all members if no filter applied
#     if not members and not start_date:
#         savings_sum = (
#             Savings.objects.filter(member=OuterRef("pk"))
#             .values("member")
#             .annotate(total=Sum("month_saving", output_field=DecimalField()))
#             .values("total")
#         )
#         members = Member.objects.annotate(
#             period_savings=Subquery(savings_sum, output_field=DecimalField())
#         )
#         total_savings = sum([m.period_savings or Decimal("0.00") for m in members])
#         total_shares = total_savings / Decimal("1000") if total_savings > 0 else Decimal("0.00")

#     # ✅ Step 3: Prepare enriched data for template
#     enriched_members = []
#     for idx, m in enumerate(members, start=1):
#         savings = m.period_savings or Decimal("0.00")
#         share = savings / Decimal("1000")
#         current_dividend = share * (unit_profit or Decimal("0.00"))

#         enriched_members.append({
#             "sn": idx,
#             "name": str(m),
#             "ippis": getattr(m, "ippis", ""),
#             "savings": savings,
#             "share": share,
#             "unit_profit": unit_profit or Decimal("0.00"),
#             "dividend_amount": current_dividend,
#             "total_profit": m.total_profit or Decimal("0.00"),
#         })

#     paginator = Paginator(enriched_members, 80)
#     page_number = request.GET.get("page", 1)
#     shares = paginator.get_page(page_number)

#     context = {
#         "form": form,
#         "shares": shares,
#         "total_savings": total_savings,
#         "total_shares": total_shares,
#         "unit_profit": unit_profit,
#         "profit": profit,
#         "show_profit_section": show_profit_section,
#         "start_date": start_date,
#         "end_date": end_date,
#     }

#     return render(request, "main/dividends_report.html", context)

@login_required
@group_required(['admin'])
def delete_dividend_round_bulk(request, profit_amount):
    try:
        # ✅ Convert profit_amount (string from URL) to Decimal
        profit_amount = Decimal(profit_amount)
    except InvalidOperation:
        messages.error(request, "Invalid profit amount.")
        return redirect("distribute_dividends")

    if request.method == "POST":
        with transaction.atomic():
            # Get all dividends for this profit round
            dividends = Dividend.objects.filter(profit=profit_amount).select_related('member')
            count = dividends.count()

            if count == 0:
                messages.warning(request, "No dividends found for this profit round.")
                return redirect("distribute_dividends")

            #  Group dividends by member in one pass
            member_adjustments = {}
            for dividend in dividends:
                member_id = dividend.member.id
                dividend_amount = dividend.dividend_amount or Decimal("0.00")
                member_adjustments[member_id] = member_adjustments.get(member_id, Decimal("0.00")) + dividend_amount

            #  Fetch all affected members at once
            member_ids = list(member_adjustments.keys())
            members = Member.objects.filter(id__in=member_ids).select_for_update()

            #  Adjust profits in memory
            members_to_update = []
            for member in members:
                adjustment = member_adjustments.get(member.id, Decimal("0.00"))

                if member.total_profit is None:
                    member.total_profit = Decimal("0.00")

                member.total_profit -= adjustment

                # Prevent negative profit
                if member.total_profit < 0:
                    member.total_profit = Decimal("0.00")

                members_to_update.append(member)

            #  Bulk update members
            if members_to_update:
                Member.objects.bulk_update(members_to_update, ["total_profit"])

            #  Delete all dividends in one query
            dividends.delete()

            #  Safe Decimal formatting
            messages.success(
                request,
                f"Successfully deleted {count} dividend(s) from profit round of ₦{profit_amount:,.2f}."
            )

        return redirect("dividend_list")

    # ===== GET request - show confirmation page =====
    dividends = Dividend.objects.filter(profit=profit_amount).select_related('member').order_by('-dividend_amount')
    dividend_count = dividends.count()

    #  Use aggregate to calculate total (safer + faster than Python sum)
    from django.db.models import Sum
    total_amount = dividends.aggregate(total=Sum("dividend_amount"))["total"] or Decimal("0.00")

    return render(request, "main/confirm_delete_dividend_round.html", {
        "profit_amount": profit_amount,
        "dividend_count": dividend_count,
        "total_amount": total_amount,
        "dividends": dividends[:10],  # Show preview of first 10
    })



@login_required
@group_required(['admin'])
def list_dividend_rounds(request):
    # Group by profit and created_by, then summarize
    rounds = (
        Dividend.objects
        .values("profit", "created_by", "created_by__first_name", "created_by__last_name")  
        .annotate(
            total_amount=Sum("dividend_amount"),
            count=Count("id"),
            created_at=Min("created_at"),  # first time the round was created
            distribution_date=Min("distribution_date")  # first time the round was created
        )
        .order_by("-created_at")
    )

    return render(request, "main/dividend_rounds_list.html", {"rounds": rounds})


def popup_message_form(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        message = request.POST.get('message')
        link_url = request.POST.get('link_url')
        is_active = request.POST.get('is_active') == 'on'

        start_date = parse_datetime(request.POST.get('start_date')) or timezone.now()
        end_date = parse_datetime(request.POST.get('end_date')) or (timezone.now() + timezone.timedelta(days=1))

        # Make timezone-aware
        if timezone.is_naive(start_date):
            start_date = timezone.make_aware(start_date)
        if timezone.is_naive(end_date):
            end_date = timezone.make_aware(end_date)

        Popup.objects.create(
            title=title,
            message=message,
            link_url=link_url or None,
            is_active=is_active,
            start_date=start_date,
            end_date=end_date,
        )

        messages.success(request, 'Popup message created successfully!')
        return redirect('popup_form')

    return render(request, 'main/popup_message.html')


@login_required
@group_required(['admin','staff'])
def member_active_summary(request, pk):
    member = get_object_or_404(Member, pk=pk)

    # 🟦 Active Loan Requests
    active_loans = (
        LoanRequest.objects
        .filter(member=member, status="approved")
        .annotate(
            total_paid=Coalesce(
                Sum('repaybacks__amount_paid'),
                Value(0, output_field=DecimalField(max_digits=14, decimal_places=2))  # ✅ fix
            ),
            repayment_count=Count('repaybacks'),
            last_payment_date=Max('repaybacks__repayment_date')
        )
    )
  
    loan_total = active_loans.aggregate(total=Sum("amount"))["total"] or 0
    loan_paid = active_loans.aggregate(paid=Sum("total_paid"))["paid"] or 0
    loan_balance = loan_total - loan_paid

    details_total_sq = (
        ConsumableRequestDetail.objects
        .filter(request=OuterRef("pk"))
        .values("request")
        .annotate(
            total=Sum(
                ExpressionWrapper(
                    F("quantity") * F("item_price"),
                    output_field=DecimalField(max_digits=14, decimal_places=2)
                )
            )
        )
        .values("total")
    )

    repayment_total_sq = (
        PaybackConsumable.objects
        .filter(consumable_request=OuterRef("pk"))
        .values("consumable_request")
        .annotate(
            total=Sum("amount_paid", output_field=DecimalField(max_digits=14, decimal_places=2))
        )
        .values("total")
    )

    active_consumables = (
        ConsumableRequest.objects
        .filter(user=member.member, status="Itempicked")
        .annotate(
            total_amount_agg=Coalesce(
                Subquery(details_total_sq),
                Value(0, output_field=DecimalField(max_digits=14, decimal_places=2))
            ),
            total_paid_agg=Coalesce(
                Subquery(repayment_total_sq),
                Value(0, output_field=DecimalField(max_digits=14, decimal_places=2))
            ),
        )
        .annotate(
            balance_agg=ExpressionWrapper(
                F("total_amount_agg") - F("total_paid_agg"),
                output_field=DecimalField(max_digits=14, decimal_places=2)
            )
        )
    )

    consumable_total = active_consumables.aggregate(total=Sum("total_amount_agg"))["total"] or 0
    consumable_paid = active_consumables.aggregate(total=Sum("total_paid_agg"))["total"] or 0
    consumable_balance = active_consumables.aggregate(total=Sum("balance_agg"))["total"] or 0


    # 🟨 Active Project Finance Requests
    active_project_finances = ProjectFinanceRequest.objects.filter(application__member=member, status="Approved").annotate(
        balance=ExpressionWrapper(F("requested_amount") - F("total_repayment_amount"), output_field=DecimalField(max_digits=12, decimal_places=2))
    )
    project_total = active_project_finances.aggregate(total=Sum("requested_amount"))["total"] or 0
    project_paid = active_project_finances.aggregate(paid=Sum("total_repayment_amount"))["paid"] or 0
    project_balance = project_total - project_paid

    # 🟧 Withdrawals (Pending or Approved)
    withdrawals = Withdrawal.objects.filter(member=member, status__in=["Pending", "Approved"])
    withdrawal_total = withdrawals.aggregate(total=Sum("total_withdrawn"))["total"] or 0

    # 🧮 Overall totals
    grand_total = loan_total + consumable_total + project_total
    grand_paid = loan_paid + consumable_paid + project_paid
    grand_balance = grand_total - grand_paid

    has_active = (
        active_loans.exists()
        or active_consumables.exists()
        or active_project_finances.exists()
        or withdrawals.exists()
    )

    messages.info(request, f"Active Requests for {member.member.get_full_name()}.")

    context = {
        "member": member,
        "active_loans": active_loans,
        "active_consumables": active_consumables,
        "active_project_finances": active_project_finances,
        "withdrawals": withdrawals,

        "loan_total": loan_total,
        "loan_paid": loan_paid,
        "loan_balance": loan_balance,

        "consumable_total": consumable_total,
        "consumable_paid": consumable_paid,
        "consumable_balance": consumable_balance,

        "project_total": project_total,
        "project_paid": project_paid,
        "project_balance": project_balance,

        "withdrawal_total": withdrawal_total,

        "grand_total": grand_total,
        "grand_paid": grand_paid,
        "grand_balance": grand_balance,

        "has_active": has_active,
    }
    return render(request, "main/member_active_summary.html", context)



@login_required
@group_required(['admin'])
def user_activity_list(request):
    if request.user.is_staff:
        activities = UserActivity.objects.select_related('user').order_by('-timestamp')
    else:
        activities = UserActivity.objects.filter(user=request.user).order_by('-timestamp')

    paginator = Paginator(activities, 50)  # 50 logs per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'main/user_activity_list.html', {'page_obj': page_obj})


login_required
@group_required(['admin'])
def delete_user_activity(request, pk):
    activity = get_object_or_404(UserActivity, pk=pk)

    if request.method == "POST":
        activity.delete()
        messages.success(request, "User activity deleted successfully.")
        return redirect("user_activity_list")

    return render(request, "main/delete_user_activity.html", {"activity": activity})