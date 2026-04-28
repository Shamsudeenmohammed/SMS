# communications/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import CustomUser


User = settings.AUTH_USER_MODEL


def get_profile(user):
    """Helper to fetch the user's profile (admin, teacher, parent, accountant)."""
    for attr in ["admin_profile", "teacher_profile", "parent_profile", "accountant_profile"]:
        if hasattr(user, attr):
            return getattr(user, attr)
    return None


# ======================================================
# 🔹 Conversation Model
# ======================================================
class Conversation(models.Model):
    """A conversation between multiple users (group or 1:1)."""
    name = models.CharField(max_length=255, blank=True)
    participants = models.ManyToManyField(User, related_name="conversations")
    is_group = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name or f"Conversation {self.id}"


# ======================================================
# 🔹 Message Model (with Email Notifications)
# ======================================================
# communications/models.py

class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, related_name="sent_messages"
    )
    content = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    edited = models.BooleanField(default=False)
    is_system = models.BooleanField(default=False)
    
    # ✅ For 1:1 chats, this is highly efficient
    # For group chats, we'll use the MessageSeen table below
    is_read = models.BooleanField(default=False)

    search_vector = SearchVectorField(null=True, editable=False)

    class Meta:
        indexes = [
            GinIndex(fields=["search_vector"]),
            # makes unread count queries lightning fast.
            models.Index(fields=['conversation', 'is_read']), 
        ]
        ordering = ["created_at"]

    def __str__(self):
        return f"Message {self.pk} by {self.sender}"

    # ✅ Email Notification Method
    def send_email_notification(self):
        """
        Sends email notifications to all conversation participants (Admin, Teacher, Parent, Accountant)
        except the sender. Works with Gmail configuration in settings.py.
        """
        if not self.sender:
            return

        # Get recipients (exclude sender)
        recipients = (
            self.conversation.participants.exclude(id=self.sender.id)
            .values_list("email", flat=True)
        )

        subject = f"New Message from {self.sender.get_full_name() or self.sender.username}"
        message_body = (
            f"You have a new message in your school communication portal.\n\n"
            f"From: {self.sender.get_full_name() or self.sender.username}\n"
            f"Message:\n{self.content}\n\n"
            f"Please log in to reply or view attachments.\n"
            f"{getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')}/communications/"
        )

        if recipients:
            send_mail(
                subject=subject,
                message=message_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=list(recipients),
                fail_silently=True,
            )



# ======================================================
# 🔹 Message Read Tracking (For Group/Scalable Chats)
# ======================================================
class MessageSeen(models.Model):
    """Tracks which user has read which message in group conversations."""
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="seen_by")
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="viewed_messages")
    seen_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('message', 'user')
        indexes = [
            models.Index(fields=['user', 'message']),
        ]


# ======================================================
# 🔹 Signal to Send Email After Message Creation
# ======================================================
@receiver(post_save, sender=Message)
def notify_conversation_participants(sender, instance, created, **kwargs):
    """Automatically notify conversation members by email after new message."""
    if created and not instance.is_system:
        instance.send_email_notification()


# ======================================================
# 🔹 File Attachment Model
# ======================================================
class Attachment(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="message_uploads/%Y/%m/%d/")
    original_name = models.CharField(max_length=260, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_name or self.file.name


# ======================================================
# 🔹 Message Flagging / Moderation
# ======================================================
class MessageFlag(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="flags")
    flagged_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="resolved_flags"
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Flag on Message {self.message.id} by {self.flagged_by}"
