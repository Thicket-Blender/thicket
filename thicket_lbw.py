# Thicket calls depending on the Laubwerk SDK
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
import time
import bpy
import laubwerk

from . import THICKET_GUID

VP_MAX_BRANCH_LEVEL = 3
VP_MIN_THICKNESS = 0.3

def new_collection(name, parent, singleton=False, exclude=False):

    if singleton and name in bpy.data.collections:
        return bpy.data.collections[name]
    col = bpy.data.collections.new(name)
    parent.children.link(col)
    if exclude:
        bpy.context.view_layer.layer_collection.children[col.name].exclude = True
    return col


def lbw_to_bl_obj(lbw_plant, name, lbw_mesh, qualifier, proxy):
    """ Generate the Blender Object from the Laubwerk mesh and materials """

    verts_list = []
    polygon_list = []
    materials = []

    # write vertices
    # Laubwerk Mesh uses cm units. Blender units *appear* to be meters
    # regardless of scene units.
    for point in lbw_mesh.points:
        verts_list.append((.01*point[0], .01*point[2], .01*point[1]))

    # write polygons
    for polygon in zip(lbw_mesh.polygons):
        for idx in zip(polygon):
            face = idx[0]
            polygon_list.append(face)

    # create mesh and object
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts_list, [], polygon_list)
    mesh.update(calc_edges=True)

    # Use smooth shading
    for face in mesh.polygons:
        face.use_smooth = True

    # create the UV Map Layer
    mesh.uv_layers.new()
    i = 0
    for d in mesh.uv_layers[0].data:
        uv = lbw_mesh.uvs[i]
        d.uv = (uv[0] * -1, uv[1] * -1)
        i += 1
    obj = bpy.data.objects.new(name, mesh)

    # String operations are expensive, do them here outside the material loop
    wood_mat_name = lbw_plant.name + " wood"
    wood_color = lbw_plant.get_wood_color()
    foliage_mat_name = lbw_plant.name + " foliage"
    foliage_color = lbw_plant.get_foliage_color()

    # read matids and materialnames and create and add materials to the laubwerktree
    i = 0
    for matID in zip(lbw_mesh.matids):
        mat_id = matID[0]
        lbw_mat = lbw_plant.materials[mat_id]
        mat_name = lbw_mat.name
        proxy_color = None

        if proxy:
            if mat_id == -1:
                mat_name = foliage_mat_name
                proxy_color = foliage_color
            else:
                mat_name = wood_mat_name
                proxy_color = wood_color

        if mat_id not in materials:
            materials.append(mat_id)
            mat = bpy.data.materials.get(mat_name)
            if mat is None:
                mat = lbw_to_bl_mat(lbw_plant, mat_id, mat_name, qualifier, proxy_color)
            obj.data.materials.append(mat)

        mat_index = obj.data.materials.find(mat_name)
        if mat_index != -1:
            obj.data.polygons[i].material_index = mat_index
        else:
            logging.warning("Material not found: %s" % mat_name)

        i += 1

    return obj


