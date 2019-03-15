import json
import base64
from unittest.mock import Mock, patch

from django.test import TestCase, Client
from django.urls import reverse

from pca import tasks
from pca.models import *
from options.models import *

TEST_SEMESTER = '2019A'


def contains_all(l1, l2):
    return len(l1) == len(l2) and sorted(l1) == sorted(l2)


@patch('pca.models.Text.send_alert')
@patch('pca.models.Email.send_alert')
class SendAlertTestCase(TestCase):
    def setUp(self):
        course, section = get_course_and_section('CIS-160-001', TEST_SEMESTER)
        self.r = Registration(email='yo@example.com',
                              phone='+15555555555',
                              section=section)

        self.r.save()

    def test_send_alert(self, mock_email, mock_text):
        self.assertFalse(Registration.objects.get(id=self.r.id).notification_sent)
        tasks.send_alert(self.r.id, sent_by='ADM')
        self.assertTrue(mock_email.called)
        self.assertTrue(mock_text.called)
        self.assertTrue(Registration.objects.get(id=self.r.id).notification_sent)
        self.assertEqual('ADM', Registration.objects.get(id=self.r.id).notification_sent_by)

    def test_dont_resend_alert(self, mock_email, mock_text):
        self.r.notification_sent = True
        self.r.save()
        tasks.send_alert(self.r.id)
        self.assertFalse(mock_email.called)
        self.assertFalse(mock_text.called)

    def test_resend_alert_forced(self, mock_email, mock_text):
        self.r.notification_sent = True
        self.r.save()
        self.r.alert(True)
        self.assertTrue(mock_email.called)
        self.assertTrue(mock_text.called)


@patch('pca.tasks.api.get_course')
class SendAlertsForSectionTestCase(TestCase):
    def setUp(self):
        self.course, self.section = get_course_and_section('CIS-160-001', TEST_SEMESTER)
        with open('pca/mock_registrar_response.json', 'r') as f:
            self.response = json.load(f)

    def assert_should_send(self, mock_get, was_open, now_open, should_send):
        self.section.is_open = was_open
        self.section.save()

        self.response['course_status'] = 'O' if now_open else 'C'
        mock_get.return_value = self.response

        result = tasks.should_send_alert(self.section.normalized, self.course.semester)
        self.assertTrue(mock_get.called)
        self.assertEquals(result, should_send)

    def test_open_then_closed(self, mock_get):
        self.assert_should_send(mock_get, True, False, False)

    def test_closed_then_closed(self, mock_get):
        self.assert_should_send(mock_get, False, False, False)

    def test_closed_then_open(self, mock_get):
        self.assert_should_send(mock_get, False, True, True)

    def test_open_then_open(self, mock_get):
        # was_open shouldn't have an effect on sending without perpetual notifications
        self.assert_should_send(mock_get, True, True, True)


class CollectRegistrationTestCase(TestCase):
    def setUp(self):
        self.sections = []
        self.sections.append(get_course_and_section('CIS-160-001', TEST_SEMESTER)[1])
        self.sections.append(get_course_and_section('CIS-160-002', TEST_SEMESTER)[1])
        self.sections.append(get_course_and_section('CIS-160-001', '2018A')[1])
        self.sections.append(get_course_and_section('CIS-120-001', TEST_SEMESTER)[1])

    def test_no_registrations(self):
        result = tasks.collect_registrations(TEST_SEMESTER)
        self.assertEqual(0, len(result))

    def test_one_registration(self):
        r = Registration(email='e@example.com', section=self.sections[0])
        r.save()
        result = tasks.collect_registrations(TEST_SEMESTER)
        self.assertEqual(1, len(result))
        self.assertTrue(contains_all(result[self.sections[0].normalized], [r.id]))

    def test_two_classes(self):
        r1 = Registration(email='e@example.com', section=self.sections[0])
        r2 = Registration(email='e@example.com', section=self.sections[3])
        r1.save()
        r2.save()
        result = tasks.collect_registrations(TEST_SEMESTER)
        self.assertDictEqual(result, {
            self.sections[0].normalized: [r1.id],
            self.sections[3].normalized: [r2.id]
        })

    def test_only_current_semester(self):
        r1 = Registration(email='e@example.com', section=self.sections[0])
        r2 = Registration(email='e@example.com', section=self.sections[2])
        r1.save()
        r2.save()
        result = tasks.collect_registrations(TEST_SEMESTER)
        self.assertDictEqual(result, {
            self.sections[0].normalized: [r1.id]
        })

    def test_two_sections(self):
        r1 = Registration(email='e@example.com', section=self.sections[0])
        r2 = Registration(email='e@example.com', section=self.sections[1])
        r1.save()
        r2.save()
        result = tasks.collect_registrations(TEST_SEMESTER)
        self.assertDictEqual(result, {
            self.sections[0].normalized: [r1.id],
            self.sections[1].normalized: [r2.id]
        })

    def test_two_registrations_same_section(self):
        r1 = Registration(email='e@example.com', section=self.sections[0])
        r2 = Registration(email='v@example.com', section=self.sections[0])
        r1.save()
        r2.save()
        result = tasks.collect_registrations(TEST_SEMESTER)
        self.assertEqual(1, len(result))
        self.assertTrue(contains_all([r1.id, r2.id], result[self.sections[0].normalized]))

    def test_only_unused_registrations(self):
        r1 = Registration(email='e@example.com', section=self.sections[0])
        r2 = Registration(email='v@example.com', section=self.sections[0], notification_sent=True)
        r1.save()
        r2.save()
        result = tasks.collect_registrations(TEST_SEMESTER)
        self.assertEqual(1, len(result))
        self.assertTrue(contains_all([r1.id], result[self.sections[0].normalized]))


