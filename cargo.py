import argparse
import uuid

import utils

parser = argparse.ArgumentParser()

subparsers = parser.add_subparsers(dest='command')

store_parser = subparsers.add_parser('store')
store_parser.add_argument('-f', '--file', required=True, type=argparse.FileType('rb'))
store_parser.add_argument('-r', '--region', required=True)
store_parser.add_argument('-s', '--sea', required=True)

args = parser.parse_args()

s3_client = utils.create_s3_client_from_dot_env(
    args.region,
    args.sea
)

if args.command == 'store':
    cargo_id = str(uuid.uuid4())
    s3_client.put_object(Body=args.file.read(),
                         Bucket=f'enfra_cargo',
                         Key=f'{cargo_id}/cargo')