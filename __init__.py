bl_info = {
    "name": "Ucup Multilayered Texture System",
    "author": "Yusuf Umar",
    "version": (0, 0, 0),
    "blender": (2, 79, 0),
    "location": "Node Editor > Properties > Texture Group",
    "description": "Texture Group Node can be substitute for layer manager within Cycles",
    "wiki_url": "http://twitter.com/ucupumar",
    "category": "Material",
}

import bpy
from bpy.props import *
from .common import *
from mathutils import *

# IMPORTED NODE GROUP NAMES
SRGB_TO_LINEAR_COLOR_GROUP_NAME = '~~SRGB to Linear Color [yPanel]'
LINEAR_TO_SRGB_COLOR_GROUP_NAME = '~~Linear to SRGB Color [yPanel]'
SRGB_TO_LINEAR_VALUE_GROUP_NAME = '~~SRGB to Linear Value [yPanel]'
LINEAR_TO_SRGB_VALUE_GROUP_NAME = '~~Linear to SRGB Value [yPanel]'

texture_type_items = (
         ('ShaderNodeTexImage', 'Image', ''),
         #('ShaderNodeTexEnvironment', 'Environment', ''),
         ('ShaderNodeTexBrick', 'Brick', ''),
         ('ShaderNodeTexChecker', 'Checker', ''),
         ('ShaderNodeTexGradient', 'Gradient', ''),
         ('ShaderNodeTexMagic', 'Magic', ''),
         ('ShaderNodeTexNoise', 'Noise', ''),
         #('ShaderNodeTexPointDensity', 'Point Density', ''),
         #('ShaderNodeTexSky', 'Sky', ''),
         ('ShaderNodeTexVoronoi', 'Voronoi', ''),
         ('ShaderNodeTexWave', 'Wave', ''),
         )

def add_io_from_new_channel(group_tree):
    # New channel should be the last item
    channel = group_tree.tg.channels[-1]

    if channel.type == 'RGB':
        socket_type = 'NodeSocketColor'
    elif channel.type == 'VALUE':
        socket_type = 'NodeSocketFloat'
    elif channel.type == 'VECTOR':
        socket_type = 'NodeSocketVector'

    inp = group_tree.inputs.new(socket_type, channel.name)
    out = group_tree.outputs.new(socket_type, channel.name)

    if channel.type == 'VALUE':
        inp.min_value = 0.0
        inp.max_value = 1.0
    elif channel.type == 'RGB':
        inp.default_value = (1,1,1,1)
    elif channel.type == 'VECTOR':
        inp.min_value = -1.0
        inp.max_value = 1.0
        inp.default_value = (0,0,1)

def create_blend_and_intensity_node(group_tree, texture, channel):

    blend = group_tree.nodes.new('ShaderNodeMixRGB')
    blend.label = 'Blend'
    channel.blend = blend.name

    intensity = group_tree.nodes.new('ShaderNodeMath')
    intensity.operation = 'MULTIPLY'
    intensity.label = 'Intensity'
    intensity.inputs[1].default_value = 1.0
    channel.intensity = intensity.name

    blend_frame = group_tree.nodes.get(texture.blend_frame)
    if not blend_frame:
        blend_frame = group_tree.nodes.new('NodeFrame')
        blend_frame.label = 'Blend'
        texture.blend_frame = blend_frame.name

    blend.parent = blend_frame
    intensity.parent = blend_frame

    return blend, intensity

