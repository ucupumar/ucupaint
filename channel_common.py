import bpy
from .common import *
from .input_outputs import *
from .node_arrangements import *
from .node_connections import *
from . import transition_common

AO_MULTIPLY = 'yP AO Multiply'

def check_yp_channel_nodes(yp, reconnect=False):

    # Link between layers
    for layer in yp.layers:
        layer_tree = get_tree(layer)
        
        # Make sure the number of channels are correct
        num_difference = len(yp.channels) - len(layer.channels)
        if num_difference > 0:
            for i in range(num_difference):
                # Add new channel
                c = layer.channels.add()
        elif num_difference < 0:
            for i in range(abs(num_difference)):
                last_idx = len(layer.channels)-1
                # Remove layer channel
                layer.channels.remove(last_idx)
    
        for mask in layer.masks:
            num_difference = len(yp.channels) - len(mask.channels)
            if num_difference > 0:
                for i in range(num_difference):
                    # Add new channel to mask
                    mc = mask.channels.add()
            elif num_difference < 0:
                for i in range(abs(num_difference)):
                    last_idx = len(mask.channels)-1
                    # Remove mask channel
                    mask.channels.remove(last_idx)

        # Check and set mask intensity nodes
        transition_common.check_transition_bump_influences_to_other_channels(layer, layer_tree) #, target_ch=c)

        # Set mask multiply nodes
        check_mask_mix_nodes(layer, layer_tree)

        # Add new nodes
        check_all_layer_channel_io_and_nodes(layer, layer_tree) #, specific_ch=c)

    # Check uv maps
    check_uv_nodes(yp)

    if reconnect:
        for layer in yp.layers:
            reconnect_layer_nodes(layer)
            rearrange_layer_nodes(layer)

        reconnect_yp_nodes(yp.id_data)
        rearrange_yp_nodes(yp.id_data)

def create_new_yp_channel(group_tree, name, channel_type, non_color=True, enable=False, special_type='NONE', add_bake_target=True):
    yp = group_tree.yp

    yp.halt_reconnect = True

    # Add new channel
    channel = yp.channels.add()
    channel.name = get_unique_name(name, yp.channels)
    channel.original_name = name
    channel.bake_to_vcol_name = 'Baked ' + channel.name
    channel.type = channel_type
    channel.special_type = special_type

    # Get last index
    last_index = len(yp.channels) - 1

    # Link new channel
    check_yp_channel_nodes(yp)

    for layer in yp.layers:
        # New channel is disabled in layer by default
        layer.channels[last_index].enable = enable

        # For normal channel, set default channel override color to default normal
        if special_type == 'NORMAL':
            layer.channels[last_index].override_color = (0.5, 0.5, 1.0)

    if channel_type in {'RGB', 'VALUE'}:
        if non_color:
            channel.colorspace = 'LINEAR'
        else: channel.colorspace = 'SRGB'
    else:
        # NOTE: Smooth bump is no longer enabled by default for realtime bump capable blender
        if is_bl_newer_than(2, 78): 
            channel.enable_smooth_bump = False

    # Special Bake target setup
    alpha_bt_setup = False
    if special_type == 'ALPHA':
        color_chs = [c for c in yp.channels if c.type == 'RGB']
        if any(color_chs): 
            color_bt = add_alpha_to_color_bt(color_chs[0], channel)
            if color_bt != None: alpha_bt_setup = True

    # Add bake_target
    bt = None
    if add_bake_target and not alpha_bt_setup:
        bt = yp.bake_targets.add()
        bt.name = get_unique_name(group_tree.name.replace(get_addon_title()+' ', '') + ' ' + name, bpy.data.images)

        #bt.use_float = self.use_float
        bt.a.default_value = 1.0

        bt.r.channel_name = name
        bt.r.subchannel_index = '0'

        bt.g.channel_name = name
        bt.g.subchannel_index = '1'

        bt.b.channel_name = name
        bt.b.subchannel_index = '2'

        bt.data_type = 'IMAGE'

        if hasattr(bpy.context, 'object'):
            bt.uv_map = get_default_uv_name(bpy.context.object, yp)

        # Set denoise default values
        bt.denoise = False

        if special_type == 'HEIGHT':
            bt.interpolation = 'Cubic'

        if special_type == 'NORMAL':
            bt.fxaa = False

            # Extra normal without bump if height channel exists
            height_root_ch = get_root_height_channel(yp)
            if height_root_ch:
                extra_bt = yp.bake_targets.add()
                extra_bt.name = get_unique_name(group_tree.name.replace(get_addon_title()+' ', '') + ' ' + name + ' without Height', bpy.data.images)

                extra_bt.a.default_value = 1.0

                extra_bt.r.channel_name = name
                extra_bt.r.subchannel_index = '0'

                extra_bt.g.channel_name = name
                extra_bt.g.subchannel_index = '1'

                extra_bt.b.channel_name = name
                extra_bt.b.subchannel_index = '2'

                extra_bt.data_type = 'IMAGE'

                extra_bt.normal_includes_height = False

                extra_bt.fxaa = False
                extra_bt.denoise  = False

                if hasattr(bpy.context, 'object'):
                    extra_bt.uv_map = get_default_uv_name(bpy.context.object, yp)
        else:
            # FXAA is enabled by default
            bt.fxaa = True

    if bt: channel.bake_target_name = bt.name
        
    yp.halt_reconnect = False

    return channel

