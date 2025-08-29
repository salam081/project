from django.shortcuts import render
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
from django.core.serializers.json import DjangoJSONEncoder

import pandas as pd
from datetime import datetime
from django.contrib import messages
from django.db import transaction
from decimal import Decimal, InvalidOperation
from django.db.models import Count
from collections import defaultdict
from django.utils import timezone
import requests
from django.utils import timezone
from datetime import datetime
from loan.models import *
from .models import *
from .forms import *
from accounts.models import *
from accounts.models import *
from accounts.models import *
from main.models import *

from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, F, Q, DecimalField, Count
from django.db.models.functions import Coalesce
from decimal import Decimal
from datetime import datetime, date




# =============ProjectFinanceApplication===================
@login_required
def application_list_view(request):
    applications = ProjectFinanceApplication.objects.select_related('member__member').order_by('-created_at')
    context = {'applications': applications}
    return render(request, 'projectfinance/project_finance_application.html', context)


@login_required
def application_detail_view(request, application_id):
    application = get_object_or_404(ProjectFinanceApplication, id=application_id)

    if request.method == 'POST':
        action = request.POST.get('action')
        comments = request.POST.get('comments', '').strip()
        # Handle 'review' or 'approve' action
        if action == 'review_application':
            if application.status not in ['Reviewed', 'Rejected']:
                application.status = 'Reviewed'
                application.save()
                messages.success(request, "Application reviewed and approved successfully.")
            else:
                messages.info(request, "This application has already been reviewed or rejected.")
        
       # Handle 'reject' action
        elif action == 'reject_application':
            if application.status not in ['Reviewed', 'Rejected']:
                # Check if comments are provided for rejection
                if comments:
                    application.status = 'Rejected'
                    new_comment = f"[{request.user.username} - {timezone.now().strftime('%Y-%m-%d %H:%M')}] - REJECTED: {comments}"
                    if application.comments:
                        application.comments += f"\n\n{new_comment}"
                    else:
                        application.comments = new_comment
                    
                    application.save()
                    messages.success(request, "Application has been rejected.")
                else:
                    # Show a warning if no comment is provided
                    messages.warning(request, "Please provide a reason for rejection in the comments box.")
            else:
                messages.info(request, "This application has already been reviewed or rejected.")
        # Handle 'add_comment' action (independent of approval/rejection)
        elif action == 'add_comment':
            if comments:
                new_comment = f"[{request.user.username} - {timezone.now().strftime('%Y-%m-%d %H:%M')}]: {comments}"
                if application.comments:
                    application.comments += f"\n\n{new_comment}"
                else:
                    application.comments = new_comment
                
                application.save()
                messages.success(request, "Comment added successfully.")
            else:
                messages.warning(request, "Please provide a comment.")

        return redirect('application_detail', application_id=application_id)

    context = {'application': application}
    return render(request, 'projectfinance/application_detail.html', context)
   

@login_required
def admin_project_finance_requests_list(request):
    requests = ProjectFinanceRequest.objects.filter(status__in=['Pending', 'Reviewed']).order_by('-created_at').select_related( 'application__member__member')
    context = {'requests': requests}
    return render(request, 'projectfinance/project_finance_list_requests.html', context)

@login_required
def admin_approve_finance_request(request, id):
    finance_request = get_object_or_404(ProjectFinanceRequest, id=id)
    
    # Check if guarantor has approved
    if finance_request.guarantor_status != 'Approved':
        messages.error(request, "Cannot approve — guarantor has not approved this request.")
        return redirect('admin_project_finance_requests')

    if request.method == 'POST':
        markup_rate_str = request.POST.get('markup_rate', '0')
        try:
            markup_rate = Decimal(markup_rate_str)
        except (TypeError, ValueError, InvalidOperation):
            messages.error(request, "Invalid markup rate provided. Please enter a number.")
            return redirect('project_finance_approved', id=id)

        # Update the request with the new markup rate
        finance_request.markup_rate = markup_rate
        finance_request.status = 'Approved'
        finance_request.approved_by = request.user
        finance_request.save()

        messages.success(request, "Request approved with markup successfully.")
        return redirect('admin_project_finance_requests')

    return render(request, 'projectfinance/project_finance_approve.html', {'finance_request': finance_request})





