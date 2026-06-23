
from email.mime import application
from itertools import count
from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from dateutil.relativedelta import relativedelta  
from datetime import date 
import time
from accounts.decorators import *
from django.core.exceptions import ValidationError
from django.db.models import Sum, DecimalField, F, Q, Value,Count
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator
from django.db.models import Sum
from django.db import transaction
from decimal import Decimal
from decimal import Decimal
from django.core.cache import cache
from django.urls import reverse 
from django.contrib import messages
from django.db.models import Prefetch
from django.utils import timezone
import datetime
import json
from django.http import JsonResponse
from datetime import date
from datetime import datetime
from accounts.decorators import group_required
from projectfinance.forms import ProjectFinanceRequestForm
from main.models import *
from loan.models import *
from accounts.models import *
from inventory_app.models import *
from consumable.models import *
from consumable.models import *
from projectfinance.models import *
from .models import *
from form_app.models import *
from ram_app.models import *
from inventory_app.models import *
from special_savings.models import *


    
@login_required(login_url='login')
@group_required(['members'])
def member_dashboard(request):
    try:
        member = Member.objects.get(member=request.user)
    except Member.DoesNotExist:
        return redirect('login')
    

    pending_guarantor_requests = ProjectFinanceRequest.objects.filter(
        guarantor=member,
        guarantor_status='Pending'
    ).order_by('-created_at').select_related('application__member__member')
    
    
    inventory_pending_guarantor_requests = MemberRequest.objects.filter(
        guarantor=member,
        guarantor_accepted=False,
        status="Pending"
    ).select_related('member__member', 'guarantor')
    
    pending_guarantor_loans = LoanRequest.objects.filter(
        guarantor=member,
        guarantor_accepted=False,
        status="pending"
    )
    
    total_savings = Savings.objects.filter(member=member).aggregate(
        total=Sum('month_saving')
    )['total'] or 0
    # print(total_savings)

    loanable_total = Loanable.objects.filter(member=member).aggregate(
        total=Sum('amount')
    )['total'] or 0

    investment_total = Investment.objects.filter(member=member).aggregate(
        total=Sum('amount')
    )['total'] or 0

    today = date.today()
    current_month = today.month
    current_year = today.year

    first_day_of_current_month = date(current_year, current_month, 1)
    previous_month_date = first_day_of_current_month - relativedelta(months=4)
    previous_month = previous_month_date.month
    previous_year = previous_month_date.year

    monthly_saving = Savings.objects.filter(
        member=member, 
        month__month=current_month, 
        month__year=current_year
    ).first()
    

    previous_monthly_saving = Savings.objects.filter(
        member=member, 
        month__month=previous_month, 
        month__year=previous_year
    ).first()

    # Prefer approved loan, fallback to rejected if none
    active_loan = LoanRequest.objects.filter(
        member=member, 
        status='approved'
    ).order_by('-approval_date').first()
    if not active_loan:
        active_loan = LoanRequest.objects.filter(
            member=member, 
            status='rejected'
        ).order_by('-approval_date').first()

    loan_paid = loan_balance = monthly_payment = 0
    if active_loan and active_loan.status == 'approved':
        repaybacks = LoanRepayback.objects.filter(loan_request=active_loan)
        loan_paid = repaybacks.aggregate(total=Sum('amount_paid'))['total'] or 0
        loan_balance = active_loan.approved_amount - loan_paid
        monthly_payment = active_loan.monthly_payment
        # print(monthly_payment,monthly_payment)
    loan_types = LoanType.objects.all()
    
    consumable_requests = ConsumableRequest.objects.filter(user=request.user) \
        .prefetch_related('details__item') \
        .order_by('-date_created')[:5]

    approved_consumable = ConsumableRequest.objects.filter(user=request.user, status='itempicked') \
        .order_by('-date_created')

    total_remaining = 0
    consumable_data = []

    for consumable in approved_consumable:
        approved_amount = consumable.calculate_total_price()
        total_paid = consumable.total_paid
        balance = approved_amount - total_paid
        total_remaining += balance
        
        if consumable.details.exists():
            loan_term_months = consumable.details.first().loan_term_months
        else:
            loan_term_months = 1
        
        monthly_payment = approved_amount / loan_term_months

        consumable_data.append({ 
            'consumable': consumable,
            'approved_amount': approved_amount,
            'total_paid': total_paid,
            'balance': balance,
            'monthly_payment': monthly_payment,
        })
        # ← loop ends here
       
   # ── item requests block ──
    item_requests = MemberRequest.objects.none()
    approved_item_requests = MemberRequest.objects.none()
    item_data = []
    item_total_remaining = Decimal('0.00')
    total_items_value = Decimal('0.00')
    total_paid_all = Decimal('0.00')

    item_requests = MemberRequest.objects.filter(member=member) \
        .prefetch_related('details__item__received_item') \
        .order_by('-date_created')[:5]

    approved_item_requests = MemberRequest.objects.filter(
        member=member, status='ItemPicked'
    ).prefetch_related(
        'details__item__received_item',
        'repayments'
    ).order_by('-date_created')

    for item in approved_item_requests:
        approved_amount = item.calculate_total_price()
        total_paid = item.total_paid
        balance = approved_amount - total_paid
        item_total_remaining += balance

        details = list(item.details.all())  # ← force evaluate once

        monthly_payment = sum(
            d.total_price / d.duration_months
            for d in details
            if d.duration_months
        ) if details else Decimal('0.00')

        paid_count = item.repayments.count()
        total_months = sum(
            d.duration_months for d in details if d.duration_months
        )
        remaining_count = max(total_months - paid_count, 0)
        # collect per-detail markup info for display
        detail_breakdown = [
            {
                'brand': d.item.received_item.brand,
                'model': d.item.received_item.model_name,
                'quantity': d.quantity,
                'original_price': d.item.selling_price_per_unit,   # before markup
                'item_price': d.item_price,                         # after markup
                'markup_rate': d.markup_rate,                       # e.g. Decimal('5.00')
                'duration_months': d.duration_months,
                'total_price': d.total_price,
            }
            for d in details
        ]

        item_data.append({
            'item': item,
            'approved_amount': approved_amount,
            'total_paid': total_paid,
            'balance': balance,
            'monthly_payment': monthly_payment,
            'detail_breakdown': detail_breakdown,          # ← new
            'has_markup': any(d['markup_rate'] for d in detail_breakdown),  # ← new
            'paid_count': paid_count,               # ← new
            'remaining_count': remaining_count,     # ← new
            'total_months': total_months,           # ← new
        })

    total_items_value = sum(e['approved_amount'] for e in item_data)
    total_paid_all = sum(e['total_paid'] for e in item_data)
    total_paid_count = sum(e['paid_count'] for e in item_data)          # ← new
    total_remaining_count = sum(e['remaining_count'] for e in item_data) # ← new
   
    context = {
        'member': member,
        'total_savings': total_savings,
        'monthly_saving': monthly_saving.month_saving if monthly_saving else 0,
        'previous_monthly_saving': previous_monthly_saving.month_saving if previous_monthly_saving else 0,
        'loan': active_loan,
        'loan_paid': loan_paid,
        'loan_balance': loan_balance,
        'monthly_payment': monthly_payment,
        'loan_types': loan_types,
        'consumable_requests': consumable_requests,
        'approved_consumable': consumable_data,
        'item_requests': item_requests,
        'approved_item_requests': approved_item_requests,
        'item_data': item_data,
        'item_total_remaining': item_total_remaining,
        'total_items_value': total_items_value,
        'total_paid_all': total_paid_all,
        'item_total_remaining': item_total_remaining,
        'total_paid_count': total_paid_count,
        'total_remaining_count': total_remaining_count,
        
        
        'loanable_total': loanable_total,
        'investment_total': investment_total,
        'approved_consumable': consumable_data,
        'total_remaining': total_remaining,
        "pending_guarantor_loans": pending_guarantor_loans,
        'pending_guarantor_requests':pending_guarantor_requests,
        'inventory_pending_guarantor_requests': inventory_pending_guarantor_requests,
    }

    return render(request, 'member/member_dashboard.html', context)

