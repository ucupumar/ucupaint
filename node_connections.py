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
        create_link(tree, color_ramp.outputs[0], color_ramp_linear.inputs[0])
        create_link(tree, color_ramp_linear.outputs[0], color_ramp_mix_rgb.inputs[mr_mixcol1])

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

                io_name = root_ch.name + io_suffix['HEIGHT_ONS']
                if io_name in node.inputs:
                    break_input_link(tree, node.inputs[io_name])

                io_name = root_ch.name + io_suffix['HEIGHT_EW']
                if io_name in node.inputs:
                    break_input_link(tree, node.inputs[io_name])

                io_name = root_ch.name + io_suffix['HEIGHT_ONS'] + io_suffix['ALPHA']
                if io_name in node.inputs:
                    break_input_link(tree, node.inputs[io_name])

                io_name = root_ch.name + io_suffix['HEIGHT_EW'] + io_suffix['ALPHA']
                if io_name in node.inputs:
                    break_input_link(tree, node.inputs[io_name])

        #if height_only: continue

        io_name = root_ch.name
        if io_name in node.inputs:
            # Should always fill normal input
            geometry = tree.nodes.get(GEOMETRY)
            if root_ch.type == 'NORMAL' and geometry:
                create_link(tree, geometry.outputs['Normal'], node.inputs[io_name])
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
        if has_channel_childrens(layer, root_ch): continue

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

            io_name = root_ch.name + io_suffix['HEIGHT_ONS'] + io_suffix['GROUP']
            if io_name in node.inputs:
                break_input_link(tree, node.inputs[io_name])

            io_name = root_ch.name + io_suffix['HEIGHT_EW'] + io_suffix['GROUP']
            if io_name in node.inputs:
                break_input_link(tree, node.inputs[io_name])

            io_name = root_ch.name + io_suffix['HEIGHT_ONS'] + io_suffix['ALPHA'] + io_suffix['GROUP']
            if io_name in node.inputs:
                break_input_link(tree, node.inputs[io_name])

            io_name = root_ch.name + io_suffix['HEIGHT_EW'] + io_suffix['ALPHA'] + io_suffix['GROUP']
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

        for i in range (num_of_layers):
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

            if i == num_of_layers-1:
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
        create_link(iterate.node_tree, 
                iterate_start.outputs[uv.name + START_UV], iterate_depth.inputs[uv.name + START_UV])
        create_link(iterate.node_tree, 
                iterate_start.outputs[uv.name + DELTA_UV], iterate_depth.inputs[uv.name + DELTA_UV])

        if baked: parallax_current_uv_mix = iterate.node_tree.nodes.get(uv.baked_parallax_current_uv_mix)
        else: parallax_current_uv_mix = iterate.node_tree.nodes.get(uv.parallax_current_uv_mix)

        mixcol0, mixcol1, mixout = get_mix_color_indices(parallax_current_uv_mix)

        create_link(iterate.node_tree, iterate_branch.outputs[0], parallax_current_uv_mix.inputs[0])
        create_link(iterate.node_tree, 
                iterate_depth.outputs[uv.name + CURRENT_UV], parallax_current_uv_mix.inputs[mixcol0])
        create_link(iterate.node_tree, 
                iterate_start.outputs[uv.name + CURRENT_UV], parallax_current_uv_mix.inputs[mixcol1])

        create_link(iterate.node_tree, 
                parallax_current_uv_mix.outputs[mixout], iterate_end.inputs[uv.name + CURRENT_UV])

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
            create_link(iterate.node_tree, 
                    iterate_start.outputs[base_name + START_UV], iterate_depth.inputs[base_name + START_UV])
            create_link(iterate.node_tree, 
                    iterate_start.outputs[base_name + DELTA_UV], iterate_depth.inputs[base_name + DELTA_UV])

            parallax_current_uv_mix = iterate.node_tree.nodes.get(PARALLAX_CURRENT_MIX_PREFIX + base_name)
            mixcol0, mixcol1, mixout = get_mix_color_indices(parallax_current_uv_mix)

            create_link(iterate.node_tree, iterate_branch.outputs[0], parallax_current_uv_mix.inputs[0])
            create_link(iterate.node_tree, 
                    iterate_depth.outputs[base_name + CURRENT_UV], parallax_current_uv_mix.inputs[mixcol0])
            create_link(iterate.node_tree, 
                    iterate_start.outputs[base_name + CURRENT_UV], parallax_current_uv_mix.inputs[mixcol1])

            create_link(iterate.node_tree, 
                    parallax_current_uv_mix.outputs[mixout], iterate_end.inputs[base_name + CURRENT_UV])

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

