import bpy, bmesh, numpy, time, time
from mathutils import *
from bpy.props import *
from .common import *

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
    bl_idname = "paint.y_toggle_eraser"
    bl_label = "Toggle Eraser Brush"
    bl_description = "Toggle eraser brush"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH' and context.object.mode in {'VERTEX_PAINT', 'TEXTURE_PAINT', 'SCULPT'}

    def execute(self, context):

        ve = context.scene.ve_edit
        mode = context.object.mode

        if mode == 'TEXTURE_PAINT':
            brush = context.tool_settings.image_paint.brush
            draw_brush = bpy.data.brushes.get('TexDraw')
        elif mode == 'VERTEX_PAINT' and is_bl_newer_than(2, 80): 
            brush = context.tool_settings.vertex_paint.brush
            draw_brush = bpy.data.brushes.get('Draw')
        elif mode == 'SCULPT' and is_bl_newer_than(3, 2): 
            brush = context.tool_settings.sculpt.brush
            draw_brush = bpy.data.brushes.get('Paint')
            if not draw_brush:
                draw_brushes = [d for d in bpy.data.brushes if d.use_paint_sculpt and d.sculpt_tool == 'PAINT']
                if draw_brushes: draw_brush = draw_brushes[0]
                else:
                    self.report({'ERROR'}, "Cannot find a paint brush!")
                    return {'CANCELLED'}
        else:
            self.report({'ERROR'}, "There's no need to use this operator on this blender version!")
            return {'CANCELLED'}

        # Get eraser brush
        eraser_name = eraser_names[mode]
        eraser_brush = bpy.data.brushes.get(eraser_name)

        if not eraser_brush:
            if mode == 'SCULPT':
                eraser_brush = draw_brush.copy()
                eraser_brush.name = eraser_name
            else:
                eraser_brush = bpy.data.brushes.new(eraser_name, mode=mode)
            eraser_brush.blend = 'ERASE_ALPHA'

        if brush == eraser_brush:

            if mode == 'VERTEX_PAINT':
                new_brush = bpy.data.brushes.get(ve.ori_brush)
            elif mode == 'TEXTURE_PAINT':
                new_brush = bpy.data.brushes.get(ve.ori_texpaint_brush)
            elif mode == 'SCULPT':
                new_brush = bpy.data.brushes.get(ve.ori_sculpt_brush)

            if new_brush: 
                if mode == 'VERTEX_PAINT':
                    new_brush.blend = ve.ori_blending_mode
                elif mode == 'TEXTURE_PAINT':
                    new_brush.blend = ve.ori_texpaint_blending_mode
                elif mode == 'SCULPT':
                    new_brush.blend = ve.ori_sculpt_blending_mode
            else:
                new_brush = draw_brush
                new_brush.blend = 'MIX'

            if mode == 'VERTEX_PAINT':
                ve.ori_brush = ''
                ve.ori_blending_mode = ''
            elif mode == 'TEXTURE_PAINT':
                ve.ori_texpaint_brush = ''
                ve.ori_texpaint_blending_mode = ''
            elif mode == 'SCULPT':
                ve.ori_sculpt_brush = ''
                ve.ori_sculpt_blending_mode = ''

        else:

            if mode == 'VERTEX_PAINT':
                ve.ori_brush = brush.name
                ve.ori_blending_mode = brush.blend
            elif mode == 'TEXTURE_PAINT':
                ve.ori_texpaint_brush = brush.name
                ve.ori_texpaint_blending_mode = brush.blend
            if mode == 'SCULPT':
                ve.ori_sculpt_brush = brush.name
                ve.ori_sculpt_blending_mode = brush.blend

            new_brush = eraser_brush

        if new_brush:
            if mode == 'TEXTURE_PAINT':
                context.tool_settings.image_paint.brush = new_brush
            elif mode == 'VERTEX_PAINT': 
                context.tool_settings.vertex_paint.brush = new_brush
            elif mode == 'SCULPT': 
                context.tool_settings.sculpt.brush = new_brush

        return {'FINISHED'}

