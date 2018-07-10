import bpy, time
from bpy.props import *
from bpy.app.handlers import persistent
from .common import *
from .node_arrangements import *
from .node_connections import *
from . import lib, Modifier, Layer

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
        group_node.inputs[channel.io_index].default_value = custom_value
        return
    
    # Set default value
    if channel.type == 'RGB':
        group_node.inputs[channel.io_index].default_value = (1,1,1,1)
        if channel.alpha:
            group_node.inputs[channel.io_index+1].default_value = 1.0
    if channel.type == 'VALUE':
        group_node.inputs[channel.io_index].default_value = 0.0
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
            start_linear = nodes.new('ShaderNodeGamma')
        else: 
            start_linear = nodes.new('ShaderNodeMath')
            start_linear.operation = 'POWER'
        start_linear.label = 'Start Linear'
        start_linear.inputs[1].default_value = 1.0/GAMMA

        #start_linear.parent = start_frame
        channel.start_linear = start_linear.name

        if channel.type == 'RGB':
            end_linear = nodes.new('ShaderNodeGamma')
        else: 
            end_linear = nodes.new('ShaderNodeMath')
            end_linear.operation = 'POWER'
        end_linear.label = 'End Linear'
        end_linear.inputs[1].default_value = GAMMA

        #end_linear.parent = end_linear_frame
        channel.end_linear = end_linear.name

    if channel.type == 'NORMAL':
        start_normal_filter = nodes.new('ShaderNodeGroup')
        start_normal_filter.node_tree = lib.get_node_tree_lib(lib.CHECK_INPUT_NORMAL)
        #start_normal_filter.parent = start_frame
        start_normal_filter.label = 'Start Normal Filter'
        channel.start_normal_filter = start_normal_filter.name

    start_entry = nodes.new('NodeReroute')
    start_entry.label = 'Start Entry'
    #start_entry.parent = start_frame
    channel.start_entry = start_entry.name

    end_entry = nodes.new('NodeReroute')
    end_entry.label = 'End Entry'
    #end_entry.parent = end_entry_frame
    channel.end_entry = end_entry.name

    if channel.type == 'RGB':
        start_alpha_entry = nodes.new('NodeReroute')
        start_alpha_entry.label = 'Start Alpha Entry'
        #start_alpha_entry.parent = start_frame
        channel.start_alpha_entry = start_alpha_entry.name

        end_alpha_entry = nodes.new('NodeReroute')
        end_alpha_entry.label = 'End Alpha Entry'
        #end_alpha_entry.parent = end_entry_frame
        channel.end_alpha_entry = end_alpha_entry.name

    # Modifier pipeline
    start_rgb = nodes.new('NodeReroute')
    start_rgb.label = 'Start RGB'
    #start_rgb.parent = modifier_frame
    channel.start_rgb = start_rgb.name

    start_alpha = nodes.new('NodeReroute')
    start_alpha.label = 'Start Alpha'
    #start_alpha.parent = modifier_frame
    channel.start_alpha = start_alpha.name

    end_rgb = nodes.new('NodeReroute')
    end_rgb.label = 'End RGB'
    #end_rgb.parent = modifier_frame
    channel.end_rgb = end_rgb.name

    end_alpha = nodes.new('NodeReroute')
    end_alpha.label = 'End Alpha'
    #end_alpha.parent = modifier_frame
    channel.end_alpha = end_alpha.name

    # Link between textures
    for i, t in reversed(list(enumerate(tl.textures))):

        # Add new channel
        c = t.channels.add()
        c.channel_index = channel_idx
        c.texture_index = i

        # Add new nodes
        Layer.create_texture_channel_nodes(group_tree, t, c)

        # Rearrange node inside textures
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
    start_node = group_tree.nodes.new('NodeGroupInput')
    end_node = group_tree.nodes.new('NodeGroupOutput')
    group_tree.tl.start = start_node.name
    group_tree.tl.end = end_node.name

    # Create solid alpha node
    solid_alpha = group_tree.nodes.new('ShaderNodeValue')
    solid_alpha.outputs[0].default_value = 1.0
    solid_alpha.label = 'Solid Alpha'
    group_tree.tl.solid_alpha = solid_alpha.name

    # Create info nodes
    create_info_nodes(group_tree)

    # Link start and end node then rearrange the nodes
    #create_tl_channel_nodes(group_tree, channel, 0)
    reconnect_tl_channel_nodes(group_tree)

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
    reconnect_tl_channel_nodes(group_tree, last_index)
    reconnect_tl_tex_nodes(group_tree, last_index)

    for tex in tl.textures:
        # New channel is disabled in texture by default
        tex.channels[last_index].enable = enable

    if channel_type in {'RGB', 'VALUE'}:
        if non_color:
            channel.colorspace = 'LINEAR'
        else: channel.colorspace = 'SRGB'

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
        row = self.layout.split(percentage=0.35)
        col = row.column()
        col.label('Type:')
        ccol = col.column(align=True)
        ccol.label('Channels:')
        if self.type == 'PRINCIPLED':
            ccol.label('')
        ccol.label('')
        ccol.label('')
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

        # Set default input value
        set_input_default_value(node, channel)

        # Rearrange nodes
        rearrange_tl_nodes(group_tree)

        # Set the location of new node
        node.select = True
        tree.nodes.active = node
        node.location = space.cursor_location

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
    items = [('VALUE', 'Value', '', lib.custom_icons['value_channel'].icon_id, 0),
             ('RGB', 'RGB', '', lib.custom_icons['rgb_channel'].icon_id, 1),
             ('NORMAL', 'Normal', '', lib.custom_icons['vector_channel'].icon_id, 2)]

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
        row = self.layout.split(percentage=0.4)

        col = row.column(align=False)
        col.label('Name:')
        col.label('Connect To:')
        if self.type != 'NORMAL':
            col.label('Color Space:')

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

