import calendar
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum,Min, Max, Count, Q, Avg , F, Case, When ,ExpressionWrapper, DecimalField
from django.db.models.functions import Coalesce
from django.db.models.functions import TruncMonth, TruncYear,TruncWeek
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.core.paginator import Paginator
from datetime import datetime, timedelta
from collections import defaultdict
from django.db.models.functions import ExtractYear
from django.db.models.functions import ExtractMonth
from django.db import transaction
from decimal import Decimal
from django.contrib import messages
import json
import logging
from consumable.models import *
from accounts.models import User
import csv
from loan.models import *
from savings.models import *
from main.models import *
from PurchasedItems.models import *
from member.models import *
from projectfinance.models import *
# from accounts.decorator import group_required

from datetime import date


@login_required
def all_income(request):
    """
    Calculates and displays all sources of income based on user-selected date filters.
    Requires the user to be logged in to view.
    """
    # Get filter parameters from GET request
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    # Build Q objects for filtering
    savings_filter = Q()
    loanrepayback_filter = Q()
    consumable_payback_filter = Q()
    loan_fee_filter = Q()
    interest_filter = Q()
    item_purchase_filter = Q()
    total_consumable_form_fee_filter = Q()

    # Filter by date range
    if date_from:
        savings_filter &= Q(month__gte=date_from)
        loanrepayback_filter &= Q(repayment_date__gte=date_from)
        consumable_payback_filter &= Q(repayment_date__gte=date_from)
        loan_fee_filter &= Q(created_at__gte=date_from)
        interest_filter &= Q(month__gte=date_from)
        item_purchase_filter &= Q(date_created__gte=date_from)  # Use 'date_created' for filtering
        total_consumable_form_fee_filter &= Q(created_at__gte=date_from)

    if date_to:
        savings_filter &= Q(month__lte=date_to)
        loanrepayback_filter &= Q(repayment_date__lte=date_to)
        consumable_payback_filter &= Q(repayment_date__lte=date_to)
        loan_fee_filter &= Q(created_at__lte=date_to)
        interest_filter &= Q(month__lte=date_to)
        item_purchase_filter &= Q(date_created__lte=date_to)  # Use 'date_created' for filtering
        total_consumable_form_fee_filter &= Q(created_at__lte=date_to)

    # Aggregations with filters
    total_loans_fee = LoanRequestFee.objects.filter(loan_fee_filter).aggregate(total=Sum('form_fee'))['total'] or 0
    total_consumable_form_fee = ConsumableFormFee.objects.filter(total_consumable_form_fee_filter).aggregate(total=Sum('form_fee'))['total'] or 0
    total_savings = Savings.objects.filter(savings_filter).aggregate(total_savings=Sum('month_saving'))['total_savings'] or 0
    deducted_amount = Interest.objects.filter(interest_filter).aggregate(total_savings=Sum('amount_deducted'))['total_savings'] or 0
    payback_loans = LoanRepayback.objects.filter(loanrepayback_filter).aggregate(total=Sum('amount_paid'))['total'] or 0
    total_consumable_payback = PaybackConsumable.objects.filter(consumable_payback_filter).aggregate(total=Sum('amount_paid'))['total'] or 0

    # CORRECTED: Use 'expenditure_amount' instead of 'total_price' and filter by 'date_added'
    total_item_purchase = SellingPlan.objects.filter(item_purchase_filter).aggregate(total=Sum('profit'))['total'] or 0
    
    # Calculate total income
    income = sum([total_loans_fee, total_savings, deducted_amount, payback_loans, total_consumable_payback, total_consumable_form_fee, total_item_purchase])

    filters_applied = any([date_from, date_to])
    context = {
        'total_loans_fee': total_loans_fee,
        'total_consumable_form_fee': total_consumable_form_fee,
        'total_savings': total_savings,
        'payback_loans': payback_loans,
        'deducted_amount': deducted_amount,
        'total_consumable_payback': total_consumable_payback,
        'income': income,
        'date_from': date_from,
        'date_to': date_to,
        'filters_applied': filters_applied,
        'total_item_purchase': total_item_purchase
    }
    return render(request, "reports/all_income.html", context)

@login_required 
def summary_view(request):
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

    # Use .all() or apply necessary filters to base querysets
    savings_monthly = format_months(get_monthly_totals(Savings.objects.all(), "month_saving"))
    interest_monthly = format_months(get_monthly_totals(Interest.objects.all(), "amount_deducted"))
    loanable_monthly = format_months(get_monthly_totals(Loanable.objects.all(), "amount"))
    investment_monthly = format_months(get_monthly_totals(Investment.objects.all(), "amount"))

    # Paginate the lists
    def paginate_data(data, page_size=12):
        paginator = Paginator(data, page_size)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        return page_obj

    savings_page = paginate_data(savings_monthly)
    interest_page = paginate_data(interest_monthly)
    loanable_page = paginate_data(loanable_monthly)
    investment_page = paginate_data(investment_monthly)

    # Total calculations (no pagination here, just sums)
    total_savings = Decimal(sum(item["total"] for item in savings_monthly))
    total_interest = Decimal(sum(item["total"] for item in interest_monthly))
    total_loanable = Decimal(sum(item["total"] for item in loanable_monthly))
    total_investment = Decimal(sum(item["total"] for item in investment_monthly))
    grand_total = total_savings + total_interest #+ total_loanable + total_investment
    # --- Existing Per-member totals ---
    member_savings = Member.objects.annotate(
        aggregated_savings=Sum('savings__month_saving', default=Decimal('0.00'))
    ).order_by('-aggregated_savings')
    
    # Optimized member interest fetching slightly
    member_interest_data = Member.objects.annotate(
        total_interest=Sum('interest__amount_deducted', default=Decimal('0.00'))
    )
    member_interest = {m.id: m.total_interest for m in member_interest_data}
    # print('member_interest_data', member_interest)

    context = {
        "savings_page": savings_page,
        "interest_page": interest_page,
        "loanable_page": loanable_page,
        "investment_page": investment_page,
        "total_savings": total_savings,
        "total_interest": total_interest,
        "total_loanable": total_loanable,
        "total_investment": total_investment,
        "grand_total": grand_total,
        "member_savings": member_savings,
        "member_interest": member_interest,
    }

    return render(request, "reports/summary.html", context)


