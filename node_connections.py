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

def break_input_link(tree, inp):
    for link in inp.links:
        tree.links.remove(link)

def reconnect_mask_modifier_nodes(tree, mod, start_value):
    
    value = start_value

    if mod.type == 'INVERT':
        invert = tree.nodes.get(mod.invert)
        create_link(tree, value, invert.inputs[1])
        value = invert.outputs[0]

    elif mod.type == 'RAMP':
        ramp = tree.nodes.get(mod.ramp)
        ramp_mix = tree.nodes.get(mod.ramp_mix)
        create_link(tree, value, ramp.inputs[0])
        create_link(tree, value, ramp_mix.inputs[1])
        create_link(tree, ramp.outputs[0], ramp_mix.inputs[2])

        value = ramp_mix.outputs[0]

    return value

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

def get_channel_inputs_length(tl, tex=None):
    length = 0
    for ch in tl.channels:
        #if (ch.type == 'RGB' and ch.alpha) or (tex and tex.type == 'GROUP' and tex.parent_idx != -1):
        if (ch.type == 'RGB' and ch.alpha) or (tex and tex.parent_idx != -1):
            length += 2
        else: length += 1

    return length

def remove_all_prev_inputs(tex):
    tree = tex.id_data
    tl = tree.tl
    node = tree.nodes.get(tex.group_node)

    #for inp in node.inputs:
    #    break_input_link(tree, inp)

    for i in range(len(tex.channels)*2):
        break_input_link(tree, node.inputs[i])

    #input_offset = get_channel_inputs_length(tl, tex)
    #for i in range(input_offset):
    #    break_input_link(tree, node.inputs[i])

def remove_all_children_inputs(tex):

    tree = tex.id_data
    tl = tree.tl
    node = tree.nodes.get(tex.group_node)

    if tex.type != 'GROUP':
        return

    if tex.parent_idx == -1:
        offset = get_channel_inputs_length(tl)
    else: offset = len(tex.channels)*2

    for i, inp in enumerate(node.inputs):
        if i >= offset:
            break_input_link(tree, inp)

def reconnect_tl_nodes(tree, ch_idx=-1):
    tl = tree.tl
    nodes = tree.nodes

    #print('Reconnect tree ' + tree.name)

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

        # Background rgb and alpha
        bg_rgb = rgb
        bg_alpha = alpha

        # Layers loop
        for j, tex in reversed(list(enumerate(tl.textures))):

            node = nodes.get(tex.group_node)

            if tex.type == 'BACKGROUND':

                # Offsets for background layer
                input_offset = get_channel_inputs_length(tl, tex)
                bg_index = input_offset + ch.io_index

                create_link(tree, bg_rgb, node.inputs[bg_index])
                if ch.type =='RGB' and ch.alpha:
                    create_link(tree, bg_alpha, node.inputs[bg_index+1])

            if tex.parent_idx != -1: continue

            create_link(tree, rgb, node.inputs[ch.io_index])
            if ch.type =='RGB' and ch.alpha:
                create_link(tree, alpha, node.inputs[ch.io_index+1])

            rgb = node.outputs[ch.io_index]
            if ch.type =='RGB' and ch.alpha:
                alpha = node.outputs[ch.io_index+1]

        rgb, alpha = reconnect_all_modifier_nodes(tree, ch, rgb, alpha)

        if end_linear:
            create_link(tree, rgb, end_linear.inputs[0])
            rgb = end_linear.outputs[0]

        create_link(tree, rgb, end.inputs[ch.io_index])
        if ch.type == 'RGB' and ch.alpha:
            create_link(tree, alpha, end.inputs[ch.io_index+1])

    # List of last members
    last_members = []
    for tex in tl.textures:
        if is_bottom_member(tex):
            last_members.append(tex)

            # Remove input links from bottom member
            remove_all_prev_inputs(tex)

        if tex.type == 'GROUP' and not has_childrens(tex):
            remove_all_children_inputs(tex)

    #print(last_members)

    # Group stuff
    for tex in last_members:

        node = nodes.get(tex.group_node)

        cur_tex = tex
        cur_node = node

        while True:
            # Get upper tex
            upper_idx, upper_tex = get_upper_neighbor(cur_tex)
            upper_node = nodes.get(upper_tex.group_node)

            #print(upper_tex.name)

            # Connect
            if upper_tex.parent_idx == cur_tex.parent_idx:
                for i, outp in enumerate(cur_node.outputs):
                    create_link(tree, outp, upper_node.inputs[i])
            else:

                input_offset = get_channel_inputs_length(tl, upper_tex)
                for i, outp in enumerate(cur_node.outputs):
                    create_link(tree, outp, upper_node.inputs[input_offset+i])

                break

            cur_tex = upper_tex
            cur_node = upper_node

        #print(upper_tex.name)

