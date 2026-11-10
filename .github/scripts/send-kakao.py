import json
import os
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def post(url, form, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    request = Request(url, data=urlencode(form).encode(), headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        raise SystemExit(f"Kakao API request failed (HTTP {error.code}).") from None


def main():
    tokens = post("https://kauth.kakao.com/oauth/token", {
        "grant_type": "refresh_token",
        "client_id": os.environ["KAKAO_REST_API_KEY"],
        "client_secret": os.environ["KAKAO_CLIENT_SECRET"],
        "refresh_token": os.environ["KAKAO_REFRESH_TOKEN"],
    })
    if tokens.get("refresh_token"):
        print("::warning::Kakao rotated the refresh token. Run setup-kakao.py again.")
    result = post("https://kapi.kakao.com/v2/api/talk/memo/default/send", {
        "template_object": json.dumps({
            "object_type": "text",
            "text": "체험단 알림 테스트입니다. 실제 신청은 실행하지 않았습니다.",
            "link": {
                "web_url": "https://gwangchul2.github.io/stylec-auto/",
                "mobile_web_url": "https://gwangchul2.github.io/stylec-auto/",
            },
        }),
    }, tokens["access_token"])
    if result.get("result_code") != 0:
        raise SystemExit("Kakao did not confirm message delivery.")
    print("Kakao accepted the test message.")


if __name__ == "__main__":
    main()