def admin_loan_reports(request):
    # Default to current month
    month = request.GET.get('month', timezone.now().strftime('%Y-%m'))
    year, month_num = month.split('-')
    


    loan_type_id = request.GET.get('loan_type')

    monthly_requests = LoanRequest.objects.filter(
        application_date__year=year,
        # application_date__month=month_num
    )

    if loan_type_id:
        monthly_requests = monthly_requests.filter(loan_type_id=loan_type_id)

    monthly_approvals = monthly_requests.filter(status='approved')
    monthly_rejections = monthly_requests.filter(status='rejected')

    
    monthly_repayments = LoanRepayback.objects.filter(
        repayment_date__year=year,
        # repayment_date__month=month_num

    )
    if loan_type_id:
        monthly_repayments = monthly_repayments.filter(loan_request__loan_type_id=loan_type_id)

    loan_type_stats = LoanType.objects.annotate(
        total_requests=Count('loanrequest'),
        total_approved=Count('loanrequest', filter=Q(loanrequest__status='approved')),
        total_amount=Sum('loanrequest__approved_amount', filter=Q(loanrequest__status='approved'))
    )

    context = {
        'selected_month': month,
        'selected_loan_type': int(loan_type_id) if loan_type_id else None,
        'monthly_requests': monthly_requests.count(),
        'monthly_approvals': monthly_approvals.count(),
        'monthly_rejections': monthly_rejections.count(),
        'monthly_approved_amount': monthly_approvals.aggregate(Sum('approved_amount'))['approved_amount__sum'] or 0,
        'monthly_repayments': monthly_repayments.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0,
        'loan_type_stats': loan_type_stats,
        'loan_types': LoanType.objects.all(),  
    }
    return render(request, 'reports/reports.html', context)

def loan_request_report(request):
    # Initialize query set with all loan requests
    loan_requests = LoanRequest.objects.all().order_by('-date_created')

    # Initialize filters dictionary
    filters = {
        'status': request.GET.get('status', 'all'),
        'date_from': request.GET.get('date_from'),
        'date_to': request.GET.get('date_to'),
        'month': request.GET.get('month'),
        'loan_type': request.GET.get('loan_type'), 
    }

    # Apply filters
    if filters['status'] and filters['status'] != 'all':
        loan_requests = loan_requests.filter(status=filters['status'])

    if filters['date_from']:
        loan_requests = loan_requests.filter(application_date__gte=filters['date_from'])

    if filters['date_to']:
        loan_requests = loan_requests.filter(application_date__lte=filters['date_to'])

    if filters['month']:
        try:
            year, month = map(int, filters['month'].split('-'))
            loan_requests = loan_requests.filter(
                application_date__year=year,
                application_date__month=month
            )
        except ValueError:
            # Handle invalid month format if necessary
            pass

    # Apply loan_type filter
    if filters['loan_type']: # If a loan type is selected
        loan_requests = loan_requests.filter(loan_type__name=filters['loan_type'])

    loan_requests = loan_requests.annotate(
    total_paid=Coalesce(Sum('repaybacks__amount_paid'), 0.00, output_field=DecimalField()),
    balance_value=ExpressionWrapper(
        F('approved_amount') - Coalesce(Sum('repaybacks__amount_paid'), 0.00),
        output_field=DecimalField()
    ),
    total_price=Coalesce(F('approved_amount'), F('amount'), output_field=DecimalField())
    )


    # Calculate summary statistics
    summary = {
        'total_requests': loan_requests.count(),
        'total_value': loan_requests.aggregate(total_approved=Coalesce(Sum('approved_amount'), 0.00, output_field=DecimalField()))['total_approved'],
        'total_paid': loan_requests.aggregate(total_repaid=Coalesce(Sum('repaybacks__amount_paid'), 0.00, output_field=DecimalField()))['total_repaid'],
        'total_balance': loan_requests.aggregate(total_outstanding=Coalesce(Sum('balance_value'), 0.00, output_field=DecimalField()))['total_outstanding'],
        'pending_count': loan_requests.filter(status='pending').count(),
        'approved_count': loan_requests.filter(status='approved').count(),
        'paid_count': loan_requests.filter(status='Fullpaid').count(),
        'declined_count': loan_requests.filter(status='rejected').count(),
    }

    # Determine status choices for the filter dropdown
    status_choices = [('all', 'All Statuses')] + list(LoanRequest.status.field.choices)

    # Get unique months from existing loan requests for the "Filter by Month" dropdown
    distinct_application_dates = LoanRequest.objects.dates('application_date', 'month', order='DESC')
    months = [d for d in distinct_application_dates]

    # Get unique loan types for the "Filter by Loan Type" dropdown
    # Ensure LoanType model is imported as it's more direct to query LoanType itself
    # rather than LoanRequest.objects.values_list, which can miss loan types with no requests.
    # However, if you only want types that HAVE requests, your original line is fine.
    # Using LoanType.objects.all() to get all available loan types is generally more robust
    # for a filter dropdown.
    loan_types_qs = LoanType.objects.all().order_by("name")

    # Pagination
    page_number = request.GET.get('page')
    paginator = Paginator(loan_requests, 100) 
    page_obj = paginator.get_page(page_number)

    context = {
        # 'requests': requests,
        'requests': page_obj,
        'summary': summary,
        'filters': filters,
        'status_choices': status_choices,
        'months': months,
        'loan_types': loan_types_qs, 
    }
    return render(request, 'reports/loan_request_report.html', context)



def filtered_loan_repayments(request):
    years = LoanRequest.objects.annotate(year=ExtractYear("application_date")) \
        .values_list("year", flat=True).distinct().order_by("-year")
    loan_types = LoanRequest.objects.values_list("loan_type__name", flat=True).distinct().order_by("loan_type__name")

    selected_year = request.GET.get("year")
    selected_type = request.GET.get("loan_type")

    filters = Q()
    if selected_year:
        filters &= Q(loan_request__application_date__year=selected_year)
    if selected_type:
        filters &= Q(loan_request__loan_type__name=selected_type)

    repayments_qs = LoanRepayback.objects.select_related("loan_request__member", "loan_request__loan_type") \
        .filter(filters).order_by("-repayment_date")
    # Sum total repayment amount across all filtered records
    total_sum_paid = repayments_qs.aggregate(Sum("amount_paid"))["amount_paid__sum"] or 0

    # Enrich each repayment with total paid and balance
    enriched_repayments = []
    total_sum_remaining = 0 
    for repay in repayments_qs:
        loan = repay.loan_request
        total_paid = LoanRepayback.objects.filter(loan_request=loan).aggregate(Sum("amount_paid"))["amount_paid__sum"] or 0
        approved = loan.approved_amount or 0
        balance = approved - total_paid
        total_sum_remaining += balance  

        enriched_repayments.append({
            "repayment": repay,"total_paid": total_paid,"balance_remaining": balance,})
        
    # Add pagination
    paginator = Paginator(enriched_repayments, 100) 
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {"page_obj": page_obj,"years": years, "loan_types": loan_types,
                "selected_year": selected_year, "selected_type": selected_type,
                "total_sum_paid": total_sum_paid,"total_sum_remaining": total_sum_remaining,}
    return render(request, "reports/filtered_loan_repayments.html", context)



