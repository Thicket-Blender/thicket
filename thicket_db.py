# ThicketDB: Laubwerk Plants database for Thicket Blender Add-on
#
# SPDX-License-Identifier: GPL-2.0-or-later
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or (at
# your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# Copyright (C) 2020 Darren Hart <dvhart@infradead.org>

import argparse
from collections import deque
import glob
import hashlib
import json
import logging
import os
from pathlib import Path
from subprocess import Popen, PIPE
import sys
import textwrap
try:
    import laubwerk as lbw
    from . import logger
except ImportError:
    # Likely running as a subprocess, these will be added in main()
    pass

# <pep8 compliant>

SCHEMA_VERSION = 2


def md5sum(filename):
    md5 = hashlib.md5()
    with open(filename, mode="rb") as f:
        buf = f.read(4096)
        while buf:
            md5.update(buf)
            buf = f.read(4096)
    return md5.hexdigest()


class DBQualifier:
    def __init__(self, db, name):
        self.name = name
        self.label = db.get_label(name)


class DBModel:
    def __init__(self, db, name, m_rec, plant_preview):
        self.name = name
        self.label = db.get_label(self.name)
        self.qualifiers = [DBQualifier(db, q) for q in m_rec["qualifiers"]]
        self._default_qualifier = DBQualifier(db, m_rec["default_qualifier"])
        self.preview = m_rec["preview"]
        if self.preview == "":
            self.preview = plant_preview

    def get_qualifier(self, name=None):
        """ Return the requested qualifier or the default qualifier if None or not found """
        if name is not None:
            for q in self.qualifiers:
                if q.name == name:
                    return q
        return self._default_qualifier


class DBPlant:
    def __init__(self, db, name):
        self.name = name
        p_rec = db._db["plants"][name]
        self.md5 = p_rec["md5"]
        self.filepath = p_rec["filepath"]
        self.label = db.get_label(self.name)
        preview = p_rec["preview"]
        self.models = [DBModel(db, m, p_rec["models"][m], preview) for m in p_rec["models"]]
        def_m = p_rec["default_model"]
        self._default_model = DBModel(db, def_m, p_rec["models"][def_m], preview)
        self.preview = preview

    def get_model(self, name=None):
        """ Return the requested model or the default model if None or not found """
        if name is not None:
            for m in self.models:
                if m.name == name:
                    return m
        return self._default_model


class DBIter:
    def __init__(self, db):
        self._items = []
        self._index = 0

        for name in db._db["plants"]:
            self._items.append(DBPlant(db, name))
        self._items.sort(key=lambda plant: plant.name)

    def __next__(self):
        if self._index < len(self._items):
            item = self._items[self._index]
            self._index += 1
            return item
        raise StopIteration


class ThicketDBOldSchemaError(Exception):
    # TODO: include current and read schema version
    pass


class ThicketDB:
    """ Thicket Database Interface """
    def __init__(self, db_filename, locale="en-US", python=sys.executable, create=False):
        global SCHEMA_VERSION
        self._db_filename = db_filename
        self.locale = locale.replace("_", "-")
        self.python = python
        try:
            with open(db_filename, "r", encoding="utf-8") as f:
                self._db = json.load(f)
            if self._db["info"]["schema_version"] < SCHEMA_VERSION:
                logger.warning("Unknown database schema version")
                raise ThicketDBOldSchemaError
        except FileNotFoundError:
            if create:
                self.initialize()
                self.save()
            else:
                raise FileNotFoundError
        except json.decoder.JSONDecodeError as e:
            logger.critical("JSONDecodeError while loading database: %s" % e)

    def __iter__(self):
        return DBIter(self)

    def initialize(self):
        global SCHEMA_VERSION
        self._db = {}
        self._db["info"] = {}
        self._db["labels"] = {}
        self._db["plants"] = {}

        self._db["info"]["sdk_version"] = lbw.version
        self._db["info"]["sdk_major"] = lbw.version_info.major
        self._db["info"]["sdk_minor"] = lbw.version_info.minor
        self._db["info"]["sdk_micro"] = lbw.version_info.micro
        self._db["info"]["schema_version"] = SCHEMA_VERSION

    def save(self):
        with open(self._db_filename, "w", encoding="utf-8") as f:
            json.dump(self._db, f, ensure_ascii=False, indent=4)

    def print_info(self):
        info = self._db["info"]
        print("Laubwerk Version: %s" % info["sdk_version"])
        print("\tmajor: %s" % info["sdk_major"])
        print("\tminor: %s" % info["sdk_minor"])
        print("\tmicro: %s" % info["sdk_micro"])
        print("Loaded %d plants:" % self.plant_count())

    def update_labels(self, labels):
        self._db["labels"].update(labels)

    def get_label(self, key, locale=None):
        if locale:
            locale = locale.replace("_", "-")
        else:
            locale = self.locale

        try:
            if locale in self._db["labels"][key]:
                return self._db["labels"][key][locale]
            elif locale[:2] in self._db["labels"][key]:
                return self._db["labels"][key][locale[:2]]
            return key
        except KeyError:
            return key

    def get_plant(self, filepath=None, name=None):
        if name:
            if name not in self._db["plants"]:
                name = None

        if name is None and filepath:
            for n in self._db["plants"]:
                if self._db["plants"][n]["filepath"] == filepath:
                    name = n

        if name:
            return DBPlant(self, name)

        return None

    def add_plant(self, filepath):
        p_rec = ThicketDB.parse_plant(filepath)
        self._db["plants"][p_rec["name"]] = p_rec["plant"]
        self.update_labels(p_rec["labels"])

    def plant_count(self):
        return len(self._db["plants"])

    def build(self, plants_dir, sdk_path):
        self.initialize()

        # FIXME: .gz is optional
        plant_files = glob.glob(plants_dir + "/*/*.lbw.gz")
        num_plants = len(plant_files)

        num_jobs = os.cpu_count()
        if not num_jobs:
            num_jobs = 4
        jobs = deque()

        log_level = logging.getLevelName(logger.level)
        logger.info("Parsing %d plants using %d parallel jobs" % (num_plants, num_jobs))
        while len(plant_files) > 0 or len(jobs) > 0:
            # Keep up to num_jobs jobs running
            while len(jobs) < num_jobs and len(plant_files) > 0:
                f = plant_files.pop()
                logger.debug("Parsing: %s" % f)
                job = Popen([self.python, __file__, "-f", f, "-s", sdk_path, "-l", log_level, "parse_plant"],
                            stdout=PIPE)
                jobs.append(job)

            # Wait for the oldest job to complete
            job = jobs.popleft()
            outs, errs = job.communicate()
            try:
                p_rec = json.loads(outs)
                self._db["plants"][p_rec["plant"]["name"]] = p_rec["plant"]
                self.update_labels(p_rec["labels"])
                logger.info('Added "%s"' % p_rec["plant"]["name"])
            except json.decoder.JSONDecodeError as e:
                logger.error("JSONDecodeError while parsing %s: %s" % (f, e))

        if len(plant_files) > 0:
            logger.error("Exited worker loop with %d plant files remaining" % len(plant_files))

        if len(jobs) > 0:
            logger.error("Exited worker loop with %d jobs still running" % len(jobs))

        self.save()
        logger.info("Processed %d/%d plants" % (self.plant_count(), num_plants))

    def read(self):
        self.print_info()

        for plant in self:
            print("%s (%s)" % (plant.name, plant.label))
            print("\tfile: %s" % plant.filepath)
            print("\tmd5: %s" % plant.md5)
            m = plant.get_model()
            print("\tdefault_model: %s (%s)" % (m.name, m.label))
            print("\tmodels:")
            for m in plant.models:
                print("\t\t%s (%s) %s" % (m.name, m.get_qualifier().label,
                                          [q.name for q in m.qualifiers]))

    # Class methods
    def parse_plant(filepath):
        p = lbw.load(filepath)
        p_rec = {}

        plant = {}
        plant["name"] = p.plant_meta["name"]
        plant["filepath"] = filepath
        plant["md5"] = md5sum(filepath)
        plant["default_model"] = p.default_model.name
        preview_stem = p.plant_meta["botanical_name"].replace(" ", "_").replace(".", "")
        preview_path = Path(filepath).parent.absolute() / (preview_stem + ".png")
        if not preview_path.is_file():
            logger.warning("Preview not found: %s" % preview_path)
            preview_path = ""
        plant["preview"] = str(preview_path)

        labels = {}
        p_labels = {}
        # Store only the first label per locale
        for label in p.plant_meta['labels']:
            if not label['lang'] in p_labels:
                p_labels[label['lang']] = label['text']

        labels[p.name] = p_labels

        models = {}
        i = 0
        seasons = []
        q_labels = {}
        for q in p.params[0]['enum']['options']:
            seasons.append(q['name'])
            q_labels[q['name']] = {}
            for q_lang in q['labels']:
                q_labels[q['name']][q_lang['lang']] = q_lang['text']
        default_season = p.params[0]['enum']['default']

        # in laubwerk API called 'variants'
        for m in p.models:
            m_rec = {}
            labels.update(q_labels)
            m_rec["index"] = i
            m_rec["qualifiers"] = seasons
            m_rec["default_qualifier"] = seasons[default_season]
            preview_path = Path(filepath).parent.absolute() / "models" / (preview_stem + "_" + m.name + ".png")
            if not preview_path.is_file():
                logger.warning("Preview not found: %s" % preview_path)
                preview_path = ""
            m_rec["preview"] = str(preview_path)
            models[m.name] = m_rec
            m_labels = {}

            for label in next(x for x in p.params[1]['enum']['options'] if x['name'] == m.name)['labels']:
                m_labels[label['lang']] = label['text']
            labels[m.name] = m_labels

            i = i + 1
        plant["models"] = models

        p_rec["plant"] = plant
        p_rec["labels"] = labels
        return p_rec

    def parse_plant_json(filepath):
        p_rec = ThicketDB.parse_plant(filepath)
        print(json.dumps(p_rec))


def main():
    global lbw, logger
    argParse = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                       description=textwrap.dedent('''\
Thicket Database Tool
Commands:
  read                read and print the db contents (requires -d)
  build               scan plants path and add all plants to a new db (requires -d -p -s)
  parse_plant         read a plant file and print the plant record json (requires -f -s)
'''))

    argParse.add_argument("cmd", choices=["read", "build", "parse_plant"])
    argParse.add_argument("-d", help="database filename")
    argParse.add_argument("-f", help="Laubwerk Plant filename (lbw.gz)")
    argParse.add_argument("-l", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                          default="INFO", help="logger level")
    argParse.add_argument("-p", help="Laubwerk Plants path")
    argParse.add_argument("-s", help="Laubwerk Python SDK path")

    args = argParse.parse_args()

    logging.basicConfig(format="%(levelname)s: thicket_db: %(message)s", level=args.l)
    logger = logging.getLogger()

    if args.s:
        # If the SDK path was specified, attempt to import the Laubwerk SDK The
        # build and parse_plant commands require the Laubwerk SDK which may or
        # may not be in the sys.path depending on the OS, environment, and how
        # it was called (from Blender, as a subprocess, or via the command
        # line).
        if args.s not in sys.path:
            sys.path.append(args.s)
        import laubwerk as lbw

    cmd = args.cmd
    if cmd == "read" and args.d:
        db = ThicketDB(args.d, create=False)
        db.read()
    elif cmd == "build" and args.d and args.p and lbw:
        db = ThicketDB(args.d, create=True)
        db.build(args.p, args.s)
    elif cmd == "parse_plant" and args.f and lbw:
        ThicketDB.parse_plant_json(args.f)
    else:
        argParse.print_help()
        return 1


if __name__ == "__main__":
    main()