class RegisterTestCase(TestCase):
    def setUp(self):
        self.sections = []
        self.sections.append(get_course_and_section('CIS-160-001', TEST_SEMESTER)[1])
        self.sections.append(get_course_and_section('CIS-160-002', TEST_SEMESTER)[1])
        self.sections.append(get_course_and_section('CIS-120-001', TEST_SEMESTER)[1])

    def test_successful_registration(self):
        res = register_for_course(self.sections[0].normalized, 'e@example.com', '+15555555555')
        self.assertEqual(RegStatus.SUCCESS, res)
        self.assertEqual(1, len(Registration.objects.all()))
        r = Registration.objects.get()
        self.assertEqual(self.sections[0].normalized, r.section.normalized)
        self.assertEqual('e@example.com', r.email)
        self.assertEqual('+15555555555', r.phone)
        self.assertFalse(r.notification_sent)

    def test_duplicate_registration(self):
        r1 = Registration(email='e@example.com', phone='+15555555555', section=self.sections[0])
        r1.save()
        res = register_for_course(self.sections[0].normalized, 'e@example.com', '+15555555555')
        self.assertEqual(RegStatus.OPEN_REG_EXISTS, res)
        self.assertEqual(1, len(Registration.objects.all()))

    def test_reregister(self):
        r1 = Registration(email='e@example.com', phone='+15555555555', section=self.sections[0], notification_sent=True)
        r1.save()
        res = register_for_course(self.sections[0].normalized, 'e@example.com', '+15555555555')
        self.assertEqual(RegStatus.SUCCESS, res)
        self.assertEqual(2, len(Registration.objects.all()))

    def test_sameuser_diffsections(self):
        r1 = Registration(email='e@example.com', phone='+15555555555', section=self.sections[0])
        r1.save()
        res = register_for_course(self.sections[1].normalized, 'e@example.com', '+15555555555')
        self.assertEqual(RegStatus.SUCCESS, res)
        self.assertEqual(2, len(Registration.objects.all()))

    def test_sameuser_diffcourse(self):
        r1 = Registration(email='e@example.com', phone='+15555555555', section=self.sections[0])
        r1.save()
        res = register_for_course(self.sections[2].normalized, 'e@example.com', '+15555555555')
        self.assertEqual(RegStatus.SUCCESS, res)
        self.assertEqual(2, len(Registration.objects.all()))

    def test_justemail(self):
        res = register_for_course(self.sections[0].normalized, 'e@example.com', None)
        self.assertEqual(RegStatus.SUCCESS, res)
        self.assertEqual(1, len(Registration.objects.all()))

    def test_justphone(self):
        res = register_for_course(self.sections[0].normalized, None, '5555555555')
        self.assertEqual(RegStatus.SUCCESS, res)
        self.assertEqual(1, len(Registration.objects.all()))

    def test_nocontact(self):
        res = register_for_course(self.sections[0].normalized, None, None)
        self.assertEqual(RegStatus.NO_CONTACT_INFO, res)
        self.assertEqual(0, len(Registration.objects.all()))