def link_new_channel(group_tree):
    # TEMPORARY SOLUTION
    # New channel should be the last item
    last_index = len(group_tree.tg.channels)-1
    channel = group_tree.tg.channels[last_index]

    # Get start and end node
    start_node = group_tree.nodes.get(group_tree.tg.start)
    end_node = group_tree.nodes.get(group_tree.tg.end)

    start_linear = None
    start_convert = None

    end_linear = None
    end_convert = None

    # Get start and end frame
    start_frame = group_tree.nodes.get(group_tree.tg.start_frame)
    if not start_frame:
        start_frame = group_tree.nodes.new('NodeFrame')
        start_frame.label = 'Start'
        group_tree.tg.start_frame = start_frame.name

    end_frame = group_tree.nodes.get(group_tree.tg.end_frame)
    if not end_frame:
        end_frame = group_tree.nodes.new('NodeFrame')
        end_frame.label = 'End'
        group_tree.tg.end_frame = end_frame.name

    # Create linarize node and converter node
    if channel.type == 'RGB':
        start_linear = group_tree.nodes.new('ShaderNodeGroup')
        start_linear.label = 'Start Linear'
        start_linear.node_tree = bpy.data.node_groups.get(LINEAR_TO_SRGB_COLOR_GROUP_NAME)
        start_linear.parent = start_frame
        channel.start_linear = start_linear.name

        end_linear = group_tree.nodes.new('ShaderNodeGroup')
        end_linear.label = 'End Linear'
        end_linear.node_tree = bpy.data.node_groups.get(SRGB_TO_LINEAR_COLOR_GROUP_NAME)
        end_linear.parent = end_frame
        channel.end_linear = end_linear.name

    start_entry = group_tree.nodes.new('NodeReroute')
    start_entry.label = 'Start Entry'
    start_entry.parent = start_frame
    channel.start_entry = start_entry.name

    end_entry = group_tree.nodes.new('NodeReroute')
    end_entry.label = 'End Entry'
    end_entry.parent = end_frame
    channel.end_entry = end_entry.name

    # Link nodes
    if start_linear:
        group_tree.links.new(start_node.outputs[last_index], start_linear.inputs[0])
        group_tree.links.new(start_linear.outputs[0], start_entry.inputs[0])
    else:
        group_tree.links.new(start_node.outputs[last_index], start_entry.inputs[0])

    if end_linear:
        group_tree.links.new(end_entry.outputs[0], end_linear.inputs[0])
        group_tree.links.new(end_linear.outputs[0], end_node.inputs[last_index])
    else:
        group_tree.links.new(end_entry.outputs[0], end_node.inputs[last_index])

    # Link between textures
    if len(group_tree.tg.textures) == 0:
        group_tree.links.new(start_entry.outputs[0], end_entry.inputs[0])
    else:
        for i, t in reversed(list(enumerate(group_tree.tg.textures))):
            # Add new channel
            c = t.channels.add()

            # Add new nodes
            blend, intensity = create_blend_and_intensity_node(group_tree, t, c)

            # Link blend & intensity
            group_tree.links.new(intensity.outputs[0], blend.inputs[0])
            source = group_tree.nodes.get(t.source)
            group_tree.links.new(source.outputs[1], intensity.inputs[0])
            linear = group_tree.nodes.get(t.linear)
            group_tree.links.new(linear.outputs[0], blend.inputs[2])

            if i == len(group_tree.tg.textures)-1:
                # Link start node
                group_tree.links.new(start_entry.outputs[0], blend.inputs[1])
            else:
                # Link between textures
                below_blend = group_tree.nodes.get(group_tree.tg.textures[i+1].channels[last_index].blend)
                group_tree.links.new(below_blend.outputs[0], blend.inputs[1])

            # Link end node
            if i == 0:
                group_tree.links.new(blend.outputs[0], end_entry.inputs[0])

