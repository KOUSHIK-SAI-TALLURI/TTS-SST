import json
import os
from urllib import request

TRANSLATION_URL = os.getenv(
    "TRANSLATION_URL",
    "https://libretranslate.com/translate",
)


def make_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": os.getenv("CORS_ORIGIN", "*"),
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "POST,OPTIONS",
        },
        "body": json.dumps(body),
    }


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return make_response(200, {"message": "OK"})

    try:
        body = event.get("body") or "{}"

        if isinstance(body, str):
            body = json.loads(body)

        text = (body.get("text") or "").strip()
        source = body.get("source", "auto")
        target = body.get("target")

        if not text:
            return make_response(
                400,
                {"error": "Text is required."},
            )

        if not target:
            return make_response(
                400,
                {"error": "Target language is required."},
            )

        payload = json.dumps(
            {
                "q": text,
                "source": source,
                "target": target,
                "format": "text",
            }
        ).encode("utf-8")

        req = request.Request(
            TRANSLATION_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with request.urlopen(req, timeout=20) as result:
            translated = json.loads(
                result.read().decode("utf-8")
            )

        return make_response(
            200,
            {
                "source": source,
                "target": target,
                "translated_text": translated["translatedText"],
            },
        )

    except Exception as exc:
        print(f"Translation error: {exc}")

        return make_response(
            502,
            {"error": "Translation service unavailable."},
        )
