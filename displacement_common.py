import bpy
from bpy.props import *
from .common import *
from . import channel_common

def get_objs_size_proportions(objs):

    sizes = []
    
    for obj in objs:
        sorted_dim = sorted(obj.dimensions, reverse=True)
        # Object size is only measured on its largest 2 dimensions because this should work on a plane too
        size = sorted_dim[0] * sorted_dim[1]
        sizes.append(size)

    total_size = sum(sizes)

    # Measure object size compared to total size
    proportions = {}
    for i, size in enumerate(sizes):
        proportions[objs[i].name] = size/total_size

    return proportions

def set_subdiv_global_dicing(height_ch, objs=[]):
    scene = bpy.context.scene

    # Blender 5.0 will set the pixel size in the modifiers rather than setting global settings
    if is_bl_newer_than(5):
        if len(objs) == 0:
            mat = get_active_material()
            objs = get_all_objects_with_same_materials(mat)

        for obj in objs:
            subsurf = get_subsurf_modifier(obj)
            if subsurf:
                subsurf.adaptive_pixel_size = height_ch.subdiv_global_dicing

        scene.cycles.dicing_rate = 1.0
        scene.cycles.preview_dicing_rate = 1.0

    else:
        scene.cycles.dicing_rate = height_ch.subdiv_global_dicing
        scene.cycles.preview_dicing_rate = height_ch.subdiv_global_dicing

def setup_subdiv_to_max_polys(obj, max_polys, subsurf=None):
    
    if obj.type != 'MESH': return
    if not subsurf: subsurf = get_subsurf_modifier(obj)
    if not subsurf: return

    # Remember active object
    ori_active_obj = bpy.context.object

    # Check object polygons
    num_poly = len(obj.data.polygons)

    # Get levels
    level = int(math.log(max_polys / num_poly, 4))

    if subsurf.type == 'MULTIRES':
        if level > subsurf.total_levels: 
            set_active_object(obj)
            for i in range(level - subsurf.total_levels):
                if not is_bl_newer_than(2, 90):
                    bpy.ops.object.multires_subdivide(modifier=subsurf.name)
                else:
                    if is_mesh_flat_shaded(obj.data):
                        bpy.ops.object.multires_subdivide(modifier=subsurf.name, mode='SIMPLE')
                    else: bpy.ops.object.multires_subdivide(modifier=subsurf.name, mode='CATMULL_CLARK')
            level = subsurf.total_levels
    else:
        # Maximum subdivision is 10
        if level > 10: level = 10

    subsurf.render_levels = level
    subsurf.levels = level

    # Recover active object
    if bpy.context.object != ori_active_obj:
        set_active_object(ori_active_obj)

def set_subdivision_levels(objs, thousand_polys_target=1000):

    proportions = get_objs_size_proportions(objs)

    for obj in objs:

        # Subsurf / Multires Modifier
        subsurf = get_subsurf_modifier(obj)
        multires = get_multires_modifier(obj, include_hidden=True)

        if multires:
            #if height_ch.enable_subdiv_setup and (height_ch.subdiv_subsurf_only or height_ch.subdiv_adaptive):
            # TODO: Disable Multires options
            if False:
                multires.show_render = False
                multires.show_viewport = False
            else:
                if subsurf: 
                    obj.modifiers.remove(subsurf)
                multires.show_render = True
                multires.show_viewport = True
                subsurf = multires

        #if height_ch.enable_subdiv_setup:
        if not subsurf:
            subsurf = obj.modifiers.new('Subsurf', 'SUBSURF')
            if obj.type == 'MESH' and is_mesh_flat_shaded(obj.data):
                subsurf.subdivision_type = 'SIMPLE'

        setup_subdiv_to_max_polys(obj, thousand_polys_target * 1000 * proportions[obj.name], subsurf)

        # Set subsurf to visible
        if subsurf:
            subsurf.show_render = True
            subsurf.show_viewport = True