def rearrange_nodes(group_tree):

    nodes = group_tree.nodes

    new_loc = Vector((0, 0))

    # Rearrange start nodes
    start_node = nodes.get(group_tree.tg.start)
    if start_node.location != new_loc: start_node.location = new_loc

    dist_y = 355.0

    # Start nodes
    for i, channel in enumerate(group_tree.tg.channels):
        new_loc.y = -dist_y * i

        # Start linear
        new_loc.x += 200.0
        if channel.start_linear != '':
            start_linear = nodes.get(channel.start_linear)
            if start_linear.location != new_loc: start_linear.location = new_loc

        # Start entry
        new_loc.x += 200.0
        start_entry = nodes.get(channel.start_entry)
        if start_entry.location != new_loc: start_entry.location = new_loc

        # Texture nodes
        new_loc.x += 100.0
        ori_y = new_loc.y
        ori_x = new_loc.x
        for t in reversed(group_tree.tg.textures):

            # Blend node
            blend = nodes.get(t.channels[i].blend)
            if blend.location != new_loc: blend.location = new_loc

            new_loc.y -= 175.0

            # Intensity node
            intensity = nodes.get(t.channels[i].intensity)
            if intensity.location != new_loc: intensity.location = new_loc

            #new_loc.x = ori_x + 200.0 * i

            # Source only need to set up once
            if i == 0:

                # Source Linear node
                new_loc.y = -dist_y * len(group_tree.tg.channels) - 65.0
                linear = nodes.get(t.linear)
                if linear.location != new_loc: linear.location = new_loc

                # Source node
                new_loc.y -= 120.0
                source = nodes.get(t.source)
                if source.location != new_loc: source.location = new_loc

            new_loc.y = ori_y
            new_loc.x += 235.0

        # End entry
        #new_loc.x += 50.0
        end_entry = nodes.get(channel.end_entry)
        if end_entry.location != new_loc: end_entry.location = new_loc

        # End linear
        new_loc.x += 50.0
        if channel.end_linear != '':
            end_linear = nodes.get(channel.end_linear)
            if end_linear.location != new_loc: end_linear.location = new_loc

        # Back to left
        if i < len(group_tree.tg.channels)-1:
            new_loc.x = 0.0

    # Back to top
    new_loc.y = 0.0

    # Shift the last x
    new_loc.x += 200.0

    # End node
    end_node = nodes.get(group_tree.tg.end)
    if end_node.location != new_loc: end_node.location = new_loc

def set_input_default_value(group_node, index):
    channel = group_node.node_tree.tg.channels[index]
    
    # Set default value
    if channel.type == 'RGB':
        group_node.inputs[index].default_value = (1,1,1,1)
    if channel.type == 'VALUE':
        group_node.inputs[index].default_value = 0.0
    if channel.type == 'VECTOR':
        group_node.inputs[index].default_value = (0,0,1)

def get_active_node():
    obj = bpy.context.object
    if not obj: return None
    mat = obj.active_material
    if not mat or not mat.node_tree: return None
    node = mat.node_tree.nodes.active
    return node

def get_active_texture_group_node():
    node = get_active_node()
    if not node or node.type != 'GROUP' or not node.node_tree or not node.node_tree.tg.is_tg_node:
        return None
    return node

def create_new_group_tree(mat):

    # Group name is based from the material
    group_name = 'TexGroup ' + mat.name

    # Create new group tree
    group_tree = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')
    group_tree.tg.is_tg_node = True

    # Add new channel
    channel = group_tree.tg.channels.add()
    channel.name = 'Color'

    add_io_from_new_channel(group_tree)

    # Create start and end node
    start_node = group_tree.nodes.new('NodeGroupInput')
    end_node = group_tree.nodes.new('NodeGroupOutput')
    group_tree.tg.start = start_node.name
    group_tree.tg.end = end_node.name

    # Link start and end node then rearrange the nodes
    link_new_channel(group_tree)
    rearrange_nodes(group_tree)

    return group_tree

class NewTextureGroupNode(bpy.types.Operator):
    bl_idname = "node.y_add_new_texture_group_node"
    bl_label = "Add new Texture Group Node"
    bl_description = "Add new texture group node"
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

        # Create new group node
        node = tree.nodes.new(type='ShaderNodeGroup')
        node.node_tree = group_tree

        # Set default input value
        set_input_default_value(node, 0)

        # Set the location of new node
        node.select = True
        tree.nodes.active = node
        node.location = space.cursor_location

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

