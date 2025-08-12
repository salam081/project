import os
import pandas as pd
import calendar
from django.shortcuts import render, redirect,get_object_or_404
from django.http import HttpResponse,HttpResponseRedirect
from django.http import JsonResponse, HttpResponseNotAllowed
from django.core.exceptions import ObjectDoesNotExist
from decimal import Decimal,DecimalException
from datetime import datetime
from django.db import transaction
from datetime import timedelta
from django.db.models import Q, Sum
from django.core.paginator import Paginator
from django.utils import timezone
from django.conf import settings
from django.contrib import messages
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.db.models import Sum,F
from django.db.models.functions import ExtractMonth, ExtractYear
from django.utils.dateparse import parse_date
# from accounts.decorator import group_required
from .models import * 
from loan.models import * 
from accounts.models import * 
from consumable.models import * 
# from financialsummary.models import *
from .forms import *
from datetime import datetime



import os
import pandas as pd
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.shortcuts import render, redirect
from django.db import transaction, IntegrityError

# Assuming these models are correctly imported from your apps
from accounts.models import Member
from .models import Savings

# def upload_savings(request):
#     """
#     An optimized view for uploading savings data from an Excel file.
    
#     This view skips members who already have a savings record for the specified month
#     and adds new records in a single, efficient bulk operation.
#     """
#     if request.method == "POST" and request.FILES.get("excel_file"):
#         excel_file = request.FILES["excel_file"]
#         selected_month = request.POST.get("month")

#         # --- Initial Validation and Setup ---
#         if not selected_month:
#             messages.error(request, "Please select a month before uploading.")
#             return redirect(request.path)
        
#         try:
#             month_date = datetime.strptime(selected_month, "%Y-%m").date().replace(day=1)
#             # Corrected the engine name from 'openyxl' to 'openpyxl'
#             df = pd.read_excel(excel_file, engine="openpyxl")

#             if df.empty:
#                 messages.error(request, "The uploaded file is empty.")
#                 return redirect(request.path)

#             required_columns = {"ippis", "amount"}
#             if not required_columns.issubset(df.columns):
#                 messages.error(request, "Excel must contain 'ippis' and 'amount' columns.")
#                 return redirect(request.path)
            
#             # --- Data Processing and Filtering ---
#             # Drop rows with missing essential data
#             df = df.dropna(subset=['ippis', 'amount'])
            
#             # Extract all unique IPPIS numbers from the uploaded file
#             ippis_list = df['ippis'].tolist()
            
#             # Perform a single, efficient query to find all members who already have
#             # a savings record for the selected month.
#             existing_savings_members = Savings.objects.filter(
#                 member__ippis__in=ippis_list,
#                 month=month_date
#             ).values_list('member__ippis', flat=True)
            
#             # Convert the list to a set for fast O(1) lookups
#             existing_ippis_set = set(existing_savings_members)

#             # Get all members from the uploaded file in a single query
#             all_members = {m.ippis: m for m in Member.objects.filter(ippis__in=ippis_list)}

#             savings_to_create = []
#             skipped_rows = 0

#             # Iterate through the DataFrame to prepare new Savings objects
#             for _, row in df.iterrows():
#                 try:
#                     ippis = int(row.get("ippis"))
#                     amount = Decimal(str(row.get("amount")))
                    
#                     # Skip the row if a savings record already exists for this member/month
#                     if ippis in existing_ippis_set:
#                         skipped_rows += 1
#                         continue

#                     # Skip the row if the member's IPPIS is not in the database
#                     member = all_members.get(ippis)
#                     if member:
#                         savings_to_create.append(
#                             Savings(
#                                 member=member,
#                                 month=month_date,
#                                 month_saving=amount,
#                                 original_amount=amount 
#                             )
#                         )
#                     else:
#                         skipped_rows += 1
#                 except (ValueError, TypeError):
#                     # Skip rows with invalid data types
#                     skipped_rows += 1

#             # Use a database transaction to ensure all or none of the new savings are created
#             with transaction.atomic():
#                 # Perform the bulk creation, inserting all objects in one query
#                 Savings.objects.bulk_create(savings_to_create, batch_size=500)

