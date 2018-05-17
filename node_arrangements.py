import bpy
from mathutils import *

#def arrange_modifier_nodes(nodes, parent, loc, original_x):
def arrange_modifier_nodes(nodes, parent, loc):

    ori_y = loc.y

    # Modifier loops
    for m in reversed(parent.modifiers):

        start_rgb = nodes.get(m.start_rgb)
        start_alpha = nodes.get(m.start_alpha)

        loc.y -= 50
        if start_rgb.location != loc: start_rgb.location = loc

        loc.y -= 50
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

        loc.y -= 50
        if end_rgb.location != loc: end_rgb.location = loc
        loc.y -= 50
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
        #loc.y = i*-dist_y
        bookmark_y = loc.y

        if start_rgb:
            loc.y -= 50
            if start_rgb.location != loc: start_rgb.location = loc

        if start_alpha:
            loc.y -= 50
            if start_alpha.location != loc: start_alpha.location = loc

        loc.x = start_x + 50
        #loc.y = i*-dist_y
        loc.y = bookmark_y

        # Modifier loop
        loc = arrange_modifier_nodes(nodes, ch, loc)

        if end_rgb:
            loc.y -= 50
            if end_rgb.location != loc: end_rgb.location = loc

        if end_alpha:
            loc.y -= 50
            if end_alpha.location != loc: end_alpha.location = loc

        loc.x += 50
        #loc.y = i*-dist_y
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

    nodes = group_tree.nodes

    # Rearrange warning node
    warning2 = nodes.get(group_tree.tl.warning2)
    loc = Vector((0, 70))
    if warning2 and warning2.location != loc: warning2.location = loc

    # Rearrange warning node
    warning1 = nodes.get(group_tree.tl.warning1)
    loc = Vector((0, 110))
    if warning1 and warning1.location != loc: warning1.location = loc

    # Rearrange version info node
    support_info = nodes.get(group_tree.tl.support_info)
    loc = Vector((0, 150))
    if support_info and support_info.location != loc: support_info.location = loc

    # Rearrange version info node
    version_info = nodes.get(group_tree.tl.version_info)
    loc = Vector((0, 190))
    if version_info and version_info.location != loc: version_info.location = loc

    # Rearrange start nodes
    start_node = nodes.get(group_tree.tl.start)
    loc = Vector((0, 0))
    if start_node.location != loc: start_node.location = loc

    new_loc = Vector((0, 0))

    #dist_y = 350.0
    dist_y = 185.0
    dist_x = 200.0

    # Start nodes
    for i, channel in enumerate(group_tree.tl.channels):
        new_loc.y = -dist_y * i

        # Start linear
        new_loc.x += 200.0
        if channel.start_linear != '':
            start_linear = nodes.get(channel.start_linear)
            if start_linear.location != new_loc: start_linear.location = new_loc
        elif channel.normal_filter != '':
            normal_filter = nodes.get(channel.normal_filter)
            if normal_filter.location != new_loc: normal_filter.location = new_loc

        if i == len(group_tree.tl.channels)-1:
            loc = Vector((new_loc.x, 0))
            loc.y = -dist_y * (i+1)

            # Rearrange solid alpha node
            solid_alpha = nodes.get(group_tree.tl.solid_alpha)
            if solid_alpha.location != loc: solid_alpha.location = loc

        # Start entry
        ori_y = new_loc.y
        new_loc.x += 200.0
        new_loc.y -= 35.0
        start_entry = nodes.get(channel.start_entry)
        if start_entry.location != new_loc: start_entry.location = new_loc

        new_loc.y -= 35.0

        start_alpha_entry = nodes.get(channel.start_alpha_entry)
        if start_alpha_entry and start_alpha_entry.location != new_loc: start_alpha_entry.location = new_loc

        new_loc.y = ori_y

        # Back to left
        if i < len(group_tree.tl.channels)-1:
            new_loc.x = 0.0

    new_loc.x += 70.0
    ori_x = new_loc.x
    new_loc.y = 0.0

    # Texture nodes
    for i, t in enumerate(reversed(group_tree.tl.textures)):

        tnode = nodes.get(t.node_group)

        if tnode.location != new_loc: tnode.location = new_loc

        new_loc.x += dist_x

    # End entry nodes
    for i, channel in enumerate(group_tree.tl.channels):
        new_loc.y = -dist_y * i

        #ori_y = new_loc.y
        new_loc.y -= 35.0

        # End entry
        end_entry = nodes.get(channel.end_entry)
        if end_entry.location != new_loc: end_entry.location = new_loc

        new_loc.y -= 35.0

        end_alpha_entry = nodes.get(channel.end_alpha_entry)
        if end_alpha_entry and end_alpha_entry.location != new_loc: end_alpha_entry.location = new_loc

    new_loc.y = 0.0
    new_loc.x += 120.0
    ori_xxx = new_loc.x

    farthest_x = 0

    # End modifiers
    for i, channel in enumerate(group_tree.tl.channels):
        bookmark_y = new_loc.y
        new_loc.x = ori_xxx

        new_loc.y -= 50

        start_rgb = nodes.get(channel.start_rgb)
        if start_rgb and start_rgb.location != new_loc: start_rgb.location = new_loc

        new_loc.y -= 50

        start_alpha = nodes.get(channel.start_alpha)
        if start_alpha and start_alpha.location != new_loc: start_alpha.location = new_loc

        new_loc.x += 50
        new_loc.y = bookmark_y

        new_loc = arrange_modifier_nodes(nodes, channel, new_loc)
        new_loc.y -= 50

        end_rgb = nodes.get(channel.end_rgb)
        if end_rgb and end_rgb.location != new_loc: end_rgb.location = new_loc

        new_loc.y -= 50

        end_alpha = nodes.get(channel.end_alpha)
        if end_alpha and end_alpha.location != new_loc: end_alpha.location = new_loc

        new_loc.x += 100
        new_loc.y = bookmark_y

        if new_loc.x > farthest_x: farthest_x = new_loc.x

        if any([m for m in channel.modifiers if m.type == 'RGB_CURVE']):
            new_loc.y -= 365
        elif any([m for m in channel.modifiers if m.type == 'INVERT']):
            new_loc.y -= 305
        elif len(channel.modifiers)>0:
            new_loc.y -= 240
        else:
            new_loc.y -= dist_y

    new_loc.y = 0.0
    new_loc.x = farthest_x
        
    # End linear
    for i, channel in enumerate(group_tree.tl.channels):
        new_loc.y = -dist_y * i
        if channel.end_linear != '':
            end_linear = nodes.get(channel.end_linear)
            if end_linear.location != new_loc: end_linear.location = new_loc

    new_loc.x += 200.0
    new_loc.y = 0.0

    # End node
    end_node = nodes.get(group_tree.tl.end)
    if end_node.location != new_loc: end_node.location = new_loc

