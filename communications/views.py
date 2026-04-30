# communications/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q
from django.utils import timezone
from django.template.loader import render_to_string
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import json

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Message, Conversation  # adjust if your app name differs
# ✅ Local imports
from .models import Conversation, Message, Attachment
from accounts.models import CustomUser


# ================================================================
# 🔹 VIEW: Conversation detail page (shows messages)
# ================================================================
@login_required
def conversation_detail(request, pk):
    convo = get_object_or_404(Conversation, pk=pk)

    if request.method == "POST":
        content = request.POST.get("content")
        files = request.FILES.getlist("attachments")
        
        msg = Message.objects.create(
            conversation=convo,
            sender=request.user,
            content=content
        )
        
        for f in files:
            Attachment.objects.create(message=msg, file=f, original_name=f.name)

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return render(request, "communications/partials/chat_message.html", {"m": msg})
        
        return redirect("conversation_detail", pk=pk)

    # 1. Fetch messages and convert to a list IMMEDIATELY to avoid the slicing error in templates
    # Added .order_by('-created_at') then reversed in Python so you get the LATEST 100 in chronological order
    messages_qs = convo.messages.select_related("sender").prefetch_related("attachments").order_by('-created_at')[:100]
    messages_list = list(messages_qs)[::-1]  # Reverse to chronological order
    
    # 2. Safely get the last message ID for your JS polling logic
    last_message_id = messages_list[-1].id if messages_list else 0

    # 3. Mark as read logic
    convo.messages.exclude(sender=request.user).update(is_read=True)

    return render(request, "communications/conversation_detail.html", {
        "conversation": convo,
        "messages": messages_list,
        "last_message_id": last_message_id,
    })


# ================================================================
# 🔹 VIEW: Create a new conversation
# ================================================================
@login_required
def create_conversation(request):
    if request.method == "POST":
        participant_ids = request.POST.getlist("participants")
        name = request.POST.get("name", "")

        convo = Conversation.objects.create(name=name or "")
        convo.participants.add(request.user)

        for uid in participant_ids:
            try:
                user = CustomUser.objects.get(pk=uid)
                convo.participants.add(user)
            except CustomUser.DoesNotExist:
                continue

        convo.save()
        return redirect("conversation_detail", pk=convo.pk)

    users = CustomUser.objects.exclude(pk=request.user.pk)
    return render(request, "communications/create_conversation.html", {"users": users})


# ================================================================
# 🔹 VIEW: Handle message send + attachments (AJAX)
# ================================================================
@login_required
def upload_attachment(request, pk):
    """
    Handles sending a new chat message (text and optional files).
    Returns rendered HTML for dynamic injection.
    """
    convo = get_object_or_404(Conversation, pk=pk)

    # 🚫 Ensure user belongs to this chat
    if not convo.participants.filter(pk=request.user.pk).exists():
        return HttpResponseForbidden("You are not a participant in this conversation.")

    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    text = request.POST.get("text", "").strip()
    files = request.FILES.getlist("files")

    # ✅ Save message to DB
    message = Message.objects.create(
        conversation=convo,
        sender=request.user,
        content=text or "",
        created_at=timezone.now()
    )

    # ✅ Save attachments (if any)
    attachments = []
    for f in files:
        att = Attachment.objects.create(
            message=message,
            file=f,
            original_name=f.name
        )
        attachments.append({
            "id": att.id,
            "url": att.file.url,
            "name": att.original_name
        })

    # ✅ Render message bubble HTML (for instant display)
    html = render_to_string("communications/message_bubble.html", {
        "m": message,
        "request": request,
    })

    # ✅ Broadcast via WebSocket (real-time)
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"chat_{convo.pk}",
        {
            "type": "message.broadcast",
            "message": {
                "id": message.id,
                "sender_id": request.user.id,
                "sender_username": request.user.get_full_name() or request.user.username,
                "content": message.content,
                "created_at": message.created_at.isoformat(),
                "attachments": attachments,
            },
        }
    )

    # ✅ Clean JSON response (no debug strings)
    return JsonResponse({
        "success": True,
        "html": html,
        "attachments": attachments,
    }, content_type="application/json")


