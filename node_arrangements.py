import bpy
from mathutils import *

INFO_PREFIX = '__ytl_info_'

def check_set_node_location(node, loc):
    if node:
        if node.location != loc:
            node.location = loc
        return True
    return False

def check_set_node_parent(child, parent):
    if child and child.parent != parent:
        child.parent = parent

def check_set_node_label(node, label):
    if node and node.label != label:
        node.label = label

def refresh_tl_channel_frame(ch, nodes):

    start_frame = nodes.get(ch.start_frame)
    if not start_frame:
        start_frame = nodes.new('NodeFrame')
        ch.start_frame = start_frame.name

    check_set_node_label(start_frame, ch.name + ' Start')

    end_frame = nodes.get(ch.end_frame)
    if not end_frame:
        end_frame = nodes.new('NodeFrame')
        ch.end_frame = end_frame.name

    check_set_node_label(end_frame, ch.name + ' End')

    return start_frame, end_frame

def rearrange_tl_frame_nodes(group_tree):
    tl = group_tree.tl
    nodes = group_tree.nodes

    # Channel loops
    for ch in tl.channels:

        start_frame, end_frame = refresh_tl_channel_frame(ch, nodes)

        start_linear = nodes.get(ch.start_linear)
        start_normal_filter = nodes.get(ch.start_normal_filter)
        start_alpha_entry = nodes.get(ch.start_alpha_entry)
        start_entry = nodes.get(ch.start_entry)

        end_linear = nodes.get(ch.end_linear)
        end_alpha_entry = nodes.get(ch.end_alpha_entry)
        end_entry = nodes.get(ch.end_entry)

        start_rgb = nodes.get(ch.start_rgb)
        start_alpha = nodes.get(ch.start_alpha)
        end_rgb = nodes.get(ch.end_rgb)
        end_alpha = nodes.get(ch.end_alpha)

        # Start Frame
        check_set_node_parent(start_entry, start_frame)
        check_set_node_parent(start_linear, start_frame)
        check_set_node_parent(start_alpha_entry, start_frame)
        check_set_node_parent(start_normal_filter, start_frame)

        # End Frame
        check_set_node_parent(end_entry, end_frame)
        check_set_node_parent(end_alpha_entry, end_frame)
        check_set_node_parent(start_rgb, end_frame)
        check_set_node_parent(start_alpha, end_frame)
        check_set_node_parent(end_rgb, end_frame)
        check_set_node_parent(end_alpha, end_frame)
        check_set_node_parent(end_linear, end_frame)

def create_info_nodes(group_tree, tex=None):
    tl = group_tree.tl
    if tex:
        nodes = tex.tree.nodes
    else: nodes = group_tree.nodes

    # Delete previous info nodes
    for node in nodes:
        if node.name.startswith(INFO_PREFIX):
            nodes.remove(node)

    # Create info nodes
    infos = []

    info = nodes.new('NodeFrame')
    if tex:
        info.label = 'Part of Texture Layers Node addon version ' + tl.version
    else: info.label = 'Created using Texture Layers Node addon version ' + tl.version
    info.use_custom_color = True
    info.color = (1.0, 1.0, 1.0)
    if tex:
        info.width = 480.0
    else: info.width = 540.0
    info.height = 30.0
    infos.append(info)

    info = nodes.new('NodeFrame')
    info.label = 'Support this addon development on patreon.com/ucupumar'
    info.use_custom_color = True
    info.color = (1.0, 1.0, 1.0)
    info.width = 590.0
    info.height = 30.0
    infos.append(info)

    info = nodes.new('NodeFrame')
    info.label = 'WARNING: Do NOT edit this group manually!'
    info.use_custom_color = True
    info.color = (1.0, 0.5, 0.5)
    info.width = 450.0
    info.height = 30.0
    infos.append(info)

    info = nodes.new('NodeFrame')
    info.label = 'Please use this panel: Node Editor > Tools > Texture Layers'
    info.use_custom_color = True
    info.color = (1.0, 0.5, 0.5)
    info.width = 580.0
    info.height = 30.0
    infos.append(info)

    loc = Vector((0, 50))

    for info in reversed(infos):
        info.name = INFO_PREFIX + info.name

        loc.y += 40
        info.location = loc

