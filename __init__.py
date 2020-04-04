# Thicket: Laubwerk Plants Add-on for Blender
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

"""Thicket: Laubwerk Plants Add-on for Blender

Thicket adds import and level-of-detail support to Blender for Laubwerk Plant
Kits. It requires the Laubwerk Python SDK included with all Laubwerk Plant Kits.
"""

import logging
from pathlib import Path, PurePath
import sys
import time

import bpy
from bpy.types import (AddonPreferences,
                       Operator,
                       Panel,
                       PropertyGroup
                       )
from bpy.props import (EnumProperty,
                       FloatProperty,
                       IntProperty,
                       PointerProperty,
                       StringProperty,
                       )
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


thicket_ready = False
db = None
plants_path = None
sdk_path = None
thicket_previews = None
thicket_ui_mode = 'VIEW'
thicket_ui_obj = None
THICKET_GUID = '5ff1c66f282a45a488a6faa3070152a2'
THICKET_SCALE = 10


###############################################################################
# Thicket helper functions
#
# These are mostly functions that are used by more than one class. Placed here
# at the top for name resolution purposes.
###############################################################################


def populate_previews():
    """Create a Blender preview collection of plant thumbnails

    Walk through all the plants in the Thicket database and add the thumbnails
    for each plant and each plant model to the previews collection for use in
    the plant properties panels.

    Previews are keyed on the plant name and model as well as just the plant
    name as a fall back. In case no previews are available, the
    "missing_preview" key points to a generic preview.
    """

    global db, thicket_previews

    if thicket_previews:
        bpy.utils.previews.remove(thicket_previews)
    thicket_previews = bpy.utils.previews.new()

    t0 = time.time()

    thicket_path = Path(bpy.utils.user_resource('SCRIPTS', 'addons', True)) / __name__
    missing_path = thicket_path / "doc" / "missing_preview.png"
    thicket_previews.load("missing_preview", str(missing_path), 'IMAGE')

    for plant in db:
        # Load the top plant (no model) preview
        plant_preview_key = plant.name.replace(' ', '_').replace('.', '')
        preview_path = plant.preview
        if preview_path != "" and Path(preview_path).is_file():
            thicket_previews.load(plant_preview_key, preview_path, 'IMAGE')

        # Load the previews for each model of the plant
        for model in plant.models:
            preview_key = plant_preview_key + "_" + model.name
            preview_path = model.preview
            if preview_path != "" and Path(preview_path).is_file():
                thicket_previews.load(preview_key, preview_path, 'IMAGE')

    logging.info("Added %d previews in %0.2fs" % (len(thicket_previews), time.time()-t0))


def get_preview(plant_name, model=""):
    """Lookup plant model preview

    Return the best match from best to worst:
        * plant and model
        * plant
        * missing_preview

    Parameters
    ----------
    plant_name : str
        The name of the plant from the db or Laubwerk plant.name
    model : str
        The name of the plant model from the db or Laubwerk model.name

    Returns
    -------
    preview
    """

    preview_key = plant_name.replace(' ', '_').replace('.', '') + "_" + model
    if preview_key not in thicket_previews:
        # The model specific preview was not found, try the plant preview
        # logging.warning("Preview key %s not found" % preview_key)
        preview_key = plant_name.replace(' ', '_').replace('.', '')
    if preview_key not in thicket_previews:
        # logging.warning("Preview key %s not found" % preview_key)
        preview_key = "missing_preview"
    return thicket_previews[preview_key]


