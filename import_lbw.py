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

"""
This script imports a Laubwerk plant lbw.gz files to Blender.

Usage:
Run this script from "File->Import" menu and then load the desired Laubwerk file.
Note, This loads mesh objects and materials.

"""
import time
import bpy
import laubwerk


def lbw_to_bl_obj(plant, name, mesh_lbw, model_season, proxy):
    """ Generate the Blender Object from the Laubwerk mesh and materials """

    verts_list = []
    polygon_list = []
    materials = []
    scalefac = 0.01    # TODO: Add this to the importer UI

    # write vertices
    for point in mesh_lbw.points:
        vert = (point[0] * scalefac, point[2] * scalefac, point[1] * scalefac)
        verts_list.append(vert)

    # write polygons
    for polygon in zip(mesh_lbw.polygons):
        for idx in zip(polygon):
            face = idx[0]
            polygon_list.append(face)

    # create mesh and object
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts_list, [], polygon_list)
    mesh.update(calc_edges=True)

    # Use smooth shading
    # FIXME: gotta be a non O(N) way to do this???
    for face in mesh.polygons:
        face.use_smooth = True

    # create the UV Map Layer
    mesh.uv_layers.new()
    i = 0
    for d in mesh.uv_layers[0].data:
        uv = mesh_lbw.uvs[i]
        d.uv = (uv[0] * -1, uv[1] * -1)
        i += 1
    obj = bpy.data.objects.new(name, mesh)

    # String operations are expensive, do them here outside the material loop
    wood_mat_name = plant.name + " wood"
    wood_color = plant.getWoodColor()
    foliage_mat_name = plant.name + " foliage"
    foliage_color = plant.getFoliageColor()

    # read matids and materialnames and create and add materials to the laubwerktree
    i = 0
    for matID in zip(mesh_lbw.matids):
        mat_id = matID[0]
        plantmat = plant.materials[mat_id]
        mat_name = plantmat.name
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
                mat = lbw_to_bl_mat(plant, mat_id, mat_name, model_season, proxy_color)
            obj.data.materials.append(mat)

        mat_index = obj.data.materials.find(mat_name)
        if mat_index != -1:
            obj.data.polygons[i].material_index = mat_index
        else:
            print('%s: WARN: Material %s not found' % (__name__, mat_name))

        i += 1

    return obj


def lbw_to_bl_mat(plant, mat_id, mat_name, model_season=None, proxy_color=None):
    NW = 300
    NH = 300

    plantmat = plant.materials[mat_id]
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

    mat.diffuse_color = proxy_color or plantmat.getFront().diffuseColor + (1.0,)
    node_dif.inputs[0].default_value = mat.diffuse_color
    if proxy_color:
        return mat

    # Diffuse Texture (FIXME: Assumes one sided)
    # print("Diffuse Texture: %s" % plantmat.getFront().diffuseTexture)
    img_path = plantmat.getFront().diffuseTexture
    node_img = nodes.new(type='ShaderNodeTexImage')
    node_img.location = 0, 2 * NH
    node_img.image = bpy.data.images.load(img_path)
    links.new(node_img.outputs[0], node_dif.inputs[0])

    # Alpha Texture
    # Blender render engines support using the diffuse map alpha channel. We
    # assume this rather than a separate alpha image.
    alpha_path = plantmat.alphaTexture
    # print("Alpha Texture: %s" % plantmat.alphaTexture)
    if alpha_path != '':
        # Enable leaf clipping in Eevee
        mat.blend_method = 'CLIP'
        # TODO: mat.transparent_shadow_method = 'CLIP' ?
        if alpha_path == img_path:
            links.new(node_img.outputs['Alpha'], node_dif.inputs['Alpha'])
        else:
            # TODO: This affects 'Fagus sylvatica'
            print("%s: WARN: Alpha Texture differs from diffuse image path. Not supported.", __name__)

    # Subsurface Texture
    # print("Subsurface Color: " + str(plantmat.subsurfaceColor))
    if plantmat.subsurfaceColor:
        node_dif.inputs['Subsurface Color'].default_value = plantmat.subsurfaceColor + (1.0,)

    # print("Subsurface Texture: %s" % plantmat.subsurfaceTexture)
    sub_path = plantmat.subsurfaceTexture
    if sub_path != '':
        node_sub = nodes.new(type='ShaderNodeTexImage')
        node_sub.location = 0, NH
        node_sub.image = bpy.data.images.load(sub_path)

        # Laubwerk models only support subsurface as a translucency effect,
        # indicated by a subsurfaceDepth of 0.0.
        # print("Subsurface Depth: %f" % plantmat.subsurfaceDepth)
        if plantmat.subsurfaceDepth == 0.0:
            node_sub.image.colorspace_settings.is_data = True
            links.new(node_sub.outputs['Color'], node_dif.inputs['Transmission'])
        else:
            print("%s: WARN: Subsurface Depth > 0. Not supported." % __name__)

    # Bump Texture
    # print("Bump Texture: %s" % plantmat.getFront().bumpTexture)
    bump_path = plantmat.getFront().bumpTexture
    if bump_path != '':
        node_bumpimg = nodes.new(type='ShaderNodeTexImage')
        node_bumpimg.location = 0, 0
        node_bumpimg.image = bpy.data.images.load(bump_path)
        node_bumpimg.image.colorspace_settings.is_data = True
        node_bump = nodes.new(type='ShaderNodeBump')
        node_bump.location = NW, 0
        # TODO: Make the Distance configurable to tune for each render engine
        # print("Bump Strength: %f" % plantmat.getFront().bumpStrength)
        node_bump.inputs['Strength'].default_value = plantmat.getFront().bumpStrength
        node_bump.inputs['Distance'].default_value = 0.02
        links.new(node_bumpimg.outputs['Color'], node_bump.inputs['Height'])
        links.new(node_bump.outputs['Normal'], node_dif.inputs['Normal'])

    # print("Displacement Texture: %s" % plantmat.displacementTexture)
    # print("Normal Texture: %s" % plantmat.getFront().normalTexture)
    # print("Specular Texture: %s" % plantmat.getFront().specularTexture)
    # print("--------------------")

    return mat