def remember_subsurf_modifiers(mat=None, objs=[]):
    if not mat: mat = get_active_material()
    if len(objs) == 0 and mat: objs = get_all_objects_with_same_materials(mat, True)

    # Displacement method is inside object data for Blender 2.77 and below 
    if not is_bl_newer_than(2, 78):
        for obj in objs:
            if obj.data and hasattr(obj.data, 'cycles'):
                obj.data.cycles.displacement_method = displacement_method

    for obj in objs:
        subsurf = get_subsurf_modifier(obj)
        if subsurf:
            obj.yp.ori_has_subsurf = True
            obj.yp.ori_subsurf_render_levels = subsurf.render_levels
            obj.yp.ori_subsurf_levels = subsurf.levels
            if is_bl_newer_than(5):
                obj.yp.ori_subsurf_use_adapative = subsurf.use_adaptive_subdivision

        multires = get_multires_modifier(obj)
        if multires:
            obj.yp.ori_has_multires = True
            obj.yp.ori_multires_render_levels = multires.render_levels
            obj.yp.ori_multires_levels = multires.levels

def recover_subsurf_modifiers(mat=None, objs=[]):
    if not mat: mat = get_active_material()
    if len(objs) == 0 and mat: objs = get_all_objects_with_same_materials(mat, True)

    for obj in objs:
        subsurf = get_subsurf_modifier(obj)

        # Recover the existance
        if not subsurf and obj.yp.ori_has_subsurf:
            subsurf = obj.modifiers.new(name="Subsurf", type='SUBSURF')
        elif subsurf and not obj.yp.ori_has_subsurf:
            obj.modifiers.remove(subsurf)
            subsurf = None

        if subsurf:
            if subsurf.render_levels != obj.yp.ori_subsurf_render_levels:
                subsurf.render_levels = obj.yp.ori_subsurf_render_levels
            if subsurf.levels != obj.yp.ori_subsurf_levels:
                subsurf.levels = obj.yp.ori_subsurf_levels
            if is_bl_newer_than(5) and subsurf.use_adaptive_subdivision != obj.yp.ori_subsurf_use_adapative:
                subsurf.use_adaptive_subdivision = obj.yp.ori_subsurf_use_adapative

        multires = get_multires_modifier(obj)

        # Recover the existance
        if not multires and obj.yp.ori_has_multires:
            multires = obj.modifiers.new(name="Multiresolution", type='MULTIRES')
        elif multires and not obj.yp.ori_has_multires:
            obj.modifiers.remove(multires)
            multires = None

        if multires:
            render_levels = obj.yp.ori_multires_render_levels if obj.yp.ori_multires_render_levels <= multires.total_levels else multires.total_levels
            if multires.render_levels != render_levels:
                multires.render_levels = render_levels

            levels = obj.yp.ori_multires_levels if obj.yp.ori_multires_levels <= multires.total_levels else multires.total_levels
            if multires.levels != levels:
                multires.levels = levels