def set_input_default_value(group_node, channel, custom_value=None):

    if custom_value:
        if channel.type == 'RGB' and len(custom_value) == 3:
            custom_value = (custom_value[0], custom_value[1], custom_value[2], 1)

        group_node.inputs[channel.name].default_value = custom_value
        return
    
    # Set default value
    if channel.type == 'RGB':
        group_node.inputs[channel.name].default_value = (1, 1, 1, 1)

    if channel.type == 'VALUE':
        group_node.inputs[channel.name].default_value = 0.0

    if channel.type == 'VECTOR':
        if channel.special_type == 'NORMAL':
            # Use 999 as normal z value so it will fallback to use geometry normal at checking process
            group_node.inputs[channel.name].default_value = (999, 999, 999)
        else: group_node.inputs[channel.name].default_value = (0.0, 0.0, 0.0)

    if channel.enable_alpha:
        group_node.inputs[channel.name + io_suffix['ALPHA']].default_value = 1.0

def set_default_height_channel_prop(channel):
    yp = channel.id_data.yp

    yp.halt_update = True

    # Disable smooth bump by default
    if is_bl_newer_than(2, 77):
        channel.enable_smooth_bump = False

    # NOTE: Height as bump is default for all blender versions 
    # since Cycles doesn't produce correct bump if material displacement setting is set to `Bump Only`.
    # Also overlay blending will cause extra bump normal on displaced surface
    #if not is_bl_newer_than(4, 2):
    channel.use_height_as_bump = True

    yp.halt_update = False

def is_node_a_displacement(node, is_vector_disp=False):
    if not is_bl_newer_than(2, 80):
        if is_vector_disp: return None
        return node.type == 'GROUP' and node.node_tree and node.node_tree.name == lib.BL27_DISP

    if is_vector_disp: return node.type == 'VECTOR_DISPLACEMENT'
    return node.type == 'DISPLACEMENT'

def get_closest_disp_node_backward(node, socket_name='', is_vector_disp=False):

    # Get input list
    if socket_name != '':
        inp = node.inputs.get(socket_name)
        if not inp: return None
        inputs = [inp]
    else: inputs = node.inputs

    # Search for displacement node
    for inp in inputs:
        for link in inp.links:
            n = link.from_node
            if is_node_a_displacement(n, is_vector_disp=is_vector_disp):
                return n
            else:
                n = get_closest_disp_node_backward(n, is_vector_disp=is_vector_disp)
                if n: return n

    return None

