from .common import *

def create_link(tree, out, inp):
    node = inp.node
    if not any(l for l in out.links if l.to_socket == inp):
        tree.links.new(out, inp)
        #print(out, 'is connected to', inp)
    if node: return node.outputs
    return []

def break_link(tree, out, inp):
    for link in out.links:
        if link.to_socket == inp:
            tree.links.remove(link)
            return True
    return False

def break_input_link(tree, inp):
    for link in inp.links:
        tree.links.remove(link)

def break_output_link(tree, outp):
    for link in outp.links:
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
        mixcol0, mixcol1, mixout = get_mix_color_indices(ramp_mix)

        create_link(tree, value, ramp.inputs[0])
        create_link(tree, value, ramp_mix.inputs[mixcol0])
        create_link(tree, ramp.outputs[0], ramp_mix.inputs[mixcol1])

        value = ramp_mix.outputs[mixout]

    elif mod.type == 'CURVE':
        curve = tree.nodes.get(mod.curve)
        create_link(tree, value, curve.inputs[1])
        value = curve.outputs[0]

    return value

def reconnect_modifier_nodes(tree, mod, start_rgb, start_alpha):

    if not mod.enable:
        return start_rgb, start_alpha

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
        color_ramp_linear_start = tree.nodes.get(mod.color_ramp_linear_start)
        color_ramp = tree.nodes.get(mod.color_ramp)
        color_ramp_linear = tree.nodes.get(mod.color_ramp_linear)
        color_ramp_mix_alpha = tree.nodes.get(mod.color_ramp_mix_alpha)
        color_ramp_mix_rgb = tree.nodes.get(mod.color_ramp_mix_rgb)

        am_mixcol0, am_mixcol1, am_mixout = get_mix_color_indices(color_ramp_alpha_multiply)
        ma_mixcol0, ma_mixcol1, ma_mixout = get_mix_color_indices(color_ramp_mix_alpha)
        mr_mixcol0, mr_mixcol1, mr_mixout = get_mix_color_indices(color_ramp_mix_rgb)

        create_link(tree, start_rgb, color_ramp_alpha_multiply.inputs[am_mixcol0])
        create_link(tree, start_alpha, color_ramp_alpha_multiply.inputs[am_mixcol1])
        if color_ramp_linear_start:
            create_link(tree, color_ramp_alpha_multiply.outputs[am_mixout], color_ramp_linear_start.inputs[0])
            create_link(tree, color_ramp_linear_start.outputs[0], color_ramp.inputs[0])
        else:
            create_link(tree, color_ramp_alpha_multiply.outputs[am_mixout], color_ramp.inputs[0])
        create_link(tree, start_rgb, color_ramp_mix_rgb.inputs[mr_mixcol0])
        if color_ramp_linear_start:
            create_link(tree, color_ramp.outputs[0], color_ramp_linear.inputs[0])
            create_link(tree, color_ramp_linear.outputs[0], color_ramp_mix_rgb.inputs[mr_mixcol1])
        else:
            create_link(tree, color_ramp.outputs[0], color_ramp_mix_rgb.inputs[mr_mixcol1])

        create_link(tree, start_alpha, color_ramp_mix_alpha.inputs[ma_mixcol0])
        create_link(tree, color_ramp.outputs[1], color_ramp_mix_alpha.inputs[ma_mixcol1])

        rgb = color_ramp_mix_rgb.outputs[mr_mixout]
        alpha = color_ramp_mix_alpha.outputs[ma_mixout]

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

    elif mod.type == 'MATH':

        math = tree.nodes.get(mod.math)
        create_link(tree, start_rgb, math.inputs[0])
        create_link(tree, start_alpha, math.inputs[1])

        rgb = math.outputs[0]
        alpha = math.outputs[1]

    return rgb, alpha

def reconnect_all_modifier_nodes(tree, parent, start_rgb, start_alpha, mod_group=None, use_modifier_1=False):

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

    modifiers = parent.modifiers
    if use_modifier_1:
        modifiers = parent.modifiers_1

    # Connect all the nodes
    for mod in reversed(modifiers):
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

def remove_all_prev_inputs(tree, layer, node): #, height_only=False):

    yp = layer.id_data.yp

    if layer.parent_idx == -1: 
        return

    for i, ch in enumerate(layer.channels):
        root_ch = yp.channels[i]
        if has_previous_layer_channels(layer, root_ch): continue

        if root_ch.type == 'NORMAL':

            io_name = root_ch.name + io_suffix['HEIGHT']
            if io_name in node.inputs:
                break_input_link(tree, node.inputs[io_name])

            io_name = root_ch.name + io_suffix['HEIGHT'] + io_suffix['ALPHA']
            if io_name in node.inputs:
                break_input_link(tree, node.inputs[io_name])

            #if height_only: continue

            if root_ch.enable_smooth_bump:

                for letter in nsew_letters:

                    io_name = root_ch.name + io_suffix['HEIGHT_' + letter.upper()]
                    if io_name in node.inputs:
                        break_input_link(tree, node.inputs[io_name])

                    io_name = root_ch.name + io_suffix['HEIGHT_' + letter.upper()] + io_suffix['ALPHA']
                    if io_name in node.inputs:
                        break_input_link(tree, node.inputs[io_name])

            io_name = root_ch.name + io_suffix['MAX_HEIGHT']
            if io_name in node.inputs:
                break_input_link(tree, node.inputs[io_name])

            io_name = root_ch.name + io_suffix['VDISP']
            if io_name in node.inputs:
                break_input_link(tree, node.inputs[io_name])

        #if height_only: continue

        io_name = root_ch.name
        if io_name in node.inputs:
            # Should always fill normal input
            #geometry = tree.nodes.get(GEOMETRY)
            if root_ch.type == 'NORMAL': # and geometry:
                create_link(tree, get_essential_node(tree, GEOMETRY)['Normal'], node.inputs[io_name])
            else:
                break_input_link(tree, node.inputs[io_name])
            
        io_name = root_ch.name + io_suffix['ALPHA']
        if io_name in node.inputs:
            break_input_link(tree, node.inputs[io_name])

def remove_unused_group_node_connections(tree, layer, node): #, height_only=False):

    yp = layer.id_data.yp
    #node = tree.nodes.get(layer.group_node)

    if layer.type != 'GROUP':
        return

    for i, ch in enumerate(layer.channels):
        root_ch = yp.channels[i]
        if has_channel_children(layer, root_ch): continue

        io_name = root_ch.name + io_suffix['HEIGHT'] + io_suffix['GROUP']
        if io_name in node.inputs:
            break_input_link(tree, node.inputs[io_name])

        io_name = root_ch.name + io_suffix['HEIGHT'] + io_suffix['ALPHA'] + io_suffix['GROUP']
        if io_name in node.inputs:
            break_input_link(tree, node.inputs[io_name])

        #if height_only: continue

        io_name = root_ch.name + io_suffix['GROUP']
        if io_name in node.inputs:
            # Should always fill normal input
            #geometry = tree.nodes.get(GEOMETRY)
            #if root_ch.type == 'NORMAL' and geometry:
            #    create_link(tree, geometry.outputs['Normal'], node.inputs[io_name])
            #else:
            break_input_link(tree, node.inputs[io_name])

        io_name = root_ch.name + io_suffix['ALPHA'] + io_suffix['GROUP']
        if io_name in node.inputs:
            break_input_link(tree, node.inputs[io_name])

        if root_ch.enable_smooth_bump:

            for letter in nsew_letters:
                io_name = root_ch.name + io_suffix['HEIGHT_' + letter.upper()] + io_suffix['GROUP']
                if io_name in node.inputs:
                    break_input_link(tree, node.inputs[io_name])

                io_name = root_ch.name + io_suffix['HEIGHT_' + letter.upper()] + io_suffix['ALPHA'] + io_suffix['GROUP']
                if io_name in node.inputs:
                    break_input_link(tree, node.inputs[io_name])

def reconnect_relief_mapping_nodes(yp, node):
    parallax_ch = get_root_parallax_channel(yp)

    if not parallax_ch: return

    linear_loop = node.node_tree.nodes.get('_linear_search')
    binary_loop = node.node_tree.nodes.get('_binary_search')

    loop = node.node_tree.nodes.get('_linear_search')
    if loop:
        tree = loop.node_tree
        loop_start = tree.nodes.get(TREE_START)
        loop_end = tree.nodes.get(TREE_END)
        prev_it = None

        for i in range (parallax_ch.parallax_num_of_linear_samples):
            it = tree.nodes.get('_iterate_' + str(i))
            if not prev_it:
                create_link(tree, loop_start.outputs['t'], it.inputs['t'])
            else:
                create_link(tree, prev_it.outputs['t'], it.inputs['t'])

            create_link(tree, loop_start.outputs['tx'], it.inputs['tx'])
            create_link(tree, loop_start.outputs['v'], it.inputs['v'])
            create_link(tree, loop_start.outputs['dataz'], it.inputs['dataz'])
            create_link(tree, loop_start.outputs['size'], it.inputs['size'])

            if i == parallax_ch.parallax_num_of_linear_samples - 1:
                create_link(tree, it.outputs['t'], loop_end.inputs['t'])

            prev_it = it

    loop = node.node_tree.nodes.get('_binary_search')
    if loop:
        loop_start = loop.node_tree.nodes.get(TREE_START)
        loop_end = loop.node_tree.nodes.get(TREE_END)
        prev_it = None
        tree = loop.node_tree

        for i in range (parallax_ch.parallax_num_of_binary_samples):
            it = tree.nodes.get('_iterate_' + str(i))
            if not prev_it:
                create_link(tree, loop_start.outputs['t'], it.inputs['t'])
                create_link(tree, loop_start.outputs['size'], it.inputs['size'])
            else:
                create_link(tree, prev_it.outputs['t'], it.inputs['t'])
                create_link(tree, prev_it.outputs['size'], it.inputs['size'])

            create_link(tree, loop_start.outputs['tx'], it.inputs['tx'])
            create_link(tree, loop_start.outputs['v'], it.inputs['v'])
            create_link(tree, loop_start.outputs['dataz'], it.inputs['dataz'])

            if i == parallax_ch.parallax_num_of_binary_samples - 1:
                create_link(tree, it.outputs['t'], loop_end.inputs['t'])

            prev_it = it

def connect_parallax_iteration(tree, prefix):

    start = tree.nodes.get(TREE_START)
    end = tree.nodes.get(TREE_END)

    # Inside iterate group
    prev_it = start
    counter = 0
    while True:
        it = tree.nodes.get(prefix + str(counter))

        if it:
            for inp in it.inputs:
                if inp.name in prev_it.outputs:
                    create_link(tree, prev_it.outputs[inp.name], inp)
                elif inp.name in start.outputs:
                    create_link(tree, start.outputs[inp.name], inp)
        else:
            for inp in end.inputs:
                if inp.name == '': continue
                if inp.name in prev_it.outputs:
                    create_link(tree, prev_it.outputs[inp.name], inp)
                elif inp.name in start.outputs:
                    create_link(tree, start.outputs[inp.name], inp)
            break

        prev_it = it
        counter += 1

def reconnect_parallax_layer_nodes__(group_tree, parallax, uv_name=''):
    yp = group_tree.yp

    parallax_ch = get_root_parallax_channel(yp)
    if not parallax_ch: return

    # Connect iterate group
    loop = parallax.node_tree.nodes.get('_parallax_loop')
    if not loop: return

    # Connect top level iteration
    connect_parallax_iteration(loop.node_tree, '_iterate_')

    # Connect depth lib iteration
    counter = 0
    while True:
        it = loop.node_tree.nodes.get('_iterate_depth_' + str(counter))
        if it:
            connect_parallax_iteration(it.node_tree, '_iterate_')
        else:
            break

        counter += 1

def reconnect_parallax_layer_nodes_(group_tree, parallax, uv_name=''):

    yp = group_tree.yp

    parallax_ch = get_root_parallax_channel(yp)
    if not parallax_ch: return

    # Connect iterate group
    loop = parallax.node_tree.nodes.get('_parallax_loop')
    if not loop: return

    connect_parallax_iteration(loop.node_tree, '_iterate_group_')

    # Connect inside iterate group
    iterate_group_0 = loop.node_tree.nodes.get('_iterate_group_0')
    if not iterate_group_0: return

    connect_parallax_iteration(iterate_group_0.node_tree, '_iterate_')

#def reconnect_parallax_layer_nodes(group_tree, parallax, uv_name=''):
#
#    yp = group_tree.yp
#
#    parallax_ch = get_root_parallax_channel(yp)
#    if not parallax_ch: return
#
#    loop = parallax.node_tree.nodes.get('_parallax_loop')
#    if not loop: return
#
#    loop_start = loop.node_tree.nodes.get(TREE_START)
#    loop_end = loop.node_tree.nodes.get(TREE_END)
#
#    prev_it = None
#
#    for i in range (parallax_ch.parallax_num_of_layers):
#        it = loop.node_tree.nodes.get('_iterate_' + str(i))
#
#        if not prev_it:
#            create_link(loop.node_tree, 
#                    loop_start.outputs['depth_from_tex'], it.inputs['depth_from_tex'])
#
#            for uv in yp.uvs:
#                if uv_name != '' and uv.name != uv_name: continue
#                create_link(loop.node_tree, 
#                        loop_start.outputs[uv.name + CURRENT_UV], it.inputs[uv.name + CURRENT_UV])
#
#            for tc in texcoord_lists:
#                io_name = TEXCOORD_IO_PREFIX + tc + CURRENT_UV
#                if io_name in loop_start.outputs:
#                    create_link(loop.node_tree, loop_start.outputs[io_name], it.inputs[io_name])
#        else:
#            create_link(loop.node_tree, 
#                    prev_it.outputs['cur_layer_depth'], it.inputs['cur_layer_depth'])
#            create_link(loop.node_tree, 
#                    prev_it.outputs['depth_from_tex'], it.inputs['depth_from_tex'])
#
#            create_link(loop.node_tree, 
#                    prev_it.outputs['index'], it.inputs['index'])
#
#            for uv in yp.uvs:
#                if uv_name != '' and uv.name != uv_name: continue
#                create_link(loop.node_tree, 
#                        prev_it.outputs[uv.name + CURRENT_UV], it.inputs[uv.name + CURRENT_UV])
#
#            for tc in texcoord_lists:
#                io_name = TEXCOORD_IO_PREFIX + tc + CURRENT_UV
#                if io_name in prev_it.outputs:
#                    create_link(loop.node_tree, prev_it.outputs[io_name], it.inputs[io_name])
#
#        create_link(loop.node_tree,
#                loop_start.outputs['layer_depth'], it.inputs['layer_depth'])
#        create_link(loop.node_tree,
#                loop_start.outputs['base'], it.inputs['base'])
#
#        for uv in yp.uvs:
#            if uv_name != '' and uv.name != uv_name: continue
#            create_link(loop.node_tree, loop_start.outputs[uv.name + START_UV], it.inputs[uv.name + START_UV])
#            create_link(loop.node_tree, loop_start.outputs[uv.name + DELTA_UV], it.inputs[uv.name + DELTA_UV])
#
#        for tc in texcoord_lists:
#            io_name = TEXCOORD_IO_PREFIX + tc + START_UV
#            if io_name in loop_start.outputs:
#                create_link(loop.node_tree, loop_start.outputs[io_name], it.inputs[io_name])
#            io_name = TEXCOORD_IO_PREFIX + tc + DELTA_UV
#            if io_name in loop_start.outputs:
#                create_link(loop.node_tree, loop_start.outputs[io_name], it.inputs[io_name])
#
#        if i == parallax_ch.parallax_num_of_layers-1:
#
#            create_link(loop.node_tree, 
#                    it.outputs['cur_layer_depth'], loop_end.inputs['cur_layer_depth'])
#            create_link(loop.node_tree, 
#                    it.outputs['depth_from_tex'], loop_end.inputs['depth_from_tex'])
#            create_link(loop.node_tree, 
#                    it.outputs['index'], loop_end.inputs['index'])
#
#            for uv in yp.uvs:
#                if uv_name != '' and uv.name != uv_name: continue
#                create_link(loop.node_tree, 
#                        it.outputs[uv.name + CURRENT_UV], loop_end.inputs[uv.name + CURRENT_UV])
#
#            for tc in texcoord_lists:
#                io_name = TEXCOORD_IO_PREFIX + tc + CURRENT_UV
#                if io_name in it.outputs:
#                    create_link(loop.node_tree, it.outputs[io_name], loop_end.inputs[io_name])
#
#        prev_it = it

def reconnect_baked_parallax_layer_nodes(yp, node):
    parallax_ch = get_root_parallax_channel(yp)
    if not parallax_ch: return

    num_of_layers = int(parallax_ch.baked_parallax_num_of_layers)

    loop = node.node_tree.nodes.get('_parallax_loop')
    if loop:
        loop_start = loop.node_tree.nodes.get(TREE_START)
        loop_end = loop.node_tree.nodes.get(TREE_END)
        prev_it = None
        tree = loop.node_tree

        for i in range (num_of_layers):
            it = tree.nodes.get('_iterate_' + str(i))
            if not prev_it:
                create_link(tree, loop_start.outputs['cur_uv'], it.inputs['cur_uv'])
                create_link(tree, loop_start.outputs['cur_layer_depth'], it.inputs['cur_layer_depth'])
                create_link(tree, loop_start.outputs['depth_from_tex'], it.inputs['depth_from_tex'])
            else:
                create_link(tree, prev_it.outputs['cur_uv'], it.inputs['cur_uv'])
                create_link(tree, prev_it.outputs['cur_layer_depth'], it.inputs['cur_layer_depth'])
                create_link(tree, prev_it.outputs['depth_from_tex'], it.inputs['depth_from_tex'])

            create_link(tree, loop_start.outputs['delta_uv'], it.inputs['delta_uv'])
            create_link(tree, loop_start.outputs['layer_depth'], it.inputs['layer_depth'])

            if i == num_of_layers-1:
                create_link(tree, it.outputs['cur_uv'], loop_end.inputs['cur_uv'])
                create_link(tree, it.outputs['cur_layer_depth'], loop_end.inputs['cur_layer_depth'])
                create_link(tree, it.outputs['depth_from_tex'], loop_end.inputs['depth_from_tex'])

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
    iterate = loop.node_tree.nodes.get('_iterate')

    iterate_start = iterate.node_tree.nodes.get(TREE_START)
    iterate_end = iterate.node_tree.nodes.get(TREE_END)
    iterate_depth = iterate.node_tree.nodes.get('_depth_from_tex')
    iterate_branch = iterate.node_tree.nodes.get('_branch')

    #iterate_group_0 = loop.node_tree.nodes.get('_iterate')
    #iterate_group_start = iterate_group_0.node_tree.nodes.get(TREE_START)
    #iterate_group_end = iterate_group_0.node_tree.nodes.get(TREE_END)

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

        mixcol0, mixcol1, mixout = get_mix_color_indices(parallax_mix)

        create_link(tree, weight.outputs[0], parallax_mix.inputs[0])
        create_link(tree, loop.outputs[uv.name + CURRENT_UV], parallax_mix.inputs[mixcol0])
        create_link(tree, depth_source_1.outputs[uv.name + CURRENT_UV], parallax_mix.inputs[mixcol1])

        # End uv
        #create_link(tree, loop.outputs[uv.name + CURRENT_UV], end.inputs[uv.name])
        create_link(tree, parallax_mix.outputs[mixout], end.inputs[uv.name])

        # Inside depth source
        if baked: delta_uv = depth_source_0.node_tree.nodes.get(uv.baked_parallax_delta_uv)
        else: delta_uv = depth_source_0.node_tree.nodes.get(uv.parallax_delta_uv)
        mixcol0, mixcol1, mixout = get_mix_color_indices(delta_uv)

        if baked: current_uv = depth_source_0.node_tree.nodes.get(uv.baked_parallax_current_uv)
        else: current_uv = depth_source_0.node_tree.nodes.get(uv.parallax_current_uv)
        height_map = depth_source_0.node_tree.nodes.get(HEIGHT_MAP)

        create_link(depth_source_0.node_tree, depth_start.outputs['index'], delta_uv.inputs[mixcol0])
        create_link(depth_source_0.node_tree, depth_start.outputs[uv.name + DELTA_UV], delta_uv.inputs[mixcol1])

        create_link(depth_source_0.node_tree, depth_start.outputs[uv.name + START_UV], current_uv.inputs[0])
        create_link(depth_source_0.node_tree, delta_uv.outputs[mixout], current_uv.inputs[1])

        create_link(depth_source_0.node_tree, current_uv.outputs[0], depth_end.inputs[uv.name + CURRENT_UV])

        if height_map:
            create_link(depth_source_0.node_tree, current_uv.outputs[0], height_map.inputs[0])
            create_link(depth_source_0.node_tree, height_map.outputs[0], depth_end.inputs[0])

        # Inside iteration
        create_link(
            iterate.node_tree, 
            iterate_start.outputs[uv.name + START_UV],
            iterate_depth.inputs[uv.name + START_UV]
        )
        create_link(
            iterate.node_tree, 
            iterate_start.outputs[uv.name + DELTA_UV],
            iterate_depth.inputs[uv.name + DELTA_UV]
        )

        if baked: parallax_current_uv_mix = iterate.node_tree.nodes.get(uv.baked_parallax_current_uv_mix)
        else: parallax_current_uv_mix = iterate.node_tree.nodes.get(uv.parallax_current_uv_mix)

        mixcol0, mixcol1, mixout = get_mix_color_indices(parallax_current_uv_mix)

        create_link(iterate.node_tree, iterate_branch.outputs[0], parallax_current_uv_mix.inputs[0])

        create_link(
            iterate.node_tree, 
            iterate_depth.outputs[uv.name + CURRENT_UV],
            parallax_current_uv_mix.inputs[mixcol0]
        )
        create_link(
            iterate.node_tree, 
            iterate_start.outputs[uv.name + CURRENT_UV],
            parallax_current_uv_mix.inputs[mixcol1]
        )
        create_link(
            iterate.node_tree, 
            parallax_current_uv_mix.outputs[mixout],
            iterate_end.inputs[uv.name + CURRENT_UV]
        )

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
            mixcol0, mixcol1, mixout = get_mix_color_indices(parallax_mix)

            create_link(tree, weight.outputs[0], parallax_mix.inputs[0])
            create_link(tree, loop.outputs[base_name + CURRENT_UV], parallax_mix.inputs[mixcol0])
            create_link(tree, depth_source_1.outputs[base_name + CURRENT_UV], parallax_mix.inputs[mixcol1])

            # End uv
            create_link(tree, parallax_mix.outputs[mixout], end.inputs[base_name])

            # Inside depth source
            delta_uv = depth_source_0.node_tree.nodes.get(PARALLAX_DELTA_PREFIX + base_name)
            mixcol0, mixcol1, mixout = get_mix_color_indices(delta_uv)
            current_uv = depth_source_0.node_tree.nodes.get(PARALLAX_CURRENT_PREFIX + base_name)

            create_link(depth_source_0.node_tree, depth_start.outputs['index'], delta_uv.inputs[mixcol0])
            create_link(depth_source_0.node_tree, depth_start.outputs[base_name + DELTA_UV], delta_uv.inputs[mixcol1])

            create_link(depth_source_0.node_tree, depth_start.outputs[base_name + START_UV], current_uv.inputs[0])
            create_link(depth_source_0.node_tree, delta_uv.outputs[mixout], current_uv.inputs[1])

            create_link(depth_source_0.node_tree, current_uv.outputs[0], depth_end.inputs[base_name + CURRENT_UV])

            # Inside iteration
            create_link(
                iterate.node_tree, 
                iterate_start.outputs[base_name + START_UV],
                iterate_depth.inputs[base_name + START_UV]
            )
            create_link(
                iterate.node_tree, 
                iterate_start.outputs[base_name + DELTA_UV],
                iterate_depth.inputs[base_name + DELTA_UV]
            )

            parallax_current_uv_mix = iterate.node_tree.nodes.get(PARALLAX_CURRENT_MIX_PREFIX + base_name)
            mixcol0, mixcol1, mixout = get_mix_color_indices(parallax_current_uv_mix)

            create_link(iterate.node_tree, iterate_branch.outputs[0], parallax_current_uv_mix.inputs[0])
            create_link(
                iterate.node_tree, 
                iterate_depth.outputs[base_name + CURRENT_UV],
                parallax_current_uv_mix.inputs[mixcol0]
            )
            create_link(
                iterate.node_tree,
                iterate_start.outputs[base_name + CURRENT_UV],
                parallax_current_uv_mix.inputs[mixcol1]
            )

            create_link(
                iterate.node_tree, 
                parallax_current_uv_mix.outputs[mixout],
                iterate_end.inputs[base_name + CURRENT_UV]
            )

    #reconnect_parallax_layer_nodes(group_tree, parallax, uv_name)
    #reconnect_parallax_layer_nodes_(group_tree, parallax, uv_name)
    reconnect_parallax_layer_nodes__(group_tree, parallax, uv_name)

