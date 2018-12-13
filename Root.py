import bpy, time, re, os
from bpy.props import *
from bpy.app.handlers import persistent
from .common import *
from .subtree import *
from .node_arrangements import *
from .node_connections import *
from . import lib, Modifier, Layer, Mask, transition, Bake, ImageAtlas

YP_GROUP_SUFFIX = ' ' + ADDON_TITLE
YP_GROUP_PREFIX = ADDON_TITLE + ' '

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

def check_all_channel_ios(yp):
    group_tree = yp.id_data

    correct_index = 0
    valid_inputs = []
    valid_outputs = []

    for ch in yp.channels:

        inp = group_tree.inputs.get(ch.name)
        if not inp:
            inp = group_tree.inputs.new(channel_socket_input_bl_idnames[ch.type], ch.name)

            if ch.type == 'VALUE':
                inp.min_value = 0.0
                inp.max_value = 1.0
            elif ch.type == 'RGB':
                inp.default_value = (1,1,1,1)
            elif ch.type == 'NORMAL':
                # Use 999 as normal z value so it will fallback to use geometry normal at checking process
                inp.default_value = (999,999,999) 

        fix_io_index(inp, group_tree.inputs, correct_index)
        valid_inputs.append(inp)

        out = group_tree.outputs.get(ch.name)
        if not out:
            out = group_tree.outputs.new(channel_socket_output_bl_idnames[ch.type], ch.name)
        fix_io_index(out, group_tree.outputs, correct_index)
        valid_outputs.append(out)

        if ch.io_index != correct_index:
            ch.io_index = correct_index

        correct_index += 1

        name = ch.name + ' Alpha'
        inp = group_tree.inputs.get(name)
        out = group_tree.outputs.get(name)

        if ch.type == 'RGB' and ch.enable_alpha:

            if not inp:
                inp = group_tree.inputs.new('NodeSocketFloatFactor', name)
                inp.min_value = 0.0
                inp.max_value = 1.0
                inp.default_value = 0.0
            fix_io_index(inp, group_tree.inputs, correct_index)
            valid_inputs.append(inp)

            if not out:
                out = group_tree.outputs.new(channel_socket_output_bl_idnames['VALUE'], name)
            fix_io_index(out, group_tree.outputs, correct_index)
            valid_outputs.append(out)

            correct_index += 1

        else:
            if inp: group_tree.inputs.remove(inp)
            if out: group_tree.outputs.remove(out)

    # Check for invalid io
    for inp in group_tree.inputs:
        if inp not in valid_inputs:
            group_tree.inputs.remove(inp)

    for outp in group_tree.outputs:
        if outp not in valid_outputs:
            group_tree.outputs.remove(outp)

    # Move layer IO
    for layer in yp.layers:
        Layer.check_all_layer_channel_io_and_nodes(layer)
        rearrange_layer_nodes(layer)
        reconnect_layer_nodes(layer)

    # Rearrange nodes
    rearrange_yp_nodes(group_tree)
    reconnect_yp_nodes(group_tree)

def set_input_default_value(group_node, channel, custom_value=None):
    #channel = group_node.node_tree.yp.channels[index]

    if custom_value:
        if channel.type == 'RGB' and len(custom_value) == 3:
            custom_value = (custom_value[0], custom_value[1], custom_value[2], 1)

        group_node.inputs[channel.io_index].default_value = custom_value
        return
    
    # Set default value
    if channel.type == 'RGB':
        group_node.inputs[channel.io_index].default_value = (1,1,1,1)

        if channel.enable_alpha:
            group_node.inputs[channel.io_index+1].default_value = 1.0
    if channel.type == 'VALUE':
        group_node.inputs[channel.io_index].default_value = 0.0
    if channel.type == 'NORMAL':
        # Use 999 as normal z value so it will fallback to use geometry normal at checking process
        group_node.inputs[channel.io_index].default_value = (999,999,999)

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

    if channel.type == 'NORMAL':
        start_normal_filter = new_node(group_tree, channel, 'start_normal_filter', 'ShaderNodeGroup', 'Start Normal Filter')
        start_normal_filter.node_tree = get_node_tree_lib(lib.CHECK_INPUT_NORMAL)

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
    create_essential_nodes(group_tree, True)

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

    # Get IO index
    io_index = last_index
    for ch in yp.channels:
        if ch.type == 'RGB' and ch.enable_alpha:
            io_index += 1

    channel.io_index = io_index

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

#def update_quick_setup_type(self, context):
#    if self.type == 'PRINCIPLED':
#        self.roughness = True
#        self.normal = True
#    elif self.type == 'DIFFUSE':
#        self.roughness = False
#        self.normal = False