def repoint_channel_index(tl):
    for tex in tl.textures:
        for i, ch in enumerate(tex.channels):
            if ch.channel_index != i:
                ch.channel_index = i

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
            swap_channel_io(channel, swap_ch, io_index, io_index_swap, tex.tree.inputs, tex.tree.outputs)

        # Move channel
        tl.channels.move(index, new_index)

        # Move tex channel
        for tex in tl.textures:
            tex.channels.move(index, new_index)

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
        repoint_channel_index(tl)

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

            t.tree.nodes.remove(t.tree.nodes.get(ch.blend))
            t.tree.nodes.remove(t.tree.nodes.get(ch.start_rgb))
            t.tree.nodes.remove(t.tree.nodes.get(ch.start_alpha))
            t.tree.nodes.remove(t.tree.nodes.get(ch.end_rgb))
            t.tree.nodes.remove(t.tree.nodes.get(ch.end_alpha))
            #t.tree.nodes.remove(t.tree.nodes.get(ch.modifier_frame_))
            t.tree.nodes.remove(t.tree.nodes.get(ch.intensity))
            #t.tree.nodes.remove(t.tree.nodes.get(ch.linear))
            try: t.tree.nodes.remove(t.tree.nodes.get(ch.alpha_passthrough_))
            except: pass
            try: t.tree.nodes.remove(t.tree.nodes.get(ch.normal))
            except: pass
            try: t.tree.nodes.remove(t.tree.nodes.get(ch.normal_flip))
            except: pass
            try: t.tree.nodes.remove(t.tree.nodes.get(ch.bump))
            except: pass
            try: t.tree.nodes.remove(t.tree.nodes.get(ch.bump_base))
            except: pass
            try: t.tree.nodes.remove(t.tree.nodes.get(ch.pipeline_frame))
            except: pass
            try: t.tree.nodes.remove(t.tree.nodes.get(ch.neighbor_uv))
            except: pass
            try: t.tree.nodes.remove(t.tree.nodes.get(ch.source_n))
            except: pass
            try: t.tree.nodes.remove(t.tree.nodes.get(ch.source_s))
            except: pass
            try: t.tree.nodes.remove(t.tree.nodes.get(ch.source_e))
            except: pass
            try: t.tree.nodes.remove(t.tree.nodes.get(ch.source_w))
            except: pass
            try: t.tree.nodes.remove(t.tree.nodes.get(ch.mod_n))
            except: pass
            try: t.tree.nodes.remove(t.tree.nodes.get(ch.mod_s))
            except: pass
            try: t.tree.nodes.remove(t.tree.nodes.get(ch.mod_e))
            except: pass
            try: t.tree.nodes.remove(t.tree.nodes.get(ch.mod_w))
            except: pass
            try: t.tree.nodes.remove(t.tree.nodes.get(ch.bump_base_n))
            except: pass
            try: t.tree.nodes.remove(t.tree.nodes.get(ch.bump_base_s))
            except: pass
            try: t.tree.nodes.remove(t.tree.nodes.get(ch.bump_base_e))
            except: pass
            try: t.tree.nodes.remove(t.tree.nodes.get(ch.bump_base_w))
            except: pass
            try: t.tree.nodes.remove(t.tree.nodes.get(ch.fine_bump))
            except: pass
            try: t.tree.nodes.remove(t.tree.nodes.get(ch.intensity_multiplier))
            except: pass

            # Remove modifiers
            if ch.mod_tree:
                t.tree.nodes.remove(t.tree.nodes.get(ch.mod_group))
                bpy.data.node_groups.remove(ch.mod_tree)
            else:
                for mod in ch.modifiers:
                    Modifier.delete_modifier_nodes(t.tree.nodes, mod)

            # Remove tex IO
            t.tree.inputs.remove(t.tree.inputs[channel.io_index])
            t.tree.outputs.remove(t.tree.outputs[channel.io_index])

            if channel.type == 'RGB' and channel.alpha:
                t.tree.inputs.remove(t.tree.inputs[channel.io_index])
                t.tree.outputs.remove(t.tree.outputs[channel.io_index])

            t.channels.remove(channel_idx)

        # Remove start and end nodes
        nodes.remove(nodes.get(channel.start_entry))
        nodes.remove(nodes.get(channel.end_entry))
        try: nodes.remove(nodes.get(channel.start_linear)) 
        except: pass
        try: nodes.remove(nodes.get(channel.end_linear)) 
        except: pass
        try: nodes.remove(nodes.get(channel.start_alpha_entry)) 
        except: pass
        try: nodes.remove(nodes.get(channel.end_alpha_entry)) 
        except: pass
        try: nodes.remove(nodes.get(channel.start_normal_filter)) 
        except: pass

        # Remove channel modifiers
        try: nodes.remove(nodes.get(channel.start_rgb))
        except: pass
        try: nodes.remove(nodes.get(channel.start_alpha))
        except: pass
        try: nodes.remove(nodes.get(channel.end_rgb))
        except: pass
        try: nodes.remove(nodes.get(channel.end_alpha))
        except: pass
        try: nodes.remove(nodes.get(channel.start_frame))
        except: pass
        try: nodes.remove(nodes.get(channel.end_frame))
        except: pass
        #nodes.remove(nodes.get(channel.modifier_frame))

        for mod in channel.modifiers:
            Modifier.delete_modifier_nodes(nodes, mod)

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

        # Rearrange nodes
        for t in tl.textures:
            rearrange_tex_nodes(t)
        rearrange_tl_nodes(group_tree)

        # Set new active index
        if (tl.active_channel_index == len(tl.channels) and
            tl.active_channel_index > 0
            ): tl.active_channel_index -= 1

        # Repoint channel index
        repoint_channel_index(tl)

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
        return len(tl.textures) > 0 and tl.textures[0].tree.users > 3

    def execute(self, context):
        tlui = context.window_manager.tlui
        group_node = get_active_texture_layers_node()
        tree = group_node.node_tree
        tl = tree.tl

        # Make all textures single(dual) user
        for t in tl.textures:
            t.tree = t.tree.copy()
            node = tree.nodes.get(t.group_node)
            node.node_tree = t.tree

            if t.type == 'IMAGE' and tlui.make_image_single_user:
                if t.source_tree:
                    t.source_tree = t.source_tree.copy()
                    source_group = t.tree.nodes.get(t.source_group)
                    source_group.node_tree = t.source_tree
                    source = t.source_tree.nodes.get(t.source)
                else:
                    source = t.tree.nodes.get(t.source)

                img = source.image

                source.image = img.copy()

        return {'FINISHED'}

