from multiprocessing.sharedctypes import Value
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST
from accounts.decorators import group_required
from django.core.paginator import Paginator,PageNotAnInteger,EmptyPage
from django.db.models import Sum, Count, F, DecimalField, ExpressionWrapper
from django.forms import DecimalField
from django.http import JsonResponse, HttpResponse
from django.db.models import F, Q, Sum,Count, Avg, DecimalField, Value
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
from django.db.models.functions import TruncMonth



import requests
from loan.models import *
from .models import *
from .forms import *
from accounts.models import *
from accounts.models import *
from accounts.models import *
from main.models import *





@login_required
@group_required(['admin','staff'])
def consumable_dashboard(request):
    # === Request Statistics ===
    total_requests = ConsumableRequest.objects.count()
    pending_count = ConsumableRequest.objects.filter(status='Pending').count()
    approved_count = ConsumableRequest.objects.filter(status='Approved').count()
    completed_count = ConsumableRequest.objects.filter(status='FullyPaid').count()
    declined_count = ConsumableRequest.objects.filter(status='Declined').count()

    # === Financials (Global) ===
    total_amount_requested = ConsumableRequestDetail.objects.aggregate(
        total=Sum(
            ExpressionWrapper(
                F('quantity') * F('item_price'),
                output_field=DecimalField()
            )
        )
    )['total'] or 0

    total_amount_paid = PaybackConsumable.objects.aggregate(
        total=Sum('amount_paid')
    )['total'] or 0

    outstanding_balance = total_amount_requested - total_amount_paid

    # === Form Fees ===
    total_form_fees = ConsumableFormFee.objects.aggregate(total=Sum('form_fee'))['total'] or 0
    form_fees_paid = ConsumableFormFee.objects.filter(status="paid").aggregate(total=Sum('form_fee'))['total'] or 0
    form_fees_used = ConsumableFormFee.objects.filter(status="used").aggregate(total=Sum('form_fee'))['total'] or 0

    # === Stock (SellingPlan) ===
    stock_plans = SellingPlan.objects.select_related('purchased_item')

    # === Recent Activity ===
    recent_requests = ConsumableRequest.objects.select_related('user', 'consumable_type').order_by('-date_created')[:10]
    pending_approvals = ConsumableRequest.objects.filter(status='Pending').select_related('user', 'consumable_type')[:5]
    recent_repayments = PaybackConsumable.objects.select_related('consumable_request').order_by('-created_at')[:5]

    # === Breakdown by Consumable Type ===
    type_breakdown = (
        ConsumableType.objects.annotate(
            total_requests=Count('consumables_type'),
            total_requested=Sum(
                ExpressionWrapper(
                    F('consumables_type__details__quantity') *
                    F('consumables_type__details__item_price'),
                    output_field=DecimalField()
                )
            ),
            total_paid=Sum('consumables_type__repayments__amount_paid'),
        )
        .annotate(balance=F('total_requested') - F('total_paid'))
        .order_by('name')
    )
   

    context = {
        # Request stats
        'total_requests': total_requests,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'completed_count': completed_count,
        'declined_count': declined_count,
         

        # Financials
        'total_amount_requested': total_amount_requested,
        'total_amount_paid': total_amount_paid,
        'outstanding_balance': outstanding_balance,

        # Form fees
        'total_form_fees': total_form_fees,
        'form_fees_paid': form_fees_paid,
        'form_fees_used': form_fees_used,

        # Stock (from SellingPlan)
        'stock_plans': stock_plans,

        # Recent activity
        'recent_requests': recent_requests,
        'pending_approvals': pending_approvals,
        'recent_repayments': recent_repayments,

        # Breakdown by type
        'type_breakdown': type_breakdown,
    }

    return render(request, 'consumable/consumable_dashboard.html', context)



@login_required
@group_required(['admin','staff'])
def add_consumable_type(request):
    consumable_types = ConsumableType.objects.all()

    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        request_fee = request.POST.get('request_fee')
        consumable_type_id = request.POST.get('consumable_type_id')
        action = request.POST.get('action')  

        if consumable_type_id:  # Editing or Toggling
            consumable_type = get_object_or_404(ConsumableType, id=consumable_type_id)

            if action == 'toggle':
                consumable_type.available = not consumable_type.available
                consumable_type.save()
                messages.success(request, 'Consumable type availability updated successfully.')
                return redirect('add_consumable_type')

            elif action == 'edit':
                consumable_type.name = name
                consumable_type.description = description
                consumable_type.request_fee = request_fee
                consumable_type.save()
                messages.success(request, 'Consumable type updated successfully.')
                return redirect('add_consumable_type')

        else:  # New consumable type
            ConsumableType.objects.create(
                name=name,
                description=description,
                request_fee=request_fee,
                available=True,
                created_by=request.user
            )
            messages.success(request, 'Consumable type created successfully.')
            return redirect('add_consumable_type')

    context = {'consumable_types': consumable_types}
    return render(request, 'consumable/add_consumable_type.html', context)

