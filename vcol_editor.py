import bpy, bmesh, numpy
from mathutils import *
from bpy.props import *

def is_greater_than_280():
    if bpy.app.version >= (2, 80, 0):
        return True
    else: return False

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

class YSetActiveVcol(bpy.types.Operator):
    bl_idname = "mesh.y_set_active_vcol"
    bl_label = "Set Active Vertex Color"
    bl_description = "Set active vertex color"
    bl_options = {'REGISTER', 'UNDO'}

    vcol_name : StringProperty(default='')

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH'

    def execute(self, context):
        obj = context.object
        mesh = obj.data
        vcol = mesh.vertex_colors.get(self.vcol_name)

        if vcol:
            mesh.vertex_colors.active = vcol
            return {'FINISHED'}

        self.report({'ERROR'}, "There's no vertex color named " + self.vcol_name + '!')
        return {'CANCELLED'}

class YToggleEraser(bpy.types.Operator):
    bl_idname = "mesh.y_toggle_eraser"
    bl_label = "Toggle Eraser Brush"
    bl_description = "Toggle eraser brush"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH' and context.object.mode in {'VERTEX_PAINT', 'TEXTURE_PAINT'}

    def execute(self, context):

        if not is_greater_than_280():
            self.report({'ERROR'}, "There's no need to use this operator on this blender version!")
            return {'CANCELLED'}

        ve = context.scene.ve_edit
        mode = context.object.mode

        if mode == 'TEXTURE_PAINT':
            brush = context.tool_settings.image_paint.brush
            draw_brush = bpy.data.brushes.get('TexDraw')
        else: 
            brush = context.tool_settings.vertex_paint.brush
            draw_brush = bpy.data.brushes.get('Draw')

        if brush.blend == 'ERASE_ALPHA':
            new_brush = bpy.data.brushes.get(ve.ori_brush)
            if new_brush: 
                new_brush.blend = ve.ori_blending_mode
            else:
                new_brush = draw_brush
                new_brush.blend = 'MIX'

            ve.ori_brush = ''
            ve.ori_blending_mode = ''
        else:
            ve.ori_brush = brush.name
            ve.ori_blending_mode = brush.blend

            new_brush = draw_brush
            if new_brush: new_brush.blend = 'ERASE_ALPHA'

        if new_brush:
            if mode == 'TEXTURE_PAINT':
                context.tool_settings.image_paint.brush = new_brush
            else: context.tool_settings.vertex_paint.brush = new_brush

        return {'FINISHED'}

