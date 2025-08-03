import io
import json
import uuid

from botocore.exceptions import ClientError

from port import utils


_DEFAULT_PORT_CONFIG = {
    "cargo_manifests": {}
}

_DIGITALOCEAN_ENDPOINT_URL_FORMAT = "https://{sea}.{ocean}.digitaloceanspaces.com"

class Port():
    def __init__(self,
                 ocean: str, # region name
                 sea: str, # Spaces name
                 port_name: str,
                 port_authority_access_key: dict=None):
        if port_authority_access_key == None:
            self.s3_client = utils.create_s3_client_from_dot_env(
                ocean,
                _DIGITALOCEAN_ENDPOINT_URL_FORMAT.format(
                    ocean=ocean,
                    sea=sea
                )
            )
        else:
            self.s3_client = utils.create_s3_client(
                ocean,
                _DIGITALOCEAN_ENDPOINT_URL_FORMAT.format(
                    ocean=ocean,
                    sea=sea
                ),
                port_authority_access_key["key_id"],
                port_authority_access_key["key_secret"]
            )

        self.port_name = port_name
        self.authority_config = self.get_port_authority_config(port_name)

    def get_port_authority_config(self,
                                  port_name: str) -> dict:
        try:
            config_json_s3_res = self.s3_client.get_object(Bucket='enfra',
                                                           Key=f'ports/{port_name}/port_authority_config.json')
            return json.load(config_json_s3_res['Body'])
        except ClientError as e:
            if e.response['Error']['Code'] == "NoSuchKey":
                raise LookupError(f"Port {port_name} does not exist")
            else:
                raise e

    def update_port_authority_config(self):
        self.s3_client.put_object(Bucket='enfra',
                                  Key=f'ports/{self.port_name}/port_authority_config.json',
                                  Body=json.dumps(self.authority_config))

    def store_cargo(self,
                    cargo_file_name: str,
                    cargo_file: io.BufferedIOBase,
                    pad_lock_key_file: io.BufferedIOBase):
        cargo_id = str(uuid.uuid4())

        self.s3_client.put_object(Body=cargo_file.read(),
                                  Bucket=f'enfra',
                                  Key=f'ports/{self.port_name}/container_yard/{cargo_id}/{cargo_file_name}')

        self.s3_client.put_object(Body=pad_lock_key_file.read(),
                                  Bucket=f'enfra',
                                  Key=f'ports/{self.port_name}/container_yard/{cargo_id}/pad_lock_key.sh')

    def create_cargo_manifest(self, cargo_manifest_name: str):
        self.authority_config = self.get_port_authority_config(self.port_name)
        self.authority_config["cargo_manifests"][cargo_manifest_name] = {
            "cargo_ids": []
        }

        self.update_port_authority_config()

    def update_cargo_mainfest(self, cargo_manifest_name: str, cargo_ids: list[str]):
        self.authority_config = self.get_port_authority_config(self.port_name)
        cargo_manifest = self.authority_config["cargo_manifests"][cargo_manifest_name]
        cargo_manifest["cargo_ids"] = cargo_ids
        self.authority_config["cargo_manifests"][cargo_manifest_name] = cargo_manifest
        self.update_port_authority_config()

    @classmethod
    def construct_port(cls, port_name: str, s3_client, pydo_client):
        s3_client.put_object(Bucket='enfra',
                             Key=f'ports/{port_name}/port_authority_config.json',
                             Body=json.dumps(_DEFAULT_PORT_CONFIG))

        pydo_client.projects.create(
            body={
                "name": port_name,
                "purpose": "Service or API",
            }
        )