import bpy, time, re, os
from bpy.props import *
from bpy.app.handlers import persistent
from .common import *
from .subtree import *
from .node_arrangements import *
from .node_connections import *
from . import lib, Modifier, Layer, Mask, transition, Bake, ImageAtlas
from .input_outputs import *

YP_GROUP_SUFFIX = ' ' + get_addon_title()
YP_GROUP_PREFIX = get_addon_title() + ' '

channel_socket_types = {
    'RGB' : 'RGBA',
    'VALUE' : 'VALUE',
    'NORMAL' : 'VECTOR',
}

channel_socket_custom_icon_names = {
    'RGB' : 'rgb_channel',
    'VALUE' : 'value_channel',
    'NORMAL' : 'vector_channel',
}

colorspace_items = (
    ('LINEAR', 'Non-Color Data', ''),
    ('SRGB', 'Color Data', '')
)

AO_MULTIPLY = 'yP AO Multiply'

def set_input_default_value(group_node, channel, custom_value=None):
    #channel = group_node.node_tree.yp.channels[index]

    if custom_value:
        if channel.type == 'RGB' and len(custom_value) == 3:
            custom_value = (custom_value[0], custom_value[1], custom_value[2], 1)

        #group_node.inputs[channel.io_index].default_value = custom_value
        group_node.inputs[channel.name].default_value = custom_value
        return
    
    # Set default value
    if channel.type == 'RGB':
        #group_node.inputs[channel.io_index].default_value = (1,1,1,1)
        group_node.inputs[channel.name].default_value = (1,1,1,1)

    if channel.type == 'VALUE':
        #group_node.inputs[channel.io_index].default_value = 0.0
        group_node.inputs[channel.name].default_value = 0.0
    if channel.type == 'NORMAL':
        # Use 999 as normal z value so it will fallback to use geometry normal at checking process
        #group_node.inputs[channel.io_index].default_value = (999,999,999)
        group_node.inputs[channel.name].default_value = (999,999,999)

    if channel.enable_alpha:
        #group_node.inputs[channel.io_index+1].default_value = 1.0
        group_node.inputs[channel.name + io_suffix['ALPHA']].default_value = 1.0

def create_yp_channel_nodes(group_tree, channel, channel_idx):
    yp = group_tree.yp
    nodes = group_tree.nodes

    # Create linarize node and converter node
    if channel.type in {'RGB', 'VALUE'}:
        if channel.type == 'RGB':
            start_linear = new_node(group_tree, channel, 'start_linear', 'ShaderNodeGamma', 'Start Linear')
        else: 
            start_linear = new_node(group_tree, channel, 'start_linear', 'ShaderNodeMath', 'Start Linear')
            start_linear.operation = 'POWER'
        start_linear.inputs[1].default_value = 1.0/GAMMA

        if channel.type == 'RGB':
            end_linear = new_node(group_tree, channel, 'end_linear', 'ShaderNodeGamma', 'End Linear')
        else: 
            end_linear = new_node(group_tree, channel, 'end_linear', 'ShaderNodeMath', 'End Linear')
            end_linear.operation = 'POWER'
        end_linear.inputs[1].default_value = GAMMA

        check_channel_clamp(group_tree, channel)

    if channel.type == 'NORMAL':
        start_normal_filter = new_node(group_tree, channel, 'start_normal_filter', 'ShaderNodeGroup', 'Start Normal Filter')
        start_normal_filter.node_tree = get_node_tree_lib(lib.CHECK_INPUT_NORMAL)

        # Set main uv
        #obj = bpy.context.object
        #uv_layers = get_uv_layers(obj)
        #if len(uv_layers) > 0:
        #    channel.main_uv = uv_layers[0].name
        #    check_uvmap_on_other_objects_with_same_mat(obj.active_material, channel.main_uv)

    # Link between layers
    for t in yp.layers:

        # Add new channel
        c = t.channels.add()

        # Add new channel to mask
        layer_tree = get_tree(t)
        for mask in t.masks:
            mc = mask.channels.add()

        # Check and set mask intensity nodes
        transition.check_transition_bump_influences_to_other_channels(t, layer_tree, target_ch=c)

        # Set mask multiply nodes
        check_mask_mix_nodes(t, layer_tree)

        # Add new nodes
        Layer.check_all_layer_channel_io_and_nodes(t, layer_tree, specific_ch=c)

    # Check uv maps
    check_uv_nodes(yp)

def create_new_group_tree(mat):

    #ypup = bpy.context.user_preferences.addons[__name__].preferences

    # Group name is based from the material
    #group_name = mat.name + YP_GROUP_SUFFIX
    group_name = YP_GROUP_PREFIX + mat.name

    # Create new group tree
    group_tree = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')
    group_tree.yp.is_ypaint_node = True
    group_tree.yp.version = get_current_version_str()

    # Create IO nodes
    create_essential_nodes(group_tree, True, True, True)

    # Create info nodes
    create_info_nodes(group_tree)

    return group_tree

def create_new_yp_channel(group_tree, name, channel_type, non_color=True, enable=False):
    yp = group_tree.yp

    yp.halt_reconnect = True

    # Add new channel
    channel = yp.channels.add()
    channel.name = name
    channel.type = channel_type

    # Get last index
    last_index = len(yp.channels)-1

    # Link new channel
    create_yp_channel_nodes(group_tree, channel, last_index)

    for layer in yp.layers:
        # New channel is disabled in layer by default
        layer.channels[last_index].enable = enable

    if channel_type in {'RGB', 'VALUE'}:
        if non_color:
            channel.colorspace = 'LINEAR'
        else: channel.colorspace = 'SRGB'

    yp.halt_reconnect = False

    return channel

class YSelectMaterialPolygons(bpy.types.Operator):
    bl_idname = "material.y_select_all_material_polygons"
    bl_label = "Select All Material Polygons"
    bl_description = "Select all polygons using this material"
    bl_options = {'REGISTER', 'UNDO'}

    new_uv : BoolProperty(
            name = 'Create New UV',
            description = 'Create new UV rather than use available one',
            default = False)

    new_uv_name : StringProperty(
            name='New UV Name', 
            description="Name of the new uv", 
            default='UVMap')

    uv_map : StringProperty(
            name='Active UV Map', 
            description="It will create one if other objects does not have it.\nIf empty, it will use whatever current active uv map for each objects", 
            default='')

    set_canvas_to_empty : BoolProperty(
            name='Set Image Editor to empty',
            description="Set image editor & canvas image to empty, so it's easier to see",
            default=True)

    uv_map_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    @classmethod
    def poll(cls, context):
        return context.object

    def invoke(self, context, event):
        if not is_greater_than_280():
            self.execute(context)

        obj = context.object

        # Always set new uv to false to avoid unwanted new uv
        self.new_uv = False
        self.new_uv_name = get_unique_name('UVMap', get_uv_layers(obj))

        node = get_active_ypaint_node()
        if node: yp = node.node_tree.yp
        else: yp = None

        # UV Map collections update
        self.uv_map = get_default_uv_name(obj, yp)

        self.uv_map_coll.clear()
        for uv in get_uv_layers(obj):
            if not uv.name.startswith(TEMP_UV):
                self.uv_map_coll.add().name = uv.name

        return context.window_manager.invoke_props_dialog(self, width=400)

    def check(self, context):
        return True

    def draw(self, context):
        self.layout.prop(self, "new_uv")
        if self.new_uv:
            self.layout.prop(self, "new_uv_name")
        else:
            self.layout.prop_search(self, "uv_map", self, "uv_map_coll", icon='GROUP_UVS')
        self.layout.prop(self, "set_canvas_to_empty")

    def execute(self, context):
        if not is_greater_than_280():
            self.report({'ERROR'}, "This feature only works on Blender 2.8+")
            return {'CANCELLED'}

        if (self.new_uv and self.new_uv_name == '') or (not self.new_uv and self.uv_map == ''):
            self.report({'ERROR'}, "UV name cannot be empty!")
            return {'CANCELLED'}

        obj = context.object
        mat = obj.active_material

        objs = []
        for o in get_scene_objects():
            if o.type != 'MESH': continue
            if is_layer_collection_hidden(o): continue
            if mat.name in o.data.materials:
                o.select_set(True)
                objs.append(o)
            else: o.select_set(False)

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.context.tool_settings.mesh_select_mode = (False, False, True)
        bpy.ops.mesh.select_all(action='DESELECT')

        bpy.ops.object.mode_set(mode='OBJECT')

        uv_name = self.uv_map if not self.new_uv else get_unique_name(self.new_uv_name, get_uv_layers(obj))

        for o in objs:

            #if uv_name != '':
            # Get uv layer
            uv_layers = get_uv_layers(o)
            uvl = uv_layers.get(uv_name)

            # Create one if it didn't exist
            if not uvl:
                uvl = uv_layers.new(name=uv_name)
            uv_layers.active = uvl

            active_mat_id = [i for i, m in enumerate(o.data.materials) if m == mat][0]
            # Select polygons
            for p in o.data.polygons:
                if p.material_index == active_mat_id:
                    p.select = True
                else: p.select = False

        bpy.ops.object.mode_set(mode='EDIT')

        if self.set_canvas_to_empty:
            update_image_editor_image(context, None)
            context.scene.tool_settings.image_paint.canvas = None

        return {'FINISHED'}

class YRenameUVMaterial(bpy.types.Operator):
    bl_idname = "material.y_rename_uv_using_the_same_material"
    bl_label = "Rename UV that using same Material"
    bl_description = "Rename UV on objects that used the same material"
    bl_options = {'REGISTER', 'UNDO'}

    uv_map : StringProperty(
            name='Target UV Map', 
            description="Target UV Map that will be renamed", 
            default='')

    uv_map_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    new_uv_name : StringProperty(
            name='New UV Name', 
            description="New name of for the UV", 
            default='UVMap')

    @classmethod
    def poll(cls, context):
        return context.object

    def invoke(self, context, event):
        obj = context.object

        # Always set new uv to false to avoid unwanted new uv
        self.new_uv_name = get_unique_name(self.new_uv_name, get_uv_layers(obj))

        node = get_active_ypaint_node()
        if node: yp = node.node_tree.yp
        else: yp = None

        # UV Map collections update
        self.uv_map = get_default_uv_name(obj, yp)

        self.uv_map_coll.clear()
        for uv in get_uv_layers(obj):
            if not uv.name.startswith(TEMP_UV):
                self.uv_map_coll.add().name = uv.name

        return context.window_manager.invoke_props_dialog(self, width=400)

    def check(self, context):
        return True

    def draw(self, context):
        self.layout.prop_search(self, "uv_map", self, "uv_map_coll", icon='GROUP_UVS')
        self.layout.prop(self, "new_uv_name")

    def execute(self, context):
        if self.new_uv_name == '' or self.uv_map == '':
            self.report({'ERROR'}, "Name cannot be empty!")
            return {'CANCELLED'}

        obj = context.object
        mat = get_active_material()

        # Check all uv names available on all objects
        #uvls = []
        #for obj in bpy.data.objects:
        #    if obj.type == 'MESH' and any([m for m in obj.data.materials if mat == m]):
        #        for uvl in get_uv_layers(obj):
        #            if uvl not in uvls:
        #                uvls.append(uvl)

        #new_uv_name = get_unique_name(self.new_uv_name, uvls)

        new_uv_name = self.new_uv_name

        for obj in bpy.data.objects:
            if obj.type == 'MESH' and any([m for m in obj.data.materials if mat == m]):
                uv_layers = get_uv_layers(obj)
                new_uvl = uv_layers.get(new_uv_name)
                if not new_uvl:
                    uvl = uv_layers.get(self.uv_map)
                    if not uvl:
                        uvl = uv_layers.new(name=new_uv_name)
                    else:
                        uvl.name = new_uv_name

        # Dealing with yp
        node = get_active_ypaint_node()
        if node: yp = node.node_tree.yp
        else: yp = None

        if yp:
            # Check baked images uv
            if yp.baked_uv_name == self.uv_map:
                yp.baked_uv_name = new_uv_name

            # Check baked normal channel
            for ch in yp.channels:
                baked_normal = node.node_tree.nodes.get(ch.baked_normal)
                if baked_normal and baked_normal.uv_map == self.uv_map:
                    baked_normal.uv_map = new_uv_name

            # Check layer and masks uv
            for layer in yp.layers:
                if layer.uv_name == self.uv_map:
                    layer.uv_name = new_uv_name

                for mask in layer.masks:
                    if mask.uv_name == self.uv_map:
                        mask.uv_name = new_uv_name

            # Check height channel uv
            height_ch = get_root_height_channel(yp)
            if height_ch and height_ch.main_uv == self.uv_map:
                height_ch.main_uv = new_uv_name

        return {'FINISHED'}