class YSetVColBase(bpy.types.Operator):
    bl_idname = "mesh.y_vcol_set_base"
    bl_label = "Set Vertex Color Base"
    bl_description = "Set vertex color base color on alpha with value of zero"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH' and context.object.mode == 'VERTEX_PAINT'

    def execute(self, context):

        if not is_greater_than_280():
            self.report({'ERROR'}, "There's no need to use this operator on this blender version!")
            return {'CANCELLED'}

        col = context.tool_settings.vertex_paint.brush.color

        obj = context.object
        ori_mode = obj.mode
        if ori_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        mesh = obj.data
        #mesh.calc_loop_triangles()
        vcol = obj.data.vertex_colors.active

        cols = numpy.zeros(len(mesh.loops)*4, dtype=numpy.float32)
        cols.shape = (cols.shape[0]//4, 4)

        for i, p in enumerate(mesh.polygons):
            zero_alpha = True
            for j in p.loop_indices:
                if vcol.data[j].color[3] > 0.0:
                    zero_alpha = False

            if zero_alpha:
                for j in p.loop_indices:
                    for k in range(3):
                        cols[j][k] = col[k]
                    cols[j][3] = vcol.data[j].color[3]
            else:
                for j in p.loop_indices:
                    for k in range(3):
                        cols[j][k] = vcol.data[j].color[k]
                    cols[j][3] = vcol.data[j].color[3]

        vcol.data.foreach_set('color', cols.ravel())

        if obj.mode != ori_mode:
            bpy.ops.object.mode_set(mode=ori_mode)

        return {'FINISHED'}

class YSpreadVColFix(bpy.types.Operator):
    bl_idname = "mesh.y_vcol_spread_fix"
    bl_label = "Vertex Color Spread Fix"
    bl_description = "Fix vertex color alpha transition (can be really slow depending on number of vertices)"
    bl_options = {'REGISTER', 'UNDO'}

    iteration : IntProperty(name='Spread Iteration', default = 3, min=1, max=10)

    @classmethod
    def poll(cls, context):
        #return context.object and context.object.type == 'MESH'
        return context.object and context.object.type == 'MESH' #and context.object.mode == 'EDIT'

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=200)

    def draw(self, context):
        #row = self.layout.row()
        row = self.layout.split(factor=0.35, align=True)
        row.label(text='Iteration:')
        row.prop(self, 'iteration', text='')

    def execute(self, context):

        if not is_greater_than_280():
            self.report({'ERROR'}, "There's no need to use this operator on this blender version!")
            return {'CANCELLED'}

        obj = context.object

        ori_mode = obj.mode
        if ori_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        vcol = obj.data.vertex_colors.active
        mesh = obj.data

        # To get average of loop colors on each vertices
        avg_vert_cols = numpy.zeros(len(mesh.vertices)*4, dtype=numpy.float32)
        avg_vert_cols.shape = (avg_vert_cols.shape[0]//4, 4)
        num_loops = numpy.zeros(len(mesh.vertices), dtype=numpy.int32)
        
        for i, l in enumerate(mesh.loops):
            avg_vert_cols[l.vertex_index] += vcol.data[i].color
            num_loops[l.vertex_index] += 1

        for i in range(len(mesh.vertices)):
            avg_vert_cols[i] /= num_loops[i]

        #mesh.calc_loop_triangles()

        # Get vertex neighbors

        # Create dictionary to store vertex neighbors
        vert_neighbors = {}

        for p in mesh.polygons:
            for vi in p.vertices:
                key = str(vi)
                if key not in vert_neighbors:
                    vert_neighbors[key] = []
                for vii in p.vertices:
                    if vi != vii and vii not in vert_neighbors[key]:
                        vert_neighbors[key].append(vii)

        # Create numpy to store new vertex color
        new_vert_cols = numpy.zeros(len(mesh.vertices)*4, dtype=numpy.float32)
        new_vert_cols.shape = (new_vert_cols.shape[0]//4, 4)

        for x in range(self.iteration):
            for i, v in enumerate(mesh.vertices):
                cur_col = avg_vert_cols[i]
                cur_alpha = avg_vert_cols[i][3]

                neighbors = vert_neighbors[str(i)]

                # Get sum of neighbor alphas
                sum_alpha = 0.0
                for n in neighbors:
                    sum_alpha += avg_vert_cols[n][3]

                if sum_alpha > 0.0:

                    # Get average of neighbor color based on it's alpha
                    neighbor_col = [0.0, 0.0, 0.0]
                    for n in neighbors:
                        cc = avg_vert_cols[n]
                        for j in range(3):
                            neighbor_col[j] += cc[j] * cc[3]/sum_alpha

                    # Do some kind of alpha blending
                    for j in range(3):
                        new_vert_cols[i][j] = cur_col[j] * cur_alpha + neighbor_col[j] * (1.0 - cur_alpha)

                else:
                    for j in range(3):
                        new_vert_cols[i][j] = avg_vert_cols[i][j]

                new_vert_cols[i][3] = cur_alpha

            # Set it back
            avg_vert_cols = new_vert_cols.copy()

        # To contain final color
        cols = numpy.zeros(len(vcol.data)*4, dtype=numpy.float32)
        cols.shape = (cols.shape[0]//4, 4)

        # Set new vertex color to loops
        for i, l in enumerate(mesh.loops):
            for j in range(3):
                cols[i][j] = new_vert_cols[l.vertex_index][j]
            cols[i][3] = vcol.data[i].color[3]

        vcol.data.foreach_set('color', cols.ravel())

        if obj.mode != ori_mode:
            bpy.ops.object.mode_set(mode=ori_mode)

        return {'FINISHED'}

class YVcolFill(bpy.types.Operator):
    bl_idname = "mesh.y_vcol_fill"
    bl_label = "Vertex Color Fill"
    bl_description = "Fill selected polygon with vertex color"
    bl_options = {'REGISTER', 'UNDO'}

    color_option : EnumProperty(
            name = 'Color Option',
            description = 'Color Option',
            items = (
                ('WHITE', 'White', ''),
                ('BLACK', 'Black', ''),
                #('TRANSPARENT', 'Transparent', ''),
                ('CUSTOM', 'Custom', ''),
                ),
            default='WHITE')

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH' and context.object.mode == 'EDIT'

    def execute(self, context):

        if is_greater_than_280():
            objs = context.objects_in_mode
        else: objs = [context.object]

        if context.tool_settings.mesh_select_mode[0] or context.tool_settings.mesh_select_mode[1]:
            fill_mode = 'VERTEX'
        else: fill_mode = 'FACE'

        for obj in objs:

            mesh = obj.data
            ve = context.scene.ve_edit
            bm = bmesh.from_edit_mesh(mesh)

            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()

            #if ve.fill_mode == 'FACE':
            if fill_mode == 'FACE':
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

            color = Color((
                        context.scene.ve_edit.color[0],
                        context.scene.ve_edit.color[1],
                        context.scene.ve_edit.color[2]
                        ))
            alpha = context.scene.ve_edit.color[3]

            if self.color_option == 'WHITE':
                color = (1,1,1)
                alpha = 1.0
            elif self.color_option == 'BLACK':
                color = (0,0,0)
                alpha = 1.0
            #elif self.color_option == 'TRANSPARENT':
            #    alpha = 0.0
            else:
                color = linear_to_srgb(color)

            if is_greater_than_280():
                color = (color[0], color[1], color[2], alpha)

            #if ve.fill_mode == 'FACE':
            if fill_mode == 'FACE':
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
    #if is_greater_than_280():
    #    ccol.operator("mesh.y_vcol_fill", icon='BRUSH_DATA', text='Fill with Black').color_option = 'TRANSPARENT'

    col.separator()
    ccol = col.column(align=True)
    ccol.operator("mesh.y_vcol_fill", icon='BRUSH_DATA', text='Fill with Color').color_option = 'CUSTOM'
    #col.separator()
    #col.template_color_picker(ve, 'color', value_slider=True)

    ccol.prop(ve, "color", text="")

    #col.separator()

    #row = col.row(align=True)
    #row.label(text='Mode:')
    #row.prop(ve, 'fill_mode', expand=True)

    #col.template_palette(ve, "palette", color=True)

    col.separator()
    col.operator("mesh.y_vcol_spread_fix", icon='GROUP_VCOL', text='Spread Fix')

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
    bl_category = "Ucupaint"

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH'

    def draw(self, context):
        vcol_editor_draw(self, context)

class YVcolEditorProps(bpy.types.PropertyGroup):
    color : FloatVectorProperty(name='Color', size=4, subtype='COLOR', default=(1.0,1.0,1.0,1.0), min=0.0, max=1.0)
    #palette : PointerProperty(type=bpy.types.Palette)

    show_vcol_list : BoolProperty(name='Show Vertex Color List',
            description='Show vertex color list', default=False)

    ori_blending_mode : StringProperty(default='')
    ori_brush : StringProperty(default='')

def register():
    bpy.utils.register_class(VIEW3D_PT_y_vcol_editor_ui)
    if not is_greater_than_280():
    #if hasattr(bpy.utils, 'previews'): # Blender 2.7 only
        bpy.utils.register_class(VIEW3D_PT_y_vcol_editor_tools)
    bpy.utils.register_class(YVcolEditorProps)

    bpy.types.Scene.ve_edit = PointerProperty(type=YVcolEditorProps)

    bpy.utils.register_class(YVcolFill)
    bpy.utils.register_class(YToggleEraser)
    bpy.utils.register_class(YSpreadVColFix)
    bpy.utils.register_class(YSetVColBase)
    bpy.utils.register_class(YSetActiveVcol)

def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_y_vcol_editor_ui)
    #if hasattr(bpy.utils, 'previews'): # Blender 2.7 only
    if not is_greater_than_280():
        bpy.utils.unregister_class(VIEW3D_PT_y_vcol_editor_tools)
    bpy.utils.unregister_class(YVcolEditorProps)

    bpy.utils.unregister_class(YVcolFill)
    bpy.utils.unregister_class(YToggleEraser)
    bpy.utils.unregister_class(YSpreadVColFix)
    bpy.utils.unregister_class(YSetVColBase)
    bpy.utils.unregister_class(YSetActiveVcol)
