import bpy
from .common import *

def check_create_node_link(tree, out, inp):
    if not any(l for l in out.links if l.to_socket == inp):
        tree.links.new(out, inp)
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
            check_create_node_link(tree, start_entry.outputs[0], end_entry.inputs[0])
            if ch.type == 'RGB':
                start_alpha_entry = nodes.get(ch.start_alpha_entry)
                end_alpha_entry = nodes.get(ch.end_alpha_entry)
                check_create_node_link(tree, start_alpha_entry.outputs[0], end_alpha_entry.inputs[0])

    for i, tex in reversed(list(enumerate(tl.textures))):

        node = nodes.get(tex.group_node)
        below_node = None
        if i != num_tex-1:
            below_node = nodes.get(tl.textures[i+1].group_node)

        for j, ch in enumerate(tl.channels):
            if ch_idx != -1 and j != ch_idx: continue
            if not below_node:
                start_entry = nodes.get(ch.start_entry)
                check_create_node_link(tree, start_entry.outputs[0], node.inputs[ch.io_index])
                if ch.type == 'RGB' and ch.alpha:
                    start_alpha_entry = nodes.get(ch.start_alpha_entry)
                    check_create_node_link(tree, start_alpha_entry.outputs[0], node.inputs[ch.io_index+1])
            else:
                check_create_node_link(tree, below_node.outputs[ch.io_index], node.inputs[ch.io_index])
                if ch.type == 'RGB' and ch.alpha:
                    check_create_node_link(tree, below_node.outputs[ch.io_index+1], 
                            node.inputs[ch.io_index+1])

            if i == 0:
                end_entry = nodes.get(ch.end_entry)
                check_create_node_link(tree, node.outputs[ch.io_index], end_entry.inputs[0])
                if ch.type == 'RGB' and ch.alpha:
                    end_alpha_entry = nodes.get(ch.end_alpha_entry)
                    check_create_node_link(tree, node.outputs[ch.io_index+1], end_alpha_entry.inputs[0])

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
            check_create_node_link(tree, start_rgb.outputs[0], end_rgb.inputs[0])
            check_create_node_link(tree, start_alpha.outputs[0], end_alpha.inputs[0])

        if len(tl.textures) == 0:
            check_create_node_link(tree, start_entry.outputs[0], end_entry.inputs[0])
            if ch.type == 'RGB':
                check_create_node_link(tree, start_alpha_entry.outputs[0], end_alpha_entry.inputs[0])

        if start_linear:
            check_create_node_link(tree, start.outputs[ch.io_index], start_linear.inputs[0])
            check_create_node_link(tree, start_linear.outputs[0], start_entry.inputs[0])
        elif start_normal_filter:
            check_create_node_link(tree, start.outputs[ch.io_index], start_normal_filter.inputs[0])
            check_create_node_link(tree, start_normal_filter.outputs[0], start_entry.inputs[0])

        if ch.type == 'RGB':
            if ch.alpha:
                check_create_node_link(tree, start.outputs[ch.io_index+1], start_alpha_entry.inputs[0])
                check_create_node_link(tree, end_alpha.outputs[0], end.inputs[ch.io_index+1])
            else: 
                check_create_node_link(tree, solid_alpha.outputs[0], start_alpha_entry.inputs[0])
                check_create_node_link(tree, start_alpha_entry.outputs[0], end_alpha_entry.inputs[0])
            check_create_node_link(tree, end_alpha_entry.outputs[0], start_alpha.inputs[0])
        else:
            check_create_node_link(tree, solid_alpha.outputs[0], start_alpha.inputs[0])

        check_create_node_link(tree, end_entry.outputs[0], start_rgb.inputs[0])

        if end_linear:
            check_create_node_link(tree, end_rgb.outputs[0], end_linear.inputs[0])
            check_create_node_link(tree, end_linear.outputs[0], end.inputs[ch.io_index])
        else:
            check_create_node_link(tree, end_rgb.outputs[0], end.inputs[ch.io_index])

