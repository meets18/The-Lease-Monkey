import os
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from .models import Land, Plot

User = get_user_model()

def lands_directory(request):
    """Renders the catalog list of available land properties."""
    lands = Land.objects.all()
    return render(request, 'lands/directory.html', {'lands': lands})

def plot_viewer(request, slug):
    """Renders the fullscreen dynamic plot viewer for the specific land site."""
    land = get_object_or_404(Land, slug=slug)
    context = {
        'land': land,
        'google_maps_api_key': os.getenv('GOOGLE_MAPS_API_KEY', '')
    }
    return render(request, 'lands/plot_viewer.html', context)

@login_required
def create_land(request):
    """Processes creation of new land from Admin dashboard."""
    # Ensure only admins or superusers can create land
    if request.user.role != 'ADMIN' and not request.user.is_superuser:
        raise PermissionDenied("You do not have permission to add new land.")

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        owner_username = request.POST.get('owner', '').strip()
        location = request.POST.get('location', '').strip()
        area = request.POST.get('area', '').strip()
        average_plot_price = request.POST.get('average_plot_price', '').strip()

        if not name or not owner_username or not location or not area or not average_plot_price:
            messages.error(request, "All fields are required to register a new land.")
            return redirect('admin_dashboard')

        try:
            owner = User.objects.get(username=owner_username, role='LAND_OWNER')
        except User.DoesNotExist:
            messages.error(request, "The selected Land Owner does not exist.")
            return redirect('admin_dashboard')

        try:
            land = Land.objects.create(
                name=name,
                owner=owner,
                location=location,
                area=area,
                average_plot_price=average_plot_price
            )
            messages.success(request, f"Land '{land.name}' has been successfully created.")
        except Exception as e:
            messages.error(request, f"Error creating land: {str(e)}")

    return redirect('admin_dashboard')

@login_required
def land_creator(request):
    """Renders the interactive Leaflet drawing workspace to outline land boundary."""
    if request.user.role != 'ADMIN' and not request.user.is_superuser:
        raise PermissionDenied("You do not have permission to access the plotting board.")

    context = {
        'name': request.GET.get('name', ''),
        'owner': request.GET.get('owner', ''),
        'location': request.GET.get('location', ''),
        'price': request.GET.get('price', ''),
    }
    return render(request, 'lands/creator.html', context)

@login_required
def save_land_layout(request):
    """Processes AJAX POST containing JSON layout parameters to register a Land."""
    if request.user.role != 'ADMIN' and not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            owner_username = data.get('owner', '').strip()
            location = data.get('location', '').strip()
            area = data.get('area')
            average_plot_price = data.get('price')
            boundary_coordinates = data.get('boundary_coordinates')

            if not name or not owner_username or not location or not area or not average_plot_price or not boundary_coordinates:
                return JsonResponse({'error': 'All fields and coordinates are required.'}, status=400)

            try:
                owner = User.objects.get(username=owner_username, role='LAND_OWNER')
            except User.DoesNotExist:
                return JsonResponse({'error': 'The selected landowner does not exist.'}, status=400)

            # Compute boundary centroid for map center coordinate
            lats = [pt[0] for pt in boundary_coordinates]
            lngs = [pt[1] for pt in boundary_coordinates]
            center_lat = sum(lats) / len(lats)
            center_lng = sum(lngs) / len(lngs)

            land = Land.objects.create(
                name=name,
                owner=owner,
                location=location,
                area=area,
                average_plot_price=average_plot_price,
                boundary_coordinates=boundary_coordinates,
                center_lat=center_lat,
                center_lng=center_lng,
                zoom_level=17
            )
            messages.success(request, f"Land '{land.name}' successfully plotted and registered.")
            return JsonResponse({'success': True, 'redirect_url': f'/lands/plots-creator/{land.slug}/'})
        except Exception as e:
            return JsonResponse({'error': f"Error registering land: {str(e)}"}, status=500)

    return JsonResponse({'error': 'Invalid request method.'}, status=400)

