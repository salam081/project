from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum, F
from django.db.models import Sum, F, DecimalField
from django.db.models.functions import Coalesce
import json
from decimal import Decimal
from django.http import HttpResponseForbidden, JsonResponse, HttpResponseRedirect
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from .forms import *
from .models import *
from accounts.models import *
from consumable.models import *
from main.models import *
from member.models import *
from .models import *
from accounts.views import *





@login_required
def purchase_consumable_dashboard(request):
    
    # Summary statistics
    total_requests = ConsumablePurchasedRequest.objects.count()
    pending_requests = ConsumablePurchasedRequest.objects.filter(
        status=ConsumablePurchasedRequest.STATUS_PENDING
    ).count()
    approved_requests = ConsumablePurchasedRequest.objects.filter(
        status=ConsumablePurchasedRequest.STATUS_APPROVED
    ).count()
    
    total_spent = PurchasedItem.objects.aggregate(
        total=Sum(F('quantity') * F('unit_price') + F('expenditure_amount'))
    )['total'] or Decimal('0')
    
    total_planned_revenue = SellingPlan.objects.filter(available=True).aggregate(
        total=Sum(F('selling_price_per_unit') * F('quantity'))
    )['total'] or Decimal('0')
    print("total_planned_revenue",total_planned_revenue)

    total_planned_profit = SellingPlan.objects.filter(available=True).aggregate(
        total=Sum('profit')
    )['total'] or Decimal('0')
    # print("total_planned_profit",total_planned_profit)

    # Recent activity
    recent_requests = ConsumablePurchasedRequest.objects.select_related('requested_by')[:5]
    recent_items = PurchasedItem.objects.select_related('consumable_purchased_request')[:5]
    recent_plans = SellingPlan.objects.select_related('purchased_item', 'created_by')[:5]
    
    context = {
        'total_requests': total_requests,
        'pending_requests': pending_requests,
        'approved_requests': approved_requests,
        'total_spent': total_spent,
        'total_planned_revenue': total_planned_revenue,
        'total_planned_profit': total_planned_profit,
        'recent_requests': recent_requests,
        'recent_items': recent_items,
        'recent_plans': recent_plans,
    }
    return render(request, 'purchaseitem/purchase_dashboard.html', context)

# ============== CONSUMABLE PURCHASE REQUEST VIEWS ==============