#def reconnect_yp_nodes(tree, ch_idx=-1):
def reconnect_yp_nodes(tree, merged_layer_ids = []):
    yp = tree.yp
    nodes = tree.nodes

    #print('Reconnect tree ' + tree.name)

    start = nodes.get(TREE_START)
    end = nodes.get(TREE_END)

    texcoord = nodes.get(TEXCOORD)
    parallax = tree.nodes.get(PARALLAX)
    geometry = tree.nodes.get(GEOMETRY)

    one_value = nodes.get(ONE_VALUE)
    if one_value: one_value = one_value.outputs[0]
    zero_value = nodes.get(ZERO_VALUE)
    if zero_value: zero_value = zero_value.outputs[0]

    # Parallax
    parallax_ch = get_root_parallax_channel(yp)
    parallax = tree.nodes.get(PARALLAX)
    baked_parallax = tree.nodes.get(BAKED_PARALLAX)
    baked_parallax_filter = tree.nodes.get(BAKED_PARALLAX_FILTER)

    # UVs

    uv_maps = {}
    tangents = {}
    bitangents = {}

    for uv in yp.uvs:
        uv_map = nodes.get(uv.uv_map)
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
    #print('Baked UV_Name:', yp.baked_uv_name, baked_uv)
    if yp.use_baked and baked_uv:

        baked_uv_map = nodes.get(baked_uv.uv_map).outputs[0]

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
            create_link(tree, texcoord.outputs[tc], parallax_prep.inputs[0])
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
        end_backface = nodes.get(ch.end_backface)
        clamp = nodes.get(ch.clamp)
        end_max_height = nodes.get(ch.end_max_height)
        end_max_height_tweak = nodes.get(ch.end_max_height_tweak)
        start_normal_filter = nodes.get(ch.start_normal_filter)

        io_name = ch.name
        io_alpha_name = ch.name + io_suffix['ALPHA']
        io_height_name = ch.name + io_suffix['HEIGHT']
        io_height_n_name = ch.name + io_suffix['HEIGHT'] + ' n'
        io_height_s_name = ch.name + io_suffix['HEIGHT'] + ' s'
        io_height_e_name = ch.name + io_suffix['HEIGHT'] + ' e'
        io_height_w_name = ch.name + io_suffix['HEIGHT'] + ' w'

        io_height_ons_name = ch.name + io_suffix['HEIGHT_ONS']
        io_height_ew_name = ch.name + io_suffix['HEIGHT_EW']

        rgb = start.outputs[io_name]
        #if ch.enable_alpha and ch.type == 'RGB':
        if ch.enable_alpha:
            alpha = start.outputs[io_alpha_name]
        else: alpha = one_value

        if ch.type == 'NORMAL':
            if ch.enable_smooth_bump:
                height_ons = start.outputs[io_height_name]
                height_ew = start.outputs[io_height_name]
                height = None
            else:
                height = start.outputs[io_height_name]
                height_ons = None
                height_ew = None
        else: 
            height = None
            height_ons = None
            height_ew = None

        #if ch.type == 'NORMAL' and ch.enable_smooth_bump:
        #    height_ons = start.outputs[io_height_name]
        #    height_ew = start.outputs[io_height_name]
        #else:
        #    height_ons = None
        #    height_ew = None
        
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

            #is_hidden = not layer.enable or is_parent_hidden(layer)

            if yp.layer_preview_mode: # and yp.layer_preview_mode_type == 'LAYER':

                if ch == yp.channels[yp.active_channel_index] and layer == yp.layers[yp.active_layer_index]:

                    col_preview = end.inputs.get(LAYER_VIEWER)
                    alpha_preview = end.inputs.get(LAYER_ALPHA_VIEWER)
                    if col_preview:
                        #create_link(tree, rgb, col_preview)
                        if not layer.enable and zero_value:
                            create_link(tree, zero_value, col_preview)
                        else: create_link(tree, node.outputs[LAYER_VIEWER], col_preview)
                    if alpha_preview:
                        if not layer.enable and zero_value:
                            create_link(tree, zero_value, alpha_preview)
                        else: create_link(tree, node.outputs[LAYER_ALPHA_VIEWER], alpha_preview)
                else:
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

            layer_ch = layer.channels[i]
            #if yp.disable_quick_toggle and not layer_ch.enable:
            #if not (ch.type == 'NORMAL' and need_prev_normal) and not layer_ch.enable:
            if not (ch.type == 'NORMAL' and need_prev_normal) and not layer_ch.enable:
                continue

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
                inp_height = node.inputs.get(ch.name + io_suffix['HEIGHT'] + io_suffix['BACKGROUND'])

                if layer.parent_idx == -1:
                    create_link(tree, bg_rgb, inp)
                    if inp_alpha:
                        create_link(tree, bg_alpha, inp_alpha)
                    if inp_height:
                        create_link(tree, bg_height, inp_height)
                else:
                    break_input_link(tree, inp)
                    if inp_alpha:
                        break_input_link(tree, inp_alpha)
                    if inp_height:
                        break_input_link(tree, inp_height)

            # Merge process doesn't care with parents
            if not merged_layer_ids and layer.parent_idx != -1: continue

            if ch.type == 'NORMAL' and need_prev_normal and not layer_ch.enable:
                create_link(tree, rgb, node.inputs[io_name])
            else: rgb = create_link(tree, rgb, node.inputs[io_name])[io_name]

            #if ch.type =='RGB' and ch.enable_alpha:
            if ch.enable_alpha:
                alpha = create_link(tree, alpha, node.inputs[io_alpha_name])[io_alpha_name]

            if height_ons:
                if ch.type == 'NORMAL' and need_prev_normal and not layer_ch.enable:
                    create_link(tree, height_ons, node.inputs[io_height_ons_name])
                    create_link(tree, height_ew, node.inputs[io_height_ew_name])
                else:
                    height_ons = create_link(tree, height_ons, node.inputs[io_height_ons_name])[io_height_ons_name]
                    height_ew = create_link(tree, height_ew, node.inputs[io_height_ew_name])[io_height_ew_name]
            elif height:
                if ch.type == 'NORMAL' and need_prev_normal and not layer_ch.enable:
                    create_link(tree, height, node.inputs[io_height_name])
                else: height = create_link(tree, height, node.inputs[io_height_name])[io_height_name]

        rgb, alpha = reconnect_all_modifier_nodes(tree, ch, rgb, alpha)

        if end_linear:
            if ch.type == 'NORMAL':
                rgb = create_link(tree, rgb, end_linear.inputs['Normal Overlay'])[0]
                if end_max_height:
                    create_link(tree, end_max_height.outputs[0], end_linear.inputs['Max Height'])

                if height_ons:
                    height = create_link(tree, height_ons, end_linear.inputs['Height ONS'])[1]
                    create_link(tree, height_ew, end_linear.inputs['Height EW'])
                else:
                    height = create_link(tree, height, end_linear.inputs[0])[1]
                
                if tangent and bitangent:
                    create_link(tree, tangent, end_linear.inputs['Tangent'])
                    create_link(tree, bitangent, end_linear.inputs['Bitangent'])
            else:
                rgb = create_link(tree, rgb, end_linear.inputs[0])[0]

                if clamp:
                    mixcol0, mixcol1, mixout = get_mix_color_indices(clamp)
                    rgb = create_link(tree, rgb, clamp.inputs[mixcol0])[mixout]

        if yp.use_baked and not ch.no_layer_using and not ch.disable_global_baked: # and baked_uv:
            baked = nodes.get(ch.baked)
            if baked:
                rgb = baked.outputs[0]

                #if ch.type == 'RGB' and ch.enable_alpha:
                if ch.enable_alpha:
                    alpha = baked.outputs[1]

                create_link(tree, baked_uv_map, baked.inputs[0])

            if ch.type == 'NORMAL':
                baked_normal_overlay = nodes.get(ch.baked_normal_overlay)
                if ch.enable_subdiv_setup and not ch.subdiv_adaptive and baked_normal_overlay:
                    rgb = baked_normal_overlay.outputs[0]
                    create_link(tree, baked_uv_map, baked_normal_overlay.inputs[0])

                # Sometimes there's no baked normal overlay, so empty up the rgb so it will use original normal
                if not baked_normal_overlay and height_ch.enable_subdiv_setup and not height_ch.subdiv_adaptive:
                    rgb = None

                baked_normal_prep = nodes.get(ch.baked_normal_prep)
                if baked_normal_prep:
                    if rgb:
                        rgb = create_link(tree, rgb, baked_normal_prep.inputs[0])[0]
                    else:
                        rgb = baked_normal_prep.outputs[0]
                        break_input_link(tree, baked_normal_prep.inputs[0])

                    #HACK: Some earlier nodes have wrong default colot input
                    baked_normal_prep.inputs[0].default_value = (0.5, 0.5, 1.0, 1.0)

                baked_normal = nodes.get(ch.baked_normal)
                if baked_normal:
                    rgb = create_link(tree, rgb, baked_normal.inputs[1])[0]

                baked_disp = nodes.get(ch.baked_disp)
                if baked_disp: 
                    height = baked_disp.outputs[0]
                    create_link(tree, baked_uv_map, baked_disp.inputs[0])

        if end_backface:
            alpha = create_link(tree, alpha, end_backface.inputs[0])[0]
            create_link(tree, geometry.outputs['Backfacing'], end_backface.inputs[1])

        #print(rgb)
        create_link(tree, rgb, end.inputs[io_name])
        #if ch.type == 'RGB' and ch.enable_alpha:
        if ch.enable_alpha:
            create_link(tree, alpha, end.inputs[io_alpha_name])
        if ch.type == 'NORMAL':
            create_link(tree, height, end.inputs[io_height_name])
            if ch.name + io_suffix['MAX_HEIGHT'] in end.inputs and end_max_height:
                if end_max_height_tweak:
                    create_link(tree, end_max_height.outputs[0], end_max_height_tweak.inputs[0])
                    create_link(tree, end_max_height_tweak.outputs[0], end.inputs[ch.name + io_suffix['MAX_HEIGHT']])
                else:
                    create_link(tree, end_max_height.outputs[0], end.inputs[ch.name + io_suffix['MAX_HEIGHT']])

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