def request_status_report(request):
    """
    Generates a status report for consumable requests with filtering and aggregation.
    """
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    user_filter = request.GET.get('user')
    consumable_type_filter = request.GET.get('consumable_type')

    # Base queryset with optimized select_related and prefetch_related
    queryset = ConsumableRequest.objects.select_related(
        'user', 'approved_by', 'consumable_type'
    ).prefetch_related('details__item', 'repayments')

    # Apply filters
    if status_filter != 'all':
        queryset = queryset.filter(status=status_filter)

    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
            queryset = queryset.filter(date_created__date__gte=date_from_parsed)
        except ValueError:
            pass

    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
            queryset = queryset.filter(date_created__date__lte=date_to_parsed)
        except ValueError:
            pass

    if user_filter:
        try:
            user_id = int(user_filter)
            queryset = queryset.filter(user_id=user_id)
        except (ValueError, TypeError):
            pass

    if consumable_type_filter:
        try:
            consumable_type_id = int(consumable_type_filter)
            queryset = queryset.filter(consumable_type_id=consumable_type_id)
        except (ValueError, TypeError):
            pass

    # Order queryset for consistent results
    queryset = queryset.order_by('-date_created')

    # Create a list to hold request data with calculated fields
    requests_with_calculations = []
    for req in queryset:
        # Calculate total price using the model method
        total_price = req.calculate_total_price()
        
        # Calculate total paid using the model method
        total_paid = req.total_paid()
        
        # Calculate balance
        balance = req.balance()
        
        # Count items
        items_count = req.details.count()
        
        # Create a dictionary with all the data the template needs
        req_data = {
            'id': req.id,
            'user': req.user,
            'date_created': req.date_created,
            'status': req.status,
            'total_price': total_price,
            'total_paid': total_paid,
            'balance': balance,
            'items_count': items_count,
            'approved_by': req.approved_by,
            'consumable_type': req.consumable_type,
        }
        requests_with_calculations.append(req_data)

    # Calculate summary statistics
    total_requests = len(requests_with_calculations)
    pending_count = sum(1 for req in requests_with_calculations if req['status'] == 'Pending')
    approved_count = sum(1 for req in requests_with_calculations if req['status'] == 'Approved')
    itempicked_count = sum(1 for req in requests_with_calculations if req['status'] == 'Itempicked')
    paid_count = sum(1 for req in requests_with_calculations if req['status'] == 'FullyPaid')
    declined_count = sum(1 for req in requests_with_calculations if req['status'] == 'Declined')

    # Calculate financial totals
    total_value = sum(req['total_price'] for req in requests_with_calculations)
    total_paid = sum(req['total_paid'] for req in requests_with_calculations)
    total_balance = total_value - total_paid

    summary = {
        'total_requests': total_requests,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'paid_count': paid_count,
        'declined_count': declined_count,
        'itempicked_count': itempicked_count,  # Added this new status
        'total_value': total_value,
        'total_paid': total_paid,
        'total_balance': total_balance,
    }

    # Get list of available consumable types
    consumable_types = ConsumableType.objects.filter(available=True).order_by('name')
    users_with_requests = User.objects.filter(
        consumablerequest__isnull=False
    ).distinct().order_by('username')
    
    # Paginate the calculated requests
    paginator = Paginator(requests_with_calculations, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'requests': page_obj,
        'summary': summary,
        'users_with_requests': users_with_requests,
        'consumable_types': consumable_types,
        'filters': {
            'status': status_filter,
            'date_from': date_from,
            'date_to': date_to,
            'user': user_filter,
            'consumable_type': consumable_type_filter,
        },
        'status_choices': [
            ('all', 'All Statuses'),
            ('Pending', 'Pending'),
            ('Approved', 'Approved'),
            ('Itempicked', 'Item Picked'),  # Added this status from your model
            ('FullyPaid', 'Fully Paid'),
            ('Declined', 'Declined'),
        ]
    }

    return render(request, 'reports/consumable_request_status_report.html', context)




