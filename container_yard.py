import argparse
import io
import os
import uuid

import port


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
store_parser.add_argument('-o', '--ocean', required=True)
store_parser.add_argument('-s', '--sea', required=True)
store_parser.add_argument('-p', '--port-name', required=True)
store_parser.add_argument('-c', '--cargo', required=True, type=file_path_or_dir_path_arg_type)
store_parser.add_argument('-k', '--pad-lock-key', required=True, type=argparse.FileType('rb'), help="Script on how to unlock cargo")

args = parser.parse_args()

if args.command == 'store':
    cargo_id = str(uuid.uuid4())

    if args.cargo["type"] == "file":
        enfra_port = port.Port(
            args.ocean,
            args.sea,
            args.port_name
        )

        cargo_file_path = args.cargo["file_path"]
        with open(cargo_file_path, "rb") as cargo_file:
            enfra_port.store_cargo(
                cargo_file_path,
                cargo_file,
                args.pad_lock_key
            )
    elif args.cargo["type"] == "directory":
        raise NotImplementedError("Haven't setup load directory as cargo")