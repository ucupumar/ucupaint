import bpy, re
from . import lib
from .common import *
from .transition_common import *
from .subtree import *
from .node_arrangements import *
from .node_connections import *

def fix_io_index_360(item, items, correct_index):
    cur_index = [i for i, it in enumerate(items) if it == item]
    if cur_index and cur_index[0] != correct_index:
        items.move(cur_index[0], correct_index)

def get_tree_input_index_400(interface, item):
    index = -1
    for it in interface.items_tree:
        if item.in_out in {'INPUT', 'BOTH'} and it.in_out in {'INPUT', 'BOTH'}:
            index += 1
        if it == item:
             return index

    return index

def get_tree_output_index_400(interface, item):
    index = -1
    for it in interface.items_tree:
        if item.in_out in {'OUTPUT', 'BOTH'} and it.in_out in {'OUTPUT', 'BOTH'}:
            index += 1
        if it == item:
             return index

    return index

def fix_tree_input_index_400(interface, item, correct_index):
    if item.in_out != 'BOTH':
        outputs = [it for it in interface.items_tree if it.in_out in {'OUTPUT', 'BOTH'}]
        offset = len(outputs)
        cur_index = [i for i, it in enumerate(interface.items_tree) if it == item]
        if cur_index and cur_index[0] != correct_index + offset:
            interface.move(item, correct_index + offset)
    else:
        if get_tree_input_index_400(interface, item) == correct_index:
            return

        # HACK: Try to move using all index because interface move is still inconsistent
        for i in range(len(interface.items_tree)):
            interface.move(item, i)
            if get_tree_input_index_400(interface, item) == correct_index:
                return

def fix_tree_output_index_400(interface, item, correct_index):
    if item.in_out != 'BOTH':
        cur_index = [i for i, it in enumerate(interface.items_tree) if it == item]
        if cur_index and cur_index[0] != correct_index:
            interface.move(item, correct_index)
    else:
        if get_tree_output_index_400(interface, item) == correct_index:
            return

        # HACK: Try to move using all index because interface move is still inconsistent
        for i in range(len(interface.items_tree)):
            interface.move(item, i)
            if get_tree_output_index_400(interface, item) == correct_index:
                return

def fix_tree_input_index(tree, item, correct_index):
    if not is_greater_than_400():
        fix_io_index_360(item, tree.inputs, correct_index)
        return

    fix_tree_input_index_400(tree.interface, item, correct_index)

def fix_tree_output_index(tree, item, correct_index):
    if not is_greater_than_400():
        fix_io_index_360(item, tree.outputs, correct_index)
        return

    fix_tree_output_index_400(tree.interface, item, correct_index)

def create_input(tree, name, socket_type, valid_inputs, index, 
        dirty = False, min_value=None, max_value=None, default_value=None, hide_value=False):

    inp = get_tree_input_by_name(tree, name)
    if not inp:
        inp = new_tree_input(tree, name, socket_type, use_both=True)
        dirty = True
        if min_value != None: inp.min_value = min_value
        if max_value != None: inp.max_value = max_value
        if default_value != None: inp.default_value = default_value
        if hasattr(inp, 'hide_value'): inp.hide_value = hide_value

    valid_inputs.append(inp)
    fix_tree_input_index(tree, inp, index)

    return dirty

def make_outputs_first_400(interface):
    outputs = []
    for i, item in enumerate(interface.items_tree):
        if item.in_out == 'OUTPUT':
            pass

def create_output(tree, name, socket_type, valid_outputs, index, dirty=False, default_value=None):

    outp = get_tree_output_by_name(tree, name)
    if not outp:
        outp = new_tree_output(tree, name, socket_type, use_both=True)
        dirty = True
        if default_value != None: outp.default_value = default_value

    valid_outputs.append(outp)
    fix_tree_output_index(tree, outp, index)

    return dirty

