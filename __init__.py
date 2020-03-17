# Blender import plugin for Lauawberk plant models
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
# This project was forked from and inspired by:
#   https://bitbucket.org/laubwerk/lbwbl
#
# Copyright (C) 2015 Fabian Quosdorf <fabian@faqgames.net>
# Copyright (C) 2019-2020 Darren Hart <dvhart@infradead.org>


# <pep8 compliant>

import logging
import os
from pathlib import Path, PurePath
import sys
import time

import bpy
from bpy.types import (AddonPreferences,
                       Operator,
                       )
from bpy.props import (BoolProperty,
                       FloatProperty,
                       IntProperty,
                       StringProperty,
                       EnumProperty,
                       )
from bpy_extras.io_utils import ImportHelper
from bpy.app.translations import locale
import bpy.utils.previews

logging.basicConfig(format='%(levelname)s: thicket: %(message)s', level=logging.INFO)

bl_info = {
    "name": "Thicket: Laubwerk Plants Add-on for Blender",
    "author": "Darren Hart",
    "version": (0, 1, 9),
    "blender": (2, 80, 0),
    "location": "File > Import",
    "description": "Import Laubwerk Plants (.lbw.gz)",
    "warning": "",
    'wiki_url': 'https://github.com/dvhart/lbwbl/blob/master/README.md',
    'tracker_url': 'https://github.com/dvhart/lbwbl/issues',
    'link': 'https://github.com/dvhart/lbwbl',
    "category": "Import"
}

# A global variable for the plant.
db = None
db_path = Path(bpy.utils.user_resource('SCRIPTS', "addons", True)) / __name__ / "thicket.db"
plants_path = None
sdk_path = None


# Update Database Operator (called from AddonPreferences)
class THICKET_OT_rebuild_db(Operator):
    bl_idname = "thicket.rebuild_db"
    bl_label = "Rebuild Database"
    bl_description = "Process Laubwerk Plants library and update the database (may take several minutes)"
    bl_options = {'REGISTER', 'INTERNAL'}

    def rebuild_db(self, context):
        global db, db_path, plants_path, sdk_path
        logging.info("Rebuilding database, this may take several minutes...")
        logging.info("Plants Library: %s" % plants_path)
        logging.info("Database: %s" % db_path)
        t0 = time.time()
        db = ThicketDB(db_path, locale, bpy.app.binary_path_python, True)  # noqa: F821
        db.build(str(plants_path), str(sdk_path))
        logging.info("Rebuilt database in %0.2fs" % (time.time()-t0))
        self.report({'INFO'}, "thicket: Added %d plants to database" % db.plant_count())

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        self.rebuild_db(context)
        context.area.tag_redraw()
        return {'FINISHED'}