def reconnect_mask_internal_nodes(mask):

    source = mask.tree.nodes.get(mask.source)
    hardness = mask.tree.nodes.get(mask.hardness)
    start = mask.tree.nodes.get(MASK_TREE_START)
    end = mask.tree.nodes.get(MASK_TREE_END)

    check_create_node_link(mask.tree, start.outputs[0], source.inputs[0])
    if hardness:
        check_create_node_link(mask.tree, source.outputs[0], hardness.inputs[0])
        check_create_node_link(mask.tree, hardness.outputs[0], end.inputs[0])
    else: 
        check_create_node_link(mask.tree, source.outputs[0], end.inputs[0])

def reconnect_tex_nodes(tex, ch_idx=-1):
    tl =  get_active_texture_layers_node().node_tree.tl

    tree = tex.tree
    nodes = tree.nodes

    start = nodes.get(tex.start)
    end = nodes.get(tex.end)

    if tex.source_tree:
        source = nodes.get(tex.source_group)
    else: source = nodes.get(tex.source)

    uv_map = nodes.get(tex.uv_map)
    texcoord = nodes.get(tex.texcoord)
    solid_alpha = nodes.get(tex.solid_alpha)
    tangent = nodes.get(tex.tangent)
    bitangent = nodes.get(tex.bitangent)
    geometry = nodes.get(tex.geometry)

    # Texcoord
    if tex.texcoord_type == 'UV':
        check_create_node_link(tree, uv_map.outputs[0], source.inputs[0])
    else: check_create_node_link(tree, texcoord.outputs[tex.texcoord_type], source.inputs[0])

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

        intensity = nodes.get(ch.intensity)
        intensity_multiplier = nodes.get(ch.intensity_multiplier)
        blend = nodes.get(ch.blend)

        # Source output
        if tex.type != 'IMAGE' and ch.tex_input == 'ALPHA':
            source_index = 1
        else: source_index = 0

        if linear:
            check_create_node_link(tree, source.outputs[source_index], linear.inputs[0])
            check_create_node_link(tree, linear.outputs[0], start_rgb.inputs[0])
        else: check_create_node_link(tree, source.outputs[source_index], start_rgb.inputs[0])

        if solid_alpha:
            check_create_node_link(tree, solid_alpha.outputs[0], start_alpha.inputs[0])
        else: check_create_node_link(tree, source.outputs[1], start_alpha.inputs[0])

        if len(ch.modifiers) == 0:
            check_create_node_link(tree, start_rgb.outputs[0], end_rgb.inputs[0])
            check_create_node_link(tree, start_alpha.outputs[0], end_alpha.inputs[0])

        # To mark final rgb
        final_rgb = None

        if root_ch.type == 'NORMAL':
            if bump_base:
                check_create_node_link(tree, end_rgb.outputs[0], bump_base.inputs[2])
                check_create_node_link(tree, end_alpha.outputs[0], bump_base.inputs[0])
            if bump:
                check_create_node_link(tree, bump_base.outputs[0], bump.inputs[2])
            if normal:
                check_create_node_link(tree, end_rgb.outputs[0], normal.inputs[1])

            if neighbor_uv:
                if tex.texcoord_type == 'UV':
                    check_create_node_link(tree, uv_map.outputs[0], neighbor_uv.inputs[0])
                else: check_create_node_link(tree, texcoord.outputs[tex.texcoord_type], neighbor_uv.inputs[0])
                check_create_node_link(tree, neighbor_uv.outputs[0], source_n.inputs[0])
                check_create_node_link(tree, neighbor_uv.outputs[1], source_s.inputs[0])
                check_create_node_link(tree, neighbor_uv.outputs[2], source_e.inputs[0])
                check_create_node_link(tree, neighbor_uv.outputs[3], source_w.inputs[0])
                #check_create_node_link(tree, source.outputs[0], fine_bump.inputs[1])
                check_create_node_link(tree, bump_base.outputs[0], fine_bump.inputs[1])

                check_create_node_link(tree, source_n.outputs[source_index], mod_n.inputs[0])
                check_create_node_link(tree, source_s.outputs[source_index], mod_s.inputs[0])
                check_create_node_link(tree, source_e.outputs[source_index], mod_e.inputs[0])
                check_create_node_link(tree, source_w.outputs[source_index], mod_w.inputs[0])

                check_create_node_link(tree, source_n.outputs[1], mod_n.inputs[1])
                check_create_node_link(tree, source_s.outputs[1], mod_s.inputs[1])
                check_create_node_link(tree, source_e.outputs[1], mod_e.inputs[1])
                check_create_node_link(tree, source_w.outputs[1], mod_w.inputs[1])

                check_create_node_link(tree, mod_n.outputs[0], bump_base_n.inputs[2])
                check_create_node_link(tree, mod_s.outputs[0], bump_base_s.inputs[2])
                check_create_node_link(tree, mod_e.outputs[0], bump_base_e.inputs[2])
                check_create_node_link(tree, mod_w.outputs[0], bump_base_w.inputs[2])

                check_create_node_link(tree, mod_n.outputs[1], bump_base_n.inputs[0])
                check_create_node_link(tree, mod_s.outputs[1], bump_base_s.inputs[0])
                check_create_node_link(tree, mod_e.outputs[1], bump_base_e.inputs[0])
                check_create_node_link(tree, mod_w.outputs[1], bump_base_w.inputs[0])

                check_create_node_link(tree, bump_base_n.outputs[0], fine_bump.inputs[2])
                check_create_node_link(tree, bump_base_s.outputs[0], fine_bump.inputs[3])
                check_create_node_link(tree, bump_base_e.outputs[0], fine_bump.inputs[4])
                check_create_node_link(tree, bump_base_w.outputs[0], fine_bump.inputs[5])

                check_create_node_link(tree, tangent.outputs[0], fine_bump.inputs[6])
                check_create_node_link(tree, bitangent.outputs[0], fine_bump.inputs[7])
                check_create_node_link(tree, geometry.outputs['Normal'], fine_bump.inputs[8])

            #if bump and ch.normal_map_type == 'BUMP_MAP':
            #    normal_flip_input = bump.outputs[0]
            #elif normal and ch.normal_map_type =='NORMAL_MAP':
            #    normal_flip_input = normal.outputs[0]
            #elif fine_bump and ch.normal_map_type =='FINE_BUMP_MAP':
            #    normal_flip_input = fine_bump.outputs[0]
            normal_flip_input = None
            if bump:
                normal_flip_input = bump.outputs[0]
            elif normal:
                normal_flip_input = normal.outputs[0]
            elif fine_bump:
                normal_flip_input = fine_bump.outputs[0]

            # Bump Mask connections
            for j, m in enumerate(tex.masks):
                c = m.channels[i]
                if c.enable_bump:

                    prev_vector_mix = None
                    if j > 0:
                        prev_m = tex.masks[j-1]
                        prev_c = prev_m.channels[i] 
                        if prev_c.enable_bump:
                            prev_vector_mix = nodes.get(prev_c.vector_mix)

                    mask_uv_map = nodes.get(m.uv_map)
                    mask_final = nodes.get(m.final)
                    mask_neighbor_uv = nodes.get(c.neighbor_uv)
                    mask_source_n = nodes.get(c.source_n)
                    mask_source_s = nodes.get(c.source_s)
                    mask_source_e = nodes.get(c.source_e)
                    mask_source_w = nodes.get(c.source_w)
                    mask_fine_bump = nodes.get(c.fine_bump)
                    mask_invert = nodes.get(c.invert)
                    mask_intensity_multiplier = nodes.get(c.vector_intensity_multiplier)
                    mask_vector_mix = nodes.get(c.vector_mix)

                    if m.texcoord_type == 'UV':
                        check_create_node_link(tree, mask_uv_map.outputs[0], mask_neighbor_uv.inputs[0])
                    else: check_create_node_link(tree, texcoord.outputs[m.texcoord_type], neighbor_uv.inputs[0])
                    check_create_node_link(tree, mask_neighbor_uv.outputs[0], mask_source_n.inputs[0])
                    check_create_node_link(tree, mask_neighbor_uv.outputs[1], mask_source_s.inputs[0])
                    check_create_node_link(tree, mask_neighbor_uv.outputs[2], mask_source_e.inputs[0])
                    check_create_node_link(tree, mask_neighbor_uv.outputs[3], mask_source_w.inputs[0])

                    check_create_node_link(tree, mask_final.outputs[0], mask_fine_bump.inputs[1])
                    check_create_node_link(tree, mask_source_n.outputs[0], mask_fine_bump.inputs[2])
                    check_create_node_link(tree, mask_source_s.outputs[0], mask_fine_bump.inputs[3])
                    check_create_node_link(tree, mask_source_e.outputs[0], mask_fine_bump.inputs[4])
                    check_create_node_link(tree, mask_source_w.outputs[0], mask_fine_bump.inputs[5])

                    check_create_node_link(tree, tangent.outputs[0], mask_fine_bump.inputs[6])
                    check_create_node_link(tree, bitangent.outputs[0], mask_fine_bump.inputs[7])
                    check_create_node_link(tree, geometry.outputs['Normal'], mask_fine_bump.inputs[8])

                    check_create_node_link(tree, mask_final.outputs[0], mask_invert.inputs[1])
                    check_create_node_link(tree, mask_invert.outputs[0], mask_intensity_multiplier.inputs[0])
                    check_create_node_link(tree, mask_intensity_multiplier.outputs[0], mask_vector_mix.inputs[0])

                    if prev_vector_mix:
                        check_create_node_link(tree, prev_vector_mix.outputs[0], mask_vector_mix.inputs[1])
                    elif fine_bump:
                        check_create_node_link(tree, fine_bump.outputs[0], mask_vector_mix.inputs[1])
                    elif bump:
                        check_create_node_link(tree, bump.outputs[0], mask_vector_mix.inputs[1])
                    elif normal:
                        check_create_node_link(tree, normal.outputs[0], mask_vector_mix.inputs[1])

                    check_create_node_link(tree, mask_fine_bump.outputs[0], mask_vector_mix.inputs[2])
                    normal_flip_input = mask_vector_mix.outputs[0]

            if normal_flip and normal_flip_input:
                check_create_node_link(tree, normal_flip_input, normal_flip.inputs[0])
                check_create_node_link(tree, bitangent.outputs[0], normal_flip.inputs[1])
                check_create_node_link(tree, normal_flip.outputs[0], blend.inputs[2])

            if ch.normal_blend == 'OVERLAY':
                check_create_node_link(tree, geometry.outputs[1], blend.inputs[3])
                check_create_node_link(tree, tangent.outputs[0], blend.inputs[4])
                check_create_node_link(tree, bitangent.outputs[0], blend.inputs[5])
        else:
            final_rgb = end_rgb.outputs[0]
            #check_create_node_link(tree, end_rgb.outputs[0], blend.inputs[2])

        if intensity_multiplier:
            check_create_node_link(tree, end_alpha.outputs[0], intensity_multiplier.inputs[0])
            check_create_node_link(tree, intensity_multiplier.outputs[0], intensity.inputs[2])
        else:
            check_create_node_link(tree, end_alpha.outputs[0], intensity.inputs[2])

        # Mark final intensity
        final_intensity = intensity.outputs[0]

        # Masks
        for j, mask in enumerate(tex.masks):
            mask_uv_map = nodes.get(mask.uv_map)

            if mask.tree:
                mask_source = nodes.get(mask.group)
                mask_hardness = None
                reconnect_mask_internal_nodes(mask)
            else:
                mask_source = nodes.get(mask.source)
                mask_hardness = nodes.get(mask.hardness)

            mask_final = nodes.get(mask.final)

            mask_intensity_multiplier = nodes.get(mask.channels[i].intensity_multiplier)
            mask_multiply = nodes.get(mask.channels[i].multiply)

            if mask.texcoord_type == 'UV':
                check_create_node_link(tree, mask_uv_map.outputs[0], mask_source.inputs[0])
            else: check_create_node_link(tree, texcoord.outputs[mask.texcoord_type], mask_source.inputs[0])

            if mask_hardness:
                check_create_node_link(tree, mask_source.outputs[0], mask_hardness.inputs[0])
                check_create_node_link(tree, mask_hardness.outputs[0], mask_final.inputs[0])
            else:
                check_create_node_link(tree, mask_source.outputs[0], mask_final.inputs[0])

            if mask_intensity_multiplier:
                check_create_node_link(tree, mask_final.outputs[0], mask_intensity_multiplier.inputs[0])
                check_create_node_link(tree, mask_intensity_multiplier.outputs[0], mask_multiply.inputs[1])
            else:
                check_create_node_link(tree, mask_final.outputs[0], mask_multiply.inputs[1])

            if j == 0:
                check_create_node_link(tree, intensity.outputs[0], mask_multiply.inputs[0])
            else:
                prev_multiply = nodes.get(tex.masks[j-1].channels[i].mask_multiply)
                check_create_node_link(tree, prev_multiply.outputs[0], mask_multiply.inputs[0])
            if j == len(tex.masks)-1:
                final_intensity = mask_multiply.outputs[0]

        # Mask ramps
        for j, mask in enumerate(tex.masks):
            mask_final = nodes.get(mask.final)
            mask_ramp = nodes.get(mask.channels[i].ramp)
            mask_ramp_multiply = nodes.get(mask.channels[i].ramp_multiply)
            mask_ramp_mix = nodes.get(mask.channels[i].ramp_mix)

            if mask_ramp:
                check_create_node_link(tree, mask_final.outputs[0], mask_ramp.inputs[0])
                if mask_ramp_multiply:
                    check_create_node_link(tree, mask_final.outputs[0], mask_ramp_multiply.inputs[0])
                    check_create_node_link(tree, mask_ramp.outputs[1], mask_ramp_multiply.inputs[1])
                if mask_ramp_mix:
                    check_create_node_link(tree, mask_ramp.outputs[0], mask_ramp_mix.inputs[0])
                    check_create_node_link(tree, mask_ramp_multiply.outputs[0], mask_ramp_mix.inputs[1])
                    check_create_node_link(tree, final_rgb, mask_ramp_mix.inputs[2])
                    check_create_node_link(tree, final_intensity, mask_ramp_mix.inputs[3])

                    final_rgb =  mask_ramp_mix.outputs[0]
                    final_intensity = mask_ramp_mix.outputs[1]

        if final_rgb:
            check_create_node_link(tree, final_rgb, blend.inputs[2])

        if root_ch.type == 'RGB' and ch.blend_type == 'MIX' and root_ch.alpha:
            check_create_node_link(tree, start.outputs[root_ch.io_index], blend.inputs[0])
            check_create_node_link(tree, start.outputs[root_ch.io_index+1], blend.inputs[1])
            check_create_node_link(tree, blend.outputs[1], end.inputs[root_ch.io_index+1])
            check_create_node_link(tree, final_intensity, blend.inputs[3])
        else:
            check_create_node_link(tree, final_intensity, blend.inputs[0])
            check_create_node_link(tree, start.outputs[root_ch.io_index], blend.inputs[1])

        check_create_node_link(tree, blend.outputs[0], end.inputs[root_ch.io_index])

        if root_ch.type == 'RGB' and ch.blend_type != 'MIX' and root_ch.alpha:
            check_create_node_link(tree, start.outputs[root_ch.io_index+1], end.inputs[root_ch.io_index+1])

