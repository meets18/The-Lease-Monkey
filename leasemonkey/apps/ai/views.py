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
- If you do not know the answer, do not make up facts. Instruct the user that you can log a support ticket for the administrator.
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

    # 3. Analyze query for problem/escalation keywords
    escalation_keywords = ['problem', 'error', 'broken', 'fail', 'bug', 'support', 'admin', 'human', 'operator', 'ticket', 'not working', 'glitch']
    has_escalation_intent = any(kw in message_text.lower() for kw in escalation_keywords)

    # 4. Check if recommendations are explicitly requested
    recommendation_keywords = ['recommend', 'suggest', 'match', 'find', 'budget', 'preference', 'best fit', 'options', 'which plot', 'suitable']
    is_recommendation_requested = any(kw in message_text.lower() for kw in recommendation_keywords)

    # 5. Build prompt
    prompt = message_text
    system_prompt = SYSTEM_GUIDE_PROMPT

    if is_recommendation_requested:
        # Load active available plots
        available_plots = Plot.objects.filter(status='available')[:10]  # Limit to avoid huge context payload
        plots_list = []
        for p in available_plots:
            plots_list.append(
                f"Plot Number: {p.plot_number}, Land: {p.land.name}, Location: {p.land.location}, Price: {p.price} INR, Area: {p.area}, Facing: {p.facing}"
            )
        plots_context = "\n".join(plots_list)

        # Load user preferences if available
        pref_context = "No profile preferences configured yet."
        if user:
            try:
                pref = UserPreferences.objects.get(user=user)
                pref_context = (
                    f"User Budget Range: {pref.min_budget or 0} to {pref.max_budget or 'No limit'} INR\n"
                    f"Acreage Range: {pref.min_acres or 0} to {pref.max_acres or 'No limit'} acres\n"
                    f"Property Condition Preference: {pref.get_property_condition_display()}\n"
                    f"Proximity Preferences: {', '.join(pref.proximity_preferences)}"
                )
            except UserPreferences.DoesNotExist:
                pass

        system_prompt += f"\n\nCONTEXT FOR RECOMMENDATIONS:\nAvailable Plots:\n{plots_context}\n\nUser Profile Preferences:\n{pref_context}\n"
        system_prompt += "\nINSTRUCTION: Recommends plots matching user profile preferences from the context. Do not make up plots."

    ticket_created = False
    ai_response_text = ""

    # If the user explicitly asks about a problem, skip Ollama or handle it directly
    if has_escalation_intent:
        SupportTicket.objects.create(
            user=user,
            chat_session=session,
            user_query=message_text
        )
        ticket_created = True
        ai_response_text = (
            "I'm sorry to hear you're experiencing an issue. I have escalated this problem directly to "
            "our system administrator. They will review your query and get back to you shortly."
        )
    else:
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
            
            # If multiple consecutive errors, degrade and escalate immediately
            if OLLAMA_ERROR_COUNT >= 2:
                ai_response_text = (
                    "Our AI engine is currently experiencing heavy load or is offline. "
                    "I have automatically created a support ticket with your query for the administrator."
                )
                SupportTicket.objects.create(
                    user=user,
                    chat_session=session,
                    user_query=message_text
                )
                ticket_created = True
            else:
                ai_response_text = (
                    "Our AI assistant is temporarily offline. Please try again shortly or let me know if "
                    "you'd like me to escalate your query to our support admin."
                )

    # Scan for recommended plots and append structured summary HTML
    try:
        available_plots = Plot.objects.filter(status='available').select_related('land')
        matched_plots = []
        for p in available_plots:
            # Match word pattern, e.g. "A1" or "P3"
            pattern = r'\b' + re.escape(p.plot_number) + r'\b'
            if re.search(pattern, ai_response_text, re.IGNORECASE):
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
