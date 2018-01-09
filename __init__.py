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

modifier_type_items = (
        ('INVERT', 'Invert', ''),
        ('RGB_TO_INTENSITY', 'RGB to Intensity', ''),
        ('COLOR_RAMP', 'Color Ramp', ''),
        ('RGB_CURVE', 'RGB Curve', ''),
        ('HUE_SATURATION', 'Hue Saturation', ''),
        #('GRAYSCALE_TO_NORMAL', 'Grayscale To Normal', ''),
        #('MASK', 'Mask', ''),
        )

# Check if name already available on the list
def get_unique_name(name, items):
    unique_name = name
    name_found = [item for item in items if item.name == name]
    if name_found:
        i = 1
        while True:
            new_name = name + ' ' + str(i)
            name_found = [item for item in items if item.name == new_name]
            if not name_found:
                unique_name = new_name
                break
            i += 1

    return unique_name

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

    # Blend nodes
    blend = group_tree.nodes.new('ShaderNodeMixRGB')
    blend.label = 'Blend'
    channel.blend = blend.name

    # Blend frame
    blend_frame = group_tree.nodes.get(texture.blend_frame)
    if not blend_frame:
        blend_frame = group_tree.nodes.new('NodeFrame')
        blend_frame.label = 'Blend'
        texture.blend_frame = blend_frame.name

    blend.parent = blend_frame
    #intensity.parent = blend_frame

    # Modifier pipeline nodes
    intensity = group_tree.nodes.new('ShaderNodeMixRGB')
    #intensity.blend_type = 'MULTIPLY'
    intensity.label = 'Intensity'
    intensity.inputs[0].default_value = 1.0
    intensity.inputs[1].default_value = (0,0,0,1)
    intensity.inputs[2].default_value = (1,1,1,1)
    channel.intensity = intensity.name

    start_rgb = group_tree.nodes.new('NodeReroute')
    start_rgb.label = 'Start RGB'
    channel.start_rgb = start_rgb.name

    start_alpha = group_tree.nodes.new('NodeReroute')
    start_alpha.label = 'Start Alpha'
    channel.start_alpha = start_alpha.name

    end_rgb = group_tree.nodes.new('NodeReroute')
    end_rgb.label = 'End RGB'
    channel.end_rgb = end_rgb.name

    end_alpha = group_tree.nodes.new('NodeReroute')
    end_alpha.label = 'End Alpha'
    channel.end_alpha = end_alpha.name

    # Get source RGB and alpha
    linear = group_tree.nodes.get(texture.linear)
    solid_alpha = group_tree.nodes.get(texture.solid_alpha)
    source = group_tree.nodes.get(texture.source)

    # Modifier frame
    modifier_frame = group_tree.nodes.get(channel.modifier_frame)
    if not modifier_frame:
        modifier_frame = group_tree.nodes.new('NodeFrame')
        modifier_frame.label = 'Modifiers'
        channel.modifier_frame = modifier_frame.name

    #intensity.parent = modifier_frame
    start_rgb.parent = modifier_frame
    start_alpha.parent = modifier_frame
    end_rgb.parent = modifier_frame
    end_alpha.parent = modifier_frame

    # Link nodes
    group_tree.links.new(linear.outputs[0], start_rgb.inputs[0])
    if solid_alpha:
        group_tree.links.new(solid_alpha.outputs[0], start_alpha.inputs[0])
    else: group_tree.links.new(source.outputs[1], start_alpha.inputs[0])

    group_tree.links.new(start_rgb.outputs[0], end_rgb.inputs[0])
    group_tree.links.new(start_alpha.outputs[0], end_alpha.inputs[0])
    #group_tree.links.new(start_alpha.outputs[0], intensity.inputs[2])

    group_tree.links.new(end_rgb.outputs[0], blend.inputs[2])
    group_tree.links.new(end_alpha.outputs[0], intensity.inputs[2])
    #group_tree.links.new(intensity.outputs[0], end_alpha.inputs[0])

    group_tree.links.new(intensity.outputs[0], blend.inputs[0])

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

    end_entry_frame = group_tree.nodes.get(group_tree.tg.end_entry_frame)
    if not end_entry_frame:
        end_entry_frame = group_tree.nodes.new('NodeFrame')
        end_entry_frame.label = 'End'
        group_tree.tg.end_entry_frame = end_entry_frame.name

    #modifier_frame = group_tree.nodes.get(channel.modifier_frame)
    modifier_frame = group_tree.nodes.new('NodeFrame')
    modifier_frame.label = 'Modifier'
    channel.modifier_frame = modifier_frame.name

    end_linear_frame = group_tree.nodes.get(group_tree.tg.end_linear_frame)
    if not end_linear_frame:
        end_linear_frame = group_tree.nodes.new('NodeFrame')
        end_linear_frame.label = 'End Linear'
        group_tree.tg.end_linear_frame = end_linear_frame.name

    # Create linarize node and converter node
    if channel.type in {'RGB', 'VALUE'}:
        start_linear = group_tree.nodes.new('ShaderNodeGroup')
        start_linear.label = 'Start Linear'
        if channel.type == 'RGB':
            start_linear.node_tree = bpy.data.node_groups.get(LINEAR_TO_SRGB_COLOR_GROUP_NAME)
        else: start_linear.node_tree = bpy.data.node_groups.get(LINEAR_TO_SRGB_VALUE_GROUP_NAME)
        start_linear.parent = start_frame
        channel.start_linear = start_linear.name

        end_linear = group_tree.nodes.new('ShaderNodeGroup')
        end_linear.label = 'End Linear'
        if channel.type == 'RGB':
            end_linear.node_tree = bpy.data.node_groups.get(SRGB_TO_LINEAR_COLOR_GROUP_NAME)
        else: end_linear.node_tree = bpy.data.node_groups.get(SRGB_TO_LINEAR_VALUE_GROUP_NAME)
        end_linear.parent = end_linear_frame
        channel.end_linear = end_linear.name

    start_entry = group_tree.nodes.new('NodeReroute')
    start_entry.label = 'Start Entry'
    start_entry.parent = start_frame
    channel.start_entry = start_entry.name

    end_entry = group_tree.nodes.new('NodeReroute')
    end_entry.label = 'End Entry'
    end_entry.parent = end_entry_frame
    channel.end_entry = end_entry.name

    # Modifier pipeline
    start_rgb = group_tree.nodes.new('NodeReroute')
    start_rgb.label = 'Start RGB'
    start_rgb.parent = modifier_frame
    channel.start_rgb = start_rgb.name

    start_alpha = group_tree.nodes.new('NodeReroute')
    start_alpha.label = 'Start Alpha'
    start_alpha.parent = modifier_frame
    channel.start_alpha = start_alpha.name

    end_rgb = group_tree.nodes.new('NodeReroute')
    end_rgb.label = 'End RGB'
    end_rgb.parent = modifier_frame
    channel.end_rgb = end_rgb.name

    end_alpha = group_tree.nodes.new('NodeReroute')
    end_alpha.label = 'End Alpha'
    end_alpha.parent = modifier_frame
    channel.end_alpha = end_alpha.name

    # Link nodes
    if start_linear:
        group_tree.links.new(start_node.outputs[last_index], start_linear.inputs[0])
        group_tree.links.new(start_linear.outputs[0], start_entry.inputs[0])
    else:
        group_tree.links.new(start_node.outputs[last_index], start_entry.inputs[0])

    group_tree.links.new(end_entry.outputs[0], start_rgb.inputs[0])
    group_tree.links.new(start_rgb.outputs[0], end_rgb.inputs[0])

    if end_linear:
        group_tree.links.new(end_rgb.outputs[0], end_linear.inputs[0])
        group_tree.links.new(end_linear.outputs[0], end_node.inputs[last_index])
    else:
        group_tree.links.new(end_rgb.outputs[0], end_node.inputs[last_index])

    # Link between textures
    if len(group_tree.tg.textures) == 0:
        group_tree.links.new(start_entry.outputs[0], end_entry.inputs[0])
    else:
        for i, t in reversed(list(enumerate(group_tree.tg.textures))):
            # Add new channel
            c = t.channels.add()

            # New channel is disabled by default
            #c.enable = False

            # Add new nodes
            blend, intensity = create_blend_and_intensity_node(group_tree, t, c)

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