@login_required
def payment_analysis_report(request):
    """Detailed payment analysis and trends with enhanced filtering and performance"""

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    user_id = request.GET.get('user_id')
    status_filter = request.GET.get('status', 'all')

    parsed_date_from = None
    parsed_date_to = None

    try:
        if date_from:
            parsed_date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        if date_to:
            parsed_date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
        if parsed_date_from and parsed_date_to and parsed_date_from > parsed_date_to:
            messages.error(request, "Start date cannot be after end date.")
            parsed_date_from = parsed_date_to = None
    except ValueError:
        messages.error(request, "Invalid date format. Please use YYYY-MM-DD.")
        parsed_date_from = parsed_date_to = None

    queryset = PaybackConsumable.objects.select_related('consumable_request__user', 'consumable_request')

    if parsed_date_from:
        queryset = queryset.filter(repayment_date__gte=parsed_date_from)
    if parsed_date_to:
        queryset = queryset.filter(repayment_date__lte=parsed_date_to)
    if user_id:
        queryset = queryset.filter(consumable_request__user_id=user_id)

    payment_stats = queryset.aggregate(
        total_payments=Sum('amount_paid'),
        avg_payment=Avg('amount_paid'),
        payment_count=Count('id'),
        min_payment=Min('amount_paid'),
        max_payment=Max('amount_paid')
    )
    payment_stats = {k: v or 0 for k, v in payment_stats.items()}

    monthly_payments = queryset.annotate(
        month=TruncMonth('repayment_date')
    ).values('month').annotate(
        total_paid=Sum('amount_paid'),
        payment_count=Count('id'),
        avg_payment=Avg('amount_paid')
    ).order_by('month')

    three_months_ago = timezone.now().date() - timedelta(days=90)
    weekly_payments = queryset.filter(
        repayment_date__gte=three_months_ago
    ).annotate(
        week=TruncWeek('repayment_date')
    ).values('week').annotate(
        total_paid=Sum('amount_paid'),
        payment_count=Count('id')
    ).order_by('week')

    outstanding_filter = Q(status__in=['Pending', 'Approved', 'Itempicked'])
    if status_filter != 'all':
        outstanding_filter &= Q(status=status_filter)

    # Use database aggregation for outstanding totals to avoid Python loops
    outstanding_data = ConsumableRequest.objects.filter(
        outstanding_filter
    ).annotate(
        total_price=Sum(F('details__quantity') * F('details__item_price')),
        total_paid=Sum('repayments__amount_paid'),
        balance=F('total_price') - F('total_paid')
    ).filter(
        balance__gt=0
    ).select_related('user').order_by('-balance', '-date_created')

    total_outstanding = outstanding_data.aggregate(total=Sum('balance'))['total'] or 0

    outstanding_data_with_urgency = []
    for req in outstanding_data:
        days_outstanding = (timezone.now().date() - req.date_created.date()).days
        if days_outstanding > 90:
            urgency = 'critical'
        elif days_outstanding > 60:
            urgency = 'high'
        elif days_outstanding > 30:
            urgency = 'medium'
        else:
            urgency = 'low'
        
        # Calculate payment_percentage based on aggregated values
        payment_percentage = (req.total_paid / req.total_price * 100) if req.total_price else 0
        
        outstanding_data_with_urgency.append({
            'request': req,
            'total_price': req.total_price,
            'total_paid': req.total_paid,
            'balance': req.balance,
            'days_outstanding': days_outstanding,
            'urgency': urgency,
            'payment_percentage': payment_percentage
        })

    outstanding_summary = {
        'critical': len([x for x in outstanding_data_with_urgency if x['urgency'] == 'critical']),
        'high': len([x for x in outstanding_data_with_urgency if x['urgency'] == 'high']),
        'medium': len([x for x in outstanding_data_with_urgency if x['urgency'] == 'medium']),
        'low': len([x for x in outstanding_data_with_urgency if x['urgency'] == 'low']),
    }
    
    top_users = queryset.values(
        'consumable_request__user__username',
        'consumable_request__user__first_name',
        'consumable_request__user__last_name'
    ).annotate(
        total_paid=Sum('amount_paid'),
        payment_count=Count('id')
    ).order_by('-total_paid')[:10]

    recent_payments = queryset.filter(
        repayment_date__gte=timezone.now().date() - timedelta(days=30)
    ).select_related('consumable_request__user').order_by('-repayment_date')[:10]
    
    month_list = ConsumableRequest.objects.dates('date_created', 'month', order='DESC')
    users_list = ConsumableRequest.objects.select_related('user').values(
        'user__id', 'user__username', 'user__first_name', 'user__last_name'
    ).distinct().order_by('user__username')

    context = {
        'payment_stats': payment_stats,
        'monthly_payments': list(monthly_payments),
        'weekly_payments': list(weekly_payments),
        'outstanding_data': outstanding_data_with_urgency,
        'outstanding_summary': outstanding_summary,
        'top_users': top_users,
        'recent_payments': recent_payments,
        'months': month_list,
        'users_list': users_list,
        'total_outstanding': total_outstanding,
        'filters': {
            'date_from': date_from,
            'date_to': date_to,
            'user_id': user_id,
            'status': status_filter
        },
        'date_range_summary': {
            'start': parsed_date_from,
            'end': parsed_date_to,
            'days': (parsed_date_to - parsed_date_from).days if parsed_date_from and parsed_date_to else None
        }
    }

    return render(request, 'reports/consumable_payment_analysis_report.html', context)



@login_required
def user_spending_report(request):
    """Report showing spending patterns by user"""
    
    # Get date range filters
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Base queryset
    queryset = User.objects.all()
    
    user_spending = []
    for user in queryset:
        user_requests = ConsumableRequest.objects.filter(user=user)
        
        # Apply date filters
        if date_from:
            user_requests = user_requests.filter(date_created__gte=date_from)
        if date_to:
            user_requests = user_requests.filter(date_created__lte=date_to)
        
        total_requested = sum(req.calculate_total_price() for req in user_requests)
        total_paid = sum(req.total_paid() for req in user_requests)
        outstanding_balance = total_requested - total_paid
        
        if total_requested > 0:  # Only include users with requests
            user_spending.append({
                'user': user,
                'total_requests': user_requests.count(),
                'total_requested': total_requested,
                'total_paid': total_paid,
                'outstanding_balance': outstanding_balance,
                'pending_requests': user_requests.filter(status='Pending').count(),
                'approved_requests': user_requests.filter(status='Approved').count(),
                'paid_requests': user_requests.filter(status='Fullpaid').count(),
                'payment_completion_rate': (total_paid / total_requested * 100) if total_requested > 0 else 0
            })
    
    # Sort by total requested (descending)
    user_spending.sort(key=lambda x: x['total_requested'], reverse=True)
    
    # Calculate totals
    totals = {
        'total_users': len(user_spending),
        'total_requested': sum(u['total_requested'] for u in user_spending),
        'total_paid': sum(u['total_paid'] for u in user_spending),
        'total_outstanding': sum(u['outstanding_balance'] for u in user_spending),
        'avg_request_value': sum(u['total_requested'] for u in user_spending) / len(user_spending) if user_spending else 0
    }
    
    context = {
        'user_spending': user_spending,
        'totals': totals,
        'filters': {
            'date_from': date_from,
            'date_to': date_to
        }
    }
    
    return render(request, 'reports/user_spending_report.html', context)