# ==========================================
# MAIN REPORT GENERATION FUNCTION
# ==========================================


import xlsxwriter
from decimal import Decimal
from datetime import datetime, date
from io import BytesIO
from datetime import datetime, time
from decimal import Decimal

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q, Sum, Count, F
from django.db.models.functions import Coalesce
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.utils import timezone

# --------- helpers ---------
def _aware_start_of_day(d):
    """Take a date or datetime and return timezone-aware start-of-day."""
    if isinstance(d, datetime):
        dt = d.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        dt = datetime.combine(d, time.min)
    return timezone.make_aware(dt) if timezone.is_naive(dt) else dt

def _aware_end_of_day(d):
    """Take a date or datetime and return timezone-aware end-of-day."""
    if isinstance(d, datetime):
        dt = d.replace(hour=23, minute=59, second=59, microsecond=999999)
    else:
        dt = datetime.combine(d, time.max)
    return timezone.make_aware(dt) if timezone.is_naive(dt) else dt


# ==========================================
# REPORT CORE
# ==========================================
def generate_project_finance_report(start_date=None, end_date=None):
    """
    start_date/end_date are expected as date objects (YYYY-MM-DD from the view).
    We convert them to timezone-aware day bounds and build filters safely.
    """
    # keep originals for display
    display_start = start_date
    display_end = end_date

    # convert to aware datetimes for filtering
    start_aware = _aware_start_of_day(start_date) if start_date else None
    end_aware = _aware_end_of_day(end_date) if end_date else None

    # Base queryset filter for ProjectFinanceRequest (created_at is DateTimeField)
    base_filter = Q()
    if start_aware:
        base_filter &= Q(created_at__gte=start_aware)
    if end_aware:
        base_filter &= Q(created_at__lte=end_aware)

    # 1) EXPENDITURE (approved/disbursed requests)
    expenditure_data = ProjectFinanceRequest.objects.filter(
        base_filter,
        status__in=['Reviewed', 'Completed', 'FullyPaid']
    ).aggregate(
        total_expenditure=Coalesce(Sum('requested_amount'), Decimal('0.00')),
        total_requests=Count('id')
    )

    # 2) INCOME (payments received) – filter like above (avoid datetime.min)
    income_filter = Q()
    if start_aware:
        income_filter &= Q(request__created_at__gte=start_aware)
    if end_aware:
        income_filter &= Q(request__created_at__lte=end_aware)

    income_data = ProjectFinancePayment.objects.filter(income_filter).aggregate(
        total_income=Coalesce(Sum('amount_paid'), Decimal('0.00')),
        total_payments=Count('id')
    )

    # 3) EXPECTED TOTAL INCOME
    expected_income_data = ProjectFinanceRequest.objects.filter(
        base_filter,
        status__in=['Reviewed', 'Completed', 'FullyPaid'],
        total_repayment_amount__isnull=False
    ).aggregate(
        expected_total_income=Coalesce(Sum('total_repayment_amount'), Decimal('0.00'))
    )

    # 4) PROFIT ANALYSIS
    total_expenditure = expenditure_data['total_expenditure']
    total_income = income_data['total_income']
    expected_total_income = expected_income_data['expected_total_income']

    current_profit = total_income - total_expenditure
    expected_profit = expected_total_income - total_expenditure
    outstanding_amount = expected_total_income - total_income

    # 5) PROFIT PER MEMBER
    member_profits = []
    members_with_requests = ProjectFinanceRequest.objects.filter(
        base_filter,
        status__in=['Reviewed', 'Completed', 'FullyPaid']
    ).values(
        'application__member__id',
        'application__member__member__first_name',
        'application__member__member__last_name'
    ).distinct()

    for m in members_with_requests:
        member_id = m['application__member__id']
        member_name = f"{m['application__member__member__first_name']} {m['application__member__member__last_name']}"

        # Requests for member (use same base_filter)
        member_requests = ProjectFinanceRequest.objects.filter(
            base_filter,
            application__member__id=member_id,
            status__in=['Reviewed', 'Completed', 'FullyPaid']
        )

        # Expenditure per member
        member_expenditure = member_requests.aggregate(
            total=Coalesce(Sum('requested_amount'), Decimal('0.00'))
        )['total']

        # Income per member
        member_income_filter = Q(request__application__member__id=member_id)
        if start_aware:
            member_income_filter &= Q(request__created_at__gte=start_aware)
        if end_aware:
            member_income_filter &= Q(request__created_at__lte=end_aware)

        member_income = ProjectFinancePayment.objects.filter(
            member_income_filter
        ).aggregate(
            total=Coalesce(Sum('amount_paid'), Decimal('0.00'))
        )['total']

        # Expected income per member
        member_expected_income = member_requests.filter(
            total_repayment_amount__isnull=False
        ).aggregate(
            total=Coalesce(Sum('total_repayment_amount'), Decimal('0.00'))
        )['total']

        # Profit calculations
        member_current_profit = member_income - member_expenditure
        member_expected_profit = member_expected_income - member_expenditure
        member_outstanding = member_expected_income - member_income

        # Counts
        active_requests = member_requests.exclude(status='FullyPaid').count()
        completed_requests = member_requests.filter(status='FullyPaid').count()

        member_profits.append({
            'member_id': member_id,
            'member_name': member_name,
            'expenditure': member_expenditure,
            'income_received': member_income,
            'expected_income': member_expected_income,
            'current_profit': member_current_profit,
            'expected_profit': member_expected_profit,
            'outstanding_amount': member_outstanding,
            'active_requests': active_requests,
            'completed_requests': completed_requests,
            'total_requests': active_requests + completed_requests
        })

    # Sort members (current profit is usually the most actionable)
    member_profits.sort(key=lambda x: x['current_profit'], reverse=True)

    # 6) SUMMARY STATS
    total_active_requests = ProjectFinanceRequest.objects.filter(
        base_filter, status__in=['Reviewed', 'Completed']
    ).count()
    total_completed_requests = ProjectFinanceRequest.objects.filter(
        base_filter, status='FullyPaid'
    ).count()

    # Margins (guard div-by-zero)
    profit_margin_current = (current_profit / total_expenditure * 100) if total_expenditure > 0 else (100 if total_income > 0 else 0)
    profit_margin_expected = (expected_profit / total_expenditure * 100) if total_expenditure > 0 else (100 if expected_total_income > 0 else 0)

    report = {
        'summary': {
            'total_expenditure': total_expenditure,
            'total_income': total_income,
            'expected_total_income': expected_total_income,
            'current_profit': current_profit,
            'expected_profit': expected_profit,
            'outstanding_amount': outstanding_amount,
            'profit_margin_current': profit_margin_current,
            'profit_margin_expected': profit_margin_expected,
        },
        'statistics': {
            'total_requests': expenditure_data['total_requests'],
            'total_payments_made': income_data['total_payments'],
            'active_requests': total_active_requests,
            'completed_requests': total_completed_requests,
            'average_request_amount': (total_expenditure / expenditure_data['total_requests']) if expenditure_data['total_requests'] > 0 else 0,
            'unique_members': len(member_profits)
        },
        'member_profits': member_profits,
        'generated_at': timezone.now(),
        'date_range': {
            # keep pure dates for clean template display
            'start_date': display_start,
            'end_date': display_end,
        }
    }
    return report


