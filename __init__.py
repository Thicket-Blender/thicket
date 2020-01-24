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
# Copyright (C) 2015 Fabian Quosdorf <fabian@faqgames.net>
# Copyright (C) 2019 Darren Hart <dvhart@infradead.org>


# <pep8-80 compliant>

import os.path
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

bl_info = {
    "name": "Laubwerk Plants Importer",
    "author": "Darren Hart",
    "version": (0, 1, 9),
    "blender": (2, 80, 0),
    "location": "File > Import",
    "description": "Import Laubwerk Plant files (lbw.gz)",
    "warning": "",
    'wiki_url': 'https://github.com/dvhart/lbwbl/blob/master/README.md',
    'tracker_url': 'https://github.com/dvhart/lbwbl/issues',
    'link': 'https://github.com/dvhart/lbwbl',
    "category": "Import"
}

# A global variable for the plant.
db = None
db_path = os.path.join(bpy.utils.user_resource('SCRIPTS', "addons", True), __name__, "laubwerk.db")
plants_path = ""
sdk_path = ""
current_path = ""
plant = None

# TODO get the locale from the current blender installation via bpy.app.translations.locale.
locale = "en_US"
alt_locale = "en"


# Update Database Operator (called from AddonPreferences)
class LBWBL_OT_rebuild_db(Operator):
    bl_idname = "lbwbl.rebuild_db"
    bl_label = "Rebuild Database"
    bl_description = "Process Laubwerk Plants library and update the database (may take several minutes)"
    bl_options = {'REGISTER', 'INTERNAL'}

    def rebuild_db(self, context):
        global db, db_path, plants_path
        print("%s: Rebuilding Laubwerk database, this may take several minutes..." % __name__)
        print("  Plants Library: %s" % plants_path)
        print("  Database: %s" % db_path)
        t0 = time.time()
        lbwdb.lbwdb_write(db_path, plants_path, bpy.app.binary_path_python)  # noqa: F821
        db = lbwdb.LaubwerkDB(db_path, bpy.app.binary_path_python)  # noqa: F821
        self.report({'INFO'}, "%s: Updated Laubwerk database with %d plants in %0.2fs" %
                    (__name__, db.plant_count(), time.time()-t0))

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        self.rebuild_db(context)
        context.area.tag_redraw()
        return {'FINISHED'}