def thicket_init():
    """Import dependencies and setup globals

    Thicket depends on the Laubwerk Python SDK. The user needs to configure the
    Laubwerk Install Path via the Thicket Addon Preferences. This function
    restricts functionality until the setup is complete.

    Check that the Laubwerk Install path is valid and import the laubwerk
    modules and the thicket components dependent on the laubwerk module.

    Setup the database and populate the preview catalog.

    Parameters
    ----------
    none

    Returns
    -------
    none
    """

    global thicket_ready, db, plants_path, sdk_path, ThicketDB, import_lbw, laubwerk

    thicket_ready = False
    db = None
    plants_path = None
    sdk_path = None

    valid_lbw_path = False
    lbw_path = bpy.context.preferences.addons[__name__].preferences.lbw_path
    if lbw_path and Path(lbw_path).is_dir():
        plants_path = Path(lbw_path) / "Plants"
        sdk_path = Path(lbw_path) / "Python"
        if plants_path.is_dir() and sdk_path.is_dir():
            valid_lbw_path = True

    if not valid_lbw_path:
        plants_path = None
        sdk_path = None
        logging.warning("Invalid Laubwerk Install Path: %s" % lbw_path)
        return

    if str(sdk_path) not in sys.path:
        sys.path.append(str(sdk_path))

    if "laubwerk" not in sys.modules:
        import laubwerk

    if "thicket_lbw" not in sys.modules:
        from .thicket_lbw import import_lbw

    if "thicket_db" not in sys.modules:
        from .thicket_db import ThicketDB

    db_path = Path(bpy.utils.user_resource('SCRIPTS', "addons", True)) / __name__ / "thicket.db"
    try:
        db = ThicketDB(db_path, locale, bpy.app.binary_path_python)
    except FileNotFoundError:
        logging.warning("Database not found, creating empty database")
        db_dir = Path(PurePath(db_path).parent)
        db_dir.mkdir(parents=True, exist_ok=True)
        db = ThicketDB(db_path, locale, bpy.app.binary_path_python, True)

    thicket_ready = True
    logging.info("Laubwerk Install Path: %s" % lbw_path)
    logging.info(laubwerk.version)
    logging.info("Database (%d plants): %s" % (db.plant_count(), db_path))
    populate_previews()
    logging.info("Ready")


def is_thicket_instance(obj):
    """Check if the object is a Thicket instance

    Thicket instances point to an instance_collection containing a
    ThicketPropGroup (thicket) with the magic property set to THICKET_GUID.

    Avoid attempting to work with Thicket object before thicket_init has been
    called successfully by requiring thicket_ready to be True.

    Parameters
    ----------
    obj : Object
        Typically bpy.context.active_object

    Returns
    -------
    Boolean
    """

    if not thicket_ready:
        return False

    if obj and obj.instance_collection and obj.instance_collection.thicket.magic == THICKET_GUID:
        return True
    return False


def delete_plant_template(template):
    """Delete a Thicket plant template with 0 users

    If there are 0 users, unlink (and optionally remove) all the objects in a
    Thicket plant collection, remove the collection, and remove any data items
    left with 0 users (saving the user a save/reload operation to clear them
    out.)

    Parameters
    ----------
    template : Collection

    Returns
    -------
    none
    """

    if len(template.users_dupli_group) == 0:
        for o in template.objects:
            template.objects.unlink(o)
            if o.users == 0:
                bpy.data.objects.remove(o)
        bpy.data.collections.remove(template, do_unlink=True)

        for d in [d for d in bpy.data.meshes if d.users == 0]:
            bpy.data.meshes.remove(d)
        for d in [d for d in bpy.data.materials if d.users == 0]:
            bpy.data.materials.remove(d)
        for d in [d for d in bpy.data.images if d.users == 0]:
            bpy.data.images.remove(d)


def delete_plant(instance):
    """Delete a Thicket plant instance

    Remove the instance and the template if this is the last user.

    Parameters
    ----------
    instance : Object (Collection Instance)

    Returns
    -------
    none
    """

    template = instance.instance_collection
    bpy.data.objects.remove(instance, do_unlink=True)
    delete_plant_template(template)


################################################################################
# Thicket Blender classes
#
# Subclasses of Blender objects, such as PropertyGroup, Operators, and Panels
################################################################################


class ThicketPropGroup(PropertyGroup):
    """Thicket plant properties

    These properties identify the Laubwerk plant by file as well as all the
    parameters used to generate the mesh. These are attached to the plant
    collection template and bpy.types.WindowManager as "thicket".

    The properties must be identical to those used in the THICKET_IO_import_lbw
    class as there does not appear to be a way to inherit from a common base
    class with these properties.
    """
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
        # Do each explicitly to get the default value from the property if it is not set.
        # Just converting to a dict directly will ignore unset # properties.
        keywords = {}
        keywords["filepath"] = self.filepath
        keywords["model"] = self.model
        keywords["qualifier"] = self.qualifier
        keywords["viewport_lod"] = self.viewport_lod
        keywords["lod_subdiv"] = self.lod_subdiv
        keywords["leaf_density"] = self.leaf_density
        keywords["leaf_amount"] = self.leaf_amount
        keywords["lod_max_level"] = self.lod_max_level
        keywords["lod_min_thick"] = self.lod_min_thick
        return keywords

    def model_callback(self, context):
        global db, thicket_ui_mode

        tp = context.window_manager.thicket
        if thicket_ui_mode == 'VIEW':
            tp = context.active_object.instance_collection.thicket
        plant = db.get_plant(tp.filepath)
        items = []

        if not plant:
            items.append(("default", "default", ""))
        else:
            for m in plant.models:
                items.append((m.name, m.label, ""))
        return items

    def qualifier_callback(self, context):
        global db

        tp = context.window_manager.thicket
        if thicket_ui_mode == 'VIEW':
            tp = context.active_object.instance_collection.thicket

        plant = db.get_plant(tp.filepath)
        items = []

        if not plant:
            items.append(("default", "default", ""))
        else:
            for q in plant.get_model(tp.model).qualifiers:
                items.append((q.name, q.label, ""))
        return items

    magic: bpy.props.StringProperty()
    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    model: EnumProperty(items=model_callback, name="Model")
    qualifier: EnumProperty(items=qualifier_callback, name="Season")
    # TODO: Use 'ALL_CAPS' Enum values
    viewport_lod: EnumProperty(name="Viewport Detail",
                               items=[("proxy", "Proxy", ""), ("low", "Partial Geometry", "")],
                               default="proxy")
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


