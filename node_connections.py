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
        tl_ch = tl.channels[i]

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
        normal_flip = nodes.get(ch.normal_flip)

        intensity = nodes.get(ch.intensity)
        blend = nodes.get(ch.blend)

        # Start and end modifiers
        check_create_node_link(tree, source.outputs[0], start_rgb.inputs[0])
        if solid_alpha:
            check_create_node_link(tree, solid_alpha.outputs[0], start_alpha.inputs[0])
        else: check_create_node_link(tree, source.outputs[1], start_alpha.inputs[0])

        if len(ch.modifiers) == 0:
            check_create_node_link(tree, start_rgb.outputs[0], end_rgb.inputs[0])
            check_create_node_link(tree, start_alpha.outputs[0], end_alpha.inputs[0])

        if tl_ch.type == 'NORMAL':
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
                check_create_node_link(tree, source_n.outputs[0], fine_bump.inputs[2])
                check_create_node_link(tree, source_s.outputs[0], fine_bump.inputs[3])
                check_create_node_link(tree, source_e.outputs[0], fine_bump.inputs[4])
                check_create_node_link(tree, source_w.outputs[0], fine_bump.inputs[5])
                check_create_node_link(tree, tangent.outputs[0], fine_bump.inputs[6])
                check_create_node_link(tree, bitangent.outputs[0], fine_bump.inputs[7])
                check_create_node_link(tree, texcoord.outputs['Normal'], fine_bump.inputs[8])

            if normal_flip:
                if bump and ch.normal_map_type == 'BUMP_MAP':
                    check_create_node_link(tree, bump.outputs[0], normal_flip.inputs[0])
                elif normal and ch.normal_map_type =='NORMAL_MAP':
                    check_create_node_link(tree, normal.outputs[0], normal_flip.inputs[0])
                elif fine_bump and ch.normal_map_type =='FINE_BUMP_MAP':
                    check_create_node_link(tree, fine_bump.outputs[0], normal_flip.inputs[0])

                check_create_node_link(tree, bitangent.outputs[0], normal_flip.inputs[1])
                check_create_node_link(tree, normal_flip.outputs[0], blend.inputs[2])

            if ch.normal_blend == 'OVERLAY':
                check_create_node_link(tree, geometry.outputs[1], blend.inputs[3])
                check_create_node_link(tree, tangent.outputs[0], blend.inputs[4])
                check_create_node_link(tree, bitangent.outputs[0], blend.inputs[5])
        else:
            check_create_node_link(tree, end_rgb.outputs[0], blend.inputs[2])

        check_create_node_link(tree, end_alpha.outputs[0], intensity.inputs[2])

        if tl_ch.type == 'RGB' and ch.blend_type == 'MIX' and tl_ch.alpha:
            check_create_node_link(tree, start.outputs[tl_ch.io_index], blend.inputs[0])
            #if tl_ch.alpha:
            #    check_create_node_link(tree, start.outputs[tl_ch.io_index+1], blend.inputs[1])
            #    check_create_node_link(tree, blend.outputs[1], end.inputs[tl_ch.io_index+1])
            check_create_node_link(tree, start.outputs[tl_ch.io_index+1], blend.inputs[1])
            check_create_node_link(tree, blend.outputs[1], end.inputs[tl_ch.io_index+1])
            check_create_node_link(tree, intensity.outputs[0], blend.inputs[3])
        else:
            check_create_node_link(tree, intensity.outputs[0], blend.inputs[0])
            check_create_node_link(tree, start.outputs[tl_ch.io_index], blend.inputs[1])

        check_create_node_link(tree, blend.outputs[0], end.inputs[tl_ch.io_index])

        if tl_ch.type == 'RGB' and ch.blend_type != 'MIX' and tl_ch.alpha:
            check_create_node_link(tree, start.outputs[tl_ch.io_index+1], end.inputs[tl_ch.io_index+1])

