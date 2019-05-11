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

def get_channel_inputs_length(yp, layer=None):
    length = 0
    for ch in yp.channels:
        length += 1

        if (ch.type == 'RGB' and ch.enable_alpha) or (layer and layer.parent_idx != -1):
            length += 1

        if ch.type == 'NORMAL' and ch.enable_parallax:
            length += 1

    return length

def remove_all_prev_inputs(tree, layer, node): #, height_only=False):

    yp = layer.id_data.yp
    #node = tree.nodes.get(layer.group_node)

    for i, ch in enumerate(layer.channels):
        root_ch = yp.channels[i]

        if root_ch.type == 'NORMAL':

            io_name = root_ch.name + io_suffix['HEIGHT']
            if io_name in node.inputs:
                break_input_link(tree, node.inputs[io_name])

            io_name = root_ch.name + io_suffix['HEIGHT'] + io_suffix['ALPHA']
            if io_name in node.inputs:
                break_input_link(tree, node.inputs[io_name])

            #if height_only: continue

            if root_ch.enable_smooth_bump:
                for d in neighbor_directions:
                    io_name = root_ch.name + io_suffix['HEIGHT'] + ' ' + d
                    if io_name in node.inputs:
                        break_input_link(tree, node.inputs[io_name])

                    io_name = root_ch.name + io_suffix['ALPHA'] + ' ' + d
                    if io_name in node.inputs:
                        break_input_link(tree, node.inputs[io_name])

        #if height_only: continue

        if root_ch.type != 'NORMAL':
            io_name = root_ch.name
            if io_name in node.inputs:
                break_input_link(tree, node.inputs[io_name])

        io_name = root_ch.name + io_suffix['ALPHA']
        if io_name in node.inputs:
            break_input_link(tree, node.inputs[io_name])

def remove_all_children_inputs(tree, layer, node): #, height_only=False):

    yp = layer.id_data.yp
    #node = tree.nodes.get(layer.group_node)

    if layer.type != 'GROUP':
        return

    for i, ch in enumerate(layer.channels):
        root_ch = yp.channels[i]

        io_name = root_ch.name + io_suffix['HEIGHT'] + io_suffix['GROUP']
        if io_name in node.inputs:
            break_input_link(tree, node.inputs[io_name])

        io_name = root_ch.name + io_suffix['HEIGHT'] + io_suffix['ALPHA'] + io_suffix['GROUP']
        if io_name in node.inputs:
            break_input_link(tree, node.inputs[io_name])

        #if height_only: continue

        if root_ch.type != 'NORMAL':
            io_name = root_ch.name + io_suffix['GROUP']
            if io_name in node.inputs:
                break_input_link(tree, node.inputs[io_name])

        io_name = root_ch.name + io_suffix['ALPHA'] + io_suffix['GROUP']
        if io_name in node.inputs:
            break_input_link(tree, node.inputs[io_name])

        if root_ch.enable_smooth_bump:
            for d in neighbor_directions:
                io_name = root_ch.name + io_suffix['HEIGHT'] + ' ' + d + io_suffix['GROUP']
                if io_name in node.inputs:
                    break_input_link(tree, node.inputs[io_name])

                io_name = root_ch.name + io_suffix['ALPHA'] + ' ' + d + io_suffix['GROUP']
                if io_name in node.inputs:
                    break_input_link(tree, node.inputs[io_name])

def reconnect_relief_mapping_nodes(yp, node):
    parallax_ch = get_root_parallax_channel(yp)

    if not parallax_ch: return

    linear_loop = node.node_tree.nodes.get('_linear_search')
    binary_loop = node.node_tree.nodes.get('_binary_search')

    loop = node.node_tree.nodes.get('_linear_search')
    if loop:
        loop_start = loop.node_tree.nodes.get(TREE_START)
        loop_end = loop.node_tree.nodes.get(TREE_END)
        prev_it = None

        for i in range (parallax_ch.parallax_num_of_linear_samples):
            it = loop.node_tree.nodes.get('_iterate_' + str(i))
            if not prev_it:
                create_link(loop.node_tree, 
                        loop_start.outputs['t'], it.inputs['t'])
            else:
                create_link(loop.node_tree, 
                        prev_it.outputs['t'], it.inputs['t'])

            create_link(loop.node_tree,
                    loop_start.outputs['tx'], it.inputs['tx'])

            create_link(loop.node_tree,
                    loop_start.outputs['v'], it.inputs['v'])

            create_link(loop.node_tree,
                    loop_start.outputs['dataz'], it.inputs['dataz'])

            create_link(loop.node_tree,
                    loop_start.outputs['size'], it.inputs['size'])

            if i == parallax_ch.parallax_num_of_linear_samples-1:
                create_link(loop.node_tree, 
                        it.outputs['t'], loop_end.inputs['t'])

            prev_it = it

    loop = node.node_tree.nodes.get('_binary_search')
    if loop:
        loop_start = loop.node_tree.nodes.get(TREE_START)
        loop_end = loop.node_tree.nodes.get(TREE_END)
        prev_it = None

        for i in range (parallax_ch.parallax_num_of_binary_samples):
            it = loop.node_tree.nodes.get('_iterate_' + str(i))
            if not prev_it:
                create_link(loop.node_tree, 
                        loop_start.outputs['t'], it.inputs['t'])

                create_link(loop.node_tree, 
                        loop_start.outputs['size'], it.inputs['size'])
            else:
                create_link(loop.node_tree, 
                        prev_it.outputs['t'], it.inputs['t'])

                create_link(loop.node_tree, 
                        prev_it.outputs['size'], it.inputs['size'])

            create_link(loop.node_tree,
                    loop_start.outputs['tx'], it.inputs['tx'])

            create_link(loop.node_tree,
                    loop_start.outputs['v'], it.inputs['v'])

            create_link(loop.node_tree,
                    loop_start.outputs['dataz'], it.inputs['dataz'])

            if i == parallax_ch.parallax_num_of_binary_samples-1:
                create_link(loop.node_tree, 
                        it.outputs['t'], loop_end.inputs['t'])

            prev_it = it

def reconnect_parallax_layer_nodes(group_tree, parallax, uv_name=''):

    yp = group_tree.yp

    parallax_ch = get_root_parallax_channel(yp)
    if not parallax_ch: return

    loop = parallax.node_tree.nodes.get('_parallax_loop')
    if not loop: return

    loop_start = loop.node_tree.nodes.get(TREE_START)
    loop_end = loop.node_tree.nodes.get(TREE_END)

    prev_it = None

    for i in range (parallax_ch.parallax_num_of_layers):
        it = loop.node_tree.nodes.get('_iterate_' + str(i))

        if not prev_it:
            create_link(loop.node_tree, 
                    loop_start.outputs['depth_from_tex'], it.inputs['depth_from_tex'])

            for uv in yp.uvs:
                if uv_name != '' and uv.name != uv_name: continue
                create_link(loop.node_tree, 
                        loop_start.outputs[uv.name + CURRENT_UV], it.inputs[uv.name + CURRENT_UV])

            for tc in texcoord_lists:
                io_name = TEXCOORD_IO_PREFIX + tc + CURRENT_UV
                if io_name in loop_start.outputs:
                    create_link(loop.node_tree, loop_start.outputs[io_name], it.inputs[io_name])
        else:
            create_link(loop.node_tree, 
                    prev_it.outputs['cur_layer_depth'], it.inputs['cur_layer_depth'])
            create_link(loop.node_tree, 
                    prev_it.outputs['depth_from_tex'], it.inputs['depth_from_tex'])

            create_link(loop.node_tree, 
                    prev_it.outputs['index'], it.inputs['index'])

            for uv in yp.uvs:
                if uv_name != '' and uv.name != uv_name: continue
                create_link(loop.node_tree, 
                        prev_it.outputs[uv.name + CURRENT_UV], it.inputs[uv.name + CURRENT_UV])

            for tc in texcoord_lists:
                io_name = TEXCOORD_IO_PREFIX + tc + CURRENT_UV
                if io_name in prev_it.outputs:
                    create_link(loop.node_tree, prev_it.outputs[io_name], it.inputs[io_name])

        create_link(loop.node_tree,
                loop_start.outputs['layer_depth'], it.inputs['layer_depth'])
        create_link(loop.node_tree,
                loop_start.outputs['base'], it.inputs['base'])

        for uv in yp.uvs:
            if uv_name != '' and uv.name != uv_name: continue
            create_link(loop.node_tree, loop_start.outputs[uv.name + START_UV], it.inputs[uv.name + START_UV])
            create_link(loop.node_tree, loop_start.outputs[uv.name + DELTA_UV], it.inputs[uv.name + DELTA_UV])

        for tc in texcoord_lists:
            io_name = TEXCOORD_IO_PREFIX + tc + START_UV
            if io_name in loop_start.outputs:
                create_link(loop.node_tree, loop_start.outputs[io_name], it.inputs[io_name])
            io_name = TEXCOORD_IO_PREFIX + tc + DELTA_UV
            if io_name in loop_start.outputs:
                create_link(loop.node_tree, loop_start.outputs[io_name], it.inputs[io_name])

        if i == parallax_ch.parallax_num_of_layers-1:

            create_link(loop.node_tree, 
                    it.outputs['cur_layer_depth'], loop_end.inputs['cur_layer_depth'])
            create_link(loop.node_tree, 
                    it.outputs['depth_from_tex'], loop_end.inputs['depth_from_tex'])
            create_link(loop.node_tree, 
                    it.outputs['index'], loop_end.inputs['index'])

            for uv in yp.uvs:
                if uv_name != '' and uv.name != uv_name: continue
                create_link(loop.node_tree, 
                        it.outputs[uv.name + CURRENT_UV], loop_end.inputs[uv.name + CURRENT_UV])

            for tc in texcoord_lists:
                io_name = TEXCOORD_IO_PREFIX + tc + CURRENT_UV
                if io_name in it.outputs:
                    create_link(loop.node_tree, it.outputs[io_name], loop_end.inputs[io_name])

        prev_it = it

def reconnect_baked_parallax_layer_nodes(yp, node):
    parallax_ch = get_root_parallax_channel(yp)
    if not parallax_ch: return

    loop = node.node_tree.nodes.get('_parallax_loop')
    if loop:
        loop_start = loop.node_tree.nodes.get(TREE_START)
        loop_end = loop.node_tree.nodes.get(TREE_END)
        prev_it = None

        for i in range (parallax_ch.parallax_num_of_layers):
            it = loop.node_tree.nodes.get('_iterate_' + str(i))
            if not prev_it:
                create_link(loop.node_tree, 
                        loop_start.outputs['cur_uv'], it.inputs['cur_uv'])
                create_link(loop.node_tree, 
                        loop_start.outputs['cur_layer_depth'], it.inputs['cur_layer_depth'])
                create_link(loop.node_tree, 
                        loop_start.outputs['depth_from_tex'], it.inputs['depth_from_tex'])
            else:
                create_link(loop.node_tree, 
                        prev_it.outputs['cur_uv'], it.inputs['cur_uv'])
                create_link(loop.node_tree, 
                        prev_it.outputs['cur_layer_depth'], it.inputs['cur_layer_depth'])
                create_link(loop.node_tree, 
                        prev_it.outputs['depth_from_tex'], it.inputs['depth_from_tex'])

            create_link(loop.node_tree,
                    loop_start.outputs['delta_uv'], it.inputs['delta_uv'])

            create_link(loop.node_tree,
                    loop_start.outputs['layer_depth'], it.inputs['layer_depth'])

            if i == parallax_ch.parallax_num_of_layers-1:
                create_link(loop.node_tree, 
                        it.outputs['cur_uv'], loop_end.inputs['cur_uv'])
                create_link(loop.node_tree, 
                        it.outputs['cur_layer_depth'], loop_end.inputs['cur_layer_depth'])
                create_link(loop.node_tree, 
                        it.outputs['depth_from_tex'], loop_end.inputs['depth_from_tex'])

            prev_it = it

