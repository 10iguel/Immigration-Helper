import pytest

from immigration_helper.accounts import AccountService, EmailAddress, EmailTakenError, InvalidCredentialsError
from immigration_helper.accounts.passwords import hash_password, verify_password
from tests.fakes import InMemoryUserStore

EMAIL = EmailAddress("Ana@Example.com")
PASSWORD = "correct horse battery"


def test_email_is_stored_lowercase_and_must_look_like_an_email():
    assert EMAIL.value == "ana@example.com"
    with pytest.raises(ValueError):
        EmailAddress("not-an-email")


def test_password_hash_is_salted_and_verifies():
    first, second = hash_password(PASSWORD), hash_password(PASSWORD)

    assert first != second  # different salt each time
    assert PASSWORD not in first
    assert verify_password(PASSWORD, first)
    assert not verify_password("wrong password", first)


def test_sign_up_then_log_in_starts_sessions_for_the_same_user():
    users = InMemoryUserStore()
    accounts = AccountService(users)

    signed_up = accounts.sign_up(EMAIL, PASSWORD)
    logged_in = accounts.log_in(EmailAddress("ana@example.com"), PASSWORD)

    assert accounts.user_for(signed_up.token) == accounts.user_for(logged_in.token) == signed_up.user
    assert signed_up.token not in users.sessions  # only the token's hash is stored


def test_sign_up_rejects_a_taken_email_and_a_short_password():
    accounts = AccountService(InMemoryUserStore())
    accounts.sign_up(EMAIL, PASSWORD)

    with pytest.raises(EmailTakenError):
        accounts.sign_up(EMAIL, PASSWORD)
    with pytest.raises(ValueError):
        accounts.sign_up(EmailAddress("bo@example.com"), "short")


@pytest.mark.parametrize("email, password", [("ana@example.com", "wrong password"), ("nobody@example.com", PASSWORD)])
def test_log_in_fails_the_same_way_for_a_wrong_password_or_an_unknown_email(email, password):
    accounts = AccountService(InMemoryUserStore())
    accounts.sign_up(EMAIL, PASSWORD)

    with pytest.raises(InvalidCredentialsError):
        accounts.log_in(EmailAddress(email), password)


def test_log_out_ends_the_session():
    accounts = AccountService(InMemoryUserStore())
    session = accounts.sign_up(EMAIL, PASSWORD)

    accounts.log_out(session.token)

    assert accounts.user_for(session.token) is None
