# views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from accounts.decorators import group_required
from django.forms import inlineformset_factory
from django.utils.dateparse import parse_date
import pandas as pd
from decimal import Decimal, InvalidOperation
from django.db.models.deletion import ProtectedError
from decimal import Decimal
from datetime import datetime
from django.db.models.functions import Coalesce
import json
from django.db import transaction
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from decimal import Decimal, InvalidOperation
from django.http import HttpResponseForbidden, JsonResponse, HttpResponseRedirect
from django.db.models import Sum, F, Q, ExpressionWrapper, DecimalField
from .models import *
from inventory_app.models import SellingPlan, MemberRequest, MemberRequestDetail,Supplier, StockIn, ReceivedItem, StockReturn
from accounts.models import *
from form_app.models import *
from .forms import StockInForm, ReceivedItemFormSet
import openpyxl
from django.http import HttpResponse
from django.utils.timezone import localtime





@login_required
@group_required(['admin', 'staff'])
def inventory_home(request):
    # ── Recent Stock Receipts ─────────────────────────────────────
    supplies = (
        StockIn.objects
        .select_related('supplier')
        .prefetch_related('items__stockreturn_set')
        .order_by('-received_at')[:5]
    )

    # ── Product / Item Stats ──────────────────────────────────────
    product_count = ReceivedItem.objects.count()

    all_items = ReceivedItem.objects.prefetch_related('stockreturn_set')

    gross_stock_value    = sum(item.total_price     for item in all_items)
    net_stock_value      = sum(item.net_stock_value for item in all_items)
    total_returned_value = gross_stock_value - net_stock_value

    # Items with zero stock left (all returned or used)
    low_stock_items = [item for item in all_items if item.net_quantity == 0]
    low_stock_count = len(low_stock_items)

    # ── Member Request Stats ──────────────────────────────────────
    all_requests = MemberRequest.objects.all()

    total_requests   = all_requests.count()
    pending_requests = all_requests.filter(status='Pending').count()
    approved_requests = all_requests.filter(status='Approved').count()
    picked_requests  = all_requests.filter(status='ItemPicked').count()
    fully_paid_count = all_requests.filter(status='Fully Paid').count()
    declined_count   = all_requests.filter(status='Declined').count()

    # ── Repayment / Financial Stats ───────────────────────────────
    total_repaid = MemberRequestPayback.objects.aggregate(
        total=Sum('amount_paid')
    )['total'] or Decimal('0.00')

    # Total approved loan value (sum of all request totals for ItemPicked/Approved)
    active_requests = MemberRequest.objects.filter(
        status__in=['Approved', 'ItemPicked', 'Fully Paid']
    ).prefetch_related('details__item')

    total_approved_value = sum(
        req.calculate_total_price() for req in active_requests
    )

    total_outstanding = total_approved_value - total_repaid

    # ── Selling Plan Stats ────────────────────────────────────────
    available_plans   = SellingPlan.objects.filter(available=True).count()
    unavailable_plans = SellingPlan.objects.filter(available=False).count()

    context = {
        # stock
        'supplies':             supplies,
        'product_count':        product_count,
        'gross_stock_value':    gross_stock_value,
        'net_stock_value':      net_stock_value,
        'total_returned_value': total_returned_value,
        'low_stock_count':      low_stock_count,

        # requests
        'total_requests':    total_requests,
        'pending_requests':  pending_requests,
        'approved_requests': approved_requests,
        'picked_requests':   picked_requests,
        'fully_paid_count':  fully_paid_count,
        'declined_count':    declined_count,

        # financials
        'total_repaid':        total_repaid,
        'total_approved_value': total_approved_value,
        'total_outstanding':   total_outstanding,

        # selling plans
        'available_plans':   available_plans,
        'unavailable_plans': unavailable_plans,
    }
    return render(request, 'inventory_app/inventory_home.html', context)

def register_supplier(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        
        Supplier.objects.create(name=name,phone=phone,address=address)
        messages.success(request,'Supplier Add Successfull')
        return redirect('inventory_home')
    return render(request, 'inventory_app/register_supplier.html')
        
@login_required
@group_required(['admin'])
def receive_products_view(request):
    if request.method == 'POST':
        form    = StockInForm(request.POST)
        formset = ReceivedItemFormSet(request.POST, queryset=ReceivedItem.objects.none())

        if form.is_valid() and formset.is_valid():
            stock_in = form.save(commit=False)
            stock_in.received_by = request.user
            stock_in.save()

            instances = formset.save(commit=False)
            for instance in instances:
                instance.stock_in    = stock_in
                instance.received_by = request.user
                instance.save()

            # handle deletions from can_delete=True
            for obj in formset.deleted_objects:
                obj.delete()

            messages.success(request, 'Stock received successfully.')
            return redirect('inventory_home')
    else:
        form    = StockInForm()
        formset = ReceivedItemFormSet(queryset=ReceivedItem.objects.none())

    context = {'form': form, 'formset': formset}
    return render(request, 'inventory_app/receive_products.html', context)


@login_required
@group_required(['admin'])
def stock_return_view(request):
    if request.method == 'POST':
        product_id = request.POST.get('product')

        try:
            qty_to_return = int(request.POST.get('quantity', 0))
            if qty_to_return <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, 'Invalid quantity provided.')
            return redirect('stock_return')

        item = get_object_or_404(ReceivedItem, id=product_id)

        if item.net_quantity >= qty_to_return:
            StockReturn.objects.create(
                stock_item=item,
                supplier=item.stock_in.supplier,
                quantity=qty_to_return,
                returned_by=request.user,
                reason=request.POST.get('reason', ''),
            )
            messages.success(
                request,
                f'Successfully returned {qty_to_return} unit(s) of {item.model_name}.'
            )
            return redirect('inventory_home')
        else:
            messages.error(
                request,
                f'Cannot return {qty_to_return}. Only {item.net_quantity} available.'
            )
            return redirect('stock_return')

    # Only show items that actually have stock left.
    # prefetch returns so net_quantity doesn't fire N+1 queries in the template.
    items = (
        ReceivedItem.objects
        .prefetch_related('stockreturn_set')
        .select_related('stock_in__supplier')
    )
    # filter in Python — net_quantity is a @property, not a DB field
    items_in_stock = [item for item in items if item.net_quantity > 0]

    context = {'items': items_in_stock}
    return render(request, 'inventory_app/stock_return.html', context)