def delete_modifier_nodes(nodes, mod):
    # Delete the nodes
    nodes.remove(nodes.get(mod.start_rgb))
    nodes.remove(nodes.get(mod.start_alpha))
    nodes.remove(nodes.get(mod.end_rgb))
    nodes.remove(nodes.get(mod.end_alpha))
    nodes.remove(nodes.get(mod.frame))

    if mod.type == 'RGB_TO_INTENSITY':
        nodes.remove(nodes.get(mod.rgb2i_color))
        nodes.remove(nodes.get(mod.rgb2i_linear))
        nodes.remove(nodes.get(mod.rgb2i_mix_rgb))
        nodes.remove(nodes.get(mod.rgb2i_mix_alpha))

    elif mod.type == 'INVERT':
        nodes.remove(nodes.get(mod.invert))

    elif mod.type == 'COLOR_RAMP':
        nodes.remove(nodes.get(mod.color_ramp))

    elif mod.type == 'RGB_CURVE':
        nodes.remove(nodes.get(mod.rgb_curve))

    elif mod.type == 'HUE_SATURATION':
        nodes.remove(nodes.get(mod.huesat))

def arrange_modifier_nodes(nodes, parent, new_loc, original_x):

    # Modifier loops
    for m in parent.modifiers:
        m_end_rgb = nodes.get(m.end_rgb)
        m_end_alpha = nodes.get(m.end_alpha)

        new_loc.x += 35.0
        if m_end_rgb.location != new_loc: m_end_rgb.location = new_loc
        new_loc.x += 65.0
        if m_end_alpha.location != new_loc: m_end_alpha.location = new_loc

        new_loc.x = original_x
        new_loc.y -= 20.0

        if m.type == 'INVERT':
            invert = nodes.get(m.invert)
            if invert.location != new_loc: invert.location = new_loc

            new_loc.y -= 120.0

        elif m.type == 'RGB_TO_INTENSITY':
            rgb2i_mix_alpha = nodes.get(m.rgb2i_mix_alpha)
            if rgb2i_mix_alpha.location != new_loc: rgb2i_mix_alpha.location = new_loc

            new_loc.y -= 180.0

            rgb2i_mix_rgb = nodes.get(m.rgb2i_mix_rgb)
            if rgb2i_mix_rgb.location != new_loc: rgb2i_mix_rgb.location = new_loc

            new_loc.y -= 180.0

            rgb2i_linear = nodes.get(m.rgb2i_linear)
            if rgb2i_linear.location != new_loc: rgb2i_linear.location = new_loc

            new_loc.y -= 120.0

            rgb2i_color = nodes.get(m.rgb2i_color)
            if rgb2i_color.location != new_loc: rgb2i_color.location = new_loc

            new_loc.y -= 200.0

        elif m.type == 'COLOR_RAMP':

            color_ramp = nodes.get(m.color_ramp)
            if color_ramp.location != new_loc: color_ramp.location = new_loc

            new_loc.y -= 240.0

        elif m.type == 'RGB_CURVE':

            rgb_curve = nodes.get(m.rgb_curve)
            if rgb_curve.location != new_loc: rgb_curve.location = new_loc

            new_loc.y -= 320.0

        elif m.type == 'HUE_SATURATION':

            huesat = nodes.get(m.huesat)
            if huesat.location != new_loc: huesat.location = new_loc

            new_loc.y -= 185.0

        m_start_rgb = nodes.get(m.start_rgb)
        m_start_alpha = nodes.get(m.start_alpha)

        new_loc.x += 35.0
        if m_start_rgb.location != new_loc: m_start_rgb.location = new_loc
        new_loc.x += 65.0
        if m_start_alpha.location != new_loc: m_start_alpha.location = new_loc

        new_loc.x = original_x
        new_loc.y -= 85.0

    return new_loc

