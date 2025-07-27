import os

from dotenv import load_dotenv

import boto3
import pydo


_DOT_ENV_FILEPATH = os.path.join(os.path.dirname(__file__), '.env')

def create_s3_client(region_name, endpoint_url, access_key, secret_access_key) -> boto3.client:
    s3_session = boto3.session.Session()
    return s3_session.client('s3',
                             region_name=region_name,
                             endpoint_url=endpoint_url,
                             aws_access_key_id=access_key,
                             aws_secret_access_key=secret_access_key)

def create_s3_client_from_dot_env(region_name, endpoint_url) -> boto3.client:
    load_dotenv(_DOT_ENV_FILEPATH)

    return create_s3_client(
        region_name=region_name,
        endpoint_url=endpoint_url,
        access_key=os.environ["ACCESS_ID"],
        secret_access_key=os.environ["SECRET_KEY"],
    )

def create_pydo_client() -> pydo.Client:
    load_dotenv(_DOT_ENV_FILEPATH)

    return pydo.Client(os.environ["DIGITALOCEAN_TOKEN"])