@login_required
@group_required(['admin'])
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
@group_required(['admin','staff'])
def consumable_fee(request):
    member_info = None
    consumable_types = ConsumableType.objects.filter(available=True)

    # Get selected filter value
    selected_consumable_type_id = request.GET.get("consumable_type")

    if request.method == "POST":
        # Step 1: Search Member
        if "search_member" in request.POST:
            ippis = request.POST.get("ippis")
            try:
                member = Member.objects.get(ippis=ippis)
                member_info = {
                    "id": member.id,
                    "name": f"{member.member.first_name} {member.member.last_name}",
                    "ippis": member.ippis,
                }
            except Member.DoesNotExist:
                messages.error(request, f"No member found with IPPIS {ippis}.")

        # Step 2: Member Payment
        elif "make_payment" in request.POST:
            member_id = request.POST.get("member_id")
            consumable_type_id = request.POST.get("consumable_type")

            member = get_object_or_404(Member, id=member_id)
            consumable_type = get_object_or_404(ConsumableType, id=consumable_type_id)

            # prevent duplicate active payment
            if ConsumableFormFee.objects.filter(
                member=member, consumable_type=consumable_type, status="paid"
            ).exists():
                messages.warning(
                    request, f"{member} already has an active paid fee for {consumable_type.name}."
                )
                return redirect("consumable_fee")

            ConsumableFormFee.objects.create(
                member=member,
                consumable_type=consumable_type,
                form_fee=consumable_type.request_fee,
                status="paid",
                created_by=request.user,
            )
            messages.success(
                request,
                f"Consumable form fee of ₦{consumable_type.request_fee} recorded for {member}.",
            )
            return redirect("consumable_fee")

        # Step 3: Guest Payment
        elif "make_guest_payment" in request.POST:
            guest_name = request.POST.get("guest_name")
            guest_ippis = request.POST.get("guest_ippis")
            consumable_type_id = request.POST.get("consumable_type")

            if not guest_name or not guest_ippis:
                messages.error(request, "Guest Name and IPPIS are required.")
                return redirect("consumable_fee")

            consumable_type = get_object_or_404(ConsumableType, id=consumable_type_id)

            ConsumableFormFee.objects.create(
                guest_name=guest_name,
                guest_ippis=guest_ippis,
                consumable_type=consumable_type,
                form_fee=consumable_type.request_fee,
                status="paid",
                created_by=request.user,
            )
            messages.success(
                request,
                f"Consumable form fee of ₦{consumable_type.request_fee} recorded for Guest {guest_name}.",
            )
            return redirect("consumable_fee")

    # ==============================
    # Filter fees by consumable type
    # ==============================
    fees = ConsumableFormFee.objects.select_related("member", "consumable_type").order_by("-created_at")

    if selected_consumable_type_id:
        fees = fees.filter(consumable_type_id=selected_consumable_type_id)

    # Aggregates (based on filtered data)
    total_fee = fees.aggregate(total=Sum("form_fee"))["total"] or Decimal("0.00")
    fee_count = fees.count()

    # Pagination
    paginator = Paginator(fees, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "total_fee": total_fee,
        "fee_count": fee_count,
        "page_obj": page_obj,
        "consumable_types": consumable_types,
        "selected_consumable_type_id": selected_consumable_type_id,
        "member_info": member_info,
    }
    return render(request, "consumable/consumable_fee.html", context)




@login_required
@group_required(['admin','staff'])
def consumable_items(request):
    consumables = SellingPlan.objects.all()
    
    if request.method == 'POST':
        title = request.POST.get('title')
        price = request.POST.get('price')
        description = request.POST.get('description')
        item_id = request.POST.get('item_id')
        action = request.POST.get('action')  # either 'toggle' or 'edit'
        
        if item_id:
            item = get_object_or_404(SellingPlan, id=item_id)

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
            item = SellingPlan.objects.create(title=title,price=price,description=description,available=True)
            item.save()
            messages.success(request, 'Consumable item Created successfully')
            return redirect('consumable_items')
           
    context = {'consumables': consumables}
    return render(request, "consumable/consumable_items.html", context)