class YQuickYPaintNodeSetup(bpy.types.Operator):
    bl_idname = "node.y_quick_ypaint_node_setup"
    bl_label = "Quick " + get_addon_title() + " Node Setup"
    bl_description = "Quick " + get_addon_title() + " Node Setup"
    bl_options = {'REGISTER', 'UNDO'}

    type : EnumProperty(
            name = 'Type',
            items = (('BSDF_PRINCIPLED', 'Principled', ''),
                     ('BSDF_DIFFUSE', 'Diffuse', ''),
                     ('EMISSION', 'Emission', ''),
                     ),
            default = 'BSDF_PRINCIPLED')
            #update=update_quick_setup_type)

    color : BoolProperty(name='Color', default=True)
    ao : BoolProperty(name='Ambient Occlusion', default=False)
    metallic : BoolProperty(name='Metallic', default=True)
    roughness : BoolProperty(name='Roughness', default=True)
    normal : BoolProperty(name='Normal', default=True)

    mute_texture_paint_overlay : BoolProperty(
            name = 'Mute Stencil Mask Opacity',
            description = 'Set Stencil Mask Opacity found in the 3D Viewport\'s Overlays menu to 0',
            default = True)

    @classmethod
    def poll(cls, context):
        return context.object

    def invoke(self, context, event):
        obj = context.object
        mat = get_active_material()

        valid_bsdf_types = ['BSDF_PRINCIPLED', 'BSDF_DIFFUSE', 'EMISSION']

        # Get target bsdf
        self.target_bsdf_name = ''
        if mat and mat.node_tree: # and is_greater_than_280():
            output = [n for n in mat.node_tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output]
            if output:
                bsdf_node = get_closest_bsdf_backward(output[0], valid_bsdf_types)
                if bsdf_node:
                    self.type = bsdf_node.type
                    self.target_bsdf_name = bsdf_node.name
                    #print(bsdf_node)

        # Normal channel does not works to non mesh object
        if obj.type != 'MESH':
            self.normal = False

        return context.window_manager.invoke_props_dialog(self)

    def check(self, context):
        return True

    def draw(self, context):
        #row = self.layout.row()
        if is_greater_than_280():
            row = self.layout.split(factor=0.35)
        else: row = self.layout.split(percentage=0.35)

        col = row.column()
        col.label(text='Type:')
        if self.type != 'EMISSION':
            ccol = col.column(align=True)
            ccol.label(text='Channels:')

            ccol.label(text='')
            if self.type == 'BSDF_PRINCIPLED':
                ccol.label(text='')
            ccol.label(text='')
            ccol.label(text='')

        col = row.column()
        col.prop(self, 'type', text='')
        if self.type != 'EMISSION':
            ccol = col.column(align=True)
            ccol.prop(self, 'color', toggle=True)
            ccol.prop(self, 'ao', toggle=True)
            if self.type == 'BSDF_PRINCIPLED':
                ccol.prop(self, 'metallic', toggle=True)
            ccol.prop(self, 'roughness', toggle=True)
            ccol.prop(self, 'normal', toggle=True)

        if is_greater_than_280():
            col.prop(self, 'mute_texture_paint_overlay')

    def execute(self, context):

        obj = context.object
        mat = get_active_material()

        if not mat:
            mat = bpy.data.materials.new(obj.name)
            mat.use_nodes = True

            if len(obj.material_slots) > 0:
                matslot = obj.material_slots[obj.active_material_index]
                matslot.material = mat
            else:
                obj.data.materials.append(mat)

            # Remove default nodes
            for n in mat.node_tree.nodes:
                mat.node_tree.nodes.remove(n)

        if not mat.node_tree:
            mat.use_nodes = True

            # Remove default nodes
            for n in mat.node_tree.nodes:
                mat.node_tree.nodes.remove(n)

        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        ao_needed = self.ao and self.type != 'EMISSION'

        main_bsdf = None
        outsoc = None
        ao_mul = None

        # If target bsdf is used as main bsdf
        target_bsdf = nodes.get(self.target_bsdf_name)
        if target_bsdf and target_bsdf.type == self.type:
            main_bsdf = target_bsdf
            for l in main_bsdf.outputs[0].links:
                outsoc = l.to_socket

        # Get active output
        output = [n for n in nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output]
        if output: 
            output = output[0]

        loc = Vector((0, 0))

        # Create new group node
        group_tree = create_new_group_tree(mat)
        node = nodes.new(type='ShaderNodeGroup')
        node.node_tree = group_tree
        node.select = True
        nodes.active = node
        mat.yp.active_ypaint_node = node.name

        # BSDF node
        if not main_bsdf:
            if self.type == 'BSDF_PRINCIPLED':
                main_bsdf = nodes.new('ShaderNodeBsdfPrincipled')
                if 'Subsurface Radius' in main_bsdf.inputs:
                    main_bsdf.inputs['Subsurface Radius'].default_value = (1.0, 0.2, 0.1) # Use eevee default value
                if 'Subsurface Color' in main_bsdf.inputs:
                    main_bsdf.inputs['Subsurface Color'].default_value = (0.8, 0.8, 0.8, 1.0) # Use eevee default value
            elif self.type == 'BSDF_DIFFUSE':
                main_bsdf = nodes.new('ShaderNodeBsdfDiffuse')
            elif self.type == 'EMISSION':
                main_bsdf = nodes.new('ShaderNodeEmission')

            if output: 
                loc = output.location.copy()
                loc.x += 200

            node.location = loc.copy()
            loc.x += 200
        else:
            loc = main_bsdf.location.copy()

            # Move away already existing nodes
            for n in mat.node_tree.nodes:

                # Skip nodes with parents
                if n.parent: continue

                if n.location.x < loc.x:
                    if ao_needed: n.location.x -= 400
                    else: n.location.x -= 200

            if ao_needed: loc.x -= 200
            loc.x -= 200

            node.location = loc.copy()
            loc.x += 200

        if ao_needed:
            ao_mul = simple_new_mix_node(mat.node_tree)
            ao_mixcol0, ao_mixcol1, ao_mixout = get_mix_color_indices(ao_mul)

            ao_mul.inputs[0].default_value = 1.0
            ao_mul.blend_type = 'MULTIPLY'
            ao_mul.label = get_addon_title() + ' AO Multiply'
            ao_mul.name = AO_MULTIPLY

            ao_mul.inputs[0].default_value = 1.0
            ao_mul.inputs[ao_mixcol0].default_value = (1.0, 1.0, 1.0, 1.0)
            ao_mul.inputs[ao_mixcol1].default_value = (1.0, 1.0, 1.0, 1.0)

            ao_mul.location = loc.copy()
            loc.x += 200

        main_bsdf.location = loc.copy()
        if main_bsdf.type == 'BSDF_PRINCIPLED' and is_greater_than_280():
            loc.x += 270
        else: loc.x += 200

        if not outsoc:
            # Blender 3.1 has bug which prevent material output changes
            if output and bpy.data.version >= (3, 1, 0) and bpy.data.version < (3, 2, 0):
                outsoc = output.inputs[0]
                output.location = loc.copy()
                loc.x += 200
            else:
                mat_out = nodes.new(type='ShaderNodeOutputMaterial')
                mat_out.is_active_output = True
                outsoc = mat_out.inputs[0]

                mat_out.location = loc.copy()
                loc.x += 200
                
                if output: 
                    output.is_active_output = False

        links.new(main_bsdf.outputs[0], outsoc)

        # Add new channels
        ch_color = None
        ch_ao = None
        ch_metallic = None
        ch_roughness = None
        ch_normal = None

        if self.color:
            ch_color = create_new_yp_channel(group_tree, 'Color', 'RGB', non_color=False)

        if self.type != 'EMISSION':
            if self.ao:
                ch_ao = create_new_yp_channel(group_tree, 'Ambient Occlusion', 'RGB', non_color=True)

            if self.type == 'BSDF_PRINCIPLED' and self.metallic:
                ch_metallic = create_new_yp_channel(group_tree, 'Metallic', 'VALUE', non_color=True)

            if self.roughness:
                ch_roughness = create_new_yp_channel(group_tree, 'Roughness', 'VALUE', non_color=True)

            if self.normal:
                ch_normal = create_new_yp_channel(group_tree, 'Normal', 'NORMAL')

        # Update io
        check_all_channel_ios(group_tree.yp)

        # HACK: Remap channel pointers, because sometimes pointers are lost at this time
        ch_color = group_tree.yp.channels.get('Color')
        ch_ao = group_tree.yp.channels.get('Ambient Occlusion')
        ch_metallic = group_tree.yp.channels.get('Metallic')
        ch_roughness = group_tree.yp.channels.get('Roughness')
        ch_normal = group_tree.yp.channels.get('Normal')

        if ch_color:
            inp = main_bsdf.inputs[0]

            # Check original link
            for l in inp.links:
                links.new(l.from_socket, node.inputs[ch_color.name])

            set_input_default_value(node, ch_color, inp.default_value)
            if ch_ao and ao_mul:
                links.new(node.outputs[ch_color.name], ao_mul.inputs[ao_mixcol0])
                links.new(node.outputs[ch_ao.name], ao_mul.inputs[ao_mixcol1])
                links.new(ao_mul.outputs[ao_mixout], inp)
            else:
                links.new(node.outputs[ch_color.name], inp)

        if ch_ao:
            set_input_default_value(node, ch_ao, (1,1,1))

        if ch_metallic:
            inp = main_bsdf.inputs['Metallic']

            # Check original link
            for l in inp.links:
                links.new(l.from_socket, node.inputs[ch_metallic.name])

            set_input_default_value(node, ch_metallic, inp.default_value)
            #links.new(node.outputs[ch_metallic.io_index], inp)
            links.new(node.outputs[ch_metallic.name], inp)

        if ch_roughness:
            inp = main_bsdf.inputs['Roughness']

            # Check original link
            for l in inp.links:
                links.new(l.from_socket, node.inputs[ch_roughness.name])

            set_input_default_value(node, ch_roughness, inp.default_value)
            #links.new(node.outputs[ch_roughness.io_index], inp)
            links.new(node.outputs[ch_roughness.name], inp)

        if ch_normal:
            inp = main_bsdf.inputs['Normal']

            # Check original link
            for l in inp.links:
                links.new(l.from_socket, node.inputs[ch_normal.name])

            set_input_default_value(node, ch_normal)
            #links.new(node.outputs[ch_normal.io_index], inp)
            links.new(node.outputs[ch_normal.name], inp)

        # Disable overlay on Blender 2.8
        if is_greater_than_280() and self.mute_texture_paint_overlay:
            screen = context.screen
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.spaces[0].overlay.texture_paint_mode_opacity = 0.0

        # Update UI
        context.window_manager.ypui.need_update = True

        return {'FINISHED'}

class YNewYPaintNode(bpy.types.Operator):
    bl_idname = "node.y_add_new_ypaint_node"
    bl_label = "Add new " + get_addon_title() + " Node"
    bl_description = "Add new " + get_addon_title() + " node"
    bl_options = {'REGISTER', 'UNDO'}

    @staticmethod
    def store_mouse_cursor(context, event):
        space = context.space_data
        tree = space.edit_tree

        # convert mouse position to the View2D for later node placement
        if context.region.type == 'WINDOW':
            # convert mouse position to the View2D for later node placement
            space.cursor_location_from_region(
                    event.mouse_region_x, event.mouse_region_y)
        else:
            space.cursor_location = tree.view_center

    @classmethod
    def poll(cls, context):
        space = context.space_data
        # needs active node editor and a tree to add nodes to
        return ((space.type == 'NODE_EDITOR') and
                space.edit_tree and not space.edit_tree.library)

    def execute(self, context):
        space = context.space_data
        tree = space.edit_tree
        mat = space.id
        ypui = context.window_manager.ypui

        # select only the new node
        for n in tree.nodes:
            n.select = False

        # Create new group tree
        group_tree = create_new_group_tree(mat)
        yp = group_tree.yp

        # Add new channel
        channel = create_new_yp_channel(group_tree, 'Color', 'RGB', non_color=False)

        # Check channel io
        check_all_channel_ios(yp)

        # Create new group node
        node = tree.nodes.new(type='ShaderNodeGroup')
        node.node_tree = group_tree

        # Select new node
        node.select = True
        tree.nodes.active = node

        # Set default input value
        set_input_default_value(node, channel)

        # Set the location of new node
        node.location = space.cursor_location

        # Update UI
        context.window_manager.ypui.need_update = True

        return {'FINISHED'}

    # Default invoke stores the mouse position to place the node correctly
    # and optionally invokes the transform operator
    def invoke(self, context, event):
        self.store_mouse_cursor(context, event)
        result = self.execute(context)

        if 'FINISHED' in result:
            # Removes the node again if transform is canceled
            bpy.ops.node.translate_attach_remove_on_cancel('INVOKE_DEFAULT')

        return result

def new_channel_items(self, context):
    items = [('VALUE', 'Value', '', lib.custom_icons[lib.channel_custom_icon_dict['VALUE']].icon_id, 0),
             ('RGB', 'RGB', '', lib.custom_icons[lib.channel_custom_icon_dict['RGB']].icon_id, 1),
             ('NORMAL', 'Normal', '', lib.custom_icons[lib.channel_custom_icon_dict['NORMAL']].icon_id, 2)]

    return items

class YPaintNodeInputCollItem(bpy.types.PropertyGroup):
    name : StringProperty(default='')
    node_name : StringProperty(default='')
    input_name : StringProperty(default='')

def update_connect_to(self, context):
    yp = get_active_ypaint_node().node_tree.yp
    item = self.input_coll.get(self.connect_to)
    if item:
        self.name = get_unique_name(item.input_name, yp.channels)

    # Emission will not use clamp by default
    if 'Emission' in self.name:
        self.use_clamp = False
    else: self.use_clamp = True

def refresh_input_coll(self, context, ch_type):
    # Refresh input names
    self.input_coll.clear()
    mat = get_active_material()
    nodes = mat.node_tree.nodes
    yp_node = get_active_ypaint_node()

    for node in nodes:
        if node == yp_node: continue
        for inp in node.inputs:
            if ch_type == 'VALUE' and inp.type != 'VALUE': continue
            elif ch_type == 'RGB' and inp.type not in {'RGBA', 'VECTOR'}: continue
            elif ch_type == 'NORMAL' and 'Normal' not in inp.name: continue
            if len(inp.links) > 0 : continue
            label = inp.name + ' (' + node.name +')'
            item = self.input_coll.add()
            item.name = label
            item.node_name = node.name
            item.input_name = inp.name

def do_alpha_setup(mat, node, channel):
    tree = mat.node_tree
    yp = node.node_tree.yp

    input_index = channel.io_index
    alpha_input = node.inputs[input_index+1]

    output_index = get_output_index(channel)
    output = node.outputs[output_index]
    alpha_output = node.outputs[output_index+1]

    # Main channel output need to be already connected
    if len(output.links) == 0:
        return

    alpha_input_connected = len(alpha_input.links) > 0
    new_nodes_created = False
    for i, l in enumerate(output.links):

        if is_valid_bsdf_node(l.to_node) or l.to_node.type == 'OUTPUT_MATERIAL':
            target_node = l.to_node
        else: target_node = get_closest_bsdf_forward(l.to_node)
        if not target_node: continue
        target_socket = None

        # Connect to alpha input if target node has one
        if 'Alpha' in target_node.inputs:
            target_socket = target_node.inputs['Alpha']

        # Search for transparent and mix bsdf
        if not target_socket and len(target_node.outputs) > 0:

            # Check if target node is mix and has transparent bsdf connected to it
            if target_node.type == 'MIX_SHADER':
                if len(target_node.inputs[1].links) > 0 and target_node.inputs[1].links[0].from_node.type == 'BSDF_TRANSPARENT':
                    target_socket = target_node.inputs[0]
                
            if not target_socket:
                # Check if node following target node is mix and has transparent bsdf connected to it
                for l in target_node.outputs[0].links:
                    if l.to_node.type == 'MIX_SHADER':
                        for n in l.to_node.inputs[1].links:
                            if n.from_node.type == 'BSDF_TRANSPARENT':
                                target_socket = l.to_node.inputs[0]

        # Create new transparent and mix bsdf if target node is BSDF
        if not target_socket and not new_nodes_created and any([o for o in target_node.outputs if o.type == 'SHADER']):
            # Shift some nodes to the right
            for n in tree.nodes:
                if n.location.x > target_node.location.x and n.location.x < target_node.location.x + 350:
                    n.location.x += 200

            mix_bsdf = tree.nodes.new('ShaderNodeMixShader')
            mix_bsdf.location = (target_node.location.x + 200, target_node.location.y)
            mix_bsdf.inputs[0].default_value = 1.0
            transp_bsdf = tree.nodes.new('ShaderNodeBsdfTransparent')
            transp_bsdf.location = (target_node.location.x, target_node.location.y + 100)

            final_sockets = []
            if len(target_node.outputs) > 0:
                final_sockets = [l.to_socket for l in target_node.outputs[0].links]
                tree.links.new(target_node.outputs[0], mix_bsdf.inputs[2])
            tree.links.new(transp_bsdf.outputs[0], mix_bsdf.inputs[1])
            target_socket = mix_bsdf.inputs[0]
            if final_sockets: 
                tree.links.new(mix_bsdf.outputs[0], final_sockets[0])

            new_nodes_created = True

        # Create new transparent and mix bsdf if target node is output material
        if not target_socket and not new_nodes_created and target_node.type == 'OUTPUT_MATERIAL':
            # Shift some nodes to the right
            for n in tree.nodes:
                if n.location.x > node.location.x and n.location.x < node.location.x + 350:
                    n.location.x += 200

            mix_bsdf = tree.nodes.new('ShaderNodeMixShader')
            mix_bsdf.location = (node.location.x + 200, node.location.y)
            mix_bsdf.inputs[0].default_value = 1.0
            transp_bsdf = tree.nodes.new('ShaderNodeBsdfTransparent')
            transp_bsdf.location = (node.location.x, node.location.y + 100)

            ori_targets = [l.to_socket for l in output.links]
            tree.links.new(output, mix_bsdf.inputs[2])
            tree.links.new(transp_bsdf.outputs[0], mix_bsdf.inputs[1])
            target_socket = mix_bsdf.inputs[0]

            for ot in ori_targets:
                tree.links.new(mix_bsdf.outputs[0], ot)

            new_nodes_created = True

        if not target_socket: continue

        if len(target_socket.links) > 0 and not alpha_input_connected:
            tree.links.new(target_socket.links[0].from_socket, alpha_input)
            alpha_input_connected = True

        tree.links.new(alpha_output, target_socket)

class YConnectYPaintChannelAlpha(bpy.types.Operator):
    bl_idname = "node.y_connect_ypaint_channel_alpha"
    bl_label = "Connect " + get_addon_title() + " Channel Alpha"
    bl_description = "Connect " + get_addon_title() + " channel alpha to other nodes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        do_alpha_setup(get_active_material(), get_active_ypaint_node(), context.channel)
        return {'FINISHED'}

