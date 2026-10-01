import json
import os
import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError

REGION = os.getenv("AWS_REGION")
BUCKET = os.environ["S3_BUCKET"]
URL_EXPIRATION = int(os.getenv("PRESIGNED_URL_EXPIRATION", "3600"))
MAX_TEXT_LENGTH = int(os.getenv("MAX_TEXT_LENGTH", "5000"))

polly = boto3.client("polly", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)


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
        voice_id = body.get("voice_id", "Joanna")
        language_code = body.get("language_code", "en-US")

        if not text:
            return make_response(400, {"error": "Text is required."})

        if len(text) > MAX_TEXT_LENGTH:
            return make_response(
                413,
                {"error": f"Text exceeds {MAX_TEXT_LENGTH} characters."},
            )

        result = polly.synthesize_speech(
            Text=text,
            OutputFormat="mp3",
            VoiceId=voice_id,
            LanguageCode=language_code,
        )

        audio = result["AudioStream"].read()
        key = f"tts/{uuid.uuid4()}.mp3"

        s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=audio,
            ContentType="audio/mpeg",
        )

        audio_url = s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": BUCKET,
                "Key": key,
            },
            ExpiresIn=URL_EXPIRATION,
        )

        return make_response(
            200,
            {
                "message": "Speech generated successfully.",
                "audio_url": audio_url,
                "expires_in": URL_EXPIRATION,
            },
        )

    except (ClientError, BotoCoreError) as exc:
        print(f"AWS TTS error: {exc}")
        return make_response(
            500,
            {"error": "Speech generation failed."},
        )

    except Exception as exc:
        print(f"Unexpected TTS error: {exc}")
        return make_response(
            500,
            {"error": "Internal server error."},
        )