def enable_displacement_setup(mat, yp=None, objs=[], thousand_polys_target=1000, displacement_method='BOTH', use_adaptive_subdivision=False, dicing_rate=1.0,):
    scene = bpy.context.scene
    if len(objs) == 0: objs = get_all_objects_with_same_materials(mat)
    if len(objs) == 0: return

    # Remember the original modifier values
    remember_subsurf_modifiers(mat, objs)

    # Displacement only works with experimental feature set in Blender 2.79
    if not is_bl_newer_than(5) and (use_adaptive_subdivision or not is_bl_newer_than(2, 80)):
        scene.cycles.feature_set = 'EXPERIMENTAL'

    # Legacy blender has different enum
    if not is_bl_newer_than(2, 80) and displacement_method == 'DISPLACEMENT':
        displacement_method = 'TRUE'

    # Set displacement mode
    if hasattr(mat, 'displacement_method'):
        mat.displacement_method = displacement_method

    # Set cycles displacement mode
    if hasattr(mat.cycles, 'displacement_method'):
        mat.cycles.displacement_method = displacement_method
    
    # Displacement method is inside object data for Blender 2.77 and below 
    if not is_bl_newer_than(2, 78):
        for obj in objs:
            if obj.data and hasattr(obj.data, 'cycles'):
                obj.data.cycles.displacement_method = displacement_method

    # Add subdivision levels
    set_subdivision_levels(objs, thousand_polys_target=thousand_polys_target)

    # Adaptive subdivision dicing rate
    if use_adaptive_subdivision:
        # Blender 5.0 will set the pixel size in the modifiers rather than setting global settings
        scene.cycles.dicing_rate = 1.0 if is_bl_newer_than(5) else dicing_rate
        scene.cycles.preview_dicing_rate = 1.0 if is_bl_newer_than(5) else dicing_rate

    # Adaptive subdivision
    for obj in objs:
        if is_bl_newer_than(5):
            subsurf = get_subsurf_modifier(obj)
            if subsurf:
                subsurf.use_adaptive_subdivision = use_adaptive_subdivision
                if use_adaptive_subdivision: subsurf.adaptive_pixel_size = dicing_rate
        else:
            obj.cycles.use_adaptive_subdivision = use_adaptive_subdivision

    if yp:
        # NOTE: Height as bump will always be disabled at this point for now
        height_root_ch = get_root_height_channel(yp)
        if height_root_ch: height_root_ch.use_height_as_bump = False

        # Create normal without height bake target so baked node can be displayed correctly
        bt = channel_common.create_normal_without_bump_bake_target(yp)

        # Set the bake target as the default bake target of normal channel
        normal_ch = get_root_normal_channel(yp)
        if normal_ch and bt: normal_ch.bake_target_name = bt.name

def disable_displacement_setup(mat, yp=None, objs=[], recover_original=False, displacement_method='BUMP', delete_subdivision=False, subdiv_level=1, disable_adaptive_subdiv=True):
    if len(objs) == 0: objs = get_all_objects_with_same_materials(mat)
    if len(objs) == 0: return

    # Set displacement mode
    if hasattr(mat, 'displacement_method'):
        mat.displacement_method = displacement_method

    # Set cycles displacement mode
    if hasattr(mat.cycles, 'displacement_method'):
        mat.cycles.displacement_method = displacement_method
    
    # Displacement method is inside object data for Blender 2.77 and below 
    if not is_bl_newer_than(2, 78):
        for obj in objs:
            if obj.data and hasattr(obj.data, 'cycles'):
                obj.data.cycles.displacement_method = displacement_method

    if recover_original:
        recover_subsurf_modifiers(mat, objs)
    else:
        for obj in objs:

            # Subsurf / Multires Modifier
            multires = get_multires_modifier(obj, include_hidden=False)
            subsurf = get_subsurf_modifier(obj)

            # Prioritize multires, since lowing the levels makes more sense
            if multires:
                subsurf = multires

            if subsurf:
                if not delete_subdivision:
                    subsurf.levels = subdiv_level
                    subsurf.render_levels = subdiv_level
                else:
                    # Remove subdivision
                    #bpy.ops.object.modifier_remove(modifier=subsurf.name)
                    obj.modifiers.remove(subsurf)

        # Disable Adaptive subdiv
        if disable_adaptive_subdiv:
            for obj in objs:
                subsurf = get_subsurf_modifier(obj)
                if not is_bl_newer_than(5):
                    obj.cycles.use_adaptive_subdivision = False
                elif subsurf: subsurf.use_adaptive_subdivision = False

    # NOTE: Height as bump will always be enabled at this point for now
    if yp:
        height_root_ch = get_root_height_channel(yp)
        if height_root_ch: height_root_ch.use_height_as_bump = True

