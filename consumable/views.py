from multiprocessing.sharedctypes import Value
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator,PageNotAnInteger,EmptyPage
from django.forms import DecimalField
from django.http import JsonResponse, HttpResponse
from django.db.models import F, Q, Sum, DecimalField, Value
from django.db.models.functions import Coalesce
from collections import defaultdict
import pandas as pd
from datetime import datetime
from django.contrib import messages
from django.db import transaction
from decimal import Decimal
from django.db.models import Count
from collections import defaultdict
from django.utils import timezone
import requests
from loan.models import *
from .models import *
from .forms import *
from accounts.models import *
from accounts.models import *
from accounts.models import *
from main.models import *




@login_required  
def consumable_dashboard(request):
    # Get basic statistics
    total_requests = ConsumableRequest.objects.count()
    pending_count = ConsumableRequest.objects.filter(status='Pending').count()
    approved_count = ConsumableRequest.objects.filter(status='Approved').count()
    completed_count = ConsumableRequest.objects.filter(status='FullyPaid').count()
    
    # Recent requests
    recent_requests = ConsumableRequest.objects.select_related(
        'user', 'consumable_type'
    ).order_by('-date_created')[:10]
    
    # Pending approvals
    pending_approvals = ConsumableRequest.objects.filter(
        status='Pending'
    ).select_related('user', 'consumable_type')[:5]
    
    context = {
        'total_requests': total_requests, 'pending_approvals': pending_approvals,
        'pending_count': pending_count,'approved_count': approved_count,
        'completed_count': completed_count, 'recent_requests': recent_requests,}
    
    return render(request, 'consumable/consumable_dashboard.html', context)


def process_item_pickup(request_id):
    try:
        request = ConsumableRequest.objects.get(id=request_id)
        if request.status == 'Itempicked':
            # Check if this deduction has already been made
            # You might need a flag to prevent multiple deductions for the same request

            details = ConsumableRequestDetail.objects.filter(request=request)
            for detail in details:
                item = detail.item
                requested_quantity = detail.quantity

                if item.quantity_in_stock >= requested_quantity:
                    item.quantity_in_stock -= requested_quantity  # Deduct stock
                    item.save()
                    print(f"Deducted {requested_quantity} of {item.title} from stock.")
                else:
                    print(f"Not enough stock for {item.title}. Available: {item.quantity_in_stock}")
                    # Handle this error (e.g., prevent the status change)
    except ConsumableRequest.DoesNotExist:
        print("Request not found.")

@login_required
# @group_required(['admin'])
def consumable_fee(request):
    if request.method == 'POST':
        member_ippis = request.POST.get('member_ippis')
        form_fee = request.POST.get('form_fee')
        
        # Get Member instance using IPPIS number
        member = get_object_or_404(Member, ippis=member_ippis)
        ConsumableFormFee.objects.create( member=member, form_fee=form_fee,created_by=request.user)
        messages.success(request, 'Payment recorded successfully')
        return redirect('consumable_fee')

    fee = ConsumableFormFee.objects.aggregate(total=Sum('form_fee'))['total'] or 0
    consumable_req_form = ConsumableFormFee.objects.count()
    members = ConsumableFormFee.objects.select_related('member')

    page_number = request.GET.get('page')
    paginator = Paginator(members, 1)  

    try:
       
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {"fee": fee,"consumable_req_form": consumable_req_form,'members':members, 'page_obj': page_obj}
    return render(request, "consumable/consumable_fee.html", context)

