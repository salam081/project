# views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from accounts.decorators import group_required
from django.forms import inlineformset_factory
from django.utils.dateparse import parse_date
import pandas as pd
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from decimal import Decimal, InvalidOperation
from django.http import HttpResponseForbidden, JsonResponse, HttpResponseRedirect
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from .models import *
from accounts.models import *
from .forms import StockInForm, ReceivedItemFormSet




def inventory_home(request):
    supplies = (
        StockIn.objects
        .select_related('supplier')
        .prefetch_related('items__stockreturn_set')
        .order_by('-received_at')[:5]
    )

    product_count = ReceivedItem.objects.count()

    # prefetch returns once for all value calculations
    all_items = ReceivedItem.objects.prefetch_related('stockreturn_set')

    gross_stock_value    = sum(item.total_price     for item in all_items)
    net_stock_value      = sum(item.net_stock_value for item in all_items)
    total_returned_value = gross_stock_value - net_stock_value

    context = {
        'supplies':supplies,
        'product_count':product_count,
        'gross_stock_value':gross_stock_value,
        'net_stock_value':net_stock_value,
        'total_returned_value':total_returned_value,
    }
    return render(request, 'inventory_app/inventory_home.html', context)


@login_required
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


def product_list_view(request):
    products = (
        ReceivedItem.objects
        .select_related('stock_in__supplier')
        .prefetch_related('stockreturn_set')
    )
    context = {'products': products}
    return render(request, 'inventory_app/product_list.html', context)


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
def receive_item_selling_plan_detail(request, id):
    plan = get_object_or_404( SellingPlan.objects.select_related('received_item', 'created_by'),id=id)
    context = {'plan':plan,'received_item': plan.received_item,'title':'Selling Plan Detail'}
    return render(request, 'inventory_app/receive_item_selling_plan_detail.html', context)


