from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from .models import User

def portal_selection(request):
    """Renders the glassmorphic portal picker page."""
    if request.user.is_authenticated:
        if request.user.role == User.BUYER:
            return redirect('buyer_dashboard')
        elif request.user.role == User.ADMIN or request.user.is_superuser:
            return redirect('/admin/')
    return render(request, 'accounts/portal_selection.html')

def buyer_login(request):
    """Handles authentication checks for the Buyer Portal."""
    if request.user.is_authenticated:
        if request.user.role == User.BUYER:
            return redirect('buyer_dashboard')
        logout(request) # Log out other roles before logging in as Buyer

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not username or not password:
            messages.error(request, 'Please provide both username/email/phone and password.')
            return render(request, 'accounts/buyer_login.html')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.role == User.BUYER:
                if user.status == User.ACTIVE:
                    login(request, user)
                    return redirect('buyer_dashboard')
                elif user.status == User.PENDING:
                    messages.error(request, 'Your buyer profile status is pending administrative approval.')
                else:
                    messages.error(request, 'Your buyer profile has been suspended.')
            else:
                messages.error(request, 'Invalid credentials for the Buyer portal.')
        else:
            messages.error(request, 'Invalid login credentials.')

    return render(request, 'accounts/buyer_login.html')

@login_required(login_url='portal_selection')
def buyer_dashboard(request):
    """Displays the Buyer Portal Dashboard if role matches."""
    if request.user.role != User.BUYER:
        # If user is superuser admin, we let them view it for debugging, otherwise deny
        if not request.user.is_superuser:
            raise PermissionDenied("You do not have access to this portal.")
    return render(request, 'accounts/buyer_dashboard.html')

def logout_view(request):
    """Logs out the user and redirects to the landing selection portal."""
    logout(request)
    return redirect('portal_selection')

def landowner_login(request):
    """Handles authentication checks for the Land Owner Portal."""
    if request.user.is_authenticated:
        if request.user.role == User.LAND_OWNER:
            return redirect('landowner_dashboard')
        logout(request)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not username or not password:
            messages.error(request, 'Please provide both username/email/phone and password.')
            return render(request, 'accounts/landowner_login.html')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.role == User.LAND_OWNER:
                if user.status == User.ACTIVE:
                    login(request, user)
                    return redirect('landowner_dashboard')
                elif user.status == User.PENDING:
                    messages.error(request, 'Your landowner profile status is pending administrative approval.')
                else:
                    messages.error(request, 'Your landowner profile has been suspended.')
            else:
                messages.error(request, 'Invalid credentials for the Land Owner portal.')
        else:
            messages.error(request, 'Invalid login credentials.')

    return render(request, 'accounts/landowner_login.html')

@login_required(login_url='portal_selection')
def landowner_dashboard(request):
    """Displays the Land Owner Portal Dashboard if role matches."""
    if request.user.role != User.LAND_OWNER:
        if not request.user.is_superuser:
            raise PermissionDenied("You do not have access to this portal.")
    return render(request, 'accounts/landowner_dashboard.html')