def rearrange_nodes(group_tree):

    nodes = group_tree.nodes

    new_loc = Vector((0, 0))

    # Rearrange start nodes
    start_node = nodes.get(group_tree.tg.start)
    if start_node.location != new_loc: start_node.location = new_loc

    #dist_y = 350.0
    dist_y = 175.0
    dist_x = 370.0

    # Start nodes
    for i, channel in enumerate(group_tree.tg.channels):
        new_loc.y = -dist_y * i

        # Start linear
        new_loc.x += 200.0
        if channel.start_linear != '':
            start_linear = nodes.get(channel.start_linear)
            if start_linear.location != new_loc: start_linear.location = new_loc

        # Start entry
        ori_y = new_loc.y
        new_loc.x += 200.0
        new_loc.y -= 35.0
        start_entry = nodes.get(channel.start_entry)
        if start_entry.location != new_loc: start_entry.location = new_loc

        new_loc.y = ori_y

        # Back to left
        if i < len(group_tree.tg.channels)-1:
            new_loc.x = 0.0

    new_loc.x += 100.0
    ori_x = new_loc.x

    # Texture nodes
    for i, t in enumerate(reversed(group_tree.tg.textures)):

        new_loc.y = 0.0
        new_loc.x = ori_x + dist_x * i * len(t.channels)
        ori_xx = new_loc.x

        # Blend nodes
        for c in t.channels:
            blend = nodes.get(c.blend)
            if blend.location != new_loc: blend.location = new_loc

            new_loc.y -= dist_y
            new_loc.x += dist_x

        new_loc.x = ori_xx
        new_loc.y -= 35.0

        ori_y = new_loc.y

        # List of y locations
        ys = []

        for c in t.channels:

            new_loc.y = ori_y
            ori_xxx = new_loc.x

            # Intensity node
            intensity = nodes.get(c.intensity)
            if intensity.location != new_loc: intensity.location = new_loc

            new_loc.y -= 220.0

            # Channel modifier pipeline
            end_rgb = nodes.get(c.end_rgb)
            end_alpha = nodes.get(c.end_alpha)
            start_rgb = nodes.get(c.start_rgb)
            start_alpha = nodes.get(c.start_alpha)

            # End
            new_loc.x += 35.0
            if end_rgb.location != new_loc: end_rgb.location = new_loc
            new_loc.x += 65.0
            if end_alpha.location != new_loc: end_alpha.location = new_loc

            new_loc.x = ori_xxx
            new_loc.y -= 50.0

            new_loc = arrange_modifier_nodes(nodes, c, new_loc, ori_xxx)

            #new_loc.x = ori_xxx
            #new_loc.y -= 50.0

            # Start
            new_loc.x += 35.0
            if start_rgb.location != new_loc: start_rgb.location = new_loc
            new_loc.x += 65.0
            if start_alpha.location != new_loc: start_alpha.location = new_loc

            new_loc.x = ori_xxx
            new_loc.x += dist_x

            ys.append(new_loc.y)

            #new_loc.y -= dist_y

        # Sort y locations and use the first one
        if ys:
            ys.sort()
            new_loc.y = ys[0]

        new_loc.x = ori_xx
        new_loc.y -= 90.0

        # Source Linear node
        linear = nodes.get(t.linear)
        if linear.location != new_loc: linear.location = new_loc

        solid_alpha = nodes.get(t.solid_alpha)
        if solid_alpha:
            new_loc.y -= 120.0
            if solid_alpha.location != new_loc: solid_alpha.location = new_loc
            new_loc.y -= 95.0
        else:
            new_loc.y -= 120.0

        # Source node
        source = nodes.get(t.source)
        if source.location != new_loc: source.location = new_loc

    #new_loc.x += 240.0
    new_loc.x = ori_x + dist_x * len(group_tree.tg.channels) * len(group_tree.tg.textures) + 25.0

    # End entry nodes
    for i, channel in enumerate(group_tree.tg.channels):
        new_loc.y = -dist_y * i

        #ori_y = new_loc.y
        new_loc.y -= 35.0

        # End entry
        end_entry = nodes.get(channel.end_entry)
        if end_entry.location != new_loc: end_entry.location = new_loc

    new_loc.y = 0.0
    new_loc.x += 120.0
    ori_xxx = new_loc.x

    # End modifiers
    for i, channel in enumerate(group_tree.tg.channels):
        new_loc.y = -dist_y * i
        new_loc.x = ori_xxx + dist_x * i

        new_loc.x += 35.0
        new_loc.y -= 35.0
        end_rgb = nodes.get(channel.end_rgb)
        if end_rgb.location != new_loc: end_rgb.location = new_loc

        new_loc.x += 65.0
        end_alpha = nodes.get(channel.end_alpha)
        if end_alpha.location != new_loc: end_alpha.location = new_loc

        new_loc.x = ori_xxx + dist_x * i
        new_loc.y -= 50.0

        new_loc = arrange_modifier_nodes(nodes, channel, new_loc, ori_xxx + dist_x * i)

        new_loc.x += 35.0
        start_rgb = nodes.get(channel.start_rgb)
        if start_rgb.location != new_loc: start_rgb.location = new_loc

        new_loc.x += 65.0
        start_alpha = nodes.get(channel.start_alpha)
        if start_alpha.location != new_loc: start_alpha.location = new_loc

    new_loc.y = 0.0
    new_loc.x += 250.0
        
    # End linear
    for i, channel in enumerate(group_tree.tg.channels):
        new_loc.y = -dist_y * i
        if channel.end_linear != '':
            end_linear = nodes.get(channel.end_linear)
            if end_linear.location != new_loc: end_linear.location = new_loc

    new_loc.x += 200.0
    new_loc.y = 0.0

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
    group_tree.tg.temp_channels.add() # Also add temp channel

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
        self.name = get_unique_name(self.name, channels)

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
        group_tree.tg.temp_channels.add()

        # Add input and output to the tree
        add_io_from_new_channel(group_tree)

        # Get last index
        last_index = len(channels)-1

        # Link new channel
        link_new_channel(group_tree)

        # New channel is disabled in texture by default
        for tex in group_tree.tg.textures:
            tex.channels[last_index].enable = False

        # Rearrange nodes
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
        group_tree.tg.temp_channels.move(index, new_index) # Temp channels

        # Move channel inside textures
        for tex in group_tree.tg.textures:
            tex.channels.move(index, new_index)

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
        tg = group_tree.tg
        nodes = group_tree.nodes

        # Get active channel
        channel_idx = tg.active_channel_index
        channel = tg.channels[channel_idx]
        channel_name = channel.name

        # Remove channel nodes from textures
        for t in tg.textures:
            ch = t.channels[channel_idx]

            nodes.remove(nodes.get(ch.blend))
            nodes.remove(nodes.get(ch.start_rgb))
            nodes.remove(nodes.get(ch.start_alpha))
            nodes.remove(nodes.get(ch.end_rgb))
            nodes.remove(nodes.get(ch.end_alpha))
            nodes.remove(nodes.get(ch.modifier_frame))
            nodes.remove(nodes.get(ch.intensity))

            # Remove modifiers
            for mod in ch.modifiers:
                delete_modifier_nodes(nodes, mod)

            t.channels.remove(channel_idx)

        # Remove start and end nodes
        nodes.remove(nodes.get(channel.start_entry))
        nodes.remove(nodes.get(channel.end_entry))
        try: nodes.remove(nodes.get(channel.start_linear)) 
        except: pass
        try: nodes.remove(nodes.get(channel.end_linear)) 
        except: pass

        # Remove channel modifiers
        nodes.remove(nodes.get(channel.start_rgb))
        nodes.remove(nodes.get(channel.start_alpha))
        nodes.remove(nodes.get(channel.end_rgb))
        nodes.remove(nodes.get(channel.end_alpha))
        nodes.remove(nodes.get(channel.modifier_frame))

        for mod in channel.modifiers:
            delete_modifier_nodes(nodes, mod)

        # Remove some frames if it's the last channel
        if len(tg.channels) == 1:
            nodes.remove(nodes.get(tg.start_frame))
            nodes.remove(nodes.get(tg.end_entry_frame))
            nodes.remove(nodes.get(tg.end_linear_frame))
            tg.start_frame = ''
            tg.end_entry_frame = ''
            tg.end_linear_frame = ''
            for t in tg.textures:
                nodes.remove(nodes.get(t.blend_frame))
                t.blend_frame = ''

        # Remove channel
        tg.channels.remove(channel_idx)
        tg.temp_channels.remove(channel_idx)

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

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        node = get_active_texture_group_node()
        tg = node.node_tree.tg

        if len(tg.channels) == 0:
            self.layout.label('No channel found! Still want to create a texture?', icon='ERROR')

        for i, ch in enumerate(tg.channels):
            row = self.layout.row(align=True)
            row.label(ch.name + ':')
            row.prop(tg.temp_channels[i], 'enable', text='')
            row.prop(tg.temp_channels[i], 'blend_type', text='')

    def execute(self, context):
        node = get_active_texture_group_node()
        group_tree = node.node_tree
        tg = group_tree.tg

        # Add texture to group
        tex = tg.textures.add()
        tex.type = self.type

        name = self.type.replace('ShaderNodeTex', '')
        tex.name = get_unique_name(name, tg.textures)

        # Move new texture to current index
        last_index = len(tg.textures)-1
        index = tg.active_texture_index
        #for i in range(
        tg.textures.move(last_index, index)
        tex = tg.textures[index] # Repoint to new index

        # Add nodes to tree
        source = group_tree.nodes.new(self.type)
        source.label = 'Source'
        tex.source = source.name

        linear = group_tree.nodes.new('ShaderNodeGroup')
        linear.label = 'Source Linear'
        linear.node_tree = bpy.data.node_groups.get(LINEAR_TO_SRGB_COLOR_GROUP_NAME)
        tex.linear = linear.name

        # Image texture and checker has SRGB color space by default
        if self.type in {'ShaderNodeTexImage', 'ShaderNodeTexChecker'}:
            tex.color_space = 'SRGB'
        else:
            # Non image texture has linear color space by default
            tex.color_space = 'LINEAR'
            linear.mute = True

        source_frame = group_tree.nodes.new('NodeFrame')
        source_frame.label = 'Source'
        tex.source_frame = source_frame.name

        source.parent = source_frame
        linear.parent = source_frame

        # Solid alpha for non image texture
        if self.type != 'ShaderNodeTexImage':
            solid_alpha = group_tree.nodes.new('ShaderNodeValue')
            solid_alpha.label = 'Solid Alpha'
            solid_alpha.outputs[0].default_value = 1.0
            tex.solid_alpha = solid_alpha.name

            solid_alpha.parent = source_frame

        # Link nodes
        group_tree.links.new(source.outputs[0], linear.inputs[0])

        # Add channels
        for i, ch in enumerate(tg.channels):
            c = tex.channels.add()

            # Add nodes
            blend, intensity = create_blend_and_intensity_node(group_tree, tex, c)

            # Set blend type
            blend.blend_type = tg.temp_channels[i].blend_type

            # Set enable
            c.enable = tg.temp_channels[i].enable
            blend.mute = not c.enable

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

        # Rearrange nodes
        rearrange_nodes(group_tree)

        return {'FINISHED'}