@login_required
@group_required(['members','non staff member','admin','loan committee'])
def member_savings(request):
    try:
        member = Member.objects.get(member=request.user)
    except Member.DoesNotExist:
        return HttpResponse("Access Denied: You don't have a member profile.")

    # Fetch all savings for this member
    savings_list = Savings.objects.filter(member=member).order_by('-month')

    # Pagination (10 records per page)
    paginator = Paginator(savings_list, 10)
    page_number = request.GET.get('page')
    savings = paginator.get_page(page_number)

    # Total savings BEFORE deductions
    total_savings = savings_list.aggregate(total=Sum('month_saving'))['total'] or 0

    # Get subscription fee from Interest table if available
    subscription_fee = member.interest.amount if hasattr(member, 'interest') and member.interest else 0

    # Deduct subscription fee
    net_savings = total_savings - subscription_fee

    # Calculate Investment and Loanable
    total_investment = net_savings / 2
    total_loanable = net_savings / 2

    context = {
        'member': member,
        'savings': savings,  # paginated object
        'total_savings': total_savings,
        'total_investment': total_investment,
        'total_loanable': total_loanable,
    }

    return render(request, 'member/member_savings.html', context)


# ===================== Special saving views =================

login_required
@group_required(['members','non staff member','admin','loan committee'])
def member_special_savings(request):
    try:
        member = request.user.member
    except Member.DoesNotExist:
        return HttpResponse("Access Denied: You don't have a member profile.")

    # Queryset
    special_savings_list = SpecialSavings.objects.filter(member=member).order_by('-id')

    # Pagination (10 per page)
    paginator = Paginator(special_savings_list, 12)
    page_number = request.GET.get('page')
    special_savings = paginator.get_page(page_number)

    # Member balance
    total_special_saving = member.total_special_savings

    context = {
        "member": member,
        "special_savings": special_savings,  # paginated object
        "total_special_saving": total_special_saving,
    }

    return render(request, 'member/member_special_savings.html', context)


@login_required
@group_required(['members','non staff member','admin','loan committee'])
def request_special_savings_withdrawal(request):
    try:
        member = request.user.member
    except Member.DoesNotExist:
        return HttpResponse("Access Denied: You don't have a member profile.")

    # Use the member's actual balance field
    available_balance = member.total_special_savings

    if request.method == "POST":
        try:
            amount = Decimal(request.POST.get("amount", 0))
        except Exception:
            messages.error(request, "Invalid amount entered.")
            return render(request, "member/request_target_withdrawal.html", {
                "member": member,
                "available_balance": available_balance,
            })

        reason = request.POST.get("reason", "").strip()

        if amount <= 0:
            messages.error(request, "Amount must be greater than zero.")
        elif amount > available_balance:
            messages.error(
                request,
                f"Insufficient target savings. Available: ₦{available_balance}"
            )
        else:
            SpecialSavingsWithdrawal.objects.create(
                member=member,
                amount=amount,
                reason=reason,
            )
            messages.success(request, "Withdrawal request submitted successfully.")
            return redirect("my_target_savings_withdrawals")

    return render(request, "member/request_special_withdrawal.html", {
        "member": member,
        "available_balance": available_balance,
    })


@login_required
@group_required(['members','non staff member','admin','loan committee'])
def my_special_savings_withdrawals(request):
    try:
        member = request.user.member
    except Member.DoesNotExist:
        return HttpResponse("Access Denied: You don't have a member profile.")

    withdrawals = SpecialSavingsWithdrawal.objects.filter(
        member=member
    ).order_by("-requested_at")

    return render(request, "member/my_special_withdrawals.html", {
        "withdrawals": withdrawals,"member": member,})
    
 # ======== Target saving =============
    
@login_required
@group_required(['members','non staff member','admin','loan committee'])
def member_target_savings(request):
    try:
        member = request.user.member
    except Member.DoesNotExist:
        return HttpResponse("Access Denied: You don't have a member profile.")

    # Queryset
    target_savings_list = TargetSavings.objects.filter(member=member).order_by('-month')

    # Pagination (10 records per page)
    paginator = Paginator(target_savings_list, 12)
    page_number = request.GET.get('page')
    target_savings = paginator.get_page(page_number)

    # Member balance
    total_target_saving = member.total_target_savings

    context = {
        "member": member,
        "target_savings": target_savings,  # paginated queryset
        "total_target_saving": total_target_saving,
    }

    return render(request, 'member/member_target_savings.html', context)