#def arrange_modifier_nodes(nodes, parent, loc, original_x):
def arrange_modifier_nodes(nodes, parent, loc):

    ori_y = loc.y

    # Modifier loops
    for m in reversed(parent.modifiers):

        start_rgb = nodes.get(m.start_rgb)
        start_alpha = nodes.get(m.start_alpha)

        loc.y -= 35
        if start_rgb.location != loc: start_rgb.location = loc

        loc.y -= 35
        if start_alpha.location != loc: start_alpha.location = loc

        loc.y = ori_y
        loc.x += 20

        #m_end_rgb = nodes.get(m.end_rgb)
        #m_end_alpha = nodes.get(m.end_alpha)

        #loc.x += 35.0
        #if m_end_rgb.location != loc: m_end_rgb.location = loc
        #loc.x += 65.0
        #if m_end_alpha.location != loc: m_end_alpha.location = loc

        #loc.x = original_x
        #loc.y -= 20.0

        if m.type == 'INVERT':
            invert = nodes.get(m.invert)
            if invert.location != loc: invert.location = loc

            loc.x += 165.0

        elif m.type == 'RGB_TO_INTENSITY':
            rgb2i = nodes.get(m.rgb2i)
            if rgb2i.location != loc: rgb2i.location = loc

            loc.x += 165.0

        elif m.type == 'COLOR_RAMP':

            color_ramp_alpha_multiply = nodes.get(m.color_ramp_alpha_multiply)
            if color_ramp_alpha_multiply.location != loc: color_ramp_alpha_multiply.location = loc

            loc.x += 165.0

            color_ramp = nodes.get(m.color_ramp)
            if color_ramp.location != loc: color_ramp.location = loc

            loc.x += 265.0

            color_ramp_mix_rgb = nodes.get(m.color_ramp_mix_rgb)
            if color_ramp_mix_rgb.location != loc: color_ramp_mix_rgb.location = loc

            loc.x += 165.0

            color_ramp_mix_alpha = nodes.get(m.color_ramp_mix_alpha)
            if color_ramp_mix_alpha.location != loc: color_ramp_mix_alpha.location = loc

            loc.x += 165.0

        elif m.type == 'RGB_CURVE':

            rgb_curve = nodes.get(m.rgb_curve)
            if rgb_curve.location != loc: rgb_curve.location = loc

            loc.x += 260.0

        elif m.type == 'HUE_SATURATION':

            huesat = nodes.get(m.huesat)
            if huesat.location != loc: huesat.location = loc

            loc.x += 175.0

        elif m.type == 'BRIGHT_CONTRAST':

            brightcon = nodes.get(m.brightcon)
            if brightcon.location != loc: brightcon.location = loc

            loc.x += 165.0

        end_rgb = nodes.get(m.end_rgb)
        end_alpha = nodes.get(m.end_alpha)

        loc.y -= 35
        if end_rgb.location != loc: end_rgb.location = loc
        loc.y -= 35
        if end_alpha.location != loc: end_alpha.location = loc

        loc.y = ori_y
        loc.x += 100

    return loc