class MoveTextureLayer(bpy.types.Operator):
    bl_idname = "node.y_move_texture_layer"
    bl_label = "Move Texture Layer"
    bl_description = "Move texture layer"
    bl_options = {'REGISTER', 'UNDO'}

    direction = EnumProperty(
            name = 'Direction',
            items = (('UP', 'Up', ''),
                     ('DOWN', 'Down', '')),
            default = 'UP')

    @classmethod
    def poll(cls, context):
        group_node = get_active_texture_group_node()
        return group_node and len(group_node.node_tree.tg.textures) > 0

    def execute(self, context):
        node = get_active_texture_group_node()
        group_tree = node.node_tree
        nodes = group_tree.nodes
        tg = group_tree.tg

        num_tex = len(tg.textures)
        tex_idx = tg.active_texture_index
        tex = tg.textures[tex_idx]
        
        # Move image slot
        if self.direction == 'UP' and tex_idx > 0:
            swap_idx = tex_idx-1
        elif self.direction == 'DOWN' and tex_idx < num_tex-1:
            swap_idx = tex_idx+1
        else:
            return {'CANCELLED'}

        swap_tex = tg.textures[swap_idx]

        for i, ch in enumerate(tex.channels):
            blend = nodes.get(ch.blend)
            swap_blend = nodes.get(swap_tex.channels[i].blend)

            inp_blend = blend.inputs[1].links[0].from_socket
            out_blend = blend.outputs[0].links[0].to_socket

            swap_in_blend = swap_blend.inputs[1].links[0].from_socket
            swap_out_blend = swap_blend.outputs[0].links[0].to_socket

            if self.direction == 'UP':
                group_tree.links.new(blend.outputs[0], swap_out_blend)
                group_tree.links.new(swap_blend.outputs[0], blend.inputs[1])
                group_tree.links.new(inp_blend, swap_blend.inputs[1])
            else:
                group_tree.links.new(swap_blend.outputs[0], out_blend)
                group_tree.links.new(blend.outputs[0], swap_blend.inputs[1])
                group_tree.links.new(swap_in_blend, blend.inputs[1])

        # Swap texture
        tg.textures.move(tex_idx, swap_idx)
        tg.active_texture_index = swap_idx

        # Rearrange nodes
        rearrange_nodes(group_tree)

        return {'FINISHED'}

class RemoveTextureLayer(bpy.types.Operator):
    bl_idname = "node.y_remove_texture_layer"
    bl_label = "Remove Texture Layer"
    bl_description = "New Texture Layer"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        group_node = get_active_texture_group_node()
        return group_node and len(group_node.node_tree.tg.textures) > 0

    def execute(self, context):
        node = get_active_texture_group_node()
        group_tree = node.node_tree
        nodes = group_tree.nodes
        tg = group_tree.tg

        tex = tg.textures[tg.active_texture_index]

        # Delete source
        nodes.remove(nodes.get(tex.source))
        nodes.remove(nodes.get(tex.linear))
        try: nodes.remove(nodes.get(tex.solid_alpha))
        except: pass

        nodes.remove(nodes.get(tex.source_frame))
        try: nodes.remove(nodes.get(tex.blend_frame))
        except: pass

        # Delete channels
        for ch in tex.channels:
            # Delete blend node and dealing with the links
            blend = nodes.get(ch.blend)
            inp = blend.inputs[1].links[0].from_socket
            outp = blend.outputs[0].links[0].to_socket
            group_tree.links.new(inp, outp)
            nodes.remove(blend)

            nodes.remove(nodes.get(ch.intensity))

            nodes.remove(nodes.get(ch.start_rgb))
            nodes.remove(nodes.get(ch.start_alpha))
            nodes.remove(nodes.get(ch.end_rgb))
            nodes.remove(nodes.get(ch.end_alpha))

            nodes.remove(nodes.get(ch.modifier_frame))

            # Remove modifiers
            for mod in ch.modifiers:
                delete_modifier_nodes(nodes, mod)

        # Delete the texture
        tg.textures.remove(tg.active_texture_index)

        # Set new active index
        if (tg.active_texture_index == len(tg.textures) and
            tg.active_texture_index > 0
            ):
            tg.active_texture_index -= 1

        # Rearrange nodes
        rearrange_nodes(group_tree)

        return {'FINISHED'}

class MoveTexModifier(bpy.types.Operator):
    bl_idname = "node.y_move_texture_modifier"
    bl_label = "Move Texture Modifier"
    bl_description = "Move Texture Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    direction = EnumProperty(
            name = 'Direction',
            items = (('UP', 'Up', ''),
                     ('DOWN', 'Down', '')),
            default = 'UP')

    parent_type = EnumProperty(
            name = 'Modifier Parent',
            items = (('CHANNEL', 'Channel', '' ),
                     ('TEXTURE_CHANNEL', 'Texture Channel', '' ),
                    ),
            default = 'TEXTURE_CHANNEL')

    channel_index = IntProperty(default=0)

    @classmethod
    def poll(cls, context):
        return get_active_texture_group_node()

    def execute(self, context):
        node = get_active_texture_group_node()
        group_tree = node.node_tree
        nodes = group_tree.nodes
        links = group_tree.links
        tg = group_tree.tg

        if len(tg.channels) == 0: return {'CANCELLED'}

        if self.parent_type == 'CHANNEL':
            parent = tg.channels[tg.active_channel_index]
        elif self.parent_type == 'TEXTURE_CHANNEL':
            if len(tg.textures) == 0: return {'CANCELLED'}
            tex = tg.textures[tg.active_texture_index]
            parent = tex.channels[self.channel_index]
        else: return

        num_mods = len(parent.modifiers)
        if num_mods < 2: return {'CANCELLED'}

        index = parent.active_modifier_index
        mod = parent.modifiers[index]

        # Get new index
        if self.direction == 'UP' and index > 0:
            new_index = index-1
        elif self.direction == 'DOWN' and index < num_mods-1:
            new_index = index+1
        else:
            return {'CANCELLED'}

        swap_mod = parent.modifiers[new_index]

        start_rgb = nodes.get(mod.start_rgb)
        start_alpha = nodes.get(mod.start_alpha)
        end_rgb = nodes.get(mod.end_rgb)
        end_alpha = nodes.get(mod.end_alpha)

        swap_start_rgb = nodes.get(swap_mod.start_rgb)
        swap_start_alpha = nodes.get(swap_mod.start_alpha)
        swap_end_rgb = nodes.get(swap_mod.end_rgb)
        swap_end_alpha = nodes.get(swap_mod.end_alpha)

        if self.direction == 'UP':
            links.new(end_rgb.outputs[0], swap_end_rgb.outputs[0].links[0].to_socket)
            links.new(end_alpha.outputs[0], swap_end_alpha.outputs[0].links[0].to_socket)

            links.new(start_rgb.inputs[0].links[0].from_socket, swap_start_rgb.inputs[0])
            links.new(start_alpha.inputs[0].links[0].from_socket, swap_start_alpha.inputs[0])

            links.new(swap_end_rgb.outputs[0], start_rgb.inputs[0])
            links.new(swap_end_alpha.outputs[0], start_alpha.inputs[0])

        else:
            links.new(swap_end_rgb.outputs[0], end_rgb.outputs[0].links[0].to_socket)
            links.new(swap_end_alpha.outputs[0], end_alpha.outputs[0].links[0].to_socket)

            links.new(swap_start_rgb.inputs[0].links[0].from_socket, start_rgb.inputs[0])
            links.new(swap_start_alpha.inputs[0].links[0].from_socket, start_alpha.inputs[0])

            links.new(end_rgb.outputs[0], swap_start_rgb.inputs[0])
            links.new(end_alpha.outputs[0], swap_start_alpha.inputs[0])

        # Swap modifier
        parent.modifiers.move(index, new_index)
        parent.active_modifier_index = new_index

        # Rearrange nodes
        rearrange_nodes(group_tree)

        return {'FINISHED'}