@login_required
def member_make_request(request):
    items = SellingPlan.objects.filter(available=True).select_related('received_item')
    member_info = None
    # views.py — fix the prefetch depth
    requests_qs = MemberRequest.objects.select_related(
        'user', 'approved_by'
    ).prefetch_related(
        'details__item__received_item',  
        'repayments',                   
    )
    paginator = Paginator(requests_qs, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

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
            file_payslip = request.FILES.get('file_payslip')
            passport_photo = request.FILES.get('passport_photo')
            gaurantor_ippis = request.POST.get("gaurantor_ippis", "").strip()

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
                    messages.error(
                        request,
                        f"Quantity exceeds available stock ({item_plan.quantity})."
                    )
                    return redirect('member_make_request')

                member_request = MemberRequest.objects.create(user=member.member,gaurantor_ippis=gaurantor_ippis,file_payslip=file_payslip,passport_photo=passport_photo)

               
                MemberRequestDetail.objects.create(
                    request=member_request,
                    item=item_plan,
                    quantity=quantity,
                    item_price=item_plan.selling_price_per_unit,
                )

                messages.success(request, "Request created successfully!")
                return redirect('member_make_request')

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
            gaurantor_ippis = request.POST.get("gaurantor_ippis", "").strip()
            item_id = request.POST.get('item_id')
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
                messages.error(
                    request,
                    f"Quantity exceeds available stock ({item_plan.quantity})."
                )
                return redirect('member_make_request')

            try:
                guest_request = MemberRequest.objects.create(
                    guest_name=guest_name,
                    guest_ippis=guest_ippis,
                    guest_phone=guest_phone,
                    gaurantor_ippis=gaurantor_ippis,
                    file_payslip=file_payslip,
                    passport_photo=passport_photo,
                )

                MemberRequestDetail.objects.create(
                    request=guest_request,
                    item=item_plan,
                    quantity=quantity,
                    item_price=item_plan.selling_price_per_unit,
                )

                messages.success(request, "Guest request created successfully!")
                return redirect('member_make_request')

            except Exception as e:
                messages.error(request, str(e))

    context = {"member_info": member_info,"items": items,"page_obj": page_obj,}
    return render(request, 'inventory_app/member_make_request.html', context)


def make_request_details(request,id):
    member_request = get_object_or_404(MemberRequest.objects.select_related('user', 'approved_by').prefetch_related('details__item__received_item', 'repayments'), id=id)
    context = {'member_request': member_request,'details': member_request.details.all(),}
    return render(request, 'inventory_app/make_request_detail.html', context)
    
def approve_member_request(request, request_id):
    members_request = get_object_or_404(MemberRequest, id=request_id)
    
    if members_request.status != "Pending":
        messages.error(request, " Request  already approved.")
        return redirect('member_make_request')
    
    # Approved Status
    members_request.status = "Approved"
    members_request.approved_by = request.user
    members_request.save(update_fields=['status', 'approved_by'])
    messages.success(request, "Request approved successfully!")
    return redirect('member_make_request')


def decline_member_request(request, request_id):
    member_request = get_object_or_404(MemberRequest, id=request_id)

    if member_request.status != "Pending":
        messages.warning(request, "Request already processed.")
        return redirect("member_make_request")

    member_request.status = "Declined"
    member_request.approved_by = request.user
    member_request.save(update_fields=["status", "approved_by"])

    messages.success(request, "Request declined.")
    return redirect("member_make_request")

def mark_item_picked(request, request_id):
    if not request.user.is_staff:
        messages.error(request, "Permission denied.")
        return redirect("member_make_request")

    member_request = get_object_or_404(MemberRequest, id=request_id)

    if member_request.status != "Approved":
        messages.warning(request, "Request must be approved first.")
        return redirect("member_make_request")

    member_request.status = "ItemPicked"
    member_request.save(update_fields=["status"])

    messages.success(request, "Item marked as picked.")
    return redirect("member_make_request")



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
                request_source = None  # for clear error messages

                # Priority 1: registered member request
                try:
                    member = Member.objects.get(ippis=ippis)
                    member_request = MemberRequest.objects.filter(
                        user=member.member
                    ).exclude(status__in=["Declined"]).first()
                    request_source = "member"
                except Member.DoesNotExist:
                    pass  # not a registered member, try guest below

                # Priority 2: guest request matched by guest_ippis
                if not member_request:
                    member_request = MemberRequest.objects.filter(
                        user__isnull=True,
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
                        f"{repayment_date.strftime('%B %Y')} "
                        f"[{request_source}]"
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

# views.py
@login_required
def create_member_request(request):
    MemberRequestFormSet = inlineformset_factory(
        MemberRequest,
        MemberRequestDetail,
        fields=('item', 'quantity'),
        extra=0, # Start empty
        can_delete=True
    )

    if request.method == 'POST':
        formset = MemberRequestFormSet(request.POST, request.FILES)
        if formset.is_valid():
            try:
                with transaction.atomic():
                    # Create parent
                    member_request = MemberRequest.objects.create(
                        user=request.user,
                        gaurantor_ippis=request.POST.get('gaurantor_ippis'),
                        file_payslip=request.FILES.get('file_payslip'),
                        passport_photo=request.FILES.get('passport_photo')
                    )
                    # Save details
                    instances = formset.save(commit=False)
                    for instance in instances:
                        instance.request = member_request
                        instance.save()
                    
                    messages.success(request, "Request submitted!")
                    return redirect('create_member_request')
            except Exception as e:
                messages.error(request, f"Error: {e}")
    else:
        formset = MemberRequestFormSet()

    return render(request, 'inventory_app/create_member_request.html', {
        'formset': formset,
        'items': ReceivedItem.objects.filter(quantity__gt=0)
    })
from django.shortcuts import get_object_or_404

@login_required
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
def my_requests(request):
    requests = MemberRequest.objects.filter(user=request.user).prefetch_related('details')

    return render(request, 'inventory_app/my_requests.html', {
        'requests': requests,
        'title': 'My Requests'
    })