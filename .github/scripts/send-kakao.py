import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

DASHBOARD = "https://gwangchul2.github.io/stylec-auto/"
TEST_TEXT = "체험단 알림 테스트입니다. 실제 신청은 실행하지 않았습니다."


def report(before, after):
    previous = {(item["at"], item["url"], item["status"]) for item in before.get("records", [])}
    entries = []
    counts = {"ok": 0, "check": 0, "fail": 0}
    for item in after.get("records", []):
        status = item["status"]
        if (item["at"], item["url"], status) in previous or status not in counts:
            continue
        counts[status] += 1
        option = f" ({item['note']})" if item.get("note") else ""
        entries.append(f"{item['title']}{option}"[:65])
    runs = after.get("runs", [])
    old_runs = before.get("runs", [])
    status = runs[-1]["status"] if runs and runs[-1:] != old_runs[-1:] else ""
    return {"counts": counts, "items": entries[:3], "status": status}


def save_report(path):
    old = subprocess.run(["git", "show", f"HEAD:{path}"], capture_output=True)
    before = json.loads(old.stdout) if old.returncode == 0 else {}
    after = json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else {}
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        print("report=" + json.dumps(report(before, after)), file=output)


def message(stylec, musinsa, outcomes):
    summary = ["[체험단 결과]"]
    items = []
    for name, info, outcome in zip(("스타일씨", "무신사"), (stylec, musinsa), outcomes):
        status = info.get("status")
        if status == "login_expired":
            summary.append(f"{name} 로그인 만료")
        elif outcome != "success" or status == "no_list":
            summary.append(f"{name} 실행 실패")
        elif not status:
            summary.append(f"{name} 실행 기록 없음")
        counts = info.get("counts", {})
        if status or any(counts.values()):
            summary.append(f"{name} 완료 {counts.get('ok', 0)} · 확인 {counts.get('check', 0)} · 실패 {counts.get('fail', 0)}")
        items.extend(info.get("items", []))
    return "\n".join(summary + items)


def post(url, form, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    request = Request(url, data=urlencode(form).encode(), headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        try:
            details = json.load(error)
        except ValueError:
            details = {}
        code = str(details.get("error_code", details.get("code", "")))
        code = code if re.fullmatch(r"(?:KOE[0-9]+|-?[0-9]+)", code) else "unknown"
        raise SystemExit(f"Kakao {urlsplit(url).path} failed (HTTP {error.code}, {code}).") from None


def send(text):
    tokens = post("https://kauth.kakao.com/oauth/token", {
        "grant_type": "refresh_token",
        "client_id": os.environ["KAKAO_REST_API_KEY"],
        "client_secret": os.environ["KAKAO_CLIENT_SECRET"],
        "refresh_token": os.environ["KAKAO_REFRESH_TOKEN"],
    })
    if tokens.get("refresh_token"):
        # shortcut: reconnect manually on token rotation, automate if regular reauthorization is a burden
        text = "카카오 로그인 재연결 필요\n" + text
        print("::warning::Kakao rotated the refresh token. Run setup-kakao.py again.")
    result = post("https://kapi.kakao.com/v2/api/talk/memo/default/send", {
        "template_object": json.dumps({
            "object_type": "text",
            "text": text if len(text) <= 200 else text[:199] + "…",
            "link": {"web_url": DASHBOARD, "mobile_web_url": DASHBOARD},
            "button_title": "전체 내역 보기",
        }),
    }, tokens["access_token"])
    if result.get("result_code") != 0:
        raise SystemExit("Kakao did not confirm message delivery.")
    print("Kakao accepted the message.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--report")
    mode.add_argument("--notify", action="store_true")
    args = parser.parse_args()
    if args.report:
        save_report(args.report)
    elif args.notify:
        send(message(
            json.loads(os.environ["STYLEC_REPORT"] or "{}"),
            json.loads(os.environ["MUSINSA_REPORT"] or "{}"),
            (os.environ["STYLEC_RESULT"], os.environ["MUSINSA_RESULT"]),
        ))
    else:
        send(TEST_TEXT)
