from django.test import RequestFactory, TestCase, Client
from django.contrib.auth.models import AnonymousUser, User
from django.contrib.auth import authenticate, login, logout
from magazine.models import Customer
from .forms import SignupForm

class ProfileTests(TestCase):
    def setUp(self):
        """
        Create some data for testing
        """
        username = 'jdoe'
        password = 'Passw0rd'
        email = 'jdoe@me.org'
        new_user = User.objects.create_user(username=username, email=email)
        new_user.set_password(password)
        new_user.save()
        new_customer = Customer()
        new_customer.user = new_user
        new_customer.save()

        self.factory = RequestFactory()
        self.user = new_user

    def test_user_creation(self):
        """
        Test new user creation.
        """
        username = 'Smith'
        password = 'password'
        email = 'smith@me.org'
        new_user = User.objects.create_user(username)
        new_user.set_password(password)
        new_user.email = email
        new_user.save()
        new_customer = Customer()
        new_customer.user = new_user
        new_customer.save()
        self.assertEqual(username, new_user.username)
        self.assertEqual(email, new_user.email)
        self.assertTrue(authenticate(username=new_user.username, password=password))

    def test_signup_form_valid(self):
        form = SignupForm(data={ 'username': 'steve', 'email': 'steve@me.org',
                'password1': 'greatestkey', 'password2': 'greatestkey' })
        self.assertTrue(form.is_valid())

    def test_signup_form_not_valid(self):
        form = SignupForm(data={ 'username': 'steve', 'email': 'steve@me.org',
                'password1': 'greatestkey', 'password2': 'NOGREATKEY' })
        self.assertFalse(form.is_valid())