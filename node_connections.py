import bpy
from .common import *

def create_link(tree, out, inp):
    if not any(l for l in out.links if l.to_socket == inp):
        tree.links.new(out, inp)
        #print(out, 'is connected to', inp)
    if inp.node: return inp.node.outputs
    return None

def break_link(tree, out, inp):
    for link in out.links:
        if link.to_socket == inp:
            tree.links.remove(link)
            return True
    return False

def reconnect_modifier_nodes(tree, mod, start_rgb, start_alpha):

    rgb = start_rgb
    alpha = start_alpha

    if mod.type == 'INVERT':

        invert = tree.nodes.get(mod.invert)
        create_link(tree, start_rgb, invert.inputs[0])
        create_link(tree, start_alpha, invert.inputs[1])

        rgb = invert.outputs[0]
        alpha = invert.outputs[1]

    elif mod.type == 'RGB_TO_INTENSITY':

        rgb2i = tree.nodes.get(mod.rgb2i)
        create_link(tree, start_rgb, rgb2i.inputs[0])
        create_link(tree, start_alpha, rgb2i.inputs[1])

        rgb = rgb2i.outputs[0]
        alpha = rgb2i.outputs[1]

    elif mod.type == 'INTENSITY_TO_RGB':

        i2rgb = tree.nodes.get(mod.i2rgb)
        create_link(tree, start_rgb, i2rgb.inputs[0])
        create_link(tree, start_alpha, i2rgb.inputs[1])

        rgb = i2rgb.outputs[0]
        alpha = i2rgb.outputs[1]

    elif mod.type == 'OVERRIDE_COLOR':

        oc = tree.nodes.get(mod.oc)
        create_link(tree, start_rgb, oc.inputs[0])
        create_link(tree, start_alpha, oc.inputs[1])

        rgb = oc.outputs[0]
        alpha = oc.outputs[1]

    elif mod.type == 'COLOR_RAMP':

        color_ramp_alpha_multiply = tree.nodes.get(mod.color_ramp_alpha_multiply)
        color_ramp = tree.nodes.get(mod.color_ramp)
        color_ramp_linear = tree.nodes.get(mod.color_ramp_linear)
        color_ramp_mix_alpha = tree.nodes.get(mod.color_ramp_mix_alpha)
        color_ramp_mix_rgb = tree.nodes.get(mod.color_ramp_mix_rgb)

        create_link(tree, start_rgb, color_ramp_alpha_multiply.inputs[1])
        create_link(tree, start_alpha, color_ramp_alpha_multiply.inputs[2])
        create_link(tree, color_ramp_alpha_multiply.outputs[0], color_ramp.inputs[0])
        create_link(tree, start_rgb, color_ramp_mix_rgb.inputs[1])
        create_link(tree, color_ramp.outputs[0], color_ramp_linear.inputs[0])
        create_link(tree, color_ramp_linear.outputs[0], color_ramp_mix_rgb.inputs[2])

        create_link(tree, start_alpha, color_ramp_mix_alpha.inputs[1])
        create_link(tree, color_ramp.outputs[1], color_ramp_mix_alpha.inputs[2])

        rgb = color_ramp_mix_rgb.outputs[0]
        alpha = color_ramp_mix_alpha.outputs[0]

    elif mod.type == 'RGB_CURVE':

        rgb_curve = tree.nodes.get(mod.rgb_curve)
        create_link(tree, start_rgb, rgb_curve.inputs[1])
        rgb = rgb_curve.outputs[0]

    elif mod.type == 'HUE_SATURATION':

        huesat = tree.nodes.get(mod.huesat)
        create_link(tree, start_rgb, huesat.inputs[4])
        rgb = huesat.outputs[0]

    elif mod.type == 'BRIGHT_CONTRAST':

        brightcon = tree.nodes.get(mod.brightcon)
        create_link(tree, start_rgb, brightcon.inputs[0])
        rgb = brightcon.outputs[0]

    elif mod.type == 'MULTIPLIER':

        multiplier = tree.nodes.get(mod.multiplier)
        create_link(tree, start_rgb, multiplier.inputs[0])
        create_link(tree, start_alpha, multiplier.inputs[1])

        rgb = multiplier.outputs[0]
        alpha = multiplier.outputs[1]

    return rgb, alpha

