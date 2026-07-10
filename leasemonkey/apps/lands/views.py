import os
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Land, Plot, Building, LandImage, Road, EntryExitPoint, SavedPlot

User = get_user_model()


def serialize_plot(plot):
    data = {
        'type': 'plot',
        'number': plot.plot_number,
        'area': plot.area,
        'price': float(plot.price),
        'facing': plot.facing,
        'status': plot.status,
        'coordinates': plot.coordinates,
        'allotted_buyer': None,
        'allotted_buyer_name': None,
    }
    try:
        from apps.core.models import PurchaseRequest
        pr = PurchaseRequest.objects.filter(
            land=plot.land, 
            plot_number=plot.plot_number, 
            status__in=['approved', 'lease_active']
        ).first()
        if pr:
            data['allotted_buyer'] = pr.buyer.username
            data['allotted_buyer_name'] = pr.full_name
            data['purchase_request_id'] = pr.id
    except ImportError:
        pass
        
    return data


def serialize_building(building):
    return {
        'type': 'building',
        'number': building.building_id,
        'area': building.area,
        'price': 0,
        'facing': 'North',
        'status': 'building',
        'coordinates': building.coordinates,
        'height': building.height,
    }

def lands_directory(request):
    """Renders the catalog list of available land properties."""
    lands_qs = Land.objects.all().prefetch_related('images', 'plots')
    lands = [land for land in lands_qs if land.boundary_coordinates and len(land.boundary_coordinates) >= 3]

    lands_data = []
    for land in lands:
        images = list(land.images.all())
        lands_data.append({
            'id': land.id,
            'name': land.name,
            'slug': land.slug,
            'owner': land.owner.username,
            'area': float(land.area),
            'average_plot_price': float(land.average_plot_price),
            'location': land.location,
            'description': land.description,
            'plots_count': land.plots.count(),
            'first_image_url': images[0].image.url if images else None,
            'images': [{'url': img.image.url, 'caption': img.caption} for img in images],
        })

    return render(request, 'lands/directory.html', {
        'lands': lands,
        'lands_json': json.dumps(lands_data),
    })

def plot_viewer(request, slug):
    """Renders the fullscreen dynamic plot viewer for the specific land site."""
    land = get_object_or_404(Land, slug=slug)
    
    # Serialize images, roads, buildings, and entry/exit points to pass directly to JavaScript
    images_list = [{'id': img.id, 'url': img.image.url, 'caption': img.caption} for img in land.images.all()]
    roads_list = [{'id': r.id, 'name': r.name, 'width': float(r.width_meters), 'coordinates': r.coordinates} for r in land.roads.all()]
    gates_list = [{'id': g.id, 'name': g.name, 'point_type': g.point_type, 'latitude': g.latitude, 'longitude': g.longitude} for g in land.points.all()]
    plots_list = [serialize_plot(plot) for plot in land.plots.all()]
    buildings_list = [serialize_building(building) for building in land.buildings.all()]
    land_items_list = plots_list + buildings_list

    is_admin = request.user.is_authenticated and (request.user.role == 'ADMIN' or request.user.is_superuser or request.user == land.owner)
    
    saved_plots = []
    if request.user.is_authenticated and request.user.role == 'BUYER':
        saved_plots = list(request.user.saved_plots.filter(land=land).values_list('plot_number', flat=True))

    context = {
        'land': land,
        'images_list_json': json.dumps(images_list),
        'roads_list_json': json.dumps(roads_list),
        'gates_list_json': json.dumps(gates_list),
        'land_items_json': json.dumps(land_items_list),
        'plots_list_json': json.dumps(plots_list),
        'buildings_list_json': json.dumps(buildings_list),
        'saved_plots_json': json.dumps(saved_plots),
        'google_maps_api_key': os.getenv('GOOGLE_MAPS_API_KEY', ''),
        'is_admin': is_admin,
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
        average_plot_price = request.POST.get('price', '').strip()
        description = request.POST.get('description', '').strip()

        if not name or not owner_username or not location or not average_plot_price:
            messages.error(request, "All fields (except description/images) are required to register a new land.")
            return redirect('admin_dashboard')

        # Check for unique land name
        if Land.objects.filter(name__iexact=name).exists():
            messages.error(request, f"A land property named '{name}' already exists. Please select a unique name.")
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
                area=0.00,  # Will be calculated and set when boundary is plotted
                average_plot_price=average_plot_price,
                description=description
            )
            
            # Save uploaded gallery images and their corresponding custom captions
            idx = 0
            while True:
                img_key = f'gallery_image_{idx}'
                cap_key = f'gallery_caption_{idx}'
                
                if img_key in request.FILES:
                    img_file = request.FILES[img_key]
                    caption = request.POST.get(cap_key, '').strip()
                    if not caption:
                        caption = f"Gallery Photo {idx + 1}"
                    
                    LandImage.objects.create(
                        land=land,
                        image=img_file,
                        caption=caption
                    )
                    idx += 1
                elif idx < 30: # Scan up to 30 slots to account for any deleted intermediate rows
                    idx += 1
                else:
                    break
                
            messages.success(request, f"Land '{land.name}' metadata successfully saved. Please trace its boundary on the map.")
            return redirect(f'/lands/creator/?slug={land.slug}')
        except Exception as e:
            messages.error(request, f"Error creating land: {str(e)}")

    return redirect('admin_dashboard')