# ==========================================
# DJANGO VIEWS
# ==========================================
@staff_member_required
def project_finance_report_view(request):
    context = {}

    # Template uses ?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    start_date = None
    end_date = None

    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = None

    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            end_date = None

    # Generate report when filters provided or explicit trigger
    if request.method == 'GET' and (start_date or end_date or 'generate' in request.GET):
        try:
            report = generate_project_finance_report(start_date, end_date)
            context['report'] = report
            context['success'] = True
        except Exception as e:
            context['error'] = f"Error generating report: {str(e)}"

    return render(request, 'projectfinance/project_finance_report.html', context)


@staff_member_required
def project_finance_report_api(request):
    """JSON API"""
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    start_date = None
    end_date = None
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'error': 'Invalid start date format'}, status=400)
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'error': 'Invalid end date format'}, status=400)

    try:
        report = generate_project_finance_report(start_date, end_date)

        # convert Decimals for JSON
        def _decimal_to_float(obj):
            if isinstance(obj, Decimal):
                return float(obj)
            if isinstance(obj, dict):
                return {k: _decimal_to_float(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_decimal_to_float(v) for v in obj]
            return obj

        report = _decimal_to_float(report)
        # generated_at is aware dt -> ISO string
        if isinstance(report.get('generated_at'), datetime):
            report['generated_at'] = report['generated_at'].isoformat()

        return JsonResponse(report)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@staff_member_required
def project_finance_report_excel(request):
    try:
        import xlsxwriter
        from io import BytesIO
    except ImportError:
        return HttpResponse('Excel generation requires XlsxWriter. Install with: pip install XlsxWriter', status=500)

    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    start_date = None
    end_date = None
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = None
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            end_date = None

    try:
        report = generate_project_finance_report(start_date, end_date)

        # Build Excel in-memory
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output)

        header_format = workbook.add_format({
            'bold': True, 'bg_color': '#2c3e50', 'font_color': 'white',
            'align': 'center', 'valign': 'vcenter', 'border': 1
        })
        currency_format = workbook.add_format({'num_format': '₦#,##0.00'})
        percent_format = workbook.add_format({'num_format': '0.00%'})

        # Summary sheet
        summary_sheet = workbook.add_worksheet('Summary')
        summary_sheet.write('A1', 'Financial Summary', header_format)
        summary_sheet.write('A3', 'Metric')
        summary_sheet.write('B3', 'Value')

        summary_data = [
            ('Total Expenditure', float(report['summary']['total_expenditure'])),
            ('Total Income', float(report['summary']['total_income'])),
            ('Expected Total Income', float(report['summary']['expected_total_income'])),
            ('Current Profit', float(report['summary']['current_profit'])),
            ('Expected Profit', float(report['summary']['expected_profit'])),
            ('Outstanding Amount', float(report['summary']['outstanding_amount'])),
            ('Current Profit Margin', float(report['summary']['profit_margin_current']) / 100),
            ('Expected Profit Margin', float(report['summary']['profit_margin_expected']) / 100),
        ]
        for i, (metric, value) in enumerate(summary_data, start=4):
            summary_sheet.write(i, 0, metric)
            fmt = percent_format if 'Margin' in metric else currency_format
            summary_sheet.write(i, 1, value, fmt)

        summary_sheet.set_column('A:A', 28)
        summary_sheet.set_column('B:B', 18)

        # Member sheet
        members_sheet = workbook.add_worksheet('Member Profits')
        headers = [
            'Member Name', 'Expenditure', 'Income Received', 'Expected Income',
            'Current Profit', 'Expected Profit', 'Outstanding Amount',
            'Total Requests', 'Active Requests', 'Completed Requests'
        ]
        for col, h in enumerate(headers):
            members_sheet.write(0, col, h, header_format)

        for row, m in enumerate(report['member_profits'], start=1):
            members_sheet.write(row, 0, m['member_name'])
            members_sheet.write(row, 1, float(m['expenditure']), currency_format)
            members_sheet.write(row, 2, float(m['income_received']), currency_format)
            members_sheet.write(row, 3, float(m['expected_income']), currency_format)
            members_sheet.write(row, 4, float(m['current_profit']), currency_format)
            members_sheet.write(row, 5, float(m['expected_profit']), currency_format)
            members_sheet.write(row, 6, float(m['outstanding_amount']), currency_format)
            members_sheet.write(row, 7, m['total_requests'])
            members_sheet.write(row, 8, m['active_requests'])
            members_sheet.write(row, 9, m['completed_requests'])

        members_sheet.set_column('A:A', 26)
        members_sheet.set_column('B:G', 16)
        members_sheet.set_column('H:J', 14)
        members_sheet.autofilter(0, 0, len(report['member_profits']), len(headers) - 1)
        members_sheet.freeze_panes(1, 0)

        workbook.close()
        output.seek(0)

        filename = f'project_finance_report_{timezone.localtime(timezone.now()).strftime("%Y%m%d_%H%M%S")}.xlsx'
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        return HttpResponse(f'Error: {str(e)}', status=500)