def reconnect_parallax_process_nodes(group_tree, parallax, baked=False, uv_name=''): #, uv_maps, tangents, bitangents):

    yp = group_tree.yp

    #parallax = group_tree.nodes.get(PARALLAX)
    #if not parallax: return

    tree = parallax.node_tree

    start = tree.nodes.get(TREE_START)
    end = tree.nodes.get(TREE_END)

    # Depth source
    depth_source_0 = tree.nodes.get('_depth_source_0')
    depth_source_1 = tree.nodes.get('_depth_source_1')

    depth_start = depth_source_0.node_tree.nodes.get(TREE_START)
    depth_end = depth_source_0.node_tree.nodes.get(TREE_END)

    # Iteration
    loop = tree.nodes.get('_parallax_loop')
    iterate_0 = loop.node_tree.nodes.get('_iterate_0')

    iterate_start = iterate_0.node_tree.nodes.get(TREE_START)
    iterate_end = iterate_0.node_tree.nodes.get(TREE_END)
    iterate_depth = iterate_0.node_tree.nodes.get('_depth_from_tex')
    iterate_branch = iterate_0.node_tree.nodes.get('_branch')

    weight = tree.nodes.get('_weight')
    
    for uv in yp.uvs:
        if uv_name != '' and uv.name != uv_name: continue

        # Start and delta uv inputs
        create_link(tree, start.outputs[uv.name + START_UV], depth_source_0.inputs[uv.name + START_UV])
        create_link(tree, start.outputs[uv.name + START_UV], depth_source_1.inputs[uv.name + START_UV])
        create_link(tree, start.outputs[uv.name + START_UV], loop.inputs[uv.name + START_UV])

        create_link(tree, start.outputs[uv.name + DELTA_UV], depth_source_0.inputs[uv.name + DELTA_UV])
        create_link(tree, start.outputs[uv.name + DELTA_UV], depth_source_1.inputs[uv.name + DELTA_UV])
        create_link(tree, start.outputs[uv.name + DELTA_UV], loop.inputs[uv.name + DELTA_UV])

        create_link(tree, depth_source_0.outputs[uv.name + CURRENT_UV], loop.inputs[uv.name + CURRENT_UV])

        # Parallax final mix
        if baked: parallax_mix = tree.nodes.get(uv.baked_parallax_mix)
        else: parallax_mix = tree.nodes.get(uv.parallax_mix)

        create_link(tree, weight.outputs[0], parallax_mix.inputs[0])
        create_link(tree, loop.outputs[uv.name + CURRENT_UV], parallax_mix.inputs[1])
        create_link(tree, depth_source_1.outputs[uv.name + CURRENT_UV], parallax_mix.inputs[2])

        # End uv
        #create_link(tree, loop.outputs[uv.name + CURRENT_UV], end.inputs[uv.name])
        create_link(tree, parallax_mix.outputs[0], end.inputs[uv.name])

        # Inside depth source
        if baked: delta_uv = depth_source_0.node_tree.nodes.get(uv.baked_parallax_delta_uv)
        else: delta_uv = depth_source_0.node_tree.nodes.get(uv.parallax_delta_uv)
        if baked: current_uv = depth_source_0.node_tree.nodes.get(uv.baked_parallax_current_uv)
        else: current_uv = depth_source_0.node_tree.nodes.get(uv.parallax_current_uv)
        height_map = depth_source_0.node_tree.nodes.get(HEIGHT_MAP)

        create_link(depth_source_0.node_tree, depth_start.outputs['index'], delta_uv.inputs[1])
        create_link(depth_source_0.node_tree, depth_start.outputs[uv.name + DELTA_UV], delta_uv.inputs[2])

        create_link(depth_source_0.node_tree, depth_start.outputs[uv.name + START_UV], current_uv.inputs[0])
        create_link(depth_source_0.node_tree, delta_uv.outputs[0], current_uv.inputs[1])

        create_link(depth_source_0.node_tree, current_uv.outputs[0], depth_end.inputs[uv.name + CURRENT_UV])

        if height_map:
            create_link(depth_source_0.node_tree, current_uv.outputs[0], height_map.inputs[0])
            create_link(depth_source_0.node_tree, height_map.outputs[0], depth_end.inputs[0])

        # Inside iteration
        create_link(iterate_0.node_tree, 
                iterate_start.outputs[uv.name + START_UV], iterate_depth.inputs[uv.name + START_UV])
        create_link(iterate_0.node_tree, 
                iterate_start.outputs[uv.name + DELTA_UV], iterate_depth.inputs[uv.name + DELTA_UV])

        if baked: parallax_current_uv_mix = iterate_0.node_tree.nodes.get(uv.baked_parallax_current_uv_mix)
        else: parallax_current_uv_mix = iterate_0.node_tree.nodes.get(uv.parallax_current_uv_mix)

        create_link(iterate_0.node_tree, iterate_branch.outputs[0], parallax_current_uv_mix.inputs[0])
        create_link(iterate_0.node_tree, 
                iterate_depth.outputs[uv.name + CURRENT_UV], parallax_current_uv_mix.inputs[1])
        create_link(iterate_0.node_tree, 
                iterate_start.outputs[uv.name + CURRENT_UV], parallax_current_uv_mix.inputs[2])

        create_link(iterate_0.node_tree, 
                parallax_current_uv_mix.outputs[0], iterate_end.inputs[uv.name + CURRENT_UV])

    if not baked:
        for tc in texcoord_lists:

            base_name = TEXCOORD_IO_PREFIX + tc
            if base_name + START_UV not in start.outputs: continue

            # Start and delta uv inputs
            create_link(tree, start.outputs[base_name + START_UV], depth_source_0.inputs[base_name + START_UV])
            create_link(tree, start.outputs[base_name + START_UV], depth_source_1.inputs[base_name + START_UV])
            create_link(tree, start.outputs[base_name + START_UV], loop.inputs[base_name + START_UV])

            create_link(tree, start.outputs[base_name + DELTA_UV], depth_source_0.inputs[base_name + DELTA_UV])
            create_link(tree, start.outputs[base_name + DELTA_UV], depth_source_1.inputs[base_name + DELTA_UV])
            create_link(tree, start.outputs[base_name + DELTA_UV], loop.inputs[base_name + DELTA_UV])

            create_link(tree, depth_source_0.outputs[base_name + CURRENT_UV], loop.inputs[base_name + CURRENT_UV])

            # Parallax final mix
            parallax_mix = tree.nodes.get(PARALLAX_MIX_PREFIX + base_name)

            create_link(tree, weight.outputs[0], parallax_mix.inputs[0])
            create_link(tree, loop.outputs[base_name + CURRENT_UV], parallax_mix.inputs[1])
            create_link(tree, depth_source_1.outputs[base_name + CURRENT_UV], parallax_mix.inputs[2])

            # End uv
            create_link(tree, parallax_mix.outputs[0], end.inputs[base_name])

            # Inside depth source
            delta_uv = depth_source_0.node_tree.nodes.get(PARALLAX_DELTA_PREFIX + base_name)
            current_uv = depth_source_0.node_tree.nodes.get(PARALLAX_CURRENT_PREFIX + base_name)

            create_link(depth_source_0.node_tree, depth_start.outputs['index'], delta_uv.inputs[1])
            create_link(depth_source_0.node_tree, depth_start.outputs[base_name + DELTA_UV], delta_uv.inputs[2])

            create_link(depth_source_0.node_tree, depth_start.outputs[base_name + START_UV], current_uv.inputs[0])
            create_link(depth_source_0.node_tree, delta_uv.outputs[0], current_uv.inputs[1])

            create_link(depth_source_0.node_tree, current_uv.outputs[0], depth_end.inputs[base_name + CURRENT_UV])

            # Inside iteration
            create_link(iterate_0.node_tree, 
                    iterate_start.outputs[base_name + START_UV], iterate_depth.inputs[base_name + START_UV])
            create_link(iterate_0.node_tree, 
                    iterate_start.outputs[base_name + DELTA_UV], iterate_depth.inputs[base_name + DELTA_UV])

            parallax_current_uv_mix = iterate_0.node_tree.nodes.get(PARALLAX_CURRENT_MIX_PREFIX + base_name)

            create_link(iterate_0.node_tree, iterate_branch.outputs[0], parallax_current_uv_mix.inputs[0])
            create_link(iterate_0.node_tree, 
                    iterate_depth.outputs[base_name + CURRENT_UV], parallax_current_uv_mix.inputs[1])
            create_link(iterate_0.node_tree, 
                    iterate_start.outputs[base_name + CURRENT_UV], parallax_current_uv_mix.inputs[2])

            create_link(iterate_0.node_tree, 
                    parallax_current_uv_mix.outputs[0], iterate_end.inputs[base_name + CURRENT_UV])

    reconnect_parallax_layer_nodes(group_tree, parallax, uv_name)

def reconnect_depth_layer_nodes(group_tree, parallax_ch, parallax):

    yp = group_tree.yp

    depth_source_0 = parallax.node_tree.nodes.get('_depth_source_0')
    tree = depth_source_0.node_tree

    start = tree.nodes.get(TREE_START)
    end = tree.nodes.get(TREE_END)

    pack = tree.nodes.get('_pack')

    io_disp_name = parallax_ch.name + io_suffix['HEIGHT']
    io_alpha_name = parallax_ch.name + io_suffix['ALPHA']
    io_disp_alpha_name = parallax_ch.name + io_suffix['HEIGHT'] + io_suffix['ALPHA']

    height = start.outputs['base']

    for i, layer in reversed(list(enumerate(yp.layers))):

        if layer.parent_idx != -1: continue

        node = tree.nodes.get(layer.depth_group_node)

        height = create_link(tree, height, node.inputs[io_disp_name])[io_disp_name]

        if i == 0:
            create_link(tree, height, pack.inputs[0])
            create_link(tree, pack.outputs[0], end.inputs['depth_from_tex'])

        uv_names = []
        if layer.texcoord_type == 'UV':
            uv_names.append(layer.uv_name)

        for mask in layer.masks:
            if mask.texcoord_type == 'UV' and mask.uv_name not in uv_names:
                uv_names.append(mask.uv_name)

        for uv_name in uv_names:
            inp = node.inputs.get(uv_name + io_suffix['UV'])
            uv = yp.uvs.get(uv_name)
            if not uv: continue
            current_uv = tree.nodes.get(uv.parallax_current_uv)

            if inp and current_uv: 
                create_link(tree, current_uv.outputs[0], inp)

        for tc in texcoord_lists:
            inp = node.inputs.get(TEXCOORD_IO_PREFIX + tc)
            if not inp: continue
            current_uv = tree.nodes.get(PARALLAX_CURRENT_PREFIX + TEXCOORD_IO_PREFIX + tc)
            if not current_uv: continue
            create_link(tree, current_uv.outputs[0], inp)

    # List of last members
    last_members = []
    for layer in yp.layers:
        if is_bottom_member(layer):
            last_members.append(layer)

            # Remove input links from bottom member
            node = tree.nodes.get(layer.depth_group_node)
            remove_all_prev_inputs(tree, layer, node) #, height_only=True)

        # Remove input links from group with no childrens
        if layer.type == 'GROUP' and not has_childrens(layer):
            node = tree.nodes.get(layer.depth_group_node)
            remove_all_children_inputs(tree, layer, node) #, height_only=True)

    # Group stuff
    for layer in last_members:

        node = tree.nodes.get(layer.depth_group_node)

        cur_layer = layer
        cur_node = node

        #actual_last = True

        while True:
            # Get upper layer
            upper_idx, upper_layer = get_upper_neighbor(cur_layer)
            upper_node = tree.nodes.get(upper_layer.depth_group_node)

            # Connect
            if upper_layer.parent_idx == cur_layer.parent_idx:
                create_link(tree, cur_node.outputs[io_alpha_name], upper_node.inputs[io_alpha_name])
                create_link(tree, cur_node.outputs[io_disp_name], upper_node.inputs[io_disp_name])
                create_link(tree, cur_node.outputs[io_disp_alpha_name], upper_node.inputs[io_disp_alpha_name])
            else:

                create_link(tree, cur_node.outputs[io_disp_name], 
                        upper_node.inputs[io_disp_name + io_suffix['GROUP']])

                create_link(tree, cur_node.outputs[io_alpha_name], 
                        upper_node.inputs[io_alpha_name + io_suffix['GROUP']])

                create_link(tree, cur_node.outputs[io_disp_alpha_name], 
                        upper_node.inputs[io_disp_alpha_name + io_suffix['GROUP']])

                break

            cur_layer = upper_layer
            cur_node = upper_node

