import requests


def test_unauthenticated_request_is_rejected(service_url):
    response = requests.get(service_url, timeout=10)
    assert response.status_code == 403


def test_health(service_url, id_token):
    response = requests.get(
        f"{service_url}/health",
        headers={"Authorization": f"Bearer {id_token}"},
        timeout=10,
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_recent_emails_shape(service_url, id_token):
    response = requests.get(
        f"{service_url}/api/v1/emails/recent",
        headers={"Authorization": f"Bearer {id_token}"},
        params={"maxResults": 3},
        timeout=30,
    )
    assert response.status_code == 200

    body = response.json()
    assert "messages" in body
    assert "resultSizeEstimate" in body

    for message in body["messages"]:
        assert set(message.keys()) == {
            "id",
            "threadId",
            "snippet",
            "labelIds",
            "headers",
        }
        # Structural read-only guarantee: no raw payload/body content ever
        # leaves the sanitizer, only the whitelisted header fields.
        assert set(message["headers"].keys()) <= {"From", "To", "Subject", "Date"}


def test_show_most_recent_email(service_url, id_token):
    """Not a real assertion - run with `-s` to print the latest email."""
    response = requests.get(
        f"{service_url}/api/v1/emails/recent",
        headers={"Authorization": f"Bearer {id_token}"},
        params={"maxResults": 1},
        timeout=30,
    )
    assert response.status_code == 200

    messages = response.json()["messages"]
    assert messages, "no messages returned"

    message = messages[0]
    print("\n--- most recent email ---")
    for field in ("From", "Date", "Subject"):
        print(f"{field}: {message['headers'].get(field, '')}")
    print(f"Snippet: {message['snippet']}")