class YConnectYPaintChannel(bpy.types.Operator):
    bl_idname = "node.y_connect_ypaint_channel"
    bl_label = "Connect " + get_addon_title() + " Channel"
    bl_description = "Connect " + get_addon_title() + " channel to other nodes"
    bl_options = {'REGISTER', 'UNDO'}

    connect_to : StringProperty(name='Connect To', default='') #, update=update_connect_to)
    input_coll : CollectionProperty(type=YPaintNodeInputCollItem)

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def invoke(self, context, event):
        self.channel = context.channel
        refresh_input_coll(self, context, self.channel.type)
        self.connect_to = ''

        return context.window_manager.invoke_props_dialog(self)

    def check(self, context):
        return True

    def draw(self, context):
        if is_greater_than_280():
            row = self.layout.split(factor=0.4)
        else: row = self.layout.split(percentage=0.4)

        col = row.column(align=False)
        col.label(text='Connect To:')

        col = row.column(align=False)
        col.prop_search(self, "connect_to", self, "input_coll", icon = 'NODETREE', text='')

    def execute(self, context):

        if self.connect_to == '':
            self.report({'ERROR'}, "'Connect To' is cannot be empty!")
            return {'CANCELLED'}

        mat = get_active_material()
        node = get_active_ypaint_node()

        channel = self.channel
        output_index = get_output_index(channel)

        # Connect to socket
        item = self.input_coll.get(self.connect_to)
        inp = None
        if item:
            target_node = mat.node_tree.nodes.get(item.node_name)
            inp = target_node.inputs[item.input_name]
            mat.node_tree.links.new(node.outputs[channel.name], inp)

            if channel.enable_alpha:
                do_alpha_setup(mat, node, channel)

        # Set input default value
        if inp and self.channel.type != 'NORMAL': 
            set_input_default_value(node, channel, inp.default_value)
        else: set_input_default_value(node, channel)

        return {'FINISHED'}

class YNewYPaintChannel(bpy.types.Operator):
    bl_idname = "node.y_add_new_ypaint_channel"
    bl_label = "Add new " + get_addon_title() + " Channel"
    bl_description = "Add new " + get_addon_title() + " channel"
    bl_options = {'REGISTER', 'UNDO'}

    name : StringProperty(
            name='Channel Name', 
            description = 'Name of the channel',
            default='Albedo')

    type : EnumProperty(
            name = 'Channel Type',
            items = new_channel_items)

    connect_to : StringProperty(name='Connect To', default='', update=update_connect_to)
    input_coll : CollectionProperty(type=YPaintNodeInputCollItem)

    colorspace : EnumProperty(
            name = 'Color Space',
            description = "Non color won't converted to linear first before blending",
            items = colorspace_items,
            default='LINEAR')

    use_clamp : BoolProperty(
            name='Use Clamp', 
            description = 'Use clamp of newly the channel',
            default=True)

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def invoke(self, context, event):
        group_node = get_active_ypaint_node()
        channels = group_node.node_tree.yp.channels

        if self.type == 'RGB':
            self.name = 'Color'
            self.colorspace = 'SRGB'
        elif self.type == 'VALUE':
            self.name = 'Value'
            self.colorspace = 'LINEAR'
        elif self.type == 'NORMAL':
            self.name = 'Normal'

        # Check if name already available on the list
        self.name = get_unique_name(self.name, channels)

        refresh_input_coll(self, context, self.type)
        self.connect_to = ''

        return context.window_manager.invoke_props_dialog(self)

    def check(self, context):
        return True

    def draw(self, context):
        if is_greater_than_280():
            row = self.layout.split(factor=0.4)
        else: row = self.layout.split(percentage=0.4)

        col = row.column(align=False)
        col.label(text='Name:')
        col.label(text='Connect To:')
        if self.type != 'NORMAL':
            col.label(text='Color Space:')
        if self.type != 'NORMAL': col.label(text='')

        col = row.column(align=False)
        col.prop(self, 'name', text='')
        col.prop_search(self, "connect_to", self, "input_coll", icon = 'NODETREE', text='')
                #lib.custom_icons[channel_socket_custom_icon_names[self.type]].icon_id)
        if self.type != 'NORMAL':
            col.prop(self, "colorspace", text='')
        if self.type != 'NORMAL': col.prop(self, 'use_clamp')

    def execute(self, context):

        T = time.time()

        wm = context.window_manager
        mat = get_active_material()
        node = get_active_ypaint_node()
        group_tree = node.node_tree
        yp = group_tree.yp
        channels = yp.channels

        if len(yp.channels) > 19:
            self.report({'ERROR'}, "Maximum channel possible is 20")
            return {'CANCELLED'}

        # Check if channel with same name is already available
        same_channel = [c for c in channels if c.name == self.name]
        if same_channel:
            self.report({'ERROR'}, "Channel named '" + self.name +"' is already available!")
            return {'CANCELLED'}

        # Check if normal channel already exists
        norm_channnel = [c for c in channels if c.type == 'NORMAL']
        if norm_channnel and self.type == 'NORMAL':
            self.report({'ERROR'}, "Cannot add more than one normal channel!")
            return {'CANCELLED'}

        # Create new yp channel
        channel = create_new_yp_channel(group_tree, self.name, self.type, 
                non_color=self.colorspace == 'LINEAR')

        # Update io
        check_all_channel_ios(yp)

        # Connect to other inputs
        item = self.input_coll.get(self.connect_to)
        inp = None
        if item:
            target_node = mat.node_tree.nodes.get(item.node_name)
            inp = target_node.inputs[item.input_name]
            mat.node_tree.links.new(node.outputs[channel.name], inp)

        # Set input default value
        if inp and self.type != 'NORMAL': 
            set_input_default_value(node, channel, inp.default_value)
        else: set_input_default_value(node, channel)

        # Set use clamp
        if channel.use_clamp != self.use_clamp:
            channel.use_clamp = self.use_clamp

        # Change active channel
        last_index = len(yp.channels)-1
        group_tree.yp.active_channel_index = last_index

        # Update UI
        wm.ypui.need_update = True
        print('INFO: Channel', channel.name, 'is created at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.yptimer.time = str(time.time())

        return {'FINISHED'}

class YMoveYPaintChannel(bpy.types.Operator):
    bl_idname = "node.y_move_ypaint_channel"
    bl_label = "Move " + get_addon_title() + " Channel"
    bl_description = "Move " + get_addon_title() + " channel"
    bl_options = {'REGISTER', 'UNDO'}

    direction : EnumProperty(
            name = 'Direction',
            items = (('UP', 'Up', ''),
                     ('DOWN', 'Down', '')),
            default = 'UP')

    @classmethod
    def poll(cls, context):
        group_node = get_active_ypaint_node()
        return group_node and len(group_node.node_tree.yp.channels) > 0

    def execute(self, context):
        T = time.time()

        wm = context.window_manager
        group_node = get_active_ypaint_node()
        group_tree = group_node.node_tree
        yp = group_tree.yp
        ypui = context.window_manager.ypui
        #ypup = context.user_preferences.addons[__name__].preferences

        # Get active channel
        index = yp.active_channel_index
        channel = yp.channels[index]
        num_chs = len(yp.channels)

        # Get new index
        if self.direction == 'UP' and index > 0:
            new_index = index-1
        elif self.direction == 'DOWN' and index < num_chs-1:
            new_index = index+1
        else:
            return {'CANCELLED'}

        # Swap collapse UI
        #temp_0 = getattr(ypui, 'show_channel_modifiers_' + str(index))
        #temp_1 = getattr(ypui, 'show_channel_modifiers_' + str(new_index))
        #setattr(ypui, 'show_channel_modifiers_' + str(index), temp_1)
        #setattr(ypui, 'show_channel_modifiers_' + str(new_index), temp_0)

        # Get IO index
        swap_ch = yp.channels[new_index]
        io_index = channel.io_index
        io_index_swap = swap_ch.io_index

        # Move channel
        yp.channels.move(index, new_index)
        swap_channel_fcurves(yp, index, new_index)

        # Move layer channels
        for layer in yp.layers:
            layer.channels.move(index, new_index)
            swap_layer_channel_fcurves(layer, index, new_index)

            # Move mask channels
            for mask in layer.masks:
                mask.channels.move(index, new_index)
                swap_mask_channel_fcurves(mask, index, new_index)

        # Move IO
        check_all_channel_ios(yp)

        # Set active index
        yp.active_channel_index = new_index

        # Repoint channel index
        #repoint_channel_index(yp)

        # Update UI
        wm.ypui.need_update = True
        print('INFO: Channel', channel.name, 'is moved at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.yptimer.time = str(time.time())

        return {'FINISHED'}

class YRemoveYPaintChannel(bpy.types.Operator):
    bl_idname = "node.y_remove_ypaint_channel"
    bl_label = "Remove " + get_addon_title() + " Channel"
    bl_description = "Remove " + get_addon_title() + " channel"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        group_node = get_active_ypaint_node()
        return group_node and len(group_node.node_tree.yp.channels) > 0

    def execute(self, context):
        T = time.time()

        wm = context.window_manager
        mat = get_active_material()
        group_node = get_active_ypaint_node()
        group_tree = group_node.node_tree
        yp = group_tree.yp
        ypui = context.window_manager.ypui
        #ypup = context.user_preferences.addons[__name__].preferences
        nodes = group_tree.nodes
        inputs = get_tree_inputs(group_tree)
        outputs = get_tree_outputs(group_tree)

        # Disable layer preview mode to avoid error
        ori_layer_preview_mode = yp.layer_preview_mode
        if yp.layer_preview_mode:
            yp.layer_preview_mode = False

        # Get active channel
        channel_idx = yp.active_channel_index
        channel = yp.channels[channel_idx]
        channel_name = channel.name

        # Remove channel fcurves first
        remove_channel_fcurves(channel)
        shift_channel_fcurves_up(yp, channel_idx)

        # Collapse the UI
        #setattr(ypui, 'show_channel_modifiers_' + str(channel_idx), False)

        # Delete special multiply node for Ambient Occlusion channel
        if channel.name == 'Ambient Occlusion':
            ao_node = mat.node_tree.nodes.get(AO_MULTIPLY)
            ao_mixcol0, ao_mixcol1, ao_mixout = get_mix_color_indices(ao_node)
            if ao_node: 
                #ao_node.mute = True
                socket_ins = [l.from_socket for l in ao_node.inputs[ao_mixcol0].links]
                socket_outs = [l.to_socket for l in ao_node.outputs[ao_mixout].links]

                for si in socket_ins:
                    for so in socket_outs:
                        mat.node_tree.links.new(si, so)

                mat.node_tree.nodes.remove(ao_node)

        # Disable smooth bump and parallax if any of those are active
        if channel.type == 'NORMAL':
            if channel.enable_parallax:
                channel.enable_parallax = False
            if channel.enable_smooth_bump:
                channel.enable_smooth_bump = False

        # Remove channel nodes from layers
        for layer in yp.layers:
            ch = layer.channels[channel_idx]
            ttree = get_tree(layer)

            remove_node(ttree, ch, 'source')
            remove_node(ttree, ch, 'blend')
            remove_node(ttree, ch, 'intensity')
            remove_node(ttree, ch, 'extra_alpha')

            remove_node(ttree, ch, 'disp_blend')

            remove_node(ttree, ch, 'source')
            remove_node(ttree, ch, 'linear')
            remove_node(ttree, ch, 'source_1')
            remove_node(ttree, ch, 'linear_1')
            remove_node(ttree, ch, 'flip_y')

            remove_node(ttree, ch, 'normal_process')
            remove_node(ttree, ch, 'normal_flip')
            remove_node(ttree, ch, 'mod_n')
            remove_node(ttree, ch, 'mod_s')
            remove_node(ttree, ch, 'mod_e')
            remove_node(ttree, ch, 'mod_w')
            remove_node(ttree, ch, 'spread_alpha')
            #remove_node(ttree, ch, 'spread_alpha_n')
            #remove_node(ttree, ch, 'spread_alpha_s')
            #remove_node(ttree, ch, 'spread_alpha_e')
            #remove_node(ttree, ch, 'spread_alpha_w')

            remove_node(ttree, ch, 'height_proc')
            remove_node(ttree, ch, 'height_blend')
            remove_node(ttree, ch, 'normal_proc')

            remove_node(ttree, ch, 'height_group_unpack')
            remove_node(ttree, ch, 'height_alpha_group_unpack')

            remove_node(ttree, ch, 'cache_ramp')
            remove_node(ttree, ch, 'cache_falloff_curve')

            remove_node(ttree, ch, 'cache_brick')
            remove_node(ttree, ch, 'cache_checker')
            remove_node(ttree, ch, 'cache_gradient')
            remove_node(ttree, ch, 'cache_magic')
            remove_node(ttree, ch, 'cache_musgrave')
            remove_node(ttree, ch, 'cache_noise')
            remove_node(ttree, ch, 'cache_voronoi')
            remove_node(ttree, ch, 'cache_wave')

            remove_node(ttree, ch, 'cache_image')
            remove_node(ttree, ch, 'cache_1_image')
            remove_node(ttree, ch, 'cache_vcol')
            remove_node(ttree, ch, 'cache_hemi')

            # Remove modifiers
            #if ch.mod_tree:
            if ch.mod_group != '':
                mod_group = ttree.nodes.get(ch.mod_group)
                bpy.data.node_groups.remove(mod_group.node_tree)
                ttree.nodes.remove(mod_group)
            else:
                for mod in ch.modifiers:
                    Modifier.delete_modifier_nodes(ttree, mod)

            # Remove transition bump and ramp
            if channel.type == 'NORMAL' and ch.enable_transition_bump:
                transition.remove_transition_bump_nodes(layer, ttree, ch, channel_idx)
            elif channel.type in {'RGB', 'VALUE'} and ch.enable_transition_ramp:
                transition.remove_transition_ramp_nodes(ttree, ch)

            # Remove mask channel
            Mask.remove_mask_channel(ttree, layer, channel_idx)

            # Remove layer channel
            layer.channels.remove(channel_idx)

            # Update layer ios
            Layer.check_all_layer_channel_io_and_nodes(layer, ttree) #, has_parent=has_parent)

        remove_node(group_tree, channel, 'start_linear')
        remove_node(group_tree, channel, 'end_linear')
        remove_node(group_tree, channel, 'end_backface')
        remove_node(group_tree, channel, 'end_max_height')
        remove_node(group_tree, channel, 'start_normal_filter')
        remove_node(group_tree, channel, 'baked')
        remove_node(group_tree, channel, 'baked_normal')
        remove_node(group_tree, channel, 'baked_normal_flip')
        remove_node(group_tree, channel, 'baked_normal_prep')

        for mod in channel.modifiers:
            Modifier.delete_modifier_nodes(group_tree, mod)

        # Remove channel
        yp.channels.remove(channel_idx)

        # Check consistency of mask multiply nodes
        for t in yp.layers:
            check_mask_mix_nodes(t)

        # Rearrange and reconnect nodes
        check_all_channel_ios(yp)
        #for t in yp.layers:
        #    rearrange_layer_nodes(t)
        #    reconnect_layer_nodes(t)
        #rearrange_yp_nodes(group_tree)

        # Set new active index
        if (yp.active_channel_index == len(yp.channels) and
            yp.active_channel_index > 0
            ): yp.active_channel_index -= 1

        if ori_layer_preview_mode:
            yp.layer_preview_mode = True

        # Repoint channel index
        #repoint_channel_index(yp)

        # Update UI
        wm.ypui.need_update = True
        print('INFO: Channel', channel_name, 'is moved at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.yptimer.time = str(time.time())

        return {'FINISHED'}

class YAddSimpleUVs(bpy.types.Operator):
    bl_idname = "node.y_add_simple_uvs"
    bl_label = "Add simple UVs"
    bl_description = "Add Simple UVs"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == 'MESH'

    def execute(self, context):
        obj = context.object
        mesh = obj.data

        # Add simple uvs
        old_mode = obj.mode
        bpy.ops.object.mode_set(mode='TEXTURE_PAINT')
        bpy.ops.paint.add_simple_uvs()
        bpy.ops.object.mode_set(mode=old_mode)

        return {'FINISHED'}

class YFixMissingUV(bpy.types.Operator):
    bl_idname = "node.y_fix_missing_uv"
    bl_label = "Fix missing UV"
    bl_description = "Fix missing UV"
    bl_options = {'REGISTER', 'UNDO'}

    source_uv_name : StringProperty(name='Missing UV Name', description='Missing UV Name', default='')
    target_uv_name : StringProperty(name='Target UV Name', description='Target UV Name', default='')

    uv_map_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == 'MESH'

    def invoke(self, context, event):
        mat = get_active_material()
        obj = context.object
        objs = get_all_objects_with_same_materials(mat)

        # Remapping will proceed if this flag is true
        self.need_remap = True

        # No need to remap if other objects has the uv
        for o in objs:
            uvls = get_uv_layers(o)
            if self.source_uv_name in uvls:
                self.need_remap = False
                return self.execute(context)

        self.target_uv_name = ''

        uv_layers = get_uv_layers(obj)

        # UV Map collections update
        self.uv_map_coll.clear()
        for uv in uv_layers:
            if not uv.name.startswith(TEMP_UV):
                self.uv_map_coll.add().name = uv.name

        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):

        if is_greater_than_280():
            row = self.layout.split(factor=0.5)
        else: row = self.layout.split(percentage=0.5)

        row.label(text='Remap ' + self.source_uv_name + ' to:')
        row.prop_search(self, "target_uv_name", self, "uv_map_coll", text='', icon='GROUP_UVS')

    def execute(self, context):
        mat = get_active_material()
        #obj = context.object
        objs = get_all_objects_with_same_materials(mat)
        node = get_active_ypaint_node()
        group_tree = node.node_tree
        yp = group_tree.yp

        if self.target_uv_name == '' and self.need_remap:
            self.report({'ERROR'}, "Target UV name is cannot be empty!")
            return {'CANCELLED'}

        target_uv_name = self.target_uv_name if self.need_remap else self.source_uv_name
        
        for o in objs:
            if o.type != 'MESH': continue

            uv_layers = get_uv_layers(o)

            # Get uv layer
            uv_layers = get_uv_layers(o)
            uvl = uv_layers.get(target_uv_name)

            # Create one if it didn't exist
            if not uvl:
                uvl = uv_layers.new(name=target_uv_name)
            uv_layers.active = uvl

        if self.need_remap:
            # Check baked images uv
            if yp.baked_uv_name == self.source_uv_name:
                yp.baked_uv_name = target_uv_name

            # Check baked normal channel
            for ch in yp.channels:
                baked_normal = group_tree.nodes.get(ch.baked_normal)
                if baked_normal and baked_normal.uv_map == self.source_uv_name:
                    baked_normal.uv_map = target_uv_name

            # Check layer and masks uv
            for layer in yp.layers:
                if layer.uv_name == self.source_uv_name:
                    layer.uv_name = target_uv_name

                for mask in layer.masks:
                    if mask.uv_name == self.source_uv_name:
                        mask.uv_name = target_uv_name

            # Check height channel uv
            height_ch = get_root_height_channel(yp)
            if height_ch and height_ch.main_uv == self.source_uv_name:
                height_ch.main_uv = target_uv_name
                #height_ch.enable_smooth_bump = height_ch.enable_smooth_bump

        return {'FINISHED'}

class YRenameYPaintTree(bpy.types.Operator):
    bl_idname = "node.y_rename_ypaint_tree"
    bl_label = "Rename " + get_addon_title() + " Group Name"
    bl_description = "Rename " + get_addon_title() + " Group Name"
    bl_options = {'REGISTER', 'UNDO'}

    name : StringProperty(name='New Name', description='New Name', default='')

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def invoke(self, context, event):
        node = get_active_ypaint_node()
        tree = node.node_tree

        self.name = tree.name
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, 'name')

    def execute(self, context):
        node = get_active_ypaint_node()
        tree = node.node_tree
        tree.name = self.name
        return {'FINISHED'}

class YChangeActiveYPaintNode(bpy.types.Operator):
    bl_idname = "node.y_change_active_ypaint_node"
    bl_label = "Change Active " + get_addon_title() + " Node"
    bl_description = "Change Active " + get_addon_title() + " Node"
    bl_options = {'REGISTER', 'UNDO'}

    name : StringProperty(name='Node Name', description=get_addon_title() + ' Node Name', default='')

    @classmethod
    def poll(cls, context):
        mat = get_active_material()
        return mat and mat.node_tree

    def execute(self, context):
        mat = get_active_material()

        found_it = False

        for node in mat.node_tree.nodes:
            if node.type == 'GROUP' and node.node_tree and node.node_tree.yp.is_ypaint_node and node.name == self.name:
                mat.node_tree.nodes.active = node
                found_it = True
                break

        if not found_it:
            self.report({'ERROR'}, "Node named " + self.name + " is not found!")
            return {'CANCELLED'}

        return {'FINISHED'}

class YDuplicateYPNodes(bpy.types.Operator):
    bl_idname = "node.y_duplicate_yp_nodes"
    bl_label = "Duplicate " + get_addon_title() + " Nodes"
    bl_description = get_addon_title() + " doesn't work with more than one user! Duplicate to make it single user"
    bl_options = {'REGISTER', 'UNDO'}

    duplicate_node : BoolProperty(
            name = 'Duplicate this Node',
            description = 'Duplicate this node',
            default=False)

    duplicate_material : BoolProperty(
            name = 'Also Duplicate Material',
            description = 'Also Duplicate this node parent materials',
            default=False)

    only_active : BoolProperty(
            name = 'Only Duplicate on active object',
            description = 'Only duplicate on active object, rather than all accessible objects using the same material',
            default=True)

    @classmethod
    def poll(cls, context):
        mat = get_active_material()
        group_node = get_active_ypaint_node()
        if not group_node: return False

        return True

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, 'only_active', text='Only Active Object')

    def execute(self, context):

        mat = get_active_material()
        if self.only_active:
            objs = [context.object]
        else: objs = get_all_objects_with_same_materials(mat)

        if self.duplicate_material:

            # Duplicate the material
            dup_mat = mat.copy()
            for obj in objs:
                for i, m in enumerate(obj.data.materials):
                    if m == mat:
                        obj.data.materials[i] = dup_mat

            mat = dup_mat

        if self.duplicate_material or self.duplicate_node:
            # Get to be duplicated trees
            tree_dict = {}
            for node in mat.node_tree.nodes:
                if node.type == 'GROUP' and node.node_tree and node.node_tree.yp.is_ypaint_node and node.node_tree.name not in tree_dict:
                    tree_dict[node.node_tree.name] = node
                    #node.node_tree = node.node_tree.copy()

            # Duplicate the trees
            for tree_name, node in tree_dict.items():
                tree = bpy.data.node_groups.get(tree_name)
                node.node_tree = tree.copy()

        ypui = context.window_manager.ypui
        group_node = get_active_ypaint_node()
        tree = group_node.node_tree
        yp = tree.yp

        # Make all layers single(dual) user
        #for layer in yp.layers:
        #Layer.duplicate_layer_nodes_and_images(tree, make_image_single_user=ypui.make_image_single_user)
        Layer.duplicate_layer_nodes_and_images(tree, make_image_single_user=True)

        # Duplicate uv nodes
        for uv in yp.uvs:
            tangent_process = tree.nodes.get(uv.tangent_process)
            if tangent_process and '_Copy' in tangent_process.node_tree.name: 
                tangent_process.node_tree = tangent_process.node_tree.copy()

        # Delete parallax node because it's too complicated to duplicate
        parallax = tree.nodes.get(PARALLAX)
        if parallax: tree.nodes.remove(parallax)
        baked_parallax = tree.nodes.get(BAKED_PARALLAX)
        if baked_parallax: tree.nodes.remove(baked_parallax)

        # Duplicate single user lib tree
        #for node in ttree.nodes:
        #    if (node.type == 'GROUP' and node.node_tree and 
        #            re.match(r'^.+_Copy\.*\d{0,3}$', node.node_tree.name)):
        #        node.node_tree = node.node_tree.copy()

        #if ypui.make_image_single_user:

        # Copy baked image
        for ch in yp.channels:
            baked = tree.nodes.get(ch.baked)
            if baked and baked.image:
                baked.image = baked.image.copy()

                # Also rename path because why not? NO, because it will cause image lost
                #path = baked.image.filepath
                #ext = os.path.splitext(path)[1]
                #baked.image.filepath = os.path.dirname(path) + baked.image.name + ext

            if ch.type == 'NORMAL':
                baked_disp = tree.nodes.get(ch.baked_disp)
                if baked_disp and baked_disp.image:
                    baked_disp.image = baked_disp.image.copy()

                baked_normal_overlay = tree.nodes.get(ch.baked_normal_overlay)
                if baked_normal_overlay and baked_normal_overlay.image:
                    baked_normal_overlay.image = baked_normal_overlay.image.copy()

        # Recover possibly deleted parallax
        height_root_ch = get_root_height_channel(yp)
        if height_root_ch:
            height_root_ch.enable_parallax = height_root_ch.enable_parallax

        # Refresh mapping and stuff
        yp.active_layer_index = yp.active_layer_index

        return {'FINISHED'}

