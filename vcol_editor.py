import bpy, bmesh
from mathutils import *
from bpy.props import *

def linear_to_srgb_per_element(e):
    if e > 0.0031308:
        return 1.055 * (pow(e, (1.0 / 2.4))) - 0.055
    else: 
        return 12.92 * e

def linear_to_srgb(inp):

    if type(inp) == float:
        return linear_to_srgb_per_element(inp)

    elif type(inp) == Color:

        c = inp.copy()

        for i in range(3):
            c[i] = linear_to_srgb_per_element(c[i])

        return c

class YVcolFill(bpy.types.Operator):
    bl_idname = "mesh.y_vcol_fill"
    bl_label = "Vertex Color Fill"
    bl_description = "Fill selected polygon with vertex color"
    bl_options = {'REGISTER', 'UNDO'}

    color_option = EnumProperty(
            name = 'Color Option',
            description = 'Color Option',
            items = (
                ('WHITE', 'White', ''),
                ('BLACK', 'Black', ''),
                ('CUSTOM', 'Custom', ''),
                ),
            default='WHITE')

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH' and context.object.mode == 'EDIT'

    def execute(self, context):

        obj = context.object
        mesh = obj.data
        ve = context.scene.ve_edit
        bm = bmesh.from_edit_mesh(mesh)

        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        if ve.fill_mode == 'FACE':
            #face_indices = []
            loop_indices = []
            for face in bm.faces:
                if face.select:
                    #face_indices.append(face.index)
                    for loop in face.loops:
                        loop_indices.append(loop.index)

        else:
            vert_indices = []
            for vert in bm.verts:
                if vert.select:
                    vert_indices.append(vert.index)

        bpy.ops.object.mode_set(mode='OBJECT')
        vcol = obj.data.vertex_colors.active

        if self.color_option == 'WHITE':
            color = (1,1,1)
        elif self.color_option == 'BLACK':
            color = (0,0,0)
        else:
            color = linear_to_srgb(context.scene.ve_edit.color)

        if ve.fill_mode == 'FACE':
            for loop_index in loop_indices:
                vcol.data[loop_index].color = color
        else:
            for poly in mesh.polygons:
                for loop_index in poly.loop_indices:
                    loop_vert_index = mesh.loops[loop_index].vertex_index
                    if loop_vert_index in vert_indices:
                        vcol.data[loop_index].color = color

        bpy.ops.object.mode_set(mode='EDIT')

        #pal = bpy.data.palettes.get('SuperPalette')
        #if not pal:
        #    pal = bpy.data.palettes.new('SuperPalette')
        #context.scene.ve_edit.palette = pal

        return {'FINISHED'}

def vcol_editor_draw(self, context):
    obj = context.object
    mesh = obj.data
    ve = context.scene.ve_edit

    col = self.layout.column() #align=True)

    if len(mesh.vertex_colors) == 0:
        col.label(text='No vertex color found!', icon='GROUP_VCOL')
        return

    row = col.row(align=True)

    if not ve.show_vcol_list:
        row.prop(ve, 'show_vcol_list', text='', emboss=False, icon='TRIA_RIGHT')
        row.label(text='Active: ' + mesh.vertex_colors.active.name)
    else:
        row.prop(ve, 'show_vcol_list', text='', emboss=False, icon='TRIA_DOWN')
        row.label(text='Vertex Colors')

        row = col.row()
        rcol = row.column()
        rcol.template_list("MESH_UL_uvmaps_vcols", "vcols", mesh, 
                "vertex_colors", mesh.vertex_colors, "active_index", rows=1)
        rcol = row.column(align=True)
        rcol.operator("mesh.vertex_color_add", icon='ZOOMIN', text="")
        rcol.operator("mesh.vertex_color_remove", icon='ZOOMOUT', text="")


    col.separator()

    ccol = col.column(align=True)
    ccol.operator("mesh.y_vcol_fill", icon='BRUSH_DATA', text='Fill with White').color_option = 'WHITE'
    ccol.operator("mesh.y_vcol_fill", icon='BRUSH_DATA', text='Fill with Black').color_option = 'BLACK'

    col.separator()
    ccol = col.column(align=True)
    ccol.operator("mesh.y_vcol_fill", icon='BRUSH_DATA', text='Fill with Color').color_option = 'CUSTOM'
    #col.separator()
    #col.template_color_picker(ve, 'color', value_slider=True)

    ccol.prop(ve, "color", text="")

    col.separator()

    row = col.row(align=True)
    row.label(text='Mode:')
    row.prop(ve, 'fill_mode', expand=True)

    #col.template_palette(ve, "palette", color=True)

class VIEW3D_PT_y_vcol_editor_ui(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_label = "Vertex Color Editor"
    bl_context = "mesh_edit"
    bl_region_type = 'UI'
    #bl_options = {'DEFAULT_CLOSED'} 

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH'

    def draw(self, context):
        vcol_editor_draw(self, context)

class VIEW3D_PT_y_vcol_editor_tools(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_label = "Vertex Color Editor"
    bl_context = "mesh_edit"
    bl_region_type = 'TOOLS'
    bl_category = "yTexLayers"

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH'

    def draw(self, context):
        vcol_editor_draw(self, context)

class YVcolEditorProps(bpy.types.PropertyGroup):
    color = FloatVectorProperty(name='Color', size=3, subtype='COLOR', default=(1.0,1.0,1.0), min=0.0, max=1.0)
    #palette = PointerProperty(type=bpy.types.Palette)

    show_vcol_list = BoolProperty(name='Show Vertex Color List',
            description='Show vertex color list', default=False)

    fill_mode = EnumProperty(
            name = 'Fill Mode',
            description='Vertex color fill mode',
            items = (
                ('FACE', 'Face', ''),
                ('VERTEX', 'Vertex', ''),
                ),
            default='FACE')

def register():
    bpy.utils.register_class(VIEW3D_PT_y_vcol_editor_ui)
    if hasattr(bpy.utils, 'previews'): # Blender 2.7 only
        bpy.utils.register_class(VIEW3D_PT_y_vcol_editor_tools)
    bpy.utils.register_class(YVcolEditorProps)

    bpy.types.Scene.ve_edit = PointerProperty(type=YVcolEditorProps)

    bpy.utils.register_class(YVcolFill)

def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_y_vcol_editor_ui)
    if hasattr(bpy.utils, 'previews'): # Blender 2.7 only
        bpy.utils.unregister_class(VIEW3D_PT_y_vcol_editor_tools)
    bpy.utils.unregister_class(YVcolEditorProps)

    bpy.utils.unregister_class(YVcolFill)
