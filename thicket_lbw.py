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


from math import radians
import time
import bpy
import laubwerk
from mathutils import Matrix

from . import logger

VP_MAX_BRANCH_LEVEL = 4
VP_MIN_THICKNESS = 0.1
# Node graph units
NW = 300
NH = 300


def new_collection(name, parent, singleton=False, exclude=False):
    if singleton and name in bpy.data.collections:
        return bpy.data.collections[name]
    col = bpy.data.collections.new(name)
    parent.children.link(col)
    if exclude:
        bpy.context.view_layer.layer_collection.children[col.name].exclude = True
    return col


def lbw_to_bl_obj(lbw_plant, suffix, lbw_mesh, qualifier, proxy):
    """ Generate the Blender Object from the Laubwerk mesh and materials """

    # construct object name
    name = lbw_plant.name
    if suffix:
        name += suffix

    # create mesh and object
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(lbw_mesh.points, [], lbw_mesh.polygons)
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
    # Rotate 90 degrees around X axis so Z is pointing up
    # Scale Laubwerk centimeters units to Blender meters units
    obj.data.transform(Matrix.Rotation(radians(90), 4, 'X') @ Matrix.Scale(.01, 4))

    # String operations are expensive, do them here outside the material loop
    wood_mat_name = lbw_plant.name + " wood"
    # FIXME: fetch proper preview colors somehow
    wood_color = (0.08423289656639099, 0.13307799398899078, 0.023182500153779984)
    foliage_mat_name = lbw_plant.name + " foliage"
    foliage_color = (0.08423289656639099, 0.13307799398899078, 0.023182500153779984)

    use_1033 = False
    lbw_version = laubwerk.version_info
    if lbw_version[0] <= 1:
        if lbw_version[1] == 0:
            if lbw_version[2] <= 33:
                use_1033 = True

    # read matids and materialnames and create and add materials to the laubwerktree
    materials = []
    i = 0
    for matID in zip(lbw_mesh.mat_idxs):
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
                if use_1033:
                    mat = lbw_to_bl_mat_1033(lbw_plant, mat_id, mat_name, qualifier, proxy_color)
                else:
                    mat = lbw_to_bl_mat(lbw_plant, mat_id, mat_name, qualifier, proxy_color)
            obj.data.materials.append(mat)

        mat_index = obj.data.materials.find(mat_name)
        if mat_index != -1:
            obj.data.polygons[i].material_index = mat_index
        else:
            logger.warning("Material not found: %s" % mat_name)

        i += 1

    return obj


