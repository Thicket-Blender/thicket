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
                       Panel,
                       PropertyGroup
                       )
from bpy.props import (BoolProperty,
                       EnumProperty,
                       FloatProperty,
                       IntProperty,
                       StringProperty,
                       )
from bpy_extras.io_utils import ImportHelper
from bpy.app.translations import locale
import bpy.utils.previews

from .thicket_utils import (is_thicket_instance,
                            delete_plant_template,
                            delete_plant,
                            make_unique,
                            )

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
previews = None


# Add thumbnails to previews
def populate_previews():
    global db, previews

    if previews:
        bpy.utils.previews.remove(previews)
    previews = bpy.utils.previews.new()

    t0 = time.time()

    thicket_path = Path(bpy.utils.user_resource('SCRIPTS', 'addons', True)) / __name__
    missing_path = thicket_path / "doc" / "missing_preview.png"
    previews.load("missing_preview", str(missing_path), 'IMAGE')

    for (filename, plant) in db.db["plants"].items():
        # Load the top plant (no model) preview
        plant_preview_key = plant["name"].replace(' ', '_').replace('.', '')
        preview_path = plant["preview"]
        if preview_path != "" and Path(preview_path).is_file():
            previews.load(plant_preview_key, preview_path, 'IMAGE')

        # Load the previews for each model of the plant
        for model in plant["models"].keys():
            preview_key = plant_preview_key + "_" + model
            preview_path = plant["models"][model]["preview"]
            if preview_path != "" and Path(preview_path).is_file():
                previews.load(preview_key, preview_path, 'IMAGE')

    logging.info("Added %d previews in %0.2fs" % (len(previews), time.time()-t0))


def get_preview(plant_name, model):
    preview_key = plant_name.replace(' ', '_').replace('.', '') + "_" + model
    if preview_key not in previews:
        # The model specific preview was not found, try the plant preview
        logging.warning("Preview key %s not found" % preview_key)
        preview_key = plant_name.replace(' ', '_').replace('.', '')
    if preview_key not in previews:
        logging.warning("Preview key %s not found" % preview_key)
        preview_key = "missing_preview"
    return previews[preview_key]


# Thicket property group
class ThicketPropGroup(PropertyGroup):
    def __eq__(self, other):
        for k, v in self.items():
            if self[k] != other[k]:
                return False
        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    def copy_to(self, other):
        for k, v in self.items():
            other[k] = v

    def as_keywords(self, ignore):
        keywords = dict(self)
        for key in ignore:
            keywords.pop(key, None)
        # Use the Enum string (not the blender internal integer)
        keywords["model"] = self.model
        keywords["qualifier"] = self.qualifier
        keywords["viewport_lod"] = self.viewport_lod
        return keywords

    def model_callback(self, context):
        global db
        # TODO: should this be active_object?
        o = context.object
        if not is_thicket_instance(o):
            return []
        tp = o.instance_collection.thicket
        plant = db.get_plant(tp.filepath)
        items = []
        for model in plant["models"].keys():
            items.append((model, db.get_label(model), ""))
        return items

    def qualifier_callback(self, context):
        global db
        # TODO: should this be active_object?
        o = context.object
        if not is_thicket_instance(o):
            return []
        tp = o.instance_collection.thicket
        plant = db.get_plant(tp.filepath)
        items = []
        for qualifier in plant["models"][tp.model]["qualifiers"]:
            items.append((qualifier, db.get_label(qualifier), ""))
        return items

    magic: bpy.props.StringProperty()

    # WARNING: Properties from here to the closing comment for ThicketPropGroup
    # and ImportLBW must be identical. A common draw routine is used for the
    # Plant Properties Panel and for the import dialog panel. Class inheritance
    # would preferable, but this does not appear to be possible with the Blender
    # Python interface.
    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    model: EnumProperty(items=model_callback, name="Model")
    qualifier: EnumProperty(items=qualifier_callback, name="Season")
    viewport_lod: EnumProperty(name="Viewport Detail", items=[("proxy", "Proxy", ""),
                                                              ("low", "Partial Geometry", "")])
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
    # End of common properties


# Thicket operator to copy the model properties to the modified shadow copy
class THICKET_OT_reset_plant(Operator):
    bl_idname = "thicket.reset_plant"
    bl_label = "Reset Plant"
    bl_description = "Restore the UI properties to the model properties"
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        instance = context.active_object
        if not is_thicket_instance(instance):
            logging.error("reset_plant failed: non-Thicket object: %" % instance.name)
            return
        template = instance.instance_collection
        template.thicket.copy_to(template.thicket_shadow)
        context.area.tag_redraw()
        return {'FINISHED'}