def create_vector_displacement_node(tree, connect_to=None):
    vdisp = None
    if is_bl_newer_than(2, 80):
        vdisp = tree.nodes.new('ShaderNodeVectorDisplacement')

        # Make sure vector displacement node has 1.0 scale
        if 'Scale' in vdisp.inputs:
            vdisp.inputs['Scale'].default_value = 1.0

    if vdisp and connect_to:
        create_link(tree, vdisp.outputs[0], connect_to)

    return vdisp

def create_displacement_node(tree, connect_to=None):
    if is_bl_newer_than(2, 80):
        disp = tree.nodes.new('ShaderNodeDisplacement')
    else:
        # Set displacement mode
        disp = tree.nodes.new('ShaderNodeGroup')
        disp.node_tree = get_node_tree_lib(lib.BL27_DISP)

    if connect_to:
        create_link(tree, disp.outputs[0], connect_to)

    return disp

def do_displacement_node_setup(mat, node, channel, is_vector_disp=False):

    matout = get_material_output(mat)

    disp_inp = matout.inputs.get('Displacement')
    channel_outp = node.outputs.get(channel.name)
    max_height_outp = node.outputs.get(channel.name + io_suffix['SCALE']) if not is_vector_disp else None
    midlevel_outp = node.outputs.get(channel.name + io_suffix['MIDLEVEL']) if not is_vector_disp else None

    loc = matout.location.copy()
    loc.y -= 170

    # Check for existing displacement node
    disp = None
    combine_node_needed = False
    if len(disp_inp.links) > 0:
        # Get closest displacement node if there's a link
        disp = get_closest_disp_node_backward(matout, 'Displacement', is_vector_disp=is_vector_disp)

        # Get relevant input sockets and check if they're connected or not
        if disp:
            if is_vector_disp: 
                inp = disp.inputs.get('Vector')
                if len(inp.links) > 0 and inp.links[0].from_node != node: disp = None
            else: 
                inp = disp.inputs.get('Height')
                if len(inp.links) > 0 and inp.links[0].from_node != node: disp = None
                if channel.use_height_as_bump:
                    inp = disp.inputs.get('Scale')
                    if len(inp.links) > 0 and inp.links[0].from_node != node: disp = None
                    inp = disp.inputs.get('Midlevel')
                    if len(inp.links) > 0 and inp.links[0].from_node != node: disp = None

        # Need combine node if there's connection but no valid displacement node
        if disp == None:
            combine_node_needed = True

    # Create new displacement node
    disp_created = False
    if disp == None:
        if is_vector_disp: 
            disp = create_vector_displacement_node(mat.node_tree)
        else: disp = create_displacement_node(mat.node_tree)

        # Default scale of displacement is 1.0
        if 'Scale' in disp.inputs: disp.inputs['Scale'].default_value = 1.0
        disp_created = True

        # Default vector is (0.0, 0.0, 0.0)
        if 'Vector' in disp.inputs: 
            disp.inputs['Vector'].default_value[0] = 0.0
            disp.inputs['Vector'].default_value[1] = 0.0
            disp.inputs['Vector'].default_value[2] = 0.0

        # Default midlevel is 0.0
        if 'Midlevel' in disp.inputs: 
            disp.inputs['Midlevel'].default_value = 0.0

    connect_to = disp_inp

    if combine_node_needed:
        from_node = disp_inp.links[0].from_node
        from_soc = disp_inp.links[0].from_socket
        
        # Create add node
        combine_disp = mat.node_tree.nodes.new('ShaderNodeVectorMath')
        combine_disp.operation = 'ADD'

        # Set locations
        combine_disp.location = loc.copy()
        combine_disp.hide = True

        loc.y -= 50

        # Offset original socket node a bit
        from_node.location.y -= 220

        # Connect add vector node
        connect_to = combine_disp.inputs[0]
        mat.node_tree.links.new(from_soc, combine_disp.inputs[1])
        mat.node_tree.links.new(combine_disp.outputs[0], disp_inp)

    # Set node position and connection if displacement node is just created
    if disp_created:
        disp.location = loc.copy()

        # Connect displacement node
        mat.node_tree.links.new(disp.outputs[0], connect_to)

    if channel_outp:
        if is_vector_disp:
            mat.node_tree.links.new(channel_outp, disp.inputs.get('Vector'))
        else: mat.node_tree.links.new(channel_outp, disp.inputs.get('Height'))
    if max_height_outp and 'Scale' in disp.inputs:
        mat.node_tree.links.new(max_height_outp, disp.inputs.get('Scale'))
    if midlevel_outp and 'Midlevel' in disp.inputs:
        mat.node_tree.links.new(midlevel_outp, disp.inputs.get('Midlevel'))

    return disp