def reconnect_all_modifier_nodes(tree, parent, start_rgb, start_alpha, mod_group=None):

    rgb = start_rgb
    alpha = start_alpha

    if mod_group:
        # Connect modifier group node
        create_link(tree, rgb, mod_group.inputs[0])
        create_link(tree, alpha, mod_group.inputs[1])

        # Get nodes inside modifier group tree and repoint it
        mod_tree = mod_group.node_tree
        start = mod_tree.nodes.get(MOD_TREE_START)
        rgb = start.outputs[0]
        alpha = start.outputs[1]
    else:
        mod_tree = tree

    # Connect all the nodes
    for mod in reversed(parent.modifiers):
        rgb, alpha = reconnect_modifier_nodes(mod_tree, mod, rgb, alpha)

    if mod_group:

        # Connect to end node
        end = mod_tree.nodes.get(MOD_TREE_END)
        create_link(mod_tree, rgb, end.inputs[0])
        create_link(mod_tree, alpha, end.inputs[1])

        # Repoint rgb and alpha to mod group
        rgb = mod_group.outputs[0]
        alpha = mod_group.outputs[1]

    return rgb, alpha

def reconnect_tl_nodes(tree, ch_idx=-1, mod_reconnect=False):
    tl = tree.tl
    nodes = tree.nodes

    start = nodes.get(tl.start)
    end = nodes.get(tl.end)
    solid_alpha = nodes.get(tl.solid_alpha)

    num_tex = len(tl.textures)

    for i, ch in enumerate(tl.channels):
        if ch_idx != -1 and i != ch_idx: continue

        start_linear = nodes.get(ch.start_linear)
        end_linear = nodes.get(ch.end_linear)
        start_normal_filter = nodes.get(ch.start_normal_filter)

        rgb = start.outputs[ch.io_index]
        if ch.alpha and ch.type == 'RGB':
            alpha = start.outputs[ch.io_index+1]
        else: alpha = solid_alpha.outputs[0]
        
        if start_linear:
            create_link(tree, start.outputs[ch.io_index], start_linear.inputs[0])
            rgb = start_linear.outputs[0]
        elif start_normal_filter:
            create_link(tree, start.outputs[ch.io_index], start_normal_filter.inputs[0])
            rgb = start_normal_filter.outputs[0]

        for j, tex in reversed(list(enumerate(tl.textures))):
            node = nodes.get(tex.group_node)
            create_link(tree, rgb, node.inputs[ch.io_index])
            rgb = node.outputs[ch.io_index]
            if ch.type =='RGB' and ch.alpha:
                create_link(tree, alpha, node.inputs[ch.io_index+1])
                alpha = node.outputs[ch.io_index+1]

        if mod_reconnect:
            rgb, alpha = reconnect_all_modifier_nodes(tree, ch, rgb, alpha)

        if end_linear:
            create_link(tree, rgb, end_linear.inputs[0])
            rgb = end_linear.outputs[0]

        create_link(tree, rgb, end.inputs[ch.io_index])
        if ch.type == 'RGB' and ch.alpha:
            create_link(tree, alpha, end.inputs[ch.io_index+1])