def fix_missing_vcol(obj, name, src):

    ref_vcol = None

    if is_greater_than_320():
        # Try to get reference vcol
        mat = get_active_material()
        objs = get_all_objects_with_same_materials(mat)

        for o in objs:
            ovcols = get_vertex_colors(o)
            if name in ovcols:
                ref_vcol = ovcols.get(name)
                break

    if ref_vcol: vcol = new_vertex_color(obj, name, ref_vcol.data_type, ref_vcol.domain)
    else: vcol = new_vertex_color(obj, name)

    set_source_vcol_name(src, name)

    # Default recovered missing vcol is black
    set_obj_vertex_colors(obj, vcol.name, (0.0, 0.0, 0.0, 0.0))

def fix_missing_img(name, src, is_mask=False):
    img = bpy.data.images.new(name=name, 
            width=1024, height=1024, alpha= not is_mask, float_buffer=False)
    if is_mask:
        img.generated_color = (1,1,1,1)
    else: img.generated_color = (0,0,0,0)
    src.image = img

class YFixMissingData(bpy.types.Operator):
    bl_idname = "node.y_fix_missing_data"
    bl_label = "Fix Missing Data"
    bl_description = "Fix missing image/vertex color data"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def execute(self, context):
        group_node = get_active_ypaint_node()
        tree = group_node.node_tree
        yp = tree.yp
        obj = context.object
        mat = obj.active_material

        # Fix missing sources
        for i, layer in reversed(list(enumerate(yp.layers))):
            src = get_layer_source(layer)

            # Delete layer if source is not found
            if not src:
                Layer.remove_layer(yp, i)
                continue

            # Delete mask if mask source is not found
            for j, mask in reversed(list(enumerate(layer.masks))):
                mask_src = get_mask_source(mask)
                if not mask_src:
                    Mask.remove_mask(layer, mask, obj)

            # Disable override if channel source is not found
            for ch in layer.channels:
                ch_src = get_channel_source(ch, layer)
                if not ch_src:
                    if ch.override: ch.override = False
                    if ch.override_1: ch.override_1 = False

        if yp.active_layer_index > len(yp.layers):
            yp.active_layer_index = len(yp.layers)-1

        # Fix missing images
        for layer in yp.layers:
            
            if layer.type in {'IMAGE' , 'VCOL'}:
                src = get_layer_source(layer)

                if layer.type == 'IMAGE' and not src.image:
                    fix_missing_img(layer.name, src, False)

            for mask in layer.masks:
                if mask.type in {'IMAGE' , 'VCOL'}:
                    mask_src = get_mask_source(mask)

                    if mask.type == 'IMAGE' and not mask_src.image:
                        fix_missing_img(mask.name, mask_src, True)

            for i, ch in enumerate(layer.channels):
                root_ch = yp.channels[i]
                if ch.override and ch.override_type in {'IMAGE', 'VCOL'}:
                    ch_src = get_channel_source(ch, layer)

                    if ch.override_type == 'IMAGE' and not ch_src.image:
                        fix_missing_img(layer.name + ' ' + root_ch.name + ' Override', ch_src, False)

        # Get relevant objects
        objs = [obj]
        if mat.users > 1:
            for ob in get_scene_objects():
                if ob.type != 'MESH': continue
                if mat.name in ob.data.materials and ob not in objs:
                    objs.append(ob)

        # Fix missing vcols
        need_color_id_vcol = False
        ref_vcol = None

        for obj in objs:
            for layer in yp.layers:
                src = get_layer_source(layer)
                if (layer.type == 'VCOL' and obj.type == 'MESH' 
                        and not get_vcol_from_source(obj, src)):
                    fix_missing_vcol(obj, layer.name, src)

                for mask in layer.masks:
                    mask_src = get_mask_source(mask)
                    if (mask.type == 'VCOL' and obj.type == 'MESH' 
                            and not get_vcol_from_source(obj, mask_src)):
                        fix_missing_vcol(obj, mask.name, mask_src)

                    if mask.type == 'COLOR_ID':
                        need_color_id_vcol = True

                for i, ch in enumerate(layer.channels):
                    root_ch = yp.channels[i]
                    ch_src = get_channel_source(ch, layer)
                    if (ch.override and ch.override_type == 'VCOL' and obj.type == 'MESH' 
                            and not get_vcol_from_source(obj, ch_src)):
                        fix_missing_vcol(obj, layer.name + ' ' + root_ch.name, ch_src)

        # Fix missing color id missing vcol
        if need_color_id_vcol: check_colorid_vcol(objs)

        # Fix missing uvs
        check_uv_nodes(yp, generate_missings=True)

        # If there's height channel, refresh uv maps to get tangent hacks
        if is_tangent_sign_hacks_needed(yp):
            height_root_ch = get_root_height_channel(yp)
            if height_root_ch:
                for uv in yp.uvs:
                    refresh_tangent_sign_vcol(obj, uv.name)

        return {'FINISHED'}

class YRefreshTangentSignVcol(bpy.types.Operator):
    bl_idname = "node.y_refresh_tangent_sign_vcol"
    bl_label = "Refresh Tangent Sign Vertex Colors"
    bl_description = "Refresh Tangent Sign Vertex Colors to make it works on Blender 2.8"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def execute(self, context):
        group_node = get_active_ypaint_node()
        tree = group_node.node_tree
        yp = tree.yp
        obj = context.object

        for uv in yp.uvs:
            refresh_tangent_sign_vcol(obj, uv.name)

        return {'FINISHED'}

class YRemoveYPaintNode(bpy.types.Operator):
    bl_idname = "node.y_remove_yp_node"
    bl_label = "Remove " + get_addon_title() + " Node"
    bl_description = "Remove " + get_addon_title() + " node, but keep all baked channel image(s)"""
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def is_baked(self, yp=None):
        if not yp:
            group_node = get_active_ypaint_node()
            tree = group_node.node_tree
            yp = tree.yp

        return any([c.baked for c in yp.channels if c.baked != ''])

    def invoke(self, context, event):
        if self.is_baked():
            return self.execute(context)
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.label(text= "This " + get_addon_title() + " node setup isn't baked yet!")
        self.layout.label(text= "Are you sure want to delete?")

    def execute(self, context):
        mat = get_active_material()
        group_node = get_active_ypaint_node()
        tree = group_node.node_tree
        yp = tree.yp

        if self.is_baked(yp):
            if not yp.use_baked:
                yp.use_baked = True
        else:
            # Search for AO node
            if 'Ambient Occlusion' in yp.channels:
                ao_node = mat.node_tree.nodes.get(AO_MULTIPLY)
                ao_mixcol0, ao_mixcol1, ao_mixout = get_mix_color_indices(ao_node)
                if ao_node: 
                    socket_ins = [l.from_socket for l in ao_node.inputs[ao_mixcol0].links]
                    socket_outs = [l.to_socket for l in ao_node.outputs[ao_mixout].links]

                    for si in socket_ins:
                        for so in socket_outs:
                            mat.node_tree.links.new(si, so)

                    mat.node_tree.nodes.remove(ao_node)

        if self.is_baked(yp) and not yp.enable_baked_outside:
            yp.enable_baked_outside = True

        # Bye bye yp node
        simple_remove_node(mat.node_tree, group_node, True, True)

        return {'FINISHED'}