class RemoveTexModifier(bpy.types.Operator):
    bl_idname = "node.y_remove_texture_modifier"
    bl_label = "Remove Texture Modifier"
    bl_description = "Remove Texture Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    parent_type = EnumProperty(
            name = 'Modifier Parent',
            items = (('CHANNEL', 'Channel', '' ),
                     ('TEXTURE_CHANNEL', 'Texture Channel', '' ),
                    ),
            default = 'TEXTURE_CHANNEL')

    channel_index = IntProperty(default=0)

    @classmethod
    def poll(cls, context):
        return get_active_texture_group_node()

    def execute(self, context):
        node = get_active_texture_group_node()
        group_tree = node.node_tree
        nodes = group_tree.nodes
        links = group_tree.links
        tg = group_tree.tg

        if len(tg.channels) == 0: return {'CANCELLED'}

        if self.parent_type == 'CHANNEL':
            parent = tg.channels[tg.active_channel_index]
        elif self.parent_type == 'TEXTURE_CHANNEL':
            if len(tg.textures) == 0: return {'CANCELLED'}
            tex = tg.textures[tg.active_texture_index]
            parent = tex.channels[self.channel_index]
        else: return

        if len(parent.modifiers) < 1: return {'CANCELLED'}

        index = parent.active_modifier_index
        mod = parent.modifiers[index]

        prev_rgb = nodes.get(mod.start_rgb).inputs[0].links[0].from_socket
        next_rgb = nodes.get(mod.end_rgb).outputs[0].links[0].to_socket
        links.new(prev_rgb, next_rgb)

        prev_alpha = nodes.get(mod.start_alpha).inputs[0].links[0].from_socket
        next_alpha = nodes.get(mod.end_alpha).outputs[0].links[0].to_socket
        links.new(prev_alpha, next_alpha)

        # Delete the nodes
        delete_modifier_nodes(nodes, mod)

        # Delete the modifier
        parent.modifiers.remove(index)
        rearrange_nodes(group_tree)

        # Set new active index
        if (parent.active_modifier_index == len(parent.modifiers) and
            parent.active_modifier_index > 0
            ): parent.active_modifier_index -= 1

        return {'FINISHED'}

class NewTexModifier(bpy.types.Operator):
    bl_idname = "node.y_new_texture_modifier"
    bl_label = "New Texture Modifier"
    bl_description = "New Texture Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    type = EnumProperty(
        name = 'Modifier Type',
        items = modifier_type_items,
        default = 'INVERT')

    parent_type = EnumProperty(
            name = 'Modifier Parent',
            items = (('CHANNEL', 'Channel', '' ),
                     ('TEXTURE_CHANNEL', 'Texture Channel', '' ),
                    ),
            default = 'TEXTURE_CHANNEL')

    channel_index = IntProperty(default=0)

    @classmethod
    def poll(cls, context):
        return get_active_texture_group_node()

    def execute(self, context):
        node = get_active_texture_group_node()
        group_tree = node.node_tree
        nodes = group_tree.nodes
        links = group_tree.links
        tg = group_tree.tg

        if len(tg.channels) == 0: return {'CANCELLED'}

        if self.parent_type == 'CHANNEL':
            parent = tg.channels[tg.active_channel_index]
        elif self.parent_type == 'TEXTURE_CHANNEL':
            if len(tg.textures) == 0: return {'CANCELLED'}
            tex = tg.textures[tg.active_texture_index]
            parent = tex.channels[self.channel_index]
        else: return

        # Get start and end node
        parent_start_rgb = nodes.get(parent.start_rgb)
        parent_start_alpha = nodes.get(parent.start_alpha)
        parent_end_rgb = nodes.get(parent.end_rgb)
        parent_end_alpha = nodes.get(parent.end_alpha)
        parent_frame = nodes.get(parent.modifier_frame)

        # Get modifier list and its index
        modifiers = parent.modifiers
        #index = parent.active_modifier_index

        # Add new modifier and move it to the top
        m = modifiers.add()
        name = [mt[1] for mt in modifier_type_items if mt[0] == self.type][0]
        m.name = get_unique_name(name, modifiers)
        modifiers.move(len(modifiers)-1, 0)
        m = modifiers[0]
        m.type = self.type
        index = 0

        # Create new pipeline nodes
        start_rgb = nodes.new('NodeReroute')
        start_rgb.label = 'Start RGB'
        m.start_rgb = start_rgb.name

        start_alpha = nodes.new('NodeReroute')
        start_alpha.label = 'Start Alpha'
        m.start_alpha = start_alpha.name

        end_rgb = nodes.new('NodeReroute')
        end_rgb.label = 'End RGB'
        m.end_rgb = end_rgb.name

        end_alpha = nodes.new('NodeReroute')
        end_alpha.label = 'End Alpha'
        m.end_alpha = end_alpha.name

        frame = nodes.new('NodeFrame')
        m.frame = frame.name
        frame.parent = parent_frame
        start_rgb.parent = frame
        start_alpha.parent = frame
        end_rgb.parent = frame
        end_alpha.parent = frame

        # Link new nodes
        links.new(start_rgb.outputs[0], end_rgb.inputs[0])
        links.new(start_alpha.outputs[0], end_alpha.inputs[0])

        # Create the nodes
        if self.type == 'INVERT':
            invert = nodes.new('ShaderNodeInvert')
            m.invert = invert.name

            links.new(start_rgb.outputs[0], invert.inputs[1])
            links.new(invert.outputs[0], end_rgb.inputs[0])

            frame.label = 'Invert'
            invert.parent = frame

        elif m.type == 'RGB_TO_INTENSITY':

            rgb2i_color = nodes.new('ShaderNodeRGB')
            m.rgb2i_color = rgb2i_color.name

            rgb2i_linear = nodes.new('ShaderNodeGroup')
            rgb2i_linear.label = 'Linear'
            rgb2i_linear.node_tree = bpy.data.node_groups.get(LINEAR_TO_SRGB_COLOR_GROUP_NAME)
            m.rgb2i_linear = rgb2i_linear.name

            rgb2i_mix_rgb = nodes.new('ShaderNodeMixRGB')
            rgb2i_mix_rgb.label = 'Mix RGB'
            rgb2i_mix_rgb.inputs[0].default_value = 1.0
            m.rgb2i_mix_rgb = rgb2i_mix_rgb.name

            rgb2i_mix_alpha = nodes.new('ShaderNodeMixRGB')
            rgb2i_mix_alpha.label = 'Mix Alpha'
            rgb2i_mix_alpha.inputs[0].default_value = 1.0
            m.rgb2i_mix_alpha = rgb2i_mix_alpha.name

            links.new(rgb2i_color.outputs[0], rgb2i_linear.inputs[0])
            links.new(rgb2i_linear.outputs[0], rgb2i_mix_rgb.inputs[2])
            links.new(start_rgb.outputs[0], rgb2i_mix_rgb.inputs[1])
            links.new(rgb2i_mix_rgb.outputs[0], end_rgb.inputs[0])

            links.new(start_rgb.outputs[0], rgb2i_mix_alpha.inputs[2])
            links.new(start_alpha.outputs[0], rgb2i_mix_alpha.inputs[1])
            links.new(rgb2i_mix_alpha.outputs[0], end_alpha.inputs[0])

            frame.label = 'RGB to Intensity'
            rgb2i_color.parent = frame

        elif m.type == 'COLOR_RAMP':

            color_ramp = nodes.new('ShaderNodeValToRGB')
            m.color_ramp = color_ramp.name

            links.new(start_rgb.outputs[0], color_ramp.inputs[0])
            links.new(color_ramp.outputs[0], end_rgb.inputs[0])

            frame.label = 'Color Ramp'
            color_ramp.parent = frame

        elif m.type == 'RGB_CURVE':

            rgb_curve = nodes.new('ShaderNodeRGBCurve')
            m.rgb_curve = rgb_curve.name

            links.new(start_rgb.outputs[0], rgb_curve.inputs[1])
            links.new(rgb_curve.outputs[0], end_rgb.inputs[0])

            frame.label = 'RGB Curve'
            rgb_curve.parent = frame

        elif m.type == 'HUE_SATURATION':

            huesat = nodes.new('ShaderNodeHueSaturation')
            m.huesat = huesat.name

            links.new(start_rgb.outputs[0], huesat.inputs[4])
            links.new(huesat.outputs[0], end_rgb.inputs[0])

            frame.label = 'RGB Curve'
            huesat.parent = frame

        # Get previous modifier
        if len(modifiers) > 1 :
            prev_m = modifiers[1]
            prev_rgb = nodes.get(prev_m.end_rgb)
            prev_alpha = nodes.get(prev_m.end_alpha)
        else:
            prev_rgb = nodes.get(parent.start_rgb)
            prev_alpha = nodes.get(parent.start_alpha)

        # Connect to previous modifier
        links.new(prev_rgb.outputs[0], start_rgb.inputs[0])
        links.new(prev_alpha.outputs[0], start_alpha.inputs[0])

        # Connect to next modifier
        links.new(end_rgb.outputs[0], parent_end_rgb.inputs[0])
        links.new(end_alpha.outputs[0], parent_end_alpha.inputs[0])

        rearrange_nodes(group_tree)

        return {'FINISHED'}