@login_required
def add_consumable_type(request):
    consumable_types = ConsumableType.objects.all()
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        max_amount = request.POST.get('max_amount') or None
        max_loan_term_months = request.POST.get('max_loan_term_months') or None
        consumable_type_id = request.POST.get('consumable_type_id')
        action = request.POST.get('action')  

        if consumable_type_id:
            consumable_type = get_object_or_404(ConsumableType, id=consumable_type_id)

            if action == 'toggle':
                consumable_type.available = not consumable_type.available
                consumable_type.save()
                messages.success(request, 'Consumable type availability updated successfully.')
                return redirect('consumable_type')

            elif action == 'edit':
                consumable_type.name = name
                consumable_type.description = description
                consumable_type.max_amount = max_amount
                consumable_type.max_loan_term_months = max_loan_term_months
                consumable_type.save()
                messages.success(request, 'Consumable type updated successfully.')
                return redirect('consumable_type')

        else:
            ConsumableType.objects.create(name=name,description=description, max_amount=max_amount,
                max_loan_term_months=max_loan_term_months,available=True,created_by=request.user)
            messages.success(request, 'Consumable type created successfully.')
            return redirect('consumable_type')

    context = {'consumable_types': consumable_types}
    return render(request, 'consumables/add_consumable_type.html', context)

@login_required
def consumable_items(request):
    consumables = Item.objects.all()
    
    if request.method == 'POST':
        title = request.POST.get('title')
        price = request.POST.get('price')
        description = request.POST.get('description')
        item_id = request.POST.get('item_id')
        action = request.POST.get('action')  # either 'toggle' or 'edit'
        
        if item_id:
            item = get_object_or_404(Item, id=item_id)

            if action == 'toggle':
                item.available = not item.available
                item.save()
                messages.success(request, 'Consumable item availability updated successfully')
                return redirect('consumable_items')

            elif action == 'edit':
                item.title = title
                item.price = price
                item.description=description,
                item.save()
                messages.success(request, 'Consumable item updated successfully')
                return redirect('consumable_items')
            
            
        else:
            item = Item.objects.create(title=title,price=price,description=description,available=True)
            item.save()
            messages.success(request, 'Consumable item Created successfully')
            return redirect('consumable_items')
           
    context = {'consumables': consumables}
    return render(request, "consumable/consumable_items.html", context)

@login_required
def delete_item(request,id):
    itemObj = get_object_or_404(Item, id=id)
    itemObj.delete()
    messages.success(request, 'Consumable item Deleted successfully')
    return redirect('consumable_items')

@login_required
def admin_consumables_list(request):
    consumables_list = ConsumableRequest.objects.select_related('user', 'consumable_type').order_by('-date_created')

    # Apply filters based on GET parameters
    status_filter = request.GET.get('status')
    user_filter = request.GET.get('user')
    consumable_type_filter = request.GET.get('consumable_type')

    if status_filter and status_filter != 'all':
        consumables_list = consumables_list.filter(status=status_filter)
    
    # Corrected filter for the 'user' input field using Q objects
    if user_filter:
        consumables_list = consumables_list.filter(
            Q(user__username__icontains=user_filter) |
            Q(user__first_name__icontains=user_filter) |
            Q(user__last_name__icontains=user_filter)
        )

    if consumable_type_filter and consumable_type_filter != 'all':
        try:
            consumable_type_filter_id = int(consumable_type_filter)
            consumables_list = consumables_list.filter(consumable_type_id=consumable_type_filter_id)
        except ValueError:
            pass

    all_consumable_types = ConsumableType.objects.filter(available=True).order_by('name')
    
    context = {
        'consumables_list': consumables_list,
        'all_consumable_types': all_consumable_types,
        'status_choices': ConsumableRequest.STATUS_CHOICES,
        'selected_status': status_filter, 'selected_user': user_filter,
        'selected_consumable_type': consumable_type_filter,}
    return render(request, 'consumable/consumables_list.html', context)

@login_required
def admin_consumable_detail(request, request_id):
    consumable_request = get_object_or_404( ConsumableRequest.objects.select_related('user', 'consumable_type')
                                 .prefetch_related('details__item'),id=request_id )
    total_paid = consumable_request.total_paid()
    balance = consumable_request.balance()

    context = {'request': consumable_request,'total_paid':total_paid,'balance':balance}
    return render(request, 'consumable/consumables_detail.html', context)


@require_POST
def admin_request_approve(request, request_id):
    consumable_request = get_object_or_404(ConsumableRequest, id=request_id)
    if consumable_request.status == 'Pending':
        consumable_request.status = 'Approved'
        consumable_request.approved_by = request.user
        consumable_request.save()
        messages.success(request, f"Request #{request_id} has been approved.")
    return redirect('admin_consumable_detail', request_id=request_id)