@login_required
@group_required(['admin', 'staff'])
def product_list_view(request):
    products = (ReceivedItem.objects.select_related('stock_in__supplier').prefetch_related('stockreturn_set').order_by('-received_at'))
    context = {'products': products}
    return render(request, 'inventory_app/product_list.html', context)

@login_required
@group_required(['admin', 'staff'])
def product_detail_view(request, id):
    product = get_object_or_404(
        ReceivedItem.objects
        .select_related('stock_in__supplier', 'received_by')
        .prefetch_related('stockreturn_set__returned_by'),
        id=id,
    )

    returned_qty = product.quantity - product.net_quantity
    context = {'product':product,'returned_qty': returned_qty,}
    return render(request, 'inventory_app/product_detail.html', context)


@login_required
@group_required(['admin'])
def create_selling_plan(request, id):
    received_item = get_object_or_404(ReceivedItem, id=id)

    # Prevent duplicate plan
    if SellingPlan.objects.filter(received_item=received_item).exists():
        messages.error(request, 'Selling plan already exists for this item.')
        return redirect('receive_item_selling_plan_detail', id=received_item.selling_plan.id)

    if request.method == 'POST':
        try:
            plan = SellingPlan(
                received_item=received_item,
                selling_price_per_unit=Decimal(request.POST.get('selling_price_per_unit', '0')),
                quantity=int(request.POST.get('quantity', 0)),
                created_by=request.user,
                notes=request.POST.get('notes', '').strip(),
                include_expenditure=request.POST.get('include_expenditure') == 'on'
            )

            plan.full_clean()
            plan.save()
            plan.update_profit()

            messages.success(request, 'Selling plan created successfully!')
            return redirect('receive_item_selling_plan_detail', id=plan.id)

        except (ValueError, ValidationError, InvalidOperation) as e:
            messages.error(request, f'Error: {str(e)}')

    context = {'received_item': received_item,'title': 'Create Selling Plan'}
    return render(request, 'inventory_app/selling_plan.html', context)


@login_required
def selling_plan_list(request):
    qs = (SellingPlan.objects.select_related('received_item', 'created_by').all())
 
    # --- filters ---
    search = request.GET.get('q', '').strip()
    available = request.GET.get('available', '')
 
    if search:
        qs = qs.filter(
            Q(received_item__brand__icontains=search) |
            Q(received_item__model_name__icontains=search)
        )
 
    if available == '1':
        qs = qs.filter(available=True)
    elif available == '0':
        qs = qs.filter(available=False)
 
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
 
    context = {
        'page_obj': page_obj,
        'search': search,
        'available': available,
        'title': 'Selling Plans',
    }
    return render(request, 'inventory_app/selling_plan_list.html', context)

@login_required
def inventory_selling_plan_edit(request, pk):
    inventory_plan = get_object_or_404(SellingPlan, pk=pk)

    if request.method == 'POST':
        original_price = inventory_plan.selling_price_per_unit
        original_qty   = inventory_plan.quantity
        original_notes = inventory_plan.notes
        original_incl  = inventory_plan.include_expenditure
        original_avail = inventory_plan.available

        try:
            inventory_plan.selling_price_per_unit = Decimal(request.POST.get('selling_price_per_unit', '0'))
            inventory_plan.quantity = int(request.POST.get('quantity', 0))
            inventory_plan.notes = request.POST.get('notes', '').strip()
            inventory_plan.include_expenditure = request.POST.get('include_expenditure') == 'on'
            inventory_plan.available = request.POST.get('available') == 'on'
            inventory_plan.full_clean()
            inventory_plan.save()
            inventory_plan.update_profit()
            messages.success(request, 'Selling plan updated successfully!')
            return redirect('receive_item_selling_plan_detail', id=inventory_plan.id)

        except (ValueError, ValidationError, InvalidOperation) as e:
            # restore original values so the template shows clean state
            inventory_plan.selling_price_per_unit = original_price
            inventory_plan.quantity = original_qty
            inventory_plan.notes = original_notes
            inventory_plan.include_expenditure = original_incl
            inventory_plan.available = original_avail
            messages.error(request, f'Error: {str(e)}')

    context = {'inventory_plan': inventory_plan}
    return render(request, 'inventory_app/inventory_selling_plan_edit.html', context)

# ──────────────────────────────────────────────
# TOGGLE AVAILABILITY (quick action)
# ──────────────────────────────────────────────
@login_required
def selling_plan_toggle_available(request, pk):
    if request.method == 'POST':
        plan = get_object_or_404(SellingPlan, pk=pk)
        plan.available = not plan.available
        plan.save(update_fields=['available'])
        status = 'available' if plan.available else 'unavailable'
        messages.success(request, f'Plan marked as {status}.')
    return redirect('inventory-selling-plans_list')

@login_required
@group_required(['admin'])
def receive_item_selling_plan_detail(request, id):
    plan = get_object_or_404( SellingPlan.objects.select_related('received_item', 'created_by'),id=id)
    context = {'plan':plan,'received_item': plan.received_item,'title':'Selling Plan Detail'}
    return render(request, 'inventory_app/receive_item_selling_plan_detail.html', context)