@login_required
def item_popularity_report(request):
    """Report showing most requested items"""
    
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Base queryset
    queryset = ConsumableRequestDetail.objects.select_related('item', 'request')
    
    # Apply date filters
    if date_from:
        queryset = queryset.filter(request__date_created__gte=date_from)
    if date_to:
        queryset = queryset.filter(request__date_created__lte=date_to)
    
    # Aggregate by item
    item_stats = queryset.values('item__title').annotate(
        total_quantity=Sum('quantity'),
        total_requests=Count('request', distinct=True),
        total_value=Sum('total_price'),
        avg_price=Avg('item_price')
    ).order_by('-total_quantity')
    
    context = {
        'item_stats': item_stats,
        'total_items': item_stats.count(),
        'filters': {
            'date_from': date_from,
            'date_to': date_to
        }
    }
    
    return render(request, 'reports/item_popularity_report.html', context)





@login_required
def approval_workflow_report(request):
    """Report on approval workflow and approver statistics"""
    
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Base queryset
    queryset = ConsumableRequest.objects.select_related('user', 'approved_by')
    
    # Apply date filters
    if date_from:
        queryset = queryset.filter(date_created__gte=date_from)
    if date_to:
        queryset = queryset.filter(date_created__lte=date_to)
    
    # Approval statistics
    approval_stats = {
        'total_requests': queryset.count(),
        'pending_requests': queryset.filter(status='Pending').count(),
        'approved_requests': queryset.filter(status='Approved').count(),
        'declined_requests': queryset.filter(status='Declined').count(),
        'paid_requests': queryset.filter(status='Fullpaid').count(),
    }
    
    # Calculate approval rates
    total_processed = approval_stats['approved_requests'] + approval_stats['declined_requests'] + approval_stats['paid_requests']
    approval_stats['approval_rate'] = (
        (approval_stats['approved_requests'] + approval_stats['paid_requests']) / total_processed * 100
    ) if total_processed > 0 else 0
    
    # Approver statistics
    

# Build approver stats in Python
    approver_dict = defaultdict(lambda: {'total_approved': 0, 'total_value_approved': 0})

    for req in queryset.filter(approved_by__isnull=False):
        username = req.approved_by.username
        approver_dict[username]['total_approved'] += 1
        approver_dict[username]['total_value_approved'] += req.calculate_total_price()

    # Convert to list and sort
    approver_stats = [
        {'approved_by__username': username, **stats}
        for username, stats in approver_dict.items()
    ]
    approver_stats.sort(key=lambda x: x['total_approved'], reverse=True)

    
    # Average approval time (for approved requests with approval_date)
    approved_requests = ConsumableRequestDetail.objects.filter(
        approval_date__isnull=False
    ).select_related('request')
    
    approval_times = []
    for detail in approved_requests:
        days_to_approve = (detail.approval_date - detail.request.date_created.date()).days
        approval_times.append(days_to_approve)
    
    avg_approval_time = sum(approval_times) / len(approval_times) if approval_times else 0
    
    context = { 'approval_stats': approval_stats, 'approver_stats': approver_stats,'avg_approval_time': avg_approval_time,
        'filters': {
            'date_from': date_from,
            'date_to': date_to
        }
    }
    
    return render(request, 'reports/consumable_approval_workflow_report.html', context)


@login_required
def export_report_csv(request):
    """Export reports to CSV format"""
    
    report_type = request.GET.get('type', 'requests')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{report_type}_report.csv"'
    
    writer = csv.writer(response)
    
    if report_type == 'requests':
        # Export all requests
        writer.writerow(['ID', 'User', 'Date Created', 'Status', 'Approved By', 'Total Price', 'Total Paid', 'Balance'])
        
        for req in ConsumableRequest.objects.select_related('user', 'approved_by'):
            writer.writerow([
                req.id,
                req.user.username,
                req.date_created.strftime('%Y-%m-%d'),
                req.status,
                req.approved_by.username if req.approved_by else '',
                req.calculate_total_price(),
                req.total_paid(),
                req.balance()
            ])
    
    elif report_type == 'payments':
        # Export all payments
        writer.writerow(['Request ID', 'User', 'Amount Paid', 'Payment Date', 'Balance Remaining'])
        
        for payment in PaybackConsumable.objects.select_related('consumable_request__user'):
            writer.writerow([
                payment.consumable_request.id,
                payment.consumable_request.user.username,
                payment.amount_paid,
                payment.repayment_date.strftime('%Y-%m-%d'),
                payment.balance_remaining or 0
            ])
    
    elif report_type == 'user_spending':
        # Export user spending summary
        writer.writerow(['User', 'Total Requests', 'Total Requested', 'Total Paid', 'Outstanding Balance', 'Completion Rate'])
        
        for user in User.objects.all():
            user_requests = ConsumableRequest.objects.filter(user=user)
            total_requested = sum(req.calculate_total_price() for req in user_requests)
            total_paid = sum(req.total_paid() for req in user_requests)
            
            if total_requested > 0:
                completion_rate = (total_paid / total_requested * 100) if total_requested > 0 else 0
                writer.writerow([
                    user.username,
                    user_requests.count(),
                    total_requested,
                    total_paid,
                    total_requested - total_paid,
                    f"{completion_rate:.1f}%"
                ])
    
    return response


@login_required
def report_api_data(request):
    """API endpoint for chart data"""
    
    chart_type = request.GET.get('chart', 'monthly_trends')
    
    if chart_type == 'monthly_trends':
        # Monthly request and payment trends
        end_date = timezone.now()
        start_date = end_date - timedelta(days=365)
        
        monthly_data = ConsumableRequest.objects.filter(
            date_created__range=[start_date, end_date]
        ).annotate(
            month=TruncMonth('date_created')
        ).values('month').annotate(
            request_count=Count('id'),
            total_value=Sum('details__total_price')
        ).order_by('month')
        
        return JsonResponse({
            'labels': [item['month'].strftime('%Y-%m') for item in monthly_data],
            'request_counts': [item['request_count'] for item in monthly_data],
            'total_values': [float(item['total_value'] or 0) for item in monthly_data]
        })
    
    elif chart_type == 'status_distribution':
        # Request status distribution
        status_data = ConsumableRequest.objects.values('status').annotate(
            count=Count('id')
        )
        
        return JsonResponse({
            'labels': [item['status'] for item in status_data],
            'data': [item['count'] for item in status_data]
        })
    
    elif chart_type == 'top_items':
        # Top 10 most requested items
        top_items = ConsumableRequestDetail.objects.values('item__title').annotate(
            total_quantity=Sum('quantity')
        ).order_by('-total_quantity')[:10]
        
        return JsonResponse({
            'labels': [item['item__title'] for item in top_items],
            'data': [item['total_quantity'] for item in top_items]
        })
    
    return JsonResponse({'error': 'Invalid chart type'}, status=400)



