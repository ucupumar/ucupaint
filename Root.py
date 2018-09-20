import bpy, time, re
from bpy.props import *
from bpy.app.handlers import persistent
from .common import *
from .node_arrangements import *
from .node_connections import *
from . import lib, Modifier, Layer, Mask

TL_GROUP_SUFFIX = ' TexLayers'

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

def add_io_from_new_channel(group_tree, channel):
    # New channel should be the last item
    #channel = group_tree.tl.channels[-1]

    inp = group_tree.inputs.new(channel_socket_input_bl_idnames[channel.type], channel.name)
    out = group_tree.outputs.new(channel_socket_output_bl_idnames[channel.type], channel.name)

    #group_tree.inputs.move(index,new_index)
    #group_tree.outputs.move(index,new_index)

    if channel.type == 'VALUE':
        inp.min_value = 0.0
        inp.max_value = 1.0
    elif channel.type == 'RGB':
        inp.default_value = (1,1,1,1)
    elif channel.type == 'NORMAL':
        #inp.min_value = -1.0
        #inp.max_value = 1.0
        # Use 999 as normal z value so it will fallback to use geometry normal at checking process
        inp.default_value = (999,999,999) 

def set_input_default_value(group_node, channel, custom_value=None):
    #channel = group_node.node_tree.tl.channels[index]

    if custom_value:
        if channel.type == 'RGB' and len(custom_value) == 3:
            custom_value = (custom_value[0], custom_value[1], custom_value[2], 1)

        if BLENDER_28_GROUP_INPUT_HACK and channel.type in {'RGB', 'VALUE'}:
            if channel.type == 'RGB':
                channel.col_input = custom_value
                channel.val_input = 0.0
            elif channel.type == 'VALUE':
                channel.val_input = custom_value
        else:
            group_node.inputs[channel.io_index].default_value = custom_value
        return
    
    # Set default value
    if channel.type == 'RGB':
        if BLENDER_28_GROUP_INPUT_HACK:
            channel.col_input = (1,1,1,1)
            channel.val_input = 0.0
        else: group_node.inputs[channel.io_index].default_value = (1,1,1,1)

        if channel.alpha:
            if BLENDER_28_GROUP_INPUT_HACK:
                channel.val_input = 1.0
            else: group_node.inputs[channel.io_index+1].default_value = 1.0
    if channel.type == 'VALUE':
        if BLENDER_28_GROUP_INPUT_HACK:
            channel.val_input = 0.0
        else: group_node.inputs[channel.io_index].default_value = 0.0
    if channel.type == 'NORMAL':
        # Use 999 as normal z value so it will fallback to use geometry normal at checking process
        group_node.inputs[channel.io_index].default_value = (999,999,999)

def create_tl_channel_nodes(group_tree, channel, channel_idx):
    tl = group_tree.tl
    nodes = group_tree.nodes

    # Get start and end node
    start_node = nodes.get(tl.start)
    end_node = nodes.get(tl.end)

    start_linear = None
    end_linear = None

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
        start_normal_filter.node_tree = lib.get_node_tree_lib(lib.CHECK_INPUT_NORMAL)

    #start_entry = new_node(group_tree, channel, 'start_entry', 'NodeReroute', 'Start Entry')
    #end_entry = new_node(group_tree, channel, 'end_entry', 'NodeReroute', 'End Entry')

    #if channel.type == 'RGB':
    #    start_alpha_entry = new_node(group_tree, channel, 'start_alpha_entry', 'NodeReroute', 'Start Alpha Entry')
    #    end_alpha_entry = new_node(group_tree, channel, 'end_alpha_entry', 'NodeReroute', 'End Alpha Entry')

    # Modifier pipeline
    #start_rgb = new_node(group_tree, channel, 'start_rgb', 'NodeReroute', 'Start RGB')
    #start_alpha = new_node(group_tree, channel, 'start_alpha', 'NodeReroute', 'Start Alpha')
    #end_rgb = new_node(group_tree, channel, 'end_rgb', 'NodeReroute', 'End RGB')
    #end_alpha = new_node(group_tree, channel, 'end_alpha', 'NodeReroute', 'End Alpha')

    # Link between textures
    for i, t in reversed(list(enumerate(tl.textures))):

        # Add new channel
        c = t.channels.add()

        # Add new channel to mask
        tex_tree = get_tree(t)
        for mask in t.masks:
            mc = mask.channels.add()
            Mask.set_mask_multiply_and_total_nodes(tex_tree, mc, c)

        # Check and set mask intensity nodes
        Mask.check_set_mask_intensity_multiplier(tex_tree, t, target_ch=c)

        # Add new nodes
        Layer.create_texture_channel_nodes(group_tree, t, c)

        # Rearrange node inside textures
        reconnect_tex_nodes(t, channel_idx)
        rearrange_tex_nodes(t)

def create_new_group_tree(mat):

    #tlup = bpy.context.user_preferences.addons[__name__].preferences

    # Group name is based from the material
    group_name = mat.name + TL_GROUP_SUFFIX

    # Create new group tree
    group_tree = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')
    group_tree.tl.is_tl_node = True
    group_tree.tl.version = get_current_version_str()

    # Add new channel
    #channel = group_tree.tl.channels.add()
    #channel.name = 'Color'
    #channel.type = 'RGB'
    #group_tree.tl.temp_channels.add() # Also add temp channel
    #tlup.channels.add()

    #add_io_from_new_channel(group_tree, channel)
    #channel.io_index = 0

    # Create start and end node
    start = new_node(group_tree, group_tree.tl, 'start', 'NodeGroupInput', 'Start')
    end = new_node(group_tree, group_tree.tl, 'end', 'NodeGroupOutput', 'End')

    # Create solid alpha node
    solid_alpha = new_node(group_tree, group_tree.tl, 'solid_alpha', 'ShaderNodeValue', 'Solid Value')
    solid_alpha.outputs[0].default_value = 1.0

    # Create info nodes
    create_info_nodes(group_tree)

    # Link start and end node then rearrange the nodes
    #create_tl_channel_nodes(group_tree, channel, 0)
    reconnect_tl_nodes(group_tree)

    # Add ui for this tree
    #add_ui(group_tree.tl)

    return group_tree

