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


# <pep8 compliant>

"""
This script imports a Laubwerk plant lbw.gz files to Blender.

Usage:
Run this script from "File->Import" menu and then load the desired Laubwerk file.
Note, This loads mesh objects and materials.

"""
import time
import bpy


def lbw_to_bl_obj(plant, model_id, is_proxy, model_season, lod_max_level, lod_min_thick,
                  leaf_amount, leaf_density, lod_subdiv):
    """ Generate the Blender Object, with mesh and materials, using the settings from the importer ui """

    verts_list = []    # the vertex array of the tree
    polygon_list = []  # the face array of the tree
    materials = []     # the material array of the tree
    scalefac = 0.01    # TODO: Add this to the importer UI

    model = plant.models[model_id]

    mesh_laubwerk = None

    if is_proxy:
        mesh_laubwerk = model.get_proxy(model_season)
    else:
        mesh_laubwerk = model.getMesh(qualifierName=model_season, maxBranchLevel=lod_max_level,
                                      minThickness=lod_min_thick, leafAmount=leaf_amount / 100.0,
                                      leafDensity=leaf_density / 100.0, maxSubDivLevel=lod_subdiv)

    # write vertices
    for point in mesh_laubwerk.points:
        vert = (point[0] * scalefac, point[2] * scalefac, point[1] * scalefac)
        verts_list.append(vert)

    # write polygons
    for polygon in zip(mesh_laubwerk.polygons):
        for idx in zip(polygon):
            face = idx[0]
            polygon_list.append(face)

    # create mesh and object
    name = "Laubwerk_" + plant.name + "_" + str(model.labels['en'])
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts_list, [], polygon_list)
    mesh.update(calc_edges=True)

    # create the UV Map Layer
    mesh.uv_layers.new()
    i = 0
    for d in mesh.uv_layers[0].data:
        uv = mesh_laubwerk.uvs[i]
        d.uv = (uv[0] * -1, uv[1] * -1)
        i += 1

    obj = bpy.data.objects.new(name, mesh)

    # read matids and materialnames and create and add materials to the laubwerktree
    i = 0
    for matID in zip(mesh_laubwerk.matids):
        mat_id = matID[0]
        plantmat = plant.materials[mat_id]
        if matID[0] not in materials:
            materials.append(mat_id)
            mat = bpy.data.materials.get(plantmat.name)
            if mat is None:
                mat = lbw_to_bl_mat(plant, mat_id, is_proxy, model_season)
            obj.data.materials.append(mat)

        mat_index = obj.data.materials.find(plantmat.name)
        if mat_index != -1:
            obj.data.polygons[i].material_index = mat_index
        else:
            print('Material %s not found' % plantmat.name)

        i += 1

    return obj