def draw_tex_props(group_tree, tex, layout):

    nodes = group_tree.nodes
    tg = group_tree.tg

    source = nodes.get(tex.source)
    title = source.bl_idname.replace('ShaderNodeTex', '')

    row = layout.row()
    row.label(title + ' Properties:')
    icon = 'TRIA_DOWN' if tg.show_texture_properties else 'TRIA_RIGHT'
    row.prop(tg, 'show_texture_properties', emboss=False, text='', icon=icon)

    if not tg.show_texture_properties:
        return

    box = layout.box()
    bcol = box.column()

    if title != 'Image':
        row = bcol.row()
        col = row.column(align=True)
        col.label('Output:')
        col.label('Color Space:')
        col = row.column(align=True)
        col.prop(tex, 'tex_output', text='')
        col.prop(tex, 'color_space', text='')

        bcol.separator()

    if title == 'Brick':
        row = bcol.row()
        col = row.column(align=True)
        col.label('Offset:')
        col.label('Frequency:')
        col.separator()

        col.label('Squash:')
        col.label('Frequency:')
        col.separator()

        col.label('Color 1:')
        col.label('Color 2:')
        col.label('Mortar:')
        col.separator()
        col.label('Scale:')
        col.label('Mortar Size:')
        col.label('Mortar Smooth:')
        col.label('Bias:')
        col.label('Brick Width:')
        col.label('Brick Height:')

        col = row.column(align=True)
        col.prop(source, 'offset', text='')
        col.prop(source, 'offset_frequency', text='')
        col.separator()

        col.prop(source, 'squash', text='')
        col.prop(source, 'squash_frequency', text='')
        col.separator()
        for i in range (1,10):
            if i == 4: col.separator()
            col.prop(source.inputs[i], 'default_value', text='')

    elif title == 'Checker':

        row = bcol.row()
        col = row.column(align=True)
        col.label('Color 1:')
        col.label('Color 2:')
        col.separator()
        col.label('Scale:')
        col = row.column(align=True)
        for i in range (1,4):
            if i == 3: col.separator()
            col.prop(source.inputs[i], 'default_value', text='')

    elif title == 'Gradient':

        row = bcol.row()
        col = row.column(align=True)
        col.label('Type:')
        col = row.column(align=True)
        col.prop(source, 'gradient_type', text='')

    elif title == 'Magic':

        row = bcol.row()
        col = row.column(align=True)
        col.label('Depth:')
        col.label('Scale:')
        col.label('Distortion:')
        col = row.column(align=True)
        col.prop(source, 'turbulence_depth', text='')
        col.prop(source.inputs[1], 'default_value', text='')
        col.prop(source.inputs[2], 'default_value', text='')

    elif title == 'Noise':

        row = bcol.row()
        col = row.column(align=True)
        col.label('Scale:')
        col.label('Detail:')
        col.label('Distortion:')
        col = row.column(align=True)
        for i in range (1,4):
            col.prop(source.inputs[i], 'default_value', text='')

    elif title == 'Voronoi':

        row = bcol.row()
        col = row.column(align=True)
        col.label('Coloring:')
        col.separator()
        col.label('Scale:')
        col = row.column(align=True)
        col.prop(source, 'coloring', text='')
        col.separator()
        col.prop(source.inputs[1], 'default_value', text='')

    elif title == 'Wave':

        row = bcol.row()
        col = row.column(align=True)
        col.label('Type:')
        col.label('Profile:')
        col.label('Scale:')
        col.label('Distortion:')
        col.label('Detail:')
        col.label('Detail Scale:')
        col = row.column(align=True)
        col.prop(source, 'wave_type', text='')
        col.prop(source, 'wave_profile', text='')
        col.separator()
        for i in range (1,5):
            col.prop(source.inputs[i], 'default_value', text='')

