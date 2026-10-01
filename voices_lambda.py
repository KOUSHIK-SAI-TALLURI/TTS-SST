import json
import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError

polly = boto3.client(
    "polly",
    region_name=os.getenv("AWS_REGION"),
)


def lambda_handler(event, context):
    try:
        voices = polly.describe_voices()["Voices"]

        result = [
            {
                "id": voice["Id"],
                "name": voice["Name"],
                "language_code": voice["LanguageCode"],
                "language_name": voice["LanguageName"],
                "gender": voice["Gender"],
            }
            for voice in voices
        ]

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": os.getenv(
                    "CORS_ORIGIN", "*"
                ),
            },
            "body": json.dumps({"voices": result}),
        }

    except (ClientError, BotoCoreError) as exc:
        print(f"Polly voice error: {exc}")

        return {
            "statusCode": 500,
            "body": json.dumps(
                {"error": "Unable to retrieve Polly voices."}
            ),
        }