def reconnect_depth_layer_nodes(group_tree, parallax_ch, parallax):

    yp = group_tree.yp

    depth_source_0 = parallax.node_tree.nodes.get('_depth_source_0')
    tree = depth_source_0.node_tree

    start = tree.nodes.get(TREE_START)
    end = tree.nodes.get(TREE_END)

    unpack = tree.nodes.get('_unpack')
    normalize = tree.nodes.get('_normalize')

    if parallax_ch.enable_smooth_bump:
        io_height_name = parallax_ch.name + io_suffix['HEIGHT_ONS']
    else: io_height_name = parallax_ch.name + io_suffix['HEIGHT']

    io_alpha_name = parallax_ch.name + io_suffix['ALPHA']
    if parallax_ch.enable_smooth_bump:
        io_height_alpha_name = parallax_ch.name + io_suffix['HEIGHT_ONS'] + io_suffix['ALPHA']
    else: io_height_alpha_name = parallax_ch.name + io_suffix['HEIGHT'] + io_suffix['ALPHA']

    height = start.outputs['base']

    parallax_ch_idx = get_channel_index(parallax_ch)

    for i, layer in reversed(list(enumerate(yp.layers))):

        #if yp.disable_quick_toggle and (not layer.enable or not layer.channels[parallax_ch_idx].enable): continue
        if not layer.enable or not layer.channels[parallax_ch_idx].enable: continue

        node = tree.nodes.get(layer.depth_group_node)

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

        if layer.parent_idx != -1: continue

        height = create_link(tree, height, node.inputs[io_height_name])[io_height_name]

    if parallax_ch.enable_smooth_bump:
        height = create_link(tree, height, unpack.inputs[0])[0]

    create_link(tree, height, normalize.inputs[0])
    create_link(tree, normalize.outputs[0], end.inputs['depth_from_tex'])

    # List of last members
    last_members = []
    for layer in yp.layers:
        if not layer.enable: continue
        if is_bottom_member(layer, True):
            last_members.append(layer)

        # Remove unused input links
        node = tree.nodes.get(layer.depth_group_node)
        if layer.type == 'GROUP':
            remove_unused_group_node_connections(tree, layer, node) #, height_only=True)
        remove_all_prev_inputs(tree, layer, node) #, height_only=True)

    # Group stuff
    for layer in last_members:

        node = tree.nodes.get(layer.depth_group_node)

        cur_layer = layer
        cur_node = node

        io_alpha = cur_node.outputs.get(io_alpha_name)
        io_height = cur_node.outputs.get(io_height_name)
        io_height_alpha = cur_node.outputs.get(io_height_alpha_name)

        while True:
            # Get upper layer
            upper_idx, upper_layer = get_upper_neighbor(cur_layer)
            upper_node = tree.nodes.get(upper_layer.depth_group_node)

            # Connect
            if upper_layer.parent_idx == cur_layer.parent_idx:

                #if not yp.disable_quick_toggle or upper_layer.enable:
                if upper_layer.enable:

                    if io_alpha_name in upper_node.inputs:
                        if io_alpha:
                            io_alpha = create_link(tree, io_alpha, upper_node.inputs[io_alpha_name])[io_alpha_name]
                        else: io_alpha = upper_node.outputs[io_alpha_name]

                    if io_height_name in upper_node.inputs:
                        if io_height:
                            io_height = create_link(tree, io_height, upper_node.inputs[io_height_name])[io_height_name]
                        else: io_height = upper_node.outputs[io_height_name]


                    if io_height_alpha_name in upper_node.inputs:
                        if io_height_alpha:
                            io_height_alpha = create_link(tree, io_height_alpha, upper_node.inputs[io_height_alpha_name])[io_height_alpha_name]
                        else: io_height_alpha = upper_node.outputs[io_height_alpha_name]

                cur_layer = upper_layer
                cur_node = upper_node

            else:

                io_name = io_alpha_name + io_suffix['GROUP']
                if io_alpha and io_name in upper_node.inputs:
                    #create_link(tree, cur_node.outputs[io_alpha_name], upper_node.inputs[io_name])
                    create_link(tree, io_alpha, upper_node.inputs[io_name])

                io_name = io_height_name + io_suffix['GROUP']
                if io_height and io_name in upper_node.inputs:
                    create_link(tree, io_height, upper_node.inputs[io_name])

                io_name = io_height_alpha_name + io_suffix['GROUP']
                if io_height_alpha and io_name in upper_node.inputs:
                    #create_link(tree, cur_node.outputs[io_height_alpha_name], upper_node.inputs[io_name])
                    create_link(tree, io_height_alpha, upper_node.inputs[io_name])

                break

''' Get essential node and if not found, create one '''
def get_essential_node(tree, name):
    node = tree.nodes.get(name)
    if not node:
        if name == TREE_START:
            node = tree.nodes.new('NodeGroupInput')
            node.name = TREE_START
            node.label = 'Start'

        elif name == TREE_END:
            node = tree.nodes.new('NodeGroupOutput')
            node.name = TREE_END
            node.label = 'End'

        elif name == ONE_VALUE:
            node = tree.nodes.new('ShaderNodeValue')
            node.name = ONE_VALUE
            node.label = 'One Value'
            node.outputs[0].default_value = 1.0

        elif name == ZERO_VALUE:
            node = tree.nodes.new('ShaderNodeValue')
            node.name = ZERO_VALUE
            node.label = 'Zero Value'
            node.outputs[0].default_value = 0.0

        elif name == GEOMETRY:
            node = tree.nodes.new('ShaderNodeNewGeometry')
            node.name = GEOMETRY

        elif name == TEXCOORD:
            node = tree.nodes.new('ShaderNodeTexCoord')
            node.name = TEXCOORD

    if name == TREE_END:
        return node.inputs

    return node.outputs

''' Check for all essential nodes and delete them if no links found '''
def clean_essential_nodes(tree, exclude_texcoord=False, exclude_geometry=False):
    for name in [ONE_VALUE, ZERO_VALUE, GEOMETRY, TEXCOORD, TREE_START, TREE_END]:
        if exclude_texcoord and name == TEXCOORD: continue
        if exclude_geometry and name == GEOMETRY: continue
        node = tree.nodes.get(name)
        if node:
            link_found = False
            if len(node.outputs) > 0:
                for outp in node.outputs:
                    if len(outp.links) > 0:
                        link_found = True
                        break
            elif len(node.inputs) > 0:
                for inp in node.inputs:
                    if len(inp.links) > 0:
                        link_found = True
                        break
            if not link_found:
                tree.nodes.remove(node)

