import bpy, bmesh, numpy
from mathutils import *
from bpy.props import *

def is_greater_than_280():
    if bpy.app.version >= (2, 80, 0):
        return True
    else: return False

def is_greater_than_320():
    if bpy.app.version >= (3, 2, 0):
        return True
    else: return False

def srgb_to_linear_per_element(e):
    if e <= 0.03928:
        return e/12.92
    else: 
        return pow((e + 0.055) / 1.055, 2.4)

def linear_to_srgb_per_element(e):
    if e > 0.0031308:
        return 1.055 * (pow(e, (1.0 / 2.4))) - 0.055
    else: 
        return 12.92 * e

def srgb_to_linear(inp):

    if type(inp) == float:
        return srgb_to_linear_per_element(inp)

    elif type(inp) == Color:

        c = inp.copy()

        for i in range(3):
            c[i] = srgb_to_linear_per_element(c[i])

        return c

def linear_to_srgb(inp):

    if type(inp) == float:
        return linear_to_srgb_per_element(inp)

    elif type(inp) == Color:

        c = inp.copy()

        for i in range(3):
            c[i] = linear_to_srgb_per_element(c[i])

        return c

def get_vertex_colors(obj):
    if not obj or obj.type != 'MESH': return []

    if not is_greater_than_320():
        return obj.data.vertex_colors

    return obj.data.color_attributes

def get_active_vertex_color(obj):
    if not obj or obj.type != 'MESH': return None

    if not is_greater_than_320():
        return obj.data.vertex_colors.active

    return obj.data.color_attributes.active_color

def set_active_vertex_color(obj, vcol):
    try:
        if is_greater_than_320():
            obj.data.color_attributes.active_color = vcol
        else: obj.data.vertex_colors.active = vcol
    except Exception as e: print(e)

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
        vcols = get_vertex_colors(obj)
        vcol = vcols.get(self.vcol_name)

        if vcol:
            set_active_vertex_color(obj, vcol)
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

        ve = context.scene.ve_edit
        mode = context.object.mode

        if mode == 'TEXTURE_PAINT':
            brush = context.tool_settings.image_paint.brush
            draw_brush = bpy.data.brushes.get('TexDraw')
        elif mode == 'VERTEX_PAINT' and is_greater_than_280(): 
            brush = context.tool_settings.vertex_paint.brush
            draw_brush = bpy.data.brushes.get('Draw')
        else:
            self.report({'ERROR'}, "There's no need to use this operator on this blender version!")
            return {'CANCELLED'}

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
        vcol = get_active_vertex_color(obj)

        if is_greater_than_320() and vcol.domain != 'CORNER':
            self.report({'ERROR'}, "Non corner domain for this operator is not implemented yet!")
            bpy.ops.object.mode_set(mode=ori_mode)
            return {'CANCELLED'}

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
        return context.object and context.object.type == 'MESH' and any(get_vertex_colors(context.object))

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

        vcol = get_active_vertex_color(obj)
        mesh = obj.data

        if is_greater_than_320() and vcol.domain != 'CORNER':
            self.report({'ERROR'}, "Non corner domain for this operator is not implemented yet!")
            bpy.ops.object.mode_set(mode=ori_mode)
            return {'CANCELLED'}

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

