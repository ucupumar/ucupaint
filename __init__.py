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

if "bpy" in locals():
    import imp
    imp.reload(image_ops)
    #print("Reloaded multifiles")
else:
    from . import image_ops
    #print("Imported multifiles")

import bpy
from bpy.props import *
from bpy.app.handlers import persistent
from .common import *
from mathutils import *

GAMMA = 2.2

# Imported node group names
UDN = '~UDN Blend'
DETAIL_ORIENTED = '~Detail Oriented Blend'

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
        ('BRIGHT_CONTRAST', 'Brightness Contrast', ''),
        #('GRAYSCALE_TO_NORMAL', 'Grayscale To Normal', ''),
        #('MASK', 'Mask', ''),
        )

texcoord_type_items = (
        ('Generated', 'Generated', ''),
        ('Normal', 'Normal', ''),
        ('UV', 'UV', ''),
        ('Object', 'Object', ''),
        ('Camera', 'Camera', ''),
        ('Window', 'Window', ''),
        ('Reflection', 'Reflection', ''),
        )

vector_blend_items = (
        ('MIX', 'Mix', ''),
        ('UDN', 'UDN', ''),
        ('DETAIL_ORIENTED', 'Detail', '')
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

def update_image_editor_image(context, image):
    for area in context.screen.areas:
        if area.type == 'IMAGE_EDITOR':
            if not area.spaces[0].use_image_pin:
                area.spaces[0].image = image

def create_texture_channel_nodes(group_tree, texture, channel):

    tg = group_tree.tg
    nodes = group_tree.nodes
    links = group_tree.links

    ch_index = [i for i, c in enumerate(texture.channels) if c == channel][0]
    group_ch = tg.channels[ch_index]

    # Linear nodes
    #linear = nodes.new('ShaderNodeGamma')
    #linear.label = 'Source Linear'
    #linear.inputs[1].default_value = 1.0/GAMMA
    #channel.linear = linear.name

    # Modifier pipeline nodes
    start_rgb = nodes.new('NodeReroute')
    start_rgb.label = 'Start RGB'
    channel.start_rgb = start_rgb.name

    start_alpha = nodes.new('NodeReroute')
    start_alpha.label = 'Start Alpha'
    channel.start_alpha = start_alpha.name

    end_rgb = nodes.new('NodeReroute')
    end_rgb.label = 'End RGB'
    channel.end_rgb = end_rgb.name

    end_alpha = nodes.new('NodeReroute')
    end_alpha.label = 'End Alpha'
    channel.end_alpha = end_alpha.name

    # Intensity nodes
    intensity = nodes.new('ShaderNodeMixRGB')
    #intensity.blend_type = 'MULTIPLY'
    intensity.label = 'Intensity'
    intensity.inputs[0].default_value = 1.0
    intensity.inputs[1].default_value = (0,0,0,1)
    intensity.inputs[2].default_value = (1,1,1,1)
    channel.intensity = intensity.name

    # Blend nodes
    if group_ch.type == 'VECTOR':
        blend = nodes.new('ShaderNodeGroup')
        blend.node_tree = bpy.data.node_groups.get(DETAIL_ORIENTED)
    else:
        blend = nodes.new('ShaderNodeMixRGB')

    blend.label = 'Blend'
    channel.blend = blend.name

    # Normal nodes
    if group_ch.type == 'VECTOR':
        normal = nodes.new('ShaderNodeNormalMap')
        channel.normal = normal.name

        bump = nodes.new('ShaderNodeBump')
        bump.inputs[1].default_value = 0.05
        channel.bump = bump.name

    # Blend frame
    blend_frame = nodes.get(texture.blend_frame)
    if not blend_frame:
        blend_frame = nodes.new('NodeFrame')
        blend_frame.label = 'Blend'
        texture.blend_frame = blend_frame.name

    blend.parent = blend_frame
    #intensity.parent = blend_frame

    # Get source RGB and alpha
    #linear = nodes.get(texture.linear)
    solid_alpha = nodes.get(texture.solid_alpha)
    source = nodes.get(texture.source)

    # Modifier frame
    modifier_frame = nodes.get(channel.modifier_frame)
    if not modifier_frame:
        modifier_frame = nodes.new('NodeFrame')
        modifier_frame.label = 'Modifiers'
        channel.modifier_frame = modifier_frame.name

    #intensity.parent = modifier_frame
    start_rgb.parent = modifier_frame
    start_alpha.parent = modifier_frame
    end_rgb.parent = modifier_frame
    end_alpha.parent = modifier_frame

    # Link nodes
    links.new(source.outputs[0], start_rgb.inputs[0])
    #links.new(source.outputs[0], linear.inputs[0])
    #links.new(linear.outputs[0], start_rgb.inputs[0])
    if solid_alpha:
        links.new(solid_alpha.outputs[0], start_alpha.inputs[0])
    else: links.new(source.outputs[1], start_alpha.inputs[0])

    links.new(start_rgb.outputs[0], end_rgb.inputs[0])
    links.new(start_alpha.outputs[0], end_alpha.inputs[0])
    #links.new(start_alpha.outputs[0], intensity.inputs[2])

    #if group_ch.type == 'VECTOR':
    #    links.new(end_rgb.outputs[0], bump.inputs[2])
    #    links.new(bump.outputs[0], blend.inputs[2])
    #else:
    links.new(end_rgb.outputs[0], blend.inputs[2])

    links.new(end_alpha.outputs[0], intensity.inputs[2])
    links.new(intensity.outputs[0], blend.inputs[0])

    return blend

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
        if channel.type == 'RGB':
            start_linear = group_tree.nodes.new('ShaderNodeGamma')
        else: 
            start_linear = group_tree.nodes.new('ShaderNodeMath')
            start_linear.operation = 'POWER'
        start_linear.label = 'Start Linear'
        start_linear.inputs[1].default_value = 1.0/GAMMA

        start_linear.parent = start_frame
        channel.start_linear = start_linear.name

        if channel.type == 'RGB':
            end_linear = group_tree.nodes.new('ShaderNodeGamma')
        else: 
            end_linear = group_tree.nodes.new('ShaderNodeMath')
            end_linear.operation = 'POWER'
        end_linear.label = 'End Linear'
        end_linear.inputs[1].default_value = GAMMA

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

            # Add new nodes
            blend = create_texture_channel_nodes(group_tree, t, c)

            if channel.type == 'VECTOR':
                c.normal_map_type = 'NORMAL'
                c.normal_map_type = 'BUMP'

            # Set color space of source input
            #if t.type not in {'ShaderNodeTexImage', 'ShaderNodeTexChecker'}:
            #    c.color_space = 'LINEAR'
            #else: c.color_space = 'SRGB'

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

    elif mod.type == 'BRIGHT_CONTRAST':
        nodes.remove(nodes.get(mod.brightcon))

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

        elif m.type == 'BRIGHT_CONTRAST':

            brightcon = nodes.get(m.brightcon)
            if brightcon.location != new_loc: brightcon.location = new_loc

            new_loc.y -= 150.0

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

            new_loc.y -= 180.0

            # Normal node
            normal = nodes.get(c.normal)
            if normal:
                if normal.location != new_loc: normal.location = new_loc
                new_loc.y -= 160.0

            # Bump node
            bump = nodes.get(c.bump)
            if bump:
                if bump.location != new_loc: bump.location = new_loc
                new_loc.y -= 175.0

            new_loc.y -= 40.0

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
            new_loc.y -= 50.0

            # Linear node
            #linear = nodes.get(c.linear)
            #if linear.location != new_loc: linear.location = new_loc

            #new_loc.y -= 120.0
            new_loc.x += dist_x

            ys.append(new_loc.y)

            #new_loc.y -= dist_y

        # Sort y locations and use the first one
        if ys:
            ys.sort()
            new_loc.y = ys[0]

        new_loc.x = ori_xx
        #new_loc.y -= 140.0
        new_loc.y -= 50.0

        # Source solid alpha
        solid_alpha = nodes.get(t.solid_alpha)
        if solid_alpha:
            if solid_alpha.location != new_loc: solid_alpha.location = new_loc
            new_loc.y -= 95.0

        # Texcoord node
        texcoord = nodes.get(t.texcoord)
        if texcoord.location != new_loc: texcoord.location = new_loc

        new_loc.y -= 245.0

        # Texcoord node
        uv_map = nodes.get(t.uv_map)
        if uv_map.location != new_loc: uv_map.location = new_loc

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
        #return context.window_manager.invoke_popup(self)

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
        temp_ch = group_tree.tg.temp_channels.add()
        temp_ch.enable = False

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
            #nodes.remove(nodes.get(ch.linear))
            try: nodes.remove(nodes.get(ch.normal))
            except: pass
            try: nodes.remove(nodes.get(ch.bump))
            except: pass

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

    name = StringProperty(default='')

    type = EnumProperty(
            name = 'Texture Type',
            items = texture_type_items,
            default = 'ShaderNodeTexImage')

    # For image texture
    width = IntProperty(name='Width', default = 1024, min=1, max=16384)
    height = IntProperty(name='Height', default = 1024, min=1, max=16384)
    color = FloatVectorProperty(name='Color', size=4, subtype='COLOR', default=(0.0,0.0,0.0,0.0), min=0.0, max=1.0)
    alpha = BoolProperty(name='Alpha', default=True)
    hdr = BoolProperty(name='32 bit Float', default=False)

    texcoord_type = EnumProperty(
            name = 'Texture Coordinate Type',
            items = texcoord_type_items,
            default = 'UV')

    uv_map = StringProperty(default='')

    @classmethod
    def poll(cls, context):
        return get_active_texture_group_node()

    def invoke(self, context, event):
        node = get_active_texture_group_node()
        tg = node.node_tree.tg
        obj = context.object

        name = self.type.replace('ShaderNodeTex', '')
        self.name = get_unique_name(name, tg.textures)

        if obj.type != 'MESH':
            self.texcoord_type = 'Object'

        # Use active uv layer name by default
        if obj.type == 'MESH' and len(obj.data.uv_textures) > 0:
            self.uv_map = obj.data.uv_textures.active.name

        return context.window_manager.invoke_props_dialog(self)

    def check(self, context):
        return True

    def draw(self, context):
        node = get_active_texture_group_node()
        tg = node.node_tree.tg
        obj = context.object

        #col = self.layout.column(align=True)

        if len(tg.channels) == 0:
            self.layout.label('No channel found! Still want to create a texture?', icon='ERROR')
            return

        row = self.layout.row(align=True)
        col = row.column(align=False)

        #col.label('Type: ' + type_name)
        col.label('Name:')
        if self.type == 'ShaderNodeTexImage':
            col.label('Width:')
            col.label('Height:')
            col.label('Color:')
            col.label('')
            #col.label('Generated Type')
            col.label('')
            #col.label('Blend:')
            #col.label('UV Layer')

        col.label('Vector:')
        col.label('Channels:')
        for i, ch in enumerate(tg.channels):
            rrow = col.row(align=True)
            rrow.label(ch.name + ':', icon='LINK')
            rrow.prop(tg.temp_channels[i], 'enable', text='')

        col = row.column(align=False)
        col.prop(self, 'name', text='')
        if self.type == 'ShaderNodeTexImage':
            col.prop(self, 'width', text='')
            col.prop(self, 'height', text='')
            col.prop(self, 'color', text='')
            col.prop(self, 'alpha')
            #col.prop(self, 'generated_type', text='')
            col.prop(self, 'hdr')
            #col.prop(self, 'blend_type', text='')

        crow = col.row(align=True)
        crow.prop(self, 'texcoord_type', text='')
        if obj.type == 'MESH' and self.texcoord_type == 'UV':
            crow.prop_search(self, "uv_map", obj.data, "uv_textures", text='', icon='GROUP_UVS')

        col.label('')

        for i, ch in enumerate(tg.channels):
            rrow = col.row(align=True)
            rrow.active = tg.temp_channels[i].enable
            if ch.type == 'VECTOR':
                rrow.prop(tg.temp_channels[i], 'vector_blend', text='')
            else:
                rrow.prop(tg.temp_channels[i], 'blend_type', text='')

    def execute(self, context):
        node = get_active_texture_group_node()
        group_tree = node.node_tree
        nodes = group_tree.nodes
        links = group_tree.links
        tg = group_tree.tg

        # Check if texture with same name is already available
        same_name = [t for t in tg.textures if t.name == self.name]
        if same_name:
            self.report({'ERROR'}, "Texture named '" + self.name +"' is already available!")
            return {'CANCELLED'}

        # Add texture to group
        tex = tg.textures.add()
        tex.type = self.type
        tex.name = self.name

        # Move new texture to current index
        last_index = len(tg.textures)-1
        index = tg.active_texture_index
        tg.textures.move(last_index, index)
        tex = tg.textures[index] # Repoint to new index

        # Add source frame
        source_frame = nodes.new('NodeFrame')
        source_frame.label = 'Source'
        tex.source_frame = source_frame.name

        # Add source node
        source = nodes.new(self.type)
        source.label = 'Source'
        source.parent = source_frame
        tex.source = source.name

        # Always set non color to image node because of linear pipeline
        if self.type == 'ShaderNodeTexImage':
            source.color_space = 'NONE'

        # Add texcoord node
        texcoord = nodes.new('ShaderNodeTexCoord')
        texcoord.label = 'Source TexCoord'
        texcoord.parent = source_frame
        tex.texcoord = texcoord.name

        # Add uv map node
        uv_map = nodes.new('ShaderNodeUVMap')
        uv_map.label = 'Source UV Map'
        uv_map.parent = source_frame
        uv_map.uv_map = self.uv_map
        tex.uv_map = uv_map.name

        # Set tex coordinate type
        tex.texcoord_type = self.texcoord_type

        # Add new image if it's image texture
        if self.type == 'ShaderNodeTexImage':
            img = bpy.data.images.new(self.name, self.width, self.height, self.alpha, self.hdr)
            #img.generated_type = self.generated_type
            img.generated_type = 'BLANK'
            img.generated_color = self.color
            source.image = img

            if self.hdr:
                img.colorspace_settings.name = 'sRGB'

            update_image_editor_image(context, img)

        # Solid alpha for non image texture
        if self.type != 'ShaderNodeTexImage':
            solid_alpha = nodes.new('ShaderNodeValue')
            solid_alpha.label = 'Solid Alpha'
            solid_alpha.outputs[0].default_value = 1.0
            tex.solid_alpha = solid_alpha.name

            solid_alpha.parent = source_frame

        # Add channels
        for i, ch in enumerate(tg.channels):
            # Add new channel to current texture
            c = tex.channels.add()

            # Add blend and other nodes
            blend = create_texture_channel_nodes(group_tree, tex, c)
            if ch.type != 'VECTOR':
                blend.blend_type = tg.temp_channels[i].blend_type

            if ch.type == 'VECTOR':
                c.normal_map_type = 'NORMAL'
                c.normal_map_type = 'BUMP'

            # Set color space of source input
            #if (tex.type == 'ShaderNodeTexImage' and not self.hdr) or tex.type == 'ShaderNodeTexChecker':
            #if tex.type == 'ShaderNodeTexImage' or tex.type == 'ShaderNodeTexChecker':
            #    c.color_space = 'SRGB'
            #else: 
            #    c.color_space = 'LINEAR'

            # Set enable and blend node automatically follows
            c.enable = tg.temp_channels[i].enable

            # Link neighbor nodes
            if index < len(tg.textures)-1:
                below_blend = nodes.get(tg.textures[index+1].channels[i].blend)
            else: below_blend = nodes.get(tg.channels[i].start_entry)
            links.new(below_blend.outputs[0], blend.inputs[1])

            if index > 0:
                upper_blend = nodes.get(tg.textures[index-1].channels[i].blend)
                links.new(blend.outputs[0], upper_blend.inputs[1])
            else: 
                end_entry = nodes.get(tg.channels[i].end_entry)
                links.new(blend.outputs[0], end_entry.inputs[0])

        # Rearrange nodes
        rearrange_nodes(group_tree)

        # Refresh paint image by updating the index
        tg.active_texture_index = index

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
        nodes.remove(nodes.get(tex.texcoord))
        nodes.remove(nodes.get(tex.uv_map))
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
            #nodes.remove(nodes.get(ch.linear))

            nodes.remove(nodes.get(ch.start_rgb))
            nodes.remove(nodes.get(ch.start_alpha))
            nodes.remove(nodes.get(ch.end_rgb))
            nodes.remove(nodes.get(ch.end_alpha))

            nodes.remove(nodes.get(ch.modifier_frame))

            try: nodes.remove(nodes.get(ch.normal))
            except: pass
            try: nodes.remove(nodes.get(ch.bump))
            except: pass

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
        else:
            # Force update the index to refesh paint image
            tg.active_texture_index = tg.active_texture_index

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

            rgb2i_linear = nodes.new('ShaderNodeGamma')
            rgb2i_linear.label = 'Linear'
            rgb2i_linear.inputs[1].default_value = 1.0/GAMMA
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

        elif m.type == 'BRIGHT_CONTRAST':

            brightcon = nodes.new('ShaderNodeBrightContrast')
            m.brightcon = brightcon.name

            links.new(start_rgb.outputs[0], brightcon.inputs[0])
            links.new(brightcon.outputs[0], end_rgb.inputs[0])

            frame.label = 'Brightness Contrast'
            brightcon.parent = frame

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

class YHackNormalConsistency(bpy.types.Operator):
    bl_idname = "node.y_hack_bump_consistency"
    bl_label = "Hack Normal Map Consistency"
    bl_description = "Hack bump map consistency (try this if Blender produce error normal map result)"
    #bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_texture_group_node()

    def execute(self, context):
        node = get_active_texture_group_node()
        group_tree = node.node_tree
        tg = group_tree.tg

        for tex in tg.textures:
            for i, ch in enumerate(tex.channels):
                if tg.channels[i].type != 'VECTOR': continue
                if ch.normal_map_type == 'BUMP':
                    ch.normal_map_type = 'NORMAL'
                    ch.normal_map_type = 'BUMP'
                else:
                    ch.normal_map_type = 'BUMP'
                    ch.normal_map_type = 'NORMAL'

        return {'FINISHED'}

def draw_tex_props(group_tree, tex, layout):

    nodes = group_tree.nodes
    tg = group_tree.tg

    source = nodes.get(tex.source)
    title = source.bl_idname.replace('ShaderNodeTex', '')

    col = layout.column()
    #col.label(title + ' Properties:')
    #col.separator()

    if title == 'Brick':
        row = col.row()
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

        row = col.row()
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

        row = col.row()
        col = row.column(align=True)
        col.label('Type:')
        col = row.column(align=True)
        col.prop(source, 'gradient_type', text='')

    elif title == 'Magic':

        row = col.row()
        col = row.column(align=True)
        col.label('Depth:')
        col.label('Scale:')
        col.label('Distortion:')
        col = row.column(align=True)
        col.prop(source, 'turbulence_depth', text='')
        col.prop(source.inputs[1], 'default_value', text='')
        col.prop(source.inputs[2], 'default_value', text='')

    elif title == 'Noise':

        row = col.row()
        col = row.column(align=True)
        col.label('Scale:')
        col.label('Detail:')
        col.label('Distortion:')
        col = row.column(align=True)
        for i in range (1,4):
            col.prop(source.inputs[i], 'default_value', text='')

    elif title == 'Voronoi':

        row = col.row()
        col = row.column(align=True)
        col.label('Coloring:')
        col.separator()
        col.label('Scale:')
        col = row.column(align=True)
        col.prop(source, 'coloring', text='')
        col.separator()
        col.prop(source.inputs[1], 'default_value', text='')

    elif title == 'Wave':

        row = col.row()
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

    elif modifier.type == 'RGB_TO_INTENSITY':
        rgb2i_color = nodes.get(modifier.rgb2i_color)
        row = layout.row(align=True)
        row.label('Color:')
        row.prop(rgb2i_color.outputs[0], 'default_value', text='')

    elif modifier.type == 'COLOR_RAMP':
        color_ramp = nodes.get(modifier.color_ramp)
        layout.template_color_ramp(color_ramp, "color_ramp", expand=True)

    elif modifier.type == 'RGB_CURVE':
        rgb_curve = nodes.get(modifier.rgb_curve)
        rgb_curve.draw_buttons_ext(context, layout)

    elif modifier.type == 'HUE_SATURATION':
        huesat = nodes.get(modifier.huesat)
        row = layout.row(align=True)
        col = row.column(align=True)
        col.label('Hue:')
        col.label('Saturation:')
        col.label('Value:')

        col = row.column(align=True)
        for i in range(3):
            col.prop(huesat.inputs[i], 'default_value', text='')

    elif modifier.type == 'BRIGHT_CONTRAST':
        brightcon = nodes.get(modifier.brightcon)
        row = layout.row(align=True)
        col = row.column(align=True)
        col.label('Brightness:')
        col.label('Contrast:')

        col = row.column(align=True)
        col.prop(brightcon.inputs[1], 'default_value', text='')
        col.prop(brightcon.inputs[2], 'default_value', text='')

#class YPopupMenu(bpy.types.Operator):
#    bl_idname = "node.y_popup_menu"
#    bl_label = "Popup menu"
#    bl_description = 'Popup menu'
#
#    name = StringProperty(default='Ewsom')
#
#    @classmethod
#    def poll(cls, context):
#        return get_active_texture_group_node()
#
#    #@staticmethod
#    def draw(self, context):
#        node = get_active_texture_group_node()
#        #self.layout.prop(context.scene, 'name')
#        self.layout.prop(self, 'name')
#        #draw_tex_props(node.node_tree, context.texture, self.layout)
#
#    def invoke(self, context, event):
#        #context.window_manager.invoke_popup(self)
#        return context.window_manager.invoke_popup(self)
#        #return context.window_manager.invoke_props_dialog(self)
#        #wm.popup_menu(self.draw_func, title="THE TITLE", icon="INFO")
#        #context.window_manager.popup_menu(self.draw)
#        #context.window_manager.popup_menu_pie(self.draw)
#        #return {'RUNNING_MODAL'}
#
#    def check(self, context):
#        #self.execute(context)
#        return True
#
#    def execute(self, context):
#        #context.window_manager.invoke_props_dialog(self)
#    #    popup_main(context)
#        #print('Something happen!')
#        context.scene.name = self.name
#        return {'FINISHED'}

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
        obj = context.object
        is_a_mesh = True if obj and obj.type == 'MESH' else False
        node = get_active_texture_group_node()

        layout = self.layout

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

            pcol = col.column()

            if tg.preview_mode: pcol.alert = True
            pcol.prop(tg, 'preview_mode', text='Preview Mode', icon='RESTRICT_VIEW_OFF')

            if len(tg.channels) > 0:

                mcol = col.column(align=True)

                channel = tg.channels[tg.active_channel_index]

                icon = 'TRIA_DOWN' if tg.show_end_modifiers else 'TRIA_RIGHT'
                row = mcol.row(align=True)
                row.label(channel.name + ' Properties:')
                row.prop(tg, 'show_end_modifiers', text='', icon=icon)
                if tg.show_end_modifiers:
                    bbox = mcol.box()
                    bcol = bbox.column()

                    inp = node.inputs[tg.active_channel_index]
                    brow = bcol.row(align=True)
                    if channel.type == 'RGB':
                        brow.label('Background:')
                    elif channel.type == 'VALUE':
                        brow.label('Base Value:')
                    elif channel.type == 'VECTOR':
                        brow.label('Base Vector:')

                    brow.prop(inp,'default_value', text='')

                    bcol.label('Final Modifiers:')

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

            # Check if uv is found
            uv_found = False
            if is_a_mesh and len(obj.data.uv_textures) > 0: 
                uv_found = True

            if is_a_mesh and not uv_found:
                row = box.row(align=True)
                row.alert = True
                row.operator("node.y_add_simple_uvs", icon='ERROR')
                row.alert = False
                return

            # Get texture, image and set context pointer
            tex = None
            source = None
            image = None
            if len(tg.textures) > 0:
                tex = tg.textures[tg.active_texture_index]
                box.context_pointer_set('texture', tex)

                source = nodes.get(tex.source)
                if tex.type == 'ShaderNodeTexImage':
                    image = source.image
                    box.context_pointer_set('image', image)

            col = box.column()

            row = col.row()
            row.template_list("NODE_UL_y_texture_layers", "", tg,
                    "textures", tg, "active_texture_index", rows=5, maxrows=5)  

            rcol = row.column(align=True)
            rcol.operator_menu_enum("node.y_new_texture_layer", 'type', icon='ZOOMIN', text='')
            rcol.operator("node.y_remove_texture_layer", icon='ZOOMOUT', text='')
            rcol.operator("node.y_move_texture_layer", text='', icon='TRIA_UP').direction = 'UP'
            rcol.operator("node.y_move_texture_layer", text='', icon='TRIA_DOWN').direction = 'DOWN'
            rcol.menu("NODE_MT_y_texture_specials", text='', icon='DOWNARROW_HLT')

            col = box.column()

            if tex:

                col.active = tex.enable

                ccol = col.column(align=True)
                row = ccol.row(align=True)
                
                if image:
                    #row.prop(source, "image", text='')
                    #row.prop_search(source, "image", bpy.data, 'images', text='')
                    row.template_ID(source, "image",
                            #open='paint.yp_open_paint_texture_from_file', 
                            unlink='node.y_remove_texture_layer')
                    row.operator("node.y_reload_image", text="", icon='FILE_REFRESH')
                else:
                    title = source.bl_idname.replace('ShaderNodeTex', '')
                    row.label(title + ' Properties:', icon='TEXTURE')
                    #row.label(tex.name, icon='TEXTURE')
                    #row.prop(tg, 'show_texture_properties', emboss=False, text='', icon=icon)

                icon = 'TRIA_DOWN' if tg.show_texture_properties else 'TRIA_RIGHT'
                row.prop(tg, 'show_texture_properties', text='', icon=icon)

                #rrow = row.row(align=True)
                #rrow.context_pointer_set('texture', tex)
                #rrow.operator('node.y_popup_menu', text='', icon='SCRIPTWIN')

                if tg.show_texture_properties:
                    bbox = ccol.box()
                    if not image:
                        draw_tex_props(group_tree, tex, bbox)
                    else:
                        incol = bbox.column()
                        if image.source == 'GENERATED':
                            incol.label('Generated image settings:')
                            row = incol.row()

                            col1 = row.column(align=True)
                            col1.prop(image, 'generated_width', text='X')
                            col1.prop(image, 'generated_height', text='Y')

                            col1.prop(image, 'use_generated_float', text='Float Buffer')
                            col2 = row.column(align=True)
                            col2.prop(image, 'generated_type', expand=True)

                            row = incol.row()
                            row.label('Color:')
                            row.prop(image, 'generated_color', text='')
                            incol.template_colorspace_settings(image, "colorspace_settings")

                        elif image.source == 'FILE':
                            if not image.filepath:
                                incol.label('Image Path: -')
                            else:
                                incol.label('Path: ' + image.filepath)

                            image_format = 'RGBA'
                            image_bit = int(image.depth/4)
                            if image.depth in {24, 48, 96}:
                                image_format = 'RGB'
                                image_bit = int(image.depth/3)

                            incol.label('Info: ' + str(image.size[0]) + ' x ' + str(image.size[1]) +
                                    ' ' + image_format + ' ' + str(image_bit) + '-bit')

                            incol.template_colorspace_settings(image, "colorspace_settings")
                            #incol.prop(image, 'use_view_as_render')
                            incol.prop(image, 'alpha_mode')
                            incol.prop(image, 'use_alpha')
                            #incol.prop(image, 'use_fields')
                            #incol.template_image(tex, "image", tex.image_user)
                        #ccol = bbox.column()
                        #ccol.operator("node.y_reload_image", icon='FILE_REFRESH')

                ccol.separator()

                #ccol = col.column(align=True)
                #col.label('Channels:')

                if len(tex.channels) == 0:
                    col.label('No channel found!', icon='ERROR')

                for i, ch in enumerate(tex.channels):

                    group_ch = tg.channels[i]

                    ccol = col.column(align=True)

                    row = ccol.row(align=True)
                    row.label(tg.channels[i].name + ':') #, icon='LINK')

                    row.prop(ch, 'enable', text='')

                    row = row.row(align=True)
                    row.active = ch.enable

                    if group_ch.type == 'VECTOR':
                        row.prop(ch, 'vector_blend', text='')
                    else:
                        blend = nodes.get(ch.blend)
                        row.prop(blend, 'blend_type', text='')

                    intensity = nodes.get(ch.intensity)
                    row.prop(intensity.inputs[0], 'default_value', text='')

                    row.prop(tg.channels[i], 'show_modifiers', text='', icon='MODIFIER')

                    if tg.channels[i].show_modifiers:
                        bbox = ccol.box()
                        #bbox.alert = True
                        bbox.active = ch.enable
                        bcol = bbox.column()
                        #bcol = bbox.column(align

                        if group_ch.type == 'VECTOR':
                            #row = bcol.row(align=True)
                            #row.label('Norma:')
                            #row.prop(ch, 'tex_input', text='')
                            #row.prop(ch, 'color_space', text='')
                            bcol.prop(ch, 'normal_map_type')

                        #row = bcol.row(align=True)
                        #row.label('Input:')
                        #row.prop(ch, 'tex_input', text='')
                        #row.prop(ch, 'color_space', text='')
                        if tex.type != 'ShaderNodeTexImage':
                            bcol.prop(ch, 'tex_input', text='Input')

                        row = bcol.row(align=True)
                        #crow = row.column(align=True)
                        row.label('Modifiers:')
                        #crow.label('Color Space:')
                        #crow = row.column(align=True)
                        #row.prop(ch, 'tex_input', text='')
                        #row.prop(ch, 'color_space', text='')

                        #bcol.label(tg.channels[i].name + ' Modifiers:')
                        #bcol.label('Modifiers:')

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

                        ccol.separator()

                    if i == len(tex.channels)-1: #and i > 0:
                        ccol.separator()

                ccol = col.column(align=True)

                row = ccol.row(align=True)
                split = row.split(percentage=0.26, align=True)
                split.label('Vector:')
                if is_a_mesh and tex.texcoord_type == 'UV':
                    uv_map = nodes.get(tex.uv_map)
                    ssplit = split.split(percentage=0.33, align=True)
                    ssplit.prop(tex, 'texcoord_type', text='')
                    ssplit.prop_search(uv_map, "uv_map", obj.data, "uv_textures", text='')
                else:
                    split.prop(tex, 'texcoord_type', text='')

                icon = 'TRIA_DOWN' if tg.show_vector_properties else 'TRIA_RIGHT'
                row.prop(tg, 'show_vector_properties', text='', icon=icon)

                if tg.show_vector_properties:
                    bbox = ccol.box()
                    #if tex.texcoord_type == 'UV':
                    bbox.prop(source.texture_mapping, 'translation', text='Offset')
                    bbox.prop(source.texture_mapping, 'scale')
                    #else:
                    #    bbox.label('This option has no settings yet!')
                    ccol.separator()

                ccol = col.column(align=True)

                row = ccol.row(align=True)
                row.label('Mask:')

                icon = 'TRIA_DOWN' if tg.show_mask_properties else 'TRIA_RIGHT'
                row.prop(tg, 'show_mask_properties', text='', icon=icon)

                if tg.show_mask_properties:
                    bbox = ccol.box()

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
        #elif item.type == 'VECTOR':
        #    row.prop(inputs[index], 'default_value', text='', expand=False)

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

        if item.type == 'ShaderNodeTexImage':
            source = nodes.get(item.source)
            image = source.image
            row.context_pointer_set('image', image)
            row.prop(image, 'name', text='', emboss=False, icon_value=image.preview.icon_id)
            if image.is_dirty:
                row.label(text='', icon_value=custom_icons["asterisk"].icon_id)
            if image.packed_file:
                #row.label(text='', icon='PACKAGE')
                row.operator('node.y_pack_image', text='', icon='PACKAGE', emboss=False)
        else:
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

class TexSpecialMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_texture_specials"
    bl_label = "Texture Special Menu"

    @classmethod
    def poll(cls, context):
        return get_active_texture_group_node()

    def draw(self, context):
        self.layout.operator('node.y_pack_image', icon='UGLYPACKAGE')
        self.layout.operator('node.y_save_image', icon='FILE_TICK')
        self.layout.operator('node.y_save_image', text='Save As', icon='SAVE_AS')
        self.layout.operator('node.y_save_image', text='Save All', icon='FILE_TICK')
        self.layout.separator()
        self.layout.operator('node.y_hack_bump_consistency', icon='MATCAP_23')
        #self.layout.operator("node.y_reload_image", icon='FILE_REFRESH')

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
            #self.layout.prop(tex, 'name')

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

        blend = nodes.get(ch.blend)
        if not blend: continue

        if self.enable and ch.enable:
            blend.mute = False
        else: blend.mute = True

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

    blend = nodes.get(self.blend)
    if not blend: return

    if tex.enable and self.enable:
        blend.mute = False
    else: blend.mute = True

def update_tex_input(self, context):
    group_tree = self.id_data
    nodes = group_tree.nodes
    tg = group_tree.tg

    tex = None
    for t in tg.textures:
        for ch in t.channels:
            if ch == self:
                tex = t
                break
    if not tex: return

    source = nodes.get(tex.source)
    start_rgb = nodes.get(self.start_rgb)

    if self.tex_input == 'RGB': index = 0
    elif self.tex_input == 'ALPHA': index = 1
    else: return

    group_tree.links.new(source.outputs[index], start_rgb.inputs[0])

#def update_tex_channel_color_space(self, context):
#    group_tree = self.id_data
#    nodes = group_tree.nodes
#
#    linear = nodes.get(self.linear)
#    if not linear: return
#
#    if self.color_space == 'SRGB':
#        linear.mute = False
#    elif self.color_space == 'LINEAR':
#        linear.mute = True

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

    elif self.type == 'BRIGHT_CONTRAST':
        brightcon = nodes.get(self.brightcon)
        brightcon.mute = not self.enable

def update_texcoord_type(self, context):
    group_tree = self.id_data
    nodes = group_tree.nodes
    links = group_tree.links

    source = nodes.get(self.source)
    texcoord = nodes.get(self.texcoord)
    uv_map = nodes.get(self.uv_map)

    if self.texcoord_type == 'UV':
        links.new(uv_map.outputs[0], source.inputs[0])
    else:
        links.new(texcoord.outputs[self.texcoord_type], source.inputs[0])

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

    # Set image paint mode to Image
    scene.tool_settings.image_paint.mode = 'IMAGE'

    tex = self.textures[self.active_texture_index]
    if tex.type != 'ShaderNodeTexImage': 
        update_image_editor_image(context, None)
        scene.tool_settings.image_paint.canvas = None
        return

    # Get source image
    source = nodes.get(tex.source)
    if not source or not source.image: return

    # Update image editor
    update_image_editor_image(context, source.image)

    # Update tex paint
    scene.tool_settings.image_paint.canvas = source.image

    # Update uv layer
    if obj.type == 'MESH':
        uv_map = nodes.get(tex.uv_map)
        for i, uv in enumerate(obj.data.uv_textures):
            if uv.name == uv_map.uv_map:
                obj.data.uv_textures.active_index = i
                break

def update_normal_map_type(self, context):
    group_tree = self.id_data
    tg = group_tree.tg
    nodes = group_tree.nodes
    links = group_tree.links

    end_rgb = nodes.get(self.end_rgb)
    blend = nodes.get(self.blend)
    bump = nodes.get(self.bump)
    normal = nodes.get(self.normal)

    if self.normal_map_type == 'BUMP':
        links.new(end_rgb.outputs[0], bump.inputs[2])
        links.new(bump.outputs[0], blend.inputs[2])
    else:
        links.new(end_rgb.outputs[0], normal.inputs[1])
        links.new(normal.outputs[0], blend.inputs[2])

        # Normal always use RGB input and sRGB color space
        #self.tex_input = 'RGB'
        #self.color_space = 'SRGB'

def update_vector_blend(self, context):
    group_tree = self.id_data
    tg = group_tree.tg
    nodes = group_tree.nodes
    links = group_tree.links

    tex = None
    ch_index = -1
    for t in tg.textures:
        for i, ch in enumerate(t.channels):
            if ch == self:
                tex = t
                ch_index = i
                break
    if not tex: return

    group_ch = tg.channels[ch_index]
    if group_ch.type != 'VECTOR': return

    blend = nodes.get(self.blend)
    
    # Remember previous links
    in_0 = blend.inputs[0].links[0].from_socket
    in_1 = blend.inputs[1].links[0].from_socket
    in_2 = blend.inputs[2].links[0].from_socket
    out_node = blend.outputs[0].links[0].to_node
    out_name = blend.outputs[0].links[0].to_socket.name

    # Remove links
    links.remove(blend.inputs[0].links[0])
    links.remove(blend.inputs[1].links[0])
    links.remove(blend.inputs[2].links[0])
    links.remove(blend.outputs[0].links[0])

    # Remember previous position and parent
    loc = blend.location.copy()
    parent = blend.parent

    #print('Aha')

    # Create new node if type isn't match
    if self.vector_blend == 'MIX' and blend.bl_idname != 'ShaderNodeMixRGB':
        nodes.remove(blend)
        blend = nodes.new('ShaderNodeMixRGB')
    elif self.vector_blend in {'UDN', 'DETAIL_ORIENTED'} and blend.bl_idname != 'ShaderNodeGroup':
        nodes.remove(blend)
        blend = nodes.new('ShaderNodeGroup')

    blend.label = 'Blend'
    self.blend = blend.name
    blend.location = loc
    blend.parent = parent

    # Set node tree
    if self.vector_blend == 'UDN':
        blend.node_tree = bpy.data.node_groups.get(UDN)
    elif self.vector_blend == 'DETAIL_ORIENTED': 
        blend.node_tree = bpy.data.node_groups.get(DETAIL_ORIENTED)

    # Relinks
    links.new(in_0, blend.inputs[0])
    links.new(in_1, blend.inputs[1])
    link = links.new(in_2, blend.inputs[2])
    links.new(blend.outputs[0], out_node.inputs[out_name])

    # Hack
    if self.normal_map_type == 'BUMP':
        self.normal_map_type = 'NORMAL'
        self.normal_map_type = 'BUMP'
    else:
        self.normal_map_type = 'BUMP'
        self.normal_map_type = 'NORMAL'

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

    # Brightness Contrast nodes
    brightcon = StringProperty(default='')

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

    vector_blend = EnumProperty(
            name = 'Vector Blend Type',
            items = vector_blend_items,
            default = 'DETAIL_ORIENTED')

class LayerChannel(bpy.types.PropertyGroup):
    enable = BoolProperty(default=True, update=update_channel_enable)

    tex_input = EnumProperty(
            name = 'Input from Texture',
            items = (('RGB', 'Color', ''),
                     ('ALPHA', 'Alpha / Factor', '')),
            default = 'RGB',
            update = update_tex_input)

    #color_space = EnumProperty(
    #        name = 'Input Color Space',
    #        items = (('LINEAR', 'Linear', ''),
    #                 ('SRGB', 'sRGB', '')),
    #        default = 'LINEAR',
    #        update = update_tex_channel_color_space)

    normal_map_type = EnumProperty(
            name = 'Normal Map Type',
            items = (('BUMP', 'Bump Map', ''),
                     ('NORMAL', 'Normal Map', '')),
            default = 'BUMP',
            update = update_normal_map_type)

    vector_blend = EnumProperty(
            name = 'Vector Blend Type',
            items = vector_blend_items,
            default = 'DETAIL_ORIENTED',
            update = update_vector_blend)

    modifiers = CollectionProperty(type=TextureModifier)
    active_modifier_index = IntProperty(default=0)

    # Node names
    #linear = StringProperty(default='')
    blend = StringProperty(default='')
    intensity = StringProperty(default='')

    # Modifier pipeline
    start_rgb = StringProperty(default='')
    start_alpha = StringProperty(default='')
    end_rgb = StringProperty(default='')
    end_alpha = StringProperty(default='')

    # Normal related
    bump = StringProperty(default='')
    normal = StringProperty(default='')

    modifier_frame = StringProperty(default='')

class TextureLayer(bpy.types.PropertyGroup):
    name = StringProperty(default='')
    enable = BoolProperty(default=True, update=update_texture_enable)
    channels = CollectionProperty(type=LayerChannel)

    type = EnumProperty(
            name = 'Texture Type',
            items = texture_type_items,
            default = 'ShaderNodeTexImage')

    texcoord_type = EnumProperty(
            name = 'Texture Coordinate Type',
            items = texcoord_type_items,
            default = 'UV',
            update=update_texcoord_type)

    # Node names
    source = StringProperty(default='')
    #linear = StringProperty(default='')
    solid_alpha = StringProperty(default='')
    #uv = StringProperty(default='')

    texcoord = StringProperty(default='')
    uv_map = StringProperty(default='')

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

    #is_alpha_channel = BoolProperty(default=False)
    input_index = IntProperty(default=-1)
    output_index = IntProperty(default=-1)
    input_alpha_index = IntProperty(default=-1)
    output_alpha_index = IntProperty(default=-1)

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
    active_texture_index = IntProperty(default=0, update=update_texture_index)

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
    show_texture_properties = BoolProperty(default=False)
    show_end_modifiers = BoolProperty(default=False)
    show_vector_properties = BoolProperty(default=False)
    show_mask_properties = BoolProperty(default=False)

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
    # Custom Icon
    global custom_icons
    custom_icons = bpy.utils.previews.new()
    custom_icons.load('asterisk', get_addon_filepath() + 'asterisk_icon.png', 'IMAGE')

    # Register classes
    bpy.utils.register_module(__name__)

    # TG Props
    bpy.types.ShaderNodeTree.tg = PointerProperty(type=TextureGroup)
    bpy.types.Material.tg = PointerProperty(type=MaterialTGProps)

    # UI panel
    bpy.types.NODE_MT_add.append(menu_func)

    # Load libraries
    bpy.app.handlers.load_post.append(load_libraries)

def unregister():
    # Custom Icon
    global custom_icons
    bpy.utils.previews.remove(custom_icons)

    # Remove UI panel
    bpy.types.NODE_MT_add.remove(menu_func)

    # Remove classes
    bpy.utils.unregister_module(__name__)

    # Remove libraries
    bpy.app.handlers.load_post.remove(load_libraries)

if __name__ == "__main__":
    register()