class YSelectFacesByVcol(bpy.types.Operator):
    bl_idname = "mesh.y_select_faces_by_vcol"
    bl_label = "Select Faces based on Vertex Color"
    bl_description = "Select faces based on vertex color"
    bl_options = {'REGISTER', 'UNDO'}

    color : FloatVectorProperty(
            name='Color', size=4,
            subtype='COLOR',
            default=(1.0, 0.0, 1.0, 1.0),
            min=0.0, max=1.0,
            )

    #deselect : BoolProperty(
    #        name='Deselect Faces',
    #        description='Deselect faces with vertex color', 
    #        default=False)

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not obj or obj.type != 'MESH' or not any(get_vertex_colors(obj)): return False

        if is_bl_newer_than(3, 2):
            vcol = obj.data.color_attributes.active_color
            if not vcol or vcol.domain != 'CORNER':
                return False

        return obj.mode == 'EDIT'

    def execute(self, context):

        threshold = .004
        mat = context.object.active_material
        vcol_name = get_active_vertex_color(context.object).name
        target = Color((self.color[0], self.color[1], self.color[2]))
        if not is_bl_newer_than(3, 2):
            target = linear_to_srgb(target)

        if mat.users > 1 and is_bl_newer_than(2, 80):
            objs = get_all_objects_with_same_materials(mat, mesh_only=True)
        else: objs = [context.object]

        # Select object first
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action='DESELECT')
        for obj in objs:
            set_object_select(obj, True)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.context.tool_settings.mesh_select_mode = (False, False, True)
        bpy.ops.mesh.reveal()
        bpy.ops.mesh.select_all(action='DESELECT')

        bpy.ops.object.mode_set(mode="OBJECT")
        
        for obj in objs:

            # Select vcol
            vcols = get_vertex_colors(obj)
            vcol = vcols.get(vcol_name)
            if not vcol: continue
            set_active_vertex_color(obj, vcol)

            # Select polygons
            for p in obj.data.polygons:
                r = g = b = 0
                for i in p.loop_indices:
                    c = vcol.data[i].color
                    r += c[0]
                    g += c[1]
                    b += c[2]
                r /= p.loop_total
                g /= p.loop_total
                b /= p.loop_total
                source = Color((r, g, b))
            
                if (abs(source.r - target.r) < threshold and
                    abs(source.g - target.g) < threshold and
                    abs(source.b - target.b) < threshold):
            
                    p.select = True
                    #p.select = not self.deselect

        bpy.ops.object.mode_set(mode="EDIT")
        
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

        if is_bl_newer_than(3, 2):
            vcol = obj.data.color_attributes.active_color
            if not vcol or vcol.domain != 'CORNER':
                return False

        return obj.mode == 'EDIT'

    def execute(self, context):
        T = time.time()

        # Experiment with numpy
        use_numpy = True #is_bl_newer_than(2, 80)

        if is_bl_newer_than(2, 80):
            objs = context.objects_in_mode

            # Set the same vertex color for all objects first
            vcol = get_active_vertex_color(context.object)
            for obj in objs:
                vcols = get_vertex_colors(obj)
                vc = vcols.get(vcol.name)
                set_active_vertex_color(obj, vc)

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

            if not vcol: 
                bpy.ops.object.mode_set(mode='EDIT')
                continue

            color = Color((self.color[0], self.color[1], self.color[2]))
            if not is_bl_newer_than(3, 2):
                color = linear_to_srgb(color)

            if is_bl_newer_than(2, 80):
                color = (color[0], color[1], color[2], self.color[3])

            # HACK: Sometimes color assigned are different so read the assigned color and write it back to mask color id
            if len(loop_indices) > 0:
                vcol.data[loop_indices[0]].color = color
                if any([color[i] for i in range(3) if color[i] != vcol.data[loop_indices[0]].color[i]]) and hasattr(context, 'mask'):
                    written_col = vcol.data[loop_indices[0]].color
                    color = (written_col[0], written_col[1], written_col[2])
                                
                    set_entity_prop_value(context.mask, 'color_id', Color(color))
                    if not is_bl_newer_than(3, 2):
                        set_entity_prop_value(context.mask, 'color_id', srgb_to_linear(get_mask_color_id_color(context.mask)))
                    if is_bl_newer_than(2, 80):
                        color = (written_col[0], written_col[1], written_col[2], written_col[3])

                # Blender 2.80+ has alpha channel on vertex color
                dimension = 4 if is_bl_newer_than(2, 80) else 3

                if use_numpy:
                    nvcol = numpy.zeros(len(vcol.data) * dimension, dtype=numpy.float32)
                    vcol.data.foreach_get('color', nvcol)
                    nvcol2D = nvcol.reshape(-1, dimension)
                    nvcol2D[loop_indices]= color    
                    vcol.data.foreach_set('color', nvcol)
                else :
                    for i, loop_index in enumerate(loop_indices):
                        vcol.data[loop_index].color = color

            bpy.ops.object.mode_set(mode='EDIT')

        print('VCOL: Fill Color ID is done at', '{:0.2f}'.format(time.time() - T), 'seconds!')

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

        if is_bl_newer_than(3, 2):
            vcol = obj.data.color_attributes.active_color
            if not vcol or vcol.domain not in {'CORNER', 'POINT'}:
                return False

        return obj.mode == 'EDIT'

    def execute(self, context):
        T = time.time()

        # Experiment with numpy
        use_numpy = True #is_bl_newer_than(2, 80)

        if is_bl_newer_than(2, 80):
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

            loop_indices = []
            for face in bm.faces:
                if face.select:
                    for loop in face.loops:
                        loop_indices.append(loop.index)

            vert_indices = []
            for vert in bm.verts:
                if vert.select:
                    vert_indices.append(vert.index)

            bpy.ops.object.mode_set(mode='OBJECT')
            vcol = get_active_vertex_color(obj)

            if not vcol: 
                bpy.ops.object.mode_set(mode='EDIT')
                continue

            color = Color((ve.color[0], ve.color[1], ve.color[2]))
            alpha = context.scene.ve_edit.color[3]

            if self.color_option == 'WHITE':
                color = (1,1,1)
                alpha = 1.0
            elif self.color_option == 'BLACK':
                color = (0,0,0)
                alpha = 1.0
            elif not is_bl_newer_than(3, 2):
                color = linear_to_srgb(color)

            # Blender 2.80+ has alpha channel on vertex color
            dimension = 4 if is_bl_newer_than(2, 80) else 3
            if is_bl_newer_than(2, 80):
                color = (color[0], color[1], color[2], alpha)

            if is_bl_newer_than(3, 2) and vcol.domain == 'POINT':
                if use_numpy:
                    nvcol = numpy.zeros(len(vcol.data) * dimension, dtype=numpy.float32)
                    vcol.data.foreach_get('color', nvcol)
                    nvcol2D = nvcol.reshape(-1, dimension)
                    nvcol2D[vert_indices]= color
                    vcol.data.foreach_set('color', nvcol)
                else:
                    for vert_index in vert_indices:
                        vcol.data[vert_index].color = color
            else:
                if fill_mode == 'FACE':
                    if use_numpy:
                        nvcol = numpy.zeros(len(vcol.data) * dimension, dtype=numpy.float32)
                        vcol.data.foreach_get('color', nvcol)
                        nvcol2D = nvcol.reshape(-1, dimension)
                        nvcol2D[loop_indices]= color
                        vcol.data.foreach_set('color', nvcol)
                    else:                    
                        for loop_index in loop_indices:
                            vcol.data[loop_index].color = color
                else:
                    if use_numpy:
                        loop_to_vert = numpy.zeros(len(mesh.loops), dtype=numpy.uint32)
                        mesh.loops.foreach_get('vertex_index', loop_to_vert)
                        loop_indices = (numpy.in1d(loop_to_vert, vert_indices)).nonzero()[0]
                        nvcol = numpy.zeros(len(vcol.data) * dimension, dtype=numpy.float32)
                        vcol.data.foreach_get('color', nvcol)
                        nvcol2D = nvcol.reshape(-1, dimension)
                        nvcol2D[loop_indices] = color
                        vcol.data.foreach_set('color', nvcol)   
                    else:
                        for poly in mesh.polygons:
                            for loop_index in poly.loop_indices:
                                loop_vert_index = mesh.loops[loop_index].vertex_index
                                if loop_vert_index in vert_indices:
                                    vcol.data[loop_index].color = color

            bpy.ops.object.mode_set(mode='EDIT')

        print('VCOL: Fill vertex color is done at', '{:0.2f}'.format(time.time() - T), 'seconds!')

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
        if is_bl_newer_than(3, 2):
            rcol.template_list("MESH_UL_color_attributes", "vcols", mesh, 
                    "color_attributes", vcols, "active_color_index", rows=2)
            rcol = row.column(align=True)
            rcol.operator("geometry.color_attribute_add", icon='ADD', text="")
            rcol.operator("geometry.color_attribute_remove", icon='REMOVE', text="")
        else:
            if is_bl_newer_than(2, 80):
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
    #if is_bl_newer_than(2, 80):
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