@require_POST
def admin_request_reject(request, request_id):
    consumable_request = get_object_or_404(ConsumableRequest, id=request_id)
    if consumable_request.status == 'Pending':
        consumable_request.status = 'Declined'
        consumable_request.approved_by = request.user
        consumable_request.save()
        messages.error(request, f"Request #{request_id} has been declined.")
    return redirect('admin_consumable_detail', request_id=request_id)

# 🆕 This view is updated to handle stock deduction and date stamping.
@login_required
def admin_request_taking(request, request_id):
    consumable_request = get_object_or_404(ConsumableRequest, id=request_id)

    with transaction.atomic():
        if consumable_request.status == 'Approved':
            # Get all the details for the request
            request_details = ConsumableRequestDetail.objects.filter(request=consumable_request)

            for detail in request_details:
                item = detail.item
                requested_quantity = detail.quantity

                # Check if enough stock is available before deducting
                if item.quantity_in_stock < requested_quantity:
                    messages.error(request, f"Insufficient stock for {item.title}. Cannot process request.")
                    # Rollback the transaction by raising an exception
                    raise Exception("Insufficient stock")

                item.quantity_in_stock -= requested_quantity
                item.save()

                detail.approval_date = timezone.now().date()
                detail.save()

            # Update the main request status only after all details have been processed
            consumable_request.status = 'Itempicked'
            consumable_request.approved_by = request.user
            consumable_request.save()

            messages.success(request, f"Request #{request_id} has been marked as 'Itempicked' and stock has been reduced.")
        
        elif consumable_request.status == 'Itempicked':
            messages.info(request, f"Request #{request_id} has already been marked as 'Itempicked'.")
        else:
            messages.error(request, f"Cannot mark request #{request_id} as 'Itempicked' because its status is '{consumable_request.status}'.")

    return redirect('admin_consumable_detail', request_id=request_id)


# @require_POST
# def admin_request_approve(request, request_id):
#     consumable_request = get_object_or_404(ConsumableRequest, id=request_id)
#     if consumable_request.status == 'Pending':
#         consumable_request.status = 'Approved'
#         consumable_request.approved_by = request.user
#         consumable_request.date_created = timezone.now()
#         consumable_request.save()
#         messages.success(request, f"Request #{request_id} has been approved.")
#     return redirect('admin_consumable_detail', request_id=request_id)

# @require_POST
# def admin_request_reject(request, request_id):
#     consumable_request = get_object_or_404(ConsumableRequest, id=request_id)
#     if consumable_request.status == 'Pending':
#         consumable_request.status = 'Declined'
#         consumable_request.approved_by = request.user
#         consumable_request.date_created = timezone.now()
#         consumable_request.save()
#         messages.error(request, f"Request #{request_id} has been declined.")
#     return redirect('admin_consumable_detail', request_id=request_id)

# @login_required
# def admin_request_taking(request, request_id):
#     consumable_request = get_object_or_404(ConsumableRequest, id=request_id)
#     if consumable_request.status == 'Approved':
#         consumable_request.status = 'Itempicked'
#         consumable_request.approved_by = request.user
#         consumable_request.date_created = timezone.now()
#         consumable_request.save()
#         messages.success(request, f"Request #{request_id} has been marked as Itempicked.")
#     return redirect('admin_consumable_detail', request_id=request_id)

@login_required
def consumable_types_with_requests(request):
    # grouped by status.
    requested_types = ConsumableType.objects.filter( consumables_type__isnull=False
    ).annotate(
        pending_count=Count('consumables_type', filter=models.Q(consumables_type__status='Pending')),
        approved_count=Count('consumables_type', filter=models.Q(consumables_type__status='Approved')),
        itempicked_count=Count('consumables_type', filter=models.Q(consumables_type__status='Itempicked')),
        fully_paid_count=Count('consumables_type', filter=models.Q(consumables_type__status='FullyPaid')),
        declined_count=Count('consumables_type', filter=models.Q(consumables_type__status='Declined')),
        # Add other statuses as needed
    ).distinct()

    context = {'requested_types': requested_types}
    return render(request, 'consumable/requested_types_list.html', context)



