import re
import base64

from django.shortcuts import render
from django.http import HttpResponseRedirect, JsonResponse, Http404, HttpResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from .models import *
from .tasks import generate_course_json, send_course_alerts
from options.models import get_bool


# Helper function to return the homepage with a banner message.
def homepage_with_msg(request, type_, msg):
    return render(request, 'index.html', {
        'notification': {
            'type': type_,
            'text': msg
        }
    })


def homepage_closed(request):
    return homepage_with_msg(request,
                             'danger',
                             "We're currently closed for signups. Come back after schedules have been released!")


def index(request):
    if not get_bool('REGISTRATION_OPEN', True):
        return homepage_closed(request)

    return render(request, 'index.html')


def register(request):
    if not get_bool('REGISTRATION_OPEN', True):
        return HttpResponseRedirect(reverse('index'))

    if request.method == 'POST':
        course_code = request.POST.get('course', None)
        email_address = request.POST.get('email', None)
        phone = request.POST.get('phone', None)

        res = register_for_course(course_code, email_address, phone)

        if res == RegStatus.SUCCESS:
            return homepage_with_msg(request,
                                     'success',
                                     'Your registration for %s was successful!' % course_code)
        elif res == RegStatus.OPEN_REG_EXISTS:
            return homepage_with_msg(request,
                                     'warning',
                                     "You've already registered to get alerts for %s!" % course_code)
        elif res == RegStatus.NO_CONTACT_INFO:
            return homepage_with_msg(request,
                                     'danger',
                                     'Please enter either a phone number or an email address.')
        else:
            return homepage_with_msg(request,
                                     'warning',
                                     'There was an error on our end. Please try again!')
    else:
        raise Http404('GET not accepted')


def resubscribe(request, id_):
    if not Registration.objects.filter(id=id_).exists():
        raise Http404('No registration found')
    else:
        old_reg = Registration.objects.get(id=id_)
        new_reg = old_reg.resubscribe()
        return homepage_with_msg(request,
                                 'info',
                                 'You have been resubscribed for alerts to %s!' % new_reg.section.normalized)


def get_sections(request):
    sections = generate_course_json()
    return JsonResponse(sections, safe=False)


course_id_re = re.compile(r'([A-Z]{3,4})(\d{3})(\d{3})')


def normalize_course_id(c):
    m = course_id_re.match(c)
    if m:
        return f'{m.group(1)}-{m.group(2)}-{m.group(3)}'
    else:
        return None


def alert_for_course(c_id, semester, sent_by):
    send_course_alerts.delay(c_id, semester=semester, sent_by=sent_by)


def extract_basic_auth(auth_header):
    """
    extract username and password from a basic auth header
    :param auth_header: content of the Authorization HTTP header
    :return: username and password extracted from the header
    """
    parts = auth_header.split(' ')
    if parts[0] != 'Basic' or len(parts) < 2:
        return None, None

    auth_parts = base64.b64decode(parts[1]).split(b':')
    if len(auth_parts) < 2:
        return None, None
    return auth_parts[0].decode(), auth_parts[1].decode()


@csrf_exempt
def accept_webhook(request):
    auth_header = request.META.get('Authorization', request.META.get('HTTP_AUTHORIZATION', ''))

    username, password = extract_basic_auth(auth_header)

    if username != settings.WEBHOOK_USERNAME or \
            password != settings.WEBHOOK_PASSWORD:
        return HttpResponse('''Your credentials cannot be verified. 
        They should be placed in the header as &quot;Authorization-Bearer&quot;,  
        YOUR_APP_ID and &quot;Authorization-Token&quot; , YOUR_TOKEN"''', status=401)

    if request.method != 'POST':
        return HttpResponse('Methods other than POST are not allowed', status=405)

    if 'json' not in request.content_type.lower():
        return HttpResponse('Request expected in JSON', status=415)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponse('Error decoding JSON body', status=400)

    course_id = data.get('result_data', [{}])[0].get('course_section', None)
    if course_id is None:
        return HttpResponse('Course ID could not be extracted', 400)

    course_status = data.get('result_data', [{}])[0].get('status', None)
    if course_status is None:
        return HttpResponse('Course Status could not be extracted from response', 400)

    course_term = data.get('result_data', [{}])[0].get('term', None)
    if course_term is None:
        return HttpResponse('Course Term could not be extracted from response', 400)

    course_id_normalized = normalize_course_id(data['result_data'][0]['course_section'])

    if get_bool('SEND_FROM_WEBHOOK', False) and course_status == 'O':
        alert_for_course(course_id_normalized, semester=course_term, sent_by='WEB')
        return JsonResponse({'message': 'webhook recieved, alerts sent'})

    else:
        return JsonResponse({'message': 'webhook recieved'})