class VIEW3D_PT_y_vcol_editor_ui(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_label = "Vertex Color Editor"
    bl_context = "mesh_edit"
    bl_region_type = 'UI'
    bl_category = 'VCol Edit'
    #bl_options = {'DEFAULT_CLOSED'} 

    @classmethod
    def poll(cls, context):
        ypup = get_user_preferences()
        return ypup and (not hasattr(ypup, 'show_experimental') or ypup.show_experimental) and context.object and context.object.type == 'MESH'

    def draw(self, context):
        vcol_editor_draw(self, context)

class VIEW3D_PT_y_vcol_editor_tools(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_label = "Vertex Color Editor"
    bl_context = "mesh_edit"
    bl_region_type = 'TOOLS'

    @classmethod
    def poll(cls, context):
        ypup = get_user_preferences()
        return ypup and (not hasattr(ypup, 'show_experimental') or ypup.show_experimental) and context.object and context.object.type == 'MESH'

    def draw(self, context):
        vcol_editor_draw(self, context)

class YVcolEditorProps(bpy.types.PropertyGroup):
    color : FloatVectorProperty(name='Color', size=4, subtype='COLOR', default=(1.0,1.0,1.0,1.0), min=0.0, max=1.0)
    #palette : PointerProperty(type=bpy.types.Palette)

    show_vcol_list : BoolProperty(name='Show Vertex Color List',
            description='Show vertex color list', default=True)

    ori_blending_mode : StringProperty(default='')
    ori_brush : StringProperty(default='')

    ori_texpaint_blending_mode : StringProperty(default='')
    ori_texpaint_brush : StringProperty(default='')

    ori_sculpt_blending_mode : StringProperty(default='')
    ori_sculpt_brush : StringProperty(default='')

def register():
    bpy.utils.register_class(VIEW3D_PT_y_vcol_editor_ui)
    if not is_bl_newer_than(2, 80):
        bpy.utils.register_class(VIEW3D_PT_y_vcol_editor_tools)
    bpy.utils.register_class(YVcolEditorProps)

    bpy.types.Scene.ve_edit = PointerProperty(type=YVcolEditorProps)

    bpy.utils.register_class(YVcolFill)
    bpy.utils.register_class(YSelectFacesByVcol)
    bpy.utils.register_class(YVcolFillFaceCustom)
    bpy.utils.register_class(YToggleEraser)
    bpy.utils.register_class(YSetActiveVcol)

def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_y_vcol_editor_ui)
    if not is_bl_newer_than(2, 80):
        bpy.utils.unregister_class(VIEW3D_PT_y_vcol_editor_tools)
    bpy.utils.unregister_class(YVcolEditorProps)

    bpy.utils.unregister_class(YVcolFill)
    bpy.utils.unregister_class(YSelectFacesByVcol)
    bpy.utils.unregister_class(YVcolFillFaceCustom)
    bpy.utils.unregister_class(YToggleEraser)
    bpy.utils.unregister_class(YSetActiveVcol)