def lbw_to_bl_mat_1033(plant, mat_id, mat_name, qualifier=None, proxy_color=None):
    logger.warning("Laubwerk 1.0.33 support is deprecated and will be removed "
                   "in future releases. Please upgrade to 1.0.34 or newer.")

    global NW, NH

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

    # Diffuse Texture
    logger.debug("Diffuse Texture: %s" % lbw_mat.get_front().diffuse_texture)
    diffuse_path = lbw_mat.get_front().diffuse_texture
    node_img = nodes.new(type='ShaderNodeTexImage')
    node_img.location = 0, 2 * NH
    node_img.image = bpy.data.images.load(diffuse_path)
    links.new(node_img.outputs[0], node_dif.inputs[0])

    # Handle Two-Sided Textures (diffuse texture only)
    if lbw_mat.is_two_sided() and lbw_mat.sides_are_different():
        logger.debug("Diffuse texture is two sided")
        diffuse_back_path = lbw_mat.get_back().diffuse_texture
        node_back_img = nodes.new(type='ShaderNodeTexImage')
        node_back_img.location = -NW, 2 * NH
        node_back_img.image = bpy.data.images.load(diffuse_back_path)
        node_mix = nodes.new(type='ShaderNodeMixRGB')
        node_mix.location = NW, 2 * NH
        node_geometry = nodes.new(type='ShaderNodeNewGeometry')
        node_geometry.location = -NW, NH
        links.new(node_geometry.outputs[6], node_mix.inputs[0])
        links.new(node_img.outputs[0], node_mix.inputs[1])
        links.new(node_back_img.outputs[0], node_mix.inputs[2])
        links.new(node_mix.outputs[0], node_dif.inputs[0])

    # Alpha Texture
    # Blender render engines support using the diffuse map alpha channel. We
    # assume this rather than a separate alpha image.
    alpha_path = lbw_mat.alpha_texture
    logger.debug("Alpha Texture: %s" % lbw_mat.alpha_texture)
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
            logger.warning("Alpha Texture differs from diffuse image path:")
            logger.warning("Alpha Texture: %s" % lbw_mat.alpha_texture)
            logger.warning("Diffuse Texture: %s" % lbw_mat.get_front().diffuse_texture)

    # Subsurface Texture
    sub_path = lbw_mat.subsurface_texture
    if sub_path != "":
        logger.debug("Subsurface Texture: %s" % lbw_mat.subsurface_texture)
        node_sub = nodes.new(type='ShaderNodeTexImage')
        node_sub.location = 0, NH
        node_sub.image = bpy.data.images.load(sub_path)

        # Laubwerk models only support subsurface as a translucency effect for
        # thin-shell material, indicated by having two sides:
        if lbw_mat.is_two_sided():
            node_sub.image.colorspace_settings.is_data = True
            links.new(node_sub.outputs['Color'], node_dif.inputs['Transmission'])
        else:
            logger.warning("Subsurface Depth > 0. Not supported.")

    # Index of Refraction (IOR)
    # All Laubwerk Materials default to 1.33 across host applications
    node_dif.inputs['IOR'].default_value = 1.33

    # Bump Texture
    bump_path = lbw_mat.get_front().bump_texture
    if bump_path != "":
        logger.debug("Bump Texture: %s" % lbw_mat.get_front().bump_texture)
        node_bumpimg = nodes.new(type='ShaderNodeTexImage')
        node_bumpimg.location = 0, 0
        node_bumpimg.image = bpy.data.images.load(bump_path)
        node_bumpimg.image.colorspace_settings.is_data = True
        node_bump = nodes.new(type='ShaderNodeBump')
        node_bump.location = NW, 0
        # TODO: Make the Distance configurable to tune for each render engine
        logger.debug("Bump Strength: %f" % lbw_mat.get_front().bump_strength)
        node_bump.inputs['Strength'].default_value = lbw_mat.get_front().bump_strength
        node_bump.inputs['Distance'].default_value = 0.02
        links.new(node_bumpimg.outputs['Color'], node_bump.inputs['Height'])
        links.new(node_bump.outputs['Normal'], node_dif.inputs['Normal'])

    if lbw_mat.displacement_texture:
        logger.debug("Displacement Texture: %s" % lbw_mat.displacement_texture)
    if lbw_mat.get_front().normal_texture:
        logger.debug("Normal Texture: %s" % lbw_mat.get_front().normal_texture)
    if lbw_mat.get_front().specular_texture:
        logger.debug("Specular Texture: %s" % lbw_mat.get_front().specular_texture)

    return mat


def lbw_side_to_bsdf(mat, side, x=0, y=0):
    global NW, NH

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    node_bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    node_bsdf.location = x + (2 * NW), y + NH
    # All Laubwerk Materials default to Index of Refraction of 1.33
    node_bsdf.inputs['IOR'].default_value = 1.33

    # Diffuse Texture
    logger.debug("Diffuse Texture: %s" % side.base_color_texture)
    base_path = side.base_color_texture
    node_img = nodes.new(type='ShaderNodeTexImage')
    node_img.location = x, y + NH
    node_img.image = bpy.data.images.load(base_path)
    links.new(node_img.outputs[0], node_bsdf.inputs[0])

    # Bump Texture
    bump_path = side.bump_texture
    if bump_path != "":
        logger.debug("Bump Texture: %s" % side.bump_texture)
        node_bumpimg = nodes.new(type='ShaderNodeTexImage')
        node_bumpimg.location = x, y
        node_bumpimg.image = bpy.data.images.load(bump_path)
        node_bumpimg.image.colorspace_settings.is_data = True

        node_bump = nodes.new(type='ShaderNodeBump')
        node_bump.location = x + NW, y
        # TODO: Make the Distance configurable to tune for each render engine
        logger.debug("Bump Strength: %f" % side.bump_strength)
        node_bump.inputs['Strength'].default_value = side.bump_strength
        node_bump.inputs['Distance'].default_value = 0.02
        links.new(node_bumpimg.outputs['Color'], node_bump.inputs['Height'])
        links.new(node_bump.outputs['Normal'], node_bsdf.inputs['Normal'])

    # TODO: Unused properties
    #   base_color (front base_color used for material base_color)
    #   specular_color
    #   specular_color_texture
    #   specular_roughness
    #   specular_roughness_texture
    #   sheen
    #   sheen_texture
    #   sheen_color
    #   sheen_color_texture
    #   sheen_roughness
    #   sheen_roughness_texture

    return node_bsdf


