# Thicket Blender utility functions (no dependency on the laubwerk module)
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

import bpy
import logging

THICKET_GUID = '5ff1c66f282a45a488a6faa3070152a2'


def is_thicket_instance(obj):
    if obj and obj.instance_collection and obj.instance_collection.thicket.magic == THICKET_GUID:
        return True
    return False


def delete_plant_template(template):
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
    template = instance.instance_collection
    bpy.data.objects.remove(instance, do_unlink=True)
    delete_plant_template(template)


def make_unique(instance):
    logging.info("make_unique")
    template = instance.instance_collection
    if len(template.users_dupli_group) == 1:
        logging.info("%s already is unique" % instance.name)
        return

    # Create a copy of the template and use the new one
    new_template = template.copy()
    bpy.data.collections['Thicket'].children.link(new_template)
    instance.instance_collection = new_template