def draw_modifier_properties(context, nodes, modifier, layout):

    if modifier.type not in {'INVERT'}:
        label = [mt[1] for mt in modifier_type_items if modifier.type == mt[0]][0]
        layout.label(label + ' Properties:')

    if modifier.type == 'INVERT':
        #invert = nodes.get(modifier.invert)
        #row = layout.row(align=True)
        #row.label('Factor:')
        #row.prop(invert.inputs[0], 'default_value', text='')
        #layout.label('Invert modifier has no properties')
        pass

    if modifier.type == 'RGB_TO_INTENSITY':
        rgb2i_color = nodes.get(modifier.rgb2i_color)
        row = layout.row(align=True)
        row.label('Color:')
        row.prop(rgb2i_color.outputs[0], 'default_value', text='')

    if modifier.type == 'COLOR_RAMP':
        color_ramp = nodes.get(modifier.color_ramp)
        layout.template_color_ramp(color_ramp, "color_ramp", expand=True)

    if modifier.type == 'RGB_CURVE':
        rgb_curve = nodes.get(modifier.rgb_curve)
        rgb_curve.draw_buttons_ext(context, layout)

    if modifier.type == 'HUE_SATURATION':
        huesat = nodes.get(modifier.huesat)
        row = layout.row(align=True)
        col = row.column(align=True)
        col.label('Hue:')
        col.label('Saturation:')
        col.label('Value:')

        col = row.column(align=True)
        for i in range(3):
            col.prop(huesat.inputs[i], 'default_value', text='')

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
        nodes = group_tree.nodes
        tg = group_tree.tg

        icon = 'TRIA_DOWN' if tg.show_channels else 'TRIA_RIGHT'
        row = layout.row(align=True)
        row.prop(tg, 'show_channels', emboss=False, text='', icon=icon)
        row.label('Channels')

        if tg.show_channels:

            box = layout.box()
            col = box.column()
            row = col.row()
            row.template_list("NODE_UL_y_texture_groups", "", tg,
                    "channels", tg, "active_channel_index", rows=4, maxrows=5)  
            rcol = row.column(align=True)
            rcol.operator_menu_enum("node.y_add_new_texture_group_channel", 'type', icon='ZOOMIN', text='')
            rcol.operator("node.y_remove_texture_group_channel", icon='ZOOMOUT', text='')
            rcol.operator("node.y_move_texture_group_channel", text='', icon='TRIA_UP').direction = 'UP'
            rcol.operator("node.y_move_texture_group_channel", text='', icon='TRIA_DOWN').direction = 'DOWN'

            col.prop(tg, 'preview_mode', text='Preview Mode')

            if len(tg.channels) > 0:
                channel = tg.channels[tg.active_channel_index]

                icon = 'TRIA_DOWN' if tg.show_end_modifiers else 'TRIA_RIGHT'
                row = col.row(align=True)
                row.label('Channel Modifiers:')
                row.prop(tg, 'show_end_modifiers', emboss=False, text='', icon=icon)
                if tg.show_end_modifiers:
                    bbox = col.box()
                    bcol = bbox.column()
                    bcol.label('Modifier:')

                    row = bcol.row()
                    row.template_list("NODE_UL_y_texture_modifiers", "", channel,
                            "modifiers", channel, "active_modifier_index", rows=4, maxrows=5)  

                    rcol = row.column(align=True)

                    rcol.context_pointer_set('channel', channel)
                    rcol.menu("NODE_MT_y_texture_modifier_specials", icon='ZOOMIN', text='')

                    op = rcol.operator('node.y_remove_texture_modifier', icon='ZOOMOUT', text='')
                    op.parent_type = 'CHANNEL'

                    op = rcol.operator('node.y_move_texture_modifier', icon='TRIA_UP', text='')
                    op.direction = 'UP'
                    op.parent_type = 'CHANNEL'

                    op = rcol.operator('node.y_move_texture_modifier', icon='TRIA_DOWN', text='')
                    op.direction = 'DOWN'
                    op.parent_type = 'CHANNEL'

                    if len(channel.modifiers) > 0:
                        mod = channel.modifiers[channel.active_modifier_index]
                        draw_modifier_properties(context, nodes, mod, bcol)

        icon = 'TRIA_DOWN' if tg.show_textures else 'TRIA_RIGHT'
        row = layout.row(align=True)
        row.prop(tg, 'show_textures', emboss=False, text='', icon=icon)
        row.label('Textures')

        if tg.show_textures:

            box = layout.box()
            col = box.column(align=False)

            row = col.row()
            row.template_list("NODE_UL_y_texture_layers", "", tg,
                    "textures", tg, "active_texture_index", rows=4, maxrows=5)  

            rcol = row.column(align=True)
            rcol.operator_menu_enum("node.y_new_texture_layer", 'type', icon='ZOOMIN', text='')
            rcol.operator("node.y_remove_texture_layer", icon='ZOOMOUT', text='')
            rcol.operator("node.y_move_texture_layer", text='', icon='TRIA_UP').direction = 'UP'
            rcol.operator("node.y_move_texture_layer", text='', icon='TRIA_DOWN').direction = 'DOWN'

            col.separator()

            if len(tg.textures) > 0:
                tex = tg.textures[tg.active_texture_index]

                if len(tex.channels) == 0:
                    col.label('No channel found!', icon='ERROR')

                for i, ch in enumerate(tex.channels):

                    #ccol = col.column(align=True)

                    row = col.row(align=True)
                    row.active = tex.enable
                    row.label(tg.channels[i].name + ':')

                    row.prop(ch, 'enable', text='')

                    row = row.row(align=True)
                    row.active = ch.enable

                    blend = nodes.get(ch.blend)
                    row.prop(blend, 'blend_type', text='')

                    intensity = nodes.get(ch.intensity)
                    row.prop(intensity.inputs[0], 'default_value', text='')

                    row.prop(tg.channels[i], 'show_modifiers', text='', icon='MODIFIER')

                    if tg.channels[i].show_modifiers:
                        bbox = col.box()
                        bbox.active = ch.enable and tex.enable
                        bcol = bbox.column()
                        #bcol = bbox.column(align
                        bcol.label('Modifier:')

                        row = bcol.row()
                        row.template_list("NODE_UL_y_texture_modifiers", "", ch,
                                "modifiers", ch, "active_modifier_index", rows=4, maxrows=5)  

                        rcol = row.column(align=True)

                        rcol.context_pointer_set('channel', ch)
                        rcol.menu("NODE_MT_y_texture_modifier_specials", icon='ZOOMIN', text='')

                        op = rcol.operator('node.y_remove_texture_modifier', icon='ZOOMOUT', text='')
                        op.parent_type = 'TEXTURE_CHANNEL'
                        op.channel_index = i

                        op = rcol.operator('node.y_move_texture_modifier', icon='TRIA_UP', text='')
                        op.direction = 'UP'
                        op.parent_type = 'TEXTURE_CHANNEL'
                        op.channel_index = i

                        op = rcol.operator('node.y_move_texture_modifier', icon='TRIA_DOWN', text='')
                        op.direction = 'DOWN'
                        op.parent_type = 'TEXTURE_CHANNEL'
                        op.channel_index = i

                        if len(ch.modifiers) > 0:
                            mod = ch.modifiers[ch.active_modifier_index]
                            draw_modifier_properties(context, nodes, mod, bcol)

                        col.separator()

                tcol = col.column()
                tcol.active = tex.enable

                draw_tex_props(group_tree, tex, tcol)

                #row = tcol.row()
                #row.label('Texture Modifiers:')
                #icon = 'TRIA_DOWN' if tg.show_texture_modifiers else 'TRIA_RIGHT'
                #row.prop(tg, 'show_texture_modifiers', emboss=False, text='', icon=icon)

                #if tg.show_texture_modifiers:
                #    bbox = tcol.box()