# ==========================================
# DJANGO VIEWS
# ==========================================

def _get_dates_from_request(request):
    """Helper function to safely parse dates from request.GET"""
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    start_date = None
    end_date = None
    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        return None, None
    return start_date, end_date

@staff_member_required
def project_finance_report_view(request):
    context = {}
    start_date, end_date = _get_dates_from_request(request)

    if request.GET.get('generate') or (start_date or end_date):
        try:
            report = generate_project_finance_report(start_date, end_date)
            context['report'] = report
            context['success'] = True
        except Exception as e:
            context['error'] = f"Error generating report: {str(e)}"

    return render(request, 'projectfinance/project_finance_report.html', context)


@staff_member_required
def project_finance_report_api(request):
    start_date, end_date = _get_dates_from_request(request)
    try:
        report = generate_project_finance_report(start_date, end_date)
        return JsonResponse(report, encoder=DjangoJSONEncoder, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@staff_member_required
def project_finance_report_excel(request):
    try:
        import xlsxwriter
    except ImportError:
        return HttpResponse('Excel generation requires XlsxWriter. Install with: pip install XlsxWriter', status=500)
    
    start_date, end_date = _get_dates_from_request(request)
    
    try:
        report = generate_project_finance_report(start_date, end_date)
        
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output)
        
        header_format = workbook.add_format({
            'bold': True, 'bg_color': '#2c3e50', 'font_color': 'white',
            'align': 'center', 'valign': 'vcenter', 'border': 1
        })
        currency_format = workbook.add_format({'num_format': '₦#,##0.00'})
        percent_format = workbook.add_format({'num_format': '0.00%'})
        
        # Summary sheet
        summary_sheet = workbook.add_worksheet('Summary')
        summary_sheet.write('A1', 'Financial Summary', header_format)
        summary_sheet.write('A3', 'Metric')
        summary_sheet.write('B3', 'Value')
        
        summary_data = [
            ('Total Expenditure', report['summary']['total_expenditure']),
            ('Total Income', report['summary']['total_income']),
            ('Expected Total Income', report['summary']['expected_total_income']),
            ('Current Profit', report['summary']['current_profit']),
            ('Expected Profit', report['summary']['expected_profit']),
            ('Outstanding Amount', report['summary']['outstanding_amount']),
            ('Current Profit Margin', report['summary']['profit_margin_current'] / 100),
            ('Expected Profit Margin', report['summary']['profit_margin_expected'] / 100),
            ('Collection Rate', report['summary']['collection_rate'] / 100)
        ]
        
        for i, (metric, value) in enumerate(summary_data):
            row = i + 4
            summary_sheet.write(f'A{row}', metric)
            if 'Margin' in metric or 'Rate' in metric:
                summary_sheet.write(f'B{row}', float(value), percent_format)
            else:
                summary_sheet.write(f'B{row}', float(value), currency_format)
        
        # Member profits sheet
        members_sheet = workbook.add_worksheet('Member Profits')
        
        headers = [
            'Member Name', 'Expenditure', 'Income Received', 'Expected Income',
            'Current Profit', 'Expected Profit', 'Outstanding Amount',
            'Total Requests', 'Active Requests', 'Completed Requests'
        ]
        
        for col, header in enumerate(headers):
            members_sheet.write(0, col, header, header_format)
        
        for row, member in enumerate(report['member_profits'], 1):
            members_sheet.write(row, 0, member['member_name'])
            members_sheet.write(row, 1, float(member['expenditure']), currency_format)
            members_sheet.write(row, 2, float(member['income_received']), currency_format)
            members_sheet.write(row, 3, float(member['expected_income']), currency_format)
            members_sheet.write(row, 4, float(member['current_profit']), currency_format)
            members_sheet.write(row, 5, float(member['expected_profit']), currency_format)
            members_sheet.write(row, 6, float(member['outstanding_amount']), currency_format)
            members_sheet.write(row, 7, member['total_requests'])
            members_sheet.write(row, 8, member['active_requests'])
            members_sheet.write(row, 9, member['completed_requests'])
        
        summary_sheet.set_column('A:A', 25)
        summary_sheet.set_column('B:B', 15)
        members_sheet.set_column('A:A', 25)
        members_sheet.set_column('B:G', 15)
        members_sheet.set_column('H:J', 12)
        
        workbook.close()
        
        output.seek(0)
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        filename = f'project_finance_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
    except Exception as e:
        return HttpResponse(f'Error: {str(e)}', status=500)