class THICKET_OT_reset_plant(Operator):
    """Reset UI plant properties to original"""

    bl_idname = "thicket.reset_plant"
    bl_label = "Reset Plant"
    bl_description = "Restore the UI properties to the model properties"
    bl_options = {'REGISTER', 'INTERNAL'}

    next_mode: StringProperty()

    def execute(self, context):
        global thicket_ui_mode
        instance = context.active_object
        if not is_thicket_instance(instance):
            logging.error("reset_plant failed: non-Thicket object: %" % instance.name)
            return
        template = instance.instance_collection
        template.thicket.copy_to(context.window_manager.thicket)
        thicket_ui_mode = self.next_mode
        context.area.tag_redraw()
        return {'FINISHED'}


# Thicket operator to modify (delete and replace) the backing objects
class THICKET_OT_update_plant(Operator):
    """Update the plant with the new properties

    Regenerate the template plant using the UI properties and point
    all the instances to the new template, and remove the original.
    """

    bl_idname = "thicket.update_plant"
    bl_label = "Update Plant"
    bl_description = "Update plant with new properties"
    bl_options = {'REGISTER', 'INTERNAL'}

    next_mode: StringProperty()

    def execute(self, context):
        global thicket_ui_mode
        instance = context.active_object
        if not is_thicket_instance(instance):
            logging.error("update_plant failed: non-Thicket object: %" % instance.name)
            return
        instance = context.active_object
        logging.info("Update plant: %s" % instance.name)
        template = instance.instance_collection

        # Load new plant model
        keywords = context.window_manager.thicket.as_keywords(ignore=("magic", "name"))
        new_instance = import_lbw(**keywords)  # noqa: F821
        new_template = new_instance.instance_collection

        # Update the instance_collection reference in the instances
        for i in template.users_dupli_group:
            i.instance_collection = new_template
            i.name = new_template.name

        # Remove the new instance collection and the old template
        delete_plant(new_instance)
        delete_plant_template(template)

        # Restore the active object
        instance.select_set(True)
        bpy.context.view_layer.objects.active = instance

        thicket_ui_mode = self.next_mode
        context.area.tag_redraw()
        return {'FINISHED'}


# Thicket make unique operator
class THICKET_OT_make_unique(Operator):
    """Make the active plant be the only user of a new plant template

    Duplicate the plant template of the active instance and point the
    instance_collection to the new template. The active instance will now be the
    only user of a new plant template. If its properties are changed, only the
    one instance will be updated.
    """

    bl_idname = "thicket.make_unique"
    bl_label = "Make Unique"
    bl_description = "Display number of plants using this template (click to make unique)"
    bl_options = {'REGISTER', 'INTERNAL'}

    def make_unique(self, instance):
        template = instance.instance_collection
        if len(template.users_dupli_group) == 1:
            logging.info("%s already is unique" % instance.name)
            return

        # Create a copy of the template and use the new one
        new_template = template.copy()
        bpy.data.collections['Thicket'].children.link(new_template)
        instance.instance_collection = new_template

    def execute(self, context):
        instance = context.active_object
        if not is_thicket_instance(instance):
            logging.error("make_unique failed: non-Thicket object: %" % instance.name)
            return
        self.make_unique(instance)
        context.area.tag_redraw()
        return {'FINISHED'}


