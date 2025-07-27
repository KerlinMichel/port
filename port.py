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
configure_action_parser = configure_action_subparser.add_parser('add-pier')
configure_action_parser.add_argument('-p', '--pier', required=True)

args = parser.parse_args()

s3_client = utils.create_s3_client_from_dot_env(
    args.region,
    args.sea
)

_DEFAULT_CONFIG = {
    "piers": []
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
        s3_client.put_object(Body=json.dumps(_DEFAULT_CONFIG), 
                             Bucket='enfra_ports',
                             Key=f'{args.name}.json')
        print("Port created")
    else:
        print("Port already exists")
elif args.command == 'configure':
    if getattr(args, 'configure-action') == 'add-pier':
        pydo_client = utils.create_pydo_client()

        load_balancers = pydo_client.load_balancers.list()['load_balancers']
        lb_exists = False
        for lb in load_balancers:
            if lb['name'] == args.pier:
                lb_exists = True
        if lb_exists is False:
            raise ValueError()

        if not args.pier in config_json['piers']:
            config_json['piers'].append(args.pier)
            print("Added pier")
        else:
            print("Pier already in port")

    s3_client.put_object(Body=json.dumps(config_json), 
                         Bucket='enfra_ports',
                         Key=f'{args.name}.json')