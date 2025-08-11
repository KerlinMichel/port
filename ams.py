# Automated Manist System
import argparse

import port


parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers(dest='command')

create_parser = subparsers.add_parser('create')
create_parser.add_argument('-o', '--ocean', required=True)
create_parser.add_argument('-s', '--sea', required=True)
create_parser.add_argument('-p', '--port-name', required=True)
create_parser.add_argument('cargo_manifest_name')

update_parser = subparsers.add_parser('update')
update_parser.add_argument('-o', '--ocean', required=True)
update_parser.add_argument('-s', '--sea', required=True)
update_parser.add_argument('-p', '--port-name', required=True)
update_parser.add_argument('-c', '--cargo', required=True)
update_parser.add_argument('cargo_manifest_name')

args = parser.parse_args()

enfra_port = port.Port(
    args.ocean,
    args.sea,
    args.port_name
)

if args.command == 'create':
    enfra_port.create_cargo_manifest(args.cargo_manifest_name)
elif args.command == 'update':
    cargo_ids = args.cargo.split(',')
    enfra_port.update_cargo_mainfest(args.cargo_manifest_name, cargo_ids)