def reconnect_yp_nodes(tree, merged_layer_ids = []):
    yp = tree.yp
    nodes = tree.nodes
    ypup = get_user_preferences()

    #print('Reconnect tree ' + tree.name)

    start = nodes.get(TREE_START)
    end = nodes.get(TREE_END)

    texcoord = nodes.get(TEXCOORD)
    parallax = tree.nodes.get(PARALLAX)

    # Parallax
    parallax_ch = get_root_parallax_channel(yp)
    parallax = tree.nodes.get(PARALLAX)
    baked_parallax = tree.nodes.get(BAKED_PARALLAX)
    baked_parallax_filter = tree.nodes.get(BAKED_PARALLAX_FILTER)

    # Get color and alpha channel
    color_ch, alpha_ch = get_color_alpha_ch_pairs(yp)

    # UVs

    uv_maps = {}
    tangents = {}
    bitangents = {}

    for uv in yp.uvs:
        uv_map = nodes.get(uv.uv_map)
        if uv_map:
            uv_maps[uv.name] = uv_map.outputs[0]

        tangent_process = nodes.get(uv.tangent_process)
        if tangent_process:
            tangents[uv.name] = tangent_process.outputs['Tangent']
            bitangents[uv.name] = tangent_process.outputs['Bitangent']

    # Get main tangent and bitangent
    height_ch = get_root_height_channel(yp)
    main_uv = None
    if height_ch and height_ch.main_uv != '':
        main_uv = yp.uvs.get(height_ch.main_uv)

    if not main_uv and len(yp.uvs) > 0:
        main_uv = yp.uvs[0]

    if main_uv and tangents and bitangents:
        tangent = tangents[main_uv.name]
        bitangent = bitangents[main_uv.name]
    else:
        tangent = None
        bitangent = None

    baked_uv = yp.uvs.get(yp.baked_uv_name)
    baked_uv_map = nodes.get(baked_uv.uv_map) if baked_uv else None
    if baked_uv_map: baked_uv_map = baked_uv_map.outputs[0]

    if yp.use_baked and baked_uv:

        if parallax_ch and baked_parallax:
            if baked_parallax_filter:
                create_link(tree, baked_uv_map, baked_parallax_filter.inputs['Cycles'])
                create_link(tree, baked_parallax.outputs[0], baked_parallax_filter.inputs['Eevee'])
                create_link(tree, baked_parallax.outputs[0], baked_parallax_filter.inputs['Blender 2.7 Viewport'])
                baked_uv_map = baked_parallax_filter.outputs[0]
            else:
                baked_uv_map = baked_parallax.outputs[0]

        #baked_tangent = tangents[baked_uv.name]
        #baked_bitangent = bitangents[baked_uv.name]

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
            if uv.name in uv_maps: create_link(tree, uv_maps[uv.name], parallax_prep.inputs[0])
            if uv.name in tangents: create_link(tree, tangents[uv.name], parallax_prep.inputs['Tangent'])
            if uv.name in bitangents: create_link(tree, bitangents[uv.name], parallax_prep.inputs['Bitangent'])
    
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
            #create_link(tree, texcoord.outputs[tc], parallax_prep.inputs[0])
            create_link(tree, get_essential_node(tree, TEXCOORD)[tc], parallax_prep.inputs[0])
            if tangent and bitangent:
                create_link(tree, tangent, parallax_prep.inputs['Tangent'])
                create_link(tree, bitangent, parallax_prep.inputs['Bitangent'])
    
            if parallax:
                create_link(tree, parallax_prep.outputs['start_uv'], parallax.inputs[TEXCOORD_IO_PREFIX + tc + START_UV])
                create_link(tree, parallax_prep.outputs['delta_uv'], parallax.inputs[TEXCOORD_IO_PREFIX + tc + DELTA_UV])

    if parallax_ch:
        if parallax:
            height = start.outputs.get(parallax_ch.name + io_suffix['HEIGHT'])
            if height: create_link(tree, height, parallax.inputs['base'])

        if baked_parallax:
            height = start.outputs.get(parallax_ch.name + io_suffix['HEIGHT'])
            if height: create_link(tree, height, baked_parallax.inputs['base'])

    #print()

    for i, ch in enumerate(yp.channels):
        #if ch_idx != -1 and i != ch_idx: continue

        start_linear = nodes.get(ch.start_linear)
        end_linear = nodes.get(ch.end_linear)
        end_normal_engine_filter = nodes.get(ch.end_normal_engine_filter)
        end_backface = nodes.get(ch.end_backface)
        clamp = nodes.get(ch.clamp)
        end_max_height = nodes.get(ch.end_max_height)
        end_max_height_tweak = nodes.get(ch.end_max_height_tweak)
        start_normal_filter = nodes.get(ch.start_normal_filter)
        start_bump_process = nodes.get(ch.start_bump_process)

        io_name = ch.name
        io_alpha_name = ch.name + io_suffix['ALPHA']

        io_height_name = ch.name + io_suffix['HEIGHT']
        io_height_n_name = ch.name + io_suffix['HEIGHT_N']
        io_height_s_name = ch.name + io_suffix['HEIGHT_S']
        io_height_e_name = ch.name + io_suffix['HEIGHT_E']
        io_height_w_name = ch.name + io_suffix['HEIGHT_W']

        io_height_alpha_name = ch.name + io_suffix['HEIGHT'] + io_suffix['ALPHA']
        io_height_n_alpha_name = ch.name + io_suffix['HEIGHT_N'] + io_suffix['ALPHA']
        io_height_s_alpha_name = ch.name + io_suffix['HEIGHT_S'] + io_suffix['ALPHA']
        io_height_e_alpha_name = ch.name + io_suffix['HEIGHT_E'] + io_suffix['ALPHA']
        io_height_w_alpha_name = ch.name + io_suffix['HEIGHT_W'] + io_suffix['ALPHA']

        io_max_height_name = ch.name + io_suffix['MAX_HEIGHT']
        io_vdisp_name = ch.name + io_suffix['VDISP']

        rgb = start.outputs[io_name]
        #if ch.enable_alpha and ch.type == 'RGB':
        if ch.enable_alpha:
            alpha = start.outputs[io_alpha_name]
        else: alpha = get_essential_node(tree, ONE_VALUE)[0]

        height = None
        height_n = None
        height_s = None
        height_e = None
        height_w = None

        height_alpha = None
        height_n_alpha = None
        height_s_alpha = None
        height_e_alpha = None
        height_w_alpha = None

        max_height = None

        vdisp = None

        if ch.type == 'NORMAL':
            height_input = start.outputs.get(io_height_name)
            height = height_input if height_input else get_essential_node(tree, ZERO_VALUE)[0]

            if is_normal_height_input_connected(ch):
                max_height = start.outputs[io_max_height_name]
            else: max_height = get_essential_node(tree, ZERO_VALUE)[0]

            vdisp_input = start.outputs.get(io_vdisp_name)
            vdisp = vdisp_input if vdisp_input else get_essential_node(tree, ZERO_VALUE)[0]

            if ch.enable_smooth_bump:
                height_n = height_input if height_input else get_essential_node(tree, ZERO_VALUE)[0]
                height_s = height_input if height_input else get_essential_node(tree, ZERO_VALUE)[0]
                height_e = height_input if height_input else get_essential_node(tree, ZERO_VALUE)[0]
                height_w = height_input if height_input else get_essential_node(tree, ZERO_VALUE)[0]

                if is_normal_height_input_connected(ch):
                    height_alpha = get_essential_node(tree, ZERO_VALUE)[0]
                    height_n_alpha = get_essential_node(tree, ZERO_VALUE)[0]
                    height_s_alpha = get_essential_node(tree, ZERO_VALUE)[0]
                    height_e_alpha = get_essential_node(tree, ZERO_VALUE)[0]
                    height_w_alpha = get_essential_node(tree, ZERO_VALUE)[0]

            if start_bump_process:
                height = create_link(tree, height, start_bump_process.inputs['Height'])[0]
                create_link(tree, max_height, start_bump_process.inputs['Max Height'])

                #if ch.enable_smooth_bump:

                #    if tangent and bitangent:
                #        create_link(tree, tangent, start_bump_process.inputs['Tangent'])
                #        create_link(tree, bitangent, start_bump_process.inputs['Bitangent'])

                #    height_n = start_bump_process.outputs['n']
                #    height_s = start_bump_process.outputs['s']
                #    height_e = start_bump_process.outputs['e']
                #    height_w = start_bump_process.outputs['w']

        if start_linear:
            rgb = create_link(tree, rgb, start_linear.inputs[0])[0]
        elif start_normal_filter:
            rgb = create_link(tree, rgb, start_normal_filter.inputs[0])[0]

        # Background rgb and alpha
        bg_rgb = rgb
        bg_alpha = alpha
        bg_height = height

        # Layers loop
        for j, layer in reversed(list(enumerate(yp.layers))):

            #print(ch.name, layer.name)

            node = nodes.get(layer.group_node)
            layer_ch = layer.channels[i]

            # Get alpha channel
            layer_color_ch, layer_alpha_ch = get_layer_color_alpha_ch_pairs(layer)

            if layer_ch != layer_alpha_ch:
                layer_ch_enable = layer_ch.enable
            else: layer_ch_enable = layer_color_ch.enable or layer_alpha_ch.enable

            #is_hidden = not layer.enable or is_parent_hidden(layer)

            if yp.layer_preview_mode: # and yp.layer_preview_mode_type == 'LAYER':

                if ch == yp.channels[yp.active_channel_index] and layer == yp.layers[yp.active_layer_index]:

                    col_preview = end.inputs.get(LAYER_VIEWER)
                    alpha_preview = end.inputs.get(LAYER_ALPHA_VIEWER)
                    if col_preview:
                        #create_link(tree, rgb, col_preview)
                        if not layer.enable:
                            create_link(tree, get_essential_node(tree, ZERO_VALUE)[0], col_preview)
                        else: create_link(tree, node.outputs[LAYER_VIEWER], col_preview)
                    if alpha_preview:
                        if not layer.enable:
                            create_link(tree, get_essential_node(tree, ZERO_VALUE)[0], alpha_preview)
                        else: create_link(tree, node.outputs[LAYER_ALPHA_VIEWER], alpha_preview)
                elif ch.type == 'NORMAL' and layer_ch.normal_map_type == 'VECTOR_DISPLACEMENT_MAP':
                    continue

            #if yp.disable_quick_toggle and not layer.enable:
            if (
                #(merged_layer_ids and j not in merged_layer_ids and not is_hidden)
                (merged_layer_ids and j not in merged_layer_ids) or
                not layer.enable
                ):

                if node:
                    for inp in node.inputs:
                        break_input_link(tree, inp)
                    for outp in node.outputs:
                        break_input_link(tree, outp)

                continue

            #if is_hidden:
            #    continue

            need_prev_normal = check_need_prev_normal(layer)

            #if yp.disable_quick_toggle and not layer_ch_enable:
            #if not (ch.type == 'NORMAL' and need_prev_normal) and not layer_ch_enable:
            if not (ch.type == 'NORMAL' and need_prev_normal) and not layer_ch_enable:
                continue

            # UV inputs
            uv_names = []

            if height_ch and height_ch.main_uv != '':
                uv_names.append(height_ch.main_uv)

            if layer.texcoord_type == 'UV' and layer.uv_name not in uv_names:
                uv_names.append(layer.uv_name)

            if layer.use_baked and layer.baked_uv_name != '' and layer.baked_uv_name not in uv_names:
                uv_names.append(layer.baked_uv_name)

            for mask in layer.masks:
                if mask.texcoord_type == 'UV' and mask.uv_name not in uv_names:
                    uv_names.append(mask.uv_name)

                if mask.use_baked and mask.baked_uv_name != '' and mask.baked_uv_name not in uv_names:
                    uv_names.append(mask.baked_uv_name)

            for uv_name in uv_names:
                uv = yp.uvs.get(uv_name)
                if not uv: continue
                inp = node.inputs.get(uv_name + io_suffix['UV'])
                if inp:
                    if parallax_ch and parallax:
                        if uv_name in parallax.outputs:
                            create_link(tree, parallax.outputs[uv_name], inp)
                    else: 
                        if uv_name in uv_maps:
                            create_link(tree, uv_maps[uv_name], inp)

                inp = node.inputs.get(uv_name + io_suffix['TANGENT'])
                if inp and uv_name in tangents: 
                    create_link(tree, tangents[uv_name], inp)

                inp = node.inputs.get(uv_name + io_suffix['BITANGENT'])
                if inp and uv_name in bitangents: 
                    create_link(tree, bitangents[uv_name], inp)

            # Texcoord inputs
            texcoords = []
            if layer.texcoord_type not in {'UV', 'Decal'}:
                texcoords.append(layer.texcoord_type)

            for mask in layer.masks:
                if mask.texcoord_type not in {'UV', 'Decal', 'Layer'} and mask.texcoord_type not in texcoords:
                    texcoords.append(mask.texcoord_type)

            for tc in texcoords:
                inp = node.inputs.get(io_names[tc])
                if inp: 
                    if parallax_ch and parallax:
                        create_link(tree, parallax.outputs[TEXCOORD_IO_PREFIX + tc], inp)
                    else: 
                        #create_link(tree, texcoord.outputs[tc], inp)
                        create_link(tree, get_essential_node(tree, TEXCOORD)[tc], inp)

            # Background layer
            if layer.type == 'BACKGROUND':
                # Offsets for background layer
                inp = node.inputs.get(ch.name + io_suffix['BACKGROUND'])
                inp_alpha = node.inputs.get(ch.name + io_suffix['ALPHA'] + io_suffix['BACKGROUND'])
                inp_height = node.inputs.get(ch.name + io_suffix['HEIGHT'] + io_suffix['BACKGROUND'])

                if layer.parent_idx == -1:
                    if inp: 
                        create_link(tree, bg_rgb, inp)
                    if inp_alpha:
                        create_link(tree, bg_alpha, inp_alpha)
                    if inp_height:
                        create_link(tree, bg_height, inp_height)
                else:
                    if inp: 
                        break_input_link(tree, inp)
                    if inp_alpha:
                        break_input_link(tree, inp_alpha)
                    if inp_height:
                        break_input_link(tree, inp_height)

            # Merge process doesn't care with parents
            if not merged_layer_ids and layer.parent_idx != -1: continue

            if io_name in node.inputs: 
                outputs = create_link(tree, rgb, node.inputs[io_name])
                if io_name in outputs: rgb = outputs[io_name]

            if ch.enable_alpha and io_alpha_name in node.inputs:
                outputs = create_link(tree, alpha, node.inputs[io_alpha_name])
                if io_alpha_name in outputs: alpha = outputs[io_alpha_name]

            if height and io_height_name in node.inputs: 
                outputs = create_link(tree, height, node.inputs[io_height_name])
                if io_height_name in outputs: height = outputs[io_height_name]

            if height_n and io_height_n_name in node.inputs: 
                outputs = create_link(tree, height_n, node.inputs[io_height_n_name])
                if io_height_n_name in outputs: height_n = outputs[io_height_n_name]

            if height_s and io_height_s_name in node.inputs: 
                outputs = create_link(tree, height_s, node.inputs[io_height_s_name])
                if io_height_s_name in outputs: height_s = outputs[io_height_s_name]

            if height_e and io_height_e_name in node.inputs: 
                outputs = create_link(tree, height_e, node.inputs[io_height_e_name])
                if io_height_e_name in outputs: height_e = outputs[io_height_e_name]

            if height_w and io_height_w_name in node.inputs: 
                outputs = create_link(tree, height_w, node.inputs[io_height_w_name])
                if io_height_w_name in outputs: height_w = outputs[io_height_w_name]

            if height_alpha and io_height_alpha_name in node.inputs:
                height_alpha = create_link(tree, height_alpha, node.inputs[io_height_alpha_name])[io_height_alpha_name]

            if height_n_alpha and io_height_n_alpha_name in node.inputs:
                height_n_alpha = create_link(tree, height_n_alpha, node.inputs[io_height_n_alpha_name])[io_height_n_alpha_name]

            if height_s_alpha and io_height_s_alpha_name in node.inputs:
                height_s_alpha = create_link(tree, height_s_alpha, node.inputs[io_height_s_alpha_name])[io_height_s_alpha_name]

            if height_e_alpha and io_height_e_alpha_name in node.inputs:
                height_e_alpha = create_link(tree, height_e_alpha, node.inputs[io_height_e_alpha_name])[io_height_e_alpha_name]

            if height_w_alpha and io_height_w_alpha_name in node.inputs:
                height_w_alpha = create_link(tree, height_w_alpha, node.inputs[io_height_w_alpha_name])[io_height_w_alpha_name]

            if max_height and io_max_height_name in node.inputs:
                outps = create_link(tree, max_height, node.inputs[io_max_height_name])
                if io_max_height_name in outps:
                    max_height = outps[io_max_height_name]

            if vdisp and io_vdisp_name in node.inputs:
                outps = create_link(tree, vdisp, node.inputs[io_vdisp_name])
                if io_vdisp_name in outps:
                    vdisp = outps[io_vdisp_name]

        rgb, alpha = reconnect_all_modifier_nodes(tree, ch, rgb, alpha)

        normal_no_bump = None

        if end_linear and (end_linear.type != 'GROUP' or end_linear.node_tree):
            if ch.type == 'NORMAL':

                normal_no_bump = rgb

                if 'Normal Overlay' in end_linear.inputs:
                    rgb = create_link(tree, rgb, end_linear.inputs['Normal Overlay'])[0]
                else: rgb = end_linear.outputs[0]

                if 'Main UV' in end_linear.inputs and ch.main_uv in uv_maps:
                    create_link(tree, uv_maps[ch.main_uv], end_linear.inputs['Main UV'])

                #if end_normal_engine_filter:
                #    create_link(tree, rgb, end_normal_engine_filter.inputs[0])
                #    create_link(tree, normal_no_bump, end_normal_engine_filter.inputs[1])
                #    rgb = create_link(tree, rgb, end_normal_engine_filter.inputs[2])[0]

                #if end_max_height:
                #    create_link(tree, end_max_height.outputs[0], end_linear.inputs['Max Height'])
                if max_height:

                    if end_max_height_tweak and 'Max Height' in end_max_height_tweak.inputs:
                        max_height = create_link(tree, max_height, end_max_height_tweak.inputs['Max Height'])['Max Height']

                    create_link(tree, max_height, end_linear.inputs['Max Height'])

                if end_max_height_tweak:
                    if height and 'Height' in end_max_height_tweak.inputs:
                        height = create_link(tree, height, end_max_height_tweak.inputs['Height'])['Height']

                    if height_n and 'Height N' in end_max_height_tweak.inputs:
                        height_n = create_link(tree, height_n, end_max_height_tweak.inputs['Height N'])['Height N']

                    if height_s and 'Height S' in end_max_height_tweak.inputs:
                        height_s = create_link(tree, height_s, end_max_height_tweak.inputs['Height S'])['Height S']

                    if height_e and 'Height E' in end_max_height_tweak.inputs:
                        height_e = create_link(tree, height_e, end_max_height_tweak.inputs['Height E'])['Height E']

                    if height_w and 'Height W' in end_max_height_tweak.inputs:
                        height_w = create_link(tree, height_w, end_max_height_tweak.inputs['Height W'])['Height W']

                if height and 'Height' in end_linear.inputs: height = create_link(tree, height, end_linear.inputs['Height'])[1]
                if height_n and 'Height N' in end_linear.inputs: create_link(tree, height_n, end_linear.inputs['Height N'])
                if height_s and 'Height S' in end_linear.inputs: create_link(tree, height_s, end_linear.inputs['Height S'])
                if height_e and 'Height E' in end_linear.inputs: create_link(tree, height_e, end_linear.inputs['Height E'])
                if height_w and 'Height W' in end_linear.inputs: create_link(tree, height_w, end_linear.inputs['Height W'])

                if height_alpha and 'Height Alpha' in end_linear.inputs: create_link(tree, height_alpha, end_linear.inputs['Height Alpha'])
                if height_n_alpha and 'Height Alpha N' in end_linear.inputs: create_link(tree, height_n_alpha, end_linear.inputs['Height Alpha N'])
                if height_s_alpha and 'Height Alpha S' in end_linear.inputs: create_link(tree, height_s_alpha, end_linear.inputs['Height Alpha S'])
                if height_e_alpha and 'Height Alpha E' in end_linear.inputs: create_link(tree, height_e_alpha, end_linear.inputs['Height Alpha E'])
                if height_w_alpha and 'Height Alpha W' in end_linear.inputs: create_link(tree, height_w_alpha, end_linear.inputs['Height Alpha W'])

                if 'Start Height' in end_linear.inputs and start_bump_process:
                    create_link(tree, start_bump_process.outputs[0], end_linear.inputs['Start Height'])
                
                if tangent and 'Tangent' in end_linear.inputs:
                    create_link(tree, tangent, end_linear.inputs['Tangent'])

                if bitangent and 'Bitangent' in end_linear.inputs:
                    create_link(tree, bitangent, end_linear.inputs['Bitangent'])
            else:
                rgb = create_link(tree, rgb, end_linear.inputs[0])[0]

        if clamp:
            mixcol0, mixcol1, mixout = get_mix_color_indices(clamp)
            rgb = create_link(tree, rgb, clamp.inputs[mixcol0])[mixout]

        if yp.use_baked and not ch.no_layer_using and not ch.disable_global_baked and not ch.use_baked_vcol: # and baked_uv:
            baked = nodes.get(ch.baked)
            if baked:
                rgb = baked.outputs[0]

                #if ch.type == 'RGB' and ch.enable_alpha:
                if ch.enable_alpha:
                    alpha = baked.outputs[1]

                create_link(tree, baked_uv_map, baked.inputs[0])

            # Use baked color alpha if baked alpha is not found
            elif alpha_ch == ch:

                baked_color = nodes.get(color_ch.baked)
                if baked_color:
                    rgb = baked_color.outputs[1]

            if ch.type == 'NORMAL':
                baked_normal = nodes.get(ch.baked_normal)
                baked_normal_overlay = nodes.get(ch.baked_normal_overlay)
                baked_normal_prep = nodes.get(ch.baked_normal_prep)
                baked_disp = nodes.get(ch.baked_disp)
                baked_vdisp = nodes.get(ch.baked_vdisp)

                if ch.enable_subdiv_setup:
                    if end_normal_engine_filter:
                        if baked_normal_overlay:
                            #create_link(tree, baked_normal_overlay.outputs[0], end_normal_engine_filter.inputs['Cycles'])
                            create_link(tree, baked_normal_overlay.outputs[0], end_normal_engine_filter.inputs['Eevee'])
                            create_link(tree, baked_normal_overlay.outputs[0], end_normal_engine_filter.inputs[2])
                        else: 
                            #break_input_link(tree, end_normal_engine_filter.inputs['Cycles'])
                            create_link(tree, rgb, end_normal_engine_filter.inputs['Eevee'])
                            create_link(tree, rgb, end_normal_engine_filter.inputs[2])

                        if rgb:
                            #create_link(tree, rgb, end_normal_engine_filter.inputs[2])
                            #rgb = create_link(tree, rgb, end_normal_engine_filter.inputs['Eevee'])[0]
                            rgb = create_link(tree, rgb, end_normal_engine_filter.inputs['Cycles'])[0]

                    #elif baked_normal_overlay:
                    #    rgb = baked_normal_overlay.outputs[0]

                if baked_normal_prep:
                    if rgb:
                        rgb = create_link(tree, rgb, baked_normal_prep.inputs[0])[0]
                    else:
                        rgb = baked_normal_prep.outputs[0]
                        break_input_link(tree, baked_normal_prep.inputs[0])

                    #HACK: Some earlier nodes have wrong default colot input
                    baked_normal_prep.inputs[0].default_value = (0.5, 0.5, 1.0, 1.0)

                if baked_normal:
                    rgb = create_link(tree, rgb, baked_normal.inputs[1])[0]

                if baked_disp: 
                    height = baked_disp.outputs[0]
                    create_link(tree, baked_uv_map, baked_disp.inputs[0])

                if baked_vdisp: 
                    vdisp = baked_vdisp.outputs[0]
                    create_link(tree, baked_uv_map, baked_vdisp.inputs[0])

                if end_max_height:
                    max_height = end_max_height.outputs[0]

        if end_backface:
            if alpha_ch and alpha_ch == ch:
                rgb = create_link(tree, rgb, end_backface.inputs[0])[0]
            else: alpha = create_link(tree, alpha, end_backface.inputs[0])[0]
            #create_link(tree, geometry.outputs['Backfacing'], end_backface.inputs[1])
            create_link(tree, get_essential_node(tree, GEOMETRY)['Backfacing'], end_backface.inputs[1])

        if yp.use_baked and ch.use_baked_vcol and not ch.disable_global_baked:
            baked_vcol = nodes.get(ch.baked_vcol)
            if baked_vcol:
                if ch.bake_to_vcol_alpha:
                    rgb = baked_vcol.outputs['Alpha']
                else:
                    rgb = baked_vcol.outputs['Color']
                if is_channel_alpha_enabled(ch):
                    alpha = baked_vcol.outputs['Alpha']

        #print(rgb)
        # Blender 2.79 cycles does not need bump normal
        if not is_bl_newer_than(2, 80) and normal_no_bump and ch.type == 'NORMAL' and ch.enable_subdiv_setup:
            create_link(tree, normal_no_bump, end.inputs[io_name])
        else: create_link(tree, rgb, end.inputs[io_name])

        #if ch.type == 'RGB' and ch.enable_alpha:
        if ch.enable_alpha:
            create_link(tree, alpha, end.inputs[io_alpha_name])
        if ch.type == 'NORMAL' and not ch.use_baked_vcol:
            if height and io_height_name in end.inputs: create_link(tree, height, end.inputs[io_height_name])
            if max_height and io_max_height_name in end.inputs: create_link(tree, max_height, end.inputs[io_max_height_name])
            if io_vdisp_name in end.inputs: 
                if yp.sculpt_mode:
                    create_link(tree, get_essential_node(tree, ZERO_VALUE)[0], end.inputs[io_vdisp_name])
                elif vdisp: create_link(tree, vdisp, end.inputs[io_vdisp_name])

    # Bake target image nodes
    for bt in yp.bake_targets:
        image_node = nodes.get(bt.image_node)
        if image_node and baked_uv_map:
            create_link(tree, baked_uv_map, image_node.inputs[0])

    # Merge process doesn't care with parents
    if merged_layer_ids: return

    # List of last members
    last_members = []
    for layer in yp.layers:
        if not layer.enable: continue
        if is_bottom_member(layer, True):
            last_members.append(layer)

        # Remove unused input links
        node = tree.nodes.get(layer.group_node)
        if layer.type == 'GROUP':
            remove_unused_group_node_connections(tree, layer, node)
        remove_all_prev_inputs(tree, layer, node)

    # Group stuff
    for layer in last_members:

        node = nodes.get(layer.group_node)

        cur_layer = layer
        cur_node = node

        # Dictionary of Outputs
        outs = {}
        for outp in node.outputs:
            outs[outp.name] = outp

        while True:
            # Get upper layer
            upper_idx, upper_layer = get_upper_neighbor(cur_layer)
            upper_node = nodes.get(upper_layer.group_node)

            # Connect
            if upper_layer.parent_idx == cur_layer.parent_idx:
                if upper_layer.enable:
                    for inp in upper_node.inputs:
                        if inp.name in outs:
                            o = create_link(tree, outs[inp.name], inp)
                            if inp.name in o:
                                outs[inp.name] = o[inp.name]
                        elif inp.name in upper_node.outputs: 
                            outs[inp.name] = upper_node.outputs[inp.name]

                cur_layer = upper_layer
                cur_node = upper_node
            else:

                for output_name, outp in outs.items():
                    io_name =  output_name + io_suffix['GROUP']
                    if io_name in upper_node.inputs:
                        create_link(tree, outp, upper_node.inputs[io_name])

                break

    # Clean unused essential nodes
    clean_essential_nodes(tree)

def reconnect_channel_source_internal_nodes(ch, ch_source_tree):

    tree = ch_source_tree

    source = tree.nodes.get(ch.source)
    linear = tree.nodes.get(ch.linear)
    start = tree.nodes.get(TREE_START)
    #solid = tree.nodes.get(ONE_VALUE)
    end = tree.nodes.get(TREE_END)

    create_link(tree, start.outputs[0], source.inputs[0])

    rgb = source.outputs[0]
    if ch.override_type == 'MUSGRAVE':
        alpha = get_essential_node(tree, ONE_VALUE)[0]
    else: alpha = source.outputs[1]

    if linear:
        rgb = create_link(tree, rgb, linear.inputs[0])[0]

    if ch.override_type not in {'IMAGE', 'VCOL', 'HEMI', 'OBJECT_INDEX', 'MUSGRAVE'}:
        rgb_1 = source.outputs[1]
        alpha = get_essential_node(tree, ONE_VALUE)[0]
        alpha_1 = get_essential_node(tree, ONE_VALUE)[0]

        #mod_group = tree.nodes.get(ch.mod_group)
        #if mod_group:
        #    rgb, alpha = reconnect_all_modifier_nodes(tree, ch, rgb, alpha, mod_group)

        #mod_group_1 = tree.nodes.get(ch.mod_group_1)
        #if mod_group_1:
        #    rgb_1 = create_link(tree, rgb_1, mod_group_1.inputs[0])[0]
        #    alpha_1 = create_link(tree, alpha_1, mod_group_1.inputs[1])[1]

        create_link(tree, rgb_1, end.inputs[2])
        create_link(tree, alpha_1, end.inputs[3])

    create_link(tree, rgb, end.inputs[0])
    create_link(tree, alpha, end.inputs[1])

    # Clean unused essential nodes
    clean_essential_nodes(tree, exclude_texcoord=True, exclude_geometry=True)

def reconnect_source_internal_nodes(layer):
    tree = get_source_tree(layer)

    source = tree.nodes.get(layer.source)
    linear = tree.nodes.get(layer.linear)
    divider_alpha = tree.nodes.get(layer.divider_alpha)
    flip_y = tree.nodes.get(layer.flip_y)
    start = tree.nodes.get(TREE_START)
    #solid = tree.nodes.get(ONE_VALUE)
    end = tree.nodes.get(TREE_END)

    create_link(tree, start.outputs[0], source.inputs[0])

    if is_bl_newer_than(2, 81) and layer.type == 'VORONOI' and layer.voronoi_feature == 'N_SPHERE_RADIUS':
        rgb = source.outputs['Radius']
    else: rgb = source.outputs[0]

    if layer.type == 'MUSGRAVE':
        alpha = get_essential_node(tree, ONE_VALUE)[0]
    else: alpha = source.outputs[1]

    if divider_alpha: 
        mixcol0, mixcol1, mixout = get_mix_color_indices(divider_alpha)
        rgb = create_link(tree, rgb, divider_alpha.inputs[mixcol0])[mixout]
        create_link(tree, alpha, divider_alpha.inputs[mixcol1])

    if linear:
        rgb = create_link(tree, rgb, linear.inputs[0])[0]

    if flip_y:
        rgb = create_link(tree, rgb, flip_y.inputs[0])[0]

    if layer.type not in {'IMAGE', 'VCOL', 'HEMI', 'OBJECT_INDEX', 'MUSGRAVE', 'EDGE_DETECT', 'AO'}:
        rgb_1 = source.outputs[1]
        alpha = get_essential_node(tree, ONE_VALUE)[0]
        alpha_1 = get_essential_node(tree, ONE_VALUE)[0]

        mod_group = tree.nodes.get(layer.mod_group)
        if mod_group:
            rgb, alpha = reconnect_all_modifier_nodes(tree, layer, rgb, alpha, mod_group)

        mod_group_1 = tree.nodes.get(layer.mod_group_1)
        if mod_group_1:
            rgb_1 = create_link(tree, rgb_1, mod_group_1.inputs[0])[0]
            alpha_1 = create_link(tree, alpha_1, mod_group_1.inputs[1])[1]

        create_link(tree, rgb_1, end.inputs[2])
        create_link(tree, alpha_1, end.inputs[3])

    if layer.type in {'IMAGE', 'VCOL', 'HEMI', 'OBJECT_INDEX', 'MUSGRAVE', 'EDGE_DETECT', 'AO'}:

        rgb, alpha = reconnect_all_modifier_nodes(tree, layer, rgb, alpha)

    create_link(tree, rgb, end.inputs[0])
    create_link(tree, alpha, end.inputs[1])

    # Clean unused essential nodes
    clean_essential_nodes(tree, exclude_texcoord=True, exclude_geometry=True)