@login_required
def plot_creator(request, slug):
    """Renders the workspace to draw individual plot shapes inside a registered land boundary."""
    if request.user.role != 'ADMIN' and not request.user.is_superuser:
        raise PermissionDenied("You do not have permission to access the plot creator.")

    land = get_object_or_404(Land, slug=slug)
    plots = land.plots.all()
    return render(request, 'lands/plots_creator.html', {'land': land, 'plots': plots})

@login_required
def save_plot_layout(request, slug):
    """Processes AJAX POST containing JSON layout parameters to register a Plot."""
    if request.user.role != 'ADMIN' and not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    land = get_object_or_404(Land, slug=slug)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            plot_number = data.get('plot_number', '').strip()
            area = data.get('area', '').strip()
            price = data.get('price')
            facing = data.get('facing', 'North')
            status = data.get('status', 'available')
            coordinates = data.get('coordinates')

            if not plot_number or not area or not price or not coordinates:
                return JsonResponse({'error': 'Plot number, area, price, and boundary coordinates are required.'}, status=400)

            # Check if plot number already exists for this land
            if land.plots.filter(plot_number=plot_number).exists():
                return JsonResponse({'error': f"Plot {plot_number} has already been registered for this land."}, status=400)

            # Compute centroid of plot coordinates
            lats = [pt[0] for pt in coordinates]
            lngs = [pt[1] for pt in coordinates]
            center_lat = sum(lats) / len(lats)
            center_lng = sum(lngs) / len(lngs)

            plot = Plot.objects.create(
                land=land,
                plot_number=plot_number,
                area=area,
                price=price,
                facing=facing,
                status=status,
                coordinates=coordinates,
                center_lat=center_lat,
                center_lng=center_lng
            )

            return JsonResponse({
                'success': True,
                'plot': {
                    'number': plot.plot_number,
                    'status': plot.status,
                    'price': float(plot.price),
                    'area': plot.area,
                    'facing': plot.facing,
                    'center': {'lat': float(plot.center_lat), 'lng': float(plot.center_lng)},
                    'coordinates': plot.coordinates
                }
            })
        except Exception as e:
            return JsonResponse({'error': f"Error saving plot: {str(e)}"}, status=500)

    return JsonResponse({'error': 'Invalid request method.'}, status=400)

@login_required
def delete_land(request, slug):
    """Deletes a Land property from the registry."""
    if request.user.role != 'ADMIN' and not request.user.is_superuser:
        raise PermissionDenied("You do not have permission to delete land.")
        
    land = get_object_or_404(Land, slug=slug)
    name = land.name
    land.delete()
    messages.success(request, f"Land '{name}' and all its plots have been deleted successfully.")
    return redirect('admin_dashboard')

@login_required
def delete_plot(request, slug, plot_number):
    """Deletes a specific Plot from a Land."""
    if request.user.role != 'ADMIN' and not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
        
    land = get_object_or_404(Land, slug=slug)
    try:
        plot = land.plots.get(plot_number=plot_number)
        plot.delete()
        return JsonResponse({'success': True})
    except Plot.DoesNotExist:
        return JsonResponse({'error': 'Plot not found.'}, status=404)

@login_required
def update_plot(request, slug, plot_number):
    """Updates an existing Plot's specifications."""
    if request.user.role != 'ADMIN' and not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
        
    land = get_object_or_404(Land, slug=slug)
    try:
        plot = land.plots.get(plot_number=plot_number)
        if request.method == 'POST':
            data = json.loads(request.body)
            plot.price = data.get('price')
            
            # extract clean area text
            area_val = data.get('area', '').strip()
            if area_val and not area_val.endswith('sqft'):
                area_val = f"{area_val} sqft"
            plot.area = area_val
            
            plot.facing = data.get('facing', plot.facing)
            plot.status = data.get('status', plot.status)
            plot.save()
            
            return JsonResponse({
                'success': True,
                'plot': {
                    'number': plot.plot_number,
                    'status': plot.status,
                    'price': float(plot.price),
                    'area': plot.area,
                    'facing': plot.facing,
                    'coordinates': plot.coordinates
                }
            })
    except Plot.DoesNotExist:
        return JsonResponse({'error': 'Plot not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
        
    return JsonResponse({'error': 'Invalid request method.'}, status=400)
