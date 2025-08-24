import io
import json
import os
import textwrap
import uuid

import pydo
from botocore.exceptions import ClientError

from port import utils


_DIGITALOCEAN_ENDPOINT_URL_FORMAT = "https://{sea}.{ocean}.digitaloceanspaces.com"

class Port():
    pydo_client: pydo.Client = utils.create_pydo_client()

    def __init__(self,
                 ocean: str, # region name
                 sea: str, # Spaces name
                 port_name: str,
                 port_authority_access_key: dict=None,
                 cargo_manifests: dict={},
                 fleet_orgs: dict={}):
        self.ocean = ocean
        self.port_name = port_name

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

        pl_res = Port.pydo_client.projects.list()
        projects_by_name = [project for project in pl_res["projects"] if project["name"] == port_name]
        if len(projects_by_name) == 0:
            project_create_res = Port.pydo_client.projects.create(
                body={
                    "name": port_name,
                    "purpose": "Service or API",
                }
            )
            self.project = project_create_res["project"]
        elif len(projects_by_name) == 1:
            self.project = projects_by_name[0]
        elif len(projects_by_name) > 1:
            raise RuntimeError(f"Multiple projects with name: {port_name}")

        self.cargo_manifests = {}
        for cargo_manifest_name in cargo_manifests:
            cargo_ids = cargo_manifests[cargo_manifest_name]
            if cargo_ids == "$CARGO_IDS":
                try:
                    self.cargo_manifests[cargo_manifest_name] = self.get_cargo_manifest(cargo_manifest_name)
                except LookupError:
                    self.update_cargo_mainfest(cargo_manifest_name, [])
                    self.cargo_manifests[cargo_manifest_name] = []
            else:
                # TODO: handle this path
                raise NotImplementedError("Currently not supporting cargo manifests with hard coded cargo ids in port org json")

        self.fleets = {}
        for fleet_name in fleet_orgs:
            fleet_org = fleet_orgs[fleet_name]
            self.fleets[fleet_name] = Fleet(self, fleet_name, fleet_org)

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

    def get_cargo_manifest(self, cargo_manifest_name: str):
        try:
            config_json_s3_res = self.s3_client.get_object(Bucket='ports',
                                                           Key=f'{self.port_name}/cargo_manifests/{cargo_manifest_name}/manifest.json')
            return json.load(config_json_s3_res['Body'])
        except ClientError as e:
            if e.response['Error']['Code'] == "NoSuchKey":
                raise LookupError(f"Cargo manifest {cargo_manifest_name} does not exist")
            else:
                raise e

    def update_cargo_mainfest(self, cargo_manifest_name: str, cargo_ids: list[str]):
        self.s3_client.put_object(Body=json.dumps(cargo_ids),
                                  Bucket=f'ports',
                                  Key=f'{self.port_name}/cargo_manifests/{cargo_manifest_name}/manifest.json')

    def create_cargo_manifest(self, cargo_manifest_name: str):
        self.authority_config = self.get_port_authority_config(self.port_name)
        self.authority_config["cargo_manifests"][cargo_manifest_name] = {
            "cargo_ids": []
        }

        self.update_port_authority_config()

    @classmethod
    def load_from_port_org(cls, port_org: dict):
        return Port(
            port_org["ocean"],
            port_org["sea"],
            port_org["port_name"],
            cargo_manifests=port_org["cargo_manifests"],
            fleet_orgs=port_org["fleets"]
        )

_MARINE_RADIO_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "marine_radio.go"))
_MARINE_RADIO_FREQUENCY = 1566