# ================================================================
# 🔹 VIEW: List conversations (with search and filters)
# ================================================================
@login_required
def conversation_list(request):
    conversations = Conversation.objects.filter(participants=request.user)
    q = request.GET.get("q", "")
    filter_option = request.GET.get("filter", "")

    if q:
        conversations = conversations.filter(
            Q(name__icontains=q) |
            Q(participants__username__icontains=q)
        ).distinct()

    if filter_option == "recent":
        conversations = conversations.order_by("-updated_at")
    elif filter_option == "active":
        conversations = conversations.filter(messages__isnull=False).distinct()

    return render(request, "communications/conversation_list.html", {"conversations": conversations})


# ================================================================
# 🔹 VIEW: AJAX filtering / search for conversations
# ================================================================
from django.db.models import Q, Count, OuterRef, Subquery, Max
from .models import Message, Conversation

@login_required
def conversation_list_ajax(request):
    # 1. Base Queryset: Conversations user is part of
    conversations = Conversation.objects.filter(participants=request.user)

    # 2. Subquery: Get the latest message content for each conversation
    latest_msg = Message.objects.filter(conversation=OuterRef('pk')).order_by('-created_at')
    
    # 3. Annotate the Queryset
    # This keeps the logic in the DB, not in Python loops.
    conversations = conversations.annotate(
        # Total unread messages for THIS user in THIS conversation
        unread_count=Count(
            'messages', 
            filter=Q(messages__is_read=False) & ~Q(messages__sender=request.user)
        ),
        # Get the ID and content of the last message
        last_msg_text=Subquery(latest_msg.values('content')[:100]), 
        last_msg_sender_name=Subquery(latest_msg.values('sender__username')[:1]),
        last_msg_time=Max('messages__created_at')
    ).order_by('-last_msg_time') # Sort by most recent activity

    # 4. Search & Filter
    q = request.GET.get("q", "")
    filter_option = request.GET.get("filter", "")

    if q:
        conversations = conversations.filter(
            Q(name__icontains=q) |
            Q(participants__username__icontains=q) |
            Q(participants__first_name__icontains=q)
        ).distinct()

    if filter_option == "unread":
        conversations = conversations.filter(unread_count__gt=0)
    elif filter_option == "recent":
        # Already ordered by last_msg_time above
        pass

    return render(request, "communications/conversation_list_partial.html", {
        "conversations": conversations
    })

# ================================================================
# 🔹 VIEW: Handle text-only message via JSON (fallback)
# ================================================================
@login_required
def send_message(request, convo_id):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            text = data.get("text", "").strip()
            if not text:
                return JsonResponse({"success": False, "error": "Empty message"})

            convo = Conversation.objects.get(pk=convo_id)
            msg = Message.objects.create(
                conversation=convo,
                sender=request.user,
                content=text,
                created_at=timezone.now()
            )

            return JsonResponse({
                "success": True,
                "message": {
                    "id": msg.id,
                    "sender": request.user.get_full_name() or request.user.username,
                    "content": msg.content,
                    "timestamp": msg.created_at.strftime("%b %d, %Y %H:%M")
                }
            })
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid method"})


# ================================================================
# 🔹 VIEW: Fetch new messages (for auto-refresh / live chat)
# ================================================================

@login_required
def fetch_new_messages(request, conversation_id):
    last_id = request.GET.get("after", 0)
    conversation = Conversation.objects.get(pk=conversation_id)

    messages = (
        Message.objects.filter(conversation=conversation, id__gt=last_id)
        .select_related("sender")
        .order_by("id")
    )

    data = []
    for m in messages:
        data.append({
            "id": m.id,
            "sender": m.sender.get_full_name() or m.sender.username,
            "content": m.content,
            "timestamp": m.created_at.strftime("%b %d, %Y %H:%M"),
            "is_self": m.sender == request.user,
        })

    return JsonResponse({"messages": data})


def mark_as_read(request, convo):
    convo.messages.exclude(sender=request.user).filter(is_read=False).update(is_read=True)

from django.http import JsonResponse
from .models import Message
from django.contrib.auth.decorators import login_required

@login_required
def unread_message_count_api(request):
    """
    Returns the total count of unread messages for the logged-in user.
    Optimized to use the database index we created.
    """
    count = Message.objects.filter(
        conversation__participants=request.user,
        is_read=False
    ).exclude(sender=request.user).count()
    
    return JsonResponse({'count': count})