def reconnect_source_internal_nodes(tex):
    tree = get_source_tree(tex)

    source = tree.nodes.get(tex.source)
    start = tree.nodes.get(SOURCE_TREE_START)
    solid = tree.nodes.get(SOURCE_SOLID_VALUE)
    end = tree.nodes.get(SOURCE_TREE_END)

    #if tex.type != 'VCOL':
    #    create_link(tree, start.outputs[0], source.inputs[0])
    create_link(tree, start.outputs[0], source.inputs[0])

    rgb = source.outputs[0]
    alpha = source.outputs[1]
    if tex.type not in {'IMAGE', 'VCOL'}:
        rgb_1 = source.outputs[1]
        alpha = solid.outputs[0]
        alpha_1 = solid.outputs[0]

        mod_group = tree.nodes.get(tex.mod_group)
        if mod_group:
            rgb, alpha = reconnect_all_modifier_nodes(tree, tex, rgb, alpha, mod_group)

        mod_group_1 = tree.nodes.get(tex.mod_group_1)
        if mod_group_1:
            rgb_1 = create_link(tree, rgb_1, mod_group_1.inputs[0])[0]
            alpha_1 = create_link(tree, alpha_1, mod_group_1.inputs[1])[1]

        create_link(tree, rgb_1, end.inputs[2])
        create_link(tree, alpha_1, end.inputs[3])

    if tex.type in {'IMAGE', 'VCOL'}:
        rgb, alpha = reconnect_all_modifier_nodes(tree, tex, rgb, alpha)

    create_link(tree, rgb, end.inputs[0])
    create_link(tree, alpha, end.inputs[1])

def reconnect_mask_internal_nodes(mask):

    tree = get_mask_tree(mask)

    source = tree.nodes.get(mask.source)
    start = tree.nodes.get(MASK_TREE_START)
    end = tree.nodes.get(MASK_TREE_END)

    if mask.type != 'VCOL':
        create_link(tree, start.outputs[0], source.inputs[0])

    create_link(tree, source.outputs[0], end.inputs[0])