def reconnect_channel_source_internal_nodes(ch, ch_source_tree):

    tree = ch_source_tree

    source = tree.nodes.get(ch.source)
    linear = tree.nodes.get(ch.linear)
    start = tree.nodes.get(TREE_START)
    solid = tree.nodes.get(ONE_VALUE)
    end = tree.nodes.get(TREE_END)

    create_link(tree, start.outputs[0], source.inputs[0])

    rgb = source.outputs[0]
    if ch.override_type == 'MUSGRAVE':
        alpha = solid.outputs[0]
    else: alpha = source.outputs[1]

    if linear:
        rgb = create_link(tree, rgb, linear.inputs[0])[0]

    if ch.override_type not in {'IMAGE', 'VCOL', 'HEMI', 'OBJECT_INDEX', 'MUSGRAVE'}:
        rgb_1 = source.outputs[1]
        alpha = solid.outputs[0]
        alpha_1 = solid.outputs[0]

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

def reconnect_source_internal_nodes(layer):
    tree = get_source_tree(layer)

    source = tree.nodes.get(layer.source)
    #mapping = tree.nodes.get(layer.mapping)
    linear = tree.nodes.get(layer.linear)
    divider_alpha = tree.nodes.get(layer.divider_alpha)
    flip_y = tree.nodes.get(layer.flip_y)
    start = tree.nodes.get(TREE_START)
    solid = tree.nodes.get(ONE_VALUE)
    end = tree.nodes.get(TREE_END)

    #if layer.type != 'VCOL':
    #    create_link(tree, start.outputs[0], source.inputs[0])
    #if mapping:
    #    create_link(tree, start.outputs[0], mapping.inputs[0])
    #    create_link(tree, mapping.outputs[0], source.inputs[0])
    #else:
    create_link(tree, start.outputs[0], source.inputs[0])

    rgb = source.outputs[0]
    if layer.type == 'MUSGRAVE':
        alpha = solid.outputs[0]
    else: alpha = source.outputs[1]

    if divider_alpha: 
        mixcol0, mixcol1, mixout = get_mix_color_indices(divider_alpha)
        rgb = create_link(tree, rgb, divider_alpha.inputs[mixcol0])[mixout]
        create_link(tree, alpha, divider_alpha.inputs[mixcol1])

    if linear:
        rgb = create_link(tree, rgb, linear.inputs[0])[0]

    if flip_y:
        rgb = create_link(tree, rgb, flip_y.inputs[0])[0]

    if layer.type not in {'IMAGE', 'VCOL', 'HEMI', 'OBJECT_INDEX', 'MUSGRAVE'}:
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

    if layer.type in {'IMAGE', 'VCOL', 'HEMI', 'OBJECT_INDEX', 'MUSGRAVE'}:

        rgb, alpha = reconnect_all_modifier_nodes(tree, layer, rgb, alpha)

    create_link(tree, rgb, end.inputs[0])
    create_link(tree, alpha, end.inputs[1])