class YQuickYPaintNodeSetup(bpy.types.Operator):
    bl_idname = "node.y_quick_ypaint_node_setup"
    bl_label = "Quick " + ADDON_TITLE + " Node Setup"
    bl_description = "Quick " + ADDON_TITLE + " Node Setup"
    bl_options = {'REGISTER', 'UNDO'}

    type = EnumProperty(
            name = 'Type',
            items = (('PRINCIPLED', 'Principled', ''),
                     ('DIFFUSE', 'Diffuse', ''),
                     ),
            default = 'PRINCIPLED')
            #update=update_quick_setup_type)

    color = BoolProperty(name='Color', default=True)
    metallic = BoolProperty(name='Metallic', default=False)
    roughness = BoolProperty(name='Roughness', default=True)
    normal = BoolProperty(name='Normal', default=True)

    mute_texture_paint_overlay = BoolProperty(
            name = 'Mute Texture Paint Overlay',
            description = 'Set Texture Paint Overlay on 3D View screen to 0. It can helps texture painting better.',
            default = True)

    @classmethod
    def poll(cls, context):
        return context.object

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def check(self, context):
        return True

    def draw(self, context):
        #row = self.layout.row()
        if bpy.app.version_string.startswith('2.8'):
            row = self.layout.split(factor=0.35)
        else: row = self.layout.split(percentage=0.35)

        col = row.column()
        col.label(text='Type:')
        ccol = col.column(align=True)
        ccol.label(text='Channels:')
        if self.type == 'PRINCIPLED':
            ccol.label(text='')
        ccol.label(text='')
        ccol.label(text='')
        col = row.column()
        col.prop(self, 'type', text='')
        ccol = col.column(align=True)
        ccol.prop(self, 'color', toggle=True)
        if self.type == 'PRINCIPLED':
            ccol.prop(self, 'metallic', toggle=True)
        ccol.prop(self, 'roughness', toggle=True)
        ccol.prop(self, 'normal', toggle=True)

        if bpy.app.version_string.startswith('2.8'):
            col.prop(self, 'mute_texture_paint_overlay')

    def execute(self, context):

        obj = context.object
        mat = get_active_material()

        if not mat:
            mat = bpy.data.materials.new(obj.name)
            mat.use_nodes = True
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

        main_bsdf = None
        trans_bsdf = None
        mix_bsdf = None
        mat_out = None

        # Get active output
        output = [n for n in nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output]
        if output: 
            output = output[0]

            # Check output connection
            output_in = [l.from_node for l in output.inputs[0].links]
            if output_in: 
                output_in = output_in[0]
                if output_in.type == 'MIX_SHADER' and not any([l for l in output_in.inputs[0].links]):

                    if self.type == 'PRINCIPLED':
                        bsdf_type = 'BSDF_PRINCIPLED'
                    elif self.type == 'DIFFUSE':
                        bsdf_type = 'BSDF_DIFFUSE'

                    # Try to search for transparent and main bsdf
                    if (any([l for l in output_in.inputs[1].links if l.from_node.type == 'BSDF_TRANSPARENT']) and
                        any([l for l in output_in.inputs[2].links if l.from_node.type == bsdf_type])):

                            mat_out = output
                            mix_bsdf = output_in
                            trans_bsdf = mix_bsdf.inputs[1].links[0].from_node
                            main_bsdf = mix_bsdf.inputs[2].links[0].from_node

        if not mat_out:
            mat_out = nodes.new(type='ShaderNodeOutputMaterial')
            mat_out.is_active_output = True

            if output:
                output.is_active_output = False
                mat_out.location = output.location.copy()
                mat_out.location.x += 180

        if not mix_bsdf:
            mix_bsdf = nodes.new('ShaderNodeMixShader')
            mix_bsdf.inputs[0].default_value = 1.0
            links.new(mix_bsdf.outputs[0], mat_out.inputs[0])

            mix_bsdf.location = mat_out.location.copy()
            mat_out.location.x += 180

        if not trans_bsdf:
            trans_bsdf = nodes.new('ShaderNodeBsdfTransparent')
            links.new(trans_bsdf.outputs[0], mix_bsdf.inputs[1])

            trans_bsdf.location = mix_bsdf.location.copy()
            mix_bsdf.location.x += 180
            mat_out.location.x += 180

        if not main_bsdf:
            if self.type == 'PRINCIPLED':
                main_bsdf = nodes.new('ShaderNodeBsdfPrincipled')
                main_bsdf.inputs[2].default_value = (1.0, 0.2, 0.1) # Use eevee default value
                main_bsdf.inputs[3].default_value = (0.8, 0.8, 0.8, 1.0) # Use eevee default value
            elif self.type == 'DIFFUSE':
                main_bsdf = nodes.new('ShaderNodeBsdfDiffuse')

            links.new(main_bsdf.outputs[0], mix_bsdf.inputs[2])

            # Rearrange position
            main_bsdf.location = trans_bsdf.location.copy()
            main_bsdf.location.y -= 90

        group_tree = create_new_group_tree(mat)

        # Create new group node
        node = nodes.new(type='ShaderNodeGroup')
        node.node_tree = group_tree
        node.select = True
        nodes.active = node
        mat.yp.active_ypaint_node = node.name

        # Add new channels
        ch_color = None
        ch_metallic = None
        ch_roughness = None
        ch_normal = None

        if self.color:
            ch_color = create_new_yp_channel(group_tree, 'Color', 'RGB', non_color=False)

        if self.type == 'PRINCIPLED' and self.metallic:
            ch_metallic = create_new_yp_channel(group_tree, 'Metallic', 'VALUE', non_color=True)

        if self.roughness:
            ch_roughness = create_new_yp_channel(group_tree, 'Roughness', 'VALUE', non_color=True)

        if self.normal:
            ch_normal = create_new_yp_channel(group_tree, 'Normal', 'NORMAL')

        # Update io
        check_all_channel_ios(group_tree.yp)

        if ch_color:
            inp = main_bsdf.inputs[0]
            set_input_default_value(node, ch_color, inp.default_value)
            links.new(node.outputs[ch_color.io_index], inp)
            # Enable, link, and disable alpha to remember which input was alpha connected to
            ch_color.enable_alpha = True
            links.new(node.outputs[ch_color.io_index+1], mix_bsdf.inputs[0])
            ch_color.enable_alpha = False

        if ch_metallic:
            inp = main_bsdf.inputs['Metallic']
            set_input_default_value(node, ch_metallic, inp.default_value)
            links.new(node.outputs[ch_metallic.io_index], inp)

        if ch_roughness:
            inp = main_bsdf.inputs['Roughness']
            set_input_default_value(node, ch_roughness, inp.default_value)
            links.new(node.outputs[ch_roughness.io_index], inp)

        if ch_normal:
            inp = main_bsdf.inputs['Normal']
            set_input_default_value(node, ch_normal)
            links.new(node.outputs[ch_normal.io_index], inp)

        # Set new yp node location
        if output:
            node.location = main_bsdf.location.copy()
            main_bsdf.location.x += 180
            trans_bsdf.location.x += 180
            mix_bsdf.location.x += 180
            mat_out.location.x += 180
        else:
            main_bsdf.location.y += 300
            trans_bsdf.location.y += 300
            mix_bsdf.location.y += 300
            mat_out.location.y += 300
            node.location = main_bsdf.location.copy()
            node.location.x -= 180

        # Disable overlay on Blender 2.8
        if bpy.app.version_string.startswith('2.8') and self.mute_texture_paint_overlay:
            screen = context.screen
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.spaces[0].overlay.texture_paint_mode_opacity = 0.0

        # Update UI
        context.window_manager.ypui.need_update = True

        return {'FINISHED'}