def do_alpha_setup(mat, node, channel):
    tree = mat.node_tree
    yp = node.node_tree.yp
    default_value = 1.0

    if channel.enable_alpha:
        alpha_input = node.inputs.get(channel.name + io_suffix['ALPHA'])
        alpha_output = node.outputs.get(channel.name + io_suffix['ALPHA'])
        output = node.outputs.get(channel.name)
    else:
        alpha_input = node.inputs[channel.name]
        alpha_output = node.outputs[channel.name]

        try: color_ch = yp.channels[channel.alpha_pair_name]
        except Exception as e:
            print(e)
            return default_value

        output = node.outputs[color_ch.name]

    # Main channel output need to be already connected
    if len(output.links) == 0:
        return default_value

    alpha_input_connected = len(alpha_input.links) > 0
    new_nodes_created = False
    for i, l in enumerate(output.links):

        if is_valid_bsdf_node(l.to_node) or l.to_node.type == 'OUTPUT_MATERIAL':
            target_node = l.to_node
        else: target_node = get_closest_bsdf_forward(l.to_node)
        if not target_node: continue
        target_socket = None

        # Connect to alpha input if target node has one
        if 'Alpha' in target_node.inputs:
            target_socket = target_node.inputs['Alpha']

        # Search for transparent and mix bsdf
        if not target_socket and len(target_node.outputs) > 0:

            # Check if target node is mix and has transparent bsdf connected to it
            if target_node.type == 'MIX_SHADER':
                if len(target_node.inputs[1].links) > 0 and target_node.inputs[1].links[0].from_node.type == 'BSDF_TRANSPARENT':
                    target_socket = target_node.inputs[0]
                
            if not target_socket:
                # Check if node following target node is mix and has transparent bsdf connected to it
                for l in target_node.outputs[0].links:
                    if l.to_node.type == 'MIX_SHADER':
                        for n in l.to_node.inputs[1].links:
                            if n.from_node.type == 'BSDF_TRANSPARENT':
                                target_socket = l.to_node.inputs[0]

        # Create new transparent and mix bsdf if target node is BSDF
        if not target_socket and not new_nodes_created and any([o for o in target_node.outputs if o.type == 'SHADER']):
            # Shift some nodes to the right
            for n in tree.nodes:
                if n.location.x > target_node.location.x and n.location.x < target_node.location.x + 350:
                    n.location.x += 200

            mix_bsdf = tree.nodes.new('ShaderNodeMixShader')
            mix_bsdf.location = (target_node.location.x + 200, target_node.location.y)
            mix_bsdf.inputs[0].default_value = 1.0
            transp_bsdf = tree.nodes.new('ShaderNodeBsdfTransparent')
            transp_bsdf.location = (target_node.location.x, target_node.location.y + 100)

            final_sockets = []
            if len(target_node.outputs) > 0:
                final_sockets = [l.to_socket for l in target_node.outputs[0].links]
                tree.links.new(target_node.outputs[0], mix_bsdf.inputs[2])
            tree.links.new(transp_bsdf.outputs[0], mix_bsdf.inputs[1])
            target_socket = mix_bsdf.inputs[0]
            if final_sockets: 
                tree.links.new(mix_bsdf.outputs[0], final_sockets[0])

            new_nodes_created = True

        # Create new transparent and mix bsdf if target node is output material
        if not target_socket and not new_nodes_created and target_node.type == 'OUTPUT_MATERIAL':
            # Shift some nodes to the right
            for n in tree.nodes:
                if n.location.x > node.location.x and n.location.x < node.location.x + 350:
                    n.location.x += 200

            mix_bsdf = tree.nodes.new('ShaderNodeMixShader')
            mix_bsdf.location = (node.location.x + 200, node.location.y)
            mix_bsdf.inputs[0].default_value = 1.0
            transp_bsdf = tree.nodes.new('ShaderNodeBsdfTransparent')
            transp_bsdf.location = (node.location.x, node.location.y + 100)

            ori_targets = [l.to_socket for l in output.links]
            tree.links.new(output, mix_bsdf.inputs[2])
            tree.links.new(transp_bsdf.outputs[0], mix_bsdf.inputs[1])
            target_socket = mix_bsdf.inputs[0]

            for ot in ori_targets:
                tree.links.new(mix_bsdf.outputs[0], ot)

            new_nodes_created = True

        if not target_socket: continue

        # Connect the original target socket connection to channel alpha input
        if len(target_socket.links) > 0 and not alpha_input_connected and target_socket.links[0].from_node != node:
            tree.links.new(target_socket.links[0].from_socket, alpha_input)
            alpha_input_connected = True

        # Only connect to target socket if the original connection isn't from yp node
        if len(target_socket.links) == 0 or target_socket.links[0].from_node != node:
            tree.links.new(alpha_output, target_socket)
            default_value = target_socket.default_value

    return default_value