@login_required
@group_required(['admin'])
def delete_item(request,id):
    itemObj = get_object_or_404(Item, id=id)
    itemObj.delete()
    messages.success(request, 'Consumable item Deleted successfully')
    return redirect('consumable_items')

@login_required
@group_required(['admin','staff'])
def admin_consumables_list(request):
    consumables_list = ConsumableRequest.objects.select_related(
        'user', 'consumable_type'
    ).order_by('-date_created')

    # Apply filters based on GET parameters
    status_filter = request.GET.get('status')
    user_filter = request.GET.get('user')
    consumable_type_filter = request.GET.get('consumable_type')

    if status_filter and status_filter != 'all':
        consumables_list = consumables_list.filter(status=status_filter)

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
        'selected_status': status_filter,
        'selected_user': user_filter,
        'selected_consumable_type': consumable_type_filter,
    }
    return render(request, 'consumable/consumables_list.html', context)


@login_required
@group_required(['admin','staff'])
def admin_consumable_detail(request, request_id):
    consumable_request = get_object_or_404(
        ConsumableRequest.objects.select_related('user', 'consumable_type')
        .prefetch_related('details__selling_item__purchased_item', 'repayments'),
        id=request_id
    )

    total_paid = consumable_request.total_paid
    balance = consumable_request.balance

    context = {
        'consumable_request': consumable_request,
        'total_paid': total_paid,
        'balance': balance
    }
    return render(request, 'consumable/consumables_detail.html', context)

@login_required
@group_required(['admin'])
@require_POST
def admin_request_approve(request, request_id):
    consumable_request = get_object_or_404(ConsumableRequest, id=request_id)
    if consumable_request.status == 'Pending':
        consumable_request.status = 'Approved'
        consumable_request.approved_by = request.user
        consumable_request.save(update_fields=['status', 'approved_by'])
        messages.success(request, f"Request #{request_id} has been approved.")
    return redirect('admin_consumable_detail', request_id=request_id)

@login_required
@group_required(['admin'])
@require_POST
def admin_request_reject(request, request_id):
    consumable_request = get_object_or_404(ConsumableRequest, id=request_id)
    if consumable_request.status == 'Pending':
        consumable_request.status = 'Declined'
        consumable_request.approved_by = request.user
        consumable_request.save(update_fields=['status', 'approved_by'])
        messages.error(request, f"Request #{request_id} has been declined.")
    return redirect('admin_consumable_detail', request_id=request_id)


@login_required
@group_required(['admin'])
def admin_request_taking(request, request_id):
    consumable_request = get_object_or_404(ConsumableRequest, id=request_id)

    with transaction.atomic():
        if consumable_request.status == 'Approved':
            request_details = ConsumableRequestDetail.objects.filter(request=consumable_request)

            for detail in request_details:
                # Set approval date
                detail.approval_date = timezone.now().date()
                detail.save(update_fields=['approval_date'])

                # Create a picked log
                PickedLog.objects.create(
                    request_detail=detail,
                    picked_by=request.user,
                )

            # Update main request status
            consumable_request.status = 'Itempicked'
            consumable_request.approved_by = request.user
            consumable_request.save(update_fields=['status', 'approved_by'])

            messages.success(
                request,
                f"Request #{request_id} has been marked as 'Itempicked'. Items logged."
            )

        elif consumable_request.status == 'Itempicked':
            messages.info(
                request,
                f"Request #{request_id} has already been marked as 'Itempicked'."
            )
        else:
            messages.error(
                request,
                f"Cannot mark request #{request_id} as 'Itempicked' because its status is '{consumable_request.status}'."
            )

    return redirect('admin_consumable_detail', request_id=request_id)

@login_required
@group_required(['admin','staff'])
def consumable_types_with_requests(request):
    # Group ConsumableTypes by status counts
    requested_types = ConsumableType.objects.filter(consumables_type__isnull=False).annotate(
        pending_count=Count('consumables_type', filter=Q(consumables_type__status='Pending')),
        approved_count=Count('consumables_type', filter=Q(consumables_type__status='Approved')),
        itempicked_count=Count('consumables_type', filter=Q(consumables_type__status='Itempicked')),
        fully_paid_count=Count('consumables_type', filter=Q(consumables_type__status='FullyPaid')),
        declined_count=Count('consumables_type', filter=Q(consumables_type__status='Declined')),
    ).distinct()

    context = {'requested_types': requested_types}
    return render(request, 'consumable/requested_types_list.html', context)