def rearrange_tex_nodes(tex):
    tree = tex.tree
    nodes = tree.nodes

    start = nodes.get(tex.start)
    end = nodes.get(tex.end)
    source = nodes.get(tex.source)
    solid_alpha = nodes.get(tex.solid_alpha)
    texcoord = nodes.get(tex.texcoord)
    uv_map = nodes.get(tex.uv_map)
    tangent = nodes.get(tex.tangent)
    bitangent = nodes.get(tex.bitangent)
    geometry = nodes.get(tex.geometry)

    dist_y = 200
    mid_y = (len(tex.channels)-1) / 2 * -dist_y

    loc = Vector((0, mid_y))
    if source:
        if source.location != loc: source.location = loc
        loc.y -= 260

    if solid_alpha:
        if solid_alpha.location != loc: solid_alpha.location = loc
        loc.y -= 90

    if uv_map:
        if uv_map.location != loc: uv_map.location = loc
        loc.y -= 115

    if texcoord:
        if texcoord.location != loc: texcoord.location = loc
        loc.y -= 240

    if bitangent:
        if bitangent.location != loc: bitangent.location = loc
        loc.y -= 160

    if tangent:
        if tangent.location != loc: tangent.location = loc
        loc.y -= 160

    if geometry:
        if geometry.location != loc: geometry.location = loc
        #loc.y += 160

    start_x = 200
    loc = Vector((start_x, 0))

    farthest_x = 0

    for i, ch in enumerate(tex.channels):

        start_rgb = nodes.get(ch.start_rgb)
        end_rgb = nodes.get(ch.end_rgb)
        start_alpha = nodes.get(ch.start_alpha)
        end_alpha = nodes.get(ch.end_alpha)

        bump_base = nodes.get(ch.bump_base)
        bump = nodes.get(ch.bump)
        normal = nodes.get(ch.normal)
        normal_flip = nodes.get(ch.normal_flip)

        loc.x = start_x
        bookmark_y = loc.y

        if start_rgb:
            loc.y -= 35
            if start_rgb.location != loc: start_rgb.location = loc

        if start_alpha:
            loc.y -= 35
            if start_alpha.location != loc: start_alpha.location = loc

        loc.x = start_x + 50
        loc.y = bookmark_y

        # Modifier loop
        loc = arrange_modifier_nodes(nodes, ch, loc)

        if end_rgb:
            loc.y -= 35
            if end_rgb.location != loc: end_rgb.location = loc

        if end_alpha:
            loc.y -= 35
            if end_alpha.location != loc: end_alpha.location = loc

        loc.x += 50
        loc.y = bookmark_y

        if bump_base:
            if bump_base.location != loc: bump_base.location = loc
            loc.x += 200.0

        if bump:
            if bump.location != loc: bump.location = loc
            loc.x += 200.0

        if normal:
            if normal.location != loc: normal.location = loc
            loc.x += 200.0

        if normal_flip:
            if normal_flip.location != loc: normal_flip.location = loc
            loc.x += 200.0

        if loc.x > farthest_x: farthest_x = loc.x

        if any([m for m in ch.modifiers if m.type == 'RGB_CURVE']):
            loc.y -= 365
        elif any([m for m in ch.modifiers if m.type == 'INVERT']):
            loc.y -= 305
        elif len(ch.modifiers)>0:
            loc.y -= 240
        else:
            loc.y -= dist_y

    # Group input
    loc.y = len(tex.channels) * -dist_y

    #loc = Vector((farthest_x+400, 0))
    loc.y = 0
    loc.x = farthest_x

    for i, ch in enumerate(tex.channels):
        intensity = nodes.get(ch.intensity)

        loc.y = i*-dist_y

        if intensity:
            if intensity.location != loc: intensity.location = loc

    loc.y = mid_y
    loc.x += 200
    if start and start.location != loc: start.location = loc
    loc.x += 200
    loc.y = 0

    for i, ch in enumerate(tex.channels):
        blend = nodes.get(ch.blend)

        loc.y = i*-dist_y

        if blend:
            if blend.location != loc: blend.location = loc

    loc.x += 200
    loc.y = mid_y
    if end and end.location != loc: end.location = loc