def reconnect_mask_internal_nodes(mask):

    tree = get_mask_tree(mask)

    source = tree.nodes.get(mask.source)
    #mapping = tree.nodes.get(mask.mapping)
    linear = tree.nodes.get(mask.linear)
    start = tree.nodes.get(TREE_START)
    end = tree.nodes.get(TREE_END)

    if mask.type not in {'VCOL', 'HEMI', 'OBJECT_INDEX'}:
        #if mapping:
        #    create_link(tree, start.outputs[0], mapping.inputs[0])
        #    create_link(tree, mapping.outputs[0], source.inputs[0])
        #else:
        create_link(tree, start.outputs[0], source.inputs[0])

    val = source.outputs[0]

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

    start = nodes.get(TREE_START)
    end = nodes.get(TREE_END)
    one_value = nodes.get(ONE_VALUE)
    if one_value: one_value = one_value.outputs[0]
    zero_value = nodes.get(ZERO_VALUE)
    if zero_value: zero_value = zero_value.outputs[0]

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
    uv_neighbor_1 = nodes.get(layer.uv_neighbor_1)

    if layer.type == 'GROUP':
        texcoord = source
    else: texcoord = nodes.get(layer.texcoord)

    #texcoord = nodes.get(TEXCOORD)
    geometry = nodes.get(GEOMETRY)
    blur_vector = nodes.get(layer.blur_vector)
    mapping = nodes.get(layer.mapping)
    linear = nodes.get(layer.linear)
    divider_alpha = nodes.get(layer.divider_alpha)
    flip_y = nodes.get(layer.flip_y)

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

    # Fake lighting stuff
    bump_process = nodes.get(layer.bump_process)
    if bump_process and height_root_ch:

        prev_normal = texcoord.outputs.get(height_root_ch.name)
        if height_root_ch.enable_smooth_bump:
            prev_height_ons = texcoord.outputs.get(height_root_ch.name + io_suffix['HEIGHT_ONS'])
            prev_height_ew = texcoord.outputs.get(height_root_ch.name + io_suffix['HEIGHT_EW'])

            create_link(tree, prev_height_ons, bump_process.inputs['Height ONS'])
            create_link(tree, prev_height_ew, bump_process.inputs['Height EW'])
        else:
            prev_height = texcoord.outputs.get(height_root_ch.name + io_suffix['HEIGHT'])

            create_link(tree, prev_height, bump_process.inputs['Height'])

        create_link(tree, prev_normal, bump_process.inputs['Normal Overlay'])
        create_link(tree, tangent, bump_process.inputs['Tangent'])
        create_link(tree, bitangent, bump_process.inputs['Bitangent'])

    if layer.type == 'HEMI':
        if layer.hemi_use_prev_normal and bump_process:
            create_link(tree, bump_process.outputs['Normal'], source.inputs['Normal'])
        else: create_link(tree, geometry.outputs['Normal'], source.inputs['Normal'])

    # Find override channels
    #using_vector = is_channel_override_using_vector(layer)

    # Texcoord
    vector = None
    #if layer.type not in {'VCOL', 'BACKGROUND', 'COLOR', 'GROUP', 'HEMI', 'OBJECT_INDEX'} or using_vector:
    if is_layer_using_vector(layer):
        if layer.texcoord_type == 'UV':
            vector = texcoord.outputs.get(layer.uv_name + io_suffix['UV'])
        else: vector = texcoord.outputs[io_names[layer.texcoord_type]]

        if vector and blur_vector:
            vector = create_link(tree, vector, blur_vector.inputs[1])[0]

        if vector and mapping:
            vector = create_link(tree, vector, mapping.inputs[0])[0]
            #create_link(tree, mapping.outputs[0], source.inputs[0])

    if vector and layer.type not in {'VCOL', 'BACKGROUND', 'COLOR', 'GROUP', 'HEMI', 'OBJECT_INDEX'}:
        #if source_group or not mapping:
        create_link(tree, vector, source.inputs[0])

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
    start_rgb = source.outputs[0]
    start_rgb_1 = None
    if layer.type not in {'COLOR', 'HEMI', 'OBJECT_INDEX', 'MUSGRAVE'}:
        start_rgb_1 = source.outputs[1]

    # Alpha
    if layer.type == 'IMAGE' or source_group:
        start_alpha = source.outputs[1]
    elif layer.type == 'VCOL' and 'Alpha' in source.outputs:
        start_alpha = source.outputs['Alpha']
    else: start_alpha = one_value
    start_alpha_1 = one_value

    alpha_preview = end.inputs.get(LAYER_ALPHA_VIEWER)

    # RGB continued
    if not source_group:
        if divider_alpha: 
            mixcol0, mixcol1, mixout = get_mix_color_indices(divider_alpha)
            start_rgb = create_link(tree, start_rgb, divider_alpha.inputs[mixcol0])[mixout]
            create_link(tree, start_alpha, divider_alpha.inputs[mixcol1])
        if linear: start_rgb = create_link(tree, start_rgb, linear.inputs[0])[0]
        if flip_y: start_rgb = create_link(tree, start_rgb, flip_y.inputs[0])[0]

    if source_group and layer.type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'HEMI', 'OBJECT_INDEX', 'MUSGRAVE'}:
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

        if layer.type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'COLOR', 'GROUP', 'HEMI', 'OBJECT_INDEX', 'MUSGRAVE'}:
            mod_group_1 = nodes.get(layer.mod_group_1)
            start_rgb_1, start_alpha_1 = reconnect_all_modifier_nodes(
                    tree, layer, source.outputs[1], one_value, mod_group_1)

    # UV neighbor vertex color
    if layer.type in {'VCOL', 'GROUP', 'HEMI', 'OBJECT_INDEX'} and uv_neighbor:
        if layer.type in {'VCOL', 'HEMI', 'OBJECT_INDEX'}:
            create_link(tree, start_rgb, uv_neighbor.inputs[0])

        if tangent and bitangent:
            create_link(tree, tangent, uv_neighbor.inputs['Tangent'])
            create_link(tree, bitangent, uv_neighbor.inputs['Bitangent'])

        if layer.type == 'VCOL' and uv_neighbor_1:
            create_link(tree, start_alpha, uv_neighbor_1.inputs[0])

            if tangent and bitangent:
                create_link(tree, tangent, uv_neighbor_1.inputs['Tangent'])
                create_link(tree, bitangent, uv_neighbor_1.inputs['Bitangent'])

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
        #compare_alpha = nodes.get(height_ch.height_blend).outputs[1]
        compare_alpha = nodes.get(height_ch.height_blend).outputs.get('Normal Alpha')
    else: compare_alpha = None

    chain = -1
    if trans_bump_ch:
        #if trans_bump_ch.write_height:
        #    chain = 10000
        #else: 
        chain = min(len(layer.masks), trans_bump_ch.transition_bump_chain)

    # Root mask value for merging mask
    root_mask_val = one_value

    # Layer Masks
    for i, mask in enumerate(layer.masks):

        # Mask source
        if mask.group_node != '':
            mask_source = nodes.get(mask.group_node)
            reconnect_mask_internal_nodes(mask)
            #mask_mapping = None
            mask_val = mask_source.outputs[0]
        else:
            mask_source = nodes.get(mask.source)
            mask_linear = nodes.get(mask.linear)
            #mask_mapping = nodes.get(mask.mapping)

            mask_val = mask_source.outputs[0]

            if mask_linear:
                mask_val = create_link(tree, mask_val, mask_linear.inputs[0])[0]

            for mod in mask.modifiers:
                mask_val = reconnect_mask_modifier_nodes(tree, mod, mask_val)

        mask_blur_vector = nodes.get(mask.blur_vector)
        mask_mapping = nodes.get(mask.mapping)

        if yp.layer_preview_mode and yp.layer_preview_mode_type == 'SPECIFIC_MASK' and mask.active_edit == True:
            if alpha_preview:
                create_link(tree, mask_val, alpha_preview)

        # Hemi related
        if mask.type == 'HEMI':
            if mask.hemi_use_prev_normal and bump_process:
                create_link(tree, bump_process.outputs['Normal'], mask_source.inputs['Normal'])
            else: create_link(tree, geometry.outputs['Normal'], mask_source.inputs['Normal'])

        # Mask source directions
        mask_source_n = nodes.get(mask.source_n)
        mask_source_s = nodes.get(mask.source_s)
        mask_source_e = nodes.get(mask.source_e)
        mask_source_w = nodes.get(mask.source_w)

        # Mask texcoord
        #mask_uv_map = nodes.get(mask.uv_map)
        if mask.type not in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'COLOR_ID'}:
            if mask.texcoord_type == 'UV':
                #mask_vector = mask_uv_map.outputs[0]
                #mask_vector = mask_uv_map.outputs[0]
                mask_vector = texcoord.outputs.get(mask.uv_name + io_suffix['UV'])
            else: 
                mask_vector = texcoord.outputs[io_names[mask.texcoord_type]]

            if mask_blur_vector:
                mask_vector = create_link(tree, mask_vector, mask_blur_vector.inputs[1])[0]

            if mask_mapping:
                mask_vector = create_link(tree, mask_vector, mask_mapping.inputs[0])[0]
                #create_link(tree, mask_mapping.outputs[0], mask_source.inputs[0])
            #else:
            create_link(tree, mask_vector, mask_source.inputs[0])

        # Mask uv neighbor
        mask_uv_neighbor = nodes.get(mask.uv_neighbor)
        if mask_uv_neighbor:

            if mask.type in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'COLOR_ID'}:
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

                if mask_source_n: create_link(tree, mask_uv_neighbor.outputs['n'], mask_source_n.inputs[0])
                if mask_source_s: create_link(tree, mask_uv_neighbor.outputs['s'], mask_source_s.inputs[0])
                if mask_source_e: create_link(tree, mask_uv_neighbor.outputs['e'], mask_source_e.inputs[0])
                if mask_source_w: create_link(tree, mask_uv_neighbor.outputs['w'], mask_source_w.inputs[0])

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

        # Mask root mix
        mmix = nodes.get(mask.mix)
        if mmix:
            mixcol0, mixcol1, mixout = get_mix_color_indices(mmix)
            root_mask_val = create_link(tree, root_mask_val, mmix.inputs[mixcol0])[mixout]
            create_link(tree, mask_val, mmix.inputs[mixcol1])

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

            if mix_remains:
                create_link(tree, mask_val, mix_remains.inputs[mr_mixcol1])

            if mix_normal:
                create_link(tree, mask_val, mix_normal.inputs[mn_mixcol1])

            if mask_mix:
                create_link(tree, mask_val, mask_mix.inputs[mmixcol1])
                if root_ch.type == 'NORMAL' and root_ch.enable_smooth_bump:
                    if mask.type in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'COLOR_ID'}:
                        if mask_uv_neighbor:
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
                            if mask_source_n: 
                                create_link(tree, mask_source_n.outputs[0], mask_mix.inputs['Color2 n'])
                            else: 
                                create_link(tree, mask_val, mask_mix.inputs['Color2 n'])

                        if mask_source_s: create_link(tree, mask_source_s.outputs[0], mask_mix.inputs['Color2 s'])
                        if mask_source_e: create_link(tree, mask_source_e.outputs[0], mask_mix.inputs['Color2 e'])
                        if mask_source_w: create_link(tree, mask_source_w.outputs[0], mask_mix.inputs['Color2 w'])

    if merge_mask and yp.layer_preview_mode:
        if alpha_preview:
            create_link(tree, root_mask_val, alpha_preview)
        return
    
    # Parent flag
    has_parent = layer.parent_idx != -1

    # Layer Channels
    for i, ch in enumerate(layer.channels):

        root_ch = yp.channels[i]

        #if yp.disable_quick_toggle and not ch.enable: continue
        if not ch.enable: 
            
            # Disabled channel layer preview
            if yp.layer_preview_mode:
                if yp.layer_preview_mode_type == 'SPECIFIC_MASK' and ch.override and ch.active_edit == True:
                    if alpha_preview and zero_value:
                        create_link(tree, zero_value, alpha_preview)
                elif root_ch == yp.channels[yp.active_channel_index]:
                    col_preview = end.inputs.get(LAYER_VIEWER)
                    if col_preview and zero_value:
                        create_link(tree, zero_value, col_preview)
                    if alpha_preview and zero_value:
                        create_link(tree, zero_value, alpha_preview)
                    #break_input_link(tree, col_preview)
                    #break_input_link(tree, alpha_preview)
                    #col_preview.default_value = (0,0,0,0)
                    #alpha_preview.default_value = 0

            continue

        # Rgb and alpha start
        rgb = start_rgb
        alpha = start_alpha
        bg_alpha = None

        prev_rgb = start.outputs.get(root_ch.name)
        prev_alpha = start.outputs.get(root_ch.name + io_suffix['ALPHA'])

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

            if root_ch.type == 'NORMAL' and root_ch.enable_smooth_bump:

                height_group_unpack = nodes.get(ch.height_group_unpack)
                height_alpha_group_unpack = nodes.get(ch.height_alpha_group_unpack)

                # Connect
                create_link(tree, source.outputs[root_ch.name + io_suffix['HEIGHT_ONS'] + io_suffix['GROUP']],
                        height_group_unpack.inputs[0])
                create_link(tree, source.outputs[root_ch.name + io_suffix['HEIGHT_EW'] + io_suffix['GROUP']],
                        height_group_unpack.inputs[1])

                create_link(tree, 
                        source.outputs[root_ch.name + io_suffix['HEIGHT_ONS'] + io_suffix['ALPHA'] + io_suffix['GROUP']],
                        height_alpha_group_unpack.inputs[0])
                create_link(tree, 
                        source.outputs[root_ch.name + io_suffix['HEIGHT_EW'] + io_suffix['ALPHA'] + io_suffix['GROUP']],
                        height_alpha_group_unpack.inputs[1])

            if root_ch.type == 'NORMAL' and ch.enable_transition_bump:
                #rgb = source.outputs.get(root_ch.name + ' Height' + io_suffix['GROUP'])
                if root_ch.enable_smooth_bump:
                    rgb = height_group_unpack.outputs[0]
                else: rgb = source.outputs.get(root_ch.name + io_suffix['HEIGHT'] + io_suffix['GROUP'])
            else:
                rgb = source.outputs.get(root_ch.name + io_suffix['GROUP'])

            if root_ch.type == 'NORMAL':
                if root_ch.enable_smooth_bump:
                    alpha = height_alpha_group_unpack.outputs[0]
                else: alpha = source.outputs.get(root_ch.name + io_suffix['HEIGHT'] + io_suffix['ALPHA'] + io_suffix['GROUP'])
                normal_alpha = source.outputs.get(root_ch.name + io_suffix['ALPHA'] + io_suffix['GROUP'])
            else:
                alpha = source.outputs.get(root_ch.name + io_suffix['ALPHA'] + io_suffix['GROUP'])

            group_alpha = alpha

        elif layer.type == 'BACKGROUND':
            rgb = source.outputs[root_ch.name + io_suffix['BACKGROUND']]
            alpha = one_value

            if root_ch.enable_alpha:
                bg_alpha = source.outputs[root_ch.name + io_suffix['ALPHA'] + io_suffix['BACKGROUND']]

        # Get source output index
        source_index = 0
        if layer.type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'COLOR', 'HEMI', 'OBJECT_INDEX', 'MUSGRAVE'}:
            # Noise and voronoi output has flipped order since Blender 2.81
            if is_greater_than_281() and layer.type in {'NOISE', 'VORONOI'}:
                if ch.layer_input == 'RGB':
                    rgb = start_rgb_1
                    alpha = start_alpha_1
                    source_index = 2
            elif ch.layer_input == 'ALPHA':
                rgb = start_rgb_1
                alpha = start_alpha_1
                source_index = 2

        rgb_before_override = rgb

        # Channel Override 
        if ch.override and (root_ch.type != 'NORMAL' or ch.normal_map_type != 'NORMAL_MAP'):

            ch_source_group = nodes.get(ch.source_group)
            if ch_source_group:
                ch_source = ch_source_group
                reconnect_channel_source_internal_nodes(ch, ch_source_group.node_tree)
            else: ch_source = nodes.get(ch.source)

            if ch_source:
                rgb = ch_source.outputs[0]
                # Override channel will not output alpha whatsoever
                #if layer.type != 'IMAGE':
                #    if ch.override_type in {'IMAGE'}:
                #        alpha = ch_source.outputs[1]
                #    else: alpha = one_value

            ch_uv_neighbor = nodes.get(ch.uv_neighbor)
            if ch_uv_neighbor:

                create_link(tree, vector, ch_uv_neighbor.inputs[0])

                if ch.override_type in {'VCOL', 'HEMI', 'OBJECT_INDEX'}:
                    create_link(tree, rgb, ch_uv_neighbor.inputs[0])

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

            if 'Vector' in ch_source.inputs:
                create_link(tree, vector, ch_source.inputs['Vector'])

            if yp.layer_preview_mode and yp.layer_preview_mode_type == 'SPECIFIC_MASK' and ch.active_edit == True:
                if alpha_preview:
                    create_link(tree, rgb, alpha_preview)

        # Override Normal
        normal = rgb_before_override
        ch_source_1 = nodes.get(ch.source_1)
        ch_linear_1 = nodes.get(ch.linear_1)
        ch_flip_y = nodes.get(ch.flip_y) # Flip Y will only applied to normal override

        if ch_source_1: #and root_ch.type == 'NORMAL' and ch.override_1: #and ch.normal_map_type == 'BUMP_NORMAL_MAP':
            normal = ch_source_1.outputs[0]
            if ch_linear_1: normal = create_link(tree, normal, ch_linear_1.inputs[0])[0]
            if ch_flip_y: normal = create_link(tree, normal, ch_flip_y.inputs[0])[0]

            if 'Vector' in ch_source_1.inputs:
                create_link(tree, vector, ch_source_1.inputs['Vector'])

        if ch_idx != -1 and i != ch_idx: continue

        intensity = nodes.get(ch.intensity)
        intensity_multiplier = nodes.get(ch.intensity_multiplier)
        extra_alpha = nodes.get(ch.extra_alpha)
        blend = nodes.get(ch.blend)
        bcol0, bcol1, bout = get_mix_color_indices(blend)

        if ch.source_group == '' and (root_ch.type != 'NORMAL' or ch.normal_map_type != 'NORMAL_MAP'):
            ch_linear = nodes.get(ch.linear)
            if ch_linear:
                create_link(tree, rgb, ch_linear.inputs[0])
                rgb = ch_linear.outputs[0]

        # Check if normal is overriden
        if root_ch.type == 'NORMAL' and ch.normal_map_type == 'NORMAL_MAP':
            rgb = normal

        mod_group = nodes.get(ch.mod_group)

        rgb_before_mod = rgb
        alpha_before_mod = alpha

        # Background layer won't use modifier outputs
        #if layer.type == 'BACKGROUND' or (layer.type == 'COLOR' and root_ch.type == 'NORMAL'):
        #if layer.type == 'BACKGROUND':
        if layer.type == 'BACKGROUND' or (layer.type == 'GROUP' and root_ch.type == 'NORMAL'):
            #reconnect_all_modifier_nodes(tree, ch, rgb, alpha, mod_group)
            pass
        elif root_ch.type == 'NORMAL' and ch.normal_map_type == 'NORMAL_MAP':
            rgb, alpha = reconnect_all_modifier_nodes(tree, ch, rgb, alpha, use_modifier_1=True)
        else:
            rgb, alpha = reconnect_all_modifier_nodes(tree, ch, rgb, alpha, mod_group)

            if root_ch.type == 'NORMAL' and ch.normal_map_type == 'BUMP_NORMAL_MAP':
                normal, alpha_normal = reconnect_all_modifier_nodes(tree, ch, normal, alpha_before_mod, use_modifier_1=True)

        rgb_after_mod = rgb
        alpha_after_mod = alpha

        # For transition input
        transition_input = alpha
        if chain == 0 and intensity_multiplier:
            alpha = create_link(tree, alpha, intensity_multiplier.inputs[0])[0]

        # Mask multiplies
        for j, mask in enumerate(layer.masks):
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

        # If transition bump is not found, use last alpha as input
        if not trans_bump_ch:
            transition_input = alpha

        # Bookmark alpha before intensity because it can be useful
        alpha_before_intensity = alpha

        # Pass alpha to intensity
        if intensity:
            alpha = create_link(tree, alpha, intensity.inputs[0])[0]

        if root_ch.type == 'NORMAL':

            write_height = get_write_height(ch)

            height_proc = nodes.get(ch.height_proc)
            normal_proc = nodes.get(ch.normal_proc)

            height_blend = nodes.get(ch.height_blend)
            hbcol0, hbcol1, hbout = get_mix_color_indices(height_blend)

            spread_alpha = nodes.get(ch.spread_alpha)
            #spread_alpha_n = nodes.get(ch.spread_alpha_n)
            #spread_alpha_s = nodes.get(ch.spread_alpha_s)
            #spread_alpha_e = nodes.get(ch.spread_alpha_e)
            #spread_alpha_w = nodes.get(ch.spread_alpha_w)

            if root_ch.enable_smooth_bump:

                prev_height_ons = start.outputs.get(root_ch.name + io_suffix['HEIGHT_ONS'])
                prev_height_ew = start.outputs.get(root_ch.name + io_suffix['HEIGHT_EW'])
                prev_height_alpha_ons = start.outputs.get(root_ch.name + io_suffix['HEIGHT_ONS'] + io_suffix['ALPHA'])
                prev_height_alpha_ew = start.outputs.get(root_ch.name + io_suffix['HEIGHT_EW'] + io_suffix['ALPHA'])

                next_height_ons = end.inputs.get(root_ch.name + io_suffix['HEIGHT_ONS'])
                next_height_ew = end.inputs.get(root_ch.name + io_suffix['HEIGHT_EW'])
                next_height_alpha_ons = end.inputs.get(root_ch.name + io_suffix['HEIGHT_ONS'] + io_suffix['ALPHA'])
                next_height_alpha_ew = end.inputs.get(root_ch.name + io_suffix['HEIGHT_EW'] + io_suffix['ALPHA'])

            else:
                prev_height = start.outputs.get(root_ch.name + io_suffix['HEIGHT'])
                next_height = end.inputs.get(root_ch.name + io_suffix['HEIGHT'])
                prev_height_alpha = start.outputs.get(root_ch.name + io_suffix['HEIGHT'] + io_suffix['ALPHA'])
                next_height_alpha = end.inputs.get(root_ch.name + io_suffix['HEIGHT'] + io_suffix['ALPHA'])

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

            elif layer.type in {'VCOL', 'HEMI', 'OBJECT_INDEX'} and uv_neighbor:
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
                    rgb_n = height_group_unpack.outputs[1]
                    rgb_s = height_group_unpack.outputs[2]
                    rgb_e = height_group_unpack.outputs[3]
                    rgb_w = height_group_unpack.outputs[4]

                    alpha_n = height_alpha_group_unpack.outputs[1]
                    alpha_s = height_alpha_group_unpack.outputs[2]
                    alpha_e = height_alpha_group_unpack.outputs[3]
                    alpha_w = height_alpha_group_unpack.outputs[4]

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
            if ch.normal_blend_type == 'OVERLAY':
                create_link(tree, tangent, blend.inputs['Tangent'])
                create_link(tree, bitangent, blend.inputs['Bitangent'])

            #if layer.type not in {'BACKGROUND', 'GROUP'}: #, 'COLOR'}:

            if ch.normal_map_type == 'NORMAL_MAP':
                create_link(tree, rgb, normal_proc.inputs['Normal Map'])
            elif ch.normal_map_type == 'BUMP_NORMAL_MAP':
                create_link(tree, normal, normal_proc.inputs['Normal Map'])
                #else: create_link(tree, rgb, normal_proc.inputs['Normal Map'])

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
            remains = one_value

            tb_falloff = nodes.get(ch.tb_falloff)

            if chain == 0 or len(layer.masks) == 0:
                if tb_falloff:
                    end_chain = pure = create_link(tree, end_chain, tb_falloff.inputs[0])[0]

                    if root_ch.enable_smooth_bump:
                        end_chain_n = alpha_n = create_link(tree, end_chain_n, tb_falloff.inputs['Value n'])['Value n']
                        end_chain_s = alpha_s = create_link(tree, end_chain_n, tb_falloff.inputs['Value s'])['Value s']
                        end_chain_e = alpha_e = create_link(tree, end_chain_n, tb_falloff.inputs['Value e'])['Value e']
                        end_chain_w = alpha_w = create_link(tree, end_chain_n, tb_falloff.inputs['Value w'])['Value w']

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
                        alpha_n = create_link(tree, one_value, mask_mix.inputs['Color1 n'])['Color n']
                        alpha_s = create_link(tree, one_value, mask_mix.inputs['Color1 s'])['Color s']
                        alpha_e = create_link(tree, one_value, mask_mix.inputs['Color1 e'])['Color e']
                        alpha_w = create_link(tree, one_value, mask_mix.inputs['Color1 w'])['Color w']
                    elif 'Color1 n' in mask_mix.inputs:
                        alpha_n = create_link(tree, alpha_n, mask_mix.inputs['Color1 n'])['Color n']
                        alpha_s = create_link(tree, alpha_s, mask_mix.inputs['Color1 s'])['Color s']
                        alpha_e = create_link(tree, alpha_e, mask_mix.inputs['Color1 e'])['Color e']
                        alpha_w = create_link(tree, alpha_w, mask_mix.inputs['Color1 w'])['Color w']

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
                        create_link(tree, mask_mix.outputs[mmixout], tb_falloff.inputs[0])[0]
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

            if 'Value' in height_proc.inputs:
                #create_link(tree, rgb_after_mod, height_proc.inputs['Value'])
                if layer.type == 'BACKGROUND':
                    create_link(tree, one_value, height_proc.inputs['Value'])
                else: create_link(tree, rgb, height_proc.inputs['Value'])

            if 'Value n' in  height_proc.inputs: 
                if layer.type == 'BACKGROUND':
                    create_link(tree, one_value, height_proc.inputs['Value n'])
                    create_link(tree, one_value, height_proc.inputs['Value s'])
                    create_link(tree, one_value, height_proc.inputs['Value e'])
                    create_link(tree, one_value, height_proc.inputs['Value w'])
                else:
                    create_link(tree, rgb_n, height_proc.inputs['Value n'])
                    create_link(tree, rgb_s, height_proc.inputs['Value s'])
                    create_link(tree, rgb_e, height_proc.inputs['Value e'])
                    create_link(tree, rgb_w, height_proc.inputs['Value w'])

            if layer.type == 'GROUP':

                normal_group = source.outputs.get(root_ch.name + io_suffix['GROUP'])
                create_link(tree, normal_group, normal_proc.inputs['Normal'])

                if root_ch.enable_smooth_bump:
                    height_group = height_group_unpack.outputs[0]
                else: height_group = source.outputs.get(root_ch.name + io_suffix['HEIGHT'] + io_suffix['GROUP'])
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

                    if 'Edge 1 Alpha' in normal_proc.inputs:
                        if not write_height and not root_ch.enable_smooth_bump:
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

                    if not write_height and not root_ch.enable_smooth_bump:

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

            height_alpha = alpha
            alpha_ns = None
            alpha_ew = None

            if 'Alpha' in height_proc.inputs:
                alpha = create_link(tree, alpha_before_intensity, height_proc.inputs['Alpha'])['Alpha']
                if 'Alpha n' in height_proc.inputs:
                    create_link(tree, alpha_n, height_proc.inputs['Alpha n'])
                    create_link(tree, alpha_s, height_proc.inputs['Alpha s'])
                    create_link(tree, alpha_e, height_proc.inputs['Alpha e'])
                    create_link(tree, alpha_w, height_proc.inputs['Alpha w'])
            else:
                if trans_bump_crease:
                    if not write_height and not root_ch.enable_smooth_bump:
                        alpha = height_proc.outputs['Filtered Alpha']
                    else: alpha = height_proc.outputs['Combined Alpha']

                elif 'Normal Alpha' in height_proc.outputs and (write_height or root_ch.enable_smooth_bump):
                    alpha = height_proc.outputs['Normal Alpha']

                alpha_ns = alpha_ew = alpha

            # Height Alpha
            if 'Filtered Alpha' in height_proc.outputs and (not write_height and not root_ch.enable_smooth_bump):
                height_alpha = alpha = height_proc.outputs['Filtered Alpha']
            elif 'Combined Alpha' in height_proc.outputs:
                height_alpha = alpha = height_proc.outputs['Combined Alpha']
            elif 'Normal Alpha' in height_proc.outputs:
                height_alpha = height_proc.outputs['Normal Alpha']
            elif 'Alpha' in height_proc.outputs:
                height_alpha = height_proc.outputs['Alpha']

            if 'Alpha NS' in height_proc.outputs:
                alpha_ns = height_proc.outputs['Alpha NS']
            if 'Alpha EW' in height_proc.outputs:
                alpha_ew = height_proc.outputs['Alpha EW']

            if not root_ch.enable_smooth_bump:

                if ch.normal_blend_type in {'MIX', 'OVERLAY'}:
                    if has_parent:
                        # Overlay without write height will disconnect prev height
                        if not write_height and ch.normal_blend_type == 'OVERLAY':
                            break_input_link(tree, height_blend.inputs[0])
                        else: create_link(tree, prev_height, height_blend.inputs[0])

                        create_link(tree, prev_alpha, height_blend.inputs[1])
                        create_link(tree, height_proc.outputs['Height'], height_blend.inputs[2])
                        height_alpha = create_link(tree, height_alpha, height_blend.inputs[3])[1]
                    else:
                        # Overlay without write height will disconnect prev height
                        if not write_height and ch.normal_blend_type == 'OVERLAY':
                            break_input_link(tree, height_blend.inputs[hbcol0])
                        else: create_link(tree, prev_height, height_blend.inputs[hbcol0])

                        create_link(tree, height_alpha, height_blend.inputs[0])
                        create_link(tree, height_proc.outputs['Height'], height_blend.inputs[hbcol1])
                else:
                    # Overlay without write height will disconnect prev height
                    if not write_height and ch.normal_blend_type == 'OVERLAY':
                        break_input_link(tree, height_blend.inputs['Prev Height'])
                    else: create_link(tree, prev_height, height_blend.inputs['Prev Height'])

                    create_link(tree, height_alpha, height_blend.inputs['Alpha'])
                    create_link(tree, height_proc.outputs['Height'], height_blend.inputs['Height'])

                    # For straight over height compare
                    if 'Prev Alpha' in height_blend.inputs:
                        create_link(tree, prev_alpha, height_blend.inputs['Prev Alpha'])
                    if 'Alpha' in height_blend.outputs:
                        height_alpha = height_blend.outputs['Alpha']

                if 'Height' in normal_proc.inputs:
                    create_link(tree, height_blend.outputs[hbout], normal_proc.inputs['Height'])

            else:

                # Overlay without write height will disconnect prev height
                if not write_height and ch.normal_blend_type == 'OVERLAY':
                    break_input_link(tree, height_blend.inputs['Prev Height ONS'])
                    break_input_link(tree, height_blend.inputs['Prev Height EW'])
                else:
                    create_link(tree, prev_height_ons, height_blend.inputs['Prev Height ONS'])
                    create_link(tree, prev_height_ew, height_blend.inputs['Prev Height EW'])

                create_link(tree, height_proc.outputs['Height ONS'], height_blend.inputs['Height ONS'])
                create_link(tree, height_proc.outputs['Height EW'], height_blend.inputs['Height EW'])
                create_link(tree, height_alpha, height_blend.inputs['Alpha'])

                if has_parent:
                    create_link(tree, prev_height_alpha_ons, height_blend.inputs['Prev Height Alpha ONS'])
                    create_link(tree, prev_height_alpha_ew, height_blend.inputs['Prev Height Alpha EW'])

                #for d in neighbor_directions:
                #    create_link(tree, alphas[d], height_blend.inputs['Alpha ' + d])

                if alpha_ns: create_link(tree, alpha_ns, height_blend.inputs['Alpha NS'])
                if alpha_ew: create_link(tree, alpha_ew, height_blend.inputs['Alpha EW'])

                if 'Height ONS' in normal_proc.inputs:
                    create_link(tree, height_blend.outputs['Height ONS'], normal_proc.inputs['Height ONS'])
                if 'Height EW' in normal_proc.inputs:
                    create_link(tree, height_blend.outputs['Height EW'], normal_proc.inputs['Height EW'])

            if 'Normal Alpha' in height_blend.outputs:
                alpha = height_blend.outputs['Normal Alpha']

            if 'Alpha' in normal_proc.inputs:
                create_link(tree, alpha, normal_proc.inputs['Alpha'])
            if 'Normal Alpha' in normal_proc.inputs:
                create_link(tree, normal_alpha, normal_proc.inputs['Normal Alpha'])

            if layer.type == 'GROUP':
                if write_height: #and 'Normal Alpha' in normal_proc.outputs:
                    alpha = normal_proc.outputs['Normal Alpha']
                #elif 'Combined Alpha' in normal_proc.outputs:
                else:
                    alpha = normal_proc.outputs['Combined Alpha']

            if tangent and bitangent and 'Tangent' in normal_proc.inputs:
                create_link(tree, tangent, normal_proc.inputs['Tangent'])
                create_link(tree, bitangent, normal_proc.inputs['Bitangent'])

            #if root_ch.type == 'NORMAL' and ch.write_height:
            if write_height:
                if ch.normal_map_type == 'BUMP_NORMAL_MAP':
                    rgb = normal_proc.outputs['Normal']
                elif 'Normal No Bump' in normal_proc.outputs:
                    rgb = normal_proc.outputs['Normal No Bump']
                else: 
                    rgb = geometry.outputs['Normal']
            else: 
                rgb = normal_proc.outputs[0]

            if not root_ch.enable_smooth_bump and not write_height:
                normal_flip = nodes.get(ch.normal_flip)
                if normal_flip:

                    if 'Tangent' in normal_flip.inputs:
                        create_link(tree, tangent, normal_flip.inputs['Tangent'])
                        create_link(tree, bitangent, normal_flip.inputs['Bitangent'])

                    rgb = create_link(tree, rgb, normal_flip.inputs[0])[0]

            if not write_height:
                if root_ch.enable_smooth_bump:
                    create_link(tree, prev_height_ons, next_height_ons)
                    create_link(tree, prev_height_ew, next_height_ew)
                else:
                    create_link(tree, prev_height, next_height)

            else:
                if root_ch.enable_smooth_bump:
                    create_link(tree, height_blend.outputs['Height ONS'], next_height_ons)
                    create_link(tree, height_blend.outputs['Height EW'], next_height_ew)
                else:
                    create_link(tree, height_blend.outputs[hbout], next_height)

            if has_parent:

                if root_ch.enable_smooth_bump:

                    if write_height:
                        create_link(tree, height_blend.outputs['Height Alpha ONS'], next_height_alpha_ons)
                        create_link(tree, height_blend.outputs['Height Alpha EW'], next_height_alpha_ew)
                    else:
                        create_link(tree, prev_height_alpha_ons, next_height_alpha_ons)
                        create_link(tree, prev_height_alpha_ew, next_height_alpha_ew)
                else:
                    if write_height:
                        create_link(tree, height_alpha, next_height_alpha)
                    else: create_link(tree, prev_height_alpha, next_height_alpha)

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
                remaining_alpha = one_value
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
                        mix_remains = nodes.get(mask.channels[i].mix_remains)
                        mr_mixcol0, mr_mixcol1, mr_mixout = get_mix_color_indices(mix_remains)
                        if mix_remains:
                            trans_ramp_input = create_link(tree, trans_ramp_input, mix_remains.inputs[mr_mixcol0])[mr_mixout]

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
        create_link(tree, rgb, blend.inputs[bcol1])

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
                #(blend_type == 'MIX' and (has_parent or (root_ch.type == 'RGB' and root_ch.enable_alpha)))
                (blend_type in {'MIX', 'COMPARE'} and (has_parent or root_ch.enable_alpha))
                or (blend_type == 'OVERLAY' and has_parent and root_ch.type == 'NORMAL')
            ):

            create_link(tree, prev_rgb, blend.inputs[0])
            create_link(tree, prev_alpha, blend.inputs[1])

            create_link(tree, alpha, blend.inputs[3])

            if bg_alpha and len(blend.inputs) > 4:
                create_link(tree, bg_alpha, blend.inputs[4])

        else:
            create_link(tree, alpha, blend.inputs[0])
            create_link(tree, prev_rgb, blend.inputs[bcol0])

        # Armory can't recognize mute node, so reconnect input to output directly
        #if layer.enable and ch.enable:
        #    create_link(tree, blend.outputs[0], next_rgb)
        #else: create_link(tree, prev_rgb, next_rgb)
        create_link(tree, blend.outputs[bout], next_rgb)

        # End alpha
        next_alpha = end.inputs.get(root_ch.name + io_suffix['ALPHA'])
        if next_alpha:
            if (
                #(blend_type != 'MIX' and (has_parent or (root_ch.type == 'RGB' and root_ch.enable_alpha)))
                (blend_type != 'MIX' and (has_parent or root_ch.enable_alpha))
                and not (blend_type == 'OVERLAY' and has_parent and root_ch.type == 'NORMAL')
                #or (has_parent and root_ch.type == 'NORMAL' and not ch.write_height)
                ):
                create_link(tree, prev_alpha, next_alpha)
            else:
                create_link(tree, blend.outputs[1], next_alpha)

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
                
                if not active_found and alpha_preview:
                    create_link(tree, source.outputs[0], alpha_preview)

            elif root_ch == yp.channels[yp.active_channel_index]:
                col_preview = end.inputs.get(LAYER_VIEWER)
                if col_preview:
                    if root_ch.type == 'NORMAL': create_link(tree, normal_proc.outputs[0], col_preview)
                    else: create_link(tree, rgb, col_preview)
                if alpha_preview and yp.layer_preview_mode_type != 'SPECIFIC_MASK':
                    create_link(tree, alpha, alpha_preview)
                