def lbw_to_bl_mat(plant, mat_id, mat_name, qualifier=None, proxy_color=None):
    global NW, NH

    lbw_mat = plant.materials[mat_id]
    mat = bpy.data.materials.new(mat_name)

    if proxy_color:
        mat.diffuse_color = proxy_color
        return mat

    mat.diffuse_color = lbw_mat.get_front().base_color + (1.0,)
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    nodes.clear()
    links = mat.node_tree.links
    x, y = (0, 0)

    # Construct the Principled BSDF Shader per Laubwerk Material Side object
    # We construct the back first to help clean the node graph cleaner
    node_back_bsdf = None
    if lbw_mat.is_two_sided() and lbw_mat.sides_are_different():
        logger.debug("Diffuse texture is two sided")
        node_back_bsdf = lbw_side_to_bsdf(mat, lbw_mat.get_back(), x, y)
        x, y = node_back_bsdf.location
        y += NH

    node_front_bsdf = lbw_side_to_bsdf(mat, lbw_mat.get_front(), 0, y)
    x, y = node_front_bsdf.location
    y += NH
    stage_out = node_front_bsdf.outputs[0]

    if node_back_bsdf:
        node_geometry = nodes.new(type='ShaderNodeNewGeometry')
        node_geometry.location = x, y

        node_mix = nodes.new(type='ShaderNodeMixShader')
        node_mix.location = x + NW, NH

        links.new(node_geometry.outputs[6], node_mix.inputs[0])
        links.new(node_front_bsdf.outputs[0], node_mix.inputs[1])
        links.new(node_back_bsdf.outputs[0], node_mix.inputs[2])
        stage_out = node_mix.outputs[0]

    # Subsurface / Translucence
    # Laubwerk models only support subsurface as a translucency effect for
    # thin-shell material, indicated by having two sides.
    sub_path = lbw_mat.subsurface_texture
    if sub_path != "" and lbw_mat.is_two_sided():
        x += NW
        logger.debug("Subsurface Texture: %s" % lbw_mat.subsurface_texture)
        # Unused properties (specific to a solid vs a thin-shell):
        #   subsurface
        #   subsurface_radius
        #   subsurface_radius_texture
        #   subsurface_radius_scale
        node_tr = nodes.new(type='ShaderNodeBsdfTranslucent')
        node_tr.location = x, 0
        node_tr.inputs['Color'].default_value = lbw_mat.subsurface_color + (1.0,)

        node_sub = nodes.new(type='ShaderNodeTexImage')
        node_sub.location = x, 2 * NH
        node_sub.image = bpy.data.images.load(sub_path)
        node_sub.image.colorspace_settings.is_data = True

        node_mix = nodes.new(type='ShaderNodeMixShader')
        node_mix.location = x + NW, 0

        links.new(node_sub.outputs[0], node_mix.inputs[0])
        links.new(stage_out, node_mix.inputs[1])
        links.new(node_tr.outputs[0], node_mix.inputs[2])
        stage_out = node_mix.outputs[0]

    # Alpha Texture
    alpha_path = lbw_mat.opacity_texture
    logger.debug("Alpha Texture: %s" % lbw_mat.opacity_texture)
    if alpha_path != "":
        x += NW
        # Enable leaf clipping in Eevee
        mat.blend_method = 'CLIP'
        # TODO: mat.transparent_shadow_method = 'CLIP' ?

        node_tr = nodes.new(type='ShaderNodeBsdfTransparent')
        node_tr.location = x, NH

        node_alpha = nodes.new(type='ShaderNodeTexImage')
        node_alpha.location = x, 2 * NH
        node_alpha.image = bpy.data.images.load(alpha_path)

        node_mix = nodes.new(type='ShaderNodeMixShader')
        node_mix.location = x + NW, NH

        links.new(node_alpha.outputs['Alpha'], node_mix.inputs[0])
        links.new(node_tr.outputs[0], node_mix.inputs[1])
        links.new(stage_out, node_mix.inputs[2])
        stage_out = node_mix.outputs[0]

    # Create Material Output and additional inputs
    x += NW
    # Displacement
    node_disp = None
    disp_path = lbw_mat.displacement_texture
    if disp_path != "":
        logger.debug("Displacement Texture: %s" % lbw_mat.displacement_texture)
        node_dispimg = nodes.new(type='ShaderNodeTexImage')
        node_dispimg.location = x, 0
        node_dispimg.image = bpy.data.images.load(disp_path)
        node_dispimg.image.colorspace_settings.is_data = True
        x += NW

        node_disp = nodes.new(type='ShaderNodeDisplacement')
        node_disp.location = x, 0

        links.new(node_dispimg.outputs[0], node_disp.inputs[0])
        node_disp.inputs[1].default_value = int(lbw_mat.displacement_centered)
        node_disp.inputs[2].default_value = lbw_mat.displacement_height

    # Create the final output node
    x += NW
    node_out = nodes.new(type='ShaderNodeOutputMaterial')
    node_out.location = x, NH
    if node_disp:
        links.new(node_disp.outputs[0], node_out.inputs[2])
    links.new(stage_out, node_out.inputs[0])

    return mat