class YCleanYPCaches(bpy.types.Operator):
    bl_idname = "node.y_clean_yp_caches"
    bl_label = "Clean " + get_addon_title() + " Caches"
    bl_description = "Clean " + get_addon_title() + " caches"""
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def execute(self, context):
        node = get_active_ypaint_node()
        tree = node.node_tree
        yp = tree.yp

        for layer in yp.layers:
            layer_tree = get_tree(layer)

            for prop in dir(layer):
                if prop.startswith('cache_'):
                    remove_node(layer_tree, layer, prop)

            for ch in layer.channels:
                for prop in dir(ch):
                    if prop.startswith('cache_'):
                        remove_node(layer_tree, ch, prop)

        return {'FINISHED'}

def update_channel_name(self, context):
    T = time.time()

    wm = context.window_manager
    group_tree = self.id_data
    yp = group_tree.yp

    if yp.halt_reconnect or yp.halt_update:
        return

    input_index = self.io_index
    output_index = get_output_index(self)

    get_tree_input_by_index(group_tree, input_index).name = self.name
    get_tree_output_by_index(group_tree, output_index).name = self.name

    shift = 1
    if self.enable_alpha:
        get_tree_input_by_index(group_tree, input_index+shift).name = self.name + io_suffix['ALPHA']
        get_tree_output_by_index(group_tree, output_index+shift).name = self.name + io_suffix['ALPHA']
        shift += 1

    if self.type == 'NORMAL':
        get_tree_input_by_index(group_tree, input_index+shift).name = self.name + io_suffix['HEIGHT']
        get_tree_output_by_index(group_tree, output_index+shift).name = self.name + io_suffix['HEIGHT']

        shift += 1

        get_tree_output_by_index(group_tree, output_index+shift).name = self.name + io_suffix['MAX_HEIGHT']


    #check_all_channel_ios(yp)

    # Fix normal input
    #if self.type == 'NORMAL':
    #    mat = get_active_material()
    #    for node in mat.node_tree.nodes:
    #        if node.type == 'GROUP' and node.node_tree == group_tree:
    #            inp = node.inputs.get(self.name)
    #            inp.default_value = (999, 999, 999)

    for layer in yp.layers:
        tree = get_tree(layer)
        Layer.check_all_layer_channel_io_and_nodes(layer, tree)
        rearrange_layer_nodes(layer)
        reconnect_layer_nodes(layer)

        rearrange_layer_frame_nodes(layer, tree)
    
    rearrange_yp_frame_nodes(yp)
    rearrange_yp_nodes(group_tree)
    reconnect_yp_nodes(group_tree)

    print('INFO: Channel renamed at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
    wm.yptimer.time = str(time.time())

def get_preview(mat, output=None, advanced=False, normal_viewer=False):
    tree = mat.node_tree
    #nodes = tree.nodes

    # Search for output
    if not output:
        output = get_active_mat_output_node(tree)

    if not output: return None

    if advanced:
        if normal_viewer:
            preview, dirty = simple_replace_new_node(
                    tree, EMISSION_VIEWER, 'ShaderNodeGroup', 'Emission Viewer', 
                    lib.ADVANCED_NORMAL_EMISSION_VIEWER,
                    return_status=True, hard_replace=True)
        else:
            preview, dirty = simple_replace_new_node(
                    tree, EMISSION_VIEWER, 'ShaderNodeGroup', 'Emission Viewer', 
                    lib.ADVANCED_EMISSION_VIEWER,
                    return_status=True, hard_replace=True)
        if dirty:
            duplicate_lib_node_tree(preview)
            #preview.node_tree = preview.node_tree.copy()
            # Set blend method to alpha
            #if is_greater_than_280():
            #    blend_method = mat.blend_method
            #    mat.blend_method = 'HASHED'
            #else:
            #    blend_method = mat.game_settings.alpha_blend
            #    mat.game_settings.alpha_blend = 'ALPHA'
            #mat.yp.ori_blend_method = blend_method
    else:
        if normal_viewer:
            preview, dirty = simple_replace_new_node(
                    tree, EMISSION_VIEWER, 'ShaderNodeGroup', 'Emission Viewer', 
                    lib.NORMAL_EMISSION_VIEWER,
                    return_status=True, hard_replace=True)
        else:
            preview, dirty = simple_replace_new_node(
                    tree, EMISSION_VIEWER, 'ShaderNodeEmission', 'Emission Viewer', 
                    return_status=True)

    if dirty:
        preview.hide = True
        preview.location = (output.location.x, output.location.y + 30.0)

    if output.inputs[0].links:

        # Remember output and original bsdf
        ori_bsdf = output.inputs[0].links[0].from_node

        # Only remember original BSDF if its not the preview node itself
        if ori_bsdf != preview:
            mat.yp.ori_bsdf = ori_bsdf.name

    return preview

def set_srgb_view_transform():
    scene = bpy.context.scene

    ypup = get_user_preferences()

    # Set view transform to srgb
    if scene.yp.ori_view_transform == '' and ypup.make_preview_mode_srgb:
        scene.yp.ori_view_transform = scene.view_settings.view_transform
        if is_greater_than_280():
            scene.view_settings.view_transform = 'Standard'
        else: scene.view_settings.view_transform = 'Default'

        scene.yp.ori_display_device = scene.display_settings.display_device
        scene.display_settings.display_device = 'sRGB'

        scene.yp.ori_look = scene.view_settings.look
        scene.view_settings.look = 'None'

        scene.yp.ori_exposure = scene.view_settings.exposure
        scene.view_settings.exposure = 0.0

        scene.yp.ori_gamma = scene.view_settings.gamma
        scene.view_settings.gamma = 1.0

        scene.yp.ori_use_curve_mapping = scene.view_settings.use_curve_mapping
        scene.view_settings.use_curve_mapping = False

def remove_preview(mat, advanced=False):
    nodes = mat.node_tree.nodes
    preview = nodes.get(EMISSION_VIEWER)
    scene = bpy.context.scene

    if preview: 
        simple_remove_node(mat.node_tree, preview)
        bsdf = nodes.get(mat.yp.ori_bsdf)
        output = get_active_mat_output_node(mat.node_tree)
        mat.yp.ori_bsdf = ''

        if bsdf and output:
            mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])

        # Recover view transform
        if scene.yp.ori_view_transform != '':
            scene.view_settings.view_transform = scene.yp.ori_view_transform
            scene.yp.ori_view_transform = ''

            scene.display_settings.display_device = scene.yp.ori_display_device
            scene.view_settings.look = scene.yp.ori_look
            scene.view_settings.exposure = scene.yp.ori_exposure
            scene.view_settings.gamma = scene.yp.ori_gamma
            scene.view_settings.use_curve_mapping = scene.yp.ori_use_curve_mapping

#def update_merge_mask_mode(self, context):
#    if not self.layer_preview_mode:
#        return
#
#    try:
#        mat = bpy.context.object.active_material
#        tree = mat.node_tree
#        group_node = get_active_ypaint_node()
#        yp = group_node.node_tree.yp
#        channel = yp.channels[yp.active_channel_index]
#        layer = yp.layers[yp.active_layer_index]
#    except: return
#
#    layer_tree = get_tree(layer)

#def update_mask_preview_mode(self, context):
#    pass

def layer_preview_mode_type_items(self, context):
    #node = get_active_ypaint_node()
    #yp = node.node_tree.yp

    items = (
            ('LAYER', 'Layer', '',  lib.custom_icons['texture'].icon_id, 0),
            ('MASK', 'Mask', '', lib.custom_icons['mask'].icon_id, 1),
            ('SPECIFIC_MASK', 'Specific Mask', '', lib.custom_icons['mask'].icon_id, 2)
            )

    #for i, ch in enumerate(yp.channels):
    #    #if hasattr(lib, 'custom_icons'):
    #    if not is_greater_than_280():
    #        icon_name = lib.channel_custom_icon_dict[ch.type]
    #        items.append((str(i), ch.name, '', lib.custom_icons[icon_name].icon_id, i))
    #    else: items.append((str(i), ch.name, '', lib.channel_icon_dict[ch.type], i))

    ##if hasattr(lib, 'custom_icons'):
    #if not is_greater_than_280():
    #    items.append(('-1', 'All Channels', '', lib.custom_icons['channels'].icon_id, len(items)))
    #else: items.append(('-1', 'All Channels', '', 'GROUP_VERTEX', len(items)))

    return items

def update_layer_preview_mode(self, context):
    yp = self
    mat = get_active_material()

    if is_yp_on_material(yp, mat):
        group_node = get_active_ypaint_node()
    else:
        mats = get_materials_using_yp(yp)
        if not mats: return
        mat = mats[0]
        group_nodes = get_nodes_using_yp(mat, yp)
        if not group_nodes: return
        group_node = group_nodes[0]

    tree = mat.node_tree
    index = yp.active_channel_index
    channel = yp.channels[index]
    layer = yp.layers[yp.active_layer_index]

    if yp.preview_mode and yp.layer_preview_mode:
        yp.preview_mode = False

    check_all_channel_ios(yp)

    # Get preview node
    if yp.layer_preview_mode:

        # Set view transform to srgb so color picker won't pick wrong color
        set_srgb_view_transform()

        output = get_active_mat_output_node(mat.node_tree)
        if yp.layer_preview_mode_type in {'ALPHA', 'SPECIFIC_MASK'}:
            preview = get_preview(mat, output, False)
            if not preview: return

            tree.links.new(group_node.outputs[LAYER_ALPHA_VIEWER], preview.inputs[0])
            tree.links.new(preview.outputs[0], output.inputs[0])

        else:
            if channel.type == 'NORMAL':
                preview = get_preview(mat, output, True, True)
            else:
                preview = get_preview(mat, output, True)
            if not preview: return

            tree.links.new(group_node.outputs[LAYER_VIEWER], preview.inputs[0])
            tree.links.new(group_node.outputs[LAYER_ALPHA_VIEWER], preview.inputs[1])
            tree.links.new(preview.outputs[0], output.inputs[0])

            # Set gamma
            if 'Gamma' in preview.inputs:
                if channel.colorspace != 'LINEAR':
                    preview.inputs['Gamma'].default_value = 2.2
                else: preview.inputs['Gamma'].default_value = 1.0

            # Set channel layer blending
            ch = layer.channels[yp.active_channel_index]
            #mix = preview.node_tree.nodes.get('Mix')
            #mix.blend_type = ch.blend_type
            update_preview_mix(ch, preview)

            # Use different grid if channel is not enabled
            preview.inputs['Missing Data'].default_value = 1.0 if (not ch.enable or not layer.enable) else 0.0

    else:
        remove_preview(mat)

def update_preview_mode(self, context):
    yp = self
    mat = get_active_material()

    if is_yp_on_material(yp, mat):
        group_node = get_active_ypaint_node()
    else:
        mats = get_materials_using_yp(yp)
        if not mats: return
        mat = mats[0]
        group_nodes = get_nodes_using_yp(mat, yp)
        if not group_nodes: return
        group_node = group_nodes[0]

    tree = mat.node_tree
    index = yp.active_channel_index
    channel = yp.channels[index]

    if yp.layer_preview_mode and yp.preview_mode:
        yp.layer_preview_mode = False

    if self.preview_mode:
        # Set view transform to srgb so color picker won't pick wrong color
        set_srgb_view_transform()

        output = get_active_mat_output_node(mat.node_tree)

        # Get preview node by name first
        preview = mat.node_tree.nodes.get(EMISSION_VIEWER)

        # Try to get socket that connected to preview first input
        if preview:
            from_socket = [link.from_socket for link in preview.inputs[0].links]
            if from_socket: from_socket = from_socket[0]
        else: from_socket = None

        # Check if there's any valid socket connected to first input of preview node
        is_from_socket_missing = not from_socket or (from_socket and not from_socket.name.startswith(channel.name))

        # Get all outputs from current channel
        outs = [o for o in group_node.outputs if o.name.startswith(channel.name)]

        # Use special preview for normal
        if channel.type == 'NORMAL' and (is_from_socket_missing or (from_socket and from_socket == outs[-1])):
            preview = get_preview(mat, output, False, True)
        else: preview = get_preview(mat, output, False)

        # Preview should exists by now
        if not preview: return

        if is_from_socket_missing:
            # Connect first output
            tree.links.new(group_node.outputs[channel.name], preview.inputs[0])
        else:
            # Cycle outputs
            for i, o in enumerate(outs):
                if o == from_socket:
                    if i != len(outs)-1:
                        tree.links.new(outs[i+1], preview.inputs[0])
                    else: tree.links.new(outs[0], preview.inputs[0])

        tree.links.new(preview.outputs[0], output.inputs[0])
    else:
        remove_preview(mat)

def update_active_yp_channel(self, context):
    obj = context.object
    tree = self.id_data
    yp = tree.yp
    ch = yp.channels[yp.active_channel_index]

    if yp.preview_mode: update_preview_mode(yp, context)
    if yp.layer_preview_mode: update_layer_preview_mode(yp, context)

    if yp.use_baked:
        baked = tree.nodes.get(ch.baked)
        if baked and baked.image:
            baked_image = baked.image
            if ch.type == 'NORMAL':

                baked_disp = tree.nodes.get(ch.baked_disp)
                baked_normal_overlay = tree.nodes.get(ch.baked_normal_overlay)

                if baked_disp:
                    cur_image = get_first_image_editor_image(context)
                    if cur_image == baked.image and baked_disp.image:
                        baked_image = baked_disp.image
                    elif cur_image == baked_disp.image and baked_normal_overlay and baked_normal_overlay.image:
                        baked_image = baked_normal_overlay.image

            update_image_editor_image(context, baked_image)
            context.scene.tool_settings.image_paint.canvas = baked_image
        else:
            update_image_editor_image(context, None)
            context.scene.tool_settings.image_paint.canvas = None

        if obj.type == 'MESH':
            uv_layers = get_uv_layers(obj)

            baked_uv_map = uv_layers.get(yp.baked_uv_name)
            if baked_uv_map: 
                uv_layers.active = baked_uv_map
                baked_uv_map.active_render = True

def update_layer_index(self, context):
    #T = time.time()
    scene = context.scene
    if hasattr(bpy.context, 'object'): obj = bpy.context.object
    elif is_greater_than_280(): obj = bpy.context.view_layer.objects.active
    if not obj: return
    group_tree = self.id_data
    nodes = group_tree.nodes
    ypui = context.window_manager.ypui

    yp = self

    if (len(yp.layers) == 0 or yp.active_layer_index >= len(yp.layers) or yp.active_layer_index < 0): 
        update_tool_canvas_image(context, None)
        return

    if yp.layer_preview_mode: update_layer_preview_mode(yp, context)

    # Set image paint mode to Image
    scene.tool_settings.image_paint.mode = 'IMAGE'

    # Get active image
    image, uv_name, src_of_img, mapping, vcol = get_active_image_and_stuffs(obj, yp)

    update_tool_canvas_image(context, image)

    # Update active vertex color
    if vcol and get_active_vertex_color(obj) != vcol:
        set_active_vertex_color(obj, vcol)

    mat = get_active_material()
    objs = get_all_objects_with_same_materials(mat, selected_only=True)
    for ob in objs:
        refresh_temp_uv(ob, src_of_img)

    update_image_editor_image(context, image)