def lbw_to_bl_mat(plant, mat_id, mat_name, qualifier=None, proxy_color=None):
    NW = 300
    NH = 300

    lbw_mat = plant.materials[mat_id]
    mat = bpy.data.materials.new(mat_name)

    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    # create Principled BSDF node (primary multi-layer mixer node)
    node_dif = nodes.new(type='ShaderNodeBsdfPrincipled')
    node_dif.location = 2 * NW, 2 * NH
    # create output node
    node_out = nodes.new(type='ShaderNodeOutputMaterial')
    node_out.location = 3 * NW, 2 * NH
    # link nodes
    links = mat.node_tree.links
    links.new(node_dif.outputs[0], node_out.inputs[0])

    mat.diffuse_color = proxy_color or lbw_mat.get_front().diffuse_color + (1.0,)
    node_dif.inputs[0].default_value = mat.diffuse_color
    if proxy_color:
        return mat

    # Diffuse Texture (FIXME: Assumes one sided)
    logging.debug("Diffuse Texture: %s" % lbw_mat.get_front().diffuse_texture)
    diffuse_path = lbw_mat.get_front().diffuse_texture
    node_img = nodes.new(type='ShaderNodeTexImage')
    node_img.location = 0, 2 * NH
    node_img.image = bpy.data.images.load(diffuse_path)
    links.new(node_img.outputs[0], node_dif.inputs[0])

    # Alpha Texture
    # Blender render engines support using the diffuse map alpha channel. We
    # assume this rather than a separate alpha image.
    alpha_path = lbw_mat.alpha_texture
    logging.debug("Alpha Texture: %s" % lbw_mat.alpha_texture)
    if alpha_path != "":
        # Enable leaf clipping in Eevee
        mat.blend_method = 'CLIP'
        # TODO: mat.transparent_shadow_method = 'CLIP' ?

        # All tested models either use the diffuse map for alpha or list a
        # different texture for alpha in error (wrong diffuse map as opposed a
        # separate alpha map). Ignore the difference if it exists, assume alpha
        # comes from diffuse, and issue a warning when the difference appears.
        links.new(node_img.outputs['Alpha'], node_dif.inputs['Alpha'])
        if alpha_path != diffuse_path:
            # NOTE: This affects at least 'Howea forsteriana'
            logging.warning("Alpha Texture differs from diffuse image path:")
            logging.warning("Alpha Texture: %s" % lbw_mat.alpha_texture)
            logging.warning("Diffuse Texture: %s" % lbw_mat.get_front().diffuse_texture)

    # Subsurface Texture
    if lbw_mat.subsurface_color:
        logging.debug("Subsurface Color: %s" % str(lbw_mat.subsurface_color))
        node_dif.inputs['Subsurface Color'].default_value = lbw_mat.subsurface_color + (1.0,)

    sub_path = lbw_mat.subsurface_texture
    if sub_path != "":
        logging.debug("Subsurface Texture: %s" % lbw_mat.subsurface_texture)
        node_sub = nodes.new(type='ShaderNodeTexImage')
        node_sub.location = 0, NH
        node_sub.image = bpy.data.images.load(sub_path)

        # Laubwerk models only support subsurface as a translucency effect,
        # indicated by a subsurface_depth of 0.0.
        logging.debug("Subsurface Depth: %f" % lbw_mat.subsurface_depth)
        if lbw_mat.subsurface_depth == 0.0:
            node_sub.image.colorspace_settings.is_data = True
            links.new(node_sub.outputs['Color'], node_dif.inputs['Transmission'])
        else:
            logging.warning("Subsurface Depth > 0. Not supported.")

    # Bump Texture
    bump_path = lbw_mat.get_front().bump_texture
    if bump_path != "":
        logging.debug("Bump Texture: %s" % lbw_mat.get_front().bump_texture)
        node_bumpimg = nodes.new(type='ShaderNodeTexImage')
        node_bumpimg.location = 0, 0
        node_bumpimg.image = bpy.data.images.load(bump_path)
        node_bumpimg.image.colorspace_settings.is_data = True
        node_bump = nodes.new(type='ShaderNodeBump')
        node_bump.location = NW, 0
        # TODO: Make the Distance configurable to tune for each render engine
        logging.debug("Bump Strength: %f" % lbw_mat.get_front().bump_strength)
        node_bump.inputs['Strength'].default_value = lbw_mat.get_front().bump_strength
        node_bump.inputs['Distance'].default_value = 0.02
        links.new(node_bumpimg.outputs['Color'], node_bump.inputs['Height'])
        links.new(node_bump.outputs['Normal'], node_dif.inputs['Normal'])

    if lbw_mat.displacement_texture:
        logging.debug("Displacement Texture: %s" % lbw_mat.displacement_texture)
    if lbw_mat.get_front().normal_texture:
        logging.debug("Normal Texture: %s" % lbw_mat.get_front().normal_texture)
    if lbw_mat.get_front().specular_texture:
        logging.debug("Specular Texture: %s" % lbw_mat.get_front().specular_texture)

    return mat