@login_required
@group_required(['members','non staff member','admin','loan committee'])
def request_target_savings_withdrawal(request):
    try:
        member = request.user.member
    except Member.DoesNotExist:
        return HttpResponse("Access Denied: You don't have a member profile.")

    # Use the member's actual balance field
    available_balance = member.total_target_savings

    if request.method == "POST":
        try:
            amount = Decimal(request.POST.get("amount", 0))
        except Exception:
            messages.error(request, "Invalid amount entered.")
            return render(request, "member/request_target_withdrawal.html", {
                "member": member,
                "available_balance": available_balance,
            })

        reason = request.POST.get("reason", "").strip()

        if amount <= 0:
            messages.error(request, "Amount must be greater than zero.")
        elif amount > available_balance:
            messages.error(
                request,
                f"Insufficient target savings. Available: ₦{available_balance}"
            )
        else:
            TargetSavingsWithdrawal.objects.create(
                member=member,
                amount=amount,
                reason=reason,
            )
            messages.success(request, "Withdrawal request submitted successfully.")
            return redirect("my_target_savings_withdrawals")

    return render(request, "member/request_target_withdrawal.html", {
        "member": member,
        "available_balance": available_balance,
    })


@login_required
@group_required(['members','non staff member','admin','loan committee'])
def my_target_savings_withdrawals(request):
    try:
        member = request.user.member
    except Member.DoesNotExist:
        return HttpResponse("Access Denied: You don't have a member profile.")

    withdrawals = TargetSavingsWithdrawal.objects.filter(
        member=member
    ).order_by("-requested_at")

    return render(request, "member/my_target_withdrawals.html", {
        "withdrawals": withdrawals,
        "member": member,
    })



def ajax_load_bank_code(request):
    bank_id = request.GET.get('bank_id')

    if not bank_id:
        return JsonResponse({'code': '', 'id': ''})

    # ✅ FIX 1: Cache per bank_id — same bank selected repeatedly won't hit DB
    cache_key = f"bank_code_{bank_id}"
    cached = cache.get(cache_key)
    if cached:
        return JsonResponse(cached)

    try:
        # ✅ FIX 2: Use .only() to fetch just the fields you need
        bank_code = BankCode.objects.only("id", "name").filter(bank_name_id=bank_id).first()

        if bank_code:
            response_data = {'code': bank_code.name, 'id': bank_code.id}
        else:
            response_data = {'code': '', 'id': ''}

        # ✅ FIX 3: Cache the result for 10 minutes — bank codes rarely change
        cache.set(cache_key, response_data, timeout=600)

        return JsonResponse(response_data)

    except Exception as e:
        return JsonResponse({'code': '', 'id': '', 'error': str(e)})

@login_required
@group_required(['members','non staff member','admin','loan committee'])
def loan_request_view(request):
    start = time.time()
    # Cache LoanSettings
    settings = cache.get("loan_settings")
    if not settings:
        settings = LoanSettings.objects.first()
        cache.set("loan_settings", settings, timeout=300)
 
    loan_types = LoanType.objects.filter(available=True)
 
    if not settings or not settings.allow_loan_requests:
        return render(request, "member/loan_request.html", {
            "loan_types": loan_types,
            "bank_names": BankName.objects.all(),
        })
 
    bank_names = cache.get("bank_names")
    if not bank_names:
        bank_names = list(BankName.objects.all())
        cache.set("bank_names", bank_names, timeout=600)
 
    member = getattr(request.user, "member", None)
 
    loanable_amount = Decimal("0.00")
    if member:
        cache_key = f"loanable_amount_{member.pk}"
        cached = cache.get(cache_key)
        if cached is not None:
            loanable_amount = cached
        else:
            loanable_amount = (
                Loanable.objects.filter(member=member)
                .aggregate(total=Sum("amount"))["total"]
                or Decimal("0.00")
            )
            cache.set(cache_key, loanable_amount, timeout=120)
 
    loan_types_list = list(loan_types)
 
    eligible_amounts = {}
    for loan_type in loan_types_list:
        name_lower = loan_type.name.lower()
        if member:
            if "short" in name_lower:
                eligible = loanable_amount / 2
            elif "long" in name_lower:
                eligible = loanable_amount * 2
            else:
                eligible = loanable_amount
        else:
            eligible = loan_type.max_amount or Decimal("500000.00")
 
        if loan_type.max_amount and eligible > loan_type.max_amount:
            eligible = loan_type.max_amount
 
        eligible_amounts[loan_type.id] = eligible
 
    if request.method == "POST":
        loan_type_id = request.POST.get("loan_type")
        amount = request.POST.get("amount")
        loan_term_months = request.POST.get("loan_term_months")
        file_one = request.FILES.get("file_one")
        bank_name_id = request.POST.get("bank_name")
        bank_code_id = request.POST.get("bank_code")
        account_number = request.POST.get("account_number")
        account_name = request.POST.get("account_name")
        guarantor_ippis = request.POST.get("guarantor_ippis")
 
        try:
            amount = Decimal(amount)
        except Exception:
            messages.error(request, "Invalid amount entered.")
            return redirect("loan_request")
 
        selected_loan_type = next(
            (lt for lt in loan_types_list if str(lt.id) == str(loan_type_id)), None
        )
        if not selected_loan_type:
            messages.error(request, "Invalid loan type selected.")
            return redirect("loan_request")
 
        selected_type_name = selected_loan_type.name.lower()
 
        if member:
            active_loans = list(
                LoanRequest.objects.filter(
                    member=member, status__in=["pending", "approved"]
                ).select_related("loan_type")
            )
 
            has_active_short = any("short" in l.loan_type.name.lower() for l in active_loans)
            has_active_long = any("long" in l.loan_type.name.lower() for l in active_loans)
 
            if "short" in selected_type_name and (has_active_short or has_active_long):
                messages.error(request, "You cannot request a SHORT TERM loan while you have an active Short or Long Term loan.")
                return redirect("loan_request")
 
            if "long" in selected_type_name and has_active_long:
                messages.error(request, "You cannot request a LONG TERM loan while you have an active Long Term loan.")
                return redirect("loan_request")
 
            try:
                fee = LoanRequestFee.objects.get(
                    member=member,
                    loan_type=selected_loan_type,
                    status="paid",
                )
            except LoanRequestFee.DoesNotExist:
                messages.error(request, f"You must pay the request fee for {selected_loan_type.name} before requesting this loan.")
                return redirect("loan_request")
 
            guarantor_member = None
            if "short" not in selected_type_name:
                try:
                    guarantor_member = Member.objects.only("id", "ippis").get(ippis=guarantor_ippis)
                except Member.DoesNotExist:
                    messages.error(request, "Guarantor IPPIS is not registered.")
                    return redirect("loan_request")
 
                if guarantor_member == member:
                    messages.error(request, "You cannot be your own guarantor.")
                    return redirect("loan_request")
        else:
            fee = None
            guarantor_member = None
 
        eligible_amount = eligible_amounts.get(selected_loan_type.id, loanable_amount)
        if amount > eligible_amount:
            messages.error(request, f"You cannot request more than ₦{eligible_amount:,.2f} for this loan type.")
            return redirect("loan_request")
 
        LoanRequest.objects.create(
            member=member,
            loan_type=selected_loan_type,
            amount=amount,
            loan_term_months=loan_term_months,
            approved_amount=None,
            file_one=file_one,
            bank_name_id=bank_name_id,
            bank_code_id=bank_code_id,
            account_number=account_number,
            account_name=account_name,
            guarantor=guarantor_member,
            created_by=request.user,
        )
 
        if fee:
            fee.status = "used"
            fee.save()
 
        if member:
            cache.delete(f"loanable_amount_{member.pk}")
 
        messages.success(request, "Loan request submitted successfully!")
        return redirect("loan_request")
 
    context = {
            "loan_types": loan_types_list,
            "bank_names": bank_names,
            "settings": settings,
            "loanable": loanable_amount,
            "eligible_amounts": eligible_amounts,
            # ✅ Convert Decimal to float inline — no custom encoder needed
            "eligible_amounts_json": json.dumps({k: float(v) for k, v in eligible_amounts.items()}),
        }
    print(f"loan_request_view took {time.time() - start:.2f} seconds")
    return render(request, "member/loan_request.html", context)
 