def update_channel_colorspace(self, context):
    group_tree = self.id_data
    yp = group_tree.yp
    nodes = group_tree.nodes

    start_linear = nodes.get(self.start_linear)
    end_linear = nodes.get(self.end_linear)

    #start_linear.mute = end_linear.mute = self.colorspace == 'LINEAR'
    if self.colorspace == 'LINEAR':
        start_linear.inputs[1].default_value = end_linear.inputs[1].default_value = 1.0
    else: 
        start_linear.inputs[1].default_value = 1.0/GAMMA
        end_linear.inputs[1].default_value = GAMMA

    # Check for modifier that aware of colorspace
    channel_index = -1
    for i, c in enumerate(yp.channels):
        if c == self:
            channel_index = i
            for mod in c.modifiers:

                if mod.type == 'RGB_TO_INTENSITY':
                    rgb2i = nodes.get(mod.rgb2i)
                    if self.colorspace == 'LINEAR':
                        rgb2i.inputs['Gamma'].default_value = 1.0
                    else: rgb2i.inputs['Gamma'].default_value = 1.0/GAMMA

                if mod.type == 'COLOR_RAMP':

                    color_ramp_linear_start = nodes.get(mod.color_ramp_linear_start)
                    if color_ramp_linear_start:
                        if self.colorspace == 'SRGB':
                            color_ramp_linear_start.inputs[1].default_value = GAMMA
                        else: color_ramp_linear_start.inputs[1].default_value = 1.0

                    color_ramp_linear = nodes.get(mod.color_ramp_linear)
                    if color_ramp_linear:
                        if self.colorspace == 'SRGB':
                            color_ramp_linear.inputs[1].default_value = 1.0/GAMMA
                        else: color_ramp_linear.inputs[1].default_value = 1.0

    for layer in yp.layers:
        ch = layer.channels[channel_index]
        tree = get_tree(layer)

        #Layer.set_layer_channel_linear_node(tree, layer, self, ch)
        check_layer_channel_linear_node(ch, layer, self, reconnect=True)

        # Check for linear node
        #linear = tree.nodes.get(ch.linear)
        #if linear:
        #    if self.colorspace == 'LINEAR':
        #        #ch.layer_input = 'RGB_LINEAR'
        #        linear.inputs[1].default_value = 1.0
        #    else: linear.inputs[1].default_value = 1.0/GAMMA

        # NOTE: STILL BUGGY AS HELL
        #if self.colorspace == 'LINEAR':
        #    if ch.layer_input == 'RGB_SRGB':
        #        ch.layer_input = 'RGB_LINEAR'
        #    elif ch.layer_input == 'CUSTOM':
        #        ch.layer_input = 'CUSTOM'

        # Change modifier colorspace only on image layer
        if layer.type == 'IMAGE':
            mod_tree = get_mod_tree(layer)

            for mod in layer.modifiers:

                if mod.type == 'RGB_TO_INTENSITY':
                    rgb2i = mod_tree.nodes.get(mod.rgb2i)
                    if self.colorspace == 'LINEAR':
                        rgb2i.inputs['Gamma'].default_value = 1.0
                    else: rgb2i.inputs['Gamma'].default_value = 1.0/GAMMA

                if mod.type == 'OVERRIDE_COLOR':
                    oc = mod_tree.nodes.get(mod.oc)
                    if self.colorspace == 'LINEAR':
                        oc.inputs['Gamma'].default_value = 1.0
                    else: oc.inputs['Gamma'].default_value = 1.0/GAMMA

                if mod.type == 'COLOR_RAMP':

                    color_ramp_linear_start = mod_tree.nodes.get(mod.color_ramp_linear_start)
                    if color_ramp_linear_start:
                        if self.colorspace == 'SRGB':
                            color_ramp_linear_start.inputs[1].default_value = GAMMA
                        else: color_ramp_linear_start.inputs[1].default_value = 1.0

                    color_ramp_linear = mod_tree.nodes.get(mod.color_ramp_linear)
                    if color_ramp_linear:
                        if self.colorspace == 'SRGB':
                            color_ramp_linear.inputs[1].default_value = 1.0/GAMMA
                        else: color_ramp_linear.inputs[1].default_value = 1.0

        if ch.enable_transition_ramp:
            tr_ramp = tree.nodes.get(ch.tr_ramp)
            if tr_ramp:
                if self.colorspace == 'SRGB':
                    tr_ramp.inputs['Gamma'].default_value = 1.0/GAMMA
                else: tr_ramp.inputs['Gamma'].default_value = 1.0

        if ch.enable_transition_ao:
            tao = tree.nodes.get(ch.tao)
            if tao:
                if self.colorspace == 'SRGB':
                    tao.inputs['Gamma'].default_value = 1.0/GAMMA
                else: tao.inputs['Gamma'].default_value = 1.0

        for mod in ch.modifiers:

            if mod.type == 'RGB_TO_INTENSITY':
                rgb2i = tree.nodes.get(mod.rgb2i)
                if self.colorspace == 'LINEAR':
                    rgb2i.inputs['Gamma'].default_value = 1.0
                else: rgb2i.inputs['Gamma'].default_value = 1.0/GAMMA

            if mod.type == 'OVERRIDE_COLOR':
                oc = tree.nodes.get(mod.oc)
                if self.colorspace == 'LINEAR':
                    oc.inputs['Gamma'].default_value = 1.0
                else: oc.inputs['Gamma'].default_value = 1.0/GAMMA

            if mod.type == 'COLOR_RAMP':

                color_ramp_linear_start = tree.nodes.get(mod.color_ramp_linear_start)
                if color_ramp_linear_start:
                    if self.colorspace == 'SRGB':
                        color_ramp_linear_start.inputs[1].default_value = GAMMA
                    else: color_ramp_linear_start.inputs[1].default_value = 1.0

                color_ramp_linear = tree.nodes.get(mod.color_ramp_linear)
                if color_ramp_linear:
                    if self.colorspace == 'SRGB':
                        color_ramp_linear.inputs[1].default_value = 1.0/GAMMA
                    else: color_ramp_linear.inputs[1].default_value = 1.0

def update_enable_smooth_bump(self, context):
    yp = self.id_data.yp

    # Update channel io
    check_all_channel_ios(yp)

    # Clean unused libraries
    lib.clean_unused_libraries()

def update_channel_parallax(self, context):
    yp = self.id_data.yp

    # Update channel io
    check_all_channel_ios(yp)

#def update_displacement_height_ratio(self, context):
#
#    group_tree = self.id_data
#    yp = group_tree.yp
#
#    max_height = self.displacement_height_ratio
#
#    baked_parallax = group_tree.nodes.get(BAKED_PARALLAX)
#    if baked_parallax:
#        baked_parallax.inputs['depth_scale'].default_value = max_height
#
#    parallax = group_tree.nodes.get(PARALLAX)
#    if parallax:
#        depth_source_0 = parallax.node_tree.nodes.get('_depth_source_0')
#        if depth_source_0:
#            pack = depth_source_0.node_tree.nodes.get('_normalize')
#            if pack:
#                if max_height != 0.0:
#                    pack.inputs['Max Height'].default_value = max_height
#                else: pack.inputs['Max Height'].default_value = 1.0
#
#        end_linear = group_tree.nodes.get(self.end_linear)
#        if end_linear:
#            if max_height != 0.0:
#                end_linear.inputs['Max Height'].default_value = max_height
#            else: end_linear.inputs['Max Height'].default_value = 1.0
#
#            if self.enable_smooth_bump:
#                end_linear.inputs['Bump Height Scale'].default_value = get_fine_bump_distance(max_height)
#
#    for uv in yp.uvs:
#        parallax_prep = group_tree.nodes.get(uv.parallax_prep)
#        if parallax_prep:
#            parallax_prep.inputs['depth_scale'].default_value = max_height

#def update_parallax_samples(self, context):
#    group_tree = self.id_data
#    yp = group_tree.yp
#
#    parallax = group_tree.nodes.get(BAKED_PARALLAX)
#    if parallax:
#        set_relief_mapping_nodes(yp, parallax)
#
#        rearrange_relief_mapping_nodes(group_tree)
#        reconnect_relief_mapping_nodes(yp, parallax)

def update_parallax_rim_hack(self, context):
    group_tree = self.id_data
    yp = group_tree.yp

    #parallax = group_tree.nodes.get(BAKED_PARALLAX)
    #if parallax:
    #    try:
    #        parallax.inputs['Rim Hack'].default_value = 1.0 if self.parallax_rim_hack else 0.0
    #        parallax.inputs['Rim Hack Hardness'].default_value = self.parallax_rim_hack_hardness
    #    except: pass

    for uv in yp.uvs:
        parallax_prep = group_tree.nodes.get(uv.parallax_prep)
        if parallax_prep:
            parallax_prep.inputs['Rim Hack'].default_value = 1.0 if self.parallax_rim_hack else 0.0
            parallax_prep.inputs['Rim Hack Hardness'].default_value = self.parallax_rim_hack_hardness

def update_parallax_height_tweak(self, context):
    group_tree = self.id_data
    yp = group_tree.yp

    for uv in yp.uvs:
        parallax_prep = group_tree.nodes.get(uv.parallax_prep)
        if parallax_prep:
            parallax_prep.inputs['depth_scale'].default_value = get_displacement_max_height(self) * self.parallax_height_tweak

def update_parallax_num_of_layers(self, context):

    group_tree = self.id_data
    yp = group_tree.yp

    # Baked parallax
    #baked_parallax = group_tree.nodes.get(BAKED_PARALLAX)
    #if baked_parallax:
    #    set_baked_parallax_node(yp, baked_parallax)

    #    rearrange_parallax_layer_nodes(yp, baked_parallax)
    #    reconnect_baked_parallax_layer_nodes(yp, baked_parallax)

    if yp.use_baked:

        num_of_layers = int(self.baked_parallax_num_of_layers)

        baked_parallax = group_tree.nodes.get(BAKED_PARALLAX)
        if baked_parallax:
            loop = baked_parallax.node_tree.nodes.get('_parallax_loop')
            #create_delete_iterate_nodes(loop.node_tree, num_of_layers)
            #create_delete_iterate_nodes_(loop.node_tree, num_of_layers)
            create_delete_iterate_nodes__(loop.node_tree, num_of_layers)

            #rearrange_parallax_layer_nodes(yp, baked_parallax)
            #reconnect_parallax_layer_nodes(group_tree, baked_parallax, yp.baked_uv_name)
            rearrange_parallax_layer_nodes_(yp, baked_parallax)
            reconnect_parallax_layer_nodes__(group_tree, baked_parallax, yp.baked_uv_name)

            baked_parallax.inputs['layer_depth'].default_value = 1.0 / num_of_layers

    else:

        num_of_layers = int(self.parallax_num_of_layers)

        # Parallax
        parallax = group_tree.nodes.get(PARALLAX)
        if parallax:
            loop = parallax.node_tree.nodes.get('_parallax_loop')
            #create_delete_iterate_nodes(loop.node_tree, num_of_layers)
            #create_delete_iterate_nodes_(loop.node_tree, num_of_layers)
            create_delete_iterate_nodes__(loop.node_tree, num_of_layers)

            #rearrange_parallax_layer_nodes(yp, parallax)
            #reconnect_parallax_layer_nodes(group_tree, parallax)
            rearrange_parallax_layer_nodes_(yp, parallax)
            reconnect_parallax_layer_nodes__(group_tree, parallax)

            parallax.inputs['layer_depth'].default_value = 1.0 / num_of_layers

    for uv in yp.uvs:
        parallax_prep = group_tree.nodes.get(uv.parallax_prep)
        if parallax_prep:
            parallax_prep.inputs['layer_depth'].default_value = 1.0 / num_of_layers

def update_displacement_ref_plane(self, context):
    group_tree = self.id_data
    yp = group_tree.yp

    for uv in yp.uvs:
        parallax_prep = group_tree.nodes.get(uv.parallax_prep)
        if parallax_prep:
            parallax_prep.inputs['ref_plane'].default_value = self.parallax_ref_plane

def update_channel_alpha(self, context):
    mat = get_active_material()
    group_tree = self.id_data
    yp = group_tree.yp
    nodes = group_tree.nodes
    inputs = get_tree_inputs(group_tree)
    outputs = get_tree_outputs(group_tree)

    # Baked outside nodes
    frame = get_node(mat.node_tree, yp.baked_outside_frame)
    tex = get_node(mat.node_tree, self.baked_outside, parent=frame)

    # Check any alpha channels
    alpha_chs = []
    for ch in yp.channels:
        if ch.enable_alpha:
            alpha_chs.append(ch)

    if not self.enable_alpha:

        if not any(alpha_chs):
            # Set material to use opaque
            if is_greater_than_280():
                mat.blend_method = 'OPAQUE'
                mat.shadow_method = 'OPAQUE'
            else:
                mat.game_settings.alpha_blend = 'OPAQUE'

        node = get_active_ypaint_node()
        inp = node.inputs[self.io_index+1]

        if yp.use_baked and yp.enable_baked_outside and tex:
            outp = tex.outputs[1]
        else:
            outp = node.outputs[self.io_index+1]

        # Remember the connections
        if len(inp.links) > 0:
            self.ori_alpha_from.node = inp.links[0].from_node.name
            self.ori_alpha_from.socket = inp.links[0].from_socket.name
        for link in outp.links:
            con = self.ori_alpha_to.add()
            con.node = link.to_node.name
            con.socket = link.to_socket.name

        # Remove connection for baked outside
        if yp.use_baked and yp.enable_baked_outside and tex:
            for l in outp.links:
                mat.node_tree.links.remove(link)

        # Try to reconnect input to output
        fn = mat.node_tree.nodes.get(self.ori_alpha_from.node)
        if fn:
            fs = fn.outputs.get(self.ori_alpha_from.socket)
            if fs:
                for oat in self.ori_alpha_to:
                    n = mat.node_tree.nodes.get(oat.node)
                    if not n: continue
                    s = n.inputs.get(oat.socket)
                    if not s: continue

                    mat.node_tree.links.new(fs, s)

    # Update channel io
    check_all_channel_ios(yp)

    if self.enable_alpha:

        if any(alpha_chs):
            # Set material to use alpha blend
            if is_greater_than_280():
                mat.blend_method = self.alpha_blend_mode
                mat.shadow_method = self.alpha_shadow_mode
            else:
                mat.game_settings.alpha_blend = 'ALPHA'

        # Get alpha index
        #alpha_index = self.io_index+1
        alpha_name = self.name + io_suffix['ALPHA']

        # Set node default_value
        node = get_active_ypaint_node()
        node.inputs[alpha_name].default_value = 0.0

        alpha_connected = False

        # Try to relink to original connections
        #tree = context.object.active_material.node_tree
        tree = mat.node_tree
        try:
            node_from = tree.nodes.get(self.ori_alpha_from.node)
            socket_from = node_from.outputs[self.ori_alpha_from.socket]
            tree.links.new(socket_from, node.inputs[alpha_name])
        except: pass

        for con in self.ori_alpha_to:
            node_to = tree.nodes.get(con.node)
            if not node_to: continue
            socket_to = node_to.inputs.get(con.socket)
            if not socket_to: continue
            if len(socket_to.links) < 1:
                if yp.use_baked and yp.enable_baked_outside and tex:
                    mat.node_tree.links.new(tex.outputs[1], socket_to)
                else:
                    tree.links.new(node.outputs[alpha_name], socket_to)
                alpha_connected = True

        # Try to connect alpha without prior memory
        if yp.alpha_auto_setup and not alpha_connected:
            do_alpha_setup(mat, node, self)

        # Reset memory
        self.ori_alpha_from.node = ''
        self.ori_alpha_from.socket = ''
        self.ori_alpha_to.clear()

    yp.refresh_tree = True

def update_channel_alpha_blend_mode(self, context):
    mat = get_active_material()
    group_tree = self.id_data
    yp = group_tree.yp

    if not self.enable_alpha or not is_greater_than_280(): return

    # Set material alpha blend
    mat.blend_method = self.alpha_blend_mode
    mat.shadow_method = self.alpha_shadow_mode

#def update_disable_quick_toggle(self, context):
#    yp = self
#
#    for layer in yp.layers:
#        Layer.update_layer_enable(layer, context)
#
#        for mod in layer.modifiers:
#            Modifier.update_modifier_enable(mod, context)
#
#        for ch in layer.channels:
#            for mod in ch.modifiers:
#                Modifier.update_modifier_enable(mod, context)
#
#        for mask in layer.masks:
#            Mask.update_layer_mask_enable(mask, context)
#
#    for ch in yp.channels:
#        for mod in ch.modifiers:
#            Modifier.update_modifier_enable(mod, context)

