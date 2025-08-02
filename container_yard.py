import argparse
import os
import uuid

import utils


parser = argparse.ArgumentParser()

subparsers = parser.add_subparsers(dest='command')

def file_path_or_dir_path_arg_type(arg: str):
    if os.path.isfile(arg):
        return {"type": "file", "file_path": arg}
    elif os.path.isdir(arg):
        return {"type": "directory", "directory": arg}
    else:
        raise ValueError(f"{arg} is not a file or director")

store_parser = subparsers.add_parser('store')
store_parser.add_argument('-r', '--region', required=True)
store_parser.add_argument('-s', '--sea', required=True)
store_parser.add_argument('-c', '--cargo', required=True, type=file_path_or_dir_path_arg_type)
store_parser.add_argument('-k', '--pad-lock-key', required=True, type=argparse.FileType('rb'), help="Script on how to unlock cargo")

args = parser.parse_args()

s3_client = utils.create_s3_client_from_dot_env(
    args.region,
    args.sea
)

if args.command == 'store':
    cargo_id = str(uuid.uuid4())

    if args.cargo["type"] == "file":
        # store cargo file
        cargo_file_path = args.cargo["file_path"]
        with open(cargo_file_path, "rb") as cargo_file:
            s3_client.put_object(Body=cargo_file.read(),
                                 Bucket=f'enfra_container_yard',
                                 Key=f'{cargo_id}/{cargo_file_path}')

        # store pad lock key script
        s3_client.put_object(Body=args.pad_lock_key.read(),
                                  Bucket=f'enfra_container_yard',
                                  Key=f'{cargo_id}/pad_lock_key.sh')
    elif args.cargo["type"] == "directory":
        raise NotImplementedError("Haven't setup load directory as cargo")