@login_required
def inventory_plan_delete(request, pk):
    plan_del = get_object_or_404(SellingPlan, pk=pk)
    try:
        plan_del.delete()
        messages.success(request, 'Selling plan deleted.')
    except ProtectedError as e:
        # extract the related objects blocking deletion
        blocking = e.protected_objects
        messages.error(
            request,
            f'Cannot delete this plan — it is referenced by '
            f'{len(blocking)} member request detail(s). '
            f'Remove those requests first, then try again.'
        )
    return redirect('inventory-selling-plans_list')
    
@login_required
@group_required(['admin', 'staff','members', 'non staff member','loan committee'])
def member_make_request(request):
    items = SellingPlan.objects.filter(available=True).select_related('received_item')
    member_info = None

    if request.method == 'POST':
        # ── SEARCH MEMBER ──────────────────────────────────────────
        if "search_member" in request.POST:
            ippis = request.POST.get('ippis', '').strip()
            try:
                member = Member.objects.get(ippis=ippis)
                member_info = {
                    'id': member.id,
                    'name': f"{member.member.first_name} {member.member.last_name}",
                    'ippis': member.ippis,
                }
            except Member.DoesNotExist:
                messages.error(request, f"No member found with IPPIS {ippis}.")

        # ── CREATE MEMBER REQUEST ──────────────────────────────────
        elif "create_request" in request.POST:
            member_id = request.POST.get('member_id')
            item_id = request.POST.get('item_id')
            duration_months = request.POST.get('duration_months')
            file_payslip = request.FILES.get('file_payslip')
            passport_photo = request.FILES.get('passport_photo')
            guarantor_ippis = request.POST.get("guarantor_ippis", "").strip()

            try:
                quantity = int(request.POST.get('quantity', 0))
            except (ValueError, TypeError):
                messages.error(request, "Invalid quantity entered.")
                return redirect('member_make_request')

            try:
                member = Member.objects.get(id=member_id)
                item_plan = SellingPlan.objects.get(id=item_id)

                if quantity <= 0:
                    messages.error(request, "Quantity must be greater than zero.")
                    return redirect('member_make_request')

                if quantity > item_plan.quantity:
                    messages.error(request, f"Quantity exceeds available stock ({item_plan.quantity}).")
                    return redirect('member_make_request')

               # ── PAYMENT CHECK ──────────────────────
                with transaction.atomic():
                    ram_payment_type = PaymentType.objects.get(title="Phones and other Items")

                    payment = RequestFormPayment.objects.filter(
                        member=member,
                        payment_type=ram_payment_type,
                        status="paid"
                    ).select_for_update().first()
                    # payment = RequestFormPayment.objects.filter(
                    #     member=member,
                    #     status="paid"
                    # ).select_for_update().first()

                    if not payment:
                        messages.error(request, f"You have not paid for this {ram_payment_type} request form Fee.")
                        return redirect("member_make_request")

                    updated = RequestFormPayment.objects.filter(
                        id=payment.id,
                        status="paid"
                    ).update(status="used")

                    if not updated:
                        messages.error(request, "Payment already used.")
                        return redirect("member_make_request")

                # ── RESOLVE GUARANTOR ──────────────────
                guarantor = None
                if guarantor_ippis:
                    try:
                        guarantor = Member.objects.get(ippis=guarantor_ippis)
                    except Member.DoesNotExist:
                        messages.error(request, f"No guarantor found with IPPIS {guarantor_ippis}.")
                        return redirect('member_make_request')

                member_request = MemberRequest.objects.create(
                    member=member,
                    guarantor=guarantor,
                    file_payslip=file_payslip,
                    passport_photo=passport_photo,
                )

                MemberRequestDetail.objects.create(
                    request=member_request,
                    item=item_plan,
                    quantity=quantity,
                    duration_months=duration_months,
                    item_price=item_plan.selling_price_per_unit,
                )

                messages.success(request, "Request created successfully!")
                return redirect('member_make_request_list')

            except Member.DoesNotExist:
                messages.error(request, "Member not found.")
            except SellingPlan.DoesNotExist:
                messages.error(request, "Selected item not found.")
            except Exception as e:
                messages.error(request, str(e))

        # ── CREATE GUEST REQUEST ───────────────────────────────────
        elif "make_guest_Request" in request.POST:
            guest_name = request.POST.get("guest_name", "").strip()
            guest_ippis = request.POST.get("guest_ippis", "").strip()
            guest_phone = request.POST.get("guest_phone", "").strip()
            guarantor_ippis = request.POST.get("guarantor_ippis", "").strip()
            item_id = request.POST.get('item_id')
            duration_months = request.POST.get('duration_months')
            file_payslip = request.FILES.get("file_payslip")
            passport_photo = request.FILES.get("passport_photo")

            try:
                quantity = int(request.POST.get('quantity', 0))
            except (ValueError, TypeError):
                messages.error(request, "Invalid quantity entered.")
                return redirect("member_make_request")

            if not guest_name or not guest_ippis:
                messages.error(request, "Guest Name and IPPIS are required.")
                return redirect("member_make_request")

            if quantity <= 0:
                messages.error(request, "Quantity must be greater than zero.")
                return redirect("member_make_request")

            try:
                item_plan = SellingPlan.objects.get(id=item_id)
            except SellingPlan.DoesNotExist:
                messages.error(request, "Selected item not found.")
                return redirect("member_make_request")

            if quantity > item_plan.quantity:
                messages.error(request, f"Quantity exceeds available stock ({item_plan.quantity}).")
                return redirect('member_make_request')

            # ── PAYMENT CHECK ──────────────────────
            with transaction.atomic():
                ram_payment_type = PaymentType.objects.get(title="Phones and other Items")

                payment = RequestFormPayment.objects.filter(
                        member=member,
                        payment_type=ram_payment_type,
                        status="paid"
                    ).select_for_update().first()

                if not payment:
                    messages.error(request, "Guest has not paid for this request form Fee.")
                    return redirect("member_make_request")

                updated = RequestFormPayment.objects.filter(
                    id=payment.id,
                    status="paid"
                ).update(status="used")

                if not updated:
                    messages.error(request, "Payment already used.")
                    return redirect("member_make_request")

            # ── RESOLVE GUARANTOR ──────────────────
            guarantor = None
            if guarantor_ippis:
                try:
                    guarantor = Member.objects.get(ippis=guarantor_ippis)
                except Member.DoesNotExist:
                    messages.error(request, f"No guarantor found with IPPIS {guarantor_ippis}.")
                    return redirect('member_make_request')

            try:
                guest_request = MemberRequest.objects.create(
                    guest_name=guest_name,
                    guest_ippis=guest_ippis,
                    guest_phone=guest_phone,
                    guarantor=guarantor,
                    file_payslip=file_payslip,
                    passport_photo=passport_photo,
                )

                MemberRequestDetail.objects.create(
                    request=guest_request,
                    item=item_plan,
                    quantity=quantity,
                    duration_months=duration_months,
                    item_price=item_plan.selling_price_per_unit,
                )

                messages.success(request, "Guest request created successfully!")
                return redirect('member_make_request_list')

            except Exception as e:
                messages.error(request, str(e))

    context = {"member_info": member_info, "items": items}
    return render(request, 'inventory_app/member_make_request.html', context)