def reconnect_mask_internal_nodes(mask, mask_source_index=0):

    tree = get_mask_tree(mask)

    baked_source = tree.nodes.get(mask.baked_source)
    if baked_source and mask.use_baked:
        source = baked_source
    else: source = tree.nodes.get(mask.source)
    linear = tree.nodes.get(mask.linear)
    separate_color_channels = tree.nodes.get(mask.separate_color_channels)
    start = tree.nodes.get(TREE_START)
    end = tree.nodes.get(TREE_END)

    if mask.type == 'MODIFIER' and mask.modifier_type in {'INVERT', 'CURVE'}:
        create_link(tree, start.outputs[0], source.inputs[1])
    elif mask.use_baked or mask.type not in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'BACKFACE', 'EDGE_DETECT', 'AO'}:
        create_link(tree, start.outputs[0], source.inputs[0])

    val = source.outputs[mask_source_index]

    if mask.source_input in {'R', 'G', 'B'}:
        separate_color_channels_outputs = create_link(tree, val, separate_color_channels.inputs[0])
        if mask.source_input == 'R': val = separate_color_channels_outputs[0]
        elif mask.source_input == 'G': val = separate_color_channels_outputs[1]
        elif mask.source_input == 'B': val = separate_color_channels_outputs[2]

    if linear:
        val = create_link(tree, val, linear.inputs[0])[0]

    for mod in mask.modifiers:
        val = reconnect_mask_modifier_nodes(tree, mod, val)

    create_link(tree, val, end.inputs[0])