class NODE_UL_y_texture_groups(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        group_node = get_active_texture_group_node()
        #if not group_node: return
        inputs = group_node.inputs

        row = layout.row()
        row.prop(item, 'name', text='', emboss=False, icon='LINK')
        if item.type == 'VALUE':
            row.prop(inputs[index], 'default_value', text='') #, emboss=False)
        elif item.type == 'RGB':
            row.prop(inputs[index], 'default_value', text='', icon='COLOR')
        elif item.type == 'VECTOR':
            row.prop(inputs[index], 'default_value', text='', expand=False)

class NODE_UL_y_texture_layers(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        group_node = get_active_texture_group_node()
        #if not group_node: return
        tg = group_node.node_tree.tg
        nodes = group_node.node_tree.nodes

        # Get active channel
        #channel_idx = tg.active_channel_index
        #channel = tg.channels[channel_idx]

        master = layout.row(align=True)

        row = master.row(align=True)

        #if not item.enable or not item.channels[channel_idx].enable: row.active = False

        row.prop(item, 'name', text='', emboss=False, icon='TEXTURE')

        #blend = nodes.get(item.channels[channel_idx].blend)
        #row.prop(blend, 'blend_type', text ='')

        #intensity = nodes.get(item.channels[channel_idx].intensity)
        #row.prop(intensity.inputs[0], 'default_value', text='')

        #row = master.row()
        #if item.enable: row.active = True
        #else: row.active = False
        #row.prop(item.channels[channel_idx], 'enable', text='')

        row = master.row()
        if item.enable: eye_icon = 'RESTRICT_VIEW_OFF'
        else: eye_icon = 'RESTRICT_VIEW_ON'
        row.prop(item, 'enable', emboss=False, text='', icon=eye_icon)

class NODE_UL_y_texture_modifiers(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(item.name, icon='MODIFIER')
        layout.prop(item, 'enable', text='')

class TexModifierSpecialMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_texture_modifier_specials"
    bl_label = "Texture Channel Modifiers"

    @classmethod
    def poll(cls, context):
        return get_active_texture_group_node()

    def draw(self, context):
        node = get_active_texture_group_node()
        tg = node.node_tree.tg

        if 'LayerChannel' in str(type(context.channel)):
            tex = tg.textures[tg.active_texture_index]
            parent_type = 'TEXTURE_CHANNEL'
            # Get index number by channel from context
            index = [i for i, ch in enumerate(tex.channels) if ch == context.channel]
            if index: index = index[0]
            else: return
        elif 'GroupChannel' in str(type(context.channel)):
            parent_type = 'CHANNEL'
            index = 0
        else: return

        # List the items
        for mt in modifier_type_items:
            op = self.layout.operator('node.y_new_texture_modifier', text=mt[1])
            op.type = mt[0]
            op.parent_type = parent_type
            op.channel_index = index

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

def update_texture_enable(self, context):
    group_tree = self.id_data
    nodes = group_tree.nodes
    for ch in self.channels:
        if ch.enable:
            try: nodes.get(ch.blend).mute = not self.enable
            except: pass

def update_channel_enable(self, context):
    group_tree = self.id_data
    nodes = group_tree.nodes

    # Get texture
    tex = None
    for t in group_tree.tg.textures:
        for ch in t.channels:
            if ch == self:
                tex = t
                break

    #print(dir(self))
    try: 
        if tex.enable:
            nodes.get(self.blend).mute = not self.enable
    except: pass

def update_tex_output(self, context):
    group_tree = self.id_data
    nodes = group_tree.nodes

    source = nodes.get(self.source)
    linear = nodes.get(self.linear)

    group_tree.links.new(source.outputs[self.tex_output], linear.inputs[0])

def update_tex_color_space(self, context):
    group_tree = self.id_data
    nodes = group_tree.nodes

    linear = nodes.get(self.linear)
    if self.color_space == 'SRGB':
        linear.mute = False
    elif self.color_space == 'LINEAR':
        linear.mute = True

def update_preview_mode(self, context):
    try:
        mat = bpy.context.object.active_material
        tree = mat.node_tree
        nodes = tree.nodes
        group_node = get_active_texture_group_node()
        tg = group_node.node_tree.tg
        channel = tg.channels[tg.active_channel_index]
        index = tg.active_channel_index
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
        mat.tg.ori_output = output.name
        ori_bsdf = output.inputs[0].links[0].from_node

        if not preview:
            preview = nodes.new('ShaderNodeEmission')
            preview.name = 'Emission Viewer'
            preview.label = 'Preview'
            preview.hide = True
            preview.location = (output.location.x, output.location.y + 30.0)

        # Only remember original BSDF if its not the preview node itself
        if ori_bsdf != preview:
            mat.tg.ori_bsdf = ori_bsdf.name

        tree.links.new(group_node.outputs[index], preview.inputs[0])
        tree.links.new(preview.outputs[0], output.inputs[0])
    else:
        try: nodes.remove(preview)
        except: pass

        bsdf = nodes.get(mat.tg.ori_bsdf)
        output = nodes.get(mat.tg.ori_output)
        mat.tg.ori_bsdf = ''
        mat.tg.ori_output = ''

        try: tree.links.new(bsdf.outputs[0], output.inputs[0])
        except: pass

def update_active_group_channel(self, context):
    try: 
        group_node = get_active_texture_group_node()
        tg = group_node.node_tree.tg
    except: return
    
    if tg.preview_mode: tg.preview_mode = True

def update_modifier_enable(self, context):
    group_node = get_active_texture_group_node()
    nodes = group_node.node_tree.nodes
    #tg = group_node.node_tree.tg

    if self.type == 'RGB_TO_INTENSITY':
        rgb2i_color = nodes.get(self.rgb2i_color)
        rgb2i_linear = nodes.get(self.rgb2i_linear)
        rgb2i_mix_rgb = nodes.get(self.rgb2i_mix_rgb)
        rgb2i_mix_alpha = nodes.get(self.rgb2i_mix_alpha)
        rgb2i_color.mute = not self.enable
        rgb2i_linear.mute = not self.enable
        rgb2i_mix_rgb.mute = not self.enable
        rgb2i_mix_alpha.mute = not self.enable

    elif self.type == 'INVERT':
        invert = nodes.get(self.invert)
        invert.mute = not self.enable

    elif self.type == 'COLOR_RAMP':
        color_ramp = nodes.get(self.color_ramp)
        color_ramp.mute = not self.enable

    elif self.type == 'RGB_CURVE':
        rgb_curve = nodes.get(self.rgb_curve)
        rgb_curve.mute = not self.enable

    elif self.type == 'HUE_SATURATION':
        huesat = nodes.get(self.huesat)
        huesat.mute = not self.enable

class TextureModifier(bpy.types.PropertyGroup):
    enable = BoolProperty(default=True, update=update_modifier_enable)
    name = StringProperty(default='')

    type = EnumProperty(
        name = 'Modifier Type',
        items = modifier_type_items,
        default = 'INVERT')

    # Base nodes
    start_rgb = StringProperty(default='')
    start_alpha = StringProperty(default='')
    end_rgb = StringProperty(default='')
    end_alpha = StringProperty(default='')

    # RGB to Intensity nodes
    rgb2i_color = StringProperty(default='')
    rgb2i_linear = StringProperty(default='')
    rgb2i_mix_rgb = StringProperty(default='')
    rgb2i_mix_alpha = StringProperty(default='')

    # Invert nodes
    invert = StringProperty(default='')

    # Mask nodes
    mask_texture = StringProperty(default='')

    # Color Ramp nodes
    color_ramp = StringProperty(default='')

    # Grayscale to Normal nodes
    gray_to_normal = StringProperty(default='')

    # RGB Curve nodes
    rgb_curve = StringProperty(default='')

    # Hue Saturation nodes
    huesat = StringProperty(default='')

    # Individual modifier frame
    frame = StringProperty(default='')

class TempChannel(bpy.types.PropertyGroup):
    enable = BoolProperty(default=True)
    blend_type = EnumProperty(
        name = 'Blend',
        items = blend_type_items,
        default = 'MIX')

class LayerChannel(bpy.types.PropertyGroup):
    enable = BoolProperty(default=True, update=update_channel_enable)

    modifiers = CollectionProperty(type=TextureModifier)
    active_modifier_index = IntProperty(default=0)

    # Node names
    blend = StringProperty(default='')
    intensity = StringProperty(default='')

    # Modifier pipeline
    start_rgb = StringProperty(default='')
    start_alpha = StringProperty(default='')
    end_rgb = StringProperty(default='')
    end_alpha = StringProperty(default='')

    modifier_frame = StringProperty(default='')

class TextureLayer(bpy.types.PropertyGroup):
    name = StringProperty(default='')
    enable = BoolProperty(default=True, update=update_texture_enable)
    channels = CollectionProperty(type=LayerChannel)

    tex_output = EnumProperty(
            name = 'Texture Output',
            items = (('Color', 'Color', ''),
                     ('Fac', 'Factor', '')),
            default = 'Color',
            update = update_tex_output)

    color_space = EnumProperty(
            name = 'Color Space',
            items = (('LINEAR', 'Linear', ''),
                     ('SRGB', 'sRGB', '')),
            default = 'LINEAR',
            update = update_tex_color_space)

    type = EnumProperty(
            name = 'Texture Type',
            items = texture_type_items,
            default = 'ShaderNodeTexImage')

    # Node names
    source = StringProperty(default='')
    linear = StringProperty(default='')
    solid_alpha = StringProperty(default='')
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

    modifiers = CollectionProperty(type=TextureModifier)
    active_modifier_index = IntProperty(default=0)

    # Node names
    start_linear = StringProperty(default='')
    start_convert = StringProperty(default='')
    start_entry = StringProperty(default='')

    end_entry = StringProperty(default='')
    end_linear = StringProperty(default='')
    end_convert = StringProperty(default='')

    # For modifiers
    start_rgb = StringProperty(default='')
    start_alpha = StringProperty(default='')
    end_rgb = StringProperty(default='')
    end_alpha = StringProperty(default='')

    modifier_frame = StringProperty(default='')

    # UI related
    show_modifiers = BoolProperty(default=False)

class TextureGroup(bpy.types.PropertyGroup):
    is_tg_node = BoolProperty(default=False)

    # Channels
    channels = CollectionProperty(type=GroupChannel)
    active_channel_index = IntProperty(default=0, update=update_active_group_channel)

    # Textures
    textures = CollectionProperty(type=TextureLayer)
    active_texture_index = IntProperty(default=0)

    # Node names
    start = StringProperty(default='')
    start_frame = StringProperty(default='')

    end = StringProperty(default='')
    end_entry_frame = StringProperty(default='')
    end_linear_frame = StringProperty(default='')

    # Temp channels to remember last channel selected when adding new texture
    temp_channels = CollectionProperty(type=TempChannel)

    # UI related
    show_channels = BoolProperty(default=True)
    show_textures = BoolProperty(default=True)
    show_texture_properties = BoolProperty(default=True)
    #show_texture_modifiers = BoolProperty(default=True)
    show_end_modifiers = BoolProperty(default=False)

    preview_mode = BoolProperty(default=False, update=update_preview_mode)

class MaterialTGProps(bpy.types.PropertyGroup):
    ori_bsdf = StringProperty(default='')
    ori_output = StringProperty(default='')

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
    bpy.types.Material.tg = PointerProperty(type=MaterialTGProps)

    bpy.types.NODE_MT_add.append(menu_func)

def unregister():
    bpy.types.NODE_MT_add.remove(menu_func)
    bpy.utils.unregister_module(__name__)

if __name__ == "__main__":
    register()