def check_all_channel_ios(yp, reconnect=True):
    group_tree = yp.id_data

    input_index = 0
    output_index = 0
    valid_inputs = []
    valid_outputs = []

    for ch in yp.channels:

        if ch.type == 'VALUE':
            create_input(group_tree, ch.name, channel_socket_input_bl_idnames[ch.type], 
                    valid_inputs, input_index, min_value = 0.0, max_value = 1.0)
        elif ch.type == 'RGB':
            create_input(group_tree, ch.name, channel_socket_input_bl_idnames[ch.type], 
                    valid_inputs, input_index, default_value=(1,1,1,1))
        elif ch.type == 'NORMAL':
            # Use 999 as normal z value so it will fallback to use geometry normal at checking process
            create_input(group_tree, ch.name, channel_socket_input_bl_idnames[ch.type], 
                    valid_inputs, input_index, default_value=(999,999,999), hide_value=True)

        create_output(group_tree, ch.name, channel_socket_output_bl_idnames[ch.type], 
                valid_outputs, output_index)

        if ch.io_index != input_index:
            ch.io_index = input_index

        input_index += 1
        output_index += 1

        #if ch.type == 'RGB' and ch.enable_alpha:
        if ch.enable_alpha:

            name = ch.name + io_suffix['ALPHA']

            create_input(group_tree, name, 'NodeSocketFloatFactor', valid_inputs, input_index, 
                    min_value = 0.0, max_value = 1.0, default_value = 0.0)

            create_output(group_tree, name, 'NodeSocketFloat', valid_outputs, output_index)

            input_index += 1
            output_index += 1

            # Backface mode
            if ch.backface_mode != 'BOTH':
                end_backface = check_new_node(group_tree, ch, 'end_backface', 'ShaderNodeMath', 'Backface')
                end_backface.use_clamp = True

            if ch.backface_mode == 'FRONT_ONLY':
                end_backface.operation = 'SUBTRACT'
            elif ch.backface_mode == 'BACK_ONLY':
                end_backface.operation = 'MULTIPLY'

        if not ch.enable_alpha or ch.backface_mode == 'BOTH':
                remove_node(group_tree, ch, 'end_backface')

        # Displacement IO
        if ch.type == 'NORMAL':

            name = ch.name + io_suffix['HEIGHT']

            create_input(group_tree, name, 'NodeSocketFloatFactor', valid_inputs, input_index, 
                    min_value = 0.0, max_value = 1.0, default_value = 0.5)

            create_output(group_tree, name, 'NodeSocketFloat', valid_outputs, output_index)

            input_index += 1
            output_index += 1

            name = ch.name + io_suffix['MAX_HEIGHT']
            create_output(group_tree, name, 'NodeSocketFloat', valid_outputs, output_index)

            output_index += 1

            # Add end linear for converting displacement map to grayscale
            if ch.enable_smooth_bump:
                lib_name = lib.FINE_BUMP_PROCESS
            else: lib_name = lib.BUMP_PROCESS

            end_linear = replace_new_node(group_tree, ch, 'end_linear', 'ShaderNodeGroup', 'Bump Process',
                    lib_name, hard_replace=True)

            max_height = get_displacement_max_height(ch)
            if max_height != 0.0:
                end_linear.inputs['Max Height'].default_value = max_height
            else: end_linear.inputs['Max Height'].default_value = 1.0

            if ch.enable_smooth_bump:
                end_linear.inputs['Bump Height Scale'].default_value = get_fine_bump_distance(max_height)

            # Create a node to store max height
            end_max_height = check_new_node(group_tree, ch, 'end_max_height', 'ShaderNodeValue', 'Max Height')
            end_max_height.outputs[0].default_value = max_height

        # Check clamps
        check_channel_clamp(group_tree, ch)

    if yp.layer_preview_mode:
        create_output(group_tree, LAYER_VIEWER, 'NodeSocketColor', valid_outputs, output_index)
        output_index += 1

        name = 'Layer Alpha Viewer'
        create_output(group_tree, LAYER_ALPHA_VIEWER, 'NodeSocketColor', valid_outputs, output_index)
        output_index += 1

    # Check for invalid io
    for inp in get_tree_inputs(group_tree):
        if inp not in valid_inputs:
            remove_tree_input(group_tree, inp)

    for outp in get_tree_outputs(group_tree):
        if outp not in valid_outputs:
            remove_tree_output(group_tree, outp)

    # Check uv maps
    check_uv_nodes(yp)

    # Move layer IO
    for layer in yp.layers:
        check_all_layer_channel_io_and_nodes(layer)

    if reconnect:
        # Rearrange layers
        for layer in yp.layers:
            rearrange_layer_nodes(layer)
            reconnect_layer_nodes(layer)

        # Rearrange nodes
        rearrange_yp_nodes(group_tree)
        reconnect_yp_nodes(group_tree)

