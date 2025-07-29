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

configure_add_ship_parser = configure_action_subparser.add_parser('add-ship')
configure_add_ship_parser.add_argument('-p', '--pier', required=True)
configure_add_ship_parser.add_argument('ship')

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
        print("Port created")
    else:
        print("Port already exists")
elif args.command == 'configure':
    if getattr(args, 'configure-action') == 'add-ship':
        pydo_client = utils.create_pydo_client()

        load_balancers = pydo_client.load_balancers.list()['load_balancers']
        lb_exists = False
        for lb in load_balancers:
            if lb['name'] == args.ship:
                lb_exists = True
        if lb_exists is False:
            raise ValueError()

        config_json['ships'][args.ship] = {"pier": args.pier}
        print("Added or updated ship")
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