def set_material_methods(mat, blend_method='HASHED', shadow_method='HASHED'):
    if not is_bl_newer_than(4, 2):
        if is_bl_newer_than(2, 80):
            # EEVEE legacy doesn't use alpha dither by default
            mat.blend_method = blend_method
            mat.shadow_method = shadow_method
        else:
            # There's no alpha dither on legacy blender
            mat.game_settings.alpha_blend = 'ALPHA'

def add_alpha_to_color_bt(color_ch, alpha_ch):
    yp = color_ch.id_data.yp

    for bt in yp.bake_targets:
        if (bt.r.channel_name == color_ch.name and bt.r.subchannel_index == '0' and
            bt.g.channel_name == color_ch.name and bt.g.subchannel_index == '1' and
            bt.b.channel_name == color_ch.name and bt.b.subchannel_index == '2' and
            bt.a.channel_name == ''
        ):
            bt.a.channel_name = alpha_ch.name
            alpha_ch.bake_target_name = bt.name
            return bt

    return None

def set_channel_index(channel, new_index, move_fcurves=True):
    yp = channel.id_data.yp

    index = get_channel_index(channel)

    if index == new_index:
        return

    # Remove props first
    check_all_channel_ios(yp, reconnect=False, remove_props=True)

    # Move channel
    yp.channels.move(index, new_index)
    if move_fcurves:
        swap_channel_fcurves(yp, index, new_index)

    # Move layer channels
    for layer in yp.layers:
        layer.channels.move(index, new_index)
        if move_fcurves:
            swap_layer_channel_fcurves(layer, index, new_index)

        # Move mask channels
        for mask in layer.masks:
            mask.channels.move(index, new_index)
            if move_fcurves:
                swap_mask_channel_fcurves(mask, index, new_index)

    # Move IO
    check_all_channel_ios(yp)