def lbw_to_bl_mat(plant, mat_id, is_proxy=False, model_season=None):
    NW = 300
    NH = 300

    plantmat = plant.materials[mat_id]
    mat = bpy.data.materials.new(plantmat.name)

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

    # dvhart: FIXME: this surely isn't correct since the UI suggests we may have both models...
    if is_proxy:
        print("PROXY ID and model season: %d %s" % (mat_id, model_season))
        if mat_id == -1:
            mat.diffuse_color = plant.getFoliageColor(model_season)
            node_dif.inputs[0].default_value = mat.diffuse_color
        else:
            mat.diffuse_color = plant.getWoodColor(model_season)
            node_dif.inputs[0].default_value = mat.diffuse_color
    else:
        mat.diffuse_color = plantmat.getFront().diffuseColor + (1.0,)

        # Diffuse Texture (FIXME: Assumes one sided)
        print("Diffuse Texture: %s" % plantmat.getFront().diffuseTexture)
        img_path = plantmat.getFront().diffuseTexture
        node_img = nodes.new(type='ShaderNodeTexImage')
        node_img.location = 0, 2 * NH
        node_img.image = bpy.data.images.load(img_path)
        node_dif.inputs[0].default_value = mat.diffuse_color
        links.new(node_img.outputs[0], node_dif.inputs[0])

        # Alpha Texture
        # Blender render engines support using the diffuse map alpha channel. We
        # assume this rather than a separate alpha image.
        alpha_path = plantmat.alphaTexture
        print("Alpha Texture: %s" % plantmat.alphaTexture)
        if alpha_path != '':
            # Enable leaf clipping in Eevee
            mat.blend_method = 'CLIP'
            # TODO: mat.transparent_shadow_method = 'CLIP' ?
            if alpha_path == img_path:
                links.new(node_img.outputs['Alpha'], node_dif.inputs['Alpha'])
            else:
                print("WARN: Alpha Texture differs from diffuse image path. Not supported.")

        # Subsurface Texture
        print("Subsurface Color: " + str(plantmat.subsurfaceColor))
        if plantmat.subsurfaceColor:
            node_dif.inputs['Subsurface Color'].default_value = plantmat.subsurfaceColor + (1.0,)

        print("Subsurface Texture: %s" % plantmat.subsurfaceTexture)
        sub_path = plantmat.subsurfaceTexture
        if sub_path != '':
            node_sub = nodes.new(type='ShaderNodeTexImage')
            node_sub.location = 0, NH
            node_sub.image = bpy.data.images.load(sub_path)

            # Laubwerk models only support subsurface as a translucency effect,
            # indicated by a subsurfaceDepth of 0.0.
            print("Subsurface Depth: %f" % plantmat.subsurfaceDepth)
            if plantmat.subsurfaceDepth == 0.0:
                node_sub.image.colorspace_settings.is_data = True
                links.new(node_sub.outputs['Color'], node_dif.inputs['Transmission'])
            else:
                print("WARN: Subsurface Depth > 0. Not supported.")

        # Bump Texture
        print("Bump Texture: %s" % plantmat.getFront().bumpTexture)
        bump_path = plantmat.getFront().bumpTexture
        if bump_path != '':
            node_bumpimg = nodes.new(type='ShaderNodeTexImage')
            node_bumpimg.location = 0, 0
            node_bumpimg.image = bpy.data.images.load(bump_path)
            node_bumpimg.image.colorspace_settings.is_data = True
            node_bump = nodes.new(type='ShaderNodeBump')
            node_bump.location = NW, 0
            # TODO: Make the Distance configurable to tune for each render engine
            print("Bump Strength: %f" % plantmat.getFront().bumpStrength)
            node_bump.inputs['Strength'].default_value = plantmat.getFront().bumpStrength
            node_bump.inputs['Distance'].default_value = 0.02
            links.new(node_bumpimg.outputs['Color'], node_bump.inputs['Height'])
            links.new(node_bump.outputs['Normal'], node_dif.inputs['Normal'])

        print("Displacement Texture: %s" % plantmat.displacementTexture)
        print("Normal Texture: %s" % plantmat.getFront().normalTexture)
        print("Specular Texture: %s" % plantmat.getFront().specularTexture)
        print("--------------------")

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

    def load(self, context, filepath, leaf_density, model_type, model_id, model_season, render_mode, viewport_mode,
             lod_cull_thick, lod_min_thick, lod_cull_level, lod_max_level, lod_subdiv, leaf_amount, plant):
        """
        Called by the user interface or another script.
        """
        print('\nimporting lbw %r' % filepath)
        print("viewport mode is %s" % viewport_mode)

        time_main = time.time()

        obj = lbw_to_bl_obj(plant, model_id, viewport_mode == "PROXY", model_season, lod_max_level, lod_min_thick,
                            leaf_amount, leaf_density, lod_subdiv)

        # set object location
        obj.location = bpy.context.scene.cursor.location
        bpy.context.scene.collection.objects.link(obj)

        # set to active object
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = bpy.data.objects[obj.name]
        if not obj.select_get():
            obj.select_set(True)

        bpy.ops.object.shade_smooth()

        # set custom properties to show in properties tab
        obj["lbw_path"] = filepath
        obj["model_type"] = model_type
        obj["model_season"] = model_season
        obj["render_mode"] = render_mode
        obj["viewport_mode"] = viewport_mode
        obj["lod_cull_thick"] = lod_cull_thick
        obj["lod_min_thick"] = lod_min_thick
        obj["lod_cull_level"] = lod_cull_level
        obj["lod_max_level"] = lod_max_level
        obj["lod_subdiv"] = lod_subdiv
        obj["leaf_density"] = leaf_density
        obj["leaf_amount"] = leaf_amount

        print("finished importing: %r in %.4f sec." % (filepath, (time.time() - time_main)))
        return {'FINISHED'}


def register():
    bpy.utils.register_class(LBWImportDialog)   # register dialog


def unregister():
    bpy.utils.uregister_class(LBWImportDialog)  # unregister dialog


if __name__ == "__main__":
    register()
