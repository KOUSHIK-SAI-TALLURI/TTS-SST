import base64
import json
import os
import time
import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError

REGION = os.getenv("AWS_REGION")
BUCKET = os.environ["S3_BUCKET"]

POLL_INTERVAL = float(os.getenv("TRANSCRIBE_POLL_SECONDS", "2"))
TIMEOUT = int(os.getenv("TRANSCRIBE_TIMEOUT_SECONDS", "120"))
MAX_AUDIO_BYTES = int(
    os.getenv("MAX_AUDIO_BYTES", str(10 * 1024 * 1024))
)

s3 = boto3.client("s3", region_name=REGION)
transcribe = boto3.client("transcribe", region_name=REGION)


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


def remove_data_uri_prefix(audio):
    if audio.startswith("data:") and "," in audio:
        return audio.split(",", 1)[1]
    return audio


def get_audio_format(filename):
    extension = filename.lower().rsplit(".", 1)[-1]

    formats = {
        "mp3": ("mp3", "audio/mpeg"),
        "wav": ("wav", "audio/wav"),
        "mp4": ("mp4", "audio/mp4"),
        "m4a": ("m4a", "audio/x-m4a"),
        "flac": ("flac", "audio/flac"),
        "ogg": ("ogg", "audio/ogg"),
    }

    return formats.get(extension, ("wav", "audio/wav"))


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return make_response(200, {"message": "OK"})

    try:
        body = event.get("body") or "{}"

        if isinstance(body, str):
            body = json.loads(body)

        encoded_audio = body.get("audio")
        filename = body.get("filename", "audio.wav")
        language_code = body.get("language_code", "en-US")

        if not encoded_audio:
            return make_response(
                400,
                {"error": "Audio is required."},
            )

        encoded_audio = remove_data_uri_prefix(encoded_audio)
        audio_bytes = base64.b64decode(encoded_audio)

        if len(audio_bytes) > MAX_AUDIO_BYTES:
            return make_response(
                413,
                {"error": "Audio file is too large."},
            )

        audio_format, content_type = get_audio_format(filename)

        key = f"stt/{uuid.uuid4()}.{audio_format}"

        s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=audio_bytes,
            ContentType=content_type,
        )

        job_name = f"transcription-{uuid.uuid4()}"

        transcribe.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={
                "MediaFileUri": f"s3://{BUCKET}/{key}",
            },
            MediaFormat=audio_format,
            LanguageCode=language_code,
        )

        deadline = time.time() + TIMEOUT

        while time.time() < deadline:
            result = transcribe.get_transcription_job(
                TranscriptionJobName=job_name
            )

            job = result["TranscriptionJob"]
            status = job["TranscriptionJobStatus"]

            if status == "COMPLETED":
                return make_response(
                    200,
                    {
                        "status": "COMPLETED",
                        "job_name": job_name,
                        "transcript_uri": job["Transcript"][
                            "TranscriptFileUri"
                        ],
                    },
                )

            if status == "FAILED":
                reason = job.get(
                    "FailureReason",
                    "Transcription failed.",
                )

                return make_response(
                    503,
                    {
                        "status": "FAILED",
                        "error": reason,
                    },
                )

            time.sleep(POLL_INTERVAL)

        return make_response(
            504,
            {
                "status": "TIMEOUT",
                "error": "Transcription timed out.",
            },
        )

    except (ClientError, BotoCoreError) as exc:
        print(f"AWS STT error: {exc}")
        return make_response(
            503,
            {
                "error": (
                    "Speech-to-Text unavailable due to "
                    "cloud service billing or availability limits."
                )
            },
        )

    except Exception as exc:
        print(f"Unexpected STT error: {exc}")
        return make_response(
            500,
            {"error": "Internal server error."},
        )