def create_new_tl_channel(group_tree, name, channel_type, non_color=True, enable=False):
    tl = group_tree.tl

    # Add new channel
    channel = tl.channels.add()
    channel.name = name
    channel.type = channel_type

    # Add input and output to the tree
    add_io_from_new_channel(group_tree, channel)

    # Get last index
    last_index = len(tl.channels)-1

    # Get IO index
    io_index = last_index
    for ch in tl.channels:
        if ch.type == 'RGB' and ch.alpha:
            io_index += 1

    channel.io_index = io_index

    # Link new channel
    create_tl_channel_nodes(group_tree, channel, last_index)
    reconnect_tl_nodes(group_tree, last_index)
    #reconnect_tl_tex_nodes(group_tree, last_index)

    for tex in tl.textures:
        # New channel is disabled in texture by default
        tex.channels[last_index].enable = enable

    if channel_type in {'RGB', 'VALUE'}:
        if non_color:
            channel.colorspace = 'LINEAR'
        else: channel.colorspace = 'SRGB'

    # Add ui for this tree
    #add_ui(channel)

    return channel

#def update_quick_setup_type(self, context):
#    if self.type == 'PRINCIPLED':
#        self.roughness = True
#        self.normal = True
#    elif self.type == 'DIFFUSE':
#        self.roughness = False
#        self.normal = False

class YQuickSetupTLNode(bpy.types.Operator):
    bl_idname = "node.y_quick_setup_texture_layers_node"
    bl_label = "Quick Texture Layers Node Setup"
    bl_description = "Quick Texture Layers Node Setup"
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

    @classmethod
    def poll(cls, context):
        return context.object

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def check(self, context):
        return True

    def draw(self, context):
        #row = self.layout.row()
        if hasattr(bpy.utils, 'previews'): # Blender 2.7 only
            row = self.layout.split(percentage=0.35)
        else: row = self.layout.split(factor=0.35)
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
        mat.tl.active_tl_node = node.name

        # Add new channels
        if self.color:
            channel = create_new_tl_channel(group_tree, 'Color', 'RGB', non_color=False)
            inp = main_bsdf.inputs[0]
            set_input_default_value(node, channel, inp.default_value)
            links.new(node.outputs[channel.io_index], inp)

            # Enable, link, and disable alpha to remember which input was alpha connected to
            channel.alpha = True
            links.new(node.outputs[channel.io_index+1], mix_bsdf.inputs[0])
            channel.alpha = False

        if self.type == 'PRINCIPLED' and self.metallic:
            channel = create_new_tl_channel(group_tree, 'Metallic', 'VALUE', non_color=True)
            inp = main_bsdf.inputs['Metallic']
            set_input_default_value(node, channel, inp.default_value)
            links.new(node.outputs[channel.io_index], inp)

        if self.roughness:
            channel = create_new_tl_channel(group_tree, 'Roughness', 'VALUE', non_color=True)
            inp = main_bsdf.inputs['Roughness']
            set_input_default_value(node, channel, inp.default_value)
            links.new(node.outputs[channel.io_index], inp)

        if self.normal:
            channel = create_new_tl_channel(group_tree, 'Normal', 'NORMAL')
            inp = main_bsdf.inputs['Normal']
            set_input_default_value(node, channel)
            links.new(node.outputs[channel.io_index], inp)

        # Rearrange nodes
        rearrange_tl_nodes(group_tree)

        # Set new tl node location
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

        # Update UI
        context.window_manager.tlui.need_update = True

        return {'FINISHED'}

class YNewTLNode(bpy.types.Operator):
    bl_idname = "node.y_add_new_texture_layers_node"
    bl_label = "Add new Texture Layers Node"
    bl_description = "Add new texture layers node"
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
        tlui = context.window_manager.tlui

        # select only the new node
        for n in tree.nodes:
            n.select = False

        # Create new group tree
        group_tree = create_new_group_tree(mat)
        tl = group_tree.tl

        # Add new channel
        channel = create_new_tl_channel(group_tree, 'Color', 'RGB', non_color=False)

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

        # Rearrange nodes
        rearrange_tl_nodes(group_tree)

        # Update UI
        context.window_manager.tlui.need_update = True

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
    if hasattr(bpy.utils, 'previews'): # Blender 2.7 only
        items = [('VALUE', 'Value', '', lib.custom_icons[lib.channel_custom_icon_dict['VALUE']].icon_id, 0),
                 ('RGB', 'RGB', '', lib.custom_icons[lib.channel_custom_icon_dict['RGB']].icon_id, 1),
                 ('NORMAL', 'Normal', '', lib.custom_icons[lib.channel_custom_icon_dict['NORMAL']].icon_id, 2)]
    else: 
        items = [('VALUE', 'Value', '', lib.channel_icon_dict['VALUE'], 0),
                 ('RGB', 'RGB', '', lib.channel_icon_dict['RGB'], 1),
                 ('NORMAL', 'Normal', '', lib.channel_icon_dict['NORMAL'], 2)]

    return items

class YNodeInputCollItem(bpy.types.PropertyGroup):
    name = StringProperty(default='')
    node_name = StringProperty(default='')
    input_name = StringProperty(default='')

def update_connect_to(self, context):
    tl = get_active_texture_layers_node().node_tree.tl
    item = self.input_coll.get(self.connect_to)
    if item:
        self.name = get_unique_name(item.input_name, tl.channels)