def reconnect_yp_nodes(tree, ch_idx=-1):
    yp = tree.yp
    nodes = tree.nodes

    #print('Reconnect tree ' + tree.name)

    start = nodes.get(TREE_START)
    end = nodes.get(TREE_END)
    one_value = nodes.get(ONE_VALUE)
    zero_value = nodes.get(ZERO_VALUE)
    texcoord = nodes.get(TEXCOORD)
    parallax = tree.nodes.get(PARALLAX)
    geometry = tree.nodes.get(GEOMETRY)

    # Parallax
    parallax_ch = get_root_parallax_channel(yp)
    parallax = tree.nodes.get(PARALLAX)
    baked_parallax = tree.nodes.get(BAKED_PARALLAX)

    # UVs

    uv_maps = {}
    tangents = {}
    bitangents = {}

    for uv in yp.uvs:
        #print('Connecting', uv.name)
        uv_map = nodes.get(uv.uv_map)
        uv_maps[uv.name] = uv_map.outputs[0]

        tangent = nodes.get(uv.tangent)
        tangent_flip = nodes.get(uv.tangent_flip)
        create_link(tree, tangent.outputs[0], tangent_flip.inputs[0])
        tangents[uv.name] = tangent_flip.outputs[0]

        bitangent = nodes.get(uv.bitangent)
        bitangent_flip = nodes.get(uv.bitangent_flip)
        create_link(tree, bitangent.outputs[0], bitangent_flip.inputs[0])
        bitangents[uv.name] = bitangent_flip.outputs[0]

    # Get main tangent and bitangent
    tangent = None
    bitangent = None

    height_ch = get_root_height_channel(yp)
    if height_ch and height_ch.main_uv != '':
        uv = yp.uvs.get(height_ch.main_uv)
        if uv:
            tangent = nodes.get(uv.tangent)
            bitangent = nodes.get(uv.bitangent)

    if not tangent and len(yp.uvs) > 0:
        tangent = nodes.get(yp.uvs[0].tangent)
        bitangent = nodes.get(yp.uvs[0].bitangent)

    baked_uv = yp.uvs.get(yp.baked_uv_name)
    if yp.use_baked and baked_uv:
        if parallax_ch and baked_parallax:
            baked_uv_map = baked_parallax.outputs[0]
        else: baked_uv_map = nodes.get(baked_uv.uv_map).outputs[0]

        baked_tangent = nodes.get(baked_uv.tangent_flip).outputs[0]
        baked_bitangent = nodes.get(baked_uv.bitangent_flip).outputs[0]

    # Parallax internal connections
    if parallax_ch:
        if parallax:
            reconnect_parallax_process_nodes(tree, parallax) #, uv_maps, tangents, bitangents)
            reconnect_depth_layer_nodes(tree, parallax_ch, parallax)
        if baked_parallax:
            reconnect_parallax_process_nodes(tree, baked_parallax, True, yp.baked_uv_name) #, uv_maps, tangents, bitangents)

    # Parallax preparations
    for uv in yp.uvs:
        parallax_prep = tree.nodes.get(uv.parallax_prep)
        if parallax_prep:
            #create_link(tree, uv_maps[uv.name], parallax_prep.inputs['UV'])
            create_link(tree, uv_maps[uv.name], parallax_prep.inputs[0])
            create_link(tree, tangents[uv.name], parallax_prep.inputs['Tangent'])
            create_link(tree, bitangents[uv.name], parallax_prep.inputs['Bitangent'])
    
            if parallax:
                create_link(tree, parallax_prep.outputs['start_uv'], parallax.inputs[uv.name + START_UV])
                create_link(tree, parallax_prep.outputs['delta_uv'], parallax.inputs[uv.name + DELTA_UV])

            if baked_parallax and uv.name == yp.baked_uv_name:
                create_link(tree, parallax_prep.outputs['start_uv'], baked_parallax.inputs[uv.name + START_UV])
                create_link(tree, parallax_prep.outputs['delta_uv'], baked_parallax.inputs[uv.name + DELTA_UV])

    # Non UV Parallax preparations
    for tc in texcoord_lists:
        parallax_prep = tree.nodes.get(tc + PARALLAX_PREP_SUFFIX)
        if parallax_prep:
            create_link(tree, texcoord.outputs[tc], parallax_prep.inputs[0])
            create_link(tree, tangent.outputs[0], parallax_prep.inputs['Tangent'])
            create_link(tree, bitangent.outputs[0], parallax_prep.inputs['Bitangent'])
    
            if parallax:
                create_link(tree, parallax_prep.outputs['start_uv'], parallax.inputs[TEXCOORD_IO_PREFIX + tc + START_UV])
                create_link(tree, parallax_prep.outputs['delta_uv'], parallax.inputs[TEXCOORD_IO_PREFIX + tc + DELTA_UV])

    if parallax_ch:
        if parallax:
            disp = start.outputs.get(parallax_ch.name + io_suffix['HEIGHT'])
            if disp: create_link(tree, disp, parallax.inputs['base'])

        if baked_parallax:
            disp = start.outputs.get(parallax_ch.name + io_suffix['HEIGHT'])
            if disp: create_link(tree, disp, baked_parallax.inputs['base'])

    for i, ch in enumerate(yp.channels):
        if ch_idx != -1 and i != ch_idx: continue

        start_linear = nodes.get(ch.start_linear)
        end_linear = nodes.get(ch.end_linear)
        end_max_height = nodes.get(ch.end_max_height)
        start_normal_filter = nodes.get(ch.start_normal_filter)

        io_name = ch.name
        io_alpha_name = ch.name + io_suffix['ALPHA']
        io_disp_name = ch.name + io_suffix['HEIGHT']
        io_disp_n_name = ch.name + io_suffix['HEIGHT'] + ' n'
        io_disp_s_name = ch.name + io_suffix['HEIGHT'] + ' s'
        io_disp_e_name = ch.name + io_suffix['HEIGHT'] + ' e'
        io_disp_w_name = ch.name + io_suffix['HEIGHT'] + ' w'

        #rgb = start.outputs[ch.io_index]
        rgb = start.outputs[io_name]
        if ch.enable_alpha and ch.type == 'RGB':
            #alpha = start.outputs[ch.io_index+1]
            alpha = start.outputs[io_alpha_name]
        else: alpha = one_value.outputs[0]

        #if ch.enable_parallax and ch.type == 'NORMAL':
        #    #disp = start.outputs[ch.io_index+1]
        #    disp = start.outputs[io_disp_name]
        #else: 
        #    #disp = one_value.outputs[0]
        #    disp = None
        if ch.type == 'NORMAL':
            disp = start.outputs[io_disp_name]
        else: disp = None

        #if ch.enable_smooth_bump and ch.type == 'NORMAL':
        #    disp_n = disp
        #    disp_s = disp
        #    disp_e = disp
        #    disp_w = disp
        #else:
        disp_n = disp
        disp_s = disp
        disp_e = disp
        disp_w = disp
        
        if start_linear:
            rgb = create_link(tree, rgb, start_linear.inputs[0])[0]
        elif start_normal_filter:
            rgb = create_link(tree, rgb, start_normal_filter.inputs[0])[0]

        # Background rgb and alpha
        bg_rgb = rgb
        bg_alpha = alpha
        bg_disp = disp

        # Layers loop
        for j, layer in reversed(list(enumerate(yp.layers))):

            node = nodes.get(layer.group_node)

            # UV inputs
            uv_names = []

            if height_ch and height_ch.main_uv != '':
                uv_names.append(height_ch.main_uv)

            if layer.texcoord_type == 'UV' and layer.uv_name not in uv_names:
                uv_names.append(layer.uv_name)

            for mask in layer.masks:
                if mask.texcoord_type == 'UV' and mask.uv_name not in uv_names:
                    uv_names.append(mask.uv_name)

            for uv_name in uv_names:
                uv = yp.uvs.get(uv_name)
                if not uv: continue
                inp = node.inputs.get(uv_name + io_suffix['UV'])
                if inp:
                    if parallax_ch and parallax:
                        create_link(tree, parallax.outputs[uv_name], inp)
                    else: create_link(tree, uv_maps[uv_name], inp)

                inp = node.inputs.get(uv_name + io_suffix['TANGENT'])
                if inp: create_link(tree, tangents[uv_name], inp)

                inp = node.inputs.get(uv_name + io_suffix['BITANGENT'])
                if inp: create_link(tree, bitangents[uv_name], inp)

            # Texcoord inputs
            texcoords = []
            if layer.texcoord_type != 'UV':
                texcoords.append(layer.texcoord_type)

            for mask in layer.masks:
                if mask.texcoord_type != 'UV' and mask.texcoord_type not in texcoords:
                    texcoords.append(mask.texcoord_type)

            for tc in texcoords:
                inp = node.inputs.get(io_names[tc])
                if inp: 
                    if parallax_ch and parallax:
                        create_link(tree, parallax.outputs[TEXCOORD_IO_PREFIX + tc], inp)
                    else: create_link(tree, texcoord.outputs[tc], inp)

            # Background layer
            if layer.type == 'BACKGROUND':
                # Offsets for background layer
                inp = node.inputs.get(ch.name + io_suffix['BACKGROUND'])
                inp_alpha = node.inputs.get(ch.name + io_suffix['ALPHA'] + io_suffix['BACKGROUND'])
                inp_disp = node.inputs.get(ch.name + io_suffix['HEIGHT'] + io_suffix['BACKGROUND'])

                if layer.parent_idx == -1:

                    #create_link(tree, bg_rgb, node.inputs[bg_index])
                    create_link(tree, bg_rgb, inp)
                    #if ch.type =='RGB' and ch.enable_alpha:
                    if inp_alpha:
                        #create_link(tree, bg_alpha, node.inputs[bg_index+1])
                        create_link(tree, bg_alpha, inp_alpha)
                    if inp_disp:
                        create_link(tree, bg_disp, inp_disp)
                else:
                    #break_input_link(tree, node.inputs[bg_index])
                    break_input_link(tree, inp)
                    #if ch.type =='RGB' and ch.enable_alpha:
                    if inp_alpha:
                        #break_input_link(tree, node.inputs[bg_index+1])
                        break_input_link(tree, inp_alpha)
                    if inp_disp:
                        break_input_link(tree, inp_disp)

            if layer.parent_idx != -1: continue

            # Group node with no children need normal input connected
            if layer.type == 'GROUP' and not has_childrens(layer):
                if ch.type == 'NORMAL':
                    #create_link(tree, geometry.outputs['Normal'], node.inputs[ch.name])
                    create_link(tree, geometry.outputs['Normal'], node.inputs[ch.name + io_suffix['GROUP']])

            #rgb = create_link(tree, rgb, node.inputs[ch.io_index])[ch.io_index]
            rgb = create_link(tree, rgb, node.inputs[io_name])[io_name]
            if ch.type =='RGB' and ch.enable_alpha:
                #alpha = create_link(tree, alpha, node.inputs[ch.io_index+1])[ch.io_index+1]
                alpha = create_link(tree, alpha, node.inputs[io_alpha_name])[io_alpha_name]

            #if ch.type =='NORMAL' and ch.enable_parallax:
            if disp:
                #disp = create_link(tree, disp, node.inputs[ch.io_index+1])[ch.io_index+1]
                disp = create_link(tree, disp, node.inputs[io_disp_name])[io_disp_name]

            if ch.type == 'NORMAL' and ch.enable_smooth_bump:
                disp_n = create_link(tree, disp_n, node.inputs[io_disp_n_name])[io_disp_n_name]
                disp_s = create_link(tree, disp_s, node.inputs[io_disp_s_name])[io_disp_s_name]
                disp_e = create_link(tree, disp_e, node.inputs[io_disp_e_name])[io_disp_e_name]
                disp_w = create_link(tree, disp_w, node.inputs[io_disp_w_name])[io_disp_w_name]

        rgb, alpha = reconnect_all_modifier_nodes(tree, ch, rgb, alpha)

        if end_linear:
            if ch.type == 'NORMAL':
                create_link(tree, rgb, end_linear.inputs['Normal Overlay'])[0]
                if end_max_height:
                    create_link(tree, end_max_height.outputs[0], end_linear.inputs['Max Height'])
                
            rgb = create_link(tree, rgb, end_linear.inputs[0])[0]

            if disp:
                disp = create_link(tree, disp, end_linear.inputs[0])[1]
                if ch.enable_smooth_bump:
                    create_link(tree, disp_n, end_linear.inputs['Height n'])
                    create_link(tree, disp_s, end_linear.inputs['Height s'])
                    create_link(tree, disp_e, end_linear.inputs['Height e'])
                    create_link(tree, disp_w, end_linear.inputs['Height w'])

                #print()
                #for i, u in enumerate(yp.uvs):
                #    print(i, u.name)

                if tangent and bitangent:
                    create_link(tree, tangent.outputs[0], end_linear.inputs['Tangent'])
                    create_link(tree, bitangent.outputs[0], end_linear.inputs['Bitangent'])

        if yp.use_baked and baked_uv:
            baked = nodes.get(ch.baked)
            rgb = baked.outputs[0]

        #if yp.use_baked:
        #    baked = nodes.get(ch.baked)
        #    baked_uv_map = nodes.get(BAKED_UV)
        #    baked_tangent = nodes.get(BAKED_TANGENT)
        #    baked_tangent_flip = nodes.get(BAKED_TANGENT_FLIP)
        #    baked_bitangent = nodes.get(BAKED_BITANGENT)
        #    baked_bitangent_flip = nodes.get(BAKED_BITANGENT_FLIP)
        #    baked_parallax = nodes.get(BAKED_PARALLAX)

        #    rgb = baked.outputs[0]

        #    if baked_tangent:
        #        baked_tangent = baked_tangent.outputs[0]

        #        if baked_tangent_flip:
        #            baked_tangent = create_link(tree, baked_tangent, baked_tangent_flip.inputs[0])[0]

        #    if baked_bitangent:
        #        baked_bitangent = baked_bitangent.outputs[0]

        #        if baked_bitangent_flip:
        #            baked_bitangent = create_link(tree, baked_bitangent, baked_bitangent_flip.inputs[0])[0]

        #    baked_uv_map = baked_uv_map.outputs[0]
        #    if baked_parallax:
        #        reconnect_baked_parallax_layer_nodes(yp, baked_parallax)

        #        create_link(tree, baked_uv_map, baked_parallax.inputs['UV'])
        #        create_link(tree, baked_tangent, baked_parallax.inputs['Tangent'])
        #        create_link(tree, baked_bitangent, baked_parallax.inputs['Bitangent'])

        #        baked_uv_map = baked_parallax.outputs[0]

        #    create_link(tree, baked_uv_map, baked.inputs[0])

            if ch.type == 'NORMAL':
                baked_normal = nodes.get(ch.baked_normal)
                rgb = create_link(tree, rgb, baked_normal.inputs[1])[0]

                baked_normal_flip = nodes.get(ch.baked_normal_flip)
                if baked_normal_flip:

                    create_link(tree, baked_tangent, baked_normal_flip.inputs['Tangent'])
                    create_link(tree, baked_bitangent, baked_normal_flip.inputs['Bitangent'])

                    rgb = create_link(tree, rgb, baked_normal_flip.inputs[0])[0]

                #if ch.enable_parallax:
                baked_disp = nodes.get(ch.baked_disp)
                if baked_disp: 
                    disp = baked_disp.outputs[0]
                    create_link(tree, baked_uv_map, baked_disp.inputs[0])

            if ch.type == 'RGB' and ch.enable_alpha:
                alpha = baked.outputs[1]

            create_link(tree, baked_uv_map, baked.inputs[0])

        #create_link(tree, rgb, end.inputs[ch.io_index])
        create_link(tree, rgb, end.inputs[io_name])
        if ch.type == 'RGB' and ch.enable_alpha:
            #create_link(tree, alpha, end.inputs[ch.io_index+1])
            create_link(tree, alpha, end.inputs[io_alpha_name])
        if ch.type == 'NORMAL': #and ch.enable_parallax:
            #create_link(tree, disp, end.inputs[ch.io_index+1])
            create_link(tree, disp, end.inputs[io_disp_name])
            if end_max_height and ch.name + io_suffix['MAX HEIGHT'] in end.inputs:
                create_link(tree, end_max_height.outputs[0], end.inputs[ch.name + io_suffix['MAX HEIGHT']])

    # List of last members
    last_members = []
    for layer in yp.layers:
        if is_bottom_member(layer):
            last_members.append(layer)

            # Remove input links from bottom member
            node = tree.nodes.get(layer.group_node)
            remove_all_prev_inputs(tree, layer, node)

        # Remove input links from group with no childrens
        if layer.type == 'GROUP' and not has_childrens(layer):
            node = tree.nodes.get(layer.group_node)
            remove_all_children_inputs(tree, layer, node)

    #print(last_members)

    # Group stuff
    for layer in last_members:

        node = nodes.get(layer.group_node)

        cur_layer = layer
        cur_node = node

        actual_last = True

        while True:
            # Get upper layer
            upper_idx, upper_layer = get_upper_neighbor(cur_layer)
            upper_node = nodes.get(upper_layer.group_node)

            #print(upper_layer.name)

            # Should always fill normal input
            if actual_last:
                for i, ch in enumerate(layer.channels):
                    root_ch = yp.channels[i]
                    if root_ch.type == 'NORMAL':

                        create_link(tree, geometry.outputs['Normal'], node.inputs[root_ch.name])
                        if layer.type == 'GROUP' and not has_childrens(layer):
                            create_link(tree, geometry.outputs['Normal'], node.inputs[root_ch.name + io_suffix['GROUP']])

                actual_last = False

            # Height should still connected to previous layer
            #if actual_last and layer.type != 'GROUP':
            #    idx = get_layer_index(layer)

            #    for i, ch in enumerate(layer.channels):
            #        root_ch = yp.channels[i]
            #        if root_ch.type == 'NORMAL':

            #            if idx != len(yp.layers)-1:
            #                # Connect to previous layer height
            #                lower_node = nodes.get(yp.layers[idx+1].group_node)
            #                create_link(tree, lower_node.outputs[root_ch.name + io_suffix['HEIGHT']],
            #                        upper_node.inputs[root_ch.name + io_suffix['HEIGHT']])

            #                # Neighbor heights are also need connection
            #                if root_ch.enable_smooth_bump:
            #                    for d in neighbor_directions:
            #                        create_link(tree, 
            #                                lower_node.outputs[root_ch.name + io_suffix['HEIGHT'] + ' ' + d],
            #                                upper_node.inputs[root_ch.name + io_suffix['HEIGHT']])
            #            else:
            #                # Connect to start height
            #                create_link(tree, start.outputs[root_ch.name + io_suffix['HEIGHT']],
            #                        upper_node.inputs[root_ch.name + io_suffix['HEIGHT']])
            #            break
            #    actual_last = False

            # Connect
            if upper_layer.parent_idx == cur_layer.parent_idx:
                for i, outp in enumerate(cur_node.outputs):
                    create_link(tree, outp, upper_node.inputs[i])
            else:

                for i, outp in enumerate(cur_node.outputs):
                    create_link(tree, outp, upper_node.inputs[outp.name + io_suffix['GROUP']])

                break

            cur_layer = upper_layer
            cur_node = upper_node

        #print(upper_layer.name)

