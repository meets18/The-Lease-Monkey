import json
import re
import logging
import requests
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Q

from apps.lands.models import Plot, Land
from apps.accounts.models import UserPreferences
from .models import ChatSession, ChatMessage, SupportTicket

logger = logging.getLogger(__name__)

# Track consecutive Ollama errors
OLLAMA_ERROR_COUNT = 0

SYSTEM_GUIDE_PROMPT = """You are the Lease Monkey AI Assistant, a helpful assistant for our land leasing platform.

Lease Monkey Platform Guide:
1. Landowners list lands. They divide lands into individual plots.
2. Buyers browse lands, view plots, save plots, or send purchase requests.
3. To finalize a purchase/lease, the buyer and landowner must hold a meeting. They schedule this meeting directly on our platform.
4. IMPORTANT MEETING RULE: Landowners cannot approve purchase requests until the scheduled meeting time + duration is completed (they can only reject requests before that). This ensures meetings are held before approval.
5. Buyers can customize their preferences (budget, size in acres, property condition, and proximity preferences like school, highway, hospital, railway, airport, city center, water source) in their Profile's Preferences tab.
6. The AI assistant can answer queries showing users how the website works.
7. The AI assistant only recommends plots or lands if the user explicitly asks for recommendations.

Instructions:
- Keep answers clear, concise, and friendly.
- If you do not know the answer, do not make up facts. Just friendly state that you do not know and suggest they check back later.
"""

