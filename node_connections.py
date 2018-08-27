import bpy
from .common import *

def create_link(tree, out, inp):
    if not any(l for l in out.links if l.to_socket == inp):
        tree.links.new(out, inp)
        #print(out, 'is connected to', inp)
        return True
    return False

def reconnect_tl_tex_nodes(tree, ch_idx=-1):
    tl = tree.tl
    nodes = tree.nodes

    num_tex = len(tl.textures)

    if num_tex == 0:
        for ch in tl.channels:
            start_entry = nodes.get(ch.start_entry)
            end_entry = nodes.get(ch.end_entry)
            create_link(tree, start_entry.outputs[0], end_entry.inputs[0])
            if ch.type == 'RGB':
                start_alpha_entry = nodes.get(ch.start_alpha_entry)
                end_alpha_entry = nodes.get(ch.end_alpha_entry)
                create_link(tree, start_alpha_entry.outputs[0], end_alpha_entry.inputs[0])

    for i, tex in reversed(list(enumerate(tl.textures))):

        node = nodes.get(tex.group_node)
        below_node = None
        if i != num_tex-1:
            below_node = nodes.get(tl.textures[i+1].group_node)

        for j, ch in enumerate(tl.channels):
            if ch_idx != -1 and j != ch_idx: continue
            if not below_node:
                start_entry = nodes.get(ch.start_entry)
                create_link(tree, start_entry.outputs[0], node.inputs[ch.io_index])
                if ch.type == 'RGB' and ch.alpha:
                    start_alpha_entry = nodes.get(ch.start_alpha_entry)
                    create_link(tree, start_alpha_entry.outputs[0], node.inputs[ch.io_index+1])
            else:
                create_link(tree, below_node.outputs[ch.io_index], node.inputs[ch.io_index])
                if ch.type == 'RGB' and ch.alpha:
                    create_link(tree, below_node.outputs[ch.io_index+1], 
                            node.inputs[ch.io_index+1])

            if i == 0:
                end_entry = nodes.get(ch.end_entry)
                create_link(tree, node.outputs[ch.io_index], end_entry.inputs[0])
                if ch.type == 'RGB' and ch.alpha:
                    end_alpha_entry = nodes.get(ch.end_alpha_entry)
                    create_link(tree, node.outputs[ch.io_index+1], end_alpha_entry.inputs[0])

def reconnect_tl_channel_nodes(tree, ch_idx=-1):
    tl = tree.tl
    nodes = tree.nodes

    start = nodes.get(tl.start)
    end = nodes.get(tl.end)
    solid_alpha = nodes.get(tl.solid_alpha)

    for i, ch in enumerate(tl.channels):
        if ch_idx != -1 and i != ch_idx: continue

        start_linear = nodes.get(ch.start_linear)
        end_linear = nodes.get(ch.end_linear)
        start_entry = nodes.get(ch.start_entry)
        end_entry = nodes.get(ch.end_entry)
        start_alpha_entry = nodes.get(ch.start_alpha_entry)
        end_alpha_entry = nodes.get(ch.end_alpha_entry)
        start_normal_filter = nodes.get(ch.start_normal_filter)

        start_rgb = nodes.get(ch.start_rgb)
        start_alpha = nodes.get(ch.start_alpha)
        end_rgb = nodes.get(ch.end_rgb)
        end_alpha = nodes.get(ch.end_alpha)

        if len(ch.modifiers) == 0:
            create_link(tree, start_rgb.outputs[0], end_rgb.inputs[0])
            create_link(tree, start_alpha.outputs[0], end_alpha.inputs[0])

        if len(tl.textures) == 0:
            create_link(tree, start_entry.outputs[0], end_entry.inputs[0])
            if ch.type == 'RGB':
                create_link(tree, start_alpha_entry.outputs[0], end_alpha_entry.inputs[0])

        if start_linear:
            create_link(tree, start.outputs[ch.io_index], start_linear.inputs[0])
            create_link(tree, start_linear.outputs[0], start_entry.inputs[0])
        elif start_normal_filter:
            create_link(tree, start.outputs[ch.io_index], start_normal_filter.inputs[0])
            create_link(tree, start_normal_filter.outputs[0], start_entry.inputs[0])

        if ch.type == 'RGB':
            if ch.alpha:
                create_link(tree, start.outputs[ch.io_index+1], start_alpha_entry.inputs[0])
                create_link(tree, end_alpha.outputs[0], end.inputs[ch.io_index+1])
            else: 
                create_link(tree, solid_alpha.outputs[0], start_alpha_entry.inputs[0])
                create_link(tree, start_alpha_entry.outputs[0], end_alpha_entry.inputs[0])
            create_link(tree, end_alpha_entry.outputs[0], start_alpha.inputs[0])
        else:
            create_link(tree, solid_alpha.outputs[0], start_alpha.inputs[0])

        create_link(tree, end_entry.outputs[0], start_rgb.inputs[0])

        if end_linear:
            create_link(tree, end_rgb.outputs[0], end_linear.inputs[0])
            create_link(tree, end_linear.outputs[0], end.inputs[ch.io_index])
        else:
            create_link(tree, end_rgb.outputs[0], end.inputs[ch.io_index])