# @login_required
# @group_required(['admin', 'staff'])
# def member_make_request_list(request):
#     search_query  = request.GET.get('search', '').strip()
#     status_filter  = request.GET.get('status', '').strip()
#     date_from = request.GET.get('date_from', '').strip()
#     date_to = request.GET.get('date_to', '').strip()
#     # requests = MemberRequest.objects.prefetch_related('details')
#     request_list = MemberRequest.objects.select_related('member', 'approved_by', 'guarantor').prefetch_related('details__item__received_item', 'repayments')
    
#     total_amount = Decimal(0.00)
#     pending_amount = Decimal(0.00)
#     approved_amount = Decimal(0.00)
#     picked_amount = Decimal(0.00)
#     declined_amount = Decimal(0.00)
#     fullypaid_amount = Decimal(0.00)
    
#     for r in request_list:
#         amount = r.calculate_total_price()or Decimal('0.00')
#         total_amount += amount 
        
#         if r.status == 'Pending':
#             pending_amount += amount
            
#         if r.status == 'Approved':
#             approved_amount += amount
            
#         if r.status == 'ItemPicked':
#             picked_amount += amount
            
#         if r.status == 'Declined':
#             declined_amount += amount
            
#         if r.status == 'Fully Paid':
#             fullypaid_amount += amount
            
        
        
    
#     # Apply Search Filter
#     if search_query:
#         request_list = request_list.filter(
#             Q(member__member__first_name__icontains=search_query) |
#             Q(member__member__last_name__icontains=search_query) |
#             Q(member__ippis__icontains=search_query) |
#             Q(guest_name__icontains=search_query) |
#             Q(guest_ippis__icontains=search_query)
#         ) 
        
#     # Apply Status Filter
#     if status_filter:
#         request_list = request_list.filter(status=status_filter)  
    
#     # Apply Date Range Filters
#     if date_from:
#         request_list = request_list.filter(date_created__date__gte=date_from)
        
#     if date_to:
#         request_list = request_list.filter(date_created__date__lte=date_to)
        
#     # Check if user requested an Excel Export
#     if request.GET.get('export') == 'excel':
#         wb = openpyxl.Workbook()
#         ws = wb.active
#         ws.title = "Member Requests"
        
#         # CHANGED: Separated Item, Qty, Markup, and Duration into clean distinct columns
#         headers = [
#             "ID", "Member Name", "IPPIS No.", 
#             "Item Name", "Quantity", "Markup Rate", "Duration (Months)", 
#             "Total Amount (₦)", "Total Paid (₦)", "Balance (₦)", 
#             "Status", "Date Created"
#         ]
#         ws.append(headers)
        
#         # Populate rows
#         for req in request_list:
#             # --- Member Name and IPPIS Consolidation ---
#             if req.member and req.member.member:
#                 customer_name = f"{req.member.member.first_name} {req.member.member.last_name}"
#                 ippis_no = req.member.ippis or "N/A"
#             else:
#                 customer_name = req.guest_name or "Unknown Customer"
#                 ippis_no = req.guest_ippis or "N/A"

#             # Use Model Properties for Financial Data
#             total_amount = req.calculate_total_price()
#             total_paid = req.total_paid
#             balance = req.balance
#             formatted_date = localtime(req.date_created).strftime('%Y-%m-%d %H:%M') if req.date_created else ""

#             # Check if request has items. If empty, write a single fallback row
#             if not req.details.exists():
#                 ws.append([
#                     req.id, customer_name, ippis_no,
#                     "No Items", 0, "0%", "0 mos",
#                     total_amount, total_paid, balance, req.status, formatted_date
#                 ])
#                 continue

#             # Loop through individual item components. 
#             # If a request has multiple items, it creates clean separate rows for each item.
#             for d in req.details.all():
#                 if d.item and d.item.received_item:
#                     brand = d.item.received_item.brand or ""
#                     model = d.item.received_item.model_name or "Item"
#                     item_name = f"{brand} {model}".strip()
#                 else:
#                     item_name = "Unknown Item"
                
#                 qty = d.approved_quantity if d.approved_quantity is not None else d.quantity
#                 markup = f"{d.markup_rate}%" if d.markup_rate else "0%"
#                 duration = f"{d.duration_months} mos"