#             total_added = len(savings_to_create)

#             # Update each member's total savings for the newly added records.
#             for savings_obj in savings_to_create:
#                 savings_obj.member.update_total_savings()
            
#             messages.success(request, f"Upload complete: {total_added} records added successfully. {skipped_rows} records were skipped (due to existing records, errors, or unmatched members).")
#             return redirect(request.path)

#         except Exception as e:
#             messages.error(request, f"Error processing file: {str(e)}")
#             return redirect(request.path)

#     return render(request, "savings/upload_savings.html")

def index(request):
    context = {}
    return render(request, "savings/index.html", context)

def search_member_for_savings(request):
    groups = UserGroup.objects.all().order_by('title')
    results = []
    search_term = request.GET.get('search_term', '').strip()
    if search_term:
        results = Member.objects.select_related('member').filter(
            Q(member__first_name__icontains=search_term) |
            Q(member__last_name__icontains=search_term) |
            Q(ippis__icontains=search_term) |
            Q(id__icontains=search_term)
        ).order_by('member__first_name', 'member__last_name')

        paginator = Paginator(results, 100)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
    else:
        page_obj = []

    context = {
        'results': page_obj,
        'search_term': search_term,
        'groups':groups
    }
    return render(request, 'savings/search_member.html', context)


def filter_requests(datefrom, dateto):
    filtered_requests = Savings.objects.all().order_by('-date_created')
    
    if datefrom:
        filtered_requests = filtered_requests.filter(month__gte=datefrom)
    if dateto:
        filtered_requests = filtered_requests.filter(month__lte=dateto)
    return filtered_requests


def all_member_saving_search(request):
    
    datefrom = request.GET.get('datefrom')
    dateto = request.GET.get('dateto')
    page_number = request.GET.get('page')

    member = None
    page_total = 0
    grand_total = 0
    total_savings = 0
    total_deductions = 0

    if datefrom or dateto:
        filtered = filter_requests(datefrom, dateto)
        paginator = Paginator(filtered, 100)  # paginate 100 per page
        member = paginator.get_page(page_number)

        # Total for this page
        page_total = sum(item.month_saving for item in member.object_list)

        # Grand total for all filtered savings
        grand_total = filtered.aggregate(total=Sum('month_saving'))['total'] or 0

        total_savings = grand_total

        total_deductions = filtered.aggregate(deduct=Sum('original_amount'))['deduct'] or 0
        print(total_deductions)
    context = {'member': member,'datefrom': datefrom,'dateto': dateto,
        'page_total': page_total,'grand_total': grand_total,
        'total_savings': total_savings,'total_deductions': total_deductions,}

    return render(request, 'savings/all_member_saving_search.html', context)


def add_individual_member_savings(request, id):
    member = get_object_or_404(Member, id=id)
    if request.method == 'POST':
        month_str = request.POST.get('month')
        month_saving_str = request.POST.get('month_saving')

        if not month_str or not month_saving_str:
            messages.error(request, "Please provide both the month and the saving amount.")
        else:
            try:
                month = timezone.datetime.strptime(month_str, '%Y-%m-%d').date()
                month_saving = float(month_saving_str)

                if Savings.objects.filter(member=member, month=month).exists():
                    messages.warning(request, f"Savings for {member.member} for {month.strftime('%Y-%m-%d')} already exists.")
                else:
                    Savings.objects.create(member=member, month=month, month_saving=month_saving)
                    messages.success(request, f"Savings for {member.member} added successfully.")
                    return redirect('add_individual_savings', id=id)
            except ValueError:
                messages.error(request, "Invalid date format or saving amount.")

    context = {'member': member,}
    return render(request, 'savings/add_individual_savings.html', context)


from django.contrib import messages
from decimal import Decimal
from datetime import datetime
import pandas as pd
from django.core.files.base import ContentFile
from django.db import transaction
import os