def update_channel_name(self, context):
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
            if self.io_index < len(tex.tree.inputs):
                tex.tree.inputs[self.io_index].name = self.name
                tex.tree.outputs[self.io_index].name = self.name

                if self.type == 'RGB' and self.alpha:
                    tex.tree.inputs[self.io_index+1].name = self.name + ' Alpha'
                    tex.tree.outputs[self.io_index+1].name = self.name + ' Alpha'

            for i, ch in enumerate(tex.channels):
                if tl.channels[i] == self:
                    refresh_tex_channel_frame(self, ch, tex.tree.nodes)
        
        refresh_tl_channel_frame(self, group_tree.nodes)

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
    scene = context.scene
    obj = context.object
    group_tree = self.id_data
    nodes = group_tree.nodes

    if (len(self.textures) == 0 or
        self.active_texture_index >= len(self.textures) or self.active_texture_index < 0): 
        update_image_editor_image(context, None)
        scene.tool_settings.image_paint.canvas = None
        return

    tex = self.textures[self.active_texture_index]

    # Set image paint mode to Image
    scene.tool_settings.image_paint.mode = 'IMAGE'

    uv_name = ''
    image = None

    for mask in tex.masks:
        if mask.type == 'IMAGE' and mask.active_edit:
            uv_map = tex.tree.nodes.get(mask.uv_map)
            uv_name = uv_map.uv_map
            if mask.tree:
                source = mask.tree.nodes.get(mask.source)
            else: source = tex.tree.nodes.get(mask.source)
            image = source.image

    if not image and tex.type == 'IMAGE':
        uv_map = tex.tree.nodes.get(tex.uv_map)
        uv_name = uv_map.uv_map
        if tex.source_tree:
            source = tex.source_tree.nodes.get(tex.source)
        else: source = tex.tree.nodes.get(tex.source)
        image = source.image

    # Update image editor
    update_image_editor_image(context, image)

    # Update tex paint
    scene.tool_settings.image_paint.canvas = image

    # Update uv layer
    if obj.type == 'MESH':
        for i, uv in enumerate(obj.data.uv_textures):
            if uv.name == uv_name:
                if obj.data.uv_textures.active_index != i:
                    obj.data.uv_textures.active_index = i
                break