# views.py - Fixed version (no model changes)
import logging
from datetime import datetime
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum, F, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce
from django.shortcuts import render


import logging
from decimal import Decimal
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum, F
from datetime import datetime
from django.utils.dateparse import parse_date

# Import your models (make sure these are correct for your project)
# from models import (
#     PurchasedItem, ConsumableRequestDetail, ProjectFinanceRequest, 
#     LoanRequest, Savings, Interest, PaybackConsumable, 
#     ProjectFinancePayment, ConsumableFormFee, LoanRepayback, LoanRequestFee
# )

logger = logging.getLogger(__name__)

@login_required
def consolidated_report(request):
    """Generate consolidated financial report with date filtering"""
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Parse and validate dates
    parsed_date_from = None
    parsed_date_to = None
    
    if date_from:
        try:
            parsed_date_from = parse_date(date_from)
            if parsed_date_from is None:
                raise ValueError("Invalid date format")
        except (ValueError, TypeError):
            context = {
                'error': 'Invalid start date format. Please use YYYY-MM-DD format.',
                'date_from': date_from,
                'date_to': date_to,
            }
            return render(request, "reports/consolidated_report.html", context)
    
    if date_to:
        try:
            parsed_date_to = parse_date(date_to)
            if parsed_date_to is None:
                raise ValueError("Invalid date format")
        except (ValueError, TypeError):
            context = {
                'error': 'Invalid end date format. Please use YYYY-MM-DD format.',
                'date_from': date_from,
                'date_to': date_to,
            }
            return render(request, "reports/consolidated_report.html", context)
    
    # Check if start date is after end date
    if parsed_date_from and parsed_date_to and parsed_date_from > parsed_date_to:
        context = {
            'error': 'Start date cannot be later than end date',
            'date_from': date_from,
            'date_to': date_to,
        }
        return render(request, "reports/consolidated_report.html", context)

    try:
        filters = {}
        if parsed_date_from:
            filters['date_from'] = parsed_date_from
        if parsed_date_to:
            filters['date_to'] = parsed_date_to

        # Calculate Total Expenditure (Money going out)
        expenditure_data = calculate_total_expenditure(filters)
        
        # Calculate Total Income (Money coming in)
        income_data = calculate_total_income(filters)
        
        # Calculate totals with proper error handling
        total_expenditure = Decimal('0')
        total_income = Decimal('0')
        
        try:
            total_expenditure = sum(expenditure_data.values())
            total_income = sum(income_data.values())
        except (TypeError, ValueError) as e:
            logger.error(f"Error calculating totals: {str(e)}")
            total_expenditure = Decimal('0')
            total_income = Decimal('0')
        
        # Calculate net position
        net_position = total_income - total_expenditure
        
        filters_applied = bool(date_from or date_to)
        
        context = {
            'total_expenditure': total_expenditure,
            'total_income': total_income,
            'net_position': net_position,
            'date_from': date_from,
            'date_to': date_to,
            'filters_applied': filters_applied,
            **expenditure_data,  # Unpack expenditure breakdown
            **income_data,       # Unpack income breakdown
        }
        
        return render(request, "reports/consolidated_report.html", context)
        
    except Exception as e:
        logger.error(f"Error generating consolidated report: {str(e)}", exc_info=True)
        context = {
            'error': 'An error occurred while generating the report. Please try again.',
            'date_from': date_from,
            'date_to': date_to,
        }
        return render(request, "reports/consolidated_report.html", context)


def calculate_total_expenditure(filters):
    """Calculate total expenditure with proper error handling"""
    date_from = filters.get('date_from')
    date_to = filters.get('date_to')
    
    try:
        # Build Q objects for filtering
       
        purchase_filter = Q()
        consumable_expenditure_filter = Q()
        finance_expenditure_filter = Q()
        loan_disbursement_filter = Q()
        
        if date_from:
           
            purchase_filter &= Q(date_added__gte=date_from)
            consumable_expenditure_filter &= Q(date_created__gte=date_from)
            finance_expenditure_filter &= Q(created_at__gte=date_from)
            loan_disbursement_filter &= Q(date_created__gte=date_from)

        if date_to:
           
            purchase_filter &= Q(date_added__lte=date_to)
            consumable_expenditure_filter &= Q(date_created__lte=date_to)
            finance_expenditure_filter &= Q(created_at__lte=date_to)
            loan_disbursement_filter &= Q(date_created__lte=date_to)

       
        
        # 1. Staff purchases with null checks
        try:
            staff_purchases = PurchasedItem.objects.filter(
                purchase_filter
            ).aggregate(
                total=Sum(
                    F('unit_price') * F('quantity') + F('expenditure_amount'),
                    output_field=models.DecimalField()
                )
            )['total'] or Decimal('0')
        except Exception as e:
            logger.error(f"Error calculating staff purchases: {str(e)}")
            staff_purchases = Decimal('0')
        
        # 2. Member-requested consumables (cost to the organization)
        try:
            member_consumable_cost = ConsumableRequestDetail.objects.filter(
                consumable_expenditure_filter,
                request__status__in=['Approved', 'Itempicked', 'FullyPaid']
            ).aggregate(
                total=Sum(
                    F('quantity') * F('item_price'),
                    output_field=models.DecimalField()
                )
            )['total'] or Decimal('0')
        except Exception as e:
            logger.error(f"Error calculating member consumable cost: {str(e)}")
            member_consumable_cost = Decimal('0')

        # 3. Member-requested project finance (loan amount disbursed)
        try:
            member_finance_loans = ProjectFinanceRequest.objects.filter(
                finance_expenditure_filter,
                status__in=['Reviewed', 'Completed', 'FullyPaid']
            ).aggregate(
                total=Sum('requested_amount')
            )['total'] or Decimal('0')
        except Exception as e:
            logger.error(f"Error calculating member finance loans: {str(e)}")
            member_finance_loans = Decimal('0')

        # 4. Member-requested loans (loan amount disbursed)
        try:
            loan_disbursements = LoanRequest.objects.filter(
                loan_disbursement_filter,
                status__in=['approved', 'Fullpaid'],
                approved_amount__isnull=False
            ).aggregate(
                total=Sum('approved_amount')
            )['total'] or Decimal('0')
        except Exception as e:
            logger.error(f"Error calculating loan disbursements: {str(e)}")
            loan_disbursements = Decimal('0')

        return {
            'staff_purchases': staff_purchases,
            'member_consumable_cost': member_consumable_cost,
            'member_finance_loans': member_finance_loans,
            'loan_disbursements': loan_disbursements,
        }
        
    except Exception as e:
        logger.error(f"Error in calculate_total_expenditure: {str(e)}", exc_info=True)
        return {
           
            'staff_purchases': Decimal('0'),
            'member_consumable_cost': Decimal('0'),
            'member_finance_loans': Decimal('0'),
            'loan_disbursements': Decimal('0'),
        }


