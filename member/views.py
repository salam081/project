
from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from dateutil.relativedelta import relativedelta  
from datetime import date
# from accounts.decorator import group_required
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.db import transaction
from decimal import Decimal
from django.urls import reverse 
from django.contrib import messages
from django.db.models import Prefetch
from django.utils import timezone
import datetime
from django.http import JsonResponse
from datetime import date
from datetime import datetime
from main.models import *
from loan.models import *
from accounts.models import *
from consumable.models import *
from consumable.models import *
from .models import *


@login_required
def member_dashboard(request):
    try:
        member = Member.objects.get(member=request.user)
    except Member.DoesNotExist:
        return redirect('login')
    
    pending_guarantor_loans = LoanRequest.objects.filter(
        guarantor=member,
        guarantor_accepted=False,
        status="pending"
    )
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
        print(monthly_payment,monthly_payment)
    loan_types = LoanType.objects.all()
    consumable_requests = ConsumableRequest.objects.filter(user=request.user) \
        .prefetch_related('details__item') \
        .order_by('-date_created')[:5]

    approved_consumable = ConsumableRequest.objects.filter(user=request.user, status='Approved') \
        .order_by('-date_created')

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
            'consumable': consumable,
            'approved_amount': approved_amount,
            'total_paid': total_paid,
            'balance': balance,
            'monthly_payment': monthly_payment,
        })

    context = {
        'member': member,
        'total_savings': member.total_savings or 0,
        'monthly_saving': monthly_saving.month_saving if monthly_saving else 0,
        'previous_monthly_saving': previous_monthly_saving.month_saving if previous_monthly_saving else 0,
        'loan': active_loan,
        'loan_paid': loan_paid,
        'loan_balance': loan_balance,
        'monthly_payment': monthly_payment,
        'loan_types': loan_types,
        'consumable_requests': consumable_requests,
        'approved_consumable': consumable_data,
        'loanable_total': loanable_total,
        'investment_total': investment_total,
        'approved_consumable': consumable_data,
        'total_remaining': total_remaining,
        "pending_guarantor_loans": pending_guarantor_loans
    }

    return render(request, 'member/member_dashboard.html', context)

def member_savings(request):
    try:
        member = Member.objects.get(member=request.user)
    except Member.DoesNotExist:
        return redirect('login')
    savings = Savings.objects.filter(member=member)
    total_savings = Savings.objects.filter(member=member).aggregate(
        total=Sum('month_saving')
    )['total'] or 0

    investmentsavings = Investment.objects.filter(member=member)
    total_investment = Investment.objects.filter(member=member).aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    loanable = Loanable.objects.filter(member=member)
    total_loanable = Loanable.objects.filter(member=member).aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    g_total = total_investment + total_loanable 
    print(g_total)
    total = g_total /4
    print(total)
    context = {'savings': savings,'total_savings':total_savings,
               'investmentsavings':investmentsavings,'total_investment':total_investment,
               'loanable':loanable,'total_loanable':total_loanable,'total':total,}
    return render(request, 'member/member_savings.html', context)

def ajax_load_bank_code(request):
    bank_id = request.GET.get('bank_id')
    try:
        bank_code = BankCode.objects.filter(bank_name_id=bank_id).first()
        return JsonResponse({'code': bank_code.name if bank_code else ''})
    except:
        return JsonResponse({'code': ''})