def check_displacement_node(mat, node, set_one=False, unset_one=False, set_outside=False):

    output_mat = get_material_output(mat)
    if not output_mat: return None

    height_ch = get_root_height_channel(node.node_tree.yp)
    if not height_ch: return None

    # Check output connection
    norm_outp = node.outputs[height_ch.name]
    height_outp = node.outputs.get(height_ch.name + io_suffix['HEIGHT'])
    max_height_outp = node.outputs.get(height_ch.name + io_suffix['MAX_HEIGHT'])
    vdisp_outp = node.outputs.get(height_ch.name + io_suffix['VDISP'])
    disp_mat_inp = output_mat.inputs['Displacement']

    disp = channel_common.get_closest_disp_node_backward(output_mat, 'Displacement')
    vdisp = channel_common.get_closest_disp_node_backward(output_mat, 'Displacement', is_vector_disp=True)
    add_disp = None

    if set_one or set_outside:
        
        # Set add vector node
        if is_bl_newer_than(2, 80) and ((not disp and not vdisp) or (disp and not vdisp) or (not disp and vdisp)):
            add_disp = mat.node_tree.nodes.new('ShaderNodeVectorMath')

            add_disp.location.x = output_mat.location.x
            add_disp.location.y = node.location.y - 170
            add_disp.hide = True

        # Set displacement
        if not disp:

            # Create displacement node
            disp = channel_common.create_displacement_node(mat.node_tree) #, disp_mat_inp)

            disp.location.x = output_mat.location.x
            disp.location.y = node.location.y - 220

            # Set displacement node default value
            disp.inputs['Height'].default_value = 0.0
            disp.inputs['Scale'].default_value = 0.0

        elif set_one:
            # Connect the original connections to yp node
            height_inp = None
            for l in disp.inputs['Height'].links:
                if not l.from_socket or l.from_node == node: continue
                height_inp = node.inputs.get(height_ch.name + io_suffix['HEIGHT'])
                if height_inp: create_link(mat.node_tree, l.from_socket, height_inp)

            for l in disp.inputs['Scale'].links:
                if not l.from_socket or l.from_node == node: continue
                max_height_inp = node.inputs.get(height_ch.name + io_suffix['MAX_HEIGHT'])
                if max_height_inp: create_link(mat.node_tree, l.from_socket, max_height_inp)
            
            # Need to check check start and end nodes again if height input is connected
            if height_inp: check_all_channel_ios(node.node_tree.yp, reconnect=False)

        # Set vector displacement
        if not vdisp:

            # Create displacement node
            vdisp = channel_common.create_vector_displacement_node(mat.node_tree) #, disp_mat_inp)

            if vdisp:
                vdisp.location.x = output_mat.location.x
                vdisp.location.y = node.location.y - 410

                # Set displacement node default value
                vdisp.inputs['Vector'].default_value = (0, 0, 0, 0)

        elif set_one:
            # Connect the original connections to yp node
            vdisp_input = None
            for l in vdisp.inputs['Vector'].links:
                if not l.from_socket or l.from_node == node: continue
                vdisp_input = node.inputs.get(height_ch.name + io_suffix['VDISP'])
                if vdisp_input: create_link(mat.node_tree, l.from_socket, vdisp_input)

        if add_disp and vdisp:
            create_link(mat.node_tree, disp.outputs[0], add_disp.inputs[0])
            create_link(mat.node_tree, vdisp.outputs[0], add_disp.inputs[1])
            create_link(mat.node_tree, add_disp.outputs[0], disp_mat_inp)
        elif disp and not vdisp:
            create_link(mat.node_tree, disp.outputs[0], disp_mat_inp)

        if set_one:
            # Create links
            if vdisp and vdisp_outp: create_link(mat.node_tree, vdisp_outp, vdisp.inputs['Vector'])
            if disp:
                create_link(mat.node_tree, height_outp, disp.inputs['Height'])
                create_link(mat.node_tree, max_height_outp, disp.inputs['Scale'])

    if unset_one:
        if disp:
            height_inp = node.inputs.get(height_ch.name + io_suffix['HEIGHT'])
            max_height_inp = node.inputs.get(height_ch.name + io_suffix['MAX_HEIGHT'])

            if height_inp and len(height_inp.links) > 0:
                soc = height_inp.links[0].from_socket
                create_link(mat.node_tree, soc, disp.inputs['Height'])
                break_input_link(mat.node_tree, height_inp)

            if max_height_inp and len(max_height_inp.links) > 0:
                soc = max_height_inp.links[0].from_socket
                create_link(mat.node_tree, soc, disp.inputs['Scale'])
                break_input_link(mat.node_tree, max_height_inp)

        if vdisp:
            vdisp_inp = node.inputs.get(height_ch.name + io_suffix['VDISP'])
            if vdisp_inp and len(vdisp_inp.links) > 0:
                soc = vdisp_inp.links[0].from_socket
                create_link(mat.node_tree, soc, vdisp.inputs['Vector'])
                break_input_link(mat.node_tree, height_inp)

    return disp