class NewTextureGroupChannel(bpy.types.Operator):
    bl_idname = "node.y_add_new_texture_group_channel"
    bl_label = "Add new Texture Group Channel"
    bl_description = "Add new texture group channel"
    bl_options = {'REGISTER', 'UNDO'}

    name = StringProperty(
            name='Channel Name', 
            description = 'Name of the channel',
            default='Albedo')

    type = EnumProperty(
            name = 'Channel Type',
            items = (('VALUE', 'Value', ''),
                     ('RGB', 'RGB', ''),
                     ('VECTOR', 'Vector', '')),
            default = 'RGB')

    @classmethod
    def poll(cls, context):
        return get_active_texture_group_node()

    def invoke(self, context, event):
        group_node = get_active_texture_group_node()
        channels = group_node.node_tree.tg.channels

        if self.type == 'RGB':
            self.name = 'Color'
        elif self.type == 'VALUE':
            self.name = 'Value'
        elif self.type == 'VECTOR':
            self.name = 'Normal'

        # Check if name already available on the list
        name_found = [c for c in channels if c.name == self.name]
        if name_found:
            i = 1
            while True:
                new_name = self.name + ' ' + str(i)
                name_found = [c for c in channels if c.name == new_name]
                if not name_found:
                    self.name = new_name
                    break
                i += 1

        return context.window_manager.invoke_props_dialog(self)

    def check(self, context):
        return True

    def draw(self, context):
        self.layout.prop(self, 'name', text='Name')

    def execute(self, context):
        #node = context.active_node
        node = get_active_texture_group_node()
        group_tree = node.node_tree
        channels = group_tree.tg.channels

        # Check if channel with same name is already available
        same_channel = [c for c in channels if c.name == self.name]
        if same_channel:
            self.report({'ERROR'}, "Channel named '" + self.name +"' is already available!")
            return {'CANCELLED'}

        # Add new channel
        channel = channels.add()
        channel.name = self.name
        channel.type = self.type

        # Add input and output to the tree
        add_io_from_new_channel(group_tree)

        # Get last index
        last_index = len(channels)-1

        # Link new channel and the rearrange the nodes
        link_new_channel(group_tree)
        rearrange_nodes(group_tree)

        # Set input default value
        set_input_default_value(node, last_index)

        # Change active channel
        group_tree.tg.active_channel_index = last_index

        return {'FINISHED'}

class MoveTextureGroupChannel(bpy.types.Operator):
    bl_idname = "node.y_move_texture_group_channel"
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
        group_node = get_active_texture_group_node()
        return group_node and len(group_node.node_tree.tg.channels) > 0

    def execute(self, context):
        group_node = get_active_texture_group_node()
        group_tree = group_node.node_tree

        # Get active channel
        index = group_tree.tg.active_channel_index
        channel = group_tree.tg.channels[index]
        num_chs = len(group_tree.tg.channels)

        # Get new index
        if self.direction == 'UP' and index > 0:
            new_index = index-1
        elif self.direction == 'DOWN' and index < num_chs-1:
            new_index = index+1
        else:
            return {'CANCELLED'}

        # Move channel
        group_tree.tg.channels.move(index, new_index)

        # Move channel inside tree
        group_tree.inputs.move(index,new_index)
        group_tree.outputs.move(index,new_index)
        rearrange_nodes(group_tree)

        # Set active index
        group_tree.tg.active_channel_index = new_index

        return {'FINISHED'}

class RemoveTextureGroupChannel(bpy.types.Operator):
    bl_idname = "node.y_remove_texture_group_channel"
    bl_label = "Remove Texture Group Channel"
    bl_description = "Remove texture group channel"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        group_node = get_active_texture_group_node()
        return group_node and len(group_node.node_tree.tg.channels) > 0

    def execute(self, context):
        group_node = get_active_texture_group_node()
        group_tree = group_node.node_tree

        # Get active channel
        channel_idx = group_tree.tg.active_channel_index
        channel = group_tree.tg.channels[channel_idx]
        channel_name = channel.name

        # Remove channel
        group_tree.tg.channels.remove(channel_idx)

        # Remove channel from tree
        group_tree.inputs.remove(group_tree.inputs[channel_idx])
        group_tree.outputs.remove(group_tree.outputs[channel_idx])
        rearrange_nodes(group_tree)

        # Set new active index
        if (group_tree.tg.active_channel_index == len(group_tree.tg.channels) and
            group_tree.tg.active_channel_index > 0
            ): group_tree.tg.active_channel_index -= 1

        return {'FINISHED'}

