from background_task import background
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.utils.timezone import now
from accounts.models import CustomUser
from uuid import UUID

@background(schedule=0)
def send_otp_email_async(user_id_str, otp):
    user_id = UUID(user_id_str)
    try:
        user = CustomUser.objects.get(pk=user_id)
    except CustomUser.DoesNotExist:
        return  # user deleted or invalid – silently skip

    # Smart fallback for name
    if user.username:
        name = user.username
    elif user.first_name or user.last_name:
        name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    else:
        name = user.email

    subject = "Your DMS Password Reset OTP"
    from_email = None  # uses DEFAULT_FROM_EMAIL from settings
    to = [user.email]

    context = {
        "name": name,
        "otp": otp,
        "year": now().year
    }

    html_content = render_to_string("emails/otp_email.html", context)
    text_content = f"Hello {name},\n\nYour OTP for password reset is: {otp}\n\nThis OTP is valid for 5 minutes."

    email = EmailMultiAlternatives(subject, text_content, from_email, to)
    email.attach_alternative(html_content, "text/html")
    email.send()
    
@background(schedule=0)
def send_set_password_otp_email_async(user_id_str, otp):
    user_id = UUID(user_id_str)
    try:
        user = CustomUser.objects.get(pk=user_id)
    except CustomUser.DoesNotExist:
        return

    name = user.first_name or user.email
    subject = "Set Your DMS Password"
    from_email = None
    to = [user.email]

    context = {
        "name": name,
        "otp": otp,
        "year": now().year
    }

    html_content = render_to_string("emails/otp_set_password_email.html", context)
    text_content = f"Hello {name},\n\nYour OTP to set your password is: {otp}\n\nThis OTP is valid for 5 minutes."

    email = EmailMultiAlternatives(subject, text_content, from_email, to)
    email.attach_alternative(html_content, "text/html")
    email.send()

@background(schedule=0)
def send_welcome_email_async(user_id_str, is_client_admin=False):
    user_id = UUID(user_id_str)
    try:
        user = CustomUser.objects.get(pk=user_id)
    except CustomUser.DoesNotExist:
        return

    name = user.username or user.first_name or user.email
    subject = "Welcome to DMS" if not is_client_admin else "You are now a Client Admin"
    from_email = None
    to = [user.email]

    context = {
        "name": name,
        "year": now().year
    }

    template = "emails/welcome_client_admin.html" if is_client_admin else "emails/welcome_user.html"

    html_content = render_to_string(template, context)
    text_content = f"Hello {name},\n\nYour account has been created successfully.\n\nThanks,\nThe DMS Team"

    email = EmailMultiAlternatives(subject, text_content, from_email, to)
    email.attach_alternative(html_content, "text/html")
    email.send()

@background(schedule=0)
def send_registration_pending_email_async(user_id_str):
    user_id = UUID(user_id_str)
    try:
        user = CustomUser.objects.get(pk=user_id)
    except CustomUser.DoesNotExist:
        return

    # Name fallback logic
    name = user.username or user.first_name or user.email
    subject = "Welcome to DMS – Pending Approval"
    from_email = None
    to = [user.email]

    context = {
        "name": name,
        "year": now().year
    }

    html_content = render_to_string("emails/pending_approval_email.html", context)
    text_content = f"""
    Hello {name},

    Thank you for registering with DMS.
    Your account is currently pending approval by the Client Admin.
    You will receive an email once your account is approved.

    Regards,
    The DMS Team
    """

    email = EmailMultiAlternatives(subject, text_content, from_email, to)
    email.attach_alternative(html_content, "text/html")
    email.send()
    
@background(schedule=0)
def send_join_request_status_email_async(email, name, status):
    subject = f"DMS Access {'Approved' if status == 'approved' else 'Rejected'}"
    from_email = None  # Uses DEFAULT_FROM_EMAIL from settings
    to = [email]

    # Select template based on status
    template = (
        "emails/join_request_approved.html"
        if status == "approved"
        else "emails/join_request_rejected.html"
    )

    context = {
        "name": name,
        "year": now().year
    }

    # Render email templates
    html_content = render_to_string(template, context)
    text_content = f"Hello {name},\n\nYour request to join DMS has been {status}. Thank you."

    # Send email
    email_msg = EmailMultiAlternatives(subject, text_content, from_email, to)
    email_msg.attach_alternative(html_content, "text/html")
    email_msg.send()

@background(schedule=0)
def send_account_deletion_email_async(email, name, role):
    subject = "Your DMS Account Has Been Deleted"
    from_email = None  # Uses DEFAULT_FROM_EMAIL
    to = [email]

    template = "emails/account_deleted.html"
    context = {
        "name": name,
        "role": role,
        "year": now().year
    }

    html_content = render_to_string(template, context)
    text_content = f"""
Hello {name},

Your DMS account with role '{role}' has been deleted by an administrator.
If this was a mistake, please contact support.

Thanks,
The DMS Team
"""

    email_msg = EmailMultiAlternatives(subject, text_content, from_email, to)
    email_msg.attach_alternative(html_content, "text/html")
    email_msg.send()
    

@background(schedule=0)
def send_password_reset_status_email_async(email, success=True):
    subject = "DMS Password Reset " + ("Successful" if success else "Failed")
    from_email = None
    to = [email]

    template = "emails/password_reset_success.html" if success else "emails/password_reset_failed.html"
    context = {"email": email, "year": now().year}

    html_content = render_to_string(template, context)
    text_content = (
        f"Hello,\n\nYour password reset was {'successful' if success else 'unsuccessful'}."
    )

    email_msg = EmailMultiAlternatives(subject, text_content, from_email, to)
    email_msg.attach_alternative(html_content, "text/html")
    email_msg.send()

@background(schedule=0)
def send_set_password_status_email_async(email, status):
    """
    Sends email notification for Set Password Success or Failure
    """
    subject = "DMS Password Set " + ("Successful" if status == "success" else "Failed")
    from_email = None
    to = [email]

    template = "emails/set_password_success.html" if status == "success" else "emails/set_password_failed.html"
    context = {"year": now().year}

    html_content = render_to_string(template, context)
    text_content = f"Your password set request was {status}. Please retry if needed."

    email_obj = EmailMultiAlternatives(subject, text_content, from_email, to)
    email_obj.attach_alternative(html_content, "text/html")
    email_obj.send()
    
@background(schedule=0)
def send_account_delete_otp_email_async(email, name, otp):
    subject = "Your OTP for Account Deletion"
    from_email = None
    to = [email]

    context = {"name": name, "otp": otp, "year": now().year}
    html_content = render_to_string("emails/account_delete_otp_email.html", context)
    text_content = f"Hello {name},\n\nYour OTP to delete your DMS account is: {otp}\nThis OTP is valid for 5 minutes."

    email_obj = EmailMultiAlternatives(subject, text_content, from_email, to)
    email_obj.attach_alternative(html_content, "text/html")
    email_obj.send()



@background(schedule=0)
def send_account_deleted_email_async(email, name):
    subject = "Your DMS Account Has Been Deleted"
    from_email = None
    to = [email]

    context = {"name": name, "year": now().year}
    html_content = render_to_string("emails/account_deleted.html", context)
    text_content = f"Hello {name},\n\nYour DMS account has been successfully deleted.\n\nIf this wasn't you, please contact support immediately."

    email_obj = EmailMultiAlternatives(subject, text_content, from_email, to)
    email_obj.attach_alternative(html_content, "text/html")
    email_obj.send()