def check_subdiv_setup(height_ch):
    tree = height_ch.id_data
    yp = tree.yp
    ypup = get_user_preferences()

    if not height_ch: return
    mat = get_active_material()
    scene = bpy.context.scene
    objs = get_all_objects_with_same_materials(mat, True)

    mtree = mat.node_tree

    # Get active output material
    output_mat = get_material_output(mat)
    if not output_mat: return

    # Get active ypaint node
    node = get_active_ypaint_node()
    norm_outp = node.outputs[height_ch.name]

    # Scene and material displacement settings
    if height_ch.enable_subdiv_setup:

        # Displacement only works with experimental feature set in Blender 2.79
        if not is_bl_newer_than(5) and (height_ch.subdiv_adaptive or not is_bl_newer_than(2, 80)):
            scene.cycles.feature_set = 'EXPERIMENTAL'

        if height_ch.subdiv_adaptive:
            set_subdiv_global_dicing(height_ch, objs)

        # Set displacement mode
        if hasattr(mat, 'displacement_method'):
            mat.displacement_method = 'BOTH'

        # Set cycles displacement mode
        if hasattr(mat.cycles, 'displacement_method'):
            if is_bl_newer_than(2, 80):
                mat.cycles.displacement_method = 'BOTH'
            else: mat.cycles.displacement_method = 'TRUE'
        
        # Displacement method is inside object data for Blender 2.77 and below 
        if not is_bl_newer_than(2, 78):
            for obj in objs:
                if obj.data and hasattr(obj.data, 'cycles'):
                    obj.data.cycles.displacement_method = 'TRUE'

        if not yp.use_baked or not yp.enable_baked_outside:
            check_displacement_node(mat, node, set_one=True)

    # Outside nodes connection set
    #if yp.use_baked and yp.enable_baked_outside:
    #    frame = get_node(mtree, yp.baked_outside_frame)
    #    norm = get_node(mtree, height_ch.baked_outside_normal_process, parent=frame)
    #    disp = get_node(mtree, height_ch.baked_outside_disp_process, parent=frame)
    #    baked_outside = get_node(mtree, height_ch.baked_outside, parent=frame)
    #    baked_outside_normal_overlay = get_node(mtree, height_ch.baked_outside_normal_overlay, parent=frame)

    #    if height_ch.enable_subdiv_setup:
    #        if disp:
    #            create_link(mtree, disp.outputs[0], output_mat.inputs['Displacement'])
    #        if baked_outside and norm:
    #            create_link(mtree, baked_outside.outputs[0], norm.inputs[1])
    #    else:
    #        if baked_outside and norm:
    #            create_link(mtree, baked_outside.outputs[0], norm.inputs[1])
    #    
    #    if norm and not baked_outside_normal_overlay and height_ch.enable_subdiv_setup:
    #        for l in norm.outputs[0].links:
    #            mtree.links.remove(l)
    #    elif norm:
    #        for con in height_ch.ori_to:
    #            n = mtree.nodes.get(con.node)
    #            if n:
    #                s = n.inputs.get(con.socket)
    #                if s:
    #                    create_link(mtree, norm.outputs[0], s)

    # Remember active object
    ori_active_obj = bpy.context.object

    # Iterate all objects with same materials
    proportions = get_objs_size_proportions(objs)
    for obj in objs:

        # Set active object to modify modifier order
        set_active_object(obj)

        # Subsurf / Multires Modifier
        subsurf = get_subsurf_modifier(obj)
        multires = get_multires_modifier(obj, include_hidden=True)

        if multires:
            if height_ch.enable_subdiv_setup and (height_ch.subdiv_subsurf_only or height_ch.subdiv_adaptive):
                multires.show_render = False
                multires.show_viewport = False
            else:
                if subsurf: 
                    obj.modifiers.remove(subsurf)
                multires.show_render = True
                multires.show_viewport = True
                subsurf = multires

        if height_ch.enable_subdiv_setup:
            if not subsurf:
                subsurf = obj.modifiers.new('Subsurf', 'SUBSURF')
                if obj.type == 'MESH' and is_mesh_flat_shaded(obj.data):
                    subsurf.subdivision_type = 'SIMPLE'

            displacement = setup_subdiv_to_max_polys(obj, height_ch.subdiv_on_max_polys * 1000 * proportions[obj.name], subsurf)

        # Set subsurf to visible
        if subsurf:
            subsurf.show_render = True
            subsurf.show_viewport = True

        # Adaptive subdiv
        subsurf = get_subsurf_modifier(obj)
        if height_ch.enable_subdiv_setup and height_ch.subdiv_adaptive:
            if not is_bl_newer_than(5):
                obj.cycles.use_adaptive_subdivision = True
            elif subsurf: subsurf.use_adaptive_subdivision = True
        else: 
            if not is_bl_newer_than(5):
                obj.cycles.use_adaptive_subdivision = False
            elif subsurf: subsurf.use_adaptive_subdivision = False

    set_active_object(ori_active_obj)