class THICKET_OT_delete_plant(Operator):
    """Delete the active plant instance and the template if it is the last user"""

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


class THICKET_OT_select_plant(Operator):
    """Change the plant of the active object"""

    bl_idname = "thicket.select_plant"
    bl_label = 'Select'
    bl_descroption = "Change the plant of the active object"
    bl_options = {'REGISTER', 'INTERNAL'}

    filepath: StringProperty(subtype='FILE_PATH')
    next_mode: StringProperty()

    def execute(self, context):
        global db, thicket_ui_mode

        tp = context.window_manager.thicket
        plant = db.get_plant(self.filepath)

        # Store the old values and set the model and qualifier to the 0 entry (should always exist)
        old_model = tp.model
        old_qual = tp.qualifier

        # If adding a new plant, start off with the defaults
        if self.next_mode == 'ADD':
            for key in tp.keys():
                tp.property_unset(key)

        # Change the filepath (which seems to trigger checks on the enum model and qualifier
        tp.filepath = self.filepath

        # Restore the old values if available, others reset to the defaults
        model = plant.get_model(old_model)
        tp.model = model.name
        tp.qualifier = model.get_qualifier(old_qual).name

        thicket_ui_mode = self.next_mode
        return {'FINISHED'}


class THICKET_OT_change_mode(Operator):
    """Select a new plant for the UI"""

    bl_idname = "thicket.change_mode"
    bl_label = "Change Plant"
    bl_description = "Change the Thicket Sidebar to display plant selection"
    bl_options = {'REGISTER', 'INTERNAL'}

    next_mode: StringProperty()

    def execute(self, context):
        global thicket_ui_mode
        thicket_ui_mode = self.next_mode
        context.area.tag_redraw()
        return {'FINISHED'}


class THICKET_OT_edit_plant(Operator):
    """Copy the active plant properties to the window_manager.thicket properties"""

    bl_idname = "thicket.edit_plant"
    bl_label = "Edit Plant"
    bl_description = "Edit the active plant"
    bl_options = {'REGISTER', 'INTERNAL'}

    next_mode: StringProperty()

    @classmethod
    def poll(self, context):
        return is_thicket_instance(context.active_object)

    def execute(self, context):
        global thicket_ui_mode, thicket_ui_obj
        thicket_ui_obj = context.active_object
        context.active_object.instance_collection.thicket.copy_to(context.window_manager.thicket)
        thicket_ui_mode = self.next_mode
        context.area.tag_redraw()
        return {'FINISHED'}


class THICKET_OT_load_plant(Operator):
    """Load a plant into the scene with the current properties"""

    bl_idname = "thicket.load_plant"
    bl_label = "Add"
    bl_description = "Load a plant into the scene with the current properties"""
    bl_options = {'REGISTER', 'INTERNAL'}

    next_mode: StringProperty()

    def execute(self, context):
        global thicket_ui_mode
        tp = context.window_manager.thicket
        keywords = tp.as_keywords(ignore=("magic", "name"))
        import_lbw(**keywords)  # noqa: F821
        thicket_ui_obj = context.active_object  # noqa: F841
        context.active_object.instance_collection.thicket.copy_to(context.window_manager.thicket)
        thicket_ui_mode = self.next_mode
        context.area.tag_redraw()
        return {'FINISHED'}