class ResubscribeTestCase(TestCase):
    def setUp(self):
        _, self.section = get_course_and_section('CIS-160-001', TEST_SEMESTER)
        self.base_reg = Registration(email='e@example.com', phone='+15555555555', section=self.section)
        self.base_reg.save()

    def test_resubscribe(self):
        self.base_reg.notification_sent = True
        self.base_reg.save()
        reg = self.base_reg.resubscribe()
        self.assertNotEqual(reg, self.base_reg)
        self.assertEqual(self.base_reg, reg.resubscribed_from)

    def test_try_resubscribe_noalert(self):
        reg = self.base_reg.resubscribe()
        self.assertEqual(reg, self.base_reg)
        self.assertIsNone(reg.resubscribed_from)

    def test_resubscribe_oldlink(self):
        """following the resubscribe chain from an old link"""
        self.base_reg.notification_sent = True
        self.base_reg.save()
        reg1 = Registration(email='e@example.com',
                            phone='+15555555555',
                            section=self.section,
                            resubscribed_from=self.base_reg,
                            notification_sent=True)
        reg1.save()
        reg2 = Registration(email='e@example.com',
                            phone='+15555555555',
                            section=self.section,
                            resubscribed_from=reg1,
                            notification_sent=True)
        reg2.save()

        result = self.base_reg.resubscribe()
        self.assertEqual(4, len(Registration.objects.all()))
        self.assertEqual(result.resubscribed_from, reg2)

    def test_resubscribe_oldlink_noalert(self):
        """testing idempotence on old links"""
        self.base_reg.notification_sent = True
        self.base_reg.save()
        reg1 = Registration(email='e@example.com',
                            phone='+15555555555',
                            section=self.section,
                            resubscribed_from=self.base_reg,
                            notification_sent=True)
        reg1.save()
        reg2 = Registration(email='e@example.com',
                            phone='+15555555555',
                            section=self.section,
                            resubscribed_from=reg1,
                            notification_sent=True)
        reg2.save()
        reg3 = Registration(email='e@example.com',
                            phone='+15555555555',
                            section=self.section,
                            resubscribed_from=reg2,
                            notification_sent=False)
        reg3.save()

        result = self.base_reg.resubscribe()
        self.assertEqual(4, len(Registration.objects.all()))
        self.assertEqual(result, reg3)


class WebhookTriggeredAlertTestCase(TestCase):
    def setUp(self):
        _, self.section = get_course_and_section('CIS-160-001', TEST_SEMESTER)
        self.r1 = Registration(email='e@example.com', phone='+15555555555', section=self.section)
        self.r2 = Registration(email='f@example.com', phone='+15555555556', section=self.section)
        self.r3 = Registration(email='g@example.com', phone='+15555555557', section=self.section)
        self.r1.save()
        self.r2.save()
        self.r3.save()

    def test_collect_all(self):
        result = tasks.get_active_registrations(self.section.normalized, TEST_SEMESTER)
        expected_ids = [r.id for r in [self.r1, self.r2, self.r3]]
        result_ids = [r.id for r in result]
        for id_ in expected_ids:
            self.assertTrue(id_ in result_ids)

        for id_ in result_ids:
            self.assertTrue(id_ in expected_ids)

    def test_collect_none(self):
        get_course_and_section('CIS-121-001', TEST_SEMESTER)
        result = tasks.get_active_registrations('CIS-121-001', TEST_SEMESTER)
        self.assertTrue(len(result) == 0)

    def test_collect_one(self):
        self.r2.notification_sent = True
        self.r3.notification_sent = True
        self.r2.save()
        self.r3.save()
        result_ids = [r.id for r in tasks.get_active_registrations(self.section.normalized, TEST_SEMESTER)]
        expected_ids = [self.r1.id]
        for id_ in expected_ids:
            self.assertTrue(id_ in result_ids)
        for id_ in result_ids:
            self.assertTrue(id_ in expected_ids)

    def test_collect_some(self):
        self.r2.notification_sent = True
        self.r2.save()
        result_ids = [r.id for r in tasks.get_active_registrations(self.section.normalized, TEST_SEMESTER)]
        expected_ids = [self.r1.id, self.r3.id]
        for id_ in expected_ids:
            self.assertTrue(id_ in result_ids)
        for id_ in result_ids:
            self.assertTrue(id_ in expected_ids)


