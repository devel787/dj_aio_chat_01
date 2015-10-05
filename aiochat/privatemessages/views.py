from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Thread
from .utils import BadJsonResponse, send_message


@require_POST
@login_required
def send_message_view(request):
    req_user = request.user

    # -------------------------------------------------------------------------

    message_text = request.POST.get('message')

    if not message_text:
        return HttpResponse('No message found')

    if len(message_text) > settings.MAX_MESSAGE_LEN:
        return HttpResponse('The message is too long')

    # -------------------------------------------------------------------------

    recipient_name = request.POST.get('recipient_name')

    try:
        recipient = User.objects.get(username=recipient_name)
    except User.DoesNotExist:
        return HttpResponse('No such user')

    if recipient == req_user:
        return HttpResponse('You cannot send messages to yourself')

    # -------------------------------------------------------------------------

    thread_queryset = (
        Thread.objects
        .filter(participants=recipient)
        .filter(participants=req_user)
    )

    if thread_queryset.exists():
        thread = thread_queryset.first()
    else:
        thread = Thread.objects.create()
        thread.participants.add(req_user, recipient)

    # -------------------------------------------------------------------------

    send_message(thread.id, req_user.id, message_text, req_user.username)

    return HttpResponseRedirect(reverse('messages_view'))


@require_POST
@csrf_exempt
def send_message_api_view(request, thread_id):
    if request.POST.get('api_key') != settings.API_KEY:
        return BadJsonResponse({'error': 'Wrong API key'})

    # -------------------------------------------------------------------------

    try:
        thread = Thread.objects.get(id=thread_id)
    except Thread.DoesNotExist:
        return BadJsonResponse({'error': 'No such thread'})

    try:
        sender = User.objects.get(id=request.POST.get('sender_id'))
    except User.DoesNotExist:
        return BadJsonResponse({'error': 'No such user'})

    # -------------------------------------------------------------------------

    message_text = request.POST.get('message')

    if not message_text:
        return BadJsonResponse({'error': 'No message found'})

    if len(message_text) > settings.MAX_MESSAGE_LEN:
        return BadJsonResponse({'error': 'The message is too long'})

    # -------------------------------------------------------------------------

    send_message(thread.id, sender.id, message_text)

    return JsonResponse({'status': 'ok'})


@login_required
def messages_view(request):
    req_user = request.user

    threads = (
        Thread.objects
        .filter(participants=req_user)
        .order_by('-last_message')
    )

    for thread in threads:
        thread.partner = (
            thread
            .participants
            .exclude(id=req_user.id)
            .first()
        )

    context = {'threads': threads}

    return render(request, 'privatemessages/private_messages.html', context)


@login_required
def chat_view(request, thread_id):
    req_user = request.user

    thread = get_object_or_404(
        Thread,
        id=thread_id,
        participants__id=req_user.id
    )

    context = {
        'thread_id': thread_id,
        'thread_messages': thread.message_set.order_by('-datetime')[:32],
        'partner': thread.participants.exclude(id=req_user.id).first(),
    }

    return render(request, 'privatemessages/chat.html', context)