# Thicket operator to modify (delete and replace) the backing objects
class THICKET_OT_update_plant(Operator):
    bl_idname = "thicket.update_plant"
    bl_label = "Update Plant"
    bl_description = "Update plant with new properties"
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        instance = context.active_object
        if not is_thicket_instance(instance):
            logging.error("update_plant failed: non-Thicket object: %" % instance.name)
            return
        instance = context.active_object
        logging.info("Update plant: %s" % instance.name)
        template = instance.instance_collection

        # Load new plant model
        from .thicket_import import LBWImportDialog
        keywords = template.thicket_shadow.as_keywords(ignore=("magic", "name"))
        LBWImportDialog.load(self, context, **keywords)  # noqa: F821
        new_instance = context.active_object
        new_template = new_instance.instance_collection

        # Update the instance_collection reference in the instances
        for i in template.users_dupli_group:
            i.instance_collection = new_template
            i.name = template.name

        # Remove the instance collection created
        delete_plant(new_instance)
        # Remove the old template
        delete_plant_template(template)

        # Restore the active object
        instance.select_set(True)
        bpy.context.view_layer.objects.active = instance

        context.area.tag_redraw()
        return {'FINISHED'}


# Thicket make unique operator
class THICKET_OT_make_unique(Operator):
    bl_idname = "thicket.make_unique"
    bl_label = "Make Unique"
    bl_description = "Display number of plants using this template (click to make unique)"
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        instance = context.active_object
        if not is_thicket_instance(instance):
            logging.error("make_unique failed: non-Thicket object: %" % instance.name)
            return
        make_unique(instance)
        context.area.tag_redraw()
        return {'FINISHED'}


# Thicket operator to delete the active object, and the template if users is 0
class THICKET_OT_delete_plant(Operator):
    bl_idname = "thicket.delete_plant"
    bl_label = "Delete Plant"
    bl_description = "Delete the active plant and remove the template if there are no instances remaining"
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        instance = context.active_object
        if not is_thicket_instance(instance):
            logging.error("delete_plant failed: non-Thicket object: %" % instance.name)
            return
        delete_plant(instance)
        context.area.tag_redraw()
        return {'FINISHED'}


# TODO: put this in the ThicketProps class? thicket_utils?
def draw_thicket_plant_props(layout, data):
    global db
    name = db.get_plant(data.filepath)["name"]
    layout.template_icon(icon_value=get_preview(name, data.model).icon_id, scale=10)
    layout.label(text="%s" % db.get_label(name))
    layout.label(text="(%s)" % name)
    layout.prop(data, "model")
    layout.prop(data, "qualifier")

    layout.separator()

    layout.label(text="Level of Detail")

    r = layout.row()
    c = r.column()
    c.alignment = 'EXPAND'
    c.label(text="Viewport:")
    c = r.column()
    c.alignment = 'RIGHT'
    c.prop(data, "viewport_lod", text="")

    layout.prop(data, "lod_subdiv")
    layout.prop(data, "leaf_density")
    layout.prop(data, "leaf_amount")
    layout.prop(data, "lod_max_level")
    layout.prop(data, "lod_min_thick")


# Thicket Plant Properties Panel
class THICKET_PT_plant_properties(Panel):
    # bl_idname = self.type
    bl_label = "Thicket Plant Properties"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Thicket"

    @classmethod
    def poll(self, context):
        return is_thicket_instance(context.active_object)

    def draw(self, context):
        global db
        instance = context.active_object
        layout = self.layout
        template = instance.instance_collection
        tp = template.thicket_shadow
        num_siblings = len(template.users_dupli_group)

        r = layout.row()
        c = r.column()
        c.operator("thicket.delete_plant", icon='NONE', text="Delete")
        c = r.column()
        c.operator("thicket.make_unique", icon="NONE", text="Make Unique (%d)" % num_siblings)
        c.enabled = num_siblings > 1

        draw_thicket_plant_props(layout, tp)

        layout.separator()

        r = layout.row()
        r.enabled = tp != template.thicket
        c = r.column()
        c.operator("thicket.reset_plant", icon="NONE", text="Reset")
        c = r.column()
        c.operator("thicket.update_plant", icon="NONE", text="Update")