@csrf_exempt
def send_chat_message(request):
    global OLLAMA_ERROR_COUNT
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    try:
        data = json.loads(request.body)
    except ValueError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    message_text = data.get('message', '').strip()
    session_id = data.get('session_id')

    if not message_text:
        return JsonResponse({'error': 'Message text is required'}, status=400)

    # 1. Retrieve or create ChatSession
    user = request.user if request.user.is_authenticated else None
    if session_id:
        try:
            session = ChatSession.objects.get(id=session_id)
        except ChatSession.DoesNotExist:
            session = ChatSession.objects.create(user=user)
    else:
        session = ChatSession.objects.create(user=user)

    # 2. Save user message
    ChatMessage.objects.create(
        session=session,
        sender='USER',
        message_text=message_text
    )

    # 3. Check if recommendations are explicitly requested
    recommendation_keywords = ['recommend', 'suggest', 'match', 'find', 'budget', 'preference', 'best fit', 'options', 'which plot', 'suitable']
    is_recommendation_requested = any(kw in message_text.lower() for kw in recommendation_keywords)

    # 5. Build prompt
    prompt = message_text
    system_prompt = SYSTEM_GUIDE_PROMPT

    # Load all active available plots to find the closest matches
    available_plots = Plot.objects.filter(status='available').select_related('land')
    
    # Simple scoring to find the top plots matching query words and user preferences
    query_words = set(re.findall(r'\w+', message_text.lower()))
    scored_plots = []
    
    pref = None
    if user:
        try:
            pref = UserPreferences.objects.get(user=user)
        except UserPreferences.DoesNotExist:
            pass

    for p in available_plots:
        score = 0
        # 1. Location match from message query text (e.g. "Sitapura", "Malviya Nagar", etc.)
        p_location_lower = p.land.location.lower()
        p_land_name_lower = p.land.name.lower()
        for qw in query_words:
            if len(qw) > 3:
                if qw in p_location_lower:
                    score += 15
                if qw in p_land_name_lower:
                    score += 15
        
        # 2. Match with user profile preferences
        if pref:
            if pref.min_budget and p.price >= pref.min_budget:
                score += 3
            if pref.max_budget and p.price <= pref.max_budget:
                score += 3
            elif pref.max_budget and p.price > pref.max_budget:
                score -= 2
                
            desc_lower = p.land.description.lower() if p.land.description else ""
            if pref.proximity_preferences:
                for prox in pref.proximity_preferences:
                    if prox.lower() in desc_lower:
                        score += 2
        
        scored_plots.append((score, p))
    
    # Sort plots by score descending
    scored_plots.sort(key=lambda x: x[0], reverse=True)
    top_plots = [item[1] for item in scored_plots[:15]]
    
    # Format the top matching plots for the AI guide/context
    plots_list = []
    for p in top_plots:
        plots_list.append(
            f"Plot Number: {p.plot_number}, Land: {p.land.name}, Location: {p.land.location}, Price: {p.price} INR, Area: {p.area}, Facing: {p.facing}"
        )
    plots_context = "\n".join(plots_list)

    if is_recommendation_requested or any(loc in message_text.lower() for loc in ['sitapura', 'jaipur', 'location', 'where', 'find land', 'any land']):
        # If they ask about locations or recommend plots, provide matched context
        pref_context = "No profile preferences configured yet."
        if pref:
            pref_context = (
                f"User Budget Range: {pref.min_budget or 0} to {pref.max_budget or 'No limit'} INR\n"
                f"Acreage Range: {pref.min_acres or 0} to {pref.max_acres or 'No limit'} acres\n"
                f"Property Condition Preference: {pref.get_property_condition_display()}\n"
                f"Proximity Preferences: {', '.join(pref.proximity_preferences)}"
            )
        
        system_prompt += f"\n\nCONTEXT FOR RECOMMENDATIONS:\nAvailable Plots:\n{plots_context}\n\nUser Profile Preferences:\n{pref_context}\n"
        system_prompt += "\nINSTRUCTION: Recommend at least 5 plots closest to the user's preferences/location query from the context if possible. For each recommended plot, explicitly state both the Plot Number and the Land Name (e.g. 'Plot P3 in LaLaLand'). Do not make up plots."

    ticket_created = False
    ai_response_text = ""

    # Call local Ollama instance
    try:
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': 'llama3.2:latest',
                'prompt': prompt,
                'system': system_prompt,
                'stream': False
            },
            timeout=120.0
        )
        if response.status_code == 200:
            OLLAMA_ERROR_COUNT = 0 # reset error count
            ai_response_text = response.json().get('response', '').strip()
        else:
            logger.error(f"Ollama returned status code {response.status_code}")
            raise requests.exceptions.RequestException("Ollama returned non-200 status code")
    except requests.exceptions.RequestException as e:
        OLLAMA_ERROR_COUNT += 1
        logger.error(f"Ollama request error (count={OLLAMA_ERROR_COUNT}): {e}")
        
        # If multiple consecutive errors, degrade and show friendly offline response
        if OLLAMA_ERROR_COUNT >= 2:
            ai_response_text = (
                "Our AI assistant is temporarily offline due to heavy load. Please try again shortly."
            )
        else:
            ai_response_text = (
                "Our AI assistant is temporarily offline. Please try again shortly."
            )

    # Scan for recommended plots and append structured summary HTML
    try:
        available_plots = Plot.objects.filter(status='available').select_related('land')
        matched_plots = []
        for p in available_plots:
            # Match word pattern, e.g. "A1" or "P3"
            pattern = r'\b' + re.escape(p.plot_number) + r'\b'
            if re.search(pattern, ai_response_text, re.IGNORECASE):
                # Verify that this is the specific land mentioned, OR the plot number is unique
                land_name_clean = p.land.name.lower()
                is_land_mentioned = (land_name_clean in ai_response_text.lower())
                
                # Check uniqueness of plot number across available plots
                is_unique_number = not available_plots.exclude(id=p.id).filter(plot_number=p.plot_number).exists()
                
                if is_land_mentioned or is_unique_number:
                    matched_plots.append(p)
        
        if matched_plots:
            summary_html = "<div class='ai-rec-summary mt-3 p-3 rounded bg-dark border-orange-glow'>"
            summary_html += "<strong style='color:#FF5E00;'><i class='bi bi-pin-angle-fill'></i> Recommended Plots Summary:</strong>"
            summary_html += "<ul class='mb-0 mt-2 pl-3' style='font-size: 0.85rem;'>"
            for p in matched_plots:
                summary_html += (
                    f"<li class='mt-1'><a href='/lands/plots/{p.land.slug}/?plot={p.plot_number}' target='_blank' style='color:#00F0FF;text-decoration:underline;font-weight:600;'>"
                    f"Plot {p.plot_number}</a> in <strong>{p.land.name}</strong> - Price: {p.price} INR, Area: {p.area}</li>"
                )
            summary_html += "</ul></div>"
            ai_response_text += "\n\n" + summary_html
    except Exception as e:
        logger.error(f"Error generating recommendation links: {e}")

    # Save assistant response
    ChatMessage.objects.create(
        session=session,
        sender='AI',
        message_text=ai_response_text
    )

    return JsonResponse({
        'session_id': session.id,
        'response': ai_response_text,
        'ticket_created': ticket_created,
        'consecutive_errors': OLLAMA_ERROR_COUNT
    })

@csrf_exempt
def resolve_ticket(request, ticket_id):
    if not request.user.is_authenticated or request.user.role != 'ADMIN':
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        ticket = SupportTicket.objects.get(id=ticket_id)
    except SupportTicket.DoesNotExist:
        return JsonResponse({'error': 'Ticket not found'}, status=404)

    try:
        data = json.loads(request.body)
        admin_notes = data.get('admin_notes', '')
    except ValueError:
        admin_notes = request.POST.get('admin_notes', '')

    ticket.status = 'RESOLVED'
    ticket.admin_notes = admin_notes
    ticket.resolved_at = timezone.now()
    ticket.save()

    return JsonResponse({'status': 'resolved'})