def update_flip_backface(self, context):

    yp = self
    group_tree = yp.id_data

    for ch in yp.channels:
        baked_normal_flip = group_tree.nodes.get(ch.baked_normal_flip)
        if baked_normal_flip:
            set_normal_backface_flip(baked_normal_flip, yp.enable_backface_always_up)

        baked_normal_prep = group_tree.nodes.get(ch.baked_normal_prep)
        if baked_normal_prep:
            baked_normal_prep.inputs['Backface Always Up'].default_value = 1.0 if yp.enable_backface_always_up else 0.0

    for uv in yp.uvs:
        #tangent_flip = group_tree.nodes.get(uv.tangent_flip)
        #if tangent_flip:
        #    set_tangent_backface_flip(tangent_flip, yp.enable_backface_always_up)

        #bitangent_flip = group_tree.nodes.get(uv.bitangent_flip)
        #if bitangent_flip:
        #    set_bitangent_backface_flip(bitangent_flip, yp.enable_backface_always_up)

        tangent_process = group_tree.nodes.get(uv.tangent_process)
        if tangent_process:
            tangent_process.inputs['Backface Always Up'].default_value = 1.0 if yp.enable_backface_always_up else 0.0

def update_channel_use_clamp(self, context):

    if self.type == 'NORMAL': return

    group_tree = self.id_data
    check_channel_clamp(group_tree, self)

    rearrange_yp_nodes(group_tree)
    reconnect_yp_nodes(group_tree)

def update_channel_disable_global_baked(self, context):
    group_tree = self.id_data

    rearrange_yp_nodes(group_tree)
    reconnect_yp_nodes(group_tree)

def update_backface_mode(self, context):
    yp = self.id_data.yp

    check_all_channel_ios(yp)

def update_channel_main_uv(self, context):
    yp = self.id_data.yp

    if self.main_uv in {TEMP_UV, ''}:
        if len(yp.uvs) > 0:
            for uv in yp.uvs:
                self.main_uv = uv.name
                break

    if self.type == 'NORMAL':
        self.enable_smooth_bump = self.enable_smooth_bump

#def update_col_input(self, context):
#    group_node = get_active_ypaint_node()
#    group_tree = group_node.node_tree
#    yp = group_tree.yp
#
#    #if yp.halt_update: return
#    if self.type != 'RGB': return
#
#    group_node.inputs[self.io_index].default_value = self.col_input
#
#    # Get start
#    start_linear = group_tree.nodes.get(self.start_linear)
#    if start_linear: start_linear.inputs[0].default_value = self.col_input

#def update_val_input(self, context):
#    group_node = get_active_ypaint_node()
#    group_tree = group_node.node_tree
#    yp = group_tree.yp
#
#    #if yp.halt_update: return
#    if self.type == 'VALUE':
#        group_node.inputs[self.io_index].default_value = self.val_input
#
#        # Get start
#        start_linear = group_tree.nodes.get(self.start_linear)
#        if start_linear: start_linear.inputs[0].default_value = self.val_input
#
#    elif self.enable_alpha and self.type == 'RGB':
#        group_node.inputs[self.io_index+1].default_value = self.val_input
#
#        # Get index
#        m = re.match(r'yp\.channels\[(\d+)\]', self.path_from_id())
#        ch_index = int(m.group(1))
#
#        blend_found = False
#        for layer in yp.layers:
#            for i, ch in enumerate(layer.channels):
#                if i == ch_index:
#                    tree = get_tree(layer)
#                    blend = tree.nodes.get(ch.blend)
#                    if blend and blend.type =='GROUP':
#                        inp = blend.node_tree.nodes.get('Group Input')
#                        inp.outputs['Alpha1'].links[0].to_socket.default_value = self.val_input
#                        blend_found = True
#                        break
#            if blend_found: break
#
#        # In case blend_found isn't found
#        for link in group_node.outputs[self.io_index+1].links:
#            link.to_socket.default_value = self.val_input

class YNodeConnections(bpy.types.PropertyGroup):
    node : StringProperty(default='')
    socket : StringProperty(default='')
    socket_index : IntProperty(default=-1)

class YPaintChannel(bpy.types.PropertyGroup):
    name : StringProperty(
            name='Channel Name', 
            description = 'Name of the channel',
            default='Albedo',
            update=update_channel_name)

    type : EnumProperty(
            name = 'Channel Type',
            items = (('VALUE', 'Value', ''),
                     ('RGB', 'RGB', ''),
                     ('NORMAL', 'Normal', '')),
            default = 'RGB')

    enable_smooth_bump : BoolProperty(
            name = 'Enable Smooth Bump',
            description = 'Enable smooth bump map.\nLooks better but bump height scaling will be different than standard bump map.\nSmooth bump map -> Texture space.\nStandard bump map -> World space',
            default=True,
            update=update_enable_smooth_bump)

    use_clamp : BoolProperty(
            name = 'Use Clamp',
            description = 'Clamp result to 0..1 range',
            default = True,
            update=update_channel_use_clamp)

    # Input output index
    io_index : IntProperty(default=-1)

    # Alpha for transparent materials
    enable_alpha : BoolProperty(
            name = 'Enable Alpha Blend on Channel',
            description = 'Enable alpha blend on channel',
            default=False, update=update_channel_alpha)

    alpha_blend_mode : EnumProperty(
            name = 'Alpha Blend Mode',
            description = 'This will change your material blend mode if alpha is enabled',
            items = (
                ('CLIP', 'Alpha Clip', ''),
                ('HASHED', 'Alpha Hashed', ''),
                ('BLEND', 'Alpha Blend', ''),
                ),
            default = 'HASHED',
            update=update_channel_alpha_blend_mode
            )

    alpha_shadow_mode : EnumProperty(
            name = 'Alpha Shadow Mode',
            description = 'This will change your material shadow mode if alpha is enabled',
            items = (
                ('NONE', 'None', ''),
                ('OPAQUE', 'Opaque', ''),
                ('HASHED', 'Alpha Hashed', ''),
                ('CLIP', 'Alpha Clip', ''),
                ),
            default = 'HASHED',
            update=update_channel_alpha_blend_mode
            )

    # Backface mode for alpha
    backface_mode : EnumProperty(
            name = 'Backface Mode',
            description = 'Backface mode',
            items = (
                ('BOTH', 'Both', ''),
                ('FRONT_ONLY', 'Front Only / Backface Culling', ''),
                ('BACK_ONLY', 'Back Only', ''),
                ),
            default = 'BOTH', update=update_backface_mode)

    # Displacement for normal channel
    enable_parallax : BoolProperty(
            name = 'Enable Parallax Mapping',
            description = 'Enable Parallax Mapping.\nIt will use texture space scaling, so it may looks different when using it as real displacement map',
            default=False, update=update_channel_parallax)

    #parallax_num_of_layers : IntProperty(default=8, min=4, max=128,
    #        update=update_parallax_num_of_layers)
    parallax_num_of_layers : EnumProperty(
            name = 'Parallax Mapping Number of Layers',
            description = 'Parallax Mapping Number of Layers',
            items = (('4', '4', ''),
                     ('8', '8', ''),
                     ('16', '16', ''),
                     ('24', '24', ''),
                     ('32', '32', ''),
                     ('64', '64', ''),
                     ('96', '96', ''),
                     ('128', '128', ''),
                     ),
            default='8',
            update=update_parallax_num_of_layers)

    baked_parallax_num_of_layers : EnumProperty(
            name = 'Baked Parallax Mapping Number of Layers',
            description = 'Baked Parallax Mapping Number of Layers',
            items = (('4', '4', ''),
                     ('8', '8', ''),
                     ('16', '16', ''),
                     ('24', '24', ''),
                     ('32', '32', ''),
                     ('64', '64', ''),
                     ('96', '96', ''),
                     ('128', '128', ''),
                     ('192', '192', ''),
                     ('256', '256', ''),
                     ),
            default='32',
            update=update_parallax_num_of_layers)

    disable_global_baked : BoolProperty(
            name = 'Disable Global Baked', 
            description = 'Disable baked image for this channel if global baked is on',
            default=False, update=update_channel_disable_global_baked)

    #use_baked : BoolProperty(
    #        name = 'Use Baked Image', 
    #        description = 'Use baked image for this channel',
    #        default=False)

    #parallax_num_of_binary_samples : IntProperty(default=5, min=4, max=64,
    #        update=update_parallax_samples)

    # To mark if channel needed to be baked or not
    no_layer_using : BoolProperty(default=True)

    parallax_rim_hack : BoolProperty(default=False, 
            update=update_parallax_rim_hack)

    parallax_rim_hack_hardness : FloatProperty(default=1.0, min=1.0, max=100.0, 
            update=update_parallax_rim_hack)

    parallax_height_tweak : FloatProperty(subtype='FACTOR', default=1.0, min=0.0, max=1.0,
            update=update_parallax_height_tweak)

    # Currently unused
    parallax_ref_plane : FloatProperty(subtype='FACTOR', default=0.5, min=0.0, max=1.0,
            update=update_displacement_ref_plane)

    # Real displacement using height map
    enable_subdiv_setup : BoolProperty(
            name = 'Enable Displacement Setup',
            description = 'Enable displacement setup. Only works if baked results is used',
            default=False, update=Bake.update_enable_subdiv_setup)

    #subdiv_standard_type : EnumProperty(
    #        name = 'Subdivision Standard Type',
    #        description = 'Subdivision Standard Type',
    #        items = (
    #            ('CATMULL_CLARK', 'Catmull-Clark', ''),
    #            ('SIMPLE', 'Simple', ''),
    #            ),
    #        default = 'CATMULL_CLARK',
    #        update=Bake.update_subdiv_standard_type
    #        )

    subdiv_adaptive : BoolProperty(
            name = 'Use Adaptive Subdivision',
            description = 'Use Adaptive Subdivision (only works on Cycles)',
            default=False, update=Bake.update_subdiv_setup
            )
    
    subdiv_on_max_polys : IntProperty(
            name = 'Subdiv On Max Polygons',
            description = 'Max Polygons (in thousand) when displacement setup is on',
            default=1000, min=0, max=5000, 
            update=Bake.update_subdiv_max_polys
            )

    #subdiv_on_level : IntProperty(
    #        name = 'Subdiv On Level',
    #        description = 'Subdivision level when displacement setup is on',
    #        default=3, min=0, max=10, 
    #        update=Bake.update_subdiv_on_off_level)

    #subdiv_off_level : IntProperty(
    #        name = 'Subdiv Off Level',
    #        description = 'Subdivision level when displacement setup is off',
    #        default=1, min=0, max=10, update=Bake.update_subdiv_on_off_level
    #        )

    subdiv_tweak : FloatProperty(
            name = 'Subdiv Tweak',
            description = 'Tweak displacement height',
            default=1.0, min=0.0, max=1000.0, 
            update=Bake.update_subdiv_tweak
            )

    subdiv_global_dicing : FloatProperty(subtype='PIXEL', default=1.0, min=0.5, max=1000,
            update=Bake.update_subdiv_global_dicing)

    subdiv_subsurf_only : BoolProperty(
            name = 'Use Subsurf Modifier Only',
            description = 'Ignore Multires and use subsurf modifier exclusively (useful if you already baked the multires to layer)',
            default=False, update=Bake.update_subdiv_setup
            )

    # Main uv is used for normal calculation of normal channel
    main_uv : StringProperty(default='', update=update_channel_main_uv)

    colorspace : EnumProperty(
            name = 'Color Space',
            description = "Non color won't converted to linear first before blending",
            items = colorspace_items,
            default='LINEAR',
            update=update_channel_colorspace)

    modifiers : CollectionProperty(type=Modifier.YPaintModifier)
    active_modifier_index : IntProperty(default=0)

    # Node names
    start_linear : StringProperty(default='')
    end_linear : StringProperty(default='')
    clamp : StringProperty(default='')
    start_normal_filter : StringProperty(default='')
    bump_process : StringProperty(default='')
    end_max_height : StringProperty(default='')
    end_max_height_tweak : StringProperty(default='')
    end_backface : StringProperty(default='')

    # Baked nodes
    baked : StringProperty(default='')
    baked_normal : StringProperty(default='')
    baked_normal_flip : StringProperty(default='')
    baked_normal_prep : StringProperty(default='')

    baked_disp : StringProperty(default='')
    baked_normal_overlay : StringProperty(default='')

    # Outside baked nodes
    baked_outside : StringProperty(default='')
    baked_outside_disp : StringProperty(default='')
    baked_outside_normal_overlay : StringProperty(default='')

    baked_outside_disp_process : StringProperty(default='')
    baked_outside_normal_process : StringProperty(default='')

    # UI related
    expand_content : BoolProperty(default=False)
    expand_base_vector : BoolProperty(default=True)
    expand_subdiv_settings : BoolProperty(default=False)
    expand_parallax_settings : BoolProperty(default=False)
    expand_alpha_settings : BoolProperty(default=False)
    expand_smooth_bump_settings : BoolProperty(default=False)

    # Connection related
    ori_alpha_to : CollectionProperty(type=YNodeConnections)
    ori_alpha_from : PointerProperty(type=YNodeConnections)

    ori_to : CollectionProperty(type=YNodeConnections)
    ori_height_to : CollectionProperty(type=YNodeConnections)
    ori_max_height_to : CollectionProperty(type=YNodeConnections)

    ori_normal_to : CollectionProperty(type=YNodeConnections)

class YPaintUV(bpy.types.PropertyGroup):
    name : StringProperty(default='')

    # Nodes
    uv_map : StringProperty(default='')
    tangent : StringProperty(default='')
    tangent_flip : StringProperty(default='')
    bitangent : StringProperty(default='')
    bitangent_flip : StringProperty(default='')
    tangent_process : StringProperty(default='')

    parallax_prep : StringProperty(default='')
    parallax_current_uv_mix : StringProperty(default='')
    parallax_current_uv : StringProperty(default='')
    parallax_delta_uv : StringProperty(default='')
    parallax_mix : StringProperty(default='')

    baked_parallax_current_uv_mix : StringProperty(default='')
    baked_parallax_current_uv : StringProperty(default='')
    baked_parallax_delta_uv : StringProperty(default='')
    baked_parallax_mix : StringProperty(default='')

    # For baking
    temp_tangent : StringProperty(default='')
    temp_bitangent : StringProperty(default='')