@login_required
def land_creator(request):
    """Renders the interactive Leaflet drawing workspace to outline land boundary."""
    if request.user.role != 'ADMIN' and not request.user.is_superuser:
        raise PermissionDenied("You do not have permission to access the plotting board.")

    slug = request.GET.get('slug')
    land = get_object_or_404(Land, slug=slug)

    # Fetch other lands to prevent overlapping
    other_lands = Land.objects.exclude(slug=slug)
    other_lands_list = []
    for ol in other_lands:
        if ol.boundary_coordinates and len(ol.boundary_coordinates) >= 3:
            other_lands_list.append({
                'name': ol.name,
                'boundary': ol.boundary_coordinates
            })

    context = {
        'land': land,
        'name': land.name,
        'owner': land.owner.username,
        'location': land.location,
        'price': land.average_plot_price,
        'other_lands_json': json.dumps(other_lands_list),
    }
    return render(request, 'lands/creator.html', context)

@login_required
def discard_land_draft(request, slug):
    """Discards a newly created land draft if boundary plotting wasn't completed."""
    if request.user.role != 'ADMIN' and not request.user.is_superuser:
        raise PermissionDenied("You do not have permission to discard land drafts.")

    land = get_object_or_404(Land, slug=slug)
    has_boundary = bool(land.boundary_coordinates and len(land.boundary_coordinates) >= 3)

    if has_boundary:
        messages.info(request, f"Land '{land.name}' already has a saved boundary and was kept.")
        return redirect('admin_dashboard')

    if land.plots.exists() or land.buildings.exists() or land.roads.exists() or land.points.exists():
        messages.info(request, f"Land '{land.name}' already has mapped data and was kept.")
        return redirect('admin_dashboard')

    name = land.name
    land.delete()
    messages.success(request, f"Draft land '{name}' was discarded because no boundary was saved.")
    return redirect('admin_dashboard')

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
            slug = data.get('slug', '').strip()

            if not name or not owner_username or not location or not area or not average_plot_price or not boundary_coordinates:
                return JsonResponse({'error': 'All fields and coordinates are required.'}, status=400)

            # Query the existing Land
            if slug:
                try:
                    land = Land.objects.get(slug=slug)
                except Land.DoesNotExist:
                    return JsonResponse({'error': f"Land with slug '{slug}' not found."}, status=404)
            else:
                # Fallback to name slug if not supplied directly
                try:
                    land = Land.objects.get(slug=slugify(name))
                except Land.DoesNotExist:
                    return JsonResponse({'error': f"Land with name '{name}' not found."}, status=404)

            # Compute boundary centroid for map center coordinate
            lats = [pt[0] for pt in boundary_coordinates]
            lngs = [pt[1] for pt in boundary_coordinates]
            center_lat = sum(lats) / len(lats)
            center_lng = sum(lngs) / len(lngs)

            # Update coordinates, area, and center values
            land.boundary_coordinates = boundary_coordinates
            land.area = area
            land.center_lat = center_lat
            land.center_lng = center_lng
            land.save()

            messages.success(request, f"Land '{land.name}' boundary successfully plotted and registered.")
            return JsonResponse({'success': True, 'redirect_url': f'/lands/plots-creator/{land.slug}/'})
        except Exception as e:
            return JsonResponse({'error': f"Error registering land: {str(e)}"}, status=500)

    return JsonResponse({'error': 'Invalid request method.'}, status=400)