#                 # Append rows mapping exactly to our 12 explicit columns
#                 ws.append([
#                     req.id,
#                     customer_name,
#                     ippis_no,
#                     item_name,       # Column 4
#                     qty,             # Column 5
#                     markup,          # Column 6
#                     duration,        # Column 7
#                     total_amount,
#                     total_paid,
#                     balance,
#                     req.status,
#                     formatted_date
#                 ])
            
#         # Build streaming download configuration wrapper
#         response = HttpResponse(
#             content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
#         )
#         response['Content-Disposition'] = 'attachment; filename="member_requests.xlsx"'
        
#         wb.save(response)
#         return response

#     # Default browser rendering UI pipeline
#     paginator = Paginator(request_list, 50)
#     page_obj = paginator.get_page(request.GET.get('page'))
    
#     context = {
#         'page_obj': page_obj,
#         'search_query': search_query,
#         'status_filter': status_filter,
#         'date_from': date_from,
#         'date_to': date_to,
        
#         "total_amount": total_amount,
#         "pending_amount": pending_amount,
#         "approved_amount": approved_amount,
#         "picked_amount": picked_amount,
#         "declined_amount": declined_amount,
#         "fullypaid_amount": fullypaid_amount,
#     }
#     return render(request, 'inventory_app/member_make_request_list.html', context)



def member_make_request_list(request):
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    request_list = MemberRequest.objects.select_related('member', 'approved_by', 'guarantor').prefetch_related('details__item__received_item','repayments')
    
    if search_query:
        request_list = request_list.filter(
            Q(member__member__first_name__icontains=search_query) |
            Q(member__member__last_name__icontains=search_query) |
            Q(member__ippis__icontains=search_query) |
            Q(guest_name__icontains=search_query) |
            Q(guest_ippis__icontains=search_query)
        )

    if status_filter:
        request_list = request_list.filter(status=status_filter)

    if date_from:
        request_list = request_list.filter(date_created__date__gte=date_from)

    if date_to:
        request_list = request_list.filter(date_created__date__lte=date_to)

    # ======================
    # EXPORT EXCEL (CLEAN CALL)
    # ======================
    if request.GET.get('export') == 'excel':
        return export_member_requests_excel(request_list)

    total_amount = Decimal('0.00')
    pending_amount = Decimal('0.00')
    approved_amount = Decimal('0.00')
    picked_amount = Decimal('0.00')
    declined_amount = Decimal('0.00')
    fullypaid_amount = Decimal('0.00')

    for r in request_list:
        amount = r.calculate_total_price() or Decimal('0.00')

        total_amount += amount

        if r.status == 'Pending':
            pending_amount += amount
        elif r.status == 'Approved':
            approved_amount += amount
        elif r.status == 'ItemPicked':
            picked_amount += amount
        elif r.status == 'Declined':
            declined_amount += amount
        elif r.status == 'Fully Paid':
            fullypaid_amount += amount

    paginator = Paginator(request_list, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,

        "total_amount": total_amount,
        "pending_amount": pending_amount,
        "approved_amount": approved_amount,
        "picked_amount": picked_amount,
        "declined_amount": declined_amount,
        "fullypaid_amount": fullypaid_amount,
    }

    return render(request, 'inventory_app/member_make_request_list.html', context)



def export_member_requests_excel(request_list):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Member Requests"

    headers = [
        "ID", "Member Name", "IPPIS No.",
        "Item Name", "Quantity", "Markup Rate", "Duration (Months)",
        "Total Amount (₦)", "Total Paid (₦)", "Balance (₦)",
        "Status", "Date Created"
    ]
    ws.append(headers)

    for req in request_list:

        if req.member and req.member.member:
            customer_name = f"{req.member.member.first_name} {req.member.member.last_name}"
            ippis_no = req.member.ippis or "N/A"
        else:
            customer_name = req.guest_name or "Unknown Customer"
            ippis_no = req.guest_ippis or "N/A"

        total_amount = req.calculate_total_price()
        total_paid = req.total_paid
        balance = req.balance
        formatted_date = localtime(req.date_created).strftime('%Y-%m-%d %H:%M') if req.date_created else ""

        if not req.details.exists():
            ws.append([
                req.id, customer_name, ippis_no,
                "No Items", 0, "0%", "0 mos",
                total_amount, total_paid, balance,
                req.status, formatted_date
            ])
            continue

        for d in req.details.all():
            if d.item and d.item.received_item:
                brand = d.item.received_item.brand or ""
                model = d.item.received_item.model_name or ""
                item_name = f"{brand} {model}".strip()
            else:
                item_name = "Unknown Item"

            qty = d.approved_quantity or d.quantity
            markup = f"{d.markup_rate}%" if d.markup_rate else "0%"
            duration = f"{d.duration_months} mos"

            ws.append([
                req.id,
                customer_name,
                ippis_no,
                item_name,
                qty,
                markup,
                duration,
                total_amount,
                total_paid,
                balance,
                req.status,
                formatted_date
            ])

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="member_requests.xlsx"'

    wb.save(response)
    return response

@login_required
@group_required(['members','non staff member','admin','loan committee'])
def guarantor_approval_view(request, pk):
    try:
        make_request = get_object_or_404(MemberRequest, pk=pk)
    except MemberRequest.DoesNotExist:
        messages.error(request,'Request do not exist')    

    member = getattr(request.user, 'member', None)
    if not member or make_request.guarantor != member:
        messages.error(request, "You are not authorized to approve this request.")
        return redirect('member_dashboard')

    if make_request.guarantor_accepted:
        messages.info(request, "You have already accepted this  request.")
    else:
        make_request.guarantor_accepted = True
        make_request.save()
        messages.success(request, "You have successfully accepted the guarantee.")

    return redirect('member_dashboard')


