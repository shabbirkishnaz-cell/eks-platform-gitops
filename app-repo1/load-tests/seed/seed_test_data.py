import requests

BASE_URL = "http://localhost:8080"
PASSWORD = "Password123!"
TOTAL_USERS = 50
TODOS_PER_USER = 5


def safe_post(url, payload):
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code, r.text
    except Exception as e:
        return None, str(e)


def main():
    for i in range(1, TOTAL_USERS + 1):
        username = f"user{i}"

        # 1. create user
        status, body = safe_post(
            f"{BASE_URL}/api/signup",
            {
                "username": username,
                "password": PASSWORD,
            },
        )

        if status == 200:
            print(f"[OK] created user {username}")
        elif status == 409:
            print(f"[SKIP] user already exists: {username}")
        else:
            print(f"[ERROR] creating user {username}: {status} {body}")
            continue

        # 2. create sample todos
        for j in range(1, TODOS_PER_USER + 1):
            status, body = safe_post(
                f"{BASE_URL}/api/todos",
                {
                    "username": username,
                    "title": f"seed todo {j} for {username}",
                },
            )

            if status in (200, 201):
                print(f"   [OK] added todo {j} for {username}")
            else:
                print(f"   [ERROR] adding todo {j} for {username}: {status} {body}")


if __name__ == "__main__":
    main()