def reconnect_tex_nodes(tex, ch_idx=-1, mod_reconnect = True):
    tl =  get_active_texture_layers_node().node_tree.tl

    tree = get_tree(tex)
    nodes = tree.nodes

    start = nodes.get(tex.start)
    end = nodes.get(tex.end)

    source_group = nodes.get(tex.source_group)

    #if tex.source_group != '':
    if source_group:
        source = source_group
        reconnect_source_internal_nodes(tex)
    else: source = nodes.get(tex.source)

    # Direction sources
    source_n = nodes.get(tex.source_n)
    source_s = nodes.get(tex.source_s)
    source_e = nodes.get(tex.source_e)
    source_w = nodes.get(tex.source_w)

    #uv_map = nodes.get(tex.uv_map)
    uv_attr = nodes.get(tex.uv_attr)
    uv_neighbor = nodes.get(tex.uv_neighbor)

    texcoord = nodes.get(tex.texcoord)
    solid_alpha = nodes.get(tex.solid_alpha)
    tangent = nodes.get(tex.tangent)
    bitangent = nodes.get(tex.bitangent)
    geometry = nodes.get(tex.geometry)

    # Texcoord
    if tex.type != 'VCOL':
        if tex.texcoord_type == 'UV':
            vector = uv_attr.outputs[1]
        else: vector = texcoord.outputs[tex.texcoord_type]

        create_link(tree, vector, source.inputs[0])

        if uv_neighbor: 
            create_link(tree, vector, uv_neighbor.inputs[0])

            if 'Tangent' in uv_neighbor.inputs:
                create_link(tree, tangent.outputs[0], uv_neighbor.inputs['Tangent'])
            if 'Bitangent' in uv_neighbor.inputs:
                create_link(tree, bitangent.outputs[0], uv_neighbor.inputs['Bitangent'])

            if source_n: create_link(tree, uv_neighbor.outputs['n'], source_n.inputs[0])
            if source_s: create_link(tree, uv_neighbor.outputs['s'], source_s.inputs[0])
            if source_e: create_link(tree, uv_neighbor.outputs['e'], source_e.inputs[0])
            if source_w: create_link(tree, uv_neighbor.outputs['w'], source_w.inputs[0])

    # RGB
    start_rgb = source.outputs[0]
    start_rgb_1 = source.outputs[1]

    # Alpha
    if tex.type == 'IMAGE':
        start_alpha = source.outputs[1]
    else: start_alpha = solid_alpha.outputs[0]
    start_alpha_1 = solid_alpha.outputs[0]

    if source_group and tex.type not in {'IMAGE', 'VCOL'}:
        start_rgb_1 = source_group.outputs[2]
        start_alpha_1 = source_group.outputs[3]
    else:
        # Layer source modifier
        mod_group = nodes.get(tex.mod_group)
        start_rgb, start_alpha = reconnect_all_modifier_nodes(
                tree, tex, start_rgb, start_alpha, mod_group)

        if tex.type not in {'IMAGE', 'VCOL'}:
            mod_group_1 = nodes.get(tex.mod_group_1)
            start_rgb_1, start_alpha_1 = reconnect_all_modifier_nodes(
                    tree, tex, source.outputs[1], solid_alpha.outputs[0], mod_group_1)

    # UV neighbor vertex color
    if tex.type == 'VCOL' and uv_neighbor:
        create_link(tree, start_rgb, uv_neighbor.inputs[0])
        create_link(tree, tangent.outputs[0], uv_neighbor.inputs['Tangent'])
        create_link(tree, bitangent.outputs[0], uv_neighbor.inputs['Bitangent'])

    # Get bump channel
    bump_ch = None
    flip_bump = False
    for i, c in enumerate(tex.channels):
        if tl.channels[i].type == 'NORMAL' and c.enable_mask_bump and c.enable:
            bump_ch = c
            if bump_ch.mask_bump_flip:
                flip_bump = True
            break

    # Layer Masks
    for mask in tex.masks:

        # Mask source
        if mask.group_node != '':
            mask_source = nodes.get(mask.group_node)
            reconnect_mask_internal_nodes(mask)
        else:
            mask_source = nodes.get(mask.source)

        # Mask texcoord
        mask_uv_map = nodes.get(mask.uv_map)
        if mask.type != 'VCOL':
            if mask.texcoord_type == 'UV':
                create_link(tree, mask_uv_map.outputs[0], mask_source.inputs[0])
            else: create_link(tree, texcoord.outputs[mask.texcoord_type], mask_source.inputs[0])

        # Mask uv neighbor
        mask_uv_neighbor = nodes.get(mask.uv_neighbor)
        if mask_uv_neighbor:

            if mask.type == 'VCOL':
                create_link(tree, mask_source.outputs[0], mask_uv_neighbor.inputs[0])
            else:
                if mask.texcoord_type == 'UV':
                    create_link(tree, mask_uv_map.outputs[0], mask_uv_neighbor.inputs[0])
                else: create_link(tree, texcoord.outputs[mask.texcoord_type], mask_uv_neighbor.inputs[0])

                # Mask source directions
                mask_source_n = nodes.get(mask.source_n)
                mask_source_s = nodes.get(mask.source_s)
                mask_source_e = nodes.get(mask.source_e)
                mask_source_w = nodes.get(mask.source_w)

                create_link(tree, mask_uv_neighbor.outputs['n'], mask_source_n.inputs[0])
                create_link(tree, mask_uv_neighbor.outputs['s'], mask_source_s.inputs[0])
                create_link(tree, mask_uv_neighbor.outputs['e'], mask_source_e.inputs[0])
                create_link(tree, mask_uv_neighbor.outputs['w'], mask_source_w.inputs[0])

            # Mask tangent
            mask_tangent = nodes.get(mask.tangent)
            mask_bitangent = nodes.get(mask.bitangent)

            if 'Tangent' in mask_uv_neighbor.inputs:
                create_link(tree, tangent.outputs[0], mask_uv_neighbor.inputs['Tangent'])
            if 'Bitangent' in mask_uv_neighbor.inputs:
                create_link(tree, bitangent.outputs[0], mask_uv_neighbor.inputs['Bitangent'])
            if 'Mask Tangent' in mask_uv_neighbor.inputs:
                create_link(tree, mask_tangent.outputs[0], mask_uv_neighbor.inputs['Mask Tangent'])
            if 'Mask Bitangent' in mask_uv_neighbor.inputs:
                create_link(tree, mask_bitangent.outputs[0], mask_uv_neighbor.inputs['Mask Bitangent'])

        # Mask channels
        for i, c in enumerate(mask.channels):
            root_ch = tl.channels[i]
            ch = tex.channels[i]

            mask_multiply = nodes.get(c.multiply)
            create_link(tree, mask_source.outputs[0], mask_multiply.inputs[1])

            # Direction multiplies
            if (root_ch.type == 'NORMAL' and ch.enable_mask_bump 
                    and ch.enable and ch.mask_bump_type in {'FINE_BUMP_MAP', 'CURVED_BUMP_MAP'}):
                mul_n = nodes.get(c.multiply_n)
                mul_s = nodes.get(c.multiply_s)
                mul_e = nodes.get(c.multiply_e)
                mul_w = nodes.get(c.multiply_w)

                if mask.type == 'VCOL':
                    create_link(tree, mask_uv_neighbor.outputs['n'], mul_n.inputs[1])
                    create_link(tree, mask_uv_neighbor.outputs['s'], mul_s.inputs[1])
                    create_link(tree, mask_uv_neighbor.outputs['e'], mul_e.inputs[1])
                    create_link(tree, mask_uv_neighbor.outputs['w'], mul_w.inputs[1])
                else:
                    create_link(tree, mask_source_n.outputs[0], mul_n.inputs[1])
                    create_link(tree, mask_source_s.outputs[0], mul_s.inputs[1])
                    create_link(tree, mask_source_e.outputs[0], mul_e.inputs[1])
                    create_link(tree, mask_source_w.outputs[0], mul_w.inputs[1])

    # Layer Channels
    for i, ch in enumerate(tex.channels):

        if ch_idx != -1 and i != ch_idx: continue
        root_ch = tl.channels[i]

        linear = nodes.get(ch.linear)

        neighbor_uv = nodes.get(ch.neighbor_uv)
        fine_bump = nodes.get(ch.fine_bump)

        mod_group = nodes.get(ch.mod_group)
        mod_n = nodes.get(ch.mod_n)
        mod_s = nodes.get(ch.mod_s)
        mod_e = nodes.get(ch.mod_e)
        mod_w = nodes.get(ch.mod_w)

        bump_base_n = nodes.get(ch.bump_base_n)
        bump_base_s = nodes.get(ch.bump_base_s)
        bump_base_e = nodes.get(ch.bump_base_e)
        bump_base_w = nodes.get(ch.bump_base_w)

        normal_flip = nodes.get(ch.normal_flip)

        mask_intensity_multiplier = nodes.get(ch.mask_intensity_multiplier)
        mask_total = nodes.get(ch.mask_total)

        intensity = nodes.get(ch.intensity)
        intensity_multiplier = nodes.get(ch.intensity_multiplier)
        blend = nodes.get(ch.blend)

        # Rgb and alpha start
        rgb = start_rgb
        alpha = start_alpha

        if tex.type not in {'IMAGE', 'VCOL'}:
            if ch.tex_input == 'ALPHA':
                rgb = start_rgb_1
                alpha = start_alpha_1

        if linear:
            create_link(tree, rgb, linear.inputs[0])
            rgb = linear.outputs[0]

        rgb, alpha = reconnect_all_modifier_nodes(tree, ch, rgb, alpha, mod_group)

        if root_ch.type == 'NORMAL':

            # Neighbor RGB and alpha
            alpha_n = start_alpha
            alpha_s = start_alpha
            alpha_e = start_alpha
            alpha_w = start_alpha

            rgb_n = start_rgb
            rgb_s = start_rgb
            rgb_e = start_rgb
            rgb_w = start_rgb

            # Get neighbor rgb
            if source_n:
                if tex.type not in {'IMAGE', 'VCOL'} and ch.tex_input == 'ALPHA':
                    source_index = 2
                else: source_index = 0

                rgb_n = source_n.outputs[source_index]
                rgb_s = source_s.outputs[source_index]
                rgb_e = source_e.outputs[source_index]
                rgb_w = source_w.outputs[source_index]

                alpha_n = source_n.outputs[source_index+1]
                alpha_s = source_s.outputs[source_index+1]
                alpha_e = source_e.outputs[source_index+1]
                alpha_w = source_w.outputs[source_index+1]

            if tex.type == 'VCOL' and uv_neighbor:
                rgb_n = uv_neighbor.outputs['n']
                rgb_s = uv_neighbor.outputs['s']
                rgb_e = uv_neighbor.outputs['e']
                rgb_w = uv_neighbor.outputs['w']

            if mod_n:
                rgb_n = create_link(tree, rgb_n, mod_n.inputs[0])[0]
                rgb_s = create_link(tree, rgb_s, mod_s.inputs[0])[0]
                rgb_e = create_link(tree, rgb_e, mod_e.inputs[0])[0]
                rgb_w = create_link(tree, rgb_w, mod_w.inputs[0])[0]

                alpha_n = create_link(tree, alpha_n, mod_n.inputs[1])[1]
                alpha_s = create_link(tree, alpha_s, mod_s.inputs[1])[1]
                alpha_e = create_link(tree, alpha_e, mod_e.inputs[1])[1]
                alpha_w = create_link(tree, alpha_w, mod_w.inputs[1])[1]

            # Connect tangent if overlay blend is used
            if ch.normal_blend == 'OVERLAY':
                create_link(tree, tangent.outputs[0], blend.inputs['Tangent'])
                create_link(tree, bitangent.outputs[0], blend.inputs['Bitangent'])

            if ch.normal_map_type == 'NORMAL_MAP':

                normal = nodes.get(ch.normal)
                create_link(tree, rgb, normal.inputs[1])

                rgb = normal.outputs[0]

            elif ch.normal_map_type == 'BUMP_MAP':

                bump = nodes.get(ch.bump)
                bump_base = nodes.get(ch.bump_base)
                create_link(tree, rgb, bump_base.inputs['Color2'])
                create_link(tree, alpha, bump_base.inputs['Fac'])

                create_link(tree, bump_base.outputs[0], bump.inputs[2])

                rgb = bump.outputs[0]

            elif ch.normal_map_type == 'FINE_BUMP_MAP':

                create_link(tree, alpha_n, bump_base_n.inputs['Fac'])
                create_link(tree, alpha_s, bump_base_s.inputs['Fac'])
                create_link(tree, alpha_e, bump_base_e.inputs['Fac'])
                create_link(tree, alpha_w, bump_base_w.inputs['Fac'])

                rgb_n = create_link(tree, rgb_n, bump_base_n.inputs['Color2'])[0]
                rgb_s = create_link(tree, rgb_s, bump_base_s.inputs['Color2'])[0]
                rgb_e = create_link(tree, rgb_e, bump_base_e.inputs['Color2'])[0]
                rgb_w = create_link(tree, rgb_w, bump_base_w.inputs['Color2'])[0]

                create_link(tree, rgb_n, fine_bump.inputs['n'])
                create_link(tree, rgb_s, fine_bump.inputs['s'])
                create_link(tree, rgb_e, fine_bump.inputs['e'])
                create_link(tree, rgb_w, fine_bump.inputs['w'])

                create_link(tree, tangent.outputs[0], fine_bump.inputs['Tangent'])
                create_link(tree, bitangent.outputs[0], fine_bump.inputs['Bitangent'])

                rgb = fine_bump.outputs[0]

        # Mask multiplies
        malpha = solid_alpha.outputs[0]
        for mask in tex.masks:
            mask_multiply = nodes.get(mask.channels[i].multiply)
            malpha = create_link(tree, malpha, mask_multiply.inputs[0])[0]

        if mask_intensity_multiplier:
            malpha = create_link(tree, malpha, mask_intensity_multiplier.inputs[0])[0]

        if mask_total:
            create_link(tree, malpha, mask_total.inputs[1])
            alpha = create_link(tree, alpha, mask_total.inputs[0])[0]

        # Mask multiply directions and alpha fine bump
        if root_ch.type == 'NORMAL' and ch.enable_mask_bump and ch.enable:

            if ch.mask_bump_mask_only:
                last_mask_multiply = nodes.get(tex.masks[-1].channels[i].multiply)
                alpha_input = last_mask_multiply.outputs[0]
            else: alpha_input = alpha
            #elif mask_total:
            #    alpha_input = mask_total.outputs[0]
            #else:
            #    alpha_input = alpha

            if ch.mask_bump_type == 'BUMP_MAP':
                mb_bump = nodes.get(ch.mb_bump)
                create_link(tree, alpha_input, mb_bump.inputs['Height'])

            elif ch.mask_bump_type in {'FINE_BUMP_MAP', 'CURVED_BUMP_MAP'}:

                if ch.mask_bump_mask_only:
                    malpha_n = solid_alpha.outputs[0]
                    malpha_s = solid_alpha.outputs[0]
                    malpha_e = solid_alpha.outputs[0]
                    malpha_w = solid_alpha.outputs[0]
                else:
                    malpha_n = alpha_n
                    malpha_s = alpha_s
                    malpha_e = alpha_e
                    malpha_w = alpha_w

                for mask in tex.masks:
                    c = mask.channels[i]
                    mul_n = nodes.get(c.multiply_n)
                    mul_s = nodes.get(c.multiply_s)
                    mul_e = nodes.get(c.multiply_e)
                    mul_w = nodes.get(c.multiply_w)

                    malpha_n = create_link(tree, malpha_n, mul_n.inputs[0])[0]
                    malpha_s = create_link(tree, malpha_s, mul_s.inputs[0])[0]
                    malpha_e = create_link(tree, malpha_e, mul_e.inputs[0])[0]
                    malpha_w = create_link(tree, malpha_w, mul_w.inputs[0])[0]

                if ch.mask_bump_type == 'FINE_BUMP_MAP':
                    mb_bump = nodes.get(ch.mb_fine_bump)
                else: 
                    mb_bump = nodes.get(ch.mb_curved_bump)
                    create_link(tree, alpha_input, mb_bump.inputs['Alpha'])

                create_link(tree, malpha_n, mb_bump.inputs['n'])
                create_link(tree, malpha_s, mb_bump.inputs['s'])
                create_link(tree, malpha_e, mb_bump.inputs['e'])
                create_link(tree, malpha_w, mb_bump.inputs['w'])

                create_link(tree, tangent.outputs[0], mb_bump.inputs['Tangent'])
                create_link(tree, bitangent.outputs[0], mb_bump.inputs['Bitangent'])

            mb_inverse = nodes.get(ch.mb_inverse)
            mb_intensity_multiplier = nodes.get(ch.mb_intensity_multiplier)
            mb_blend = nodes.get(ch.mb_blend)

            create_link(tree, alpha_input, mb_inverse.inputs[1])
            if mb_intensity_multiplier:
                create_link(tree, mb_inverse.outputs[0], mb_intensity_multiplier.inputs[0])
                create_link(tree, mb_intensity_multiplier.outputs[0], mb_blend.inputs[0])
            else:
                create_link(tree, mb_inverse.outputs[0], mb_blend.inputs[0])

            create_link(tree, rgb, mb_blend.inputs[1])
            create_link(tree, mb_bump.outputs[0], mb_blend.inputs[2])

            rgb = mb_blend.outputs[0]

        # Ramp
        if root_ch.type in {'RGB', 'VALUE'} and ch.enable_mask_ramp:
            mr_inverse = nodes.get(ch.mr_inverse)
            mr_ramp = nodes.get(ch.mr_ramp)
            mr_linear = nodes.get(ch.mr_linear)
            mr_intensity_multiplier = nodes.get(ch.mr_intensity_multiplier)
            mr_alpha = nodes.get(ch.mr_alpha)
            mr_intensity = nodes.get(ch.mr_intensity)
            mr_blend = nodes.get(ch.mr_blend)

            mr_flip_hack = nodes.get(ch.mr_flip_hack)
            mr_flip_blend = nodes.get(ch.mr_flip_blend)

            if bump_ch and bump_ch.mask_bump_mask_only:
                last_mask_multiply = nodes.get(tex.masks[-1].channels[i].multiply)
                multiply_input = last_mask_multiply.outputs[0]
            elif mask_total:
                multiply_input = mask_total.outputs[0]
            else:
                multiply_input = alpha

            if flip_bump:
                create_link(tree, multiply_input, mr_ramp.inputs[0])
            else:
                create_link(tree, multiply_input, mr_inverse.inputs[1])
                create_link(tree, mr_inverse.outputs[0], mr_ramp.inputs[0])

            create_link(tree, mr_ramp.outputs[0], mr_linear.inputs[0])
            create_link(tree, mr_linear.outputs[0], mr_blend.inputs[2])

            create_link(tree, mr_ramp.outputs[1], mr_alpha.inputs[1])

            if mr_intensity_multiplier:
                if flip_bump:
                    create_link(tree, multiply_input, mr_intensity_multiplier.inputs[0])
                else: create_link(tree, mr_inverse.outputs[0], mr_intensity_multiplier.inputs[0])
                create_link(tree, mr_intensity_multiplier.outputs[0], mr_alpha.inputs[0])
            else:
                create_link(tree, mr_inverse.outputs[0], mr_alpha.inputs[0])

            if flip_bump and bump_ch.mask_bump_mask_only:
                mr_alpha1 = nodes.get(ch.mr_alpha1)
                create_link(tree, mr_alpha.outputs[0], mr_alpha1.inputs[0])
                create_link(tree, alpha, mr_alpha1.inputs[1])
                create_link(tree, mr_alpha1.outputs[0], mr_intensity.inputs[0])
            else:
                create_link(tree, mr_alpha.outputs[0], mr_intensity.inputs[0])

            create_link(tree, mr_intensity.outputs[0], mr_blend.inputs[0])

            if flip_bump:
                create_link(tree, start.outputs[root_ch.io_index], mr_blend.inputs[1])

                if bump_ch.mask_bump_mask_only:
                    if mask_intensity_multiplier:
                        create_link(tree, mask_intensity_multiplier.outputs[0], mr_flip_hack.inputs[0])
                    else: create_link(tree, alpha, mr_flip_hack.inputs[0])
                else:
                    create_link(tree, intensity_multiplier.outputs[0], mr_flip_hack.inputs[0])

                create_link(tree, mr_flip_hack.outputs[0], mr_flip_blend.inputs[0])
                create_link(tree, mr_blend.outputs[0], mr_flip_blend.inputs[1])
                create_link(tree, start.outputs[root_ch.io_index], mr_flip_blend.inputs[2])
            else: 
                create_link(tree, rgb, mr_blend.inputs[1])
                rgb = mr_blend.outputs[0]

        if normal_flip:
            create_link(tree, rgb, normal_flip.inputs[0])
            create_link(tree, bitangent.outputs[0], normal_flip.inputs[1])
            rgb = normal_flip.outputs[0]

        if intensity_multiplier:
            create_link(tree, alpha, intensity_multiplier.inputs[0])
            alpha = intensity_multiplier.outputs[0]

        create_link(tree, alpha, intensity.inputs[0])
        alpha = intensity.outputs[0]

        create_link(tree, rgb, blend.inputs[2])

        if root_ch.type == 'RGB' and ch.blend_type == 'MIX' and root_ch.alpha:

            if ch.enable_mask_ramp and flip_bump:
                create_link(tree, mr_flip_blend.outputs[0], blend.inputs[0])
            else: create_link(tree, start.outputs[root_ch.io_index], blend.inputs[0])

            create_link(tree, start.outputs[root_ch.io_index+1], blend.inputs[1])
            create_link(tree, alpha, blend.inputs[3])

            create_link(tree, blend.outputs[1], end.inputs[root_ch.io_index+1])
        else:
            create_link(tree, alpha, blend.inputs[0])

            if ch.enable_mask_ramp and flip_bump:
                create_link(tree, mr_flip_blend.outputs[0], blend.inputs[1])
            else: create_link(tree, start.outputs[root_ch.io_index], blend.inputs[1])

        # Armory can't recognize mute node, so reconnect input to output directly
        #if tex.enable and ch.enable:
        #    create_link(tree, blend.outputs[0], end.inputs[root_ch.io_index])
        #else: create_link(tree, start.outputs[root_ch.io_index], end.inputs[root_ch.io_index])
        create_link(tree, blend.outputs[0], end.inputs[root_ch.io_index])

        if root_ch.type == 'RGB' and ch.blend_type != 'MIX' and root_ch.alpha:
            create_link(tree, start.outputs[root_ch.io_index+1], end.inputs[root_ch.io_index+1])

