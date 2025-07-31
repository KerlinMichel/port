import argparse
import json

from botocore.exceptions import ClientError

import utils


parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers(dest='command')

create_parser = subparsers.add_parser('create')
create_parser.add_argument('-r', '--region', required=True)
create_parser.add_argument('-s', '--sea', required=True)
create_parser.add_argument('-n', '--name', required=True)

configure_parser = subparsers.add_parser('configure')
configure_parser.add_argument('-r', '--region', required=True)
configure_parser.add_argument('-s', '--sea', required=True)
configure_parser.add_argument('-n', '--name', required=True)

configure_action_subparser = configure_parser.add_subparsers(dest='configure-action')

configure_add_ship_parser = configure_action_subparser.add_parser('add-fleet')
configure_add_ship_parser.add_argument('-p', '--pier', required=True)
configure_add_ship_parser.add_argument('-k', '--ssh-key-fp', default="local")
configure_add_ship_parser.add_argument('fleet')

configure_add_pier_parser = configure_action_subparser.add_parser('add-pier')
configure_add_pier_parser.add_argument('pier')

configure_load_pier_parser = configure_action_subparser.add_parser('load-pier')
configure_load_pier_parser.add_argument('-p', '--pier', required=True)
configure_load_pier_parser.add_argument('cargo_id')

args = parser.parse_args()

s3_client = utils.create_s3_client_from_dot_env(
    args.region,
    args.sea
)

_DEFAULT_PORT_CONFIG = {
    "ships": {},
}

_DEFAULT_PIER_CONFIG = {
    "cargo_id": None
}

port_exists = False

try:
    config_json_s3_res = s3_client.get_object(Bucket='enfra_ports',
                                              Key=f'{args.name}.json')
    config_json = json.load(config_json_s3_res['Body'])
    port_exists = True
except ClientError as e:
    if e.response['Error']['Code'] == "NoSuchKey":
        print("Port does not exists")
    else:
        raise e

if args.command == 'create':
    if port_exists is False:
        s3_client.put_object(Body=json.dumps(_DEFAULT_PORT_CONFIG),
                             Bucket='enfra_ports',
                             Key=f'{args.name}.json')

        pydo_client = utils.create_pydo_client()

        pydo_client.projects.create(
            body={
                "name": args.name,
                "purpose": "Service or API",
            }
        )
        print("Port created")
    else:
        print("Port already exists")
elif args.command == 'configure':
    if getattr(args, 'configure-action') == 'add-fleet':
        pydo_client = utils.create_pydo_client()

        ship_tag = f"{args.name}-{args.pier}-{args.fleet}-ship"

        if args.ssh_key_fp == "local":
            args.ssh_key_fp = utils.get_local_machine_ssh_key_fingerprint()

        asp_resp = pydo_client.autoscalepools.create(
            body={
                "name": f"{args.name}-{args.pier}-{args.fleet}",
                "config": {
                    "min_instances": 1,
                    "max_instances": 2,
                    "target_cpu_utilization": 0.5,
                },
                "droplet_template": {
                    "name": args.fleet,
                    "region": args.region,
                    "image": "ubuntu-25-04-x64", # TODO: Don't like that I'm hard coding, but can be change manually
                    "size": "s-1vcpu-1gb", # TODO: Don't like that I'm hard coding, but can be change manually
                    "ssh_keys": [args.ssh_key_fp],
                    "tags": [ship_tag]
                }
            }
        )

        lb_resp = pydo_client.load_balancers.create(
            body={
                "name": f"{args.name}-{args.pier}-{args.fleet}",
                "region": args.region,
                "forwarding_rules": [
                    {
                        "entry_protocol": "http",
                        "entry_port": 80,
                        "target_protocol": "http",
                        "target_port": 80,
                        "tls_passthrough": False
                    }
                ],
                "tag": ship_tag
            }
        )

        print("Added fleet")
    elif getattr(args, 'configure-action') == 'add-pier':
        s3_client.put_object(Body=json.dumps(_DEFAULT_PIER_CONFIG),
                             Bucket='enfra_piers',
                             Key=f'{args.pier}.json')
    elif getattr(args, 'configure-action') == 'load-pier':
        s3_client.put_object(Body=json.dumps({"cargo_id": args.cargo_id}),
                             Bucket='enfra_piers',
                             Key=f'{args.pier}.json')

    s3_client.put_object(Body=json.dumps(config_json),
                         Bucket='enfra_ports',
                         Key=f'{args.name}.json')