class NewTextureLayer(bpy.types.Operator):
    bl_idname = "node.y_new_texture_layer"
    bl_label = "New Texture Layer"
    bl_description = "New Texture Layer"
    bl_options = {'REGISTER', 'UNDO'}

    type = EnumProperty(
            name = 'Texture Type',
            items = texture_type_items,
            default = 'ShaderNodeTexImage')

    @classmethod
    def poll(cls, context):
        return get_active_texture_group_node()

    def execute(self, context):
        node = get_active_texture_group_node()
        group_tree = node.node_tree
        tg = group_tree.tg

        # Add texture to group
        tex = tg.textures.add()
        tex.type = self.type

        # For now, new texture always placed in the bottom
        index = len(tg.textures)-1

        # Add nodes to tree
        source = group_tree.nodes.new(self.type)
        source.label = 'Source'
        tex.source = source.name

        linear = group_tree.nodes.new('ShaderNodeGroup')
        linear.label = 'Source Linear'
        linear.node_tree = bpy.data.node_groups.get(LINEAR_TO_SRGB_COLOR_GROUP_NAME)
        tex.linear = linear.name

        source_frame = group_tree.nodes.new('NodeFrame')
        source_frame.label = 'Source'
        tex.source_frame = source_frame.name

        source.parent = source_frame
        linear.parent = source_frame

        # Link nodes
        group_tree.links.new(source.outputs[0], linear.inputs[0])

        # Add channels
        for i, ch in enumerate(tg.channels):
            c = tex.channels.add()

            # Add nodes
            blend, intensity = create_blend_and_intensity_node(group_tree, tex, c)

            # Link nodes
            group_tree.links.new(intensity.outputs[0], blend.inputs[0])
            group_tree.links.new(linear.outputs[0], blend.inputs[2])
            group_tree.links.new(source.outputs[1], intensity.inputs[0])

            # Link neighbor nodes
            if index < len(tg.textures)-1:
                below_blend = group_tree.nodes.get(tg.textures[index+1].channels[i].blend)
            else: below_blend = group_tree.nodes.get(tg.channels[i].start_entry)
            group_tree.links.new(below_blend.outputs[0], blend.inputs[1])

            if index > 0:
                upper_blend = group_tree.nodes.get(tg.textures[index-1].channels[i].blend)
                group_tree.links.new(blend.outputs[0], upper_blend.inputs[1])
            else: 
                end_entry = group_tree.nodes.get(tg.channels[i].end_entry)
                group_tree.links.new(blend.outputs[0], end_entry.inputs[0])

        rearrange_nodes(group_tree)

        return {'FINISHED'}

class NODE_PT_texture_groups(bpy.types.Panel):
    #bl_space_type = 'VIEW_3D'
    bl_space_type = 'NODE_EDITOR'
    bl_label = "Texture Groups"
    bl_region_type = 'UI'
    #bl_region_type = 'TOOLS'
    #bl_category = "Texture Groups"

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        layout = self.layout
        node = get_active_texture_group_node()

        if not node:
            layout.label("No texture group node selected!")
            return

        group_tree = node.node_tree
        layout.label('Channel Base Value:', icon='COLOR')
        row = layout.row()
        row.template_list("NODE_UL_y_texture_groups", "", group_tree.tg,
                "channels", group_tree.tg, "active_channel_index", rows=4, maxrows=5)  
        col = row.column(align=True)
        col.operator_menu_enum("node.y_add_new_texture_group_channel", 'type', icon='ZOOMIN', text='')
        col.operator("node.y_remove_texture_group_channel", icon='ZOOMOUT', text='')
        col.operator("node.y_move_texture_group_channel", text='', icon='TRIA_UP').direction = 'UP'
        col.operator("node.y_move_texture_group_channel", text='', icon='TRIA_DOWN').direction = 'DOWN'

        layout.label('Textures:', icon='TEXTURE')
        row = layout.row()
        row.template_list("NODE_UL_y_texture_layers", "", group_tree.tg,
                "textures", group_tree.tg, "active_texture_index", rows=4, maxrows=5)  

        col = row.column(align=True)
        col.operator_menu_enum("node.y_new_texture_layer", 'type', icon='ZOOMIN', text='')
        #col.operator("node.y_remove_texture_group_channel", icon='ZOOMOUT', text='')
        #col.operator("node.y_move_texture_group_channel", text='', icon='TRIA_UP').direction = 'UP'
        #col.operator("node.y_move_texture_group_channel", text='', icon='TRIA_DOWN').direction = 'DOWN'