# Add Plant to Database Operator (called from Import File Dialog)
class THICKET_OT_add_plant_db(Operator):
    bl_idname = "thicket.add_plant_db"
    bl_label = "Add Plant to Database"
    bl_description = "Parse a Laubwerk Plants file and add to the database"
    bl_options = {'REGISTER', 'INTERNAL'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def add_plant_db(self):
        global db, sdk_path
        t0 = time.time()
        db.add_plant(self.filepath)
        db.save()
        self.report({'INFO'}, "%s: Added %s to database in %0.2fs" %
                    (__name__, db.get_plant(self.filepath)["name"], time.time()-t0))

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        self.add_plant_db()
        context.area.tag_redraw()
        return {'FINISHED'}


# Addon Preferences
class THICKET_Pref(AddonPreferences):
    bl_idname = __name__

    lbw_path: StringProperty(
        name="Install Path",
        subtype="DIR_PATH",
        description="absolute path to Laubwerk installation containing Plants and Python folders",
        default=""
        )

    def draw(self, context):
        global db, db_path, plants_path, sdk_path, ThicketDB

        # Test for a valid Laubwerk installation path
        # It should contain both a Plants and a Python directory
        valid_lbw_path = False
        if Path(self.lbw_path).is_dir():
            plants_path = Path(self.lbw_path) / "Plants"
            sdk_path = Path(self.lbw_path) / "Python"
            valid_lbw_path = plants_path.is_dir() and sdk_path.is_dir()

        if valid_lbw_path:
            if str(sdk_path) not in sys.path:
                sys.path.append(str(sdk_path))
                db = None
            if "thicket_db" not in sys.modules:
                from .thicket_db import ThicketDB
                db = None
            if not db:
                db = ThicketDB(db_path, locale, bpy.app.binary_path_python, True)

        box = self.layout.box()
        box.label(text="Laubwerk Plants Library")
        row = box.row()
        row.alert = not valid_lbw_path
        row.prop(self, "lbw_path")

        if valid_lbw_path:
            import laubwerk
            row = box.row()
            row.label(text=laubwerk.version)

        row = box.row()
        row.enabled = valid_lbw_path
        row.operator("thicket.rebuild_db", icon="FILE_REFRESH")

        if db:
            row.label(text="Database contains %d plants" % db.plant_count())


class THICKET_IO_import_lbw(bpy.types.Operator, ImportHelper):
    """Import a Laubwerk LBW.GZ File"""
    bl_idname = "import_object.lbw"
    bl_label = "Import LBW"

    filter_glob: StringProperty(default="*.lbw;*.lbw.gz", options={'HIDDEN'})
    filepath: StringProperty(name="File Path", subtype="FILE_PATH")
    oldpath: StringProperty(name="Old Path", subtype="FILE_PATH")

    # Level of detail settings
    viewport_lod: EnumProperty(name="Detail", items=[("proxy", "Very Low (Convex Hull)", ""),
                                                     ("low", "Low (Realistic)", "")])
    lod_subdiv: IntProperty(name="Subdivision", description="How round the trunk and branches appear",
                            default=3, min=0, max=5, step=1)
    leaf_density: FloatProperty(name="Leaf Density", description="How full the foliage appears",
                                default=100.0, min=0.01, max=100.0, subtype='PERCENTAGE')
    leaf_amount: FloatProperty(name="Leaf Amount", description="How many leaves used for leaf density "
                               "(smaller number means larger leaves)",
                               default=100.0, min=0.01, max=100.0, subtype='PERCENTAGE')
    lod_max_level: IntProperty(name="Branching Level", description="Max branching levels off the trunk",
                               default=5, min=0, max=10, step=1)
    lod_min_thick: FloatProperty(name="Min Branch Thickness", description="Min thickness of trunk or branches",
                                 default=0.1, min=0.1, max=10000.0, step=1.0)

    # Class variable
    plant = None

    def model_id_callback(self, context):
        global db
        items = []
        for model in THICKET_IO_import_lbw.plant["models"].keys():
            index = THICKET_IO_import_lbw.plant["models"][model]["index"]
            items.append((model, db.get_label(model), "", index))
        return items

    def model_season_callback(self, context):
        global db
        items = []
        for qualifier in THICKET_IO_import_lbw.plant["models"][self.model_id]["qualifiers"]:
            items.append((qualifier, db.get_label(qualifier), ""))
        return items

    model_id: EnumProperty(items=model_id_callback, name="Model")
    model_season: EnumProperty(items=model_season_callback, name="Season")

    def execute(self, context):
        from .thicket_import import LBWImportDialog
        keywords = self.as_keywords(ignore=("filter_glob", "oldpath"))
        keywords["model_id"] = self.properties["model_id"]
        return LBWImportDialog.load(self, context, **keywords)  # noqa: F821

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        global db
        layout = self.layout
        new_file = False

        if not self.oldpath == self.filepath:
            self.oldpath = self.filepath
            new_file = True

        if not Path(self.filepath).is_file():
            # Path is most likely a directory
            layout.label(text="Choose a Laubwerk Plant (.lbw.gz)")
            return

        THICKET_IO_import_lbw.plant = db.get_plant(self.filepath)
        if not THICKET_IO_import_lbw.plant:
            layout.label(text="Plant not found in database.", icon='ERROR')
            layout.label(text="Rebuild the database in")
            layout.label(text="Addon Preferences.")
            layout.separator()
            layout.label(text="You may add this plant individually.")
            op = layout.operator("thicket.add_plant_db", icon="IMPORT")
            op.filepath = self.filepath
            # Because this plant was not in the database, the model_id and
            # model_season properties are empty. We need to force reloading them
            # after it is added to the DB. Force this by setting oldpath to the
            # empty string, which will trigger draw() to treat this as a new
            # file.
            self.oldpath = ""
            return

        if new_file:
            self.model_id = THICKET_IO_import_lbw.plant["default_model"]
            self.model_season = THICKET_IO_import_lbw.plant["models"][self.model_id]["default_qualifier"]

        # Create the UI entries.
        preview_key = THICKET_IO_import_lbw.plant["name"].replace(' ', '_').replace('.', '') + "_" + self.model_id
        if preview_key not in previews:
            # Attempt to add the model specific preview if it is not already loaded
            preview_path = THICKET_IO_import_lbw.plant["models"][self.model_id]["preview"]
            if preview_path != "" and Path(preview_path).is_file():
                previews.load(preview_key, preview_path, 'IMAGE')
        if preview_key not in previews:
            # The model specific preview was not found, try the plant preview
            logging.warning("Preview key %s not found" % preview_key)
            preview_key = THICKET_IO_import_lbw.plant["name"].replace(' ', '_').replace('.', '')
        if preview_key not in previews:
            preview_path = THICKET_IO_import_lbw.plant["preview"]
            if preview_path != "" and Path(preview_path).is_file():
                previews.load(preview_key, preview_path, 'IMAGE')
        if preview_key not in previews:
            logging.warning("Preview key %s not found" % preview_key)
            preview_key = "missing_preview"
        layout.template_icon(icon_value=previews[preview_key].icon_id, scale=10)

        layout.label(text="%s" % db.get_label(THICKET_IO_import_lbw.plant["name"]))
        layout.label(text="(%s)" % THICKET_IO_import_lbw.plant["name"])
        layout.prop(self, "model_id")
        layout.prop(self, "model_season")

        box = layout.box()
        box.label(text="Viewport Model")
        box.prop(self, "viewport_lod")
        box = layout.box()
        box.label(text="Render Model")
        box.prop(self, "lod_subdiv")
        box.prop(self, "leaf_density")
        box.prop(self, "leaf_amount")
        box.prop(self, "lod_max_level")
        box.prop(self, "lod_min_thick")


def menu_import_lbw(self, context):
    global plants_path, db

    if not db:
        self.layout.label(text="Laubwerk Plant (not configured)")
        return

    op = self.layout.operator(THICKET_IO_import_lbw.bl_idname, text="Laubwerk Plant (.lbw.gz)")
    op.filepath = str(plants_path) + os.sep


def register():
    global db, db_path, plants_path, sdk_path, previews, ThicketDB

    # create Laubwerk Plant object properties
    bpy.types.Object.viewport_proxy = BoolProperty(name="Viewport Proxy", default=True)
    bpy.types.Object.lod_subdiv = IntProperty(name="Subdivision", default=3, min=0, max=5, step=1)
    bpy.types.Object.leaf_density = FloatProperty(name="Leaf density",
                                                  description="The density of the leafs of the plant.",
                                                  default=100.0, min=0.01, max=100.0, subtype='PERCENTAGE')
    bpy.types.Object.leaf_amount = FloatProperty(name="Leaf amount", description="The amount of leafs of the plant.",
                                                 default=100.0, min=0.01, max=100.0, subtype='PERCENTAGE',
                                                 options={'HIDDEN'})
    bpy.types.Object.lod_min_thick = FloatProperty(name="Min. Thickness", default=0.1, min=0.1, max=10000.0, step=1.0)
    bpy.types.Object.lod_max_level = IntProperty(name="Maximum Level", default=5, min=0, max=10, step=1)

    bpy.utils.register_class(THICKET_IO_import_lbw)
    bpy.utils.register_class(THICKET_Pref)
    bpy.utils.register_class(THICKET_OT_rebuild_db)
    bpy.utils.register_class(THICKET_OT_add_plant_db)
    bpy.types.TOPBAR_MT_file_import.append(menu_import_lbw)

    # Create the database path if it does not exist
    if not db_path.exists():
        db_dir = Path(PurePath(db_path).parent)
        db_dir.mkdir(parents=True, exist_ok=True)

    # Initial global plants_path and sdk_path
    lbw_path = bpy.context.preferences.addons[__name__].preferences.lbw_path
    if lbw_path and Path(lbw_path).is_dir():
        plants_path = Path(lbw_path) / "Plants"
        sdk_path = Path(lbw_path) / "Python"

    previews = bpy.utils.previews.new()
    missing_path = Path(bpy.utils.user_resource('SCRIPTS', "addons", True)) / __name__ / "doc" / "missing_preview.png"
    previews.load("missing_preview", str(missing_path), 'IMAGE')

    # Dynamically add the sdk_path to the sys.path
    if not sdk_path or not sdk_path.is_dir():
        logging.info("Please configure Laubwerk Install Path in Addon Preferences")
        return

    if str(sdk_path) not in sys.path:
        sys.path.append(str(sdk_path))

    from .thicket_db import ThicketDB
    try:
        db = ThicketDB(db_path, locale, bpy.app.binary_path_python)
    except FileNotFoundError:
        logging.warning("Database not found, creating empty database")
        db = ThicketDB(db_path, locale, bpy.app.binary_path_python, True)
    logging.info("Ready")


def unregister():
    global previews

    bpy.utils.unregister_class(THICKET_IO_import_lbw)
    bpy.utils.unregister_class(THICKET_Pref)
    bpy.utils.unregister_class(THICKET_OT_rebuild_db)
    bpy.utils.unregister_class(THICKET_OT_add_plant_db)
    bpy.types.TOPBAR_MT_file_import.remove(menu_import_lbw)
    bpy.utils.previews.remove(previews)


if __name__ == "__main__":
    register()
