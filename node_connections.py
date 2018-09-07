import bpy
from .common import *

def create_link(tree, out, inp):
    if not any(l for l in out.links if l.to_socket == inp):
        tree.links.new(out, inp)
        #print(out, 'is connected to', inp)
        return True
    return False

def break_link(tree, out, inp):
    for link in out.links:
        if link.to_socket == inp:
            tree.links.remove(link)
            return True
    return False

def reconnect_between_modifier_nodes(parent):

    tl = parent.id_data.tl
    modifiers = parent.modifiers

    tree = get_mod_tree(parent)
    nodes = tree.nodes

    match = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', parent.path_from_id())

    if match and parent.mod_group != '':
        tex = tl.textures[int(match.group(1))]
        tex_tree = get_tree(tex)

        # start and end inside modifier tree
        parent_start = nodes.get(MODIFIER_TREE_START)
        parent_start_rgb = parent_start.outputs[0]
        parent_start_alpha = parent_start.outputs[1]

        parent_end = nodes.get(MODIFIER_TREE_END)
        parent_end_rgb = parent_end.inputs[0]
        parent_end_alpha = parent_end.inputs[1]

        # Connect outside tree nodes
        mod_group = tex_tree.nodes.get(parent.mod_group)
        start_rgb = tex_tree.nodes.get(parent.start_rgb)
        start_alpha = tex_tree.nodes.get(parent.start_alpha)
        end_rgb = tex_tree.nodes.get(parent.end_rgb)
        end_alpha = tex_tree.nodes.get(parent.end_alpha)

        create_link(tex_tree, start_rgb.outputs[0], mod_group.inputs[0])
        create_link(tex_tree, start_alpha.outputs[0], mod_group.inputs[1])
        create_link(tex_tree, mod_group.outputs[0], end_rgb.inputs[0])
        create_link(tex_tree, mod_group.outputs[1], end_alpha.inputs[0])

    else:
        parent_start_rgb = nodes.get(parent.start_rgb).outputs[0]
        parent_start_alpha = nodes.get(parent.start_alpha).outputs[0]
        parent_end_rgb = nodes.get(parent.end_rgb).inputs[0]
        parent_end_alpha = nodes.get(parent.end_alpha).inputs[0]

    if len(modifiers) == 0:
        create_link(tree, parent_start_rgb, parent_end_rgb)
        create_link(tree, parent_start_alpha, parent_end_alpha)

    for i, m in enumerate(modifiers):
        start_rgb = nodes.get(m.start_rgb)
        end_rgb = nodes.get(m.end_rgb)
        start_alpha = nodes.get(m.start_alpha)
        end_alpha = nodes.get(m.end_alpha)

        # Get previous modifier
        if i == len(modifiers)-1:
            prev_rgb = parent_start_rgb
            prev_alpha = parent_start_alpha
        else:
            prev_m = modifiers[i+1]
            prev_rgb = nodes.get(prev_m.end_rgb)
            prev_alpha = nodes.get(prev_m.end_alpha)
            prev_rgb = prev_rgb.outputs[0]
            prev_alpha = prev_alpha.outputs[0]

        # Connect to previous modifier
        create_link(tree, prev_rgb, start_rgb.inputs[0])
        create_link(tree, prev_alpha, start_alpha.inputs[0])

        if i == 0:
            # Connect to next modifier
            create_link(tree, end_rgb.outputs[0], parent_end_rgb)
            create_link(tree, end_alpha.outputs[0], parent_end_alpha)

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

def reconnect_tl_channel_nodes(tree, ch_idx=-1, mod_reconnect=False):
    tl = tree.tl
    nodes = tree.nodes

    start = nodes.get(tl.start)
    end = nodes.get(tl.end)
    solid_alpha = nodes.get(tl.solid_alpha)

    for i, ch in enumerate(tl.channels):
        if ch_idx != -1 and i != ch_idx: continue

        if mod_reconnect:
            reconnect_between_modifier_nodes(ch)

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

#def reconnect_source_tree(tex):
#    pass