class YPaint(bpy.types.PropertyGroup):

    is_ypaint_node : BoolProperty(default=False)
    is_ypaint_layer_node : BoolProperty(default=False)
    version : StringProperty(default='')

    # Channels
    channels : CollectionProperty(type=YPaintChannel)
    active_channel_index : IntProperty(default=0, update=update_active_yp_channel)

    # Layers
    layers : CollectionProperty(type=Layer.YLayer)
    active_layer_index : IntProperty(default=0, update=update_layer_index)

    # UVs
    uvs : CollectionProperty(type=YPaintUV)

    # Temp channels to remember last channel selected when adding new layer
    #temp_channels = CollectionProperty(type=YChannelUI)
    preview_mode : BoolProperty(default=False, update=update_preview_mode)

    # Layer Preview Mode
    layer_preview_mode : BoolProperty(
            name= 'Enable Layer Preview Mode',
            description= 'Enable layer preview mode',
            default=False,
            update=update_layer_preview_mode)

    # Mask Preview Mode
    #mask_preview_mode : BoolProperty(
    #        name= 'Enable Mask Preview Mode',
    #        description= 'Enable mask preview mode',
    #        default=False,
    #        update=update_mask_preview_mode)

    layer_preview_mode_type : EnumProperty(
            name= 'Layer Preview Mode Type',
            description = 'Layer preview mode type',
            #items = (('LAYER', 'Layer', '', lib.get_icon('mask'), 0),
            #         ('MASK', 'Mask', '', lib.get_icon('mask'), 1),
            #         ('SPECIFIC_MASK', 'Specific Mask', '', lib.get_icon('mask'), 2),
            #         ),
            #items = (('LAYER', 'Layer', '', 'TEXTURE', 0),
            #         ('MASK', 'Mask', '', 'MOD_MASK', 1),
            #         ('SPECIFIC_MASK', 'Specific Mask', '', 'MOD_MASK', 2),
            #         ),
            items = (('LAYER', 'Layer', ''),
                     ('ALPHA', 'Alpha', ''),
                     ('SPECIFIC_MASK', 'Specific Mask / Override', ''),
                     ),
            #items = layer_preview_mode_type_items,
            default = 'LAYER',
            update=update_layer_preview_mode
            )

    # Mode exclusively for merging mask
    #merge_mask_mode = BoolProperty(default=False,
    #        update=update_merge_mask_mode)

    # Toggle to use baked results or not
    use_baked : BoolProperty(default=False, update=Bake.update_use_baked)
    baked_uv_name : StringProperty(default='')

    enable_baked_outside : BoolProperty(
            name= 'Enable Baked Outside',
            description= 'Create baked texture nodes outside of main node\n(Can be useful for exporting material to other application)',
            default=False, update=Bake.update_enable_baked_outside)
    
    # Outside nodes
    baked_outside_uv : StringProperty(default='')
    baked_outside_frame : StringProperty(default='')
    baked_outside_x_shift : IntProperty(default=0)

    # Flip backface
    enable_backface_always_up : BoolProperty(
            name= 'Make backface normal always up',
            description= 'Make sure normal will face toward camera even at backface',
            default=True, update=update_flip_backface)

    # Layer alpha Viewer Mode
    #enable_layer_alpha_viewer : BoolProperty(
    #        name= 'Enable Layer Alpha Viewer Mode',
    #        description= 'Enable layer alpha viewer mode',
    #        default=False)

    # Path folder for auto save bake
    #bake_folder : StringProperty(default='')

    # Disable quick toggle for better shader performance
    #disable_quick_toggle : BoolProperty(
    #        name = 'Disable Quick Toggle',
    #        description = 'Disable quick toggle to improve shader performance',
    #        default=False, update=update_disable_quick_toggle)

    #performance_mode : EnumProperty(
    #        name = 'Performance Mode',
    #        description = 'Performance mode to make this addon useful for various cases',
    #        items = (('QUICK_TOGGLE', 'Quick toggle, but can be painfully slow if using more than 4 layers', ''),
    #                 ('SLOW_TOGGLE', 'Slow toggle, but can be useful with many layers', ''),
    #                 ),
    #        default='SLOW_TOGGLE')

    enable_tangent_sign_hacks : BoolProperty(
            name = 'Enable Tangent Sign VCol Hacks for Blender 2.80+ Cycles',
            description = "Tangent sign vertex color needed to make sure Blender 2.8 Cycles normal and parallax works.\n(This is because Blender 2.8 normal map node has different behavior than Blender 2.7)",
            default=False, update=update_enable_tangent_sign_hacks)

    # When enabled, alpha can create some node setup, disable this to avoid that
    alpha_auto_setup : BoolProperty(default=True)

    # HACK: Refresh tree to remove glitchy normal
    refresh_tree : BoolProperty(default=False)

    # Useful to suspend update when adding new stuff
    halt_update : BoolProperty(default=False)

    # Useful to suspend node rearrangements and reconnections when adding new stuff
    halt_reconnect : BoolProperty(default=False)

    # Remind user to refresh UV after edit image layer mapping
    need_temp_uv_refresh : BoolProperty(default=False)

    # Index pointer to the UI
    #ui_index : IntProperty(default=0)

    #random_prop : BoolProperty(default=False)

    # Trash node for collecting disabled nodes
    trash : StringProperty(default='')

class YPaintMaterialProps(bpy.types.PropertyGroup):
    ori_bsdf : StringProperty(default='')
    #ori_blend_method : StringProperty(default='')
    active_ypaint_node : StringProperty(default='')

class YPaintTimer(bpy.types.PropertyGroup):
    time : StringProperty(default='')

class YPaintWMProps(bpy.types.PropertyGroup):
    clipboard_tree : StringProperty(default='')
    clipboard_layer : StringProperty(default='')

class YPaintSceneProps(bpy.types.PropertyGroup):
    last_object : StringProperty(default='')
    last_mode : StringProperty(default='')

    ori_display_device : StringProperty(default='')
    ori_view_transform : StringProperty(default='')
    ori_exposure : FloatProperty(default=0.0)
    ori_gamma : FloatProperty(default=1.0)
    ori_look : StringProperty(default='')
    ori_use_curve_mapping : BoolProperty(default=False)

    edit_image_editor_area_index : IntProperty(default=-1)

class YPaintObjectProps(bpy.types.PropertyGroup):
    ori_subsurf_render_levels : IntProperty(default=1)
    ori_subsurf_levels : IntProperty(default=1)
    ori_multires_render_levels : IntProperty(default=1)
    ori_multires_levels : IntProperty(default=1)

    ori_mirror_offset_u : FloatProperty(default=0.0)
    ori_mirror_offset_v : FloatProperty(default=0.0)
    ori_offset_u : FloatProperty(default=0.0)
    ori_offset_v : FloatProperty(default=0.0)

#class YPaintMeshProps(bpy.types.PropertyGroup):
#    parallax_scale_min : FloatProperty(default=0.0)
#    parallax_scale_span : FloatProperty(default=1.0)
#    parallax_curvature_min : FloatProperty(default=0.0)
#    parallax_curvature_span : FloatProperty(default=1.0)

@persistent
def ypaint_hacks_and_scene_updates(scene):
    # Get active yp node
    group_node = get_active_ypaint_node()
    if not group_node: return
    tree = group_node.node_tree
    yp = tree.yp

    # HACK: Refresh normal
    if yp.refresh_tree:
        # Just reconnect any connection twice to refresh normal
        for link in tree.links:
            from_socket = link.from_socket
            to_socket = link.to_socket
            tree.links.new(from_socket, to_socket)
            tree.links.new(from_socket, to_socket)
            break
        yp.refresh_tree = False

    # Check single user image layer
    if len(yp.layers) > 0:
        layer = yp.layers[yp.active_layer_index]

        if layer.type == 'IMAGE':
            source = get_layer_source(layer)
            img = source.image

            if img and img.name != layer.image_name:
                # Update active layer paint image
                layer.image_name = img.name
                yp.active_layer_index = yp.active_layer_index

@persistent
def ypaint_last_object_update(scene):
    try: obj = bpy.context.object
    except: return
    if not obj: return

    if scene.yp.last_object != obj.name:
        scene.yp.last_object = obj.name
        node = get_active_ypaint_node()

        # Refresh layer index to update editor image
        if node:
            yp = node.node_tree.yp
            if yp.use_baked and len(yp.channels) > 0:
                update_active_yp_channel(yp, bpy.context)

            elif len(yp.layers) > 0 :
                image, uv_name, src_of_img, mapping, vcol = get_active_image_and_stuffs(obj, yp)
                update_image_editor_image(bpy.context, image)
                scene.tool_settings.image_paint.canvas = image

    if obj.type == 'MESH' and scene.yp.last_object == obj.name and scene.yp.last_mode != obj.mode:

        node = get_active_ypaint_node()
        yp = node.node_tree.yp if node else None

        if obj.mode == 'TEXTURE_PAINT' or scene.yp.last_mode == 'TEXTURE_PAINT':
            scene.yp.last_mode = obj.mode
            if yp and len(yp.layers) > 0 :
                image, uv_name, src_of_img, mapping, vcol = get_active_image_and_stuffs(obj, yp)

                # Store original uv mirror offsets
                if obj.mode == 'TEXTURE_PAINT':
                    mirror = get_first_mirror_modifier(obj)
                    if mirror:
                        obj.yp.ori_mirror_offset_u = mirror.mirror_offset_u
                        obj.yp.ori_mirror_offset_v = mirror.mirror_offset_v
                        if is_greater_than_280():
                            obj.yp.ori_offset_u = mirror.offset_u
                            obj.yp.ori_offset_v = mirror.offset_v

                refresh_temp_uv(obj, src_of_img)

        # Into edit mode
        if obj.mode == 'EDIT' and scene.yp.last_mode != 'EDIT':
            scene.yp.last_mode = obj.mode
            # Remember the space
            space, area_index = get_first_unpinned_image_editor_space(bpy.context, return_index=True)
            if space and area_index != -1:
                scene.yp.edit_image_editor_area_index = area_index

            # Trigger updating active index to update image
            #if yp: 
            #    if yp.use_baked:
            #        yp.active_channel_index = yp.active_channel_index
            #    else: yp.active_layer_index = yp.active_layer_index

        # Out of edit mode
        if obj.mode != 'EDIT' and scene.yp.last_mode == 'EDIT':
            scene.yp.last_mode = obj.mode
            space = get_edit_image_editor_space(bpy.context)
            if space:
                space.use_image_pin = False
            scene.yp.edit_image_editor_area_index = -1

            # Trigger updating active index to update image
            #if yp: 
            #    if yp.use_baked:
            #        yp.active_channel_index = yp.active_channel_index
            #    else: yp.active_layer_index = yp.active_layer_index

        if scene.yp.last_mode != obj.mode:
            scene.yp.last_mode = obj.mode

@persistent
def ypaint_force_update_on_anim(scene):
    #print(scene.frame_current)

    yp_keyframe_found = False
    for act in bpy.data.actions:
        if act.id_root == 'NODETREE' and len(act.fcurves) > 0 and act.fcurves[0].data_path.startswith('yp.'):
            yp_keyframe_found = True
            break

    if yp_keyframe_found:
        ngs = [ng for ng in bpy.data.node_groups if hasattr(ng, 'yp') and ng.yp.is_ypaint_node and ng.animation_data and ng.animation_data.action]
        for ng in ngs:
            fcs = ng.animation_data.action.fcurves
            for fc in fcs:
                if not fc.mute and fc.data_path.startswith('yp.'):

                    # Get the datapath of the keyframed prop
                    ng_string = 'bpy.data.node_groups["' + ng.name + '"].'
                    path = ng_string + fc.data_path

                    # Get evaluated value
                    val = fc.evaluate(scene.frame_current)

                    # Check if path is a string
                    if type(eval(path)) == str:
                        # Get prop name
                        m = re.match(r'(.+)\.(.+)$', fc.data_path)
                        if m:
                            parent_path = ng_string + m.group(1)
                            prop_name = m.group(2)
                            enum_path = parent_path + '.bl_rna.properties["' + prop_name + '"].enum_items[' + str(int(val)) + '].identifier'
                            val = eval(enum_path)

                    # Check if path is an array
                    elif hasattr(eval(path), '__len__'):
                        path += '[' + str(fc.array_index) + ']'

                    # Check if path is a boolean
                    elif type(eval(path)) == bool:
                        val = val == 1.0

                    #print(path, val)

                    # Only run script if needed
                    if eval(path) != val:

                        # Convert evaluated value to string
                        string_val = str(val) if type(val) != str else '"' + val + '"'

                        # Construct the script
                        script = path + ' = ' + string_val

                        # Run the script to trigger update
                        #print(script)
                        exec(script)

def register():
    bpy.utils.register_class(YSelectMaterialPolygons)
    bpy.utils.register_class(YRenameUVMaterial)
    bpy.utils.register_class(YQuickYPaintNodeSetup)
    bpy.utils.register_class(YNewYPaintNode)
    bpy.utils.register_class(YPaintNodeInputCollItem)
    bpy.utils.register_class(YConnectYPaintChannel)
    bpy.utils.register_class(YConnectYPaintChannelAlpha)
    bpy.utils.register_class(YNewYPaintChannel)
    bpy.utils.register_class(YMoveYPaintChannel)
    bpy.utils.register_class(YRemoveYPaintChannel)
    bpy.utils.register_class(YAddSimpleUVs)
    bpy.utils.register_class(YFixMissingUV)
    bpy.utils.register_class(YRenameYPaintTree)
    bpy.utils.register_class(YChangeActiveYPaintNode)
    bpy.utils.register_class(YDuplicateYPNodes)
    bpy.utils.register_class(YFixMissingData)
    bpy.utils.register_class(YRefreshTangentSignVcol)
    bpy.utils.register_class(YRemoveYPaintNode)
    bpy.utils.register_class(YCleanYPCaches)
    bpy.utils.register_class(YNodeConnections)
    bpy.utils.register_class(YPaintChannel)
    bpy.utils.register_class(YPaintUV)
    bpy.utils.register_class(YPaint)
    bpy.utils.register_class(YPaintMaterialProps)
    bpy.utils.register_class(YPaintTimer)
    bpy.utils.register_class(YPaintWMProps)
    bpy.utils.register_class(YPaintSceneProps)
    bpy.utils.register_class(YPaintObjectProps)
    #bpy.utils.register_class(YPaintMeshProps)

    # YPaint Props
    bpy.types.ShaderNodeTree.yp = PointerProperty(type=YPaint)
    bpy.types.Material.yp = PointerProperty(type=YPaintMaterialProps)
    bpy.types.WindowManager.yptimer = PointerProperty(type=YPaintTimer)
    bpy.types.WindowManager.ypprops = PointerProperty(type=YPaintWMProps)
    bpy.types.Scene.yp = PointerProperty(type=YPaintSceneProps)
    bpy.types.Object.yp = PointerProperty(type=YPaintObjectProps)
    #bpy.types.Mesh.yp = PointerProperty(type=YPaintMeshProps)

    # Handlers
    if is_greater_than_280():
        bpy.app.handlers.depsgraph_update_post.append(ypaint_last_object_update)
    else:
        bpy.app.handlers.scene_update_pre.append(ypaint_last_object_update)
        bpy.app.handlers.scene_update_pre.append(ypaint_hacks_and_scene_updates)

    bpy.app.handlers.frame_change_pre.append(ypaint_force_update_on_anim)

def unregister():
    bpy.utils.unregister_class(YSelectMaterialPolygons)
    bpy.utils.unregister_class(YRenameUVMaterial)
    bpy.utils.unregister_class(YQuickYPaintNodeSetup)
    bpy.utils.unregister_class(YNewYPaintNode)
    bpy.utils.unregister_class(YPaintNodeInputCollItem)
    bpy.utils.unregister_class(YConnectYPaintChannel)
    bpy.utils.unregister_class(YConnectYPaintChannelAlpha)
    bpy.utils.unregister_class(YNewYPaintChannel)
    bpy.utils.unregister_class(YMoveYPaintChannel)
    bpy.utils.unregister_class(YRemoveYPaintChannel)
    bpy.utils.unregister_class(YAddSimpleUVs)
    bpy.utils.unregister_class(YFixMissingUV)
    bpy.utils.unregister_class(YRenameYPaintTree)
    bpy.utils.unregister_class(YChangeActiveYPaintNode)
    bpy.utils.unregister_class(YDuplicateYPNodes)
    bpy.utils.unregister_class(YFixMissingData)
    bpy.utils.unregister_class(YRefreshTangentSignVcol)
    bpy.utils.unregister_class(YRemoveYPaintNode)
    bpy.utils.unregister_class(YCleanYPCaches)
    bpy.utils.unregister_class(YNodeConnections)
    bpy.utils.unregister_class(YPaintChannel)
    bpy.utils.unregister_class(YPaintUV)
    bpy.utils.unregister_class(YPaint)
    bpy.utils.unregister_class(YPaintMaterialProps)
    bpy.utils.unregister_class(YPaintTimer)
    bpy.utils.unregister_class(YPaintWMProps)
    bpy.utils.unregister_class(YPaintSceneProps)
    bpy.utils.unregister_class(YPaintObjectProps)
    #bpy.utils.unregister_class(YPaintMeshProps)

    # Remove handlers
    if is_greater_than_280():
        bpy.app.handlers.depsgraph_update_post.remove(ypaint_last_object_update)
    else:
        bpy.app.handlers.scene_update_pre.remove(ypaint_hacks_and_scene_updates)
        bpy.app.handlers.scene_update_pre.remove(ypaint_last_object_update)

    bpy.app.handlers.frame_change_pre.remove(ypaint_force_update_on_anim)