def rearrange_tl_nodes(group_tree):

    tl = group_tree.tl
    nodes = group_tree.nodes

    start_node = nodes.get(tl.start)
    solid_alpha = nodes.get(tl.solid_alpha)
    end_node = nodes.get(tl.end)

    dist_y = 185
    dist_x = 200
    loc = Vector((0, 0))

    # Rearrange start nodes
    check_set_node_location(start_node, loc)

    loc.x += 200
    ori_x = loc.x

    # Start nodes
    for i, channel in enumerate(tl.channels):

        start_linear = nodes.get(channel.start_linear)
        start_normal_filter = nodes.get(channel.start_normal_filter)
        start_entry = nodes.get(channel.start_entry)
        start_alpha_entry = nodes.get(channel.start_alpha_entry)

        bookmark_y = loc.y
        loc.x = ori_x

        # Start nodes
        check_set_node_location(start_linear, loc)
        check_set_node_location(start_normal_filter, loc)

        # Start entry
        loc.x += 200
        loc.y -= 35
        check_set_node_location(start_entry, loc)

        loc.y -= 35
        check_set_node_location(start_alpha_entry, loc)

        loc.y = bookmark_y

        if channel.type == 'RGB':
            loc.y -= 165
        elif channel.type == 'VALUE':
            loc.y -= 220
        elif channel.type == 'NORMAL':
            loc.y -= 175

    # Rearrange solid alpha node
    if len(tl.channels) > 0:
        loc.y += 30
    loc.x = ori_x
    check_set_node_location(solid_alpha, loc)

    #if len(tl.textures) == 0 and len(tl.channels) == 0:
    #    loc.x = ori_x + 200.0
    if len(tl.textures) == 0:
        loc.x = ori_x + 300.0
    else: 
        loc.x = ori_x + 280.0
    ori_x = loc.x
    loc.y = 0.0

    # Texture nodes
    for i, t in enumerate(reversed(tl.textures)):

        tnode = nodes.get(t.group_node)
        check_set_node_location(tnode, loc)

        if i == len(tl.textures)-1:
            loc.x += 220
        else: loc.x += 190

    ori_x = loc.x
    farthest_x = loc.x

    # End nodes
    for i, channel in enumerate(tl.channels):

        end_entry = nodes.get(channel.end_entry)
        end_alpha_entry = nodes.get(channel.end_alpha_entry)
        start_rgb = nodes.get(channel.start_rgb)
        start_alpha = nodes.get(channel.start_alpha)
        end_rgb = nodes.get(channel.end_rgb)
        end_alpha = nodes.get(channel.end_alpha)
        end_linear = nodes.get(channel.end_linear)

        loc.x = ori_x
        bookmark_y = loc.y
        loc.y -= 35.0

        check_set_node_location(end_entry, loc)

        loc.y -= 35.0
        check_set_node_location(end_alpha_entry, loc)

        loc.x += 120.0
        loc.y = bookmark_y
        loc.y -= 35

        check_set_node_location(start_rgb, loc)

        loc.y -= 35
        check_set_node_location(start_alpha, loc)

        loc.x += 70
        loc.y = bookmark_y

        loc = arrange_modifier_nodes(nodes, channel, loc)
        loc.y -= 35

        check_set_node_location(end_rgb, loc)

        loc.y -= 35
        check_set_node_location(end_alpha, loc)

        loc.x += 100
        loc.y = bookmark_y

        if check_set_node_location(end_linear, loc):
            loc.x += 200

        if loc.x > farthest_x: farthest_x = loc.x

        if any([m for m in channel.modifiers if m.type == 'RGB_CURVE']):
            loc.y -= 390
        elif any([m for m in channel.modifiers if m.type == 'INVERT']):
            loc.y -= 330
        elif any([m for m in channel.modifiers if m.type == 'COLOR_RAMP']):
            loc.y -= 315
        elif any([m for m in channel.modifiers if m.type == 'RGB_TO_INTENSITY']):
            loc.y -= 270
        elif any([m for m in channel.modifiers if m.type == 'HUE_SATURATION']):
            loc.y -= 265
        elif any([m for m in channel.modifiers if m.type == 'BRIGHT_CONTRAST']):
            loc.y -= 220
        #elif len(channel.modifiers)>0:
        #    loc.y -= 270
        elif channel.type == 'RGB':
            loc.y -= 165
        elif channel.type == 'VALUE':
            loc.y -= 220
        elif channel.type == 'NORMAL':
            loc.y -= 155

        if i+1 < len(tl.channels):
            next_ch = tl.channels[i+1]
            if next_ch.type == 'NORMAL':
                loc.y += 25
            if len(next_ch.modifiers) > 0:
                loc.y -= 35

    loc.x = farthest_x
    loc.y = 0.0

    # End node
    check_set_node_location(end_node, loc)

    # Rearrange frames
    rearrange_tl_frame_nodes(group_tree)