@login_required
@group_required(['members','non staff member','admin','loan committee'])
def show_guarantor_approval(request, pk):
    loan = get_object_or_404(LoanRequest, pk=pk)

    # Get the Member object linked to the current user
    member = getattr(request.user, 'member', None)

    if not member:
        messages.error(request, "You must be a registered member to access this.")
        return redirect('member_dashboard')

    if loan.guarantor != member:
        messages.error(request, "You are not authorized to view this loan.")
        return redirect('member_dashboard')

    # Show approval page
    return render(request, 'member/guarantor.html', {'loan': loan})


@login_required
@group_required(['members','non staff member','admin','loan committee'])
def confirm_guarantor_approval(request, pk):
    try:
        loan = get_object_or_404(LoanRequest, pk=pk)
    except LoanRequest.DoesNotExist:
        messages.error(request,'loan do not exist')    

    member = getattr(request.user, 'member', None)
    if not member or loan.guarantor != member:
        messages.error(request, "You are not authorized to approve this loan.")
        return redirect('member_dashboard')

    if loan.guarantor_accepted:
        messages.info(request, "You have already accepted this loan request.")
    else:
        loan.guarantor_accepted = True
        loan.save()
        messages.success(request, "You have successfully accepted the loan guarantee.")

    return redirect('member_dashboard')