# Update Database Operator (called from AddonPreferences)
class THICKET_OT_rebuild_db(Operator):
    bl_idname = "thicket.rebuild_db"
    bl_label = "Rebuild Database"
    bl_description = "Process Laubwerk Plants library and update the database (may take several minutes)"
    bl_options = {'REGISTER', 'INTERNAL'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        global db, db_path, plants_path, sdk_path
        logging.info("Rebuilding database, this may take several minutes...")
        logging.info("Plants Library: %s" % plants_path)
        logging.info("Database: %s" % db_path)
        t0 = time.time()
        db = ThicketDB(db_path, locale, bpy.app.binary_path_python, True)  # noqa: F821
        db.build(str(plants_path), str(sdk_path))
        logging.info("Rebuilt database in %0.2fs" % (time.time()-t0))
        self.report({'INFO'}, "thicket: Added %d plants to database" % db.plant_count())
        populate_previews()
        context.area.tag_redraw()
        return {'FINISHED'}


# Add Plant to Database Operator (called from Import File Dialog)
class THICKET_OT_add_plant_db(Operator):
    bl_idname = "thicket.add_plant_db"
    bl_label = "Add Plant to Database"
    bl_description = "Parse a Laubwerk Plants file and add to the database"
    bl_options = {'REGISTER', 'INTERNAL'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        global db, sdk_path
        t0 = time.time()
        db.add_plant(self.filepath)
        db.save()
        self.report({'INFO'}, "%s: Added %s to database in %0.2fs" %
                    (__name__, db.get_plant(self.filepath)["name"], time.time()-t0))
        populate_previews()
        context.area.tag_redraw()
        return {'FINISHED'}


# Addon Preferences
class THICKET_Pref(AddonPreferences):
    bl_idname = __name__

    def lbw_path_on_update(self, context):
        populate_previews()

    lbw_path: StringProperty(
        name="Install Path",
        subtype="DIR_PATH",
        description="absolute path to Laubwerk installation containing Plants and Python folders",
        default="",
        update=lbw_path_on_update
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

    def model_callback(self, context):
        global db
        items = []
        for model in THICKET_IO_import_lbw.plant["models"].keys():
            items.append((model, db.get_label(model), ""))
        return items

    def qualifier_callback(self, context):
        global db
        items = []
        for qualifier in THICKET_IO_import_lbw.plant["models"][self.model]["qualifiers"]:
            items.append((qualifier, db.get_label(qualifier), ""))
        return items

    filter_glob: StringProperty(default="*.lbw;*.lbw.gz", options={'HIDDEN'})
    oldpath: StringProperty(name="Old Path", subtype="FILE_PATH")

    # WARNING: Properties from here to the closing comment for ThicketPropGroup
    # and ImportLBW must be identical. A common draw routine is used for the
    # Plant Properties Panel and for the import dialog panel. Class inheritance
    # would preferable, but this does not appear to be possible with the Blender
    # Python interface.
    filepath: StringProperty(name="File Path", subtype="FILE_PATH")
    viewport_lod: EnumProperty(name="Viewport Detail", items=[("proxy", "Proxy", ""),
                                                              ("low", "Partial Geometry", "")])
    model: EnumProperty(items=model_callback, name="Model")
    qualifier: EnumProperty(items=qualifier_callback, name="Season")
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
    # End of common properties

    # Class variable
    plant = None

    def execute(self, context):
        from .thicket_import import LBWImportDialog
        keywords = self.as_keywords(ignore=("filter_glob", "oldpath"))
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
            # Because this plant was not in the database, the model and
            # qualifier properties are empty. We need to force reloading them
            # after it is added to the DB. Force this by setting oldpath to the
            # empty string, which will trigger draw() to treat this as a new
            # file.
            self.oldpath = ""
            return

        if new_file:
            self.model = THICKET_IO_import_lbw.plant["default_model"]
            self.qualifier = THICKET_IO_import_lbw.plant["models"][self.model]["default_qualifier"]

        # Create the UI entries.
        draw_thicket_plant_props(layout, self)


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
    bpy.utils.register_class(THICKET_OT_reset_plant)
    bpy.utils.register_class(THICKET_OT_update_plant)
    bpy.utils.register_class(THICKET_OT_delete_plant)
    bpy.utils.register_class(THICKET_OT_make_unique)
    bpy.types.TOPBAR_MT_file_import.append(menu_import_lbw)
    bpy.utils.register_class(ThicketPropGroup)
    bpy.utils.register_class(THICKET_PT_plant_properties)
    bpy.types.Collection.thicket = bpy.props.PointerProperty(type=ThicketPropGroup)
    bpy.types.Collection.thicket_shadow = bpy.props.PointerProperty(type=ThicketPropGroup)

    # Create the database path if it does not exist
    if not db_path.exists():
        db_dir = Path(PurePath(db_path).parent)
        db_dir.mkdir(parents=True, exist_ok=True)

    # Initial global plants_path and sdk_path
    lbw_path = bpy.context.preferences.addons[__name__].preferences.lbw_path
    if lbw_path and Path(lbw_path).is_dir():
        plants_path = Path(lbw_path) / "Plants"
        sdk_path = Path(lbw_path) / "Python"

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
    populate_previews()
    logging.info("Ready")


def unregister():
    global previews

    bpy.utils.unregister_class(THICKET_IO_import_lbw)
    bpy.utils.unregister_class(THICKET_Pref)
    bpy.utils.unregister_class(THICKET_OT_rebuild_db)
    bpy.utils.unregister_class(THICKET_OT_reset_plant)
    bpy.utils.unregister_class(THICKET_OT_update_plant)
    bpy.utils.unregister_class(THICKET_OT_delete_plant)
    bpy.utils.unregister_class(THICKET_OT_make_unique)
    bpy.utils.unregister_class(THICKET_OT_add_plant_db)
    bpy.types.TOPBAR_MT_file_import.remove(menu_import_lbw)
    bpy.utils.unregister_class(ThicketPropGroup)
    bpy.utils.unregister_class(THICKET_PT_plant_properties)
    bpy.utils.previews.remove(previews)


if __name__ == "__main__":
    register()