class NODE_UL_y_texture_groups(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        group_node = get_active_texture_group_node()
        if not group_node: return
        inputs = group_node.inputs

        row = layout.row()
        row.prop(item, 'name', text='', emboss=False)
        if item.type == 'VALUE':
            row.prop(inputs[index], 'default_value', text='') #, emboss=False)
        elif item.type == 'RGB':
            row.prop(inputs[index], 'default_value', text='', icon='COLOR')
        elif item.type == 'VECTOR':
            row.prop(inputs[index], 'default_value', text='', expand=False)

class NODE_UL_y_texture_layers(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row()
        row.label(item.type)

def menu_func(self, context):
    l = self.layout
    l.operator_context = 'INVOKE_REGION_WIN'
    l.separator()
    l.operator('node.y_add_new_texture_group_node', text='Texture Group', icon='NODE')

def update_channel_name(self, context):
    group_tree = self.id_data
    index = [i for i, ch in enumerate(group_tree.tg.channels) if ch == self][0]

    if index < len(group_tree.inputs):
        group_tree.inputs[index].name = self.name
        group_tree.outputs[index].name = self.name

class LayerChannel(bpy.types.PropertyGroup):
    enable = BoolProperty(default=True)

    #modifiers = CollectionProperty(type=TextureModifier)

    # Node names
    intensity = StringProperty(default='')
    blend = StringProperty(default='')

class TextureLayer(bpy.types.PropertyGroup):
    enable = BoolProperty(default=True)

    channels = CollectionProperty(type=LayerChannel)

    type = EnumProperty(
            name = 'Texture Type',
            items = texture_type_items,
            default = 'ShaderNodeTexImage')

    # Node names
    source = StringProperty(default='')
    linear = StringProperty(default='')
    #uv = StringProperty(default='')

    source_frame = StringProperty(default='')
    blend_frame = StringProperty(default='')

class GroupChannel(bpy.types.PropertyGroup):
    name = StringProperty(
            name='Channel Name', 
            description = 'Name of the channel',
            default='Albedo',
            update=update_channel_name)

    type = EnumProperty(
            name = 'Channel Type',
            items = (('VALUE', 'Value', ''),
                     ('RGB', 'RGB', ''),
                     ('VECTOR', 'Vector', '')),
            default = 'RGB')

    is_alpha_channel = BoolProperty(default=False)

    # Node names
    start_linear = StringProperty(default='')
    start_convert = StringProperty(default='')
    start_entry = StringProperty(default='')

    end_entry = StringProperty(default='')
    end_linear = StringProperty(default='')
    end_convert = StringProperty(default='')

    #end_modifiers = PointerProperty(type=TextureGroupModifiers)

class TextureGroup(bpy.types.PropertyGroup):
    is_tg_node = BoolProperty(default=False)

    # Channels
    channels = CollectionProperty(type=GroupChannel)
    active_channel_index = IntProperty(default=0)

    # Textures
    textures = CollectionProperty(type=TextureLayer)
    active_texture_index = IntProperty(default=0)

    # Node names
    start = StringProperty(default='')
    start_frame = StringProperty(default='')

    end = StringProperty(default='')
    end_frame = StringProperty(default='')

@persistent
def load_libraries(scene):
    # Node groups necessary are in nodegroups_lib.blend
    filepath = get_addon_filepath() + "lib.blend"

    with bpy.data.libraries.load(filepath) as (data_from, data_to):

        # Load node groups
        exist_groups = [ng.name for ng in bpy.data.node_groups]
        for ng in data_from.node_groups:
            if ng not in exist_groups:
                data_to.node_groups.append(ng)

def register():
    bpy.utils.register_module(__name__)

    bpy.types.ShaderNodeTree.tg = PointerProperty(type=TextureGroup)

    bpy.types.NODE_MT_add.append(menu_func)

def unregister():
    bpy.types.NODE_MT_add.remove(menu_func)
    bpy.utils.unregister_module(__name__)

if __name__ == "__main__":
    register()