@login_required
@group_required(['members','non staff member','admin','loan committee'])
def my_loan_requests(request):
    member = request.user.member  

    loan_requests = (
        LoanRequest.objects
        .filter(member=member).select_related("loan_type").prefetch_related("repaybacks")
        .annotate(
            total_paid=Coalesce(
                Sum("repaybacks__amount_paid"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )
        .order_by("-date_created")
    )

    loan_data = []

    for loan in loan_requests:
        approved_amount = loan.approved_amount or Decimal("0.00")
        total_paid = loan.total_paid
        balance = approved_amount - total_paid
        monthly_payment = loan.monthly_payment or Decimal("0.00")

        loan_data.append({
            'loan': loan,
            'approved_amount': approved_amount,
            'total_paid': total_paid,
            'balance': balance,
            'monthly_payment': monthly_payment,
        })

    return render(request, 'member/my_loan_requests.html', {'loan_data': loan_data})



@login_required
@group_required(['members','non staff member','admin','loan committee'])
def member_loan_request_detail(request, request_id):
    loan_request = get_object_or_404(LoanRequest.objects.prefetch_related('repaybacks'),id=request_id, member=request.user.member)

    total_paid = sum(repay.amount_paid for repay in loan_request.repaybacks.all())
    approved_amount = loan_request.approved_amount or 0
    balance = approved_amount - total_paid
    monthly_payment = loan_request.monthly_payment or 0

    context = {
        'loan_request': loan_request,
        'repaybacks': loan_request.repaybacks.all(),'approved_amount': approved_amount,
        'total_paid': total_paid,'balance': balance,'monthly_payment': monthly_payment,}

    return render(request, 'member/loan_request_detail.html', context)

# ============ consumable =================

@login_required
@group_required(['members','non staff member','admin','loan committee'])
def request_consumable(request):
    now = timezone.now()

    # ✅ Try to detect member profile (optional)
    member = getattr(request.user, "member", None)

    if request.method == "POST":
        consumable_type_id = request.POST.get("consumable_type")
        loan_term_months = request.POST.get("loan_term_months")
        payslip_file = request.FILES.get("file_payslpt")
        passport = request.FILES.get("passport")
        selected_item_ids = request.POST.getlist("selected_items")
        
        
        if ConsumableRequest.objects.filter(user=request.user, status="Pending").exists():
            messages.warning(request, "You already have a pending consumable request.")
            return redirect("my_consumablerequests")

        # ✅ Basic validations
        if not loan_term_months or not loan_term_months.isdigit() or int(loan_term_months) <= 0:
            messages.error(request, "A valid loan term (in months) must be provided.")
            return redirect("request_consumable")

        if not selected_item_ids:
            messages.error(request, "You must select at least one item.")
            return redirect("request_consumable")

        # ✅ Collect item quantities
        item_details = {}
        for item_id in selected_item_ids:
            try:
                quantity = int(request.POST.get(f"quantity_{item_id}", 0))
                if quantity <= 0:
                    raise ValueError("Quantity must be positive.")
                item_details[item_id] = {"quantity": quantity}
            except (ValueError, TypeError):
                messages.error(request, f"Invalid quantity for item ID {item_id}.")
                return redirect("request_consumable")

        with transaction.atomic():
            try:
                # Get consumable type
                consumable_type_obj = get_object_or_404(ConsumableType, id=consumable_type_id)
                loan_term_months = int(loan_term_months)

                # ✅ Create the consumable request object
                consumable_request = ConsumableRequest(
                    consumable_type=consumable_type_obj,
                    file_payslpt=payslip_file,
                    passport=passport,
                    status="Pending",
                )

                # ✅ If the user has a Member profile (member logic)
                if member:
                    # Check if form fee has been paid for this month/type
                    has_paid = ConsumableFormFee.objects.filter(
                        member=member,
                        consumable_type=consumable_type_obj,
                        created_at__year=now.year,
                        created_at__month=now.month,
                        status="paid",
                    ).first()

                    if not has_paid:
                        messages.error(
                            request,
                            f"Please pay the form fee for {consumable_type_obj.name} before applying."
                        )
                        return redirect("member_dashboard")

                    consumable_request.user = request.user
                    consumable_request.member = member

                    # Mark fee as used
                    has_paid.status = "used"
                    has_paid.save()

                else:
                    # ✅ Staff/Admin/Other user (non-member)
                    consumable_request.user = request.user
                    # Optional: auto-approve their requests
                    # consumable_request.status = "Approved"

                consumable_request.save()

                # ✅ Process requested items
                for item_id, details in item_details.items():
                    selling_item = get_object_or_404(
                        SellingPlan.objects.select_related("purchased_item"), id=item_id
                    )
                    quantity = details["quantity"]

                    if quantity > selling_item.quantity:
                        messages.error(
                            request,
                            f"Only {selling_item.quantity} units available for {selling_item.purchased_item.item_name}."
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

                messages.success(request, "Your consumable request has been submitted successfully!")
                return redirect("my_consumablerequests" if member else "request_consumable")

            except Exception as e:
                messages.error(request, f"An unexpected error occurred: {e}")
                return redirect("request_consumable")

    # ✅ GET request
    selling_plans = SellingPlan.objects.filter(quantity__gt=0)
    consumable_types = ConsumableType.objects.filter(available=True)

    context = {
        "consumable_types": consumable_types,
        "selling_plans": selling_plans,
    }
    return render(request, "member/request_consumable.html", context)

@login_required
@group_required(['members','non staff member','admin','loan committee'])
def edit_consumable_request(request, request_id):
    now = timezone.now()
    
    # Get member profile
    member = getattr(request.user, "member", None)
    
    # Get the consumable request
    consumable_request = get_object_or_404(
        ConsumableRequest, 
        id=request_id,
        user=request.user
    )
    
    # Only allow editing if status is Pending or Approved
    if consumable_request.status not in ["Pending", "Approved"]:
        messages.error(request, "You can only edit requests with 'Pending' or 'Approved' status.")
        return redirect("my_consumablerequests")
    
    if request.method == "POST":
        consumable_type_id = request.POST.get("consumable_type")
        loan_term_months = request.POST.get("loan_term_months")
        payslip_file = request.FILES.get("file_payslpt")
        passport = request.FILES.get("passport")
        selected_item_ids = request.POST.getlist("selected_items")
        
        # Basic validations
        if not loan_term_months or not loan_term_months.isdigit() or int(loan_term_months) <= 0:
            messages.error(request, "A valid loan term (in months) must be provided.")
            return redirect("edit_consumable_request", request_id=request_id)
        
        if not selected_item_ids:
            messages.error(request, "You must select at least one item.")
            return redirect("edit_consumable_request", request_id=request_id)
        
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
                return redirect("edit_consumable_request", request_id=request_id)
        
        with transaction.atomic():
            try:
                consumable_type_obj = get_object_or_404(ConsumableType, id=consumable_type_id)
                loan_term_months = int(loan_term_months)
                
                # Restore stock for old items before updating
                old_details = ConsumableRequestDetail.objects.filter(request=consumable_request)
                for old_detail in old_details:
                    selling_item = old_detail.selling_item
                    selling_item.quantity += old_detail.quantity
                    selling_item.save(update_fields=["quantity"])
                
                # Delete old request details
                old_details.delete()
                
                # Update the consumable request
                consumable_request.consumable_type = consumable_type_obj
                
                # Update files only if new ones are provided
                if payslip_file:
                    consumable_request.file_payslpt = payslip_file
                if passport:
                    consumable_request.passport = passport
                
                consumable_request.save()
                
                # Process new requested items
                for item_id, details in item_details.items():
                    selling_item = get_object_or_404(
                        SellingPlan.objects.select_related("purchased_item"), 
                        id=item_id
                    )
                    quantity = details["quantity"]
                    
                    if quantity > selling_item.quantity:
                        messages.error(
                            request,
                            f"Only {selling_item.quantity} units available for {selling_item.purchased_item.item_name}."
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
                
                messages.success(request, "Your consumable request has been updated successfully!")
                return redirect("my_consumablerequests")
                
            except Exception as e:
                messages.error(request, f"An unexpected error occurred: {e}")
                return redirect("edit_consumable_request", request_id=request_id)
    
    # GET request - populate form with existing data
    existing_details = ConsumableRequestDetail.objects.filter(
        request=consumable_request
    ).select_related('selling_item', 'selling_item__purchased_item')
    
    # Get IDs of items already in the request
    selected_item_ids = [detail.selling_item.id for detail in existing_details]
    
    # Get all available selling plans (including those in current request)
    all_selling_plans = SellingPlan.objects.filter(
        quantity__gt=0
    ).select_related('purchased_item')
    
    # Separate selected items and available items
    selected_items = []
    available_items = []
    
    for plan in all_selling_plans:
        # Check if this item is in the current request
        existing_detail = next(
            (detail for detail in existing_details if detail.selling_item.id == plan.id),
            None
        )
        
        if existing_detail:
            # This item was previously selected
            selected_items.append({
                'plan': plan,
                'quantity': existing_detail.quantity,
                'is_selected': True
            })
        else:
            # This item is available to add
            available_items.append({
                'plan': plan,
                'quantity': 1,
                'is_selected': False
            })
    
    consumable_types = ConsumableType.objects.filter(available=True)
    
    context = {
        "consumable_request": consumable_request,
        "consumable_types": consumable_types,
        "selected_items": selected_items,
        "available_items": available_items,
        "existing_details": existing_details,
    }
    return render(request, "member/edit_consumable_request.html", context)


@login_required
@group_required(['members','non staff member','admin','loan committee'])
def my_consumable_requests(request):
    user = request.user

    # Prefetch the updated related field
    requests = ConsumableRequest.objects.filter(user=user
    ).prefetch_related('details__selling_item__purchased_item').order_by('-date_created')

    total_remaining = 0
    consumable_data = []

    for consumable in requests:
        approved_amount = consumable.calculate_total_price()
        total_paid = consumable.total_paid
        balance = approved_amount - total_paid
        total_remaining += balance

        if consumable.details.exists():
            loan_term_months = consumable.details.first().loan_term_months
        else:
            loan_term_months = 1

        monthly_payment = approved_amount / loan_term_months if loan_term_months else approved_amount

        consumable_data.append({
            'consumable': consumable,
            'approved_amount': approved_amount,
            'total_paid': total_paid,
            'balance': balance,
            'monthly_payment': monthly_payment,
        })

    context = {
        'requests': requests,
        'consumable_data': consumable_data,
        'total_remaining': total_remaining,
    }

    return render(request, 'member/my_requests.html', context)


@login_required
@group_required(['members','non staff member','admin','loan committee'])
def request_detail(request, request_id):
    consumable_request = get_object_or_404(
        ConsumableRequest.objects.prefetch_related('details__selling_item__purchased_item', 'repayments'),
        id=request_id,
        user=request.user
    )

    # Get all the individual items requested
    details = consumable_request.details.all()
    repayments = consumable_request.repayments.all()

    # Calculate financial summary
    total_price = consumable_request.calculate_total_price()
    total_paid = consumable_request.total_paid
    balance = consumable_request.balance

    context = {
        'consumable_request': consumable_request,
        'details': details,'repayments': repayments,'total_price': total_price,
        'total_paid': total_paid,'balance': balance,'total_amount': total_price,}

    return render(request, 'member/consumable_request_detail.html', context)


@login_required
@group_required(['members','non staff member','admin','loan committee'])
def cancel_consumable_request(request, id):
    try:
        consumable_request = ConsumableRequest.objects.get(id=id, user=request.user)
        if consumable_request.status != 'Pending':
            messages.error(request, 'Only pending requests can be deleted.')
        else:
            consumable_request.delete()
            messages.success(request, 'Request has been deleted successfully.')
    except ConsumableRequest.DoesNotExist:
        messages.error(request, 'Request not found.')
    except Exception as e:
        messages.error(request, f'An error occurred: {str(e)}')

    return redirect('my_consumablerequests')


@login_required
@group_required(['members','non staff member','admin','loan committee'])
def member_withdrawal_request(request):
    member = get_object_or_404(Member, member=request.user)

    if request.method == 'POST':
        reason = request.POST.get('reason', '')

        # 1. Check pending withdrawal
        if Withdrawal.objects.filter(member=member, status='Pending').exists():
            messages.warning(request, "You already have a pending withdrawal request.")
            return redirect('member_withdrawal_request')

        # 2. Check savings balance
        if member.total_savings is None or member.total_savings <= 0:
            messages.warning(request, "You are not eligible for withdrawal.")
            return redirect('member_withdrawal_request')

        # 3. Block if active loan
        if LoanRequest.objects.filter(member=member, status="Approved").exists():
            messages.warning(request, "You have an approved loan request. Resolve it before withdrawal.")
            return redirect('member_withdrawal_request')

        # 4. Block if active consumable
        if ConsumableRequest.objects.filter(user=request.user, status="Itempicked").exists():
            messages.warning(request, "You have an approved consumable request. Resolve it before withdrawal.")
            return redirect('member_withdrawal_request')

        # 5. Block if active project finance
        if ProjectFinanceRequest.objects.filter(application__member=member, status="Approved").exists():
            messages.warning(request, "You have an approved project finance request. Resolve it before withdrawal.")
            return redirect('member_withdrawal_request')

        # 6. Block if active RAM request
        if RamRequest.objects.filter(member=member, status="Approved").exists():
            messages.warning(request, "You have an approved RAM request. Resolve it before withdrawal.")
            return redirect('member_withdrawal_request')

        # 7. Block if active member request
        if MemberRequest.objects.filter(member=member, status="Approved").exists():
            messages.warning(request, "You have an approved item request. Resolve it before withdrawal.")
            return redirect('member_withdrawal_request')

        # 8. Payment check + create withdrawal atomically
        try:
            with transaction.atomic():
                withdrawal_payment_type = PaymentType.objects.get(title="Withdrawal form")

                payment = RequestFormPayment.objects.filter(
                    member=member,
                    payment_type=withdrawal_payment_type,
                    status="paid"
                ).select_for_update().first()

                if not payment:
                    messages.error(request, "You have not paid the withdrawal form fee.")
                    return redirect('member_withdrawal_request')

                updated = RequestFormPayment.objects.filter(
                    id=payment.id,
                    status="paid"
                ).update(status="used")

                if not updated:
                    messages.error(request, "Payment already used. Please pay again.")
                    return redirect('member_withdrawal_request')

                # All checks passed — create withdrawal
                Withdrawal.objects.create(member=member, reason=reason)
                messages.success(request, "Withdrawal request submitted successfully.")

        except PaymentType.DoesNotExist:
            messages.error(request,  "Withdrawal payment has not been made. Please make the payment before submitting your withdrawal request.")

        except Exception as e:
            messages.error(request, "An error occurred. Please try again.")
        return redirect('member_withdrawal_request')

    return render(request, 'member/withdrawal_request_form.html', {'member': member})

@login_required
@group_required(['members','non staff member','admin','loan committee'])
def create_partial_withdrawal_request(request):
    """Member creates withdrawal request"""
    member = request.user.member

    # Calculate savings once — reused in both GET and POST
    total_savings = Savings.objects.filter(member=member).aggregate(
        total=Sum('month_saving')
    )['total'] or Decimal('0.00')

    max_withdrawal = (total_savings * Decimal('0.50')).quantize(Decimal('0.01'))

    context = {
        'total_savings': total_savings,
        'max_withdrawal': max_withdrawal,
    }

    if request.method == 'POST':
        reason = request.POST.get('reason', '')

        try:
            amount = Decimal(request.POST.get('amount', '0'))
        except Exception:
            messages.error(request, "Invalid amount entered.")
            return render(request, 'member/create_partial_withdrawal_request.html', context)

        # 1. Check amount is positive
        if amount <= 0:
            messages.error(request, "Amount must be greater than zero.")
            return render(request, 'member/create_partial_withdrawal_request.html', context)

        # 2. Check amount does not exceed 50% of savings
        if amount > max_withdrawal:
            messages.error(request, f"You can only withdraw up to 50% of your savings (₦{max_withdrawal:,.2f}).")
            return render(request, 'member/create_partial_withdrawal_request.html', context)

        # 3. Payment check + create atomically
        try:
            with transaction.atomic():
                payment_type = PaymentType.objects.get(title="Partial withdrawal form")

                payment = RequestFormPayment.objects.filter(
                    member=member,
                    payment_type=payment_type,
                    status="paid"
                ).select_for_update().first()

                if not payment:
                    messages.error(request, "You have not paid the partial withdrawal form fee.")
                    return render(request, 'member/create_partial_withdrawal_request.html', context)

                updated = RequestFormPayment.objects.filter(
                    id=payment.id,
                    status="paid"
                ).update(status="used")

                if not updated:
                    messages.error(request, "Payment already used. Please pay again.")
                    return render(request, 'member/create_partial_withdrawal_request.html', context)

                # All checks passed — create withdrawal
                PartialWithdrawal.objects.create(
                    member=member,
                    amount_requested=amount,
                    reason=reason
                )
                messages.success(request, f"Withdrawal request of ₦{amount:,.2f} submitted successfully!")

        except PaymentType.DoesNotExist:
            messages.error(request, "Payment type not configured. Contact admin.")

        except Exception:
            messages.error(request, "An error occurred. Please try again.")

        return redirect('my_partial_withdrawal_requests')

    return render(request, 'member/create_partial_withdrawal_request.html', context)

# def create_partial_withdrawal_request(request):
#     """Member creates withdrawal request"""
#     member = request.user.member
    
#     if request.method == 'POST':
#         amount = Decimal(request.POST.get('amount'))
#         reason = request.POST.get('reason', '')
        
#         # Simple validation
#         total_savings = Savings.objects.filter(member=member).aggregate(
#             total=models.Sum('month_saving')
#         )['total'] or Decimal('0.00')
        
#         if amount > total_savings:
#             messages.error(request, f'Amount exceeds your savings of ₦{total_savings:,.2f}')
#             return redirect('my_partial_withdrawal_requests')
        
#          # ── PAYMENT CHECK ──────────────────────
#         with transaction.atomic():
#             ram_payment_type = PaymentType.objects.get(title="Partial withdrawal form")

#             payment = RequestFormPayment.objects.filter(
#                 member=member,
#                 payment_type=ram_payment_type,
#                 status="paid"
#             ).select_for_update().first()
            

#             if not payment:
#                 messages.error(request, "You have not paid for this request form Fee.")
#                 return render(request, 'member/create_partial_withdrawal_request.html', {'total_savings': total_savings})

#             updated = RequestFormPayment.objects.filter(
#                 id=payment.id,
#                 status="paid"
#             ).update(status="used")

#             if not updated:
#                 messages.error(request, "Payment already used.")
#                 return render(request, 'member/create_partial_withdrawal_request.html', {'total_savings': total_savings})

#         # Create request
#         PartialWithdrawal.objects.create(
#             member=member,
#             amount_requested=amount,
#             reason=reason
#         )
        
#         messages.success(request, f'Withdrawal request of ₦{amount:,.2f} submitted!')
#         return redirect('my_partial_withdrawal_requests')
    
#     # Show form
#     total_savings = Savings.objects.filter(member=member).aggregate(
#         total=models.Sum('month_saving')
#     )['total'] or Decimal('0.00')
    
#     return render(request, 'member/create_partial_withdrawal_request.html', {'total_savings': total_savings})


@login_required
@group_required(['members','non staff member','admin','loan committee'])
def my_partial_withdrawal_requests(request):
    """List member's withdrawal requests"""
    member = request.user.member
    withdrawals = PartialWithdrawal.objects.filter(member=member)
    
    return render(request, 'member/my_partial_withdrawal_requests.html', {'withdrawals': withdrawals})

#==============project_finance_application===================

@login_required
@group_required(['members','non staff member','admin','loan committee'])
def project_finance_application(request):
    if request.method == "POST":
       application_letter = request.POST.get("application_letter")
       if application_letter:
           application = ProjectFinanceApplication(
               member=request.user.member,
               application_letter=application_letter
           )
           application.save()
           messages.success(request, "Application submitted successfully.")
           return redirect("project_finance_application")
       else:
           messages.error(request, "Please provide an application letter.")

  
    return render(request, 'member/project_finance_application_form.html',)

@login_required
@group_required(['members','non staff member','admin','loan committee'])
def project_finance_application_list(request):
    member = request.user.member  
    applications = ProjectFinanceApplication.objects.filter(member=member).prefetch_related('requests').order_by("-created_at")
    requests = ProjectFinanceRequest.objects.filter(application__member=member).select_related('application__member__member')
      # Get member's requests
    member_requests = ProjectFinanceRequest.objects.filter(
            application__member=member,
            status__in=['Reviewed', 'Completed', 'FullyPaid']
        )
        
        # Calculate expenditure for this member
    member_expenditure = member_requests.aggregate(
            total=Sum('requested_amount', default=Decimal('0.00'))
        )['total'] or Decimal('0.00')
    
    markup_expenditure = member_requests.aggregate(
        total_markup=Sum(F('requested_amount') * F('markup_rate') / 100, output_field=DecimalField())
    )['total_markup'] or Decimal('0.00')
    # print("markup_expenditure",markup_expenditure)
    context = {'applications':applications,'requests':requests,'member_expenditure':member_expenditure,'markup_expenditure':markup_expenditure}
    return render(request, 'member/project_finance_application_list.html', context)


@login_required
@group_required(['members','non staff member','admin','loan committee'])
def update_project_finance_application(request,id):
    application = ProjectFinanceApplication.objects.get(id=id, member=request.user.member)
    if request.method == 'POST':
        application_letter = request.POST.get("application_letter")
        if application_letter:
            application.application_letter = application_letter
            application.save()
            messages.success(request, "Application updated successfully.")
            return redirect("project_finance_application_list")
        else:
            messages.error(request, "Please provide an application letter.")

    return render(request, 'member/update_project_finance_application.html', {'application': application})


@login_required
@group_required(['members','non staff member','admin','loan committee'])
def create_project_finance_request(request, id):
    application = get_object_or_404(ProjectFinanceApplication, pk=id, member=request.user.member)

    # Get all requests for this application that are NOT fully paid
    unpaid_requests = ProjectFinanceRequest.objects.filter(application=application).exclude(status='FullyPaid')
    if unpaid_requests.exists():
        messages.warning(request, "You cannot create a new request until your existing one is fully paid.")
        return redirect('project_finance_application_list')

    if request.method == 'POST':
        form = ProjectFinanceRequestForm(request.POST)
        if form.is_valid():
            guarantor_ippis = form.cleaned_data.get('guarantor_ippis')
            try:
                guarantor = Member.objects.get(ippis=guarantor_ippis)
            except Member.DoesNotExist:
                messages.error(request, "The IPPIS number provided does not belong to an existing member.")
                return redirect('create_project_finance_request', id=id)

            # ── PAYMENT CHECK (inside POST + valid form only) ──
            with transaction.atomic():
                ram_payment_type = PaymentType.objects.get(title="Project finance form")
                updated = RequestFormPayment.objects.filter(
                    member=request.user.member, 
                    payment_type=ram_payment_type, 
                    status="paid"
                ).select_for_update().update(status="used")

                if not updated:
                    messages.error(request, "No valid payment found. Please pay the request form fee.")
                    return redirect('create_project_finance_request', id=id)

                project_finance_request = form.save(commit=False)
                project_finance_request.application = application
                project_finance_request.guarantor = guarantor
                project_finance_request.status = 'Pending'
                project_finance_request.guarantor_status = 'Pending'
                project_finance_request.save()

            messages.success(request, "Your project finance request has been submitted successfully.")
            return redirect('project_finance_application_list')
    else:
        # ── Show warning on GET if no payment exists ──
        has_payment = RequestFormPayment.objects.filter(
            member=request.user.member,
            status="paid"
        ).exists()
        if not has_payment:
            messages.error(request, "You have not paid for this request form fee.")
            # return redirect('create_project_finance_request', id=id)

        form = ProjectFinanceRequestForm()

    context = {'form': form, 'application': application}
    return render(request, 'member/create_project_finance_request.html', context)


@login_required
@group_required(['members','non staff member','admin','loan committee'])
def project_finance_request_detail(request, id):

    # Admin / superuser can view everything
    if request.user.is_superuser or (
        hasattr(request.user, "group") and request.user.group and request.user.group.title == "admin"
    ):
        finance_request = get_object_or_404(ProjectFinanceRequest, pk=id)

    else:
        member = getattr(request.user, "member", None)

        if not member:
            return render(request, "member/member_dashboard.html")

        finance_request = get_object_or_404(
            ProjectFinanceRequest,
            pk=id,
            application__member=member
        )

    payments = finance_request.payments.all().order_by('-created_at')

    total_paid = payments.aggregate(total=Sum('amount_paid'))['total'] or 0
    last_payment = payments.first()

    balance_remaining = (
        last_payment.balance_remaining
        if last_payment
        else (finance_request.total_repayment_amount or finance_request.requested_amount)
    )
    context = {
        "finance_request": finance_request,
        "payments": payments,
        "total_paid": total_paid,
        "balance_remaining": balance_remaining,
    }
    return render(request, "member/project_finance_request_detail.html",context )

@login_required
@group_required(['members','non staff member'])
def approve_guarantor_request(request, id):
    if request.method == 'POST':
        project_request = get_object_or_404( ProjectFinanceRequest,  pk=id, guarantor=request.user.member,guarantor_status='Pending')
        project_request.guarantor_status = 'Approved'
        project_request.save()
        messages.success(request, f"You have successfully approved the request for {project_request.application.member.member.first_name}.")
    return redirect('member_dashboard')


@login_required
@group_required(['members','non staff member'])
def member_items_request(request):
    try:
        member = Member.objects.get(member=request.user)
    except Member.DoesNotExist:
        return redirect('member_dashboard')

    item_requests = MemberRequest.objects.filter(member=member) \
        .prefetch_related('details__item__received_item') \
        .order_by('-date_created')[:5]

    approved_item_requests = MemberRequest.objects.filter(
        member=member, #status='pending'
    ).prefetch_related(
        'details__item__received_item',
        'repayments'
    ).order_by('-date_created')

    item_data = []
    item_total_remaining = Decimal('0.00')

    for item in approved_item_requests:
        approved_amount = item.calculate_total_price()
        total_paid = item.total_paid
        balance = approved_amount - total_paid
        item_total_remaining += balance

        details = list(item.details.all())

        monthly_payment = sum(
            d.total_price / d.duration_months
            for d in details
            if d.duration_months
        ) if details else Decimal('0.00')

        paid_count = item.repayments.count()
        total_months = sum(d.duration_months for d in details if d.duration_months)
        remaining_count = max(total_months - paid_count, 0)

        detail_breakdown = [
            {
                'brand': d.item.received_item.brand,
                'model': d.item.received_item.model_name,
                'quantity': d.quantity,
                'original_price': d.item.selling_price_per_unit,
                'item_price': d.item_price,
                'markup_rate': d.markup_rate,
                'duration_months': d.duration_months,
                'total_price': d.total_price,
            }
            for d in details
        ]

        item_data.append({
            'item': item,
            'approved_amount': approved_amount,
            'total_paid': total_paid,
            'balance': balance,
            'monthly_payment': monthly_payment,
            'detail_breakdown': detail_breakdown,
            'has_markup': any(d['markup_rate'] for d in detail_breakdown),
            'paid_count': paid_count,
            'remaining_count': remaining_count,
            'total_months': total_months,
        })

    context = {
        'member': member,
        'item_requests': item_requests,
        'approved_item_requests': approved_item_requests,
        'item_data': item_data,
        'item_total_remaining': item_total_remaining,
        'total_items_value': sum(e['approved_amount'] for e in item_data),
        'total_paid_all': sum(e['total_paid'] for e in item_data),
        'total_paid_count': sum(e['paid_count'] for e in item_data),
        'total_remaining_count': sum(e['remaining_count'] for e in item_data),
    }

    return render(request, 'member/member_items_request.html', context)


def my_ram_request(request):
    try:
        member = Member.objects.get(member=request.user)
    except Member.DoesNotExist:
        return redirect('member_dashboard')
    ram_requests = (
    RamRequest.objects.filter(member=member).select_related('budget').prefetch_related('items', 'payments').order_by('-date_requested'))
   
    total_billed = sum(r.total_selling_price for r in ram_requests) 
    total_paid =  sum(r.total_paid for r in ram_requests)
    total_balance = total_billed - total_paid
    print(ram_requests)
    context = {'member':member, 'ram_requests': ram_requests,
               'total_billed': total_billed,
               "total_paid": total_paid,
               "total_balance": total_balance,
               }
    return render(request,'member/my_ram_request.html',context)