class LBWImportDialog(bpy.types.Operator):
    """ This will be the Laubwerk Player window for browsing and importing trees from the library."""
    bl_idname = "object.lbw_import_dialog"
    bl_label = "Laubwerk Plant Player"

    def execute(self, context):
        return {'FINISHED'}

    def draw(self, context):
        pass

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def load(self, context, filepath, leaf_density, model_id, model_season, viewport_proxy,
             lod_min_thick, lod_max_level, lod_subdiv, leaf_amount):
        """
        Called by the user interface or another script.
        """
        print('%s: Importing Laubwerk Plant from %r' % (__name__, filepath))

        time_main = time.time()
        plant = laubwerk.load(filepath)
        model = plant.models[model_id]

        # Create the viewport object (low detail)
        time_local = time.time()
        if viewport_proxy:
            mesh_lbw = model.getProxy()
        else:
            mesh_lbw = model.getMesh(qualifierName=model_season, maxBranchLevel=3, minThickness=0.6,
                                     leafAmount=leaf_amount / 100.0,
                                     leafDensity=0.3 * (leaf_density / 100.0),
                                     maxSubDivLevel=0)
        obj_viewport = lbw_to_bl_obj(plant, plant.name, mesh_lbw, model_season, viewport_proxy)
        bpy.context.collection.objects.link(obj_viewport)
        obj_viewport.hide_render = True
        obj_viewport.show_name = True
        print("\tgenerated low resolution viewport object in %.4fs" % (time.time() - time_local))

        # Create the render object (high detail)
        time_local = time.time()
        mesh_lbw = model.getMesh(qualifierName=model_season, maxBranchLevel=lod_max_level,
                                 minThickness=lod_min_thick, leafAmount=leaf_amount / 100.0,
                                 leafDensity=leaf_density / 100.0, maxSubDivLevel=lod_subdiv)
        obj_render = lbw_to_bl_obj(plant, plant.name + " (render)", mesh_lbw, model_season, False)
        bpy.context.collection.objects.link(obj_render)
        obj_render.parent = obj_viewport
        obj_render.hide_viewport = True
        obj_render.hide_select = True
        print("\tgenerated high resolution render object in %.4fs" % (time.time() - time_local))

        # set custom properties to show in properties tab
        obj_viewport["lbw_path"] = filepath
        obj_viewport["model_type"] = model.name
        obj_viewport["model_season"] = model_season
        obj_viewport["viewport_proxy"] = viewport_proxy
        obj_viewport["lod_subdiv"] = lod_subdiv
        obj_viewport["leaf_density"] = leaf_density
        obj_viewport["leaf_amount"] = leaf_amount
        obj_viewport["lod_max_level"] = lod_max_level
        obj_viewport["lod_min_thick"] = lod_min_thick

        print("\tfinished importing %s in %.4fs" % (plant.name, (time.time() - time_main)))
        return {'FINISHED'}


def register():
    bpy.utils.register_class(LBWImportDialog)


def unregister():
    bpy.utils.uregister_class(LBWImportDialog)


if __name__ == "__main__":
    register()