def check_all_layer_channel_io_and_nodes(layer, tree=None, specific_ch=None): #, check_uvs=False): #, has_parent=False):

    yp = layer.id_data.yp
    if not tree: tree = get_tree(layer)

    # Check uv maps
    #if check_uvs:
    #    check_uv_nodes(yp)

    # Check layer tree io
    check_layer_tree_ios(layer, tree)

    # Get source_tree
    source_tree = get_source_tree(layer, tree)

    # Find override channels
    #using_vector = is_layer_using_vector(layer)

    # Mapping node
    #if layer.type not in {'BACKGROUND', 'VCOL', 'GROUP', 'COLOR'} or using_vector:
    if is_layer_using_vector(layer):
        mapping = source_tree.nodes.get(layer.mapping)
        if not mapping:
            mapping = new_node(source_tree, layer, 'mapping', 'ShaderNodeMapping', 'Mapping')

    # Flip Y
    #update_image_flip_y(self, context)

    # Linear node
    check_layer_image_linear_node(layer, source_tree)

    # Check the need of bump process
    check_layer_bump_process(layer, tree)

    # Check the need of divider alpha
    check_layer_divider_alpha(layer)

    #print(specific_ch.enable)

    # Update transition related nodes
    height_ch = get_height_channel(layer)
    if height_ch:
        check_transition_bump_nodes(layer, tree, height_ch)

    # Channel nodes
    for i, ch in enumerate(layer.channels):
        if specific_ch and specific_ch != ch: continue
        root_ch = yp.channels[i]

        # Update layer ch blend type
        check_blend_type_nodes(root_ch, layer, ch)

        if root_ch.type != 'NORMAL': # Because normal map related nodes should already created
            # Check mask mix nodes
            check_mask_mix_nodes(layer, tree, specific_ch=ch)

    # Mask nodes
    #for mask in layer.masks:
    #    check_mask_image_linear_node(mask)

    # Linear nodes
    check_yp_linear_nodes(yp, layer, False)