def make_channel_as_alpha(mat, node, channel, do_setup=False, move_index=False, ch_pair_name=''):
    yp = channel.id_data.yp
    if channel.type != 'VALUE': return

    # Mark channel as alpha
    channel.special_type = 'ALPHA'

    color_ch = None
    color_idx = -1
    if ch_pair_name != '':
        color_ch = yp.channels.get(ch_pair_name)
        if color_ch: color_idx = get_channel_index(color_ch)

    if color_ch:
        yp.halt_update = True
        channel.alpha_pair_name = color_ch.name
        yp.halt_update = False

    # Move channel to below color channel
    if move_index and color_ch:
        set_channel_index(channel, color_idx+1)

        # Repoint channel to alpha channel since the orders are changed
        color_ch, alpha_ch = get_color_alpha_ch_pairs(yp)
        channel = alpha_ch

    # Update io since alpha is enabled on all color layers
    check_all_channel_ios(yp, yp_node=node)

    if do_setup:
        # Set up alpha connections
        default_value = do_alpha_setup(mat, node, channel)
        node.inputs[channel.name].default_value = default_value

    # Bake target setup with the color channel
    color_ch = yp.channels.get(ch_pair_name)
    if color_ch: add_alpha_to_color_bt(color_ch, channel)

def create_ao_node(mat, node, channel=None, shift_other_nodes=False):

    ao_mul = simple_new_mix_node(mat.node_tree)
    ao_mixcol0, ao_mixcol1, ao_mixout = get_mix_color_indices(ao_mul)

    # Set blend node
    ao_mul.inputs[0].default_value = 1.0
    ao_mul.blend_type = 'MULTIPLY'
    ao_mul.label = get_addon_title() + ' AO Multiply'
    ao_mul.name = AO_MULTIPLY

    # Set default value
    ao_mul.inputs[0].default_value = 1.0
    ao_mul.inputs[ao_mixcol0].default_value = (1.0, 1.0, 1.0, 1.0)
    ao_mul.inputs[ao_mixcol1].default_value = (1.0, 1.0, 1.0, 1.0)

    # Set AO multiply node location
    loc = node.location.copy()
    loc.x += 200
    ao_mul.location = loc

    # Shift other nodes
    if shift_other_nodes:
        for n in mat.node_tree.nodes:
            if n in {ao_mul, node}: continue
            if n.location.x > node.location.x:
                n.location.x += 200

    # Connect node outputs to AO multiply
    if channel:
        yp = channel.id_data.yp

        # Get first color channel
        ch_color = None
        for ch in yp.channels:
            if ch.type == 'RGB':
                ch_color = ch
                break

        if ch_color and ch_color.name in node.outputs: 

            outp = node.outputs[ch_color.name]

            # Check original color connections
            to_sockets = []
            for link in outp.links:
                to_sockets.append(link.to_socket)

            # Connect to original socket connections
            for soc in to_sockets:
                mat.node_tree.links.new(ao_mul.outputs[ao_mixout], soc)

            # Connect color channel to AO multiply
            mat.node_tree.links.new(outp, ao_mul.inputs[ao_mixcol0])

        # Connect AO channel to AO multiply
        if channel.name in node.outputs: 
            mat.node_tree.links.new(node.outputs[channel.name], ao_mul.inputs[ao_mixcol1])

        # Set default value
        if channel.name in node.inputs: 
            node.inputs[channel.name].default_value = (1, 1, 1, 1)

    return ao_mul