def import_lbw(filepath, model, viewport_lod, render_lod, mesh_args, obj_viewport=None, obj_render=None):
    time_main = time.time()
    lbw_plant = laubwerk.load(filepath)
    # TODO: This should be debug, but we cannot silence the SDK [debug] message
    # which appear without context without this appearing in the log first
    logger.info('Importing "%s"' % lbw_plant.name)
    lbw_model = next((m for m in lbw_plant.models if m.name == model), lbw_plant.default_model)
    if not lbw_model.name == model:
        logger.warning("Model '%s' not found for '%s', using default model '%s'" %
                       (model, lbw_plant.name, lbw_model.name))

    # Create the viewport object (low detail)
    time_local = time.time()
    if viewport_lod != render_lod:
        if obj_viewport:
            obj_viewport.name = lbw_plant.name
            obj_viewport.data.name = lbw_plant.name
            logger.debug("Reusing existing viewport object")
        elif viewport_lod == 'PROXY':
            lbw_mesh = lbw_model.get_proxy()
            obj_viewport = lbw_to_bl_obj(lbw_plant, None, lbw_mesh, mesh_args["qualifier"], True)
            logger.debug("Generated proxy viewport object in %.4fs" % (time.time() - time_local))
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
            logger.debug("viewport get_mesh(%s)" % str(vp_mesh_args))
            lbw_mesh = lbw_model.get_mesh(**vp_mesh_args)
            obj_viewport = lbw_to_bl_obj(lbw_plant, None, lbw_mesh, mesh_args["qualifier"], False)
            logger.debug("Generated low resolution viewport object in %.4fs" % (time.time() - time_local))
        else:
            logger.warning("Unknown viewport_lod: %s" % viewport_lod)

    # Create the render object (high detail)
    time_local = time.time()
    if obj_render:
        obj_render.name = lbw_plant.name + " (render)"
        obj_render.data.name = lbw_plant.name + " (render)"
        logger.debug("Reusing existing render object")
    elif render_lod == 'PROXY':
        lbw_mesh = lbw_model.get_proxy()
        obj_render = lbw_to_bl_obj(lbw_plant, " (render)", lbw_mesh, mesh_args["qualifier"], True)
        logger.debug("Generated proxy render object in %.4fs" % (time.time() - time_local))
    elif render_lod == 'FULL':
        logger.debug("render get_mesh(%s)" % str(mesh_args))
        lbw_mesh = lbw_model.get_mesh(**mesh_args)
        obj_render = lbw_to_bl_obj(lbw_plant, " (render)", lbw_mesh, mesh_args["qualifier"], False)
        logger.debug("Generated high resolution render object in %.4fs" % (time.time() - time_local))
    else:
        logger.warning("Unknown render_lod: %s" % render_lod)

    # Setup viewport and render visibility
    if obj_viewport:
        obj_viewport.parent = None
        obj_viewport.hide_render = True
        obj_viewport.show_name = True
        obj_render.show_name = False
        obj_render.parent = obj_viewport
        obj_render.hide_viewport = True
        obj_render.hide_select = True
    else:
        obj_render.show_name = True
        obj_render.parent = None
        obj_render.hide_render = False
        obj_render.hide_viewport = False
        obj_render.hide_select = False

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

    logger.info('Imported "%s" in %.4fs' % (lbw_plant.name, time.time() - time_main))
    return obj_inst