def upload_savings(request):
    if request.method == "POST" and request.FILES.get("excel_file"):
        excel_file = request.FILES["excel_file"]
        selected_month = request.POST.get("month")

        if not selected_month:
            messages.error(request, "Please select a month before uploading.")
            return redirect(request.path)

        try:
            month_date = datetime.strptime(selected_month, "%Y-%m").date().replace(day=1)

            relative_path = default_storage.save(f"upload/{excel_file.name}", ContentFile(excel_file.read()))
            absolute_path = os.path.join(settings.MEDIA_ROOT, relative_path)

            df = pd.read_excel(absolute_path, engine="openpyxl")
            default_storage.delete(relative_path)

            if df.empty:
                messages.error(request, "The uploaded file is empty.")
                return redirect(request.path)

            required_columns = {"ippis", "amount"}
            if not required_columns.issubset(df.columns):
                messages.error(request, "Excel must contain: ippis, amount.")
                return redirect(request.path)

            total_added = 0
            total_skipped = 0
            skipped_ippis = []

            with transaction.atomic():
                for _, row in df.iterrows():
                    ippis = row.get("ippis")
                    amount = row.get("amount")

                    if pd.isna(ippis) or pd.isna(amount):
                        total_skipped += 1
                        continue

                    try:
                        ippis = int(ippis)
                        amount = Decimal(str(amount))
                    except ValueError:
                        total_skipped += 1
                        continue

                    member = Member.objects.filter(ippis=ippis).first()
                    if not member:
                        total_skipped += 1
                        continue

                    savings, created = Savings.objects.get_or_create(
                        member=member,
                        month=month_date,
                        defaults={
                            "month_saving": amount,
                            "original_amount": amount,
                        }
                    )

                    if created:
                        total_added += 1
                    else:
                        skipped_ippis.append(ippis)
                        total_skipped += 1

            # Skipped IPPIS message (informational)
            if skipped_ippis:
                skipped_str = ", ".join(map(str, skipped_ippis))
                messages.warning(
                    request,
                    f"Skipped {total_skipped} entries — either record already exists for the month  {month_date.strftime('%B %Y')}: or the row is invalid or incomplete.  {skipped_str}."
                )

            # Final result message
            if total_added > 0 and total_skipped == 0:
                messages.success(request, f"{total_added} savings records uploaded successfully.")
            elif total_added > 0 and total_skipped > 0:
                messages.success(request, f"{total_added} uploaded successfully, {total_skipped} skipped.")
            elif total_added == 0 and total_skipped > 0:
                messages.info(request, f"All {total_skipped} records skipped.for {month_date.strftime('%B %Y')}: No new savings added.")
            else:
                messages.error(request, "No records processed. Please check the file.")

            return redirect(request.path)

        except Exception as e:
            messages.error(request, f"Error processing file: {str(e)}")
            return redirect(request.path)

    return render(request, "savings/upload_savings.html")



def get_upload_savings(request):
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    savings = Savings.objects.all()

    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d')
            savings = savings.filter(month__gte=date_from_parsed)
        except ValueError:
            pass

    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d')
            savings = savings.filter(month__lte=date_to_parsed)
        except ValueError:
            pass

    months = savings.annotate(
        month_num=ExtractMonth("month"),
        year_num=ExtractYear("month")
    ).values("month_num", "year_num").distinct()

    data = [
        {"num": m["month_num"], "year": m["year_num"], "name": calendar.month_name[m["month_num"]]}
        for m in months if m["month_num"]
    ]

    # Sort by year then month (optional)
    data.sort(key=lambda x: (x["year"], x["num"]))

    # Paginator setup
    paginator = Paginator(data, 12)  
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "savings/get_upload_savings.html", {"page_obj": page_obj,"date_from": date_from,"date_to": date_to})



def get_upload_details(request, month):
    savings_list = Savings.objects.filter(month__month=month)
    paginator = Paginator(savings_list, 100) 
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(request,"savings/get_upload_savings_details.html",{"page_obj": page_obj})