class THICKET_PT_plant_properties(Panel):
    """Thicket Plant Properties Panel

    Sidebar panel to display the properties of the active plant. It displays a
    delete and make unique button, followed by a thumbnail and all the
    properties from the ThicketPropGroup, along with a reset and update button
    to restore the properties to the original state or regenerate the template
    plant and updating all plants using that same template.
    """

    # bl_idname = self.type
    bl_label = "Thicket Plant Properties"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Thicket"

    def next_mode(self, op):
        global thicket_ui_mode
        # modes: ADD, EDIT, SELECT, SELECT_ADD, VIEW
        ops = ['ADD', 'CANCEL', 'CHANGE', 'CONFIRM', 'DELETE', 'EDIT', 'MAKE_UNIQUE']
        m = thicket_ui_mode
        nm = m

        if op not in ops:
            logging.error("Unknown ui mode transition operator: %s" % (op))
            return nm

        if m == 'ADD':
            if op == 'CANCEL':
                nm = 'VIEW'
            elif op == 'CHANGE':
                nm = 'SELECT_ADD'
            elif op == 'CONFIRM':
                nm = 'VIEW'
            elif op == 'DELETE':
                nm = 'VIEW'
        elif m == 'EDIT':
            if op == 'ADD':
                nm = 'SELECT_ADD'
            if op == 'CANCEL':
                nm = 'VIEW'
            elif op == 'CHANGE':
                nm = 'SELECT'
            elif op == 'CONFIRM':
                nm = 'VIEW'
            elif op == 'DELETE':
                nm = 'VIEW'
        elif m == 'SELECT':
            if op == 'CANCEL':
                nm = 'VIEW'
            elif op == 'CONFIRM':
                nm = 'EDIT'
        elif m == 'SELECT_ADD':
            if op == 'CANCEL':
                nm = 'VIEW'
            elif op == 'CONFIRM':
                nm = 'ADD'
        elif m == 'VIEW':
            if op == 'ADD':
                nm = 'SELECT_ADD'
            elif op == 'EDIT':
                nm = 'EDIT'

        return nm

    def draw_gallery(self, context, tp):
        global THICKET_SCALE
        layout = self.layout
        # TODO:
        #  - add a filter box (not sure how this will work yet)
        panel_w = context.region.width
        # cell_w = int(0.75 * scale * bpy.app.render_icon_size)
        cell_w = 175
        num_cols = max(1, panel_w / cell_w)
        o = layout.operator("thicket.change_mode", text="Cancel")
        o.next_mode = self.next_mode('CANCEL')

        grid = layout.grid_flow(columns=num_cols, even_columns=True, even_rows=False)
        for plant in db:
            cell = grid.column().box()
            cell.template_icon(icon_value=get_preview(plant.name).icon_id, scale=THICKET_SCALE)
            cell.label(text="%s" % plant.label)
            cell.label(text="(%s)" % plant.name)
            o = cell.operator("thicket.select_plant")
            o.filepath = plant.filepath
            o.next_mode = self.next_mode('CONFIRM')
        o = layout.operator("thicket.change_mode", text="Cancel")
        o.next_mode = self.next_mode('CANCEL')

    def draw_props(self, layout, plant, tp):
        """Draw the plant properties UI"""

        layout.label(text="%s" % plant.label)
        layout.label(text="(%s)" % plant.name)
        layout.prop(tp, "model")
        layout.prop(tp, "qualifier")

        layout.separator()

        layout.label(text="Level of Detail")
        r = layout.row()
        c = r.column()
        c.alignment = 'EXPAND'
        c.label(text="Viewport:")
        c = r.column()
        c.alignment = 'RIGHT'
        c.prop(tp, "viewport_lod", text="")

        layout.prop(tp, "lod_subdiv")
        layout.prop(tp, "leaf_density")
        layout.prop(tp, "leaf_amount")
        layout.prop(tp, "lod_max_level")
        layout.prop(tp, "lod_min_thick")

    def draw(self, context):
        global db, thicket_ui_mode, thicket_ui_obj, THICKET_SCALE

        template = None
        num_siblings = 0
        tp = None

        instance = context.active_object
        if instance is not thicket_ui_obj:
            thicket_ui_obj = None
            if thicket_ui_mode == 'EDIT':
                thicket_ui_mode = 'VIEW'

        if (instance and is_thicket_instance(instance)):
            thicket_ui_obj = instance
            template = instance.instance_collection
            num_siblings = len(template.users_dupli_group)

        if thicket_ui_mode == 'VIEW':
            if template:
                tp = template.thicket
        else:
            tp = context.window_manager.thicket

        if thicket_ui_mode in ['SELECT', 'SELECT_ADD']:
            self.draw_gallery(context, tp)
            return

        layout = self.layout

        # Draw Add and Delete in VIEW mode only
        if thicket_ui_mode == 'VIEW':
            o = layout.operator("thicket.change_mode", text="Add Plant")
            o.next_mode = self.next_mode('ADD')
            if template:
                layout.operator("thicket.delete_plant", icon='NONE', text="Delete")

        # If tp is not set, there is not active plant or no plant being added. Nothing else to draw.
        if tp is None:
            return

        plant = db.get_plant(tp.filepath)
        layout.template_icon(icon_value=get_preview(plant.name, tp.model).icon_id, scale=THICKET_SCALE)
        if thicket_ui_mode == 'VIEW':
            o = layout.operator("thicket.edit_plant")
            o.next_mode = self.next_mode('EDIT')
        elif thicket_ui_mode in ['ADD', 'EDIT']:
            o = layout.operator("thicket.change_mode")
            o.next_mode = self.next_mode('CHANGE')
            if thicket_ui_mode == 'EDIT':
                r = layout.row()
                r.operator("thicket.make_unique", icon='NONE', text="Make Unique (%d)" % num_siblings)
                r.enabled = num_siblings > 1

        col = layout.column()
        col.enabled = thicket_ui_mode != 'VIEW'
        self.draw_props(col, plant, tp)

        if thicket_ui_mode == 'VIEW':
            return

        layout.separator()
        r = layout.row()
        if thicket_ui_mode == 'EDIT':
            c = r.column()
            o = c.operator("thicket.reset_plant", icon="NONE", text="Cancel")
            o.next_mode = self.next_mode('CANCEL')
            c = r.column()
            o = c.operator("thicket.update_plant", icon="NONE", text="Update")
            o.next_mode = self.next_mode('CONFIRM')
            c.enabled = tp != template.thicket
        elif thicket_ui_mode == 'ADD':
            c = r.column()
            o = c.operator("thicket.change_mode", text="Cancel")
            o.next_mode = self.next_mode('CANCEL')
            c = r.column()
            o = c.operator("thicket.load_plant")
            o.next_mode = self.next_mode('CONFIRM')