def calculate_total_income(filters):
    """Calculate total income with proper filtering and error handling"""
    date_from = filters.get('date_from')
    date_to = filters.get('date_to')
    
    try:
        # Build Q objects for filtering
        admin_fee_filter = Q()
        saving_filter = Q()
        member_payback_filter = Q()
        member_finance_payback_filter = Q()
        member_fees_filter = Q()
        loan_payback_filter = Q()
        loan_fee_filter = Q()
        
        if date_from:
            admin_fee_filter &= Q(date_deducted__gte=date_from)
            saving_filter &= Q(date_created__gte=date_from)
            member_payback_filter &= Q(repayment_date__gte=date_from)
            member_finance_payback_filter &= Q(paid_at__gte=date_from)
            member_fees_filter &= Q(created_at__gte=date_from)
            loan_payback_filter &= Q(repayment_date__gte=date_from)
            loan_fee_filter &= Q(created_at__gte=date_from)

        if date_to:
            admin_fee_filter &= Q(date_deducted__lte=date_to)
            saving_filter &= Q(date_created__lte=date_to)
            member_payback_filter &= Q(repayment_date__lte=date_to)
            member_finance_payback_filter &= Q(paid_at__lte=date_to)
            member_fees_filter &= Q(created_at__lte=date_to)
            loan_payback_filter &= Q(repayment_date__lte=date_to)
            loan_fee_filter &= Q(created_at__lte=date_to)

        # 1. Income from saving items
        try:
            saving_income = Savings.objects.filter(
                saving_filter
            ).aggregate(
                total=Sum('month_saving')
            )['total'] or Decimal('0')
        except Exception as e:
            logger.error(f"Error calculating saving income: {str(e)}")
            saving_income = Decimal('0')

        # 2. Income from Admin fee items
        try:
            admin_fee_income = Interest.objects.filter(
                admin_fee_filter
            ).aggregate(
                total=Sum('amount_deducted')
            )['total'] or Decimal('0')
        except Exception as e:
            logger.error(f"Error calculating admin fee income: {str(e)}")
            admin_fee_income = Decimal('0')

        # 3. Member repayments for consumables
        try:
            consumable_payback_income = PaybackConsumable.objects.filter(
                member_payback_filter
            ).aggregate(
                total=Sum('amount_paid')
            )['total'] or Decimal('0')
        except Exception as e:
            logger.error(f"Error calculating consumable payback income: {str(e)}")
            consumable_payback_income = Decimal('0')

        # 4. Member repayments for project finance
        try:
            finance_payback_income = ProjectFinancePayment.objects.filter(
                member_finance_payback_filter
            ).aggregate(
                total=Sum('amount_paid')
            )['total'] or Decimal('0')
        except Exception as e:
            logger.error(f"Error calculating finance payback income: {str(e)}")
            finance_payback_income = Decimal('0')

        # 5. Income from consumable form fees
        try:
            form_fee_income = ConsumableFormFee.objects.filter(
                member_fees_filter
            ).aggregate(
                total=Sum('form_fee')
            )['total'] or Decimal('0')
        except Exception as e:
            logger.error(f"Error calculating form fee income: {str(e)}")
            form_fee_income = Decimal('0')

        # 6. Member repayments for loans
        try:
            loan_payback_income = LoanRepayback.objects.filter(
                loan_payback_filter
            ).aggregate(
                total=Sum('amount_paid')
            )['total'] or Decimal('0')
        except Exception as e:
            logger.error(f"Error calculating loan payback income: {str(e)}")
            loan_payback_income = Decimal('0')

        # 7. Income from loan form fees
        try:
            loan_form_fee_income = LoanRequestFee.objects.filter(
                loan_fee_filter
            ).aggregate(
                total=Sum('form_fee')
            )['total'] or Decimal('0')
        except Exception as e:
            logger.error(f"Error calculating loan form fee income: {str(e)}")
            loan_form_fee_income = Decimal('0')

        return {
            'saving_income': saving_income,
            'admin_fee_income': admin_fee_income,
            'consumable_payback_income': consumable_payback_income,
            'finance_payback_income': finance_payback_income,
            'form_fee_income': form_fee_income,
            'loan_payback_income': loan_payback_income,
            'loan_form_fee_income': loan_form_fee_income,
        }
        
    except Exception as e:
        logger.error(f"Error in calculate_total_income: {str(e)}", exc_info=True)
        return {
            'saving_income': Decimal('0'),
            'admin_fee_income': Decimal('0'),
            'consumable_payback_income': Decimal('0'),
            'finance_payback_income': Decimal('0'),
            'form_fee_income': Decimal('0'),
            'loan_payback_income': Decimal('0'),
            'loan_form_fee_income': Decimal('0'),
        }




# logger = logging.getLogger(__name__)
# @login_required
# def consolidated_report(request):
#     date_from = request.GET.get('date_from')
#     date_to = request.GET.get('date_to')
    
#     if date_from and date_to and date_from > date_to:
#         context = { 'error': 'Start date cannot be later than end date',
#             'date_from': date_from,'date_to': date_to, }
#         return render(request, "reports/consolidated_report.html", context)

#     try:
#         filters = {}
#         if date_from:
#             filters['date_from'] = date_from
#         if date_to:
#             filters['date_to'] = date_to

#         # --- Calculate Total Expenditure (Money going out) ---
#         expenditure_data = calculate_total_expenditure(filters)
        
#         # --- Calculate Total Income (Money coming in) ---
#         income_data = calculate_total_income(filters)
        
#         # Calculate totals
#         total_expenditure = sum(expenditure_data.values())
#         total_income = sum(income_data.values())
        
#         # Calculate net position
#         net_position = total_income - total_expenditure
        
