import io
import json
import uuid

from botocore.exceptions import ClientError

from port import utils


_DEFAULT_PORT_CONFIG = {
    "cargo_manifests": {},
    "fleets": {}
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

        self.ocean = ocean
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
                                  Bucket='enfra',
                                  Key=f'ports/{self.port_name}/container_yard/{cargo_id}/pad_lock_key.sh')

    def cargo_exists(self, cargo_id: str):
        try:
            self.s3_client.head_object(Bucket='enfra',
                                       Key=f'ports/{self.port_name}/container_yard/{cargo_id}/pad_lock_key.sh')
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == "404":
                return False
            raise e

    def create_cargo_manifest(self, cargo_manifest_name: str):
        self.authority_config = self.get_port_authority_config(self.port_name)
        self.authority_config["cargo_manifests"][cargo_manifest_name] = {
            "cargo_ids": []
        }

        self.update_port_authority_config()

    def update_cargo_mainfest(self, cargo_manifest_name: str, cargo_ids: list[str]):
        if not all(self.cargo_exists(cargo_id) for cargo_id in cargo_ids):
            raise ValueError("Non-existant cargo id detect")

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

class Fleet():
    def __init__(self, port: Port, fleet_name: str):
        self.port = port
        self.fleet_name = fleet_name
        try:
            self.fleet_organization = self.port.authority_config[fleet_name]
        except KeyError:
            raise LookupError(f"No fleet named {fleet_name} in port {port.port_name}")

    @classmethod
    def construct_fleet(cls,
                        port_of_fleet: Port,
                        fleet_name: str,
                        pydo_client,
                        ship_type: str,
                        crew: str,
                        captain: str,
                        ssh_key_fingerprint: str,
                        reinforcement_strategy: str, # when to scale up resource:threshold_to_trigger_scale_up (e.g cpu:0.5, mem:0.7)
                        gangways: list[dict], # [{"pier_end": {"type": "HTTP" | ..., "number": int}, "ship_end": {"type": "HTTP" | ..., "number": int}, "purser"?: $id_to_ssl_certificate}]
                        min_size=1,
                        max_size=2,):
        fleet_call_sign = f"{port_of_fleet.port_name}-{fleet_name}"

        port_of_fleet.authority_config["fleets"][fleet_name] = {
            "fleet_call_sign": fleet_call_sign,
            "ship_type": ship_type,
            "crew": crew,
            "captain": captain,
            "min_size": min_size,
            "max_size": max_size,
            "reinforcement_strategy": reinforcement_strategy
        }

        # TODO: handle memory resource and perform better value validation
        def reinforcement_strategy_to_do_config(reinforcement_strategy: str):
            reinforcement_strategy_parts = reinforcement_strategy.split(':')
            resource_type = reinforcement_strategy_parts[0]
            resource_threshold = reinforcement_strategy_parts[1]
            if resource_type == 'cpu':
                return {"target_cpu_utilization": float(resource_threshold)}
            raise ValueError(f"Can't parse {reinforcement_strategy} as a reinforcement strategy")

        asp_resp = pydo_client.autoscalepools.create(
            body={
                "name": fleet_call_sign,
                "config": {
                    "min_instances": min_size,
                    "max_instances": max_size,
                    **reinforcement_strategy_to_do_config(reinforcement_strategy)
                },
                "droplet_template": {
                    "name": fleet_call_sign,
                    "region": port_of_fleet.ocean,
                    "image": crew,
                    "size": ship_type,
                    "ssh_keys": [ssh_key_fingerprint],
                    "tags": [fleet_call_sign]
                }
            }
        )

        def gangway_to_forwarding_rule(gangway: dict):
            if "purser" in gangway:
                ssl_cert_config = {"tls_passthrough": True, "certificate_id": gangway["purser"]}
            else:
                ssl_cert_config = {"tls_passthrough": False}

            return {
                "entry_protocol": gangway["pier_end"]["type"],
                "entry_port": gangway["pier_end"]["number"],
                "target_protocol": gangway["ship_end"]["type"],
                "target_port": gangway["ship_end"]["number"],
                **ssl_cert_config
            }

        lb_resp = pydo_client.load_balancers.create(
            body={
                "name": fleet_call_sign,
                "region": port_of_fleet.ocean,
                "forwarding_rules": list(map(gangway_to_forwarding_rule, gangways)),
                "tag": fleet_call_sign
            }
        )