def auto_setup_active_yp_new_channel(mode, channel_pair_name='', blend_method='HASHED', shadow_method='HASHED'):
    mat = get_active_material()
    node = get_active_ypaint_node()
    group_tree = node.node_tree
    yp = group_tree.yp

    ch_name = 'Channel'
    if mode == 'AO':
        ch_name = 'Ambient Occlusion'
        ch_type = 'RGB'
    elif mode == 'ALPHA':
        ch_name = 'Alpha'
        ch_type = 'VALUE'
    elif mode == 'HEIGHT':
        ch_name = 'Height'
        ch_type = 'VALUE'
    elif mode == 'NORMAL':
        ch_name = 'Normal'
        ch_type = 'VECTOR'
    elif mode == 'VDISP':
        ch_name = 'Vector Displacement'
        ch_type = 'RGB'

    # Check if channel with same name is already available
    same_channel = [c for c in yp.channels if c.name == ch_name]
    if same_channel:
        return "Channel named '"+ch_name+"' is already available!"

    if mode in {'ALPHA', 'HEIGHT', 'VDISP'}:
        existing_special_channels = [c for c in yp.channels if c.special_type == mode]
        if any(existing_special_channels):
            return "Special channel already exists ('"+existing_special_channels[0].name+"')!"

    if mode in {'ALPHA', 'AO'}:
        color_chs = [c for c in yp.channels if c.type == 'RGB']
        if not any(color_chs):
            return "Need at least one existing color channel!"

    ori_use_baked = yp.use_baked
    if yp.use_baked and yp.enable_baked_outside:
        yp.use_baked = False
        ori_use_baked = True

    # Check for normal input
    normal_inp = None
    if mode == 'NORMAL':
        # Get available channel connections
        for ch in yp.channels:
            outp = node.outputs.get(ch.name)
            if outp and len(outp.links) > 0:
                for link in outp.links:
                    for inp in link.to_node.inputs:
                        if inp.name == 'Normal':
                            normal_inp = inp
                            break
                    if normal_inp != None: break
            if normal_inp != None: break

        if normal_inp == None:
            if yp.use_baked != ori_use_baked:
                yp.use_baked = True
            return "There's no proper normal input found in the material nodes!"

    special_type = 'NONE'
    if mode in {'HEIGHT', 'NORMAL', 'VDISP'}:
        special_type = mode

    orm_bt = None
    # Get ORM Bake target
    if mode == 'AO':
        for bt in yp.bake_targets:
            img_node = node.node_tree.get(bt.baked_node)
            bt_name = img_node.image.name if img_node and img_node.image else bt.name
            if bt_name.endswith(' ORM') and bt.r.channel_name == '':
                orm_bt = bt
                break

    # Only add bake target when necessary
    add_bake_target = mode not in {'ALPHA', 'AO'} or (mode == 'AO' and not orm_bt)

    # Create new channel
    channel = create_new_yp_channel(group_tree, ch_name, ch_type, non_color=True, special_type=special_type, add_bake_target=add_bake_target)
    actual_ch_name = channel.name

    # Add AO to ORM bake target
    if mode == 'AO' and orm_bt:
        orm_bt.r.channel_name = channel.name
        orm_bt.r.subchannel_index = '3'

    # Make sure height will use `Height as Bump` by default
    if mode == 'HEIGHT':
        set_default_height_channel_prop(channel)

    # Update io
    check_all_channel_ios(yp, yp_node=node)

    # Create the node setup
    if mode == 'AO':
        create_ao_node(mat, node, channel, shift_other_nodes=True)
    elif mode == 'ALPHA':
        make_channel_as_alpha(mat, node, channel, do_setup=True, move_index=True, ch_pair_name=channel_pair_name)
        set_material_methods(mat, blend_method, shadow_method)
    elif mode == 'HEIGHT':
        if not channel.use_height_as_bump:
            do_displacement_node_setup(mat, node, channel, is_vector_disp=False)
    elif mode == 'NORMAL':
        outp = node.outputs.get(channel.name)
        mat.node_tree.links.new(outp, normal_inp)
        set_input_default_value(node, channel)
    elif mode == 'VDISP':
        do_displacement_node_setup(mat, node, channel, is_vector_disp=True)

    # Set active channel to the newly created one
    channel = yp.channels.get(actual_ch_name)
    yp.active_channel_index = get_channel_index(channel)

    if yp.use_baked != ori_use_baked:
        yp.use_baked = True

    # Automatically enable new layer channel for group and background layers
    for layer in yp.layers:
        if layer.type in {'GROUP', 'BACKGROUND'}:
            layer.channels[yp.active_channel_index].enable = True

    return ''