def reconnect_mask_internal_nodes(mask):

    tree = get_mask_tree(mask)

    source = tree.nodes.get(mask.source)
    hardness = tree.nodes.get(mask.hardness)
    start = tree.nodes.get(MASK_TREE_START)
    end = tree.nodes.get(MASK_TREE_END)

    create_link(tree, start.outputs[0], source.inputs[0])
    if hardness:
        create_link(tree, source.outputs[0], hardness.inputs[0])
        create_link(tree, hardness.outputs[0], end.inputs[0])
    else: 
        create_link(tree, source.outputs[0], end.inputs[0])

def reconnect_tex_nodes(tex, ch_idx=-1):
    tl =  get_active_texture_layers_node().node_tree.tl

    tree = get_tree(tex)
    nodes = tree.nodes

    start = nodes.get(tex.start)
    end = nodes.get(tex.end)

    if tex.source_group != '':
        source = nodes.get(tex.source_group)
    else: source = nodes.get(tex.source)

    #uv_map = nodes.get(tex.uv_map)
    uv_attr = nodes.get(tex.uv_attr)
    texcoord = nodes.get(tex.texcoord)
    solid_alpha = nodes.get(tex.solid_alpha)
    tangent = nodes.get(tex.tangent)
    #hacky_tangent = nodes.get(tex.hacky_tangent)
    bitangent = nodes.get(tex.bitangent)
    geometry = nodes.get(tex.geometry)

    # Texcoord
    if tex.texcoord_type == 'UV':
        #create_link(tree, uv_map.outputs[0], source.inputs[0])
        create_link(tree, uv_attr.outputs[1], source.inputs[0])
    else: create_link(tree, texcoord.outputs[tex.texcoord_type], source.inputs[0])

    # Get bitangent from tangent
    #if hacky_tangent:
    #    create_link(tree, tangent.outputs[0], bitangent.inputs[0])
    #    create_link(tree, hacky_tangent.outputs[0], bitangent.inputs[1])
    #    tangent_output = bitangent.outputs[1]
    #else: 
    tangent_output = tangent.outputs[0]

    flip_bump = any([c for i, c in enumerate(tex.channels) if tl.channels[i].type == 'NORMAL' 
        and c.enable_mask_bump and c.mask_bump_flip and c.enable])

    for i, ch in enumerate(tex.channels):
        if ch_idx != -1 and i != ch_idx: continue
        root_ch = tl.channels[i]

        linear = nodes.get(ch.linear)

        start_rgb = nodes.get(ch.start_rgb)
        start_alpha = nodes.get(ch.start_alpha)
        end_rgb = nodes.get(ch.end_rgb)
        end_alpha = nodes.get(ch.end_alpha)

        bump_base = nodes.get(ch.bump_base)
        bump = nodes.get(ch.bump)
        normal = nodes.get(ch.normal)
        neighbor_uv = nodes.get(ch.neighbor_uv)
        fine_bump = nodes.get(ch.fine_bump)

        source_n = nodes.get(ch.source_n)
        source_s = nodes.get(ch.source_s)
        source_e = nodes.get(ch.source_e)
        source_w = nodes.get(ch.source_w)

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

        # Source output
        if tex.type != 'IMAGE' and ch.tex_input == 'ALPHA':
            source_index = 1
        else: source_index = 0

        if linear:
            create_link(tree, source.outputs[source_index], linear.inputs[0])
            create_link(tree, linear.outputs[0], start_rgb.inputs[0])
        else: create_link(tree, source.outputs[source_index], start_rgb.inputs[0])

        if tex.type == 'IMAGE':
            create_link(tree, source.outputs[1], start_alpha.inputs[0])
        else: create_link(tree, solid_alpha.outputs[0], start_alpha.inputs[0])

        if len(ch.modifiers) == 0:
            create_link(tree, start_rgb.outputs[0], end_rgb.inputs[0])
            create_link(tree, start_alpha.outputs[0], end_alpha.inputs[0])

        # To mark final rgb
        final_rgb = end_rgb.outputs[0]
        
        if root_ch.type == 'NORMAL':
            if bump_base:
                create_link(tree, end_rgb.outputs[0], bump_base.inputs[2])
                create_link(tree, end_alpha.outputs[0], bump_base.inputs[0])
            if bump:
                create_link(tree, bump_base.outputs[0], bump.inputs[2])
            if normal:
                create_link(tree, end_rgb.outputs[0], normal.inputs[1])

            if neighbor_uv:
                if tex.texcoord_type == 'UV':
                    #create_link(tree, uv_map.outputs[0], neighbor_uv.inputs[0])
                    create_link(tree, uv_attr.outputs[1], neighbor_uv.inputs[0])
                else: create_link(tree, texcoord.outputs[tex.texcoord_type], neighbor_uv.inputs[0])

                if 'Tangent' in neighbor_uv.inputs:
                    create_link(tree, tangent.outputs[0], neighbor_uv.inputs['Tangent'])
                if 'Bitangent' in neighbor_uv.inputs:
                    create_link(tree, bitangent.outputs[0], neighbor_uv.inputs['Bitangent'])

                create_link(tree, neighbor_uv.outputs[0], source_n.inputs[0])
                create_link(tree, neighbor_uv.outputs[1], source_s.inputs[0])
                create_link(tree, neighbor_uv.outputs[2], source_e.inputs[0])
                create_link(tree, neighbor_uv.outputs[3], source_w.inputs[0])
                #create_link(tree, source.outputs[0], fine_bump.inputs[1])
                create_link(tree, bump_base.outputs[0], fine_bump.inputs[1])

                create_link(tree, source_n.outputs[source_index], mod_n.inputs[0])
                create_link(tree, source_s.outputs[source_index], mod_s.inputs[0])
                create_link(tree, source_e.outputs[source_index], mod_e.inputs[0])
                create_link(tree, source_w.outputs[source_index], mod_w.inputs[0])

                create_link(tree, source_n.outputs[1], mod_n.inputs[1])
                create_link(tree, source_s.outputs[1], mod_s.inputs[1])
                create_link(tree, source_e.outputs[1], mod_e.inputs[1])
                create_link(tree, source_w.outputs[1], mod_w.inputs[1])

                create_link(tree, mod_n.outputs[0], bump_base_n.inputs[2])
                create_link(tree, mod_s.outputs[0], bump_base_s.inputs[2])
                create_link(tree, mod_e.outputs[0], bump_base_e.inputs[2])
                create_link(tree, mod_w.outputs[0], bump_base_w.inputs[2])

                create_link(tree, mod_n.outputs[1], bump_base_n.inputs[0])
                create_link(tree, mod_s.outputs[1], bump_base_s.inputs[0])
                create_link(tree, mod_e.outputs[1], bump_base_e.inputs[0])
                create_link(tree, mod_w.outputs[1], bump_base_w.inputs[0])

                create_link(tree, bump_base_n.outputs[0], fine_bump.inputs[2])
                create_link(tree, bump_base_s.outputs[0], fine_bump.inputs[3])
                create_link(tree, bump_base_e.outputs[0], fine_bump.inputs[4])
                create_link(tree, bump_base_w.outputs[0], fine_bump.inputs[5])

                create_link(tree, tangent_output, fine_bump.inputs[6])
                create_link(tree, bitangent.outputs[0], fine_bump.inputs[7])

            if bump:
                final_rgb = bump.outputs[0]
            elif normal:
                final_rgb = normal.outputs[0]
            elif fine_bump:
                final_rgb = fine_bump.outputs[0]

            if ch.normal_blend == 'OVERLAY':
                create_link(tree, tangent_output, blend.inputs[3])
                create_link(tree, bitangent.outputs[0], blend.inputs[4])

        if intensity_multiplier:
            create_link(tree, end_alpha.outputs[0], intensity_multiplier.inputs[0])
            create_link(tree, intensity_multiplier.outputs[0], intensity.inputs[0])
        else:
            create_link(tree, end_alpha.outputs[0], intensity.inputs[0])

        # Mark final intensity
        final_intensity = intensity.outputs[0]

        # Masks
        for j, mask in enumerate(tex.masks):
            mask_uv_map = nodes.get(mask.uv_map)

            if mask.group_node != '':
                mask_source = nodes.get(mask.group_node)
                mask_hardness = None
                reconnect_mask_internal_nodes(mask)
            else:
                mask_source = nodes.get(mask.source)
                mask_hardness = nodes.get(mask.hardness)

            mask_final = nodes.get(mask.final)

            mask_multiply = nodes.get(mask.channels[i].multiply)

            if mask.texcoord_type == 'UV':
                create_link(tree, mask_uv_map.outputs[0], mask_source.inputs[0])
            else: create_link(tree, texcoord.outputs[mask.texcoord_type], mask_source.inputs[0])

            if mask_hardness:
                create_link(tree, mask_source.outputs[0], mask_hardness.inputs[0])
                create_link(tree, mask_hardness.outputs[0], mask_final.inputs[0])
            else:
                create_link(tree, mask_source.outputs[0], mask_final.inputs[0])

            create_link(tree, mask_final.outputs[0], mask_multiply.inputs[1])

            if j == 0:
                #create_link(tree, intensity.outputs[0], mask_multiply.inputs[0])
                create_link(tree, solid_alpha.outputs[0], mask_multiply.inputs[0])
            else:
                prev_multiply = nodes.get(tex.masks[j-1].channels[i].multiply)
                create_link(tree, prev_multiply.outputs[0], mask_multiply.inputs[0])
            if j == len(tex.masks)-1:
                if mask_intensity_multiplier:
                    create_link(tree, mask_multiply.outputs[0], mask_intensity_multiplier.inputs[0])
                    create_link(tree, mask_intensity_multiplier.outputs[0], mask_total.inputs[1])
                else:
                    create_link(tree, mask_multiply.outputs[0], mask_total.inputs[1])
                #final_intensity = mask_multiply.outputs[0]
                final_intensity = mask_total.outputs[0]

        if len(tex.masks) > 0:
            create_link(tree, intensity.outputs[0], mask_total.inputs[0])

            # Ramp
            if root_ch.type in {'RGB', 'VALUE'} and ch.enable_mask_ramp:
                mr_inverse = nodes.get(ch.mr_inverse)
                mr_ramp = nodes.get(ch.mr_ramp)
                mr_intensity_multiplier = nodes.get(ch.mr_intensity_multiplier)
                mr_alpha = nodes.get(ch.mr_alpha)
                mr_intensity = nodes.get(ch.mr_intensity)
                mr_blend = nodes.get(ch.mr_blend)
                mr_flip_blend = nodes.get(ch.mr_flip_blend)

                last_mask_multiply = nodes.get(tex.masks[-1].channels[i].multiply)

                create_link(tree, last_mask_multiply.outputs[0], mr_inverse.inputs[1])
                create_link(tree, mr_inverse.outputs[0], mr_ramp.inputs[0])
                create_link(tree, mr_ramp.outputs[0], mr_blend.inputs[2])
                create_link(tree, mr_ramp.outputs[1], mr_alpha.inputs[1])

                if mr_intensity_multiplier:
                    if flip_bump:
                        create_link(tree, last_mask_multiply.outputs[0], mr_intensity_multiplier.inputs[0])
                    else: create_link(tree, mr_inverse.outputs[0], mr_intensity_multiplier.inputs[0])
                    create_link(tree, mr_intensity_multiplier.outputs[0], mr_alpha.inputs[0])
                else:
                    create_link(tree, mr_inverse.outputs[0], mr_alpha.inputs[0])

                create_link(tree, mr_alpha.outputs[0], mr_intensity.inputs[0])

                create_link(tree, mr_intensity.outputs[0], mr_blend.inputs[0])

                if flip_bump:
                    create_link(tree, start.outputs[root_ch.io_index], mr_blend.inputs[1])
                    if mask_intensity_multiplier:
                        create_link(tree, mask_intensity_multiplier.outputs[0], mr_flip_blend.inputs[0])
                    else: create_link(tree, intensity.outputs[0], mr_flip_blend.inputs[0])
                    create_link(tree, mr_blend.outputs[0], mr_flip_blend.inputs[1])
                    create_link(tree, start.outputs[root_ch.io_index], mr_flip_blend.inputs[2])
                else: 
                    create_link(tree, end_rgb.outputs[0], mr_blend.inputs[1])
                    final_rgb = mr_blend.outputs[0]

            # Bump
            if root_ch.type == 'NORMAL' and ch.enable_mask_bump:

                for j, mask in enumerate(tex.masks):
                    c = mask.channels[i]

                    mask_source = nodes.get(mask.group_node)
                    mask_uv_map = nodes.get(mask.uv_map)
                    mask_tangent = nodes.get(mask.tangent)
                    mask_bitangent = nodes.get(mask.bitangent)
                    mask_multiply = nodes.get(c.multiply)

                    mb_neighbor_uv = nodes.get(c.neighbor_uv)
                    mb_source_n = nodes.get(c.source_n)
                    mb_source_s = nodes.get(c.source_s)
                    mb_source_e = nodes.get(c.source_e)
                    mb_source_w = nodes.get(c.source_w)
                    #mb_multiply_me = nodes.get(c.multiply_me)
                    mb_multiply_n = nodes.get(c.multiply_n)
                    mb_multiply_s = nodes.get(c.multiply_s)
                    mb_multiply_e = nodes.get(c.multiply_e)
                    mb_multiply_w = nodes.get(c.multiply_w)

                    create_link(tree, mb_neighbor_uv.outputs[0], mb_source_n.inputs[0])
                    create_link(tree, mb_neighbor_uv.outputs[1], mb_source_s.inputs[0])
                    create_link(tree, mb_neighbor_uv.outputs[2], mb_source_e.inputs[0])
                    create_link(tree, mb_neighbor_uv.outputs[3], mb_source_w.inputs[0])

                    if mask.texcoord_type == 'UV':
                        create_link(tree, mask_uv_map.outputs[0], mb_neighbor_uv.inputs[0])
                    else: create_link(tree, texcoord.outputs[mask.texcoord_type], mb_neighbor_uv.inputs[0])

                    if 'Tangent' in mb_neighbor_uv.inputs:
                        create_link(tree, tangent.outputs[0], mb_neighbor_uv.inputs['Tangent'])
                    if 'Bitangent' in mb_neighbor_uv.inputs:
                        create_link(tree, bitangent.outputs[0], mb_neighbor_uv.inputs['Bitangent'])
                    if 'Mask Tangent' in mb_neighbor_uv.inputs:
                        create_link(tree, mask_tangent.outputs[0], mb_neighbor_uv.inputs['Mask Tangent'])
                    if 'Mask Bitangent' in mb_neighbor_uv.inputs:
                        create_link(tree, mask_bitangent.outputs[0], mb_neighbor_uv.inputs['Mask Bitangent'])

                    if j == 0:
                        #create_link(tree, solid_alpha.outputs[0], mb_multiply_me.inputs[0])
                        create_link(tree, solid_alpha.outputs[0], mb_multiply_n.inputs[0])
                        create_link(tree, solid_alpha.outputs[0], mb_multiply_s.inputs[0])
                        create_link(tree, solid_alpha.outputs[0], mb_multiply_e.inputs[0])
                        create_link(tree, solid_alpha.outputs[0], mb_multiply_w.inputs[0])
                    else:
                        #prev_mul_me = nodes.get(tex.masks[j-1].channels[i].multiply_me)
                        prev_mul_n = nodes.get(tex.masks[j-1].channels[i].multiply_n)
                        prev_mul_s = nodes.get(tex.masks[j-1].channels[i].multiply_s)
                        prev_mul_e = nodes.get(tex.masks[j-1].channels[i].multiply_e)
                        prev_mul_w = nodes.get(tex.masks[j-1].channels[i].multiply_w)

                        #create_link(tree, prev_mul_me.outputs[0], mb_multiply_me.inputs[0])
                        create_link(tree, prev_mul_n.outputs[0], mb_multiply_n.inputs[0])
                        create_link(tree, prev_mul_s.outputs[0], mb_multiply_s.inputs[0])
                        create_link(tree, prev_mul_e.outputs[0], mb_multiply_e.inputs[0])
                        create_link(tree, prev_mul_w.outputs[0], mb_multiply_w.inputs[0])

                    #create_link(tree, mask_source.outputs[0], mb_multiply_me.inputs[1])
                    create_link(tree, mb_source_n.outputs[0], mb_multiply_n.inputs[1])
                    create_link(tree, mb_source_s.outputs[0], mb_multiply_s.inputs[1])
                    create_link(tree, mb_source_e.outputs[0], mb_multiply_e.inputs[1])
                    create_link(tree, mb_source_w.outputs[0], mb_multiply_w.inputs[1])

                mb_fine_bump = nodes.get(ch.mb_fine_bump)
                mb_inverse = nodes.get(ch.mb_inverse)
                mb_intensity_multiplier = nodes.get(ch.mb_intensity_multiplier)
                mb_blend = nodes.get(ch.mb_blend)

                #create_link(tree, mb_multiply_me.outputs[0], mb_fine_bump.inputs[1])
                create_link(tree, mask_multiply.outputs[0], mb_fine_bump.inputs[1])
                create_link(tree, mb_multiply_n.outputs[0], mb_fine_bump.inputs[2])
                create_link(tree, mb_multiply_s.outputs[0], mb_fine_bump.inputs[3])
                create_link(tree, mb_multiply_e.outputs[0], mb_fine_bump.inputs[4])
                create_link(tree, mb_multiply_w.outputs[0], mb_fine_bump.inputs[5])
                create_link(tree, tangent.outputs[0], mb_fine_bump.inputs['Tangent'])
                create_link(tree, bitangent.outputs[0], mb_fine_bump.inputs['Bitangent'])

                create_link(tree, mask_multiply.outputs[0], mb_inverse.inputs[1])
                if mb_intensity_multiplier:
                    create_link(tree, mb_inverse.outputs[0], mb_intensity_multiplier.inputs[0])
                    create_link(tree, mb_intensity_multiplier.outputs[0], mb_blend.inputs[0])
                else:
                    create_link(tree, mb_inverse.outputs[0], mb_blend.inputs[0])

                create_link(tree, final_rgb, mb_blend.inputs[1])
                create_link(tree, mb_fine_bump.outputs[0], mb_blend.inputs[2])

                final_rgb = mb_blend.outputs[0]

        if normal_flip:
            create_link(tree, final_rgb, normal_flip.inputs[0])
            create_link(tree, bitangent.outputs[0], normal_flip.inputs[1])
            final_rgb = normal_flip.outputs[0]

        create_link(tree, final_rgb, blend.inputs[2])

        if root_ch.type == 'RGB' and ch.blend_type == 'MIX' and root_ch.alpha:

            if ch.enable_mask_ramp and flip_bump:
                create_link(tree, mr_flip_blend.outputs[0], blend.inputs[0])
            else: create_link(tree, start.outputs[root_ch.io_index], blend.inputs[0])

            create_link(tree, start.outputs[root_ch.io_index+1], blend.inputs[1])
            create_link(tree, final_intensity, blend.inputs[3])

            create_link(tree, blend.outputs[1], end.inputs[root_ch.io_index+1])
        else:
            create_link(tree, final_intensity, blend.inputs[0])

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

