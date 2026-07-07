import os
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from .models import Land, Plot, Building, LandImage, Road, EntryExitPoint

User = get_user_model()


def serialize_plot(plot):
    return {
        'type': 'plot',
        'number': plot.plot_number,
        'area': plot.area,
        'price': float(plot.price),
        'facing': plot.facing,
        'status': plot.status,
        'coordinates': plot.coordinates,
    }


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
    lands = [land for land in Land.objects.all() if land.boundary_coordinates and len(land.boundary_coordinates) >= 3]
    return render(request, 'lands/directory.html', {'lands': lands})

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

    context = {
        'land': land,
        'images_list_json': json.dumps(images_list),
        'roads_list_json': json.dumps(roads_list),
        'gates_list_json': json.dumps(gates_list),
        'land_items_json': json.dumps(land_items_list),
        'plots_list_json': json.dumps(plots_list),
        'buildings_list_json': json.dumps(buildings_list),
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
    if request.user.role != 'ADMIN' and not request.user.is_superuser:
        raise PermissionDenied("You do not have permission to access the plot creator.")

    land = get_object_or_404(Land, slug=slug)
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
