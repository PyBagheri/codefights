from django.test import TestCase, TransactionTestCase

from unittest import mock
import datetime
import pytz

from django.db.utils import IntegrityError
from django.core.exceptions import ValidationError

from accounts.models import User


class UserTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='dummy',
                                            email='dummy@dummy.com',
                                            password='dummy')
    
    def test_field_labels(self):
        fields_and_labels = {
            'username': 'username',
            'email': 'email',
            'is_staff': 'is staff',
            'is_active': 'is active',
            'last_login': 'last login',
            'date_joined': 'date joined',
        }
        
        for (field, label) in fields_and_labels.items():
            with self.subTest(field=field):
                self.assertEqual(self.user._meta.get_field(field).verbose_name, label)
            
    
    def test_max_length_username(self):
        user = User.objects.get(id=1)
        self.assertEqual(user._meta.get_field('username').max_length, 50)
        
    def test_max_length_email(self):
        user = User.objects.get(id=1)
        self.assertEqual(user._meta.get_field('email').max_length, 255)
    
    def test_str_gives_username(self):
        user = User.objects.get(id=1)
        self.assertEqual(str(user), user.username)
    
    def test_username_field_is_username(self):
        self.assertEqual(User.USERNAME_FIELD, 'username')
        
    def test_email_field_is_email(self):
        self.assertEqual(User.EMAIL_FIELD, 'email')
    
    def test_invalid_usernames(self):
        for i, username in enumerate([
            'lt5',  # less than 5 chars
            '_no_leading_underscores',
            'illegal_chars_$$$',
            'non_latin_digits_۱۲۳',
        ]):
            with self.subTest(username=username):
                user = User.objects.create_user(username=username,
                                                email=f'dummyinvunm{i}@dummy.com',
                                                password='dummy')
                self.assertRaises(ValidationError, user.full_clean)

    
    def test_default_value_of_is_staff(self):
        self.assertEqual(self.user.is_staff, False)
        
    def test_default_value_of_is_active(self):
        # before the email is validated, the user
        # should be inactive.
        self.assertEqual(self.user.is_staff, False)
        
    def test_date_joined_auto_now_add(self):
        mocked_date = datetime.datetime(2015, 10, 5, 0, 0, 0, tzinfo=pytz.utc)
        with mock.patch('django.utils.timezone.now', mock.Mock(return_value=mocked_date)):
            user = User.objects.create_user(username='dummydate',
                                            email='dummydate@dummy.com',
                                            password='dummy')
            self.assertEqual(user.date_joined, mocked_date)

    def test_last_login_is_blank_after_registration(self):
        # a login has not happened after the registration.
        self.assertIsNone(self.user.last_login)


class TransactionUserTests(TransactionTestCase):
    """Tests that will depend upon the transaction behavior
    of the SQL database.
    
    Uniqueness Tests:
      Since TestCase wraps the entire test class and
      each method in atomic blocks, once a command
      raises a DatabaseError (e.g., IntegrityError),
      the entire transaction is aborted, unless we
      use nested atomic blocks (inner ones will create 
      savepoints in the transaction) and wrap the inner
      atomic blocks in try-catch (so that Django rolls
      back to the savepoint once an error happens and
      thus prevents the error from bubbling up and clogging
      the upper atomic block, which might be the test
      function).
      
      One other way is to simply use TransactionTestCase,
      which runs each test in its own transaction (i.e.,
      doesn't wrap everything in a single transaction).
      The compromise is that the database has to lock and
      unlock the data for each transaction, and thus our
      tests might go slowly. So we only use them in appropriate
      cases, one of which is testing for uniqueness.
    """
    
    def test_lowercase_username_is_unique(self):
        User.objects.create_user(username='nonlowerunique',
                                 email='test1@dummy.com',
                                 password='dummy')
        
        with self.assertRaises(IntegrityError):
            User.objects.create_user(username='NoNlOwErUnIqUe',
                                     email='test2@dummy.com',
                                     password='dummy')
    
    
    def test_email_is_unique(self):
        User.objects.create_user(username='dummy1',
                                 email='nonunique@dummy.com',
                                 password='dummy')
        
        with self.assertRaises(IntegrityError):
            User.objects.create_user(username='dummy2',
                                     email='nonunique@dummy.com',
                                     password='dummy')
