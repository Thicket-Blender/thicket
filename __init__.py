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

from io_import_laubwerk import lbwdb
from io_import_laubwerk import import_lbw

bl_info = {
    "name": "Laubwerk lbw.gz format importer",
    "author": "Fabian Quosdorf",
    "version": (0, 1, 0),
    "blender": (2, 80, 0),
    "location": "File > Import",
    "description": "Import LBW.GZ, Import Laubwerk mesh, UV's, materials and textures",
    "warning": "",
    'wiki_url': 'https://github.com/dvhart/lbwbl/blob/master/README.md',
    'tracker_url': 'https://github.com/dvhart/lbwbl/issues',
    'link': 'https://github.com/dvhart/lbwbl',
    "category": "Import"
}

# A global variable for the plant.
db = None
plant = None
current_path = ""
models = []
m_items = []
s_items = []
locale = "en"
alt_locale = "en_US"

# TODO get the locale from the current blender installation via bpy.app.translations.locale. This can be void.

# Update Database Operator (called from AddonPreferences)
class LBWBL_OT_update_db(Operator):
    bl_idname = "lbwbl.update_db"
    bl_label = "Update Database"
    bl_description = "Process Laubwerk Plants library and update the database (may take several minutes)"
    bl_options = {'REGISTER', 'INTERNAL'}

    def update_db(self, context):
        global db
        addon_name = __name__.split('.')[0]
        prefs = context.preferences.addons[addon_name].preferences
        lbw_path = prefs.laubwerk_path
        print("Updating Laubwerk database from %s, this may take several minutes..." % lbw_path)
        t0 = time.time()
        lbwdb.lbwdb_write("lbwdb.json", lbw_path)
        db = lbwdb.LaubwerkDB("lbwdb.json")
        self.report({'INFO'}, "Updated Laubwerk database with %d plants in %0.2fs" %
                    (db.plant_count(), time.time()-t0))

    def invoke(self, context, event):
        addon_name = __name__.split('.')[0]
        lbw_path = context.preferences.addons[addon_name].preferences.laubwerk_path
        if lbw_path == '':
            self.report({'ERROR'}, "You must setup the Laubwerk Plants installation path in addon preferences")
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        self.update_db(context)
        context.area.tag_redraw()
        return {'FINISHED'}


# Addon Preferences
class LBWBL_Pref(AddonPreferences):
    bl_idname = __name__
    laubwerk_path: StringProperty(
        name="Laubwerk Path",
        subtype="DIR_PATH",
        description="absolute path to Laubwerk installation",
        default=""
        )

    def draw(self, context):
        global db
        layout = self.layout
        box = layout.box()
        box.label(text="Plants Library")

        row = box.row()
        row.prop(self, "laubwerk_path")

        row = box.row()
        # TODO: this should be inactive until a laubwerk_path is configured
        row.operator("lbwbl.update_db", icon="FILE_REFRESH")
        # TODO: how do we make this label expand and align left?
        row.label(text="Database contains %d plants" % db.plant_count())


class ImportLBW(bpy.types.Operator, ImportHelper):
    """Load a Laubwerk LBW.GZ File"""
    global db
    bl_idname = "import_object.lbw"
    bl_label = "Import Laubwerk Plant"

    filename_ext = ".lbw.gz"
    short_ext = ".lbw"
    oldpath = ""
    model_id = 0
    db = lbwdb.LaubwerkDB("lbwdb.json")

    filter_glob: StringProperty(default="*.lbw;*.lbw.gz", options={'HIDDEN'})
    filepath: StringProperty(name="File Path", maxlen=1024, default="")

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

    def update_seasons(self, context):
        global locale, alt_locale, s_items, plant, db
        s_items = []
        for qualifier in plant["models"][models[self["model_type"]]]["qualifiers"]:
            s_items.append((qualifier, db.get_label(qualifier), ""))
        self["model_season"] = plant["models"][plant["default_model"]]["default_qualifier"]

    def model_type_callback(self, context):
        global m_items
        return m_items

    def model_season_callback(self, context):
        global s_items
        return s_items

    model_type: EnumProperty(items=model_type_callback, name="Model", update=update_seasons)
    model_season: EnumProperty(items=model_season_callback, name="Season")

    def execute(self, context):
        # Set the model_id to the currently selected model type.
        self.model_id = models.index(self.model_type)
        # Use this dictionary to store additional parameters like season and so on.
        keywords = self.as_keywords(ignore=("filter_glob", "oldpath"))
        keywords["model_id"] = self.model_id
        return import_lbw.LBWImportDialog.load(self, context, **keywords)

    def invoke(self, context, event):
        self.oldpath = self.filepath
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        global locale, alt_locale, plant, db

        layout = self.layout
        if not os.path.isfile(self.filepath):
            # Path is most likely a directory
            layout.label(text="Choose a Laubwerk file.")
            return

        if not self.filepath == self.oldpath:
            self.oldpath = self.filepath
            plant = None
            if os.path.isfile(self.filepath):
                plant = db.get_plant(self.filepath)
                if plant:
                    for model in plant["models"].items():
                        m_items.append((model[0], db.get_label(model[0]), ""))
                        models.append(model[0])
                    self.model_type = plant["default_model"]
                    self.model_id = models.index(self.model_type)

        if not plant:
            layout.label(text="Plant not found in database.", icon='ERROR')
            layout.label(text="Update the database")
            layout.label(text="in the %s" % __name__)
            layout.label(text="Addon Preferences.")
            return

        # Create the UI entries.
        layout.label(text="%s" % db.get_label(plant["name"]))
        layout.label(text="(%s)" % plant["name"])
        layout.prop(self, "model_type")
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
    self.layout.operator(ImportLBW.bl_idname, text="Laubwerk plant (.lbw.gz)")


def register():
    # create LBW Settings
    bpy.types.Object.leaf_density = FloatProperty(name="Leaf density",
                                                  description="The density of the leafs of the plant.",
                                                  default=100.0, min=0.01, max=100.0, subtype='PERCENTAGE')
    bpy.types.Object.viewport_proxy = BoolProperty(name="Viewport Proxy", default=True)
    bpy.types.Object.lod_cull_thick = BoolProperty(name="Cull by Thickness", default=False)
    bpy.types.Object.lod_min_thick = FloatProperty(name="Min. Thickness", default=0.1, min=0.1, max=10000.0, step=1.0)
    bpy.types.Object.lod_cull_level = BoolProperty(name="Cull by Level", default=False)
    bpy.types.Object.lod_max_level = IntProperty(name="Maximum Level", default=5, min=0, max=10, step=1)
    bpy.types.Object.lod_subdiv = IntProperty(name="Subdivision", default=3, min=0, max=5, step=1)
    bpy.types.Object.leaf_amount = FloatProperty(name="Leaf amount", description="The amount of leafs of the plant.",
                                                 default=100.0, min=0.01, max=100.0, subtype='PERCENTAGE',
                                                 options={'HIDDEN'})

    bpy.utils.register_class(ImportLBW)
    bpy.utils.register_class(LBWBL_Pref)
    bpy.utils.register_class(LBWBL_OT_update_db)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.utils.unregister_class(ImportLBW)
    bpy.utils.unregister_class(LBWBL_Pref)
    bpy.utils.unregister_class(LBWBL_OT_update_db)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


if __name__ == "__main__":
    register()