def delete_saving(request, month):
    savings_qs = Savings.objects.filter(month__month=month)
    affected_member = set(saving.member for saving in savings_qs)
    savings_qs.delete()
    for member in affected_member:
        member.update_total_savings()

    messages.success(request, f"Deleted savings records for {calendar.month_name[month]} .")    
    return redirect("get_upload_savings")




def interest_form_view(request):
    return render(request, 'savings/deduct_interest_form.html')

def deduct_monthly_interest(request):
    if request.method == 'POST':
        deduction_amount_str = request.POST.get('deduction_amount')
        month_str = request.POST.get('month')  # Format: 'YYYY-MM'

        if not deduction_amount_str or not month_str:
            messages.error(request, "Please enter both the month and deduction amount.")
            return redirect('interest_form')

        try:
            year, month = map(int, month_str.split('-'))
        except ValueError:
            messages.error(request, "Invalid month format.")
            return redirect('interest_form')

        try:
            deduction_amount = Decimal(deduction_amount_str)
            if deduction_amount <= Decimal("0.00"):
                messages.error(request, "Deduction amount must be greater than zero.")
                return redirect('interest_form')
        except DecimalException:
            messages.error(request, "Invalid deduction amount.")
            return redirect('interest_form')

        savings_this_month = Savings.objects.filter(month__year=year, month__month=month)
        count = 0

        for saving in savings_this_month:
            member = saving.member
            already_deducted = Interest.objects.filter(member=member, month=saving.month).exists()

            if not already_deducted and saving.month_saving >= deduction_amount:
                if saving.original_amount is None:
                    saving.original_amount = saving.month_saving

                saving.month_saving -= deduction_amount
                saving.save()

                Interest.objects.create(member=member, month=saving.month, amount_deducted=deduction_amount)
                count += 1

        if count:
            messages.success(request, f"₦{deduction_amount} deducted from {count} members for {calendar.month_name[month]} {year}.")
            return redirect('interest_form')
        else:
            messages.info(request, f"No deductions made for {calendar.month_name[month]} {year}. Either already deducted .")
            return redirect('interest_form')

    return redirect('interest_form')


#========== distribute saving ===================

def distribute_savings(year, month, distribution_ratios=None):
    if distribution_ratios is None:
        distribution_ratios = {"loanable": Decimal("0.50"), "investment": Decimal("0.50")}

    savings_this_month = Savings.objects.filter(month__year=year, month__month=month)

    if not savings_this_month.exists():
        return "no_savings"

    distributed_count = 0

    for saving in savings_this_month:
        member = saving.member

        already_loanable = Loanable.objects.filter(member=member, month=saving.month).exists()
        already_investment = Investment.objects.filter(member=member, month=saving.month).exists()

        if already_loanable or already_investment:
            continue  # Skip this member, already distributed

        total = saving.month_saving

        loanable_amount = total * distribution_ratios.get("loanable", Decimal("0.00"))
        investment_amount = total * distribution_ratios.get("investment", Decimal("0.00"))

        Loanable.objects.create( member=member, month=saving.month, amount=loanable_amount,total_amount=total)
        Investment.objects.create( member=member, month=saving.month, amount=investment_amount, total_amount=total)

        distributed_count += 1

    return distributed_count


def distribute_savings_form(request):
    if request.method == "POST":
        month_str = request.POST.get("month")

        if not month_str:
            messages.error(request, "Please select a month.")
            return render(request, "savings/distribute_savings_form.html")

        try:
            year, month = map(int, month_str.split("-"))
        except ValueError:
            messages.error(request, "Invalid month format.")
            return render(request, "savings/distribute_savings_form.html")

        distribution_ratios = {"loanable": Decimal("0.50"), "investment": Decimal("0.50")}
        result = distribute_savings(year, month, distribution_ratios)

        if result == "exists":
            messages.warning(request, f"Savings distribution for {calendar.month_name[month]} {year} already exists.")
        elif result == "no_savings":
            messages.warning(request, f"No savings found for {calendar.month_name[month]} {year}.")
        else:
            messages.success(request, f"Savings for {calendar.month_name[month]} {year} distributed to {result} member(s).")

        return redirect("loanable_investment_months")

    return render(request, "savings/distribute_savings_form.html")