def check_layer_tree_ios(layer, tree=None):

    yp = layer.id_data.yp
    if not tree: tree = get_tree(layer)

    dirty = False

    input_index = 0
    output_index = 0
    valid_inputs = []
    valid_outputs = []

    has_parent = layer.parent_idx != -1
    need_prev_normal = check_need_prev_normal(layer)
    
    # Tree input and outputs
    for i, ch in enumerate(layer.channels):
        #if yp.disable_quick_toggle and not ch.enable: continue
        root_ch = yp.channels[i]

        if not (root_ch.type == 'NORMAL' and need_prev_normal) and not ch.enable:
            continue

        dirty = create_input(tree, root_ch.name, channel_socket_input_bl_idnames[root_ch.type], 
                valid_inputs, input_index, dirty)
        input_index += 1

        if root_ch.type != 'NORMAL' or not need_prev_normal or ch.enable:
            dirty = create_output(tree, root_ch.name, channel_socket_output_bl_idnames[root_ch.type], 
                    valid_outputs, output_index, dirty)
            output_index += 1

        # Alpha IO
        #if (root_ch.type == 'RGB' and root_ch.enable_alpha) or has_parent:
        if root_ch.enable_alpha or has_parent:

            name = root_ch.name + io_suffix['ALPHA']
            dirty = create_input(tree, name, 'NodeSocketFloatFactor', valid_inputs, input_index, dirty)
            input_index += 1

            if root_ch.type != 'NORMAL' or not need_prev_normal or ch.enable:
                dirty = create_output(tree, name, 'NodeSocketFloat', valid_outputs, output_index, dirty)
                output_index += 1

        # Displacement IO
        if root_ch.type == 'NORMAL':

            if not root_ch.enable_smooth_bump:

                name = root_ch.name + io_suffix['HEIGHT']
                dirty = create_input(tree, name, 'NodeSocketFloatFactor', valid_inputs, input_index, dirty)
                input_index += 1

                if not need_prev_normal or ch.enable:
                    dirty = create_output(tree, name, 'NodeSocketFloat', valid_outputs, output_index, dirty)
                    output_index += 1

                if has_parent:

                    name = root_ch.name + io_suffix['HEIGHT'] + io_suffix['ALPHA']
                    dirty = create_input(tree, name, 'NodeSocketFloatFactor', valid_inputs, input_index, dirty)
                    input_index += 1

                    if not need_prev_normal or ch.enable:
                        dirty = create_output(tree, name, 'NodeSocketFloat', valid_outputs, output_index, dirty)
                        output_index += 1

            else:

                name = root_ch.name + io_suffix['HEIGHT_ONS']
                dirty = create_input(tree, name, 'NodeSocketVector', valid_inputs, input_index, dirty)
                input_index += 1

                if not need_prev_normal or ch.enable:
                    dirty = create_output(tree, name, 'NodeSocketVector', valid_outputs, output_index, dirty)
                    output_index += 1

                name = root_ch.name + io_suffix['HEIGHT_EW']
                dirty = create_input(tree, name, 'NodeSocketVector', valid_inputs, input_index, dirty)
                input_index += 1

                if not need_prev_normal or ch.enable:
                    dirty = create_output(tree, name, 'NodeSocketVector', valid_outputs, output_index, dirty)
                    output_index += 1

                if has_parent:

                    name = root_ch.name + io_suffix['HEIGHT_ONS'] + io_suffix['ALPHA']
                    dirty = create_input(tree, name, 'NodeSocketVector', valid_inputs, input_index, dirty)
                    input_index += 1

                    if not need_prev_normal or ch.enable:
                        dirty = create_output(tree, name, 'NodeSocketVector', valid_outputs, output_index, dirty)
                        output_index += 1

                    name = root_ch.name + io_suffix['HEIGHT_EW'] + io_suffix['ALPHA']
                    dirty = create_input(tree, name, 'NodeSocketVector', valid_inputs, input_index, dirty)
                    input_index += 1

                    if not need_prev_normal or ch.enable:
                        dirty = create_output(tree, name, 'NodeSocketVector', valid_outputs, output_index, dirty)
                        output_index += 1

                #for d in neighbor_directions:

                #    name = root_ch.name + io_suffix['HEIGHT'] + ' ' + d
                #    dirty = create_input(tree, name, 'NodeSocketFloatFactor', valid_inputs, input_index, dirty)
                #    dirty = create_output(tree, name, 'NodeSocketFloat', valid_outputs, output_index, dirty)
                #    input_index += 1
                #    output_index += 1

                #    if has_parent:

                #        name = root_ch.name + io_suffix['ALPHA'] + ' ' + d
                #        dirty = create_input(tree, name, 'NodeSocketFloatFactor', valid_inputs, input_index, dirty)
                #        dirty = create_output(tree, name, 'NodeSocketFloat', valid_outputs, output_index, dirty)
                #        input_index += 1
                #        output_index += 1

    # Tree background inputs
    if layer.type in {'BACKGROUND', 'GROUP'}:

        for i, ch in enumerate(layer.channels):
            #if yp.disable_quick_toggle and not ch.enable: continue
            if not ch.enable: continue

            root_ch = yp.channels[i]

            name = root_ch.name + io_suffix[layer.type]
            dirty = create_input(tree, name, channel_socket_input_bl_idnames[root_ch.type],
                    valid_inputs, input_index, dirty)
            input_index += 1

            # Alpha Input
            if root_ch.enable_alpha or layer.type == 'GROUP':

                name = root_ch.name + io_suffix['ALPHA'] + io_suffix[layer.type]
                dirty = create_input(tree, name, 'NodeSocketFloatFactor',
                        valid_inputs, input_index, dirty)
                input_index += 1

            # Displacement Input
            if root_ch.type == 'NORMAL' and layer.type == 'GROUP':

                if not root_ch.enable_smooth_bump:

                    name = root_ch.name + io_suffix['HEIGHT'] + io_suffix['GROUP']
                    dirty = create_input(tree, name, 'NodeSocketFloat',
                            valid_inputs, input_index, dirty)
                    input_index += 1

                    name = root_ch.name + io_suffix['HEIGHT'] + io_suffix['ALPHA'] + io_suffix['GROUP']
                    dirty = create_input(tree, name, 'NodeSocketFloat',
                            valid_inputs, input_index, dirty)
                    input_index += 1

                else:

                    name = root_ch.name + io_suffix['HEIGHT_ONS'] + io_suffix['GROUP']
                    dirty = create_input(tree, name, 'NodeSocketVector', valid_inputs, input_index, dirty)
                    input_index += 1

                    name = root_ch.name + io_suffix['HEIGHT_EW'] + io_suffix['GROUP']
                    dirty = create_input(tree, name, 'NodeSocketVector', valid_inputs, input_index, dirty)
                    input_index += 1

                    name = root_ch.name + io_suffix['HEIGHT_ONS'] + io_suffix['ALPHA'] + io_suffix['GROUP']
                    dirty = create_input(tree, name, 'NodeSocketVector', valid_inputs, input_index, dirty)
                    input_index += 1

                    name = root_ch.name + io_suffix['HEIGHT_EW'] + io_suffix['ALPHA'] + io_suffix['GROUP']
                    dirty = create_input(tree, name, 'NodeSocketVector', valid_inputs, input_index, dirty)
                    input_index += 1

                    #for d in neighbor_directions:
                    #    name = root_ch.name + io_suffix['HEIGHT'] + ' ' + d + io_suffix['GROUP']

                    #    dirty = create_input(tree, name, 'NodeSocketFloat', valid_inputs, input_index, dirty)
                    #    input_index += 1

                    #    name = (root_ch.name + 
                    #            #io_suffix['HEIGHT'] + ' ' + 
                    #            io_suffix['ALPHA'] + ' ' + 
                    #            d + io_suffix['GROUP'])

                    #    dirty = create_input(tree, name, 'NodeSocketFloatFactor', valid_inputs, input_index, dirty)
                    #    input_index += 1

    # UV necessary container
    uv_names = []

    # Check height root channel
    height_root_ch = get_root_height_channel(yp)
    height_ch = get_height_channel(layer)
    if height_root_ch and height_root_ch.main_uv != '' and height_root_ch.main_uv not in uv_names:
        uv_names.append(height_root_ch.main_uv)

    # Add main UV if need previous normal
    if need_prev_normal and height_root_ch.main_uv != '':
        uv_names.append(height_root_ch.main_uv)

    # Check layer uv
    if layer.texcoord_type == 'UV' and layer.uv_name not in uv_names and layer.uv_name != '':
        uv_names.append(layer.uv_name)

    # Check masks uvs
    for mask in layer.masks:
        if mask.texcoord_type == 'UV' and mask.uv_name not in uv_names and mask.uv_name != '':
            uv_names.append(mask.uv_name)

    #print(height_root_ch.main_uv)

    # Create inputs
    for uv_name in uv_names:
        name = uv_name + io_suffix['UV']
        dirty = create_input(tree, name, 'NodeSocketVector', valid_inputs, input_index, dirty)
        input_index += 1

        #print(uv_name)

        #if height_ch and not (yp.disable_quick_toggle and not height_ch.enable):
        if (height_ch and height_ch.enable) or (need_prev_normal and uv_name == height_root_ch.main_uv):

            name = uv_name + io_suffix['TANGENT']
            dirty = create_input(tree, name, 'NodeSocketVector', valid_inputs, input_index, dirty)
            input_index += 1

            name = uv_name + io_suffix['BITANGENT']
            dirty = create_input(tree, name, 'NodeSocketVector', valid_inputs, input_index, dirty)
            input_index += 1

    # Other than uv texcoord name container
    texcoords = []

    # Check layer texcoords
    if layer.texcoord_type != 'UV':
        texcoords.append(layer.texcoord_type)

    for mask in layer.masks:
        if mask.texcoord_type != 'UV' and mask.texcoord_type not in texcoords:
            texcoords.append(mask.texcoord_type)

    for texcoord in texcoords:
        name = io_names[texcoord]
        dirty = create_input(tree, name, 'NodeSocketVector', valid_inputs, input_index, dirty)
        input_index += 1

    if yp.layer_preview_mode:
        dirty = create_output(tree, LAYER_VIEWER, 'NodeSocketColor', valid_outputs, output_index, dirty)
        output_index += 1

        dirty = create_output(tree, LAYER_ALPHA_VIEWER, 'NodeSocketColor', valid_outputs, output_index, dirty)
        output_index += 1

    # Check for invalid io
    for inp in get_tree_inputs(tree):
        if inp not in valid_inputs:
            remove_tree_input(tree, inp)

    for outp in get_tree_outputs(tree):
        if outp not in valid_outputs:
            remove_tree_output(tree, outp)

    return dirty