def reconnect_source_internal_nodes(layer):
    tree = get_source_tree(layer)

    source = tree.nodes.get(layer.source)
    mapping = tree.nodes.get(layer.mapping)
    start = tree.nodes.get(TREE_START)
    solid = tree.nodes.get(ONE_VALUE)
    end = tree.nodes.get(TREE_END)

    #if layer.type != 'VCOL':
    #    create_link(tree, start.outputs[0], source.inputs[0])
    if mapping:
        create_link(tree, start.outputs[0], mapping.inputs[0])
        create_link(tree, mapping.outputs[0], source.inputs[0])
    else:
        create_link(tree, start.outputs[0], source.inputs[0])

    rgb = source.outputs[0]
    alpha = source.outputs[1]
    if layer.type not in {'IMAGE', 'VCOL'}:
        rgb_1 = source.outputs[1]
        alpha = solid.outputs[0]
        alpha_1 = solid.outputs[0]

        mod_group = tree.nodes.get(layer.mod_group)
        if mod_group:
            rgb, alpha = reconnect_all_modifier_nodes(tree, layer, rgb, alpha, mod_group)

        mod_group_1 = tree.nodes.get(layer.mod_group_1)
        if mod_group_1:
            rgb_1 = create_link(tree, rgb_1, mod_group_1.inputs[0])[0]
            alpha_1 = create_link(tree, alpha_1, mod_group_1.inputs[1])[1]

        create_link(tree, rgb_1, end.inputs[2])
        create_link(tree, alpha_1, end.inputs[3])

    if layer.type in {'IMAGE', 'VCOL'}:

        rgb, alpha = reconnect_all_modifier_nodes(tree, layer, rgb, alpha)

    create_link(tree, rgb, end.inputs[0])
    create_link(tree, alpha, end.inputs[1])

def reconnect_mask_internal_nodes(mask):

    tree = get_mask_tree(mask)

    source = tree.nodes.get(mask.source)
    mapping = tree.nodes.get(mask.mapping)
    start = tree.nodes.get(TREE_START)
    end = tree.nodes.get(TREE_END)

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

