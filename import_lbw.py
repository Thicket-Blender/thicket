# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>

# Script copyright (C) Fabian Quosdorf
# Contributors: Fabian Quosdorf, Laubwerk, 

"""
This script imports a Laubwerk plant lbw.gz files to Blender.

Usage:
Run this script from "File->Import" menu and then load the desired Laubwerk file.
Note, This loads mesh objects and materials.

"""
import bpy, laubwerk, bmesh, os, time
from bpy.props import *

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


    def load(self, context, filepath, leaf_density, model_type, model_id, model_season, render_mode, 
            viewport_mode, lod_cull_thick, lod_min_thick, lod_cull_level, lod_max_level, lod_subdiv, leaf_amount, plant):
        """
        Called by the user interface or another script.
        """
        print('\nimporting lbw %r' % filepath)

        time_main = time.time()
        # mesh arrays
        verts_list = []  # the vertex array of the tree
        polygon_list = []  # the face array of the tree
        uv_list = [] # the uv array of the tree
        materials = [] # the material array of the tree
        scalefac = 0.01 # TODO: Add this to the importer UI

        # pick the model in the plant file.
        model = plant.models[model_id]

        # generate the actual model geometry with the settings from the importer ui
        print("viewport mode is %s" % viewport_mode)
        mesh_laubwerk = None
        if viewport_mode == "PROXY":
            mesh_laubwerk = model.getProxy(model.qualifiers[model.qualifiers.index(model_season)])
        else:
            mesh_laubwerk = model.getMesh(qualifierName = model_season, maxBranchLevel = lod_max_level, minThickness = lod_min_thick,
            leafAmount = leaf_amount / 100.0, leafDensity = leaf_density / 100.0, maxSubDivLevel = lod_subdiv)

        # write vertices
        for point in mesh_laubwerk.points:
            vert = (point[0] * scalefac, point[2] * scalefac, point[1] * scalefac)
            verts_list.append(vert)

        # write polygons
        for polygon in zip(mesh_laubwerk.polygons):
            for idx in zip(polygon):
                face = idx[0]
                polygon_list.append(face)

        #create mesh and object
        modelname = str(model.labels['en'])
        mesh = bpy.data.meshes.new("Laubwerk_" + plant.name + "_" + modelname)
        object = bpy.data.objects.new("Laubwerk_" + plant.name + "_" + modelname, mesh)

        #set custom properties to show in properties tab
        object["lbw_path"] = filepath
        object["model_type"] = model_type
        object["model_season"] = model_season
        object["render_mode"] = render_mode
        object["viewport_mode"] = viewport_mode
        object["lod_cull_thick"] = lod_cull_thick
        object["lod_min_thick"] = lod_min_thick
        object["lod_cull_level"] = lod_cull_level
        object["lod_max_level"] = lod_max_level
        object["lod_subdiv"] = lod_subdiv
        object["leaf_density"] = leaf_density
        object["leaf_amount"] = leaf_amount

        #set mesh location
        object.location = bpy.context.scene.cursor_location
        bpy.context.scene.objects.link(object)

        #create mesh from python data
        mesh.from_pydata(verts_list, [], polygon_list)
        mesh.update(calc_edges = True)
        me = object.data

        #set created tree to active object
        bpy.ops.object.select_all(action = 'DESELECT')
        bpy.context.scene.objects.active = bpy.data.objects[object.name]
        object.select = True
        #set shadingmode to smooth
        bpy.ops.object.shade_smooth()

        #create a UV Map Layer for the tree
        mesh.uv_textures.new()

        #write uvs
        for uv in mesh_laubwerk.uvs:
             uvmap = (uv[0] * -1, uv[1] * -1)
             uv_list.append(uvmap)

        # add uvs to laubwerktree
        x = 0
        for i in mesh.uv_layers[0].data:
            i.uv = uv_list[x]
            x += 1


        # read matids and materialnames and create and add materials to the laubwerktree
        i = 0
        for matID in zip(mesh_laubwerk.matids):
            plantmat = plant.materials[matID[0]]
            if matID[0] not in materials:
                materials.append(matID[0])
                checkexistingmat = bpy.data.materials.get(plantmat.name)
                if checkexistingmat is None:
                    # Add new material to current object
                    bpy.data.materials.new(plantmat.name)
                    mat = bpy.data.materials.get(plantmat.name)
                    me.materials.append(mat)
                    MatIndex = me.materials.find(plantmat.name)
                    me.polygons[i].material_index = MatIndex
                else:
                    # Add existing material to current object
                    me.materials.append(checkexistingmat)
                    MatIndex = me.materials.find(plantmat.name)
                    me.polygons[i].material_index = MatIndex
                    print('PolygonID: ' + str(me.polygons[i].material_index))
            else:
                MatIndex = me.materials.find(plantmat.name)
                if MatIndex != -1:
                    me.polygons[i].material_index = MatIndex
                    #print('PolygonID: ' + str(me.polygons[i].index))
                    #print('Materialindex: ' + str(MatIndex))
                else:
                    print('Material ' + plantmat.name + ' nicht gefunden.')
            i += 1

        time_new = time.time()

        print("finished importing: %r in %.4f sec." % (filepath, (time_new - time_main)))
        return {'FINISHED'}


def register():
    bpy.utils.register_class(LBWImportDialog)   # register dialog

def unregister():
    bpy.utils.uregister_class(LBWImportDialog)   # unregister dialog


if __name__ == "__main__":
    register()
