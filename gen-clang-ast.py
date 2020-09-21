#!/usr/bin/env python3

"""
Generate a Clang AST (in JSON format) from a compilation database. Adapted from
run-clang-format.py

Author: Adrian Herrera
"""


from argparse import ArgumentParser
import json
import multiprocessing
import os
from queue import Queue
import re
import subprocess
import sys
import threading


def parse_args():
    """Parse command-line arguments."""
    parser = ArgumentParser(description='Generate Clang ASTs from a '
                                        'compilation database')
    parser.add_argument('-c', '--clang-binary', metavar='PATH', default='clang',
                        help='Path to clang binary')
    parser.add_argument('-o', '--output', metavar='OUT', required=True,
                        help='Output directory for AST JSON files')
    parser.add_argument('-j', type=int, default=0,
                        help='Number of clang instances to be run in parallel')
    parser.add_argument('-p', '--build-path',
                        help='Path used to read a compile command database')
    parser.add_argument('files', nargs='*', default=['.*'],
                        help='Files to be processed (regex on path)')
    return parser.parse_args()


def find_compilation_database(path):
    """Adjusts the directory until a compilation database is found."""
    result = './'
    while not os.path.isfile(os.path.join(result, path)):
        if os.path.realpath(result) == '/':
            print('Error: could not find compilation database.')
            sys.exit(1)
        result += '../'
    return os.path.realpath(result)


def make_absolute(f, directory):
    """Make an absolute path."""
    if os.path.isabs(f):
        return f
    return os.path.normpath(os.path.join(directory, f))


def run_clang(args, queue, lock, failed_files):
    """Takes filesname out of queue and runs clang on them."""
    while True:
        entry = queue.get()
        name = entry['file']
        clang_args = entry['arguments'][1:] # skip the compiler argument
        path = make_absolute(name, entry['directory'])

        clang_args = []
        for arg in entry['arguments'][1:]:
            if arg == name:
                clang_args.append(path)
            else:
                clang_args.append(arg)

        invocation = [args.clang_binary, '-Xclang', '-ast-dump=json',
                      '-fsyntax-only', *clang_args]

        proc = subprocess.Popen(invocation, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        output, err = proc.communicate()
        if proc.returncode != 0:
            failed_files.append(path)
        with lock:
            out_path = os.path.join(args.output,
                                    '%s.json' % name.replace(os.sep, '_'))
            with open(out_path, 'w') as outf:
                outf.write(output.decode('utf-8'))
            if len(err) > 0:
                sys.stderr.write('%s\n' % err.decode('utf-8'))
        queue.task_done()


def main():
    """The main function."""
    args = parse_args()

    if not os.path.isdir(args.output):
        raise Exception('Invalid output directory `%s`' % args.output)

    db_path = 'compile_commands.json'
    if args.build_path is not None:
        build_path = args.build_path
    else:
        # Find our database
        build_path = find_compilation_database(db_path)

    # Load the database and extract all files
    with open(os.path.join(build_path, db_path), 'r') as inf:
        database = json.load(inf)

    max_task = args.j
    if max_task == 0:
        max_task = multiprocessing.cpu_count()

    # Build up a big regexy filter from all command line arguments.
    file_name_re = re.compile('|'.join(args.files))

    return_code = 0
    try:
        # Spin up a bunch of clang-launching threads
        task_queue = Queue(max_task)
        # List of files with a non-zero return code.
        failed_files = []
        lock = threading.Lock()
        for _ in range(max_task):
            t = threading.Thread(target=run_clang,
                                 args=(args, task_queue, lock, failed_files))
            t.daemon = True
            t.start()

        # Fill the queue with files
        for entry in database:
            path = make_absolute(entry['file'], entry['directory'])
            if file_name_re.search(path):
                task_queue.put(entry)

        # Wait for all threads to be done
        task_queue.join()
        if len(failed_files) > 0:
            return_code = 1

    except KeyboardInterrupt:
        # This is a sad hack. Unfortunately subprocess goes
        # bonkers with ctrl-c and we start forking merrily.
        print('\nCtrl-C detected, goodbye.')
        os.kill(0, 9)

    sys.exit(return_code)


if __name__ == '__main__':
    main()
