#!/usr/bin/env python3


from argparse import ArgumentParser
from csv import DictWriter as CsvDictWriter
import json
import sys


AST_VAR_TYPE_MAP = dict(EnumConstantDecl='enum', FunctionDecl='function',
                        ParmVarDecl='parameter', VarDecl='variable')


def parse_args():
    """Parse command-line arguments."""
    parser = ArgumentParser(description='Get variable and function names from '
                                        'a Clang AST')
    parser.add_argument('json', nargs='+', help='Path to AST JSON file(s)')
    return parser.parse_args()


def parse_ast(json_file):
    """Parse the JSON file produced by Clang."""
    data = json_file.read()
    data_len = len(data)

    start = 0
    end = data_len

    while start < end:
        try:
            ast = json.loads(data[start:end])
            yield ast

            start = end
            end = data_len
        except json.decoder.JSONDecodeError as err:
            if err.msg == 'Extra data':
                end = start + err.pos
            else:
                raise


def walk_ast_rec(node, identifiers=None):
    if not identifiers:
        identifiers = set()
    if 'kind' not in node:
        return identifiers

    node_kind = node['kind']

    if node_kind == 'DeclRefExpr':
        identifier = node['referencedDecl']['name']
        identifier_kind = node['referencedDecl']['kind']
        identifiers.add((identifier, AST_VAR_TYPE_MAP[identifier_kind]))
    if 'inner' in node:
        for inner in node['inner']:
            identifiers |= walk_ast_rec(inner, identifiers)

    return identifiers


def main():
    """The main function."""
    args = parse_args()

    identifiers = set()

    for path in args.json:
        with open(path, 'r') as inf:
            for ast in parse_ast(inf):
                identifiers |= walk_ast_rec(ast)

    identifiers = [dict(identifier=iden, type=iden_type)
                   for iden, iden_type in identifiers]

    csv_writer = CsvDictWriter(sys.stdout,
                               fieldnames=('identifier', 'type'))
    csv_writer.writeheader()
    csv_writer.writerows(identifiers)


if __name__ == '__main__':
    main()