@login_required
@group_required(['admin', 'staff','members', 'non staff member','loan committee'])
def make_request_details(request,id):
    member_request = get_object_or_404(MemberRequest.objects.select_related('member', 'approved_by').prefetch_related('details__item__received_item', 'repayments'), id=id)
    context = {'member_request': member_request,'details': member_request.details.all(),}
    return render(request, 'inventory_app/make_request_detail.html', context)
  
    
@login_required
@group_required(['admin'])
def approve_member_request(request, request_id):
    members_request = get_object_or_404(MemberRequest, id=request_id)

    if members_request.guarantor_accepted != True:
        messages.error(request, "Your Guarantor has not accepted your request yet.")
        return redirect('member_make_request_list')

    if members_request.status != "Pending":
        messages.error(request, "Request already approved.")
        return redirect('member_make_request_list')

    if request.method == "POST":
        markup_rate = request.POST.get('markup_rate')

        try:
            markup_rate = Decimal(markup_rate) if markup_rate else None
            if markup_rate is not None and markup_rate < 0:
                raise ValueError
        except (ValueError, InvalidOperation):
            messages.error(request, "Invalid markup rate. Please enter a valid number.")
            return redirect('approve_member_request', request_id=request_id)

        # apply markup to each detail
        for detail in members_request.details.all():
            if markup_rate:
                detail.markup_rate = markup_rate
                multiplier = 1 + (markup_rate / Decimal('100'))
                detail.item_price = (
                    detail.item.selling_price_per_unit * multiplier
                ).quantize(Decimal('0.01'))
                detail.save(update_fields=['markup_rate', 'item_price'])

        # approve the request
        members_request.status = "Approved"
        members_request.approved_by = request.user
        members_request.save(update_fields=['status', 'approved_by'])

        messages.success(request, f"Request approved successfully!{ ' Markup of ' + str(markup_rate) + '% applied.' if markup_rate else ''}")
        return redirect('member_make_request_list')

    return render(request, 'inventory_app/approve_member_request.html', {'members_request': members_request,})

@login_required
@group_required(['admin'])
def decline_member_request(request, request_id):
    member_request = get_object_or_404(MemberRequest, id=request_id)

    if member_request.status != "Pending":
        messages.warning(request, "Request already processed.")
        return redirect("member_make_request_list")

    member_request.status = "Declined"
    member_request.approved_by = request.user
    member_request.save(update_fields=["status", "approved_by"])

    messages.success(request, "Request declined.")
    return redirect("member_make_request_list")

@login_required
@group_required(['admin'])
def mark_item_picked(request, request_id):
   
    member_request = get_object_or_404(MemberRequest, id=request_id)

    if member_request.status != "Approved":
        messages.warning(request, "Request must be approved first.")
        return redirect("member_make_request_list")

    member_request.status = "ItemPicked"
    member_request.save(update_fields=["status"])

    messages.success(request, "Item marked as picked.")
    return redirect("member_make_request_list")





def add_single_member_request_payment(request):
    requests_list = []
    selected_member = None

    ippis = request.GET.get("ippis") or request.POST.get("ippis")

    # -----------------------------
    # FETCH MEMBER + REQUESTS
    # -----------------------------
    if ippis:
        try:
            member_obj = Member.objects.filter(ippis=int(ippis)).first()

            if member_obj:
                selected_member = member_obj

                requests_list = MemberRequest.objects.filter(
                    member=member_obj
                ).exclude(
                    status__in=["Fully Paid", "Declined"]
                )

        except Exception as e:
            messages.error(request, f"Error fetching member: {e}")

    # -----------------------------
    # HANDLE PAYMENT SUBMISSION
    # -----------------------------
    if request.method == "POST":

        amount_paid = request.POST.get("amount_paid")
        month = request.POST.get("month")
        payment_receipt = request.FILES.get("payment_receipt")
        member_request_id = request.POST.get("member_request")

        # -----------------------------
        # VALIDATE REQUIRED FIELDS
        # -----------------------------
        if not (ippis and amount_paid and month and member_request_id):
            messages.error(request, "All fields are required.")
            return redirect(f"{request.path}?ippis={ippis}")

        try:
            amount_paid = Decimal(amount_paid)

            if amount_paid <= 0:
                raise ValueError("Amount must be greater than zero.")

            month_date = datetime.strptime(month, "%Y-%m").date()

            member_request_id = int(member_request_id)

        except (ValueError, TypeError) as e:
            messages.error(request, f"Invalid input: {e}")
            return redirect(f"{request.path}?ippis={ippis}")

        # -----------------------------
        # FETCH MEMBER REQUEST
        # -----------------------------
        member_request = MemberRequest.objects.filter(
            id=member_request_id,
            member=selected_member
        ).first()

        if not member_request:
            messages.error(request, "Selected request not found.")
            return redirect(f"{request.path}?ippis={ippis}")

        # -----------------------------
        # CALCULATE BALANCE
        # -----------------------------
        total_price = member_request.calculate_total_price()
        total_paid = member_request.total_paid
        remaining_balance = total_price - total_paid

        # -----------------------------
        # VALIDATE PAYMENT AMOUNT
        # -----------------------------
        if amount_paid > remaining_balance:
            messages.error(
                request,
                f"Payment exceeds remaining balance of ₦{remaining_balance:,.2f}"
            )
            return redirect(f"{request.path}?ippis={ippis}")

        # -----------------------------
        # CHECK MONTH DUPLICATE PAYMENT
        # -----------------------------
        existing_payment = MemberRequestPayback.objects.filter(
            member_request=member_request,
            repayment_date__year=month_date.year,
            repayment_date__month=month_date.month
        ).exists()

        if existing_payment:
            messages.warning(
                request,
                f"Payment already exists for {month_date.strftime('%B %Y')}."
            )
            return redirect(f"{request.path}?ippis={ippis}")

        # -----------------------------
        # CREATE PAYMENT
        # -----------------------------
        with transaction.atomic():

            MemberRequestPayback.objects.create(
                member_request=member_request,
                amount_paid=amount_paid,
                repayment_date=month_date,
                payment_receipt=payment_receipt,
                created_by=request.user
            )

            # Refresh totals
            member_request.refresh_from_db()

            # Update status if fully paid
            if member_request.total_paid >= member_request.calculate_total_price():

                member_request.status = "Fully Paid"

                member_request.save(update_fields=["status"])

        # -----------------------------
        # SUCCESS MESSAGE
        # -----------------------------
        messages.success(
            request,
            (
                f"Payment of ₦{amount_paid:,.2f} recorded successfully "
                f"for {selected_member} ({ippis})."
            )
        )

        return redirect(f"{request.path}?ippis={ippis}")

    # -----------------------------
    # TEMPLATE
    # -----------------------------
    context = {"requests": requests_list,"selected_member": selected_member,}
    return render(request,"inventory_app/add_single_payment.html",context)