#         filters_applied = bool(date_from or date_to)
        
#         context = {
#             'total_expenditure': total_expenditure,
#             'total_income': total_income,
#             'net_position': net_position,
#             'date_from': date_from,
#             'date_to': date_to,
#             'filters_applied': filters_applied,
#             **expenditure_data,  # Unpack expenditure breakdown
#             **income_data,       # Unpack income breakdown
#         }
        
#         return render(request, "reports/consolidated_report.html", context)
        
#     except Exception as e:
#         logger.error(f"Error generating consolidated report: {str(e)}")
#         context = {'error': 'An error occurred while generating the report. Please try again.',
#             'date_from': date_from,'date_to': date_to, }
#         return render(request, "reports/consolidated_report.html", context)


# def calculate_total_expenditure(filters):
#     date_from = filters.get('date_from')
#     date_to = filters.get('date_to')
    
#     # Build Q objects for filtering
#     purchase_filter = Q()
#     consumable_expenditure_filter = Q()
#     finance_expenditure_filter = Q()
#     loan_disbursement_filter = Q()
    
#     if date_from:
#         purchase_filter &= Q(date_added__gte=date_from)
#         consumable_expenditure_filter &= Q(date_created__gte=date_from)
#         finance_expenditure_filter &= Q(created_at__gte=date_from)
#         loan_disbursement_filter &= Q(date_created__gte=date_from)

#     if date_to:
#         purchase_filter &= Q(date_added__lte=date_to)
#         consumable_expenditure_filter &= Q(date_created__lte=date_to)
#         finance_expenditure_filter &= Q(created_at__lte=date_to)
#         loan_disbursement_filter &= Q(date_created__lte=date_to)

#     staff_purchases = PurchasedItem.objects.filter(
#         purchase_filter
#     ).aggregate(
#         total=Sum(F('unit_price') * F('quantity') + F('expenditure_amount'))
#     )['total'] or Decimal('0')
    
#     # 2. Member-requested consumables (cost to the organization)
#     # Only include approved/completed requests
#     member_consumable_cost = ConsumableRequestDetail.objects.filter(
#         consumable_expenditure_filter,
#         request__status__in=['Approved', 'Itempicked', 'FullyPaid']
#     ).aggregate(
#         total=Sum(F('quantity') * F('item_price'))
#     )['total'] or Decimal('0')

#     # 3. Member-requested project finance (loan amount disbursed)
#     # Only include approved/completed requests
#     member_finance_loans = ProjectFinanceRequest.objects.filter(
#         finance_expenditure_filter,
#         status__in=['Reviewed', 'Completed', 'FullyPaid']
#     ).aggregate(total=Sum('requested_amount'))['total'] or Decimal('0')

#     # 4. Member-requested loans (loan amount disbursed)
#     # Only include actually approved loans with disbursed amounts
#     loan_disbursements = LoanRequest.objects.filter(
#         loan_disbursement_filter,
#         status__in=['approved', 'paid'],
#         approved_amount__isnull=False
#     ).aggregate(total=Sum('approved_amount'))['total'] or Decimal('0')

#     return {
#         'staff_purchases': staff_purchases,
#         'member_consumable_cost': member_consumable_cost,
#         'member_finance_loans': member_finance_loans,
#         'loan_disbursements': loan_disbursements,
#     }


# def calculate_total_income(filters):
#     """Calculate total income with proper filtering"""
#     date_from = filters.get('date_from')
#     date_to = filters.get('date_to')
    
#     # Build Q objects for filtering
#     admin_fee_filter = Q()
#     saving_filter = Q()
#     member_payback_filter = Q()
#     member_finance_payback_filter = Q()
#     member_fees_filter = Q()
#     loan_payback_filter = Q()
#     loan_fee_filter = Q()
    
#     if date_from:
#         admin_fee_filter &= Q(created_at__gte=date_from)
#         saving_filter &= Q(date_created__gte=date_from)
#         member_payback_filter &= Q(repayment_date__gte=date_from)
#         member_finance_payback_filter &= Q(paid_at__gte=date_from)
#         member_fees_filter &= Q(created_at__gte=date_from)
#         loan_payback_filter &= Q(repayment_date__gte=date_from)
#         loan_fee_filter &= Q(created_at__gte=date_from)

#     if date_to:
#         admin_fee_filter &= Q(created_at__lte=date_to)
#         saving_filter &= Q(date_created__lte=date_to)
#         member_payback_filter &= Q(repayment_date__lte=date_to)
#         member_finance_payback_filter &= Q(paid_at__lte=date_to)
#         member_fees_filter &= Q(created_at__lte=date_to)
#         loan_payback_filter &= Q(repayment_date__lte=date_to)
#         loan_fee_filter &= Q(created_at__lte=date_to)

#     # 1. Income from saving items
#     saving_income = Savings.objects.filter(saving_filter
#     ).aggregate( total=Sum(F('month_saving'))
#     )['total'] or Decimal('0')

#    # 2. Income from Admin fee items
#     admin_fee_income = Interest.objects.filter(admin_fee_filter
#     ).aggregate(total=Sum(F('amount_deducted'))
#     )['total'] or Decimal('0')

#     # 3. Member repayments for consumables
#     consumable_payback_income = PaybackConsumable.objects.filter(
#         member_payback_filter
#     ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0')

#     # 4. Member repayments for project finance
#     finance_payback_income = ProjectFinancePayment.objects.filter(
#         member_finance_payback_filter
#     ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0')

#     # 5. Income from consumable form fees
#     form_fee_income = ConsumableFormFee.objects.filter( member_fees_filter
#                 ).aggregate(total=Sum('form_fee'))['total'] or Decimal('0')

#     # 6. Member repayments for loans
#     loan_payback_income = LoanRepayback.objects.filter(loan_payback_filter
#                 ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0')

#     # 7. Income from loan form fees
#     loan_form_fee_income = LoanRequestFee.objects.filter(loan_fee_filter
#                 ).aggregate(total=Sum('form_fee'))['total'] or Decimal('0')

#     return {
#         'saving_income': saving_income, 'admin_fee_income': admin_fee_income,
#         'consumable_payback_income': consumable_payback_income,'finance_payback_income': finance_payback_income,
#         'form_fee_income': form_fee_income,'loan_payback_income': loan_payback_income,
#         'loan_form_fee_income': loan_form_fee_income,
#     }



