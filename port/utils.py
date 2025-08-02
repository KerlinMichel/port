import os
import subprocess

from dotenv import load_dotenv

import boto3
import pydo


_DOT_ENV_FILEPATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__), '../.env'
))

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

def get_local_machine_ssh_key_fingerprint():
    ssh_public_key_ls_cmd = subprocess.check_output(['ls ~/.ssh/*.pub'], shell=True, text=True)
    ssh_public_key_files = ssh_public_key_ls_cmd.splitlines()
    if len(ssh_public_key_files) > 1:
        raise ValueError(f'Multiple public key files {ssh_public_key_files}')
    
    ssh_public_key_file = ssh_public_key_files[0]

    ssh_public_key_fingerprint_cmd = subprocess.check_output([f'ssh-keygen -l -E md5 -f {ssh_public_key_file}'], shell=True, text=True)
    ssh_public_key_fingerprint = ssh_public_key_fingerprint_cmd[8:55]

    return ssh_public_key_fingerprint