class YRemoveDisplacementSetup(bpy.types.Operator):
    bl_idname = "wm.y_remove_displacement_setup"
    bl_label = "Remove Displacement and Subdivision Setup"
    bl_description = "Disable material displacement settings and remove or use lower subdivision modifer to all objects with the same material.\nNOTE: This will also make the height output no longer accessible."
    bl_options = {'REGISTER', 'UNDO'}

    action : EnumProperty(
        name = 'Remove Displacement Action',
        items = (
            ('ORIGINAL', 'Recover Original State', 'Recover original object modifier states before displacement setup.'),
            ('REMOVE', 'Remove Subdivision Modifier', 'Delete existing subdivision or multires modifier.'),
            ('KEEP', 'Keep Subdivision Modifier', 'Keep subdivision or multires modifier.'),
        ),
        default = 'ORIGINAL'
    )

    subdiv_level : IntProperty(
        name = 'Subdivision Level',
        description = 'Set subdivision level on all objects with the same material',
        default=1, min=0, max=10, 
    )

    @classmethod
    def poll(cls, context):
        return context.object and get_active_material()

    def invoke(self, context, event):
        #displacement_method = get_displacement_method()
        #
        #self.displacement_found = displacement_method in {'DISPLACEMENT', 'BOTH', 'TRUE'}
        #if not self.displacement_found:
        #    return self.execute(context)

        return context.window_manager.invoke_props_dialog(self, width=350)

    def draw(self, context):
        row = split_layout(self.layout, 0.35)
        col = row.column()
        col.label(text='Action:')
        if self.action == 'KEEP':
            col.label(text='Set Subdivision Level:')

        col = row.column()
        col.prop(self, 'action', text='')
        if self.action == 'KEEP':
            col.prop(self, 'subdiv_level', text='')

    def execute(self, context):
        #if not self.displacement_found:
        #    self.report({'ERROR'}, "Displacement setup doesn't exist yet!")
        #    return {'CANCELLED'}

        mat = get_active_material()
        node = get_active_ypaint_node()
        yp = node.node_tree.yp if node else None

        # Remove subdivision
        disable_displacement_setup(mat, yp,
            recover_original = self.action == 'ORIGINAL',
            delete_subdivision = self.action == 'REMOVE',
            subdiv_level = self.subdiv_level
        )

        return {'FINISHED'}