@login_required
@group_required(['admin','staff'])
def members_by_consumable_type(request, id):
    consumable_type = get_object_or_404(ConsumableType, id=id)
    requests_qs = ConsumableRequest.objects.filter(
        consumable_type=consumable_type
    ).select_related('user').prefetch_related('details', 'repayments').order_by('-date_created')

    # Annotate total price per request
    requests_with_amounts = requests_qs.annotate(
        total_price=Sum(F('details__item_price') * F('details__quantity'))
    )

    # Pagination
    paginator = Paginator(requests_with_amounts, 10)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.get_page(1)
    except EmptyPage:
        page_obj = paginator.get_page(paginator.num_pages)

    # Calculate totals
    total_requests_amount = requests_with_amounts.aggregate(
        total_requested=Sum('total_price')
    )['total_requested'] or Decimal('0.00')

    total_paid = requests_qs.aggregate(
        total_paid=Sum('repayments__amount_paid')
    )['total_paid'] or Decimal('0.00')

    total_remaining_balance = total_requests_amount - total_paid

    # Format decimals
    formatted_total_requests_amount = '{:.2f}'.format(total_requests_amount)
    formatted_total_paid = '{:.2f}'.format(total_paid)
    formatted_total_remaining_balance = '{:.2f}'.format(total_remaining_balance)

    # Unique members
    members = {req.user for req in requests_qs}

    context = {
        'consumable_type': consumable_type,
        'page_obj': page_obj,
        'requests': requests_with_amounts,
        'members': members,
        'total_requests_amount': formatted_total_requests_amount,
        'total_remaining_balance': formatted_total_remaining_balance,
        'total_paid': formatted_total_paid,
    }
    return render(request, 'consumable/members_by_type.html', context)