@login_required
def members_by_consumable_type(request, id):
    consumable_type = get_object_or_404(ConsumableType, id=id)
    requests = ConsumableRequest.objects.filter( consumable_type=consumable_type
    ).select_related('user').prefetch_related('details', 'repayments').order_by('-date_created')

    requests_with_amounts = requests.annotate(
        total_price=Sum(F('details__item_price') * F('details__quantity'))
    )

    paginator = Paginator(requests_with_amounts, 10)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.get_page(1)
    except EmptyPage:
        page_obj = paginator.get_page(paginator.num_pages)

    # Calculate the total of all requested amounts from the annotated queryset.
    total_requests_amount = requests_with_amounts.aggregate( total_requested=Sum('total_price')
    )['total_requested'] or Decimal('0.00')

    # Calculate total paid using a single aggregation query.
    total_paid = requests.aggregate(total_paid=Sum('repayments__amount_paid')
    )['total_paid'] or Decimal('0.00')
    
    total_remaining_balance = total_requests_amount - total_paid

    # Use a string formatting method to control the number of decimal places.
    # We use '{:.2f}'.format() to force two decimal places.
    formatted_total_requests_amount = '{:.2f}'.format(total_requests_amount)
    formatted_total_paid = '{:.2f}'.format(total_paid)
    formatted_total_remaining_balance = '{:.2f}'.format(total_remaining_balance)

    # Get a set of unique members from the original queryset.
    members = {req.user for req in requests}

    context = {
        'consumable_type': consumable_type,'page_obj': page_obj, 'requests': requests_with_amounts, 'members': members,
        'total_requests_amount': formatted_total_requests_amount,'total_remaining_balance': formatted_total_remaining_balance,'total_paid': formatted_total_paid,}
    return render(request, 'consumable/members_by_type.html', context)