class Fleet():
    with open(_MARINE_RADIO_FILE_PATH) as ship_radio_file:
        MARINE_RADIO = ship_radio_file.read()

    CLOUD_CONFIG = f"""
#cloud-config
packages:
  - supervisor
  - golang-go
write_files:
  - path: /ecosystem.config.js
    content: |
        module.exports = {{
            apps : [{{
                name: "marine_radio",
                script: "/marine_radio.go",
                interpreter: "go",
                interpreter_args: "run"
            }}]
        }}
  - path: /marine_radio.go
    content: |
{textwrap.indent(MARINE_RADIO, '      ')}
  - path: /etc/supervisor/conf.d/marine_radio.conf
    content: |
      [supervisord]
      environment=GOCACHE="/root/.cache/go-build"
      [program:marine_radio]
      command=go run /marine_radio.go
      autostart=true
      autorestart=true
      startsecs=0
runcmd:
  - service supervisor start
  - supervisorctl reread
  - supervisorctl update
""".strip()
    def __init__(self, port: Port, fleet_name: str, fleet_org: dict):
        self.port = port
        self.fleet_name = fleet_name
        self.fleet_call_sign = f"{port.port_name}-{fleet_name}"

        aspl_res = Port.pydo_client.autoscalepools.list()
        asps_by_name = [asp for asp in aspl_res["autoscale_pools"] if asp["name"] == self.fleet_call_sign]
        if len(asps_by_name) == 0:
            # TODO: handle memory resource and perform better value validation
            def reinforcement_strategy_to_do_config(reinforcement_strategy: str):
                reinforcement_strategy_parts = reinforcement_strategy.split(':')
                resource_type = reinforcement_strategy_parts[0]
                resource_threshold = reinforcement_strategy_parts[1]
                if resource_type == 'cpu':
                    return {"target_cpu_utilization": float(resource_threshold)}
                raise ValueError(f"Can't parse {reinforcement_strategy} as a reinforcement strategy")
            
            if fleet_org["ssh_key_fingerprint"] == "$LOCAL":
                fleet_org["ssh_key_fingerprint"] = utils.get_local_machine_ssh_key_fingerprint()

            autoscalepool_create_res = Port.pydo_client.autoscalepools.create(
                body={
                    "name": self.fleet_call_sign,
                    "config": {
                        "min_instances": fleet_org["min_size"],
                        "max_instances": fleet_org["max_size"],
                        **reinforcement_strategy_to_do_config(fleet_org["reinforcement_strategy"])
                    },
                    "droplet_template": {
                        "name": self.fleet_call_sign,
                        "region": port.ocean,
                        "image": fleet_org["crew"],
                        "size": fleet_org["ship_type"],
                        "ssh_keys": [fleet_org["ssh_key_fingerprint"]],
                        "user_data": Fleet.CLOUD_CONFIG,
                        "tags": [self.fleet_call_sign]
                    }
                }
            )
            # TODO: look into assigning autoscaling pool to a project.
            # Based on DigitalOcean UI it seems like autoscale pools can't be assigned to groups.
        elif len(asps_by_name) > 1:
            raise RuntimeError(f"Multiple autoscale pools with name: {fleet_name}")

        lbl_res = Port.pydo_client.load_balancers.list()
        lbs_by_name = [lb for lb in lbl_res["load_balancers"] if lb["name"] == self.fleet_call_sign]

        if len(lbs_by_name) == 0:
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

            loadbalancer_create_res = Port.pydo_client.load_balancers.create(
                body={
                    "name": self.fleet_call_sign,
                    "region": port.ocean,
                    "forwarding_rules": list(map(gangway_to_forwarding_rule, fleet_org["gangways"])),
                    "tag": self.fleet_call_sign,
                    "health_check": {
                        "protocol": "http",
                        "port": _MARINE_RADIO_FREQUENCY,
                        "path": "/",
                        "check_interval_seconds": 5,
                        "response_timeout_seconds": 5,
                        "unhealthy_threshold": 2,
                        "healthy_threshold": 3
                    }
                }
            )

            loadbalancer_pool_id = loadbalancer_create_res["load_balancer"]["id"]
            Port.pydo_client.projects.assign_resources(
                port.project["id"],
                body={
                    "resources": [f"do:loadbalancer:{loadbalancer_pool_id}"]
                }
            )
        elif len(lbs_by_name) > 1:
            raise RuntimeError(f"Multiple load balancers with name: {fleet_name}")