def reconnect_layer_nodes(layer, ch_idx=-1, merge_mask=False):
    yp = layer.id_data.yp

    #print('Reconnect layer ' + layer.name)
    if yp.halt_reconnect: return

    tree = get_tree(layer)
    nodes = tree.nodes

    source_group = nodes.get(layer.source_group)

    #if layer.source_group != '':
    if source_group:
        source = source_group
        reconnect_source_internal_nodes(layer)
    else: source = nodes.get(layer.source)

    baked_source = None
    if layer.use_baked:
        baked_source = nodes.get(layer.baked_source)

    # Direction sources
    source_n = nodes.get(layer.source_n)
    source_s = nodes.get(layer.source_s)
    source_e = nodes.get(layer.source_e)
    source_w = nodes.get(layer.source_w)

    uv_map = nodes.get(layer.uv_map)
    uv_neighbor = nodes.get(layer.uv_neighbor)
    uv_neighbor_1 = nodes.get(layer.uv_neighbor_1)

    #if layer.type == 'GROUP':
    #    texcoord = source
    #else: texcoord = nodes.get(layer.texcoord)

    #texcoord = nodes.get(TEXCOORD)
    texcoord = nodes.get(layer.texcoord)
    #geometry = nodes.get(GEOMETRY)
    blur_vector = nodes.get(layer.blur_vector)
    mapping = nodes.get(layer.mapping)
    linear = nodes.get(layer.linear)
    divider_alpha = nodes.get(layer.divider_alpha)
    flip_y = nodes.get(layer.flip_y)
    decal_process = nodes.get(layer.decal_process)

    # Get tangent and bitangent
    layer_tangent = get_essential_node(tree, TREE_START).get(layer.uv_name + io_suffix['TANGENT'])
    layer_bitangent = get_essential_node(tree, TREE_START).get(layer.uv_name + io_suffix['BITANGENT'])

    height_root_ch = get_root_height_channel(yp)
    if height_root_ch and height_root_ch.main_uv != '':
        tangent = get_essential_node(tree, TREE_START).get(height_root_ch.main_uv + io_suffix['TANGENT'])
        bitangent = get_essential_node(tree, TREE_START).get(height_root_ch.main_uv + io_suffix['BITANGENT'])
    else:
        tangent = layer_tangent
        bitangent = layer_bitangent

    # Fake lighting stuff
    bump_process = nodes.get(layer.bump_process)
    if bump_process and height_root_ch:

        prev_normal = get_essential_node(tree, TREE_START).get(height_root_ch.name)
        prev_height = get_essential_node(tree, TREE_START).get(height_root_ch.name + io_suffix['HEIGHT'])
        prev_max_height = get_essential_node(tree, TREE_START).get(height_root_ch.name + io_suffix['MAX_HEIGHT'])

        if prev_height and 'Height' in bump_process.inputs: create_link(tree, prev_height, bump_process.inputs['Height'])
        if prev_max_height and 'Max Height' in bump_process.inputs: create_link(tree, prev_max_height, bump_process.inputs['Max Height'])

        if height_root_ch.enable_smooth_bump:
            prev_height_n = get_essential_node(tree, TREE_START).get(height_root_ch.name + io_suffix['HEIGHT_N'])
            prev_height_s = get_essential_node(tree, TREE_START).get(height_root_ch.name + io_suffix['HEIGHT_S'])
            prev_height_e = get_essential_node(tree, TREE_START).get(height_root_ch.name + io_suffix['HEIGHT_E'])
            prev_height_w = get_essential_node(tree, TREE_START).get(height_root_ch.name + io_suffix['HEIGHT_W'])

            if prev_height_n and 'Height N' in bump_process.inputs: create_link(tree, prev_height_n, bump_process.inputs['Height N'])
            if prev_height_s and 'Height S' in bump_process.inputs: create_link(tree, prev_height_s, bump_process.inputs['Height S'])
            if prev_height_e and 'Height E' in bump_process.inputs: create_link(tree, prev_height_e, bump_process.inputs['Height E'])
            if prev_height_w and 'Height W' in bump_process.inputs: create_link(tree, prev_height_w, bump_process.inputs['Height W'])

        if prev_normal: create_link(tree, prev_normal, bump_process.inputs['Normal Overlay'])
        if tangent and 'Tangent' in bump_process.inputs: create_link(tree, tangent, bump_process.inputs['Tangent'])
        if bitangent and 'Bitangent' in bump_process.inputs: create_link(tree, bitangent, bump_process.inputs['Bitangent'])

    # Edge Detect related
    if layer.type == 'EDGE_DETECT':
        edge_detect_radius_val = get_essential_node(tree, TREE_START).get(get_entity_input_name(layer, 'edge_detect_radius'))
        if edge_detect_radius_val and 'Radius' in source.inputs:
            create_link(tree, edge_detect_radius_val, source.inputs['Radius'])

    # AO Related
    elif layer.type == 'AO':
        ao_distance_val = get_essential_node(tree, TREE_START).get(get_entity_input_name(layer, 'ao_distance'))
        if ao_distance_val and 'Distance' in source.inputs:
            create_link(tree, ao_distance_val, source.inputs['Distance'])

    # Use previous normal
    if layer.type in {'HEMI', 'EDGE_DETECT', 'AO'}:
        if layer.hemi_use_prev_normal and bump_process:
            create_link(tree, bump_process.outputs['Normal'], source.inputs['Normal'])
        elif 'Normal' in source.inputs: create_link(tree, get_essential_node(tree, GEOMETRY)['Normal'], source.inputs['Normal'])

    # Find override channels
    #using_vector = is_channel_override_using_vector(layer)

    baked_vector = None
    if layer.use_baked:
        baked_vector = get_essential_node(tree, TREE_START).get(layer.baked_uv_name + io_suffix['UV'])

    if baked_vector and baked_source:
        create_link(tree, baked_vector, baked_source.inputs[0])

    # Texcoord
    vector = None
    if is_layer_using_vector(layer):
        if layer.texcoord_type == 'UV':
            vector = get_essential_node(tree, TREE_START).get(layer.uv_name + io_suffix['UV'])
        elif layer.texcoord_type == 'Decal':
            if texcoord:
                vector = texcoord.outputs['Object']
                if decal_process: 
                    layer_decal_distance = get_essential_node(tree, TREE_START).get(get_entity_input_name(layer, 'decal_distance_value'))
                    vector = create_link(tree, vector, decal_process.inputs[0])[0]
                    if layer_decal_distance: create_link(tree, layer_decal_distance, decal_process.inputs[1])
        else: vector = get_essential_node(tree, TREE_START).get(io_names[layer.texcoord_type])

        if vector and blur_vector:
            vector = create_link(tree, vector, blur_vector.inputs[1])[0]

            layer_blur_factor = get_essential_node(tree, TREE_START).get(get_entity_input_name(layer, 'blur_vector_factor'))
            if layer_blur_factor: create_link(tree, layer_blur_factor, blur_vector.inputs[0])

        if vector and mapping and layer.texcoord_type != 'Decal':
            vector = create_link(tree, vector, mapping.inputs[0])[0]
        
        # Layer UV uniform scale value
        if is_bl_newer_than(2, 81):
            uniform_scale_value = get_essential_node(tree, TREE_START).get(get_entity_input_name(layer, 'uniform_scale_value'))
            if uniform_scale_value:
                if layer.enable_uniform_scale:
                    create_link(tree, uniform_scale_value, mapping.inputs[3])
                else:
                    break_link(tree, uniform_scale_value, mapping.inputs[3])

    if vector:
        if 'Vector' in source.inputs:
            create_link(tree, vector, source.inputs['Vector'])

        if layer.type not in {'VCOL', 'BACKGROUND', 'COLOR', 'GROUP', 'HEMI', 'OBJECT_INDEX', 'EDGE_DETECT', 'AO'}:

            if uv_neighbor: 
                create_link(tree, vector, uv_neighbor.inputs[0])

                if tangent and 'Tangent' in uv_neighbor.inputs:
                    create_link(tree, tangent, uv_neighbor.inputs['Tangent'])
                    create_link(tree, bitangent, uv_neighbor.inputs['Bitangent'])

                if layer_tangent:
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
    if baked_source:
        start_rgb = baked_source.outputs[0]
    elif is_bl_newer_than(2, 81) and layer.type == 'VORONOI' and layer.voronoi_feature == 'N_SPHERE_RADIUS' and 'Radius' in source.outputs:
        start_rgb = source.outputs['Radius']
    else: start_rgb = source.outputs[0]

    start_rgb_1 = None
    if layer.type not in {'COLOR', 'HEMI', 'OBJECT_INDEX', 'MUSGRAVE', 'EDGE_DETECT', 'AO'} and len(source.outputs) > 1:
        start_rgb_1 = source.outputs[1]

    # Alpha
    if baked_source:
        start_alpha = baked_source.outputs[1]
    elif layer.type == 'IMAGE' or source_group:
        start_alpha = source.outputs[1]
    elif layer.type == 'VCOL' and 'Alpha' in source.outputs:
        start_alpha = source.outputs['Alpha']
    else: start_alpha = get_essential_node(tree, ONE_VALUE)[0]
    start_alpha_1 = get_essential_node(tree, ONE_VALUE)[0]

    alpha_preview = get_essential_node(tree, TREE_END).get(LAYER_ALPHA_VIEWER)

    # RGB continued
    if not source_group:
        if divider_alpha: 
            mixcol0, mixcol1, mixout = get_mix_color_indices(divider_alpha)
            start_rgb = create_link(tree, start_rgb, divider_alpha.inputs[mixcol0])[mixout]
            create_link(tree, start_alpha, divider_alpha.inputs[mixcol1])
        if linear: start_rgb = create_link(tree, start_rgb, linear.inputs[0])[0]
        if flip_y: start_rgb = create_link(tree, start_rgb, flip_y.inputs[0])[0]

    if source_group and layer.type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'HEMI', 'OBJECT_INDEX', 'MUSGRAVE', 'EDGE_DETECT', 'AO'}:
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
                tree, layer, start_rgb, start_alpha, mod_group
            )

        if layer.type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'COLOR', 'GROUP', 'HEMI', 'OBJECT_INDEX', 'MUSGRAVE', 'EDGE_DETECT', 'AO'}:
            mod_group_1 = nodes.get(layer.mod_group_1)
            start_rgb_1, start_alpha_1 = reconnect_all_modifier_nodes(
                tree, layer, source.outputs[1], get_essential_node(tree, ONE_VALUE)[0], mod_group_1
            )

    # UV neighbor vertex color
    if layer.type in {'VCOL', 'GROUP', 'HEMI', 'OBJECT_INDEX', 'EDGE_DETECT', 'AO'} and uv_neighbor:
        if layer.type in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'EDGE_DETECT', 'AO'}:
            create_link(tree, start_rgb, uv_neighbor.inputs[0])

        if tangent and bitangent:
            if 'Tangent' in uv_neighbor.inputs: create_link(tree, tangent, uv_neighbor.inputs['Tangent'])
            if 'Bitangent' in uv_neighbor.inputs: create_link(tree, bitangent, uv_neighbor.inputs['Bitangent'])

        if layer.type == 'VCOL' and uv_neighbor_1:
            create_link(tree, start_alpha, uv_neighbor_1.inputs[0])

            if tangent and bitangent:
                if 'Tangent' in uv_neighbor_1.inputs: create_link(tree, tangent, uv_neighbor_1.inputs['Tangent'])
                if 'Bitangent' in uv_neighbor_1.inputs: create_link(tree, bitangent, uv_neighbor_1.inputs['Bitangent'])

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
    compare_alpha = None
    height_ch = get_height_channel(layer)
    bump_smooth_multiplier_value = None
    if height_ch:
        if height_ch.normal_blend_type == 'COMPARE':
            height_blend = nodes.get(height_ch.height_blend)
            if height_blend: compare_alpha = height_blend.outputs.get('Normal Alpha')

        # UV Neighbor multiplier
        bump_smooth_multiplier_value = get_essential_node(tree, TREE_START).get(get_entity_input_name(height_ch, 'bump_smooth_multiplier'))
        if bump_smooth_multiplier_value:

            if uv_neighbor and 'Multiplier' in uv_neighbor.inputs:
                create_link(tree, bump_smooth_multiplier_value, uv_neighbor.inputs['Multiplier'])

            if uv_neighbor_1 and 'Multiplier' in uv_neighbor_1.inputs:
                create_link(tree, bump_smooth_multiplier_value, uv_neighbor_1.inputs['Multiplier'])

    chain = -1
    tb_value = None
    tb_second_value = None
    if trans_bump_ch:
        #if trans_bump_ch.write_height:
        #    chain = 10000
        #else: 
        chain = min(len(layer.masks), trans_bump_ch.transition_bump_chain)

        tb_value = get_essential_node(tree, TREE_START).get(get_entity_input_name(trans_bump_ch, 'transition_bump_value'))
        tb_second_value = get_essential_node(tree, TREE_START).get(get_entity_input_name(trans_bump_ch, 'transition_bump_second_edge_value'))

    # Root mask value for merging mask
    root_mask_val = get_essential_node(tree, ONE_VALUE)[0]

    # Layer Masks
    for i, mask in enumerate(layer.masks):
        # Get source output index
        mask_source_index = 0
        if not mask.use_baked and mask.type not in {'COLOR_ID', 'HEMI', 'OBJECT_INDEX', 'EDGE_DETECT', 'AO'}:
            # Noise and voronoi output has flipped order since Blender 2.81
            if is_bl_newer_than(2, 81) and mask.type == 'VORONOI' and mask.voronoi_feature == 'DISTANCE_TO_EDGE':
                mask_source_index = 'Distance'
            elif is_bl_newer_than(2, 81) and mask.type == 'VORONOI' and mask.voronoi_feature == 'N_SPHERE_RADIUS':
                mask_source_index = 'Radius'
            elif is_bl_newer_than(2, 81) and mask.type in {'NOISE', 'VORONOI'}:
                if mask.source_input == 'RGB':
                    mask_source_index = 1
            elif mask.type == 'BACKFACE':
                mask_source_index = 'Backfacing'
            elif mask.source_input == 'ALPHA':
                if mask.type == 'VCOL':
                    if is_bl_newer_than(2, 92):
                        mask_source_index = 'Alpha'
                    else: mask_source_index = 'Fac'
                else: mask_source_index = 1

        # Mask source
        if mask.group_node != '':
            mask_source = nodes.get(mask.group_node)
            reconnect_mask_internal_nodes(mask, mask_source_index)

            #mask_val = mask_source.outputs[mask_source_index]
            mask_val = mask_source.outputs[0]
        else:
            baked_mask_source = nodes.get(mask.baked_source)
            if baked_mask_source and mask.use_baked:
                mask_source = baked_mask_source
            else: mask_source = nodes.get(mask.source)
            mask_linear = nodes.get(mask.linear)
            mask_separate_color_channels = nodes.get(mask.separate_color_channels)

            if mask.type == 'BACKFACE':
                mask_val = get_essential_node(tree, GEOMETRY)[mask_source_index]
            else: mask_val = mask_source.outputs[mask_source_index]

            if mask.source_input in {'R', 'G', 'B'}:
                separate_color_channels_outputs = create_link(tree, mask_val, mask_separate_color_channels.inputs[0])
                if mask.source_input == 'R': mask_val = separate_color_channels_outputs[0]
                elif mask.source_input == 'G': mask_val = separate_color_channels_outputs[1]
                elif mask.source_input == 'B': mask_val = separate_color_channels_outputs[2]

            if mask_linear:
                mask_val = create_link(tree, mask_val, mask_linear.inputs[0])[0]

            for mod in mask.modifiers:
                mask_val = reconnect_mask_modifier_nodes(tree, mod, mask_val)

        mask_blur_vector = nodes.get(mask.blur_vector)
        mask_mapping = nodes.get(mask.mapping)
        mask_decal_process = nodes.get(mask.decal_process)
        mask_decal_alpha = nodes.get(mask.decal_alpha)
        mask_texcoord = nodes.get(mask.texcoord)

        if mask_decal_alpha and mask_decal_process:
            mask_val = create_link(tree, mask_val, mask_decal_alpha.inputs[0])[0]
            create_link(tree, mask_decal_process.outputs[1], mask_decal_alpha.inputs[1])

        if yp.layer_preview_mode and yp.layer_preview_mode_type == 'SPECIFIC_MASK' and mask.active_edit == True:
            if alpha_preview:
                create_link(tree, mask_val, alpha_preview)

        # Color ID related
        if mask.type == 'COLOR_ID':
            color_id_val = get_essential_node(tree, TREE_START).get(get_entity_input_name(mask, 'color_id'))
            if color_id_val and 'Color ID' in mask_source.inputs:
                create_link(tree, color_id_val, mask_source.inputs['Color ID'])

        # Edge Detect related
        elif mask.type == 'EDGE_DETECT':
            edge_detect_radius_val = get_essential_node(tree, TREE_START).get(get_entity_input_name(mask, 'edge_detect_radius'))
            if edge_detect_radius_val and 'Radius' in mask_source.inputs:
                create_link(tree, edge_detect_radius_val, mask_source.inputs['Radius'])

        # AO related
        elif mask.type == 'AO':
            ao_distance_val = get_essential_node(tree, TREE_START).get(get_entity_input_name(mask, 'ao_distance'))
            if ao_distance_val and 'Distance' in mask_source.inputs:
                create_link(tree, ao_distance_val, mask_source.inputs['Distance'])

        # Hemi related
        if mask.type in {'HEMI', 'EDGE_DETECT', 'AO'} and not mask.use_baked: #and 'Normal' in mask_source.inputs:
            if mask.hemi_use_prev_normal and bump_process:
                create_link(tree, bump_process.outputs['Normal'], mask_source.inputs['Normal'])
            elif 'Normal' in mask_source.inputs: create_link(tree, get_essential_node(tree, GEOMETRY)['Normal'], mask_source.inputs['Normal'])

        # Mask source directions
        mask_val_n = None
        mask_val_s = None
        mask_val_e = None
        mask_val_w = None

        # Mask start
        mask_vector = None
        mask_uv_name = mask.uv_name if not mask.use_baked or mask.baked_uv_name == '' else mask.baked_uv_name
        if mask.use_baked or mask.type not in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'COLOR_ID', 'BACKFACE', 'EDGE_DETECT', 'AO'}:
            if mask.use_baked or mask.texcoord_type == 'UV':
                mask_vector = get_essential_node(tree, TREE_START).get(mask_uv_name + io_suffix['UV'])
            elif mask.texcoord_type == 'Decal':
                if mask_texcoord:
                    mask_vector = mask_texcoord.outputs['Object']
                    if mask_decal_process: 
                        layer_decal_distance = get_essential_node(tree, TREE_START).get(get_entity_input_name(mask, 'decal_distance_value'))
                        mask_vector = create_link(tree, mask_vector, mask_decal_process.inputs[0])[0]
                        if layer_decal_distance: create_link(tree, layer_decal_distance, mask_decal_process.inputs[1])
            elif mask.texcoord_type == 'Layer':
                mask_vector = vector
            else: 
                mask_vector = get_essential_node(tree, TREE_START).get(io_names[mask.texcoord_type])

            if mask_vector:

                if mask.use_baked:
                    mask_baked_mapping = nodes.get(mask.baked_mapping)
                    if mask_baked_mapping:
                        mask_vector = create_link(tree, mask_vector, mask_baked_mapping.inputs[0])[0]

                elif mask.texcoord_type != 'Layer':

                    mask_blur_factor = get_essential_node(tree, TREE_START).get(get_entity_input_name(mask, 'blur_vector_factor'))
                    if mask_blur_factor: create_link(tree, mask_blur_factor, mask_blur_vector.inputs[0])

                    if mask_blur_vector:
                        mask_vector = create_link(tree, mask_vector, mask_blur_vector.inputs[1])[0]

                    if mask_mapping and mask.texcoord_type != 'Decal':
                        mask_vector = create_link(tree, mask_vector, mask_mapping.inputs[0])[0]

                create_link(tree, mask_vector, mask_source.inputs[0])

                # Mask UV uniform scale value
                if is_bl_newer_than(2, 81):
                    uniform_scale_value = get_essential_node(tree, TREE_START).get(get_entity_input_name(mask, 'uniform_scale_value'))
                    if uniform_scale_value:
                        if mask.enable_uniform_scale:
                            create_link(tree, uniform_scale_value, mask_mapping.inputs[3])
                        else:
                            break_link(tree, uniform_scale_value, mask_mapping.inputs[3])

        # Mask uv neighbor
        mask_uv_neighbor = nodes.get(mask.uv_neighbor) if mask.texcoord_type != 'Layer' else uv_neighbor
        if mask_uv_neighbor:

            if not mask.use_baked and mask.type in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'COLOR_ID', 'BACKFACE', 'EDGE_DETECT', 'AO'}:
                create_link(tree, mask_val, mask_uv_neighbor.inputs[0])
            else:
                if mask_vector and mask.texcoord_type != 'Layer':
                    create_link(tree, mask_vector, mask_uv_neighbor.inputs[0])

                mask_source_n = nodes.get(mask.source_n)
                mask_source_s = nodes.get(mask.source_s)
                mask_source_e = nodes.get(mask.source_e)
                mask_source_w = nodes.get(mask.source_w)

                if mask_source_n: mask_val_n = create_link(tree, mask_uv_neighbor.outputs['n'], mask_source_n.inputs[0])[0]
                if mask_source_s: mask_val_s = create_link(tree, mask_uv_neighbor.outputs['s'], mask_source_s.inputs[0])[0]
                if mask_source_e: mask_val_e = create_link(tree, mask_uv_neighbor.outputs['e'], mask_source_e.inputs[0])[0]
                if mask_source_w: mask_val_w = create_link(tree, mask_uv_neighbor.outputs['w'], mask_source_w.inputs[0])[0]

                # Decal Stuff
                if mask_decal_process:

                    mask_decal_alpha_n = nodes.get(mask.decal_alpha_n)
                    mask_decal_alpha_s = nodes.get(mask.decal_alpha_s)
                    mask_decal_alpha_e = nodes.get(mask.decal_alpha_e)
                    mask_decal_alpha_w = nodes.get(mask.decal_alpha_w)

                    if mask_decal_alpha_n:
                        mask_val_n = create_link(tree, mask_val_n, mask_decal_alpha_n.inputs[0])[0]
                        create_link(tree, mask_decal_process.outputs[1], mask_decal_alpha_n.inputs[1])
                    if mask_decal_alpha_s:
                        mask_val_s = create_link(tree, mask_val_s, mask_decal_alpha_s.inputs[0])[0]
                        create_link(tree, mask_decal_process.outputs[1], mask_decal_alpha_s.inputs[1])
                    if mask_decal_alpha_e:
                        mask_val_e = create_link(tree, mask_val_e, mask_decal_alpha_e.inputs[0])[0]
                        create_link(tree, mask_decal_process.outputs[1], mask_decal_alpha_e.inputs[1])
                    if mask_decal_alpha_w:
                        mask_val_w = create_link(tree, mask_val_w, mask_decal_alpha_w.inputs[0])[0]
                        create_link(tree, mask_decal_process.outputs[1], mask_decal_alpha_w.inputs[1])

            if mask.texcoord_type != 'Layer':

                # UV Neighbor multiplier
                if bump_smooth_multiplier_value and 'Multiplier' in mask_uv_neighbor.inputs:
                    create_link(tree, bump_smooth_multiplier_value, mask_uv_neighbor.inputs['Multiplier'])

                # Mask tangent
                mask_tangent = get_essential_node(tree, TREE_START).get(mask_uv_name + io_suffix['TANGENT'])
                mask_bitangent = get_essential_node(tree, TREE_START).get(mask_uv_name + io_suffix['BITANGENT'])

                if 'Tangent' in mask_uv_neighbor.inputs:
                    if tangent: create_link(tree, tangent, mask_uv_neighbor.inputs['Tangent'])
                    if bitangent: create_link(tree, bitangent, mask_uv_neighbor.inputs['Bitangent'])

                if 'Mask Tangent' in mask_uv_neighbor.inputs:
                    if mask_tangent: create_link(tree, mask_tangent, mask_uv_neighbor.inputs['Mask Tangent'])
                    if mask_bitangent: create_link(tree, mask_bitangent, mask_uv_neighbor.inputs['Mask Bitangent'])

                if 'Entity Tangent' in mask_uv_neighbor.inputs:
                    if mask_tangent: create_link(tree, mask_tangent, mask_uv_neighbor.inputs['Entity Tangent'])
                    if mask_bitangent: create_link(tree, mask_bitangent, mask_uv_neighbor.inputs['Entity Bitangent'])

        # Mask root mix
        mmix = nodes.get(mask.mix)
        if mmix:
            mixcol0, mixcol1, mixout = get_mix_color_indices(mmix)
            root_mask_val = create_link(tree, root_mask_val, mmix.inputs[mixcol0])[mixout]
            create_link(tree, mask_val, mmix.inputs[mixcol1])

        # Mask intensity
        mask_intensity = get_essential_node(tree, TREE_START).get(get_entity_input_name(mask, 'intensity_value'))

        # Mask channels
        for j, c in enumerate(mask.channels):
            root_ch = yp.channels[j]
            ch = layer.channels[j]

            #if yp.disable_quick_toggle and not ch.enable:
            if not ch.enable:
                continue

            mask_mix = nodes.get(c.mix)
            mix_pure = nodes.get(c.mix_pure)
            mix_remains = nodes.get(c.mix_remains)
            mix_normal = nodes.get(c.mix_normal)

            mmixcol0, mmixcol1, mmixout = get_mix_color_indices(mask_mix)
            mp_mixcol0, mp_mixcol1, mp_mixout = get_mix_color_indices(mix_pure)
            mr_mixcol0, mr_mixcol1, mr_mixout = get_mix_color_indices(mix_remains)
            mn_mixcol0, mn_mixcol1, mn_mixout = get_mix_color_indices(mix_normal)

            if mix_pure:
                create_link(tree, mask_val, mix_pure.inputs[mp_mixcol1])
                if mask_intensity: create_link(tree, mask_intensity, mix_pure.inputs[0])

            if mix_remains:
                create_link(tree, mask_val, mix_remains.inputs[mr_mixcol1])
                if mask_intensity: create_link(tree, mask_intensity, mix_remains.inputs[0])

            if mix_normal:
                create_link(tree, mask_val, mix_normal.inputs[mn_mixcol1])
                if mask_intensity: create_link(tree, mask_intensity, mix_normal.inputs[0])

            if mask_mix:

                if mask_intensity: create_link(tree, mask_intensity, mask_mix.inputs[0])

                create_link(tree, mask_val, mask_mix.inputs[mmixcol1])
                if root_ch.type == 'NORMAL' and root_ch.enable_smooth_bump:
                    if not mask.use_baked and mask.type in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'COLOR_ID', 'BACKFACE', 'EDGE_DETECT', 'AO'}:
                        if mask_uv_neighbor:
                            if 'Color2 n' in mask_mix.inputs:
                                create_link(tree, mask_uv_neighbor.outputs['n'], mask_mix.inputs['Color2 n'])
                                create_link(tree, mask_uv_neighbor.outputs['s'], mask_mix.inputs['Color2 s'])
                                create_link(tree, mask_uv_neighbor.outputs['e'], mask_mix.inputs['Color2 e'])
                                create_link(tree, mask_uv_neighbor.outputs['w'], mask_mix.inputs['Color2 w'])
                        else: 
                            if 'Color2 n' in mask_mix.inputs:
                                create_link(tree, mask_val, mask_mix.inputs['Color2 n'])
                                create_link(tree, mask_val, mask_mix.inputs['Color2 s'])
                                create_link(tree, mask_val, mask_mix.inputs['Color2 e'])
                                create_link(tree, mask_val, mask_mix.inputs['Color2 w'])
                    else:
                        if 'Color2 n' in mask_mix.inputs:
                            if mask_val_n: 
                                create_link(tree, mask_val_n, mask_mix.inputs['Color2 n'])
                            else: 
                                create_link(tree, mask_val, mask_mix.inputs['Color2 n'])

                        if mask_val_s: create_link(tree, mask_val_s, mask_mix.inputs['Color2 s'])
                        if mask_val_e: create_link(tree, mask_val_e, mask_mix.inputs['Color2 e'])
                        if mask_val_w: create_link(tree, mask_val_w, mask_mix.inputs['Color2 w'])

    if merge_mask and yp.layer_preview_mode:
        if alpha_preview:
            create_link(tree, root_mask_val, alpha_preview)
        return

    # Layer intensity input
    layer_intensity_value = get_essential_node(tree, TREE_START).get(get_entity_input_name(layer, 'intensity_value'))
    
    # Parent flag
    has_parent = layer.parent_idx != -1

    # Get color and alpha channel
    color_ch, alpha_ch = get_layer_color_alpha_ch_pairs(layer)
    alpha_ch_rgb = None

    # Make sure alpha channel in earlier list so the output can be used with color channel
    if color_ch and alpha_ch:
        layer_channels = [alpha_ch, color_ch]
        for ch in layer.channels:
            if ch not in layer_channels:
                layer_channels.append(ch)
    else:
        layer_channels = layer.channels

    # Layer Channels
    for ch in layer_channels:

        i = get_layer_channel_index(layer, ch)
        root_ch = yp.channels[i]

        # Alpha channel will get ignored if color channel is also enabled
        channel_enabled = get_channel_enabled(ch, layer, root_ch) or (ch == alpha_ch and get_channel_enabled(color_ch))

        #if yp.disable_quick_toggle and not ch.enable: continue
        if not channel_enabled:
            
            # Disabled channel layer preview
            if yp.layer_preview_mode:
                if yp.layer_preview_mode_type == 'SPECIFIC_MASK' and ch.override and ch.active_edit == True:
                    if alpha_preview:
                        create_link(tree, get_essential_node(tree, ZERO_VALUE)[0], alpha_preview)
                elif root_ch == yp.channels[yp.active_channel_index]:
                    col_preview = get_essential_node(tree, TREE_END).get(LAYER_VIEWER)
                    if col_preview:
                        create_link(tree, get_essential_node(tree, ZERO_VALUE)[0], col_preview)
                    if alpha_preview:
                        create_link(tree, get_essential_node(tree, ZERO_VALUE)[0], alpha_preview)
                    #break_input_link(tree, col_preview)
                    #break_input_link(tree, alpha_preview)
                    #col_preview.default_value = (0,0,0,0)
                    #alpha_preview.default_value = 0

            continue

        # Rgb and alpha start
        rgb = start_rgb
        alpha = start_alpha
        bg_alpha = None

        # Use alpha channel output as alpha of color channel
        if ch == color_ch and alpha_ch_rgb:
            alpha = alpha_ch_rgb

        ch_intensity = get_essential_node(tree, TREE_START).get(get_entity_input_name(ch, 'intensity_value'))
        prev_rgb = get_essential_node(tree, TREE_START).get(root_ch.name)
        if alpha_ch and ch == color_ch:
            alpha_idx = get_layer_channel_index(layer, alpha_ch)
            root_alpha_ch = yp.channels[alpha_idx]
            prev_alpha = get_essential_node(tree, TREE_START).get(root_alpha_ch.name)
        else:
            prev_alpha = get_essential_node(tree, TREE_START).get(root_ch.name + io_suffix['ALPHA'])

        prev_vdisp = None
        next_vdisp = None

        height_alpha = None
        normal_alpha = None
        group_alpha = None

        ch_uv_neighbor = nodes.get(ch.uv_neighbor)
        #ch_uv_neighbor_1 = nodes.get(ch.uv_neighbor_1)

        ch_source_n = None
        ch_source_s = None
        ch_source_e = None
        ch_source_w = None

        if layer.type == 'GROUP':

            if root_ch.type == 'NORMAL' and ch.enable_transition_bump:

                group_height = source.outputs.get(root_ch.name + io_suffix['HEIGHT'] + io_suffix['GROUP'])
                if group_height: rgb = group_height

            else:
                group_channel = source.outputs.get(root_ch.name + io_suffix['GROUP'])
                if group_channel: rgb = group_channel

            if root_ch.type == 'NORMAL':
                group_height_alpha = source.outputs.get(root_ch.name + io_suffix['HEIGHT'] + io_suffix['ALPHA'] + io_suffix['GROUP'])
                if group_height_alpha: alpha = group_height_alpha

            else:
                group_channel_alpha = source.outputs.get(root_ch.name + io_suffix['ALPHA'] + io_suffix['GROUP'])
                if group_channel_alpha: alpha = group_channel_alpha

            group_alpha = alpha

        elif layer.type == 'BACKGROUND':
            source_rgb = source.outputs.get(root_ch.name + io_suffix['BACKGROUND'])
            if source_rgb: rgb = source_rgb
            alpha = get_essential_node(tree, ONE_VALUE)[0]

            if root_ch.enable_alpha:
                bg_alpha = source.outputs.get(root_ch.name + io_suffix['ALPHA'] + io_suffix['BACKGROUND'])

        # Get source output index
        source_index = 0
        if not layer.use_baked and layer.type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'COLOR', 'HEMI', 'OBJECT_INDEX', 'MUSGRAVE', 'EDGE_DETECT', 'AO'}:
            # Noise and voronoi output has flipped order since Blender 2.81
            if is_bl_newer_than(2, 81) and (layer.type == 'NOISE' or (layer.type == 'VORONOI' and layer.voronoi_feature not in {'DISTANCE_TO_EDGE', 'N_SPHERE_RADIUS'})):
                if ch.layer_input == 'RGB':
                    rgb = start_rgb_1
                    alpha = start_alpha_1
                    source_index = 2
            elif ch.layer_input == 'ALPHA':
                rgb = start_rgb_1
                alpha = start_alpha_1
                source_index = 2

        rgb_before_override = rgb

        # Use layer alpha as rgb of alpha channel if color channel is enabled
        if ch == alpha_ch and get_channel_enabled(color_ch):
            rgb = alpha

        # Channel Override 
        if ch.override and (root_ch.type != 'NORMAL' or ch.normal_map_type != 'NORMAL_MAP'):

            ch_source_group = nodes.get(ch.source_group)
            ch_source = None
            if ch_source_group:
                ch_source = ch_source_group
                reconnect_channel_source_internal_nodes(ch, ch_source_group.node_tree)
            else: 
                if ch.override_type == 'DEFAULT':
                    if root_ch.type == 'VALUE':
                        ch_override_value = get_essential_node(tree, TREE_START).get(get_entity_input_name(ch, 'override_value'))
                        if ch_override_value: rgb = ch_override_value
                    else: 
                        ch_override_color = get_essential_node(tree, TREE_START).get(get_entity_input_name(ch, 'override_color'))
                        if ch_override_color: rgb = ch_override_color
                else:
                    ch_source = nodes.get(ch.source)


            if ch_source:
                if is_bl_newer_than(2, 81) and ch.override_type == 'VORONOI' and ch.voronoi_feature == 'N_SPHERE_RADIUS':
                    rgb = ch_source.outputs['Radius']
                else: rgb = ch_source.outputs[0]
                # Override channel will not output alpha whatsoever
                #if layer.type != 'IMAGE':
                #    if ch.override_type in {'IMAGE'}:
                #        alpha = ch_source.outputs[1]
                #    else: alpha = get_essential_node(tree, ONE_VALUE)[0]

            if ch_uv_neighbor:

                if vector: create_link(tree, vector, ch_uv_neighbor.inputs[0])

                if ch.override_type in {'VCOL', 'HEMI', 'OBJECT_INDEX'}:
                    create_link(tree, rgb, ch_uv_neighbor.inputs[0])

                # UV Neighbor multiplier
                if bump_smooth_multiplier_value and 'Multiplier' in ch_uv_neighbor.inputs:
                    create_link(tree, bump_smooth_multiplier_value, ch_uv_neighbor.inputs['Multiplier'])

                if tangent and 'Tangent' in ch_uv_neighbor.inputs:
                    create_link(tree, tangent, ch_uv_neighbor.inputs['Tangent'])
                if bitangent and 'Bitangent' in ch_uv_neighbor.inputs:
                    create_link(tree, bitangent, ch_uv_neighbor.inputs['Bitangent'])

                if layer_tangent:
                    if 'Entity Tangent' in ch_uv_neighbor.inputs:
                        create_link(tree, layer_tangent, ch_uv_neighbor.inputs['Entity Tangent'])
                        create_link(tree, layer_bitangent, ch_uv_neighbor.inputs['Entity Bitangent'])

                    if 'Mask Tangent' in ch_uv_neighbor.inputs:
                        create_link(tree, layer_tangent, ch_uv_neighbor.inputs['Mask Tangent'])
                        create_link(tree, layer_bitangent, ch_uv_neighbor.inputs['Mask Bitangent'])

            #if root_ch.type == 'NORMAL' and layer.type in {'VCOL', 'GROUP', 'HEMI', 'OBJECT_INDEX'} and uv_neighbor and ch.override_type == 'DEFAULT':
            #    create_link(tree, rgb, uv_neighbor.inputs[0])

            # Source NSEW
            if root_ch.type == 'NORMAL' and root_ch.enable_smooth_bump and ch.override_type != 'DEFAULT':
                ch_source_n = nodes.get(ch.source_n)
                ch_source_s = nodes.get(ch.source_s)
                ch_source_e = nodes.get(ch.source_e)
                ch_source_w = nodes.get(ch.source_w)

                if ch_uv_neighbor:
                    if ch_source_n: create_link(tree, ch_uv_neighbor.outputs['n'], ch_source_n.inputs[0])
                    if ch_source_s: create_link(tree, ch_uv_neighbor.outputs['s'], ch_source_s.inputs[0])
                    if ch_source_e: create_link(tree, ch_uv_neighbor.outputs['e'], ch_source_e.inputs[0])
                    if ch_source_w: create_link(tree, ch_uv_neighbor.outputs['w'], ch_source_w.inputs[0])

            if vector and ch.override_type != 'DEFAULT' and 'Vector' in ch_source.inputs:
                create_link(tree, vector, ch_source.inputs['Vector'])

            if yp.layer_preview_mode and yp.layer_preview_mode_type == 'SPECIFIC_MASK' and ch.active_edit == True:
                if alpha_preview:
                    create_link(tree, rgb, alpha_preview)

        # Override Normal
        normal = rgb_before_override
        if root_ch.type == 'NORMAL' and ch.override_1: 
            if ch.override_1_type == 'DEFAULT':
                ch_override_1_color = get_essential_node(tree, TREE_START).get(get_entity_input_name(ch, 'override_1_color'))
                if ch_override_1_color: 
                    normal = ch_override_1_color
            else:
                ch_source_1 = nodes.get(ch.source_1)
                if ch_source_1: 
                    normal = ch_source_1.outputs[0]

                    if vector and 'Vector' in ch_source_1.inputs:
                        create_link(tree, vector, ch_source_1.inputs['Vector'])

            ch_linear_1 = nodes.get(ch.linear_1)
            ch_flip_y = nodes.get(ch.flip_y) # Flip Y will only applied to normal override
            if ch_linear_1: normal = create_link(tree, normal, ch_linear_1.inputs[0])[0]
            if ch_flip_y: normal = create_link(tree, normal, ch_flip_y.inputs[0])[0]

            if yp.layer_preview_mode and yp.layer_preview_mode_type == 'SPECIFIC_MASK' and ch.active_edit_1 == True:
                if alpha_preview:
                    create_link(tree, normal, alpha_preview)

        if ch_idx != -1 and i != ch_idx: continue

        intensity = nodes.get(ch.intensity)
        layer_intensity = nodes.get(ch.layer_intensity)
        intensity_multiplier = nodes.get(ch.intensity_multiplier)
        extra_alpha = nodes.get(ch.extra_alpha)
        decal_alpha = nodes.get(ch.decal_alpha)
        blend = nodes.get(ch.blend)

        # Check if normal is overriden
        if root_ch.type == 'NORMAL' and ch.normal_map_type == 'NORMAL_MAP':
            rgb = normal

        ch_tb_fac = get_essential_node(tree, TREE_START).get(get_entity_input_name(ch, 'transition_bump_fac'))

        if intensity_multiplier and ch != trans_bump_ch:
            if trans_bump_flip:
                if tb_second_value: create_link(tree, tb_second_value, intensity_multiplier.inputs['Multiplier'])
            elif tb_value: create_link(tree, tb_value, intensity_multiplier.inputs['Multiplier'])

            if ch_tb_fac: create_link(tree, ch_tb_fac, intensity_multiplier.inputs['Factor'])

        if ch.source_group == '': # and (root_ch.type != 'NORMAL' or ch.normal_map_type != 'NORMAL_MAP'):
            ch_linear = nodes.get(ch.linear)
            if ch_linear:
                create_link(tree, rgb, ch_linear.inputs[0])
                rgb = ch_linear.outputs[0]

        mod_group = nodes.get(ch.mod_group)

        rgb_before_mod = rgb
        alpha_before_mod = alpha

        # Background layer won't use modifier outputs
        if layer.type == 'BACKGROUND':
            pass
        elif layer.type == 'GROUP' and root_ch.type == 'NORMAL':
            if root_ch.name + io_suffix['GROUP'] in source.outputs:
                normal = source.outputs.get(root_ch.name + io_suffix['GROUP'])
            if root_ch.name + io_suffix['ALPHA'] + io_suffix['GROUP'] in source.outputs:
                normal_alpha = source.outputs.get(root_ch.name + io_suffix['ALPHA'] + io_suffix['GROUP'])
        elif root_ch.type == 'NORMAL' and ch.normal_map_type == 'NORMAL_MAP':
            rgb, alpha = reconnect_all_modifier_nodes(tree, ch, rgb, alpha, use_modifier_1=True)
        else:
            rgb, alpha = reconnect_all_modifier_nodes(tree, ch, rgb, alpha, mod_group)

            if root_ch.type == 'NORMAL' and ch.normal_map_type == 'BUMP_NORMAL_MAP':
                normal, normal_alpha = reconnect_all_modifier_nodes(tree, ch, normal, alpha_before_mod, use_modifier_1=True)

        rgb_after_mod = rgb
        alpha_after_mod = alpha

        # For transition input
        transition_input = alpha
        if chain == 0 and intensity_multiplier:
            alpha = create_link(tree, alpha, intensity_multiplier.inputs[0])[0]

        # Mask multiplies
        for j, mask in enumerate(layer.masks):

            # Modifier mask need previous alpha
            if mask.type == 'MODIFIER':
                if mask.group_node != '':
                    mask_source = nodes.get(mask.group_node)
                    if mask_source: create_link(tree, alpha, mask_source.inputs[0])
                else:
                    mask_source = nodes.get(mask.source)
                    if mask_source:
                        if mask.modifier_type in {'CURVE', 'INVERT'}:
                            create_link(tree, alpha, mask_source.inputs[1])
                        else: create_link(tree, alpha, mask_source.inputs[0])

            mask_mix = nodes.get(mask.channels[i].mix)
            mmixcol0, mmixcol1, mmixout = get_mix_color_indices(mask_mix)
            if mask_mix:
                alpha = create_link(tree, alpha, mask_mix.inputs[mmixcol0])[mmixout]

            mix_limit = nodes.get(mask.channels[i].mix_limit)
            if mix_limit and group_alpha:
                alpha = create_link(tree, alpha, mix_limit.inputs[0])[0]
                create_link(tree, group_alpha, mix_limit.inputs[1])

            if j == chain-1 and intensity_multiplier:
                transition_input = alpha
                alpha = create_link(tree, alpha, intensity_multiplier.inputs[0])[0]

        # Decal alpha
        if decal_alpha and decal_process:
            alpha = create_link(tree, alpha, decal_alpha.inputs[0])[0]
            create_link(tree, decal_process.outputs[1], decal_alpha.inputs[1])[0]

        # If transition bump is not found, use last alpha as input
        if not trans_bump_ch:
            transition_input = alpha

        # Pass alpha to layer intensity
        if layer_intensity and layer_intensity_value:
            if ch_intensity: ch_intensity = create_link(tree, ch_intensity, layer_intensity.inputs[0])[0]
            create_link(tree, layer_intensity_value, layer_intensity.inputs[1])

        # Bookmark alpha before intensity because it can be useful
        alpha_before_intensity = alpha

        height_proc = nodes.get(ch.height_proc)
        normal_proc = nodes.get(ch.normal_proc)
        normal_map_proc = nodes.get(ch.normal_map_proc)
        vdisp_proc = nodes.get(ch.vdisp_proc)

        if root_ch.type == 'NORMAL':

            write_height = get_write_height(ch)

            ch_bump_distance = get_essential_node(tree, TREE_START).get(get_entity_input_name(ch, 'bump_distance'))
            ch_bump_midlevel = get_essential_node(tree, TREE_START).get(get_entity_input_name(ch, 'bump_midlevel'))
            ch_normal_strength = get_essential_node(tree, TREE_START).get(get_entity_input_name(ch, 'normal_strength'))
            max_height_calc = nodes.get(ch.max_height_calc)

            # Set intensity
            if ch_intensity:
                if height_proc: 
                    create_link(tree, ch_intensity, height_proc.inputs['Intensity'])
                if normal_proc and 'Intensity' in normal_proc.inputs:
                    create_link(tree, ch_intensity, normal_proc.inputs['Intensity'])

            # Set normal strength
            if normal_proc and ch_normal_strength and 'Strength' in normal_proc.inputs:
                create_link(tree, ch_normal_strength, normal_proc.inputs['Strength'])

            if normal_map_proc:
                create_link(tree, ch_normal_strength, normal_map_proc.inputs['Strength'])

            height_blend = nodes.get(ch.height_blend)
            hbcol0, hbcol1, hbout = get_mix_color_indices(height_blend)

            spread_alpha = nodes.get(ch.spread_alpha)
            #spread_alpha_n = nodes.get(ch.spread_alpha_n)
            #spread_alpha_s = nodes.get(ch.spread_alpha_s)
            #spread_alpha_e = nodes.get(ch.spread_alpha_e)
            #spread_alpha_w = nodes.get(ch.spread_alpha_w)

            if root_ch.enable_smooth_bump:

                prev_height_n = get_essential_node(tree, TREE_START).get(root_ch.name + io_suffix['HEIGHT_N'])
                prev_height_s = get_essential_node(tree, TREE_START).get(root_ch.name + io_suffix['HEIGHT_S'])
                prev_height_e = get_essential_node(tree, TREE_START).get(root_ch.name + io_suffix['HEIGHT_E'])
                prev_height_w = get_essential_node(tree, TREE_START).get(root_ch.name + io_suffix['HEIGHT_W'])

                prev_height_alpha_n = get_essential_node(tree, TREE_START).get(root_ch.name + io_suffix['HEIGHT_N'] + io_suffix['ALPHA'])
                prev_height_alpha_s = get_essential_node(tree, TREE_START).get(root_ch.name + io_suffix['HEIGHT_S'] + io_suffix['ALPHA'])
                prev_height_alpha_e = get_essential_node(tree, TREE_START).get(root_ch.name + io_suffix['HEIGHT_E'] + io_suffix['ALPHA'])
                prev_height_alpha_w = get_essential_node(tree, TREE_START).get(root_ch.name + io_suffix['HEIGHT_W'] + io_suffix['ALPHA'])

                next_height_n = get_essential_node(tree, TREE_END).get(root_ch.name + io_suffix['HEIGHT_N'])
                next_height_s = get_essential_node(tree, TREE_END).get(root_ch.name + io_suffix['HEIGHT_S'])
                next_height_e = get_essential_node(tree, TREE_END).get(root_ch.name + io_suffix['HEIGHT_E'])
                next_height_w = get_essential_node(tree, TREE_END).get(root_ch.name + io_suffix['HEIGHT_W'])

                next_height_alpha_n = get_essential_node(tree, TREE_END).get(root_ch.name + io_suffix['HEIGHT_N'] + io_suffix['ALPHA'])
                next_height_alpha_s = get_essential_node(tree, TREE_END).get(root_ch.name + io_suffix['HEIGHT_S'] + io_suffix['ALPHA'])
                next_height_alpha_e = get_essential_node(tree, TREE_END).get(root_ch.name + io_suffix['HEIGHT_E'] + io_suffix['ALPHA'])
                next_height_alpha_w = get_essential_node(tree, TREE_END).get(root_ch.name + io_suffix['HEIGHT_W'] + io_suffix['ALPHA'])

            prev_height = get_essential_node(tree, TREE_START).get(root_ch.name + io_suffix['HEIGHT'])
            next_height = get_essential_node(tree, TREE_END).get(root_ch.name + io_suffix['HEIGHT'])
            prev_height_alpha = get_essential_node(tree, TREE_START).get(root_ch.name + io_suffix['HEIGHT'] + io_suffix['ALPHA'])
            next_height_alpha = get_essential_node(tree, TREE_END).get(root_ch.name + io_suffix['HEIGHT'] + io_suffix['ALPHA'])

            prev_vdisp = get_essential_node(tree, TREE_START).get(root_ch.name + io_suffix['VDISP'])
            next_vdisp = get_essential_node(tree, TREE_END).get(root_ch.name + io_suffix['VDISP'])

            # Get neighbor rgb
            alpha_n = alpha_after_mod
            alpha_s = alpha_after_mod
            alpha_e = alpha_after_mod
            alpha_w = alpha_after_mod

            rgb_n = rgb
            rgb_s = rgb
            rgb_e = rgb
            rgb_w = rgb

            group_alpha_n = None
            group_alpha_s = None
            group_alpha_e = None
            group_alpha_w = None

            if source_n and source_s and source_e and source_w:
                # Use override value instead from actual layer if using default override type
                if not ch.override or ch.override_type != 'DEFAULT':
                    rgb_n = source_n.outputs[source_index]
                    rgb_s = source_s.outputs[source_index]
                    rgb_e = source_e.outputs[source_index]
                    rgb_w = source_w.outputs[source_index]

                alpha_n = source_n.outputs[source_index+1]
                alpha_s = source_s.outputs[source_index+1]
                alpha_e = source_e.outputs[source_index+1]
                alpha_w = source_w.outputs[source_index+1]

            elif layer.type in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'EDGE_DETECT', 'AO'} and uv_neighbor:
                rgb_n = uv_neighbor.outputs['n']
                rgb_s = uv_neighbor.outputs['s']
                rgb_e = uv_neighbor.outputs['e']
                rgb_w = uv_neighbor.outputs['w']

                if layer.type == 'VCOL' and uv_neighbor_1:
                    alpha_n = uv_neighbor_1.outputs['n']
                    alpha_s = uv_neighbor_1.outputs['s']
                    alpha_e = uv_neighbor_1.outputs['e']
                    alpha_w = uv_neighbor_1.outputs['w']
                else:
                    alpha_n = start_alpha
                    alpha_s = start_alpha
                    alpha_e = start_alpha
                    alpha_w = start_alpha

            elif layer.type == 'GROUP':

                if root_ch.enable_smooth_bump:
                    rgb_n = source.outputs.get(root_ch.name + io_suffix['HEIGHT_N'] + io_suffix['GROUP'])
                    rgb_s = source.outputs.get(root_ch.name + io_suffix['HEIGHT_S'] + io_suffix['GROUP'])
                    rgb_e = source.outputs.get(root_ch.name + io_suffix['HEIGHT_E'] + io_suffix['GROUP'])
                    rgb_w = source.outputs.get(root_ch.name + io_suffix['HEIGHT_W'] + io_suffix['GROUP'])

                    alpha_n = source.outputs.get(root_ch.name + io_suffix['HEIGHT_N'] + io_suffix['ALPHA'] + io_suffix['GROUP'])
                    alpha_s = source.outputs.get(root_ch.name + io_suffix['HEIGHT_S'] + io_suffix['ALPHA'] + io_suffix['GROUP'])
                    alpha_e = source.outputs.get(root_ch.name + io_suffix['HEIGHT_E'] + io_suffix['ALPHA'] + io_suffix['GROUP'])
                    alpha_w = source.outputs.get(root_ch.name + io_suffix['HEIGHT_W'] + io_suffix['ALPHA'] + io_suffix['GROUP'])

                    group_alpha_n = alpha_n
                    group_alpha_s = alpha_s
                    group_alpha_e = alpha_e
                    group_alpha_w = alpha_w

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

            if ch.override:

                if ch.override_type == 'DEFAULT':
                    rgb_n = rgb
                    rgb_s = rgb
                    rgb_e = rgb
                    rgb_w = rgb

                elif ch.override_type in {'VCOL', 'HEMI', 'OBJECT_INDEX'} and ch_uv_neighbor:
                    rgb_n = ch_uv_neighbor.outputs['n']
                    rgb_s = ch_uv_neighbor.outputs['s']
                    rgb_e = ch_uv_neighbor.outputs['e']
                    rgb_w = ch_uv_neighbor.outputs['w']

                elif ch_source_n and ch_source_s and ch_source_e and ch_source_w:
                    rgb_n = ch_source_n.outputs[0]
                    rgb_s = ch_source_s.outputs[0]
                    rgb_e = ch_source_e.outputs[0]
                    rgb_w = ch_source_w.outputs[0]

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
            if blend and ch.normal_blend_type == 'OVERLAY':
                if tangent and 'Tangent' in blend.inputs: create_link(tree, tangent, blend.inputs['Tangent'])
                if bitangent and 'Bitangent' in blend.inputs: create_link(tree, bitangent, blend.inputs['Bitangent'])

            if normal_map_proc:
                if ch.normal_map_type == 'NORMAL_MAP':
                    create_link(tree, rgb, normal_map_proc.inputs['Color'])
                elif ch.normal_map_type == 'BUMP_NORMAL_MAP':
                    create_link(tree, normal, normal_map_proc.inputs['Color'])

            if write_height:
                chain_local = len(layer.masks)
            else: chain_local = min(len(layer.masks), ch.transition_bump_chain)

            if spread_alpha:
                rgb = create_link(tree, rgb, spread_alpha.inputs['Color'])[0]
                create_link(tree, alpha_after_mod, spread_alpha.inputs['Alpha'])
                if root_ch.enable_smooth_bump:
                    rgb_n = create_link(tree, rgb_n, spread_alpha.inputs['Color n'])['Color n']
                    rgb_s = create_link(tree, rgb_s, spread_alpha.inputs['Color s'])['Color s']
                    rgb_e = create_link(tree, rgb_e, spread_alpha.inputs['Color e'])['Color e']
                    rgb_w = create_link(tree, rgb_w, spread_alpha.inputs['Color w'])['Color w']

                    create_link(tree, alpha_n, spread_alpha.inputs['Alpha n'])
                    create_link(tree, alpha_s, spread_alpha.inputs['Alpha s'])
                    create_link(tree, alpha_e, spread_alpha.inputs['Alpha e'])
                    create_link(tree, alpha_w, spread_alpha.inputs['Alpha w'])

            # Decal
            decal_alpha_n = nodes.get(ch.decal_alpha_n)
            decal_alpha_s = nodes.get(ch.decal_alpha_s)
            decal_alpha_e = nodes.get(ch.decal_alpha_e)
            decal_alpha_w = nodes.get(ch.decal_alpha_w)

            if decal_process:
                if decal_alpha_n: 
                    alpha_n = create_link(tree, alpha_n, decal_alpha_n.inputs[0])[0]
                    create_link(tree, decal_process.outputs[1], decal_alpha_n.inputs[1])
                if decal_alpha_s: 
                    alpha_s = create_link(tree, alpha_s, decal_alpha_s.inputs[0])[0]
                    create_link(tree, decal_process.outputs[1], decal_alpha_s.inputs[1])
                if decal_alpha_e: 
                    alpha_e = create_link(tree, alpha_e, decal_alpha_e.inputs[0])[0]
                    create_link(tree, decal_process.outputs[1], decal_alpha_e.inputs[1])
                if decal_alpha_w: 
                    alpha_w = create_link(tree, alpha_w, decal_alpha_w.inputs[0])[0]
                    create_link(tree, decal_process.outputs[1], decal_alpha_w.inputs[1])

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
            remains = get_essential_node(tree, ONE_VALUE)[0]

            tb_falloff = nodes.get(ch.tb_falloff)

            if tb_falloff:
                tb_emulated_curve_fac = get_essential_node(tree, TREE_START).get(get_entity_input_name(ch, 'transition_bump_falloff_emulated_curve_fac'))
                if tb_emulated_curve_fac:
                    if 'Fac' in tb_falloff.inputs:
                        create_link(tree, tb_emulated_curve_fac, tb_falloff.inputs['Fac'])

            if chain == 0 or len(layer.masks) == 0:
                if tb_falloff:
                    end_chain = pure = create_link(tree, end_chain, tb_falloff.inputs[0])[0]

                    if root_ch.enable_smooth_bump:
                        end_chain_n = alpha_n = create_link(tree, end_chain_n, tb_falloff.inputs['Value n'])['Value n']
                        end_chain_s = alpha_s = create_link(tree, end_chain_s, tb_falloff.inputs['Value s'])['Value s']
                        end_chain_e = alpha_e = create_link(tree, end_chain_e, tb_falloff.inputs['Value e'])['Value e']
                        end_chain_w = alpha_w = create_link(tree, end_chain_w, tb_falloff.inputs['Value w'])['Value w']

            for j, mask in enumerate(layer.masks):
                if not mask.enable: continue

                c = mask.channels[i]
                mask_mix = nodes.get(c.mix)
                mix_pure = nodes.get(c.mix_pure)
                mix_remains = nodes.get(c.mix_remains)
                mix_normal = nodes.get(c.mix_normal)
                mix_limit_normal = nodes.get(c.mix_limit_normal)

                mmixcol0, mmixcol1, mmixout = get_mix_color_indices(mask_mix)
                mp_mixcol0, mp_mixcol1, mp_mixout = get_mix_color_indices(mix_pure)
                mr_mixcol0, mr_mixcol1, mr_mixout = get_mix_color_indices(mix_remains)
                mn_mixcol0, mn_mixcol1, mn_mixout = get_mix_color_indices(mix_normal)

                if mask.type == 'MODIFIER' and root_ch.enable_smooth_bump:
                    mask_source_n = nodes.get(mask.source_n)
                    mask_source_s = nodes.get(mask.source_s)
                    mask_source_e = nodes.get(mask.source_e)
                    mask_source_w = nodes.get(mask.source_w)

                    if mask_source_n: create_link(tree, alpha_n, mask_source_n.inputs[0])
                    if mask_source_s: create_link(tree, alpha_s, mask_source_s.inputs[0])
                    if mask_source_e: create_link(tree, alpha_e, mask_source_e.inputs[0])
                    if mask_source_w: create_link(tree, alpha_w, mask_source_w.inputs[0])

                if tb_falloff and (j == chain-1 or (j == chain_local-1 and not trans_bump_ch)):
                    pure = tb_falloff.outputs[0]
                elif j < chain:
                    if mask_mix: pure = mask_mix.outputs[mmixout]
                else:
                    if mix_pure: pure = create_link(tree, pure, mix_pure.inputs[mp_mixcol0])[mp_mixout]

                if j >= chain:
                    if mix_remains: remains = create_link(tree, remains, mix_remains.inputs[mr_mixcol0])[mr_mixout]

                if normal_alpha:
                    if mix_normal:
                        normal_alpha = create_link(tree, normal_alpha, mix_normal.inputs[mn_mixcol0])[mn_mixout]
                    if mix_limit_normal and group_alpha:
                        normal_alpha = create_link(tree, normal_alpha, mix_limit_normal.inputs[0])[0]
                        create_link(tree, group_alpha, mix_limit_normal.inputs[1])

                if root_ch.enable_smooth_bump and mask_mix:
                    if j == chain and trans_bump_ch == ch and trans_bump_crease:
                        alpha_n = create_link(tree, get_essential_node(tree, ONE_VALUE)[0], mask_mix.inputs['Color1 n'])['Color n']
                        alpha_s = create_link(tree, get_essential_node(tree, ONE_VALUE)[0], mask_mix.inputs['Color1 s'])['Color s']
                        alpha_e = create_link(tree, get_essential_node(tree, ONE_VALUE)[0], mask_mix.inputs['Color1 e'])['Color e']
                        alpha_w = create_link(tree, get_essential_node(tree, ONE_VALUE)[0], mask_mix.inputs['Color1 w'])['Color w']
                    elif 'Color1 n' in mask_mix.inputs:
                        if alpha_n: alpha_n = create_link(tree, alpha_n, mask_mix.inputs['Color1 n'])['Color n']
                        if alpha_s: alpha_s = create_link(tree, alpha_s, mask_mix.inputs['Color1 s'])['Color s']
                        if alpha_e: alpha_e = create_link(tree, alpha_e, mask_mix.inputs['Color1 e'])['Color e']
                        if alpha_w: alpha_w = create_link(tree, alpha_w, mask_mix.inputs['Color1 w'])['Color w']

                        if group_alpha and 'Limit' in mask_mix.inputs:
                            create_link(tree, group_alpha, mask_mix.inputs['Limit'])

                        if group_alpha_n and 'Limit n' in mask_mix.inputs:
                            create_link(tree, group_alpha_n, mask_mix.inputs['Limit n'])
                            create_link(tree, group_alpha_s, mask_mix.inputs['Limit s'])
                            create_link(tree, group_alpha_e, mask_mix.inputs['Limit e'])
                            create_link(tree, group_alpha_w, mask_mix.inputs['Limit w'])

                if j == chain-1 or (j == chain_local-1 and not trans_bump_ch):
                    
                    if mask_mix:
                        end_chain_crease = mask_mix.outputs[mmixout]
                    #else: end_chain_crease = alpha
                    end_chain_crease_n = alpha_n
                    end_chain_crease_s = alpha_s
                    end_chain_crease_e = alpha_e
                    end_chain_crease_w = alpha_w

                    if tb_falloff:
                        if mask_mix: create_link(tree, mask_mix.outputs[mmixout], tb_falloff.inputs[0])[0]
                        end_chain = tb_falloff.outputs[0]
                    elif mask_mix: 
                        end_chain = mask_mix.outputs[mmixout]

                    if tb_falloff and root_ch.enable_smooth_bump: 
                        end_chain_n = alpha_n = create_link(tree, alpha_n, tb_falloff.inputs['Value n'])['Value n']
                        end_chain_s = alpha_s = create_link(tree, alpha_s, tb_falloff.inputs['Value s'])['Value s']
                        end_chain_e = alpha_e = create_link(tree, alpha_e, tb_falloff.inputs['Value e'])['Value e']
                        end_chain_w = alpha_w = create_link(tree, alpha_w, tb_falloff.inputs['Value w'])['Value w']
                    else:
                        end_chain_n = alpha_n
                        end_chain_s = alpha_s
                        end_chain_e = alpha_e
                        end_chain_w = alpha_w

            if ch_bump_distance:
                bump_distance_ignorer = nodes.get(ch.bump_distance_ignorer)
                if bump_distance_ignorer:
                    ch_bump_distance = create_link(tree, ch_bump_distance, bump_distance_ignorer.inputs[0])[0]

                if height_proc and 'Value Max Height' in height_proc.inputs:
                    create_link(tree, ch_bump_distance, height_proc.inputs['Value Max Height'])

                if height_proc and 'Midlevel' in height_proc.inputs:
                    create_link(tree, ch_bump_midlevel, height_proc.inputs['Midlevel'])

            bdistance = None
            if layer.type == 'GROUP':
                bdistance = get_essential_node(tree, TREE_START).get(root_ch.name + io_suffix['MAX_HEIGHT'] + io_suffix['GROUP'])
            elif ch_bump_distance:
                bdistance = ch_bump_distance

            prev_max_height = get_essential_node(tree, TREE_START).get(root_ch.name + io_suffix['MAX_HEIGHT'])
            next_max_height = get_essential_node(tree, TREE_END).get(root_ch.name + io_suffix['MAX_HEIGHT'])

            if max_height_calc:

                if prev_max_height: create_link(tree, prev_max_height, max_height_calc.inputs['Prev Bump Distance'])
                if next_max_height: create_link(tree, max_height_calc.outputs[0], next_max_height)

                if bdistance:
                    create_link(tree, bdistance, max_height_calc.inputs['Bump Distance'])
                else: break_input_link(tree, max_height_calc.inputs['Bump Distance'])

                if ch_intensity:
                    create_link(tree, ch_intensity, max_height_calc.inputs['Intensity'])

                if ch_bump_midlevel and 'Midlevel' in max_height_calc.inputs:
                    create_link(tree, ch_bump_midlevel, max_height_calc.inputs['Midlevel'])

                if normal_proc and 'Max Height' in normal_proc.inputs:
                    create_link(tree, max_height_calc.outputs[0], normal_proc.inputs['Max Height'])

            elif prev_max_height and next_max_height:
                create_link(tree, prev_max_height, next_max_height)

            if height_proc:
                if 'Value' in height_proc.inputs:
                    #create_link(tree, rgb_after_mod, height_proc.inputs['Value'])
                    if layer.type == 'BACKGROUND':
                        create_link(tree, get_essential_node(tree, ONE_VALUE)[0], height_proc.inputs['Value'])
                    else: create_link(tree, rgb, height_proc.inputs['Value'])

                if 'Value n' in  height_proc.inputs: 
                    if layer.type == 'BACKGROUND':
                        create_link(tree, get_essential_node(tree, ONE_VALUE)[0], height_proc.inputs['Value n'])
                        create_link(tree, get_essential_node(tree, ONE_VALUE)[0], height_proc.inputs['Value s'])
                        create_link(tree, get_essential_node(tree, ONE_VALUE)[0], height_proc.inputs['Value e'])
                        create_link(tree, get_essential_node(tree, ONE_VALUE)[0], height_proc.inputs['Value w'])
                    else:
                        create_link(tree, rgb_n, height_proc.inputs['Value n'])
                        create_link(tree, rgb_s, height_proc.inputs['Value s'])
                        create_link(tree, rgb_e, height_proc.inputs['Value e'])
                        create_link(tree, rgb_w, height_proc.inputs['Value w'])

            if layer.type == 'GROUP':

                if normal_proc: create_link(tree, normal, normal_proc.inputs['Normal'])

                height_group = source.outputs.get(root_ch.name + io_suffix['HEIGHT'] + io_suffix['GROUP'])
                if height_proc and height_group: create_link(tree, height_group, height_proc.inputs['Height'])

                if height_proc and root_ch.enable_smooth_bump:
                    if rgb_n and 'Height n' in height_proc.inputs: create_link(tree, rgb_n, height_proc.inputs['Height n'])
                    if rgb_s and 'Height s' in height_proc.inputs: create_link(tree, rgb_s, height_proc.inputs['Height s'])
                    if rgb_e and 'Height e' in height_proc.inputs: create_link(tree, rgb_e, height_proc.inputs['Height e'])
                    if rgb_w and 'Height w' in height_proc.inputs: create_link(tree, rgb_w, height_proc.inputs['Height w'])
            elif normal_map_proc and normal_proc and 'Normal' in normal_proc.inputs:
                create_link(tree, normal_map_proc.outputs[0], normal_proc.inputs['Normal'])
            else:
                prev_normal = get_essential_node(tree, TREE_START).get(root_ch.name)
                if prev_normal and normal_proc and 'Normal' in normal_proc.inputs: 
                    create_link(tree, prev_normal, normal_proc.inputs['Normal'])

            height_alpha = alpha
            #alpha_ns = None
            #alpha_ew = None

            if height_proc:

                # Transition Bump
                if ch.enable_transition_bump and ch.enable:

                    tb_distance = get_essential_node(tree, TREE_START).get(get_entity_input_name(ch, 'transition_bump_distance'))
                    if tb_distance:

                        tb_distance_flipper = nodes.get(ch.tb_distance_flipper)
                        if tb_distance_flipper:
                            tb_distance = create_link(tree, tb_distance, tb_distance_flipper.inputs[0])[0]
                    
                        if ch.normal_map_type in {'BUMP_MAP', 'BUMP_NORMAL_MAP'}:
                            if 'Transition Max Height' in height_proc.inputs:
                                create_link(tree, tb_distance, height_proc.inputs['Transition Max Height'])
                        elif ch.normal_map_type == 'NORMAL_MAP':
                            create_link(tree, tb_distance, height_proc.inputs['Bump Height'])

                        if 'Delta' in height_proc.inputs and ch_bump_distance:
                            tb_delta_calc = nodes.get(ch.tb_delta_calc)
                            if tb_delta_calc:
                                create_link(tree, tb_distance, tb_delta_calc.inputs[0])
                                create_link(tree, ch_bump_distance, tb_delta_calc.inputs[1])
                                create_link(tree, tb_delta_calc.outputs[0], height_proc.inputs['Delta'])

                        if max_height_calc and 'Transition Bump Distance' in max_height_calc.inputs:
                            create_link(tree, tb_distance, max_height_calc.inputs['Transition Bump Distance'])

                    if trans_bump_crease:

                        tb_crease_factor = get_essential_node(tree, TREE_START).get(get_entity_input_name(ch, 'transition_bump_crease_factor'))
                        if tb_crease_factor:
                            if 'Crease Factor' in height_proc.inputs:
                                create_link(tree, tb_crease_factor, height_proc.inputs['Crease Factor'])

                            if max_height_calc and 'Crease Factor' in max_height_calc.inputs:
                                create_link(tree, tb_crease_factor, max_height_calc.inputs['Crease Factor'])

                        tb_crease_power = get_essential_node(tree, TREE_START).get(get_entity_input_name(ch, 'transition_bump_crease_power'))
                        if tb_crease_power:
                            if 'Crease Power' in height_proc.inputs:
                                create_link(tree, tb_crease_power, height_proc.inputs['Crease Power'])

                        create_link(tree, remains, height_proc.inputs['Remaining Alpha'])
                        create_link(tree, end_chain, height_proc.inputs['Transition'])

                        if 'Transition n' in height_proc.inputs: 
                            create_link(tree, end_chain_n, height_proc.inputs['Transition n'])
                            create_link(tree, end_chain_s, height_proc.inputs['Transition s'])
                            create_link(tree, end_chain_e, height_proc.inputs['Transition e'])
                            create_link(tree, end_chain_w, height_proc.inputs['Transition w'])

                        if not write_height or len(layer.masks) == chain:
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

                        #if normal_proc and 'Edge 1 Alpha' in normal_proc.inputs:
                        #    if not write_height and not root_ch.enable_smooth_bump:
                        #        create_link(tree, height_proc.outputs['Filtered Alpha'], normal_proc.inputs['Edge 1 Alpha'])
                        #    else: create_link(tree, intensity_multiplier.outputs[0], normal_proc.inputs['Edge 1 Alpha'])

                        if 'Transition Crease' in height_proc.inputs:
                            create_link(tree, end_chain_crease, height_proc.inputs['Transition Crease'])

                        if 'Transition Crease n' in height_proc.inputs:
                            create_link(tree, end_chain_crease_n, height_proc.inputs['Transition Crease n'])
                            create_link(tree, end_chain_crease_s, height_proc.inputs['Transition Crease s'])
                            create_link(tree, end_chain_crease_e, height_proc.inputs['Transition Crease e'])
                            create_link(tree, end_chain_crease_w, height_proc.inputs['Transition Crease w'])

                    else:

                        if not write_height and not root_ch.enable_smooth_bump:

                            create_link(tree, end_chain, height_proc.inputs['Transition'])

                            if 'Edge 1 Alpha' in height_proc.inputs:
                                create_link(tree, intensity_multiplier.outputs[0], height_proc.inputs['Edge 1 Alpha'])

                            #if normal_proc and 'Edge 1 Alpha' in normal_proc.inputs:
                            #    create_link(tree, intensity_multiplier.outputs[0], normal_proc.inputs['Edge 1 Alpha'])

                        else:

                            create_link(tree, pure, height_proc.inputs['Transition'])
                            if 'Transition n' in height_proc.inputs: 
                                create_link(tree, alpha_n, height_proc.inputs['Transition n'])
                                create_link(tree, alpha_s, height_proc.inputs['Transition s'])
                                create_link(tree, alpha_e, height_proc.inputs['Transition e'])
                                create_link(tree, alpha_w, height_proc.inputs['Transition w'])

                            if 'Edge 1 Alpha' in height_proc.inputs:
                                create_link(tree, alpha_before_intensity, height_proc.inputs['Edge 1 Alpha'])

                            #if normal_proc and 'Edge 1 Alpha' in normal_proc.inputs:
                            #    create_link(tree, alpha_before_intensity, normal_proc.inputs['Edge 1 Alpha'])

                    tb_inverse = nodes.get(ch.tb_inverse)
                    tb_intensity_multiplier = nodes.get(ch.tb_intensity_multiplier)

                    if tb_intensity_multiplier:
                        #if normal_proc and 'Edge 2 Alpha' in normal_proc.inputs:
                        #    create_link(tree, tb_intensity_multiplier.outputs[0], normal_proc.inputs['Edge 2 Alpha'])

                        if height_proc and 'Edge 2 Alpha' in height_proc.inputs:
                            create_link(tree, tb_intensity_multiplier.outputs[0], height_proc.inputs['Edge 2 Alpha'])

                        if tb_inverse:
                            create_link(tree, transition_input, tb_inverse.inputs[1])
                            create_link(tree, tb_inverse.outputs[0], tb_intensity_multiplier.inputs[0])

                        if tb_second_value:
                            create_link(tree, tb_second_value, tb_intensity_multiplier.inputs[1])

                    if tb_value:
                        create_link(tree, tb_value, intensity_multiplier.inputs[1])

                else:

                    if 'Alpha' in height_proc.inputs:
                        if not write_height and not root_ch.enable_smooth_bump:
                            create_link(tree, end_chain, height_proc.inputs['Alpha'])
                        else: create_link(tree, alpha_before_intensity, height_proc.inputs['Alpha'])

                    if ch.normal_map_type == 'NORMAL_MAP':
                        if not write_height and not root_ch.enable_smooth_bump:
                            create_link(tree, end_chain, height_proc.inputs['Transition'])
                        else: create_link(tree, alpha_before_intensity, height_proc.inputs['Transition'])

                    if 'Transition n' in height_proc.inputs: 
                        create_link(tree, alpha_n, height_proc.inputs['Transition n'])
                        create_link(tree, alpha_s, height_proc.inputs['Transition s'])
                        create_link(tree, alpha_e, height_proc.inputs['Transition e'])
                        create_link(tree, alpha_w, height_proc.inputs['Transition w'])

                # Height Blend

                if 'Alpha' in height_proc.inputs:
                    alpha = create_link(tree, alpha_before_intensity, height_proc.inputs['Alpha'])['Alpha']
                    if 'Alpha n' in height_proc.inputs:
                        if alpha_n and 'Alpha n' in height_proc.inputs: create_link(tree, alpha_n, height_proc.inputs['Alpha n'])
                        if alpha_s and 'Alpha s' in height_proc.inputs: create_link(tree, alpha_s, height_proc.inputs['Alpha s'])
                        if alpha_e and 'Alpha e' in height_proc.inputs: create_link(tree, alpha_e, height_proc.inputs['Alpha e'])
                        if alpha_w and 'Alpha w' in height_proc.inputs: create_link(tree, alpha_w, height_proc.inputs['Alpha w'])
                else:
                    if trans_bump_crease:
                        if not write_height and not root_ch.enable_smooth_bump:
                            alpha = height_proc.outputs['Filtered Alpha']
                        else: alpha = height_proc.outputs['Combined Alpha']

                    elif 'Normal Alpha' in height_proc.outputs and (write_height or root_ch.enable_smooth_bump):
                        alpha = height_proc.outputs['Normal Alpha']

                    alpha_n = alpha_s = alpha_e = alpha_w = alpha

                # Height Alpha
                if 'Filtered Alpha' in height_proc.outputs and (not write_height and not root_ch.enable_smooth_bump):
                    height_alpha = alpha = height_proc.outputs['Filtered Alpha']
                elif 'Combined Alpha' in height_proc.outputs:
                    height_alpha = alpha = height_proc.outputs['Combined Alpha']
                elif 'Normal Alpha' in height_proc.outputs:
                    height_alpha = height_proc.outputs['Normal Alpha']
                elif 'Alpha' in height_proc.outputs:
                    height_alpha = height_proc.outputs['Alpha']

                if 'Alpha N' in height_proc.outputs: alpha_n = height_proc.outputs['Alpha N']
                if 'Alpha S' in height_proc.outputs: alpha_s = height_proc.outputs['Alpha S']
                if 'Alpha E' in height_proc.outputs: alpha_e = height_proc.outputs['Alpha E']
                if 'Alpha W' in height_proc.outputs: alpha_w = height_proc.outputs['Alpha W']

            if height_blend:
                if not root_ch.enable_smooth_bump:

                    if ch.normal_blend_type in {'MIX', 'OVERLAY'}:
                        if has_parent:
                            # Overlay without write height will disconnect prev height
                            if not write_height and ch.normal_blend_type == 'OVERLAY':
                                break_input_link(tree, height_blend.inputs[0])
                            elif prev_height: create_link(tree, prev_height, height_blend.inputs[0])

                            #create_link(tree, prev_alpha, height_blend.inputs[1])
                            if prev_height_alpha: create_link(tree, prev_height_alpha, height_blend.inputs[1])
                            if height_proc: create_link(tree, height_proc.outputs['Height'], height_blend.inputs[2])
                            height_alpha = create_link(tree, height_alpha, height_blend.inputs[3])[1]
                        else:
                            # Overlay without write height will disconnect prev height
                            if not write_height and ch.normal_blend_type == 'OVERLAY':
                                break_input_link(tree, height_blend.inputs[hbcol0])
                            elif prev_height: create_link(tree, prev_height, height_blend.inputs[hbcol0])

                            create_link(tree, height_alpha, height_blend.inputs[0])
                            if height_proc: create_link(tree, height_proc.outputs['Height'], height_blend.inputs[hbcol1])
                    else:
                        # Overlay without write height will disconnect prev height
                        if not write_height and ch.normal_blend_type == 'OVERLAY':
                            break_input_link(tree, height_blend.inputs['Prev Height'])
                        elif prev_height: create_link(tree, prev_height, height_blend.inputs['Prev Height'])

                        create_link(tree, height_alpha, height_blend.inputs['Alpha'])
                        if height_proc: create_link(tree, height_proc.outputs['Height'], height_blend.inputs['Height'])

                        # For straight over height compare
                        if 'Prev Alpha' in height_blend.inputs and prev_height_alpha:
                            #create_link(tree, prev_alpha, height_blend.inputs['Prev Alpha'])
                            create_link(tree, prev_height_alpha, height_blend.inputs['Prev Alpha'])
                        if 'Alpha' in height_blend.outputs:
                            height_alpha = height_blend.outputs['Alpha']

                    if normal_proc and 'Height' in normal_proc.inputs:
                        create_link(tree, height_blend.outputs[hbout], normal_proc.inputs['Height'])

                else:

                    # Overlay without write height will disconnect prev height
                    if not write_height and ch.normal_blend_type == 'OVERLAY':
                        break_input_link(tree, height_blend.inputs['Prev Height'])
                        break_input_link(tree, height_blend.inputs['Prev Height N'])
                        break_input_link(tree, height_blend.inputs['Prev Height S'])
                        break_input_link(tree, height_blend.inputs['Prev Height E'])
                        break_input_link(tree, height_blend.inputs['Prev Height W'])
                    else:
                        if prev_height: create_link(tree, prev_height, height_blend.inputs['Prev Height'])
                        if prev_height_n: create_link(tree, prev_height_n, height_blend.inputs['Prev Height N'])
                        if prev_height_s: create_link(tree, prev_height_s, height_blend.inputs['Prev Height S'])
                        if prev_height_e: create_link(tree, prev_height_e, height_blend.inputs['Prev Height E'])
                        if prev_height_w: create_link(tree, prev_height_w, height_blend.inputs['Prev Height W'])

                    if height_proc: 
                        if 'Height' in height_proc.outputs and 'Height' in height_blend.inputs:
                            create_link(tree, height_proc.outputs['Height'], height_blend.inputs['Height'])

                        if 'Height N' in height_proc.outputs and 'Height N' in height_blend.inputs:
                            create_link(tree, height_proc.outputs['Height N'], height_blend.inputs['Height N'])

                        if 'Height S' in height_proc.outputs and 'Height S' in height_blend.inputs:
                            create_link(tree, height_proc.outputs['Height S'], height_blend.inputs['Height S'])

                        if 'Height E' in height_proc.outputs and 'Height E' in height_blend.inputs:
                            create_link(tree, height_proc.outputs['Height E'], height_blend.inputs['Height E'])

                        if 'Height W' in height_proc.outputs and 'Height W' in height_blend.inputs:
                            create_link(tree, height_proc.outputs['Height W'], height_blend.inputs['Height W'])

                    create_link(tree, height_alpha, height_blend.inputs['Alpha'])

                    if has_parent or is_normal_height_input_connected(root_ch):
                        if prev_height_alpha: create_link(tree, prev_height_alpha, height_blend.inputs['Prev Height Alpha'])
                        if prev_height_alpha_n: create_link(tree, prev_height_alpha_n, height_blend.inputs['Prev Height Alpha N'])
                        if prev_height_alpha_s: create_link(tree, prev_height_alpha_s, height_blend.inputs['Prev Height Alpha S'])
                        if prev_height_alpha_e: create_link(tree, prev_height_alpha_e, height_blend.inputs['Prev Height Alpha E'])
                        if prev_height_alpha_w: create_link(tree, prev_height_alpha_w, height_blend.inputs['Prev Height Alpha W'])

                    #for d in neighbor_directions:
                    #    create_link(tree, alphas[d], height_blend.inputs['Alpha ' + d])

                    #if alpha_ns: create_link(tree, alpha_ns, height_blend.inputs['Alpha NS'])
                    #if alpha_ew: create_link(tree, alpha_ew, height_blend.inputs['Alpha EW'])

                    if alpha_n and 'Alpha N' in height_blend.inputs: create_link(tree, alpha_n, height_blend.inputs['Alpha N'])
                    if alpha_s and 'Alpha S' in height_blend.inputs: create_link(tree, alpha_s, height_blend.inputs['Alpha S'])
                    if alpha_e and 'Alpha E' in height_blend.inputs: create_link(tree, alpha_e, height_blend.inputs['Alpha E'])
                    if alpha_w and 'Alpha W' in height_blend.inputs: create_link(tree, alpha_w, height_blend.inputs['Alpha W'])

                    if normal_proc:

                        if 'Height N' in normal_proc.inputs and 'Height N' in height_blend.outputs:
                            create_link(tree, height_blend.outputs['Height N'], normal_proc.inputs['Height N'])

                        if 'Height S' in normal_proc.inputs and 'Height S' in height_blend.outputs:
                            create_link(tree, height_blend.outputs['Height S'], normal_proc.inputs['Height S'])

                        if 'Height E' in normal_proc.inputs and 'Height E' in height_blend.outputs:
                            create_link(tree, height_blend.outputs['Height E'], normal_proc.inputs['Height E'])

                        if 'Height W' in normal_proc.inputs and 'Height W' in height_blend.outputs:
                            create_link(tree, height_blend.outputs['Height W'], normal_proc.inputs['Height W'])

                if 'Normal Alpha' in height_blend.outputs:
                    alpha = height_blend.outputs['Normal Alpha']

            if normal_proc:
                if 'Alpha' in normal_proc.inputs:
                    create_link(tree, alpha, normal_proc.inputs['Alpha'])
                if 'Normal Alpha' in normal_proc.inputs and normal_alpha:
                    create_link(tree, normal_alpha, normal_proc.inputs['Normal Alpha'])

            if layer.type == 'GROUP':
                if normal_proc:
                    if write_height:
                        alpha = normal_proc.outputs['Normal Alpha']
                    else: alpha = normal_proc.outputs['Combined Alpha']

            if normal_proc and tangent and bitangent and 'Tangent' in normal_proc.inputs:
                create_link(tree, tangent, normal_proc.inputs['Tangent'])
                create_link(tree, bitangent, normal_proc.inputs['Bitangent'])

            # Normal map
            if normal_map_proc and ch.normal_map_type in {'NORMAL_MAP', 'BUMP_NORMAL_MAP'}:
                rgb = normal_map_proc.outputs[0]

            # Bump turned normal map when 'Write Height' is disabled
            if normal_proc and ch.normal_map_type in {'BUMP_MAP', 'BUMP_NORMAL_MAP'} and not ch.write_height:
                rgb = normal_proc.outputs[0]

            # Default normal
            if not normal_map_proc and not normal_proc and ch.normal_map_type != 'VECTOR_DISPLACEMENT_MAP':
                rgb = get_essential_node(tree, GEOMETRY)['Normal']

            vdisp_flip_yz = tree.nodes.get(ch.vdisp_flip_yz)
            if ch.normal_map_type == 'VECTOR_DISPLACEMENT_MAP' and vdisp_flip_yz:
                rgb = create_link(tree, rgb, vdisp_flip_yz.inputs[0])[0]

            if vdisp_proc:
                inp0, inp1, outp0 = get_mix_color_indices(vdisp_proc)
                ch_vdisp_strength = get_essential_node(tree, TREE_START).get(get_entity_input_name(ch, 'vdisp_strength'))
                
                rgb = create_link(tree, rgb, vdisp_proc.inputs[inp0])[outp0]
                create_link(tree, ch_vdisp_strength, vdisp_proc.inputs[inp1])

            if not root_ch.enable_smooth_bump and not write_height:
                normal_flip = nodes.get(ch.normal_flip)
                if normal_flip:

                    if 'Tangent' in normal_flip.inputs:
                        create_link(tree, tangent, normal_flip.inputs['Tangent'])
                        create_link(tree, bitangent, normal_flip.inputs['Bitangent'])

                    rgb = create_link(tree, rgb, normal_flip.inputs[0])[0]

            if write_height and height_blend:
                if root_ch.enable_smooth_bump:
                    #if next_height_ons: create_link(tree, height_blend.outputs['Height ONS'], next_height_ons)
                    #if next_height_ew: create_link(tree, height_blend.outputs['Height EW'], next_height_ew)

                    if next_height: create_link(tree, height_blend.outputs['Height'], next_height)
                    if next_height_n: create_link(tree, height_blend.outputs['Height N'], next_height_n)
                    if next_height_s: create_link(tree, height_blend.outputs['Height S'], next_height_s)
                    if next_height_e: create_link(tree, height_blend.outputs['Height E'], next_height_e)
                    if next_height_w: create_link(tree, height_blend.outputs['Height W'], next_height_w)

                elif next_height:
                    create_link(tree, height_blend.outputs[hbout], next_height)
            else:
                if root_ch.enable_smooth_bump:
                    #if prev_height_ons and next_height_ons: create_link(tree, prev_height_ons, next_height_ons)
                    #if prev_height_ew and next_height_ew: create_link(tree, prev_height_ew, next_height_ew)

                    if prev_height_n and next_height_n: create_link(tree, prev_height_n, next_height_n)
                    if prev_height_s and next_height_s: create_link(tree, prev_height_s, next_height_s)
                    if prev_height_e and next_height_e: create_link(tree, prev_height_e, next_height_e)
                    if prev_height_w and next_height_w: create_link(tree, prev_height_w, next_height_w)

                if prev_height and next_height: create_link(tree, prev_height, next_height)

            if has_parent or is_normal_height_input_connected(root_ch):

                if root_ch.enable_smooth_bump:

                    if height_blend and write_height:
                        if next_height_alpha: create_link(tree, height_blend.outputs['Height Alpha'], next_height_alpha)
                        if next_height_alpha_n: create_link(tree, height_blend.outputs['Height Alpha N'], next_height_alpha_n)
                        if next_height_alpha_s: create_link(tree, height_blend.outputs['Height Alpha S'], next_height_alpha_s)
                        if next_height_alpha_e: create_link(tree, height_blend.outputs['Height Alpha E'], next_height_alpha_e)
                        if next_height_alpha_w: create_link(tree, height_blend.outputs['Height Alpha W'], next_height_alpha_w)

                    else:
                        if prev_height_alpha and next_height_alpha: create_link(tree, prev_height_alpha, next_height_alpha)
                        if prev_height_alpha_n and next_height_alpha_n: create_link(tree, prev_height_alpha_n, next_height_alpha_n)
                        if prev_height_alpha_s and next_height_alpha_s: create_link(tree, prev_height_alpha_s, next_height_alpha_s)
                        if prev_height_alpha_e and next_height_alpha_e: create_link(tree, prev_height_alpha_e, next_height_alpha_e)
                        if prev_height_alpha_w and next_height_alpha_w: create_link(tree, prev_height_alpha_w, next_height_alpha_w)
                else:
                    # Do not connect from height_alpha if height_blend is not found
                    if next_height_alpha:
                        if height_blend and write_height:
                            if height_alpha: create_link(tree, height_alpha, next_height_alpha)
                        else:
                            if prev_height_alpha: create_link(tree, prev_height_alpha, next_height_alpha)

        # Pass alpha to intensity
        if intensity:

            if layer.type == 'GROUP' and root_ch.type == 'NORMAL' and not normal_proc and normal_alpha:
                normal_alpha = create_link(tree, normal_alpha, intensity.inputs[0])[0]
            else: alpha = create_link(tree, alpha, intensity.inputs[0])[0]

            if ch_intensity:
                create_link(tree, ch_intensity, intensity.inputs[1])

        # Transition AO
        tao = nodes.get(ch.tao)
        if tao and root_ch.type in {'RGB', 'VALUE'} and trans_bump_ch and ch.enable_transition_ao: # and layer.type != 'BACKGROUND':

            if ch_intensity:
                create_link(tree, ch_intensity, tao.inputs['Intensity Channel'])

            if layer_intensity_value and 'Intensity Layer' in tao.inputs:
                create_link(tree, layer_intensity_value, tao.inputs['Intensity Layer'])

            tao_intensity = get_essential_node(tree, TREE_START).get(get_entity_input_name(ch, 'transition_ao_intensity'))
            if tao_intensity:
                create_link(tree, tao_intensity, tao.inputs['Intensity'])

            tao_power = get_essential_node(tree, TREE_START).get(get_entity_input_name(ch, 'transition_ao_power'))
            if tao_power:
                create_link(tree, tao_power, tao.inputs['Power'])

            tao_color = get_essential_node(tree, TREE_START).get(get_entity_input_name(ch, 'transition_ao_color'))
            if tao_color:
                create_link(tree, tao_color, tao.inputs['AO Color'])

            tao_inside_intensity = get_essential_node(tree, TREE_START).get(get_entity_input_name(ch, 'transition_ao_inside_intensity'))
            if tao_inside_intensity:
                create_link(tree, tao_inside_intensity, tao.inputs['Inside Intensity'])

            if trans_bump_flip:
                create_link(tree, rgb, tao.inputs[0])
                rgb = tao.outputs[0]

                # Get bump intensity multiplier of transition bump
                #if trans_bump_ch.transition_bump_flip or layer.type == 'BACKGROUND':
                #    trans_im = nodes.get(trans_bump_ch.intensity_multiplier)
                #else: 
                trans_im = nodes.get(trans_bump_ch.tb_intensity_multiplier)

                if trans_im: create_link(tree, trans_im.outputs[0], tao.inputs['Multiplied Alpha'])

                if 'Bg Alpha' in tao.inputs and bg_alpha:
                    create_link(tree, bg_alpha, tao.inputs['Bg Alpha'])
                    bg_alpha = tao.outputs['Bg Alpha']

            else: 
                if prev_rgb: create_link(tree, prev_rgb, tao.inputs[0])

                # Get intensity multiplier of transition bump
                trans_im = nodes.get(trans_bump_ch.intensity_multiplier)
                if trans_im: create_link(tree, trans_im.outputs[0], tao.inputs['Multiplied Alpha'])

                # Dealing with chain
                remaining_alpha = get_essential_node(tree, ONE_VALUE)[0]
                for j, mask in enumerate(layer.masks):
                    if j >= chain:
                        mix_remains = nodes.get(mask.channels[i].mix_remains)
                        mr_mixcol0, mr_mixcol1, mr_mixout = get_mix_color_indices(mix_remains)
                        if mix_remains:
                            remaining_alpha = create_link(tree, remaining_alpha, mix_remains.inputs[mr_mixcol0])[mr_mixout]

                prev_rgb = tao.outputs[0]
                if 'Remaining Alpha' in tao.inputs:
                    create_link(tree, remaining_alpha, tao.inputs['Remaining Alpha'])

                if 'Input Alpha' in tao.inputs:
                    if prev_alpha: create_link(tree, prev_alpha, tao.inputs['Input Alpha'])
                    prev_alpha = tao.outputs['Input Alpha']

                # Extra alpha
                if 'Extra Alpha' in tao.inputs:
                    if height_ch and height_ch.normal_blend_type == 'COMPARE' and compare_alpha:
                        create_link(tree, compare_alpha, tao.inputs['Extra Alpha'])
                    else:
                        break_input_link(tree, tao.inputs['Extra Alpha'])

            create_link(tree, transition_input, tao.inputs['Transition'])

        # Transition Ramp
        tr_ramp = nodes.get(ch.tr_ramp)
        if tr_ramp and root_ch.type in {'RGB', 'VALUE'} and ch.enable_transition_ramp:

            tr_ramp_blend = nodes.get(ch.tr_ramp_blend)
            tr_intensity_value = get_essential_node(tree, TREE_START).get(get_entity_input_name(ch, 'transition_ramp_intensity_value'))
            tb_second_fac = get_essential_node(tree, TREE_START).get(get_entity_input_name(ch, 'transition_bump_second_fac'))

            create_link(tree, transition_input, tr_ramp.inputs['Transition'])

            if tb_second_fac:
                create_link(tree, tb_second_fac, tr_ramp.inputs['Factor'])

            if tr_intensity_value:
                if 'Intensity' in tr_ramp.inputs:
                    create_link(tree, tr_intensity_value, tr_ramp.inputs['Intensity'])

            if trans_bump_flip:

                # Connect intensity
                if ch_intensity:
                    create_link(tree, ch_intensity, tr_ramp_blend.inputs['Intensity Channel'])

                if layer_intensity_value and 'Intensity Layer' in tr_ramp_blend.inputs:
                    create_link(tree, layer_intensity_value, tr_ramp_blend.inputs['Intensity Layer'])

                if tr_intensity_value:
                    if 'Intensity' in tr_ramp_blend.inputs:
                        create_link(tree, tr_intensity_value, tr_ramp_blend.inputs['Intensity'])

                if tb_value:
                    create_link(tree, tb_value, tr_ramp.inputs['Multiplier'])

                if prev_rgb: create_link(tree, prev_rgb, tr_ramp_blend.inputs['Input RGB'])
                create_link(tree, intensity_multiplier.outputs[0], tr_ramp_blend.inputs['Multiplied Alpha'])

                create_link(tree, tr_ramp.outputs[0], tr_ramp_blend.inputs['Ramp RGB'])

                trans_ramp_input = tr_ramp.outputs['Ramp Alpha']

                for j, mask in enumerate(layer.masks):
                    if j >= chain:
                        mix_remains = nodes.get(mask.channels[i].mix_remains)
                        mr_mixcol0, mr_mixcol1, mr_mixout = get_mix_color_indices(mix_remains)
                        if mix_remains:
                            trans_ramp_input = create_link(tree, trans_ramp_input, mix_remains.inputs[mr_mixcol0])[mr_mixout]

                create_link(tree, trans_ramp_input, tr_ramp_blend.inputs['Ramp Alpha'])
                prev_rgb = tr_ramp_blend.outputs[0]

                if 'Input Alpha' in tr_ramp_blend.inputs:
                    if prev_alpha: create_link(tree, prev_alpha, tr_ramp_blend.inputs['Input Alpha'])
                    prev_alpha = tr_ramp_blend.outputs['Input Alpha']

                #break_input_link(tree, tr_ramp_blend.inputs['Intensity'])

            elif not trans_bump_flip:
                create_link(tree, rgb, tr_ramp.inputs['RGB'])
                rgb = tr_ramp.outputs[0]

                if tb_second_value:
                    create_link(tree, tb_second_value, tr_ramp.inputs['Multiplier'])

                if 'Bg Alpha' in tr_ramp.inputs and bg_alpha:
                    create_link(tree, bg_alpha, tr_ramp.inputs['Bg Alpha'])
                    bg_alpha = tr_ramp.outputs[1] #'Bg Alpha']
                    #create_link(tree, alpha_before_intensity, tr_ramp.inputs['Remaining Alpha'])
                    #create_link(tree, alpha, tr_ramp.inputs['Channel Intensity'])
                    if ch.transition_ramp_intensity_unlink or layer.parent_idx != -1:
                        create_link(tree, alpha, tr_ramp.inputs['Alpha'])

                        if ch.transition_ramp_intensity_unlink:
                            create_link(tree, alpha_before_intensity, tr_ramp.inputs['Alpha before Intensity'])

                        if prev_rgb: create_link(tree, prev_rgb, tr_ramp.inputs['Input RGB'])
                        if prev_alpha: create_link(tree, prev_alpha, tr_ramp.inputs['Input Alpha'])

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

        # End node
        next_rgb = get_essential_node(tree, TREE_END).get(root_ch.name)
        if alpha_ch and ch == color_ch:
            alpha_idx = get_layer_channel_index(layer, alpha_ch)
            root_alpha_ch = yp.channels[alpha_idx]
            next_alpha = get_essential_node(tree, TREE_END).get(root_alpha_ch.name)
        else: next_alpha = get_essential_node(tree, TREE_END).get(root_ch.name + io_suffix['ALPHA'])

        # Background layer only know mix
        if layer.type == 'BACKGROUND':
            blend_type = 'MIX'
        else: 
            if root_ch.type == 'NORMAL':
                blend_type = ch.normal_blend_type
            else: blend_type = ch.blend_type

        # Get output of alpha channel before blend node
        if ch == alpha_ch:
            alpha_ch_rgb = rgb

        if blend:
            bcol0, bcol1, bout = get_mix_color_indices(blend)

            # Pass rgb to blend
            if layer.type == 'GROUP' and root_ch.type == 'NORMAL' and not normal_proc:
                create_link(tree, normal, blend.inputs[bcol1])
            else:
                create_link(tree, rgb, blend.inputs[bcol1])

            if (
                    #(blend_type == 'MIX' and (has_parent or (root_ch.type == 'RGB' and root_ch.enable_alpha)))
                    (blend_type in {'MIX', 'COMPARE'} and (has_parent or is_channel_alpha_enabled(root_ch)))
                    or (blend_type == 'OVERLAY' and has_parent and root_ch.type == 'NORMAL')
                ):

                if prev_rgb: create_link(tree, prev_rgb, blend.inputs[0])
                if prev_alpha: create_link(tree, prev_alpha, blend.inputs[1])

                create_link(tree, alpha, blend.inputs[3])

                if bg_alpha and len(blend.inputs) > 4:
                    create_link(tree, bg_alpha, blend.inputs[4])

            else:
                if layer.type == 'GROUP' and root_ch.type == 'NORMAL' and not normal_proc and normal_alpha:
                    create_link(tree, normal_alpha, blend.inputs[0])
                else: create_link(tree, alpha, blend.inputs[0])

                if root_ch.type == 'NORMAL' and ch.normal_map_type == 'VECTOR_DISPLACEMENT_MAP':
                    if prev_vdisp: create_link(tree, prev_vdisp, blend.inputs[bcol0])
                else:
                    if prev_rgb: create_link(tree, prev_rgb, blend.inputs[bcol0])

            # Armory can't recognize mute node, so reconnect input to output directly
            #if layer.enable and ch.enable:
            #    create_link(tree, blend.outputs[0], next_rgb)
            #else: create_link(tree, prev_rgb, next_rgb)

            if root_ch.type == 'NORMAL' and ch.normal_map_type == 'VECTOR_DISPLACEMENT_MAP':
                if next_vdisp: create_link(tree, blend.outputs[bout], next_vdisp)
                if prev_rgb and next_rgb: create_link(tree, prev_rgb, next_rgb)
            else:
                if next_rgb: create_link(tree, blend.outputs[bout], next_rgb)
        elif prev_rgb and next_rgb: 
            create_link(tree, prev_rgb, next_rgb)

        if root_ch.type == 'NORMAL' and ch.normal_map_type != 'VECTOR_DISPLACEMENT_MAP' and prev_vdisp and next_vdisp: 
            create_link(tree, prev_vdisp, next_vdisp)

        if next_alpha:
            if not blend or (
                (blend_type != 'MIX' and (has_parent or is_channel_alpha_enabled(root_ch)))
                and not (blend_type == 'OVERLAY' and has_parent and root_ch.type == 'NORMAL')
                ):
                if prev_alpha and next_alpha: create_link(tree, prev_alpha, next_alpha)
            else:
                if blend and next_alpha: create_link(tree, blend.outputs[1], next_alpha)

        # Layer preview
        if yp.layer_preview_mode:

            # If previewing specific mask with any mask or override channel active
            if yp.layer_preview_mode_type == 'SPECIFIC_MASK':
                active_found = False

                for mask in layer.masks:
                    if mask.active_edit:
                        active_found = True
                        break

                for ch in layer.channels:
                    if ch.override and ch.override_type != 'DEFAULT' and ch.active_edit:
                        active_found = True
                        break

                    if ch.override_1 and ch.override_1_type != 'DEFAULT' and ch.active_edit_1:
                        active_found = True
                        break
                
                if not active_found and alpha_preview:
                    create_link(tree, source.outputs[0], alpha_preview)

            elif root_ch == yp.channels[yp.active_channel_index]:
                col_preview = get_essential_node(tree, TREE_END).get(LAYER_VIEWER)
                if col_preview:
                    if root_ch.type == 'NORMAL' and normal_proc: create_link(tree, normal_proc.outputs[0], col_preview)
                    else: create_link(tree, rgb, col_preview)
                if alpha_preview and yp.layer_preview_mode_type != 'SPECIFIC_MASK':
                    create_link(tree, alpha, alpha_preview)
                
    # Clean unused essential nodes
    clean_essential_nodes(tree, exclude_texcoord=True)