@login_required
@group_required(['admin'])
def upload_payments_excel(request):

    if request.method == "POST" and request.FILES.get("file"):

        file = request.FILES["file"]
        repayment_date_str = request.POST.get("repayment_date", "").strip()

        repayment_date = parse_date(repayment_date_str)
        if not repayment_date:
            messages.error(request, "Invalid or missing repayment date.")
            return redirect("upload_payments_excel")

        try:
            df = pd.read_excel(file)
        except Exception as e:
            messages.error(request, f"Could not read file: {str(e)}")
            return redirect("upload_payments_excel")

        required_columns = {"ippis", "amount"}
        if not required_columns.issubset({col.lower().strip() for col in df.columns}):
            messages.error(request, "Excel file must have 'ippis' and 'amount' columns.")
            return redirect("upload_payments_excel")

        df.columns = [col.lower().strip() for col in df.columns]

        success_count = 0
        errors = []

        for index, row in df.iterrows():
            row_num = index + 2

            # ── Validate IPPIS ────────────────────────────────────────
            raw_ippis = row.get("ippis")
            if pd.isna(raw_ippis):
                errors.append(f"Row {row_num}: Missing IPPIS")
                continue
            ippis = str(raw_ippis).strip()

            # ── Validate amount ───────────────────────────────────────
            try:
                amount = Decimal(str(row["amount"])).quantize(Decimal("0.01"))
            except (InvalidOperation, KeyError):
                errors.append(f"Row {row_num} ({ippis}): Invalid amount")
                continue

            if amount <= 0:
                errors.append(f"Row {row_num} ({ippis}): Amount must be greater than zero")
                continue

            # ── Resolve request (member OR guest) ─────────────────────
            try:
                member_request = None
                request_source = None

                # Priority 1: registered member request
                # FIX: MemberRequest uses `member` FK to Member, not `user`
                try:
                    member = Member.objects.get(ippis=ippis)
                    member_request = MemberRequest.objects.filter(
                        member=member                          # ← was user=member.member
                    ).exclude(status__in=["Declined"]).first()
                    request_source = "member"
                except Member.DoesNotExist:
                    pass

                # Priority 2: guest request matched by guest_ippis
                if not member_request:
                    member_request = MemberRequest.objects.filter(
                        member__isnull=True,                  # ← was user__isnull=True
                        guest_ippis=ippis,
                    ).exclude(status__in=["Declined"]).first()
                    request_source = "guest"

                # RULE 1: No request found at all
                if not member_request:
                    errors.append(
                        f"Row {row_num} ({ippis}): No active request found "
                        f"(checked both member and guest records)"
                    )
                    continue

                # RULE 2: Already fully paid
                if member_request.status == "Fully Paid":
                    errors.append(
                        f"Row {row_num} ({ippis}): Request #{member_request.id} "
                        f"already fully paid [{request_source}]"
                    )
                    continue

                # RULE 3: Double payment in same month
                already_paid_this_month = MemberRequestPayback.objects.filter(
                    member_request=member_request,
                    repayment_date__year=repayment_date.year,
                    repayment_date__month=repayment_date.month,
                ).exists()

                if already_paid_this_month:
                    errors.append(
                        f"Row {row_num} ({ippis}): Payment already recorded for "
                        f"{repayment_date.strftime('%B %Y')} [{request_source}]"
                    )
                    continue

                # RULE 4: Amount exceeds balance
                balance = member_request.balance or Decimal("0.00")
                if amount > balance:
                    errors.append(
                        f"Row {row_num} ({ippis}): "
                        f"Payment ₦{amount} exceeds balance ₦{balance} "
                        f"[{request_source}]"
                    )
                    continue

                # ✅ All checks passed — save payment
                MemberRequestPayback.objects.create(
                    member_request=member_request,
                    amount_paid=amount,
                    repayment_date=repayment_date,
                    created_by=request.user,
                )
                member_request.update_status_based_on_balance()  # auto mark Fully Paid
                success_count += 1

            except Exception as e:
                errors.append(f"Row {row_num} ({ippis}): Unexpected error — {str(e)}")

        # ── Summary ───────────────────────────────────────────────────
        if success_count:
            messages.success(request, f"{success_count} payment(s) uploaded successfully.")
        if errors:
            for error in errors:
                messages.warning(request, error)
        if not success_count and not errors:
            messages.info(request, "No rows found in the uploaded file.")

        return redirect("upload_payments_excel")

    return render(request, "inventory_app/upload_payments_excel.html")