class YNewYPaintNode(bpy.types.Operator):
    bl_idname = "node.y_add_new_ypaint_node"
    bl_label = "Add new " + ADDON_TITLE + " Node"
    bl_description = "Add new " + ADDON_TITLE + " node"
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
    if bpy.app.version_string.startswith('2.8'):
        items = [('VALUE', 'Value', '', lib.channel_icon_dict['VALUE'], 0),
                 ('RGB', 'RGB', '', lib.channel_icon_dict['RGB'], 1),
                 ('NORMAL', 'Normal', '', lib.channel_icon_dict['NORMAL'], 2)]
    else:
        items = [('VALUE', 'Value', '', lib.custom_icons[lib.channel_custom_icon_dict['VALUE']].icon_id, 0),
                 ('RGB', 'RGB', '', lib.custom_icons[lib.channel_custom_icon_dict['RGB']].icon_id, 1),
                 ('NORMAL', 'Normal', '', lib.custom_icons[lib.channel_custom_icon_dict['NORMAL']].icon_id, 2)]

    return items

class YPaintNodeInputCollItem(bpy.types.PropertyGroup):
    name = StringProperty(default='')
    node_name = StringProperty(default='')
    input_name = StringProperty(default='')

def update_connect_to(self, context):
    yp = get_active_ypaint_node().node_tree.yp
    item = self.input_coll.get(self.connect_to)
    if item:
        self.name = get_unique_name(item.input_name, yp.channels)