class YNewTLChannel(bpy.types.Operator):
    bl_idname = "node.y_add_new_texture_layers_channel"
    bl_label = "Add new Texture Group Channel"
    bl_description = "Add new texture group channel"
    bl_options = {'REGISTER', 'UNDO'}

    name = StringProperty(
            name='Channel Name', 
            description = 'Name of the channel',
            default='Albedo')

    type = EnumProperty(
            name = 'Channel Type',
            items = new_channel_items)

    connect_to = StringProperty(name='Connect To', default='', update=update_connect_to)
    input_coll = CollectionProperty(type=YNodeInputCollItem)

    colorspace = EnumProperty(
            name = 'Color Space',
            description = "Non color won't converted to linear first before blending",
            items = colorspace_items,
            default='LINEAR')

    @classmethod
    def poll(cls, context):
        return get_active_texture_layers_node()

    def refresh_input_coll(self, context):
        # Refresh input names
        self.input_coll.clear()
        mat = get_active_material()
        nodes = mat.node_tree.nodes
        tl_node = get_active_texture_layers_node()

        for node in nodes:
            if node == tl_node: continue
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
        group_node = get_active_texture_layers_node()
        channels = group_node.node_tree.tl.channels

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
        if hasattr(bpy.utils, 'previews'): # Blender 2.7 only
            row = self.layout.split(percentage=0.4)
        else: row = self.layout.split(factor=0.4)

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
        mat = get_active_material()
        node = get_active_texture_layers_node()
        group_tree = node.node_tree
        tl = group_tree.tl
        #tlup = context.user_preferences.addons[__name__].preferences
        channels = tl.channels

        if len(tl.channels) > 19:
            self.report({'ERROR'}, "Maximum channel possible is 20")
            return {'CANCELLED'}

        # Check if channel with same name is already available
        same_channel = [c for c in channels if c.name == self.name]
        if same_channel:
            self.report({'ERROR'}, "Channel named '" + self.name +"' is already available!")
            return {'CANCELLED'}

        # Create new tl channel
        channel = create_new_tl_channel(group_tree, self.name, self.type, 
                non_color=self.colorspace == 'LINEAR')

        # Rearrange nodes
        rearrange_tl_nodes(group_tree)

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
                                channel.alpha = True
                                mat.node_tree.links.new(node.outputs[channel.io_index+1], l.to_node.inputs[0])
                                channel.alpha = False

        # Set input default value
        if inp and self.type != 'NORMAL': 
            set_input_default_value(node, channel, inp.default_value)
        else: set_input_default_value(node, channel)

        # Change active channel
        last_index = len(tl.channels)-1
        group_tree.tl.active_channel_index = last_index

        # Update UI
        context.window_manager.tlui.need_update = True

        print('INFO: Channel', channel.name, 'is created at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

        return {'FINISHED'}

def swap_channel_io(root_ch, swap_ch, io_index, io_index_swap, inputs, outputs):
    if root_ch.type == 'RGB' and root_ch.alpha:
        if swap_ch.type == 'RGB' and swap_ch.alpha:
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
        if swap_ch.type == 'RGB' and swap_ch.alpha:
            if io_index > io_index_swap:
                inputs.move(io_index, io_index_swap)
                outputs.move(io_index, io_index_swap)
            else:
                inputs.move(io_index, io_index_swap+1)
                outputs.move(io_index, io_index_swap+1)
        else:
            inputs.move(io_index, io_index_swap)
            outputs.move(io_index, io_index_swap)

class YMoveTLChannel(bpy.types.Operator):
    bl_idname = "node.y_move_texture_layers_channel"
    bl_label = "Move Texture Group Channel"
    bl_description = "Move texture group channel"
    bl_options = {'REGISTER', 'UNDO'}

    direction = EnumProperty(
            name = 'Direction',
            items = (('UP', 'Up', ''),
                     ('DOWN', 'Down', '')),
            default = 'UP')

    @classmethod
    def poll(cls, context):
        group_node = get_active_texture_layers_node()
        return group_node and len(group_node.node_tree.tl.channels) > 0

    def execute(self, context):
        group_node = get_active_texture_layers_node()
        group_tree = group_node.node_tree
        tl = group_tree.tl
        tlui = context.window_manager.tlui
        #tlup = context.user_preferences.addons[__name__].preferences
        inputs = group_tree.inputs
        outputs = group_tree.outputs

        # Get active channel
        index = tl.active_channel_index
        channel = tl.channels[index]
        num_chs = len(tl.channels)

        # Get new index
        if self.direction == 'UP' and index > 0:
            new_index = index-1
        elif self.direction == 'DOWN' and index < num_chs-1:
            new_index = index+1
        else:
            return {'CANCELLED'}

        # Swap collapse UI
        #temp_0 = getattr(tlui, 'show_channel_modifiers_' + str(index))
        #temp_1 = getattr(tlui, 'show_channel_modifiers_' + str(new_index))
        #setattr(tlui, 'show_channel_modifiers_' + str(index), temp_1)
        #setattr(tlui, 'show_channel_modifiers_' + str(new_index), temp_0)

        # Get IO index
        swap_ch = tl.channels[new_index]
        io_index = channel.io_index
        io_index_swap = swap_ch.io_index

        # Move IO
        swap_channel_io(channel, swap_ch, io_index, io_index_swap, inputs, outputs)

        # Move tex IO
        for tex in tl.textures:
            tree = get_tree(tex)
            swap_channel_io(channel, swap_ch, io_index, io_index_swap, tree.inputs, tree.outputs)

        # Move channel
        tl.channels.move(index, new_index)

        # Move tex channels
        for tex in tl.textures:
            tex.channels.move(index, new_index)

            # Move mask channels
            for mask in tex.masks:
                mask.channels.move(index, new_index)

        # Reindex IO
        i = 0
        for ch in tl.channels:
            ch.io_index = i
            i += 1
            if ch.type == 'RGB' and ch.alpha: i += 1

        # Rearrange nodes
        for tex in tl.textures:
            rearrange_tex_nodes(tex)
        rearrange_tl_nodes(group_tree)

        # Set active index
        tl.active_channel_index = new_index

        # Repoint channel index
        #repoint_channel_index(tl)

        # Update UI
        context.window_manager.tlui.need_update = True

        return {'FINISHED'}

class YRemoveTLChannel(bpy.types.Operator):
    bl_idname = "node.y_remove_texture_layers_channel"
    bl_label = "Remove Texture Group Channel"
    bl_description = "Remove texture group channel"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        group_node = get_active_texture_layers_node()
        return group_node and len(group_node.node_tree.tl.channels) > 0

    def execute(self, context):
        group_node = get_active_texture_layers_node()
        group_tree = group_node.node_tree
        tl = group_tree.tl
        tlui = context.window_manager.tlui
        #tlup = context.user_preferences.addons[__name__].preferences
        nodes = group_tree.nodes
        inputs = group_tree.inputs
        outputs = group_tree.outputs

        # Get active channel
        channel_idx = tl.active_channel_index
        channel = tl.channels[channel_idx]
        channel_name = channel.name

        # Collapse the UI
        #setattr(tlui, 'show_channel_modifiers_' + str(channel_idx), False)

        # Remove channel nodes from textures
        for t in tl.textures:
            ch = t.channels[channel_idx]
            ttree = get_tree(t)

            remove_node(ttree, ch, 'blend')
            remove_node(ttree, ch, 'start_rgb')
            remove_node(ttree, ch, 'start_alpha')
            remove_node(ttree, ch, 'end_rgb')
            remove_node(ttree, ch, 'end_alpha')
            remove_node(ttree, ch, 'intensity')

            remove_node(ttree, ch, 'source')
            remove_node(ttree, ch, 'linear')

            remove_node(ttree, ch, 'pipeline_frame')
            remove_node(ttree, ch, 'normal')
            remove_node(ttree, ch, 'normal_flip')
            remove_node(ttree, ch, 'bump')
            remove_node(ttree, ch, 'bump_base')
            remove_node(ttree, ch, 'neighbor_uv')
            remove_node(ttree, ch, 'source_n')
            remove_node(ttree, ch, 'source_s')
            remove_node(ttree, ch, 'source_e')
            remove_node(ttree, ch, 'source_w')
            remove_node(ttree, ch, 'mod_n')
            remove_node(ttree, ch, 'mod_s')
            remove_node(ttree, ch, 'mod_e')
            remove_node(ttree, ch, 'mod_w')
            remove_node(ttree, ch, 'bump_base_n')
            remove_node(ttree, ch, 'bump_base_s')
            remove_node(ttree, ch, 'bump_base_e')
            remove_node(ttree, ch, 'bump_base_w')
            remove_node(ttree, ch, 'fine_bump')
            remove_node(ttree, ch, 'intensity_multiplier')

            # Remove modifiers
            #if ch.mod_tree:
            if ch.mod_group != '':
                mod_group = ttree.nodes.get(ch.mod_group)
                bpy.data.node_groups.remove(mod_group.node_tree)
                ttree.nodes.remove(mod_group)
            else:
                for mod in ch.modifiers:
                    Modifier.delete_modifier_nodes(ttree, mod)

            # Remove tex IO
            ttree.inputs.remove(ttree.inputs[channel.io_index])
            ttree.outputs.remove(ttree.outputs[channel.io_index])

            if channel.type == 'RGB' and channel.alpha:
                ttree.inputs.remove(ttree.inputs[channel.io_index])
                ttree.outputs.remove(ttree.outputs[channel.io_index])

            # Remove mask bump, ramp, and channel
            #for mask in t.masks:
            #    #print(channel_idx, len(mask.channels))
            Mask.remove_mask_ramp_nodes(ttree, ch, True)
            Mask.remove_mask_bump_nodes(t, ch, channel_idx)
            Mask.remove_mask_channel(ttree, t, channel_idx)

            t.channels.remove(channel_idx)

        # Remove start and end nodes
        #remove_node(group_tree, channel, 'start_entry')
        #remove_node(group_tree, channel, 'end_entry')
        remove_node(group_tree, channel, 'start_linear')
        remove_node(group_tree, channel, 'end_linear')
        #remove_node(group_tree, channel, 'start_alpha_entry')
        #remove_node(group_tree, channel, 'end_alpha_entry')
        remove_node(group_tree, channel, 'start_normal_filter')

        # Remove channel modifiers
        remove_node(group_tree, channel, 'start_rgb')
        remove_node(group_tree, channel, 'start_alpha')
        remove_node(group_tree, channel, 'end_rgb')
        remove_node(group_tree, channel, 'end_alpha')
        remove_node(group_tree, channel, 'start_frame')
        remove_node(group_tree, channel, 'end_frame')

        for mod in channel.modifiers:
            Modifier.delete_modifier_nodes(group_tree, mod)

        # Remove channel from tree
        inputs.remove(inputs[channel.io_index])
        outputs.remove(outputs[channel.io_index])

        shift = 1

        if channel.type == 'RGB' and channel.alpha:
            inputs.remove(inputs[channel.io_index])
            outputs.remove(outputs[channel.io_index])

            shift = 2

        # Shift IO index
        for ch in tl.channels:
            if ch.io_index > channel.io_index:
                ch.io_index -= shift

        # Remove channel
        tl.channels.remove(channel_idx)
        #tlup.channels.remove(channel_idx)
        #tl.temp_channels.remove(channel_idx)

        # Rearrange and reconnect nodes
        for t in tl.textures:
            rearrange_tex_nodes(t)
            reconnect_tex_nodes(t)
        rearrange_tl_nodes(group_tree)

        # Set new active index
        if (tl.active_channel_index == len(tl.channels) and
            tl.active_channel_index > 0
            ): tl.active_channel_index -= 1

        # Repoint channel index
        #repoint_channel_index(tl)

        # Update UI
        context.window_manager.tlui.need_update = True

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

class YRenameTLTree(bpy.types.Operator):
    bl_idname = "node.y_rename_tl_tree"
    bl_label = "Rename Texture Layers Group Name"
    bl_description = "Rename Texture Layers Group Name"
    bl_options = {'REGISTER', 'UNDO'}

    name = StringProperty(name='New Name', description='New Name', default='')

    @classmethod
    def poll(cls, context):
        return get_active_texture_layers_node()

    def invoke(self, context, event):
        node = get_active_texture_layers_node()
        tree = node.node_tree

        self.name = tree.name
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, 'name')

    def execute(self, context):
        node = get_active_texture_layers_node()
        tree = node.node_tree
        tree.name = self.name
        return {'FINISHED'}