def update_channel_colorspace(self, context):
    group_tree = self.id_data
    tl = group_tree.tl
    nodes = group_tree.nodes

    start_linear = nodes.get(self.start_linear)
    end_linear = nodes.get(self.end_linear)

    start_linear.mute = end_linear.mute = self.colorspace == 'LINEAR'

    # Check for modifier that aware of colorspace
    channel_index = -1
    for i, c in enumerate(tl.channels):
        if c == self:
            channel_index = i
            for mod in c.modifiers:
                if mod.type == 'RGB_TO_INTENSITY':
                    rgb2i = nodes.get(mod.rgb2i)
                    if self.colorspace == 'LINEAR':
                        rgb2i.inputs['Linearize'].default_value = 0.0
                    else: rgb2i.inputs['Linearize'].default_value = 1.0

    for tex in tl.textures:
        ch = tex.channels[channel_index]

        # Check for linear node
        linear = tex.tree.nodes.get(ch.linear)
        if self.colorspace == 'LINEAR' and linear:
            ch.tex_input = 'RGB_LINEAR'

        for mod in ch.modifiers:
            if mod.type == 'RGB_TO_INTENSITY':
                rgb2i = tex.tree.nodes.get(mod.rgb2i)
                if self.colorspace == 'LINEAR':
                    rgb2i.inputs['Linearize'].default_value = 0.0
                else: rgb2i.inputs['Linearize'].default_value = 1.0