def import_lbw(filepath, model, viewport_lod, render_lod, mesh_args):
    time_main = time.time()
    lbw_plant = laubwerk.load(filepath)
    # TODO: This should be debug, but we cannot silence the SDK [debug] message
    # which appear without context without this appearing in the log first
    logging.info('Importing "%s"' % lbw_plant.name)
    lbw_model = next((m for m in lbw_plant.models if m.name == model), lbw_plant.default_model)
    if not lbw_model.name == model:
        logging.warning("Model '%s' not found for '%s', using default model '%s'" %
                        (model, lbw_plant.name, lbw_model.name))
    proxy = False

    # Create the viewport object (low detail)
    time_local = time.time()
    lbw_mesh = None
    if viewport_lod == 'PROXY' and not render_lod == 'PROXY':
        proxy = True
        lbw_mesh = lbw_model.get_proxy()
    elif viewport_lod == 'LOW':
        vp_mesh_args = mesh_args.copy()
        vp_mesh_args["max_branch_level"] = VP_MAX_BRANCH_LEVEL
        if "max_branch_level" in mesh_args:
            vp_mesh_args["max_branch_level"] = min(VP_MAX_BRANCH_LEVEL, mesh_args["max_branch_level"])
        vp_mesh_args["min_thickness"] = VP_MIN_THICKNESS
        if "min_thickness" in mesh_args:
            vp_mesh_args["min_thickness"] = max(VP_MIN_THICKNESS, mesh_args["min_thickness"])
        vp_mesh_args["leaf_amount"] = 0.66 * mesh_args["leaf_amount"]
        vp_mesh_args["leaf_density"] = 0.5 * mesh_args["leaf_density"]
        vp_mesh_args["max_subdiv_level"] = 0
        lbw_mesh = lbw_model.get_mesh(**vp_mesh_args)
    elif viewport_lod != 'FULL':
            logging.warning("Unknown viewport_lod: %s" % viewport_lod)

    obj_viewport = None
    if lbw_mesh:
        obj_viewport = lbw_to_bl_obj(lbw_plant, lbw_plant.name, lbw_mesh, mesh_args["qualifier"], proxy)
        obj_viewport.hide_render = True
        obj_viewport.show_name = True
        logging.debug("Generated low resolution viewport object in %.4fs" % (time.time() - time_local))

    # Create the render object (high detail)
    time_local = time.time()
    if render_lod == 'PROXY':
        lbw_mesh = lbw_model.get_proxy()
    else:
        if not render_lod == 'FULL':
            logging.warning("Unknown render_lod: %s" % render_lod)
        lbw_mesh = lbw_model.get_mesh(**mesh_args)
    obj_render = lbw_to_bl_obj(lbw_plant, lbw_plant.name + " (render)", lbw_mesh, mesh_args["qualifier"],
                               render_lod == 'PROXY')
    logging.debug("Generated high resolution render object in %.4fs" % (time.time() - time_local))

    # Setup viewport and render visibility
    if obj_viewport:
        obj_render.parent = obj_viewport
        obj_render.hide_viewport = True
        obj_render.hide_select = True
    else:
        obj_render.show_name = True

    # Setup collection hierarchy
    thicket_col = new_collection("Thicket", bpy.context.scene.collection, singleton=True, exclude=True)
    plant_col = new_collection(lbw_plant.name, thicket_col)

    # Add objects to the plant collection
    if obj_viewport:
        plant_col.objects.link(obj_viewport)
    plant_col.objects.link(obj_render)

    # Create an instance of the plant collection in the active collection
    obj_inst = bpy.data.objects.new(name=lbw_plant.name, object_data=None)
    obj_inst.instance_collection = plant_col
    obj_inst.instance_type = 'COLLECTION'
    obj_inst.show_name = True

    bpy.context.collection.objects.link(obj_inst)

    # Make the instance the active selected object
    for o in bpy.context.selected_objects:
        o.select_set(False)
    obj_inst.select_set(True)
    bpy.context.view_layer.objects.active = obj_inst

    # Set Thicket properties on the template plant collection
    tp = plant_col.thicket
    tp.magic = THICKET_GUID
    tp.name = lbw_plant.name
    tp.model = lbw_model.name
    tp.qualifier = mesh_args["qualifier"]
    tp.leaf_density = mesh_args["leaf_density"] * 100
    tp.viewport_lod = viewport_lod
    tp.render_lod = render_lod
    tp.use_lod_max_level = "max_branch_level" in mesh_args
    if tp.use_lod_max_level:
        tp.lod_max_level = mesh_args["max_branch_level"]
    tp.use_lod_min_thick = "min_thickness" in mesh_args
    if tp.use_lod_min_thick:
        tp.lod_min_thick = mesh_args["min_thickness"]
    tp.lod_subdiv = mesh_args["max_subdiv_level"]
    tp.leaf_amount = mesh_args["leaf_amount"] * 100

    logging.info('Imported "%s" in %.4fs' % (lbw_plant.name, time.time() - time_main))
    return obj_inst
