import bpy
from mathutils import *

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

            color_ramp_alpha_mix = nodes.get(m.color_ramp_alpha_mix)
            if color_ramp_alpha_mix.location != new_loc: color_ramp_alpha_mix.location = new_loc

            new_loc.y -= 180.0

            color_ramp = nodes.get(m.color_ramp)
            if color_ramp.location != new_loc: color_ramp.location = new_loc

            new_loc.y -= 220.0

            color_ramp_alpha_multiply = nodes.get(m.color_ramp_alpha_multiply)
            if color_ramp_alpha_multiply.location != new_loc: color_ramp_alpha_multiply.location = new_loc

            new_loc.y -= 180.0

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

        # Start solid alpha
        new_loc.y -= 100.0
        solid_alpha = nodes.get(channel.solid_alpha)
        if solid_alpha and solid_alpha.location != new_loc: solid_alpha.location = new_loc
        new_loc.y += 100.0

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

            alpha_passthrough = nodes.get(c.alpha_passthrough)
            if alpha_passthrough:
                new_loc.y -= 195.0
                new_loc.x += 29.0
                if alpha_passthrough.location != new_loc: alpha_passthrough.location = new_loc
                new_loc.y += 195.0
                new_loc.x -= 29.0

            new_loc.y -= dist_y
            new_loc.x += dist_x

        new_loc.x = ori_xx
        new_loc.y -= 75.0

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

            bump_base = nodes.get(c.bump_base)
            if bump_base:
                if bump_base.location != new_loc: bump_base.location = new_loc
                new_loc.y -= 180.0

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

        new_loc.y -= 35.0

        end_alpha_entry = nodes.get(channel.end_alpha_entry)
        if end_alpha_entry and end_alpha_entry.location != new_loc: end_alpha_entry.location = new_loc

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

