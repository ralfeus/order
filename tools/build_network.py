#!/usr/bin/env python3 
import argparse
from app import create_app
from app.network.jobs import build_network

arg_parser = argparse.ArgumentParser(description="Build network")
group = arg_parser.add_mutually_exclusive_group()
group.add_argument('--root', metavar='ROOT_ID', help="ID of the tree or subtree root")
group.add_argument('--update', help='Update data of existing nodes', action='store_true')
group.add_argument('--incremental', help='Build trees from all leaves', 
                   action='store_true', default=True)
group.add_argument('--continue', dest='cont', 
                   help='Continue tree building after being interrupted', action='store_true')
args = arg_parser.parse_args()
print(f'Building tree with following arguments: {args}')

with create_app().app_context():
    build_network(
        root_id=args.root, cont=args.cont, incremental=args.incremental,
        update=args.update)
