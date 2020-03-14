# Copyright (c) 2020, Darren Hart
# SPDX-License-Identifier: GPL-2.0-only

import argparse
import glob
import hashlib
import json
from subprocess import Popen, PIPE
import sys
import textwrap
try:
    import laubwerk as lbw
except ImportError:
    # Likely running as a subprocess, this will be added in main()
    pass


def md5sum(filename):
    md5 = hashlib.md5()
    with open(filename, mode='rb') as f:
        buf = f.read(4096)
        while buf:
            md5.update(buf)
            buf = f.read(4096)
    return md5.hexdigest()


def parse_plant(filename):
    p = lbw.load(filename)
    p_rec = {}

    plant = {}
    plant["name"] = p.name
    plant["md5"] = md5sum(filename)
    plant["default_model"] = p.default_model.name

    labels = {}
    p_labels = {}
    # Store only the first label per locale
    for l in p.labels.items():
        p_labels[l[0]] = l[1][0]
    labels[p.name] = p_labels

    models = {}
    i = 0
    for m in p.models:
        m_rec = {}
        seasons = []
        q_labels = {}
        for q in m.qualifiers:
            seasons.append(q)
            q_labels[q] = {}
            for q_lang in m.qualifier_labels[q].items():
                q_labels[q][q_lang[0]] = q_lang[1][0]
        labels.update(q_labels)
        m_rec["index"] = i
        m_rec["qualifiers"] = seasons
        m_rec["default_qualifier"] = m.default_qualifier
        models[m.name] = m_rec
        m_labels = {}
        # FIXME: highly redundant
        for l in m.labels.items():
            m_labels[l[0]] = l[1][0]
        labels[m.name] = m_labels
        i = i + 1
    plant["models"] = models

    p_rec["plant"] = plant
    p_rec["labels"] = labels
    return p_rec


def parse_plant_json(filename):
    p_rec = parse_plant(filename)
    print(json.dumps(p_rec))


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
        p_rec = parse_plant(plant_filename)
        self.add_plant_record(plant_filename, p_rec["plant"])
        self.update_labels(p_rec["labels"])

    def plant_count(self):
        return len(self.db["plants"])


def lbwdb_write(db_filename, plants_dir, sdk_path, python=sys.executable):
    db = LaubwerkDB(db_filename, python=python)
    db.initialize()

    # FIXME: .gz is optional
    plant_files = glob.glob(plants_dir + "/*/*.lbw.gz")

    subs = []
    for f in plant_files:
        sub = Popen([db.python, __file__, "-f", f, "-s", sdk_path, "parse"], stdout=PIPE)
        subs.append(sub)

    for sub in subs:
        outs, errs = sub.communicate()
        p_rec = json.loads(outs)
        db.add_plant_record(sub.args[3], p_rec["plant"])
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
    global lbw
    argParse = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                       description=textwrap.dedent('''\
Thicket Database Tool
Comands:
  read                read and print the db contents (requires -d)
  write               scan plants path and add all plants to a new db (requires -d -p -s)
  parse               read a plant file and print the plant record json (requires -f -s)
'''))

    argParse.add_argument('cmd', choices=['read', 'write', 'parse'], help='command')
    argParse.add_argument('-d', help='database filename', default="thicket.db")
    argParse.add_argument('-f', help='Laubwerk Plant filename (lbw.gz)')
    argParse.add_argument('-p', help='Laubwerk Plants path')
    argParse.add_argument('-s', help='Laubwerk Python SDK path')

    args = argParse.parse_args()

    cmd = args.cmd
    if cmd == 'read' and args.d:
        lbwdb_read(args.d)
    elif cmd == 'write' and args.d and args.p and args.s:
        lbwdb_write(args.d, args.p, args.s)
    elif cmd == 'parse' and args.f and args.s:
        # The plant command is intended to be run as a separate process
        # The Laubwerk SDK may need to be explicitly added to the sys.path
        # This is required on Mac. and not on Windows in my testing.
        if args.s not in sys.path:
            sys.path.append(args.s)
        import laubwerk as lbw
        parse_plant_json(args.f)
    else:
        argParse.print_help()
        return 1


if __name__ == "__main__":
    main()