def update_channel_alpha(self, context):
    group_tree = self.id_data
    tl = group_tree.tl
    nodes = group_tree.nodes
    links = group_tree.links
    inputs = group_tree.inputs
    outputs = group_tree.outputs

    start_alpha_entry = nodes.get(self.start_alpha_entry)
    end_alpha_entry = nodes.get(self.end_alpha_entry)
    if not start_alpha_entry: return

    start = nodes.get(tl.start)
    end = nodes.get(tl.end)
    end_alpha = nodes.get(self.end_alpha)

    alpha_io_found = False
    for out in start.outputs:
        for link in out.links:
            if link.to_socket == start_alpha_entry.inputs[0]:
                alpha_io_found = True
                break
        if alpha_io_found: break
    
    # Create alpha IO
    if self.alpha and not alpha_io_found:
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

        links.new(start.outputs[alpha_index], start_alpha_entry.inputs[0])
        links.new(end_alpha.outputs[0], end.inputs[alpha_index])

        # Set node default_value
        node = get_active_texture_layers_node()
        node.inputs[alpha_index].default_value = 0.0

        # Shift other IO index
        for ch in tl.channels:
            if ch.io_index >= alpha_index:
                ch.io_index += 1

        # Add socket to texture tree
        for tex in tl.textures:
            tree = tex.tree

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
        reconnect_tl_tex_nodes(group_tree)

        tl.refresh_tree = True

    # Remove alpha IO
    elif not self.alpha and alpha_io_found:

        node = get_active_texture_layers_node()
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

        inputs.remove(inputs[self.io_index+1])
        outputs.remove(outputs[self.io_index+1])

        # Relink inside tree
        solid_alpha = nodes.get(tl.solid_alpha)
        links.new(solid_alpha.outputs[0], start_alpha_entry.inputs[0])

        # Shift other IO index
        for ch in tl.channels:
            if ch.io_index > self.io_index:
                ch.io_index -= 1

        # Remove socket from texture tree
        for tex in tl.textures:
            tree = tex.tree
            tree.inputs.remove(tree.inputs[self.io_index+1])
            tree.outputs.remove(tree.outputs[self.io_index+1])

            # Update texture blend nodes
            for i, ch in enumerate(tex.channels):
                root_ch = tl.channels[i]
                if Layer.update_blend_type_(root_ch, tex, ch):
                    reconnect_tex_nodes(tex, i)
                    rearrange_tex_nodes(tex)

        # Reconnect solid alpha to end alpha
        links.new(start_alpha_entry.outputs[0], end_alpha_entry.inputs[0])

        tl.refresh_tree = True

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

    io_index = IntProperty(default=-1)
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
    start_entry = StringProperty(default='')
    start_alpha_entry = StringProperty(default='')
    start_normal_filter = StringProperty(default='')

    end_entry = StringProperty(default='')
    end_alpha_entry = StringProperty(default='')
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
            if tex.source_tree:
                source = tex.source_tree.nodes.get(tex.source)
            else: source = tex.tree.nodes.get(tex.source)
            img = source.image

            if img and img.name != tex.image_name:
                # Update active texture paint image
                tex.image_name = img.name
                tl.active_texture_index = tl.active_texture_index

def register():
    # TL Props
    bpy.types.ShaderNodeTree.tl = PointerProperty(type=YTextureLayersRoot)
    bpy.types.Material.tl = PointerProperty(type=YMaterialTLProps)

    # Handlers
    bpy.app.handlers.scene_update_pre.append(ytl_hacks_and_scene_updates)

def unregister():

    # Remove handlers
    bpy.app.handlers.scene_update_pre.remove(ytl_hacks_and_scene_updates)