def distribute_savings_view(request, year, month):
    # This view is no longer directly called from a URL, the distribution happens in the form view
    return HttpResponse(f"Distribution initiated for {calendar.month_name[month]} {year}. Check messages for status.")

#============== distribute saving end ===============


#============== loanable investment start ===============
def loanable_investment_months(request):
    """
    Collect all distinct months from Loanable and Investment tables,
    merge and sort them for display.
    """
    # Get distinct months from Loanable
    loanable_months = Loanable.objects.annotate(
        year=ExtractYear("month"), month_num=ExtractMonth("month")
    ).values("year", "month_num").distinct()

    # Get distinct months from Investment
    investment_months = Investment.objects.annotate(
        year=ExtractYear("month"), month_num=ExtractMonth("month")
    ).values("year", "month_num").distinct()

    # Combine and deduplicate months
    all_months_set = {
        (item["year"], item["month_num"]) for item in loanable_months
    } | {
        (item["year"], item["month_num"]) for item in investment_months
    }

    # Convert to sorted list of dicts with month names
    all_months = sorted(
        [
            {
                "year": year,
                "month_num": month,
                "month": calendar.month_name[month] if 1 <= month <= 12 else "Invalid"
            }
            for year, month in all_months_set
        ],
        key=lambda x: (x["year"], x["month_num"]),
        reverse=True
    )

    # Add pagination (10 items per page or adjust as needed)
    paginator = Paginator(all_months, 100)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "savings/loanable_investment_months.html", {"all_months": page_obj,   "page_obj": page_obj    })


def loanable_investment_details(request, year, month):
    # Filter by year and month
    loanables_qs = Loanable.objects.filter(month__year=year, month__month=month)
    investments_qs = Investment.objects.filter(month__year=year, month__month=month)

    # Totals
    total_loanable = loanables_qs.aggregate(total=Sum("amount"))["total"] or 0
    total_investment = investments_qs.aggregate(total=Sum("amount"))["total"] or 0

    # Paginate Loanables
    loanable_paginator = Paginator(loanables_qs, 100)
    loanable_page_number = request.GET.get("loanable_page")
    loanables = loanable_paginator.get_page(loanable_page_number)

    # Paginate Investments
    investment_paginator = Paginator(investments_qs, 100)
    investment_page_number = request.GET.get("investment_page")
    investments = investment_paginator.get_page(investment_page_number)

    context = {
        "loanables": loanables,
        "investments": investments,
        "month_name": calendar.month_name[month] if 1 <= month <= 12 else "Invalid",
        "year": year,
        "total_loanable": total_loanable,
        "total_investment": total_investment,
        "loanable_page_obj": loanables,
        "investment_page_obj": investments,
    }

    return render(request, "savings/loanable_investment_details.html", context)

def delete_month_entries(request, year, month):
    if request.method == "POST":
        Loanable.objects.filter(month__year=year, month__month=month).delete()
        Investment.objects.filter(month__year=year, month__month=month).delete()
        messages.success(request, f"Deleted records for {calendar.month_name[month]} {year}.")
    return redirect("loanable_investment_months")



#============== loanable investment end ===============


def get_upload_interest(request):
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    interest = Interest.objects.all()

    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d')
            interest = interest.filter(month__gte=date_from_parsed)
        except ValueError:
            pass

    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d')
            interest = interest.filter(month__lte=date_to_parsed)
        except ValueError:
            pass

    months = interest.annotate(
        month_num=ExtractMonth("month"),
        year_num=ExtractYear("month")
    ).values("month_num", "year_num").distinct()

    data = [
        {"num": m["month_num"], "year": m["year_num"], "name": calendar.month_name[m["month_num"]]}
        for m in months if m["month_num"]
    ]

    # Sort by year then month (optional)
    data.sort(key=lambda x: (x["year"], x["num"]))

    # Paginator setup
    paginator = Paginator(data, 100) 
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "savings/get_upload_interest.html", {"page_obj": page_obj,"date_from": date_from,"date_to": date_to})