@login_required
def add_payment(request, request_id):
    consumable_request = get_object_or_404(ConsumableRequest, id=request_id)
    if request.method == 'POST':
        amount_paid = request.POST.get('amount_paid')
        repayment_date = request.POST.get('repayment_date')
        
        # Validate inputs
        try:
            amount_paid = float(amount_paid)
            if amount_paid <= 0:
                raise ValueError("Amount must be positive")
        except (ValueError, TypeError):
            messages.error(request, 'Invalid amount provided')
            return redirect('admin_consumable_detail', request_id=request_id)
        
        try:
            repayment_date = datetime.strptime(repayment_date, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.error(request, 'Invalid date provided')
            return redirect('admin_consumable_detail', request_id=request_id)
        
        # Check if payment doesn't exceed balance
        current_balance = consumable_request.balance()
        if amount_paid > current_balance:
            messages.error(request, f'Payment amount (₦{amount_paid:,.2f}) exceeds remaining balance (₦{current_balance:,.2f})')
            return redirect('admin_consumable_detail', request_id=request_id)
        
        # Create payment record
        payment = PaybackConsumable.objects.create(
            consumable_request=consumable_request,
            amount_paid=amount_paid,
            repayment_date=repayment_date,
            created_by=request.user
        )
        
        messages.success(request, f'Payment of ₦{amount_paid:,.2f} added successfully')
        
        # Update request status if fully paid
        if consumable_request.balance() <= 0:
            consumable_request.status = 'FullyPaid'
            consumable_request.save()
            messages.info(request, 'Request marked as Fully Paid')
    
    return redirect('admin_consumable_detail', request_id=request_id)

@login_required
def admin_edit_consumable_request(request, request_id):
    consumable_request = get_object_or_404(ConsumableRequest, id=request_id)
    details = consumable_request.details.all()

    if request.method == 'POST':
        detail_id = request.POST.get('detail_id')
        if not detail_id:
            messages.error(request, "Detail ID is missing.")
            return redirect('admin_edit_consumable_request')

        detail_to_update = get_object_or_404(ConsumableRequestDetail, id=detail_id, request=consumable_request)
        form = AdminUpdateConsumableRequestForm(request.POST)

        if form.is_valid():
            loan_term_months = form.cleaned_data['loan_term_months']
            quantity = form.cleaned_data.get('quantity', detail_to_update.quantity)
            item_price = form.cleaned_data.get('item_price', detail_to_update.item_price)

            try:
                with transaction.atomic():
                    detail_to_update.loan_term_months = loan_term_months
                    detail_to_update.quantity = quantity
                    detail_to_update.item_price = item_price
                    detail_to_update.save()

                messages.success(request, "Consumable request updated successfully.")
                return redirect('admin_edit_consumable_request')

            except Exception as e:
                messages.error(request, f"An error occurred: {e}")
                
        else:
            messages.error(request, "Please provide a valid loan term.")
            
    # GET request or form is invalid
    context = {'request_obj': consumable_request,'details': details, 'form': AdminUpdateConsumableRequestForm()}
    return render(request, 'consumable/admin_edit_request.html', context)

@login_required
def add_single_consumable_payment(request):
   
    requests = []
    selected_user = None
    
    # Get IPPIS from either GET or POST data
    ippis = request.GET.get("ippis") or request.POST.get("ippis")
    if ippis:
        try:
            # Find the member by IPPIS
            member = Member.objects.filter(ippis=int(ippis)).first()
            if member and member.member:
                selected_user = member.member
                # Filter for unpaid or partially paid requests for the member
                requests = ConsumableRequest.objects.filter(
                    user=selected_user
                ).exclude(status__in=['FullyPaid', 'Declined'])
        except Exception as e:
            messages.error(request, f"Error fetching member: {e}")

    if request.method == "POST":
        amount_paid = request.POST.get("amount_paid")
        month = request.POST.get("month")
        request_id = request.POST.get("consumable_request")

        # Validate that all required fields are present
        if not ippis or not amount_paid or not month or not request_id:
            messages.error(request, "All fields are required.")
            return redirect(request.path + f"?ippis={ippis}")

        try:
            # Type conversion and validation
            amount_paid = Decimal(amount_paid)
            # Use datetime to create a date object for the first day of the selected month
            month = datetime.strptime(month, "%Y-%m").date()
            request_id = int(request_id)
        except (ValueError, TypeError) as e:
            messages.error(request, f"Invalid input: {e}")
            return redirect(request.path + f"?ippis={ippis}")

        consumable_request = ConsumableRequest.objects.filter(id=request_id, user=selected_user).first()
        if not consumable_request:
            messages.error(request, "Selected consumable request not found.")
            return redirect(request.path + f"?ippis={ippis}")

        # Use the total_paid method on the ConsumableRequest model for consistency
        total_paid = consumable_request.total_paid()
        remaining_balance = consumable_request.calculate_total_price() - total_paid

        if amount_paid > remaining_balance:
            messages.error(request, "Payment exceeds remaining balance.")
            return redirect(request.path + f"?ippis={ippis}")
        
        # Check if a payment for the same month already exists
        already_paid = PaybackConsumable.objects.filter(
            consumable_request=consumable_request,
            repayment_date__year=month.year,
            repayment_date__month=month.month
        ).exists()

        if already_paid:
            messages.warning(request, f"Payment already exists for {month.strftime('%B %Y')}.")
            return redirect(request.path + f"?ippis={ippis}")

        # Use a database transaction for atomicity
        with transaction.atomic():
            PaybackConsumable.objects.create(
                consumable_request=consumable_request,
                amount_paid=amount_paid,
                repayment_date=month,
                created_by=request.user # Assuming a logged-in user is making the payment
            )

            # Update the request status after the payment is created
            new_total_paid = consumable_request.total_paid()
            if new_total_paid >= consumable_request.calculate_total_price():
                consumable_request.status = 'FullyPaid'
                consumable_request.save()

        messages.success(request, f"Payment of ₦{amount_paid} recorded for {selected_user.first_name} ({ippis}).")
        return redirect(request.path + f"?ippis={ippis}")

    # Render the form for GET requests
    return render(request, "consumable/add_single_payment.html", { "requests": requests, "selected_user": selected_user,})



@login_required
def upload_consumable_payment(request):
    # 1 — Group by type instead of month
    available_requests = ConsumableRequest.objects.filter(status="Itempicked").select_related(
        "user", "consumable_type"
    )

    grouped_by_type = defaultdict(list)
    for req in available_requests:
        if req.balance() > 0:  # uses model method
            grouped_by_type[req.consumable_type].append(req)

    grouped_list = sorted(grouped_by_type.items(), key=lambda x: x[0].name)

    # 2 — Handle upload
    if request.method == "POST":
        selected_type_id = request.POST.get("selected_type")
        repayment_date_str = request.POST.get("repayment_date")
        file = request.FILES.get("excel_file")

        if not selected_type_id or not repayment_date_str or not file:
            messages.error(request, "All fields are required.")
            return redirect("upload_consumable_payment")

        try:
            selected_type = ConsumableType.objects.get(id=selected_type_id)
        except ConsumableType.DoesNotExist:
            messages.error(request, "Invalid consumable type.")
            return redirect("upload_consumable_payment")

        try:
            repayment_date = datetime.strptime(repayment_date_str, "%Y-%m-%d").date()
        except ValueError:
            messages.error(request, "Invalid repayment date format.")
            return redirect("upload_consumable_payment")

        try:
            df = pd.read_excel(file)
        except Exception as e:
            messages.error(request, f"Error reading Excel file: {e}")
            return redirect("upload_consumable_payment")

        required_cols = {"IPPIS", "Amount Paid"}
        if not required_cols.issubset(df.columns):
            messages.error(request, "Excel must contain 'IPPIS' and 'Amount Paid' columns.")
            return redirect("upload_consumable_payment")

        # Map IPPIS to requests for the selected type
        type_requests = grouped_by_type.get(selected_type, [])
        ippis_map = {
            str(req.user.member.ippis): req
            for req in type_requests
            if hasattr(req.user, "member") and req.user.member.ippis
        }

        paybacks_to_create = []
        skipped = []
        uploaded = 0

        with transaction.atomic():
            for _, row in df.iterrows():
                ippis = str(row["IPPIS"]).strip()

                # ✅ Convert amount to Decimal safely
                try:
                    amount = Decimal(str(row["Amount Paid"]))
                except Exception:
                    skipped.append(f"{ippis} (invalid amount)")
                    continue

                req = ippis_map.get(ippis)
                if not req:
                    skipped.append(ippis)
                    continue

                # Skip duplicates
                if PaybackConsumable.objects.filter(
                    consumable_request=req,
                    repayment_date=repayment_date
                ).exists():
                    skipped.append(ippis)
                    continue

                # Calculate balance_remaining before bulk_create
                total_price = Decimal(str(req.calculate_total_price()))
                total_paid_so_far = Decimal(str(
                    req.repayments.aggregate(total=Sum("amount_paid"))["total"] or 0
                ))
                balance = total_price - (total_paid_so_far + amount)

                paybacks_to_create.append(
                    PaybackConsumable(
                        consumable_request=req,
                        amount_paid=amount,
                        repayment_date=repayment_date,
                        balance_remaining=balance,
                        created_by=request.user
                    )
                )
                uploaded += 1

            if paybacks_to_create:
                PaybackConsumable.objects.bulk_create(paybacks_to_create)

                # ✅ Update statuses after creating repayments
                request_ids = {repay.consumable_request_id for repay in paybacks_to_create}
                for req in ConsumableRequest.objects.filter(id__in=request_ids):
                    req.update_status_based_on_balance()

        messages.success(request, f"{uploaded} payment(s) uploaded successfully.")
        if skipped:
            messages.warning(request, f"Skipped IPPIS: {', '.join(skipped)}")

        return redirect("upload_consumable_payment")

    context = {"grouped_list": grouped_list}
    return render(request, "consumable/upload_consumable_payment.html", context)