def reconnect_layer_nodes(layer, ch_idx=-1):
    yp = layer.id_data.yp

    #print('Reconnect layer ' + layer.name)
    if yp.halt_reconnect: return

    tree = get_tree(layer)
    nodes = tree.nodes

    start = nodes.get(TREE_START)
    end = nodes.get(TREE_END)
    one_value = nodes.get(ONE_VALUE)

    source_group = nodes.get(layer.source_group)

    #if layer.source_group != '':
    if source_group:
        source = source_group
        reconnect_source_internal_nodes(layer)
    else: source = nodes.get(layer.source)

    # Direction sources
    source_n = nodes.get(layer.source_n)
    source_s = nodes.get(layer.source_s)
    source_e = nodes.get(layer.source_e)
    source_w = nodes.get(layer.source_w)

    uv_map = nodes.get(layer.uv_map)
    uv_neighbor = nodes.get(layer.uv_neighbor)

    if layer.type == 'GROUP':
        texcoord = source
    else: texcoord = nodes.get(layer.texcoord)

    #texcoord = nodes.get(TEXCOORD)
    geometry = nodes.get(GEOMETRY)
    mapping = nodes.get(layer.mapping)

    # Get tangent and bitangent
    layer_tangent = texcoord.outputs.get(layer.uv_name + io_suffix['TANGENT'])
    layer_bitangent = texcoord.outputs.get(layer.uv_name + io_suffix['BITANGENT'])

    height_root_ch = get_root_height_channel(yp)
    if height_root_ch and height_root_ch.main_uv != '':
        tangent = texcoord.outputs.get(height_root_ch.main_uv + io_suffix['TANGENT'])
        bitangent = texcoord.outputs.get(height_root_ch.main_uv + io_suffix['BITANGENT'])
    else:
        tangent = layer_tangent
        bitangent = layer_bitangent

    # Texcoord
    if layer.type not in {'VCOL', 'BACKGROUND', 'COLOR', 'GROUP'}:
        if layer.texcoord_type == 'UV':
            #vector = uv_map.outputs[0]
            vector = texcoord.outputs.get(layer.uv_name + io_suffix['UV'])
        else: 
            vector = texcoord.outputs[io_names[layer.texcoord_type]]

        if source_group or not mapping:
            create_link(tree, vector, source.inputs[0])
        elif mapping:
            create_link(tree, vector, mapping.inputs[0])
            create_link(tree, mapping.outputs[0], source.inputs[0])

        if uv_neighbor: 
            create_link(tree, vector, uv_neighbor.inputs[0])

            if 'Tangent' in uv_neighbor.inputs:
                create_link(tree, tangent, uv_neighbor.inputs['Tangent'])
                create_link(tree, bitangent, uv_neighbor.inputs['Bitangent'])

            if 'Entity Tangent' in uv_neighbor.inputs:
                create_link(tree, layer_tangent, uv_neighbor.inputs['Entity Tangent'])
                create_link(tree, layer_bitangent, uv_neighbor.inputs['Entity Bitangent'])

            if 'Mask Tangent' in uv_neighbor.inputs:
                create_link(tree, layer_tangent, uv_neighbor.inputs['Mask Tangent'])
                create_link(tree, layer_bitangent, uv_neighbor.inputs['Mask Bitangent'])

            #if 'Tangent' in uv_neighbor.inputs:
            #    create_link(tree, tangent, uv_neighbor.inputs['Tangent'])
            #if 'Bitangent' in uv_neighbor.inputs:
            #    create_link(tree, bitangent, uv_neighbor.inputs['Bitangent'])

            if source_n: create_link(tree, uv_neighbor.outputs['n'], source_n.inputs[0])
            if source_s: create_link(tree, uv_neighbor.outputs['s'], source_s.inputs[0])
            if source_e: create_link(tree, uv_neighbor.outputs['e'], source_e.inputs[0])
            if source_w: create_link(tree, uv_neighbor.outputs['w'], source_w.inputs[0])

    # RGB
    start_rgb = source.outputs[0]
    start_rgb_1 = None
    if layer.type != 'COLOR':
        start_rgb_1 = source.outputs[1]

    # Alpha
    if layer.type == 'IMAGE' or source_group:
        start_alpha = source.outputs[1]
    else: start_alpha = one_value.outputs[0]
    start_alpha_1 = one_value.outputs[0]

    if source_group and layer.type not in {'IMAGE', 'VCOL', 'BACKGROUND'}:
        start_rgb_1 = source_group.outputs[2]
        start_alpha_1 = source_group.outputs[3]

    elif not source_group:

        # Layer source modifier
        mod_group = nodes.get(layer.mod_group)

        # Background layer won't use modifier outputs
        if layer.type in {'BACKGROUND', 'GROUP'}:
            #reconnect_all_modifier_nodes(tree, layer, start_rgb, start_alpha, mod_group)
            pass
        else:
            start_rgb, start_alpha = reconnect_all_modifier_nodes(
                    tree, layer, start_rgb, start_alpha, mod_group)

        if layer.type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'COLOR', 'GROUP'}:
            mod_group_1 = nodes.get(layer.mod_group_1)
            start_rgb_1, start_alpha_1 = reconnect_all_modifier_nodes(
                    tree, layer, source.outputs[1], one_value.outputs[0], mod_group_1)

    # UV neighbor vertex color
    if layer.type in {'VCOL', 'GROUP'} and uv_neighbor:
        if layer.type == 'VCOL':
            create_link(tree, start_rgb, uv_neighbor.inputs[0])

        create_link(tree, tangent, uv_neighbor.inputs['Tangent'])
        create_link(tree, bitangent, uv_neighbor.inputs['Bitangent'])

    # Get transition bump channel
    trans_bump_flip = False
    trans_bump_crease = False
    #fine_bump_ch = False
    trans_bump_ch = get_transition_bump_channel(layer)
    if trans_bump_ch:
        trans_bump_flip = trans_bump_ch.transition_bump_flip #or layer.type == 'BACKGROUND'
        trans_bump_crease = trans_bump_ch.transition_bump_crease and not trans_bump_flip
        #trans_bump_flip = trans_bump_ch.transition_bump_flip
        #fine_bump_ch = trans_bump_ch.transition_bump_type in {'FINE_BUMP_MAP', 'CURVED_BUMP_MAP'}

    # Get normal/height channel
    height_ch = get_height_channel(layer)
    if height_ch and height_ch.normal_blend_type == 'COMPARE':
        compare_alpha = nodes.get(height_ch.height_blend).outputs[1]
    else: compare_alpha = None

    chain = -1
    if trans_bump_ch:
        #if trans_bump_ch.write_height:
        #    chain = 10000
        #else: 
        chain = min(len(layer.masks), trans_bump_ch.transition_bump_chain)

    # Layer Masks
    for i, mask in enumerate(layer.masks):

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
        #mask_uv_map = nodes.get(mask.uv_map)
        if mask.type != 'VCOL':
            if mask.texcoord_type == 'UV':
                #mask_vector = mask_uv_map.outputs[0]
                #mask_vector = mask_uv_map.outputs[0]
                mask_vector = texcoord.outputs.get(mask.uv_name + io_suffix['UV'])
            else: 
                mask_vector = texcoord.outputs[io_names[mask.texcoord_type]]

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
                    #create_link(tree, mask_uv_map.outputs[0], mask_uv_neighbor.inputs[0])
                    create_link(tree, mask_vector, mask_uv_neighbor.inputs[0])
                else: 
                    #create_link(tree, texcoord.outputs[mask.texcoord_type], mask_uv_neighbor.inputs[0])
                    create_link(tree, texcoord.outputs[io_names[mask.texcoord_type]],
                            mask_uv_neighbor.inputs[0])

                create_link(tree, mask_uv_neighbor.outputs['n'], mask_source_n.inputs[0])
                create_link(tree, mask_uv_neighbor.outputs['s'], mask_source_s.inputs[0])
                create_link(tree, mask_uv_neighbor.outputs['e'], mask_source_e.inputs[0])
                create_link(tree, mask_uv_neighbor.outputs['w'], mask_source_w.inputs[0])

            # Mask tangent
            mask_tangent = texcoord.outputs.get(mask.uv_name + io_suffix['TANGENT'])
            mask_bitangent = texcoord.outputs.get(mask.uv_name + io_suffix['BITANGENT'])

            if 'Tangent' in mask_uv_neighbor.inputs:
                create_link(tree, tangent, mask_uv_neighbor.inputs['Tangent'])
                create_link(tree, bitangent, mask_uv_neighbor.inputs['Bitangent'])

            if 'Mask Tangent' in mask_uv_neighbor.inputs:
                create_link(tree, mask_tangent, mask_uv_neighbor.inputs['Mask Tangent'])
                create_link(tree, mask_bitangent, mask_uv_neighbor.inputs['Mask Bitangent'])

            if 'Entity Tangent' in mask_uv_neighbor.inputs:
                create_link(tree, mask_tangent, mask_uv_neighbor.inputs['Entity Tangent'])
                create_link(tree, mask_bitangent, mask_uv_neighbor.inputs['Entity Bitangent'])

        # Mask channels
        for j, c in enumerate(mask.channels):
            root_ch = yp.channels[j]
            ch = layer.channels[j]

            mask_mix = nodes.get(c.mix)
            create_link(tree, mask_val, mask_mix.inputs[2])

            # Direction multiplies
            mix_pure = nodes.get(c.mix_pure)
            mix_remains = nodes.get(c.mix_remains)
            mix_normal = nodes.get(c.mix_normal)
            mix_n = nodes.get(c.mix_n)
            mix_s = nodes.get(c.mix_s)
            mix_e = nodes.get(c.mix_e)
            mix_w = nodes.get(c.mix_w)

            if mix_pure:
                create_link(tree, mask_val, mix_pure.inputs[2])

            if mix_remains:
                create_link(tree, mask_val, mix_remains.inputs[2])

            if mix_normal:
                create_link(tree, mask_val, mix_normal.inputs[2])

            if mask.type == 'VCOL':
                if mix_n: 
                    if mask_uv_neighbor:
                        create_link(tree, mask_uv_neighbor.outputs['n'], mix_n.inputs[2])
                    else: create_link(tree, mask_val, mix_n.inputs[2])

                if mix_s: create_link(tree, mask_uv_neighbor.outputs['s'], mix_s.inputs[2])
                if mix_e: create_link(tree, mask_uv_neighbor.outputs['e'], mix_e.inputs[2])
                if mix_w: create_link(tree, mask_uv_neighbor.outputs['w'], mix_w.inputs[2])
            else:
                if mix_n:
                    if mask_source_n: 
                        create_link(tree, mask_source_n.outputs[0], mix_n.inputs[2])
                    else: create_link(tree, mask_val, mix_n.inputs[2])

                if mix_s and mask_source_s: create_link(tree, mask_source_s.outputs[0], mix_s.inputs[2])
                if mix_e and mask_source_e: create_link(tree, mask_source_e.outputs[0], mix_e.inputs[2])
                if mix_w and mask_source_w: create_link(tree, mask_source_w.outputs[0], mix_w.inputs[2])

    # Parent flag
    has_parent = layer.parent_idx != -1

    # Layer Channels
    for i, ch in enumerate(layer.channels):

        root_ch = yp.channels[i]

        # Rgb and alpha start
        rgb = start_rgb
        alpha = start_alpha
        bg_alpha = None

        prev_rgb = start.outputs.get(root_ch.name)
        prev_alpha = start.outputs.get(root_ch.name + io_suffix['ALPHA'])

        height_alpha = None
        normal_alpha = None

        if layer.type == 'GROUP':
            if root_ch.type == 'NORMAL' and ch.enable_transition_bump:
                rgb = source.outputs.get(root_ch.name + ' Height' + io_suffix['GROUP'])
            else:
                rgb = source.outputs.get(root_ch.name + io_suffix['GROUP'])

            if root_ch.type == 'NORMAL':
                alpha = source.outputs.get(root_ch.name + io_suffix['HEIGHT'] + io_suffix['ALPHA'] + io_suffix['GROUP'])
                height_alpha = source.outputs.get(root_ch.name + io_suffix['HEIGHT'] + io_suffix['ALPHA'] + io_suffix['GROUP'])
                normal_alpha = source.outputs.get(root_ch.name + io_suffix['ALPHA'] + io_suffix['GROUP'])
            else:
                alpha = source.outputs.get(root_ch.name + io_suffix['ALPHA'] + io_suffix['GROUP'])

        elif layer.type == 'BACKGROUND':
            rgb = source.outputs[root_ch.name + io_suffix['BACKGROUND']]
            alpha = one_value.outputs[0]

            if root_ch.enable_alpha:
                bg_alpha = source.outputs[root_ch.name + io_suffix['ALPHA'] + io_suffix['BACKGROUND']]

        if layer.type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'COLOR'}:
            if ch.layer_input == 'ALPHA':
                rgb = start_rgb_1
                alpha = start_alpha_1

        if ch_idx != -1 and i != ch_idx: continue

        intensity = nodes.get(ch.intensity)
        intensity_multiplier = nodes.get(ch.intensity_multiplier)
        extra_alpha = nodes.get(ch.extra_alpha)
        blend = nodes.get(ch.blend)

        linear = nodes.get(ch.linear)
        if linear:
            create_link(tree, rgb, linear.inputs[0])
            rgb = linear.outputs[0]

        mod_group = nodes.get(ch.mod_group)

        rgb_before_mod = rgb
        alpha_before_mod = alpha

        # Background layer won't use modifier outputs
        #if layer.type == 'BACKGROUND' or (layer.type == 'COLOR' and root_ch.type == 'NORMAL'):
        #if layer.type == 'BACKGROUND':
        if layer.type == 'BACKGROUND' or (layer.type == 'GROUP' and root_ch.type == 'NORMAL'):
            #reconnect_all_modifier_nodes(tree, ch, rgb, alpha, mod_group)
            pass
        else:
            rgb, alpha = reconnect_all_modifier_nodes(tree, ch, rgb, alpha, mod_group)

        rgb_after_mod = rgb
        alpha_after_mod = alpha

        # For transition input
        transition_input = alpha
        if chain == 0 and intensity_multiplier:
            alpha = create_link(tree, alpha, intensity_multiplier.inputs[0])[0]

        # Mask multiplies
        for j, mask in enumerate(layer.masks):
            mask_mix = nodes.get(mask.channels[i].mix)
            alpha = create_link(tree, alpha, mask_mix.inputs[1])[0]

            if j == chain-1 and intensity_multiplier:
                transition_input = alpha
                alpha = create_link(tree, alpha, intensity_multiplier.inputs[0])[0]

        # If transition bump is not found, use last alpha as input
        if not trans_bump_ch:
            transition_input = alpha

        # Bookmark alpha before intensity because it can be useful
        alpha_before_intensity = alpha

        # Pass alpha to intensity
        if intensity:
            alpha = create_link(tree, alpha, intensity.inputs[0])[0]

        if root_ch.type == 'NORMAL':

            height_proc = nodes.get(ch.height_proc)
            normal_proc = nodes.get(ch.normal_proc)

            height_blend = nodes.get(ch.height_blend)
            height_blends = {}
            for d in neighbor_directions:
                height_blends[d] = nodes.get(getattr(ch, 'height_blend_' + d))

            spread_alpha = nodes.get(ch.spread_alpha)
            spread_alpha_n = nodes.get(ch.spread_alpha_n)
            spread_alpha_s = nodes.get(ch.spread_alpha_s)
            spread_alpha_e = nodes.get(ch.spread_alpha_e)
            spread_alpha_w = nodes.get(ch.spread_alpha_w)

            prev_height = start.outputs.get(root_ch.name + io_suffix['HEIGHT'])
            next_height = end.inputs.get(root_ch.name + io_suffix['HEIGHT'])

            prev_heights = {}
            next_heights = {}
            next_alphas = {}
            prev_alphas = {}

            if root_ch.enable_smooth_bump:
                for d in neighbor_directions:
                    prev_heights[d] = start.outputs.get(root_ch.name + io_suffix['HEIGHT'] + ' ' + d)
                    next_heights[d] = end.inputs.get(root_ch.name + io_suffix['HEIGHT'] + ' ' + d)
                    prev_alphas[d] = start.outputs.get(root_ch.name + io_suffix['ALPHA'] + ' ' + d)
                    next_alphas[d] = end.inputs.get(root_ch.name + io_suffix['ALPHA'] + ' ' + d)

            # Get neighbor rgb
            if source_n and source_s and source_e and source_w:
                if layer.type not in {'IMAGE', 'VCOL'} and ch.layer_input == 'ALPHA':
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

            elif layer.type == 'VCOL' and uv_neighbor:
                rgb_n = uv_neighbor.outputs['n']
                rgb_s = uv_neighbor.outputs['s']
                rgb_e = uv_neighbor.outputs['e']
                rgb_w = uv_neighbor.outputs['w']

                alpha_n = start_alpha
                alpha_s = start_alpha
                alpha_e = start_alpha
                alpha_w = start_alpha

            elif layer.type == 'GROUP':
                rgb_n = source.outputs.get(root_ch.name + io_suffix['HEIGHT'] + ' n' + io_suffix['GROUP'])
                rgb_s = source.outputs.get(root_ch.name + io_suffix['HEIGHT'] + ' s' + io_suffix['GROUP'])
                rgb_e = source.outputs.get(root_ch.name + io_suffix['HEIGHT'] + ' e' + io_suffix['GROUP'])
                rgb_w = source.outputs.get(root_ch.name + io_suffix['HEIGHT'] + ' w' + io_suffix['GROUP'])

                alpha_n = source.outputs.get(root_ch.name + io_suffix['ALPHA'] + ' n' + io_suffix['GROUP'])
                alpha_s = source.outputs.get(root_ch.name + io_suffix['ALPHA'] + ' s' + io_suffix['GROUP'])
                alpha_e = source.outputs.get(root_ch.name + io_suffix['ALPHA'] + ' e' + io_suffix['GROUP'])
                alpha_w = source.outputs.get(root_ch.name + io_suffix['ALPHA'] + ' w' + io_suffix['GROUP'])

            elif ch.enable_transition_bump and uv_neighbor:
                create_link(tree, alpha_after_mod, uv_neighbor.inputs[0])

                rgb_n = rgb_before_mod
                rgb_s = rgb_before_mod
                rgb_e = rgb_before_mod
                rgb_w = rgb_before_mod

                alpha_n = uv_neighbor.outputs['n']
                alpha_s = uv_neighbor.outputs['s']
                alpha_e = uv_neighbor.outputs['e']
                alpha_w = uv_neighbor.outputs['w']

            else:
                alpha_n = alpha_after_mod
                alpha_s = alpha_after_mod
                alpha_e = alpha_after_mod
                alpha_w = alpha_after_mod

                rgb_n = rgb
                rgb_s = rgb
                rgb_e = rgb
                rgb_w = rgb

            if layer.type != 'BACKGROUND' and not (layer.type == 'GROUP' and root_ch.type == 'NORMAL'):
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
            if ch.normal_blend_type == 'OVERLAY':
                create_link(tree, tangent, blend.inputs['Tangent'])
                create_link(tree, bitangent, blend.inputs['Bitangent'])

            #if layer.type not in {'BACKGROUND', 'GROUP'}: #, 'COLOR'}:

            if ch.normal_map_type == 'NORMAL_MAP':
                create_link(tree, rgb, normal_proc.inputs['Normal Map'])

            if ch.write_height:
                chain_local = len(layer.masks)
            else: chain_local = min(len(layer.masks), ch.transition_bump_chain)

            if spread_alpha:
                rgb = create_link(tree, rgb, spread_alpha.inputs['Color'])[0]
                create_link(tree, alpha_after_mod, spread_alpha.inputs['Alpha'])

                if spread_alpha_n:
                    rgb_n = create_link(tree, rgb_n, spread_alpha_n.inputs['Color'])[0]
                    rgb_s = create_link(tree, rgb_s, spread_alpha_s.inputs['Color'])[0]
                    rgb_e = create_link(tree, rgb_e, spread_alpha_e.inputs['Color'])[0]
                    rgb_w = create_link(tree, rgb_w, spread_alpha_w.inputs['Color'])[0]

                    create_link(tree, alpha_n, spread_alpha_n.inputs['Alpha'])
                    create_link(tree, alpha_s, spread_alpha_s.inputs['Alpha'])
                    create_link(tree, alpha_e, spread_alpha_e.inputs['Alpha'])
                    create_link(tree, alpha_w, spread_alpha_w.inputs['Alpha'])

            #if not trans_bump_ch:
            #chain_local = min(len(layer.masks), ch.transition_bump_chain)

            end_chain = alpha_after_mod
            end_chain_n = alpha_n
            end_chain_s = alpha_s
            end_chain_e = alpha_e
            end_chain_w = alpha_w

            end_chain_crease = alpha_after_mod
            end_chain_crease_n = alpha_n
            end_chain_crease_s = alpha_s
            end_chain_crease_e = alpha_e
            end_chain_crease_w = alpha_w

            pure = alpha_after_mod
            remains = one_value.outputs[0]

            tb_falloff = nodes.get(ch.tb_falloff)
            tb_falloff_n = nodes.get(ch.tb_falloff_n)
            tb_falloff_s = nodes.get(ch.tb_falloff_s)
            tb_falloff_e = nodes.get(ch.tb_falloff_e)
            tb_falloff_w = nodes.get(ch.tb_falloff_w)

            if chain == 0 or len(layer.masks) == 0:
                if tb_falloff:
                    end_chain = pure = create_link(tree, end_chain, tb_falloff.inputs[0])[0]
                if tb_falloff_n:
                    end_chain_n = alpha_n = create_link(tree, end_chain_n, tb_falloff_n.inputs[0])[0]
                    end_chain_s = alpha_s = create_link(tree, end_chain_s, tb_falloff_s.inputs[0])[0]
                    end_chain_e = alpha_e = create_link(tree, end_chain_e, tb_falloff_e.inputs[0])[0]
                    end_chain_w = alpha_w = create_link(tree, end_chain_w, tb_falloff_w.inputs[0])[0]

            for j, mask in enumerate(layer.masks):
                #if j < chain: break
                #if not ch.write_height and j >= chain_local:
                #    break

                c = mask.channels[i]

                mix = nodes.get(c.mix)
                mix_n = nodes.get(c.mix_n)
                mix_s = nodes.get(c.mix_s)
                mix_e = nodes.get(c.mix_e)
                mix_w = nodes.get(c.mix_w)

                if tb_falloff and (j == chain-1 or (j == chain_local-1 and not trans_bump_ch)):
                    pure = tb_falloff.outputs[0]
                elif j < chain:
                    pure = mix.outputs[0]
                else:
                    mix_pure = nodes.get(c.mix_pure)
                    if mix_pure: pure = create_link(tree, pure, mix_pure.inputs[1])[0]

                if j >= chain:
                    mix_remains = nodes.get(c.mix_remains)
                    if mix_remains: remains = create_link(tree, remains, mix_remains.inputs[1])[0]

                mix_normal = nodes.get(c.mix_normal)
                if mix_normal and normal_alpha: 
                    normal_alpha = create_link(tree, normal_alpha, mix_normal.inputs[1])[0]

                if j == chain and trans_bump_ch == ch and trans_bump_crease:
                    if mix_n: alpha_n = create_link(tree, one_value.outputs[0], mix_n.inputs[1])[0]
                    if mix_s: alpha_s = create_link(tree, one_value.outputs[0], mix_s.inputs[1])[0]
                    if mix_e: alpha_e = create_link(tree, one_value.outputs[0], mix_e.inputs[1])[0]
                    if mix_w: alpha_w = create_link(tree, one_value.outputs[0], mix_w.inputs[1])[0]
                else:
                    if mix_n: alpha_n = create_link(tree, alpha_n, mix_n.inputs[1])[0]
                    if mix_s: alpha_s = create_link(tree, alpha_s, mix_s.inputs[1])[0]
                    if mix_e: alpha_e = create_link(tree, alpha_e, mix_e.inputs[1])[0]
                    if mix_w: alpha_w = create_link(tree, alpha_w, mix_w.inputs[1])[0]

                if j == chain-1 or (j == chain_local-1 and not trans_bump_ch):
                    
                    end_chain_crease = mix.outputs[0]
                    end_chain_crease_n = alpha_n
                    end_chain_crease_s = alpha_s
                    end_chain_crease_e = alpha_e
                    end_chain_crease_w = alpha_w

                    if tb_falloff:
                        create_link(tree, mix.outputs[0], tb_falloff.inputs[0])[0]
                        end_chain = tb_falloff.outputs[0]
                    else: 
                        end_chain = mix.outputs[0]

                    if tb_falloff_n: 
                        end_chain_n = alpha_n = create_link(tree, alpha_n, tb_falloff_n.inputs[0])[0]
                        end_chain_s = alpha_s = create_link(tree, alpha_s, tb_falloff_s.inputs[0])[0]
                        end_chain_e = alpha_e = create_link(tree, alpha_e, tb_falloff_e.inputs[0])[0]
                        end_chain_w = alpha_w = create_link(tree, alpha_w, tb_falloff_w.inputs[0])[0]
                    else:
                        end_chain_n = alpha_n
                        end_chain_s = alpha_s
                        end_chain_e = alpha_e
                        end_chain_w = alpha_w

            if 'Value' in height_proc.inputs:
                #create_link(tree, rgb_after_mod, height_proc.inputs['Value'])
                if layer.type == 'BACKGROUND':
                    create_link(tree, one_value.outputs[0], height_proc.inputs['Value'])
                else: create_link(tree, rgb, height_proc.inputs['Value'])

            if 'Value n' in  height_proc.inputs: 
                if layer.type == 'BACKGROUND':
                    create_link(tree, one_value.outputs[0], height_proc.inputs['Value n'])
                    create_link(tree, one_value.outputs[0], height_proc.inputs['Value s'])
                    create_link(tree, one_value.outputs[0], height_proc.inputs['Value e'])
                    create_link(tree, one_value.outputs[0], height_proc.inputs['Value w'])
                else:
                    create_link(tree, rgb_n, height_proc.inputs['Value n'])
                    create_link(tree, rgb_s, height_proc.inputs['Value s'])
                    create_link(tree, rgb_e, height_proc.inputs['Value e'])
                    create_link(tree, rgb_w, height_proc.inputs['Value w'])

            if layer.type == 'GROUP':

                normal_group = source.outputs.get(root_ch.name + io_suffix['GROUP'])
                height_group = source.outputs.get(root_ch.name + io_suffix['HEIGHT'] + io_suffix['GROUP'])

                create_link(tree, normal_group, normal_proc.inputs['Normal'])
                create_link(tree, height_group, height_proc.inputs['Height'])
                if root_ch.enable_smooth_bump:
                    create_link(tree, rgb_n, height_proc.inputs['Height n'])
                    create_link(tree, rgb_s, height_proc.inputs['Height s'])
                    create_link(tree, rgb_e, height_proc.inputs['Height e'])
                    create_link(tree, rgb_w, height_proc.inputs['Height w'])

            # Transition Bump
            if ch.enable_transition_bump and ch.enable:

                if trans_bump_crease:

                    create_link(tree, remains, height_proc.inputs['Remaining Alpha'])
                    create_link(tree, end_chain, height_proc.inputs['Transition'])

                    if 'Transition n' in height_proc.inputs: 
                        create_link(tree, end_chain_n, height_proc.inputs['Transition n'])
                        create_link(tree, end_chain_s, height_proc.inputs['Transition s'])
                        create_link(tree, end_chain_e, height_proc.inputs['Transition e'])
                        create_link(tree, end_chain_w, height_proc.inputs['Transition w'])

                    if not ch.write_height or len(layer.masks) == chain:
                        if 'Remaining Alpha n' in height_proc.inputs: 
                            create_link(tree, remains, height_proc.inputs['Remaining Alpha n'])
                            create_link(tree, remains, height_proc.inputs['Remaining Alpha s'])
                            create_link(tree, remains, height_proc.inputs['Remaining Alpha e'])
                            create_link(tree, remains, height_proc.inputs['Remaining Alpha w'])

                    else:
                        if 'Remaining Alpha n' in height_proc.inputs: 
                            create_link(tree, alpha_n, height_proc.inputs['Remaining Alpha n'])
                            create_link(tree, alpha_s, height_proc.inputs['Remaining Alpha s'])
                            create_link(tree, alpha_e, height_proc.inputs['Remaining Alpha e'])
                            create_link(tree, alpha_w, height_proc.inputs['Remaining Alpha w'])

                    if 'Edge 1 Alpha' in height_proc.inputs:
                        create_link(tree, intensity_multiplier.outputs[0], height_proc.inputs['Edge 1 Alpha'])

                    if 'Edge 1 Alpha' in normal_proc.inputs:
                        if not ch.write_height and not root_ch.enable_smooth_bump:
                            create_link(tree, height_proc.outputs['Filtered Alpha'], normal_proc.inputs['Edge 1 Alpha'])
                        else: create_link(tree, intensity_multiplier.outputs[0], normal_proc.inputs['Edge 1 Alpha'])

                    if 'Transition Crease' in height_proc.inputs:
                        create_link(tree, end_chain_crease, height_proc.inputs['Transition Crease'])

                    if 'Transition Crease n' in height_proc.inputs:
                        create_link(tree, end_chain_crease_n, height_proc.inputs['Transition Crease n'])
                        create_link(tree, end_chain_crease_s, height_proc.inputs['Transition Crease s'])
                        create_link(tree, end_chain_crease_e, height_proc.inputs['Transition Crease e'])
                        create_link(tree, end_chain_crease_w, height_proc.inputs['Transition Crease w'])

                else:

                    if not ch.write_height and not root_ch.enable_smooth_bump:

                        create_link(tree, end_chain, height_proc.inputs['Transition'])

                        if 'Edge 1 Alpha' in height_proc.inputs:
                            create_link(tree, intensity_multiplier.outputs[0], height_proc.inputs['Edge 1 Alpha'])

                        if 'Edge 1 Alpha' in normal_proc.inputs:
                            create_link(tree, intensity_multiplier.outputs[0], normal_proc.inputs['Edge 1 Alpha'])

                    else:

                        create_link(tree, pure, height_proc.inputs['Transition'])
                        if 'Transition n' in height_proc.inputs: 
                            create_link(tree, alpha_n, height_proc.inputs['Transition n'])
                            create_link(tree, alpha_s, height_proc.inputs['Transition s'])
                            create_link(tree, alpha_e, height_proc.inputs['Transition e'])
                            create_link(tree, alpha_w, height_proc.inputs['Transition w'])

                        if 'Edge 1 Alpha' in height_proc.inputs:
                            create_link(tree, alpha_before_intensity, height_proc.inputs['Edge 1 Alpha'])

                        if 'Edge 1 Alpha' in normal_proc.inputs:
                            create_link(tree, alpha_before_intensity, normal_proc.inputs['Edge 1 Alpha'])

                tb_inverse = nodes.get(ch.tb_inverse)
                tb_intensity_multiplier = nodes.get(ch.tb_intensity_multiplier)

                if 'Edge 2 Alpha' in normal_proc.inputs:
                    create_link(tree, tb_intensity_multiplier.outputs[0], normal_proc.inputs['Edge 2 Alpha'])

                if 'Edge 2 Alpha' in height_proc.inputs:
                        create_link(tree, tb_intensity_multiplier.outputs[0], height_proc.inputs['Edge 2 Alpha'])

                create_link(tree, transition_input, tb_inverse.inputs[1])
                if tb_intensity_multiplier:
                    create_link(tree, tb_inverse.outputs[0], tb_intensity_multiplier.inputs[0])

            else:

                if 'Alpha' in height_proc.inputs:
                    if not ch.write_height and not root_ch.enable_smooth_bump:
                        create_link(tree, end_chain, height_proc.inputs['Alpha'])
                    else: create_link(tree, alpha_before_intensity, height_proc.inputs['Alpha'])

                if ch.normal_map_type == 'NORMAL_MAP':
                    if not ch.write_height and not root_ch.enable_smooth_bump:
                        create_link(tree, end_chain, height_proc.inputs['Transition'])
                    else: create_link(tree, alpha_before_intensity, height_proc.inputs['Transition'])

                if 'Transition n' in height_proc.inputs: 
                    create_link(tree, alpha_n, height_proc.inputs['Transition n'])
                    create_link(tree, alpha_s, height_proc.inputs['Transition s'])
                    create_link(tree, alpha_e, height_proc.inputs['Transition e'])
                    create_link(tree, alpha_w, height_proc.inputs['Transition w'])

            # Height Blend

            #if 'Normal Alpha' in height_proc.outputs and (ch.write_height or root_ch.enable_smooth_bump):
            #    alpha = height_proc.outputs['Normal Alpha']

            height_alpha = alpha

            if 'Alpha' in height_proc.inputs:
                #height_alpha = alpha = create_link(tree, alpha_before_intensity, height_proc.inputs['Alpha'])['Alpha']
                alpha = create_link(tree, alpha_before_intensity, height_proc.inputs['Alpha'])['Alpha']
                if 'Alpha n' in height_proc.inputs:
                    create_link(tree, alpha_n, height_proc.inputs['Alpha n'])
                    create_link(tree, alpha_s, height_proc.inputs['Alpha s'])
                    create_link(tree, alpha_e, height_proc.inputs['Alpha e'])
                    create_link(tree, alpha_w, height_proc.inputs['Alpha w'])
            else:
                if trans_bump_crease:
                    #height_alpha = height_proc.outputs['Combined Alpha']
                    if not ch.write_height and not root_ch.enable_smooth_bump:
                        alpha = height_proc.outputs['Filtered Alpha']
                    else: alpha = height_proc.outputs['Combined Alpha']

                #elif 'Normal Alpha' in height_proc.outputs:
                elif 'Normal Alpha' in height_proc.outputs and (ch.write_height or root_ch.enable_smooth_bump):
                    alpha = height_proc.outputs['Normal Alpha']

                #if 'Normal Alpha' in height_proc.outputs and (not ch.write_height and not root_ch.enable_smooth_bump):
                #    height_alpha = height_proc.outputs['Normal Alpha']

                alpha_n = alpha_s = alpha_e = alpha_w = alpha

            # Height Alpha
            if 'Filtered Alpha' in height_proc.outputs and (not ch.write_height and not root_ch.enable_smooth_bump):
                height_alpha = alpha = height_proc.outputs['Filtered Alpha']
            elif 'Combined Alpha' in height_proc.outputs:
                height_alpha = alpha = height_proc.outputs['Combined Alpha']
            elif 'Normal Alpha' in height_proc.outputs:
                height_alpha = height_proc.outputs['Normal Alpha']
            elif 'Alpha' in height_proc.outputs:
                height_alpha = height_proc.outputs['Alpha']

            if 'Alpha n' in height_proc.outputs:
                alpha_n = height_proc.outputs['Alpha n']
                alpha_s = height_proc.outputs['Alpha s']
                alpha_e = height_proc.outputs['Alpha e']
                alpha_w = height_proc.outputs['Alpha w']

            alphas = {}
            alphas['n'] = alpha_n
            alphas['s'] = alpha_s
            alphas['e'] = alpha_e
            alphas['w'] = alpha_w

            #if not root_ch.enable_smooth_bump and ch.normal_blend_type in {'MIX', 'OVERLAY'}:
            if ch.normal_blend_type in {'MIX', 'OVERLAY'}:
                if has_parent: #and ch.normal_blend_type == 'MIX':
                    create_link(tree, prev_height, height_blend.inputs[0])
                    create_link(tree, prev_alpha, height_blend.inputs[1])
                    create_link(tree, height_proc.outputs['Height'], height_blend.inputs[2])
                    height_alpha = create_link(tree, height_alpha, height_blend.inputs[3])[1]
                else:
                #elif ch.normal_blend_type in {'MIX', 'OVERLAY'}:
                    create_link(tree, height_alpha, height_blend.inputs[0])
                    create_link(tree, prev_height, height_blend.inputs[1])
                    create_link(tree, height_proc.outputs['Height'], height_blend.inputs[2])
            else:
                create_link(tree, height_alpha, height_blend.inputs['Alpha'])
                create_link(tree, prev_height, height_blend.inputs['Prev Height'])
                create_link(tree, height_proc.outputs['Height'], height_blend.inputs['Height'])

            if root_ch.enable_smooth_bump:
                for d in neighbor_directions:
                    if ch.normal_blend_type in {'MIX', 'OVERLAY'}:
                        if has_parent: #and ch.normal_blend_type == 'MIX':
                            create_link(tree, prev_heights[d], height_blends[d].inputs[0])
                            create_link(tree, prev_alphas[d], height_blends[d].inputs[1])
                            create_link(tree, height_proc.outputs['Height ' + d], height_blends[d].inputs[2])
                            alphas[d] = create_link(tree, alphas[d], height_blends[d].inputs[3])[1]
                        else:
                        #elif ch.normal_blend_type in {'MIX', 'OVERLAY'}:
                            create_link(tree, alphas[d], height_blends[d].inputs[0])
                            create_link(tree, prev_heights[d], height_blends[d].inputs[1])
                            create_link(tree, height_proc.outputs['Height ' + d], height_blends[d].inputs[2])
                    else:
                        create_link(tree, alphas[d], height_blends[d].inputs['Alpha'])
                        create_link(tree, prev_heights[d], height_blends[d].inputs['Prev Height'])
                        create_link(tree, height_proc.outputs['Height ' + d], height_blends[d].inputs['Height'])

                    create_link(tree, height_blends[d].outputs[0], normal_proc.inputs['Height ' + d])
            else:
                create_link(tree, height_blend.outputs[0], normal_proc.inputs['Height'])

            if 'Normal Alpha' in height_blend.outputs:
                alpha = height_blend.outputs['Normal Alpha']

            if 'Alpha' in normal_proc.inputs:
                create_link(tree, alpha, normal_proc.inputs['Alpha'])
            if 'Normal Alpha' in normal_proc.inputs:
                create_link(tree, normal_alpha, normal_proc.inputs['Normal Alpha'])

            if layer.type == 'GROUP':
                if ch.write_height: #and 'Normal Alpha' in normal_proc.outputs:
                    alpha = normal_proc.outputs['Normal Alpha']
                #elif 'Combined Alpha' in normal_proc.outputs:
                else:
                    alpha = normal_proc.outputs['Combined Alpha']

            if 'Tangent' in normal_proc.inputs:
                create_link(tree, tangent, normal_proc.inputs['Tangent'])
                create_link(tree, bitangent, normal_proc.inputs['Bitangent'])

            if root_ch.type == 'NORMAL' and ch.write_height:
                if 'Normal No Bump' in normal_proc.outputs:
                    rgb = normal_proc.outputs['Normal No Bump']
                else: 
                    rgb = geometry.outputs['Normal']
            else: 
                rgb = normal_proc.outputs[0]

            if not root_ch.enable_smooth_bump and not ch.write_height:
                normal_flip = nodes.get(ch.normal_flip)
                if normal_flip:

                    if 'Tangent' in normal_flip.inputs:
                        create_link(tree, tangent, normal_flip.inputs['Tangent'])
                        create_link(tree, bitangent, normal_flip.inputs['Bitangent'])

                    rgb = create_link(tree, rgb, normal_flip.inputs[0])[0]

            if not ch.write_height:
                create_link(tree, prev_height, next_height)
                if root_ch.enable_smooth_bump:
                    for d in neighbor_directions:
                        create_link(tree, prev_heights[d], next_heights[d])

            else:
                create_link(tree, height_blend.outputs[0], next_height)
                if root_ch.enable_smooth_bump:
                    for d in neighbor_directions:
                        create_link(tree, height_blends[d].outputs[0], next_heights[d])

            if has_parent:

                if ch.write_height:
                    create_link(tree, height_alpha, end.inputs.get(root_ch.name + io_suffix['HEIGHT'] + io_suffix['ALPHA']))
                else:
                    create_link(tree, 
                            start.outputs.get(root_ch.name + io_suffix['HEIGHT'] + io_suffix['ALPHA']),
                            end.inputs.get(root_ch.name + io_suffix['HEIGHT'] + io_suffix['ALPHA']))

                if root_ch.enable_smooth_bump:

                    if ch.write_height:
                        for d in neighbor_directions:
                            create_link(tree, alphas[d], next_alphas[d])
                    else:
                        for d in neighbor_directions:
                            create_link(tree, prev_alphas[d], next_alphas[d])

        # Transition AO
        if root_ch.type in {'RGB', 'VALUE'} and trans_bump_ch and ch.enable_transition_ao: # and layer.type != 'BACKGROUND':
            tao = nodes.get(ch.tao)

            if trans_bump_flip:
                create_link(tree, rgb, tao.inputs[0])
                rgb = tao.outputs[0]

                # Get bump intensity multiplier of transition bump
                #if trans_bump_ch.transition_bump_flip or layer.type == 'BACKGROUND':
                #    trans_im = nodes.get(trans_bump_ch.intensity_multiplier)
                #else: 
                trans_im = nodes.get(trans_bump_ch.tb_intensity_multiplier)

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
                remaining_alpha = one_value.outputs[0]
                for j, mask in enumerate(layer.masks):
                    if j >= chain:
                        mix_n = nodes.get(mask.channels[i].mix_n)
                        if mix_n:
                            remaining_alpha = create_link(tree, remaining_alpha, mix_n.inputs[1])[0]

                prev_rgb = tao.outputs[0]
                if 'Remaining Alpha' in tao.inputs:
                    create_link(tree, remaining_alpha, tao.inputs['Remaining Alpha'])

                if 'Input Alpha' in tao.inputs:
                    create_link(tree, prev_alpha, tao.inputs['Input Alpha'])
                    prev_alpha = tao.outputs['Input Alpha']

                # Extra alpha
                if 'Extra Alpha' in tao.inputs:
                    if height_ch and height_ch.normal_blend_type == 'COMPARE' and compare_alpha:
                        create_link(tree, compare_alpha, tao.inputs['Extra Alpha'])
                    else:
                        break_input_link(tree, tao.inputs['Extra Alpha'])

            create_link(tree, transition_input, tao.inputs['Transition'])

        # Transition Ramp
        if root_ch.type in {'RGB', 'VALUE'} and ch.enable_transition_ramp:

            tr_ramp = nodes.get(ch.tr_ramp)
            tr_ramp_blend = nodes.get(ch.tr_ramp_blend)

            create_link(tree, transition_input, tr_ramp.inputs['Transition'])

            if trans_bump_flip:

                create_link(tree, prev_rgb, tr_ramp_blend.inputs['Input RGB'])
                create_link(tree, intensity_multiplier.outputs[0], tr_ramp_blend.inputs['Multiplied Alpha'])

                create_link(tree, tr_ramp.outputs[0], tr_ramp_blend.inputs['Ramp RGB'])

                trans_ramp_input = tr_ramp.outputs['Ramp Alpha']

                for j, mask in enumerate(layer.masks):
                    if j >= chain:
                        mix_n = nodes.get(mask.channels[i].mix_n)
                        if mix_n:
                            trans_ramp_input = create_link(tree, trans_ramp_input, mix_n.inputs[1])[0]

                create_link(tree, trans_ramp_input, tr_ramp_blend.inputs['Ramp Alpha'])
                prev_rgb = tr_ramp_blend.outputs[0]

                if 'Input Alpha' in tr_ramp_blend.inputs:
                    create_link(tree, prev_alpha, tr_ramp_blend.inputs['Input Alpha'])
                    prev_alpha = tr_ramp_blend.outputs['Input Alpha']

                break_input_link(tree, tr_ramp_blend.inputs['Intensity'])

            else:
                create_link(tree, rgb, tr_ramp.inputs['RGB'])
                rgb = tr_ramp.outputs[0]

                if 'Bg Alpha' in tr_ramp.inputs and bg_alpha:
                    create_link(tree, bg_alpha, tr_ramp.inputs['Bg Alpha'])
                    bg_alpha = tr_ramp.outputs[1] #'Bg Alpha']
                    #create_link(tree, alpha_before_intensity, tr_ramp.inputs['Remaining Alpha'])
                    #create_link(tree, alpha, tr_ramp.inputs['Channel Intensity'])
                    if ch.transition_ramp_intensity_unlink or layer.parent_idx != -1:
                        create_link(tree, alpha, tr_ramp.inputs['Alpha'])

                        if ch.transition_ramp_intensity_unlink:
                            create_link(tree, alpha_before_intensity, tr_ramp.inputs['Alpha before Intensity'])

                        create_link(tree, prev_rgb, tr_ramp.inputs['Input RGB'])
                        create_link(tree, prev_alpha, tr_ramp.inputs['Input Alpha'])

                        prev_rgb = tr_ramp.outputs[0]
                        prev_alpha = tr_ramp.outputs[1]

                        rgb = tr_ramp.outputs[2]
                        alpha = tr_ramp.outputs[3]

                elif ch.transition_ramp_intensity_unlink and ch.transition_ramp_blend_type == 'MIX':
                    create_link(tree, alpha_before_intensity, tr_ramp.inputs['Remaining Alpha'])
                    create_link(tree, alpha, tr_ramp.inputs['Channel Intensity'])

                    alpha = tr_ramp.outputs[1]

        # Extra alpha
        if extra_alpha and height_ch and height_ch.normal_blend_type == 'COMPARE' and compare_alpha:
            alpha = create_link(tree, alpha, extra_alpha.inputs[0])[0]
            create_link(tree, compare_alpha, extra_alpha.inputs[1])

        # Pass rgb to blend
        create_link(tree, rgb, blend.inputs[2])

        # End node
        next_rgb = end.inputs.get(root_ch.name)

        # Background layer only know mix
        if layer.type == 'BACKGROUND':
            blend_type = 'MIX'
        else: 
            if root_ch.type == 'NORMAL':
                blend_type = ch.normal_blend_type
            else: blend_type = ch.blend_type

        if (
                (blend_type == 'MIX' and (has_parent or (root_ch.type == 'RGB' and root_ch.enable_alpha)))
                or (blend_type == 'OVERLAY' and has_parent and root_ch.type == 'NORMAL')
            ):

            create_link(tree, prev_rgb, blend.inputs[0])
            create_link(tree, prev_alpha, blend.inputs[1])

            create_link(tree, alpha, blend.inputs[3])

            if bg_alpha and len(blend.inputs) > 4:
                create_link(tree, bg_alpha, blend.inputs[4])

        else:
            create_link(tree, alpha, blend.inputs[0])
            create_link(tree, prev_rgb, blend.inputs[1])

        # Armory can't recognize mute node, so reconnect input to output directly
        #if layer.enable and ch.enable:
        #    create_link(tree, blend.outputs[0], next_rgb)
        #else: create_link(tree, prev_rgb, next_rgb)
        create_link(tree, blend.outputs[0], next_rgb)

        # End alpha
        next_alpha = end.inputs.get(root_ch.name + io_suffix['ALPHA'])
        if next_alpha:
            if (
                (blend_type != 'MIX' and (has_parent or (root_ch.type == 'RGB' and root_ch.enable_alpha)))
                and not (blend_type == 'OVERLAY' and has_parent and root_ch.type == 'NORMAL')
                #or (has_parent and root_ch.type == 'NORMAL' and not ch.write_height)
                ):
                create_link(tree, prev_alpha, next_alpha)
            else:
                create_link(tree, blend.outputs[1], next_alpha)