class YQuickDisplacementSetup(bpy.types.Operator):
    bl_idname = "wm.y_quick_displacement_setup"
    bl_label = "Quick Displacement and Subdivision Setup"
    bl_description = "Enable material displacement settings and add subdivision modifer to all objects with the same material.\nNOTE: This will also make the height output accessible."
    bl_options = {'REGISTER', 'UNDO'}

    displacement_method : EnumProperty(
        name = 'Displacement Method',
        items = (
            #('BUMP', 'Bump Only', 'Bump mapping to simulate the appearance of displacement.'),
            ('DISPLACEMENT', 'Displacement Only', 'Use true displacement of surface only, requires fine subdivision.'),
            ('BOTH', 'Displacement and Bump', 'Combination of true displacement and bump mapping for finer detail.'),
        ),
        default = 'BOTH'
    )

    max_polys : IntProperty(
        name = 'Subdivision Max Polygons',
        description = 'Add subdivision modifier with number of max polygons (in thousand)',
        default=1000, min=1, max=10000, 
    )

    use_adaptive_subdivision : BoolProperty(
        name = 'Use Adaptive Subdivision',
        description = 'Use adaptive subdivion (Cycles Only)',
        default = False
    )

    dicing_rate : FloatProperty(
        name = 'Adaptive Subdivision Dicing Rate',
        description = 'Adaptive subdivision dicing rate in pixels',
        default=1.0, min=0.5, max=1000,
    )

    @classmethod
    def poll(cls, context):
        return context.object and get_active_material()

    def invoke(self, context, event):
        # Check current displacement mode
        method = get_displacement_method()

        if method in {'TRUE', 'DISPLACEMENT'}:
            self.displacement_method = 'DISPLACEMENT'
        elif method == 'BOTH':
            self.displacement_method = 'BOTH'

        return context.window_manager.invoke_props_dialog(self, width=330)

    def draw(self, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp if node else None
        try: ch = yp.channels[yp.active_channel_index] if yp else None
        except: ch = None

        row = split_layout(self.layout, 0.35)
        col = row.column()
        col.label(text='Method:')
        col.label(text='Max Polygons:')
        col.label(text='')
        if self.use_adaptive_subdivision:
            col.label(text='Dicing Rate')

        col = row.column()
        col.prop(self, 'displacement_method', text='')
        col.prop(self, 'max_polys', text='')
        col.prop(self, 'use_adaptive_subdivision', text='Adaptive (Cycles Only)')
        if self.use_adaptive_subdivision:
            col.prop(self, 'dicing_rate', text='')

    def execute(self, context):
        mat = get_active_material()
        node = get_active_ypaint_node()
        yp = node.node_tree.yp if node else None

        # Add subdivisions
        enable_displacement_setup(mat, yp=yp,
            thousand_polys_target = self.max_polys, 
            displacement_method = self.displacement_method,
            use_adaptive_subdivision = self.use_adaptive_subdivision,
            dicing_rate = self.dicing_rate
        )

        return {'FINISHED'}

def register():
    bpy.utils.register_class(YQuickDisplacementSetup)
    bpy.utils.register_class(YRemoveDisplacementSetup)

def unregister():
    bpy.utils.unregister_class(YQuickDisplacementSetup)
    bpy.utils.unregister_class(YRemoveDisplacementSetup)