class YNewYPaintChannel(bpy.types.Operator):
    bl_idname = "node.y_add_new_ypaint_channel"
    bl_label = "Add new " + ADDON_TITLE + " Channel"
    bl_description = "Add new " + ADDON_TITLE + " channel"
    bl_options = {'REGISTER', 'UNDO'}

    name = StringProperty(
            name='Channel Name', 
            description = 'Name of the channel',
            default='Albedo')

    type = EnumProperty(
            name = 'Channel Type',
            items = new_channel_items)

    connect_to = StringProperty(name='Connect To', default='', update=update_connect_to)
    input_coll = CollectionProperty(type=YPaintNodeInputCollItem)

    colorspace = EnumProperty(
            name = 'Color Space',
            description = "Non color won't converted to linear first before blending",
            items = colorspace_items,
            default='LINEAR')

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def refresh_input_coll(self, context):
        # Refresh input names
        self.input_coll.clear()
        mat = get_active_material()
        nodes = mat.node_tree.nodes
        yp_node = get_active_ypaint_node()

        for node in nodes:
            if node == yp_node: continue
            for inp in node.inputs:
                #if inp.type != channel_socket_types[self.type]: continue
                if self.type == 'VALUE' and inp.type != 'VALUE': continue
                elif self.type == 'RGB' and inp.type not in {'RGBA', 'VECTOR'}: continue
                elif self.type == 'NORMAL' and 'Normal' not in inp.name: continue
                if len(inp.links) > 0 : continue
                label = inp.name + ' (' + node.name +')'
                item = self.input_coll.add()
                item.name = label
                item.node_name = node.name
                item.input_name = inp.name

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

        self.refresh_input_coll(context)
        self.connect_to = ''

        return context.window_manager.invoke_props_dialog(self)
        #return context.window_manager.invoke_popup(self)

    def check(self, context):
        return True

    def draw(self, context):
        if bpy.app.version_string.startswith('2.8'):
            row = self.layout.split(factor=0.4)
        else: row = self.layout.split(percentage=0.4)

        col = row.column(align=False)
        col.label(text='Name:')
        col.label(text='Connect To:')
        if self.type != 'NORMAL':
            col.label(text='Color Space:')

        col = row.column(align=False)
        col.prop(self, 'name', text='')
        col.prop_search(self, "connect_to", self, "input_coll", icon = 'NODETREE', text='')
                #lib.custom_icons[channel_socket_custom_icon_names[self.type]].icon_id)
        if self.type != 'NORMAL':
            col.prop(self, "colorspace", text='')

    def execute(self, context):

        T = time.time()

        #node = context.active_node
        wm = context.window_manager
        mat = get_active_material()
        node = get_active_ypaint_node()
        group_tree = node.node_tree
        yp = group_tree.yp
        #ypup = context.user_preferences.addons[__name__].preferences
        channels = yp.channels

        if len(yp.channels) > 19:
            self.report({'ERROR'}, "Maximum channel possible is 20")
            return {'CANCELLED'}

        # Check if channel with same name is already available
        same_channel = [c for c in channels if c.name == self.name]
        if same_channel:
            self.report({'ERROR'}, "Channel named '" + self.name +"' is already available!")
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
            mat.node_tree.links.new(node.outputs[channel.io_index], inp)

            # Search for possible alpha input
            if self.type == 'RGB':
                for l in target_node.outputs[0].links:
                    if l.to_node.type == 'MIX_SHADER' and not any([m for m in l.to_node.inputs[0].links]):
                        for n in l.to_node.inputs[1].links:
                            if n.from_node.type == 'BSDF_TRANSPARENT':
                                channel.enable_alpha = True
                                mat.node_tree.links.new(node.outputs[channel.io_index+1], l.to_node.inputs[0])
                                channel.enable_alpha = False

        # Set input default value
        if inp and self.type != 'NORMAL': 
            set_input_default_value(node, channel, inp.default_value)
        else: set_input_default_value(node, channel)

        # Change active channel
        last_index = len(yp.channels)-1
        group_tree.yp.active_channel_index = last_index

        # Update UI
        wm.ypui.need_update = True
        print('INFO: Channel', channel.name, 'is created at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.yptimer.time = str(time.time())

        return {'FINISHED'}

def swap_channel_io(root_ch, swap_ch, io_index, io_index_swap, inputs, outputs):
    if root_ch.type == 'RGB' and root_ch.enable_alpha:
        if swap_ch.type == 'RGB' and swap_ch.enable_alpha:
            if io_index > io_index_swap:
                inputs.move(io_index, io_index_swap)
                inputs.move(io_index+1, io_index_swap+1)
                outputs.move(io_index, io_index_swap)
                outputs.move(io_index+1, io_index_swap+1)
            else:
                inputs.move(io_index, io_index_swap)
                inputs.move(io_index, io_index_swap+1)
                outputs.move(io_index, io_index_swap)
                outputs.move(io_index, io_index_swap+1)
        else:
            if io_index > io_index_swap:
                inputs.move(io_index, io_index_swap)
                inputs.move(io_index+1, io_index_swap+1)
                outputs.move(io_index, io_index_swap)
                outputs.move(io_index+1, io_index_swap+1)
            else:
                inputs.move(io_index+1, io_index_swap)
                inputs.move(io_index, io_index_swap-1)
                outputs.move(io_index+1, io_index_swap)
                outputs.move(io_index, io_index_swap-1)
    else:
        if swap_ch.type == 'RGB' and swap_ch.enable_alpha:
            if io_index > io_index_swap:
                inputs.move(io_index, io_index_swap)
                outputs.move(io_index, io_index_swap)
            else:
                inputs.move(io_index, io_index_swap+1)
                outputs.move(io_index, io_index_swap+1)
        else:
            inputs.move(io_index, io_index_swap)
            outputs.move(io_index, io_index_swap)

class YMoveYPaintChannel(bpy.types.Operator):
    bl_idname = "node.y_move_ypaint_channel"
    bl_label = "Move " + ADDON_TITLE + " Channel"
    bl_description = "Move " + ADDON_TITLE + " channel"
    bl_options = {'REGISTER', 'UNDO'}

    direction = EnumProperty(
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

        # Move IO
        #swap_channel_io(channel, swap_ch, io_index, io_index_swap, group_tree.inputs, group_tree.outputs)

        # Move channel
        yp.channels.move(index, new_index)

        # Move layer channels
        for layer in yp.layers:
            layer.channels.move(index, new_index)

            # Move mask channels
            for mask in layer.masks:
                mask.channels.move(index, new_index)

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
    bl_label = "Remove " + ADDON_TITLE + " Channel"
    bl_description = "Remove " + ADDON_TITLE + " channel"
    bl_options = {'REGISTER', 'UNDO'}

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
        nodes = group_tree.nodes
        inputs = group_tree.inputs
        outputs = group_tree.outputs

        # Get active channel
        channel_idx = yp.active_channel_index
        channel = yp.channels[channel_idx]
        channel_name = channel.name

        # Collapse the UI
        #setattr(ypui, 'show_channel_modifiers_' + str(channel_idx), False)

        # Remove channel nodes from layers
        for t in yp.layers:
            ch = t.channels[channel_idx]
            ttree = get_tree(t)

            remove_node(ttree, ch, 'blend')
            remove_node(ttree, ch, 'intensity')

            remove_node(ttree, ch, 'source')
            remove_node(ttree, ch, 'linear')

            remove_node(ttree, ch, 'normal')
            remove_node(ttree, ch, 'normal_flip')
            remove_node(ttree, ch, 'mod_n')
            remove_node(ttree, ch, 'mod_s')
            remove_node(ttree, ch, 'mod_e')
            remove_node(ttree, ch, 'mod_w')
            remove_node(ttree, ch, 'bump_base')
            remove_node(ttree, ch, 'bump_base_n')
            remove_node(ttree, ch, 'bump_base_s')
            remove_node(ttree, ch, 'bump_base_e')
            remove_node(ttree, ch, 'bump_base_w')
            remove_node(ttree, ch, 'intensity_multiplier')

            remove_node(ttree, ch, 'cache_ramp')

            # Remove modifiers
            #if ch.mod_tree:
            if ch.mod_group != '':
                mod_group = ttree.nodes.get(ch.mod_group)
                bpy.data.node_groups.remove(mod_group.node_tree)
                ttree.nodes.remove(mod_group)
            else:
                for mod in ch.modifiers:
                    Modifier.delete_modifier_nodes(ttree, mod)

            # Remove layer IO
            ttree.inputs.remove(ttree.inputs[channel.io_index])
            ttree.outputs.remove(ttree.outputs[channel.io_index])

            if channel.type == 'RGB' and channel.enable_alpha:
                ttree.inputs.remove(ttree.inputs[channel.io_index])
                ttree.outputs.remove(ttree.outputs[channel.io_index])

            # Remove transition bump and ramp
            if channel.type == 'NORMAL' and ch.enable_transition_bump:
                transition.remove_transition_bump_nodes(t, ttree, ch, channel_idx)
            elif channel.type in {'RGB', 'VALUE'} and ch.enable_transition_ramp:
                transition.remove_transition_ramp_nodes(ttree, ch)

            # Remove mask channel
            Mask.remove_mask_channel(ttree, t, channel_idx)

            # Remove layer channel
            t.channels.remove(channel_idx)

        remove_node(group_tree, channel, 'start_linear')
        remove_node(group_tree, channel, 'end_linear')
        remove_node(group_tree, channel, 'start_normal_filter')
        remove_node(group_tree, channel, 'baked')
        remove_node(group_tree, channel, 'baked_normal')
        remove_node(group_tree, channel, 'baked_normal_flip')

        for mod in channel.modifiers:
            Modifier.delete_modifier_nodes(group_tree, mod)

        # Remove channel from tree
        inputs.remove(inputs[channel.io_index])
        outputs.remove(outputs[channel.io_index])

        shift = 1

        if channel.type == 'RGB' and channel.enable_alpha:
            inputs.remove(inputs[channel.io_index])
            outputs.remove(outputs[channel.io_index])

            shift = 2

        # Shift IO index
        for ch in yp.channels:
            if ch.io_index > channel.io_index:
                ch.io_index -= shift

        # Remove channel
        yp.channels.remove(channel_idx)
        #ypup.channels.remove(channel_idx)
        #yp.temp_channels.remove(channel_idx)

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

class YRenameYPaintTree(bpy.types.Operator):
    bl_idname = "node.y_rename_ypaint_tree"
    bl_label = "Rename " + ADDON_TITLE + " Group Name"
    bl_description = "Rename " + ADDON_TITLE + " Group Name"
    bl_options = {'REGISTER', 'UNDO'}

    name = StringProperty(name='New Name', description='New Name', default='')

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
    bl_label = "Change Active " + ADDON_TITLE + " Node"
    bl_description = "Change Active " + ADDON_TITLE + " Node"
    bl_options = {'REGISTER', 'UNDO'}

    name = StringProperty(name='Node Name', description=ADDON_TITLE + ' Node Name', default='')

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

class YFixDuplicatedLayers(bpy.types.Operator):
    bl_idname = "node.y_fix_duplicated_layers"
    bl_label = "Fix Duplicated Layers"
    bl_description = "Fix duplicated layers caused by duplicated " + ADDON_TITLE + " Node"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        group_node = get_active_ypaint_node()
        yp = group_node.node_tree.yp
        if len(yp.layers) == 0: return False
        layer_tree = get_tree(yp.layers[-1])
        return layer_tree.users > 1

    def execute(self, context):
        ypui = context.window_manager.ypui
        group_node = get_active_ypaint_node()
        tree = group_node.node_tree
        yp = tree.yp

        #img_mappings = []
        img_users = []
        img_nodes = []
        imgs = []

        # Make all layers single(dual) user
        for layer in yp.layers:
            oldtree = get_tree(layer)
            ttree = oldtree.copy()
            node = tree.nodes.get(layer.group_node)
            node.node_tree = ttree

            # Duplicate layer source groups
            if layer.source_group != '':
                source_group = ttree.nodes.get(layer.source_group)
                source_group.node_tree = source_group.node_tree.copy()
                source = source_group.node_tree.nodes.get(layer.source)

                for d in neighbor_directions:
                    s = ttree.nodes.get(getattr(layer, 'source_' + d))
                    if s: s.node_tree = source_group.node_tree

                # Duplicate layer modifier groups
                mod_group = source_group.node_tree.nodes.get(layer.mod_group)
                if mod_group:
                    mod_group.node_tree = mod_group.node_tree.copy()

                    mod_group_1 = source_group.node_tree.nodes.get(layer.mod_group_1)
                    if mod_group_1: mod_group_1.node_tree = mod_group.node_tree

            else:
                source = ttree.nodes.get(layer.source)

                # Duplicate layer modifier groups
                mod_group = ttree.nodes.get(layer.mod_group)
                if mod_group:
                    mod_group.node_tree = mod_group.node_tree.copy()

                    mod_group_1 = ttree.nodes.get(layer.mod_group_1)
                    if mod_group_1: mod_group_1.node_tree = mod_group.node_tree

            if layer.type == 'IMAGE': # and ypui.make_image_single_user:
                img = source.image
                if img:
                    #mapping = get_layer_mapping(layer)
                    #img_mappings.append(mapping)
                    img_users.append(layer)
                    img_nodes.append(source)
                    imgs.append(img)
                    #source.image = img.copy()

            # Duplicate masks
            for mask in layer.masks:
                if mask.group_node != '':
                    mask_group =  ttree.nodes.get(mask.group_node)
                    mask_group.node_tree = mask_group.node_tree.copy()
                    mask_source = mask_group.node_tree.nodes.get(mask.source)

                    for d in neighbor_directions:
                        s = ttree.nodes.get(getattr(mask, 'source_' + d))
                        if s: s.node_tree = mask_group.node_tree
                else:
                    mask_source = ttree.nodes.get(mask.source)

                if mask.type == 'IMAGE': # and ypui.make_image_single_user:
                    img = mask_source.image
                    if img:
                        #mapping = get_mask_mapping(mask)
                        #img_mappings.append(mapping)
                        img_users.append(mask)
                        img_nodes.append(mask_source)
                        imgs.append(img)
                        #mask_source.image = img.copy()

            # Duplicate channel modifiers
            for i, ch in enumerate(layer.channels):

                mod_group = ttree.nodes.get(ch.mod_group)
                if mod_group:
                    mod_group.node_tree = mod_group.node_tree.copy()

                    for d in neighbor_directions:
                        m = ttree.nodes.get(getattr(ch, 'mod_' + d))
                        if m: m.node_tree = mod_group.node_tree
                
            # Duplicate single user lib tree
            for node in ttree.nodes:
                if (node.type == 'GROUP' and node.node_tree and 
                        re.match(r'^.+_Copy\.*\d{0,3}$', node.node_tree.name)):
                    node.node_tree = node.node_tree.copy()

        if ypui.make_image_single_user:

            # Copy baked image
            for ch in yp.channels:
                baked = tree.nodes.get(ch.baked)
                if baked and baked.image:
                    baked.image = baked.image.copy()

                    # Also rename path because why not? NO, because it will cause image lost
                    #path = baked.image.filepath
                    #ext = os.path.splitext(path)[1]
                    #baked.image.filepath = os.path.dirname(path) + baked.image.name + ext

            already_copied_ids = []

            # Copy image on layer and masks
            for i, img in enumerate(imgs):

                if img.yia.is_image_atlas:
                    segment = img.yia.segments.get(img_users[i].segment_name)

                    # create new segment based on previous one
                    new_segment = ImageAtlas.get_set_image_atlas_segment(segment.width, segment.height,
                            img.yia.color, img.is_float, img, segment)

                    #print(img_users[i], new_segment.tile_x, new_segment.tile_y)

                    img_users[i].segment_name = new_segment.name

                    # Change image if different image is returned
                    if new_segment.id_data != img:
                        img_nodes[i].image = new_segment.id_data

                    # Update layer transform
                    update_mapping(img_users[i])

                elif i not in already_copied_ids:
                    # Copy image if not atlas
                    img_nodes[i].image = img.copy()

                    # Check other nodes using the same image
                    for j, imgg in enumerate(imgs):
                        if j != i and imgg == img:
                            img_nodes[j].image = img_nodes[i].image
                            already_copied_ids.append(j)

        # Refresh mapping and stuff
        yp.active_layer_index = yp.active_layer_index

        return {'FINISHED'}

def fix_missing_vcol(obj, name, src):
    vcol = obj.data.vertex_colors.new(name)
    src.attribute_name = name

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
        return True

    def execute(self, context):
        group_node = get_active_ypaint_node()
        tree = group_node.node_tree
        yp = tree.yp
        obj = context.object

        for layer in yp.layers:
            if layer.type in {'IMAGE' , 'VCOL'}:
                src = get_layer_source(layer)

                if layer.type == 'IMAGE' and not src.image:
                    fix_missing_img(layer.name, src, False)

                elif (layer.type == 'VCOL' and obj.type == 'MESH' 
                        and not obj.data.vertex_colors.get(src.attribute_name)):
                    fix_missing_vcol(obj, layer.name, src)

            for mask in layer.masks:
                if mask.type in {'IMAGE' , 'VCOL'}:
                    mask_src = get_mask_source(mask)

                    if mask.type == 'IMAGE' and not mask_src.image:
                        fix_missing_img(mask.name, mask_src, True)

                    elif (mask.type == 'VCOL' and obj.type == 'MESH' 
                            and not obj.data.vertex_colors.get(mask_src.attribute_name)):
                        fix_missing_vcol(obj, mask.name, mask_src)

        return {'FINISHED'}

def update_channel_name(self, context):
    T = time.time()

    wm = context.window_manager
    group_tree = self.id_data
    yp = group_tree.yp

    if yp.halt_reconnect or yp.halt_update:
        return

    group_tree.inputs[self.io_index].name = self.name
    group_tree.outputs[self.io_index].name = self.name

    if self.type == 'RGB' and self.enable_alpha:
        group_tree.inputs[self.io_index+1].name = self.name + ' Alpha'
        group_tree.outputs[self.io_index+1].name = self.name + ' Alpha'

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

def update_preview_mode(self, context):
    try:
        mat = bpy.context.object.active_material
        tree = mat.node_tree
        nodes = tree.nodes
        group_node = get_active_ypaint_node()
        yp = group_node.node_tree.yp
        channel = yp.channels[yp.active_channel_index]
        index = yp.active_channel_index
    except: return

    # Search for preview node
    preview = nodes.get('Emission Viewer')

    if self.preview_mode:

        # Search for output
        output = get_active_mat_output_node(tree)

        if not output: return

        # Remember output and original bsdf
        mat.yp.ori_output = output.name
        ori_bsdf = output.inputs[0].links[0].from_node

        if not preview:
            preview = nodes.new('ShaderNodeEmission')
            preview.name = 'Emission Viewer'
            preview.label = 'Preview'
            preview.hide = True
            preview.location = (output.location.x, output.location.y + 30.0)

        # Only remember original BSDF if its not the preview node itself
        if ori_bsdf != preview:
            mat.yp.ori_bsdf = ori_bsdf.name

        if channel.type == 'RGB' and channel.enable_alpha:
            from_socket = [link.from_socket for link in preview.inputs[0].links]
            if not from_socket: 
                tree.links.new(group_node.outputs[channel.io_index], preview.inputs[0])
            else:
                from_socket = from_socket[0]
                color_output = group_node.outputs[channel.io_index]
                alpha_output = group_node.outputs[channel.io_index+1]
                if from_socket == color_output:
                    tree.links.new(alpha_output, preview.inputs[0])
                else:
                    tree.links.new(color_output, preview.inputs[0])
        else:
            tree.links.new(group_node.outputs[channel.io_index], preview.inputs[0])
        tree.links.new(preview.outputs[0], output.inputs[0])
    else:
        try: nodes.remove(preview)
        except: pass

        bsdf = nodes.get(mat.yp.ori_bsdf)
        output = nodes.get(mat.yp.ori_output)
        mat.yp.ori_bsdf = ''
        mat.yp.ori_output = ''

        try: tree.links.new(bsdf.outputs[0], output.inputs[0])
        except: pass

def update_active_yp_channel(self, context):
    obj = context.object
    tree = self.id_data
    yp = tree.yp
    ch = yp.channels[yp.active_channel_index]
    
    if yp.preview_mode: yp.preview_mode = True

    if yp.use_baked:
        baked = tree.nodes.get(ch.baked)
        if baked and baked.image:
            update_image_editor_image(context, baked.image)

        if obj.type == 'MESH':
            if hasattr(obj.data, 'uv_textures'):
                uv_layers = self.uv_layers = obj.data.uv_textures
            else: uv_layers = self.uv_layers = obj.data.uv_layers

            baked_uv_map = tree.nodes.get(BAKED_UV)
            if baked_uv_map:
                uv_layers.active = uv_layers.get(baked_uv_map.uv_map)

def update_layer_index(self, context):
    #T = time.time()
    scene = context.scene
    obj = context.object
    group_tree = self.id_data
    nodes = group_tree.nodes
    ypui = context.window_manager.ypui

    if (len(self.layers) == 0 or
        self.active_layer_index >= len(self.layers) or self.active_layer_index < 0): 
        update_image_editor_image(context, None)
        scene.tool_settings.image_paint.canvas = None
        #print('INFO: Active layer is updated at {:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        return

    layer = self.layers[self.active_layer_index]
    tree = get_tree(layer)
    yp = layer.id_data.yp

    # Set image paint mode to Image
    scene.tool_settings.image_paint.mode = 'IMAGE'

    uv_name = ''
    image = None
    vcol = None
    src_of_img = None
    mapping = None

    for mask in layer.masks:
        if mask.active_edit:
            source = get_mask_source(mask)
            if mask.type == 'IMAGE':
                uv_name = mask.uv_name
                image = source.image
                src_of_img = mask
                mapping = get_mask_mapping(mask)
            elif mask.type == 'VCOL' and obj.type == 'MESH':
                vcol = obj.data.vertex_colors.get(source.attribute_name)

    if not image and layer.type == 'IMAGE':
        uv_name = layer.uv_name
        source = get_layer_source(layer, tree)
        image = source.image
        src_of_img = layer
        mapping = get_layer_mapping(layer)

    if not vcol and layer.type == 'VCOL' and obj.type == 'MESH':
        source = get_layer_source(layer, tree)
        vcol = obj.data.vertex_colors.get(source.attribute_name)

    # Update image editor
    #if src_of_img and src_of_img.segment_name != '' and ypui.disable_auto_temp_uv_update:
    if ypui.disable_auto_temp_uv_update and mapping and is_transformed(mapping):
        update_image_editor_image(context, None)
        scene.tool_settings.image_paint.canvas = None
        yp.need_temp_uv_refresh = True
    else: 
        update_image_editor_image(context, image)
        # Update layer paint
        scene.tool_settings.image_paint.canvas = image
        yp.need_temp_uv_refresh = False

    # Update active vertex color
    if vcol and obj.data.vertex_colors.active != vcol:
        obj.data.vertex_colors.active = vcol

    # Update uv layer
    if obj.type == 'MESH':

        if ypui.disable_auto_temp_uv_update or not refresh_temp_uv(obj, src_of_img):
        #if not refresh_temp_uv(obj, src_of_img):

            if hasattr(obj.data, 'uv_textures'): # Blender 2.7 only
                uv_layers = obj.data.uv_textures
            else: uv_layers = obj.data.uv_layers

            for i, uv in enumerate(uv_layers):
                if uv.name == uv_name:
                    if uv_layers.active_index != i:
                        uv_layers.active_index = i
                    #break

                if uv.name == TEMP_UV:
                    uv_layers.remove(uv)

    #yp.need_temp_uv_refresh = False

    #print('INFO: Active layer is updated at {:0.2f}'.format((time.time() - T) * 1000), 'ms!')

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

    for layer in yp.layers:
        ch = layer.channels[channel_index]
        tree = get_tree(layer)

        Layer.set_layer_channel_linear_node(tree, layer, self, ch)

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
                color_ramp_linear = tree.nodes.get(mod.color_ramp_linear)
                if self.colorspace == 'SRGB':
                    color_ramp_linear.inputs[1].default_value = 1.0/GAMMA
                else: color_ramp_linear.inputs[1].default_value = 1.0

def update_channel_alpha(self, context):
    mat = get_active_material()
    group_tree = self.id_data
    yp = group_tree.yp
    nodes = group_tree.nodes
    inputs = group_tree.inputs
    outputs = group_tree.outputs

    if not self.enable_alpha:
        # Set material to use opaque
        if hasattr(mat, 'blend_method'): # Blender 2.8
            mat.blend_method = 'OPAQUE'
        else: # Blender 2.7
            mat.game_settings.alpha_blend = 'OPAQUE'

        node = get_active_ypaint_node()
        inp = node.inputs[self.io_index+1]
        outp = node.outputs[self.io_index+1]

        # Remember the connections
        if len(inp.links) > 0:
            self.ori_alpha_from.node = inp.links[0].from_node.name
            self.ori_alpha_from.socket = inp.links[0].from_socket.name
        for link in outp.links:
            con = self.ori_alpha_to.add()
            con.node = link.to_node.name
            con.socket = link.to_socket.name

    # Update channel io
    check_all_channel_ios(yp)

    if self.enable_alpha:

        # Set material to use alpha blend
        if hasattr(mat, 'blend_method'): # Blender 2.8
            mat.blend_method = 'BLEND'
        else: # Blender 2.7
            mat.game_settings.alpha_blend = 'ALPHA'

        # Get alpha index
        alpha_index = self.io_index+1

        # Set node default_value
        node = get_active_ypaint_node()
        node.inputs[alpha_index].default_value = 0.0

        # Try to relink to original connections
        tree = context.object.active_material.node_tree
        try:
            node_from = tree.nodes.get(self.ori_alpha_from.node)
            socket_from = node_from.outputs[self.ori_alpha_from.socket]
            tree.links.new(socket_from, node.inputs[alpha_index])
        except: pass

        for con in self.ori_alpha_to:
            try:
                node_to = tree.nodes.get(con.node)
                socket_to = node_to.inputs[con.socket]
                if len(socket_to.links) < 1:
                    tree.links.new(node.outputs[alpha_index], socket_to)
            except: pass

        # Reset memory
        self.ori_alpha_from.node = ''
        self.ori_alpha_from.socket = ''
        self.ori_alpha_to.clear()

    yp.refresh_tree = True

def update_disable_quick_toggle(self, context):
    yp = self

    for layer in yp.layers:
        Layer.update_layer_enable(layer, context)

        for mod in layer.modifiers:
            Modifier.update_modifier_enable(mod, context)

        for ch in layer.channels:
            for mod in ch.modifiers:
                Modifier.update_modifier_enable(mod, context)

        for mask in layer.masks:
            Mask.update_layer_mask_enable(mask, context)

    for ch in yp.channels:
        for mod in ch.modifiers:
            Modifier.update_modifier_enable(mod, context)

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
    node = StringProperty(default='')
    socket = StringProperty(default='')

class YPaintChannel(bpy.types.PropertyGroup):
    name = StringProperty(
            name='Channel Name', 
            description = 'Name of the channel',
            default='Albedo',
            update=update_channel_name)

    type = EnumProperty(
            name = 'Channel Type',
            items = (('VALUE', 'Value', ''),
                     ('RGB', 'RGB', ''),
                     ('NORMAL', 'Normal', '')),
            default = 'RGB')

    # Input output index
    io_index = IntProperty(default=-1)

    # Alpha for transparent materials
    enable_alpha = BoolProperty(default=False, update=update_channel_alpha)

    colorspace = EnumProperty(
            name = 'Color Space',
            description = "Non color won't converted to linear first before blending",
            items = colorspace_items,
            default='LINEAR',
            update=update_channel_colorspace)

    modifiers = CollectionProperty(type=Modifier.YPaintModifier)
    active_modifier_index = IntProperty(default=0)

    # Node names
    start_linear = StringProperty(default='')
    end_linear = StringProperty(default='')
    start_normal_filter = StringProperty(default='')

    # Baked nodes
    baked = StringProperty(default='')
    #baked_1 = StringProperty(default='')
    #baked_uv_map = StringProperty(default='')
    baked_normal = StringProperty(default='')
    baked_normal_flip = StringProperty(default='')
    #baked_mix = StringProperty(default='')

    # UI related
    expand_content = BoolProperty(default=False)
    expand_base_vector = BoolProperty(default=True)

    # Connection related
    ori_alpha_to = CollectionProperty(type=YNodeConnections)
    ori_alpha_from = PointerProperty(type=YNodeConnections)

class YPaint(bpy.types.PropertyGroup):

    is_ypaint_node = BoolProperty(default=False)
    is_ypaint_layer_node = BoolProperty(default=False)
    version = StringProperty(default='')

    # Channels
    channels = CollectionProperty(type=YPaintChannel)
    active_channel_index = IntProperty(default=0, update=update_active_yp_channel)

    # Layers
    layers = CollectionProperty(type=Layer.YLayer)
    active_layer_index = IntProperty(default=0, update=update_layer_index)

    # Temp channels to remember last channel selected when adding new layer
    #temp_channels = CollectionProperty(type=YChannelUI)
    preview_mode = BoolProperty(default=False, update=update_preview_mode)

    # Toggle to use baked results or not
    use_baked = BoolProperty(default=False, update=Bake.update_use_baked)

    # Path folder for auto save bake
    #bake_folder = StringProperty(default='')

    # Disable quick toggle for better shader performance
    disable_quick_toggle = BoolProperty(
            name = 'Disable Quick Toggle',
            description = 'Disable quick toggle to improve shader performance',
            default=False, update=update_disable_quick_toggle)

    # HACK: Refresh tree to remove glitchy normal
    refresh_tree = BoolProperty(default=False)

    # Useful to suspend update when adding new stuff
    halt_update = BoolProperty(default=False)

    # Useful to suspend node rearrangements and reconnections when adding new stuff
    halt_reconnect = BoolProperty(default=False)

    # Remind user to refresh UV after edit image layer mapping
    need_temp_uv_refresh = BoolProperty(default=False)

    # Index pointer to the UI
    #ui_index = IntProperty(default=0)

    #random_prop = BoolProperty(default=False)

class YPaintMaterialProps(bpy.types.PropertyGroup):
    ori_bsdf = StringProperty(default='')
    ori_output = StringProperty(default='')
    active_ypaint_node = StringProperty(default='')

class YPaintTimer(bpy.types.PropertyGroup):
    time = StringProperty(default='')

@persistent
def ypaint_hacks_and_scene_updates(scene):
    # Get active yp node
    group_node =  get_active_ypaint_node()
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

def register():
    bpy.utils.register_class(YQuickYPaintNodeSetup)
    bpy.utils.register_class(YNewYPaintNode)
    bpy.utils.register_class(YPaintNodeInputCollItem)
    bpy.utils.register_class(YNewYPaintChannel)
    bpy.utils.register_class(YMoveYPaintChannel)
    bpy.utils.register_class(YRemoveYPaintChannel)
    bpy.utils.register_class(YAddSimpleUVs)
    bpy.utils.register_class(YRenameYPaintTree)
    bpy.utils.register_class(YChangeActiveYPaintNode)
    bpy.utils.register_class(YFixDuplicatedLayers)
    bpy.utils.register_class(YFixMissingData)
    bpy.utils.register_class(YNodeConnections)
    bpy.utils.register_class(YPaintChannel)
    bpy.utils.register_class(YPaint)
    bpy.utils.register_class(YPaintMaterialProps)
    bpy.utils.register_class(YPaintTimer)

    # YPaint Props
    bpy.types.ShaderNodeTree.yp = PointerProperty(type=YPaint)
    bpy.types.Material.yp = PointerProperty(type=YPaintMaterialProps)
    bpy.types.WindowManager.yptimer = PointerProperty(type=YPaintTimer)

    # Handlers
    if hasattr(bpy.app.handlers, 'scene_update_pre'):
        bpy.app.handlers.scene_update_pre.append(ypaint_hacks_and_scene_updates)

def unregister():
    bpy.utils.unregister_class(YQuickYPaintNodeSetup)
    bpy.utils.unregister_class(YNewYPaintNode)
    bpy.utils.unregister_class(YPaintNodeInputCollItem)
    bpy.utils.unregister_class(YNewYPaintChannel)
    bpy.utils.unregister_class(YMoveYPaintChannel)
    bpy.utils.unregister_class(YRemoveYPaintChannel)
    bpy.utils.unregister_class(YAddSimpleUVs)
    bpy.utils.unregister_class(YRenameYPaintTree)
    bpy.utils.unregister_class(YChangeActiveYPaintNode)
    bpy.utils.unregister_class(YFixDuplicatedLayers)
    bpy.utils.unregister_class(YFixMissingData)
    bpy.utils.unregister_class(YNodeConnections)
    bpy.utils.unregister_class(YPaintChannel)
    bpy.utils.unregister_class(YPaint)
    bpy.utils.unregister_class(YPaintMaterialProps)
    bpy.utils.unregister_class(YPaintTimer)

    # Remove handlers
    if hasattr(bpy.app.handlers, 'scene_update_pre'):
        bpy.app.handlers.scene_update_pre.remove(ypaint_hacks_and_scene_updates)