@login_required
def plot_creator(request, slug):
    """Renders the workspace to draw individual plot shapes inside a registered land boundary."""
    land = get_object_or_404(Land, slug=slug)

    is_admin = request.user.role == 'ADMIN' or request.user.is_superuser
    is_owner = request.user == land.owner

    if not is_admin and not is_owner:
        raise PermissionDenied("You do not have permission to access this plot workspace.")

    plots = [serialize_plot(plot) for plot in land.plots.all()]
    buildings = [serialize_building(building) for building in land.buildings.all()]
    land_items = plots + buildings

    # Serialize roads and entry/exit points for creator JS
    roads_list = [{'id': r.id, 'name': r.name, 'width': float(r.width_meters), 'coordinates': r.coordinates} for r in land.roads.all()]
    gates_list = [{'id': g.id, 'name': g.name, 'point_type': g.point_type, 'latitude': g.latitude, 'longitude': g.longitude} for g in land.points.all()]

    context = {
        'land': land,
        'plots_json': json.dumps(plots),
        'buildings_json': json.dumps(buildings),
        'land_items_json': json.dumps(land_items),
        'roads_list_json': json.dumps(roads_list),
        'gates_list_json': json.dumps(gates_list),
        'user_role': request.user.role if not request.user.is_superuser else 'ADMIN',
    }
    return render(request, 'lands/plots_creator.html', context)


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
            is_building = status == 'building'

            if not plot_number or not area or (not price and not is_building) or not coordinates:
                return JsonResponse({'error': 'Plot number, area, price, and boundary coordinates are required.'}, status=400)

            # Compute centroid of plot coordinates
            lats = [pt[0] for pt in coordinates]
            lngs = [pt[1] for pt in coordinates]
            center_lat = sum(lats) / len(lats)
            center_lng = sum(lngs) / len(lngs)

            if is_building:
                if land.buildings.filter(building_id=plot_number).exists():
                    return JsonResponse({'error': f"Building {plot_number} has already been registered for this land."}, status=400)

                building = Building.objects.create(
                    land=land,
                    building_id=plot_number,
                    area=area,
                    height=int(data.get('height', 1)),
                    coordinates=coordinates,
                    center_lat=center_lat,
                    center_lng=center_lng
                )

                return JsonResponse({
                    'success': True,
                    'plot': serialize_building(building) | {
                        'center': {'lat': float(building.center_lat), 'lng': float(building.center_lng)},
                    }
                })

            if land.plots.filter(plot_number=plot_number).exists():
                return JsonResponse({'error': f"Plot {plot_number} has already been registered for this land."}, status=400)

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
                'plot': serialize_plot(plot) | {
                    'center': {'lat': float(plot.center_lat), 'lng': float(plot.center_lng)},
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
    messages.success(request, f"Land '{name}' and all its plots and buildings have been deleted successfully.")
    return redirect('admin_dashboard')

@login_required
def delete_plot(request, slug, plot_number):
    """Deletes a specific Plot from a Land."""
    if request.user.role != 'ADMIN' and not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
        
    land = get_object_or_404(Land, slug=slug)
    try:
        kind = request.GET.get('kind', '').lower()
        if kind == 'building':
            building = land.buildings.filter(building_id=plot_number).first()
            if not building:
                return JsonResponse({'error': 'Building not found.'}, status=404)
            building.delete()
        elif kind == 'plot':
            plot = land.plots.filter(plot_number=plot_number).first()
            if not plot:
                return JsonResponse({'error': 'Plot not found.'}, status=404)
            plot.delete()
        else:
            plot = land.plots.filter(plot_number=plot_number).first()
            if plot:
                plot.delete()
            else:
                building = land.buildings.filter(building_id=plot_number).first()
                if not building:
                    return JsonResponse({'error': 'Plot not found.'}, status=404)
                building.delete()
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
        if request.method == 'POST':
            data = json.loads(request.body)
            kind = request.GET.get('kind', '').lower()

            if kind == 'plot':
                plot = land.plots.filter(plot_number=plot_number).first()
                if not plot:
                    return JsonResponse({'error': 'Plot not found.'}, status=404)

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
                    'plot': serialize_plot(plot) | {
                        'coordinates': plot.coordinates
                    }
                })

            if kind == 'building':
                building = land.buildings.filter(building_id=plot_number).first()
                if not building:
                    return JsonResponse({'error': 'Building not found.'}, status=404)

                area_val = data.get('area', '').strip()
                if area_val and not area_val.endswith('sqft'):
                    area_val = f"{area_val} sqft"
                building.area = area_val or building.area
                building.height = int(data.get('height', building.height))
                building.save()

                return JsonResponse({
                    'success': True,
                    'plot': serialize_building(building) | {
                        'coordinates': building.coordinates,
                        'center': {'lat': float(building.center_lat), 'lng': float(building.center_lng)},
                    }
                })

            plot = land.plots.filter(plot_number=plot_number).first()
            if plot:
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
                    'plot': serialize_plot(plot) | {
                        'coordinates': plot.coordinates
                    }
                })

            building = land.buildings.filter(building_id=plot_number).first()
            if building:
                area_val = data.get('area', '').strip()
                if area_val and not area_val.endswith('sqft'):
                    area_val = f"{area_val} sqft"
                building.area = area_val or building.area
                building.height = int(data.get('height', building.height))
                building.save()

                return JsonResponse({
                    'success': True,
                    'plot': serialize_building(building) | {
                        'coordinates': building.coordinates,
                        'center': {'lat': float(building.center_lat), 'lng': float(building.center_lng)},
                    }
                })

            return JsonResponse({'error': 'Plot not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
        
    return JsonResponse({'error': 'Invalid request method.'}, status=400)

@require_POST
@login_required
def deallot_plot(request, slug, plot_number):
    """De-allot a plot from a buyer by rejecting their approved purchase request."""
    land = get_object_or_404(Land, slug=slug)
    
    if request.user != land.owner and not request.user.is_superuser:
        return JsonResponse({'error': 'Permission denied.'}, status=403)
        
    try:
        data = json.loads(request.body)
        reason = data.get('reason', '').strip()
        
        if not reason:
            return JsonResponse({'error': 'A reason for de-allocation is required.'}, status=400)
            
        from apps.core.models import PurchaseRequest, Notification
        from django.core.mail import send_mail
        from django.conf import settings as django_settings
        
        # Find the approved purchase request
        pr = PurchaseRequest.objects.filter(
            land=land, 
            plot_number=plot_number, 
            status__in=['approved', 'lease_active']
        ).first()
        
        if not pr:
            return JsonResponse({'error': 'No allotted buyer found for this plot.'}, status=404)
            
        # Update Purchase Request
        pr.status = 'rejected'
        pr.rejection_reason = reason
        pr.save()
        
        # Update Plot status back to available
        plot = land.plots.filter(plot_number=plot_number).first()
        if plot:
            plot.status = 'available'
            plot.save()
            
        # Send Notification to Buyer
        Notification.objects.create(
            recipient=pr.buyer,
            sender=request.user,
            notif_type='purchase_request_rejected',
            title=f"Plot {plot_number} De-allocated",
            message=f"Your allotment for Plot {plot_number} in {land.name} has been cancelled by the landowner.\n\nReason: {reason}",
            land_slug=land.slug,
            plot_number=plot_number
        )
        
        # Send Email to Buyer
        try:
            send_mail(
                subject=f'[Lease Monkey] Plot {plot_number} De-allocation Notice',
                message=f'Hello {pr.buyer.username},\n\nWe regret to inform you that your allotment for Plot {plot_number} in {land.name} has been cancelled by the landowner.\n\nReason for de-allocation: {reason}\n\nIf you have any questions, please contact the landowner or our support team.\n\n— The Lease Monkey Team',
                from_email=django_settings.EMAIL_HOST_USER,
                recipient_list=[pr.buyer.email],
                fail_silently=True,
            )
        except Exception:
            pass
            
        return JsonResponse({'status': 'ok', 'message': f'Plot {plot_number} has been de-allotted successfully.'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def save_road(request, slug):
    """Creates a new road inside the land boundary."""
    if request.user.role != 'ADMIN' and not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    land = get_object_or_404(Land, slug=slug)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            width_meters = data.get('width_meters', 9.0)
            coordinates = data.get('coordinates')

            if not name or not coordinates:
                return JsonResponse({'error': 'Road name and coordinates are required.'}, status=400)

            road = Road.objects.create(
                land=land,
                name=name,
                width_meters=width_meters,
                coordinates=coordinates
            )

            return JsonResponse({
                'success': True,
                'road': {
                    'id': road.id,
                    'name': road.name,
                    'width': float(road.width_meters),
                    'coordinates': road.coordinates
                }
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request method.'}, status=400)

@login_required
def delete_road(request, slug, road_id):
    """Deletes a specific road from a land."""
    if request.user.role != 'ADMIN' and not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    land = get_object_or_404(Land, slug=slug)
    try:
        road = land.roads.get(id=road_id)
        road.delete()
        return JsonResponse({'success': True})
    except Road.DoesNotExist:
        return JsonResponse({'error': 'Road not found.'}, status=404)

@login_required
def save_gate(request, slug):
    """Creates a new entry/exit point inside the land."""
    if request.user.role != 'ADMIN' and not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    land = get_object_or_404(Land, slug=slug)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            point_type = data.get('point_type', 'entry')
            latitude = data.get('latitude')
            longitude = data.get('longitude')

            if not name or latitude is None or longitude is None:
                return JsonResponse({'error': 'Name, latitude, and longitude are required.'}, status=400)

            gate = EntryExitPoint.objects.create(
                land=land,
                name=name,
                point_type=point_type,
                latitude=latitude,
                longitude=longitude
            )

            return JsonResponse({
                'success': True,
                'gate': {
                    'id': gate.id,
                    'name': gate.name,
                    'point_type': gate.point_type,
                    'latitude': gate.latitude,
                    'longitude': gate.longitude
                }
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request method.'}, status=400)

@login_required
def delete_gate(request, slug, gate_id):
    """Deletes a specific entry/exit point."""
    if request.user.role != 'ADMIN' and not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    land = get_object_or_404(Land, slug=slug)
    try:
        gate = land.points.get(id=gate_id)
        gate.delete()
        return JsonResponse({'success': True})
    except EntryExitPoint.DoesNotExist:
        return JsonResponse({'error': 'Gate not found.'}, status=404)

@login_required
def update_land_info(request, slug):
    """Updates Land metadata (name, location, description) via AJAX."""
    land = get_object_or_404(Land, slug=slug)
    if request.user.role != 'ADMIN' and not request.user.is_superuser and request.user != land.owner:
        return JsonResponse({'success': False, 'error': "Permission Denied"}, status=403)
        
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            location = data.get('location', '').strip()
            description = data.get('description', '').strip()
            
            if not name or not location:
                return JsonResponse({'success': False, 'error': 'Name and location are required.'})

            # Check for name uniqueness excluding current land
            if Land.objects.filter(name__iexact=name).exclude(id=land.id).exists():
                return JsonResponse({'success': False, 'error': f"A land property named '{name}' already exists."})
                
            land.name = name
            land.location = location
            land.description = description
            
            avg_price = data.get('average_plot_price')
            if avg_price is not None:
                land.average_plot_price = float(avg_price)
                
            land.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': "Invalid request method"}, status=400)

@login_required
def add_gallery_photo(request, slug):
    """Adds a new photo to the land gallery via AJAX/Form POST."""
    land = get_object_or_404(Land, slug=slug)
    if request.user.role != 'ADMIN' and not request.user.is_superuser and request.user != land.owner:
        return JsonResponse({'success': False, 'error': "Permission Denied"}, status=403)
        
    if request.method == 'POST' and request.FILES.get('image'):
        try:
            image_file = request.FILES['image']
            caption = request.POST.get('caption', '').strip()
            if not caption:
                caption = f"Gallery Photo {land.images.count() + 1}"
            
            new_img = LandImage.objects.create(
                land=land,
                image=image_file,
                caption=caption
            )
            return JsonResponse({
                'success': True,
                'image': {
                    'id': new_img.id,
                    'url': new_img.image.url,
                    'caption': new_img.caption
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': "Invalid request or missing file"}, status=400)

@login_required
def delete_gallery_photo(request, slug, photo_id):
    """Deletes a specific gallery photo via AJAX."""
    land = get_object_or_404(Land, slug=slug)
    if request.user.role != 'ADMIN' and not request.user.is_superuser and request.user != land.owner:
        return JsonResponse({'success': False, 'error': "Permission Denied"}, status=403)
        
    if request.method == 'POST':
        try:
            photo = get_object_or_404(LandImage, id=photo_id, land=land)
            photo.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': "Invalid request method"}, status=400)

@login_required
def update_photo_caption(request, slug, photo_id):
    """Updates the caption of a specific gallery photo via AJAX."""
    land = get_object_or_404(Land, slug=slug)
    if request.user.role != 'ADMIN' and not request.user.is_superuser and request.user != land.owner:
        return JsonResponse({'success': False, 'error': "Permission Denied"}, status=403)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_caption = data.get('caption', '').strip()
            photo = get_object_or_404(LandImage, id=photo_id, land=land)
            photo.caption = new_caption
            photo.save()
            return JsonResponse({'success': True, 'caption': photo.caption})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': "Invalid request method"}, status=400)


# ──────────────────────────────────────────────────────────────────────────────
# Landowner Deletion Request Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@login_required
def request_land_deletion(request, slug):
    """
    Landowner requests admin to delete a land.
    Creates Notification for each admin + sends email. Does NOT delete the land.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=400)

    land = get_object_or_404(Land, slug=slug)

    # Verify the requester owns this land
    if request.user != land.owner and not request.user.is_superuser:
        return JsonResponse({'error': 'Permission denied.'}, status=403)

    if not land:
        return JsonResponse({'error': 'Land not found.'}, status=404)

    from apps.core.models import Notification, PurchaseRequest
    from django.core.mail import send_mail
    from django.conf import settings as django_settings

    if PurchaseRequest.objects.filter(land=land, status__in=['approved', 'lease_active']).exists():
        return JsonResponse({'error': 'Cannot delete land. Some plots are allotted to buyers. Please de-allot them first.'}, status=400)

    admins = User.objects.filter(role='ADMIN')
    if not admins.exists():
        # Fallback: try superusers
        admins = User.objects.filter(is_superuser=True)

    for admin in admins:
        Notification.objects.create(
            recipient=admin,
            sender=request.user,
            notif_type='land_delete_request',
            title=f"Deletion Request: Land \"{land.name}\"",
            message=(
                f"Landowner {request.user.username} has requested deletion of land \"{land.name}\" "
                f"(Location: {land.location}).\n\n"
                f"Please review and approve or reject this request in your notifications."
            ),
            land_slug=land.slug,
        )
        # Send email to this admin
        admin_email = django_settings.ADMIN_EMAIL or admin.email
        if admin_email:
            try:
                send_mail(
                    subject=f"[Lease Monkey] Deletion Request — Land \"{land.name}\"",
                    message=(
                        f"Hello {admin.username},\n\n"
                        f"Landowner '{request.user.username}' has submitted a deletion request for:\n\n"
                        f"  Land: {land.name}\n"
                        f"  Location: {land.location}\n"
                        f"  Slug: {land.slug}\n\n"
                        f"Please log in to your dashboard and review the Notifications tab to approve or reject this request.\n\n"
                        f"— The Lease Monkey System"
                    ),
                    from_email=django_settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[admin_email],
                    fail_silently=True,
                )
            except Exception:
                pass

    return JsonResponse({'status': 'ok', 'message': 'Deletion request sent to admin.'})


@login_required
def request_plot_deletion(request, slug, plot_number):
    """
    Landowner requests admin to delete a specific plot or building.
    Creates Notification for each admin + sends email. Does NOT delete the plot.
    Query param: ?kind=plot|building  (defaults to 'plot')
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=400)

    land = get_object_or_404(Land, slug=slug)

    if request.user != land.owner and not request.user.is_superuser:
        return JsonResponse({'error': 'Permission denied.'}, status=403)

    kind = request.GET.get('kind', 'plot').lower()
    if kind == 'building':
        obj = land.buildings.filter(building_id=plot_number).first()
        item_label = f"Building {plot_number}"
    else:
        obj = land.plots.filter(plot_number=plot_number).first()
        item_label = f"Plot {plot_number}"
        kind = 'plot'

    if not obj:
        return JsonResponse({'error': f'{item_label} not found in land {land.name}.'}, status=404)

    from apps.core.models import Notification, PurchaseRequest
    from django.core.mail import send_mail
    from django.conf import settings as django_settings

    if kind == 'plot':
        if PurchaseRequest.objects.filter(land=land, plot_number=plot_number, status__in=['approved', 'lease_active']).exists():
            return JsonResponse({'error': 'Cannot delete plot. Please de-allot the buyer first.'}, status=400)

    admins = User.objects.filter(role='ADMIN')
    if not admins.exists():
        admins = User.objects.filter(is_superuser=True)

    for admin in admins:
        Notification.objects.create(
            recipient=admin,
            sender=request.user,
            notif_type='plot_delete_request',
            title=f"Deletion Request: {item_label} in \"{land.name}\"",
            message=(
                f"Landowner {request.user.username} has requested deletion of {item_label} "
                f"in land \"{land.name}\".\n\n"
                f"Please review and approve or reject this request in your notifications."
            ),
            land_slug=land.slug,
            plot_number=plot_number,
            plot_kind=kind,
        )
        admin_email = django_settings.ADMIN_EMAIL or admin.email
        if admin_email:
            try:
                send_mail(
                    subject=f"[Lease Monkey] Deletion Request — {item_label} in \"{land.name}\"",
                    message=(
                        f"Hello {admin.username},\n\n"
                        f"Landowner '{request.user.username}' has submitted a deletion request for:\n\n"
                        f"  {item_label} in Land: {land.name}\n"
                        f"  Land Slug: {land.slug}\n\n"
                        f"Please log in to your dashboard and review the Notifications tab to approve or reject this request.\n\n"
                        f"— The Lease Monkey System"
                    ),
                    from_email=django_settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[admin_email],
                    fail_silently=True,
                )
            except Exception:
                pass

    return JsonResponse({'status': 'ok', 'message': f'Deletion request for {item_label} sent to admin.'})

# ── Purchase Requests ─────────────────────────────────────────────────────

import random
from django.utils import timezone
from apps.core.models import EmailOTP, PurchaseRequest, Notification
from django.core.mail import send_mail
from django.conf import settings

@login_required
def send_otp(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=400)
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip()
        if not email:
            return JsonResponse({'error': 'Email is required.'}, status=400)
        
        # Enforce 1-minute wait before resending
        last_otp = EmailOTP.objects.filter(email=email).order_by('-created_at').first()
        if last_otp:
            time_diff = (timezone.now() - last_otp.created_at).total_seconds()
            if time_diff < 60:
                wait_time = int(60 - time_diff)
                return JsonResponse({'error': f'Please wait {wait_time} seconds before requesting another OTP.'}, status=400)
        
        # Generate and save new OTP
        otp = f"{random.randint(100000, 999999)}"
        EmailOTP.objects.create(email=email, otp_code=otp)
        
        # Send OTP via email using EMAIL_HOST_USER
        send_mail(
            subject='[Lease Monkey] Your OTP for Purchase Request',
            message=f'Hello,\n\nYour randomly generated OTP for verifying your email for the purchase request is: {otp}\n\nThis OTP is valid for 5 minutes and will be automatically deleted afterwards.\n\n— The Lease Monkey Team',
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[email],
            fail_silently=False,
        )
            
        return JsonResponse({'status': 'sent', 'message': 'OTP sent successfully.'})
    except Exception as e:
        return JsonResponse({'error': f'Failed to send email. Error: {str(e)}'}, status=500)


@login_required
def verify_otp(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=400)
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip()
        otp = data.get('otp', '').strip()
        
        if not email or not otp:
            return JsonResponse({'error': 'Email and OTP are required.'}, status=400)
            
        otp_record = EmailOTP.objects.filter(email=email, otp_code=otp, is_used=False).first()
        if not otp_record:
            return JsonResponse({'error': 'Incorrect OTP or email.'}, status=400)
            
        if otp_record.is_expired():
            return JsonResponse({'error': 'OTP expired. Please request a new one.'}, status=400)
            
        otp_record.is_used = True
        otp_record.save()
        return JsonResponse({'status': 'verified', 'message': 'Email verified successfully.'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def purchase_request_form(request, slug, plot_number):
    if request.user.role != 'BUYER':
        messages.error(request, 'Only buyers can raise purchase requests.')
        return redirect('lands:plot_viewer', slug=slug)
        
    land = get_object_or_404(Land, slug=slug)
    plot = land.plots.filter(plot_number=plot_number).first()
    if not plot:
        plot = land.buildings.filter(building_id=plot_number).first()
        
    if not plot or getattr(plot, 'status', 'available') != 'available':
        messages.error(request, 'This plot is not available for purchase requests.')
        return redirect('lands:plot_viewer', slug=slug)
        
    context = {
        'land': land,
        'plot': plot,
        'plot_number': plot_number,
        'land_slug': slug,
    }
    return render(request, 'lands/purchase_request_form.html', context)

@login_required
def submit_purchase_request(request, slug, plot_number):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=400)
        
    if request.user.role != 'BUYER':
        return JsonResponse({'error': 'Only buyers can raise purchase requests.'}, status=403)
        
    try:
        data = json.loads(request.body)
        full_name = data.get('full_name', '').strip()
        aadhaar_number = data.get('aadhaar_number', '').strip()
        pan_number = data.get('pan_number', '').strip().upper()
        email = data.get('email', '').strip()
        phone_number = data.get('phone_number', '').strip()
        proposed_amount = data.get('proposed_amount')
        
        if not (full_name and aadhaar_number and pan_number and email and phone_number and proposed_amount):
            return JsonResponse({'error': 'All fields are required.'}, status=400)
            
        # Verify OTP was used
        recent_otp = EmailOTP.objects.filter(email=email, is_used=True).order_by('-created_at').first()
        if not recent_otp or (timezone.now() - recent_otp.created_at).total_seconds() > 1800:
            return JsonResponse({'error': 'Email not verified or verification expired.'}, status=400)
            
        land = get_object_or_404(Land, slug=slug)
        
        # Check for existing pending request
        if PurchaseRequest.objects.filter(buyer=request.user, land=land, plot_number=plot_number, status__in=['pending', 'meeting_scheduled']).exists():
            return JsonResponse({'error': 'You already have an active request for this plot.'}, status=400)
            
        # Create request
        pr = PurchaseRequest.objects.create(
            buyer=request.user,
            land=land,
            plot_number=plot_number,
            full_name=full_name,
            aadhaar_number=aadhaar_number,
            pan_number=pan_number,
            email=email,
            phone_number=phone_number,
            proposed_amount=proposed_amount,
            status='pending'
        )
        
        # Notify landowner
        Notification.objects.create(
            recipient=land.owner,
            sender=request.user,
            notif_type='purchase_request',
            title=f"New Purchase Request for Plot {plot_number}",
            message=f"Buyer {full_name} ({request.user.username}) has requested to purchase Plot {plot_number} in {land.name} for {proposed_amount}.",
            land_slug=land.slug,
            plot_number=plot_number
        )
        
        # Send emails
        try:
            # Landowner email
            send_mail(
                subject=f'[Lease Monkey] New Purchase Request — Plot {plot_number} in {land.name}',
                message=f'Hello {land.owner.username},\n\nYou have a new purchase request from {full_name} for Plot {plot_number}.\nProposed Amount: {proposed_amount}\n\nPlease check your dashboard.\n\n— The Lease Monkey Team',
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[land.owner.email],
                fail_silently=False,
            )
            # Buyer email
            send_mail(
                subject=f'[Lease Monkey] Your Purchase Request has been submitted',
                message=f'Hello {full_name},\n\nYour purchase request for Plot {plot_number} in {land.name} has been successfully submitted to the landowner. You will be notified when they respond.\n\n— The Lease Monkey Team',
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[email],
                fail_silently=False,
            )
        except Exception as e:
            pass
            
        return JsonResponse({'status': 'ok', 'message': 'Purchase request submitted successfully.'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def purchase_request_action(request, request_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=400)
        
    if request.user.role != 'LAND_OWNER':
        return JsonResponse({'error': 'Only landowners can manage purchase requests.'}, status=403)
        
    pr = get_object_or_404(PurchaseRequest, id=request_id, land__owner=request.user)
    
    try:
        data = json.loads(request.body)
        action = data.get('action')
        reason = data.get('reason', '').strip()
        
        if action == 'fix_meeting' and pr.status == 'pending':
            # --- Parse meeting datetime and duration sent from the modal ---
            meeting_datetime_str = data.get('meeting_datetime', '').strip()
            duration_minutes = int(data.get('duration_minutes', 30))

            if not meeting_datetime_str:
                return JsonResponse({'error': 'Meeting date and time are required.'}, status=400)

            from django.utils import timezone as tz
            from django.utils.dateparse import parse_datetime
            import pytz

            # Parse the ISO string from the frontend (e.g. "2026-07-12T14:30")
            naive_dt = parse_datetime(meeting_datetime_str)
            if naive_dt is None:
                return JsonResponse({'error': 'Invalid date/time format.'}, status=400)

            ist = pytz.timezone('Asia/Kolkata')
            if naive_dt.tzinfo is None:
                meeting_dt = ist.localize(naive_dt)
            else:
                meeting_dt = naive_dt

            # --- Create Google Meet via Calendar API ---
            meet_link = ''
            calendar_event_id = ''
            try:
                from apps.core.google_calendar import create_meet_event
                event_result = create_meet_event(
                    title=f'Lease Monkey Meeting — Plot {pr.plot_number} in {pr.land.name}',
                    description=(
                        f'Purchase Request Meeting\n\n'
                        f'Buyer: {pr.full_name} ({pr.buyer.username})\n'
                        f'Plot: {pr.plot_number}\n'
                        f'Land: {pr.land.name}\n'
                        f'Proposed Amount: ₹{pr.proposed_amount}\n\n'
                        f'{data.get("message", "")}'
                    ),
                    start_datetime=meeting_dt,
                    duration_minutes=duration_minutes,
                    attendee_emails=[pr.email, request.user.email],
                )
                meet_link = event_result.get('meet_link', '')
                calendar_event_id = event_result.get('event_id', '')
            except Exception as cal_err:
                # Log but don't block — still schedule in our system
                import logging
                logging.getLogger(__name__).error(f'Google Calendar error: {cal_err}')

            # --- Update the Purchase Request ---
            pr.status = 'meeting_scheduled'
            pr.meeting_datetime = meeting_dt
            pr.meeting_duration_mins = duration_minutes
            pr.meet_link = meet_link
            pr.calendar_event_id = calendar_event_id
            pr.meeting_notes = data.get('message', '')
            pr.save()

            # Update plot status to reserved
            plot = pr.land.plots.filter(plot_number=pr.plot_number).first()
            if plot:
                plot.status = 'reserved'
                plot.save()

            # --- In-app notification ---
            meeting_dt_display = meeting_dt.strftime('%d %b %Y at %I:%M %p IST')
            meet_info = f'\n\nGoogle Meet Link: {meet_link}' if meet_link else ''
            Notification.objects.create(
                recipient=pr.buyer,
                sender=request.user,
                notif_type='purchase_request_meeting',
                title=f"Meeting Scheduled for Plot {pr.plot_number}",
                message=(
                    f"The landowner has scheduled a Google Meet with you for Plot {pr.plot_number} "
                    f"in {pr.land.name}.\n\n"
                    f"📅 Date & Time: {meeting_dt_display}\n"
                    f"⏱ Duration: {duration_minutes} minutes"
                    f"{meet_info}"
                ),
                land_slug=pr.land.slug,
                plot_number=pr.plot_number
            )

            # --- Email to buyer ---
            try:
                meet_line = f'\n\nJoin Google Meet: {meet_link}' if meet_link else ''
                send_mail(
                    subject=f'[Lease Monkey] Meeting Scheduled — Plot {pr.plot_number}',
                    message=(
                        f'Hello {pr.full_name},\n\n'
                        f'The landowner has scheduled a Google Meet for your purchase request.\n\n'
                        f'📅 Date & Time: {meeting_dt_display}\n'
                        f'⏱ Duration: {duration_minutes} minutes\n'
                        f'🏡 Property: Plot {pr.plot_number} in {pr.land.name}'
                        f'{meet_line}\n\n'
                        f'— The Lease Monkey Team'
                    ),
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=[pr.email],
                    fail_silently=True,
                )
            except Exception:
                pass

            response_data = {
                'success': True,
                'message': 'Meeting scheduled successfully.',
                'meet_link': meet_link,
                'meeting_datetime': meeting_dt_display,
            }
            return JsonResponse(response_data)
            
        elif action == 'approve' and pr.status == 'meeting_scheduled':
            # Check if meeting has concluded
            from datetime import timedelta
            from django.utils import timezone
            if pr.meeting_datetime:
                meeting_end = pr.meeting_datetime + timedelta(minutes=pr.meeting_duration_mins)
                if timezone.now() < meeting_end:
                    return JsonResponse({
                        'error': 'Cannot approve purchase request yet. The scheduled meeting has not concluded.'
                    }, status=400)

            pr.status = 'approved'
            pr.save()
            
            # Update plot status to sold
            plot = pr.land.plots.filter(plot_number=pr.plot_number).first()
            if plot:
                plot.status = 'sold'
                plot.save()
                
            # Reject all other pending/meeting_scheduled requests for this plot
            other_requests = PurchaseRequest.objects.filter(
                land=pr.land, plot_number=pr.plot_number, status__in=['pending', 'meeting_scheduled']
            ).exclude(id=pr.id)
            
            for other_pr in other_requests:
                other_pr.status = 'rejected'
                other_pr.rejection_reason = 'Plot sold to another buyer.'
                other_pr.save()
                Notification.objects.create(
                    recipient=other_pr.buyer,
                    sender=request.user,
                    notif_type='purchase_request_rejected',
                    title=f"Purchase Request Rejected for Plot {pr.plot_number}",
                    message=f"Your purchase request for Plot {pr.plot_number} in {pr.land.name} has been rejected. Reason: Plot sold to another buyer.",
                    land_slug=pr.land.slug,
                    plot_number=pr.plot_number
                )
                
            Notification.objects.create(
                recipient=pr.buyer,
                sender=request.user,
                notif_type='purchase_request_approved',
                title=f"Purchase Request Approved for Plot {pr.plot_number}",
                message=f"Congratulations! Your purchase request for Plot {pr.plot_number} in {pr.land.name} has been approved.",
                land_slug=pr.land.slug,
                plot_number=pr.plot_number
            )
            
            try:
                send_mail(
                    subject=f'[Lease Monkey] Purchase Request Approved! — Plot {pr.plot_number}',
                    message=f'Hello {pr.full_name},\n\nCongratulations! The landowner has approved your purchase request for Plot {pr.plot_number} in {pr.land.name}.\n\n— The Lease Monkey Team',
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=[pr.email],
                    fail_silently=False,
                )
            except Exception:
                pass
                
            return JsonResponse({'success': True, 'message': 'Purchase approved successfully.'})
            
        elif action == 'reject' and pr.status in ['pending', 'meeting_scheduled']:
            if not reason:
                return JsonResponse({'error': 'Rejection reason is required.'}, status=400)
                
            was_meeting_scheduled = (pr.status == 'meeting_scheduled')
            pr.status = 'rejected'
            pr.rejection_reason = reason
            pr.save()
            
            # Revert plot status to available if it was reserved
            if was_meeting_scheduled:
                plot = pr.land.plots.filter(plot_number=pr.plot_number).first()
                if plot and plot.status == 'reserved':
                    plot.status = 'available'
                    plot.save()
                    
            Notification.objects.create(
                recipient=pr.buyer,
                sender=request.user,
                notif_type='purchase_request_rejected',
                title=f"Purchase Request Rejected for Plot {pr.plot_number}",
                message=f"Your purchase request for Plot {pr.plot_number} in {pr.land.name} has been rejected. Reason: {reason}",
                land_slug=pr.land.slug,
                plot_number=pr.plot_number
            )
            
            try:
                send_mail(
                    subject=f'[Lease Monkey] Purchase Request Rejected — Plot {pr.plot_number}',
                    message=f'Hello {pr.full_name},\n\nYour purchase request for Plot {pr.plot_number} in {pr.land.name} has been rejected.\nReason: {reason}\n\n— The Lease Monkey Team',
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=[pr.email],
                    fail_silently=False,
                )
            except Exception:
                pass
                
            return JsonResponse({'success': True, 'message': 'Request rejected successfully.'})
            
        else:
            return JsonResponse({'error': 'Invalid action or request state.'}, status=400)
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
def toggle_saved_plot(request, slug, plot_number):
    if request.user.role != 'BUYER':
        return JsonResponse({'error': 'Only buyers can save plots.'}, status=403)
        
    land = get_object_or_404(Land, slug=slug)
    
    # Check if plot exists in this land
    plot_exists = land.plots.filter(plot_number=plot_number).exists()
    if not plot_exists:
        return JsonResponse({'error': 'Plot not found in this land.'}, status=404)
        
    saved_plot = SavedPlot.objects.filter(user=request.user, land=land, plot_number=plot_number).first()
    
    if saved_plot:
        saved_plot.delete()
        return JsonResponse({'status': 'unsaved'})
    else:
        SavedPlot.objects.create(user=request.user, land=land, plot_number=plot_number)
        return JsonResponse({'status': 'saved'})