@login_required
def loan_request_view(request):
    settings = LoanSettings.objects.first()
    if not settings or not settings.allow_loan_requests:
        return render(request, "member/loan_request.html", {
            "loan_types": LoanType.objects.all(),
            "bank_names": BankName.objects.all(),
        })
    current_month = datetime.now().strftime('%b')
    member = getattr(request.user, 'member', None)
    if not member:
        messages.error(request, "You must be a registered member to request a loan.")
        return redirect("dashboard")

    loan_types = LoanType.objects.filter(available=True)
    # loan_types = LoanType.objects.filter(name__icontains=current_month)
    # loan_types = LoanType.objects.filter(name__icontains=current_month, available=True)

    bank_names = BankName.objects.all()

    if request.method == "POST":
        loan_type_id = request.POST.get('loan_type')
        amount = request.POST.get('amount')
        loan_term_months = request.POST.get('loan_term_months')
        file_one = request.FILES.get('file_one')
        bank_name_id = request.POST.get('bank_name')
        bank_code_id = request.POST.get('bank_code')
        account_number = request.POST.get('account_number')
        guarantor_ippis = request.POST.get('guarantor_ippis')
        # form_fee = request.POST.get('form_fee')

        # Validate loan type
        try:
            selected_loan_type = LoanType.objects.get(id=loan_type_id)
        except LoanType.DoesNotExist:
            messages.error(request, "Invalid loan type selected.")
            return redirect('loan_request')

        selected_type_name = selected_loan_type.name.lower()

        # Check active loans
        active_loans = LoanRequest.objects.filter(
            member=member,
            status__in=['pending', 'approved']
        ).select_related('loan_type')

        has_active_short = any('short term' in loan.loan_type.name.lower() for loan in active_loans)
        has_active_long = any('long term' in loan.loan_type.name.lower() for loan in active_loans)

        # Validation rules
        if 'short term' in selected_type_name and (has_active_short or has_active_long):
            messages.error(request, "You cannot request a SHORT TERM loan while you have an active Short or Long Term loan.")
            return redirect('loan_request')

        if 'long term' in selected_type_name and has_active_long:
            messages.error(request, "You cannot request a LONG TERM loan while you have an active Long Term loan.")
            return redirect('loan_request')
        
        now = timezone.now()
        paid = LoanRequestFee.objects.filter(
            member=request.user.member,  # or however you access the member
            created_at__year=now.year,
            created_at__month=now.month
        ).exists()

        if not paid:
            messages.error(request, "You must pay the loan request form fee  before requesting a loan.")
            return redirect('loan_request')
            
        # Guarantor validation
        try:
            guarantor_member = Member.objects.get(ippis=guarantor_ippis)
        except Member.DoesNotExist:
            messages.error(request, "Guarantor IPPIS is not registered.")
            return redirect('loan_request')

        if guarantor_member == member:
            messages.error(request, "You cannot be your own guarantor.")
            return redirect('loan_request')


        # Create the loan request
        LoanRequest.objects.create(
            member=member,loan_type=selected_loan_type,
            amount=amount,loan_term_months=loan_term_months,
            approved_amount=None,file_one=file_one,
            bank_name_id=bank_name_id, bank_code_id=bank_code_id,
            account_number=account_number, guarantor=guarantor_member,
            created_by=request.user,
        )
        # LoanFormFee.objects.create(form_fee = '500',paid_by=request.user,)
        
        messages.success(request, "Loan request submitted successfully!")
        return redirect('loan_request')

    context = {
        "loan_types": loan_types,
        "bank_names": bank_names,
        "settings": settings,
    }
    return render(request, "member/loan_request.html", context)

@login_required
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
def confirm_guarantor_approval(request, pk):
    loan = get_object_or_404(LoanRequest, pk=pk)

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


def my_loan_requests(request):
    member = request.user.member  
    loan_requests = LoanRequest.objects.filter(member=member).exclude(status='Rejected').order_by('-date_created')

    loan_data = []
    for loan in loan_requests:
        approved_amount = loan.approved_amount or 0
        total_paid = sum(repay.amount_paid for repay in loan.repaybacks.all())
        balance = approved_amount - total_paid
        monthly_payment = loan.monthly_payment or 0

        loan_data.append({
            'loan': loan,'approved_amount': approved_amount,'total_paid': total_paid,
            'balance': balance,'monthly_payment': monthly_payment,})

    return render(request, 'member/my_loan_requests.html', {'loan_data': loan_data})