@login_required
def consumable_purchase_request_list(request):
    """List all consumable requests with filtering and pagination"""
    requests = ConsumablePurchasedRequest.objects.all().order_by('-date_requested')
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        requests = requests.filter(status=status_filter)
    
    # Filter by user (for non-staff users, show only their requests)
    if not request.user.is_staff :
        requests = requests.filter(requested_by=request.user)
    
    # Search functionality
    search_query = request.GET.get('search')
    if search_query:
        requests = requests.filter(
            Q(purpose__icontains=search_query) |
            Q(requested_by__username__icontains=search_query) |
            Q(remarks__icontains=search_query)
        )
    # Pagination
    paginator = Paginator(requests, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {'page_obj': page_obj,
        'status_choices': ConsumablePurchasedRequest.STATUS_CHOICES,
        'current_status': status_filter,'search_query': search_query,}
    return render(request, 'purchaseitem/purchase_request_list.html', context)


@login_required
def consumable_purchase_review(request, pk):
    """Review consumable purchase request before approval"""
    consumable_request = get_object_or_404(ConsumablePurchasedRequest, pk=pk)

    if request.method == "POST":
        comment = request.POST.get("comment", "").strip()
        try:
            consumable_request.review(request.user, comment)
            messages.success(request, "Request reviewed successfully! It is now ready for approval.")
            return redirect("purchase_consumable_dashboard")
        except ValidationError as e:
            messages.error(request, str(e))

    context = {
        "consumable_request": consumable_request,
    }
    return render(request, "purchaseitem/purchase_request_review.html", context)


@login_required
def consumable_purchase_request_detail(request, pk):
    consumable_request = get_object_or_404(ConsumablePurchasedRequest, pk=pk)
    
    # Calculate correct total including expenditure
    total_spent_correct = consumable_request.items.aggregate(
        total=Coalesce(
            Sum(
                F('quantity') * F('unit_price') + F('expenditure_amount'), 
                output_field=DecimalField()
            ),
            Decimal('0')
        )
    )['total']
    
    context = {
        'consumable_request': consumable_request,
        'total_spent_correct': total_spent_correct,
    }
    return render(request, 'purchaseitem/purchase_request_detail.html', context)


@login_required
def consumable_purchase_request_create(request):
    if request.method == 'POST':
        try:
            consumable_request = ConsumablePurchasedRequest(
                requested_by=request.user,
                item=request.POST.get('item', '').strip(),
                purpose=request.POST.get('purpose', '').strip(),
                amount_requested=Decimal(request.POST.get('amount_requested', '0')),
                remarks=request.POST.get('remarks', '').strip()
            )
            consumable_request.full_clean()
            consumable_request.save()
            
            messages.success(request, 'Consumable purchase request created successfully!')
            return redirect('consumable_purchase_request_detail', pk=consumable_request.pk)
            
        except (ValueError, ValidationError) as e:
            messages.error(request, f'Error creating request: {str(e)}')

    return render(request, 'purchaseitem/purchase_item_form.html', { 'title': 'Create New Consumable Request'})


@login_required
def consumable_request_edit(request, pk):
    """Edit existing consumable purchase request"""
    consumable_request = get_object_or_404(ConsumablePurchasedRequest, pk=pk)
    
    if not consumable_request.can_be_modified():
        messages.error(request, 'This request cannot be modified.')
        return redirect('consumable_request_detail', pk=pk)
    
    if request.method == 'POST':
        try:
            consumable_request.item = request.POST.get('item', '').strip()
            consumable_request.purpose = request.POST.get('purpose', '').strip()
            consumable_request.amount_requested = Decimal(request.POST.get('amount_requested', '0'))
            consumable_request.remarks = request.POST.get('remarks', '').strip()
            
            consumable_request.full_clean()
            consumable_request.save()
            
            messages.success(request, 'Request updated successfully!')
            return redirect('consumable_request_detail', pk=pk)
            
        except (ValueError, ValidationError) as e:
            messages.error(request, f'Error updating request: {str(e)}')
    
    context = {
        'consumable_request': consumable_request,
        'title': 'Edit Consumable Request'
    }
    return render(request, 'purchaseitem/request_form.html', context)


@login_required
def consumable_purchase_approve(request, pk):
    """Approve consumable purchase request"""
    consumable_request = get_object_or_404(ConsumablePurchasedRequest, pk=pk)
    
    if request.method == 'POST':
        try:
            approved_amount = Decimal(request.POST.get('approved_amount', '0'))
            consumable_request.approve(approved_amount, request.user)
            
            messages.success(request, 'Request approved successfully!')
            return redirect('consumable_purchase_request_detail', pk=pk)
            
        except (ValueError, ValidationError) as e:
            messages.error(request, f'Error approving request: {str(e)}')
    
    context = {
        'consumable_request': consumable_request,
    }
    return render(request, 'purchaseitem/purchase_request_approve.html', context)


# @login_required
# def consumable_request_mark_accounted(request, pk):
#     """Mark consumable request as fully accounted"""
#     consumable_request = get_object_or_404(ConsumablePurchasedRequest, pk=pk)
    
#     if request.method == 'POST':
#         try:
#             consumable_request.mark_as_accounted()
#             messages.success(request, 'Request marked as fully accounted!')
#             return redirect('consumable_request_detail', pk=pk)
            
#         except ValidationError as e:
#             messages.error(request, f'Error: {str(e)}')
    
#     return redirect('consumable_request_detail', pk=pk)

login_required
def consumable_request_mark_accounted(request, pk):
    consumable_request = get_object_or_404(ConsumablePurchasedRequest, pk=pk)

    if not (hasattr(request.user, "group") and request.user.group and request.user.group.title == 'admin') \
       and consumable_request.requested_by != request.user:
        messages.error(request, "You don't have permission to modify this request.")
        return redirect('consumable_purchase_request_detail', pk=pk)

    if consumable_request.status != 'approved':
        messages.error(request, "Request must be approved before marking as accounted.")
        return redirect('consumable_purchase_request_detail', pk=pk)

    if request.method == 'POST':
        # set approved_amount to total spent and mark accounted
        total_spent = consumable_request.total_spent() or Decimal('0.00')
        consumable_request.approved_amount = total_spent
        consumable_request.status = 'accounted'
        consumable_request.remarks = (consumable_request.remarks or '') + f"\n\nAccounted on {timezone.now().date()}"
        consumable_request.save()
        messages.success(request, 'Consumable request marked as fully accounted!')
        return redirect('consumable_purchase_request_detail', pk=pk)

    return render(request, 'purchaseitem/purchase_request_mark_accounted.html', {'consumable_request': consumable_request})


@login_required
@transaction.atomic
def refund_and_account_request(request, pk):
    request_obj = get_object_or_404(ConsumablePurchasedRequest, pk=pk)

    if not (hasattr(request.user, "group") and request.user.group and request.user.group.title in ('admin', 'staff')) \
       and request_obj.requested_by != request.user:
        messages.error(request, "You are not authorized to perform this action.")
        return redirect('consumable_purchase_request_detail', pk=pk)

    if request_obj.status != 'approved':
        messages.warning(request, "This request is not in the 'Approved' state and cannot be accounted for.")
        return redirect('consumable_purchase_request_detail', pk=pk)

    # total spent using PurchasedItem totals
    total_spent = request_obj.total_spent() or Decimal('0.00')

    # If spent >= approved_amount, nothing to refund
    if request_obj.approved_amount is not None and total_spent >= request_obj.approved_amount:
        messages.warning(request, "No balance to refund. The spent amount is greater than or equal to the approved amount.")
        return redirect('consumable_purchase_request_detail', pk=pk)

    # Update request as accounted and set approved_amount = actual spent
    request_obj.approved_amount = total_spent
    request_obj.status = 'accounted'
    request_obj.remarks = (request_obj.remarks or '') + f"\n\n- Member refunded the balance. Approved amount updated to ₦{total_spent:.2f}."
    request_obj.save()

    messages.success(request, f"Request successfully accounted for. Approved amount changed to ₦{total_spent:.2f}.")
    return redirect('consumable_purchase_request_detail', pk=pk)


# ============== PURCHASED ITEM VIEWS ==============
@login_required
def purchased_item_create(request, request_pk):
    """Add new purchased item to a request"""
    consumable_request = get_object_or_404(ConsumablePurchasedRequest, pk=request_pk)
    
    if request.method == 'POST':
        try:
            quantity = int(request.POST.get('quantity', 0))
            unit_price = Decimal(request.POST.get('unit_price', '0'))
            expenditure_amount = Decimal(request.POST.get('expenditure_amount', '0'))
            
            # Calculate total cost for validation
            item_total = (quantity * unit_price) + expenditure_amount
            
            # Check if item can be added
            can_add, message = consumable_request.can_add_item(item_total)
            if not can_add:
                messages.error(request, message)
                return render(request, 'purchaseitem/create_purchased_item_form.html', {
                    'consumable_request': consumable_request,
                    'title': 'Add Purchased Item'
                })
            
            item = PurchasedItem(
                consumable_purchased_request=consumable_request,
                item_name=request.POST.get('item_name', '').strip(),
                description=request.POST.get('description', '').strip(),
                quantity=quantity,
                unit_price=unit_price,
                created_by = request.user,#now
                expenditure_amount=expenditure_amount,
                receipt=request.FILES.get('receipt')
            )
            item.full_clean()
            item.save()
            
            messages.success(request, 'Purchased item added successfully!')
            # return redirect('consumable_purchase_request_detail', pk=request_pk)
            return redirect('purchased_item_list') #now
            
        except (ValueError, ValidationError) as e:
            messages.error(request, f'Error adding item: {str(e)}')
    
    context = {
        'consumable_request': consumable_request,
        'title': 'Add Purchased Item'
    }
    return render(request, 'purchaseitem/create_purchased_item_form.html', context)


@login_required
def purchased_item_list(request):
    """List all purchased items"""
    items = PurchasedItem.objects.select_related('consumable_purchased_request')
    
    # Filtering
    search_query = request.GET.get('search')
    if search_query:
        items = items.filter(
            Q(item_name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    request_id = request.GET.get('request_id')
    if request_id:
        items = items.filter(consumable_purchased_request_id=request_id)
    
    # Pagination
    paginator = Paginator(items, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'request_id': request_id,
    }
    return render(request, 'purchaseitem/purchased_item_list.html', context)


@login_required
def purchased_item_detail(request, pk):
    """Detail view for purchased item"""
    item = get_object_or_404(PurchasedItem, pk=pk)
    adjustments = item.adjustments.all()
    context = {'item': item,'adjustments': adjustments,}
    return render(request, 'purchaseitem/purchased_item_detail.html', context)

@login_required
def purchased_item_edit(request, pk):
    """Edit purchased item"""
    item = get_object_or_404(PurchasedItem, pk=pk)
    if request.user != item.created_by and request.user.group.title != 'admin':
        return HttpResponseForbidden("You don't have permission to Edit this item.")
    
    if request.method == 'POST':
        try:
            # Store old price for adjustment tracking
            old_price = item.unit_price
            
            item.item_name = request.POST.get('item_name', '').strip()
            item.description = request.POST.get('description', '').strip()
            item.quantity = int(request.POST.get('quantity', 0))
            item.unit_price = Decimal(request.POST.get('unit_price', '0'))
            item.expenditure_amount = Decimal(request.POST.get('expenditure_amount', '0'))
            
            if request.FILES.get('receipt'):
                item.receipt = request.FILES.get('receipt')
            
            item.full_clean()
            item.save()
            
            # Create adjustment record if price changed
            new_price = item.unit_price
            if old_price != new_price:
                PurchasedItemAdjustment.objects.create(
                    purchased_item=item,
                    old_price=old_price,
                    new_price=new_price,
                    reason=request.POST.get('adjustment_reason', ''),
                    adjusted_by=request.user
                )
            
            messages.success(request, 'Purchased item updated successfully!')
            return redirect('purchased_item_detail', pk=pk)
            
        except (ValueError, ValidationError) as e:
            messages.error(request, f'Error updating item: {str(e)}')
    
    context = {'item': item,'title': 'Edit Purchased Item'}
    return render(request, 'purchaseitem/purchased_edit_item_form.html', context)


@login_required
def purchased_item_delete(request, pk):
    """Delete purchased item"""
    item = get_object_or_404(PurchasedItem, pk=pk)
    if request.user != item.created_by and getattr(request.user.group, 'title', '') != 'admin':
        return HttpResponseForbidden("You don't have permission to delete this item.")

    request_pk = item.consumable_purchased_request.pk
    
    if request.method == 'POST':
        item.delete()
        messages.success(request, 'Purchased item deleted successfully!')
        return redirect('purchased_item_list')
    
    context = {'item': item,}
    return render(request, 'purchaseitem/purchased_item_confirm_delete.html', context)


# ============== SELLING PLAN VIEWS ==============

@login_required
def selling_plan_create(request, item_pk):
    """Create selling plan for purchased item"""
    purchased_item = get_object_or_404(PurchasedItem, pk=item_pk)
    if request.user != purchased_item.created_by and getattr(request.user.group, 'title', '') != 'admin':
        return HttpResponseForbidden("You don't have permission to Create this item.")

    # Check if selling plan already exists
    if hasattr(purchased_item, 'selling_plan'):
        messages.error(request, 'Selling plan already exists for this item.')
        return redirect('selling_plan_detail', pk=purchased_item.selling_plan.pk)
    
    if request.method == 'POST':
        try:
            plan = SellingPlan(
                purchased_item=purchased_item,
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
            return redirect('selling_plan_detail', pk=plan.pk)
            
        except (ValueError, ValidationError) as e:
            messages.error(request, f'Error creating selling plan: {str(e)}')
    
    context = {
        'purchased_item': purchased_item,
        'title': 'Create Selling Plan'
    }
    return render(request, 'purchaseitem/selling_plan_form.html', context)

@login_required
def selling_plan_list(request):
    plans = SellingPlan.objects.select_related('purchased_item', 'created_by')
    
    # Filtering
    search_query = request.GET.get('search')
    if search_query:
        plans = plans.filter(
            Q(purchased_item__item_name__icontains=search_query) |
            Q(notes__icontains=search_query)
        )
    
    available_only = request.GET.get('available_only')
    if available_only:
        plans = plans.filter(available=True)
    
    # Pagination
    paginator = Paginator(plans, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {'page_obj': page_obj,'search_query': search_query,'available_only': available_only,}
    return render(request, 'purchaseitem/selling_plan_list.html', context)

@login_required
def selling_plan_detail(request, pk):
    selling_plan = get_object_or_404(SellingPlan, pk=pk)
    context = {
        'plan': selling_plan,  # Template uses 'plan' variable
        'selling_plan': selling_plan,  # Keep this for the edit/delete buttons
    }
    return render(request, 'purchaseitem/selling_plan_detail.html', context)


@login_required
def selling_plan_edit(request, pk):
    """Edit selling plan"""
    plan = get_object_or_404(SellingPlan, pk=pk)
    if request.user != plan.created_by and request.user.group.title != 'admin':
        return HttpResponseForbidden("You don't have permission to edit this plan.")
    
    if request.method == 'POST':
        try:
            # Store old price for adjustment tracking
            old_price = plan.selling_price_per_unit
            
            plan.selling_price_per_unit = Decimal(request.POST.get('selling_price_per_unit', '0'))
            plan.quantity = int(request.POST.get('quantity', 0))
            plan.notes = request.POST.get('notes', '').strip()
            plan.available = request.POST.get('available') == 'on'
            plan.include_expenditure = request.POST.get('include_expenditure') == 'on'
            
            plan.full_clean()
            plan.save()
            plan.update_profit()
            
            # Create adjustment record if price changed
            new_price = plan.selling_price_per_unit
            if old_price != new_price:
                SellingPlanAdjustment.objects.create(
                    selling_plan=plan,old_price=old_price,new_price=new_price,
                    reason=request.POST.get('adjustment_reason', ''),
                    adjusted_by=request.user)
            
            messages.success(request, 'Selling plan updated successfully!')
            return redirect('selling_plan_detail', pk=pk)
            
        except (ValueError, ValidationError) as e:
            messages.error(request, f'Error updating selling plan: {str(e)}')
    
    context = {'plan': plan,'title': 'Edit Selling Plan'}
    return render(request, 'purchaseitem/selling_plan_edit_form.html', context)


@login_required
def selling_plan_delete(request, pk):
    """Delete selling plan"""
    plan = get_object_or_404(SellingPlan, pk=pk)
    if request.user != plan.created_by and request.user.group.title != 'admin':
        return HttpResponseForbidden("You don't have permission to Delete this plan.")
    
    if request.method == 'POST':
        plan.delete()
        messages.success(request, 'Selling plan deleted successfully!')
        return redirect('selling_plan_list')
    
    context = {
        'plan': plan,
    }
    return render(request, 'purchaseitem/selling_plan_confirm_delete.html', context)


# ============== AJAX VIEWS ==============

@login_required
@require_http_methods(["GET"])
def get_request_balance(request, pk):
    """AJAX view to get remaining balance for a request"""
    try:
        consumable_request = get_object_or_404(ConsumablePurchasedRequest, pk=pk)
        balance = consumable_request.balance_remaining()
        
        return JsonResponse({
            'success': True,
            'balance': str(balance) if balance else None,
            'total_spent': str(consumable_request.total_spent()),
            'approved_amount': str(consumable_request.approved_amount) if consumable_request.approved_amount else None
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_http_methods(["POST"])
def calculate_item_total(request):
    """AJAX view to calculate item total cost"""
    try:
        data = json.loads(request.body)
        quantity = int(data.get('quantity', 0))
        unit_price = Decimal(data.get('unit_price', '0'))
        expenditure = Decimal(data.get('expenditure_amount', '0'))
        
        total = (quantity * unit_price) + expenditure
        
        return JsonResponse({
            'success': True,
            'total': str(total)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_http_methods(["POST"])
def calculate_selling_profit(request):
    """AJAX view to calculate selling profit"""
    try:
        data = json.loads(request.body)
        selling_price = Decimal(data.get('selling_price', '0'))
        quantity = int(data.get('quantity', 0))
        cost_per_unit = Decimal(data.get('cost_per_unit', '0'))
        
        total_revenue = selling_price * quantity
        total_cost = cost_per_unit * quantity
        profit = total_revenue - total_cost
        
        return JsonResponse({
            'success': True,
            'total_revenue': str(total_revenue),
            'total_cost': str(total_cost),
            'profit': str(profit)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


# ============== DASHBOARD VIEWS ==============