@login_required
@group_required(['admin'])
def add_payment(request, request_id):
    consumable_request = get_object_or_404(ConsumableRequest, id=request_id)
    if request.method == 'POST':
        amount_paid = request.POST.get('amount_paid')
        repayment_date = request.POST.get('repayment_date')
        payment_receipt = request.FILES.get("payment_receipt")

        # Validate amount
        try:
            amount_paid = float(amount_paid)
            if amount_paid <= 0:
                raise ValueError("Amount must be positive")
        except (ValueError, TypeError):
            messages.error(request, 'Invalid amount provided')
            return redirect('admin_consumable_detail', request_id=request_id)

        # Validate date
        try:
            repayment_date = datetime.strptime(repayment_date, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.error(request, 'Invalid date provided')
            return redirect('admin_consumable_detail', request_id=request_id)

        # Check balance
        current_balance = consumable_request.balance
        if amount_paid > current_balance:
            messages.error(
                request,
                f'Payment amount (₦{amount_paid:,.2f}) exceeds remaining balance (₦{current_balance:,.2f})'
            )
            return redirect('admin_consumable_detail', request_id=request_id)

        # Create payment record
        PaybackConsumable.objects.create(
            consumable_request=consumable_request,
            amount_paid=amount_paid,
            repayment_date=repayment_date,
            payment_receipt=payment_receipt,
            created_by=request.user
        )

        messages.success(request, f'Payment of ₦{amount_paid:,.2f} added successfully')

        # Update request status if fully paid
        if consumable_request.balance <= 0:
            consumable_request.status = 'FullyPaid'
            consumable_request.save(update_fields=['status'])
            messages.info(request, 'Request marked as Fully Paid')

    return redirect('admin_consumable_detail', request_id=request_id)

@login_required
@group_required(['admin'])
def admin_edit_consumable_request(request, request_id):
    consumable_request = get_object_or_404(ConsumableRequest, id=request_id)
    details = consumable_request.details.all()

    if request.method == 'POST':
        detail_id = request.POST.get('detail_id')
        if not detail_id:
            messages.error(request, "Detail ID is missing.")
            return redirect('admin_edit_consumable_request', request_id=request_id)

        detail_to_update = get_object_or_404(
            ConsumableRequestDetail, id=detail_id, request=consumable_request
        )
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
                return redirect('admin_edit_consumable_request', request_id=request_id)
            except Exception as e:
                messages.error(request, f"An error occurred: {e}")
        else:
            messages.error(request, "Please provide valid input for all fields.")

    context = {
        'request_obj': consumable_request,
        'details': details,
        'form': AdminUpdateConsumableRequestForm()
    }
    return render(request, 'consumable/admin_edit_request.html', context)


@login_required
@group_required(['admin'])
def add_single_consumable_payment(request):
    requests_list = []
    selected_user = None
    ippis = request.GET.get("ippis") or request.POST.get("ippis")

    if ippis:
        try:
            member_obj = Member.objects.filter(ippis=int(ippis)).first()
            if member_obj and member_obj.member:
                selected_user = member_obj.member
                requests_list = ConsumableRequest.objects.filter(
                    user=selected_user
                ).exclude(status__in=['FullyPaid', 'Declined'])
        except Exception as e:
            messages.error(request, f"Error fetching member: {e}")

    if request.method == "POST":
        amount_paid = request.POST.get("amount_paid")
        month = request.POST.get("month")
        payment_receipt = request.FILES.get("payment_receipt")
        request_id = request.POST.get("consumable_request")

        # Validate required fields
        if not (ippis and amount_paid and month and request_id):
            messages.error(request, "All fields are required.")
            return redirect(f"{request.path}?ippis={ippis}")

        try:
            amount_paid = Decimal(amount_paid)
            if amount_paid <= 0:
                raise ValueError("Amount must be positive")
            month_date = datetime.strptime(month, "%Y-%m").date()
            request_id = int(request_id)
        except (ValueError, TypeError) as e:
            messages.error(request, f"Invalid input: {e}")
            return redirect(f"{request.path}?ippis={ippis}")

        consumable_request = ConsumableRequest.objects.filter(
            id=request_id, user=selected_user
        ).first()

        if not consumable_request:
            messages.error(request, "Selected consumable request not found.")
            return redirect(f"{request.path}?ippis={ippis}")

        total_paid = consumable_request.total_paid
        remaining_balance = consumable_request.calculate_total_price() - total_paid

        if amount_paid > remaining_balance:
            messages.error(request, "Payment exceeds remaining balance.")
            return redirect(f"{request.path}?ippis={ippis}")

        # Check for existing payment for the same month
        if PaybackConsumable.objects.filter(
            consumable_request=consumable_request,
            repayment_date__year=month_date.year,
            repayment_date__month=month_date.month
        ).exists():
            messages.warning(request, f"Payment already exists for {month_date.strftime('%B %Y')}.")
            return redirect(f"{request.path}?ippis={ippis}")

        # Create payment transaction
        with transaction.atomic():
            PaybackConsumable.objects.create(
                consumable_request=consumable_request,
                amount_paid=amount_paid,
                repayment_date=month_date,
                payment_receipt=payment_receipt,
                created_by=request.user
            )
            # Update status if fully paid
            if consumable_request.total_paid >= consumable_request.calculate_total_price():
                consumable_request.status = 'FullyPaid'
                consumable_request.save(update_fields=['status'])

        messages.success(
            request,
            f"Payment of ₦{amount_paid:,.2f} recorded for {selected_user.first_name} ({ippis})."
        )
        return redirect(f"{request.path}?ippis={ippis}")

    return render(
        request,
        "consumable/add_single_payment.html",
        {"requests": requests_list, "selected_user": selected_user}
    )


@login_required
@group_required(['admin'])
def upload_consumable_payment(request):
    # 1 — Group by type instead of month
    available_requests = ConsumableRequest.objects.filter(status="Itempicked").select_related(
        "user", "consumable_type"
    )

    grouped_by_type = defaultdict(list)
    for req in available_requests:
        if req.balance > 0:  # uses model method
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
                raw_ippis = row["IPPIS"]

                if pd.isna(raw_ippis):  # skip empty IPPIS
                    skipped.append("Empty IPPIS")
                    continue

                if isinstance(raw_ippis, (int, float)):
                    ippis = str(int(raw_ippis))
                else:
                    ippis = str(raw_ippis).strip()

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


@login_required
@group_required(['admin','staff'])
def item_list_with_requests(request):
    items = ( SellingPlan.objects.all().select_related("purchased_item")
        .prefetch_related("details__request") 
    )
    # sel = SellingPlan.objects.annotate(totla_value=F('selling_price_per_unit') * F('quantity'))
    # print('sel', sel)
    grand_total_amount = 0
    grand_total_profit = 0

    for item in items:
        # Total quantity requested for this selling item
        total_requested = item.details.aggregate(total=Sum("quantity"))["total"] or 0
        print(total_requested)
        item.total_requested = total_requested

        # Total amount requested = selling price * requested quantity
        item.total_amount_requested = item.selling_price_per_unit * total_requested

        # Total profit requested = sum of each detail's profit (already correct in model)
        item.total_profit_requested = sum(detail.profit for detail in item.details.all())

        # Remaining stock
        # item.remaining_stock = item.quantity - total_requested
        
        # Add to grand totals
        grand_total_amount += item.total_amount_requested
        grand_total_profit += item.total_profit_requested

    context = {
        "items": items,
        "grand_total_amount": grand_total_amount,
        "grand_total_profit": grand_total_profit,
        # "sel":sel,
    }
    return render(request, "consumable/item_list.html", context)

@login_required
@group_required(['admin','staff'])
def item_request_list(request, item_id):
    # Get the item (SellingPlan)
    selling_plan = get_object_or_404(SellingPlan, id=item_id)

    # Get all requests related to this item
    requests_for_item = ConsumableRequestDetail.objects.filter( selling_item_id=selling_plan ).select_related("request__user")

    context = {
        "selling_plan": selling_plan,
        "requests_for_item": requests_for_item,
        'title': f"Requests for {selling_plan.purchased_item.item_name}"
    }
    return render(request, "consumable/item_request_list.html", context)




# 1. Monthly totals
def monthly_consumable_paybacks_summary():
    """Get monthly payback totals for consumables"""
    return (
        PaybackConsumable.objects
        .annotate(month=TruncMonth("repayment_date"))
        .values("month")
        .annotate(
            total_payments=Sum("amount_paid"),
            number_of_payments=Count("id"),
            average_payment=Avg("amount_paid")
        )
        .order_by("month")
    )

# 2. Totals by Consumable Type
def total_consumable_payments_by_type():
    """Get total repayments grouped by consumable type"""
    return (
        PaybackConsumable.objects
        .values("consumable_request__consumable_type__name")
        .annotate(total_amount=Sum("amount_paid"))
        .order_by("-total_amount")
    )

# 3. Monthly breakdown by Consumable Type
def monthly_consumable_payments_by_type():
    """Monthly breakdown of repayments by consumable type"""
    return (
        PaybackConsumable.objects
        .annotate(month=TruncMonth("repayment_date"))
        .values("month", "consumable_request__consumable_type__name")
        .annotate(
            total_amount=Sum("amount_paid"),
            payment_count=Count("id"),
            average_payment=Avg("amount_paid")
        )
        .order_by("month", "consumable_request__consumable_type__name")
    )



@login_required
@group_required(['admin'])
def consumable_analytics_view(request):
    # Get datasets
    monthly_payments = monthly_consumable_paybacks_summary()
    type_totals_raw = total_consumable_payments_by_type()
    detailed_breakdown = monthly_consumable_payments_by_type()

    # Pagination
    paginator = Paginator(detailed_breakdown, 10)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # Summary statistics
    all_payments = PaybackConsumable.objects.aggregate(
        total=Sum("amount_paid"),
        count=Count("id")
    )

    # Current month total
    current_month = timezone.now().date().replace(day=1)
    current_month_payments = PaybackConsumable.objects.filter(
        repayment_date__gte=current_month
    ).aggregate(total=Sum("amount_paid"))

    # Build normalized consumable_type_totals with percentages
    total_all = all_payments["total"] or Decimal("0.00")
    consumable_type_totals = []
    for item in type_totals_raw:
        amt = item.get("total_amount") or Decimal("0.00")
        percentage = (amt / total_all * 100) if total_all and total_all > 0 else 0
        consumable_type_totals.append({
            # simpler key for template
            "consumable_type": item.get("consumable_request__consumable_type__name"),
            "total_amount": amt,
            "percentage": percentage,
        })

    context = {
        # Data for charts/tables
        "monthly_payments": monthly_payments,
        "consumable_type_totals": consumable_type_totals,   # <-- template expects this
        "type_totals": consumable_type_totals,              # <-- keep alias if other code uses it
        "detailed_breakdown": page_obj,

        # Summary statistics
        "total_all_payments": total_all,
        "total_transactions": all_payments["count"] or 0,
        "current_month_total": current_month_payments["total"] or 0,

        # Pagination
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "today": timezone.now().date(),
    }

    return render(request, "consumable/consumable_analytics.html", context)