class THICKET_OT_rebuild_db(Operator):
    """Rebuild the Thicket database from the installed Laubwerk Plant Kits

    Create a new database, adding all the plants found in the Laubwerk install
    path. This will take some time depending on the configuration of the
    computer. One plant parsing process is spawned for every available CPU.
    """

    bl_idname = "thicket.rebuild_db"
    bl_label = "Rebuild Database"
    bl_description = "Process Laubwerk Plants library and update the database (may take several minutes)"
    bl_options = {'REGISTER', 'INTERNAL'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        global db, plants_path, sdk_path
        logging.info("Rebuilding database, this may take several minutes...")
        t0 = time.time()
        db.build(str(plants_path), str(sdk_path))
        logging.info("Rebuilt database in %0.2fs" % (time.time()-t0))
        populate_previews()
        context.area.tag_redraw()
        return {'FINISHED'}


class THICKET_Pref(AddonPreferences):
    """Thicket Addon Preference Panel

    Configure the location of the Laubwerk Install Path and rebuild the database
    for the first time, or after installing a new Laubwerk Plant Pack.
    """

    bl_idname = __name__

    def lbw_path_on_update(self, context):
        self["lbw_path"] = str(Path(self.lbw_path).resolve())
        thicket_init()

    lbw_path: StringProperty(
        name="Install Path",
        subtype="DIR_PATH",
        description="absolute path to Laubwerk installation containing Plants and Python folders",
        default="",
        update=lbw_path_on_update
        )

    def draw(self, context):
        global db, thicket_ready

        box = self.layout.box()
        box.label(text="Laubwerk Plants Library")
        row = box.row()
        row.alert = not thicket_ready
        row.prop(self, "lbw_path")

        lbw_version = "Laubwerk Version: N/A"
        db_status = "No database found"
        if thicket_ready:
            lbw_version = laubwerk.version
            db_status = "Database contains %d plants" % db.plant_count()

        row = box.row()
        row.enabled = thicket_ready
        row.label(text=lbw_version)

        row = box.row()
        row.enabled = thicket_ready
        row.label(text=db_status)
        row.operator("thicket.rebuild_db", icon="FILE_REFRESH")


__classes__ = (
        THICKET_Pref,
        THICKET_OT_rebuild_db,
        THICKET_OT_reset_plant,
        THICKET_OT_update_plant,
        THICKET_OT_delete_plant,
        THICKET_OT_make_unique,
        THICKET_OT_change_mode,
        THICKET_OT_select_plant,
        THICKET_OT_edit_plant,
        THICKET_OT_load_plant,
        ThicketPropGroup,
        THICKET_PT_plant_properties
)


def register():
    """Thicket Add-on Blender register"""

    for c in __classes__:
        bpy.utils.register_class(c)

    bpy.types.Collection.thicket = PointerProperty(type=ThicketPropGroup)
    bpy.types.WindowManager.thicket = PointerProperty(type=ThicketPropGroup)

    thicket_init()


def unregister():
    """Thicket Add-on Blender unregister"""

    global thicket_previews

    if thicket_previews:
        bpy.utils.previews.remove(thicket_previews)
    for c in reversed(__classes__):
        bpy.utils.unregister_class(c)


if __name__ == "__main__":
    register()