@login_required
@group_required(['admin', 'staff','members', 'non staff member','loan committee'])
def member_request_detail(request, pk):
    req = get_object_or_404(MemberRequest, pk=pk)

    if req.user != request.user and not request.user.is_staff:
        return HttpResponseForbidden("Not allowed")

    context = {
        'request_obj': req,
        'details': req.details.all(),
        'title': f"Request #{req.id}"
    }

    return render(request, 'inventory_app/member_request_detail.html', context)



@login_required
def create_member_request(request):

    # get logged-in member
    try:
        member = Member.objects.get(member=request.user)
    except Member.DoesNotExist:
        messages.error(request, "Member profile not found.")
        return redirect('dashboard')

    items = SellingPlan.objects.filter(
        available=True,
        quantity__gt=0
    ).select_related('received_item')

    if request.method == "POST":

        cart_data = request.POST.get("cart_data", "[]")
        guarantor_ippis = request.POST.get("guarantor_ippis", "").strip()

        try:
            cart_items = json.loads(cart_data)
        except:
            messages.error(request, "Invalid cart data.")
            return redirect("create_member_request")

        if not cart_items:
            messages.error(request, "Cart is empty.")
            return redirect("create_member_request")

        guarantor = None
        if guarantor_ippis:
            try:
                guarantor = Member.objects.get(ippis=guarantor_ippis)
            except Member.DoesNotExist:
                messages.error(request, "Guarantor not found.")
                return redirect("create_member_request")

        try:
            with transaction.atomic():

                member_request = MemberRequest.objects.create(
                    member=member,
                    guarantor=guarantor,
                    file_payslip=request.FILES.get("file_payslip"),
                    passport_photo=request.FILES.get("passport_photo"),
                    status="Pending"
                )

                for item in cart_items:

                    plan = SellingPlan.objects.select_for_update().get(
                        id=item["id"]
                    )

                    qty = int(item["quantity"])

                    if qty <= 0:
                        raise ValueError("Invalid quantity")

                    if qty > plan.quantity:
                        raise ValueError(
                            f"{plan.received_item.brand} not enough stock"
                        )

                    MemberRequestDetail.objects.create(
                        request=member_request,
                        item=plan,
                        quantity=qty,
                        duration_months=1,
                        item_price=plan.selling_price_per_unit,
                    )

                messages.success(request, "Request submitted successfully!")
                return redirect("member_make_request_list")

        except Exception as e:
            messages.error(request, str(e))

    return render(request, "inventory_app/create_member_request.html", {
        "member": member,
        "items": items
    })
@login_required
def my_requests(request):
    requests = MemberRequest.objects.filter(user=request.user).prefetch_related('details')

    return render(request, 'inventory_app/my_requests.html', {
        'requests': requests,
        'title': 'My Requests'
    })
    
    
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum, DecimalField
from django.db.models.functions import Coalesce
from decimal import Decimal

from .models import StockIn, MemberRequest, MemberRequestPayback


@login_required
def inventory_report(request):

    # ── STOCK IN ──────────────────────────────────────────────────────────────
    stock_qs = (
        StockIn.objects
        .select_related('supplier', 'received_by')
        .prefetch_related('items__stockreturn_set')
        .order_by('-received_at')
    )

    # ── MEMBER REQUESTS ───────────────────────────────────────────────────────
    requests_qs = (
        MemberRequest.objects
        .select_related('member', 'approved_by')
        .prefetch_related('details__item', 'repayments')
        .annotate(
            annotated_total_paid=Coalesce(
                Sum('repayments__amount_paid'),
                Decimal('0.00'),
                output_field=DecimalField()
            )
        )
        .order_by('-date_created')
    )

    # ── REPAYMENTS ────────────────────────────────────────────────────────────
    repayments_qs = (
        MemberRequestPayback.objects
        .select_related('member_request__member', 'created_by')
        .order_by('-repayment_date')
    )

    # ── SUMMARY METRICS (run on full querysets BEFORE paginating) ─────────────
    total_repaid = MemberRequestPayback.objects.aggregate(
        total=Coalesce(Sum('amount_paid'), Decimal('0.00'))
    )['total']

    # These still need Python loops because they rely on model properties.
    # They run once on the full qs before pagination slices it.
    all_requests      = list(requests_qs)
    total_requested   = sum(r.calculate_total_price() for r in all_requests)
    total_outstanding = sum(r.balance for r in all_requests)
    fully_paid_count  = sum(1 for r in all_requests if r.status == 'Fully Paid')

    all_stock        = list(stock_qs)
    total_stock_cost = sum(s.get_total_cost for s in all_stock)
    total_stock_net  = sum(s.net_voucher_value for s in all_stock)

    # ── PAGINATION ────────────────────────────────────────────────────────────
    # Each tab has its own page parameter so switching tabs keeps its position.
    stock_page   = request.GET.get('stock_page', 1)
    req_page     = request.GET.get('req_page', 1)
    repay_page   = request.GET.get('repay_page', 1)

    stock_paginator      = Paginator(all_stock,              25)
    requests_paginator   = Paginator(all_requests,           25)
    repayments_paginator = Paginator(list(repayments_qs),    25)

    stock_ins       = stock_paginator.get_page(stock_page)
    member_requests = requests_paginator.get_page(req_page)
    repayments      = repayments_paginator.get_page(repay_page)

    context = {
        'stock_ins':         stock_ins,
        'member_requests':   member_requests,
        'repayments':        repayments,
        'total_stock_cost':  total_stock_cost,
        'total_stock_net':   total_stock_net,
        'total_requested':   total_requested,
        'total_repaid':      total_repaid,
        'total_outstanding': total_outstanding,
        'fully_paid_count':  fully_paid_count,
    }
    return render(request, 'inventory_app/report.html', context)    