class YVcolFillFaceCustom(bpy.types.Operator):
    bl_idname = "mesh.y_vcol_fill_face_custom"
    bl_label = "Vertex Color Fill Face with Custom Color"
    bl_description = "Fill selected polygon with vertex color with custom color"
    bl_options = {'REGISTER', 'UNDO'}

    color : FloatVectorProperty(
            name='Color ID', size=4,
            subtype='COLOR',
            default=(1.0, 0.0, 1.0, 1.0),
            min=0.0, max=1.0,
            )

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not obj or obj.type != 'MESH' or not any(get_vertex_colors(obj)): return False

        if is_greater_than_320():
            vcol = obj.data.color_attributes.active_color
            if not vcol or vcol.domain != 'CORNER':
                return False

        return obj.mode == 'EDIT'

    def execute(self, context):
        if is_greater_than_280():
            objs = context.objects_in_mode
        else: objs = [context.object]

        for obj in objs:

            mesh = obj.data
            bm = bmesh.from_edit_mesh(mesh)

            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()

            loop_indices = []
            for face in bm.faces:
                if face.select:
                    for loop in face.loops:
                        loop_indices.append(loop.index)

            bpy.ops.object.mode_set(mode='OBJECT')
            vcol = get_active_vertex_color(obj)

            color = Color((self.color[0], self.color[1], self.color[2]))
            color = linear_to_srgb(color)

            if is_greater_than_280():
                color = (color[0], color[1], color[2], self.color[3])

            for i, loop_index in enumerate(loop_indices):
                vcol.data[loop_index].color = color

                # HACK: Sometimes color assigned are different so read the assigned color and write it back to mask color id
                if i == 0 and any([color[i] for i in range(3) if color[i] != vcol.data[loop_index].color[i]]) and hasattr(context, 'mask'):
                    #print(color[0], vcol.data[loop_index].color[0])
                    written_col = vcol.data[loop_index].color
                    color = (written_col[0], written_col[1], written_col[2])

                    # Set color back to mask color id
                    context.mask.color_id = srgb_to_linear(Color(color))

                    if is_greater_than_280():
                        color = (written_col[0], written_col[1], written_col[2], written_col[3])

            bpy.ops.object.mode_set(mode='EDIT')

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
        obj = context.object
        if not obj or obj.type != 'MESH' or not any(get_vertex_colors(obj)): return False

        if is_greater_than_320():
            vcol = obj.data.color_attributes.active_color
            if not vcol or vcol.domain not in {'CORNER', 'POINT'}:
                return False

        return obj.mode == 'EDIT'

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

            #if fill_mode == 'FACE':
            #face_indices = []
            loop_indices = []
            for face in bm.faces:
                if face.select:
                    #face_indices.append(face.index)
                    for loop in face.loops:
                        loop_indices.append(loop.index)

            #else:
            vert_indices = []
            for vert in bm.verts:
                if vert.select:
                    vert_indices.append(vert.index)

            bpy.ops.object.mode_set(mode='OBJECT')
            vcol = get_active_vertex_color(obj)

            color = Color((ve.color[0], ve.color[1], ve.color[2]))
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

            if is_greater_than_320() and vcol.domain == 'POINT':
                for vert_index in vert_indices:
                    vcol.data[vert_index].color = color
            else:
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
    vcols = get_vertex_colors(obj)
    vcol = get_active_vertex_color(obj)

    #if len(vcols) == 0:
    #    col.label(text='No vertex color found!', icon='GROUP_VCOL')
    #    return

    row = col.row(align=True)

    if not ve.show_vcol_list:
        row.prop(ve, 'show_vcol_list', text='', emboss=False, icon='TRIA_RIGHT')
        if vcol: row.label(text='Active: ' + vcol.name)
        else: row.label(text='Active: -')
    else:
        row.prop(ve, 'show_vcol_list', text='', emboss=False, icon='TRIA_DOWN')
        row.label(text='Vertex Colors')

        row = col.row()
        rcol = row.column()
        if is_greater_than_320():
            rcol.template_list("MESH_UL_color_attributes", "vcols", mesh, 
                    "color_attributes", vcols, "active_color_index", rows=2)
            rcol = row.column(align=True)
            rcol.operator("geometry.color_attribute_add", icon='ADD', text="")
            rcol.operator("geometry.color_attribute_remove", icon='REMOVE', text="")
        else:
            if is_greater_than_280():
                rcol.template_list("MESH_UL_vcols", "vcols", mesh, 
                        "vertex_colors", vcols, "active_index", rows=3)
                rcol = row.column(align=True)
                rcol.operator("mesh.vertex_color_add", icon='ADD', text="")
                rcol.operator("mesh.vertex_color_remove", icon='REMOVE', text="")
            else:
                rcol.template_list("MESH_UL_uvmaps_vcols", "vcols", mesh, 
                        "vertex_colors", vcols, "active_index", rows=3)
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

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH'

    def draw(self, context):
        vcol_editor_draw(self, context)

class YVcolEditorProps(bpy.types.PropertyGroup):
    color : FloatVectorProperty(name='Color', size=4, subtype='COLOR', default=(1.0,1.0,1.0,1.0), min=0.0, max=1.0)
    #palette : PointerProperty(type=bpy.types.Palette)

    show_vcol_list : BoolProperty(name='Show Vertex Color List',
            description='Show vertex color list', default=True)

    ori_blending_mode : StringProperty(default='')
    ori_brush : StringProperty(default='')

def register():
    bpy.utils.register_class(VIEW3D_PT_y_vcol_editor_ui)
    if not is_greater_than_280():
        bpy.utils.register_class(VIEW3D_PT_y_vcol_editor_tools)
    bpy.utils.register_class(YVcolEditorProps)

    bpy.types.Scene.ve_edit = PointerProperty(type=YVcolEditorProps)

    bpy.utils.register_class(YVcolFill)
    bpy.utils.register_class(YVcolFillFaceCustom)
    bpy.utils.register_class(YToggleEraser)
    bpy.utils.register_class(YSpreadVColFix)
    bpy.utils.register_class(YSetVColBase)
    bpy.utils.register_class(YSetActiveVcol)

def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_y_vcol_editor_ui)
    if not is_greater_than_280():
        bpy.utils.unregister_class(VIEW3D_PT_y_vcol_editor_tools)
    bpy.utils.unregister_class(YVcolEditorProps)

    bpy.utils.unregister_class(YVcolFill)
    bpy.utils.unregister_class(YVcolFillFaceCustom)
    bpy.utils.unregister_class(YToggleEraser)
    bpy.utils.unregister_class(YSpreadVColFix)
    bpy.utils.unregister_class(YSetVColBase)
    bpy.utils.unregister_class(YSetActiveVcol)