def get_upload_interest_details(request, month):
    interest_list = Interest.objects.filter(month__month=month)
    paginator = Paginator(interest_list, 100)  # Show 10 items per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(request,"savings/get_upload_interest_details.html",{"page_obj": page_obj})


def delete_interest_saving(request, year, month):
    if request.method == "POST":
        interest_qs = Interest.objects.select_related("member").filter(month__year=year, month__month=month)
        
        affected_members = {interest.member for interest in interest_qs}
        interest_qs.delete()

        for member in affected_members:
            member.update_total_savings()  # Optimize this method if it's slow

        messages.success(request, f"Deleted interest savings for {calendar.month_name[month]} {year}.")

    return redirect("get_upload_interest")





def combined_upload_view(request):
    """
    Combined view for savings months, loanable/investment months, and interest details
    """
    # Get the active tab from request
    active_tab = request.GET.get('tab', 'savings')
    
    context = {
        'active_tab': active_tab,
    }
    
    if active_tab == 'savings':
        # Savings months logic
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')

        savings = Savings.objects.all()

        if date_from:
            try:
                date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d')
                savings = savings.filter(month__gte=date_from_parsed)
            except ValueError:
                pass

        if date_to:
            try:
                date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d')
                savings = savings.filter(month__lte=date_to_parsed)
            except ValueError:
                pass

        months = savings.annotate(
            month_num=ExtractMonth("month"),
            year_num=ExtractYear("month")
        ).values("month_num", "year_num").distinct()

        data = [
            {"num": m["month_num"], "year": m["year_num"], "name": calendar.month_name[m["month_num"]]}
            for m in months if m["month_num"]
        ]

        # Sort by year then month
        data.sort(key=lambda x: (x["year"], x["num"]))

        # Paginator setup
        paginator = Paginator(data, 12)  
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context.update({
            'savings_page_obj': page_obj,
            'date_from': date_from,
            'date_to': date_to
        })

    elif active_tab == 'loanable_investment':
        # Loanable/Investment months logic
        # Get distinct months from Loanable
        loanable_months = Loanable.objects.annotate(
            year=ExtractYear("month"), month_num=ExtractMonth("month")
        ).values("year", "month_num").distinct()

        # Get distinct months from Investment
        investment_months = Investment.objects.annotate(
            year=ExtractYear("month"), month_num=ExtractMonth("month")
        ).values("year", "month_num").distinct()

        # Combine and deduplicate months
        all_months_set = {
            (item["year"], item["month_num"]) for item in loanable_months
        } | {
            (item["year"], item["month_num"]) for item in investment_months
        }

        # Convert to sorted list of dicts with month names
        all_months = sorted(
            [
                {
                    "year": year,
                    "month_num": month,
                    "month": calendar.month_name[month] if 1 <= month <= 12 else "Invalid"
                }
                for year, month in all_months_set
            ],
            key=lambda x: (x["year"], x["month_num"]),
            reverse=True
        )

        # Add pagination
        paginator = Paginator(all_months, 12)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context.update({
            'loanable_investment_page_obj': page_obj
        })

    elif active_tab == 'interest':
        # Interest months logic (similar to savings)
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')

        interest = Interest.objects.all()

        if date_from:
            try:
                date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d')
                interest = interest.filter(month__gte=date_from_parsed)
            except ValueError:
                pass

        if date_to:
            try:
                date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d')
                interest = interest.filter(month__lte=date_to_parsed)
            except ValueError:
                pass

        months = interest.annotate(
            month_num=ExtractMonth("month"),
            year_num=ExtractYear("month")
        ).values("month_num", "year_num").distinct()

        data = [
            {"num": m["month_num"], "year": m["year_num"], "name": calendar.month_name[m["month_num"]]}
            for m in months if m["month_num"]
        ]

        # Sort by year then month
        data.sort(key=lambda x: (x["year"], x["num"]))

        # Paginator setup
        paginator = Paginator(data, 12)  
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context.update({
            'interest_page_obj': page_obj,
            'date_from': date_from,
            'date_to': date_to
        })

    return render(request, "savings/combined_upload.html", context)