def reconnect_source_internal_nodes(tex):
    tree = get_source_tree(tex)

    source = tree.nodes.get(tex.source)
    mapping = tree.nodes.get(tex.mapping)
    start = tree.nodes.get(SOURCE_TREE_START)
    solid = tree.nodes.get(SOURCE_SOLID_VALUE)
    end = tree.nodes.get(SOURCE_TREE_END)

    #if tex.type != 'VCOL':
    #    create_link(tree, start.outputs[0], source.inputs[0])
    if mapping:
        create_link(tree, start.outputs[0], mapping.inputs[0])
        create_link(tree, mapping.outputs[0], source.inputs[0])
    else:
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
    mapping = tree.nodes.get(mask.mapping)
    start = tree.nodes.get(MASK_TREE_START)
    end = tree.nodes.get(MASK_TREE_END)

    if mask.type != 'VCOL':
        if mapping:
            create_link(tree, start.outputs[0], mapping.inputs[0])
            create_link(tree, mapping.outputs[0], source.inputs[0])
        else:
            create_link(tree, start.outputs[0], source.inputs[0])

    val = source.outputs[0]

    for mod in mask.modifiers:
        val = reconnect_mask_modifier_nodes(tree, mod, val)

    create_link(tree, val, end.inputs[0])

def reconnect_tex_nodes(tex, ch_idx=-1):
    #tl =  get_active_texture_layers_node().node_tree.tl
    tl = tex.id_data.tl

    #print('Reconnect texture ' + tex.name)
    if tl.halt_reconnect: return

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

    mapping = nodes.get(tex.mapping)
    texcoord = nodes.get(tex.texcoord)
    solid_alpha = nodes.get(tex.solid_alpha)
    tangent = nodes.get(tex.tangent)
    bitangent = nodes.get(tex.bitangent)
    geometry = nodes.get(tex.geometry)

    # Texcoord
    if tex.type not in {'VCOL', 'BACKGROUND', 'COLOR', 'GROUP'}:
        if tex.texcoord_type == 'UV':
            vector = uv_attr.outputs[1]
        else: vector = texcoord.outputs[tex.texcoord_type]

        if source_group or not mapping:
            create_link(tree, vector, source.inputs[0])
        elif mapping:
            create_link(tree, vector, mapping.inputs[0])
            create_link(tree, mapping.outputs[0], source.inputs[0])

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
    start_rgb_1 = None
    if tex.type != 'COLOR':
        start_rgb_1 = source.outputs[1]

    # Alpha
    if tex.type == 'IMAGE' or source_group:
        start_alpha = source.outputs[1]
    else: start_alpha = solid_alpha.outputs[0]
    start_alpha_1 = solid_alpha.outputs[0]

    if source_group and tex.type not in {'IMAGE', 'VCOL', 'BACKGROUND'}:
        start_rgb_1 = source_group.outputs[2]
        start_alpha_1 = source_group.outputs[3]

    elif not source_group:

        # Layer source modifier
        mod_group = nodes.get(tex.mod_group)

        # Background layer won't use modifier outputs
        if tex.type in {'BACKGROUND', 'GROUP'}:
            #reconnect_all_modifier_nodes(tree, tex, start_rgb, start_alpha, mod_group)
            pass
        else:
            start_rgb, start_alpha = reconnect_all_modifier_nodes(
                    tree, tex, start_rgb, start_alpha, mod_group)

        if tex.type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'COLOR', 'GROUP'}:
            mod_group_1 = nodes.get(tex.mod_group_1)
            start_rgb_1, start_alpha_1 = reconnect_all_modifier_nodes(
                    tree, tex, source.outputs[1], solid_alpha.outputs[0], mod_group_1)

    # UV neighbor vertex color
    if tex.type in {'VCOL', 'GROUP'} and uv_neighbor:
        if tex.type == 'VCOL':
            create_link(tree, start_rgb, uv_neighbor.inputs[0])
        create_link(tree, tangent.outputs[0], uv_neighbor.inputs['Tangent'])
        create_link(tree, bitangent.outputs[0], uv_neighbor.inputs['Bitangent'])

    # Get transition bump channel
    trans_bump_flip = False
    chain = -1
    fine_bump_ch = False
    trans_bump_ch = get_transition_bump_channel(tex)
    if trans_bump_ch:
        trans_bump_flip = trans_bump_ch.mask_bump_flip or tex.type == 'BACKGROUND'
        chain = min(len(tex.masks), trans_bump_ch.mask_bump_chain)
        fine_bump_ch = trans_bump_ch.mask_bump_type in {'FINE_BUMP_MAP', 'CURVED_BUMP_MAP'}
    #elif tex.type == 'BACKGROUND':
    #    trans_bump_flip = True

    # Layer Masks
    for i, mask in enumerate(tex.masks):

        # Mask source
        if mask.group_node != '':
            mask_source = nodes.get(mask.group_node)
            reconnect_mask_internal_nodes(mask)
            mask_mapping = None
            mask_val = mask_source.outputs[0]
        else:
            mask_source = nodes.get(mask.source)
            mask_mapping = nodes.get(mask.mapping)

            mask_val = mask_source.outputs[0]
            for mod in mask.modifiers:
                mask_val = reconnect_mask_modifier_nodes(tree, mod, mask_val)

        # Mask source directions
        mask_source_n = nodes.get(mask.source_n)
        mask_source_s = nodes.get(mask.source_s)
        mask_source_e = nodes.get(mask.source_e)
        mask_source_w = nodes.get(mask.source_w)

        # Mask texcoord
        mask_uv_map = nodes.get(mask.uv_map)
        if mask.type != 'VCOL':
            if mask.texcoord_type == 'UV':
                mask_vector = mask_uv_map.outputs[0]
            else: mask_vector = texcoord.outputs[mask.texcoord_type]

            if mask_mapping:
                create_link(tree, mask_vector, mask_mapping.inputs[0])
                create_link(tree, mask_mapping.outputs[0], mask_source.inputs[0])
            else:
                create_link(tree, mask_vector, mask_source.inputs[0])

        # Mask uv neighbor
        mask_uv_neighbor = nodes.get(mask.uv_neighbor)
        if mask_uv_neighbor:

            if mask.type == 'VCOL':
                #create_link(tree, mask_source.outputs[0], mask_uv_neighbor.inputs[0])
                create_link(tree, mask_val, mask_uv_neighbor.inputs[0])
            else:
                if mask.texcoord_type == 'UV':
                    create_link(tree, mask_uv_map.outputs[0], mask_uv_neighbor.inputs[0])
                else: create_link(tree, texcoord.outputs[mask.texcoord_type], mask_uv_neighbor.inputs[0])

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
        for j, c in enumerate(mask.channels):
            root_ch = tl.channels[j]
            ch = tex.channels[j]

            mask_multiply = nodes.get(c.multiply)
            #create_link(tree, mask_source.outputs[0], mask_multiply.inputs[2])
            create_link(tree, mask_val, mask_multiply.inputs[2])

            # Direction multiplies
            #if (root_ch.type == 'NORMAL' and ch.enable_mask_bump 
            #        and ch.enable and ch.mask_bump_type in {'FINE_BUMP_MAP', 'CURVED_BUMP_MAP'}):
            #if ch == trans_bump_ch and fine_bump_ch and i < chain:

            mul_n = nodes.get(c.multiply_n)
            mul_s = nodes.get(c.multiply_s)
            mul_e = nodes.get(c.multiply_e)
            mul_w = nodes.get(c.multiply_w)

            if mask.type == 'VCOL':
                if mul_n: 
                    if mask_uv_neighbor:
                        create_link(tree, mask_uv_neighbor.outputs['n'], mul_n.inputs[2])
                    else: create_link(tree, mask_val, mul_n.inputs[2])

                if mul_s: create_link(tree, mask_uv_neighbor.outputs['s'], mul_s.inputs[2])
                if mul_e: create_link(tree, mask_uv_neighbor.outputs['e'], mul_e.inputs[2])
                if mul_w: create_link(tree, mask_uv_neighbor.outputs['w'], mul_w.inputs[2])
            else:
                if mul_n:
                    if mask_source_n: 
                        create_link(tree, mask_source_n.outputs[0], mul_n.inputs[2])
                    else: create_link(tree, mask_val, mul_n.inputs[2])

                if mul_s and mask_source_s: create_link(tree, mask_source_s.outputs[0], mul_s.inputs[2])
                if mul_e and mask_source_e: create_link(tree, mask_source_e.outputs[0], mul_e.inputs[2])
                if mul_w and mask_source_w: create_link(tree, mask_source_w.outputs[0], mul_w.inputs[2])

    # Offset for background layer
    #prev_offset = 0
    # Offsets for background layer
    input_offset = get_channel_inputs_length(tl, tex)
    has_parent = tex.parent_idx != -1

    # Layer Channels
    for i, ch in enumerate(tex.channels):

        root_ch = tl.channels[i]

        # Rgb and alpha start
        rgb = start_rgb
        alpha = start_alpha
        bg_alpha = None

        if tex.type == 'GROUP': # and root_ch.alpha:
            rgb = source.outputs[i*2 + input_offset]
            alpha = source.outputs[i*2 + input_offset + 1]

        elif tex.type == 'BACKGROUND':
            rgb = source.outputs[root_ch.io_index + input_offset]
            alpha = solid_alpha.outputs[0]

            if root_ch.alpha:
                bg_alpha = source.outputs[root_ch.io_index + 1 + input_offset]

        # Color layer uses geometry normal
        #if tex.type == 'COLOR' and root_ch.type == 'NORMAL' and is_valid_to_remove_bump_nodes(tex, ch): # and len(ch.modifiers) == 0:
        #    rgb = geometry.outputs['Normal']

        # Input RGB from layer below
        #if tex.type == 'BACKGROUND':
        #    prev_rgb = start.outputs[root_ch.io_index + input_offset]
        #    prev_alpha = start.outputs[root_ch.io_index+1 + input_offset]
        #else:
        if has_parent:
            prev_rgb = start.outputs[i*2]
            prev_alpha = start.outputs[i*2+1]
        else:
            prev_rgb = start.outputs[root_ch.io_index]
            prev_alpha = start.outputs[root_ch.io_index+1]

        #if tex.type == 'BACKGROUND':

        #    prev_rgb = start.outputs[prev_offset]

        #    if root_ch.alpha:
        #        prev_alpha = start.outputs[prev_offset+1]
        #        rgb = source.outputs[prev_offset+2]
        #        alpha = source.outputs[prev_offset+3]
        #        prev_offset += 4
        #    else: 
        #        rgb = source.outputs[prev_offset+1]
        #        prev_offset += 2

        if tex.type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'COLOR'}:
            if ch.tex_input == 'ALPHA':
                rgb = start_rgb_1
                alpha = start_alpha_1

        if ch_idx != -1 and i != ch_idx: continue

        intensity = nodes.get(ch.intensity)
        intensity_multiplier = nodes.get(ch.intensity_multiplier)
        blend = nodes.get(ch.blend)

        linear = nodes.get(ch.linear)
        if linear:
            create_link(tree, rgb, linear.inputs[0])
            rgb = linear.outputs[0]

        mod_group = nodes.get(ch.mod_group)

        rgb_before_mod = rgb
        alpha_before_mod = rgb

        # Background layer won't use modifier outputs
        #if tex.type == 'BACKGROUND' or (tex.type == 'COLOR' and root_ch.type == 'NORMAL'):
        if tex.type == 'BACKGROUND':
            #reconnect_all_modifier_nodes(tree, ch, rgb, alpha, mod_group)
            pass
        else:
            rgb, alpha = reconnect_all_modifier_nodes(tree, ch, rgb, alpha, mod_group)

        if root_ch.type == 'NORMAL':

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

            elif tex.type == 'VCOL' and uv_neighbor:
                rgb_n = uv_neighbor.outputs['n']
                rgb_s = uv_neighbor.outputs['s']
                rgb_e = uv_neighbor.outputs['e']
                rgb_w = uv_neighbor.outputs['w']

                alpha_n = start_alpha
                alpha_s = start_alpha
                alpha_e = start_alpha
                alpha_w = start_alpha

            elif ch.enable_mask_bump and tex.type == 'GROUP' and uv_neighbor:
                create_link(tree, alpha, uv_neighbor.inputs[0])

                rgb_n = rgb_before_mod
                rgb_s = rgb_before_mod
                rgb_e = rgb_before_mod
                rgb_w = rgb_before_mod

                alpha_n = uv_neighbor.outputs['n']
                alpha_s = uv_neighbor.outputs['s']
                alpha_e = uv_neighbor.outputs['e']
                alpha_w = uv_neighbor.outputs['w']

            else:
                alpha_n = alpha
                alpha_s = alpha
                alpha_e = alpha
                alpha_w = alpha

                rgb_n = rgb
                rgb_s = rgb
                rgb_e = rgb
                rgb_w = rgb

            mod_n = nodes.get(ch.mod_n)
            mod_s = nodes.get(ch.mod_s)
            mod_e = nodes.get(ch.mod_e)
            mod_w = nodes.get(ch.mod_w)

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

            if tex.type not in {'BACKGROUND', 'GROUP'}: #, 'COLOR'}:

                normal_map_type = ch.normal_map_type
                #if tex.type in {'VCOL', 'COLOR'} and ch.normal_map_type == 'FINE_BUMP_MAP':
                #    normal_map_type = 'BUMP_MAP'

                if normal_map_type == 'NORMAL_MAP':

                    normal = nodes.get(ch.normal)
                    if normal:
                        create_link(tree, rgb, normal.inputs[1])
                        rgb = normal.outputs[0]

                elif normal_map_type == 'BUMP_MAP':

                    bump = nodes.get(ch.bump)
                    bump_base = nodes.get(ch.bump_base)
                    if bump and bump_base:

                        create_link(tree, rgb, bump_base.inputs['Color2'])

                        chain_local = min(len(tex.masks), ch.mask_bump_chain)

                        if not trans_bump_ch and len(tex.masks) > 0 and chain_local > 0:
                            mul = nodes.get(tex.masks[chain_local-1].channels[i].multiply).outputs[0]
                            create_link(tree, mul, bump_base.inputs['Fac'])
                        else:
                            create_link(tree, alpha, bump_base.inputs['Fac'])

                        create_link(tree, bump_base.outputs[0], bump.inputs[2])
                        rgb = bump.outputs[0]

                elif normal_map_type == 'FINE_BUMP_MAP':

                    fine_bump = nodes.get(ch.fine_bump)
                    bump_base_n = nodes.get(ch.bump_base_n)
                    bump_base_s = nodes.get(ch.bump_base_s)
                    bump_base_e = nodes.get(ch.bump_base_e)
                    bump_base_w = nodes.get(ch.bump_base_w)

                    if bump_base_n and bump_base_s and bump_base_e and bump_base_w and fine_bump:

                        malpha_n = alpha_n
                        malpha_s = alpha_s
                        malpha_e = alpha_e
                        malpha_w = alpha_w

                        if not trans_bump_ch:
                            chain_local = min(len(tex.masks), ch.mask_bump_chain)
                            for j, mask in enumerate(tex.masks):
                                if j >= chain_local:
                                    break

                                c = mask.channels[i]
                                mul_n = nodes.get(c.multiply_n)
                                mul_s = nodes.get(c.multiply_s)
                                mul_e = nodes.get(c.multiply_e)
                                mul_w = nodes.get(c.multiply_w)

                                malpha_n = create_link(tree, malpha_n, mul_n.inputs[1])[0]
                                malpha_s = create_link(tree, malpha_s, mul_s.inputs[1])[0]
                                malpha_e = create_link(tree, malpha_e, mul_e.inputs[1])[0]
                                malpha_w = create_link(tree, malpha_w, mul_w.inputs[1])[0]

                        create_link(tree, malpha_n, bump_base_n.inputs['Fac'])
                        create_link(tree, malpha_s, bump_base_s.inputs['Fac'])
                        create_link(tree, malpha_e, bump_base_e.inputs['Fac'])
                        create_link(tree, malpha_w, bump_base_w.inputs['Fac'])

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

        # For transition input
        transition_input = alpha
        if chain == 0 and intensity_multiplier:
            alpha = create_link(tree, alpha, intensity_multiplier.inputs[0])[0]

        # Mask multiplies
        for j, mask in enumerate(tex.masks):
            mask_multiply = nodes.get(mask.channels[i].multiply)
            alpha = create_link(tree, alpha, mask_multiply.inputs[1])[0]

            if j == chain-1 and intensity_multiplier:
                transition_input = alpha
                alpha = create_link(tree, alpha, intensity_multiplier.inputs[0])[0]

        # If transition bump is not found, use last alpha as input
        if not trans_bump_ch:
            transition_input = alpha

        # Transition Bump
        if root_ch.type == 'NORMAL' and ch.enable_mask_bump and ch.enable:

            if ch.mask_bump_type == 'BUMP_MAP':
                mb_bump = nodes.get(ch.mb_bump)
                create_link(tree, transition_input, mb_bump.inputs['Height'])

            elif ch.mask_bump_type in {'FINE_BUMP_MAP', 'CURVED_BUMP_MAP'}:

                #if tex.type == 'GROUP' and uv_neighbor:
                #    malpha_n = uv_neighbor.outputs[0]
                #    malpha_s = uv_neighbor.outputs[1]
                #    malpha_e = uv_neighbor.outputs[2]
                #    malpha_w = uv_neighbor.outputs[3]
                #else:
                malpha_n = alpha_n
                malpha_s = alpha_s
                malpha_e = alpha_e
                malpha_w = alpha_w

                for j, mask in enumerate(tex.masks):
                    if j >= chain:
                        break

                    c = mask.channels[i]
                    mul_n = nodes.get(c.multiply_n)
                    mul_s = nodes.get(c.multiply_s)
                    mul_e = nodes.get(c.multiply_e)
                    mul_w = nodes.get(c.multiply_w)

                    malpha_n = create_link(tree, malpha_n, mul_n.inputs[1])[0]
                    malpha_s = create_link(tree, malpha_s, mul_s.inputs[1])[0]
                    malpha_e = create_link(tree, malpha_e, mul_e.inputs[1])[0]
                    malpha_w = create_link(tree, malpha_w, mul_w.inputs[1])[0]

                if ch.mask_bump_type == 'FINE_BUMP_MAP':
                    mb_bump = nodes.get(ch.mb_fine_bump)
                else: 
                    mb_bump = nodes.get(ch.mb_curved_bump)
                    create_link(tree, transition_input, mb_bump.inputs['Alpha'])

                create_link(tree, malpha_n, mb_bump.inputs['n'])
                create_link(tree, malpha_s, mb_bump.inputs['s'])
                create_link(tree, malpha_e, mb_bump.inputs['e'])
                create_link(tree, malpha_w, mb_bump.inputs['w'])

                create_link(tree, tangent.outputs[0], mb_bump.inputs['Tangent'])
                create_link(tree, bitangent.outputs[0], mb_bump.inputs['Bitangent'])

            mb_inverse = nodes.get(ch.mb_inverse)
            mb_intensity_multiplier = nodes.get(ch.mb_intensity_multiplier)
            mb_blend = nodes.get(ch.mb_blend)

            create_link(tree, transition_input, mb_inverse.inputs[1])
            if mb_intensity_multiplier:
                create_link(tree, mb_inverse.outputs[0], mb_intensity_multiplier.inputs[0])
                create_link(tree, mb_intensity_multiplier.outputs[0], mb_blend.inputs[0])
            else:
                create_link(tree, mb_inverse.outputs[0], mb_blend.inputs[0])

            create_link(tree, rgb, mb_blend.inputs[1])
            create_link(tree, mb_bump.outputs[0], mb_blend.inputs[2])

            rgb = mb_blend.outputs[0]

        # Transition AO
        if root_ch.type in {'RGB', 'VALUE'} and trans_bump_ch and ch.enable_transition_ao: # and tex.type != 'BACKGROUND':
            tao = nodes.get(ch.tao)

            if trans_bump_flip:
                create_link(tree, rgb, tao.inputs[0])
                rgb = tao.outputs[0]

                # Get bump intensity multiplier of transition bump
                trans_im = nodes.get(trans_bump_ch.mb_intensity_multiplier)
                create_link(tree, trans_im.outputs[0], tao.inputs['Multiplied Alpha'])

                if 'Bg Alpha' in tao.inputs and bg_alpha:
                    create_link(tree, bg_alpha, tao.inputs['Bg Alpha'])
                    bg_alpha = tao.outputs['Bg Alpha']

            else: 
                create_link(tree, prev_rgb, tao.inputs[0])

                # Get intensity multiplier of transition bump
                trans_im = nodes.get(trans_bump_ch.intensity_multiplier)
                create_link(tree, trans_im.outputs[0], tao.inputs['Multiplied Alpha'])

                # Dealing with chain
                remaining_alpha = solid_alpha.outputs[0]
                for j, mask in enumerate(tex.masks):
                    if j >= chain:
                        if mask.group_node != '':
                            mask_source = nodes.get(mask.group_node)
                            mask_val = mask_source.outputs[0]
                        else: 
                            mask_source = nodes.get(mask.source)
                        c = mask.channels[i]
                        mul_n = nodes.get(c.multiply_n)

                        remaining_alpha = create_link(tree, remaining_alpha, mul_n.inputs[1])[0]
                        #create_link(tree, mask_source.outputs[0], mul_n.inputs[2])

                prev_rgb = tao.outputs[0]
                create_link(tree, remaining_alpha, tao.inputs['Remaining Alpha'])

                if 'Input Alpha' in tao.inputs:
                    create_link(tree, prev_alpha, tao.inputs['Input Alpha'])
                    prev_alpha = tao.outputs['Input Alpha']

            create_link(tree, transition_input, tao.inputs['Alpha'])

        # Transition Ramp
        if root_ch.type in {'RGB', 'VALUE'} and ch.enable_mask_ramp:

            mr_ramp = nodes.get(ch.mr_ramp)
            mr_ramp_blend = nodes.get(ch.mr_ramp_blend)

            create_link(tree, transition_input, mr_ramp.inputs['Alpha'])

            if trans_bump_flip:

                create_link(tree, prev_rgb, mr_ramp_blend.inputs['Input RGB'])
                create_link(tree, intensity_multiplier.outputs[0], mr_ramp_blend.inputs['Multiplied Alpha'])

                create_link(tree, mr_ramp.outputs[0], mr_ramp_blend.inputs['Ramp RGB'])

                ramp_alpha_input = mr_ramp.outputs['Ramp Alpha']

                for j, mask in enumerate(tex.masks):
                    if j >= chain:
                        mask_source = get_mask_source(mask)
                        mul_n = nodes.get(mask.channels[i].multiply_n)

                        ramp_alpha_input = create_link(tree, ramp_alpha_input, mul_n.inputs[1])[0]
                        #create_link(tree, mask_source.outputs[0], mul_n.inputs[2])

                create_link(tree, ramp_alpha_input, mr_ramp_blend.inputs['Ramp Alpha'])
                prev_rgb = mr_ramp_blend.outputs[0]

                if 'Input Alpha' in mr_ramp_blend.inputs:
                    create_link(tree, prev_alpha, mr_ramp_blend.inputs['Input Alpha'])
                    prev_alpha = mr_ramp_blend.outputs['Input Alpha']

                break_input_link(tree, mr_ramp_blend.inputs['Intensity'])

            else:
                create_link(tree, rgb, mr_ramp.inputs['RGB'])
                rgb = mr_ramp.outputs[0]


            '''
            mr_inverse = nodes.get(ch.mr_inverse)
            mr_ramp = nodes.get(ch.mr_ramp)
            mr_linear = nodes.get(ch.mr_linear)
            mr_intensity_multiplier = nodes.get(ch.mr_intensity_multiplier)
            mr_alpha = nodes.get(ch.mr_alpha)
            mr_intensity = nodes.get(ch.mr_intensity)
            mr_blend = nodes.get(ch.mr_blend)

            if trans_bump_flip:
                create_link(tree, transition_input, mr_ramp.inputs[0])
            else:
                create_link(tree, transition_input, mr_inverse.inputs[1])
                create_link(tree, mr_inverse.outputs[0], mr_ramp.inputs[0])

            create_link(tree, mr_ramp.outputs[0], mr_linear.inputs[0])
            create_link(tree, mr_linear.outputs[0], mr_blend.inputs[2])

            create_link(tree, mr_ramp.outputs[1], mr_alpha.inputs[1])

            if mr_intensity_multiplier:
                if trans_bump_flip:
                    create_link(tree, transition_input, mr_intensity_multiplier.inputs[0])
                else: create_link(tree, mr_inverse.outputs[0], mr_intensity_multiplier.inputs[0])
                create_link(tree, mr_intensity_multiplier.outputs[0], mr_alpha.inputs[0])
            else:
                create_link(tree, mr_inverse.outputs[0], mr_alpha.inputs[0])

            # Ramp blending
            if trans_bump_flip:
                mr_flip_hack = nodes.get(ch.mr_flip_hack)
                mr_flip_blend = nodes.get(ch.mr_flip_blend)

                #create_link(tree, mr_alpha.outputs[0], mr_intensity.inputs[0])
                #hack_input = mr_intensity.outputs[0]
                hack_input = mr_alpha.outputs[0]

                for j, mask in enumerate(tex.masks):
                    if j >= chain:
                        if mask.group_node != '':
                            mask_source = nodes.get(mask.group_node)
                        else: mask_source = nodes.get(mask.source)
                        c = mask.channels[i]
                        mul_n = nodes.get(c.multiply_n)

                        hack_input = create_link(tree, hack_input, mul_n.inputs[1])[0]
                        create_link(tree, mask_source.outputs[0], mul_n.inputs[2])

                #create_link(tree, hack_input, mr_blend.inputs[0])
                create_link(tree, hack_input, mr_intensity.inputs[0])
                create_link(tree, mr_intensity.outputs[0], mr_blend.inputs[0])

                create_link(tree, intensity_multiplier.outputs[0], mr_flip_hack.inputs[0])
                create_link(tree, mr_flip_hack.outputs[0], mr_flip_blend.inputs[0])

                create_link(tree, prev_rgb, mr_blend.inputs[1])
                create_link(tree, mr_blend.outputs[0], mr_flip_blend.inputs[1])
                create_link(tree, prev_rgb, mr_flip_blend.inputs[2])

                # Override input rgb
                prev_rgb = mr_flip_blend.outputs[0]

            else: 
                create_link(tree, mr_alpha.outputs[0], mr_intensity.inputs[0])
                create_link(tree, mr_intensity.outputs[0], mr_blend.inputs[0])

                create_link(tree, rgb, mr_blend.inputs[1])
                rgb = mr_blend.outputs[0]
            '''

        # Normal flip check
        normal_flip = nodes.get(ch.normal_flip)
        if normal_flip:
            create_link(tree, rgb, normal_flip.inputs[0])
            create_link(tree, bitangent.outputs[0], normal_flip.inputs[1])
            rgb = normal_flip.outputs[0]

        # Pass alpha to intensity
        create_link(tree, alpha, intensity.inputs[0])
        alpha = intensity.outputs[0]

        # Pass rgb to blend
        create_link(tree, rgb, blend.inputs[2])

        # End node
        if has_parent:
            next_rgb = end.inputs[i*2]
            next_alpha = end.inputs[i*2+1]
        else:
            next_rgb = end.inputs[root_ch.io_index]
            next_alpha = end.inputs[root_ch.io_index+1]

        # Background layer only know mix
        if tex.type == 'BACKGROUND':
            blend_type = 'MIX'
        else: 
            if root_ch.type == 'NORMAL':
                blend_type = ch.normal_blend
            else: blend_type = ch.blend_type

        if blend_type == 'MIX' and (has_parent or (root_ch.type == 'RGB' and root_ch.alpha)):

            create_link(tree, prev_rgb, blend.inputs[0])
            create_link(tree, prev_alpha, blend.inputs[1])

            create_link(tree, alpha, blend.inputs[3])
            create_link(tree, blend.outputs[1], next_alpha)

            if bg_alpha:
                create_link(tree, bg_alpha, blend.inputs[4])
        else:
            create_link(tree, alpha, blend.inputs[0])
            create_link(tree, prev_rgb, blend.inputs[1])

        # Armory can't recognize mute node, so reconnect input to output directly
        #if tex.enable and ch.enable:
        #    create_link(tree, blend.outputs[0], next_rgb)
        #else: create_link(tree, prev_rgb, next_rgb)
        create_link(tree, blend.outputs[0], next_rgb)

        if blend_type != 'MIX' and (has_parent or (root_ch.type == 'RGB' and root_ch.alpha)):
            create_link(tree, prev_alpha, next_alpha)