# Import Plant Operator (called from Import File Dialog)
class LBWBL_OT_import_plant_db(Operator):
    bl_idname = "lbwbl.import_plant_db"
    bl_label = "Import Plant into Database"
    bl_description = "Process a Laubwerk Plants file and add to the database"
    bl_options = {'REGISTER', 'INTERNAL'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def import_plant_db(self):
        global db
        print("%s: Importing Laubwerk Plant into database from %s" % (__name__, self.filepath))
        t0 = time.time()
        db.import_plant(self.filepath)
        db.save()
        self.report({'INFO'}, "%s: Imported Laubwerk Plant into database in %0.2fs" %
                    (__name__, time.time()-t0))

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        self.import_plant_db()
        context.area.tag_redraw()
        return {'FINISHED'}


# Addon Preferences
class LBWBL_Pref(AddonPreferences):
    bl_idname = __name__

    lbw_path: StringProperty(
        name="Install Path",
        subtype="DIR_PATH",
        description="absolute path to Laubwerk installation containing Plants and Python folders",
        default=""
        )

    def draw(self, context):
        global db, db_path, plants_path, sdk_path

        # Test for a valid Laubwerk installation path
        # It should contain both a Plants and a Python directory
        valid_lbw_path = False
        if os.path.isdir(self.lbw_path):
            plants_path = os.path.join(self.lbw_path, "Plants" + os.sep)
            sdk_path = os.path.join(self.lbw_path, "Python" + os.sep)
            valid_lbw_path = os.path.isdir(plants_path) and os.path.isdir(sdk_path)

        if valid_lbw_path and "lbwdb" not in sys.modules:
            if sdk_path not in sys.path:
                sys.path.append(sdk_path)
            from io_import_laubwerk import lbwdb
            db = lbwdb.LaubwerkDB(db_path, bpy.app.binary_path_python)

        box = self.layout.box()
        box.label(text="Laubwerk Plants Library")
        row = box.row()
        row.alert = not valid_lbw_path
        row.prop(self, "lbw_path")

        row = box.row()
        row.enabled = valid_lbw_path
        row.operator("lbwbl.rebuild_db", icon="FILE_REFRESH")

        if db:
            row.label(text="Database contains %d plants" % db.plant_count())


class ImportLBW(bpy.types.Operator, ImportHelper):
    """Load a Laubwerk LBW.GZ File"""
    bl_idname = "import_object.lbw"
    bl_label = "Import Laubwerk Plant"

    filename_ext = ".lbw.gz"
    short_ext = ".lbw"

    filter_glob: StringProperty(default="*.lbw;*.lbw.gz", options={'HIDDEN'})
    filepath: StringProperty(name="File Path", subtype="FILE_PATH")
    oldpath = None

    # Viewport Settings
    viewport_proxy: BoolProperty(name="Display Proxy", default=True)

    # Render Settings
    lod_subdiv: IntProperty(name="Subdivision", default=3, min=0, max=5, step=1)
    leaf_density: FloatProperty(name="Leaf density",
                                description="The density of the leafs of the plant.",
                                default=100.0, min=0.01, max=100.0, subtype='PERCENTAGE')
    leaf_amount: FloatProperty(name="Leaf amount",
                               description="The amount of leafs of the plant.",
                               default=100.0, min=0.01, max=100.0, subtype='PERCENTAGE')
    lod_max_level: IntProperty(name="Maximum Level", default=5, min=0, max=10, step=1)
    lod_min_thick: FloatProperty(name="Minimum Thickness", default=0.1, min=0.1, max=10000.0, step=1.0)

    def model_id_callback(self, context):
        global locale, alt_locale, db, plant
        items = []
        for model in plant["models"].keys():
            index = plant["models"][model]["index"]
            items.append((model, db.get_label(model, locale, alt_locale), "", index))
        return items

    def model_season_callback(self, context):
        global locale, alt_locale, db, plant
        items = []
        for qualifier in plant["models"][self.model_id]["qualifiers"]:
            items.append((qualifier, db.get_label(qualifier, locale, alt_locale), ""))
        return items

    model_id: EnumProperty(items=model_id_callback, name="Model")
    model_season: EnumProperty(items=model_season_callback, name="Season")

    def execute(self, context):
        from io_import_laubwerk import import_lbw
        global plant
        keywords = self.as_keywords(ignore=("filter_glob",))
        keywords["model_id"] = self.properties["model_id"]
        return import_lbw.LBWImportDialog.load(self, context, **keywords)  # noqa: F821

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        global locale, alt_locale, db, plant
        layout = self.layout
        new_file = False

        if not self.oldpath == self.filepath:
            self.oldpath = self.filepath
            new_file = True

        if not os.path.isfile(self.filepath):
            # Path is most likely a directory
            layout.label(text="Choose a Laubwerk file.")
            return

        plant = db.get_plant(self.filepath)
        if not plant:
            layout.label(text="Plant not found in database.", icon='ERROR')
            layout.label(text="Rebuild the database in")
            layout.label(text="Addon Preferences.")
            layout.separator()
            layout.label(text="You may also import only this plant.")
            op = layout.operator("lbwbl.import_plant_db", icon="IMPORT")
            op.filepath = self.filepath
            return

        if new_file:
            self.model_id = plant["default_model"]
            self.model_season = plant["models"][self.model_id]["default_qualifier"]

        # Create the UI entries.
        layout.label(text="%s" % db.get_label(plant["name"], locale, alt_locale))
        layout.label(text="(%s)" % plant["name"])
        layout.prop(self, "model_id")
        layout.prop(self, "model_season")

        box = layout.box()
        box.label(text="Viewport Settings")
        box.prop(self, "viewport_proxy")

        box = layout.box()
        box.label(text="Render Settings")
        box.prop(self, "lod_subdiv")
        box.prop(self, "leaf_density")
        box.prop(self, "leaf_amount")
        box.prop(self, "lod_max_level")
        box.prop(self, "lod_min_thick")


def menu_func_import(self, context):
    global plants_path, db

    if not db:
        self.layout.label(text="Laubwerk plant (not configured)")
        return

    op = self.layout.operator(ImportLBW.bl_idname, text="Laubwerk plant (.lbw.gz)")
    op.filepath = plants_path


def register():
    global db, db_path, plants_path, sdk_path

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

    bpy.utils.register_class(ImportLBW)
    bpy.utils.register_class(LBWBL_Pref)
    bpy.utils.register_class(LBWBL_OT_rebuild_db)
    bpy.utils.register_class(LBWBL_OT_import_plant_db)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

    # Create the database path if it does not exist
    if not os.path.exists(db_path):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # Initial global plants_path and sdk_path
    lbw_path = bpy.context.preferences.addons[__name__].preferences.lbw_path
    if lbw_path and os.path.isdir(lbw_path):
        plants_path = os.path.join(lbw_path, "Plants" + os.sep)
        sdk_path = os.path.join(lbw_path, "Python" + os.sep)

    # Dynamically add the sdk_path to the sys.path
    if not sdk_path or not os.path.isdir(sdk_path):
        print("%s: Please configure Laubwerk Install Path in Addon Preferences" % __name__)
        return

    if sdk_path not in sys.path:
        sys.path.append(sdk_path)

    from io_import_laubwerk import lbwdb
    db = lbwdb.LaubwerkDB(db_path, bpy.app.binary_path_python)


def unregister():
    bpy.utils.unregister_class(ImportLBW)
    bpy.utils.unregister_class(LBWBL_Pref)
    bpy.utils.unregister_class(LBWBL_OT_rebuild_db)
    bpy.utils.unregister_class(LBWBL_OT_import_plant_db)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


if __name__ == "__main__":
    register()