@patch('pca.views.alert_for_course')
class WebhookViewTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        auth = base64.standard_b64encode('webhook:password'.encode('ascii'))
        self.headers = {
            'Authorization': f'Basic {auth.decode()}',
        }
        self.body = {
            "course_section": "ANTH361401",
            "previous_status": "X",
            "status": "O",
            "status_code_normalized": "Open",
            "term": "2019A"
        }
        Option.objects.update_or_create(key='SEND_FROM_WEBHOOK', value_type='BOOL', defaults={'value': 'TRUE'})

    def test_alert_called_and_sent(self, mock_alert):
        res = self.client.post(
            reverse('webhook'),
            data=json.dumps(self.body),
            content_type='application/json',
            **self.headers)

        self.assertEqual(200, res.status_code)
        self.assertTrue(mock_alert.called)
        self.assertEqual('ANTH-361-401', mock_alert.call_args[0][0])
        self.assertEqual('2019A', mock_alert.call_args[1]['semester'])
        self.assertTrue('sent' in json.loads(res.content)['message'])
        self.assertEqual(1, CourseUpdate.objects.count())
        u = CourseUpdate.objects.get()
        self.assertTrue(u.alert_sent)

    def test_alert_bad_json(self, mock_alert):
        res = self.client.post(
            reverse('webhook'),
            data='blah',
            content_type='application/json',
            **self.headers)

        self.assertEqual(400, res.status_code)
        self.assertFalse(mock_alert.called)
        self.assertEqual(0, CourseUpdate.objects.count())

    def test_alert_called_closed_course(self, mock_alert):
        self.body['status'] = 'C'
        self.body['status_code_normalized'] = 'Closed'
        res = self.client.post(
            reverse('webhook'),
            data=json.dumps(self.body),
            content_type='application/json',
            **self.headers)

        self.assertEqual(200, res.status_code)
        self.assertFalse('sent' in json.loads(res.content)['message'])
        self.assertFalse(mock_alert.called)
        self.assertEqual(1, CourseUpdate.objects.count())
        u = CourseUpdate.objects.get()
        self.assertFalse(u.alert_sent)

    def test_alert_called_alerts_off(self, mock_alert):
        Option.objects.update_or_create(key='SEND_FROM_WEBHOOK', value_type='BOOL', defaults={'value': 'FALSE'})
        res = self.client.post(
            reverse('webhook'),
            data=json.dumps(self.body),
            content_type='application/json',
            **self.headers)

        self.assertEqual(200, res.status_code)
        self.assertFalse('sent' in json.loads(res.content)['message'])
        self.assertFalse(mock_alert.called)
        self.assertEqual(1, CourseUpdate.objects.count())
        u = CourseUpdate.objects.get()
        self.assertFalse(u.alert_sent)

    def test_bad_format(self, mock_alert):
        self.body = {'hello': 'world'}
        res = self.client.post(
            reverse('webhook'),
            data=json.dumps({
                "hello": "world"
            }),
            content_type='application/json',
            **self.headers)
        self.assertEqual(400, res.status_code)
        self.assertFalse(mock_alert.called)
        self.assertEqual(0, CourseUpdate.objects.count())

    def test_no_status(self, mock_alert):
        res = self.client.post(
            reverse('webhook'),
            data=json.dumps({
                "course_section": "ANTH361401",
                "previous_status": "X",
                "status_code_normalized": "Open",
                "term": "2019A"
            }),
            content_type='application/json',
            **self.headers)
        self.assertEqual(400, res.status_code)
        self.assertFalse(mock_alert.called)
        self.assertEqual(0, CourseUpdate.objects.count())

    def test_wrong_method(self, mock_alert):
        res = self.client.get(reverse('webhook'), **self.headers)
        self.assertEqual(405, res.status_code)
        self.assertFalse(mock_alert.called)
        self.assertEqual(0, CourseUpdate.objects.count())

    def test_wrong_content(self, mock_alert):
        res = self.client.post(reverse('webhook'),
                               **self.headers)
        self.assertEqual(415, res.status_code)
        self.assertFalse(mock_alert.called)
        self.assertEqual(0, CourseUpdate.objects.count())

    def test_wrong_password(self, mock_alert):
        self.headers['Authorization'] = 'Basic ' + base64.standard_b64encode('webhook:abc123'.encode('ascii')).decode()
        res = self.client.post(
            reverse('webhook'),
            data=json.dumps(self.body),
            content_type='application/json',
            **self.headers)
        self.assertEqual(401, res.status_code)
        self.assertFalse(mock_alert.called)
        self.assertEqual(0, CourseUpdate.objects.count())

    def test_wrong_user(self, mock_alert):
        self.headers['Authorization'] = 'Basic ' + base64.standard_b64encode('baduser:password'.encode('ascii')).decode()
        res = self.client.post(
            reverse('webhook'),
            data=json.dumps(self.body),
            content_type='application/json',
            **self.headers)
        self.assertEqual(401, res.status_code)
        self.assertFalse(mock_alert.called)
        self.assertEqual(0, CourseUpdate.objects.count())