# ==========================================
# SIMPLE TEST VIEW (Optional - for testing)
# ==========================================

@staff_member_required
def simple_report_test(request):
    """
    Simple view to test the report generation without template
    """
    try:
        report = generate_project_finance_report()
        return JsonResponse({
            'status': 'success',
            'total_expenditure': str(report['summary']['total_expenditure']),
            'total_income': str(report['summary']['total_income']),
            'current_profit': str(report['summary']['current_profit']),
            'member_count': len(report['member_profits'])
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})



@login_required
def upload_project_finance_repayment(request):
    if request.method == "POST":
        file = request.FILES.get("file")

        if not file:
            messages.error(request, "Please upload an Excel file.")
            return redirect('upload_project_finance_payment')

        try:
            # Read Excel file
            df = pd.read_excel(file)

            # Normalize column names
            df_columns = {col.strip().lower(): col.strip() for col in df.columns}
            required_columns_lower = ["ippis", "amount paid", "month"]

            # Validate required columns
            for col in required_columns_lower:
                if col not in df_columns:
                    found_columns = ", ".join(df.columns)
                    messages.error(request, f"Missing required column: '{col.title()}'. Found columns: {found_columns}")
                    return redirect('upload_project_finance_payment')

            # Get column names
            ippis_col = df_columns["ippis"]
            amount_paid_col = df_columns["amount paid"]
            month_col = df_columns["month"]

            successful_uploads = 0
            skipped_payments = []

            with transaction.atomic():
                for index, row in df.iterrows():
                    row_number = index + 1

                    # --- Validate IPPIS ---
                    ippis = str(row[ippis_col]).strip()
                    if not ippis or ippis.lower() in ['nan', 'none', '']:
                        skipped_payments.append({
                            "row": row_number,
                            "ippis": ippis or "Empty",
                            "reason": "IPPIS is empty or invalid"
                        })
                        continue

                    # --- Validate Amount Paid ---
                    try:
                        amount_str = str(row[amount_paid_col]).strip().replace('₦', '').replace(',', '').replace(' ', '')
                        amount_paid = Decimal(amount_str)

                        if amount_paid <= 0:
                            skipped_payments.append({
                                "row": row_number,
                                "ippis": ippis,
                                "reason": f"Invalid amount: {amount_paid}. Must be greater than 0"
                            })
                            continue
                    except (ValueError, InvalidOperation):
                        skipped_payments.append({
                            "row": row_number,
                            "ippis": ippis,
                            "reason": f"Invalid amount format: '{row[amount_paid_col]}'"
                        })
                        continue

                    # --- Validate Month ---
                    try:
                        month = pd.to_datetime(row[month_col]).date()
                    except (ValueError, TypeError):
                        skipped_payments.append({
                            "row": row_number,
                            "ippis": ippis,
                            "reason": f"Invalid date format: '{row[month_col]}'"
                        })
                        continue

                    # --- Find Active Finance Request ---
                    try:
                       request_obj = ProjectFinanceRequest.objects.select_related("application__member").annotate(
                        total_paid=Coalesce(
                            Sum('payments__amount_paid'),   # ✅ FIXED HERE
                            Decimal('0')
                        ),
                        remaining_balance=F('total_repayment_amount') - F('total_paid')
                    ).get(
                        application__member__ippis=ippis,
                        status__in=["Approved", "Pending"]
                    )

                    except ProjectFinanceRequest.DoesNotExist:
                        all_requests = ProjectFinanceRequest.objects.filter(application__member__ippis=ippis)
                        if all_requests.exists():
                            statuses = list(all_requests.values_list('status', flat=True))
                            skipped_payments.append({
                                "row": row_number,
                                "ippis": ippis,
                                "reason": f"No active request found. Existing statuses: {', '.join(statuses)}"
                            })
                        else:
                            skipped_payments.append({
                                "row": row_number,
                                "ippis": ippis,
                                "reason": "No finance request found for this IPPIS"
                            })
                        continue
                    except ProjectFinanceRequest.MultipleObjectsReturned:
                        skipped_payments.append({
                            "row": row_number,
                            "ippis": ippis,
                            "reason": "Multiple active requests found for this IPPIS"
                        })
                        continue

                    # --- Check for Existing Payment ---
                    if ProjectFinancePayment.objects.filter(
                        request=request_obj,
                        month__year=month.year,
                        month__month=month.month
                    ).exists():
                        skipped_payments.append({
                            "row": row_number,
                            "ippis": ippis,
                            "reason": f"Payment already exists for {month.strftime('%B %Y')}"
                        })
                        continue

                    # --- Check Fully Paid Status ---
                    if request_obj.remaining_balance <= 0:
                        skipped_payments.append({
                            "row": row_number,
                            "ippis": ippis,
                            "reason": f"Request fully paid (Total: ₦{request_obj.total_repayment_amount:,.2f}, Paid: ₦{request_obj.total_paid:,.2f})"
                        })
                        continue

                    # --- Check Overpayment ---
                    if amount_paid > request_obj.remaining_balance:
                        skipped_payments.append({
                            "row": row_number,
                            "ippis": ippis,
                            "reason": f"Payment ₦{amount_paid:,.2f} exceeds remaining balance ₦{request_obj.remaining_balance:,.2f}"
                        })
                        continue

                    # --- Save Payment ---
                    try:
                        ProjectFinancePayment.objects.create(
                            request=request_obj,
                            amount_paid=amount_paid,
                            month=month,
                        )

                        # Update request status if fully paid
                        new_total_paid = request_obj.total_paid + amount_paid
                        if new_total_paid >= request_obj.total_repayment_amount:
                            request_obj.status = "FullyPaid"
                            request_obj.save()

                        successful_uploads += 1

                    except Exception as save_error:
                        skipped_payments.append({
                            "row": row_number,
                            "ippis": ippis,
                            "reason": f"Database error: {str(save_error)}"
                        })
                        continue

                # --- Store Results in Session ---
                request.session['upload_results'] = {
                    'successful_uploads': successful_uploads,
                    'skipped_payments': skipped_payments,
                    'total_rows': len(df)
                }

                # --- Messages ---
                if successful_uploads > 0:
                    messages.success(request, f"Successfully uploaded {successful_uploads} payments!")
                if skipped_payments:
                    messages.warning(request, f"{len(skipped_payments)} payments were skipped.")
                if successful_uploads == 0 and skipped_payments:
                    messages.error(request, "No payments were uploaded. All rows had errors.")

        except Exception as e:
            messages.error(request, f"Error processing file: {str(e)}")

        return redirect('upload_project_finance_payment')

    # --- GET Request ---
    upload_results = request.session.pop('upload_results', None)
    context = {'skipped_payments': upload_results['skipped_payments'] if upload_results else []}
    return render(request, "projectfinance/upload_project_finance_payment.html", context)