class YFixDuplicatedTextures(bpy.types.Operator):
    bl_idname = "node.y_fix_duplicated_textures"
    bl_label = "Fix Duplicated Textures"
    bl_description = "Fix dupliacted textures caused by duplicated Texture Layers Group Node"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        group_node = get_active_texture_layers_node()
        tl = group_node.node_tree.tl
        if len(tl.textures) == 0: return False
        tex_tree = get_tree(tl.textures[-1])
        return tex_tree.users > 1

    def execute(self, context):
        tlui = context.window_manager.tlui
        group_node = get_active_texture_layers_node()
        tree = group_node.node_tree
        tl = tree.tl

        # Make all textures single(dual) user
        for t in tl.textures:
            oldtree = get_tree(t)
            ttree = oldtree.copy()
            node = tree.nodes.get(t.group_node)
            node.node_tree = ttree

            if t.type == 'IMAGE' and tlui.make_image_single_user:
                if t.source_group != '':
                    source_group = ttree.nodes.get(t.source_group)
                    source_group.node_tree = source_group.node_tree.copy()
                    source = source_group.node_tree.nodes.get(t.source)
                else:
                    source = ttree.nodes.get(t.source)

                img = source.image

                source.image = img.copy()

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
        group_node = get_active_texture_layers_node()
        tree = group_node.node_tree
        tl = tree.tl
        obj = context.object

        for tex in tl.textures:
            if tex.type in {'IMAGE' , 'VCOL'}:
                src = get_tex_source(tex)

                if tex.type == 'IMAGE' and not src.image:
                    fix_missing_img(tex.name, src, False)

                elif (tex.type == 'VCOL' and obj.type == 'MESH' 
                        and not obj.data.vertex_colors.get(src.attribute_name)):
                    fix_missing_vcol(obj, tex.name, src)

            for mask in tex.masks:
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

    group_tree = self.id_data
    tl = group_tree.tl

    if self.io_index == -1: return

    if self.io_index < len(group_tree.inputs):
        group_tree.inputs[self.io_index].name = self.name
        group_tree.outputs[self.io_index].name = self.name

        if self.type == 'RGB' and self.alpha:
            group_tree.inputs[self.io_index+1].name = self.name + ' Alpha'
            group_tree.outputs[self.io_index+1].name = self.name + ' Alpha'

        for tex in tl.textures:
            tree = get_tree(tex)
            if self.io_index < len(tree.inputs):
                tree.inputs[self.io_index].name = self.name
                tree.outputs[self.io_index].name = self.name

                if self.type == 'RGB' and self.alpha:
                    tree.inputs[self.io_index+1].name = self.name + ' Alpha'
                    tree.outputs[self.io_index+1].name = self.name + ' Alpha'

            rearrange_tex_frame_nodes(tex, tree)
        
        rearrange_tl_frame_nodes(tl)

    print('INFO: Channel renamed at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

def update_preview_mode(self, context):
    try:
        mat = bpy.context.object.active_material
        tree = mat.node_tree
        nodes = tree.nodes
        group_node = get_active_texture_layers_node()
        tl = group_node.node_tree.tl
        channel = tl.channels[tl.active_channel_index]
        index = tl.active_channel_index
    except: return

    # Search for preview node
    preview = nodes.get('Emission Viewer')

    if self.preview_mode:

        # Search for output
        output = None
        for node in nodes:
            if node.bl_idname == 'ShaderNodeOutputMaterial' and node.is_active_output:
                output = node
                break

        if not output: return

        # Remember output and original bsdf
        mat.tl.ori_output = output.name
        ori_bsdf = output.inputs[0].links[0].from_node

        if not preview:
            preview = nodes.new('ShaderNodeEmission')
            preview.name = 'Emission Viewer'
            preview.label = 'Preview'
            preview.hide = True
            preview.location = (output.location.x, output.location.y + 30.0)

        # Only remember original BSDF if its not the preview node itself
        if ori_bsdf != preview:
            mat.tl.ori_bsdf = ori_bsdf.name

        if channel.type == 'RGB' and channel.alpha:
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

        bsdf = nodes.get(mat.tl.ori_bsdf)
        output = nodes.get(mat.tl.ori_output)
        mat.tl.ori_bsdf = ''
        mat.tl.ori_output = ''

        try: tree.links.new(bsdf.outputs[0], output.inputs[0])
        except: pass

def update_active_tl_channel(self, context):
    try: 
        group_node = get_active_texture_layers_node()
        tl = group_node.node_tree.tl
    except: return
    
    if tl.preview_mode: tl.preview_mode = True

def update_texture_index(self, context):
    T = time.time()
    scene = context.scene
    obj = context.object
    group_tree = self.id_data
    nodes = group_tree.nodes

    if (len(self.textures) == 0 or
        self.active_texture_index >= len(self.textures) or self.active_texture_index < 0): 
        update_image_editor_image(context, None)
        scene.tool_settings.image_paint.canvas = None
        #print('INFO: Active texture is updated at {:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        return

    tex = self.textures[self.active_texture_index]
    tree = get_tree(tex)

    # Set image paint mode to Image
    scene.tool_settings.image_paint.mode = 'IMAGE'

    uv_name = ''
    image = None
    vcol = None

    for mask in tex.masks:
        if mask.active_edit:
            source = get_mask_source(mask)
            if mask.type == 'IMAGE':
                uv_name = mask.uv_name
                image = source.image
            elif mask.type == 'VCOL' and obj.type == 'MESH':
                vcol = obj.data.vertex_colors.get(source.attribute_name)

    if not image and tex.type == 'IMAGE':
        uv_name = tex.uv_name
        source = get_tex_source(tex, tree)
        image = source.image

    if not vcol and tex.type == 'VCOL' and obj.type == 'MESH':
        source = get_tex_source(tex, tree)
        vcol = obj.data.vertex_colors.get(source.attribute_name)

    # Update image editor
    update_image_editor_image(context, image)

    # Update active vertex color
    if vcol and obj.data.vertex_colors.active != vcol:
        obj.data.vertex_colors.active = vcol

    # Update tex paint
    scene.tool_settings.image_paint.canvas = image

    # Update uv layer
    if obj.type == 'MESH':
        if hasattr(obj.data, 'uv_textures'): # Blender 2.7 only
            uv_layers = obj.data.uv_textures
        else: uv_layers = obj.data.uv_layers

        for i, uv in enumerate(uv_layers):
            if uv.name == uv_name:
                if uv_layers.active_index != i:
                    uv_layers.active_index = i
                break

    print('INFO: Active texture is updated at {:0.2f}'.format((time.time() - T) * 1000), 'ms!')

def update_channel_colorspace(self, context):
    group_tree = self.id_data
    tl = group_tree.tl
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
    for i, c in enumerate(tl.channels):
        if c == self:
            channel_index = i
            for mod in c.modifiers:
                if mod.type == 'RGB_TO_INTENSITY':
                    rgb2i = nodes.get(mod.rgb2i)
                    if self.colorspace == 'LINEAR':
                        rgb2i.inputs['Gamma'].default_value = 1.0
                    else: rgb2i.inputs['Gamma'].default_value = 1.0/GAMMA

                    if BLENDER_28_GROUP_INPUT_HACK:
                        match_group_input(rgb2i, 'Gamma')
                        #inp = rgb2i.node_tree.nodes.get('Group Input')
                        #if inp.outputs[3].links[0].to_socket.default_value != rgb2i.inputs['Gamma'].default_value:
                        #    inp.outputs[3].links[0].to_socket.default_value = rgb2i.inputs['Gamma'].default_value

    for tex in tl.textures:
        ch = tex.channels[channel_index]
        tree = get_tree(tex)

        Layer.set_tex_channel_linear_node(tree, tex, self, ch, rearrange=True)

        # Check for linear node
        #linear = tree.nodes.get(ch.linear)
        #if linear:
        #    if self.colorspace == 'LINEAR':
        #        #ch.tex_input = 'RGB_LINEAR'
        #        linear.inputs[1].default_value = 1.0
        #    else: linear.inputs[1].default_value = 1.0/GAMMA

        # NOTE: STILL BUGGY AS HELL
        #if self.colorspace == 'LINEAR':
        #    if ch.tex_input == 'RGB_SRGB':
        #        ch.tex_input = 'RGB_LINEAR'
        #    elif ch.tex_input == 'CUSTOM':
        #        ch.tex_input = 'CUSTOM'

        if ch.enable_mask_ramp:
            mr_linear = tree.nodes.get(ch.mr_linear)
            if mr_linear:
                if self.colorspace == 'SRGB':
                    mr_linear.inputs[1].default_value = 1.0/GAMMA
                else: mr_linear.inputs[1].default_value = 1.0

        for mod in ch.modifiers:

            if mod.type == 'RGB_TO_INTENSITY':
                rgb2i = tree.nodes.get(mod.rgb2i)
                if self.colorspace == 'LINEAR':
                    rgb2i.inputs['Gamma'].default_value = 1.0
                else: rgb2i.inputs['Gamma'].default_value = 1.0/GAMMA

                if BLENDER_28_GROUP_INPUT_HACK:
                    match_group_input(rgb2i, 'Gamma')

            if mod.type == 'OVERRIDE_COLOR':
                oc = tree.nodes.get(mod.oc)
                if self.colorspace == 'LINEAR':
                    oc.inputs['Gamma'].default_value = 1.0
                else: oc.inputs['Gamma'].default_value = 1.0/GAMMA

                if BLENDER_28_GROUP_INPUT_HACK:
                    match_group_input(oc, 'Gamma')

            if mod.type == 'COLOR_RAMP':
                color_ramp_linear = tree.nodes.get(mod.color_ramp_linear)
                if self.colorspace == 'SRGB':
                    color_ramp_linear.inputs[1].default_value = 1.0/GAMMA
                else: color_ramp_linear.inputs[1].default_value = 1.0

def update_channel_alpha(self, context):
    mat = get_active_material()
    group_tree = self.id_data
    tl = group_tree.tl
    nodes = group_tree.nodes
    links = group_tree.links
    inputs = group_tree.inputs
    outputs = group_tree.outputs

    #start_alpha_entry = nodes.get(self.start_alpha_entry)
    #end_alpha_entry = nodes.get(self.end_alpha_entry)
    #if not start_alpha_entry: return

    #start = nodes.get(tl.start)
    #end = nodes.get(tl.end)
    #end_alpha = nodes.get(self.end_alpha)

    #alpha_io_found = False
    #for out in start.outputs:
    #    for link in out.links:
    #        if link.to_socket == start_alpha_entry.inputs[0]:
    #            alpha_io_found = True
    #            break
    #    if alpha_io_found: break
    
    # Create alpha IO
    if self.alpha: #and not alpha_io_found:

        # Set material to use alpha blend
        if hasattr(mat, 'blend_method'): # Blender 2.8
            mat.blend_method = 'BLEND'
        else: # Blender 2.7
            mat.game_settings.alpha_blend = 'ALPHA'

        name = self.name + ' Alpha'
        inp = inputs.new('NodeSocketFloatFactor', name)
        out = outputs.new('NodeSocketFloat', name)

        # Set min max
        inp.min_value = 0.0
        inp.max_value = 1.0
        inp.default_value = 0.0

        last_index = len(inputs)-1
        alpha_index = self.io_index+1

        inputs.move(last_index, alpha_index)
        outputs.move(last_index, alpha_index)

        #links.new(start.outputs[alpha_index], start_alpha_entry.inputs[0])
        #if end_alpha:
        #    links.new(end_alpha.outputs[0], end.inputs[alpha_index])
        #elif end_alpha_entry:
        #    links.new(end_alpha_entry.outputs[0], end.inputs[alpha_index])

        # Set node default_value
        node = get_active_texture_layers_node()
        node.inputs[alpha_index].default_value = 0.0

        # Shift other IO index
        for ch in tl.channels:
            if ch.io_index >= alpha_index:
                ch.io_index += 1

        # Add socket to texture tree
        for tex in tl.textures:
            tree = get_tree(tex)

            ti = tree.inputs.new('NodeSocketFloatFactor', name)
            to = tree.outputs.new('NodeSocketFloat', name)

            tree.inputs.move(last_index, alpha_index)
            tree.outputs.move(last_index, alpha_index)

            # Update texture blend nodes
            for i, ch in enumerate(tex.channels):
                root_ch = tl.channels[i]
                if Layer.update_blend_type_(root_ch, tex, ch):
                    reconnect_tex_nodes(tex, i)
                    rearrange_tex_nodes(tex)
        
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

        # Reconnect link between textures
        #reconnect_tl_tex_nodes(group_tree)
        reconnect_tl_nodes(group_tree, mod_reconnect=True)

        tl.refresh_tree = True

    # Remove alpha IO
    elif not self.alpha: #and alpha_io_found:

        # Set material to use opaque
        if hasattr(mat, 'blend_method'): # Blender 2.8
            mat.blend_method = 'OPAQUE'
        else: # Blender 2.7
            mat.game_settings.alpha_blend = 'OPAQUE'

        node = get_active_texture_layers_node()
        inp = node.inputs[self.io_index+1]
        outp = node.outputs[self.io_index+1]

        if BLENDER_28_GROUP_INPUT_HACK:
            # In case blend_found isn't found
            for link in outp.links:
                link.to_socket.default_value = 1.0

        # Remember the connections
        if len(inp.links) > 0:
            self.ori_alpha_from.node = inp.links[0].from_node.name
            self.ori_alpha_from.socket = inp.links[0].from_socket.name
        for link in outp.links:
            con = self.ori_alpha_to.add()
            con.node = link.to_node.name
            con.socket = link.to_socket.name

        inputs.remove(inputs[self.io_index+1])
        outputs.remove(outputs[self.io_index+1])

        # Relink inside tree
        #solid_alpha = nodes.get(tl.solid_alpha)
        #links.new(solid_alpha.outputs[0], start_alpha_entry.inputs[0])

        # Shift other IO index
        for ch in tl.channels:
            if ch.io_index > self.io_index:
                ch.io_index -= 1

        # Remove socket from texture tree
        for tex in tl.textures:
            tree = get_tree(tex)
            tree.inputs.remove(tree.inputs[self.io_index+1])
            tree.outputs.remove(tree.outputs[self.io_index+1])

            # Update texture blend nodes
            for i, ch in enumerate(tex.channels):
                root_ch = tl.channels[i]
                if Layer.update_blend_type_(root_ch, tex, ch):
                    reconnect_tex_nodes(tex, i)
                    rearrange_tex_nodes(tex)

        # Reconnect solid alpha to end alpha
        #links.new(start_alpha_entry.outputs[0], end_alpha_entry.inputs[0])
        reconnect_tl_nodes(group_tree, mod_reconnect=True)

        tl.refresh_tree = True

def update_col_input(self, context):
    group_node = get_active_texture_layers_node()
    group_tree = group_node.node_tree
    tl = group_tree.tl

    #if tl.halt_update: return
    if self.type != 'RGB': return

    group_node.inputs[self.io_index].default_value = self.col_input

    # Get start
    start_linear = group_tree.nodes.get(self.start_linear)
    if start_linear: start_linear.inputs[0].default_value = self.col_input

def update_val_input(self, context):
    group_node = get_active_texture_layers_node()
    group_tree = group_node.node_tree
    tl = group_tree.tl

    #if tl.halt_update: return
    if self.type == 'VALUE':
        group_node.inputs[self.io_index].default_value = self.val_input

        # Get start
        start_linear = group_tree.nodes.get(self.start_linear)
        if start_linear: start_linear.inputs[0].default_value = self.val_input

    elif self.alpha and self.type == 'RGB':
        group_node.inputs[self.io_index+1].default_value = self.val_input

        # Get index
        m = re.match(r'tl\.channels\[(\d+)\]', self.path_from_id())
        ch_index = int(m.group(1))

        blend_found = False
        for tex in tl.textures:
            for i, ch in enumerate(tex.channels):
                if i == ch_index:
                    tree = get_tree(tex)
                    blend = tree.nodes.get(ch.blend)
                    if blend and blend.type =='GROUP':
                        inp = blend.node_tree.nodes.get('Group Input')
                        inp.outputs['Alpha1'].links[0].to_socket.default_value = self.val_input
                        blend_found = True
                        break
            if blend_found: break

        # In case blend_found isn't found
        for link in group_node.outputs[self.io_index+1].links:
            link.to_socket.default_value = self.val_input

class YNodeConnections(bpy.types.PropertyGroup):
    node = StringProperty(default='')
    socket = StringProperty(default='')

class YRootChannel(bpy.types.PropertyGroup):
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

    # Blender 2.8 need these
    col_input = FloatVectorProperty(name='Color Input', size=4, subtype='COLOR', 
            default=(0.0,0.0,0.0,1.0), min=0.0, max=1.0,
            update=update_col_input)

    val_input = FloatProperty(default=1.0, min=0.0, max=1.0, subtype='FACTOR',
            update=update_val_input)

    # Input output index
    io_index = IntProperty(default=-1)

    # Alpha
    alpha = BoolProperty(default=False, update=update_channel_alpha)

    colorspace = EnumProperty(
            name = 'Color Space',
            description = "Non color won't converted to linear first before blending",
            items = colorspace_items,
            default='LINEAR',
            update=update_channel_colorspace)

    modifiers = CollectionProperty(type=Modifier.YTextureModifier)
    active_modifier_index = IntProperty(default=0)

    # Node names
    start_linear = StringProperty(default='')
    #start_entry = StringProperty(default='')
    #start_alpha_entry = StringProperty(default='')
    start_normal_filter = StringProperty(default='')

    #end_entry = StringProperty(default='')
    #end_alpha_entry = StringProperty(default='')
    end_linear = StringProperty(default='')

    start_frame = StringProperty(default='')
    end_frame = StringProperty(default='')

    # For modifiers
    start_rgb = StringProperty(default='')
    start_alpha = StringProperty(default='')
    end_rgb = StringProperty(default='')
    end_alpha = StringProperty(default='')
    #modifier_frame = StringProperty(default='')

    # UI related
    expand_content = BoolProperty(default=False)
    expand_base_vector = BoolProperty(default=True)

    # Connection related
    ori_alpha_to = CollectionProperty(type=YNodeConnections)
    ori_alpha_from = PointerProperty(type=YNodeConnections)

class YTextureLayersRoot(bpy.types.PropertyGroup):
    is_tl_node = BoolProperty(default=False)
    is_tl_tex_node = BoolProperty(default=False)
    version = StringProperty(default='')

    # Channels
    channels = CollectionProperty(type=YRootChannel)
    active_channel_index = IntProperty(default=0, update=update_active_tl_channel)

    # Textures
    textures = CollectionProperty(type=Layer.YTextureLayer)
    active_texture_index = IntProperty(default=0, update=update_texture_index)

    # Solid alpha for modifier alpha input
    solid_alpha = StringProperty(default='')

    # Node names
    start = StringProperty(default='')
    #start_frame = StringProperty(default='')

    end = StringProperty(default='')
    #end_entry_frame = StringProperty(default='')
    #end_linear_frame = StringProperty(default='')

    # Temp channels to remember last channel selected when adding new texture
    #temp_channels = CollectionProperty(type=YChannelUI)

    preview_mode = BoolProperty(default=False, update=update_preview_mode)

    # HACK: Refresh tree to remove glitchy normal
    refresh_tree = BoolProperty(default=False)

    # Useful to suspend update when adding new stuff
    halt_update = BoolProperty(default=False)

    # Index pointer to the UI
    #ui_index = IntProperty(default=0)

    #random_prop = BoolProperty(default=False)

class YMaterialTLProps(bpy.types.PropertyGroup):
    ori_bsdf = StringProperty(default='')
    ori_output = StringProperty(default='')
    active_tl_node = StringProperty(default='')

@persistent
def ytl_hacks_and_scene_updates(scene):
    # Get active tl node
    group_node =  get_active_texture_layers_node()
    if not group_node: return
    tree = group_node.node_tree
    tl = tree.tl

    # HACK: Refresh normal
    if tl.refresh_tree:
        # Just reconnect any connection twice to refresh normal
        for link in tree.links:
            from_socket = link.from_socket
            to_socket = link.to_socket
            tree.links.new(from_socket, to_socket)
            tree.links.new(from_socket, to_socket)
            break
        tl.refresh_tree = False

    # Check single user image texture
    if len(tl.textures) > 0:
        tex = tl.textures[tl.active_texture_index]

        if tex.type == 'IMAGE':
            source = get_tex_source(tex)
            img = source.image

            if img and img.name != tex.image_name:
                # Update active texture paint image
                tex.image_name = img.name
                tl.active_texture_index = tl.active_texture_index

def register():
    bpy.utils.register_class(YQuickSetupTLNode)
    bpy.utils.register_class(YNewTLNode)
    bpy.utils.register_class(YNodeInputCollItem)
    bpy.utils.register_class(YNewTLChannel)
    bpy.utils.register_class(YMoveTLChannel)
    bpy.utils.register_class(YRemoveTLChannel)
    bpy.utils.register_class(YAddSimpleUVs)
    bpy.utils.register_class(YRenameTLTree)
    bpy.utils.register_class(YFixDuplicatedTextures)
    bpy.utils.register_class(YFixMissingData)
    bpy.utils.register_class(YNodeConnections)
    bpy.utils.register_class(YRootChannel)
    bpy.utils.register_class(YTextureLayersRoot)
    bpy.utils.register_class(YMaterialTLProps)

    # TL Props
    bpy.types.ShaderNodeTree.tl = PointerProperty(type=YTextureLayersRoot)
    bpy.types.Material.tl = PointerProperty(type=YMaterialTLProps)

    # Handlers
    if hasattr(bpy.app.handlers, 'scene_update_pre'):
        bpy.app.handlers.scene_update_pre.append(ytl_hacks_and_scene_updates)

def unregister():
    bpy.utils.unregister_class(YQuickSetupTLNode)
    bpy.utils.unregister_class(YNewTLNode)
    bpy.utils.unregister_class(YNodeInputCollItem)
    bpy.utils.unregister_class(YNewTLChannel)
    bpy.utils.unregister_class(YMoveTLChannel)
    bpy.utils.unregister_class(YRemoveTLChannel)
    bpy.utils.unregister_class(YAddSimpleUVs)
    bpy.utils.unregister_class(YRenameTLTree)
    bpy.utils.unregister_class(YFixDuplicatedTextures)
    bpy.utils.unregister_class(YFixMissingData)
    bpy.utils.unregister_class(YNodeConnections)
    bpy.utils.unregister_class(YRootChannel)
    bpy.utils.unregister_class(YTextureLayersRoot)
    bpy.utils.unregister_class(YMaterialTLProps)

    # Remove handlers
    if hasattr(bpy.app.handlers, 'scene_update_pre'):
        bpy.app.handlers.scene_update_pre.remove(ytl_hacks_and_scene_updates)