def reconnect_tex_nodes(tex, ch_idx=-1, mod_reconnect = False):
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

    # Get bump channel
    bump_ch = None
    flip_bump = False
    #if len(tex.masks) > 0:
    for i, c in enumerate(tex.channels):
        if tl.channels[i].type == 'NORMAL' and c.enable_mask_bump and c.enable:
            bump_ch = c
            if bump_ch.mask_bump_flip:
                flip_bump = True
            break

    for i, ch in enumerate(tex.channels):
        if ch_idx != -1 and i != ch_idx: continue
        root_ch = tl.channels[i]

        ch_source = nodes.get(ch.source)
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

        # Modifiers
        if mod_reconnect:
            reconnect_between_modifier_nodes(ch)

        #if tex.type != 'IMAGE' and ch.tex_input == 'ALPHA': # and tex.source_group == '':
        if ch.tex_input == 'ALPHA': # and tex.source_group == '':
            source_index = 1
        else: source_index = 0

        #if tex.type != 'IMAGE' and ch.tex_input  and tex.source_group != '':
        #    source_tree = get_source_tree(tex)
        #    src = source_tree.nodes.get(tex.source)
        #    create_link(source_tree, src.outputs[1], 

        # Source output
        source_output = source.outputs[source_index]
        #if ch.tex_input == 'CUSTOM' and root_ch.type in {'RGB', 'VALUE'} and ch_source:
        #    source_output = ch_source.outputs[0]
        #if ch.tex_input == 'CUSTOM' and root_ch.type in {'RGB', 'VALUE'} and ch_source:
        #    linear = linear.outputs[0]
        #if ch_source:
        #    if linear: create_link(tree, ch_source.outputs[0], linear.inputs[0]) 
        #    else: create_link(tree, ch_source.outputs[0], start_rgb.inputs[0]) 

        if linear:
            if ch.tex_input == 'CUSTOM' and root_ch.type in {'RGB', 'VALUE'}:
                break_link(tree, source_output, linear.inputs[0])
            else: create_link(tree, source_output, linear.inputs[0])

            create_link(tree, linear.outputs[0], start_rgb.inputs[0])
        elif ch_source:
            #if linear: create_link(tree, ch_source.outputs[0], linear.inputs[0]) 
            create_link(tree, ch_source.outputs[0], start_rgb.inputs[0]) 
        else: 
            create_link(tree, source_output, start_rgb.inputs[0])

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
                #create_link(tree, end_rgb.outputs[0], bump.inputs[2])
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

                if mod_n:
                    if ch.tex_input == 'CUSTOM':
                        if linear:
                            create_link(tree, linear.outputs[0], mod_n.inputs[0])
                            create_link(tree, linear.outputs[0], mod_s.inputs[0])
                            create_link(tree, linear.outputs[0], mod_e.inputs[0])
                            create_link(tree, linear.outputs[0], mod_w.inputs[0])
                        elif ch_source:
                            create_link(tree, ch_source.outputs[0], mod_n.inputs[0])
                            create_link(tree, ch_source.outputs[0], mod_s.inputs[0])
                            create_link(tree, ch_source.outputs[0], mod_e.inputs[0])
                            create_link(tree, ch_source.outputs[0], mod_w.inputs[0])
                    else:
                        create_link(tree, source_n.outputs[source_index], mod_n.inputs[0])
                        create_link(tree, source_s.outputs[source_index], mod_s.inputs[0])
                        create_link(tree, source_e.outputs[source_index], mod_e.inputs[0])
                        create_link(tree, source_w.outputs[source_index], mod_w.inputs[0])

                    if tex.type != 'IMAGE':
                        create_link(tree, solid_alpha.outputs[0], mod_n.inputs[1])
                        create_link(tree, solid_alpha.outputs[0], mod_s.inputs[1])
                        create_link(tree, solid_alpha.outputs[0], mod_e.inputs[1])
                        create_link(tree, solid_alpha.outputs[0], mod_w.inputs[1])
                    else:
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
                else:
                #elif tex.type == 'IMAGE':
                    if ch.tex_input == 'CUSTOM':
                        if linear:
                            create_link(tree, linear.outputs[0], bump_base_n.inputs[2])
                            create_link(tree, linear.outputs[0], bump_base_s.inputs[2])
                            create_link(tree, linear.outputs[0], bump_base_e.inputs[2])
                            create_link(tree, linear.outputs[0], bump_base_w.inputs[2])
                        elif ch_source:
                            create_link(tree, ch_source.outputs[0], bump_base_n.inputs[2])
                            create_link(tree, ch_source.outputs[0], bump_base_s.inputs[2])
                            create_link(tree, ch_source.outputs[0], bump_base_e.inputs[2])
                            create_link(tree, ch_source.outputs[0], bump_base_w.inputs[2])
                    else:
                        create_link(tree, source_n.outputs[source_index], bump_base_n.inputs[2])
                        create_link(tree, source_s.outputs[source_index], bump_base_s.inputs[2])
                        create_link(tree, source_e.outputs[source_index], bump_base_e.inputs[2])
                        create_link(tree, source_w.outputs[source_index], bump_base_w.inputs[2])

                    if tex.type != 'IMAGE':
                        create_link(tree, solid_alpha.outputs[0], bump_base_n.inputs[0])
                        create_link(tree, solid_alpha.outputs[0], bump_base_s.inputs[0])
                        create_link(tree, solid_alpha.outputs[0], bump_base_e.inputs[0])
                        create_link(tree, solid_alpha.outputs[0], bump_base_w.inputs[0])
                    else:
                    #if tex.type == 'IMAGE':
                        create_link(tree, source_n.outputs[1], bump_base_n.inputs[0])
                        create_link(tree, source_s.outputs[1], bump_base_s.inputs[0])
                        create_link(tree, source_e.outputs[1], bump_base_e.inputs[0])
                        create_link(tree, source_w.outputs[1], bump_base_w.inputs[0])

                #if len(ch.modifiers) == 0 and tex.type != 'IMAGE':
                #    create_link(tree, source_n.outputs[source_index], fine_bump.inputs[2])
                #    create_link(tree, source_s.outputs[source_index], fine_bump.inputs[3])
                #    create_link(tree, source_e.outputs[source_index], fine_bump.inputs[4])
                #    create_link(tree, source_w.outputs[source_index], fine_bump.inputs[5])
                #else:
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

        # Mark final intensity
        final_intensity = end_alpha.outputs[0]

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

        #if len(tex.masks) > 0:
        if mask_total:
            create_link(tree, end_alpha.outputs[0], mask_total.inputs[0])

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
                multiply_input = end_alpha.outputs[0]

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
                create_link(tree, end_alpha.outputs[0], mr_alpha1.inputs[1])
                create_link(tree, mr_alpha1.outputs[0], mr_intensity.inputs[0])
            else:
                create_link(tree, mr_alpha.outputs[0], mr_intensity.inputs[0])

            create_link(tree, mr_intensity.outputs[0], mr_blend.inputs[0])

            if flip_bump:
                create_link(tree, start.outputs[root_ch.io_index], mr_blend.inputs[1])

                if bump_ch.mask_bump_mask_only:
                    if mask_intensity_multiplier:
                        create_link(tree, mask_intensity_multiplier.outputs[0], mr_flip_hack.inputs[0])
                    else: create_link(tree, end_alpha.outputs[0], mr_flip_hack.inputs[0])
                else:
                    create_link(tree, intensity_multiplier.outputs[0], mr_flip_hack.inputs[0])

                create_link(tree, mr_flip_hack.outputs[0], mr_flip_blend.inputs[0])
                create_link(tree, mr_blend.outputs[0], mr_flip_blend.inputs[1])
                create_link(tree, start.outputs[root_ch.io_index], mr_flip_blend.inputs[2])
            else: 
                create_link(tree, end_rgb.outputs[0], mr_blend.inputs[1])
                final_rgb = mr_blend.outputs[0]

        # Bump
        if root_ch.type == 'NORMAL' and ch.enable_mask_bump and ch.enable:

            if ch.mask_bump_type == 'FINE_BUMP_MAP':

                mb_neighbor_uv = nodes.get(ch.mb_neighbor_uv)
                
                mb_source_n = nodes.get(ch.mb_source_n)
                mb_source_s = nodes.get(ch.mb_source_s)
                mb_source_e = nodes.get(ch.mb_source_e)
                mb_source_w = nodes.get(ch.mb_source_w)

                mb_mod_n = nodes.get(ch.mb_mod_n)
                mb_mod_s = nodes.get(ch.mb_mod_s)
                mb_mod_e = nodes.get(ch.mb_mod_e)
                mb_mod_w = nodes.get(ch.mb_mod_w)

                if tex.texcoord_type == 'UV':
                    create_link(tree, uv_attr.outputs[1], mb_neighbor_uv.inputs[0])
                else: create_link(tree, texcoord.outputs[tex.texcoord_type], mb_neighbor_uv.inputs[0])

                if 'Tangent' in mb_neighbor_uv.inputs:
                    create_link(tree, tangent.outputs[0], mb_neighbor_uv.inputs['Tangent'])
                if 'Bitangent' in mb_neighbor_uv.inputs:
                    create_link(tree, bitangent.outputs[0], mb_neighbor_uv.inputs['Bitangent'])

                create_link(tree, mb_neighbor_uv.outputs[0], mb_source_n.inputs[0])
                create_link(tree, mb_neighbor_uv.outputs[1], mb_source_s.inputs[0])
                create_link(tree, mb_neighbor_uv.outputs[2], mb_source_e.inputs[0])
                create_link(tree, mb_neighbor_uv.outputs[3], mb_source_w.inputs[0])

                if mb_mod_n:
                    if ch.tex_input == 'CUSTOM':
                        if linear:
                            create_link(tree, linear.outputs[0], mb_mod_n.inputs[0])
                            create_link(tree, linear.outputs[0], mb_mod_s.inputs[0])
                            create_link(tree, linear.outputs[0], mb_mod_e.inputs[0])
                            create_link(tree, linear.outputs[0], mb_mod_w.inputs[0])
                        elif ch_source:
                            create_link(tree, ch_source.outputs[0], mb_mod_n.inputs[0])
                            create_link(tree, ch_source.outputs[0], mb_mod_s.inputs[0])
                            create_link(tree, ch_source.outputs[0], mb_mod_e.inputs[0])
                            create_link(tree, ch_source.outputs[0], mb_mod_w.inputs[0])
                    else:
                        create_link(tree, mb_source_n.outputs[0], mb_mod_n.inputs[0])
                        create_link(tree, mb_source_s.outputs[0], mb_mod_s.inputs[0])
                        create_link(tree, mb_source_e.outputs[0], mb_mod_e.inputs[0])
                        create_link(tree, mb_source_w.outputs[0], mb_mod_w.inputs[0])

                    if tex.type != 'IMAGE':
                        create_link(tree, solid_alpha.outputs[0], mb_mod_n.inputs[1])
                        create_link(tree, solid_alpha.outputs[0], mb_mod_s.inputs[1])
                        create_link(tree, solid_alpha.outputs[0], mb_mod_e.inputs[1])
                        create_link(tree, solid_alpha.outputs[0], mb_mod_w.inputs[1])
                    else:
                        create_link(tree, mb_source_n.outputs[1], mb_mod_n.inputs[1])
                        create_link(tree, mb_source_s.outputs[1], mb_mod_s.inputs[1])
                        create_link(tree, mb_source_e.outputs[1], mb_mod_e.inputs[1])
                        create_link(tree, mb_source_w.outputs[1], mb_mod_w.inputs[1])

                for j, mask in enumerate(tex.masks):
                    c = mask.channels[i]

                    mask_source = nodes.get(mask.group_node)
                    mask_uv_map = nodes.get(mask.uv_map)
                    mask_tangent = nodes.get(mask.tangent)
                    mask_bitangent = nodes.get(mask.bitangent)
                    mask_multiply = nodes.get(c.multiply)

                    c_neighbor_uv = nodes.get(c.neighbor_uv)
                    c_source_n = nodes.get(c.source_n)
                    c_source_s = nodes.get(c.source_s)
                    c_source_e = nodes.get(c.source_e)
                    c_source_w = nodes.get(c.source_w)
                    c_multiply_n = nodes.get(c.multiply_n)
                    c_multiply_s = nodes.get(c.multiply_s)
                    c_multiply_e = nodes.get(c.multiply_e)
                    c_multiply_w = nodes.get(c.multiply_w)

                    create_link(tree, c_neighbor_uv.outputs[0], c_source_n.inputs[0])
                    create_link(tree, c_neighbor_uv.outputs[1], c_source_s.inputs[0])
                    create_link(tree, c_neighbor_uv.outputs[2], c_source_e.inputs[0])
                    create_link(tree, c_neighbor_uv.outputs[3], c_source_w.inputs[0])

                    if mask.texcoord_type == 'UV':
                        create_link(tree, mask_uv_map.outputs[0], c_neighbor_uv.inputs[0])
                    else: create_link(tree, texcoord.outputs[mask.texcoord_type], c_neighbor_uv.inputs[0])

                    if 'Tangent' in c_neighbor_uv.inputs:
                        create_link(tree, tangent.outputs[0], c_neighbor_uv.inputs['Tangent'])
                    if 'Bitangent' in c_neighbor_uv.inputs:
                        create_link(tree, bitangent.outputs[0], c_neighbor_uv.inputs['Bitangent'])
                    if 'Mask Tangent' in c_neighbor_uv.inputs:
                        create_link(tree, mask_tangent.outputs[0], c_neighbor_uv.inputs['Mask Tangent'])
                    if 'Mask Bitangent' in c_neighbor_uv.inputs:
                        create_link(tree, mask_bitangent.outputs[0], c_neighbor_uv.inputs['Mask Bitangent'])

                    if j == 0:
                        if mb_mod_n:
                            create_link(tree, mb_mod_n.outputs[1], c_multiply_n.inputs[0])
                            create_link(tree, mb_mod_s.outputs[1], c_multiply_s.inputs[0])
                            create_link(tree, mb_mod_e.outputs[1], c_multiply_e.inputs[0])
                            create_link(tree, mb_mod_w.outputs[1], c_multiply_w.inputs[0])
                        elif tex.type == 'IMAGE':
                            create_link(tree, mb_source_n.outputs[1], c_multiply_n.inputs[0])
                            create_link(tree, mb_source_s.outputs[1], c_multiply_s.inputs[0])
                            create_link(tree, mb_source_e.outputs[1], c_multiply_e.inputs[0])
                            create_link(tree, mb_source_w.outputs[1], c_multiply_w.inputs[0])
                        else:
                            create_link(tree, solid_alpha.outputs[0], c_multiply_n.inputs[0])
                            create_link(tree, solid_alpha.outputs[0], c_multiply_s.inputs[0])
                            create_link(tree, solid_alpha.outputs[0], c_multiply_e.inputs[0])
                            create_link(tree, solid_alpha.outputs[0], c_multiply_w.inputs[0])
                    else:
                        prev_mul_n = nodes.get(tex.masks[j-1].channels[i].multiply_n)
                        prev_mul_s = nodes.get(tex.masks[j-1].channels[i].multiply_s)
                        prev_mul_e = nodes.get(tex.masks[j-1].channels[i].multiply_e)
                        prev_mul_w = nodes.get(tex.masks[j-1].channels[i].multiply_w)

                        create_link(tree, prev_mul_n.outputs[0], c_multiply_n.inputs[0])
                        create_link(tree, prev_mul_s.outputs[0], c_multiply_s.inputs[0])
                        create_link(tree, prev_mul_e.outputs[0], c_multiply_e.inputs[0])
                        create_link(tree, prev_mul_w.outputs[0], c_multiply_w.inputs[0])

                    create_link(tree, c_source_n.outputs[0], c_multiply_n.inputs[1])
                    create_link(tree, c_source_s.outputs[0], c_multiply_s.inputs[1])
                    create_link(tree, c_source_e.outputs[0], c_multiply_e.inputs[1])
                    create_link(tree, c_source_w.outputs[0], c_multiply_w.inputs[1])

            if len(tex.masks) > 0:
                if ch.mask_bump_mask_only:
                    last_multiply = nodes.get(tex.masks[-1].channels[i].multiply)
                    intensity_output = last_multiply.outputs[0]
                else:
                    intensity_output = mask_total.outputs[0]
            else:
                intensity_output = end_alpha.outputs[0]

            if ch.mask_bump_type == 'FINE_BUMP_MAP':
                mb_bump = nodes.get(ch.mb_fine_bump)

                if len(tex.masks) > 0:
                    c_multiply_n = nodes.get(tex.masks[-1].channels[i].multiply_n)
                    c_multiply_s = nodes.get(tex.masks[-1].channels[i].multiply_s)
                    c_multiply_e = nodes.get(tex.masks[-1].channels[i].multiply_e)
                    c_multiply_w = nodes.get(tex.masks[-1].channels[i].multiply_w)

                    create_link(tree, c_multiply_n.outputs[0], mb_bump.inputs[2])
                    create_link(tree, c_multiply_s.outputs[0], mb_bump.inputs[3])
                    create_link(tree, c_multiply_e.outputs[0], mb_bump.inputs[4])
                    create_link(tree, c_multiply_w.outputs[0], mb_bump.inputs[5])
                else:
                    if mb_mod_n:
                        create_link(tree, mb_mod_n.outputs[1], mb_bump.inputs[2])
                        create_link(tree, mb_mod_s.outputs[1], mb_bump.inputs[3])
                        create_link(tree, mb_mod_e.outputs[1], mb_bump.inputs[4])
                        create_link(tree, mb_mod_w.outputs[1], mb_bump.inputs[5])
                    else:
                        create_link(tree, mb_source_n.outputs[1], mb_bump.inputs[2])
                        create_link(tree, mb_source_s.outputs[1], mb_bump.inputs[3])
                        create_link(tree, mb_source_e.outputs[1], mb_bump.inputs[4])
                        create_link(tree, mb_source_w.outputs[1], mb_bump.inputs[5])
                
                create_link(tree, intensity_output, mb_bump.inputs[1])
                create_link(tree, tangent.outputs[0], mb_bump.inputs['Tangent'])
                create_link(tree, bitangent.outputs[0], mb_bump.inputs['Bitangent'])

            if ch.mask_bump_type == 'BUMP_MAP':
                mb_bump = nodes.get(ch.mb_bump)

                create_link(tree, intensity_output, mb_bump.inputs[2])

            mb_inverse = nodes.get(ch.mb_inverse)
            mb_intensity_multiplier = nodes.get(ch.mb_intensity_multiplier)
            mb_blend = nodes.get(ch.mb_blend)

            create_link(tree, intensity_output, mb_inverse.inputs[1])
            if mb_intensity_multiplier:
                create_link(tree, mb_inverse.outputs[0], mb_intensity_multiplier.inputs[0])
                create_link(tree, mb_intensity_multiplier.outputs[0], mb_blend.inputs[0])
            else:
                create_link(tree, mb_inverse.outputs[0], mb_blend.inputs[0])

            create_link(tree, final_rgb, mb_blend.inputs[1])
            create_link(tree, mb_bump.outputs[0], mb_blend.inputs[2])

            final_rgb = mb_blend.outputs[0]

        if normal_flip:
            create_link(tree, final_rgb, normal_flip.inputs[0])
            create_link(tree, bitangent.outputs[0], normal_flip.inputs[1])
            final_rgb = normal_flip.outputs[0]

        if intensity_multiplier:
            create_link(tree, final_intensity, intensity_multiplier.inputs[0])
            final_intensity = intensity_multiplier.outputs[0]

        create_link(tree, final_intensity, intensity.inputs[0])
        final_intensity = intensity.outputs[0]

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

