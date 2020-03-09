# Copyright (c) 2020, Darren Hart
# SPDX-License-Identifier: GPL-2.0-only

import argparse
import glob
import json
import pathlib
import subprocess
import sys
import time
import laubwerk as lbw


class LaubwerkDB:
    """ Laubwerk Database Interface """
    def __init__(self, db_filename, locale="en-US", python=sys.executable):
        self.db_filename = db_filename
        self.locale = locale.replace('_', '-')
        self.python = python
        try:
            with open(db_filename, 'r', encoding='utf-8') as f:
                self.db = json.load(f)
        except FileNotFoundError:
            # if failed, create, and initialize
            self.initialize()
            self.save()

    def initialize(self):
        self.db = {}
        self.db["info"] = {}
        self.db["labels"] = {}
        self.db["plants"] = {}

        self.db["info"]["sdk_version"] = lbw.version
        self.db["info"]["sdk_major"] = lbw.version_info.major
        self.db["info"]["sdk_minor"] = lbw.version_info.minor
        self.db["info"]["sdk_micro"] = lbw.version_info.micro

    def save(self):
        with open(self.db_filename, 'w', encoding='utf-8') as f:
            json.dump(self.db, f, ensure_ascii=False, indent=4)

    def print_info(self):
        info = self.db["info"]
        print("Laubwerk Version: %s" % info["sdk_version"])
        print("\tmajor: %s" % info["sdk_major"])
        print("\tminor: %s" % info["sdk_minor"])
        print("\tmicro: %s" % info["sdk_micro"])
        print("Loaded %d plants:" % self.plant_count())

    def update_labels(self, labels):
        self.db["labels"].update(labels)

    def get_label(self, key, locale=None):
        if locale:
            locale = locale.replace('_', '-')
        else:
            locale = self.locale

        try:
            if locale in self.db["labels"][key]:
                return self.db["labels"][key][locale]
            elif locale[:2] in self.db["labels"][key]:
                return self.db["labels"][key][locale[:2]]
            return key
        except KeyError:
            return key

    def get_plant(self, plant_filename):
        try:
            return self.db["plants"][plant_filename]
        except KeyError:
            return None

    def add_plant_record(self, plant_filename, plant_record):
        self.db["plants"][plant_filename] = plant_record

    def import_plant(self, plant_filename):
        lbwdb_plant_cmd = pathlib.Path(__file__).parent.absolute() / "lbwdb_plant.py"
        sub = subprocess.Popen([self.python, str(lbwdb_plant_cmd), plant_filename],
                               stdout=subprocess.PIPE)
        outs, errs = sub.communicate()
        p_rec = json.loads(outs)
        self.add_plant_record(plant_filename, p_rec["plant"])
        self.update_labels(p_rec["labels"])

    def plant_count(self):
        return len(self.db["plants"])


def lbwdb_write(db_filename, plants_dir, python=sys.executable):
    db = LaubwerkDB(db_filename, python=python)
    db.initialize()

    # FIXME: .gz is optional
    plant_files = glob.glob(plants_dir + "/*/*.lbw.gz")

    lbwdb_plant_cmd = pathlib.Path(__file__).parent.absolute() / "lbwdb_plant.py"
    subs = []
    for f in plant_files:
        subs.append(subprocess.Popen([db.python, str(lbwdb_plant_cmd), f], stdout=subprocess.PIPE))

    for sub in subs:
        outs, errs = sub.communicate()
        p_rec = json.loads(outs)
        db.add_plant_record(sub.args[2], p_rec["plant"])
        db.update_labels(p_rec["labels"])
    db.save()
    print("Processed %d/%d plants" % (db.plant_count(), len(plant_files)))


def lbwdb_read(db_filename):
    db = LaubwerkDB(db_filename)

    db.print_info()

    for p_rec in db.db["plants"].items():
        f = p_rec[0]
        plant = p_rec[1]
        print("%s (%s)" % (plant["name"], db.get_label(plant["name"], "ja")))
        print("\tfile: %s" % f)
        print("\tmd5: %s" % plant['md5'])
        print("\tdefault_model: %s (%s)" % (plant["default_model"], db.get_label(plant["default_model"], "en")))
        print("\tmodels:")
        for m_rec in plant["models"].items():
            print("\t\t%s (%s) %s" % (m_rec[0], db.get_label(m_rec[1]["default_qualifier"], "en"),
                  str(m_rec[1]["qualifiers"])))


def main():
    argParse = argparse.ArgumentParser(description='Laubwerk Database Tool')
    argParse.add_argument('cmd', help='read or write')
    argParse.add_argument('db', help='database filename')
    argParse.add_argument('-p', help='path to Laubwerk Plants directory')

    args = argParse.parse_args()

    cmd = args.cmd
    if cmd == 'read':
        lbwdb_read(args.db)
    elif cmd == 'write':
        if args.p == None:
            print("Error: you must specify the Laubwerk plants directory")
            return
        lbwdb_write(args.db, args.p)


if __name__ == "__main__":
    main()