@login_required
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
def request_consumable(request):
    now = timezone.now()
    has_paid = ConsumableFormFee.objects.filter( member=request.user.member, created_at__year=now.year, created_at__month=now.month, ).exists()
    
    if not has_paid:
        messages.error(request, " pay your consumables request form fee and  apply for consumables.")
        return redirect('member_dashboard')
    
    if request.method == 'POST':
        consumable_type_id = request.POST.get('consumable_type')
        loan_term_months = request.POST.get('loan_term_months')
        payslip_file = request.FILES.get('file_payslpt')
        
        selected_item_ids = request.POST.getlist('selected_items')
        
        # Basic validation
        if not consumable_type_id:
            messages.error(request, "You must select a consumable type.")
            return redirect('member_dashboard')
            
        if not loan_term_months or not loan_term_months.isdigit() or int(loan_term_months) <= 0:
            messages.error(request, "A valid loan term (in months) must be provided.")
            return redirect('request_consumable')

        if not selected_item_ids:
            messages.error(request, "You must select at least one item to request.")
            return redirect('member_dashboard')
        
        # Get quantities for the selected items
        item_details = {}
        for item_id in selected_item_ids:
            try:
                quantity = int(request.POST.get(f'quantity_{item_id}', 0))
                if quantity <= 0:
                    raise ValueError("Quantity must be a positive number.")
                item_details[item_id] = {'quantity': quantity}
            except (ValueError, TypeError):
                messages.error(request, f"Invalid quantity for item ID {item_id}.")
                return redirect('request_consumable')

        with transaction.atomic():
            try:
                # Get the selected consumable type object 
                try:
                    consumable_type_obj = ConsumableType.objects.get(id=consumable_type_id)
                except ConsumableType.DoesNotExist:
                    messages.error(request, "The selected consumable type does not exist.")
                    return redirect('request_consumable')

                loan_term_months = int(loan_term_months)
                    
                # Create the main ConsumableRequest object
                consumable_request = ConsumableRequest.objects.create(
                    user=request.user,
                    consumable_type=consumable_type_obj,
                    file_payslpt=payslip_file,
                    status='Pending'
                )

                # Process each selected item
                for item_id, details in item_details.items():
                    try:
                        item_obj = Item.objects.get(id=item_id, available=True)
                        quantity = details['quantity']

                        # Create the ConsumableRequestDetail object
                        ConsumableRequestDetail.objects.create(
                            request=consumable_request,
                            item=item_obj,
                            quantity=quantity,
                            item_price=item_obj.price, # Use the price from the Item model
                            loan_term_months=loan_term_months
                        )
                    except Item.DoesNotExist:
                        messages.error(request, f"Item with ID {item_id} is not available.")
                        raise
                
                messages.success(request, 'Your consumable request has been submitted successfully!')
                return redirect('my_consumablerequests')
            
            except Exception as e:
                messages.error(request, f'An unexpected error occurred: {e}')
                return redirect('request_consumable')
    
    # GET request: Render the page with all consumable types and available items
    consumable_types = ConsumableType.objects.filter(available=True)
    items = Item.objects.filter(available=True)
    context = {
        'consumable_types': consumable_types,
        'items': items,
    }
    return render(request, 'member/request_consumable.html', context)


@login_required
def my_consumable_requests(request):
    user = request.user
    requests = ConsumableRequest.objects.filter(
        user=user
    ).prefetch_related('details__item').order_by('-date_created')

    total_remaining = 0
    consumable_data = []

    for consumable in requests:
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
            'consumable': consumable,'approved_amount': approved_amount,
            'total_paid': total_paid,'balance': balance,
            'monthly_payment': monthly_payment,
        })
    context = {'requests': requests,'consumable_data': consumable_data,'total_remaining': total_remaining,}

    return render(request, 'member/my_requests.html', context)


@login_required
def request_detail(request, request_id):
    consumable_request = get_object_or_404(ConsumableRequest, id=request_id, user=request.user)

    # Get all the individual items requested
    details = consumable_request.details.all()
    repayments = consumable_request.repayments.all() 
    
    # Calculate financial summary for display
    total_price = consumable_request.calculate_total_price()
    total_paid = consumable_request.total_paid()
    balance = consumable_request.balance()
    
    context = {
        'consumable_request': consumable_request,'details': details,
        'repayments': repayments, 'total_price': total_price,
        'total_paid': total_paid,'balance': balance,
        'total_amount': consumable_request.calculate_total_price(),
    }
    return render(request, 'member/consumable_request_detail.html', context)


@login_required
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
def member_withdrawal_request(request):
    member = get_object_or_404(Member, member=request.user)
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        if Withdrawal.objects.filter(member=member, status='Pending').exists():
            messages.warning(request, "You already have a pending request.")
        elif member.total_savings <= 0:
            messages.warning(request, "You are not eligible for withdrawal.")
        else:
            Withdrawal.objects.create(member=member, reason=reason)
            messages.success(request, "Withdrawal request submitted successfully.")
        return redirect('member_withdrawal_request')

    return render(request, 'member/withdrawal_request_form.html', {'member': member,})

